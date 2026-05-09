"""
Resumable Transfer Module
Implements file transfer resume from breakpoint
"""
import os
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass


@dataclass
class TransferCheckpoint:
    """传输检查点"""
    transfer_id: str
    filename: str
    file_path: str
    total_size: int
    transferred_size: int
    chunk_size: int
    file_hash: str
    last_chunk: int
    
    def to_dict(self) -> dict:
        return {
            "transfer_id": self.transfer_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "total_size": self.total_size,
            "transferred_size": self.transferred_size,
            "chunk_size": self.chunk_size,
            "file_hash": self.file_hash,
            "last_chunk": self.last_chunk
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TransferCheckpoint':
        return cls(
            transfer_id=data["transfer_id"],
            filename=data["filename"],
            file_path=data["file_path"],
            total_size=data["total_size"],
            transferred_size=data["transferred_size"],
            chunk_size=data["chunk_size"],
            file_hash=data["file_hash"],
            last_chunk=data["last_chunk"]
        )


class ResumableTransfer:
    """
    断点续传管理器
    - 保存传输检查点
    - 恢复中断的传输
    - 验证文件完整性
    """
    
    CHECKPOINT_SUFFIX = ".checkpoint"
    MANIFEST_SUFFIX = ".manifest"
    CHUNK_SIZE = 65536
    
    def __init__(self, checkpoint_dir: str = None):
        if checkpoint_dir:
            self.checkpoint_dir = Path(checkpoint_dir)
        else:
            self.checkpoint_dir = Path.home() / "UniShare" / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def create_checkpoint(self, transfer_id: str, filename: str, 
                         file_path: str, total_size: int) -> TransferCheckpoint:
        """创建传输检查点"""
        file_hash = self._calculate_file_hash(file_path, total_size)
        
        checkpoint = TransferCheckpoint(
            transfer_id=transfer_id,
            filename=filename,
            file_path=file_path,
            total_size=total_size,
            transferred_size=0,
            chunk_size=self.CHUNK_SIZE,
            file_hash=file_hash,
            last_chunk=0
        )
        
        self._save_checkpoint(checkpoint)
        return checkpoint
    
    def update_checkpoint(self, transfer_id: str, transferred_size: int, last_chunk: int):
        """更新检查点"""
        checkpoint = self.load_checkpoint(transfer_id)
        if checkpoint:
            checkpoint.transferred_size = transferred_size
            checkpoint.last_chunk = last_chunk
            self._save_checkpoint(checkpoint)
    
    def load_checkpoint(self, transfer_id: str) -> Optional[TransferCheckpoint]:
        """加载检查点"""
        checkpoint_file = self.checkpoint_dir / f"{transfer_id}{self.CHECKPOINT_SUFFIX}"
        
        if not checkpoint_file.exists():
            return None
        
        try:
            with open(checkpoint_file, 'r') as f:
                data = json.load(f)
            return TransferCheckpoint.from_dict(data)
        except Exception:
            return None
    
    def delete_checkpoint(self, transfer_id: str):
        """删除检查点"""
        checkpoint_file = self.checkpoint_dir / f"{transfer_id}{self.CHECKPOINT_SUFFIX}"
        manifest_file = self.checkpoint_dir / f"{transfer_id}{self.MANIFEST_SUFFIX}"
        
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            if manifest_file.exists():
                manifest_file.unlink()
        except Exception:
            pass
    
    def has_checkpoint(self, transfer_id: str) -> bool:
        """检查是否存在检查点"""
        checkpoint_file = self.checkpoint_dir / f"{transfer_id}{self.CHECKPOINT_SUFFIX}"
        return checkpoint_file.exists()
    
    def get_resume_position(self, transfer_id: str) -> int:
        """获取恢复位置"""
        checkpoint = self.load_checkpoint(transfer_id)
        if checkpoint:
            return checkpoint.transferred_size
        return 0
    
    def validate_partial_file(self, transfer_id: str, partial_file_path: str) -> bool:
        """验证部分文件"""
        checkpoint = self.load_checkpoint(transfer_id)
        if not checkpoint:
            return False
        
        partial_path = Path(partial_file_path)
        if not partial_path.exists():
            return False
        
        actual_size = partial_path.stat().st_size
        return actual_size == checkpoint.transferred_size
    
    def get_missing_chunks(self, transfer_id: str) -> list:
        """获取缺失的块"""
        checkpoint = self.load_checkpoint(transfer_id)
        if not checkpoint:
            return []
        
        total_chunks = (checkpoint.total_size + checkpoint.chunk_size - 1) // checkpoint.chunk_size
        manifest_file = self.checkpoint_dir / f"{transfer_id}{self.MANIFEST_SUFFIX}"
        
        received_chunks = set()
        if manifest_file.exists():
            try:
                with open(manifest_file, 'r') as f:
                    manifest = json.load(f)
                    received_chunks = set(manifest.get("chunks", []))
            except Exception:
                pass
        
        missing = []
        for i in range(total_chunks):
            if i not in received_chunks:
                missing.append(i)
        
        return missing
    
    def mark_chunk_received(self, transfer_id: str, chunk_index: int):
        """标记块已接收"""
        manifest_file = self.checkpoint_dir / f"{transfer_id}{self.MANIFEST_SUFFIX}"
        
        received_chunks = set()
        if manifest_file.exists():
            try:
                with open(manifest_file, 'r') as f:
                    manifest = json.load(f)
                    received_chunks = set(manifest.get("chunks", []))
            except Exception:
                pass
        
        received_chunks.add(chunk_index)
        
        manifest = {"chunks": list(received_chunks)}
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f)
    
    def _save_checkpoint(self, checkpoint: TransferCheckpoint):
        """保存检查点"""
        checkpoint_file = self.checkpoint_dir / f"{checkpoint.transfer_id}{self.CHECKPOINT_SUFFIX}"
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint.to_dict(), f)
    
    def _calculate_file_hash(self, file_path: str, size: int) -> str:
        """计算文件哈希（仅前1MB）"""
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                chunk = f.read(min(1048576, size))
                hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""
    
    def cleanup_old_checkpoints(self, max_age_days: int = 7):
        """清理旧检查点"""
        import time
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60
        
        for file in self.checkpoint_dir.iterdir():
            if file.suffix in [self.CHECKPOINT_SUFFIX, self.MANIFEST_SUFFIX]:
                try:
                    if current_time - file.stat().st_mtime > max_age_seconds:
                        file.unlink()
                except Exception:
                    pass
