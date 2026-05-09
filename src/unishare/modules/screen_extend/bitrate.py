"""
Adaptive Bitrate Controller - 根据网络状况动态调整推流码率
"""
from collections import deque
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class BitrateSettings:
    quality: int
    fps: int


class AdaptiveBitrateController:
    """
    自适应码率控制器
    根据网络延迟和丢包率动态调整推流质量
    """
    
    LATENCY_TIERS = [
        (50, BitrateSettings(90, 30)),
        (100, BitrateSettings(75, 25)),
        (200, BitrateSettings(60, 20)),
        (float('inf'), BitrateSettings(50, 15)),
    ]
    
    def __init__(self, default_quality: int = 80, default_fps: int = 30):
        self.current_quality = default_quality
        self.current_fps = default_fps
        self.min_quality = 30
        self.max_quality = 95
        self.min_fps = 15
        self.max_fps = 60
        
        self.latency_history: deque = deque(maxlen=10)
        self.loss_history: deque = deque(maxlen=10)
        self._last_adjust_time: float = 0
        self._adjust_interval: float = 2.0
        self._stable_count: int = 0
    
    def update_metrics(self, latency_ms: float, packet_loss: float):
        """更新网络指标"""
        self.latency_history.append(latency_ms)
        self.loss_history.append(packet_loss)
    
    def get_quality_settings(self) -> Tuple[int, int]:
        """根据网络状况返回建议的质量设置"""
        if not self.latency_history:
            return self.current_quality, self.current_fps
        
        avg_latency = sum(self.latency_history) / len(self.latency_history)
        avg_loss = sum(self.loss_history) / len(self.loss_history) if self.loss_history else 0
        
        target_quality = self.current_quality
        target_fps = self.current_fps
        
        for threshold, settings in self.LATENCY_TIERS:
            if avg_latency < threshold:
                target_quality = settings.quality
                target_fps = settings.fps
                break
        
        if avg_loss > 0.05:
            target_quality = max(self.min_quality, target_quality - 10)
        if avg_loss > 0.10:
            target_fps = max(self.min_fps, target_fps - 5)
        
        if target_quality == self.current_quality and target_fps == self.current_fps:
            self._stable_count += 1
        else:
            self._stable_count = 0
        
        if self._stable_count > 5:
            if target_quality < self.max_quality:
                target_quality = min(self.max_quality, target_quality + 5)
                self._stable_count = 0
        
        self.current_quality = max(self.min_quality, min(self.max_quality, target_quality))
        self.current_fps = max(self.min_fps, min(self.max_fps, target_fps))
        
        return self.current_quality, self.current_fps
    
    def reset(self):
        """重置控制器状态"""
        self.latency_history.clear()
        self.loss_history.clear()
        self.current_quality = 80
        self.current_fps = 30
        self._stable_count = 0
    
    def get_stats(self) -> dict:
        """获取当前统计信息"""
        avg_latency = sum(self.latency_history) / len(self.latency_history) if self.latency_history else 0
        avg_loss = sum(self.loss_history) / len(self.loss_history) if self.loss_history else 0
        return {
            "quality": self.current_quality,
            "fps": self.current_fps,
            "avg_latency_ms": round(avg_latency, 1),
            "avg_packet_loss": round(avg_loss, 4),
            "stable_count": self._stable_count,
        }
