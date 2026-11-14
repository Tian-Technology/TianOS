"""
TianOS Bootloader - 引导加载程序
===================================
BIOS完成POST后，将控制权转交给引导加载程序。
引导加载程序负责加载内核到内存并启动内核。

引导流程:
1. BIOS加载引导扇区到 0x7C00
2. 引导加载程序初始化基本环境
3. 加载内核映像到内存
4. 设置保护模式/长模式
5. 跳转到内核入口点
"""

import time
import struct
from typing import Optional, Callable, Dict, List
from enum import Enum

from boot.bios import BIOS
from system.config import sys_config


class BootStage(Enum):
    """引导阶段"""
    LOADED = "boot_loaded"          # 引导加载程序已加载
    ENV_INIT = "env_init"           # 环境初始化
    KERNEL_LOAD = "kernel_load"     # 加载内核
    KERNEL_VERIFY = "kernel_verify" # 校验内核
    MEMORY_SETUP = "memory_setup"   # 内存布局设置
    PROTECTED_MODE = "protected_mode"  # 进入保护模式
    KERNEL_START = "kernel_start"   # 启动内核
    BOOT_FAILED = "boot_failed"     # 引导失败


class Bootloader:
    """
    TianOS 引导加载程序
    
    模拟Stage 1 + Stage 2引导过程:
    - Stage 1: 从引导扇区加载 (446字节引导代码 + 64字节分区表)
    - Stage 2: 加载内核并设置执行环境
    """

    def __init__(self, bios: BIOS):
        self.bios = bios
        self.config = sys_config
        self.stage = BootStage.LOADED
        self.stage_history: List[BootStage] = []
        
        # 内核信息
        self.kernel_info = {
            "name": "TianOS Kernel",
            "version": self.config.SYSTEM_VERSION,
            "entry_point": 0x100000,   # 1MB 标记 - 内核加载地址
            "size_kb": 0,
            "offset": 0,
            "checksum": 0,
        }
        
        # 内存布局
        self.memory_map = {
            "low_memory": {
                "start": 0x000000,
                "end": 0x09FFFF,
                "size_kb": 640,
                "type": "常规内存"
            },
            "bios_area": {
                "start": 0x0A0000,
                "end": 0x0FFFFF,
                "size_kb": 384,
                "type": "BIOS/硬件"
            },
            "kernel_base": {
                "start": 0x100000,
                "end": 0x500000,
                "size_kb": 4096,
                "type": "内核区域"
            },
            "user_space": {
                "start": 0x500000,
                "end": 0x40000000,
                "size_kb": sys_config.HARDWARE["memory"]["total_mb"] * 1024,
                "type": "用户空间"
            },
        }
        
        # 多引导信息 (Multiboot)
        self.multiboot_info = {}
        
        # 命令行参数
        self.cmdline = f"root=/dev/hda1 ro quiet splash"
        
        # 回调
        self.on_stage_change: Optional[Callable] = None
        self.on_progress: Optional[Callable] = None

    def set_stage_callback(self, callback: Callable):
        """设置阶段变化回调"""
        self.on_stage_change = callback

    def set_progress_callback(self, callback: Callable):
        """设置进度回调"""
        self.on_progress = callback

    def _update_stage(self, stage: BootStage):
        """更新阶段并触发回调"""
        self.stage = stage
        self.stage_history.append(stage)
        if self.on_stage_change:
            self.on_stage_change(stage)

    def _simulate_kernel_load(self) -> bool:
        """
        模拟加载内核到内存
        在模拟环境中，我们直接加载Python内核模块
        """
        try:
            # 模拟从磁盘读取内核
            kernel_size = 2048  # 模拟2MB内核
            
            # 模拟读取进度
            for i in range(0, 100, 5):
                time.sleep(0.05)
                if self.on_progress:
                    self.on_progress("加载内核", i, f"正在读取内核数据... {i}%")
            
            self.kernel_info["size_kb"] = kernel_size
            
            if self.on_progress:
                self.on_progress("加载内核", 100, "内核加载完成")
            
            return True
            
        except Exception as e:
            raise RuntimeError(f"内核加载失败: {e}")

    def _verify_kernel(self) -> bool:
        """
        校验内核映像的完整性
        模拟检查校验和、签名等
        """
        checks = {
            "checksum": True,
            "signature": True,
            "format": True,
            "version_compat": True,
        }
        
        if self.on_progress:
            self.on_progress("校验内核", 0, "正在校验内核完整性...")
        
        time.sleep(0.2)
        
        # 模拟校验失败率 (1%概率失败)
        import random
        if random.random() < 0.01:
            checks["checksum"] = False
            return False
        
        self.kernel_info["checksum"] = 0xA55A5AA5  # 模拟校验和
        
        if self.on_progress:
            self.on_progress("校验内核", 100, "内核校验通过")
        
        return True

    def _setup_memory(self) -> Dict:
        """
        设置内存布局
        准备页表、GDT、IDT等
        """
        memory_info = {
            "gdt": {
                "address": 0x00000800,
                "size": 64,
                "entries": 3,  # NULL, Code, Data
            },
            "idt": {
                "address": 0x00000840,
                "size": 2048,
                "entries": 256,
            },
            "page_directory": {
                "address": 0x00001000,
                "size": 4096,
            },
            "page_tables": {
                "address": 0x00002000,
                "size": 16384,
                "count": 4,
            },
            "kernel_stack": {
                "address": 0x0007E000,
                "size": 8192,
            },
        }
        
        if self.on_progress:
            self.on_progress("内存设置", 100, "内存布局初始化完成")
        
        return memory_info

    def _enter_protected_mode(self) -> bool:
        """
        进入保护模式
        模拟: 开启A20线、设置控制寄存器等
        """
        steps = [
            ("开启A20地址线", True),
            ("加载GDT", True),
            ("设置CR0保护模式位", True),
            ("刷新流水线", True),
            ("跳转到保护模式代码", True),
        ]
        
        for i, (step_name, success) in enumerate(steps):
            time.sleep(0.1)
            if self.on_progress:
                self.on_progress("保护模式", (i + 1) * 20, step_name)
            if not success:
                return False
        
        return True

    def boot(self, progress_callback: Optional[Callable] = None) -> bool:
        """
        执行完整的引导流程
        
        Args:
            progress_callback: 进度回调 (阶段名, 进度, 描述)
            
        Returns:
            bool: 引导是否成功
        """
        try:
            if progress_callback:
                self.on_progress = progress_callback
            
            # ========== Stage 1: 引导加载程序初始化 ==========
            self._update_stage(BootStage.ENV_INIT)
            
            if self.on_progress:
                self.on_progress("引导初始化", 0, "BIOS将控制权转交给引导程序")
            
            # 显示引导信息
            self._print_boot_banner()
            time.sleep(0.3)
            
            if self.on_progress:
                self.on_progress("引导初始化", 100, "引导环境初始化完成")
            
            # ========== Stage 2: 加载内核 ==========
            self._update_stage(BootStage.KERNEL_LOAD)
            
            if not self._simulate_kernel_load():
                raise RuntimeError("内核加载失败")
            
            # ========== Stage 3: 校验内核 ==========
            self._update_stage(BootStage.KERNEL_VERIFY)
            
            if not self._verify_kernel():
                raise RuntimeError("内核校验失败: 内核映像损坏")
            
            # ========== Stage 4: 设置内存布局 ==========
            self._update_stage(BootStage.MEMORY_SETUP)
            
            memory_setup = self._setup_memory()
            
            # ========== Stage 5: 进入保护模式 ==========
            self._update_stage(BootStage.PROTECTED_MODE)
            
            if not self._enter_protected_mode():
                raise RuntimeError("进入保护模式失败")
            
            # ========== Stage 6: 启动内核 ==========
            self._update_stage(BootStage.KERNEL_START)
            
            if self.on_progress:
                self.on_progress("启动内核", 0, f"正在启动 {self.kernel_info['name']}...")
            
            time.sleep(0.3)
            
            if self.on_progress:
                self.on_progress("启动内核", 100, f"内核已加载到 0x{self.kernel_info['entry_point']:08X}")
            
            # 准备多引导信息
            self.multiboot_info = {
                "flags": 0x00000003,
                "mem_lower": 640,
                "mem_upper": sys_config.HARDWARE["memory"]["total_mb"] * 1024,
                "boot_device": 0xFFFFFF80,
                "cmdline": 0x00050000,
                "mods_count": 0,
                "mods_addr": 0,
                "mmap_length": len(self.memory_map) * 20,
                "mmap_addr": 0x00010000,
            }
            
            self._update_stage(BootStage.KERNEL_START)
            return True
            
        except Exception as e:
            self._update_stage(BootStage.BOOT_FAILED)
            error_msg = f"引导失败: {e}"
            if self.on_progress:
                self.on_progress("引导失败", 0, error_msg)
            return False

    def _print_boot_banner(self):
        """显示引导横幅"""
        banner = f"""
╔══════════════════════════════════════════╗
║          TianOS Bootloader              ║
║          Version {self.config.SYSTEM_VERSION:<8}         ║
║          {self.config.SYSTEM_BUILD}              ║
╚══════════════════════════════════════════╝
        """
        print(banner)

    def get_boot_info(self) -> Dict:
        """获取引导信息"""
        return {
            "stage": self.stage.value,
            "kernel": self.kernel_info,
            "memory_map": self.memory_map,
            "multiboot": self.multiboot_info,
            "cmdline": self.cmdline,
        }


