"""
Python USB/IP 协议实现 (v1.1.1)
完整实现 USB/IP 协议的数据结构与序列化
基于 Linux 内核 drivers/usb/usbip/usbip_protocol.h
"""
import struct
from enum import IntEnum
from typing import Tuple, Optional


USBIP_VERSION = 0x0111

# OP 码
class OpCode(IntEnum):
    OP_REQ_DEVLIST  = 0x8005
    OP_REP_DEVLIST  = 0x0005
    OP_REQ_IMPORT   = 0x8003
    OP_REP_IMPORT   = 0x0003

# USB 请求方向
class UsbDirection(IntEnum):
    USB_DIR_OUT = 0
    USB_DIR_IN  = 1

# USB 传输类型
class UsbType(IntEnum):
    USB_TYPE_STANDARD = 0x00
    USB_TYPE_CLASS    = 0x20
    USB_TYPE_VENDOR   = 0x40

# USB 接收者
class UsbRecipient(IntEnum):
    USB_RECIP_DEVICE     = 0x00
    USB_RECIP_INTERFACE  = 0x01
    USB_RECIP_ENDPOINT   = 0x02
    USB_RECIP_OTHER      = 0x03

# USB 标准请求
class UsbRequest(IntEnum):
    USB_REQ_GET_DESCRIPTOR       = 0x06
    USB_REQ_SET_CONFIGURATION    = 0x09
    USB_REQ_SET_INTERFACE        = 0x0B

# USB 描述符类型
class DescriptorType(IntEnum):
    DEVICE        = 0x01
    CONFIGURATION = 0x02
    STRING        = 0x03
    INTERFACE     = 0x04
    ENDPOINT      = 0x05
    DEVICE_QUALIFIER = 0x06

# USB 速度
class UsbSpeed(IntEnum):
    USB_SPEED_UNKNOWN = 0
    USB_SPEED_LOW     = 1
    USB_SPEED_FULL    = 2
    USB_SPEED_HIGH    = 3
    USB_SPEED_WIRELESS = 4
    USB_SPEED_SUPER   = 5

# USB/IP 传输标志
XFER_FLAGS = {
    "URB_SHORT_NOT_OK": 0x0001,
    "URB_ISO_ASAP":     0x0002,
    "URB_NO_TRANSFER_DMA_MAP": 0x0004,
    "URB_ZERO_PACKET":  0x0040,
    "URB_NO_INTERRUPT": 0x0080,
    "URB_FREE_BUFFER":  0x0100,
    "URB_DIR_MASK":     0x0200,
}


class USBIPHeader:
    """USB/IP OP 层协议头 (12 bytes)"""
    FORMAT = "!HHII"

    def __init__(self, version: int = USBIP_VERSION, op_code: int = 0, status: int = 0):
        self.version = version
        self.op_code = op_code
        self.status = status

    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, self.version, self.op_code, self.status, 0)

    @classmethod
    def unpack(cls, data: bytes):
        v, op, st, _ = struct.unpack(cls.FORMAT, data[:12])
        return cls(v, op, st)

    def __repr__(self):
        return f"USBIPHeader(ver={self.version:#x}, op={self.op_code:#x}, st={self.status})"


