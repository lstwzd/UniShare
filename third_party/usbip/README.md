# USB/IP 集成模块

本模块集成了 USB/IP 协议支持，提供两种后端实现：

## 1. 原生 C 工具 (Linux)
从 Linux 内核源码编译 `usbip` 和 `usbipd` 工具。

## 2. 纯 Python 实现 (跨平台)
基于 libusb 的纯 Python USB/IP 协议实现，无需编译。

## 构建方法

### 自动构建 (推荐)
```bash
python third_party/usbip/build.py
```

### 手动构建 (Linux)
```bash
cd third_party/usbip
make
```

## 目录结构
- `src/` - USB/IP 源代码
- `bin/` - 编译后的二进制文件
- `build/` - 构建中间文件
- `patches/` - 平台兼容补丁
