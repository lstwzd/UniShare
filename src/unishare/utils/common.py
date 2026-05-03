import os
import time
import uuid
from pathlib import Path

class CommonUtil:
    @staticmethod
    def generate_device_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def get_app_data_path() -> Path:
        if sys.platform.startswith("win"):
            return Path(os.environ["APPDATA"]) / "UniShare"
        elif sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "UniShare"
        else:
            return Path.home() / ".unishare"

    @staticmethod
    def format_file_size(size: int) -> str:
        units = ["B", "KB", "MB", "GB"]
        index = 0
        while size > 1024 and index < len(units) - 1:
            size /= 1024
            index += 1
        return f"{round(size, 2)} {units[index]}"

common_util = CommonUtil()
