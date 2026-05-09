"""
USB Device State Sync Module
Synchronizes USB device state between server and client
"""
import socket
import threading
import json
import time
from typing import Dict, Optional, Callable
from enum import Enum


class DeviceState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    EXPORTED = "exported"
    ATTACHED = "attached"
    ERROR = "error"


class USBDeviceSync:
    """
    USB 设备状态同步
    - 服务端广播设备状态变更
    - 客户端接收并更新本地状态
    - 支持设备热插拔通知
    """
    
    SYNC_PORT_OFFSET = 20
    HEARTBEAT_INTERVAL = 5.0
    STATE_UPDATE_INTERVAL = 2.0
    
    def __init__(self, base_port: int = 3240):
        self.sync_port = base_port + self.SYNC_PORT_OFFSET
        self._running = False
        self._server_socket: Optional[socket.socket] = None
        self._client_socket: Optional[socket.socket] = None
        self._device_states: Dict[str, DeviceState] = {}
        self._state_callbacks: Dict[str, Callable] = {}
        self._lock = threading.Lock()
        
    def start_server(self) -> bool:
        """启动状态同步服务端"""
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._server_socket.bind(("0.0.0.0", self.sync_port))
            self._server_socket.settimeout(1.0)
            self._running = True
            
            def broadcast_loop():
                last_broadcast = 0
                while self._running:
                    try:
                        current_time = time.time()
                        
                        if current_time - last_broadcast >= self.STATE_UPDATE_INTERVAL:
                            with self._lock:
                                states = {
                                    busid: state.value 
                                    for busid, state in self._device_states.items()
                                }
                            
                            if states:
                                msg = json.dumps({
                                    "type": "state_update",
                                    "timestamp": current_time,
                                    "devices": states
                                }).encode()
                                
                                self._server_socket.sendto(msg, ("255.255.255.255", self.sync_port))
                            
                            last_broadcast = current_time
                        
                        try:
                            data, addr = self._server_socket.recvfrom(1024)
                            msg = json.loads(data.decode())
                            
                            if msg.get("type") == "request_state":
                                with self._lock:
                                    states = {
                                        busid: state.value 
                                        for busid, state in self._device_states.items()
                                    }
                                response = json.dumps({
                                    "type": "state_response",
                                    "devices": states
                                }).encode()
                                self._server_socket.sendto(response, addr)
                                
                        except socket.timeout:
                            continue
                            
                    except Exception:
                        continue
            
            threading.Thread(target=broadcast_loop, daemon=True).start()
            return True
        except Exception:
            return False
    
    def start_client(self, server_ip: str, on_state_change: Callable) -> bool:
        """启动状态同步客户端"""
        try:
            self._client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._client_socket.settimeout(1.0)
            self._running = True
            self._on_state_change = on_state_change
            
            def receive_loop():
                while self._running:
                    try:
                        request = json.dumps({"type": "request_state"}).encode()
                        self._client_socket.sendto(request, (server_ip, self.sync_port))
                        
                        try:
                            data, _ = self._client_socket.recvfrom(65535)
                            msg = json.loads(data.decode())
                            
                            if msg.get("type") in ["state_update", "state_response"]:
                                devices = msg.get("devices", {})
                                
                                for busid, state_str in devices.items():
                                    new_state = DeviceState(state_str)
                                    old_state = self._device_states.get(busid)
                                    
                                    if old_state != new_state:
                                        self._device_states[busid] = new_state
                                        if self._on_state_change:
                                            self._on_state_change(busid, new_state, old_state)
                                        
                        except socket.timeout:
                            continue
                            
                    except Exception:
                        continue
                    
                    time.sleep(self.STATE_UPDATE_INTERVAL)
            
            threading.Thread(target=receive_loop, daemon=True).start()
            return True
        except Exception:
            return False
    
    def stop(self):
        """停止状态同步"""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except:
                pass
        if self._client_socket:
            try:
                self._client_socket.close()
            except:
                pass
    
    def update_device_state(self, busid: str, state: DeviceState):
        """更新设备状态（服务端）"""
        with self._lock:
            self._device_states[busid] = state
    
    def remove_device(self, busid: str):
        """移除设备"""
        with self._lock:
            self._device_states.pop(busid, None)
    
    def get_device_state(self, busid: str) -> Optional[DeviceState]:
        """获取设备状态"""
        return self._device_states.get(busid)
    
    def get_all_states(self) -> Dict[str, DeviceState]:
        """获取所有设备状态"""
        return self._device_states.copy()
    
    def register_callback(self, busid: str, callback: Callable):
        """注册设备状态变更回调"""
        self._state_callbacks[busid] = callback
    
    def unregister_callback(self, busid: str):
        """取消注册回调"""
        self._state_callbacks.pop(busid, None)