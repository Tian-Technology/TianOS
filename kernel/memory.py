"""
TianOS 内存管理模块
物理内存管理、虚拟内存、分页
"""

import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from system.hardware_manager import hardware_manager


class PageSize(Enum):
    """页面大小"""
    SIZE_4K = 4096
    SIZE_2M = 2 * 1024 * 1024
    SIZE_1G = 1024 * 1024 * 1024


class MemoryRegion(Enum):
    """内存区域类型"""
    FREE = "free"
    KERNEL = "kernel"
    USER = "user"
    RESERVED = "reserved"
    MMIO = "mmio"
    ACPI = "acpi"


@dataclass
class PageFrame:
    """物理页帧"""
    frame_number: int
    address: int
    size: int = PageSize.SIZE_4K.value
    allocated: bool = False
    owner_pid: Optional[int] = None
    region: MemoryRegion = MemoryRegion.FREE


@dataclass
class PageTable:
    """页表"""
    virtual_address: int
    physical_address: int
    size: int = PageSize.SIZE_4K.value
    present: bool = True
    writable: bool = True
    user_accessible: bool = True
    cached: bool = True


class MemoryManager:
    """
    内存管理器
    管理物理内存分配、虚拟内存映射
    """

    def __init__(self, total_mb: int = None):
        if total_mb is None:
            ram_info = hardware_manager.get_ram_info()
            total_mb = int(ram_info.get("total_mb") or 16384)
        self.total_memory = total_mb * 1024 * 1024
        self.page_size = PageSize.SIZE_4K.value
        self.total_frames = self.total_memory // self.page_size

        # 必须在 _init_frame_table 之前初始化
        self.allocated_memory = 0
        ram_info = hardware_manager.get_ram_info()
        self.reserved_memory = int(ram_info.get("reserved_mb") or 512) * 1024 * 1024

        # 虚拟内存映射
        self.page_tables: Dict[int, List[PageTable]] = {}

        self.lock = threading.Lock()
        self._init_frame_table()

    def _init_frame_table(self):
        """
        物理内存帧表（稀疏 / 惰性物化）

        整个 32GB 内存按 4KB 分页共有约 838 万帧。若在 __init__ 时为每一帧都
        创建 PageFrame 对象，光初始化就要消耗约 10 秒，会严重拖慢开机速度。

        因此这里只维护一个稀疏帧表：仅在真正被分配/保留的帧号上创建对象，
        其余未被使用的帧在逻辑上视为空闲，不占用内存。对外接口
        frame_table / allocate_frames / free_frames / get_memory_stats 用法不变。
        """
        self.frame_table: Dict[int, PageFrame] = {}
        # 分配游标：0 ~ reserved 区域视为保留，从保留区末尾开始向下分配
        self._frame_counter = self.reserved_memory // self.page_size

    def _materialize(self, frame_number: int, region: MemoryRegion = MemoryRegion.FREE) -> PageFrame:
        """按需创建帧对象（惰性物化）"""
        frame = self.frame_table.get(frame_number)
        if frame is None:
            frame = PageFrame(
                frame_number=frame_number,
                address=frame_number * self.page_size,
            )
            self.frame_table[frame_number] = frame
        return frame

    def allocate_frames(self, size: int, pid: int, region: MemoryRegion = MemoryRegion.USER) -> List[int]:
        """
        分配物理页帧

        稀疏实现：从游标开始顺序取未分配的帧号，只对其按需物化。
        系统（模拟）单次分配量都很小，因此帧表始终只包含实际使用的少量帧。
        """
        with self.lock:
            required_frames = (size + self.page_size - 1) // self.page_size
            allocated_frames: List[int] = []

            while len(allocated_frames) < required_frames:
                if self._frame_counter >= self.total_frames:
                    raise MemoryError(
                        f"内存不足: 需要 {required_frames} 帧, "
                        f"可用 {self.total_frames - self._frame_counter}"
                    )
                fn = self._frame_counter
                self._frame_counter += 1
                if fn in self.frame_table and self.frame_table[fn].allocated:
                    continue
                frame = self._materialize(fn, region)
                frame.allocated = True
                frame.owner_pid = pid
                frame.region = region
                allocated_frames.append(fn)
                if region == MemoryRegion.KERNEL:
                    self.allocated_memory += frame.size

            return allocated_frames

    def free_frames(self, frame_numbers: List[int]):
        """释放页帧"""
        with self.lock:
            for fn in frame_numbers:
                frame = self.frame_table.get(fn)
                if frame is not None:
                    frame.allocated = False
                    frame.owner_pid = None
                    frame.region = MemoryRegion.FREE

    def map_page(self, virtual_addr: int, physical_addr: int, pid: int = 0):
        """建立虚拟地址到物理地址的映射"""
        if pid not in self.page_tables:
            self.page_tables[pid] = []
        
        page = PageTable(
            virtual_address=virtual_addr,
            physical_address=physical_addr
        )
        self.page_tables[pid].append(page)

    def unmap_page(self, virtual_addr: int, pid: int = 0):
        """解除虚拟地址映射"""
        if pid in self.page_tables:
            self.page_tables[pid] = [p for p in self.page_tables[pid] 
                                      if p.virtual_address != virtual_addr]

    def get_memory_stats(self) -> Dict:
        """获取内存统计"""
        # 稀疏帧表：已物化的帧数代表正在使用的帧
        kernel_frames = sum(1 for f in self.frame_table.values() if f.region == MemoryRegion.KERNEL)
        user_frames = sum(1 for f in self.frame_table.values() if f.region == MemoryRegion.USER)
        free_frames = self.total_frames - len(self.frame_table)

        return {
            "total_mb": self.total_memory / (1024 * 1024),
            "used_mb": self.allocated_memory / (1024 * 1024),
            "free_mb": (free_frames * self.page_size) / (1024 * 1024),
            "kernel_mb": (kernel_frames * self.page_size) / (1024 * 1024),
            "user_mb": (user_frames * self.page_size) / (1024 * 1024),
            "total_frames": self.total_frames,
            "free_frames": free_frames,
        }


# 全局内存管理器
# 内存总容量与保留量由全局硬件管理器动态决定（受硬件配置器选择影响）
_ram_info = hardware_manager.get_ram_info()
_KERNEL_TOTAL_MB = int(_ram_info.get("total_mb") or 16384)
_KERNEL_RESERVED_MB = int(_ram_info.get("reserved_mb") or 512)
memory_manager = MemoryManager(total_mb=_KERNEL_TOTAL_MB)