import threading
import sys
import os
from io import BytesIO

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTabWidget, QPushButton, QListWidget,
    QListWidgetItem, QTextEdit, QGroupBox, QGridLayout,
    QComboBox, QCheckBox, QLineEdit, QSpinBox,
    QTreeWidget, QTreeWidgetItem, QMessageBox,
    QScrollArea, QCheckBox,
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import (
    QFont, QPalette, QColor, QIcon, QPixmap, QImage,
    QDragEnterEvent, QDropEvent
)

from src.unishare.core.discovery import discovery
from src.unishare.modules.input_share import InputLeapModule
from src.unishare.modules.usb_share import USBShareModule
from src.unishare.modules.screen_extend import ScreenExtendModule
from src.unishare.core.logger import log
from src.unishare.core.config import config


class DragDropWindow(QWidget):
    """
    全屏拖拽窗口 - 客户端显示扩展屏，支持拖入文件发送到服务端
    """
    file_dropped = Signal(str)

    def __init__(self, screen_extend_module: ScreenExtendModule):
        super().__init__()
        self.screen_extend = screen_extend_module
        self.setWindowTitle("UniShare 扩展屏")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAcceptDrops(True)
        self.setCursor(Qt.BlankCursor)

        # 背景标签，显示接收到的屏幕流
        self.bg_label = QLabel(self)
        self.bg_label.setAlignment(Qt.AlignCenter)
        self.bg_label.setStyleSheet("background-color: #1a1a2e; color: white;")
        self.bg_label.setText("等待屏幕流...\n\n拖拽文件到此窗口即可发送")

        layout = QVBoxLayout(self)
        layout.addWidget(self.bg_label)
        self.setLayout(layout)

        # 注册屏幕流回调
        self.screen_extend.set_preview_callback(self._on_frame_received)

        # ESC 退出全屏
        self.installEventFilter(self)

    def _on_frame_received(self, jpeg_data: bytes):
        """接收 JPEG 帧并显示"""
        try:
            image = QImage()
            image.loadFromData(jpeg_data, "JPEG")
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                scaled = pixmap.scaled(
                    self.bg_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.bg_label.setPixmap(scaled)
                self.bg_label.setText("")
        except Exception as e:
            log.error(f"渲染帧失败: {str(e)}")

    def show_fullscreen(self):
        """进入全屏"""
        self.show()
        self.showFullScreen()

    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖入检测"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        """文件拖放处理"""
        urls = event.mimeData().urls()
        for url in urls:
            file_path = url.toLocalFile()
            if file_path and os.path.isfile(file_path):
                self.file_dropped.emit(file_path)

    def keyPressEvent(self, event):
        """ESC 退出全屏"""
        if event.key() == Qt.Key_Escape:
            self.close()
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UniShare - 全平台跨机共享工具 V1.0.0")
        self.setMinimumSize(1200, 800)
        self.resize(1200, 800)

        # 初始化模块
        self.input_module = InputLeapModule()
        self.usb_module = USBShareModule()
        self.screen_extend = ScreenExtendModule()

        # 拖拽窗口（客户端扩展屏）
        self.drag_drop_window = DragDropWindow(self.screen_extend)
        self.drag_drop_window.file_dropped.connect(self._on_file_dropped)

        # 界面初始化
        self.init_ui()
        self.start_all_modules()

        # 设备刷新定时器
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_device_list)
        self.refresh_timer.start(5000)

        # 扩展屏状态定时器
        self.extend_timer = QTimer()
        self.extend_timer.timeout.connect(self._update_extend_status)
        self.extend_timer.start(2000)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title_label = QLabel("UniShare 跨设备共享中心")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        title_label.setStyleSheet("color: #1976D2;")
        main_layout.addWidget(title_label)

        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Microsoft YaHei", 11))

        self.init_device_tab()
        self.init_input_tab()
        self.init_screen_tab()
        self.init_usb_tab()
        self.init_setting_tab()

        main_layout.addWidget(self.tabs)

    # ============ 设备发现 Tab ============

    def init_device_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        header_layout = QHBoxLayout()
        tip = QLabel("当前局域网在线设备")
        tip.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        header_layout.addWidget(tip)
        header_layout.addStretch()

        self.refresh_btn = QPushButton("🔄 手动刷新")
        self.refresh_btn.setFont(QFont("Microsoft YaHei", 10))
        self.refresh_btn.setStyleSheet(self._get_green_button_style())
        self.refresh_btn.clicked.connect(self.manual_refresh)
        header_layout.addWidget(self.refresh_btn)

        layout.addLayout(header_layout)

        self.device_list = QListWidget()
        self.device_list.setFont(QFont("Microsoft YaHei", 10))
        self.device_list.setStyleSheet(self._get_list_widget_style())
        layout.addWidget(self.device_list)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Microsoft YaHei", 9))
        self.status_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.status_label)

        self.tabs.addTab(page, "🔍 设备发现")

    # ============ 键鼠共享 Tab ============

    def init_input_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)

        status_group = QGroupBox("键鼠共享状态")
        status_layout = QGridLayout()

        self.input_status_label = QLabel("● 运行中")
        self.input_status_label.setStyleSheet("color: green; font-weight: bold;")
        status_layout.addWidget(self.input_status_label, 0, 0)

        mode_text = "服务端" if self.input_module.mode == "server" else "客户端"
        self.input_mode_label = QLabel(f"模式：{mode_text}")
        status_layout.addWidget(self.input_mode_label, 1, 0)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        info_text = QTextEdit()
        info_text.setPlainText("""
键鼠共享功能说明:
- 服务端模式：监听端口等待连接，捕获本机键鼠操作
- 客户端模式：连接服务端，接收并执行远程操作
- 基于 pynput 库实现跨平台键鼠控制
        """)
        info_text.setReadOnly(True)
        info_text.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(info_text)

        self.tabs.addTab(page, "🖱️ 键鼠共享")

    # ============ 扩展屏 Tab ============

    def init_screen_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)

        # 状态
        status_group = QGroupBox("扩展屏状态")
        status_layout = QGridLayout()

        mode_text = "服务端（推流中）" if self.screen_extend.mode == "server" else "客户端（接收中）"
        self.screen_status_label = QLabel(f"● {mode_text}")
        self.screen_status_label.setStyleSheet("color: green; font-weight: bold;")
        status_layout.addWidget(self.screen_status_label, 0, 0)

        self.screen_info_label = QLabel(f"IP: {self.screen_extend.server_ip} | 端口: {self.screen_extend.stream_port}")
        status_layout.addWidget(self.screen_info_label, 1, 0)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 操作按钮
        btn_layout = QHBoxLayout()

        if self.screen_extend.mode == "server":
            self.extend_btn = QPushButton("▶ 开始推流")
            self.extend_btn.setFont(QFont("Microsoft YaHei", 11))
            self.extend_btn.setStyleSheet(self._get_green_button_style())
            self.extend_btn.clicked.connect(self._toggle_extend_stream)
            btn_layout.addWidget(self.extend_btn)
        else:
            self.extend_btn = QPushButton("🖥️ 打开扩展屏")
            self.extend_btn.setFont(QFont("Microsoft YaHei", 11))
            self.extend_btn.setStyleSheet(self._get_blue_button_style())
            self.extend_btn.clicked.connect(self._open_extend_screen)
            btn_layout.addWidget(self.extend_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 预览区域
        preview_group = QGroupBox("屏幕预览")
        preview_layout = QVBoxLayout()

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(300)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a2e;
                color: #888;
                border: 2px dashed #555;
                border-radius: 8px;
            }
        """)
        self.preview_label.setText("等待屏幕流...\n\n客户端模式下打开扩展屏窗口后将显示预览")
        preview_layout.addWidget(self.preview_label)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # 拖拽共享说明
        drag_group = QGroupBox("拖拽文件共享")
        drag_layout = QVBoxLayout()

        if self.screen_extend.mode == "client":
            desc = "打开扩展屏后，将文件直接拖拽到扩展屏窗口即可发送到服务端"
        else:
            desc = "开启推流后，客户端拖拽文件到扩展屏窗口将自动接收"

        drag_info = QLabel(f"📤 {desc}")
        drag_info.setFont(QFont("Microsoft YaHei", 10))
        drag_info.setWordWrap(True)
        drag_layout.addWidget(drag_info)

        save_path_label = QLabel(f"保存路径: {config.get('drag_share.save_path', '~/Downloads/UniShare')}")
        save_path_label.setFont(QFont("Microsoft YaHei", 9))
        save_path_label.setStyleSheet("color: #888;")
        drag_layout.addWidget(save_path_label)

        drag_group.setLayout(drag_layout)
        layout.addWidget(drag_group)

        self.tabs.addTab(page, "🖥️ 扩展屏")

    # ============ USB 设备共享 Tab ============

    def init_usb_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)

        header_group = QGroupBox("USB 设备共享管理")
        header_layout = QVBoxLayout()

        status_layout = QHBoxLayout()
        self.usb_dev_count = QLabel(f"已扫描 {len(self.usb_module.shared_devices)} 个设备，"
                                    f"已勾选 {len(self.usb_module.get_shared_ids())} 个")
        self.usb_dev_count.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        status_layout.addWidget(self.usb_dev_count)
        status_layout.addStretch()

        usb_refresh_btn = QPushButton("🔄 重新扫描")
        usb_refresh_btn.setFont(QFont("Microsoft YaHei", 11))
        usb_refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white; border: none;
                padding: 10px 24px; border-radius: 6px; font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        usb_refresh_btn.clicked.connect(self._refresh_usb_devices)
        status_layout.addWidget(usb_refresh_btn)

        header_layout.addLayout(status_layout)

        # 说明
        info_label = QLabel("勾选需要共享的 USB 设备，客户端连接后将仅能看到已勾选的设备")
        info_label.setFont(QFont("Microsoft YaHei", 11))
        info_label.setStyleSheet("color: #666; padding: 5px 0;")
        header_layout.addWidget(info_label)

        header_group.setLayout(header_layout)
        layout.addWidget(header_group)

        # 设备勾选列表
        list_group = QGroupBox("设备列表")
        list_layout = QVBoxLayout()

        self.usb_device_checkboxes = []
        self.usb_device_scroll = QScrollArea()
        self.usb_device_scroll.setWidgetResizable(True)
        self.usb_device_scroll.setMinimumHeight(300)
        usb_check_widget = QWidget()
        usb_check_layout = QVBoxLayout(usb_check_widget)
        usb_check_layout.setContentsMargins(10, 10, 10, 10)
        usb_check_layout.setSpacing(8)

        if not self.usb_module.shared_devices:
            empty_label = QLabel("未检测到 USB 设备，请点击「重新扫描」")
            empty_label.setFont(QFont("Microsoft YaHei", 12))
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #999; padding: 40px;")
            usb_check_layout.addWidget(empty_label)
        else:
            for dev in self.usb_module.shared_devices:
                dev_id = dev["id"]
                name = dev.get("name", "未知设备")
                vendor = dev.get("vendor", "")
                product = dev.get("product", "")
                manufacturer = dev.get("manufacturer", "")

                label = f"{name}"
                if manufacturer:
                    label += f"  ({manufacturer})"
                if vendor and product:
                    label += f"  [{vendor}:{product}]"

                cb = QCheckBox(label)
                cb.setChecked(dev_id in self.usb_module.get_shared_ids())
                cb.setFont(QFont("Microsoft YaHei", 12))
                cb.setStyleSheet("padding: 6px;")
                self.usb_device_checkboxes.append((dev_id, cb))
                usb_check_layout.addWidget(cb)

        usb_check_layout.addStretch()
        self.usb_device_scroll.setWidget(usb_check_widget)
        list_layout.addWidget(self.usb_device_scroll)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        # 保存按钮
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        usb_save_btn = QPushButton("💾 保存 USB 共享设置")
        usb_save_btn.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        usb_save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3; color: white; border: none;
                padding: 12px 36px; border-radius: 6px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        usb_save_btn.clicked.connect(self._save_usb_shared_devices)
        save_layout.addWidget(usb_save_btn)
        save_layout.addStretch()
        layout.addLayout(save_layout)

        self.tabs.addTab(page, "💾 USB 共享")

    # ============ 设置 Tab ============

    def init_setting_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(25)
        FONT = QFont("Microsoft YaHei", 12)
        FONT_BOLD = QFont("Microsoft YaHei", 12, QFont.Bold)

        # 全局模式
        mode_group = QGroupBox("全局模式设置")
        mode_group.setFont(FONT_BOLD)
        mode_layout = QGridLayout()
        mode_layout.setSpacing(12)

        mode_layout.addWidget(QLabel("运行模式:"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["client", "server"])
        self.mode_combo.setCurrentText(config.get("mode", "client"))
        self.mode_combo.setFont(FONT)
        self.mode_combo.setMinimumHeight(36)
        mode_layout.addWidget(self.mode_combo, 0, 1)

        mode_layout.addWidget(QLabel("服务器地址:"), 0, 2)
        self.server_ip_input = QLineEdit(config.get("server_ip", "192.168.1.100"))
        self.server_ip_input.setPlaceholderText("服务端 IP 地址")
        self.server_ip_input.setFont(FONT)
        self.server_ip_input.setMinimumHeight(36)
        mode_layout.addWidget(self.server_ip_input, 0, 3)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # 网络设置
        network_group = QGroupBox("网络设置")
        network_group.setFont(FONT_BOLD)
        network_layout = QGridLayout()
        network_layout.setSpacing(12)

        network_layout.addWidget(QLabel("服务名称:"), 0, 0)
        self.service_name_input = QLineEdit(config.get("network.mdns_service_name", "unishare"))
        self.service_name_input.setFont(FONT)
        self.service_name_input.setMinimumHeight(36)
        network_layout.addWidget(self.service_name_input, 0, 1)

        network_layout.addWidget(QLabel("端口范围:"), 1, 0)
        self.port_range_input = QLineEdit(config.get("network.port_range", "24800-24810"))
        self.port_range_input.setFont(FONT)
        self.port_range_input.setMinimumHeight(36)
        network_layout.addWidget(self.port_range_input, 1, 1)

        network_group.setLayout(network_layout)
        layout.addWidget(network_group)

        # 扩展屏设置
        extend_group = QGroupBox("扩展屏设置")
        extend_group.setFont(FONT_BOLD)
        extend_layout = QGridLayout()
        extend_layout.setSpacing(12)

        extend_layout.addWidget(QLabel("帧率 (FPS):"), 0, 0)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(config.get("screen_extend.fps", 30))
        self.fps_spin.setFont(FONT)
        self.fps_spin.setMinimumHeight(36)
        extend_layout.addWidget(self.fps_spin, 0, 1)

        extend_layout.addWidget(QLabel("画质 (1-100):"), 0, 2)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(config.get("screen_extend.quality", 80))
        self.quality_spin.setFont(FONT)
        self.quality_spin.setMinimumHeight(36)
        extend_layout.addWidget(self.quality_spin, 0, 3)

        extend_layout.addWidget(QLabel("扩展方向:"), 1, 0)
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["right", "left", "top", "bottom"])
        self.direction_combo.setCurrentText(config.get("screen_extend.extend_direction", "right"))
        self.direction_combo.setFont(FONT)
        self.direction_combo.setMinimumHeight(36)
        extend_layout.addWidget(self.direction_combo, 1, 1)

        extend_group.setLayout(extend_layout)
        layout.addWidget(extend_group)

        # 模块开关
        module_group = QGroupBox("模块开关")
        module_group.setFont(FONT_BOLD)
        module_layout = QGridLayout()
        module_layout.setSpacing(12)

        module_layout.addWidget(QLabel("键鼠共享:"), 0, 0)
        self.input_enable_checkbox = QCheckBox("启用")
        self.input_enable_checkbox.setChecked(config.get("input_share.enabled", True))
        self.input_enable_checkbox.setFont(FONT)
        module_layout.addWidget(self.input_enable_checkbox, 0, 1)

        module_layout.addWidget(QLabel("扩展屏:"), 0, 2)
        self.screen_enable_checkbox = QCheckBox("启用")
        self.screen_enable_checkbox.setChecked(config.get("screen_extend.enabled", True))
        self.screen_enable_checkbox.setFont(FONT)
        module_layout.addWidget(self.screen_enable_checkbox, 0, 3)

        module_layout.addWidget(QLabel("USB 共享:"), 1, 0)
        self.usb_enable_checkbox = QCheckBox("启用")
        self.usb_enable_checkbox.setChecked(config.get("usb_share.enabled", True))
        self.usb_enable_checkbox.setFont(FONT)
        module_layout.addWidget(self.usb_enable_checkbox, 1, 1)

        module_group.setLayout(module_layout)
        layout.addWidget(module_group)

        save_btn = QPushButton("💾 保存设置")
        save_btn.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        save_btn.setStyleSheet(self._get_big_green_button_style())
        save_btn.setFont(QFont("Microsoft YaHei", 11))
        save_btn.setStyleSheet(self._get_green_button_style())
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        info_text = QTextEdit()
        info_text.setPlainText("""
设置说明:
- 客户端模式：本机作为副屏，连接远程主机的扩展屏
- 服务端模式：本机作为主机，推流屏幕到客户端
- 拖拽文件到客户端的扩展屏窗口即可传输文件到服务端
- 修改配置后需重启软件生效
        """)
        info_text.setReadOnly(True)
        info_text.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(info_text)

        self.tabs.addTab(page, "⚙️ 全局设置")

    # ============ 启动 / 停止 ============

    def start_all_modules(self):
        discovery.start()
        self.input_module.start()
        self.usb_module.start()
        self.screen_extend.start()
        log.info("所有功能模块启动完成")

    def closeEvent(self, event):
        self.refresh_timer.stop()
        self.extend_timer.stop()
        if self.drag_drop_window.isVisible():
            self.drag_drop_window.close()
        discovery.stop()
        self.input_module.stop()
        self.usb_module.stop()
        self.screen_extend.stop()
        log.info("程序正常退出")
        event.accept()

    # ============ 扩展屏操作 ============

    def _toggle_extend_stream(self):
        """服务端：切换推流"""
        if self.screen_extend.is_running:
            self.screen_extend.stop()
            self.extend_btn.setText("▶ 开始推流")
            self.extend_btn.setStyleSheet(self._get_green_button_style())
        else:
            self.screen_extend.start()
            self.extend_btn.setText("⏹ 停止推流")
            self.extend_btn.setStyleSheet(self._get_red_button_style())

    def _open_extend_screen(self):
        """客户端：打开扩展屏窗口"""
        if not self.screen_extend.is_running:
            self.screen_extend.start()
        self.drag_drop_window.show_fullscreen()
        self.screen_status_label.setText("● 扩展屏已打开")

    def _update_extend_status(self):
        """定时更新扩展屏状态"""
        if self.screen_extend.mode == "client":
            if self.drag_drop_window.isVisible():
                self.screen_status_label.setText("● 扩展屏运行中")
                self.screen_status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.screen_status_label.setText("○ 扩展屏已关闭 (点击上方按钮打开)")
                self.screen_status_label.setStyleSheet("color: #888;")

    def _on_file_dropped(self, file_path: str):
        """拖拽文件到扩展屏后的处理"""
        result = self.screen_extend.send_file(file_path)
        if result:
            filename = os.path.basename(file_path)
            QMessageBox.information(self, "发送成功", f"文件 {filename} 已发送到服务端")
            log.info(f"拖拽文件发送成功: {file_path}")
        else:
            QMessageBox.warning(self, "发送失败", f"文件 {file_path} 发送失败")

    # ============ 设备发现 ============

    def manual_refresh(self):
        self.refresh_btn.setEnabled(False)
        self.status_label.setText("正在扫描局域网设备...")

        discovery.zeroconf.close()
        from src.unishare.core.discovery import DeviceDiscovery
        discovery.zeroconf = __import__('zeroconf', fromlist=['Zeroconf']).Zeroconf()

        discovery.devices = []
        discovery.register_local_service()

        def refresh_after_delay():
            import time
            time.sleep(1)
            self.refresh_device_list()
            self.refresh_btn.setEnabled(True)
            self.status_label.setText(f"刷新完成，共发现 {len(discovery.devices)} 台设备")

        threading.Thread(target=refresh_after_delay, daemon=True).start()

    def refresh_device_list(self):
        self.device_list.clear()
        devices = discovery.get_online_devices()
        if not devices:
            item = QListWidgetItem("暂无在线设备")
            item.setTextAlignment(Qt.AlignCenter)
            self.device_list.addItem(item)
            return

        for dev in devices:
            is_local = dev.get("is_local", False)
            prefix = "◎ " if is_local else "● "
            info = f"{prefix}设备名：{dev['name']} | IP：{dev['ip']} | 端口：{dev['port']} | 版本：{dev['version']}"
            item = QListWidgetItem(info)
            if is_local:
                item.setBackground(QColor("#E3F2FD"))
            self.device_list.addItem(item)

    # ============ 保存设置 ============

    def save_settings(self):
        try:
            config.set("mode", self.mode_combo.currentText())
            config.set("server_ip", self.server_ip_input.text())

            config.set("network.mdns_service_name", self.service_name_input.text())
            config.set("network.port_range", self.port_range_input.text())

            config.set("screen_extend.fps", self.fps_spin.value())
            config.set("screen_extend.quality", self.quality_spin.value())
            config.set("screen_extend.extend_direction", self.direction_combo.currentText())

            config.set("input_share.enabled", self.input_enable_checkbox.isChecked())
            config.set("screen_extend.enabled", self.screen_enable_checkbox.isChecked())
            config.set("usb_share.enabled", self.usb_enable_checkbox.isChecked())

            config.save()
            QMessageBox.information(self, "成功", "设置已保存，请重启软件生效")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存设置失败：{str(e)}")

    def _refresh_usb_devices(self):
        """重新扫描 USB 设备"""
        self.usb_module._scan_devices()
        self._rebuild_usb_checkboxes()

    def _rebuild_usb_checkboxes(self):
        """重建 USB 设备勾选列表"""
        scroll = self.usb_device_scroll
        check_widget = scroll.widget()
        if check_widget:
            layout = check_widget.layout()
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            self.usb_device_checkboxes = []
            for dev in self.usb_module.shared_devices:
                dev_id = dev["id"]
                name = dev.get("name", "未知设备")
                vendor = dev.get("vendor", "")
                product = dev.get("product", "")
                label = f"{name}"
                if vendor and product:
                    label += f"  ({vendor}:{product})"
                cb = QCheckBox(label)
                cb.setChecked(dev_id in self.usb_module.get_shared_ids())
                cb.setFont(QFont("Microsoft YaHei", 9))
                self.usb_device_checkboxes.append((dev_id, cb))
                layout.addWidget(cb)
            layout.addStretch()

    def _save_usb_shared_devices(self):
        """保存 USB 设备勾选状态"""
        selected = [dev_id for dev_id, cb in self.usb_device_checkboxes if cb.isChecked()]
        self.usb_module.set_shared_ids(selected)
        QMessageBox.information(self, "成功", f"已保存 {len(selected)} 个 USB 共享设备")

    # ============ 样式 ============

    def _get_big_green_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 14px 40px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #3d8b40; }
        """

    def _get_green_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #3d8b40; }
            QPushButton:disabled { background-color: #cccccc; }
        """

    def _get_blue_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:pressed { background-color: #1565C0; }
        """

    def _get_red_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d32f2f; }
            QPushButton:pressed { background-color: #c62828; }
        """

    def _get_list_widget_style(self) -> str:
        return """
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
                padding: 10px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
        """
