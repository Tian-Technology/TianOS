"""
TianOS 桌面环境
===============
使用 PyQt6 构建的桌面环境，包含:
- 桌面背景和图标
- 任务栏
- 窗口管理器
- 系统托盘
- 桌面右键菜单
"""

import sys
import time
import os
import math
import json
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QMenu, QSystemTrayIcon, QToolButton,
    QLineEdit, QScrollArea, QDialog, QSizePolicy, QSpacerItem,
    QGridLayout, QStatusBar, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import (
    Qt, QTimer, QRect, QSize, QPoint, pyqtSignal, pyqtProperty, QPropertyAnimation,
    QEasingCurve, QParallelAnimationGroup, QEvent, QObject, QRectF
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QLinearGradient, QPen, QBrush,
    QPixmap, QIcon, QAction, QPalette, QFontDatabase, QMouseEvent,
    QKeyEvent, QRadialGradient, QPainterPath, QCursor
)

from gui.run_dialog import RunDialog, resolve_run_command


@dataclass
class DesktopIcon:
    """桌面图标"""
    name: str
    icon_text: str
    action: Optional[Callable] = None
    color: str = "#00d4ff"
    icon_file: str = ""


@dataclass
class AppWindow:
    """应用程序窗口"""
    title: str
    widget: QWidget
    minimized: bool = False
    width: int = 800
    height: int = 600
    taskbar_button: Optional['TaskbarButton'] = None
    icon_file: str = ""


