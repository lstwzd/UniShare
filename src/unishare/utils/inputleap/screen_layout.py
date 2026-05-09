"""
Screen Layout Manager - 管理多设备屏幕布局和边界检测
"""
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class Direction(Enum):
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


@dataclass
class ScreenInfo:
    device_id: str
    width: int
    height: int
    position: Tuple[int, int]
    is_local: bool
    
    @property
    def left(self) -> int:
        return self.position[0]
    
    @property
    def right(self) -> int:
        return self.position[0] + self.width
    
    @property
    def top(self) -> int:
        return self.position[1]
    
    @property
    def bottom(self) -> int:
        return self.position[1] + self.height
    
    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom


class ScreenLayoutManager:
    """
    管理多设备屏幕布局，实现边界检测和设备切换
    """
    
    def __init__(self, boundary_threshold: int = 5):
        self.screens: Dict[str, ScreenInfo] = {}
        self.current_screen: str = "local"
        self.boundary_threshold = boundary_threshold
        self._switch_callback = None
    
    def set_switch_callback(self, callback):
        """设置屏幕切换回调函数"""
        self._switch_callback = callback
    
    def add_screen(self, device_id: str, width: int, height: int,
                   position: Tuple[int, int], is_local: bool = False):
        """添加屏幕到布局"""
        self.screens[device_id] = ScreenInfo(
            device_id=device_id,
            width=width,
            height=height,
            position=position,
            is_local=is_local
        )
    
    def remove_screen(self, device_id: str):
        """移除屏幕"""
        if device_id in self.screens:
            del self.screens[device_id]
    
    def get_screen(self, device_id: str) -> Optional[ScreenInfo]:
        """获取指定设备的屏幕信息"""
        return self.screens.get(device_id)
    
    def get_current_screen(self) -> Optional[ScreenInfo]:
        """获取当前屏幕"""
        return self.screens.get(self.current_screen)
    
    def check_boundary(self, x: int, y: int) -> Optional[Tuple[str, Direction]]:
        """
        检查鼠标是否触及边界
        
        Returns:
            如果触及边界，返回 (目标设备ID, 方向)；否则返回 None
        """
        current = self.get_current_screen()
        if not current:
            return None
        
        for device_id, screen in self.screens.items():
            if device_id == self.current_screen:
                continue
            
            if self._is_adjacent(current, screen):
                direction = self._get_adjacent_direction(current, screen)
                if self._at_boundary(x, y, current, direction):
                    return (device_id, direction)
        
        return None
    
    def _is_adjacent(self, screen1: ScreenInfo, screen2: ScreenInfo) -> bool:
        """检查两个屏幕是否相邻"""
        horizontal_adjacent = (
            abs(screen1.right - screen2.left) <= self.boundary_threshold or
            abs(screen1.left - screen2.right) <= self.boundary_threshold
        ) and not (screen1.top >= screen2.bottom or screen1.bottom <= screen2.top)
        
        vertical_adjacent = (
            abs(screen1.bottom - screen2.top) <= self.boundary_threshold or
            abs(screen1.top - screen2.bottom) <= self.boundary_threshold
        ) and not (screen1.left >= screen2.right or screen1.right <= screen2.left)
        
        return horizontal_adjacent or vertical_adjacent
    
    def _get_adjacent_direction(self, from_screen: ScreenInfo, to_screen: ScreenInfo) -> Direction:
        """获取相邻屏幕的方向"""
        if to_screen.left >= from_screen.right:
            return Direction.RIGHT
        elif to_screen.right <= from_screen.left:
            return Direction.LEFT
        elif to_screen.top >= from_screen.bottom:
            return Direction.BOTTOM
        else:
            return Direction.TOP
    
    def _at_boundary(self, x: int, y: int, screen: ScreenInfo, direction: Direction) -> bool:
        """检查坐标是否在指定方向的边界"""
        threshold = self.boundary_threshold
        
        if direction == Direction.RIGHT:
            return screen.right - threshold <= x <= screen.right and screen.top <= y <= screen.bottom
        elif direction == Direction.LEFT:
            return screen.left <= x <= screen.left + threshold and screen.top <= y <= screen.bottom
        elif direction == Direction.BOTTOM:
            return screen.bottom - threshold <= y <= screen.bottom and screen.left <= x <= screen.right
        else:
            return screen.top <= y <= screen.top + threshold and screen.left <= x <= screen.right
    
    def switch_control(self, target_device: str, position: Optional[Tuple[int, int]] = None) -> bool:
        """
        切换控制权到目标设备
        
        Args:
            target_device: 目标设备 ID
            position: 可选的鼠标位置（在目标屏幕上的位置）
        
        Returns:
            切换是否成功
        """
        if target_device not in self.screens:
            return False
        
        old_screen = self.current_screen
        self.current_screen = target_device
        
        if self._switch_callback:
            self._switch_callback(old_screen, target_device, position)
        
        return True
    
    def get_all_screens(self) -> Dict[str, ScreenInfo]:
        """获取所有屏幕"""
        return self.screens.copy()
    
    def clear(self):
        """清除所有屏幕"""
        self.screens.clear()
        self.current_screen = "local"
