from src.unishare.modules.base import BaseModule
from src.unishare.core.config import config

class InputShareModule(BaseModule):
    def __init__(self):
        super().__init__("键鼠共享模块")
        self.enabled = config.get("input_share.enabled", True)

    def start(self):
        if not self.enabled:
            self.log_info("键鼠共享功能已关闭")
            return
        self.is_running = True
        self.log_info("键鼠共享模块启动成功")

    def stop(self):
        self.is_running = False
        self.log_info("键鼠共享模块已停止")
