"""
TianOS 进程间通信 (IPC) 模块
消息队列、共享内存、信号量
"""

import time
import uuid
import threading
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import deque


class MessageType(Enum):
    """消息类型"""
    SYSTEM = 0x01        # 系统消息
    USER = 0x02          # 用户消息
    SIGNAL = 0x03        # 信号
    INTERRUPT = 0x04     # 中断
    IO_REQUEST = 0x05    # IO请求
    IO_RESPONSE = 0x06   # IO响应
    NETWORK = 0x07       # 网络消息
    GUI_EVENT = 0x08     # GUI事件


@dataclass
class Message:
    """IPC消息"""
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_pid: int = 0
    receiver_pid: int = 0
    msg_type: MessageType = MessageType.USER
    content: Any = None
    priority: int = 0
    timestamp: float = field(default_factory=time.time)
    response_to: Optional[str] = None


class MessageQueue:
    """
    消息队列
    支持进程间的异步通信
    """

    def __init__(self, max_size: int = 256):
        self.queue = deque(maxlen=max_size)
        self.max_size = max_size
        self.lock = threading.Lock()
        self.not_empty = threading.Condition(self.lock)
        self.not_full = threading.Condition(self.lock)

    def send(self, message: Message, block: bool = True, timeout: float = None) -> bool:
        """发送消息"""
        with self.not_full:
            if len(self.queue) >= self.max_size:
                if not block:
                    return False
                self.not_full.wait(timeout)
            self.queue.append(message)
            self.not_empty.notify()
            return True

    def receive(self, block: bool = True, timeout: float = None) -> Optional[Message]:
        """接收消息"""
        with self.not_empty:
            if len(self.queue) == 0:
                if not block:
                    return None
                self.not_empty.wait(timeout)
            if len(self.queue) == 0:
                return None
            message = self.queue.popleft()
            self.not_full.notify()
            return message

    def peek(self) -> Optional[Message]:
        """查看队列头部消息但不移除"""
        with self.lock:
            if self.queue:
                return self.queue[0]
            return None

    def clear(self):
        """清空队列"""
        with self.lock:
            self.queue.clear()
            self.not_full.notify_all()

    @property
    def size(self) -> int:
        return len(self.queue)


class SharedMemory:
    """
    共享内存区域
    允许进程间共享数据
    """

    def __init__(self, name: str, size_kb: int = 4):
        self.name = name
        self.size = size_kb * 1024
        self.data = bytearray(self.size)
        self.lock = threading.RLock()
        self.access_count = 0

    def read(self, offset: int = 0, size: int = None) -> bytes:
        """从共享内存读取数据"""
        with self.lock:
            if size is None:
                size = self.size - offset
            return bytes(self.data[offset:offset + size])

    def write(self, data: bytes, offset: int = 0):
        """写入数据到共享内存"""
        with self.lock:
            end = offset + len(data)
            if end > self.size:
                raise ValueError(f"数据超出共享内存大小 (最大 {self.size} 字节)")
            self.data[offset:end] = data

    def clear(self):
        """清空共享内存"""
        with self.lock:
            self.data = bytearray(self.size)


class Semaphore:
    """
    信号量
    用于进程同步
    """

    def __init__(self, initial: int = 1, max_count: int = 1):
        self.count = initial
        self.max_count = max_count
        self.lock = threading.Condition(threading.Lock())
        self.waiting_processes: List[int] = []

    def acquire(self, pid: int, timeout: float = None) -> bool:
        """获取信号量 (P操作)"""
        with self.lock:
            if self.count > 0:
                self.count -= 1
                return True
            self.waiting_processes.append(pid)
            return self.lock.wait(timeout)

    def release(self) -> bool:
        """释放信号量 (V操作)"""
        with self.lock:
            if self.count < self.max_count:
                self.count += 1
                if self.waiting_processes:
                    self.waiting_processes.pop(0)
                self.lock.notify()
                return True
            return False

    @property
    def value(self) -> int:
        return self.count


class IPCRegistry:
    """
    IPC注册表
    管理所有IPC资源 (消息队列、共享内存、信号量)
    """

    def __init__(self):
        self.message_queues: Dict[str, MessageQueue] = {}
        self.shared_memory: Dict[str, SharedMemory] = {}
        self.semaphores: Dict[str, Semaphore] = {}
        self.ports: Dict[int, MessageQueue] = {}  # 端口 -> 消息队列

    def create_queue(self, name: str, max_size: int = 256) -> MessageQueue:
        """创建消息队列"""
        if name not in self.message_queues:
            self.message_queues[name] = MessageQueue(max_size)
        return self.message_queues[name]

    def create_shared_memory(self, name: str, size_kb: int = 4) -> SharedMemory:
        """创建共享内存"""
        if name not in self.shared_memory:
            self.shared_memory[name] = SharedMemory(name, size_kb)
        return self.shared_memory[name]

    def create_semaphore(self, name: str, initial: int = 1) -> Semaphore:
        """创建信号量"""
        if name not in self.semaphores:
            self.semaphores[name] = Semaphore(initial)
        return self.semaphores[name]

    def register_port(self, port: int, queue: MessageQueue):
        """注册端口"""
        self.ports[port] = queue

    def send_to_port(self, port: int, message: Message) -> bool:
        """发送消息到端口"""
        if port in self.ports:
            return self.ports[port].send(message)
        return False

    def remove_queue(self, name: str):
        """删除消息队列"""
        self.message_queues.pop(name, None)

    def remove_shared_memory(self, name: str):
        """删除共享内存"""
        self.shared_memory.pop(name, None)

    def remove_semaphore(self, name: str):
        """删除信号量"""
        self.semaphores.pop(name, None)


# 全局IPC注册表
ipc_registry = IPCRegistry()