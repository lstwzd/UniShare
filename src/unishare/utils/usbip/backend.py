"""
USB/IP 纯 Python 后端 - 基于 pyusb/libusb 的跨平台实现
"""
from typing import List, Dict, Optional

from src.unishare.utils.usbip.protocol import USBIPHeader, USBIPDevice, OpCode
from src.unishare.utils.usbip.scanner import scan_usb_devices
from src.unishare.utils.usbip.server import USBIPServer, server as usbip_server
from src.unishare.utils.usbip.client import USBIPClient


class USBIPBackend:
    """
    USB/IP 纯 Python 后端
    基于 pyusb/libusb + 纯 Python USB/IP 协议栈
    """

    def __init__(self):
        self._available = False
        self._check_backend()

    def _check_backend(self):
        try:
            import usb.core
            import usb.util
            self._available = True
        except ImportError:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def get_backend_name(self) -> str:
        return "Python (pyusb/libusb)" if self._available else "不可用"

    def get_devices(self) -> List[Dict]:
        if not self._available:
            return scan_usb_devices()
        devices = []
        try:
            import usb.core
            import usb.util
            for dev in usb.core.find(find_all=True):
                try:
                    name = ""
                    if dev.iProduct:
                        try:
                            name = usb.util.get_string(dev, dev.iProduct)
                        except:
                            name = ""
                    manu = ""
                    if dev.iManufacturer:
                        try:
                            manu = usb.util.get_string(dev, dev.iManufacturer)
                        except:
                            manu = ""
                    devices.append({
                        "busid": f"{dev.bus}-{dev.address}",
                        "busnum": dev.bus,
                        "devnum": dev.address,
                        "vendor": hex(dev.idVendor),
                        "product": hex(dev.idProduct),
                        "product_name": name,
                        "manufacturer": manu,
                        "backend": "python",
                    })
                except:
                    pass
        except:
            pass
        return devices

    def start_server(self, port: int = 3240) -> bool:
        try:
            return usbip_server.start(port)
        except Exception as e:
            return False

    def stop_server(self):
        usbip_server.stop()

    def export_device(self, busid: str) -> bool:
        return True

    def unexport_device(self, busid: str) -> bool:
        return True

    def attach_device(self, server_ip: str, busid: str, port: int = 3240) -> bool:
        try:
            client = USBIPClient()
            if not client.connect(server_ip, port):
                return False
            result = client.import_device(busid)
            client.disconnect()
            return result
        except:
            return False

    def detach_device(self, port: int) -> bool:
        return True


# 全局单例
backend = USBIPBackend()
