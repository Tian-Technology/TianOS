"""
TianOS BIOS - 基本输入输出系统
================================
模拟PC开机自检(POST)、硬件检测和引导加载流程。

BIOS启动流程:
1. 上电自检 (POST) - 检测CPU、内存、基本硬件
2. 硬件初始化 - 枚举并初始化检测到的硬件
3. 启动设备选择 - 查找可引导设备
4. 引导加载 - 将引导扇区加载到内存并跳转执行
"""

import time
import struct
import threading
from typing import List, Dict, Optional, Callable
from enum import Enum

from system.config import sys_config


class POSTStatus(Enum):
    """POST状态码"""
    POWER_ON = 0x00        # 开机
    CPU_CHECK = 0x01       # CPU检测
    MEMORY_TEST = 0x02     # 内存测试
    DEVICE_ENUM = 0x03     # 设备枚举
    DEVICE_INIT = 0x04     # 设备初始化
    BOOT_SELECT = 0x05     # 启动选择
    BOOTING = 0x06         # 正在引导
    BOOT_COMPLETE = 0x07   # 引导完成
    ERROR = 0xFF           # 错误


class HardwareDevice(Enum):
    """硬件设备类型"""
    CPU = "cpu"
    MEMORY = "memory"
    DISPLAY = "display"
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    STORAGE = "storage"
    NETWORK = "network"
    AUDIO = "audio"
    USB = "usb"
    PCI = "pci"


