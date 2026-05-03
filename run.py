#!/usr/bin/env python3
"""UniShare 启动入口"""
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.unishare.__main__ import main

if __name__ == "__main__":
    main()