class TaskbarButton(QPushButton):
    """任务栏按钮 (Windows 11 风格：图标 + 底部指示条)"""

    def __init__(self, title: str, parent=None, icon_file: str = ""):
        super().__init__(title, parent)
        self.setFixedSize(40, 40)
        self.setToolTip(title)
        self._icon_file = icon_file
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 15);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 25);
            }
        """)
        # 用标题首字符作为图标（无图片时的回退）
        self.setText(title[:1] if title else "▢")
        self._bounce = 0.0
        self._jump_anim: Optional[QPropertyAnimation] = None

    # 弹跳动画（Win11 任务栏图标跳动）
    def _get_bounce(self):
        return self._bounce

    def _set_bounce(self, val):
        self._bounce = float(val)
        self.update()

    bounce = pyqtProperty(float, _get_bounce, _set_bounce)

    def jump(self):
        """图标跳动：先上升回落再轻微回弹"""
        if self._jump_anim and self._jump_anim.state() == \
                QPropertyAnimation.State.Running:
            self._jump_anim.stop()
        self.setProperty("bounce", 0.0)
        anim = QPropertyAnimation(self, b"bounce", self)
        anim.setDuration(420)
        anim.setStartValue(0.0)
        anim.setKeyValueAt(0.5, 1.0)   # 途中达到最高点
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._jump_anim = anim
        anim.start()

    def paintEvent(self, event):
        if self._icon_file:
            from apps import get_icon_pixmap
            pix = get_icon_pixmap(self._icon_file, 26)
            if pix:
                p = QPainter(self)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                x = (self.width() - pix.width()) // 2
                y = (self.height() - pix.height()) // 2
                # 弹跳：向上抬起（sin 曲线），并轻微放大产生弹跳感
                b = self._bounce
                if b > 0:
                    lift = -9.0 * math.sin(math.pi * b)
                    scale = 1.0 + 0.18 * math.sin(math.pi * b)
                    w = int(pix.width() * scale)
                    h = int(pix.height() * scale)
                    p.drawPixmap(x - (w - pix.width()) // 2,
                                 y + int(lift) - (h - pix.height()) // 2, w, h, pix)
                else:
                    p.drawPixmap(x, y, pix)
                p.end()
                return
        super().paintEvent(event)


class DesktopWidget(QWidget):
    """
    桌面Widget
    桌面背景、图标绘制
    """

    icon_clicked = pyqtSignal(str)  # 图标名称
    context_action = pyqtSignal(str, str)  # (动作, 图标名或空) 右键菜单

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.desktop_icons: List[DesktopIcon] = []
        self.clock_text = time.strftime("%H:%M")
        self._icon_rects: List[Tuple[str, QRect]] = []  # (icon_name, rect)

        # 拖拽/选择/摆放状态
        self._icon_positions: Dict[str, QPoint] = {}   # 图标名 -> 自定义位置(自由摆放)
        self.selected: Optional[str] = None            # 当前选中图标名
        self._drag_index: Optional[int] = None
        self._drag_pos = QPoint()
        self._press_pos = QPoint()
        self._dragging = False

        # 时钟更新
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)

    def update_clock(self):
        """更新时间"""
        self.clock_text = time.strftime("%H:%M")
        self.update()

    def mousePressEvent(self, event):
        """按下：记录选中/拖拽的起始图标"""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            hit = self._icon_name_at(pos)
            if hit is not None:
                self._drag_index = self._icon_names().index(hit)
                self._press_pos = pos
                self._dragging = False
                return
            # 点空白处取消选中
            if self.selected:
                self.selected = None
                self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """拖动图标到任意位置"""
        if (self._drag_index is not None and
                event.buttons() & Qt.MouseButton.LeftButton):
            pos = event.position().toPoint()
            if not self._dragging:
                if (pos - self._press_pos).manhattanLength() < 12:
                    return
                self._dragging = True
                self.selected = None   # 拖动时取消选中
            self._drag_pos = pos
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """释放：吸附到最近格子完成换位，或单击选中"""
        if event.button() == Qt.MouseButton.LeftButton and \
                self._drag_index is not None:
            name = self._icon_names()[self._drag_index]
            if self._dragging:
                # 只能落在格子里：吸附到最近格子，并保证一格只有一图标（交换原占用者）
                target = self._snap_to_cell(self._drag_pos)
                cells = self._cell_map()
                old = cells.get(name, (target.x(), target.y()))
                by_cell = {cell: n for n, cell in cells.items()}
                occupant = by_cell.get((target.x(), target.y()))
                if occupant is not None and occupant != name:
                    # 让原占用者换到该图标原来的格子
                    self._icon_positions[occupant] = QPoint(old[0], old[1])
                self._icon_positions[name] = QPoint(target)
                self._save_order()
            else:
                # 单击 → 选中
                self.selected = name
            self._drag_index = None
            self._dragging = False
            self.update()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """双击桌面图标 → 打开软件"""
        if event.button() == Qt.MouseButton.LeftButton:
            name = self._icon_name_at(event.position().toPoint())
            if name is not None:
                self.selected = name
                self.icon_clicked.emit(name)
                return
        super().mouseDoubleClickEvent(event)

    def _icon_names(self):
        return [ic.name for ic in self.desktop_icons]

    def _icon_name_at(self, pos):
        """返回指定位置所在的图标名（命中图标画布）"""
        for name, rect in self._icon_rects:
            if rect.contains(pos):
                return name
        return None

    def contextMenuEvent(self, event):
        """右键打开上下文菜单（背景/图标）"""
        from PyQt6.QtWidgets import QMenu
        from system.context_menu import build_menu, load_menus

        pos = event.pos()
        icon_name = ""
        for name, rect in self._icon_rects:
            if rect.contains(pos):
                icon_name = name
                break

        menus = load_menus()
        items = menus.get("file", []) if icon_name else menus.get("desktop", [])
        handler = lambda action, name=icon_name: self.context_action.emit(action, name)
        menu = build_menu(items, self, handler)
        menu.exec(event.globalPos())
        event.accept()

    def _icon_at(self, pos):
        for name, rect in self._icon_rects:
            if rect.contains(pos):
                return name
        return None

    # ---------- 图标布局（默认自上而下排列，每列最多 8 个） ----------

    def _layout_params(self):
        """返回 (cols, rows, spacing_x, spacing_y, start_x, start_y, icon_size)"""
        spacing_x = 96
        spacing_y = 96
        start_x = 20
        start_y = 20
        icon_size = 48
        # 每列最多 8 个图标
        rows = max(1, min(8, (self.height() - start_y) // spacing_y + 1))
        cols = max(1, (self.width() - start_x * 2) // spacing_x + 1)
        return cols, rows, spacing_x, spacing_y, start_x, start_y, icon_size

    def _default_pos(self, index: int):
        """默认自动排列位置：列优先（自上而下），每列最多 8 个"""
        _, rows, spacing_x, spacing_y, start_x, start_y, _ = self._layout_params()
        col = index // rows
        row = index % rows
        return QPoint(start_x + col * spacing_x, start_y + row * spacing_y)

    def _snap_to_cell(self, pos: QPoint):
        """把任意坐标吸附到最近的网格格子（每列最多 rows 个），返回格子左上角"""
        _, rows, spacing_x, spacing_y, start_x, start_y, _ = self._layout_params()
        col = int(round((pos.x() - start_x) / spacing_x))
        row = int(round((pos.y() - start_y) / spacing_y))
        max_col = max(0, (self.width() - start_x * 2) // spacing_x)
        col = max(0, min(max_col, col))
        row = max(0, min(rows - 1, row))
        return QPoint(start_x + col * spacing_x, start_y + row * spacing_y)

    def _assign_cells(self):
        """生成每个图标占用的格子（一键一格，无重叠），返回 {名: (x,y)}"""
        occupied = set()
        cells: Dict[str, tuple] = {}
        # 已保存位置的图标优先占用
        for icon in self.desktop_icons:
            if icon.name in self._icon_positions:
                p = self._icon_positions[icon.name]
                key = (p.x(), p.y())
                cells[icon.name] = key
                occupied.add(key)
        # 其余图标自动填入空余格子（列优先）
        idx = 0
        for icon in self.desktop_icons:
            if icon.name in cells:
                continue
            while True:
                cand = self._default_pos(idx)
                idx += 1
                key = (cand.x(), cand.y())
                if key not in occupied:
                    cells[icon.name] = key
                    occupied.add(key)
                    break
        return cells

    def _cell_map(self):
        """别名：返回 {图标名: 格子坐标(tuple)}，与渲染一致"""
        return self._assign_cells()

    def _icon_rect(self, pos: QPoint, spacing_x, spacing_y, icon_size):
        """由图标左上角位置构建画布矩形"""
        return QRect(pos.x(), pos.y(), spacing_x - 8, spacing_y - 8)

    # ---------- 图标排序持久化 ----------

    def _order_file(self):
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data",
            "desktop_icons.json")

    def _load_positions(self):
        """读取已保存的图标自由摆放位置 {name: [x, y]}"""
        try:
            with open(self._order_file(), "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                raw = data.get("positions", {})
                out = {}
                for name, xy in raw.items():
                    if isinstance(xy, (list, tuple)) and len(xy) == 2:
                        out[str(name)] = QPoint(int(xy[0]), int(xy[1]))
                return out
            return {}
        except Exception:
            return {}

    def _save_order(self):
        """保存当前图标自由摆放位置"""
        try:
            os.makedirs(os.path.dirname(self._order_file()), exist_ok=True)
            payload = {
                "positions": {name: [p.x(), p.y()]
                              for name, p in self._icon_positions.items()},
            }
            with open(self._order_file(), "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[DESKTOP] 保存图标位置失败: {e}")

    def restore_positions(self):
        """恢复上次保存的自由摆放位置"""
        self._icon_positions = self._load_positions()

    def paintEvent(self, event):
        """绘制桌面背景 (Windows 11 风格蓝色波浪壁纸)"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 基础背景：深蓝渐变
        base = QLinearGradient(0, 0, self.width(), self.height())
        base.setColorAt(0.0, QColor(0, 30, 80))
        base.setColorAt(0.5, QColor(0, 60, 140))
        base.setColorAt(1.0, QColor(0, 20, 60))
        painter.fillRect(self.rect(), QBrush(base))

        # Win11 风格蓝色波浪丝带
        self._draw_win11_waves(painter)

        # 绘制桌面图标并保存位置
        self._icon_rects.clear()
        self._draw_desktop_icons(painter)

    def _draw_win11_waves(self, painter: QPainter):
        """绘制 Windows 11 风格的层叠蓝色波浪"""
        w, h = self.width(), self.height()
        painter.setPen(Qt.PenStyle.NoPen)

        waves = [
            {"cx": 0.62, "cy": 0.55, "rx": 0.55, "ry": 0.45,
             "c1": QColor(0, 120, 215, 220), "c2": QColor(0, 70, 170, 180)},
            {"cx": 0.50, "cy": 0.62, "rx": 0.50, "ry": 0.40,
             "c1": QColor(0, 150, 235, 200), "c2": QColor(0, 90, 190, 160)},
            {"cx": 0.58, "cy": 0.70, "rx": 0.45, "ry": 0.35,
             "c1": QColor(20, 170, 250, 180), "c2": QColor(0, 110, 200, 140)},
            {"cx": 0.45, "cy": 0.78, "rx": 0.40, "ry": 0.30,
             "c1": QColor(40, 190, 255, 160), "c2": QColor(10, 130, 210, 120)},
        ]

        for wv in waves:
            cx = int(w * wv["cx"])
            cy = int(h * wv["cy"])
            rx = int(w * wv["rx"])
            ry = int(h * wv["ry"])

            grad = QRadialGradient(cx, cy, max(rx, ry))
            grad.setColorAt(0.0, wv["c1"])
            grad.setColorAt(1.0, wv["c2"])
            painter.setBrush(QBrush(grad))

            path = QPainterPath()
            rect = QRectF(cx - rx, cy - ry, rx * 2, ry * 2)
            # 用椭圆近似波浪丝带，层叠产生流动感
            path.addEllipse(rect)
            painter.drawPath(path)

        # 顶层亮带高光
        hi = QLinearGradient(0, int(h * 0.4), 0, int(h * 0.55))
        hi.setColorAt(0.0, QColor(120, 200, 255, 60))
        hi.setColorAt(1.0, QColor(120, 200, 255, 0))
        painter.fillRect(self.rect(), QBrush(hi))

    def _draw_desktop_icons(self, painter: QPainter):
        """绘制桌面图标，默认自上而下排列（每列最多 8 个），一格一图标"""
        _, rows, spacing_x, spacing_y, start_x, start_y, icon_size = \
            self._layout_params()

        # 计算每个图标对应的格子（一键一格，无重叠）
        cells = self._assign_cells()
        dragged_name = None
        if self._dragging and self._drag_index is not None:
            dragged_name = self._icon_names()[self._drag_index]

        self._icon_rects.clear()
        for icon in self.desktop_icons:
            if icon.name == dragged_name:
                continue  # 被拖动的图标单独绘制
            x, y = cells[icon.name]
            self._draw_icon_at(painter, icon, QPoint(x, y),
                               spacing_x, spacing_y, icon_size)

        # 绘制随鼠标浮动的被拖动图标
        if dragged_name is not None:
            icon = self.desktop_icons[self._drag_index]
            self._draw_icon_at(painter, icon, QPoint(self._drag_pos),
                               spacing_x, spacing_y, icon_size,
                               selected=False, alpha=200)

    def _draw_icon_at(self, painter, icon, pos, spacing_x, spacing_y,
                      icon_size, selected=None, alpha=None):
        """在指定位置绘制单个图标（含选中高亮）"""
        x, y = pos.x(), pos.y()
        cell_rect = QRect(x, y, spacing_x - 8, spacing_y - 8)
        icon_rect = QRect(x + (cell_rect.width() - icon_size) // 2,
                          y + 6, icon_size, icon_size)
        text_rect = QRect(x, y + icon_size + 10, cell_rect.width(), 36)

        if selected is None:
            selected = (self.selected == icon.name)

        # 选中高亮（半透明圆角方框）
        if selected:
            painter.setPen(QPen(QColor(255, 255, 255, 90), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255, 45)))
            painter.drawRoundedRect(cell_rect, 8, 8)

        self._icon_rects.append((icon.name, cell_rect))
        self._draw_single_icon(painter, icon, cell_rect, icon_rect,
                               text_rect, icon_size, alpha=alpha)

    def _draw_single_icon(self, painter, icon, cell_rect, icon_rect,
                          text_rect, icon_size, alpha=None):
        """绘制单个图标（图片或回退）+ 名称文字"""
        x, y = cell_rect.x(), cell_rect.y()
        if icon.icon_file:
            from apps import get_icon_pixmap
            pix = get_icon_pixmap(icon.icon_file, icon_size)
            if pix:
                if alpha is not None and alpha < 255:
                    tmp = QPixmap(pix)
                    tp = QPainter(tmp)
                    tp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    tp.fillRect(tmp.rect(), QColor(255, 255, 255, alpha))
                    tp.end()
                    pix = tmp
                px = x + (cell_rect.width() - pix.width()) // 2
                py = y + 6 + (icon_size - pix.height()) // 2
                painter.drawPixmap(px, py, pix)
            else:
                self._draw_fallback_icon(painter, icon, icon_rect, sym=icon.icon_text[:2])
        else:
            self._draw_fallback_icon(painter, icon, icon_rect, sym=icon.icon_text[:2])

        # 名称（白色，带阴影，自动换行）
        font = QFont("Microsoft YaHei UI", 9)
        painter.setFont(font)
        painter.setPen(QPen(QColor(0, 0, 0, 160)))
        painter.drawText(text_rect.adjusted(1, 1, 1, 1),
                         Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop |
                         Qt.TextFlag.TextWordWrap, icon.name)
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(text_rect,
                         Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop |
                         Qt.TextFlag.TextWordWrap, icon.name)

    def _draw_fallback_icon(self, painter: QPainter, icon, icon_rect, sym: str):
        """绘制无图片时的回退图标（彩色圆角方块 + 文字符号）"""
        bg = QColor(icon.color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(icon_rect, 8, 8)

        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont("Segoe UI Emoji", 22, QFont.Weight.Bold)
        painter.setFont(font)
        if not sym:
            sym = icon.name[:1] if icon.name else "▢"
        painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, sym)


