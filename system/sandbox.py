"""
TianOS 应用沙箱（硬件限制）
==========================
在启动任何新应用之前检查当前系统的模拟硬件负载。

- 应用声明所需的线程数/内存配额；
- 若申请的资源超过当前 CPU/RAM 的物理上限，抛出 HardwareOverloadError；
- 上层捕获后在 boot/bsod.py 中触发蓝屏（HARDWARE_LIMIT_EXCEEDED）。
"""

from typing import Dict, Optional, Tuple

from system.hardware_manager import hardware_manager


class HardwareOverloadError(RuntimeError):
    """硬件过载：应用申请的资源超过了当前硬件的物理上限。

    属性:
        resource: 被限制的资源名称（cpu / ram / vram）
        requested: 应用申请的数量
        available: 当前系统可用数量
    """

    def __init__(
        self,
        resource: str,
        requested: object,
        available: object,
        message: Optional[str] = None,
    ):
        self.resource = resource
        self.requested = requested
        self.available = available
        if message is None:
            message = (
                f"硬件资源不足：{resource} 申请 {requested}，"
                f"当前系统仅支持 {available}"
            )
        super().__init__(message)


# ---------------------------------------------------------------------------
# 应用资源需求表（模拟）
#
# 每个应用声明它启动所需的线程数与内存配额（内存单位为 MB）。
# 未登记的应用使用默认值。
# ---------------------------------------------------------------------------

# 按应用模块名映射资源需求
_APP_RESOURCE_REQUIREMENTS: Dict[str, Dict[str, object]] = {
    # 重量级应用：申请大量线程与内存
    "browser": {"threads": 8, "memory_mb": 4096, "vram_mb": 0},
    "downloader": {"threads": 4, "memory_mb": 2048, "vram_mb": 0},
    "game": {"threads": 16, "memory_mb": 8192, "vram_mb": 4096},
    # 中型应用
    "terminal": {"threads": 4, "memory_mb": 1024, "vram_mb": 0},
    "this_pc": {"threads": 4, "memory_mb": 1024, "vram_mb": 0},
    "file_manager": {"threads": 4, "memory_mb": 1024, "vram_mb": 0},
    # 开发类应用
    "app_store": {"threads": 2, "memory_mb": 1536, "vram_mb": 0},
    "settings": {"threads": 2, "memory_mb": 1024, "vram_mb": 0},
}

# 未登记应用的默认资源需求
_DEFAULT_REQUIREMENTS: Dict[str, object] = {
    "threads": 2,
    "memory_mb": 512,
    "vram_mb": 0,
}

# 当前系统常驻基础负载：内核/桌面等已占用的模拟资源
_SYSTEM_BASE_LOAD = {
    "threads": 4,      # 系统核心进程占用的线程数
    "memory_mb": 768,  # 系统常驻内存（MB）
    "vram_mb": 512,    # 桌面合成器占用的显存（MB）
}


def _resource_label(resource: str) -> str:
    """返回资源的中文说明"""
    return {
        "cpu": "CPU 线程",
        "ram": "内存",
        "vram": "显存",
    }.get(resource, resource)


def _format_requested(requested) -> str:
    """格式化申请量，内存/显存自动换算为 GB 展示"""
    try:
        mb = float(requested)
        if mb >= 1024:
            gb = mb / 1024
            return f"{mb:.0f}MB（约 {gb:g}GB）" if gb % 1 else f"{mb:.0f}MB（{gb:.0f}GB）"
        return f"{mb:.0f}MB"
    except (TypeError, ValueError):
        return str(requested)


def _format_available(resource: str, available) -> str:
    """格式化可用量"""
    if resource in ("ram", "vram"):
        try:
            mb = float(available)
            if mb >= 1024:
                gb = mb / 1024
                return f"{gb:g}GB" if gb % 1 else f"{gb:.0f}GB"
            return f"{mb:.0f}MB"
        except (TypeError, ValueError):
            pass
    return str(available)


