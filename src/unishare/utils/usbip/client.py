"""
USB/IP 客户端 - 基于 pyusb/libusb 的纯 Python 实现
连接远程 USB/IP 服务端，获取设备列表
"""
import socket
import struct
from typing import List, Dict, Optional

from src.unishare.utils.usbip.protocol import (
    USBIPHeader, USBIPDevice, OpCode,
)
from src.unishare.utils.usbip.server import USBIPServer


class USBIPClient:
    """
    USB/IP 协议客户端
    - 连接远程 USB/IP 服务端
    - 获取设备列表
    - 请求导入设备
    """

    def __init__(self):
        self._sock = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self, host: str, port: int = 3240) -> bool:
        """连接到远程 USB/IP 服务端"""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(10)
            self._sock.connect((host, port))
            self._connected = True
            return True
        except Exception as e:
            print(f"[USBIP Client] connect failed: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        self._connected = False
        if self._sock:
            try:
                self._sock.close()
            except:
                pass
            self._sock = None

    def list_devices(self) -> List[Dict]:
        """获取远程设备列表"""
        if not self._connected or not self._sock:
            return []

        try:
            # 发送 OP_REQ_DEVLIST
            req = USBIPHeader(op_code=OpCode.OP_REQ_DEVLIST)
            self._sock.sendall(req.pack())

            # 读取 OP_REP_DEVLIST
            resp_data = self._recv_all(12)
            if not resp_data:
                return []
            resp = USBIPHeader.unpack(resp_data)
            if resp.op_code != OpCode.OP_REP_DEVLIST:
                return []

            # 读取设备数量
            count_data = self._recv_all(4)
            if not count_data:
                return []
            count = struct.unpack("!I", count_data)[0]

            # 读取每个设备
            devices = []
            for _ in range(count):
                # 设备描述符固定 812 bytes (44 + 3*256)
                dev_data = self._recv_all(812)
                if not dev_data:
                    break
                # 读取配置描述符数量 (从偏移 20 开始)
                ncfg = struct.unpack_from("!H", dev_data, 20)[0]
                dev, offset = USBIPDevice.unpack(dev_data)
                # 读取配置描述符
                for _ in range(ncfg):
                    if offset + 4 <= len(dev_data) + 2048:
                        pass  # 简化处理
                devices.append(dev.to_dict())

            return devices

        except Exception as e:
            print(f"[USBIP Client] list_devices failed: {e}")
            return []

    def import_device(self, busid: str) -> bool:
        """
        请求导入远程设备
        busid 格式: "bus-address"
        """
        if not self._connected or not self._sock:
            return False

        try:
            # 发送 OP_REQ_IMPORT + busid
            req = USBIPHeader(op_code=OpCode.OP_REQ_IMPORT)
            self._sock.sendall(req.pack())
            busid_bytes = busid.encode('utf-8')[:255]
            self._sock.sendall(struct.pack("256s", busid_bytes))

            # 读取 OP_REP_IMPORT
            resp_data = self._recv_all(12)
            if not resp_data:
                return False
            resp = USBIPHeader.unpack(resp_data)
            if resp.op_code != OpCode.OP_REP_IMPORT:
                return False

            if resp.status != 0:
                return False

            return True

        except Exception as e:
            print(f"[USBIP Client] import_device failed: {e}")
            return False

    def _recv_all(self, size: int) -> Optional[bytes]:
        """接收指定字节数"""
        data = b''
        while len(data) < size:
            try:
                chunk = self._sock.recv(size - len(data))
                if not chunk:
                    return None
                data += chunk
            except socket.timeout:
                continue
            except:
                return None
        return data
