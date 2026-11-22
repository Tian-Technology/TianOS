"""
TianOS 系统配置文件
System Configuration for TianOS

系统全局配置参数，包含硬件信息、启动参数、网络配置等。
"""
# 硬件配置为模拟参数，名称仅供娱乐/学习用途，
# 与 AMD、NVIDIA 等公司无任何关联。
import json
import os
from typing import Dict, Any, Optional


# 设置持久化文件路径: TianOS/data/settings.json
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
SETTINGS_FILE = os.path.normpath(os.path.join(_DATA_DIR, "settings.json"))

# 系统元数据键：仅由代码定义（system/config.py），不参与持久化。
# settings.json 中的同名键在保存时会被排除、加载时会被跳过，
# 从而保证版本等系统信息始终以代码为准。
SYSTEM_META_KEYS = frozenset({
    "SYSTEM_NAME", "SYSTEM_VERSION", "SYSTEM_BUILD",
    "SYSTEM_ARCH", "SYSTEM_AUTHOR",
})


def _deep_update(target: dict, source: dict) -> None:
    """递归地将 source 中的键更新到 target（仅覆盖已存在的键）"""
    for k, v in source.items():
        if k in target and isinstance(target[k], dict) and isinstance(v, dict):
            _deep_update(target[k], v)
        else:
            target[k] = v


