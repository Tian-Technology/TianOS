"""
TianOS 开机启动画面 (3 段式 Boot Splash Screen)
================================================
阶段 1: 主板 BIOS 界面 —— TianByte Pro4000
阶段 2: 虚拟机开机界面 —— TianWare Workstation
阶段 3: TianOS 开机界面 —— 蓝色四格 Logo + 底部加载点
随后进入桌面
"""

import sys
import os

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint, QRect, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QBrush, QFontMetrics
)

from system.config import sys_config


# =====================================================================
#  阶段 1: 主板 BIOS 界面 (TianByte Pro4000)
# =====================================================================

class MotherboardStage(QWidget):
    """模拟主板 POST 自检界面"""

    def __init__(self):
        super().__init__()
        self._lines = []
        self._cursor_on = True
        self._elapsed = 0.0
        self._font = QFont("Consolas", 14)
        self._title_font = QFont("Consolas", 26, QFont.Weight.Bold)

        # POST 自检文本序列（从系统配置读取，与 settings.json 保持一致）
        hw = sys_config.HARDWARE
        cpu = hw["cpu"]
        mem = hw["memory"]
        net = hw["network"]
        stor = hw["storage"]
        self._post_lines = [
            "TianByte Pro4000  BIOS  v2.81",
            "Copyright (C) 2024 TianByte Inc.",
            "",
            f"CPU: {cpu['model']} @ {cpu['frequency_mhz'] / 1000:.2f} GHz",
            f"Memory Test: {mem['total_mb']} MB OK",
            "Detecting IDE drives ...",
            f"  Primary Master: {stor['disk_label']}",
            "  Secondary Master: DVD-RW",
            "Detecting USB devices ...",
            "  USB Keyboard ........ OK",
            "  USB Mouse ........... OK",
            "",
            "Initializing PCI devices ...",
            f"  {net['nic_model']}",
            "  Audio: TianByte HD Audio",
            "",
            "Press <F2> to enter Setup, <F12> for Boot Menu",
        ]

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(120)

    def _tick(self):
        self._elapsed += 0.12
        # 每次添加 1 行
        if len(self._lines) < len(self._post_lines):
            self._lines.append(self._post_lines[len(self._lines)])
        self._cursor_on = not self._cursor_on
        self.update()

    def is_done(self) -> bool:
        return len(self._lines) >= len(self._post_lines) and self._elapsed > 1.2

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        fm_title = QFontMetrics(self._title_font)
        fm = QFontMetrics(self._font)

        x = 60
        y = 60

        # 标题
        painter.setFont(self._title_font)
        painter.setPen(QColor(0, 200, 255))
        painter.drawText(x, y + fm_title.ascent(), "TianByte Pro4000")
        y += fm_title.height() + 10

        # 分隔线
        painter.setFont(self._font)
        painter.setPen(QColor(80, 80, 100))
        painter.drawLine(x, y, self.width() - 60, y)
        y += 30

        # POST 行
        painter.setPen(QColor(200, 200, 200))
        for line in self._lines:
            painter.drawText(x, y + fm.ascent(), line)
            y += fm.height() + 2

        # 闪烁光标
        if self._cursor_on:
            painter.fillRect(QRect(x, y, 10, fm.height()), QColor(200, 200, 200))


# =====================================================================
#  阶段 2: 虚拟机开机界面 (TianWare Workstation)
# =====================================================================

