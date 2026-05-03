import sys
from pathlib import Path

# 项目路径注入
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PySide6.QtWidgets import QApplication
from src.unishare.gui.main_window import MainWindow
from src.unishare.core.logger import log

def main():
    log.info("=" * 50)
    log.info("UniShare 程序启动")
    log.info("=" * 50)

    app = QApplication(sys.argv)
    app.setApplicationName("UniShare")
    app.setApplicationVersion("0.1.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
