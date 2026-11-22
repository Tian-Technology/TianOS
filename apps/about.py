"""
TianOS 关于
"""

APP_NAME = "关于"
APP_ICON = "©"
APP_ICON_FILE = "imageres 095.png"
APP_COLOR = "#ffffff"

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from system.config import sys_config

# 更新日志内容（新版本在上，按时间倒序）
CHANGELOG = """\
【2026-11-22】版本 3.2.5
  · 新增：硬件配置器（扫描硬件/目录、兼容性检测、保存配置）
  · 新增：组策略编辑器支持策略勾选与注册表写入
  · 优化：系统设置修改后实时写入本地配置文件

【2026-10-25】版本 3.1.0
  · 修复：右键删除桌面文件夹导致系统崩溃的 BUG
  · 关于窗口新增「更新日志」标签页
  · 浏览器改进 HTML5 视频播放兼容性

【2026-09-28】版本 3.0.3
  · 新增：任务管理器实时监控资源占用
  · 优化：开机启动流程与安全模式
  · 修复：若干界面交互细节问题

【2026-09-15】版本 3.0.2
  · 新增：Tian浏览器（内置 Chromium 内核）
  · 新增：HTML5 多媒体播放器
  · 工具箱新增网络工具

【2026-08-30】版本 3.0.1
  · 新增：桌面右键菜单（复制/剪切/重命名/删除）
  · 新增：运行对话框 winver 快捷入口
  · 优化：深色主题界面细节

【2026-08-10】版本 3.0.0 (首个正式版)
  · 构建完整微内核模拟：启动流程、系统服务
  · 实现 TCP/IP 网络协议栈
  · 打造图形桌面环境与系统设置
"""


class _InfoTab(QWidget):
    """「关于」标签页：标题、版本、简介与版权"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        title = QLabel(sys_config.SYSTEM_NAME)
        title.setFont(QFont("Consolas", 40, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ccff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        ver = QLabel(f"版本 {sys_config.SYSTEM_VERSION}")
        ver.setFont(QFont("Microsoft YaHei", 14))
        ver.setStyleSheet("color: #888899;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver)

        build = QLabel(f"构建 {sys_config.SYSTEM_BUILD}")
        build.setFont(QFont("Microsoft YaHei", 10))
        build.setStyleSheet("color: #666688;")
        build.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(build)

        desc = QLabel(
            "TianOS 是一个用 Python + PyQt6 构建的\n"
            "微内核操作系统模拟器\n\n"
            "包含完整的系统启动流程、内核模拟、\n"
            "TCP/IP 网络协议栈和图形桌面环境"
        )
        desc.setFont(QFont("Microsoft YaHei", 11))
        desc.setStyleSheet("color: #aaaaaa;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        copyright_label = QLabel("© 2026 TianOS 项目")
        copyright_label.setFont(QFont("Microsoft YaHei", 9))
        copyright_label.setStyleSheet("color: #666688;")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(copyright_label)

        layout.addStretch()


class _ChangelogTab(QWidget):
    """「更新日志」标签页：展示版本更新记录"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText(CHANGELOG.strip() + "\n")
        self.text.setFont(QFont("Consolas", 10))
        self.text.setStyleSheet("""
            QTextEdit {
                background-color: #171c2c;
                color: #b7c4e0;
                border: 1px solid #2a3550;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.text)


class About(QWidget):
    """关于 TianOS"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"关于 {sys_config.SYSTEM_NAME}")
        self.setMinimumSize(500, 420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #2a3550;
                border-radius: 6px;
                background-color: #131624;
                top: -1px;
            }
            QTabBar::tab {
                background: #171c2c;
                color: #8899bb;
                border: 1px solid #2a3550;
                padding: 7px 22px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #00ccff;
                color: #06121f;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background: #1f2640;
                color: #00ccff;
            }
        """)
        self.tabs.addTab(_InfoTab(self), "简介")
        self.tabs.addTab(_ChangelogTab(self), "更新日志")
        layout.addWidget(self.tabs)