class BootManager:
    """
    启动管理器
    协调 BIOS POST → Bootloader → Kernel 的完整启动流程
    """

    def __init__(self):
        self.bios = BIOS()
        self.bootloader = None
        self.boot_log: List[Dict] = []

    def add_log(self, message: str, level: str = "INFO"):
        """添加启动日志"""
        self.boot_log.append({
            "time": time.strftime("%H:%M:%S"),
            "level": level,
            "message": message
        })

    def run_boot_sequence(self, progress_callback: Optional[Callable] = None) -> bool:
        """
        运行完整的启动序列
        
        Args:
            progress_callback: 进度回调
            
        Returns:
            bool: 启动是否成功
        """
        self.add_log("TianOS 启动序列开始", "INFO")
        
        # ===== 阶段1: BIOS POST =====
        self.add_log("BIOS POST 开始...", "INFO")
        
        def post_callback(stage, progress, desc):
            self.add_log(f"POST {stage}: {desc}", "DEBUG")
            if progress_callback:
                progress_callback("POST", progress, desc)
        
        post_success = self.bios.post(post_callback)
        
        if not post_success:
            self.add_log("BIOS POST 失败!", "ERROR")
            return False
        
        self.add_log(f"BIOS POST 完成 - 检测到 {len(self.bios.detected_hardware)} 个设备", "INFO")
        
        # ===== 阶段2: 引导加载 =====
        self.add_log("引导加载程序启动...", "INFO")
        
        self.bootloader = Bootloader(self.bios)
        
        def boot_callback(stage, progress, desc):
            self.add_log(f"引导 {stage}: {desc}", "DEBUG")
            if progress_callback:
                progress_callback("BOOT", progress, desc)
        
        boot_success = self.bootloader.boot(boot_callback)
        
        if not boot_success:
            self.add_log("引导加载失败!", "ERROR")
            return False
        
        self.add_log(f"内核加载完成 - 入口: 0x{self.bootloader.kernel_info['entry_point']:08X}", "INFO")
        
        # ===== 准备启动内核 =====
        self.add_log("准备将控制权转交给内核...", "INFO")
        
        return True

    def get_boot_log(self) -> List[Dict]:
        """获取启动日志"""
        return self.boot_log