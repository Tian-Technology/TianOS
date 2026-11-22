"""
TianOS 搜索面板
================
点击任务栏搜索按钮（🔍）弹出，支持:
- 实时搜索已安装的应用（按名称/模块名模糊匹配），点击即启动
- 输入网址或关键词后回车，通过 Tian浏览器 打开网页或执行网络搜索
"""

from typing import List, Optional
from urllib.parse import quote

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont


class SearchPanel(QWidget):
    """搜索面板 - 无边框浮窗，实时搜索应用并可浏览网页"""

    app_launch = pyqtSignal(str)   # 启动应用（应用显示名）
    web_launch = pyqtSignal(str)   # 用 Tian浏览器 打开网址/搜索

    def __init__(self, parent=None):
        super().__init__(parent)
        self._apps: List = []
        self._last_query: str = ""
        self._load_apps()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(480, 470)
        self.setStyleSheet("""
            SearchPanel {
                background-color: rgba(16, 18, 40, 250);
                border: 1px solid #00ccff;
                border-radius: 12px;
            }
        """)
        self._setup_ui()
        self.hide()

    # ---------- 数据 ----------

    def _load_apps(self):
        """加载已安装应用列表（含桌面快捷方式目标）"""
        try:
            from apps import app_registry
            self._apps = sorted(
                app_registry.scan(), key=lambda a: a.name)
        except Exception:
            self._apps = []

    # ---------- 界面 ----------

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 14)
        outer.setSpacing(8)

        title = QLabel("🔍 搜索")
        title.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ccff;")
        outer.addWidget(title)

        # 输入框
        self.input = QLineEdit()
        self.input.setPlaceholderText("搜索应用；或输入网址 / 关键词浏览网页")
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
        self.input.textChanged.connect(self._update_results)
        outer.addWidget(self.input)

        # "应用" 标题
        app_header = QLabel("应用")
        app_header.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        app_header.setStyleSheet("color:#8a98b8; font-size:11px;")
        outer.addWidget(app_header)

        # 应用结果列表（滚动区域）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(255,255,255,0.05); width: 4px; border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.25); border-radius: 2px;
            }
        """)
        self.result_widget = QWidget()
        self.result_widget.setStyleSheet("background: transparent;")
        self.result_layout = QVBoxLayout(self.result_widget)
        self.result_layout.setContentsMargins(0, 0, 0, 0)
        self.result_layout.setSpacing(1)
        scroll.setWidget(self.result_widget)
        outer.addWidget(scroll, 1)

        # 分隔线
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255,255,255,12);")
        outer.addWidget(sep)

        # 网页提示行
        self.web_hint = QLabel()
        self.web_hint.setStyleSheet("color:#556677; font-size:11px;")
        self.web_hint.setWordWrap(True)
        outer.addWidget(self.web_hint)

        self._update_results("")

    # ---------- 结果 ----------

    def _clear_results(self):
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _result_row(self, text: str, tooltip: str, handler) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(32)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                text-align: left;
                padding-left: 10px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: rgba(255,255,255,0.10); }
        """)
        btn.clicked.connect(handler)
        return btn

    def _update_results(self, text: str):
        self._clear_results()
        query = (text or "").strip().lower()
        self._last_query = query

        matched = []
        if query:
            for info in self._apps:
                if (query in info.name.lower()
                        or query in info.module_name.lower()):
                    matched.append(info)
            # 名字前缀匹配优先
            matched.sort(key=lambda a: (0 if a.name.lower().startswith(query) else 1,
                                        a.name))
        else:
            # 空输入：显示全部应用（限制数量，避免刷屏）
            matched = self._apps[:20]

        for info in matched:
            icon = info.icon if info.icon else "📄"
            btn = self._result_row(
                f"{icon}   {info.name}",
                f"启动 {info.name}",
                lambda checked=False, name=info.name: self._launch_app(name),
            )
            self.result_layout.addWidget(btn)

        if not matched:
            hint = QLabel("（没有匹配的应用）")
            hint.setStyleSheet("color:#556677; font-size:11px; padding-left:10px;")
            self.result_layout.addWidget(hint)

        self.result_layout.addStretch()

        if query:
            url = self._to_web_url(text)
            self.web_hint.setText(
                f"将用 Tian浏览器 打开: {url}. 按回车确认。")
        else:
            self.web_hint.setText("输入应用名称搜索应用，或输入网址 / 关键词浏览网页。")

    # ---------- 动作 ----------

    def _launch_app(self, name: str):
        self.hide()
        self.input.clear()
        self.app_launch.emit(name)

    def _accept(self):
        """回车处理：优先启动匹配的应用，否则浏览网页"""
        text = self.input.text().strip()
        if not text:
            return
        query = text.lower()
        # 精确匹配应用名 → 启动
        for info in self._apps:
            if info.name.lower() == query:
                self._launch_app(info.name)
                return
        # 命令别名解析（regedit / explorer / settings 等）
        try:
            from gui.run_dialog import resolve_run_command
            app = resolve_run_command(text)
            if app:
                self._launch_app(app)
                return
        except Exception:
            pass
        # 否则按网址 / 搜索词浏览网页
        url = self._to_web_url(text)
        self.hide()
        self.input.clear()
        self.web_launch.emit(url)

    def _to_web_url(self, text: str) -> str:
        """网页地址转换：网址直达，否则用 Bing 搜索"""
        t = text.strip()
        if t.startswith("http://") or t.startswith("https://"):
            return t
        if t.startswith("tian://"):
            return t
        # 形如 xx.xxx 且无空格 → 当作域名
        if "." in t and " " not in t:
            return "https://" + t
        return "https://www.bing.com/search?q=" + quote(t)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    def show_at(self, x: int, y: int):
        self.move(x - self.width() // 2, y - self.height() // 2)
        self.show()
        self.raise_()
        self.input.setFocus()
        self.input.selectAll()