import sys
import platform

class PlatformUtil:
    @staticmethod
    def is_windows() -> bool:
        return sys.platform.startswith("win")

    @staticmethod
    def is_macos() -> bool:
        return sys.platform == "darwin"

    @staticmethod
    def is_linux() -> bool:
        return sys.platform.startswith("linux")

    @staticmethod
    def get_system_name() -> str:
        if PlatformUtil.is_windows():
            return "Windows"
        elif PlatformUtil.is_macos():
            return "macOS"
        elif PlatformUtil.is_linux():
            return "Linux"
        return "Unknown"

    @staticmethod
    def get_system_version() -> str:
        return platform.version()

# 全局平台工具实例
platform_util = PlatformUtil()
