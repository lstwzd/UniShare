"""
File Transfer Progress Module
Tracks and reports file transfer progress
"""
import time
import threading
from typing import Dict, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class TransferState(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TransferProgress:
    """传输进度信息"""
    transfer_id: str
    filename: str
    file_path: str
    total_size: int
    transferred_size: int = 0
    state: TransferState = TransferState.PENDING
    start_time: float = 0.0
    end_time: float = 0.0
    error_message: str = ""
    speed: float = 0.0
    
    @property
    def percent(self) -> float:
        if self.total_size == 0:
            return 0.0
        return (self.transferred_size / self.total_size) * 100
    
    @property
    def elapsed_time(self) -> float:
        if self.start_time == 0:
            return 0.0
        end = self.end_time if self.end_time > 0 else time.time()
        return end - self.start_time
    
    @property
    def remaining_time(self) -> float:
        if self.speed <= 0 or self.transferred_size >= self.total_size:
            return 0.0
        remaining_bytes = self.total_size - self.transferred_size
        return remaining_bytes / self.speed
    
    def to_dict(self) -> dict:
        return {
            "transfer_id": self.transfer_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "total_size": self.total_size,
            "transferred_size": self.transferred_size,
            "percent": round(self.percent, 2),
            "state": self.state.value,
            "elapsed_time": round(self.elapsed_time, 2),
            "remaining_time": round(self.remaining_time, 2),
            "speed": round(self.speed, 2),
            "error_message": self.error_message
        }


class TransferProgressTracker:
    """
    传输进度跟踪器
    - 跟踪多个并发传输
    - 计算传输速度
    - 提供进度回调
    """
    
    SPEED_SAMPLE_SIZE = 10
    SPEED_CALC_INTERVAL = 0.5
    
    def __init__(self):
        self._transfers: Dict[str, TransferProgress] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._speed_samples: Dict[str, list] = {}
        self._lock = threading.Lock()
    
    def create_transfer(self, transfer_id: str, filename: str, 
                       file_path: str, total_size: int) -> TransferProgress:
        """创建新传输"""
        with self._lock:
            progress = TransferProgress(
                transfer_id=transfer_id,
                filename=filename,
                file_path=file_path,
                total_size=total_size,
                state=TransferState.PENDING
            )
            self._transfers[transfer_id] = progress
            self._speed_samples[transfer_id] = []
            return progress
    
    def start_transfer(self, transfer_id: str):
        """开始传输"""
        with self._lock:
            if transfer_id in self._transfers:
                self._transfers[transfer_id].state = TransferState.IN_PROGRESS
                self._transfers[transfer_id].start_time = time.time()
    
    def update_progress(self, transfer_id: str, transferred_size: int):
        """更新传输进度"""
        with self._lock:
            if transfer_id not in self._transfers:
                return
            
            transfer = self._transfers[transfer_id]
            transfer.transferred_size = transferred_size
            
            current_time = time.time()
            samples = self._speed_samples.get(transfer_id, [])
            
            samples.append({
                "size": transferred_size,
                "time": current_time
            })
            
            if len(samples) > self.SPEED_SAMPLE_SIZE:
                samples.pop(0)
            
            if len(samples) >= 2:
                size_diff = samples[-1]["size"] - samples[0]["size"]
                time_diff = samples[-1]["time"] - samples[0]["time"]
                if time_diff > 0:
                    transfer.speed = size_diff / time_diff
            
            self._notify_callback(transfer_id)
    
    def complete_transfer(self, transfer_id: str):
        """完成传输"""
        with self._lock:
            if transfer_id in self._transfers:
                transfer = self._transfers[transfer_id]
                transfer.state = TransferState.COMPLETED
                transfer.transferred_size = transfer.total_size
                transfer.end_time = time.time()
                self._notify_callback(transfer_id)
    
    def fail_transfer(self, transfer_id: str, error: str):
        """传输失败"""
        with self._lock:
            if transfer_id in self._transfers:
                transfer = self._transfers[transfer_id]
                transfer.state = TransferState.FAILED
                transfer.error_message = error
                transfer.end_time = time.time()
                self._notify_callback(transfer_id)
    
    def cancel_transfer(self, transfer_id: str):
        """取消传输"""
        with self._lock:
            if transfer_id in self._transfers:
                transfer = self._transfers[transfer_id]
                transfer.state = TransferState.CANCELLED
                transfer.end_time = time.time()
                self._notify_callback(transfer_id)
    
    def pause_transfer(self, transfer_id: str):
        """暂停传输"""
        with self._lock:
            if transfer_id in self._transfers:
                self._transfers[transfer_id].state = TransferState.PAUSED
                self._notify_callback(transfer_id)
    
    def resume_transfer(self, transfer_id: str):
        """恢复传输"""
        with self._lock:
            if transfer_id in self._transfers:
                self._transfers[transfer_id].state = TransferState.IN_PROGRESS
                self._notify_callback(transfer_id)
    
    def get_transfer(self, transfer_id: str) -> Optional[TransferProgress]:
        """获取传输进度"""
        with self._lock:
            return self._transfers.get(transfer_id)
    
    def get_all_transfers(self) -> Dict[str, TransferProgress]:
        """获取所有传输"""
        with self._lock:
            return self._transfers.copy()
    
    def remove_transfer(self, transfer_id: str):
        """移除传输记录"""
        with self._lock:
            self._transfers.pop(transfer_id, None)
            self._speed_samples.pop(transfer_id, None)
            self._callbacks.pop(transfer_id, None)
    
    def register_callback(self, transfer_id: str, callback: Callable):
        """注册进度回调"""
        with self._lock:
            self._callbacks[transfer_id] = callback
    
    def _notify_callback(self, transfer_id: str):
        """通知回调"""
        if transfer_id in self._callbacks:
            try:
                transfer = self._transfers.get(transfer_id)
                if transfer:
                    self._callbacks[transfer_id](transfer)
            except Exception:
                pass
    
    def get_active_count(self) -> int:
        """获取活动传输数量"""
        with self._lock:
            return sum(
                1 for t in self._transfers.values()
                if t.state == TransferState.IN_PROGRESS
            )
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._lock:
            total = len(self._transfers)
            completed = sum(1 for t in self._transfers.values() if t.state == TransferState.COMPLETED)
            failed = sum(1 for t in self._transfers.values() if t.state == TransferState.FAILED)
            active = sum(1 for t in self._transfers.values() if t.state == TransferState.IN_PROGRESS)
            
            total_bytes = sum(t.total_size for t in self._transfers.values())
            transferred_bytes = sum(t.transferred_size for t in self._transfers.values())
            
            return {
                "total_transfers": total,
                "completed": completed,
                "failed": failed,
                "active": active,
                "total_bytes": total_bytes,
                "transferred_bytes": transferred_bytes
            }
