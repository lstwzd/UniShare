"""
Frame Recovery Module
Implements UDP retransmission mechanism for lost frames
"""
import socket
import threading
import time
import struct
from collections import deque
from typing import Dict, Optional, Tuple, Callable


class FrameRecovery:
    """
    帧恢复机制
    - 发送端缓存最近N帧用于重传
    - 接收端检测丢帧并请求重传
    - 使用NACK机制（负反馈重传）
    """
    
    FRAME_BUFFER_SIZE = 60
    MAX_RETRIES = 3
    NACK_TIMEOUT = 0.05
    RETRANSMIT_PORT_OFFSET = 10
    
    def __init__(self, base_port: int = 24803):
        self.base_port = base_port
        self.retransmit_port = base_port + self.RETRANSMIT_PORT_OFFSET
        
        self._frame_buffer: Dict[int, bytes] = {}
        self._buffer_lock = threading.Lock()
        self._frame_ids = deque(maxlen=self.FRAME_BUFFER_SIZE)
        
        self._expected_frame_id = 0
        self._missing_frames: Dict[int, int] = {}
        self._missing_lock = threading.Lock()
        
        self._retransmit_socket: Optional[socket.socket] = None
        self._running = False
        self._on_frame_received: Optional[Callable] = None
        
    def start_server(self):
        """启动服务端重传监听"""
        try:
            self._retransmit_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._retransmit_socket.bind(("0.0.0.0", self.retransmit_port))
            self._retransmit_socket.settimeout(0.1)
            self._running = True
            
            def retransmit_loop():
                while self._running:
                    try:
                        data, addr = self._retransmit_socket.recvfrom(1024)
                        if data.startswith(b"NACK"):
                            if len(data) >= 3:
                                frame_id = struct.unpack(">H", data[1:3])[0]
                                frame_data = self._get_buffered_frame(frame_id)
                                if frame_data:
                                    response = struct.pack(">H", frame_id) + frame_data
                                    self._retransmit_socket.sendto(response, addr)
                    except socket.timeout:
                        continue
                    except Exception:
                        continue
            
            threading.Thread(target=retransmit_loop, daemon=True).start()
            return True
        except Exception:
            return False
    
    def start_client(self, server_ip: str, on_frame_received: Callable):
        """启动客户端重传请求"""
        self._server_ip = server_ip
        self._on_frame_received = on_frame_received
        
        try:
            self._retransmit_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._retransmit_socket.settimeout(0.1)
            self._running = True
            
            def nack_loop():
                while self._running:
                    try:
                        with self._missing_lock:
                            missing = list(self._missing_frames.items())
                        
                        for frame_id, retries in missing:
                            if retries >= self.MAX_RETRIES:
                                with self._missing_lock:
                                    self._missing_frames.pop(frame_id, None)
                                continue
                            
                            nack = b"NACK" + struct.pack(">H", frame_id)
                            self._retransmit_socket.sendto(
                                nack, 
                                (self._server_ip, self.retransmit_port)
                            )
                            
                            with self._missing_lock:
                                if frame_id in self._missing_frames:
                                    self._missing_frames[frame_id] = retries + 1
                        
                        try:
                            data, _ = self._retransmit_socket.recvfrom(65535)
                            if len(data) >= 2:
                                frame_id = struct.unpack(">H", data[:2])[0]
                                frame_data = data[2:]
                                
                                with self._missing_lock:
                                    self._missing_frames.pop(frame_id, None)
                                
                                if self._on_frame_received:
                                    self._on_frame_received(frame_id, frame_data)
                        except socket.timeout:
                            continue
                            
                    except Exception:
                        continue
                    
                    time.sleep(self.NACK_TIMEOUT)
            
            threading.Thread(target=nack_loop, daemon=True).start()
            return True
        except Exception:
            return False
    
    def stop(self):
        """停止重传机制"""
        self._running = False
        if self._retransmit_socket:
            try:
                self._retransmit_socket.close()
            except:
                pass
    
    def buffer_frame(self, frame_id: int, frame_data: bytes):
        """缓存帧用于重传（服务端）"""
        with self._buffer_lock:
            if len(self._frame_ids) >= self.FRAME_BUFFER_SIZE:
                old_id = self._frame_ids.popleft()
                self._frame_buffer.pop(old_id, None)
            
            self._frame_ids.append(frame_id)
            self._frame_buffer[frame_id] = frame_data
    
    def _get_buffered_frame(self, frame_id: int) -> Optional[bytes]:
        """获取缓存的帧"""
        with self._buffer_lock:
            return self._frame_buffer.get(frame_id)
    
    def check_frame(self, frame_id: int) -> bool:
        """检查帧是否丢失（客户端）"""
        if frame_id == self._expected_frame_id:
            self._expected_frame_id = (frame_id + 1) % 65536
            return True
        
        if self._is_frame_missing(frame_id):
            return True
        
        missing_start = self._expected_frame_id
        missing_end = frame_id
        
        if missing_end < missing_start:
            missing_end += 65536
        
        with self._missing_lock:
            for i in range(missing_start, missing_end):
                missing_id = i % 65536
                if missing_id not in self._missing_frames:
                    self._missing_frames[missing_id] = 0
        
        self._expected_frame_id = (frame_id + 1) % 65536
        return False
    
    def _is_frame_missing(self, frame_id: int) -> bool:
        """检查帧是否在丢失列表中"""
        with self._missing_lock:
            return frame_id in self._missing_frames
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._buffer_lock:
            buffered = len(self._frame_buffer)
        with self._missing_lock:
            missing = len(self._missing_frames)
        
        return {
            "buffered_frames": buffered,
            "missing_frames": missing,
            "expected_frame_id": self._expected_frame_id
        }