class USBIPDevice:
    """USB/IP 设备信息 (固定部分 = 44 + 3*256 = 812 bytes + 配置描述符)"""

    def __init__(self):
        self.busnum = 0
        self.devnum = 0
        self.speed = 0
        self.vendor = 0
        self.product = 0
        self.bcd_device = 0
        self.dev_class = 0
        self.dev_subclass = 0
        self.dev_protocol = 0
        self.manufacturer = ""
        self.product_name = ""
        self.serial = ""
        self.configurations = []

    def from_pyusb(self, dev):
        """从 pyusb 设备填充"""
        import usb.util
        self.busnum = dev.bus
        self.devnum = dev.address
        self.speed = self._pyusb_speed(dev)
        self.vendor = dev.idVendor
        self.product = dev.idProduct
        self.bcd_device = dev.bcdDevice
        self.dev_class = dev.bDeviceClass
        self.dev_subclass = dev.bDeviceSubClass
        self.dev_protocol = dev.bDeviceProtocol
        try:
            self.manufacturer = usb.util.get_string(dev, dev.iManufacturer) if dev.iManufacturer else ""
        except:
            self.manufacturer = ""
        try:
            self.product_name = usb.util.get_string(dev, dev.iProduct) if dev.iProduct else ""
        except:
            self.product_name = ""
        try:
            self.serial = usb.util.get_string(dev, dev.iSerialNumber) if dev.iSerialNumber else ""
        except:
            self.serial = ""
        self.configurations = []

    @staticmethod
    def _pyusb_speed(dev) -> int:
        s = getattr(dev, 'speed', None)
        if s is None:
            return UsbSpeed.USB_SPEED_HIGH
        speed_map = {
            1: UsbSpeed.USB_SPEED_LOW,
            2: UsbSpeed.USB_SPEED_FULL,
            3: UsbSpeed.USB_SPEED_HIGH,
            4: UsbSpeed.USB_SPEED_SUPER,
            5: UsbSpeed.USB_SPEED_SUPER,
        }
        return speed_map.get(s, UsbSpeed.USB_SPEED_HIGH)

    def pack(self) -> bytes:
        """打包为 USB/IP 设备描述符"""
        fmt = "!IIHHHHHHBBH"
        data = struct.pack(
            fmt,
            self.busnum, self.devnum,
            self.speed, self.vendor, self.product,
            self.bcd_device,
            self.dev_class, self.dev_subclass,
            self.dev_protocol, 0,
            len(self.configurations)
        )
        for s in [self.manufacturer, self.product_name, self.serial]:
            encoded = s.encode('utf-8')[:255]
            data += struct.pack("256s", encoded)
        for cfg in self.configurations:
            data += struct.pack("!I", len(cfg))
            data += cfg
        return data

    @classmethod
    def unpack(cls, data: bytes, offset: int = 0) -> Tuple['USBIPDevice', int]:
        """解包设备描述符"""
        dev = cls()
        fmt = "!IIHHHHHHBBH"
        fields = struct.unpack_from(fmt, data, offset)
        dev.busnum, dev.devnum = fields[0], fields[1]
        dev.speed = fields[2]
        dev.vendor, dev.product = fields[3], fields[4]
        dev.bcd_device = fields[5]
        dev.dev_class, dev.dev_subclass = fields[6], fields[7]
        dev.dev_protocol = fields[8]
        ncfg = fields[10]
        offset += struct.calcsize(fmt)
        for s in ['manufacturer', 'product_name', 'serial']:
            raw = data[offset:offset+256]
            setattr(dev, s, raw.split(b'\0', 1)[0].decode('utf-8', errors='replace'))
            offset += 256
        for _ in range(ncfg):
            if offset + 4 <= len(data):
                clen = struct.unpack_from("!I", data, offset)[0]
                offset += 4
                dev.configurations.append(data[offset:offset+clen])
                offset += clen
        return dev, offset

    def to_dict(self) -> dict:
        return {
            "busnum": self.busnum,
            "devnum": self.devnum,
            "vendor": hex(self.vendor),
            "product": hex(self.product),
            "manufacturer": self.manufacturer,
            "product_name": self.product_name,
            "serial": self.serial,
            "speed": self.speed,
        }

    def __repr__(self):
        return (f"USBIPDevice({self.busnum}:{self.devnum} "
                f"{self.vendor:#06x}:{self.product:#06x} {self.product_name})")


