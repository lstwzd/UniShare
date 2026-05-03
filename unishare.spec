# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None
project_root = Path(__file__).parent

# 打包携带资源文件
datas = [
    (str(project_root / "config"), "config"),
    (str(project_root / "third_party"), "third_party")
]

a = Analysis(
    ['src/unishare/__main__.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['zeroconf', 'structlog', 'psutil', 'PySide6'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 打包为无控制台GUI程序
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='UniShare',
    debug=False,
    strip=False,
    upx=True,
    console=False
)