class BIOS:
    """
    TianOS BIOS模拟器
    
    模拟真实BIOS的启动流程，包括:
    - 上电自检 (POST)
    - 硬件检测与初始化
    - 启动设备选择
    - 引导加载程序
    """

    def __init__(self):
        self.config = sys_config
        self.status = POSTStatus.POWER_ON
        self.status_history: List[POSTStatus] = []
        
        # 硬件清单
        self.detected_hardware: Dict[HardwareDevice, Dict] = {}
        
        # 引导设备列表
        self.boot_devices: List[Dict] = []
        
        # BIOS数据区
        self.bios_data = {
            "bios_version": f"TianOS BIOS v{self.config.SYSTEM_VERSION}",
            "bios_date": self.config.SYSTEM_BUILD,
            "bios_vendor": self.config.SYSTEM_AUTHOR,
            "system_name": self.config.SYSTEM_NAME,
        }
        
        # 中断向量表 (IVT) - 模拟
        self.interrupt_vector_table = {}
        
        # CMOS - 模拟CMOS存储
        self.cmos = {
            "boot_sequence": ["hda", "cdrom", "usb"],
            "boot_device": self.config.BOOT["boot_device"],
            "date_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "memory_test": True,
            "quick_boot": False,
        }
        
        # BIOS回调
        self.on_status_change: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # POST结果
        self.post_results = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "hardware_summary": {}
        }

    def set_status_callback(self, callback: Callable):
        """设置状态变化回调"""
        self.on_status_change = callback

    def set_error_callback(self, callback: Callable):
        """设置错误回调"""
        self.on_error = callback

    def _update_status(self, status: POSTStatus):
        """更新状态并触发回调"""
        self.status = status
        self.status_history.append(status)
        if self.on_status_change:
            self.on_status_change(status)

    def _beep(self, frequency: int = 800, duration_ms: int = 200):
        """模拟BIOS蜂鸣器（已禁用）"""
        pass  # 蜂鸣已关闭

    def _check_cpu(self) -> Dict:
        """
        CPU检测
        模拟: 检查CPU寄存器、特性、缓存等
        """
        cpu_info = self.config.HARDWARE["cpu"]
        
        # 模拟CPU检测步骤
        checks = {
            "registers": True,      # 寄存器测试
            "cache_l1": True,       # L1缓存测试
            "cache_l2": True,       # L2缓存测试
            "cache_l3": True,       # L3缓存测试
            "features": True,       # 特性检测
            "frequency": True,      # 频率检测
        }
        
        # 计算CPU评分 (模拟)
        cpu_score = sum(checks.values()) * 25
        
        return {
            "model": cpu_info["model"],
            "cores": cpu_info["cores"],
            "frequency_mhz": cpu_info["frequency_mhz"],
            "checks": checks,
            "score": cpu_score,
            "passed": all(checks.values())
        }

    def _test_memory(self, total_mb: int = None) -> Dict:
        """
        内存测试
        模拟: 检测内存大小、进行基本的内存读写测试
        """
        if total_mb is None:
            total_mb = sys_config.HARDWARE["memory"]["total_mb"]
        start_time = time.time()
        
        # 模拟测试延迟 (按比例)
        test_time = min(total_mb / 100.0, 3.0)  # 最多3秒
        
        # 模拟内存测试进度
        memory_regions = []
        for i in range(0, total_mb, 64):
            end = min(i + 64, total_mb)
            region = {
                "start": i,
                "end": end,
                "size_kb": (end - i) * 1024,
                "test_pattern": "0xAA55",
                "passed": True
            }
            memory_regions.append(region)
        
        # 模拟内存速度
        mem_type = self.config.HARDWARE["memory"].get("type", "DDR5")
        if mem_type == "DDR5":
            speed_mbps = 38400  # DDR5 速度
        else:
            speed_mbps = 3200
        
        return {
            "total_mb": total_mb,
            "available_mb": total_mb - self.config.HARDWARE["memory"]["reserved_mb"],
            "reserved_mb": self.config.HARDWARE["memory"]["reserved_mb"],
            "regions": memory_regions,
            "speed_mbps": speed_mbps,
            "test_time_s": test_time,
            "passed": True
        }

    def _enumerate_devices(self) -> Dict[HardwareDevice, Dict]:
        """
        设备枚举
        检测所有连接到系统的硬件设备
        """
        devices = {}
        
        # CPU
        cpu_info = self._check_cpu()
        devices[HardwareDevice.CPU] = {
            "name": "CPU",
            "model": cpu_info["model"],
            "status": "检测到",
            "details": cpu_info
        }
        
        # 内存
        mem_info = self._test_memory(self.config.HARDWARE["memory"]["total_mb"])
        devices[HardwareDevice.MEMORY] = {
            "name": "系统内存",
            "model": f"{self.config.HARDWARE['memory']['type']} 模拟内存",
            "status": "检测到",
            "details": mem_info
        }
        
        # 显示器
        display_config = self.config.HARDWARE["display"]
        devices[HardwareDevice.DISPLAY] = {
            "name": "显示适配器",
            "model": f"{self.config.HARDWARE['display']['gpu_model']}",
            "status": "检测到",
            "details": {
                "resolution": f"{display_config['width']}x{display_config['height']}",
                "bpp": display_config["bpp"],
                "refresh_rate": display_config["refresh_rate"]
            }
        }
        
        # 键盘
        devices[HardwareDevice.KEYBOARD] = {
            "name": "键盘",
            "model": "PS/2 标准键盘",
            "status": "检测到",
            "details": {"layout": "US", "type": "ps2"}
        }
        
        # 鼠标
        devices[HardwareDevice.MOUSE] = {
            "name": "鼠标",
            "model": "PS/2 兼容鼠标",
            "status": "检测到",
            "details": {"buttons": 3, "type": "ps2"}
        }
        
        # 存储设备
        storage_config = self.config.HARDWARE["storage"]
        devices[HardwareDevice.STORAGE] = {
            "name": "ATA 硬盘",
            "model": "TianOS Disk v1.0",
            "status": "检测到",
            "details": {
                "size_mb": storage_config["disk_size_mb"],
                "block_size": storage_config["block_size"],
                "label": storage_config["disk_label"]
            }
        }
        
        # 网卡
        net_config = self.config.HARDWARE["network"]
        devices[HardwareDevice.NETWORK] = {
            "name": "以太网控制器",
            "model": net_config["nic_model"],
            "status": "检测到",
            "details": {
                "mac": net_config["mac_address"],
                "count": net_config["nic_count"]
            }
        }
        
        return devices

    def _find_boot_devices(self) -> List[Dict]:
        """
        查找可引导设备
        模拟: 检查各存储设备是否有引导扇区
        """
        boot_devices = []
        
        # 检查硬盘
        boot_devices.append({
            "device": "hda",
            "type": "ATA 硬盘",
            "sector_size": 512,
            "bootable": True,
            "priority": 1,
            "description": "Primary ATA Hard Disk"
        })
        
        # 检查光驱 (模拟)
        boot_devices.append({
            "device": "cdrom",
            "type": "ATAPI 光驱",
            "sector_size": 2048,
            "bootable": False,
            "priority": 2,
            "description": "ATAPI CD-ROM"
        })
        
        # 网络引导 (PXE)
        boot_devices.append({
            "device": "pxe",
            "type": "网络引导",
            "sector_size": 512,
            "bootable": False,
            "priority": 3,
            "description": "Realtek PXE B02"
        })
        
        return boot_devices

    def post(self, progress_callback: Optional[Callable] = None) -> bool:
        """
        上电自检 (Power-On Self Test)
        执行完整的开机自检流程
        
        Args:
            progress_callback: 进度回调函数, 参数为 (阶段名, 进度百分比, 描述)
            
        Returns:
            bool: POST是否通过
        """
        self._update_status(POSTStatus.CPU_CHECK)
        
        try:
            # ========== 阶段1: CPU检测 ==========
            if progress_callback:
                progress_callback("CPU检测", 5, "正在检测处理器...")
            
            cpu_result = self._check_cpu()
            if not cpu_result["passed"]:
                raise RuntimeError(f"CPU检测失败: {cpu_result}")
            
            time.sleep(0.2)  # 模拟检测耗时
            
            # ========== 阶段2: 内存测试 ==========
            self._update_status(POSTStatus.MEMORY_TEST)
            
            total_mem = self.config.HARDWARE["memory"]["total_mb"]
            if progress_callback:
                progress_callback("内存测试", 15, f"正在测试 {total_mem}MB 内存...")
            
            memory_result = self._test_memory(total_mem)
            self.post_results["hardware_summary"]["memory"] = memory_result
            
            # 模拟内存测试进度动画
            for i in range(10, 91, 10):
                time.sleep(0.1)
                if progress_callback:
                    progress_callback("内存测试", i, f"内存测试中... {i}%")
            
            # ========== 阶段3: 设备枚举 ==========
            self._update_status(POSTStatus.DEVICE_ENUM)
            
            if progress_callback:
                progress_callback("设备枚举", 55, "正在枚举硬件设备...")
            
            self.detected_hardware = self._enumerate_devices()
            time.sleep(0.3)
            
            if progress_callback:
                progress_callback("设备枚举", 70, f"已检测 {len(self.detected_hardware)} 个设备")
            
            # ========== 阶段4: 设备初始化 ==========
            self._update_status(POSTStatus.DEVICE_INIT)
            
            if progress_callback:
                progress_callback("设备初始化", 75, "正在初始化设备驱动...")
            
            # 初始化存储
            time.sleep(0.2)
            
            # 初始化网络
            if progress_callback:
                progress_callback("设备初始化", 85, "正在初始化网络控制器...")
            time.sleep(0.2)
            
            if progress_callback:
                progress_callback("设备初始化", 90, "硬件初始化完成")
            
            # ========== 阶段5: 查找引导设备 ==========
            self._update_status(POSTStatus.BOOT_SELECT)
            
            if progress_callback:
                progress_callback("启动设备", 93, "正在查找可引导设备...")
            
            self.boot_devices = self._find_boot_devices()
            
            # 选择默认引导设备
            boot_device = None
            for dev in self.boot_devices:
                if dev["bootable"]:
                    boot_device = dev
                    break
            
            if boot_device is None:
                raise RuntimeError("未找到可引导设备!")
            
            if progress_callback:
                progress_callback("启动设备", 96, f"引导设备: {boot_device['description']}")
            
            # ========== POST完成 ==========
            self._update_status(POSTStatus.BOOT_COMPLETE)
            
            if progress_callback:
                progress_callback("POST完成", 100, "开机自检完成，准备引导系统...")
            
            # 蜂鸣提示
            self._beep(1000, 150)
            
            self.post_results["passed"] = True
            self._update_status(POSTStatus.BOOTING)
            
            return True
            
        except Exception as e:
            self.post_results["passed"] = False
            self.post_results["errors"].append(str(e))
            self._update_status(POSTStatus.ERROR)
            
            # 错误蜂鸣
            self._beep(400, 500)
            self._beep(200, 500)
            
            if self.on_error:
                self.on_error(str(e))
            
            return False

    def get_hardware_info(self) -> Dict:
        """获取检测到的硬件信息"""
        info = {}
        for device_type, device_info in self.detected_hardware.items():
            info[device_type.value] = {
                "name": device_info["name"],
                "model": device_info["model"],
                "status": device_info["status"],
                "details": device_info["details"]
            }
        return info

    def get_boot_sequence(self) -> List[str]:
        """获取启动顺序"""
        return self.cmos.get("boot_sequence", ["hda"])

    def reset_cmos(self):
        """重置CMOS设置"""
        self.cmos = {
            "boot_sequence": ["hda", "cdrom", "usb"],
            "boot_device": "hda",
            "date_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "memory_test": True,
            "quick_boot": False,
        }

    def get_status_summary(self) -> Dict:
        """获取POST状态摘要"""
        return {
            "status": self.status.value,
            "status_name": self.status.name,
            "passed": self.post_results["passed"],
            "error_count": len(self.post_results["errors"]),
            "warning_count": len(self.post_results["warnings"]),
            "device_count": len(self.detected_hardware),
            "boot_devices": len(self.boot_devices),
        }


