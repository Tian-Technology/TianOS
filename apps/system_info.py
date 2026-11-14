"""
TianOS 系统信息
"""

APP_NAME = "系统信息"
APP_ICON = "ℹ"
APP_ICON_FILE = "imageres 077.png"
APP_COLOR = "#ff66cc"

import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from system.config import sys_config


class SystemInfo(QWidget):
    """系统信息面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统信息")
        self.setMinimumSize(500, 400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel(f"{sys_config.SYSTEM_NAME} 系统信息")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ccff;")
        layout.addWidget(title)

        hw = sys_config.HARDWARE
        gpu = hw.get("gpu", {})
        gpu_name = gpu.get("model", "无")
        mem_type = hw["memory"].get("type", "DDR5")
        info_lines = [
            ("操作系统", f"{sys_config.SYSTEM_NAME}"),
            ("系统版本", sys_config.SYSTEM_VERSION),
            ("构建日期", sys_config.SYSTEM_BUILD),
            ("内核", "TianOS 微内核"),
            ("架构", "x86_64 (模拟)"),
            ("处理器", f"{hw['cpu']['model']}  {hw['cpu']['cores']}核  {hw['cpu']['frequency_mhz']}MHz"),
            ("内存", f"{mem_type}  {hw['memory']['total_mb']}MB ({hw['memory']['total_mb']//1024}GB)"),
            ("显卡", gpu_name),
            ("存储设备", f"{hw['storage']['disk_label']}  {hw['storage']['disk_size_mb']}MB"),
            ("显示器", f"{hw['display']['width']}x{hw['display']['height']}  {hw['display']['refresh_rate']}Hz"),
            ("网络协议栈", "TCP/IP v4"),
            ("桌面环境", "TianOS Desktop"),
            ("Python", sys.version.split()[0]),
            ("PyQt", "6"),
        ]

        for k, v in info_lines:
            row = QLabel(
                f"<b style='color:#8888ff; font-size:13px;'>{k}:</b>  "
                f"<span style='color:#cccccc; font-size:13px;'>{v}</span>"
            )
            row.setFont(QFont("Consolas", 11))
            layout.addWidget(row)

        layout.addStretch()