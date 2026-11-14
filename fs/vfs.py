"""
TianOS 虚拟文件系统 (VFS)
=========================
提供统一的文件系统接口，支持多种文件系统后端。

目录结构:
/
├── boot/       - 引导文件
├── bin/        - 系统二进制文件
├── dev/        - 设备文件
├── etc/        - 配置文件
├── home/       - 用户目录
├── lib/        - 系统库
├── mnt/        - 挂载点
├── proc/       - 进程信息 (虚拟)
├── sys/        - 系统信息 (虚拟)
├── tmp/        - 临时文件
├── usr/        - 用户程序
└── var/        - 可变数据
"""

import time
import os
import json
from typing import Dict, List, Optional, Tuple, Any, BinaryIO
from enum import Enum
from dataclasses import dataclass, field

from system.config import sys_config


class FileType(Enum):
    """文件类型"""
    REGULAR = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    DEVICE = "device"
    PIPE = "pipe"
    SOCKET = "socket"


class FilePermission(Enum):
    """文件权限"""
    READ = 0x04
    WRITE = 0x02
    EXECUTE = 0x01
    
    @classmethod
    def from_string(cls, s: str) -> int:
        """从字符串解析权限 (如 "rwxr-xr-x")"""
        perm = 0
        if len(s) >= 3:
            if s[0] == 'r': perm |= cls.READ.value
            if s[1] == 'w': perm |= cls.WRITE.value
            if s[2] == 'x': perm |= cls.EXECUTE.value
        return perm


@dataclass
class FileEntry:
    """文件条目"""
    name: str
    file_type: FileType = FileType.REGULAR
    size: int = 0
    permissions: int = 0o644
    owner: str = "root"
    group: str = "root"
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    content: bytes = field(default_factory=bytes)
    target: Optional[str] = None  # Symlink target
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.file_type.value,
            "size": self.size,
            "permissions": self.permissions,
            "owner": self.owner,
            "group": self.group,
            "created": self.created_at,
            "modified": self.modified_at,
        }


