from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTabWidget, QPushButton, QListWidget,
    QListWidgetItem, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from src.unishare.core.discovery import discovery
from src.unishare.modules.input_share import InputShareModule
from src.unishare.modules.usb_share import USBShareModule
from src.unishare.modules.file_share import FileShareModule
from src.unishare.core.logger import log

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UniShare - 全平台跨机共享工具 V0.1.0")
        self.setMinimumSize(1200, 800)
        self.resize(1200, 800)

        # 初始化模块
        self.input_module = InputShareModule()
        self.usb_module = USBShareModule()
        self.file_module = FileShareModule()

        # 界面初始化
        self.init_ui()
        self.start_all_modules()

        # 设备刷新定时器
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_device_list)
        self.refresh_timer.start(2000)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 标题
        title_label = QLabel("UniShare 跨设备共享中心")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        main_layout.addWidget(title_label)

        # 分页标签
        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Microsoft YaHei", 11))

        self.init_device_tab()
        self.init_input_tab()
        self.init_usb_tab()
        self.init_file_tab()
        self.init_setting_tab()

        main_layout.addWidget(self.tabs)

    def init_device_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        tip = QLabel("当前局域网在线设备（自动刷新）")
        tip.setFont(QFont("Microsoft YaHei", 12))
        layout.addWidget(tip)

        self.device_list = QListWidget()
        self.device_list.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(self.device_list)

        self.tabs.addTab(page, "🔍 设备发现")

    def init_input_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        tip = QLabel("🖱️ 键鼠共享模块运行中\n支持多设备屏幕联动、鼠标边缘切换、键盘同步输入")
        tip.setAlignment(Qt.AlignCenter)
        tip.setFont(QFont("Microsoft YaHei", 12))
        layout.addWidget(tip)
        self.tabs.addTab(page, "🖱️ 键鼠共享")

    def init_usb_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        tip = QLabel("💾 USB设备共享模块运行中\n支持U盘、打印机、加密狗等设备跨网络挂载")
        tip.setAlignment(Qt.AlignCenter)
        tip.setFont(QFont("Microsoft YaHei", 12))
        layout.addWidget(tip)
        self.tabs.addTab(page, "💾 USB共享")

    def init_file_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        tip = QLabel("📤 文件传输模块运行中\n局域网高速互传、文件夹同步、断点续传")
        tip.setAlignment(Qt.AlignCenter)
        tip.setFont(QFont("Microsoft YaHei", 12))
        layout.addWidget(tip)
        self.tabs.addTab(page, "📤 文件传输")

    def init_setting_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        tip = QLabel("⚙️ 全局设置\n端口配置、加密开关、自动同步、设备管理")
        tip.setAlignment(Qt.AlignCenter)
        tip.setFont(QFont("Microsoft YaHei", 12))
        layout.addWidget(tip)
        self.tabs.addTab(page, "⚙️ 全局设置")

    def start_all_modules(self):
        discovery.start()
        self.input_module.start()
        self.usb_module.start()
        self.file_module.start()
        log.info("所有功能模块启动完成")

    def refresh_device_list(self):
        self.device_list.clear()
        devices = discovery.get_online_devices()
        if not devices:
            item = QListWidgetItem("暂无在线设备")
            item.setTextAlignment(Qt.AlignCenter)
            self.device_list.addItem(item)
            return

        for dev in devices:
            info = f"设备名：{dev['name']} | IP：{dev['ip']} | 版本：{dev['version']}"
            self.device_list.addItem(info)

    def closeEvent(self, event):
        # 窗口关闭时释放资源
        self.refresh_timer.stop()
        discovery.stop()
        self.input_module.stop()
        self.usb_module.stop()
        self.file_module.stop()
        log.info("程序正常退出")
        event.accept()
