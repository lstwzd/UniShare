import yaml
from pathlib import Path
from typing import Dict, Any
from src.unishare.core.logger import log

class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_config()
        return cls._instance

    def _init_config(self):
        self.config_path = Path(__file__).parent.parent.parent.parent / "config" / "unishare-config.yaml"
        self.config_data: Dict[str, Any] = {}
        self.load_config()

    def load_config(self) -> None:
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config_data = yaml.safe_load(f) or {}
                log.info("配置文件加载成功")
            else:
                log.warning("配置文件不存在，使用默认配置")
        except Exception as e:
            log.error(f"配置文件加载失败: {str(e)}")

    def get(self, key: str, default=None):
        keys = key.split(".")
        data = self.config_data
        for k in keys:
            if isinstance(data, dict) and k in data:
                data = data[k]
            else:
                return default
        return data

    def set(self, key: str, value) -> None:
        keys = key.split(".")
        data = self.config_data
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        data[keys[-1]] = value

    def save(self) -> None:
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(self.config_data, f, allow_unicode=True, sort_keys=False)
            log.info("配置文件保存成功")
        except Exception as e:
            log.error(f"配置文件保存失败: {str(e)}")

# 全局配置单例
config = ConfigManager()
