# InputLeap 集成模块

本模块集成了键鼠共享功能，提供两种实现：

## 1. 纯 Python 实现 (跨平台)
基于 `pynput` 库，无需编译，支持 Windows/macOS/Linux。

## 2. 原生 InputLeap (C++, Linux)
从 https://github.com/input-leap/input-leap 编译。
需要 CMake、Qt5/Qt6、X11 开发库。

## 构建方法

### Python 后端 (默认)
无需构建，`pip install pynput` 即可。

### 原生编译 (Linux)
```bash
python third_party/inputleap/build.py
```

## 目录
- `src/` - InputLeap 源码
- `bin/` - 编译后的二进制
- `build/` - 构建中间文件