class VirtualFileSystem:
    """
    虚拟文件系统
    内存中的文件系统，模拟完整目录结构
    """

    def __init__(self):
        self.root: Dict[str, FileEntry] = {}
        self.current_directory = "/"
        self.mount_points: Dict[str, str] = {}
        self._init_filesystem()

    def _init_filesystem(self):
        """初始化文件系统目录结构"""
        # 创建标准目录
        directories = [
            "/boot", "/bin", "/dev", "/etc", "/home",
            "/lib", "/mnt", "/proc", "/sys", "/tmp",
            "/usr", "/usr/bin", "/usr/lib", "/usr/share",
            "/var", "/var/log", "/var/tmp",
            "/home/user", "/home/user/Documents",
            "/home/user/Downloads", "/home/user/Desktop",
        ]
        
        for dir_path in directories:
            self._mkdir_p(dir_path)
        
        # 创建一些系统文件
        self._create_system_files()
        
        # 创建设备文件
        self._create_device_files()

    def _mkdir_p(self, path: str):
        """递归创建目录"""
        parts = path.strip("/").split("/")
        current = self.root
        
        for part in parts:
            if part not in current:
                entry = FileEntry(
                    name=part,
                    file_type=FileType.DIRECTORY,
                    permissions=0o755,
                )
                current[part] = entry
            current = current[part].content if isinstance(current[part].content, dict) else {}

    def _create_system_files(self):
        """创建系统文件"""
        system_files = {
            "/etc/hostname": b"tianos\n",
            "/etc/hosts": b"127.0.0.1\tlocalhost\n10.0.2.15\ttianos\n",
            "/etc/resolv.conf": b"nameserver 8.8.8.8\nnameserver 8.8.4.4\n",
            "/etc/fstab": b"# TianOS File System Table\n/dev/hda1\t/\t\text4\tdefaults\t0\t1\n",
            "/etc/passwd": b"root:x:0:0:root:/root:/bin/bash\nuser:x:1000:1000:user:/home/user:/bin/bash\n",
            "/etc/issue": f"TianOS {sys_config.SYSTEM_VERSION} \\n \\l\n".encode(),
            "/boot/kernel.bin": b"[TianOS Kernel Image - Simulated]",
            "/boot/initrd.img": b"[TianOS Initrd - Simulated]",
        }
        
        for path, content in system_files.items():
            self.create_file(path, content)

    def _create_device_files(self):
        """创建设备文件"""
        devices = {
            "/dev/null": b"",
            "/dev/zero": b"\x00" * 4096,
            "/dev/random": b"\xff" * 4096,
            "/dev/tty0": b"[Virtual Console]",
            "/dev/hda": b"[ATA Hard Disk]",
            "/dev/eth0": b"[Ethernet Device]",
        }
        
        for path, content in devices.items():
            entry = self._get_entry_by_path(path)
            if entry:
                entry.file_type = FileType.DEVICE
                entry.content = content

    def _get_entry_by_path(self, path: str) -> Optional[FileEntry]:
        """通过路径获取文件条目"""
        if path.startswith("/"):
            path = path[1:]
        
        parts = path.split("/")
        current = self.root
        
        for part in parts:
            if not part:
                continue
            if isinstance(current, dict) and part in current:
                entry = current[part]
                if entry.file_type == FileType.DIRECTORY:
                    current = entry.content if isinstance(entry.content, dict) else {}
                else:
                    return entry
            else:
                return None
        
        return None  # 目录本身

    def _resolve_path(self, path: str) -> str:
        """解析路径 (处理相对路径和 ..)"""
        if not path.startswith("/"):
            path = self.current_directory.rstrip("/") + "/" + path
        
        # 规范化路径
        parts = []
        for part in path.split("/"):
            if part == "..":
                if parts:
                    parts.pop()
            elif part and part != ".":
                parts.append(part)
        
        return "/" + "/".join(parts)

    def list_directory(self, path: str = ".") -> List[FileEntry]:
        """列出目录内容"""
        resolved = self._resolve_path(path)
        
        if resolved == "/":
            return list(self.root.values())
        
        entry = self._get_entry_by_path(resolved)
        if entry and entry.file_type == FileType.DIRECTORY:
            if isinstance(entry.content, dict):
                return list(entry.content.values())
        
        return []

    def create_file(self, path: str, content: bytes = b"", 
                    permissions: int = 0o644) -> bool:
        """创建文件"""
        resolved = self._resolve_path(path)
        dir_path = os.path.dirname(resolved)
        filename = os.path.basename(resolved)
        
        # 确保父目录存在
        self._mkdir_p(dir_path)
        
        # 获取父目录
        parent = self._get_entry_by_path(dir_path)
        if parent and parent.file_type == FileType.DIRECTORY:
            if isinstance(parent.content, dict):
                parent.content[filename] = FileEntry(
                    name=filename,
                    content=content,
                    size=len(content),
                    permissions=permissions,
                )
                return True
        
        return False

    def read_file(self, path: str) -> Optional[bytes]:
        """读取文件"""
        resolved = self._resolve_path(path)
        entry = self._get_entry_by_path(resolved)
        
        if entry and entry.file_type == FileType.REGULAR:
            entry.modified_at = time.time()
            return entry.content
        
        return None

    def write_file(self, path: str, content: bytes) -> bool:
        """写入文件"""
        resolved = self._resolve_path(path)
        entry = self._get_entry_by_path(resolved)
        
        if entry:
            entry.content = content
            entry.size = len(content)
            entry.modified_at = time.time()
            return True
        
        return self.create_file(path, content)

    def delete(self, path: str) -> bool:
        """删除文件或空目录"""
        resolved = self._resolve_path(path)
        dir_path = os.path.dirname(resolved)
        filename = os.path.basename(resolved)
        
        parent = self._get_entry_by_path(dir_path)
        if parent and parent.file_type == FileType.DIRECTORY:
            if isinstance(parent.content, dict) and filename in parent.content:
                del parent.content[filename]
                return True
        
        return False

    def file_exists(self, path: str) -> bool:
        """检查文件是否存在"""
        resolved = self._resolve_path(path)
        return self._get_entry_by_path(resolved) is not None

    def get_info(self, path: str) -> Optional[Dict]:
        """获取文件信息"""
        resolved = self._resolve_path(path)
        entry = self._get_entry_by_path(resolved)
        
        if entry:
            return entry.to_dict()
        
        if resolved == "/":
            return {
                "name": "/", "type": "directory",
                "size": len(self.root), "permissions": 0o755,
                "owner": "root", "group": "root",
            }
        
        return None

    def get_status(self) -> Dict:
        """获取文件系统状态"""
        total_files = self._count_entries(self.root)
        return {
            "type": "Virtual File System",
            "total_inodes": total_files,
            "used_inodes": total_files,
            "free_inodes": "unlimited",
            "total_size": "unlimited",
            "mounts": list(self.mount_points.keys()),
        }

    def _count_entries(self, node: Dict) -> int:
        """递归统计条目数"""
        count = 0
        for entry in node.values():
            count += 1
            if entry.file_type == FileType.DIRECTORY and isinstance(entry.content, dict):
                count += self._count_entries(entry.content)
        return count

    def format_tree(self, path: str = "/", indent: str = "") -> str:
        """生成目录树"""
        result = []
        entries = self.list_directory(path)
        
        for i, entry in enumerate(entries):
            is_last = (i == len(entries) - 1)
            prefix = "└── " if is_last else "├── "
            result.append(f"{indent}{prefix}{entry.name}/" 
                         if entry.file_type == FileType.DIRECTORY 
                         else f"{indent}{prefix}{entry.name}")
            
            if entry.file_type == FileType.DIRECTORY:
                sub_path = os.path.join(path, entry.name) if path != "/" else f"/{entry.name}"
                sub_indent = indent + ("    " if is_last else "│   ")
                result.append(self.format_tree(sub_path, sub_indent))
        
        return "\n".join(result)


# 全局文件系统实例
vfs = VirtualFileSystem()