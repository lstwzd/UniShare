import socket
import json
import struct
import threading
from typing import Dict, Optional, Tuple

from src.unishare.modules.base import BaseModule
from src.unishare.core.config import config
from src.unishare.core.logger import log
from src.unishare.core.connection import connection_manager
from src.unishare.utils.inputleap import InputLeapBackend, get_backend
from src.unishare.utils.inputleap.screen_layout import ScreenLayoutManager, Direction
from src.unishare.utils.inputleap.smooth import MouseSmoother


class InputLeapModule(BaseModule):
    """
    键鼠共享模块
    纯 Python 实现，基于 pynput 库
    通过 TCP 协议在设备间同步键盘鼠标事件
    支持屏幕边界检测和鼠标平滑
    """

    def __init__(self):
        super().__init__("InputLeap 键鼠共享模块")
        self.enabled = config.get("input_share.enabled", True)
        self.mode = config.get("mode", "client")
        self.server_ip = config.get("server_ip", "127.0.0.1")
        self.server_port = 24800

        self.server_socket = None
        self.client_socket = None
        self.running_thread = None
        self._backend = get_backend()
        
        self.screen_layout = ScreenLayoutManager()
        self.mouse_smoother = MouseSmoother()
        self._control_active = True
        
        if self._backend:
            self.log_info(f"后端: {self._backend.get_name()}")

    def start(self):
        if not self.enabled:
            self.log_info("InputLeap 功能已关闭")
            return
        if not self._backend:
            self.log_error("无可用后端")
            return

        self.is_running = True
        self._init_screen_layout()
        connection_manager.start()

        if self.mode == "server":
            self._start_server()
        else:
            self._start_client()

        self.log_info(f"InputLeap 模块启动成功 (模式：{self.mode})")

    def _init_screen_layout(self):
        """初始化屏幕布局"""
        try:
            import mss
            with mss.mss() as sct:
                if sct.monitors:
                    monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                    self.screen_layout.add_screen(
                        device_id="local",
                        width=monitor["width"],
                        height=monitor["height"],
                        position=(monitor["left"], monitor["top"]),
                        is_local=True
                    )
                    self.log_info(f"本地屏幕: {monitor['width']}x{monitor['height']}")
        except Exception as e:
            self.log_warning(f"初始化屏幕布局失败: {e}")
            self.screen_layout.add_screen(
                device_id="local",
                width=1920,
                height=1080,
                position=(0, 0),
                is_local=True
            )
        
        self.screen_layout.set_switch_callback(self._on_screen_switch)

    def _on_screen_switch(self, from_device: str, to_device: str, position: Optional[Tuple[int, int]]):
        """屏幕切换回调"""
        self.log_info(f"屏幕切换: {from_device} -> {to_device}")
        if to_device != "local":
            self._control_active = False
        else:
            self._control_active = True

    def add_remote_screen(self, device_id: str, width: int, height: int, 
                          position: Tuple[int, int], direction: str = "right"):
        """添加远程屏幕到布局"""
        self.screen_layout.add_screen(device_id, width, height, position, is_local=False)
        self.log_info(f"添加远程屏幕: {device_id} {width}x{height} at {position}")

    def remove_remote_screen(self, device_id: str):
        """移除远程屏幕"""
        self.screen_layout.remove_screen(device_id)
        self.log_info(f"移除远程屏幕: {device_id}")

    def stop(self):
        self.is_running = False
        connection_manager.unregister_connection("input_share")
        if self._backend:
            self._backend.stop_capture()
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        if self.running_thread and self.running_thread.is_alive():
            self.running_thread.join(timeout=2)
        self.log_info("InputLeap 模块已停止")

    def _start_server(self):
        """启动服务端 - 捕获本机输入，推送到远程"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.server_port))
            self.server_socket.listen(5)
            self.log_info(f"InputLeap 服务器监听端口 {self.server_port}")

            def accept_loop():
                while self.is_running:
                    try:
                        self.server_socket.settimeout(1)
                        client, addr = self.server_socket.accept()
                        self.log_info(f"远程客户端已连接: {addr}")
                        self.client_socket = client
                        self._backend.start_capture(self._send_command)
                        self._handle_client()
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.is_running:
                            self.log_error(f"连接异常: {e}")
                        break

            self.running_thread = threading.Thread(target=accept_loop, daemon=True)
            self.running_thread.start()

        except Exception as e:
            self.log_error(f"启动服务端失败: {e}")
            self.is_running = False

    def _start_client(self):
        """启动客户端 - 连接远程服务端，接收并执行命令"""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(10)
            self.client_socket.connect((self.server_ip, self.server_port))
            self.log_info(f"已连接服务端: {self.server_ip}:{self.server_port}")
            connection_manager.register_connection("input_share", self.client_socket)

            def recv_loop():
                while self.is_running:
                    try:
                        length_data = self._recv_all(self.client_socket, 4)
                        if not length_data:
                            break
                        length = struct.unpack('>I', length_data)[0]
                        cmd_data = self._recv_all(self.client_socket, length)
                        if cmd_data:
                            command = json.loads(cmd_data.decode('utf-8'))
                            self._backend.execute_command(command)
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.is_running:
                            log.info(f"[InputLeap] 接收命令: {e}")
                        break

            self.running_thread = threading.Thread(target=recv_loop, daemon=True)
            self.running_thread.start()

        except Exception as e:
            self.log_info("InputLeap 客户端模式，等待服务器连接")
            self.is_running = False

    def _handle_client(self):
        """处理已连接的客户端 (在服务端线程中运行)"""
        sock = self.client_socket
        if not sock:
            return
        try:
            sock.settimeout(5)
            while self.is_running and sock == self.client_socket:
                try:
                    length_data = self._recv_all(sock, 4)
                    if not length_data:
                        break
                    length = struct.unpack('>I', length_data)[0]
                    cmd_data = self._recv_all(sock, length)
                    if cmd_data:
                        command = json.loads(cmd_data.decode('utf-8'))
                        self._backend.execute_command(command)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.is_running:
                        self.log_error(f"处理命令异常: {e}")
                    break
        finally:
            try:
                sock.close()
            except:
                pass
            if self.client_socket is sock:
                self.client_socket = None

    def _send_command(self, command: Dict):
        """发送命令到远程客户端"""
        if not self.client_socket:
            return
        
        if command.get("type") == "mouse_move":
            x, y = command["x"], command["y"]
            boundary_result = self.screen_layout.check_boundary(x, y)
            if boundary_result:
                target_device, direction = boundary_result
                if target_device != "local":
                    switch_cmd = {
                        "type": "screen_switch",
                        "target_device": target_device,
                        "direction": direction.value,
                        "position": self._calculate_entry_position(target_device, direction, x, y)
                    }
                    self._send_raw_command(switch_cmd)
                    self.screen_layout.switch_control(target_device)
                    return
        
        self._send_raw_command(command)

    def _send_raw_command(self, command: Dict):
        """直接发送命令（不进行边界检测）"""
        if not self.client_socket:
            return
        try:
            data = json.dumps(command).encode('utf-8')
            self.client_socket.sendall(struct.pack('>I', len(data)))
            self.client_socket.sendall(data)
        except:
            pass

    def _calculate_entry_position(self, target_device: str, direction: Direction, 
                                   x: int, y: int) -> Tuple[int, int]:
        """计算鼠标进入目标屏幕的位置"""
        target_screen = self.screen_layout.get_screen(target_device)
        if not target_screen:
            return (0, 0)
        
        current_screen = self.screen_layout.get_current_screen()
        if not current_screen:
            return (0, 0)
        
        rel_y = (y - current_screen.top) / current_screen.height
        entry_y = int(target_screen.top + rel_y * target_screen.height)
        
        if direction == Direction.RIGHT:
            return (target_screen.left + 5, entry_y)
        elif direction == Direction.LEFT:
            return (target_screen.right - 5, entry_y)
        elif direction == Direction.BOTTOM:
            rel_x = (x - current_screen.left) / current_screen.width
            entry_x = int(target_screen.left + rel_x * target_screen.width)
            return (entry_x, target_screen.top + 5)
        else:
            rel_x = (x - current_screen.left) / current_screen.width
            entry_x = int(target_screen.left + rel_x * target_screen.width)
            return (entry_x, target_screen.bottom - 5)

    @staticmethod
    def _recv_all(sock: Optional[socket.socket], size: int) -> Optional[bytes]:
        """接收指定字节数"""
        if not sock:
            return None
        data = b''
        while len(data) < size:
            try:
                chunk = sock.recv(size - len(data))
                if not chunk:
                    return None
                data += chunk
            except socket.timeout:
                return None if len(data) == 0 else data
            except:
                return None
        return data
