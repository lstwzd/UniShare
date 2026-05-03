import socket
import json
import threading
import subprocess
import platform
import uuid
from typing import Dict, List, Optional

from src.unishare.modules.base import BaseModule
from src.unishare.core.config import config
from src.unishare.core.logger import log
from src.unishare.utils.usbip import backend, scan_usb_devices


class USBShareModule(BaseModule):
    """
    USB 设备共享模块 - 基于纯 Python USB/IP 协议栈
    支持勾选指定 USB 设备进行共享
    """

    def __init__(self):
        super().__init__("USB 共享模块")
        self.enabled = config.get("usb_share.enabled", True)
        self.mode = config.get("mode", "client")
        self.server_ip = config.get("server_ip", "127.0.0.1")
        self.usbip_port = 3240
        self.server_socket = None
        self.connected_clients: List[socket.socket] = []
        self.shared_devices: List[Dict] = []
        self._shared_ids: set = set(config.get("usb_share.shared_device_ids", []))
        self.running_thread = None
        
    def start(self):
        if not self.enabled:
            self.log_info("USB 共享功能已关闭")
            return
        self.is_running = True
        
        # 加载 USB/IP 后端
        self._check_backend()
        
        if self.mode == "server":
            self._start_server()
        else:
            self._start_client()
        
        # 扫描本机 USB 设备
        self._scan_devices()
            
        self.log_info(f"USB 共享模块启动成功 (模式：{self.mode})")
    
    def _check_backend(self):
        """检查 USB/IP 后端状态"""
        if backend.available:
            self.log_info(f"USB/IP 后端: {backend.get_backend_name()}")
        else:
            self.log_info("USB/IP 后端未加载，使用系统扫描")
    
    def _scan_devices(self):
        """扫描本机 USB 设备"""
        try:
            devs = scan_usb_devices()
            self.shared_devices = []
            
            for idx, dev in enumerate(devs):
                device_entry = {
                    "id": str(uuid.uuid4()),
                    "name": dev.get("name") or dev.get("product_name") or dev.get("description", f"USB Device {idx}"),
                    "busid": dev.get("busid", f"{dev.get('busnum', 0)}-{dev.get('devnum', idx)}"),
                    "vendor": dev.get("vendor", ""),
                    "product": dev.get("product", ""),
                    "manufacturer": dev.get("manufacturer", ""),
                    "serial": dev.get("serial", ""),
                    "platform": platform.system().lower(),
                    "backend": backend.get_backend_name()
                }
                self.shared_devices.append(device_entry)
            
            self.log_info(f"扫描到 {len(self.shared_devices)} 个 USB 设备")

        except Exception as e:
            self.log_error(f"扫描 USB 设备失败：{str(e)}")

    def get_shared_ids(self) -> list:
        return list(self._shared_ids)

    def set_shared_ids(self, ids: list):
        self._shared_ids = set(ids)
        config.set("usb_share.shared_device_ids", list(self._shared_ids))
        config.save()

    def is_device_shared(self, device_id: str) -> bool:
        return device_id in self._shared_ids

    def get_exportable_devices(self) -> List[Dict]:
        return [d for d in self.shared_devices if d["id"] in self._shared_ids]

    def stop(self):
        self.is_running = False
        
        # 停止 USB/IP 后端服务
        if self.mode == "server":
            backend.stop_server()
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        for client in self.connected_clients:
            try:
                client.close()
            except:
                pass
        
        if self.running_thread and self.running_thread.is_alive():
            self.running_thread.join(timeout=2)
            
        self.log_info("USB 共享模块已停止")
    
    def _start_server(self):
        """启动 USB 共享服务端"""
        # 启动 USB/IP 后端服务
        if backend.start_server(self.usbip_port):
            self.log_info(f"USB/IP 服务端启动，端口: {self.usbip_port}")
        else:
            self.log_warning("USB/IP 服务端启动失败，使用用户态协议栈")
        
        # 启动用户态 TCP 服务 (备份通信通道)
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', 24801))
            self.server_socket.listen(5)
            self.log_info(f"USB 共享 TCP 服务监听端口 24801")
            
            def accept_connections():
                while self.is_running:
                    try:
                        self.server_socket.settimeout(1)
                        client, addr = self.server_socket.accept()
                        self.connected_clients.append(client)
                        self.log_info(f"USB 客户端已连接：{addr}")
                        self._handle_client(client)
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.is_running:
                            self.log_error(f"接受连接失败：{str(e)}")
                        break
            
            self.running_thread = threading.Thread(target=accept_connections, daemon=True)
            self.running_thread.start()
            
        except Exception as e:
            self.log_error(f"启动 TCP 服务失败：{str(e)}")
    
    def _handle_client(self, client: socket.socket):
        """处理 USB 客户端连接"""
        try:
            client.settimeout(5)
            while self.is_running:
                try:
                    length_data = client.recv(4)
                    if not length_data:
                        break
                    
                    import struct
                    length = struct.unpack('>I', length_data)[0]
                    command_data = client.recv(length)
                    command = json.loads(command_data.decode('utf-8'))
                    
                    self._process_usb_command(command, client)
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    self.log_error(f"处理 USB 命令失败：{str(e)}")
                    break
        finally:
            if client in self.connected_clients:
                self.connected_clients.remove(client)
            client.close()
    
    def _process_usb_command(self, command: Dict, client: socket.socket):
        """处理 USB 命令"""
        cmd_type = command.get("type")
        
        if cmd_type == "list_devices":
            self._send_device_list(client)
        elif cmd_type == "mount_device":
            device_id = command.get("device_id")
            busid = command.get("busid", "")
            self._mount_usb_device(device_id, busid, client)
        elif cmd_type == "unmount_device":
            device_id = command.get("device_id")
            port = command.get("port", 0)
            self._unmount_usb_device(device_id, port, client)
        elif cmd_type == "scan_devices":
            self._scan_devices()
            self._send_device_list(client)
        else:
            self.log_info(f"收到未知 USB 命令：{cmd_type}")
    
    def _send_device_list(self, client: socket.socket):
        """发送 USB 设备列表"""
        response = {
            "type": "device_list",
            "devices": self.shared_devices
        }
        try:
            import struct
            json_data = json.dumps(response).encode('utf-8')
            client.sendall(struct.pack('>I', len(json_data)))
            client.sendall(json_data)
        except Exception as e:
            self.log_error(f"发送设备列表失败：{str(e)}")
    
    def _mount_usb_device(self, device_id: str, busid: str, client: socket.socket):
        """挂载 USB 设备"""
        success = False
        message = ""
        
        if self.mode == "server":
            # 服务端: 导出本地 USB 设备
            if busid:
                success = backend.export_device(busid)
                message = f"设备 {busid} 已导出" if success else f"导出设备 {busid} 失败"
            else:
                # 查找设备的 busid
                for dev in self.shared_devices:
                    if dev["id"] == device_id:
                        busid = dev.get("busid", "")
                        if busid:
                            success = backend.export_device(busid)
                            message = f"设备 {dev['name']} 已导出" if success else f"导出失败"
                        break
        else:
            # 客户端: 连接远程 USB 设备
            import struct
            success = backend.attach_device(self.server_ip, busid)
            message = f"远程设备已连接" if success else f"连接远程设备失败"
        
        response = {
            "type": "mount_result",
            "device_id": device_id,
            "busid": busid,
            "success": success,
            "message": message or "操作完成"
        }
        
        self._send_json_response(client, response)
    
    def _unmount_usb_device(self, device_id: str, port: int, client: socket.socket):
        """卸载 USB 设备"""
        success = False
        if port > 0:
            success = backend.detach_device(port)
        
        response = {
            "type": "unmount_result",
            "device_id": device_id,
            "success": success,
            "message": "设备已卸载" if success else "卸载失败"
        }
        self._send_json_response(client, response)
    
    def _send_json_response(self, client: socket.socket, data: Dict):
        """发送 JSON 响应"""
        try:
            import struct
            json_data = json.dumps(data).encode('utf-8')
            client.sendall(struct.pack('>I', len(json_data)))
            client.sendall(json_data)
        except:
            pass
    
    def _start_client(self):
        """启动 USB 客户端"""
        try:
            # 尝试连接服务端
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(3)
            client_socket.connect((self.server_ip, 24801))
            
            # 请求设备列表
            import struct
            request = json.dumps({"type": "list_devices"}).encode('utf-8')
            client_socket.sendall(struct.pack('>I', len(request)))
            client_socket.sendall(request)
            
            # 读取回复
            length_data = client_socket.recv(4)
            if length_data:
                length = struct.unpack('>I', length_data)[0]
                response_data = client_socket.recv(length)
                response = json.loads(response_data.decode('utf-8'))
                if response.get("type") == "device_list":
                    self.shared_devices = response.get("devices", [])
            
            client_socket.close()
            self.log_info(f"已连接 USB 服务端：{self.server_ip}")
            
        except Exception as e:
            self.log_info(f"USB 客户端模式，等待服务端: {self.server_ip}")
