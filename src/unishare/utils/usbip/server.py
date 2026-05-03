"""
USB/IP 服务端 - 基于 pyusb/libusb 的纯 Python 实现
导出本地 USB 设备，处理远程客户端请求，转发 USB 传输
"""
import socket
import struct
import threading
import time
import traceback
from typing import Dict, List, Optional

from src.unishare.utils.usbip.protocol import (
    USBIPHeader, USBIPDevice, USBIPCmdSubmit, USBIPRetSubmit,
    USBIPCmdUnlink, OpCode, UsbDirection,
)

REQ_HEADER_SIZE = 48  # USBIP_CMD_SUBMIT header size
RET_HEADER_SIZE = 40  # USBIP_RET_SUBMIT header size


class USBIPServer:
    """
    USB/IP 协议服务端
    - 监听 TCP 端口 (默认 3240)
    - 处理 OP_REQ_DEVLIST / OP_REQ_IMPORT
    - 导入后转发 URB 到本地 pyusb 设备
    """

    def __init__(self):
        self._server = None
        self._running = False
        self._thread = None
        self._devices: Dict[str, USBIPDevice] = {}
        self._pyusb_devices: Dict[str, object] = {}
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._running

    def start(self, port: int = 3240) -> bool:
        """启动 USB/IP 服务端"""
        if self._running:
            return True
        try:
            self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server.bind(('0.0.0.0', port))
            self._server.listen(10)
            self._server.settimeout(1.0)
            self._running = True
            self._thread = threading.Thread(target=self._accept_loop, daemon=True)
            self._thread.start()
            return True
        except Exception as e:
            print(f"[USBIP Server] start failed: {e}")
            return False

    def stop(self):
        """停止服务端"""
        self._running = False
        if self._server:
            try:
                self._server.close()
            except:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _accept_loop(self):
        """接受客户端连接循环"""
        while self._running:
            try:
                client, addr = self._server.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(client, addr),
                    daemon=True
                ).start()
            except socket.timeout:
                continue
            except:
                break

    def _handle_client(self, client: socket.socket, addr: tuple):
        """处理单个客户端连接"""
        try:
            client.settimeout(30)

            while self._running:
                # 读取 OP 层协议头
                header_data = self._recv_all(client, 12)
                if not header_data:
                    break

                header = USBIPHeader.unpack(header_data)
                import struct

                if header.op_code == OpCode.OP_REQ_DEVLIST:
                    self._handle_devlist(client)

                elif header.op_code == OpCode.OP_REQ_IMPORT:
                    # 读取 busid (256 bytes)
                    busid_data = self._recv_all(client, 256)
                    if not busid_data:
                        break
                    busid = busid_data.split(b'\0', 1)[0].decode('utf-8', errors='replace')
                    self._handle_import(client, busid)

                else:
                    print(f"[USBIP Server] unknown op: {header.op_code:#x}")
                    break

        except socket.timeout:
            pass
        except Exception as e:
            print(f"[USBIP Server] client error: {e}")
        finally:
            client.close()

    def _handle_devlist(self, client: socket.socket):
        """处理设备列表请求: OP_REQ_DEVLIST"""
        import struct

        # 获取当前设备列表
        devices = self._get_pyusb_devices()

        # 发送 OP_REP_DEVLIST
        reply = USBIPHeader(op_code=OpCode.OP_REP_DEVLIST)
        client.sendall(reply.pack())
        # 设备数量
        client.sendall(struct.pack("!I", len(devices)))

        # 发送每个设备的信息
        for dev in devices:
            client.sendall(dev.pack())

    def _handle_import(self, client: socket.socket, busid: str):
        """处理设备导入请求: OP_REQ_IMPORT"""
        import struct

        # 解析 busid 格式: "busnum-devnum" 或 "bus-dev"
        target_dev = self._find_pyusb_device(busid)

        if target_dev is None:
            # 设备未找到 - 返回错误
            reply = USBIPHeader(op_code=OpCode.OP_REP_IMPORT, status=1)
            client.sendall(reply.pack())
            return

        pyusb_dev, usbip_dev = target_dev

        # 发送 OP_REP_IMPORT 成功 + 设备描述符
        reply = USBIPHeader(op_code=OpCode.OP_REP_IMPORT)
        client.sendall(reply.pack())
        client.sendall(usbip_dev.pack())

        # 进入 URB 转发循环
        self._urb_forward_loop(client, pyusb_dev, usbip_dev)

    def _urb_forward_loop(self, client: socket.socket, pyusb_dev, usbip_dev: USBIPDevice):
        """
        URB 转发循环
        读取客户端的 USBIP_CMD_SUBMIT/CMD_UNLINK
        通过 pyusb 执行实际 USB 传输
        返回 USBIP_RET_SUBMIT/RET_UNLINK
        """
        try:
            # 分离内核驱动 + 设置配置
            try:
                pyusb_dev.detach_kernel_driver(0)
            except:
                pass
            try:
                pyusb_dev.set_configuration()
            except:
                pass
            try:
                pyusb_dev.claim_interface(0)
            except:
                pass

            while self._running:
                # 读取 48 字节的命令头
                header_data = self._recv_all(client, REQ_HEADER_SIZE)
                if not header_data:
                    break

                # 判断命令类型 (前 4 字节)
                cmd_type = struct.unpack_from("!I", header_data)[0]

                if cmd_type == 0x0001:
                    # CMD_SUBMIT
                    cmd = USBIPCmdSubmit.unpack(header_data)
                    if not self._process_submit(client, pyusb_dev, cmd):
                        break
                elif cmd_type == 0x0003:
                    # CMD_UNLINK
                    seq_to_unlink = USBIPCmdUnlink.unpack(header_data)
                    self._process_unlink(client, seq_to_unlink)
                else:
                    break

        except Exception as e:
            print(f"[USBIP Server] URB loop error: {e}")
        finally:
            try:
                pyusb_dev.release_interface(0)
            except:
                pass

    def _process_submit(self, client: socket.socket, pyusb_dev, cmd: USBIPCmdSubmit) -> bool:
        """处理 CMD_SUBMIT - 执行实际 USB 传输"""
        reply = USBIPRetSubmit()
        reply.command = 0x0002
        reply.seqnum = cmd.seqnum
        reply.devid = cmd.devid
        reply.direction = cmd.direction
        reply.ep = cmd.ep
        reply.start_frame = cmd.start_frame
        reply.number_of_packets = cmd.number_of_packets

        try:
            # 根据端点类型选择传输方式
            ep_num = cmd.ep & 0x7F
            is_in = bool(cmd.ep & 0x80)

            if cmd.is_control():
                bmRT = cmd.bmRequestType()
                bReq = cmd.bRequest()
                wVal = cmd.wValue()
                wIdx = cmd.wIndex()
                wLen = cmd.wLength()

                if is_in:
                    actual = pyusb_dev.ctrl_transfer(
                        bmRT, bReq, wVal, wIdx, wLen,
                        timeout=5000
                    )
                    if isinstance(actual, bytes):
                        reply.actual_length = len(actual)
                        reply.data = actual
                    else:
                        reply.actual_length = actual if actual else 0
                else:
                    actual = pyusb_dev.ctrl_transfer(
                        bmRT, bReq, wVal, wIdx,
                        cmd.data if cmd.data else None,
                        timeout=5000
                    )
                    reply.actual_length = actual if actual else 0

                reply.status = 0

            elif is_in:
                # IN 传输 (设备 -> 主机)
                if cmd.is_bulk():
                    data = pyusb_dev.read(ep_num | 0x80, cmd.transfer_buffer_length or 16384, timeout=5000)
                elif cmd.is_interrupt():
                    data = pyusb_dev.read(ep_num | 0x80, cmd.transfer_buffer_length or 64, timeout=5000)
                else:
                    data = pyusb_dev.read(ep_num | 0x80, cmd.transfer_buffer_length or 512, timeout=5000)

                reply.actual_length = len(data)
                reply.data = bytes(data)
                reply.status = 0

            else:
                # OUT 传输 (主机 -> 设备)
                if cmd.data:
                    if cmd.is_bulk():
                        pyusb_dev.write(ep_num, bytes(cmd.data), timeout=5000)
                    elif cmd.is_interrupt():
                        pyusb_dev.write(ep_num, bytes(cmd.data), timeout=5000)
                    else:
                        pyusb_dev.write(ep_num, bytes(cmd.data), timeout=5000)

                reply.actual_length = cmd.transfer_buffer_length or len(cmd.data)
                reply.status = 0

        except Exception as e:
            # 传输失败
            reply.status = -1
            reply.actual_length = 0
            reply.data = b''
            print(f"[USBIP] transfer error seq={cmd.seqnum}: {e}")

        # 发送回复
        try:
            header = reply.pack()
            client.sendall(header)
            if reply.data:
                client.sendall(bytes(reply.data))
            return True
        except:
            return False

    def _process_unlink(self, client: socket.socket, seqnum: int):
        """处理 CMD_UNLINK"""
        import struct
        reply = struct.pack("!IIIIIIIIII", 0x0004, seqnum, 0, 0, 0, 0, 0, 0, 0, 0)
        try:
            client.sendall(reply)
        except:
            pass

    def _recv_all(self, sock: socket.socket, size: int) -> Optional[bytes]:
        """接收指定字节数"""
        data = b''
        while len(data) < size:
            try:
                chunk = sock.recv(size - len(data))
                if not chunk:
                    return None
                data += chunk
            except socket.timeout:
                return None if len(data) == 0 else data
            except:
                return None
        return data

    # ---- 设备枚举 ----

    def _get_pyusb_devices(self) -> List[USBIPDevice]:
        """枚举所有 pyusb 设备"""
        devices = []
        try:
            import usb.core
            for dev in usb.core.find(find_all=True):
                try:
                    usbip_dev = USBIPDevice()
                    usbip_dev.from_pyusb(dev)
                    devices.append(usbip_dev)
                    busid = f"{dev.bus}-{dev.address}"
                    self._pyusb_devices[busid] = dev
                except:
                    pass
        except:
            pass
        return devices

    def _find_pyusb_device(self, busid: str):
        """
        根据 busid 查找 pyusb 设备
        busid 格式: "bus-address" 如 "1-2"
        """
        try:
            import usb.core
            parts = busid.split('-')
            if len(parts) == 2:
                bus = int(parts[0])
                addr = int(parts[1])
                for dev in usb.core.find(find_all=True):
                    if dev.bus == bus and dev.address == addr:
                        usbip_dev = USBIPDevice()
                        usbip_dev.from_pyusb(dev)
                        return dev, usbip_dev
        except:
            pass
        return None


# 全局单例
server = USBIPServer()
