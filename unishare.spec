# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/leo/Documents/lazytech/unis/unishare_opencode/src/unishare/__main__.py'],
    pathex=['/Users/leo/Documents/lazytech/unis/unishare_opencode/src'],
    binaries=[],
    datas=[('/Users/leo/Documents/lazytech/unis/unishare_opencode/config', 'config')],
    hiddenimports=['src.unishare.utils.usbip', 'src.unishare.utils.usbip.protocol', 'src.unishare.utils.usbip.server', 'src.unishare.utils.usbip.client', 'src.unishare.utils.usbip.scanner', 'src.unishare.utils.usbip.backend', 'src.unishare.utils.inputleap', 'src.unishare.utils.inputleap.backend', 'src.unishare.modules.base', 'src.unishare.modules.input_share', 'src.unishare.modules.usb_share', 'src.unishare.modules.screen_extend', 'src.unishare.modules.screen_extend.module', 'src.unishare.core.logger', 'src.unishare.core.config', 'src.unishare.core.discovery', 'zeroconf', 'structlog', 'yaml', 'pynput', 'pynput.keyboard', 'pynput.mouse', 'mss', 'PIL', 'numpy', 'usb.core', 'usb.util', 'usb.backend', 'libusb_package', 'structlog', 'yaml', 'zeroconf', 'pynput', 'mss', 'numpy', 'PIL', 'usb', 'libusb_package', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='UniShare',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=['vcruntime140.dll'],
    name='UniShare',
)
app = BUNDLE(
    coll,
    name='UniShare.app',
    icon=None,
    bundle_identifier='com.unishare.app',
)
