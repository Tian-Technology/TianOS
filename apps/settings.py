"""
TianOS 系统设置 (TianOS 风格)
左侧分类导航 + 右侧卡片式设置项，修改即时保存到本地 data/settings.json
"""

APP_NAME = "设置"
APP_ICON = "⚙"
APP_ICON_FILE = "shell32 315.png"
APP_COLOR = "#00ccff"

import time as _time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QFrame, QScrollArea,
    QLineEdit, QSlider
)
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush
from PyQt6.QtCore import Qt, QTimer, QRect, pyqtSignal

from system.config import sys_config


# ===================== 颜色常量 (Win11 深色主题) =====================
BG_COLOR = "#202028"
SIDEBAR_BG = "#1c1c24"
CARD_BG = "#2a2a35"
CARD_BORDER = "#3a3a48"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#b0b0b8"
TEXT_TERTIARY = "#80808a"
ACCENT = "#00ccff"
HOVER_BG = "#32323f"
SELECTED_BG = "#3a3a4a"
TOGGLE_OFF = "#555566"


class ToggleSwitch(QWidget):
    """TianOS 风格开关"""

    toggled = pyqtSignal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 20)
        self._checked = checked
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self.update()
            self.toggled.emit(checked)

    def mousePressEvent(self, event):
        self.setChecked(not self._checked)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        radius = h // 2

        if self._checked:
            p.setBrush(QBrush(QColor(ACCENT)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(0, 0, w, h, radius, radius)
            knob_x = w - h
        else:
            p.setBrush(QBrush(QColor(TOGGLE_OFF)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(0, 0, w, h, radius, radius)
            knob_x = 2

        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(knob_x + 1, 1, h - 2, h - 2)
        p.end()


class CategoryButton(QPushButton):
    """左侧分类按钮 (图标 + 文字)"""

    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._text = text
        self._selected = False
        self.setCheckable(True)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def set_selected(self, selected: bool):
        self._selected = selected
        self.setChecked(selected)
        self._apply_style()

    def _apply_style(self):
        bg = SELECTED_BG if self._selected else "transparent"
        self.setStyleSheet(f"""
            CategoryButton {{
                background-color: {bg};
                color: {TEXT_PRIMARY};
                border: none;
                border-radius: 6px;
                text-align: left;
                padding-left: 16px;
                font-size: 13px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
            CategoryButton:hover {{
                background-color: {HOVER_BG};
            }}
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Segoe UI Emoji", 14)
        p.setFont(font)
        p.setPen(QColor(TEXT_PRIMARY))
        p.drawText(QRect(16, 0, 24, self.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter,
                   self._icon)
        p.setFont(QFont("Segoe UI", 13))
        p.drawText(QRect(48, 0, self.width() - 56, self.height()),
                   Qt.AlignmentFlag.AlignVCenter, self._text)
        p.end()


class SettingsCard(QFrame):
    """设置卡片 (Win11 圆角卡片)"""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            SettingsCard {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 8px;
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(10)

        if title:
            lbl = QLabel(title)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: 600;")
            lbl.setContentsMargins(0, 0, 0, 6)
            self._layout.addWidget(lbl)

    def add_row(self, label_text: str, widget: QWidget, description: str = ""):
        """向卡片添加一行: 标签/说明 + 控件"""
        row = QHBoxLayout()
        row.setContentsMargins(0, 4, 0, 4)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px;")
        text_col.addWidget(lbl)

        if description:
            desc = QLabel(description)
            desc.setStyleSheet(f"color: {TEXT_TERTIARY}; font-size: 11px;")
            desc.setWordWrap(True)
            text_col.addWidget(desc)

        row.addLayout(text_col, 1)
        row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        self._layout.addLayout(row)
        return row


# ===================== 主设置窗口 =====================

class Settings(QWidget):
    """系统设置 - TianOS 风格"""

    # 分类定义: (id, 图标, 显示名)
    CATEGORIES = [
        ("system", "🖥️", "系统"),
        ("network", "🌐", "网络和 Internet"),
        ("personalization", "🎨", "个性化"),
        ("apps", "📦", "应用"),
        ("accounts", "👤", "账户"),
        ("time", "🕒", "时间和语言"),
        ("gaming", "🎮", "游戏"),
        ("accessibility", "♿", "辅助功能"),
        ("privacy", "🔒", "隐私和安全性"),
        ("update", "🔄", "TianOS 更新"),
        ("developer", "⚒️", "开发者选项"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumSize(760, 520)
        self._current_page = "system"
        self._category_buttons = {}
        self._clock_timer = None
        self._setup_ui()

    # ---------- UI 构建 ----------

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 左侧边栏 ----
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet(f"background-color: {SIDEBAR_BG};")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(8, 16, 8, 16)
        side_layout.setSpacing(2)

        # 设置标题
        title = QLabel("设置")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; padding-left: 8px; padding-bottom: 12px;")
        side_layout.addWidget(title)

        # 分类按钮
        for cat_id, icon, name in self.CATEGORIES:
            btn = CategoryButton(icon, name)
            btn.clicked.connect(lambda checked, cid=cat_id: self._select_category(cid))
            self._category_buttons[cat_id] = btn
            side_layout.addWidget(btn)

        side_layout.addStretch()
        root.addWidget(sidebar)

        # ---- 右侧内容区 ----
        content = QFrame()
        content.setStyleSheet(f"background-color: {BG_COLOR};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 顶部条
        header = QFrame()
        header.setFixedHeight(56)
        header.setStyleSheet(f"background-color: {BG_COLOR}; border-bottom: 1px solid {CARD_BORDER};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)

        self._page_title = QLabel("系统")
        self._page_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._page_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        header_layout.addWidget(self._page_title)
        header_layout.addStretch()
        content_layout.addWidget(header)

        # 滚动内容区
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background: {BG_COLOR}; border: none; }}
            QScrollBar:vertical {{
                background: transparent; width: 10px;
            }}
            QScrollBar::handle:vertical {{
                background: #555566; border-radius: 5px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: #666677; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(24, 20, 24, 20)
        self._content_layout.setSpacing(16)
        self._scroll.setWidget(self._content_widget)
        content_layout.addWidget(self._scroll, 1)

        root.addWidget(content, 1)

        # 选中第一个分类
        self._select_category("system")

    # ---------- 分类切换 ----------

    def _select_category(self, cat_id: str):
        self._current_page = cat_id
        for cid, btn in self._category_buttons.items():
            btn.set_selected(cid == cat_id)

        cat_name = next(n for c, _, n in self.CATEGORIES if c == cat_id)
        self._page_title.setText(cat_name)

        self._stop_clock()
        self._clear_layout(self._content_layout)
        self._render_category(cat_id)
        self._content_layout.addStretch()

    # ---------- 控件工厂 ----------

    def _readonly_label(self, text: str) -> QLabel:
        lbl = QLabel(str(text) if text is not None else "-")
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return lbl

    def _make_toggle(self, key: str):
        value = bool(sys_config.get(key))
        sw = ToggleSwitch(value)
        sw.toggled.connect(lambda checked, k=key: sys_config.set(k, checked))
        return sw

    def _make_combo(self, key: str, choices):
        value = sys_config.get(key)
        cb = QComboBox()
        cb.addItems(list(choices))
        if value in choices:
            cb.setCurrentText(str(value))
        cb.setStyleSheet(f"""
            QComboBox {{
                background-color: #333340; color: {TEXT_PRIMARY};
                border: 1px solid {CARD_BORDER}; border-radius: 4px;
                padding: 4px 10px; min-width: 120px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background-color: #2a2a35; color: {TEXT_PRIMARY};
                selection-background-color: {ACCENT}; border: 1px solid {CARD_BORDER};
            }}
        """)
        cb.currentTextChanged.connect(
            lambda text, k=key: sys_config.set(k, text))
        return cb

    def _make_spin(self, key: str, low: int, high: int):
        value = sys_config.get(key)
        sb = QSpinBox()
        sb.setRange(low, high)
        try:
            sb.setValue(int(value))
        except (TypeError, ValueError):
            sb.setValue(low)
        sb.setStyleSheet(f"""
            QSpinBox {{
                background-color: #333340; color: {TEXT_PRIMARY};
                border: 1px solid {CARD_BORDER}; border-radius: 4px;
                padding: 4px 8px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background-color: #3a3a48; border: none; width: 16px;
            }}
        """)
        sb.valueChanged.connect(lambda v, k=key: sys_config.set(k, v))
        return sb

    def _make_slider(self, key: str, low: int = 0, high: int = 100):
        value = sys_config.get(key, low)
        try:
            val = int(value)
        except (TypeError, ValueError):
            val = low
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(low, high)
        slider.setValue(val)
        slider.setFixedWidth(140)
        slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px; background: #444455; border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT}; width: 14px; height: 14px;
                margin: -5px 0; border-radius: 7px;
            }}
        """)
        label = QLabel(str(val))
        label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px;")
        label.setFixedWidth(32)

        def on_change(v, lbl=label):
            lbl.setText(str(v))

        def on_release(k=key):
            sys_config.set(k, slider.value())

        slider.valueChanged.connect(on_change)
        slider.sliderReleased.connect(on_release)
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(slider)
        lay.addWidget(label)
        return wrap

    def _make_text(self, key: str):
        value = sys_config.get(key, "")
        line = QLineEdit(str(value) if value is not None else "")
        line.setStyleSheet(f"""
            QLineEdit {{
                background-color: #333340; color: {TEXT_PRIMARY};
                border: 1px solid {CARD_BORDER}; border-radius: 4px;
                padding: 4px 8px; min-width: 140px;
            }}
        """)
        line.returnPressed.connect(lambda k=key, w=line: sys_config.set(k, w.text()))
        return line

    # ---------- 各分类渲染 ----------

    def _render_category(self, cat_id: str):
        renderer = getattr(self, f"_page_{cat_id}", None)
        if renderer:
            renderer()
        else:
            self._page_coming_soon(cat_id)

    def _add_card(self, title: str = "") -> SettingsCard:
        card = SettingsCard(title)
        self._content_layout.addWidget(card)
        return card

    def _page_system(self):
        display = self._add_card("显示")
        w = sys_config.get("HARDWARE.display.width")
        h = sys_config.get("HARDWARE.display.height")
        display.add_row("显示器分辨率", self._readonly_label(f"{w} × {h}"))
        display.add_row("刷新率 (Hz)", self._make_spin("HARDWARE.display.refresh_rate", 30, 360))
        display.add_row("字体大小", self._make_spin("GUI.font_size", 8, 32))
        display.add_row("字体", self._make_combo(
            "GUI.font_family",
            ["Microsoft YaHei", "Consolas", "SimSun", "Comic Sans MS", "Segoe UI"]))
        display.add_row("透明度效果", self._make_toggle("GUI.transparency_effects"),
                        "让窗口和菜单呈现半透明效果")

        sound = self._add_card("声音")
        sound.add_row("主音量", self._make_slider("SOUND.volume", 0, 100))
        sound.add_row("静音", self._make_toggle("SOUND.muted"))
        sound.add_row("输出设备", self._readonly_label(sys_config.get("SOUND.device")))

        about = self._add_card("关于")
        about.add_row("系统名称", self._readonly_label(sys_config.SYSTEM_NAME))
        about.add_row("版本", self._readonly_label(sys_config.SYSTEM_VERSION))
        about.add_row("架构", self._readonly_label(sys_config.SYSTEM_ARCH))

    def _page_network(self):
        net = self._add_card("网络")
        net.add_row("主机 IP", self._readonly_label(sys_config.get("NETWORK.host_ip")))
        net.add_row("子网掩码", self._readonly_label(sys_config.get("NETWORK.netmask")))
        net.add_row("网关", self._readonly_label(sys_config.get("NETWORK.gateway")))
        net.add_row("首选 DNS", self._readonly_label(sys_config.get("NETWORK.dns_primary")))
        net.add_row("备用 DNS", self._readonly_label(sys_config.get("NETWORK.dns_secondary")))
        net.add_row("MTU", self._make_spin("NETWORK.mtu", 576, 1500))
        net.add_row("TCP 窗口大小", self._make_spin("NETWORK.tcp_window_size", 1024, 65535))
        net.add_row("启用 DHCP", self._make_toggle("NETWORK.enable_dhcp"))

    def _page_personalization(self):
        bg = self._add_card("背景")
        bg.add_row("主题", self._make_combo(
            "GUI.theme",
            ["TianOS-Default", "深色", "浅色", "高对比度"]))
        bg.add_row("强调色", self._make_combo(
            "GUI.accent_color",
            ["#00ccff", "#ff9900", "#00ff99", "#ff5577", "#aa66ff"]))
        bg.add_row("壁纸颜色", self._make_text("GUI.wallpaper_color"))

        start = self._add_card("开始菜单和任务栏")
        start.add_row("开始菜单样式", self._make_combo(
            "PERSONALIZATION.start_menu_style",
            ["centered", "left"]))
        start.add_row("显示任务标签", self._make_toggle("PERSONALIZATION.show_task_labels"))
        start.add_row("启用坞站", self._make_toggle("GUI.dock_enabled"))
        start.add_row("启用动画", self._make_toggle("GUI.enable_animations"))

    def _page_apps(self):
        self._info_card("应用", [
            "已安装的应用程序列表",
            "在此管理应用的启动、卸载和默认设置",
            "应用数量会随安装情况动态变化",
        ])

    def _page_accounts(self):
        acc = self._add_card("账户信息")
        acc.add_row("用户名", self._readonly_label(sys_config.get("ACCOUNTS.username")))
        acc.add_row("显示名称", self._make_text("ACCOUNTS.display_name"))
        acc.add_row("账户类型", self._readonly_label(sys_config.get("ACCOUNTS.account_type")))
        acc.add_row("主目录", self._readonly_label(sys_config.get("ACCOUNTS.home_dir")))

    def _page_time(self):
        card = self._add_card("日期和时间")

        clock_label = QLabel()
        clock_label.setFont(QFont("Consolas", 22, QFont.Weight.Bold))
        clock_label.setStyleSheet(f"color: {ACCENT};")
        clock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.add_row("当前时间", clock_label)

        card.add_row("时区", self._readonly_label(sys_config.get("LOCALE.timezone")))
        card.add_row("显示语言", self._readonly_label(sys_config.get("LOCALE.language")))
        card.add_row("自动设置时间", self._make_toggle("LOCALE.auto_set_time"))

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(
            lambda: clock_label.setText(_time.strftime("%Y-%m-%d  %H:%M:%S")))
        self._clock_timer.start(1000)
        clock_label.setText(_time.strftime("%Y-%m-%d  %H:%M:%S"))

    def _page_gaming(self):
        self._info_card("游戏", [
            "游戏模式：开启后系统会优先分配资源给游戏",
            "Xbox Game Bar：按 Win+G 打开游戏栏",
            "捕获：截图和录屏设置",
            "图形设置：为特定应用指定 GPU",
        ])

    def _page_accessibility(self):
        self._info_card("辅助功能", [
            "视觉：放大镜、颜色滤镜、高对比度",
            "听觉：单声道音频、可视化通知",
            "交互：粘滞键、筛选键、切换键",
            "语音：语音识别、讲述人",
        ])

    def _page_privacy(self):
        self._info_card("隐私和安全性", [
            "TianOS 安全中心：病毒和威胁防护",
            "位置服务：控制应用的位置访问权限",
            "摄像头：管理应用的摄像头访问",
            "麦克风：管理应用的麦克风访问",
            "诊断和反馈：遥测数据设置",
        ])

    def _page_update(self):
        self._info_card("TianOS 更新", [
            f"当前版本: {sys_config.SYSTEM_VERSION}",
            "系统已是最新版本",
            "上次检查: 刚刚",
            "高级选项：暂停更新、传递优化",
        ])

    def _page_developer(self):
        dev = self._add_card("开发者选项")
        dev.add_row("引导设备", self._readonly_label(sys_config.get("BOOT.boot_device")))
        dev.add_row("开机菜单延迟 (秒)", self._make_spin("BOOT.boot_menu_delay", 0, 30))
        dev.add_row("详细启动日志", self._make_toggle("BOOT.enable_verbose"))
        dev.add_row("启用 EFI 引导", self._make_toggle("BOOT.enable_efi"))

        perf = self._add_card("性能")
        perf.add_row("最大进程数", self._make_spin("PROCESS.max_processes", 16, 1024))
        perf.add_row("每进程最大线程数", self._make_spin("PROCESS.max_threads_per_process", 1, 512))
        perf.add_row("时间片 (ms)", self._make_spin("PROCESS.quantum_ms", 1, 100))

    def _info_card(self, title: str, lines):
        card = self._add_card(title)
        for line in lines:
            lbl = QLabel(f"•  {line}")
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; padding: 4px 0;")
            card._layout.addWidget(lbl)

    def _page_coming_soon(self, cat_id: str):
        self._info_card("即将推出", [
            "此设置页正在开发中，敬请期待。",
        ])

    # ---------- 工具方法 ----------

    def _stop_clock(self):
        if hasattr(self, "_clock_timer") and self._clock_timer:
            try:
                self._clock_timer.stop()
            except Exception:
                pass
            self._clock_timer = None

    def _clear_layout(self, layout):
        self._stop_clock()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                for timer in widget.findChildren(QTimer):
                    timer.stop()
                widget.deleteLater()
            else:
                sub = item.layout()
                if sub is not None:
                    self._clear_layout(sub)