class BIOSInterrupt:
    """
    BIOS中断服务
    模拟BIOS中断调用 (int 0x10, int 0x13, int 0x16等)
    """
    
    @staticmethod
    def int_10h(ah: int, al: int = 0, **registers) -> Dict:
        """
        INT 0x10 - 视频服务
        
        功能:
        - AH=0x00: 设置视频模式
        - AH=0x01: 设置光标形状
        - AH=0x02: 设置光标位置
        - AH=0x03: 获取光标信息
        - AH=0x06: 滚动屏幕
        - AH=0x09: 在光标处写入字符
        - AH=0x0E: TTY模式输出
        """
        if ah == 0x00:
            # 设置视频模式
            modes = {
                0x00: (320, 200, 4),    # CGA 320x200x4
                0x03: (640, 480, 4),    # VGA 640x480x16
                0x12: (640, 480, 8),    # VGA 640x480x256
                0x13: (320, 200, 8),    # VGA 320x200x256
            }
            mode = modes.get(al, modes[0x03])
            return {"width": mode[0], "height": mode[1], "bpp": mode[2], "mode": al}
        
        elif ah == 0x0E:
            # TTY输出
            char = chr(al)
            return {"char": char, "teletype": True}
        
        return {}

    @staticmethod
    def int_13h(ah: int, **registers) -> Dict:
        """
        INT 0x13 - 磁盘服务
        
        功能:
        - AH=0x00: 重置磁盘系统
        - AH=0x02: 读扇区
        - AH=0x03: 写扇区
        - AH=0x08: 获取驱动器参数
        """
        if ah == 0x02:
            # 读扇区
            return {
                "sectors_read": registers.get("al", 1),
                "cylinder": registers.get("ch", 0),
                "sector": registers.get("cl", 1),
                "head": registers.get("dh", 0),
                "drive": registers.get("dl", 0x80),
            }
        return {}

    @staticmethod
    def int_16h(ah: int, **registers) -> Dict:
        """
        INT 0x16 - 键盘服务
        
        功能:
        - AH=0x00: 读键盘输入
        - AH=0x01: 检查键盘缓冲区
        """
        if ah == 0x00:
            return {"key_code": 0, "ascii": 0}
        return {}