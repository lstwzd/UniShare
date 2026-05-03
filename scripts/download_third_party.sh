#!/bin/bash

# UniShare third_party 工具自动下载脚本
# 支持 macOS / Windows / Linux

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
THIRD_PARTY_DIR="$PROJECT_ROOT/third_party"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检测操作系统
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        echo "windows"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    else
        echo "unknown"
    fi
}

# 检测 CPU 架构
detect_arch() {
    if [[ "$ARCH" ]]; then
        echo "$ARCH"
        return
    fi
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if [[ $(uname -m) == "arm64" ]]; then
            echo "arm64"
        else
            echo "amd64"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [[ $(uname -m) == "aarch64" ]]; then
            echo "arm64"
        else
            echo "amd64"
        fi
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        echo "amd64"
    else
        echo "amd64"
    fi
}

OS=$(detect_os)
ARCH=$(detect_arch)

log_info "检测到操作系统：$OS"
log_info "检测到 CPU 架构：$ARCH"

# 创建 third_party 目录
mkdir -p "$THIRD_PARTY_DIR"

# 下载 InputLeap
download_inputleap() {
    log_info "正在下载 InputLeap..."
    
    local inputleap_dir="$THIRD_PARTY_DIR/inputleap"
    mkdir -p "$inputleap_dir"
    
    case "$OS" in
        "macos")
            local url="https://github.com/input-leap/input-leap/releases/download/2.4.0/input-leap-2.4.0-mac.zip"
            local file="inputleap.zip"
            curl -L "$url" -o "$inputleap_dir/$file" 2>/dev/null || {
                log_warn "InputLeap macOS 下载失败，请手动下载"
                log_info "下载地址：https://github.com/input-leap/input-leap/releases"
                return 1
            }
            unzip -o "$inputleap_dir/$file" -d "$inputleap_dir" 2>/dev/null
            rm "$inputleap_dir/$file"
            ;;
        "windows")
            local url="https://github.com/input-leap/input-leap/releases/download/2.4.0/input-leap-2.4.0-windows.exe"
            local file="inputleap.exe"
            curl -L "$url" -o "$inputleap_dir/$file" 2>/dev/null || {
                log_warn "InputLeap Windows 下载失败，请手动下载"
                log_info "下载地址：https://github.com/input-leap/input-leap/releases"
                return 1
            }
            ;;
        "linux")
            log_warn "Linux 平台 InputLeap 暂不支持自动下载"
            log_info "请手动下载：https://github.com/input-leap/input-leap/releases"
            return 1
            ;;
    esac
    
    log_info "InputLeap 下载完成：$inputleap_dir"
}

# 下载 Syncthing
download_syncthing() {
    log_info "正在下载 Syncthing..."
    
    local syncthing_dir="$THIRD_PARTY_DIR/syncthing"
    mkdir -p "$syncthing_dir"
    
    case "$OS" in
        "macos")
            local url="https://github.com/syncthing/syncthing/releases/download/v2.0.16/syncthing-macos-$ARCH-v2.0.16.zip"
            local file="syncthing.zip"
            curl -L "$url" -o "$syncthing_dir/$file" 2>/dev/null || {
                log_warn "Syncthing macOS 下载失败，请手动下载"
                log_info "下载地址：https://github.com/syncthing/syncthing/releases"
                return 1
            }
            unzip -o "$syncthing_dir/$file" -d "$syncthing_dir" 2>/dev/null
            rm "$syncthing_dir/$file"
            chmod +x "$syncthing_dir/syncthing"
            ;;
        "windows")
            local url="https://github.com/syncthing/syncthing/releases/download/v2.0.16/syncthing-windows-$ARCH-v2.0.16.zip"
            local file="syncthing.zip"
            curl -L "$url" -o "$syncthing_dir/$file" 2>/dev/null || {
                log_warn "Syncthing Windows 下载失败，请手动下载"
                log_info "下载地址：https://github.com/syncthing/syncthing/releases"
                return 1
            }
            unzip -o "$syncthing_dir/$file" -d "$syncthing_dir" 2>/dev/null
            rm "$syncthing_dir/$file"
            ;;
        "linux")
            local url="https://github.com/syncthing/syncthing/releases/download/v2.0.16/syncthing-linux-$ARCH-v2.0.16.tar.gz"
            local file="syncthing.tar.gz"
            curl -L "$url" -o "$syncthing_dir/$file" 2>/dev/null || {
                log_warn "Syncthing Linux 下载失败，请手动下载"
                log_info "下载地址：https://github.com/syncthing/syncthing/releases"
                return 1
            }
            tar -xzf "$syncthing_dir/$file" -C "$syncthing_dir" 2>/dev/null
            rm "$syncthing_dir/$file"
            chmod +x "$syncthing_dir/syncthing"
            ;;
    esac
    
    log_info "Syncthing 下载完成：$syncthing_dir"
}

