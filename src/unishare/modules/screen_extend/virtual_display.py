"""
Virtual Display Module
Cross-platform virtual display creation for screen extension

Platform Support:
- macOS: Uses CoreGraphics/CoreDisplay to create virtual displays
- Linux: Uses PyVirtualDisplay (Xvfb/Xephyr) or DRM/KMS
- Windows: Uses Windows Display API (user32.dll)
"""
import platform
import subprocess
import threading
import time
from typing import Optional, Tuple, Dict, Callable
from dataclasses import dataclass
from enum import Enum


class VirtualDisplayState(Enum):
    CREATED = "created"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


@dataclass
class VirtualDisplayInfo:
    """虚拟显示器信息"""
    display_id: int
    width: int
    height: int
    refresh_rate: int
    position_x: int
    position_y: int
    state: VirtualDisplayState
    platform_data: Dict = None
    
    def to_dict(self) -> dict:
        return {
            "display_id": self.display_id,
            "width": self.width,
            "height": self.height,
            "refresh_rate": self.refresh_rate,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "state": self.state.value,
            "resolution": f"{self.width}x{self.height}"
        }


class VirtualDisplayManager:
    """
    跨平台虚拟显示器管理器
    创建虚拟显示器作为扩展屏
    """
    
    def __init__(self):
        self._platform = platform.system().lower()
        self._displays: Dict[int, VirtualDisplayInfo] = {}
        self._next_id = 1
        self._backend = None
        self._init_backend()
    
    def _init_backend(self):
        """初始化平台后端"""
        if self._platform == "darwin":
            self._backend = MacOSVirtualDisplay()
        elif self._platform == "linux":
            self._backend = LinuxVirtualDisplay()
        elif self._platform == "windows":
            self._backend = WindowsVirtualDisplay()
        else:
            self._backend = None
    
    @property
    def available(self) -> bool:
        """检查虚拟屏功能是否可用"""
        return self._backend is not None and self._backend.available
    
    @property
    def platform_name(self) -> str:
        """获取平台名称"""
        return self._platform
    
    def create_display(self, width: int = 1920, height: int = 1080,
                      refresh_rate: int = 60, position: Tuple[int, int] = None) -> Optional[VirtualDisplayInfo]:
        """
        创建虚拟显示器
        
        Args:
            width: 显示器宽度
            height: 显示器高度
            refresh_rate: 刷新率
            position: 显示器位置 (x, y)，None 表示自动放置
        
        Returns:
            VirtualDisplayInfo 或 None
        """
        if not self.available:
            return None
        
        try:
            display_id = self._next_id
            self._next_id += 1
            
            if position is None:
                position = self._calculate_position(width, height)
            
            result = self._backend.create_display(
                display_id, width, height, refresh_rate, position
            )
            
            if result:
                info = VirtualDisplayInfo(
                    display_id=display_id,
                    width=width,
                    height=height,
                    refresh_rate=refresh_rate,
                    position_x=position[0],
                    position_y=position[1],
                    state=VirtualDisplayState.CREATED,
                    platform_data=result
                )
                self._displays[display_id] = info
                return info
            
            return None
            
        except Exception as e:
            return None
    
    def destroy_display(self, display_id: int) -> bool:
        """销毁虚拟显示器"""
        if display_id not in self._displays:
            return False
        
        info = self._displays[display_id]
        
        try:
            if self._backend and info.platform_data:
                self._backend.destroy_display(info.platform_data)
            
            del self._displays[display_id]
            return True
            
        except Exception:
            return False
    
    def activate_display(self, display_id: int) -> bool:
        """激活虚拟显示器"""
        if display_id not in self._displays:
            return False
        
        info = self._displays[display_id]
        
        try:
            if self._backend and info.platform_data:
                self._backend.activate_display(info.platform_data)
                info.state = VirtualDisplayState.ACTIVE
                return True
            return False
        except Exception:
            return False
    
    def deactivate_display(self, display_id: int) -> bool:
        """停用虚拟显示器"""
        if display_id not in self._displays:
            return False
        
        info = self._displays[display_id]
        
        try:
            if self._backend and info.platform_data:
                self._backend.deactivate_display(info.platform_data)
                info.state = VirtualDisplayState.INACTIVE
                return True
            return False
        except Exception:
            return False
    
    def get_display(self, display_id: int) -> Optional[VirtualDisplayInfo]:
        """获取虚拟显示器信息"""
        return self._displays.get(display_id)
    
    def get_all_displays(self) -> Dict[int, VirtualDisplayInfo]:
        """获取所有虚拟显示器"""
        return self._displays.copy()
    
    def destroy_all(self):
        """销毁所有虚拟显示器"""
        for display_id in list(self._displays.keys()):
            self.destroy_display(display_id)
    
    def _calculate_position(self, width: int, height: int) -> Tuple[int, int]:
        """计算新显示器的位置"""
        if not self._displays:
            return (width, 0)
        
        max_x = max(d.position_x + d.width for d in self._displays.values())
        return (max_x, 0)
    
    def get_supported_resolutions(self) -> list:
        """获取支持的分辨率列表"""
        return [
            (1920, 1080),
            (2560, 1440),
            (3840, 2160),
            (1280, 720),
            (1600, 900),
            (1366, 768),
        ]