class VMwareStage(QWidget):
    """模拟 VMware Workstation 启动界面"""

    def __init__(self):
        super().__init__()
        self._alpha = 0
        self._fade_in = True
        self._elapsed = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def _tick(self):
        self._elapsed += 0.03
        if self._fade_in:
            self._alpha = min(255, self._alpha + 12)
            if self._alpha >= 255:
                self._fade_in = False
        self.update()

    def is_done(self) -> bool:
        return self._elapsed > 1.6

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(8, 8, 16))

        cx = self.width() // 2
        cy = self.height() // 2

        a = self._alpha

        # 左侧方形色块 (模拟 VMware 风格 logo)
        block = 70
        bx = cx - 130
        by = cy - block // 2
        colors = [
            QColor(30, 120, 220, a),
            QColor(20, 160, 220, a),
            QColor(230, 120, 30, a),
            QColor(200, 60, 60, a),
        ]
        for i, c in enumerate(colors):
            row, col = i // 2, i % 2
            painter.fillRect(
                QRect(bx + col * (block // 2 + 4),
                      by + row * (block // 2 + 4),
                      block // 2, block // 2), c)

        # 文字
        title_font = QFont("Segoe UI", 38, QFont.Weight.Light)
        sub_font = QFont("Segoe UI", 13, QFont.Weight.Normal)
        painter.setFont(title_font)
        painter.setPen(QColor(255, 255, 255, a))
        tx = bx + block + 30
        painter.drawText(tx, cy - 10, "TianWare")
        painter.setFont(sub_font)
        painter.setPen(QColor(180, 180, 200, a))
        painter.drawText(tx, cy + 26, "Workstation")

        # 底部版本
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(120, 120, 140, a))
        painter.drawText(QRect(0, self.height() - 40, self.width(), 20),
                         Qt.AlignmentFlag.AlignCenter,
                         "TianWare Workstation Pro 17.5  ·  Build 23749192")


# =====================================================================
#  主启动画面容器 —— 依次播放两个阶段
# =====================================================================

class BootSplashScreen(QMainWindow):
    """两段式开机启动画面: 主板 BIOS → TianWare → 桌面"""

    boot_complete = pyqtSignal()
    # 淡出动画开始时发出，用于在此之前把桌面放到开机画面下层
    fade_started = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TianOS 正在启动...")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)

        screen = QApplication.primaryScreen()
        if screen:
            g = screen.geometry()
            self.screen_width = g.width()
            self.screen_height = g.height()
        else:
            self.screen_width = 1280
            self.screen_height = 720
        self.setGeometry(0, 0, self.screen_width, self.screen_height)

        self._stage = 0  # 0=主板, 1=虚拟机（最后阶段）
        self._stage_widget = None
        self._boot_finished = False
        self._completed = False
        self._fade_anim = None  # 淡出动画
        self._fade_delay_timer = None  # 淡出前延时

        # 阶段切换定时器
        self._switch_timer = QTimer(self)
        self._switch_timer.timeout.connect(self._check_switch)
        self._switch_timer.start(100)

        self._show_stage(0)

    def _show_stage(self, idx: int):
        if self._stage_widget is not None:
            self._stage_widget.deleteLater()
        if idx == 0:
            self._stage_widget = MotherboardStage()
        else:
            self._stage_widget = VMwareStage()
        self.setCentralWidget(self._stage_widget)
        self._stage = idx

    def _check_switch(self):
        if self._stage == 0:
            if isinstance(self._stage_widget, MotherboardStage) and self._stage_widget.is_done():
                self._show_stage(1)
        elif self._stage == 1:
            # VMware 阶段播放完毕 + 启动线程结束 → 直接进入桌面
            if isinstance(self._stage_widget, VMwareStage) and self._stage_widget.is_done():
                if self._boot_finished and not self._completed:
                    self._finish_boot()

    # ---- 对外接口 ----

    def set_boot_progress(self, phase: str, progress: int, description: str):
        """接收启动进度（TianOS 阶段时可显示描述，但为简洁暂不显示）"""
        pass

    def boot_finished(self):
        """启动线程执行完毕 —— 由 main.py 调用"""
        self._boot_finished = True

    def skip_animation(self):
        """快速启动模式：直接进入 VMware 阶段"""
        if self._stage < 1:
            self._show_stage(1)

    def _finish_boot(self):
        """TianWare 启动完成后，延后淡出 → 进入桌面"""
        if self._completed:
            return
        self._completed = True
        self._switch_timer.stop()

        delay_ms = getattr(self, '_fade_delay_ms', 0)
        if delay_ms > 0:
            self._fade_delay_timer = QTimer(self)
            self._fade_delay_timer.setSingleShot(True)
            self._fade_delay_timer.timeout.connect(self._start_fade)
            self._fade_delay_timer.start(delay_ms)
        else:
            self._start_fade()

    def _start_fade(self):
        """启动淡出动画（先告知外部把桌面放到下层，再开始透明）"""
        self.fade_started.emit()
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(700)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.finished.connect(self.boot_complete.emit)
        self._fade_anim.start()

    def _skip_to_desktop(self):
        """跳过淡出动画（含延时期），直接进入桌面"""
        if self._completed:
            return
        self._completed = True
        self._switch_timer.stop()
        if self._fade_delay_timer is not None:
            self._fade_delay_timer.stop()
        if self._fade_anim is not None:
            self._fade_anim.stop()
        self.boot_complete.emit()

    def keyPressEvent(self, event):
        """按任意键跳过动画；淡出期间按键则直接进入桌面"""
        if self._completed:
            self._skip_to_desktop()
        elif self._stage < 1:
            self._show_stage(1)
        else:
            self._boot_finished = True

    def mousePressEvent(self, event):
        """点击跳过动画；淡出期间点击则直接进入桌面"""
        if self._completed:
            self._skip_to_desktop()
        elif self._stage < 1:
            self._show_stage(1)
        else:
            self._boot_finished = True

    def closeEvent(self, event):
        self._switch_timer.stop()
        super().closeEvent(event)