# 下载 USB/IP 工具
download_usbip() {
    log_info "正在下载 USB/IP 工具..."
    
    local usbip_dir="$THIRD_PARTY_DIR/usbip"
    mkdir -p "$usbip_dir"
    
    case "$OS" in
        "macos")
            log_info "macOS USB/IP 工具通过 Homebrew 安装..."
            if ! command -v brew &> /dev/null; then
                log_error "未检测到 Homebrew，请先安装 Homebrew"
                log_info "安装命令：/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                return 1
            fi
            
            brew tap beriberikix/usbipd-mac 2>/dev/null || true
            brew install usbip 2>/dev/null || {
                log_error "Homebrew 安装 usbip 失败"
                return 1
            }
            
            # 创建符号链接
            ln -sf $(which usbip) "$usbip_dir/usbip" 2>/dev/null || true
            log_info "USB/IP macOS 工具安装完成"
            ;;
        "windows")
            log_info "Windows USB/IP 工具通过 winget 安装..."
            if command -v winget &> /dev/null; then
                winget install usbipd 2>/dev/null || {
                    log_warn "winget 安装失败，请手动下载"
                    log_info "下载地址：https://github.com/dorssel/usbipd-win/releases"
                    return 1
                }
                log_info "USB/IP Windows 工具安装完成"
            else
                log_warn "未检测到 winget，请手动下载"
                log_info "下载地址：https://github.com/dorssel/usbipd-win/releases"
                return 1
            fi
            ;;
        "linux")
            log_info "Linux USB/IP 工具已通过系统包管理器安装 (内核集成)"
            log_info "如未安装，请执行:"
            log_info "  Ubuntu/Debian: sudo apt install linux-tools-generic usbip-utils"
            log_info "  Fedora/RHEL:   sudo dnf install usbip-utils"
            log_info "  Arch Linux:    sudo pacman -S usbip-tools"
            ;;
    esac
}

# 主程序
main() {
    log_info "=========================================="
    log_info "UniShare third_party 工具下载脚本"
    log_info "=========================================="
    log_info "操作系统：$OS"
    log_info "CPU 架构：$ARCH"
    log_info "目标目录：$THIRD_PARTY_DIR"
    log_info ""
    
    # 询问是否下载所有工具
    read -p "是否下载所有工具？(y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        download_inputleap || true
        download_syncthing || true
        download_usbip || true
    else
        # 选择性下载
        log_info "请选择要下载的工具:"
        log_info "1) InputLeap (键鼠共享)"
        log_info "2) Syncthing (文件同步)"
        log_info "3) USB/IP 工具"
        log_info "0) 退出"
        read -p "请选择 [0-3]: " -n 1 -r
        echo
        
        case $REPLY in
            1) download_inputleap ;;
            2) download_syncthing ;;
            3) download_usbip ;;
            0) log_info "退出"; exit 0 ;;
            *) log_error "无效选择" ;;
        esac
    fi
    
    log_info ""
    log_info "=========================================="
    log_info "下载完成!"
    log_info "目录内容:"
    ls -la "$THIRD_PARTY_DIR"
    log_info "=========================================="
}

main "$@"
