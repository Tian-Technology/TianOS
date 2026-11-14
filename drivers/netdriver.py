"""
TianOS 网络设备驱动
虚拟网卡驱动程序，为网络协议栈提供硬件接口
"""

import threading
import time
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass

from net.tcpip import (
    VirtualNIC, MACAddress, IPAddress, NetworkStack
)
from system.config import SystemConfig


def _system_version() -> str:
    """驱动版本与系统版本保持同步（版本修改只需改 system/config.py）"""
    return SystemConfig().SYSTEM_VERSION


class NetworkDriver:
    """
    网络设备驱动程序
    
    管理虚拟网卡并提供:
    - 设备初始化/关闭
    - 数据包发送/接收
    - 中断处理
    - 统计信息
    """

    def __init__(self):
        self.nic: Optional[VirtualNIC] = None
        self.is_initialized = False
        self.irq_number = 11  # 模拟IRQ 11
        self.driver_name = "tianos-vnic"
        self.driver_version = _system_version()
        
        # 中断处理
        self.interrupt_handler: Optional[Callable] = None
        self.interrupt_pending = False
        
        # 统计
        self.stats = {
            "interrupts": 0,
            "dma_transfers": 0,
            "buffer_overruns": 0,
            "crc_errors": 0,
        }

    def probe(self) -> bool:
        """探测设备"""
        # 模拟硬件探测
        self.nic = VirtualNIC(
            name="eth0",
            mac=MACAddress(),
            ip=IPAddress()
        )
        return True

    def initialize(self) -> bool:
        """初始化驱动"""
        if not self.nic:
            if not self.probe():
                return False
        
        # 分配I/O端口 (模拟)
        self.io_base = 0x300
        self.mmio_base = 0xFEB00000
        
        # 设置中断
        self._setup_interrupts()
        
        self.is_initialized = True
        print(f"[DRV] {self.driver_name} v{self.driver_version} 已加载")
        print(f"[DRV]   MAC: {self.nic.mac}")
        print(f"[DRV]   IRQ: {self.irq_number}")
        print(f"[DRV]   I/O: 0x{self.io_base:04X}")
        
        return True

    def _setup_interrupts(self):
        """设置中断处理"""
        def irq_handler():
            self.stats["interrupts"] += 1
            if self.interrupt_handler:
                self.interrupt_handler()
        
        # 中断处理线程
        self.irq_thread = threading.Thread(target=self._irq_loop, daemon=True)

    def _irq_loop(self):
        """中断循环"""
        while self.is_initialized:
            if self.interrupt_pending:
                self.interrupt_pending = False
                if self.interrupt_handler:
                    self.interrupt_handler()
            time.sleep(0.001)

    def send_packet(self, data: bytes) -> bool:
        """发送数据包"""
        if not self.is_initialized or not self.nic:
            return False
        
        # DMA传输 (模拟)
        self.stats["dma_transfers"] += 1
        
        # 触发发送完成中断
        self.interrupt_pending = True
        
        return True

    def receive_packet(self) -> Optional[bytes]:
        """接收数据包"""
        # 模拟接收
        return None

    def get_mac_address(self) -> str:
        """获取MAC地址"""
        if self.nic:
            return str(self.nic.mac)
        return ""

    def set_promiscuous_mode(self, enabled: bool):
        """设置混杂模式"""
        pass  # 模拟驱动不支持混杂模式

    def get_statistics(self) -> Dict:
        """获取驱动统计"""
        if self.nic:
            nic_stats = self.nic.get_stats()
            return {**self.stats, **nic_stats}
        return self.stats

    def shutdown(self):
        """关闭驱动"""
        self.is_initialized = False
        if self.nic:
            self.nic.down()
        print(f"[DRV] {self.driver_name} 已卸载")


# 全局网络驱动实例
net_driver = NetworkDriver()