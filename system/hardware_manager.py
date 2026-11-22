"""
TianOS 全局硬件管理器
======================
系统唯一的硬件信息源。

- 系统启动时读取 data/active_hardware.json，确定当前使用的硬件。
- 动态加载 hardware/cpu/、hardware/gpu/、hardware/memory/（兼容 ram）下的 .py 文件，
  通过 AST 仅提取 HARDWARE_INFO 字典，绝不执行文件其余代码。
- 提供 get_cpu_info() / get_gpu_info() / get_ram_info() 等统一查询接口，
  供任务管理器、关于界面、沙箱等全系统调用。
- 加载完成后会把当前硬件配置同步回 sys_config.HARDWARE，
  使 BIOS 自检、内存管理器等底层组件一并受硬件限制约束。
"""

import os
import ast
import json
from typing import Dict, Optional, Any

from system.config import sys_config

# ---------------------------------------------------------------------------
# 路径与常量
# ---------------------------------------------------------------------------

ROOT_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".."))
HARDWARE_DIR = os.path.join(ROOT_DIR, "hardware")
DATA_DIR = os.path.join(ROOT_DIR, "data")
ACTIVE_HARDWARE_FILE = os.path.join(DATA_DIR, "active_hardware.json")

# 硬件类别 -> hardware/ 下目录名（兼容用户习惯的 ram 写法）
CATEGORY_DIRS = {
    "cpu": "cpu",
    "gpu": "gpu",
    "ram": "memory",
    "memory": "memory",
    "motherboard": "motherboard",
}


