from src.unishare.modules.base import BaseModule
from src.unishare.core.config import config

class FileShareModule(BaseModule):
    def __init__(self):
        super().__init__("文件传输模块")
        self.enabled = config.get("file_share.temp_transfer_enabled", True)

    def start(self):
        if not self.enabled:
            self.log_info("文件传输功能已关闭")
            return
        self.is_running = True
        self.log_info("文件传输模块启动成功")

    def stop(self):
        self.is_running = False
        self.log_info("文件传输模块已停止")
