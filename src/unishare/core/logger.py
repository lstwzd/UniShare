import structlog
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

def init_logger():
    log_dir = Path.home() / ".unishare" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "unishare.log"

    # 基础日志配置
    logging.basicConfig(level=logging.INFO)
    logger = structlog.get_logger()

    # 文件日志轮转
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)

    # 控制台日志
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 日志格式
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return logger

# 全局单例日志对象
log = init_logger()
