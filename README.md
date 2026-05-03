# UniShare
## 全平台跨机共享一体化开源工具

### 项目简介
UniShare 是一款**开源、跨平台、一站式**设备共享工具，整合市面多款工具功能，
一套软件实现：键鼠共享、剪贴板同步、USB设备共享、局域网文件传输，
完美适配 Windows / macOS / Linux 多设备互联。

### ✨ 核心功能
- 🖱️ **键鼠无缝共享**：多设备屏幕联动，鼠标边缘自动切换，键盘全局复用
- 📋 **跨端剪贴板同步**：文本、图片、文件双向实时同步
- 💾 **USB网络共享**：U盘、打印机、加密狗等USB设备跨网络挂载使用
- 📤 **局域网极速传输**：mDNS自动发现设备，拖拽传输、断点续传
- 🔒 **安全加密传输**：支持TLS加密，保障局域网数据安全

### 🚀 快速启动
```bash
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活虚拟环境
# Windows
venv\Scriptsctivate
# macOS / Linux
source venv/bin/activate

# 3. 安装全部依赖
pip install -r requirements.txt

# 4. 启动 UniShare
python -m unishare
```

### 📁 完整项目结构
```
unishare_opencode/
├── src/unishare/          # 核心源码目录
│   ├── core/              # 核心框架（配置/日志/设备发现）
│   ├── modules/           # 四大功能模块代码
│   ├── utils/             # 跨平台工具类
│   ├── gui/               # 可视化界面
│   └── __main__.py        # 程序入口
├── config/                # 全局配置文件
├── docs/                  # 开发文档+用户文档
├── tests/                 # 单元测试用例
├── third_party/           # 跨平台依赖工具
├── LICENSE                # 开源协议
├── requirements.txt       # 依赖清单
├── pyproject.toml         # 项目打包配置
└── unishare.spec          # 可执行程序打包脚本
```

### 🤝 参与贡献
欢迎提交 Issue、PR 参与项目迭代，开发规范详见 docs/DEVELOPMENT.md

### 📄 开源协议
本项目基于 **GPL-3.0-only** 开源，禁止闭源商用。
