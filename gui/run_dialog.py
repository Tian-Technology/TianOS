"""
TianOS 运行框
支持 Ctrl+R 呼出（桌面），也可被终端命令复用。
提供命令别名到应用显示名的解析。
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# 内置别名 (Windows 风格 / 中文 → 应用显示名)
RUN_ALIASES = {
    # 注册表
    "regedit": "注册表",
    "regedit.exe": "注册表",
    "regedit32": "注册表",
    "注册表": "注册表",
    "注册表编辑器": "注册表",
    # 任务管理器
    "taskmgr": "任务管理器",
    "taskmgr.exe": "任务管理器",
    "任务管理器": "任务管理器",
    # 文件/资源管理器
    "explorer": "文件管理器",
    "explorer.exe": "文件管理器",
    "文件管理器": "文件管理器",
    "资源管理器": "文件管理器",
    # 组策略
    "gpedit": "组策略",
    "gpedit.msc": "组策略",
    "组策略": "组策略",
    "组策略编辑器": "组策略",
    # 设置
    "settings": "设置",
    "control": "设置",
    "control.exe": "设置",
    "设置": "设置",
    "控制面板": "设置",
    "ms-settings": "设置",
    # 终端
    "terminal": "终端",
    "cmd": "终端",
    "cmd.exe": "终端",
    "powershell": "终端",
    "终端": "终端",
    "命令行": "终端",
    # 系统信息
    "msinfo32": "系统信息",
    "sysinfo": "系统信息",
    "系统信息": "系统信息",
    # 网络工具
    "ncpa.cpl": "网络工具",
    "网络工具": "网络工具",
    "网络": "网络工具",
    # 关于
    "winver": "关于",
    "关于": "关于",
}

_SUFFIXES = (".exe", ".msc", ".cpl", ".bat", ".cmd", ".com")


def _build_index() -> dict:
    """构建 别名 -> 应用显示名 的索引，并入已注册应用的模块名/显示名"""
    index = dict(RUN_ALIASES)
    try:
        from apps import app_registry
        for info in app_registry.scan():
            for key in (info.name, info.name.lower(), info.module_name,
                        info.module_name.lower(), info.icon):
                index.setdefault(key, info.name)
    except Exception:
        pass
    return index


def resolve_run_command(cmd: str) -> Optional[str]:
    """将输入命令解析为应用显示名，无法解析返回 None"""
    raw = (cmd or "").strip().strip('"').strip("'")
    if not raw:
        return None
    index = _build_index()
    norm = raw.lower()
    # 去掉常见文件后缀再匹配
    for suffix in _SUFFIXES:
        if norm.endswith(suffix):
            norm = norm[: -len(suffix)]
            break
    return index.get(norm) or index.get(raw)


class RunDialog(QWidget):
    """运行对话框 - 无边框浮窗，带应用建议列表"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._on_launch = None  # 回调 fn(app_name, raw_cmd)

        self._app_names = []
        from apps import app_registry
        try:
            self._app_names = sorted(info.name for info in app_registry.scan())
        except Exception:
            self._app_names = []

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(440, 280)
        self.setStyleSheet("""
            RunDialog {
                background-color: rgba(16, 18, 40, 250);
                border: 1px solid #00ccff;
                border-radius: 12px;
            }
        """)
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 14)
        outer.setSpacing(8)

        title = QLabel("运行")
        title.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ccff;")
        outer.addWidget(title)

        # 输入框
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入程序名称后按回车（如 regedit、explorer、gpedit、taskmgr）")
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255,255,255,0.08);
                color: #ffffff;
                border: 1px solid #334466;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #00ccff; }
        """)
        self.input.returnPressed.connect(self._accept)
        self.input.textChanged.connect(self._update_suggestions)
        outer.addWidget(self.input)

        # 建议列表
        hint = QLabel("常用:")
        hint.setStyleSheet("color:#556677; font-size:11px;")
        outer.addWidget(hint)

        self.suggest_label = QLabel()
        self.suggest_label.setStyleSheet("color:#88aacc; font-size:12px;")
        self.suggest_label.setWordWrap(True)
        outer.addWidget(self.suggest_label, 1)
        self._update_suggestions("")

        # 按钮行
        btn_row = QHBoxLayout()
        btn_style = """
            QPushButton {
                background-color: rgba(255,255,255,0.08);
                color: #cccccc;
                border: 1px solid #334466;
                border-radius: 6px;
                padding: 6px 22px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: rgba(0,180,255,0.2); border-color: #00ccff; }
        """
        ok_btn = QPushButton("确定")
        ok_btn.setStyleSheet(btn_style)
        ok_btn.clicked.connect(self._accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(btn_style)
        cancel_btn.clicked.connect(self.hide)
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

    def set_launch_callback(self, fn):
        """设置启动回调: fn(app_name, raw_cmd)"""
        self._on_launch = fn

    def _update_suggestions(self, text):
        common = self._app_names
        if text:
            t = text.lower()
            common = [n for n in common if t in n.lower()]
        shown = common[:8]
        if shown:
            lines = [f"• {n}" for n in shown]
            if len(common) > len(shown):
                lines.append(f"… 共 {len(common)} 个")
            self.suggest_label.setText("\n".join(lines))
        else:
            self.suggest_label.setText("（无匹配应用）")

    def _accept(self):
        cmd = self.input.text().strip()
        if not cmd:
            return
        app = resolve_run_command(cmd)
        if self._on_launch:
            self._on_launch(app, cmd)
        self.input.clear()
        self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        if event.key() == Qt.Key.Key_R and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.hide()
            return
        super().keyPressEvent(event)

    def show_at(self, x, y):
        self.move(x - self.width() // 2, y - self.height() // 2)
        self.show()
        self.raise_()
        self.input.setFocus()