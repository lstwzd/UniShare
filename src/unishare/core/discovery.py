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

    def stop(self):
        self.running = False
        self.zeroconf.close()
        log.info("停止设备发现服务")

    def register_local_service(self):
        try:
            ip = socket.gethostbyname(socket.gethostname())
            port = config.get("network.port_range", "24800-24810").split("-")[0]
            info = ServiceInfo(
                self.service_type,
                self.service_name,
                addresses=[socket.inet_aton(ip)],
                port=int(port),
                properties={"version": "0.1.0"}
            )
            self.zeroconf.register_service(info)
            log.info(f"本地设备注册成功 {ip}:{port}")
        except Exception as e:
            log.error(f"本地设备注册失败: {str(e)}")

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

    def remove_service(self, zc, type_, name):
        self.devices = [d for d in self.devices if d["name"] != name]
        log.info(f"设备离线: {name}")

    def get_online_devices(self) -> List[Dict]:
        return self.devices.copy()

# 全局设备发现实例
discovery = DeviceDiscovery()