def get_application_requirements(app_name: str) -> Dict[str, object]:
    """返回应用远端声明的资源需求（默认兜底 2 线程 / 512MB）"""
    if not app_name:
        return dict(_DEFAULT_REQUIREMENTS)
    try:
        base = _APP_RESOURCE_REQUIREMENTS.get(app_name)
        if base is None:
            return dict(_DEFAULT_REQUIREMENTS)
        return dict(base)
    except Exception:
        return dict(_DEFAULT_REQUIREMENTS)


def check_application_resources(
    app_name: str,
    requested_threads: Optional[int] = None,
    requested_memory_mb: Optional[int] = None,
    requested_vram_mb: Optional[int] = None,
) -> Tuple[Dict[str, object], bool]:
    """检查应用能否在当前硬件限制内启动。

    参数:
        app_name: 应用模块名
        requested_threads / memory_mb / vram_mb: 覆盖应用需求表的声明值

    返回:
        (需求表, bool) —— (需求, 是否通过检查)

    若检查未通过，抛出 HardwareOverloadError。
    """
    req = get_application_requirements(app_name)
    threads = requested_threads if requested_threads is not None else req.get("threads", 2)
    mem_mb = requested_memory_mb if requested_memory_mb is not None else req.get("memory_mb", 512)
    vram_mb = requested_vram_mb if requested_vram_mb is not None else req.get("vram_mb", 0)

    limits = hardware_manager.get_limits()
    load = dict(_SYSTEM_BASE_LOAD)

    # ---------------- CPU 线程检查 ----------------
    avail_threads = int(limits["cpu_threads"]) - int(load["threads"])
    if int(threads) > 0 and int(threads) > avail_threads:
        raise HardwareOverloadError(
            "cpu",
            f"{threads} 个线程",
            f"{max(avail_threads, 0)} 个线程（当前硬件仅 {limits['cpu_threads']:.0f} 线程）",
            message=(
                f"CPU 线程数超出限制：{app_name or '应用'} 申请 {threads} 个线程，"
                f"当前硬件仅支持 {limits['cpu_threads']:.0f} 线程"
                f"（系统基础负载已占用 {load['threads']} 个）"
            ),
        )

    # ---------------- 内存检查 ----------------
    usable_mb = limits["ram_total_mb"] - limits["ram_reserved_mb"] - load["memory_mb"]
    if int(mem_mb) > 0 and int(mem_mb) > usable_mb:
        avail_gb = _format_available("ram", usable_mb)
        raise HardwareOverloadError(
            "ram",
            f"{_format_requested(mem_mb)}",
            f"{avail_gb}",
            message=(
                f"内存溢出：{app_name or '应用'} 申请 {_format_requested(mem_mb)} 内存，"
                f"当前配置仅支持 {_format_available('ram', limits['ram_total_mb'])}"
                f"（系统保留 {limits['ram_reserved_mb']:.0f}MB + 基础负载 {load['memory_mb']:.0f}MB）"
            ),
        )

    # ---------------- 显存检查 ----------------
    if int(vram_mb) > 0 and limits["vram_total_mb"] > 0:
        avail_vram = limits["vram_total_mb"] - load["vram_mb"]
        if int(vram_mb) > avail_vram:
            raise HardwareOverloadError(
                "vram",
                f"{_format_requested(vram_mb)}",
                f"{_format_available('vram', avail_vram)}",
                message=(
                    f"显存溢出：{app_name or '应用'} 申请 {_format_requested(vram_mb)} 显存，"
                    f"当前显卡仅支持 {_format_available('vram', limits['vram_total_mb'])}"
                ),
            )

    return req, True


def assert_application_resources(
    app_name: str,
    requested_threads: Optional[int] = None,
    requested_memory_mb: Optional[int] = None,
) -> None:
    """启动应用前的硬性检查。资源超限时抛出 HardwareOverloadError。

    上层捕获 HardwareOverloadError 后应调用 boot.bsod.handle_crash() 触发蓝屏。
    """
    check_application_resources(
        app_name,
        requested_threads=requested_threads,
        requested_memory_mb=requested_memory_mb,
    )