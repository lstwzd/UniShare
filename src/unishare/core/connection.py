"""
Connection Manager - 连接状态管理器
支持心跳检测、自动重连、状态监控
"""
import socket
import threading
import time
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


@dataclass
class Connection:
    name: str
    socket: Optional[socket.socket] = None
    state: ConnectionState = ConnectionState.DISCONNECTED
    last_heartbeat: float = 0
    reconnect_attempts: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConnectionManager:
    """
    连接状态管理器
    管理所有模块的网络连接，提供心跳检测和自动重连
    """
    
    def __init__(self):
        self.connections: Dict[str, Connection] = {}
        self.heartbeat_interval = 3.0
        self.heartbeat_timeout = 10.0
        self.reconnect_delay = 5.0
        self.max_reconnect_attempts = 3
        self._running = False
        self._heartbeat_thread = None
        self._on_disconnect_callback: Optional[Callable] = None
        self._on_reconnect_callback: Optional[Callable] = None
    
    def set_callbacks(self, on_disconnect: Optional[Callable] = None, 
                      on_reconnect: Optional[Callable] = None):
        """设置断开和重连回调"""
        self._on_disconnect_callback = on_disconnect
        self._on_reconnect_callback = on_reconnect
    
    def start(self):
        """启动连接管理器"""
        if self._running:
            return
        self._running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
    
    def stop(self):
        """停止连接管理器"""
        self._running = False
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2)
        
        for conn in self.connections.values():
            if conn.socket:
                try:
                    conn.socket.close()
                except:
                    pass
        self.connections.clear()
    
    def register_connection(self, name: str, sock: socket.socket, 
                            metadata: Optional[Dict] = None) -> bool:
        """注册连接"""
        if name in self.connections:
            return False
        
        self.connections[name] = Connection(
            name=name,
            socket=sock,
            state=ConnectionState.CONNECTED,
            last_heartbeat=time.time(),
            metadata=metadata or {}
        )
        return True
    
    def unregister_connection(self, name: str):
        """注销连接"""
        if name in self.connections:
            conn = self.connections[name]
            if conn.socket:
                try:
                    conn.socket.close()
                except:
                    pass
            del self.connections[name]
    
    def get_connection(self, name: str) -> Optional[Connection]:
        """获取连接"""
        return self.connections.get(name)
    
    def get_state(self, name: str) -> ConnectionState:
        """获取连接状态"""
        conn = self.connections.get(name)
        return conn.state if conn else ConnectionState.DISCONNECTED
    
    def get_all_states(self) -> Dict[str, ConnectionState]:
        """获取所有连接状态"""
        return {name: conn.state for name, conn in self.connections.items()}
    
    def update_heartbeat(self, name: str):
        """更新心跳时间"""
        conn = self.connections.get(name)
        if conn:
            conn.last_heartbeat = time.time()
            conn.state = ConnectionState.CONNECTED
    
    def _heartbeat_loop(self):
        """心跳检测循环"""
        while self._running:
            current_time = time.time()
            
            for name, conn in list(self.connections.items()):
                if conn.state != ConnectionState.CONNECTED:
                    continue
                
                if current_time - conn.last_heartbeat > self.heartbeat_timeout:
                    self._handle_disconnect(name)
            
            time.sleep(self.heartbeat_interval)
    
    def _handle_disconnect(self, name: str):
        """处理断开连接"""
        conn = self.connections.get(name)
        if not conn:
            return
        
        conn.state = ConnectionState.DISCONNECTED
        self.log_warning(f"连接 {name} 已断开")
        
        if self._on_disconnect_callback:
            try:
                self._on_disconnect_callback(name)
            except Exception as e:
                self.log_error(f"断开回调执行失败: {e}")
        
        threading.Thread(target=self._attempt_reconnect, args=(name,), daemon=True).start()
    
    def _attempt_reconnect(self, name: str):
        """尝试重连"""
        conn = self.connections.get(name)
        if not conn:
            return
        
        conn.state = ConnectionState.RECONNECTING
        
        for attempt in range(self.max_reconnect_attempts):
            if not self._running:
                break
            
            self.log_info(f"尝试重连 {name} ({attempt + 1}/{self.max_reconnect_attempts})")
            
            time.sleep(self.reconnect_delay)
            
            if self._try_reconnect(name):
                conn.state = ConnectionState.CONNECTED
                conn.last_heartbeat = time.time()
                conn.reconnect_attempts = 0
                self.log_info(f"连接 {name} 重连成功")
                
                if self._on_reconnect_callback:
                    try:
                        self._on_reconnect_callback(name)
                    except Exception as e:
                        self.log_error(f"重连回调执行失败: {e}")
                return
        
        conn.state = ConnectionState.DISCONNECTED
        self.log_error(f"连接 {name} 重连失败，已放弃")
    
    def _try_reconnect(self, name: str) -> bool:
        """尝试实际重连（子类可重写）"""
        return False
    
    def log_info(self, msg: str):
        from src.unishare.core.logger import log
        log.info(f"[ConnectionManager] {msg}")
    
    def log_warning(self, msg: str):
        from src.unishare.core.logger import log
        log.warning(f"[ConnectionManager] {msg}")
    
    def log_error(self, msg: str):
        from src.unishare.core.logger import log
        log.error(f"[ConnectionManager] {msg}")


connection_manager = ConnectionManager()
