from abc import ABC, abstractmethod
from src.unishare.core.logger import log

class BaseModule(ABC):
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.is_running = False

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    def status(self) -> dict:
        return {
            "name": self.module_name,
            "running": self.is_running
        }

    def log_info(self, msg: str):
        log.info(f"[{self.module_name}] {msg}")

    def log_warning(self, msg: str):
        log.warning(f"[{self.module_name}] {msg}")

    def log_error(self, msg: str):
        log.error(f"[{self.module_name}] {msg}")
