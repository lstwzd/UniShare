"""
USB 设备扫描器 - 跨平台 USB 设备发现
"""
import subprocess
import platform
import re
import json
from typing import List, Dict
from pathlib import Path


def scan_usb_devices() -> List[Dict]:
    """扫描系统中的 USB 设备"""
    system = platform.system().lower()
    
    if system == "windows":
        return _scan_windows()
    elif system == "darwin":
        return _scan_macos()
    elif system == "linux":
        return _scan_linux()
    else:
        return []


def _scan_windows() -> List[Dict]:
    """Windows: 使用 wmic 或 PowerShell"""
    devices = []
    try:
        result = subprocess.run(
            ["wmic", "path", "Win32_PnPEntity", "where",
             '"ConfigManagerErrorCode = 0"',
             "get", "DeviceID,Description,Manufacturer",
             "/format:csv"],
            capture_output=True, text=True, timeout=15
        )
        lines = result.stdout.strip().split('\n')
        for line in lines[2:]:  # Skip header
            parts = line.split(',')
            if len(parts) >= 4:
                devices.append({
                    "busid": parts[1].strip(),
                    "description": parts[2].strip(),
                    "manufacturer": parts[3].strip(),
                    "platform": "windows"
                })
    except:
        pass
    return devices


def _scan_macos() -> List[Dict]:
    """macOS: 使用 system_profiler 和 ioreg"""
    devices = []
    try:
        # 使用 ioreg 获取详细的 USB 设备信息
        result = subprocess.run(
            ["ioreg", "-p", "IOUSB", "-l", "-w", "0"],
            capture_output=True, text=True, timeout=15
        )
        
        current = {}
        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # 匹配 USB 设备条目
            usb_match = re.search(r'\+\-o ([^<]+)@', line)
            if usb_match:
                if current:
                    devices.append(current)
                current = {
                    "name": usb_match.group(1).strip(),
                    "platform": "macos"
                }
                continue
            
            if not current:
                continue
            
            # 提取属性
            for key, attr in [
                ("USB Vendor Name", "manufacturer"),
                ("USB Product Name", "product"),
                ("idVendor", "vendor_id"),
                ("idProduct", "product_id"),
                ("USB Serial Number", "serial"),
                ("bcdDevice", "bcd_device"),
            ]:
                match = re.search(rf'"{key}"\s*=\s*"([^"]*)"', line)
                if match:
                    current[attr] = match.group(1)
                    break
            
            hex_match = re.search(rf'"([^"]*)"\s*=\s*(\d+)', line)
            if hex_match:
                key = hex_match.group(1)
                val = hex_match.group(2)
                if key == "idVendor":
                    current["vendor_id"] = f"0x{int(val):04x}"
                elif key == "idProduct":
                    current["product_id"] = f"0x{int(val):04x}"
        
        if current:
            devices.append(current)
            
    except:
        pass
    
    # 回退到 system_profiler
    if not devices:
        try:
            result = subprocess.run(
                ["system_profiler", "SPUSBDataType", "-json"],
                capture_output=True, text=True, timeout=15
            )
            data = json.loads(result.stdout)
            items = data.get("SPUSBDataType", [])
            for item in _flatten_usb_items(items):
                devices.append(item)
        except:
            pass
    
    return devices


def _flatten_usb_items(items: List[Dict], depth: int = 0) -> List[Dict]:
    """递归展平 system_profiler 的 USB 树"""
    result = []
    for item in items:
        dev = {
            "name": item.get("_name", "Unknown"),
            "manufacturer": item.get("manufacturer", ""),
            "vendor_id": item.get("vendor_id", ""),
            "product_id": item.get("product_id", ""),
            "platform": "macos"
        }
        result.append(dev)
        # 递归子设备
        for key in item:
            if isinstance(item[key], list) and key != "_name":
                result.extend(_flatten_usb_items(item[key], depth + 1))
    return result


def _scan_linux() -> List[Dict]:
    """Linux: 使用 lsusb"""
    devices = []
    try:
        result = subprocess.run(
            ["lsusb"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 6:
                bus_id = parts[1]
                device_id = parts[3].rstrip(':')
                device_name = ' '.join(parts[6:]) if len(parts) > 6 else "Unknown"
                
                devices.append({
                    "busid": f"{bus_id}:{device_id}",
                    "name": device_name,
                    "platform": "linux"
                })
    except:
        pass
    return devices
