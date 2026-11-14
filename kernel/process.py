"""
TianOS 进程管理模块
进程调度、线程管理、上下文切换
"""

import time
import threading
import uuid
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field


class ProcessState(Enum):
    """进程状态"""
    NEW = "new"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    WAITING = "waiting"
    TERMINATED = "terminated"
    SUSPENDED = "suspended"


class Priority(Enum):
    """进程优先级"""
    IDLE = 0
    LOW = 1
    NORMAL = 2
    HIGH = 3
    REALTIME = 4


@dataclass
class ProcessContext:
    """进程上下文"""
    registers: Dict[str, int] = field(default_factory=dict)
    stack_pointer: int = 0
    program_counter: int = 0
    page_directory: int = 0


@dataclass
class Process:
    """进程控制块 (PCB)"""
    pid: int
    name: str
    state: ProcessState = ProcessState.NEW
    priority: Priority = Priority.NORMAL
    context: ProcessContext = field(default_factory=ProcessContext)
    
    # 资源
    memory_used_kb: int = 0
    cpu_time_ms: float = 0.0
    thread_count: int = 1
    
    # 调度
    arrival_time: float = 0.0
    burst_time: float = 0.0
    remaining_time: float = 0.0
    wait_time: float = 0.0
    
    # IPC
    message_queue: List[Dict] = field(default_factory=list)
    waiting_for: Optional[int] = None
    
    # 线程对象 (实际执行)
    thread: Optional[threading.Thread] = None
    thread_event: threading.Event = field(default_factory=threading.Event)
    
    # 元数据
    created_at: float = field(default_factory=time.time)
    user: str = "root"
    cmdline: str = ""


class Scheduler:
    """
    进程调度器
    实现多级反馈队列调度算法 (MLFQ)
    """

    def __init__(self):
        self.queues = {
            Priority.REALTIME: [],
            Priority.HIGH: [],
            Priority.NORMAL: [],
            Priority.LOW: [],
            Priority.IDLE: [],
        }
        self.current_process: Optional[Process] = None
        self.process_table: Dict[int, Process] = {}
        self.next_pid: int = 1
        self.quantum_ms = 20
        self.is_running = False
        self.scheduling_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # 统计
        self.total_switches = 0
        self.total_processes = 0

    def create_process(self, name: str, priority: Priority = Priority.NORMAL,
                       target: Optional[Callable] = None, args: tuple = ()) -> Process:
        """创建新进程"""
        with self.lock:
            pid = self.next_pid
            self.next_pid += 1
            
            proc = Process(
                pid=pid,
                name=name,
                priority=priority,
                state=ProcessState.NEW,
            )
            
            if target:
                proc.thread = threading.Thread(target=target, args=args, 
                                                name=f"proc-{pid}-{name}")
                proc.thread.daemon = True
            
            self.process_table[pid] = proc
            self.total_processes += 1
            
            # 加入就绪队列
            self._enqueue(proc)
            
            return proc

    def _enqueue(self, proc: Process):
        """将进程加入对应优先级的队列"""
        proc.state = ProcessState.READY
        self.queues[proc.priority].append(proc)

    def _dequeue(self, priority: Priority) -> Optional[Process]:
        """从指定优先级队列取出进程"""
        if self.queues[priority]:
            return self.queues[priority].pop(0)
        return None

    def schedule(self) -> Optional[Process]:
        """调度下一个运行的进程"""
        for priority in [Priority.REALTIME, Priority.HIGH, Priority.NORMAL, Priority.LOW, Priority.IDLE]:
            if self.queues[priority]:
                return self._dequeue(priority)
        return None

    def yield_cpu(self, pid: int):
        """主动让出CPU"""
        with self.lock:
            proc = self.process_table.get(pid)
            if proc and proc.state == ProcessState.RUNNING:
                proc.state = ProcessState.READY
                self._enqueue(proc)

    def block_process(self, pid: int):
        """阻塞进程"""
        with self.lock:
            proc = self.process_table.get(pid)
            if proc:
                proc.state = ProcessState.BLOCKED

    def unblock_process(self, pid: int):
        """解除阻塞"""
        with self.lock:
            proc = self.process_table.get(pid)
            if proc and proc.state == ProcessState.BLOCKED:
                proc.state = ProcessState.READY
                self._enqueue(proc)

    def terminate_process(self, pid: int):
        """终止进程"""
        with self.lock:
            proc = self.process_table.get(pid)
            if proc:
                proc.state = ProcessState.TERMINATED
                # 从队列中移除
                for queue in self.queues.values():
                    if proc in queue:
                        queue.remove(proc)

    def get_process(self, pid: int) -> Optional[Process]:
        """获取进程信息"""
        return self.process_table.get(pid)

    def list_processes(self) -> List[Process]:
        """列出所有进程"""
        return list(self.process_table.values())

    def get_stats(self) -> Dict:
        """获取调度统计"""
        return {
            "total_processes": self.total_processes,
            "total_switches": self.total_switches,
            "active_processes": len([p for p in self.process_table.values() 
                                      if p.state in [ProcessState.READY, ProcessState.RUNNING]]),
            "current_pid": self.current_process.pid if self.current_process else None,
        }


# 全局调度器
scheduler = Scheduler()