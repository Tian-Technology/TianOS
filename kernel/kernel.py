"""
TianOS 微内核核心
===================
微内核架构，提供最小化的核心服务:
- 进程管理 (通过 process.py)
- 进程间通信 (通过 ipc.py)
- 内存管理 (通过 memory.py)
- 系统调用处理
- 设备驱动管理

微内核设计原则:
1. 内核只提供最小化服务
2. 文件系统、网络协议栈、设备驱动都在用户态运行
3. 通过IPC进行服务间通信
4. 高度模块化
"""

import time
import sys
import os
from typing import Dict, List, Optional, Callable, Any
from enum import Enum, IntEnum

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from system.config import sys_config
from kernel.process import scheduler, Process, ProcessState, Priority
from kernel.ipc import ipc_registry, Message, MessageType, MessageQueue
from kernel.memory import memory_manager


class SysCall(IntEnum):
    """系统调用号"""
    EXIT = 0x01
    FORK = 0x02
    EXEC = 0x03
    WAIT = 0x04
    GET_PID = 0x05
    
    # IPC
    SEND_MSG = 0x10
    RECV_MSG = 0x11
    SHARED_MEM = 0x12
    SEMAPHORE = 0x13
    
    # 内存
    ALLOC_MEM = 0x20
    FREE_MEM = 0x21
    MAP_PAGE = 0x22
    
    # IO
    READ = 0x30
    WRITE = 0x31
    OPEN = 0x32
    CLOSE = 0x33
    
    # 网络
    NET_SOCKET = 0x40
    NET_BIND = 0x41
    NET_LISTEN = 0x42
    NET_ACCEPT = 0x43
    NET_CONNECT = 0x44
    NET_SEND = 0x45
    NET_RECV = 0x46
    
    # 系统
    SHUTDOWN = 0xFF


class KernelService(Enum):
    """内核服务类型"""
    PROCESS_MGR = "process_manager"
    MEMORY_MGR = "memory_manager"
    IPC_MGR = "ipc_manager"
    DRIVER_MGR = "driver_manager"
    FS_MGR = "filesystem_manager"
    NET_MGR = "network_manager"
    GUI_MGR = "gui_manager"


