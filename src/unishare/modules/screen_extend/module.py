import socket
import threading
import time
import struct
import io
import json
import numpy as np
from typing import Optional
from pathlib import Path

from src.unishare.modules.base import BaseModule
from src.unishare.core.config import config
from src.unishare.core.logger import log

try:
    import mss
except ImportError:
    mss = None

try:
    from PIL import Image
except ImportError:
    Image = None


class ScreenExtendModule(BaseModule):
    """
    扩展屏模块 - 服务端捕获屏幕推流 + 客户端接收渲染 + 拖拽文件接收
    """

    def __init__(self):
        super().__init__("扩展屏模块")
        self.enabled = config.get("screen_extend.enabled", True)
        self.mode = config.get("mode", "client")
        self.server_ip = config.get("server_ip", "127.0.0.1")
        self.stream_port = config.get("network.stream_port", 24803)
        self.transfer_port = config.get("network.transfer_port", 24804)
        self.fps = config.get("screen_extend.fps", 30)
        self.quality = config.get("screen_extend.quality", 80)
        self.extend_direction = config.get("screen_extend.extend_direction", "right")

        self.sct = None
        self.server_socket = None
        self.client_socket = None
        self.transfer_server = None
        self.transfer_client = None
        self.preview_callback = None
        self.file_received_callback = None
        self.stream_thread = None
        self.transfer_thread = None

    def start(self):
        if not self.enabled:
            self.log_info("扩展屏功能已关闭")
            return
        self.is_running = True

        if self.mode == "server":
            self._start_stream_server()
            self._start_transfer_server()
        else:
            self._start_stream_client()

        self.log_info(f"扩展屏模块启动成功 (模式：{self.mode})")

    def stop(self):
        self.is_running = False
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
        if self.transfer_server:
            try:
                self.transfer_server.close()
            except:
                pass
        if self.transfer_client:
            try:
                self.transfer_client.close()
            except:
                pass
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=2)
        if self.transfer_thread and self.transfer_thread.is_alive():
            self.transfer_thread.join(timeout=2)
        self.log_info("扩展屏模块已停止")

    def set_preview_callback(self, callback):
        """设置预览回调（用于 GUI 显示）"""
        self.preview_callback = callback

    def set_file_received_callback(self, callback):
        """设置文件接收回调"""
        self.file_received_callback = callback

    # ============ 屏幕推流（服务端） ============

    def _start_stream_server(self):
        """启动屏幕推流服务端"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server_socket.bind(("0.0.0.0", self.stream_port))
            self.log_info(f"屏幕推流服务启动，端口: {self.stream_port}")

            def stream_loop():
                if not mss or not Image:
                    self.log_error("缺少依赖：mss 或 Pillow，无法推流")
                    return

                self.sct = mss.mss()
                frame_interval = 1.0 / self.fps
                monitor = self.sct.monitors[1]  # 主显示器

                self.log_info(f"开始捕获屏幕: {monitor}")

                client_addr = None

                while self.is_running:
                    start = time.time()
                    try:
                        # 等待客户端发送请求（包含地址信息）
                        self.server_socket.settimeout(0.1)
                        try:
                            data, addr = self.server_socket.recvfrom(1024)
                            if data == b"HELLO":
                                client_addr = addr
                                self.server_socket.sendto(b"OK", addr)
                                self.log_info(f"推流客户端已连接: {addr}")
                        except socket.timeout:
                            pass

                        if not client_addr:
                            continue

                        # 捕获屏幕
                        img = self.sct.grab(monitor)
                        img_np = np.array(img)
                        img_pil = Image.fromarray(img_np)

                        # JPEG 压缩
                        buf = io.BytesIO()
                        img_pil.save(buf, format="JPEG", quality=self.quality)
                        img_bytes = buf.getvalue()

                        # 发送数据长度 + JPEG 数据
                        packet = struct.pack(">I", len(img_bytes)) + img_bytes
                        self.server_socket.sendto(packet, client_addr)

                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.is_running:
                            self.log_error(f"推流异常: {str(e)}")
                        continue

                    elapsed = time.time() - start
                    if elapsed < frame_interval:
                        time.sleep(frame_interval - elapsed)

            self.stream_thread = threading.Thread(target=stream_loop, daemon=True)
            self.stream_thread.start()

        except Exception as e:
            self.log_error(f"启动推流服务失败: {str(e)}")
            self.is_running = False

    # ============ 屏幕接收（客户端） ============

    def _start_stream_client(self):
        """启动屏幕接收客户端（返回 JPEG 数据给 GUI 渲染）"""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.log_info(f"连接推流服务器: {self.server_ip}:{self.stream_port}")

            def recv_loop():
                # 发送 HELLO 握手
                try:
                    self.client_socket.sendto(b"HELLO", (self.server_ip, self.stream_port))
                    self.client_socket.settimeout(2)
                    data, _ = self.client_socket.recvfrom(1024)
                    if data != b"OK":
                        self.log_error("握手失败")
                        return
                    self.log_info("握手成功，开始接收屏幕流")
                except Exception as e:
                    self.log_error(f"连接推流服务器失败: {str(e)}")
                    return

                self.client_socket.settimeout(1.0)

                while self.is_running:
                    try:
                        # 接收长度（4 字节）
                        length_data, addr = self.client_socket.recvfrom(4)
                        if len(length_data) < 4:
                            continue

                        length = struct.unpack(">I", length_data)[0]

                        # 接收 JPEG 数据
                        img_data = b""
                        while len(img_data) < length:
                            chunk, _ = self.client_socket.recvfrom(65535)
                            img_data += chunk

                        # 回调通知 GUI 渲染
                        if self.preview_callback:
                            self.preview_callback(img_data)

                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.is_running:
                            self.log_error(f"接收屏幕流异常: {str(e)}")
                        continue

            self.stream_thread = threading.Thread(target=recv_loop, daemon=True)
            self.stream_thread.start()

        except Exception as e:
            self.log_error(f"启动屏幕接收失败: {str(e)}")
            self.is_running = False

    # ============ 文件传输（拖拽共享） ============

    def _start_transfer_server(self):
        """启动文件传输 TCP 服务器（服务端接收文件）"""
        try:
            self.transfer_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.transfer_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.transfer_server.bind(("0.0.0.0", self.transfer_port))
            self.transfer_server.listen(5)
            self.log_info(f"文件接收服务启动，端口: {self.transfer_port}")

            def accept_loop():
                while self.is_running:
                    try:
                        self.transfer_server.settimeout(1)
                        client, addr = self.transfer_server.accept()
                        self.log_info(f"文件传输客户端连接: {addr}")
                        threading.Thread(
                            target=self._handle_file_transfer,
                            args=(client,),
                            daemon=True,
                        ).start()
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.is_running:
                            self.log_error(f"文件接收异常: {str(e)}")
                        break

            self.transfer_thread = threading.Thread(target=accept_loop, daemon=True)
            self.transfer_thread.start()

        except Exception as e:
            self.log_error(f"启动文件接收服务失败: {str(e)}")

    def _handle_file_transfer(self, client: socket.socket):
        """处理文件接收"""
        try:
            # 读取文件名长度 + 文件名
            name_len_data = client.recv(4)
            if not name_len_data:
                return
            name_len = struct.unpack(">I", name_len_data)[0]
            filename = client.recv(name_len).decode("utf-8")

            # 读取文件大小
            size_data = client.recv(8)
            file_size = struct.unpack(">Q", size_data)[0]

            # 读取文件内容
            save_path = Path(config.get("drag_share.save_path", "~/Downloads/UniShare"))
            save_path = save_path.expanduser()
            save_path.mkdir(parents=True, exist_ok=True)
            file_path = save_path / filename

            received = 0
            with open(file_path, "wb") as f:
                while received < file_size:
                    chunk = client.recv(min(65536, file_size - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)

            self.log_info(f"文件接收完成: {filename} ({file_size} bytes)")

            if self.file_received_callback:
                self.file_received_callback(str(file_path))

        except Exception as e:
            self.log_error(f"文件接收失败: {str(e)}")
        finally:
            client.close()

    def send_file(self, file_path: str):
        """客户端发送文件到服务端"""
        if self.mode != "client":
            self.log_error("仅客户端模式可发送文件")
            return False

        try:
            path_obj = Path(file_path)
            if not path_obj.exists():
                self.log_error(f"文件不存在: {file_path}")
                return False

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.server_ip, self.transfer_port))

            filename = path_obj.name.encode("utf-8")
            file_size = path_obj.stat().st_size

            # 发送文件名长度 + 文件名
            sock.sendall(struct.pack(">I", len(filename)))
            sock.sendall(filename)

            # 发送文件大小
            sock.sendall(struct.pack(">Q", file_size))

            # 发送文件内容
            with open(path_obj, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    sock.sendall(chunk)

            sock.close()
            self.log_info(f"文件发送完成: {filename.decode()} ({file_size} bytes)")
            return True

        except Exception as e:
            self.log_error(f"文件发送失败: {str(e)}")
            return False