class USBIPCmdSubmit:
    """
    USB/IP CMD_SUBMIT 头 (48 bytes)
    struct usbip_header_cmd_submit:
        __u32 command, seqnum, devid, direction, ep;
        __u32 transfer_flags, transfer_buffer_length, start_frame;
        __u32 number_of_packets, interval;
        unsigned char setup[8];
    """
    FORMAT = "!IIIIIIIIII8s"

    def __init__(self):
        self.command = 0x0001
        self.seqnum = 0
        self.devid = 0
        self.direction = 0
        self.ep = 0
        self.transfer_flags = 0
        self.transfer_buffer_length = 0
        self.start_frame = 0
        self.number_of_packets = 0
        self.interval = 0
        self.setup = b'\x00' * 8
        self.data = b''

    @classmethod
    def unpack(cls, data: bytes) -> 'USBIPCmdSubmit':
        """解包 CMD_SUBMIT 头"""
        cmd = cls()
        fields = struct.unpack_from(cls.FORMAT, data)
        cmd.command, cmd.seqnum = fields[0], fields[1]
        cmd.devid, cmd.direction = fields[2], fields[3]
        cmd.ep = fields[4]
        cmd.transfer_flags, cmd.transfer_buffer_length = fields[5], fields[6]
        cmd.start_frame = fields[7]
        cmd.number_of_packets, cmd.interval = fields[8], fields[9]
        cmd.setup = fields[10]
        # 后面的数据
        cmd.data = data[48:48 + cmd.transfer_buffer_length]
        return cmd

    def is_output(self) -> bool:
        return not (self.ep & 0x80)

    def is_control(self) -> bool:
        return (self.ep & 0x1F) == 0

    def is_interrupt(self) -> bool:
        return (self.ep & 0x1F) == 3

    def is_bulk(self) -> bool:
        return (self.ep & 0x1F) == 2

    def is_isochronous(self) -> bool:
        return (self.ep & 0x1F) == 1

    def bmRequestType(self) -> int:
        return self.setup[0]

    def bRequest(self) -> int:
        return self.setup[1]

    def wValue(self) -> int:
        return struct.unpack('<H', self.setup[2:4])[0]

    def wIndex(self) -> int:
        return struct.unpack('<H', self.setup[4:6])[0]

    def wLength(self) -> int:
        return struct.unpack('<H', self.setup[6:8])[0]

    def __repr__(self):
        return (f"CMD_SUBMIT(seq={self.seqnum} ep=0x{self.ep:02x} "
                f"len={self.transfer_buffer_length} flags={self.transfer_flags:#x})")


class USBIPRetSubmit:
    """
    USB/IP RET_SUBMIT 头 (40 bytes)
    struct usbip_header_ret_submit:
        __u32 command, seqnum, devid, direction, ep;
        __u32 status, actual_length, start_frame;
        __u32 number_of_packets, error_count;
    """
    FORMAT = "!IIIIIIIIII"

    def __init__(self):
        self.command = 0x0002
        self.seqnum = 0
        self.devid = 0
        self.direction = 0
        self.ep = 0
        self.status = 0
        self.actual_length = 0
        self.start_frame = 0
        self.number_of_packets = 0
        self.error_count = 0
        self.data = b''

    def pack(self) -> bytes:
        return struct.pack(
            self.FORMAT,
            self.command, self.seqnum, self.devid,
            self.direction, self.ep, self.status,
            self.actual_length, self.start_frame,
            self.number_of_packets, self.error_count
        )

    def __repr__(self):
        return (f"RET_SUBMIT(seq={self.seqnum} st={self.status} "
                f"actual={self.actual_length})")


class USBIPCmdUnlink:
    """
    USB/IP CMD_UNLINK 头
    struct usbip_header_cmd_unlink:
        __u32 command, seqnum, devid, direction, ep;
        __u32 seqnum_to_unlink;
    """
    FORMAT = "!IIIIIII"

    @classmethod
    def unpack(cls, data: bytes) -> int:
        fields = struct.unpack_from(cls.FORMAT, data)
        return fields[6]  # seqnum_to_unlink


# ---- USB 标准请求构建辅助 ----

def make_get_descriptor_setup(desc_type: int, desc_index: int, lang_id: int = 0) -> bytes:
    """构建 GET_DESCRIPTOR 请求的 setup packet"""
    wValue = (desc_type << 8) | desc_index
    return struct.pack('<BBHHH', 0x80, 6, wValue, lang_id, 255)


def make_set_configuration_setup(config: int) -> bytes:
    """构建 SET_CONFIGURATION 请求的 setup packet"""
    return struct.pack('<BBHHH', 0x00, 9, config, 0, 0)


def make_set_interface_setup(interface: int, alternate: int = 0) -> bytes:
    """构建 SET_INTERFACE 请求的 setup packet"""
    return struct.pack('<BBHHH', 0x01, 11, alternate, interface, 0)