def _extract_hardware_info(file_path: str) -> Optional[Dict]:
    """通过 AST 安全提取文件中的 HARDWARE_INFO 字典（不执行文件代码）"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "HARDWARE_INFO":
                        info = ast.literal_eval(node.value)
                        return info if isinstance(info, dict) else None
    except Exception:
        return None
    return None


class HardwareManager:
    """全局硬件管理器（单例）。

    用法::

        from system.hardware_manager import hardware_manager
        cpu = hardware_manager.get_cpu_info()
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
            cls._instance._cache: Dict[str, dict] = {}
            cls._instance._active: Dict[str, str] = {}
        return cls._instance

    def __init__(self):
        if not self._loaded:
            self.reload()
            self._loaded = True

    # ---------- 加载 ----------

    def reload(self) -> None:
        """重新读取 active_hardware.json 并动态加载对应硬件文件。

        同时将当前硬件配置同步到 sys_config.HARDWARE，
        使 BIOS、内存管理器等底层组件自动跟随硬件配置。
        """
        self._active = self._read_active_config()
        self._cache = {}

        for category, dirname in CATEGORY_DIRS.items():
            device_id = self._active.get(category)
            if not device_id:
                continue
            file_path = os.path.join(HARDWARE_DIR, dirname, f"{device_id}.py")
            if not os.path.isfile(file_path):
                continue
            info = _extract_hardware_info(file_path)
            if info:
                info = dict(info)
                info.setdefault("id", device_id)
                info.setdefault("category", category)
                self._cache[category] = self._normalize(category, info)

        self._apply_to_sys_config()

    def _read_active_config(self) -> Dict[str, str]:
        """读取 data/active_hardware.json，返回 {类别: 硬件id}"""
        if not os.path.isfile(ACTIVE_HARDWARE_FILE):
            return {}
        try:
            with open(ACTIVE_HARDWARE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return {str(k).lower(): str(v) for k, v in data.items() if v}
        except Exception:
            return {}

    @staticmethod
    def _normalize(category: str, info: Dict) -> Dict:
        """把硬件文件字段归一化为系统通用字段。

        hardware 文件通常使用 memory_type/total_mb/name 等字段，
        sys_config.HARDWARE 则使用 type/type_total_mb/model 等；
        这里补齐兼容字段以便各类 UI 与子系统平滑使用。
        """
        info = dict(info)
        if category in ("ram", "memory"):
            info.setdefault("type", info.get("memory_type", "DDR5"))
        return info

    # ---------- 同步到底层配置 ----------

    def _apply_to_sys_config(self) -> None:
        """把当前硬件配置写回 sys_config.HARDWARE。

        - cpu / gpu / memory 字段由 active_hardware.json 决定；
        - 未配置的类别保持 sys_config 默认值；
        - storage / display / network 等非配置器管理字段不受影响。
        """
        cpu = self._cache.get("cpu")
        if cpu:
            sys_config.HARDWARE["cpu"] = {
                "model": cpu.get("name") or cpu.get("model", sys_config.HARDWARE["cpu"]["model"]),
                "cores": cpu.get("cores", sys_config.HARDWARE["cpu"]["cores"]),
                "threads": cpu.get("threads", cpu.get("cores", sys_config.HARDWARE["cpu"]["cores"])),
                "frequency_mhz": cpu.get("frequency_mhz", sys_config.HARDWARE["cpu"]["frequency_mhz"]),
                "features": cpu.get("features", sys_config.HARDWARE["cpu"]["features"]),
            }
            sys_config.HARDWARE["cpu"]["name"] = cpu.get("name", "")
            sys_config.HARDWARE["cpu"]["max_frequency_mhz"] = cpu.get("max_frequency_mhz", 0)
            sys_config.HARDWARE["cpu"]["tdp_w"] = cpu.get("tdp_w", 0)

        gpu = self._cache.get("gpu")
        if gpu:
            sys_config.HARDWARE["gpu"] = {
                "model": gpu.get("name") or gpu.get("model", sys_config.HARDWARE["gpu"]["model"]),
                "vram_mb": gpu.get("vram_mb", sys_config.HARDWARE["gpu"]["vram_mb"]),
                "cuda_cores": gpu.get("cuda_cores", sys_config.HARDWARE["gpu"]["cuda_cores"]),
                "core_clock_mhz": gpu.get("core_clock_mhz", sys_config.HARDWARE["gpu"]["core_clock_mhz"]),
                "memory_clock_mhz": gpu.get("memory_clock_mhz", sys_config.HARDWARE["gpu"]["memory_clock_mhz"]),
            }
            sys_config.HARDWARE["gpu"]["name"] = gpu.get("name", "")
            sys_config.HARDWARE["display"]["gpu_model"] = gpu.get("name") or gpu.get("model", "")

        mem = self._cache.get("ram") or self._cache.get("memory")
        if mem:
            sys_config.HARDWARE["memory"] = {
                "type": mem.get("memory_type", mem.get("type",
                              sys_config.HARDWARE["memory"]["type"])),
                "total_mb": mem.get("total_mb", sys_config.HARDWARE["memory"]["total_mb"]),
                "frequency_mhz": mem.get("frequency_mhz", 0),
                "modules": mem.get("modules", 1),
                "reserved_mb": sys_config.HARDWARE["memory"]["reserved_mb"],
                "kernel_heap_mb": sys_config.HARDWARE["memory"]["kernel_heap_mb"],
            }
            sys_config.HARDWARE["memory"]["name"] = mem.get("name", "")

        # 主板：作为独立类别缓存，不覆盖 sys_config 结构
        mobo = self._cache.get("motherboard")
        if mobo:
            sys_config.HARDWARE["motherboard"] = {
                "name": mobo.get("name", ""),
                "model": mobo.get("model", ""),
                "chipset": mobo.get("chipset", ""),
                "socket": mobo.get("socket", ""),
                "memory_types": mobo.get("memory_types", []),
                "form_factor": mobo.get("form_factor", ""),
            }

    # ---------- 查询接口 ----------

    def get_cpu_info(self) -> Dict[str, Any]:
        """返回当前 CPU 硬件信息"""
        if "cpu" in self._cache:
            return self._cache["cpu"]
        return dict(sys_config.HARDWARE.get("cpu", {}) or {})

    def get_gpu_info(self) -> Dict[str, Any]:
        """返回当前 GPU 硬件信息"""
        if "gpu" in self._cache:
            return self._cache["gpu"]
        return dict(sys_config.HARDWARE.get("gpu", {}) or {})

    def get_ram_info(self) -> Dict[str, Any]:
        """返回当前内存（RAM）硬件信息"""
        for key in ("ram", "memory"):
            if key in self._cache:
                return self._cache[key]
        return dict(sys_config.HARDWARE.get("memory", {}) or {})

    def get_memory_info(self) -> Dict[str, Any]:
        """返回当前内存硬件信息（与 get_ram_info 等价）"""
        return self.get_ram_info()

    def get_motherboard_info(self) -> Dict[str, Any]:
        """返回当前主板硬件信息；未配置时返回空字典"""
        return dict(self._cache.get("motherboard") or {})

    def get_limits(self) -> Dict[str, Any]:
        """返回当前硬件的物理资源上限（供沙箱/权限系统使用）。

        返回: {
            "cpu_threads": int,      # CPU 逻辑线程数
            "cpu_cores": int,        # CPU 物理核心数
            "ram_total_mb": int,     # 物理内存总容量 (MB)
            "ram_reserved_mb": int,  # 系统保留内存 (MB)
            "vram_total_mb": int,    # 显存总容量 (MB)
        }
        """
        cpu = self.get_cpu_info()
        ram = self.get_ram_info()
        gpu = self.get_gpu_info()
        return {
            "cpu_threads": int(cpu.get("threads") or cpu.get("cores") or 8),
            "cpu_cores": int(cpu.get("cores") or 8),
            "ram_total_mb": float(ram.get("total_mb") or 16384),
            "ram_reserved_mb": float(ram.get("reserved_mb") or 512),
            "vram_total_mb": float(gpu.get("vram_mb") or 0),
        }

    def get_all_info(self) -> Dict[str, Any]:
        """返回全部当前硬件信息（CPU/GPU/内存/主板）"""
        return {
            "cpu": self.get_cpu_info(),
            "gpu": self.get_gpu_info(),
            "ram": self.get_ram_info(),
            "memory": self.get_ram_info(),
            "motherboard": self.get_motherboard_info(),
        }

    def is_active_config_present(self) -> bool:
        """当前是否存在 data/active_hardware.json 配置"""
        return bool(self._active)


# 全局单例
hardware_manager = HardwareManager()