class Taskbar(QFrame):
    """任务栏 (Windows 11 风格：居中、亚克力背景)"""

    context_action = pyqtSignal(str)  # 任务栏右键菜单动作
    hidden_tray_clicked = pyqtSignal()  # 点击隐藏托盘（⌃）按钮

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet("""
            Taskbar {
                background-color: rgba(30, 30, 40, 200);
                border-top: 1px solid rgba(255, 255, 255, 15);
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 左侧弹性空间（让中间组居中）
        layout.addStretch(1)

        # === 居中组：开始 + 搜索 + 固定应用 + 运行中应用 ===
        center = QWidget()
        center_layout = QHBoxLayout(center)
        center_layout.setContentsMargins(0, 4, 0, 4)
        center_layout.setSpacing(2)

        # 开始按钮（Windows 四格图标）
        self.start_button = QPushButton()
        self.start_button.setFixedSize(40, 40)
        self.start_button.setToolTip("开始")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 15);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 25);
            }
        """)
        self.start_button.paintEvent = self._paint_win_logo
        center_layout.addWidget(self.start_button)

        # 搜索按钮
        self.search_button = QPushButton("🔍")
        self.search_button.setFixedSize(40, 40)
        self.search_button.setToolTip("搜索")
        self.search_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 15);
            }
        """)
        center_layout.addWidget(self.search_button)

        # 固定应用分隔
        sep1 = QFrame()
        sep1.setFixedWidth(1)
        sep1.setStyleSheet("background-color: rgba(255,255,255,20); margin: 6px 4px;")
        center_layout.addWidget(sep1)

        # 固定应用区
        self.pinned_layout = QHBoxLayout()
        self.pinned_layout.setSpacing(2)
        center_layout.addLayout(self.pinned_layout)

        # 运行中应用分隔
        sep2 = QFrame()
        sep2.setFixedWidth(1)
        sep2.setStyleSheet("background-color: rgba(255,255,255,20); margin: 6px 4px;")
        center_layout.addWidget(sep2)

        # 运行中应用区
        self.task_buttons_layout = QHBoxLayout()
        self.task_buttons_layout.setSpacing(2)
        center_layout.addLayout(self.task_buttons_layout)

        layout.addWidget(center)

        # 右侧弹性空间（配合左侧，使中间组严格居中）
        layout.addStretch(1)

        # === 系统托盘（右侧）===
        self.system_tray = QWidget()
        tray_layout = QHBoxLayout(self.system_tray)
        tray_layout.setContentsMargins(8, 0, 12, 0)
        tray_layout.setSpacing(6)

        tray_btn_style = """
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 5px;
                color: #ffffff;
                font-size: 14px;
                padding: 0 4px;
            }
            QPushButton:hover { background-color: rgba(255,255,255,15); }
        """

        self.chevron_btn = QPushButton("⌃")
        self.chevron_btn.setFixedSize(24, 32)
        self.chevron_btn.setStyleSheet(tray_btn_style)
        self._chevron_base_style = tray_btn_style
        self.chevron_btn.setToolTip("隐藏托盘（后台运行的程序）")
        self.chevron_btn.clicked.connect(self.hidden_tray_clicked.emit)
        tray_layout.addWidget(self.chevron_btn)

        self.wifi_btn = QPushButton("📶")
        self.wifi_btn.setFixedSize(28, 32)
        self.wifi_btn.setStyleSheet(tray_btn_style)
        tray_layout.addWidget(self.wifi_btn)

        self.volume_btn = QPushButton("🔊")
        self.volume_btn.setFixedSize(28, 32)
        self.volume_btn.setStyleSheet(tray_btn_style)
        tray_layout.addWidget(self.volume_btn)

        self.battery_btn = QPushButton("🔋")
        self.battery_btn.setFixedSize(28, 32)
        self.battery_btn.setStyleSheet(tray_btn_style)
        tray_layout.addWidget(self.battery_btn)

        # 时钟（显示 时间 + 日期，两行）
        self.clock_label = QLabel()
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.clock_label.setStyleSheet("""
            color: #ffffff;
            font-size: 11px;
            font-family: Segoe UI;
            background: transparent;
            padding: 0 6px;
        """)
        self.clock_label.setFixedHeight(40)
        tray_layout.addWidget(self.clock_label)

        # 更新时钟
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

        layout.addWidget(self.system_tray)

        self.window_buttons: List[TaskbarButton] = []
        self.net_label = self.wifi_btn  # 兼容旧引用

    def contextMenuEvent(self, event):
        """任务栏右键菜单 (Windows 11 风格)"""
        from system.context_menu import build_menu, load_menus

        items = load_menus().get("taskbar", [])
        menu = build_menu(items, self, self.context_action.emit)
        menu.exec(event.globalPos())
        event.accept()

    def _paint_win_logo(self, event):
        """绘制 Windows 11 logo 图片作为开始按钮图标"""
        from apps import get_icon_pixmap
        pix = get_icon_pixmap("Windows11-LOGO.png", 18)
        if pix and not pix.isNull():
            painter = QPainter(self.start_button)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            x = (self.start_button.width() - pix.width()) // 2
            y = (self.start_button.height() - pix.height()) // 2
            painter.drawPixmap(x, y, pix)
            painter.end()
            return
        # 回退：绘制 Windows 四格 logo
        painter = QPainter(self.start_button)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        size = 18
        x = (self.start_button.width() - size) // 2
        y = (self.start_button.height() - size) // 2
        gap = 2
        cell = (size - gap) // 2
        colors = [
            QColor(0, 120, 215), QColor(0, 150, 235),
            QColor(0, 90, 190),  QColor(0, 110, 210),
        ]
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(4):
            r, c = i // 2, i % 2
            painter.setBrush(QBrush(colors[i]))
            painter.drawRoundedRect(
                QRect(x + c * (cell + gap), y + r * (cell + gap), cell, cell), 1, 1)

    def _update_clock(self):
        """更新时钟显示（时间 + 日期）"""
        t = time.strftime("%H:%M")
        d = time.strftime("%Y/%m/%d")
        self.clock_label.setText(f"{t}\n{d}")

    def add_window_button(self, title: str, icon_file: str = "") -> TaskbarButton:
        """添加窗口按钮"""
        btn = TaskbarButton(title, icon_file=icon_file)
        self.task_buttons_layout.addWidget(btn)
        self.window_buttons.append(btn)
        return btn

    def remove_window_button(self, btn: TaskbarButton):
        """移除窗口按钮"""
        self.task_buttons_layout.removeWidget(btn)
        if btn in self.window_buttons:
            self.window_buttons.remove(btn)
        btn.deleteLater()

    def set_hidden_count(self, n: int):
        """更新隐藏托盘（后台运行程序）数量显示"""
        base = getattr(self, "_chevron_base_style", "")
        if n > 0:
            self.chevron_btn.setText("⌃")
            self.chevron_btn.setStyleSheet(base + " color:#00e5a0; font-weight:bold;")
            self.chevron_btn.setToolTip(f"隐藏托盘（{n} 个程序在后台运行）")
        else:
            self.chevron_btn.setText("⌃")
            self.chevron_btn.setStyleSheet(base)
            self.chevron_btn.setToolTip("隐藏托盘（后台运行的程序）")


class AppWindowFrame(QWidget):
    """
    应用程序窗口框架
    提供标题栏、关闭/最小化/最大化按钮、拖拽功能、边缘调整大小
    """

    closed = pyqtSignal()
    hide_to_tray_requested = pyqtSignal()  # 请求隐藏到后台托盘

    RESIZE_MARGIN = 6  # 边缘检测区域宽度

    def __init__(self, title: str, content: QWidget, parent=None):
        super().__init__(parent)
        self.title_text = title
        self.content_widget = content
        self._drag_pos = None
        self._resize_mode = None   # 当前调整大小的方向
        self._resize_start_pos = None
        self._resize_start_rect = None
        
        # 窗口样式 - 无系统装饰，独立顶层窗口
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        # 允许透明背景，使圆角真正生效（四角透出桌面）
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)  # 允许无按键时跟踪鼠标
        
        # 强制背景色，防止白框
        self.setStyleSheet("""
            AppWindowFrame {
                background-color: #1a1a2e;
                border: 1px solid rgba(0, 212, 255, 0.3);
                border-radius: 8px;
            }
        """)
        # 使用 palette 确保无白框
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(26, 26, 46))
        self.setPalette(palette)
        # 关闭自动填充，避免方形实心底遮挡圆角
        self.setAutoFillBackground(False)
        
        # 动画相关
        self.taskbar_button = None          # 关联的任务栏按钮（用于动画原点）
        self._open_anim: Optional[QParallelAnimationGroup] = None
        self._close_anim: Optional[QParallelAnimationGroup] = None
        self._anim_origin = QPoint()        # 动画缩放原点（任务栏位置）
        
        self._setup_ui()

    # ---------- Win11 风格 打开/关闭 动画 ----------

    def set_anim_origin(self, point: QPoint):
        """设置动画原点（任务栏图标位置）"""
        self._anim_origin = point

    def _stop_animations(self):
        if self._open_anim and self._open_anim.state() == \
                QParallelAnimationGroup.State.Running:
            self._open_anim.stop()
        if self._close_anim and self._close_anim.state() == \
                QParallelAnimationGroup.State.Running:
            self._close_anim.stop()

    def play_open_animation(self, final_geometry: QRect):
        """Win11 风格打开动画：从下方(窗口底边)向上展开 + 淡入"""
        self._stop_animations()
        self.setWindowOpacity(0.0)
        f = final_geometry
        # 从窗口底边的一条线向上展开（X/宽度固定，因此不会产生斜向位移）
        start = QRect(f.x(), f.bottom(), f.width(), 1)
        self.setGeometry(start)
        self.show()
        self.raise_()

        anims = QParallelAnimationGroup(self)
        geo = QPropertyAnimation(self, b"geometry")
        geo.setDuration(280)
        geo.setStartValue(start)
        geo.setEndValue(f)
        geo.setEasingCurve(QEasingCurve.Type.OutCubic)

        op = QPropertyAnimation(self, b"windowOpacity")
        op.setDuration(280)
        op.setStartValue(0.0)
        op.setEndValue(1.0)
        op.setEasingCurve(QEasingCurve.Type.OutCubic)

        anims.addAnimation(geo)
        anims.addAnimation(op)
        anims.finished.connect(lambda: self.setWindowOpacity(1.0))
        self._open_anim = anims
        anims.start()

    def play_close_animation(self):
        """Win11 风格关闭动画：向下收拢(缩到窗口底边) + 淡出"""
        self._stop_animations()
        current = self.frameGeometry()
        # 向下收拢：X/宽度固定，高度收为一条线（不产生斜向位移）
        target = QRect(current.x(), current.bottom(), current.width(), 1)

        anims = QParallelAnimationGroup(self)
        geo = QPropertyAnimation(self, b"geometry")
        geo.setDuration(200)
        geo.setStartValue(current)
        geo.setEndValue(target)
        geo.setEasingCurve(QEasingCurve.Type.InCubic)

        op = QPropertyAnimation(self, b"windowOpacity")
        op.setDuration(200)
        op.setStartValue(self.windowOpacity())
        op.setEndValue(0.0)
        op.setEasingCurve(QEasingCurve.Type.InCubic)

        anims.addAnimation(geo)
        anims.addAnimation(op)
        anims.finished.connect(self._finish_close)
        self._close_anim = anims
        anims.start()

    def _finish_close(self):
        self.setWindowOpacity(1.0)
        self.hide()
        self.closed.emit()

    def _setup_ui(self):
        """设置UI - 无白框，内容自动填满"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)  # 仅留1px防止边框重叠
        layout.setSpacing(0)

        # ===== 标题栏 =====
        title_bar = QWidget()
        title_bar.setFixedHeight(34)
        title_bar.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 25, 50, 240);
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                border: none;
                border-bottom: 1px solid #334466;
            }
        """)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(12, 0, 6, 0)

        # 标题
        title_label = QLabel(self.title_text)
        title_label.setFont(QFont("Microsoft YaHei", 10))
        title_label.setStyleSheet("color: #ffffff; background: transparent;")
        title_layout.addWidget(title_label, 1)

        # 窗口控制按钮样式
        btn_style = """
            QPushButton {
                background-color: transparent;
                color: #cccccc;
                border: none;
                font-size: 13px;
                padding: 2px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
                color: #ffffff;
            }
        """

        hide_btn = QPushButton("⤓")
        hide_btn.setStyleSheet(btn_style)
        hide_btn.setFixedSize(30, 26)
        hide_btn.setToolTip("后台运行（隐藏到托盘）")
        hide_btn.clicked.connect(self.hide_to_tray_requested.emit)
        title_layout.addWidget(hide_btn)

        min_btn = QPushButton("─")
        min_btn.setStyleSheet(btn_style)
        min_btn.setFixedSize(36, 26)
        min_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(min_btn)

        max_btn = QPushButton("□")
        max_btn.setStyleSheet(btn_style)
        max_btn.setFixedSize(36, 26)
        max_btn.clicked.connect(self._toggle_maximize)
        title_layout.addWidget(max_btn)

        close_btn = QPushButton("✕")
        close_btn.setStyleSheet(btn_style + """
            QPushButton:hover { background-color: #e81123; color: white; }
        """)
        close_btn.setFixedSize(36, 26)
        close_btn.clicked.connect(self.close_window)
        title_layout.addWidget(close_btn)

        layout.addWidget(title_bar)

        # ===== 内容区域 =====
        content_container = QWidget()
        content_container.setStyleSheet("""
            QWidget {
                background-color: #1a1a2e;
                border: none;
                border-bottom-left-radius: 7px;
                border-bottom-right-radius: 7px;
            }
        """)
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        # ★ 关键：stretch=1 让内容控件填满整个容器
        content_layout.addWidget(self.content_widget, 1)

        layout.addWidget(content_container, 1)

        # 拖拽标题栏
        title_bar.mousePressEvent = self._title_mouse_press
        title_bar.mouseMoveEvent = self._title_mouse_move
        title_bar.mouseReleaseEvent = self._title_mouse_release

    # ---------- 窗口拖拽（标题栏） ----------

    def _title_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _title_mouse_move(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def _title_mouse_release(self, event):
        self._drag_pos = None

    # ---------- 窗口调整大小（边缘拖拽） ----------

    def _get_resize_mode(self, pos) -> str | None:
        """根据鼠标位置判断调整方向"""
        r = self.rect()
        margin = self.RESIZE_MARGIN
        x, y = pos.x(), pos.y()

        on_left   = x <= margin
        on_right  = x >= r.width() - margin
        on_top    = y <= margin
        on_bottom = y >= r.height() - margin

        # 四角优先
        if on_top and on_left:
            return "top-left"
        if on_top and on_right:
            return "top-right"
        if on_bottom and on_left:
            return "bottom-left"
        if on_bottom and on_right:
            return "bottom-right"
        if on_left:
            return "left"
        if on_right:
            return "right"
        if on_top:
            return "top"
        if on_bottom:
            return "bottom"
        return None

    def _resize_cursor(self, mode: str | None):
        """根据调整方向设置鼠标样式"""
        cursors = {
            "top-left":     Qt.CursorShape.SizeFDiagCursor,
            "bottom-right": Qt.CursorShape.SizeFDiagCursor,
            "top-right":    Qt.CursorShape.SizeBDiagCursor,
            "bottom-left":  Qt.CursorShape.SizeBDiagCursor,
            "left":         Qt.CursorShape.SizeHorCursor,
            "right":        Qt.CursorShape.SizeHorCursor,
            "top":          Qt.CursorShape.SizeVerCursor,
            "bottom":       Qt.CursorShape.SizeVerCursor,
        }
        self.setCursor(cursors.get(mode, Qt.CursorShape.ArrowCursor))

    def mousePressEvent(self, event):
        """按下鼠标：开始调整大小"""
        if event.button() == Qt.MouseButton.LeftButton:
            mode = self._get_resize_mode(event.position().toPoint())
            if mode:
                self._resize_mode = mode
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_rect = self.frameGeometry()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """移动鼠标：调整大小或更新光标"""
        pos = event.position().toPoint()

        if self._resize_mode and event.buttons() & Qt.MouseButton.LeftButton:
            # 正在拖动调整大小
            global_pos = event.globalPosition().toPoint()
            dx = global_pos.x() - self._resize_start_pos.x()
            dy = global_pos.y() - self._resize_start_pos.y()

            start_rect = self._resize_start_rect
            x, y, w, h = start_rect.x(), start_rect.y(), start_rect.width(), start_rect.height()

            mode = self._resize_mode
            if "left" in mode:
                x = start_rect.x() + dx
                w = start_rect.width() - dx
            if "right" in mode:
                w = start_rect.width() + dx
            if "top" in mode:
                y = start_rect.y() + dy
                h = start_rect.height() - dy
            if "bottom" in mode:
                h = start_rect.height() + dy

            # 最小尺寸限制
            MIN_W, MIN_H = 400, 300
            if w < MIN_W:
                w = MIN_W
                if "left" in mode:
                    x = start_rect.right() - MIN_W
            if h < MIN_H:
                h = MIN_H
                if "top" in mode:
                    y = start_rect.bottom() - MIN_H

            self.setGeometry(x, y, w, h)
            event.accept()
            return
        else:
            # 悬停时更新光标
            mode = self._get_resize_mode(pos)
            self._resize_cursor(mode)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """释放鼠标：结束调整大小"""
        if event.button() == Qt.MouseButton.LeftButton and self._resize_mode:
            self._resize_mode = None
            self._resize_start_pos = None
            self._resize_start_rect = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def close_window(self):
        self.play_close_animation()


class DesktopEnvironment(QMainWindow):
    """
    TianOS 桌面环境
    包含桌面、任务栏、窗口管理器
    """

    def __init__(self):
        super().__init__()
        
        # 窗口设置
        self.setWindowTitle("TianOS Desktop")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        screen = QApplication.primaryScreen()
        if screen:
            screen_rect = screen.geometry()
            self.screen_width = screen_rect.width()
            self.screen_height = screen_rect.height()
        else:
            self.screen_width = 1280
            self.screen_height = 720
        
        self.setGeometry(0, 0, self.screen_width, self.screen_height)
        
        # 组件
        self.desktop = DesktopWidget()
        self.taskbar = Taskbar()
        
        # 开始菜单
        self.start_menu = StartMenu(self)
        self.start_menu.app_launch.connect(self._on_icon_clicked)
        self.start_menu.shutdown_signal.connect(self._power_action)
        
        # 运行框 (Ctrl+R)
        self.run_dialog = RunDialog(self)
        self.run_dialog.set_launch_callback(self._run_command)
        
        # 窗口管理
        self.open_windows: List[AppWindow] = []
        self.window_z_index = 0

        # 隐藏托盘（后台运行的程序）
        self._hidden_windows: List[AppWindow] = []
        
        # 主布局
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 桌面区域
        main_layout.addWidget(self.desktop, 1)
        
        # 任务栏
        main_layout.addWidget(self.taskbar)
        
        self.setCentralWidget(main_widget)
        
        # 连接开始按钮
        self.taskbar.start_button.clicked.connect(self._toggle_start_menu)

        # 监听全局鼠标点击：点击菜单外部时关闭开始菜单
        QApplication.instance().installEventFilter(self)

        # 全局快捷键 Ctrl+F4：关闭当前应用窗口；无窗口时弹出关机提示
        from PyQt6.QtGui import QShortcut, QKeySequence
        sc_f4 = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_F4), self)
        sc_f4.setContext(Qt.ShortcutContext.ApplicationShortcut)
        sc_f4.activated.connect(self._handle_ctrl_f4)
        
        # 连接桌面图标点击信号
        self.desktop.icon_clicked.connect(self._on_icon_clicked)
        self.desktop.context_action.connect(self._handle_context_action)
        
        # 连接任务栏右键菜单
        self.taskbar.context_action.connect(self._handle_taskbar_action)

        # 点击隐藏托盘（⌃）按钮：弹出后台运行程序列表
        self.taskbar.hidden_tray_clicked.connect(self._open_hidden_tray)
        
        # 初始化桌面图标
        self._init_desktop_icons()

        # 将所有已安装应用注册到虚拟注册表
        try:
            from apps import register_all_apps
            register_all_apps()
        except Exception as e:
            print(f"[REG] 应用注册失败: {e}")

    def _on_icon_clicked(self, icon_name: str):
        """桌面图标点击处理 - 通过快捷方式解析目标应用并启动"""
        from apps import app_registry, resolve_shortcut, desktop_folder_path

        widget = None
        shortcut = resolve_shortcut(icon_name)
        if shortcut:
            # 快捷方式指向 apps/ 中的模块
            widget = app_registry.launch(shortcut.target)
            title = shortcut.name
        else:
            # 用户新建的文件夹 → 用文件管理器打开
            folder_path = desktop_folder_path(icon_name)
            if folder_path is not None:
                from apps.file_manager import FileManager
                fm = FileManager()
                fm._navigate(folder_path)
                widget = fm
                title = icon_name
            else:
                # 兼容直接按应用显示名启动（如运行框传入）
                widget = app_registry.launch_by_name(icon_name)
                title = icon_name

        if widget:
            self.open_application(widget, title)

    def _run_command(self, app_name, raw_cmd=None):
        """运行框/终端命令解析后启动应用"""
        if self.run_dialog and self.run_dialog.isVisible():
            self.run_dialog.hide()
        if app_name:
            self._on_icon_clicked(app_name)
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "运行",
                f"未找到程序: '{raw_cmd}'\n\n可用: regedit, taskmgr, explorer, gpedit, "
                f"settings, 终端, 系统信息, 网络工具, 关于 等",
            )

    @staticmethod
    def _system_root():
        import os
        return os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".."))

    def _unique_path(self, base):
        import os
        if not os.path.exists(base):
            return base
        root, ext = os.path.splitext(base)
        i = 1
        while True:
            cand = f"{root} ({i}){ext}"
            if not os.path.exists(cand):
                return cand
            i += 1

    def _handle_context_action(self, action: str, icon_name: str):
        """处理桌面右键菜单动作"""
        import os
        from system.context_menu import get_clipboard, set_clipboard
        from PyQt6.QtWidgets import QMessageBox

        if action == "settings":
            self._on_icon_clicked("设置")
            return
        if action == "terminal":
            self._on_icon_clicked("终端")
            return
        if action == "refresh":
            self._init_desktop_icons()
            return

        if action == "new_folder":
            from apps import create_desktop_folder
            folder = create_desktop_folder("新建文件夹")
            self._init_desktop_icons()
            # 选中新建的文件夹
            self.desktop.selected = os.path.basename(folder)
            self.desktop.update()
            return
        if action == "new_text":
            path = self._unique_path(os.path.join(self._system_root(), "新建文本文档.txt"))
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
            QMessageBox.information(self, "新建文件", f"已创建:\n{path}")
            return
        if action == "paste":
            src, mode = get_clipboard()
            if not src or not os.path.exists(src):
                QMessageBox.information(self, "粘贴", "剪贴板中没有可粘贴的文件。")
                return
            dst = os.path.join(self._system_root(), os.path.basename(src))
            dst = self._unique_path(dst)
            try:
                if os.path.isdir(src):
                    import shutil
                    shutil.copytree(src, dst)
                else:
                    import shutil
                    shutil.copy2(src, dst)
                QMessageBox.information(self, "粘贴", f"已粘贴到:\n{dst}")
            except Exception as e:
                QMessageBox.warning(self, "粘贴失败", str(e))
            return

        # 其余动作针对图标使用 resolve_shortcut
        if action in ("copy", "cut", "rename", "delete", "properties", "open", "edit") and icon_name:
            import shutil
            from apps import resolve_shortcut, desktop_folder_path
            sc = resolve_shortcut(icon_name)
            # 非快捷方式（用户新建的文件夹）→ 定位到真实文件夹路径
            folder_path = None
            if sc is None:
                folder_path = desktop_folder_path(icon_name)
                if folder_path is None:
                    # 既不是快捷方式也不是文件夹，无法定位
                    return

            if action in ("open", "edit"):
                self._on_icon_clicked(icon_name)
            elif action in ("copy", "cut"):
                src = sc.file_path if sc else folder_path
                set_clipboard(src, action)
                label = "复制" if action == "copy" else "剪切"
                QMessageBox.information(self, label, f"已{label}:\n{sc.name if sc else icon_name}")
            elif action == "delete":
                path = sc.file_path if sc else folder_path
                if not path or not os.path.exists(path):
                    QMessageBox.information(self, "删除", "无法定位目标。")
                    return
                display = sc.name if sc else icon_name
                if QMessageBox.question(self, "删除", f"确定删除“{display}”吗？") == QMessageBox.StandardButton.Yes:
                    try:
                        if os.path.isdir(path):
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                        self._init_desktop_icons()
                    except Exception as e:
                        QMessageBox.warning(self, "删除失败", str(e))
            elif action == "properties":
                path = sc.file_path if sc else folder_path
                info = (
                    f"名称: {sc.name}\n目标应用: {sc.target}\n"
                    f"快捷方式文件: {path}\n"
                    if sc else
                    f"名称: {icon_name}\n类型: 文件夹\n路径: {path}\n"
                )
                QMessageBox.information(
                    self, f"{sc.name if sc else icon_name} - 属性", info)
            return

    def _handle_taskbar_action(self, action: str):
        """处理任务栏右键菜单动作"""
        from PyQt6.QtWidgets import QMessageBox

        if action == "run":
            self._show_run_dialog()
            return
        if action in ("settings", "terminal", "task_manager", "system_info"):
            display_name = {
                "settings": "设置",
                "terminal": "终端",
                "task_manager": "任务管理器",
                "system_info": "系统信息",
            }[action]
            self._on_icon_clicked(display_name)
            return
        if action == "taskbar_settings":
            QMessageBox.information(self, "任务栏设置",
                                    "任务栏预览模式\n\n"
                                    "任务栏行为、系统托盘等自定义设置\n"
                                    "敬请期待后续版本。")
            return

    def keyPressEvent(self, event):
        """全局快捷键: Ctrl+R 呼出运行框"""
        if (event.key() == Qt.Key.Key_R and
                event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self._show_run_dialog()
            return
        super().keyPressEvent(event)

    def _show_run_dialog(self):
        """显示运行框"""
        desktop_pos = self.mapToGlobal(self.desktop.pos())
        cx = desktop_pos.x() + self.desktop.width() // 2
        cy = desktop_pos.y() + self.desktop.height() // 3
        self.run_dialog.show_at(cx, cy)

    def _init_desktop_icons(self):
        """从 programfiles/desktop 加载快捷方式与用户文件夹"""
        from apps import (load_desktop_shortcuts, load_desktop_folders,
                          FOLDER_ICON)

        shortcuts = load_desktop_shortcuts()
        self.desktop.desktop_icons = [
            DesktopIcon(sc.name, sc.icon, color=sc.color, icon_file=sc.icon_file)
            for sc in shortcuts
        ]
        # 用户新建的文件夹（imageres 154.png）
        for folder in load_desktop_folders():
            self.desktop.desktop_icons.append(
                DesktopIcon(folder, "📁", color="#e8a33d",
                            icon_file=FOLDER_ICON))
        # 恢复上次拖拽后的图标自由摆放位置
        self.desktop.restore_positions()

    def open_application(self, app_widget: QWidget, title: str):
        """打开应用窗口"""
        # 确保内容控件有合理的默认大小
        MIN_W = 800
        MIN_H = 600
        app_widget.setMinimumSize(MIN_W, MIN_H)
        
        # 创建窗口框架（独立顶层窗口，浮在桌面之上）
        window_frame = AppWindowFrame(title, app_widget)
        
        # 终端等支持启动其它应用时，连接其请求信号
        if hasattr(app_widget, "launch_requested"):
            app_widget.launch_requested.connect(self._run_command)
        
        # 计算屏幕坐标（居中于桌面主窗口）
        desktop_pos = self.mapToGlobal(self.desktop.pos())
        desktop_w = self.desktop.width()
        desktop_h = self.desktop.height()
        # 居中放置（多开时轻微偏移，避免完全重叠）
        n = len(self.open_windows)
        offset_x = desktop_pos.x() + (desktop_w - MIN_W) // 2 + n * 20
        offset_y = desktop_pos.y() + (desktop_h - MIN_H) // 2 + n * 20
        final_geometry = QRect(offset_x, offset_y, MIN_W, MIN_H)
        
        window = AppWindow(
            title=title,
            widget=window_frame,
            width=MIN_W,
            height=MIN_H,
            taskbar_button=None,
        )
        
        self.open_windows.append(window)
        
        # 解析应用图标文件（任务栏按钮使用）
        from apps import resolve_shortcut
        sc = resolve_shortcut(title)
        icon_file = sc.icon_file if sc else ""
        window.icon_file = icon_file
        
        # 添加任务栏按钮
        btn = self.taskbar.add_window_button(title, icon_file)
        btn.clicked.connect(lambda checked, w=window, b=btn: self._toggle_window(w, b))
        window.taskbar_button = btn
        
        # 设置动画原点：任务栏按钮中心，实现 Win11 式打开/关闭动画
        btn_center = btn.mapToGlobal(btn.rect().center())
        window_frame.set_anim_origin(btn_center)
        window_frame.taskbar_button = btn
        
        # 窗口关闭时清理任务栏按钮
        window_frame.closed.connect(lambda: self._on_window_closed(window))

        # 标题栏"后台运行（隐藏到托盘）"按钮
        window_frame.hide_to_tray_requested.connect(
            lambda: self._hide_to_tray(window))
        
        # 打开动画（从窗口底边向上展开 + 淡入）
        window_frame.play_open_animation(final_geometry)
        # 任务栏图标跳动（Win11 打开提示）
        btn.jump()

    def _on_window_closed(self, window: AppWindow):
        """窗口关闭回调"""
        if window in self.open_windows:
            self.open_windows.remove(window)
        # 若正在后台托盘运行，则同时移除并刷新计数
        if window in self._hidden_windows:
            self._hidden_windows.remove(window)
        # 移除任务栏按钮
        if window.taskbar_button:
            self.taskbar.remove_window_button(window.taskbar_button)
            window.taskbar_button = None
        self._update_hidden_tray()

    # ---------- 隐藏托盘（后台运行） ----------

    def _update_hidden_tray(self):
        """刷新隐藏托盘按钮上的后台程序数量"""
        self.taskbar.set_hidden_count(len(self._hidden_windows))

    def _hide_to_tray(self, window: AppWindow):
        """将窗口最小化到后台托盘继续运行"""
        if window not in self.open_windows or window in self._hidden_windows:
            return
        if window.widget:
            window.widget.hide()  # 隐藏窗口，程序继续在后台运行
            window.minimized = True
        # 移除任务栏按钮，进入隐藏托盘
        if window.taskbar_button:
            self.taskbar.remove_window_button(window.taskbar_button)
            window.taskbar_button = None
            window.widget.taskbar_button = None
        self._hidden_windows.append(window)
        self._update_hidden_tray()

    def _restore_from_tray(self, window: AppWindow):
        """从后台托盘恢复窗口显示"""
        if window not in self._hidden_windows:
            return
        self._hidden_windows.remove(window)
        window.minimized = False
        # 重新添加任务栏按钮
        if window.widget and not window.taskbar_button:
            btn = self.taskbar.add_window_button(window.title, window.icon_file)
            btn.clicked.connect(
                lambda checked, w=window, b=btn: self._toggle_window(w, b))
            window.taskbar_button = btn
            window.widget.taskbar_button = btn
        # 重新显示窗口
        if window.widget:
            window.widget.show()
            window.widget.showNormal()
            window.widget.raise_()
        self._update_hidden_tray()

    def _restore_all_from_tray(self):
        """恢复所有后台托盘中的程序"""
        for window in list(self._hidden_windows):
            self._restore_from_tray(window)

    def _open_hidden_tray(self):
        """点击隐藏托盘按钮：列出所有后台运行的程序"""
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1c1c2e;
                border: 1px solid #334466;
                border-radius: 8px;
                padding: 6px;
                color: #ffffff;
                font-family: 'Microsoft YaHei';
            }
            QMenu::item { padding: 6px 18px; border-radius: 5px; }
            QMenu::item:selected { background-color: rgba(0, 212, 255, 0.2); }
            QMenu::separator { height: 1px; background: #334466; margin: 4px 8px; }
        """)
        if not self._hidden_windows:
            act = menu.addAction("（暂无后台运行的程序）")
            act.setEnabled(False)
        else:
            for w in self._hidden_windows:
                act = menu.addAction(f"⇪ {w.title}")
                act.triggered.connect(
                    lambda checked=False, win=w: self._restore_from_tray(win))
            menu.addSeparator()
            item = menu.addAction("全部恢复")
            item.triggered.connect(self._restore_all_from_tray)
        # 菜单显示在隐藏托盘按钮上方
        pos = self.taskbar.chevron_btn.mapToGlobal(QPoint(0, 0))
        menu.exec(pos + QPoint(0, -menu.sizeHint().height()))

    def _handle_ctrl_f4(self):
        """Ctrl+F4: 关闭当前应用窗口；若没有打开任何窗口则弹出关机提示"""
        target = None

        # 优先关闭当前激活（聚焦）的应用窗口
        active = QApplication.activeWindow()
        if active is not None:
            for w in self.open_windows:
                if w.widget is active:
                    target = w
                    break

        # 回退：焦点不在应用窗口时，关闭最近打开的一个
        if target is None and self.open_windows:
            target = self.open_windows[-1]

        if target is not None and target.widget is not None:
            # 若窗口处于最小化状态，先恢复正常以便播放关闭动画
            if target.widget.isMinimized():
                target.widget.showNormal()
            target.widget.close_window()
        else:
            # 没有打开的界面 → 弹出关机提示框
            self._power_action("shutdown")

    def _toggle_window(self, window: AppWindow, btn: TaskbarButton):
        """切换窗口显示状态"""
        if window.widget.isVisible():
            if window.widget.isMinimized():
                window.widget.showNormal()
            else:
                window.widget.showMinimized()
        else:
            window.widget.show()

    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        # 全屏显示
        self.showFullScreen()

    def eventFilter(self, obj, event):
        """点击开始菜单外部区域时关闭开始菜单"""
        if (event.type() == QEvent.Type.MouseButtonPress
                and self.start_menu.isVisible()):
            click_pos = event.globalPosition().toPoint()
            menu_geo = self.start_menu.frameGeometry()
            # 开始按钮所在区域（点击开始按钮由 _toggle_start_menu 处理，这里不拦截）
            btn = self.taskbar.start_button
            btn_rect = QRect(btn.mapToGlobal(btn.rect().topLeft()), btn.size())
            if not menu_geo.contains(click_pos) and not btn_rect.contains(click_pos):
                self.start_menu.hide()
        return super().eventFilter(obj, event)

    def _toggle_start_menu(self):
        """切换开始菜单显示 (Win11 风格：任务栏上方居中)"""
        if self.start_menu.isVisible():
            self.start_menu.hide()
        else:
            # 任务栏上方水平居中
            taskbar_geo = self.taskbar.geometry()
            global_pos = self.taskbar.mapToGlobal(
                QPoint((taskbar_geo.width() - self.start_menu.width()) // 2,
                       -self.start_menu.height()))
            self.start_menu.move(global_pos)
            self.start_menu.show()
            self.start_menu.raise_()
            self.start_menu.animate_in()

    def _power_action(self, action: str):
        """电源操作处理"""
        self.start_menu.hide()
        
        if action == "shutdown":
            self._show_power_dialog("关机", "⏻ 系统将在 3 秒后关闭...", "#ff4444", 
                                    lambda: sys.exit(0))
        elif action == "reboot":
            self._show_power_dialog("重启", "🔄 系统将在 3 秒后重启...", "#ff9900",
                                    lambda: [self.close(), QApplication.quit()])
        elif action == "sleep":
            self._show_power_dialog("睡眠", "💤 系统已进入睡眠状态\n点击任意位置唤醒", "#00ccff",
                                    lambda: None)

    def _show_power_dialog(self, title: str, message: str, color: str, callback):
        """显示电源操作对话框（非阻塞）"""
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog |
                           Qt.WindowType.WindowStaysOnTopHint)
        dlg.setFixedSize(380, 180)
        dlg.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        dlg.setStyleSheet(f"""
            QDialog {{
                background-color: rgba(12, 12, 35, 245);
                border: 2px solid {color};
                border-radius: 16px;
            }}
        """)
        
        layout = QVBoxLayout(dlg)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        layout.setContentsMargins(30, 20, 30, 20)
        
        # 标题
        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("Microsoft YaHei", 22, QFont.Weight.Bold))
        lbl_title.setStyleSheet(f"color: {color};")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)
        
        # 消息
        lbl_msg = QLabel(message)
        lbl_msg.setFont(QFont("Microsoft YaHei", 12))
        lbl_msg.setStyleSheet("color: #aaaaaa;")
        lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_msg)
        
        # 进度条
        from PyQt6.QtWidgets import QProgressBar
        progress = QProgressBar()
        progress.setRange(0, 30)
        progress.setValue(30)
        progress.setTextVisible(False)
        progress.setFixedHeight(4)
        progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255,255,255,0.05);
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(progress)
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(100, 32)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.08);
                color: #888888;
                border: 1px solid #334466;
                border-radius: 6px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.15);
                color: #cccccc;
            }
        """)
        cancel_btn.clicked.connect(dlg.close)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 居中显示
        dlg.move(
            self.screen_width // 2 - 190,
            self.screen_height // 2 - 90
        )
        dlg.show()
        
        # 倒计时进度动画
        self._power_countdown = 30
        timer = QTimer(dlg)
        timer.timeout.connect(lambda: self._update_power_progress(progress, timer, dlg, callback))
        timer.start(100)

    def _update_power_progress(self, progress, timer, dlg, callback):
        """更新电源操作倒计时"""
        self._power_countdown -= 1
        progress.setValue(self._power_countdown)
        if self._power_countdown <= 0:
            timer.stop()
            dlg.close()
            dlg.deleteLater()
            if callback:
                callback()


class StartMenu(QFrame):
    """开始菜单 (Windows 11 风格：固定应用网格 + 所有应用列表)"""

    app_launch = pyqtSignal(str)  # 启动应用信号
    shutdown_signal = pyqtSignal(str)  # 电源操作信号

    def __init__(self, parent=None):
        super().__init__(parent)
        # 使用普通工具窗口而非 Popup：Popup 在点击外部时会自动关闭，
        # 导致点击开始按钮无法关闭菜单（总是重新打开）。
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        # 允许透明背景，使开始菜单圆角真正生效
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.setFixedSize(560, 580)
        # 不透明背景（保留圆角所需的最小透明合成）
        self.setStyleSheet("""
            StartMenu {
                background-color: #1f2430;
                border: 1px solid rgba(255, 255, 255, 26);
                border-radius: 12px;
            }
        """)
        # 动画状态
        self._menu_anim: Optional[QParallelAnimationGroup] = None
        self._setup_ui()
        self._load_apps()

    def paintEvent(self, event):
        """手动绘制背景，保证在 WA_TranslucentBackground 下圆角背景始终生效。
        Windows + Qt6 下，QSS 设置在最顶层无边框 QFrame 的 background-color
        有几率不会被合成绘制，导致开始菜单透明、背景消失。这里用 QPainter 兜底。
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        # 背景
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        painter.fillPath(path, QBrush(QColor(31, 36, 48)))  # #1f2430
        # 边框
        painter.setPen(QPen(QColor(255, 255, 255, 26), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()

    def animate_in(self):
        """Win11 风格打开动画：从底部向上展开 + 淡入"""
        if self._menu_anim and self._menu_anim.state() == \
                QParallelAnimationGroup.State.Running:
            self._menu_anim.stop()
        final_geometry = self.frameGeometry()
        # 从底边一条线向上展开（X/宽度固定，不产生斜向位移）
        start = QRect(final_geometry.x(), final_geometry.bottom(),
                      final_geometry.width(), 1)
        self.setGeometry(start)
        self.setWindowOpacity(0.0)

        anims = QParallelAnimationGroup(self)
        geo = QPropertyAnimation(self, b"geometry")
        geo.setDuration(260)
        geo.setStartValue(start)
        geo.setEndValue(final_geometry)
        geo.setEasingCurve(QEasingCurve.Type.OutCubic)

        op = QPropertyAnimation(self, b"windowOpacity")
        op.setDuration(260)
        op.setStartValue(0.0)
        op.setEndValue(1.0)
        op.setEasingCurve(QEasingCurve.Type.OutCubic)

        anims.addAnimation(geo)
        anims.addAnimation(op)
        anims.finished.connect(lambda: self.setWindowOpacity(1.0))
        self._menu_anim = anims
        anims.start()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(10)

        # 搜索框
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍  搜索应用、设置和文档")
        self.search_box.setFixedHeight(34)
        self.search_box.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.08);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 12);
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: rgba(0, 120, 215, 0.8);
                background-color: rgba(255, 255, 255, 0.12);
            }
        """)
        self.search_box.textChanged.connect(self._filter_apps)
        layout.addWidget(self.search_box)

        # "已固定" 标题
        pinned_header = QLabel("已固定")
        pinned_header.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold))
        pinned_header.setStyleSheet("color: #ffffff;")
        layout.addWidget(pinned_header)

        # 固定应用网格
        self.pinned_widget = QWidget()
        self.pinned_layout = QGridLayout(self.pinned_widget)
        self.pinned_layout.setContentsMargins(0, 0, 0, 0)
        self.pinned_layout.setSpacing(4)
        layout.addWidget(self.pinned_widget)

        # 分隔线
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255,255,255,12);")
        layout.addWidget(sep)

        # "所有应用" 标题
        all_header = QLabel("所有应用")
        all_header.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold))
        all_header.setStyleSheet("color: #ffffff;")
        layout.addWidget(all_header)

        # 应用列表（滚动区域）
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

        self.app_list_widget = QWidget()
        self.app_list_widget.setStyleSheet("background: transparent;")
        self.app_layout = QVBoxLayout(self.app_list_widget)
        self.app_layout.setContentsMargins(0, 0, 0, 0)
        self.app_layout.setSpacing(1)
        scroll.setWidget(self.app_list_widget)
        layout.addWidget(scroll, 1)

        # 底部：用户 + 电源
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)

        user_btn = QPushButton("👤  用户")
        user_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #ffffff;
                border: none; border-radius: 6px;
                padding: 6px 10px; font-size: 12px; text-align: left;
            }
            QPushButton:hover { background-color: rgba(255,255,255,0.12); }
        """)
        bottom.addWidget(user_btn)
        bottom.addStretch()

        # 电源菜单按钮
        self.power_btn = QPushButton("⏻")
        self.power_btn.setFixedSize(34, 34)
        self.power_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #ffffff;
                border: none; border-radius: 6px; font-size: 16px;
            }
            QPushButton:hover { background-color: rgba(255,255,255,0.12); }
        """)
        self.power_btn.setMenu(self._build_power_menu())
        bottom.addWidget(self.power_btn)

        layout.addLayout(bottom)

        self.app_buttons: Dict[str, QPushButton] = {}
        self.pinned_buttons: List[QPushButton] = []

    def _build_power_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(40, 40, 55, 250);
                color: #ffffff; border: 1px solid rgba(255,255,255,18);
                border-radius: 6px; padding: 4px;
            }
            QMenu::item { padding: 6px 24px; border-radius: 4px; }
            QMenu::item:selected { background-color: rgba(0, 120, 215, 0.6); }
        """)
        for action, label in (("sleep", "💤  睡眠"),
                              ("reboot", "🔄  重启"),
                              ("shutdown", "⏻  关机")):
            act = menu.addAction(label)
            act.triggered.connect(lambda _=False, a=action: self.shutdown_signal.emit(a))
        return menu

    def _load_apps(self):
        """加载应用列表"""
        from apps import app_registry
        apps = app_registry.scan()

        self._clear_app_buttons()

        # 所有应用列表
        for app in apps:
            btn = QPushButton(f"    {app.name}")
            btn.setFixedHeight(32)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            if app.icon_file:
                from apps import get_icon_icon
                btn.setIcon(get_icon_icon(app.icon_file, 18))
                btn.setIconSize(QSize(18, 18))
            else:
                btn.setText(f"  {app.icon if app.icon else '📄'}  {app.name}")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #ffffff;
                    border: none;
                    border-radius: 4px;
                    text-align: left;
                    padding-left: 8px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.10);
                }
            """)
            btn.clicked.connect(lambda checked, name=app.name: self.app_launch.emit(name))
            self.app_layout.addWidget(btn)
            self.app_buttons[app.name] = btn

        self.app_layout.addStretch()

        # 固定应用网格（前 18 个，6 列 x 3 行）
        cols = 6
        for i, app in enumerate(apps[:cols * 3]):
            row, col = i // cols, i % cols
            pbtn = self._make_pinned_button(app)
            self.pinned_layout.addWidget(pbtn, row, col)
            self.pinned_buttons.append(pbtn)

    def _make_pinned_button(self, app) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(72, 72)
        btn.setToolTip(app.name)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-size: 22px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.10);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.18);
            }
        """)
        btn.setText(app.icon if app.icon else app.name[:1])
        if app.icon_file:
            from apps import get_icon_icon
            btn.setIcon(get_icon_icon(app.icon_file, 44))
            btn.setIconSize(QSize(44, 44))
            btn.setText("")
        btn.clicked.connect(lambda checked, name=app.name: self.app_launch.emit(name))
        return btn

    def _clear_app_buttons(self):
        for btn in self.app_buttons.values():
            self.app_layout.removeWidget(btn)
            btn.deleteLater()
        self.app_buttons.clear()
        for btn in self.pinned_buttons:
            self.pinned_layout.removeWidget(btn)
            btn.deleteLater()
        self.pinned_buttons.clear()

    def _filter_apps(self, text: str):
        for name, btn in self.app_buttons.items():
            btn.setVisible(text.lower() in name.lower())


def run_desktop():
    """启动桌面环境"""
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    desktop = DesktopEnvironment()
    desktop.show()
    return app, desktop