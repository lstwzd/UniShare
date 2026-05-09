"""
Large File Chunking Module
Implements chunked file transfer for large files
"""
import os
import struct
import time
from pathlib import Path
from typing import Generator, Optional, Tuple, Callable
from dataclasses import dataclass


@dataclass
class ChunkInfo:
    """块信息"""
    chunk_index: int
    chunk_size: int
    chunk_offset: int
    is_last: bool
    data: bytes = b''
    
    def to_header(self) -> bytes:
        flags = 1 if self.is_last else 0
        return struct.pack(">III", self.chunk_index, self.chunk_size, flags)


class FileChunker:
    """
    大文件分片器
    - 将大文件分割为小块传输
    - 支持流式读取
    - 自动调整块大小
    """
    
    DEFAULT_CHUNK_SIZE = 65536
    MAX_CHUNK_SIZE = 1048576
    MIN_CHUNK_SIZE = 8192
    
    def __init__(self, chunk_size: int = None):
        self.chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE
    
    def calculate_chunks(self, file_size: int) -> int:
        """计算总块数"""
        return (file_size + self.chunk_size - 1) // self.chunk_size
    
    def get_chunk_range(self, chunk_index: int, file_size: int) -> Tuple[int, int]:
        """获取块的偏移范围"""
        start = chunk_index * self.chunk_size
        end = min(start + self.chunk_size, file_size)
        return start, end
    
    def read_chunk(self, file_path: str, chunk_index: int, 
                   file_size: int = None) -> Optional[ChunkInfo]:
        """读取指定块"""
        try:
            path = Path(file_path)
            if not path.exists():
                return None
            
            if file_size is None:
                file_size = path.stat().st_size
            
            total_chunks = self.calculate_chunks(file_size)
            
            if chunk_index >= total_chunks:
                return None
            
            start, end = self.get_chunk_range(chunk_index, file_size)
            chunk_size = end - start
            is_last = chunk_index == total_chunks - 1
            
            with open(path, 'rb') as f:
                f.seek(start)
                data = f.read(chunk_size)
            
            return ChunkInfo(
                chunk_index=chunk_index,
                chunk_size=len(data),
                chunk_offset=start,
                is_last=is_last,
                data=data
            )
        except Exception:
            return None
    
    def chunk_file(self, file_path: str, 
                   callback: Callable = None) -> Generator[ChunkInfo, None, None]:
        """分片生成器"""
        path = Path(file_path)
        if not path.exists():
            return
        
        file_size = path.stat().st_size
        total_chunks = self.calculate_chunks(file_size)
        
        with open(path, 'rb') as f:
            for chunk_index in range(total_chunks):
                start, end = self.get_chunk_range(chunk_index, file_size)
                f.seek(start)
                data = f.read(end - start)
                
                chunk_info = ChunkInfo(
                    chunk_index=chunk_index,
                    chunk_size=len(data),
                    chunk_offset=start,
                    is_last=chunk_index == total_chunks - 1,
                    data=data
                )
                
                if callback:
                    callback(chunk_info)
                
                yield chunk_info
    
    def write_chunk(self, file_path: str, chunk_info: ChunkInfo, 
                    append: bool = False):
        """写入块"""
        mode = 'ab' if append else 'r+b'
        path = Path(file_path)
        
        if not append and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        
        with open(path, mode) as f:
            f.seek(chunk_info.chunk_offset)
            f.write(chunk_info.data)
    
    def optimize_chunk_size(self, file_size: int, bandwidth: float = None) -> int:
        """优化块大小"""
        if bandwidth is None:
            if file_size < 1048576:
                return self.MIN_CHUNK_SIZE
            elif file_size < 104857600:
                return self.DEFAULT_CHUNK_SIZE
            else:
                return self.MAX_CHUNK_SIZE
        
        optimal = int(bandwidth * 0.1)
        return max(self.MIN_CHUNK_SIZE, min(optimal, self.MAX_CHUNK_SIZE))


class ChunkReceiver:
    """
    块接收器
    - 接收并重组文件块
    - 支持乱序接收
    - 验证完整性
    """
    
    def __init__(self, file_path: str, total_size: int, chunk_size: int):
        self.file_path = Path(file_path)
        self.total_size = total_size
        self.chunk_size = chunk_size
        self.total_chunks = (total_size + chunk_size - 1) // chunk_size
        
        self._received_chunks = set()
        self._file = None
        self._last_progress_time = 0
    
    def open(self):
        """打开文件"""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.file_path, 'wb')
        self._file.truncate(self.total_size)
    
    def close(self):
        """关闭文件"""
        if self._file:
            self._file.close()
            self._file = None
    
    def receive_chunk(self, chunk_info: ChunkInfo) -> bool:
        """接收块"""
        if not self._file:
            return False
        
        if chunk_info.chunk_index in self._received_chunks:
            return True
        
        try:
            self._file.seek(chunk_info.chunk_offset)
            self._file.write(chunk_info.data)
            self._received_chunks.add(chunk_info.chunk_index)
            return True
        except Exception:
            return False
    
    def is_complete(self) -> bool:
        """检查是否完成"""
        return len(self._received_chunks) == self.total_chunks
    
    def get_progress(self) -> float:
        """获取进度"""
        if self.total_chunks == 0:
            return 0.0
        return len(self._received_chunks) / self.total_chunks * 100
    
    def get_missing_chunks(self) -> list:
        """获取缺失的块"""
        missing = []
        for i in range(self.total_chunks):
            if i not in self._received_chunks:
                missing.append(i)
        return missing
    
    def get_received_size(self) -> int:
        """获取已接收大小"""
        return len(self._received_chunks) * self.chunk_size
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_chunks": self.total_chunks,
            "received_chunks": len(self._received_chunks),
            "missing_chunks": len(self.get_missing_chunks()),
            "progress": round(self.get_progress(), 2),
            "received_size": self.get_received_size(),
            "total_size": self.total_size
        }
