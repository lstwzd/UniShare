#!/usr/bin/env python3
"""
UniShare 打包构建脚本
支持: macOS (.app) / Linux / Windows (.exe)
用法:
    python build.py             # 默认生产构建
    python build.py --debug     # 调试模式 (带控制台)
    python build.py --clean     # 清理构建目录
"""
import os
import sys
import shutil
import subprocess
import platform
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
SRC_DIR = PROJECT_ROOT / "src"
CONFIG_DIR = PROJECT_ROOT / "config"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
VENV_DIR = PROJECT_ROOT / ".venv"

SYSTEM = platform.system().lower()

# 所有需要 pip 安装的依赖
REQUIREMENTS = [
    "PyYAML", "structlog", "zeroconf",
    "pynput", "mss", "numpy", "Pillow",
    "pyusb", "libusb-package",
    "PySide6",
]

# PyInstaller 需要显式声明的隐藏导入
HIDDEN_IMPORTS = [
    # USB/IP
    "src.unishare.utils.usbip",
    "src.unishare.utils.usbip.protocol",
    "src.unishare.utils.usbip.server",
    "src.unishare.utils.usbip.client",
    "src.unishare.utils.usbip.scanner",
    "src.unishare.utils.usbip.backend",
    # InputLeap
    "src.unishare.utils.inputleap",
    "src.unishare.utils.inputleap.backend",
    # 模块
    "src.unishare.modules.base",
    "src.unishare.modules.input_share",
    "src.unishare.modules.usb_share",
    "src.unishare.modules.screen_extend",
    "src.unishare.modules.screen_extend.module",
    # 核心
    "src.unishare.core.logger",
    "src.unishare.core.config",
    "src.unishare.core.discovery",
    # 第三方库
    "zeroconf", "structlog", "yaml",
    "pynput", "pynput.keyboard", "pynput.mouse",
    "mss", "PIL", "numpy",
    "usb.core", "usb.util", "usb.backend",
    "libusb_package",
]


def log(msg):
    print(f"[build] {msg}")


def check_venv():
    """检查是否在虚拟环境中"""
    in_venv = sys.prefix != sys.base_prefix
    if not in_venv:
        # 尝试使用 .venv 中的 python
        venv_python = None
        if SYSTEM == "win32":
            venv_python = VENV_DIR / "Scripts" / "python.exe"
        else:
            venv_python = VENV_DIR / "bin" / "python"
        
        if venv_python and venv_python.exists():
            log(f"使用虚拟环境: {venv_python}")
            return str(venv_python)
        else:
            log("警告: 未在虚拟环境中且未找到 .venv")
            log("运行: source .venv/bin/activate && pip install -r requirements.txt")
            return sys.executable
    return sys.executable


def install_deps(python_exe: str):
    """安装构建依赖"""
    log("安装构建依赖...")
    subprocess.run(
        [python_exe, "-m", "pip", "install", "--upgrade", "pip"],
        check=False, capture_output=True
    )
    subprocess.run(
        [python_exe, "-m", "pip", "install", "-r", str(PROJECT_ROOT / "requirements.txt")],
        check=True
    )
    subprocess.run(
        [python_exe, "-m", "pip", "install", "pyinstaller"],
        check=True
    )
    log("依赖安装完成")


def clean_build():
    """清理构建产物"""
    log("清理构建目录...")
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
            log(f"  删除: {d}")
    # 清理 spec 文件
    for spec in PROJECT_ROOT.glob("*.spec"):
        if spec.name != "unishare.spec":
            spec.unlink()
    log("清理完成")


def build(python_exe: str, debug: bool = False):
    """执行 PyInstaller 打包"""
    log(f"系统: {SYSTEM}")
    log(f"Python: {python_exe}")

    # 确保入口文件存在
    entry = SRC_DIR / "unishare" / "__main__.py"
    if not entry.exists():
        log(f"错误: 入口文件不存在 {entry}")
        sys.exit(1)

    # 构建平台特定的输出名称
    if SYSTEM == "darwin":
        app_name = "UniShare.app"
        icon_file = PROJECT_ROOT / "icon.icns"
        icon_opt = ["--icon", str(icon_file)] if icon_file.exists() else []
    elif SYSTEM == "win32":
        app_name = "UniShare.exe"
        icon_file = PROJECT_ROOT / "icon.ico"
        icon_opt = ["--icon", str(icon_file)] if icon_file.exists() else []
    else:
        app_name = "UniShare"
        icon_opt = []

    # 构建 PyInstaller 命令
    cmd = [
        python_exe, "-m", "PyInstaller",
        "--name", "UniShare",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(PROJECT_ROOT),
        "--add-data", f"{CONFIG_DIR}{os.pathsep}config",
        "--paths", str(SRC_DIR),
        "--noconfirm",
    ]

    # 隐藏导入
    for imp in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", imp])

    # 收集所有需要的包
    for pkg in [
        "structlog", "yaml", "zeroconf", "pynput", "mss", "numpy", "PIL",
        "usb", "libusb_package",
    ]:
        cmd.extend(["--hidden-import", pkg])

    # 只收集 PySide6 实际使用的子模块
    for sub in ["PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"]:
        cmd.extend(["--hidden-import", sub])

    # 图标
    cmd.extend(icon_opt)

    # 平台特定选项
    if SYSTEM == "darwin":
        cmd.extend([
            "--windowed",  # macOS .app
            "--osx-bundle-identifier", "com.unishare.app",
        ])
    elif SYSTEM == "win32":
        cmd.extend([
            "--windowed",  # Windows 无控制台
        ])

    if debug:
        cmd.append("--debug")
        entry_point = str(entry)
    else:
        # 生产构建
        cmd.extend(["--strip", "--upx-exclude", "vcruntime140.dll"])
        entry_point = str(entry)

    cmd.append(entry_point)

    # 打印构建信息
    log("=" * 60)
    log(f"输出: {DIST_DIR / app_name}")
    log(f"模式: {'调试' if debug else '生产'}")
    log(f"命令: {' '.join(str(c) for c in cmd)}")
    log("=" * 60)

    # 执行构建
    result = subprocess.run(cmd)

    if result.returncode == 0:
        log("=" * 60)
        log("构建成功!")
        output_path = DIST_DIR / app_name
        if output_path.exists():
            size = _get_size(output_path)
            log(f"输出路径: {output_path}")
            log(f"文件大小: {size}")
        log("=" * 60)
    else:
        log("=" * 60)
        log("构建失败!")
        log("=" * 60)
        sys.exit(1)


def _get_size(path: Path) -> str:
    """获取文件/目录大小"""
    if path.is_file():
        size = path.stat().st_size
    else:
        size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def main():
    parser = argparse.ArgumentParser(description="UniShare 打包工具")
    parser.add_argument("--debug", action="store_true", help="调试模式 (带控制台)")
    parser.add_argument("--clean", action="store_true", help="清理构建产物")
    parser.add_argument("--no-venv", action="store_true", help="不使用虚拟环境")
    args = parser.parse_args()

    if args.clean:
        clean_build()
        return

    python_exe = sys.executable if args.no_venv else check_venv()
    
    if not args.no_venv:
        install_deps(python_exe)
    
    build(python_exe, debug=args.debug)


if __name__ == "__main__":
    main()
