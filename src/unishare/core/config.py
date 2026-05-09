import yaml
import threading
from pathlib import Path
from typing import Dict, Any, Callable, Optional, List
from src.unishare.core.logger import log

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object


class ConfigFileHandler(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    def __init__(self, callback: Callable):
        self.callback = callback
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.yaml'):
            self.callback()


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
        self._change_callbacks: List[Callable[[str, Any, Any], None]] = []
        self._observer: Optional[Any] = None
        self._watching = False
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

    def watch_file(self) -> bool:
        """监听配置文件变化"""
        if not WATCHDOG_AVAILABLE:
            log.warning("watchdog 库未安装，无法监听配置文件变化")
            return False
        
        if self._watching:
            return True
        
        try:
            self._observer = Observer()
            handler = ConfigFileHandler(self._on_file_changed)
            self._observer.schedule(handler, str(self.config_path.parent), recursive=False)
            self._observer.start()
            self._watching = True
            log.info("配置文件监听已启动")
            return True
        except Exception as e:
            log.error(f"启动配置文件监听失败: {str(e)}")
            return False

    def stop_watching(self):
        """停止监听配置文件"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        self._watching = False

    def _on_file_changed(self):
        """配置文件变化回调"""
        old_data = self.config_data.copy()
        self.load_config()
        
        for key in self._get_changed_keys(old_data, self.config_data):
            old_value = self._get_nested_value(old_data, key)
            new_value = self._get_nested_value(self.config_data, key)
            self.notify_change(key, old_value, new_value)

    def register_change_callback(self, callback: Callable[[str, Any, Any], None]):
        """注册配置变更回调"""
        self._change_callbacks.append(callback)

    def unregister_change_callback(self, callback: Callable):
        """注销配置变更回调"""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)

    def notify_change(self, key: str, old_value: Any, new_value: Any):
        """通知配置变更"""
        for callback in self._change_callbacks:
            try:
                callback(key, old_value, new_value)
            except Exception as e:
                log.error(f"配置变更回调执行失败: {str(e)}")

    def hot_update(self, key: str, value: Any) -> bool:
        """热更新配置项"""
        hot_updateable = [
            "screen_extend.fps",
            "screen_extend.quality",
            "screen_extend.extend_direction",
            "input_share.mouse_smooth",
            "drag_share.save_path",
        ]
        
        if key not in hot_updateable:
            log.warning(f"配置项 {key} 不支持热更新")
            return False
        
        old_value = self.get(key)
        self.set(key, value)
        self.notify_change(key, old_value, value)
        log.info(f"配置热更新: {key} = {value}")
        return True

    def _get_nested_value(self, data: Dict, key: str) -> Any:
        """获取嵌套字典的值"""
        keys = key.split(".")
        for k in keys:
            if isinstance(data, dict) and k in data:
                data = data[k]
            else:
                return None
        return data

    def _get_changed_keys(self, old: Dict, new: Dict, prefix: str = "") -> List[str]:
        """获取变更的配置键"""
        changed = []
        all_keys = set(old.keys()) | set(new.keys())
        
        for key in all_keys:
            full_key = f"{prefix}.{key}" if prefix else key
            old_val = old.get(key)
            new_val = new.get(key)
            
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                changed.extend(self._get_changed_keys(old_val, new_val, full_key))
            elif old_val != new_val:
                changed.append(full_key)
        
        return changed


config = ConfigManager()