class SystemConfig:
    """系统全局配置"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 系统基本信息
        self.SYSTEM_NAME = "TianOS Constar"
        self.SYSTEM_VERSION = "tianos_constar_4.0.0_20261122_6sh2"
        self.SYSTEM_BUILD = "2026-11-22"
        self.SYSTEM_ARCH = "x86_64 (模拟)"
        self.SYSTEM_AUTHOR = "TianOS Team"

        # 硬件配置 (模拟)
        self.HARDWARE = {
            "cpu": {
                "model": "AMD 9950XtianOS",
                "cores": 16,
                "frequency_mhz": 5760,
                "features": ["sse2", "sse3", "ssse3", "sse4_1", "sse4_2", "avx", "avx2", "avx512f", "avx512bw"]
            },
            "gpu": {
                "model": "NVIDIA GeForce 5090 tianOS",
                "vram_mb": 32768,
                "cuda_cores": 21760,
                "core_clock_mhz": 2895,
                "memory_clock_mhz": 2400
            },
            "memory": {
                "type": "DDR5",
                "total_mb": 32768,
                "reserved_mb": 512,
                "kernel_heap_mb": 2048
            },
            "storage": {
                "disk_size_mb": 5120,
                "block_size": 512,
                "disk_label": "TianOS Disk"
            },
            "display": {
                "width": 2560,
                "height": 1440,
                "bpp": 32,
                "refresh_rate": 240,
                "gpu_model": "NVIDIA GeForce 5090 tianOS"
            },
            "network": {
                "nic_count": 1,
                "nic_model": "TianOS-VNIC",
                "mac_address": "00:1A:2B:3C:4D:5E",
                "default_gateway": "10.0.2.2",
                "dns_servers": ["8.8.8.8", "8.8.4.4"]
            }
        }

        # 启动配置
        self.BOOT = {
            "boot_device": "hda",
            "kernel_path": "/boot/kernel.bin",
            "initrd_path": "/boot/initrd.img",
            "boot_timeout_ms": 5000,
            "enable_verbose": True,
            "enable_efi": False,
            "boot_menu_delay": 3,
            "splash_time_s": 1.2
        }

        # 网络配置
        self.NETWORK = {
            "host_ip": "10.0.2.15",
            "netmask": "255.255.255.0",
            "gateway": "10.0.2.2",
            "dns_primary": "8.8.8.8",
            "dns_secondary": "8.8.4.4",
            "mtu": 1500,
            "tcp_window_size": 65535,
            "enable_dhcp": True
        }

        # GUI配置
        self.GUI = {
            "desktop_width": 1280,
            "desktop_height": 720,
            "theme": "TianOS-Default",
            "font_size": 14,
            "font_family": "Microsoft YaHei",
            "wallpaper_color": "#1a1a2e",
            "accent_color": "#00ccff",
            "enable_animations": True,
            "taskbar_height": 40,
            "dock_enabled": True,
            "transparency_effects": True,
        }

        # 声音配置
        self.SOUND = {
            "volume": 80,
            "muted": False,
            "device": "TianOS 模拟声卡",
        }

        # 个性化配置
        self.PERSONALIZATION = {
            "lock_screen_image": "",
            "start_menu_style": "centered",
            "show_task_labels": False,
        }

        # 账户配置
        self.ACCOUNTS = {
            "username": "user",
            "display_name": "用户",
            "account_type": "管理员",
            "home_dir": "/home/user",
        }

        # 时间和语言
        self.LOCALE = {
            "timezone": "中国标准时间 (UTC+8)",
            "language": "简体中文",
            "auto_set_time": True,
        }

        # 文件系统配置
        self.FS = {
            "root_device": "hda1",
            "mount_point": "/",
            "max_files": 4096,
            "max_file_size_mb": 100,
            "cache_size_mb": 64,
            "enable_journal": True
        }

        # 进程配置
        self.PROCESS = {
            "max_processes": 256,
            "max_threads_per_process": 64,
            "quantum_ms": 20,
            "stack_size_kb": 1024
        }

        # ------------------------------------------------------------------
        # 应用/游戏/辅助功能/隐私/更新 设置（由设置应用写入并持久化）
        # ------------------------------------------------------------------

        self.APPS = {
            "external_install": False,
            "auto_update": True,
            "show_recommendations": True,
            "show_notifications": True,
            "default_install_location": "C:\\Program Files\\TianOS",
            "show_recent_apps": True,
        }

        self.GAMING = {
            "game_mode": False,
            "prioritize_foreground_fps": False,
            "show_game_bar": True,
            "capture_in_background": False,
            "hdr": False,
        }

        self.ACCESSIBILITY = {
            "magnifier": False,
            "color_filters": "无",
            "high_contrast": False,
            "mono_audio": False,
            "visual_notifications": True,
            "sticky_keys": False,
            "text_size": 100,
        }

        self.PRIVACY = {
            "real_time_protection": True,
            "cloud_sample_submission": True,
            "location": True,
            "camera": True,
            "microphone": True,
            "diagnostics": "仅必需诊断数据",
            "advertising_id": False,
            "activity_history": True,
        }

        self.UPDATE = {
            "auto_update": True,
            "include_drivers": True,
            "preview_builds": False,
            "delivery_optimization": True,
            "download_bandwidth": 100,
            "last_check": "刚刚",
        }

        # 从本地文件加载已保存的设置（覆盖默认值）
        self._load_from_file()

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split(".")
        value = self.__dict__
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = getattr(value, k, None)
            if value is None:
                return default
        return value

    def set(self, key: str, value: Any, persist: bool = True):
        """设置配置项。persist=True 时立即写入本地文件。"""
        keys = key.split(".")
        target = self.__dict__
        for k in keys[:-1]:
            if isinstance(target, dict):
                target = target.setdefault(k, {})
            else:
                target = getattr(target, k, {})
        if isinstance(target, dict):
            target[keys[-1]] = value
        else:
            setattr(target, keys[-1], value)

        if persist:
            self._save_to_file()

    def to_dict(self) -> Dict[str, Any]:
        """导出配置为字典（系统元数据如版本不参与持久化）"""
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith("_") and key not in SYSTEM_META_KEYS:
                result[key] = value
        return result

    def to_json(self) -> str:
        """导出配置为JSON"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def save(self, path: str = None):
        """保存配置到文件（默认保存到 SETTINGS_FILE）"""
        path = path or SETTINGS_FILE
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.to_json())
        except Exception as e:
            print(f"[Config] 保存设置失败: {e}")

    def _save_to_file(self):
        """内部方法：保存到默认设置文件"""
        self.save(SETTINGS_FILE)

    def save_to_disk(self, path: str = None):
        """把当前所有配置立即写入本地 JSON 文件（默认写入 data/settings.json）。
        与 save() 等价，专门供设置应用在控件变更后显式调用，
        确保用户改完设置立刻落盘。
        """
        self.save(path or SETTINGS_FILE)

    def _load_from_file(self):
        """从默认设置文件加载配置，与默认值深度合并。

        系统元数据（版本等）始终以代码定义为准，不读取文件中的值。
        """
        path = SETTINGS_FILE
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[Config] 读取设置文件失败: {e}")
            return

        for key, value in data.items():
            if key in SYSTEM_META_KEYS:
                continue  # 版本等系统信息以 system/config.py 为准
            if not key.startswith("_") and hasattr(self, key):
                current = getattr(self, key)
                if isinstance(current, dict) and isinstance(value, dict):
                    _deep_update(current, value)
                else:
                    setattr(self, key, value)

    @classmethod
    def load(cls, path: str) -> "SystemConfig":
        """从文件加载配置（系统元数据如版本以代码定义为准）"""
        config = cls()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                if key in SYSTEM_META_KEYS:
                    continue
                if hasattr(config, key):
                    current = getattr(config, key)
                    if isinstance(current, dict) and isinstance(value, dict):
                        _deep_update(current, value)
                    else:
                        setattr(config, key, value)
        return config


# 全局单例
sys_config = SystemConfig()