# UniShare

## 全平台跨机共享一体化开源工具

UniShare 是一款**开源、跨平台、一站式**设备共享工具，一套软件实现键鼠共享、USB 设备共享、扩展屏、文件传输，完美适配 Windows / macOS / Linux 多设备互联。

---

### ✨ 核心功能

| 功能 | 说明 | 技术栈 |
|------|------|--------|
| 🖱️ **键鼠共享** | 多设备键鼠穿透、远程控制 | `pynput` TCP 协议 |
| 🖥️ **扩展屏** | 服务端截屏推流、客户端全屏显示 | `mss` `Pillow` UDP |
| 💾 **USB 共享** | USB 设备跨网络挂载、远程使用 | `pyusb` `libusb` USB/IP |
| 📤 **拖拽文件** | 拖拽文件到扩展屏窗口自动传输 | TCP 自定义协议 |

> 全部模块均为 **纯 Python 实现**，无需编译任何 C 代码。

---

### 🚀 快速启动

```bash
# 1. 克隆项目
git clone https://github.com/lstwzd/UniShare.git && cd unishare_opencode

# 2. 创建虚拟环境
python -m venv .venv

# 3. 激活虚拟环境
# macOS / Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

# 4. 安装依赖
pip install -r requirements.txt
pip install -e .

# 5. 启动
python -m unishare
```

---

### 📦 打包构建

将 UniShare 打包为独立可执行程序（无需 Python 环境即可运行）。

#### 前提条件

```bash
pip install pyinstaller
```

#### 生产构建

```bash
python build.py
```

输出：
- **macOS**: `dist/UniShare.app` (~320 MB)
- **Windows**: `dist/UniShare.exe`
- **Linux**: `dist/UniShare`

#### 调试构建

```bash
python build.py --debug
```

带控制台输出，方便排查问题。

#### 清理

```bash
python build.py --clean
```

#### 手动 PyInstaller

```bash
pyinstaller unishare.spec
```

---

### 🗂️ 项目结构

```
unishare_opencode/
├── build.py                   # 一键打包脚本
├── unishare.spec              # PyInstaller 配置
├── requirements.txt           # Python 依赖
├── pyproject.toml             # 项目元数据
│
├── src/unishare/              # 核心源码
│   ├── __main__.py            # 程序入口
│   ├── core/                  # 框架层
│   │   ├── config.py          #   YAML 配置读写
│   │   ├── logger.py          #   结构化日志
│   │   └── discovery.py       #   mDNS 设备发现
│   ├── modules/               # 功能模块
│   │   ├── base.py            #   模块基类
│   │   ├── input_share.py     #   键鼠共享 (pynput)
│   │   ├── usb_share.py       #   USB/IP 共享
│   │   └── screen_extend/     #   扩展屏 (截屏推流)
│   ├── utils/                 # 工具库
│   │   ├── inputleap/         #   键鼠后端 (纯 Python)
│   │   └── usbip/             #   USB/IP 协议栈 (纯 Python)
│   │       ├── protocol.py    #     USB/IP 协议结构
│   │       ├── server.py      #     USB/IP 服务端
│   │       ├── client.py      #     USB/IP 客户端
│   │       ├── scanner.py     #     跨平台 USB 扫描
│   │       └── backend.py     #     统一后端接口
│   └── gui/
│       └── main_window.py     # Qt6 主窗口 (5 Tab)
│
├── config/
│   └── unishare-config.yaml   # 默认配置文件
│
├── third_party/               # 第三方依赖说明
├── docs/                      # 文档
└── tests/                     # 测试
```

---

### ⚙️ 配置说明

全局配置文件 `config/unishare-config.yaml`：

```yaml
# 运行模式 (client / server)
mode: "client"
# 服务端 IP 地址（客户端模式下）
server_ip: "192.168.1.100"

network:
  port_range: "24800-24810"
  mdns_service_name: "unishare"

input_share:
  enabled: true

screen_extend:
  enabled: true
  fps: 30
  quality: 80

usb_share:
  enabled: true
  shared_device_ids: []

drag_share:
  enabled: true
  save_path: "~/Downloads/UniShare"
```

可在 GUI **设置 Tab** 中修改配置。

---

### 🧩 技术架构

```
┌─────────────────────────────────────────────────────┐
│                     MainWindow                       │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐ │
│  │ 设备  │ │ 键鼠  │ │ 扩展屏│ │ USB  │ │  设置    │ │
│  │ 发现  │ │ 共享  │ │      │ │ 共享  │ │          │ │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────────┘ │
└─────────────────────────────────────────────────────┘
         │         │         │         │
    ┌────▼──┐ ┌───▼───┐ ┌───▼───┐ ┌───▼────────┐
    │mDNS   │ │pynput │ │mss    │ │pyusb/libusb│
    │zeroconf│ │TCP    │ │Pillow │ │USB/IP proto│
    │       │ │JSON   │ │UDP    │ │TCP         │
    └───────┘ └───────┘ └───────┘ └────────────┘
```

所有通信基于 **TCP/UDP 局域网协议**，无需互联网连接。

---

### 📄 开源协议

本项目基于 **GPL-3.0-only** 开源。