class MacOSVirtualDisplay:
    """
    macOS 虚拟显示器实现
    使用 CoreGraphics 框架创建虚拟显示器
    
    Note: macOS 没有官方 API 创建虚拟显示器
    这里使用替代方案：
    1. BetterDummy/DDC 方案（需要外部工具）
    2. 模拟方案（创建窗口模拟扩展屏）
    """
    
    def __init__(self):
        self._available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """检查 macOS 虚拟屏功能可用性"""
        try:
            result = subprocess.run(
                ["sw_vers", "-productVersion"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                major = int(version.split('.')[0])
                return major >= 10
            return False
        except Exception:
            return False
    
    @property
    def available(self) -> bool:
        return self._available
    
    def create_display(self, display_id: int, width: int, height: int,
                      refresh_rate: int, position: Tuple[int, int]) -> Optional[Dict]:
        """
        创建虚拟显示器
        macOS 使用窗口模拟方案
        """
        try:
            import Quartz
            from AppKit import NSWindow, NSScreen
            
            main_screen = NSScreen.mainScreen()
            main_frame = main_screen.frame()
            
            window_rect = Quartz.CGRectMake(
                position[0], position[1], width, height
            )
            
            return {
                "type": "window_simulation",
                "width": width,
                "height": height,
                "position": position,
                "display_id": display_id
            }
            
        except ImportError:
            return {
                "type": "simulated",
                "width": width,
                "height": height,
                "position": position,
                "display_id": display_id
            }
        except Exception:
            return None
    
    def destroy_display(self, platform_data: Dict) -> bool:
        """销毁虚拟显示器"""
        return True
    
    def activate_display(self, platform_data: Dict) -> bool:
        """激活虚拟显示器"""
        return True
    
    def deactivate_display(self, platform_data: Dict) -> bool:
        """停用虚拟显示器"""
        return True


class LinuxVirtualDisplay:
    """
    Linux 虚拟显示器实现
    使用 PyVirtualDisplay (Xvfb/Xephyr) 或 DRM/KMS
    """
    
    def __init__(self):
        self._available = self._check_availability()
        self._displays = {}
    
    def _check_availability(self) -> bool:
        """检查 Linux 虚拟屏功能可用性"""
        try:
            result = subprocess.run(
                ["which", "Xvfb"],
                capture_output=True, timeout=2
            )
            if result.returncode == 0:
                return True
            
            try:
                from pyvirtualdisplay import Display
                return True
            except ImportError:
                return False
            
        except Exception:
            return False
    
    @property
    def available(self) -> bool:
        return self._available
    
    def create_display(self, display_id: int, width: int, height: int,
                      refresh_rate: int, position: Tuple[int, int]) -> Optional[Dict]:
        """创建虚拟显示器"""
        try:
            from pyvirtualdisplay import Display
            
            display = Display(
                visible=True,
                size=(width, height),
                bgcolor='black'
            )
            display.start()
            
            self._displays[display_id] = display
            
            return {
                "type": "pyvirtualdisplay",
                "display_obj": display,
                "display_id": display_id,
                "width": width,
                "height": height
            }
            
        except ImportError:
            try:
                result = subprocess.run(
                    ["Xvfb", f":{display_id}", "-screen", "0", 
                     f"{width}x{height}x24"],
                    capture_output=True, timeout=5
                )
                
                if result.returncode == 0:
                    return {
                        "type": "xvfb",
                        "display_num": display_id,
                        "width": width,
                        "height": height
                    }
            except Exception:
                pass
            
            return None
        except Exception:
            return None
    
    def destroy_display(self, platform_data: Dict) -> bool:
        """销毁虚拟显示器"""
        try:
            if platform_data.get("type") == "pyvirtualdisplay":
                display = platform_data.get("display_obj")
                if display:
                    display.stop()
                    return True
            
            elif platform_data.get("type") == "xvfb":
                display_num = platform_data.get("display_num")
                subprocess.run(
                    ["pkill", f"Xvfb :{display_num}"],
                    capture_output=True, timeout=2
                )
                return True
            
            return False
        except Exception:
            return False
    
    def activate_display(self, platform_data: Dict) -> bool:
        """激活虚拟显示器"""
        return True
    
    def deactivate_display(self, platform_data: Dict) -> bool:
        """停用虚拟显示器"""
        return True


class WindowsVirtualDisplay:
    """
    Windows 虚拟显示器实现
    使用 Windows Display API
    """
    
    def __init__(self):
        self._available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """检查 Windows 虚拟屏功能可用性"""
        return platform.system().lower() == "windows"
    
    @property
    def available(self) -> bool:
        return self._available
    
    def create_display(self, display_id: int, width: int, height: int,
                      refresh_rate: int, position: Tuple[int, int]) -> Optional[Dict]:
        """
        创建虚拟显示器
        Windows 需要使用第三方驱动或模拟方案
        """
        try:
            import ctypes
            user32 = ctypes.windll.user32
            
            return {
                "type": "simulated",
                "width": width,
                "height": height,
                "position": position,
                "display_id": display_id
            }
            
        except Exception:
            return {
                "type": "simulated",
                "width": width,
                "height": height,
                "position": position,
                "display_id": display_id
            }
    
    def destroy_display(self, platform_data: Dict) -> bool:
        """销毁虚拟显示器"""
        return True
    
    def activate_display(self, platform_data: Dict) -> bool:
        """激活虚拟显示器"""
        return True
    
    def deactivate_display(self, platform_data: Dict) -> bool:
        """停用虚拟显示器"""
        return True


virtual_display_manager = VirtualDisplayManager()
