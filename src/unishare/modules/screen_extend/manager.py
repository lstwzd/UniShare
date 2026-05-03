import socket
import threading
import mss
import numpy as np
from PIL import Image
from typing import Tuple
from src.unishare.modules.base import BaseModule
from src.unishare.core.config import config
from src.unishare.core.logger import log

class ScreenExtendManager(BaseModule):
    def __init__(self):
        super().__init__("扩展屏管理模块")
        self.sct = mss.mss()
        self.running = False
        self.stream_thread: threading.Thread = None
        self.client_socket: socket.socket = None
        self.server_socket: socket.socket = None
        self.client_addr = None

    def get_virtual_screen_monitor(self) -> Tuple[int, dict]:
        """获取虚拟扩展屏的监视器信息"""
        monitors = self.sct.monitors
        if len(monitors) > 2:
            return len(monitors)-1, monitors[-1]
        return 1, monitors[1]

    def _stream_server(self):
        """屏幕推流服务端（主机端）"""
        host = "0.0.0.0"
        port = config.get("network.stream_port", 24803)
        fps = config.get("screen_extend.fps", 30)
        quality = config.get("screen_extend.quality", 80)
        frame_interval = 1 / fps

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server_socket.bind((host, port))
            self.log_info(f"屏幕推流服务启动，端口: {port}")

            monitor_idx, monitor = self.get_virtual_screen_monitor()
            self.log_info(f"捕获虚拟屏: {monitor}")

            import time
            while self.running:
                start_time = time.time()

                # 捕获虚拟屏画面
                img = self.sct.grab(monitor)
                img_np = np.array(img)
                img_pil = Image.fromarray(img_np)

                # JPEG压缩
                img_bytes = img_pil.tobytes("jpeg", quality=quality)
                # 分包发送（UDP最大包长限制）
                chunk_size = 60000
                for i in range(0, len(img_bytes), chunk_size):
                    chunk = img_bytes[i:i+chunk_size]
                    if self.client_socket and self.client_addr:
                        try:
                            self.client_socket.sendto(chunk, self.client_addr)
                        except:
                            pass

                # 帧率控制
                elapsed = time.time() - start_time
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)

        except Exception as e:
            self.log_error(f"推流服务异常: {str(e)}")

    def _stream_client(self, server_ip: str):
        """屏幕渲染客户端（副屏端）"""
        import cv2
        host = "0.0.0.0"
        port = config.get("network.stream_port", 24803)
        server_port = config.get("network.stream_port", 24803)

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.client_socket.bind((host, port))
            self.client_socket.settimeout(1.0)
            self.server_addr = (server_ip, server_port)
            self.log_info(f"客户端连接到主机: {server_ip}:{server_port}")

            buffer = b""
            cv2.namedWindow("UniShare 扩展屏", cv2.WND_PROP_FULLSCREEN)
            cv2.setWindowProperty("UniShare 扩展屏", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

            while self.running:
                try:
                    data, addr = self.client_socket.recvfrom(65535)
                    buffer += data

                    # 检测JPEG结束标记
                    if buffer.endswith(b"\xff\xd9"):
                        img_np = np.frombuffer(buffer, dtype=np.uint8)
                        img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
                        if img is not None:
                            cv2.imshow("UniShare 扩展屏", img)
                            cv2.waitKey(1)
                        buffer = b""

                except socket.timeout:
                    continue
                except Exception as e:
                    self.log_error(f"客户端渲染异常: {str(e)}")
                    continue

            cv2.destroyAllWindows()

        except Exception as e:
            self.log_error(f"客户端异常: {str(e)}")

    def start_server(self):
        """启动主机端扩展屏服务"""
        if self.running:
            return
        self.running = True
        self.stream_thread = threading.Thread(target=self._stream_server, daemon=True)
        self.stream_thread.start()
        self.is_running = True
        self.log_info("主机端扩展屏服务启动成功")

    def start_client(self, server_ip: str):
        """启动客户端扩展屏渲染"""
        if self.running:
            return
        self.running = True
        self.stream_thread = threading.Thread(target=self._stream_client, args=(server_ip,), daemon=True)
        self.stream_thread.start()
        self.is_running = True
        self.log_info(f"客户端扩展屏启动成功，连接主机: {server_ip}")

    def start(self):
        """默认启动主机模式"""
        mode = config.get("screen_extend.mode", "server")
        if mode == "server":
            self.start_server()
        else:
            self.start_client(config.get("network.static_ip", "127.0.0.1"))

    def stop(self):
        self.running = False
        self.is_running = False
        if self.server_socket:
            self.server_socket.close()
        if self.client_socket:
            self.client_socket.close()
        if self.stream_thread:
            self.stream_thread.join(timeout=2)
        self.log_info("扩展屏服务已停止")

# 全局单例
screen_extend_manager = ScreenExtendManager()