class Kernel:
    """
    TianOS 微内核
    
    内核启动后:
    1. 初始化核心子系统
    2. 启动系统服务进程
    3. 启动GUI (如果配置)
    4. 进入空闲循环
    """

    def __init__(self):
        self.config = sys_config
        self.name = "TianOS Microkernel"
        self.version = self.config.SYSTEM_VERSION
        
        # 内核状态
        self.is_running = False
        self.start_time = 0.0
        self.uptime_seconds = 0.0
        
        # 内核服务
        self.services: Dict[KernelService, Dict] = {
            KernelService.PROCESS_MGR: {"status": "stopped", "pid": 0},
            KernelService.MEMORY_MGR: {"status": "stopped", "pid": 0},
            KernelService.IPC_MGR: {"status": "stopped", "pid": 0},
            KernelService.DRIVER_MGR: {"status": "stopped", "pid": 0},
            KernelService.FS_MGR: {"status": "stopped", "pid": 0},
            KernelService.NET_MGR: {"status": "stopped", "pid": 0},
            KernelService.GUI_MGR: {"status": "stopped", "pid": 0},
        }
        
        # 系统调用表
        self.syscall_table: Dict[int, Callable] = {}
        
        # 中断处理
        self.interrupt_handlers: Dict[int, Callable] = {}
        
        # 内核日志
        self.kernel_log: List[Dict] = []
        
        # 回调
        self.on_kernel_log: Optional[Callable] = None
        self.on_kernel_ready: Optional[Callable] = None

    def log(self, message: str, level: str = "INFO"):
        """添加内核日志"""
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "level": level,
            "message": f"[KERNEL] {message}"
        }
        self.kernel_log.append(entry)
        print(f"[{entry['time']}] {entry['level']}: {entry['message']}")
        if self.on_kernel_log:
            self.on_kernel_log(entry)

    def _init_syscalls(self):
        """初始化系统调用表"""
        self.syscall_table = {
            SysCall.EXIT: self._sys_exit,
            SysCall.GET_PID: self._sys_get_pid,
            SysCall.ALLOC_MEM: self._sys_alloc_mem,
            SysCall.FREE_MEM: self._sys_free_mem,
            SysCall.SEND_MSG: self._sys_send_message,
            SysCall.RECV_MSG: self._sys_recv_message,
            SysCall.SHUTDOWN: self._sys_shutdown,
        }
        self.log("系统调用表初始化完成", "INFO")

    def _sys_exit(self, pid: int, code: int = 0):
        """系统调用: 退出进程"""
        scheduler.terminate_process(pid)
        self.log(f"进程 {pid} 退出 (code={code})", "INFO")

    def _sys_get_pid(self, pid: int) -> int:
        """系统调用: 获取进程ID"""
        return pid

    def _sys_alloc_mem(self, pid: int, size: int) -> List[int]:
        """系统调用: 分配内存"""
        try:
            frames = memory_manager.allocate_frames(size, pid)
            self.log(f"进程 {pid} 分配 {size} 字节内存 ({len(frames)} 帧)", "DEBUG")
            return frames
        except MemoryError as e:
            self.log(f"内存分配失败 (pid={pid}): {e}", "ERROR")
            return []

    def _sys_free_mem(self, pid: int, frames: List[int]):
        """系统调用: 释放内存"""
        memory_manager.free_frames(frames)
        self.log(f"进程 {pid} 释放 {len(frames)} 帧", "DEBUG")

    def _sys_send_message(self, sender_pid: int, receiver_pid: int, content: Any) -> bool:
        """系统调用: 发送消息"""
        msg = Message(
            sender_pid=sender_pid,
            receiver_pid=receiver_pid,
            content=content
        )
        return ipc_registry.send_to_port(receiver_pid, msg)

    def _sys_recv_message(self, pid: int) -> Optional[Message]:
        """系统调用: 接收消息"""
        if pid in ipc_registry.ports:
            return ipc_registry.ports[pid].receive(block=False)
        return None

    def _sys_shutdown(self, pid: int, reason: str = ""):
        """系统调用: 关机"""
        self.log(f"收到关机请求 (from pid={pid}): {reason}", "WARN")
        self.is_running = False

    def handle_syscall(self, syscall_number: int, pid: int, *args, **kwargs) -> Any:
        """处理系统调用"""
        if syscall_number in self.syscall_table:
            return self.syscall_table[syscall_number](pid, *args, **kwargs)
        else:
            self.log(f"未知系统调用: {syscall_number:#04x} (pid={pid})", "WARN")
            return None

    def _init_services(self):
        """初始化内核服务"""
        self.log("正在初始化内核服务...", "INFO")
        
        # 进程管理器
        self.services[KernelService.PROCESS_MGR] = {
            "status": "running",
            "pid": 1,
            "description": "进程管理服务"
        }
        self.log("进程管理器已启动", "INFO")
        
        # 内存管理器
        mem_stats = memory_manager.get_memory_stats()
        self.services[KernelService.MEMORY_MGR] = {
            "status": "running",
            "pid": 2,
            "description": "内存管理服务",
            "stats": mem_stats
        }
        self.log(f"内存管理器已启动 (总计 {mem_stats['total_mb']:.0f}MB)", "INFO")
        
        # IPC管理器
        self.services[KernelService.IPC_MGR] = {
            "status": "running",
            "pid": 3,
            "description": "IPC管理服务"
        }
        self.log("IPC管理器已启动", "INFO")
        
        # 设备驱动管理器
        self.services[KernelService.DRIVER_MGR] = {
            "status": "running",
            "pid": 4,
            "description": "设备驱动管理服务"
        }
        self.log("设备驱动管理器已启动", "INFO")
        
        # 文件系统管理器
        self.services[KernelService.FS_MGR] = {
            "status": "running",
            "pid": 5,
            "description": "文件系统服务"
        }
        self.log("文件系统服务已启动", "INFO")
        
        # 网络管理器
        self.services[KernelService.NET_MGR] = {
            "status": "running",
            "pid": 6,
            "description": "网络协议栈服务"
        }
        self.log("网络协议栈服务已启动", "INFO")
        
        # GUI管理器
        self.services[KernelService.GUI_MGR] = {
            "status": "pending",
            "pid": 7,
            "description": "GUI桌面环境"
        }
        self.log("GUI管理器等待启动", "INFO")

    def _start_idle_process(self):
        """启动空闲进程"""
        def idle_task():
            while self.is_running:
                time.sleep(0.1)
                self.uptime_seconds = time.time() - self.start_time
        
        idle_proc = scheduler.create_process("idle", Priority.IDLE, idle_task)
        self.log(f"空闲进程已创建 (pid={idle_proc.pid})", "INFO")

    def start(self) -> bool:
        """
        启动内核
        
        Returns:
            bool: 启动是否成功
        """
        self.log("=" * 50, "INFO")
        self.log(f"{self.name} v{self.version} 启动中...", "INFO")
        self.log(f"架构: {self.config.SYSTEM_ARCH}", "INFO")
        self.log("=" * 50, "INFO")
        
        self.start_time = time.time()
        
        try:
            # 1. 初始化系统调用
            self._init_syscalls()
            
            # 2. 初始化服务
            self._init_services()
            
            # 3. 启动空闲进程
            self._start_idle_process()
            
            # 4. 设置内核状态
            self.is_running = True
            
            self.log(f"内核启动完成 (用时 {time.time() - self.start_time:.2f}s)", "INFO")
            self.log(f"系统就绪, 准备启动用户环境...", "INFO")
            
            if self.on_kernel_ready:
                self.on_kernel_ready()
            
            return True
            
        except Exception as e:
            self.log(f"内核启动失败: {e}", "ERROR")
            self.is_running = False
            return False

    def shutdown(self):
        """关闭内核"""
        self.log("正在关闭内核...", "WARN")
        self.is_running = False
        
        # 终止所有进程
        for proc in scheduler.list_processes():
            if proc.pid != 0:  # 保留空闲进程
                scheduler.terminate_process(proc.pid)
        
        self.log(f"内核关闭完成 (运行时间: {self.uptime_seconds:.2f}s)", "INFO")

    def get_info(self) -> Dict:
        """获取内核信息"""
        return {
            "name": self.name,
            "version": self.version,
            "uptime": self.uptime_seconds,
            "is_running": self.is_running,
            "services": {k.value: v["status"] for k, v in self.services.items()},
            "process_count": len(scheduler.list_processes()),
            "memory": memory_manager.get_memory_stats(),
        }


# 全局内核实例
kernel = Kernel()