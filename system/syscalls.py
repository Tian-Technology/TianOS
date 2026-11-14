"""
TianOS 系统调用接口
为用户态程序提供内核服务访问接口
"""

from typing import Any, Optional, List, Dict
from enum import IntEnum

from kernel.kernel import kernel
from kernel.process import scheduler, Process, ProcessState, Priority
from kernel.ipc import ipc_registry, Message, MessageType
from kernel.memory import memory_manager


class SyscallNumber(IntEnum):
    """系统调用号"""
    EXIT = 1
    GET_PID = 2
    GET_PPID = 3
    ALLOC_MEM = 4
    FREE_MEM = 5
    SEND_MSG = 6
    RECV_MSG = 7
    GET_TIME = 8
    LOG = 9
    GET_INFO = 10
    SHUTDOWN = 255


def syscall(number: int, *args, **kwargs) -> Any:
    """
    通用系统调用接口
    
    Args:
        number: 系统调用号
        args: 参数
        kwargs: 关键字参数
        
    Returns:
        系统调用结果
    """
    return kernel.handle_syscall(number, 0, *args, **kwargs)


def sys_getpid() -> int:
    """获取当前进程ID"""
    return SyscallNumber.GET_PID


def sys_alloc_mem(size: int) -> List[int]:
    """分配内存"""
    return memory_manager.allocate_frames(size, 0)


def sys_free_mem(frames: List[int]):
    """释放内存"""
    memory_manager.free_frames(frames)


def sys_send_message(receiver_pid: int, content: Any) -> bool:
    """发送消息"""
    msg = Message(sender_pid=0, receiver_pid=receiver_pid, content=content)
    return ipc_registry.send_to_port(receiver_pid, msg)


def sys_recv_message() -> Optional[Message]:
    """接收消息"""
    return ipc_registry.ports.get(0, None).receive(block=False) if 0 in ipc_registry.ports else None


def sys_get_time() -> float:
    """获取系统时间"""
    import time
    return time.time()


def sys_log(message: str, level: str = "INFO"):
    """记录系统日志"""
    kernel.log(message, level)


def sys_get_info() -> Dict:
    """获取系统信息"""
    return kernel.get_info()


def sys_shutdown(reason: str = ""):
    """关闭系统"""
    kernel.shutdown()


# 导出所有系统调用接口
__all__ = [
    'syscall', 'sys_getpid', 'sys_alloc_mem', 'sys_free_mem',
    'sys_send_message', 'sys_recv_message', 'sys_get_time',
    'sys_log', 'sys_get_info', 'sys_shutdown',
    'SyscallNumber',
]