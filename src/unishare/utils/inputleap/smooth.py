"""
Mouse Smoother - 鼠标移动平滑处理
"""
from collections import deque
from typing import Tuple, Optional


class MouseSmoother:
    """
    鼠标移动平滑处理，使用加权平均减少抖动
    """
    
    def __init__(self, buffer_size: int = 3, smoothing_factor: float = 0.3):
        self.position_buffer: deque = deque(maxlen=buffer_size)
        self.smoothing_factor = smoothing_factor
        self._last_smoothed: Optional[Tuple[int, int]] = None
    
    def smooth_move(self, target_x: int, target_y: int) -> Tuple[int, int]:
        """
        应用平滑算法，返回平滑后的坐标
        
        Args:
            target_x: 目标 X 坐标
            target_y: 目标 Y 坐标
        
        Returns:
            平滑后的 (x, y) 坐标
        """
        self.position_buffer.append((target_x, target_y))
        
        if len(self.position_buffer) < 2:
            self._last_smoothed = (target_x, target_y)
            return target_x, target_y
        
        if self._last_smoothed is None:
            self._last_smoothed = (target_x, target_y)
            return target_x, target_y
        
        weighted_x = 0.0
        weighted_y = 0.0
        total_weight = 0.0
        
        for i, (x, y) in enumerate(self.position_buffer):
            weight = (i + 1) * self.smoothing_factor
            weighted_x += x * weight
            weighted_y += y * weight
            total_weight += weight
        
        if total_weight > 0:
            smoothed_x = int(weighted_x / total_weight)
            smoothed_y = int(weighted_y / total_weight)
        else:
            smoothed_x, smoothed_y = target_x, target_y
        
        delta_threshold = 2
        if abs(smoothed_x - self._last_smoothed[0]) < delta_threshold:
            smoothed_x = self._last_smoothed[0]
        if abs(smoothed_y - self._last_smoothed[1]) < delta_threshold:
            smoothed_y = self._last_smoothed[1]
        
        self._last_smoothed = (smoothed_x, smoothed_y)
        return smoothed_x, smoothed_y
    
    def reset(self):
        """重置平滑器状态"""
        self.position_buffer.clear()
        self._last_smoothed = None
    
    def set_buffer_size(self, size: int):
        """设置缓冲区大小"""
        old_buffer = list(self.position_buffer)
        self.position_buffer = deque(maxlen=size)
        self.position_buffer.extend(old_buffer[-size:])
    
    def set_smoothing_factor(self, factor: float):
        """设置平滑因子"""
        self.smoothing_factor = max(0.1, min(1.0, factor))
