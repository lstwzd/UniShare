import socket
import json
import threading
import os
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Callable
from src.unishare.modules.base import BaseModule
from src.unishare.core.config import config
from src.unishare.core.logger import log

class FileShareModule(BaseModule):
    """文件传输模块 - 基于自定义 TCP 协议"""
    
    def __init__(self):
        super().__init__("文件传输模块")
        self.enabled = config.get("file_share.temp_transfer_enabled", True)
        self.mode = config.get("mode", "client")
        self.server_ip = config.get("server_ip", "127.0.0.1")
        self.server_port = 24802
        self.server_socket = None
        self.connected_clients: List[socket.socket] = []
        self.transfer_dir = Path.home() / "UniShare" / "transfers"
        self.running_thread = None
        
    def start(self):
        if not self.enabled:
            self.log_info("文件传输功能已关闭")
            return
        self.is_running = True
        
        # 创建传输目录
        self.transfer_dir.mkdir(parents=True, exist_ok=True)
        
        if self.mode == "server":
            self._start_server()
        else:
            self._start_client()
            
        self.log_info(f"文件传输模块启动成功 (模式：{self.mode})")
    
    def stop(self):
        self.is_running = False
        
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
            
        self.log_info("文件传输模块已停止")
    
    def _start_server(self):
        """启动文件服务器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.server_port))
            self.server_socket.listen(5)
            self.log_info(f"文件服务器监听端口 {self.server_port}")
            
            def accept_connections():
                while self.is_running:
                    try:
                        self.server_socket.settimeout(1)
                        client, addr = self.server_socket.accept()
                        self.connected_clients.append(client)
                        self.log_info(f"文件传输客户端已连接：{addr}")
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
            self.log_error(f"启动文件服务器失败：{str(e)}")
            self.is_running = False
    
    def _handle_client(self, client: socket.socket):
        """处理文件传输客户端连接"""
        try:
            client.settimeout(5)
            while self.is_running:
                try:
                    # 读取命令长度 (4 字节)
                    length_data = client.recv(4)
                    if not length_data:
                        break
                    
                    import struct
                    length = struct.unpack('>I', length_data)[0]
                    
                    # 读取命令数据
                    command_data = client.recv(length)
                    command = json.loads(command_data.decode('utf-8'))
                    
                    self._process_file_command(command, client)
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    self.log_error(f"处理文件命令失败：{str(e)}")
                    break
        finally:
            if client in self.connected_clients:
                self.connected_clients.remove(client)
            client.close()
    
    def _process_file_command(self, command: Dict, client: socket.socket):
        """处理文件命令"""
        cmd_type = command.get("type")
        
        if cmd_type == "list_directory":
            self._list_directory(command, client)
        elif cmd_type == "upload":
            self._receive_file(command, client)
        elif cmd_type == "download":
            self._send_file(command, client)
        elif cmd_type == "delete":
            self._delete_file(command, client)
        elif cmd_type == "create_folder":
            self._create_folder(command, client)
        else:
            self.log_info(f"收到未知文件命令：{cmd_type}")
    
    def _list_directory(self, command: Dict, client: socket.socket):
        """列出目录内容"""
        path = command.get("path", str(self.transfer_dir))
        
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                path_obj = self.transfer_dir
            
            items = []
            for item in path_obj.iterdir():
                items.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else 0,
                    "modified": item.stat().st_mtime
                })
            
            response = {
                "type": "directory_list",
                "items": items,
                "current_path": str(path_obj)
            }
            
            self._send_response(client, response)
            
        except Exception as e:
            self._send_error(client, f"列出目录失败：{str(e)}")
    
    def _receive_file(self, command: Dict, client: socket.socket):
        """接收上传的文件"""
        filename = command.get("filename", "unknown")
        file_size = command.get("size", 0)
        save_path = command.get("save_path", str(self.transfer_dir))
        
        try:
            save_path = Path(save_path)
            save_path.mkdir(parents=True, exist_ok=True)
            file_path = save_path / filename
            
            # 接收文件数据
            total_received = 0
            buffer_size = 8192
            
            while total_received < file_size:
                to_read = min(buffer_size, file_size - total_received)
                data = client.recv(to_read)
                
                if not data:
                    break
                
                with open(file_path, 'ab') as f:
                    f.write(data)
                
                total_received += len(data)
                
                # 发送进度
                progress = {
                    "type": "upload_progress",
                    "filename": filename,
                    "received": total_received,
                    "total": file_size,
                    "percent": (total_received / file_size * 100) if file_size > 0 else 0
                }
                self._send_response(client, progress)
            
            response = {
                "type": "upload_result",
                "success": True,
                "path": str(file_path),
                "message": f"文件上传成功：{filename}"
            }
            self._send_response(client, response)
            
        except Exception as e:
            self._send_error(client, f"接收文件失败：{str(e)}")
    
    def _send_file(self, command: Dict, client: socket.socket):
        """发送下载的文件"""
        file_path = command.get("path", "")
        
        try:
            path_obj = Path(file_path)
            if not path_obj.exists():
                self._send_error(client, "文件不存在")
                return
            
            file_size = path_obj.stat().st_size
            filename = path_obj.name
            
            # 发送文件信息
            info = {
                "type": "file_info",
                "filename": filename,
                "size": file_size
            }
            self._send_response(client, info)
            
            # 发送文件数据
            buffer_size = 8192
            with open(path_obj, 'rb') as f:
                while True:
                    data = f.read(buffer_size)
                    if not data:
                        break
                    
                    # 发送数据长度 + 数据
                    import struct
                    client.sendall(struct.pack('>I', len(data)))
                    client.sendall(data)
            
            response = {
                "type": "download_result",
                "success": True,
                "message": f"文件发送完成：{filename}"
            }
            self._send_response(client, response)
            
        except Exception as e:
            self._send_error(client, f"发送文件失败：{str(e)}")
    
    def _delete_file(self, command: Dict, client: socket.socket):
        """删除文件"""
        file_path = command.get("path", "")
        
        try:
            path_obj = Path(file_path)
            if path_obj.exists():
                if path_obj.is_dir():
                    shutil.rmtree(path_obj)
                else:
                    path_obj.unlink()
                
                response = {
                    "type": "delete_result",
                    "success": True,
                    "message": "文件已删除"
                }
            else:
                response = {
                    "type": "delete_result",
                    "success": False,
                    "message": "文件不存在"
                }
            
            self._send_response(client, response)
            
        except Exception as e:
            self._send_error(client, f"删除文件失败：{str(e)}")
    
    def _create_folder(self, command: Dict, client: socket.socket):
        """创建文件夹"""
        folder_name = command.get("name", "new_folder")
        parent_path = command.get("path", str(self.transfer_dir))
        
        try:
            parent = Path(parent_path)
            parent.mkdir(parents=True, exist_ok=True)
            folder_path = parent / folder_name
            folder_path.mkdir(exist_ok=True)
            
            response = {
                "type": "create_folder_result",
                "success": True,
                "path": str(folder_path)
            }
            self._send_response(client, response)
            
        except Exception as e:
            self._send_error(client, f"创建文件夹失败：{str(e)}")
    
    def _send_response(self, client: socket.socket, data: Dict):
        """发送响应数据"""
        import struct
        json_data = json.dumps(data).encode('utf-8')
        client.sendall(struct.pack('>I', len(json_data)))
        client.sendall(json_data)
    
    def _send_error(self, client: socket.socket, message: str):
        """发送错误信息"""
        self._send_response(client, {
            "type": "error",
            "message": message
        })
    
    def _start_client(self):
        """启动文件客户端"""
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((self.server_ip, self.server_port))
            self.log_info(f"已连接到文件服务器：{self.server_ip}:{self.server_port}")
            
            def send_keepalive():
                import time
                while self.is_running:
                    try:
                        time.sleep(30)
                        heartbeat = json.dumps({"type": "heartbeat"}).encode('utf-8')
                        import struct
                        client_socket.sendall(struct.pack('>I', len(heartbeat)))
                        client_socket.sendall(heartbeat)
                    except:
                        break
            
            self.running_thread = threading.Thread(target=send_keepalive, daemon=True)
            self.running_thread.start()
            
        except Exception as e:
            self.log_info(f"文件传输客户端模式，等待服务器连接")
    
    def send_file(self, file_path: str, target_client: socket.socket) -> bool:
        """发送文件到指定客户端"""
        try:
            path_obj = Path(file_path)
            if not path_obj.exists():
                return False
            
            file_size = path_obj.stat().st_size
            filename = path_obj.name
            
            command = {
                "type": "upload",
                "filename": filename,
                "size": file_size,
                "save_path": str(self.transfer_dir)
            }
            
            import struct
            json_data = json.dumps(command).encode('utf-8')
            target_client.sendall(struct.pack('>I', len(json_data)))
            target_client.sendall(json_data)
            
            # 读取并发送文件
            buffer_size = 8192
            with open(path_obj, 'rb') as f:
                while True:
                    data = f.read(buffer_size)
                    if not data:
                        break
                    
                    target_client.sendall(data)
            
            return True
            
        except Exception as e:
            self.log_error(f"发送文件失败：{str(e)}")
            return False
