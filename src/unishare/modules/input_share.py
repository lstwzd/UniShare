import socket
import json
import struct
import threading
from typing import Dict, Optional

from src.unishare.modules.base import BaseModule
from src.unishare.core.config import config
from src.unishare.core.logger import log
from src.unishare.utils.inputleap import InputLeapBackend, get_backend


class InputLeapModule(BaseModule):
    """
    键鼠共享模块
    纯 Python 实现，基于 pynput 库
    通过 TCP 协议在设备间同步键盘鼠标事件
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

        if self.mode == "server":
            self._start_server()
        else:
            self._start_client()

        self.log_info(f"InputLeap 模块启动成功 (模式：{self.mode})")

    def stop(self):
        self.is_running = False
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
        try:
            data = json.dumps(command).encode('utf-8')
            self.client_socket.sendall(struct.pack('>I', len(data)))
            self.client_socket.sendall(data)
        except:
            pass

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
