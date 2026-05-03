import socket
import threading
from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo
from typing import List, Dict
from src.unishare.core.logger import log
from src.unishare.core.config import config

class DeviceDiscovery:
    def __init__(self):
        self.zeroconf = Zeroconf()
        self.service_type = "_unishare._tcp.local."
        self.service_name = config.get("network.mdns_service_name", "unishare.local")
        self.devices: List[Dict] = []
        self.running = False

    def start(self):
        if self.running:
            return
        self.running = True
        log.info("启动局域网设备发现服务")
        ServiceBrowser(self.zeroconf, self.service_type, listener=self)
        self.register_local_service()
        # 添加本机到设备列表
        self._add_local_device()

    def _add_local_device(self):
        """添加本机设备到列表"""
        try:
            ip = self._get_local_ip()
            port = config.get("network.port_range", "24800-24810").split("-")[0]
            local_device = {
                "name": self.service_name,
                "ip": ip,
                "port": int(port),
                "version": "0.1.0",
                "is_local": True
            }
            # 避免重复添加
            if not any(d.get("is_local") and d["ip"] == ip for d in self.devices):
                self.devices.insert(0, local_device)
                log.info(f"本机设备已添加：{local_device}")
        except Exception as e:
            log.error(f"添加本机设备失败：{str(e)}")

    def stop(self):
        self.running = False
        self.zeroconf.close()
        log.info("停止设备发现服务")

    def register_local_service(self):
        try:
            ip = self._get_local_ip()
            port = config.get("network.port_range", "24800-24810").split("-")[0]
            # 服务名称必须是完整格式：_name._tcp.local.
            service_name = config.get("network.mdns_service_name", "unishare")
            full_service_name = f"{service_name}.{self.service_type}"
            info = ServiceInfo(
                self.service_type,
                full_service_name,
                addresses=[socket.inet_aton(ip)],
                port=int(port),
                properties={"version": "0.1.0"}
            )
            self.zeroconf.register_service(info)
            log.info(f"本地设备注册成功 {ip}:{port}")
        except Exception as e:
            log.error(f"本地设备注册失败：{str(e)}")

    def _get_local_ip(self) -> str:
        """获取本机局域网 IP 地址，优先选择非回环地址"""
        try:
            # 方法 1: 连接到外部地址获取本机出口 IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except Exception:
                s.close()
        except Exception:
            pass

        # 方法 2: 回退到 hostname 解析
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            pass

        # 方法 3: 最后回退到 127.0.0.1
        return "127.0.0.1"

    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if info:
            device = {
                "name": name,
                "ip": info.parsed_addresses()[0],
                "port": info.port,
                "version": info.properties.get(b"version", b"0.0.0").decode()
            }
            self.devices.append(device)
            log.info(f"发现新设备: {device}")

    def update_service(self, zc, type_, name):
        """必需的 ServiceListener 方法"""
        self.add_service(zc, type_, name)

    def remove_service(self, zc, type_, name):
        self.devices = [d for d in self.devices if d["name"] != name]
        log.info(f"设备离线: {name}")

    def get_online_devices(self) -> List[Dict]:
        return self.devices.copy()

# 全局设备发现实例
discovery = DeviceDiscovery()
