# UniShare 开发指南

## 环境要求
- Python 3.12 及以上版本
- 支持 Windows / macOS / Linux

## 本地开发流程
1. 克隆项目到本地
2. 新建虚拟环境：python -m venv venv
3. 激活虚拟环境
4. 安装依赖：pip install -r requirements.txt
5. 启动项目：python -m unishare

## 项目架构
1. core 核心层：日志、配置管理、mDNS设备发现
2. modules 功能层：四大核心业务模块
3. utils 工具层：跨平台判断、通用方法封装
4. gui 界面层：可视化交互窗口

## 开发规范
1. 所有功能模块继承 BaseModule 基类
2. 跨平台判断统一使用 utils/platform.py
3. 日志统一使用全局 log 对象
4. 配置读写统一使用全局 config 对象
5. 新增功能需同步更新文档

## 打包命令
pyinstaller unishare.spec
