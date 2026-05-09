"""
Multi-Monitor Manager - 多显示器选择和管理
"""
from typing import List, Optional, Dict
from dataclasses import dataclass


@dataclass
class MonitorInfo:
    index: int
    width: int
    height: int
    left: int
    top: int
    
    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"
    
    @property
    def position(self) -> str:
        return f"({self.left}, {self.top})"
    
    def to_dict(self) -> Dict:
        return {
            "index": self.index,
            "width": self.width,
            "height": self.height,
            "left": self.left,
            "top": self.top,
            "resolution": self.resolution,
        }


class MultiMonitorManager:
    """
    多显示器管理器
    支持扫描和选择要推流的显示器
    """
    
    def __init__(self):
        self.monitors: List[MonitorInfo] = []
        self.selected_monitor: int = 1
        self._mss_available = False
        self._check_mss()
    
    def _check_mss(self):
        """检查 mss 库是否可用"""
        try:
            import mss
            self._mss_available = True
        except ImportError:
            self._mss_available = False
    
    def scan_monitors(self) -> List[MonitorInfo]:
        """扫描所有显示器"""
        if not self._mss_available:
            self.monitors = [MonitorInfo(
                index=1,
                width=1920,
                height=1080,
                left=0,
                top=0
            )]
            return self.monitors
        
        try:
            import mss
            with mss.mss() as sct:
                self.monitors = []
                for i, mon in enumerate(sct.monitors[1:], start=1):
                    self.monitors.append(MonitorInfo(
                        index=i,
                        width=mon["width"],
                        height=mon["height"],
                        left=mon["left"],
                        top=mon["top"]
                    ))
        except Exception as e:
            self.monitors = [MonitorInfo(
                index=1,
                width=1920,
                height=1080,
                left=0,
                top=0
            )]
        
        return self.monitors
    
    def select_monitor(self, index: int) -> bool:
        """选择要推流的显示器"""
        if 1 <= index <= len(self.monitors):
            self.selected_monitor = index
            return True
        return False
    
    def get_selected_monitor(self) -> Optional[MonitorInfo]:
        """获取当前选择的显示器"""
        for mon in self.monitors:
            if mon.index == self.selected_monitor:
                return mon
        return self.monitors[0] if self.monitors else None
    
    def get_monitor_count(self) -> int:
        """获取显示器数量"""
        return len(self.monitors)
    
    def get_monitor_dict(self, index: int) -> Optional[Dict]:
        """获取指定显示器的字典表示"""
        for mon in self.monitors:
            if mon.index == index:
                return mon.to_dict()
        return None
    
    def get_all_monitors(self) -> List[Dict]:
        """获取所有显示器的字典列表"""
        return [mon.to_dict() for mon in self.monitors]
    
    def get_capture_region(self) -> Optional[Dict]:
        """获取当前选择显示器的捕获区域"""
        mon = self.get_selected_monitor()
        if mon:
            return {
                "left": mon.left,
                "top": mon.top,
                "width": mon.width,
                "height": mon.height,
            }
        return None
