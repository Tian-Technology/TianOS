"""
TianOS 登录界面 (Windows 风格锁屏)
================================
全屏不透明锁屏窗口, 覆盖宿主机桌面:
  - 背景 = 与桌面同款的 Win11 蓝色波浪壁纸 (彻底与桌面风格统一)
  - 半透明压暗遮罩 (类似 Windows 锁屏的亚光效果)
  - 中央大时钟 + 日期, 底部居中: 头像 / 用户名 / 密码 / 登录按钮
  - 右下角电源键, 左上品牌, 右上放弃登录按钮
  - 登录成功发射 login_succeeded, 失败弹窗; 放弃登录安全退出
"""

from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QBrush, QLinearGradient, QRadialGradient,
    QPainterPath, QFontMetrics,
)

from system.config import sys_config
from system.user_manager import user_manager

# 自 Windows 锁屏 (审核认证界面) 借鉴的布局参数
PANEL_W = 336
# 时钟基线相对屏幕高度的位置 (顶部留白, 给时钟+日期留出空间)
CLOCK_BASE_Y_RATIO = 0.13
# 登录面板顶部相对屏幕高度的位置 (必须在时钟/日期下方, 避免重叠)
PANEL_TOP_Y_RATIO = 0.38

WEEK_CN = "一二三四五六日"


# =====================================================================
#  桌面同款 Win11 蓝色波浪壁纸 (与 gui/desktop.py 一致)
# =====================================================================
def _paint_win11_wallpaper(painter: QPainter, w: int, h: int) -> None:
    """绘制与桌面环境完全一致的 Win11 风格蓝色波浪壁纸"""
    base = QLinearGradient(0, 0, w, h)
    base.setColorAt(0.0, QColor(0, 30, 80))
    base.setColorAt(0.5, QColor(0, 60, 140))
    base.setColorAt(1.0, QColor(0, 20, 60))
    painter.fillRect(QRectF(0, 0, w, h), QBrush(base))

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

    painter.setPen(Qt.PenStyle.NoPen)
    for wv in waves:
        cx, cy = int(w * wv["cx"]), int(h * wv["cy"])
        rx, ry = int(w * wv["rx"]), int(h * wv["ry"])
        grad = QRadialGradient(cx, cy, max(rx, ry))
        grad.setColorAt(0.0, wv["c1"])
        grad.setColorAt(1.0, wv["c2"])
        painter.setBrush(QBrush(grad))
        path = QPainterPath()
        path.addEllipse(QRectF(cx - rx, cy - ry, rx * 2, ry * 2))
        painter.drawPath(path)

    hi = QLinearGradient(0, int(h * 0.4), 0, int(h * 0.55))
    hi.setColorAt(0.0, QColor(120, 200, 255, 60))
    hi.setColorAt(1.0, QColor(120, 200, 255, 0))
    painter.fillRect(QRectF(0, 0, w, h), QBrush(hi))


class LoginWindow(QWidget):
    """TianOS 全屏登录窗口 (Windows 风格锁屏)"""

    # 登录成功信号: 携带用户信息 dict
    login_succeeded = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TianOS - 登录")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        # 全屏不透明: 盖住整个屏幕 (含任务栏), 隐藏宿主机桌面
        screen = QApplication.primaryScreen()
        if screen is None:
            self.setGeometry(0, 0, 1280, 720)
        else:
            self.setGeometry(screen.geometry())

        # 放弃登录标记 (登录成功后置 True, 关闭时不会误退出系统)
        self._login_accepted = False

        self._build_ui()

        # 大时钟每秒刷新 (由 paintEvent 直接绘制)
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self.update)
        self._clock_timer.start(1000)

    # ---------- UI (Windows 锁屏布局) ----------

    @staticmethod
    def _circle_button(text, tip="", size=38, danger=False):
        """圆形工具按钮 (放弃登录/电源)"""
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tip)
        btn.setFixedSize(size, size)
        color = "#ff7a7a" if danger else "#ffffff"
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(12, 16, 34, 150);
                color: {color}; font-size: 14px;
                border: 1px solid rgba(255, 255, 255, 45);
                border-radius: {size // 2}px;
            }}
            QPushButton:hover {{
                background-color: rgba(35, 45, 85, 200);
                border-color: rgba(255, 255, 255, 120);
            }}
        """)
        return btn

    @staticmethod
    def _input(placeholder: str, password: bool = False) -> QLineEdit:
        """Windows 登录样式输入框 (毛玻璃半透明)"""
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setEchoMode(QLineEdit.EchoMode.Password if password
                         else QLineEdit.EchoMode.Normal)
        edit.setFixedHeight(44)
        edit.setStyleSheet("""
            QLineEdit {
                background-color: rgba(12, 16, 34, 200);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 60);
                border-radius: 9px;
                padding: 0 16px;
                font-size: 14px;
                selection-background-color: #1e6ef8;
                selection-color: #ffffff;
            }
            QLineEdit:hover { border: 1px solid rgba(255, 255, 255, 110); }
            QLineEdit:focus {
                border: 1px solid #7ac0ff;
                background-color: rgba(16, 22, 44, 225);
            }
        """)
        return edit

    def _build_ui(self):
        w, h = self.width(), self.height()

        # ---------- 顶栏: 品牌 + 放弃登录 (绝对定位, 最顶部) ----------
        self._top_bar = QWidget(self)
        top = QHBoxLayout(self._top_bar)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(0)
        brand = QLabel(f"◈  {sys_config.SYSTEM_NAME}")
        brand.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        brand.setStyleSheet("color: rgba(255, 255, 255, 165);")
        top.addWidget(brand)
        top.addStretch()
        quit_btn = self._circle_button("✕", "放弃登录并退出", danger=True)
        quit_btn.clicked.connect(self.close)  # closeEvent → 安全退出
        top.addWidget(quit_btn)

        # ---------- 中央: 登录面板 (输入框, 类似 Windows 登录) ----------
        # 注意: 时钟由 paintEvent 直接绘制, 不参与 layout;
        # 所以面板必须用绝对坐标钉在时钟下方, 绝不能用 stretch 弹性猜测位置
        self._login_panel = QWidget(self)
        self._login_panel.setFixedWidth(PANEL_W)
        pl = QVBoxLayout(self._login_panel)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)

        heading = QLabel("登录 TianOS")
        heading.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        heading.setFont(QFont("Segoe UI", 15, QFont.Weight.DemiBold))
        heading.setStyleSheet("color: #ffffff;")
        pl.addWidget(heading)
        pl.addSpacing(4)

        sub = QLabel("请输入用户名与密码以继续")
        sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sub.setFont(QFont("Microsoft YaHei", 10))
        sub.setStyleSheet("color: rgba(255, 255, 255, 150);")
        pl.addWidget(sub)
        pl.addSpacing(24)

        self._username_edit = self._input("用户名")
        pl.addWidget(self._username_edit)
        pl.addSpacing(14)

        self._password_edit = self._input("密码", password=True)
        pl.addWidget(self._password_edit)
        pl.addSpacing(22)

        login_btn = QPushButton("登  录")
        login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        login_btn.setFixedHeight(44)
        login_btn.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        login_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e6ef8; color: #ffffff;
                border: none; border-radius: 9px;
            }
            QPushButton:hover { background-color: #2f7bfa; }
            QPushButton:pressed { background-color: #1557c9; }
        """)
        login_btn.clicked.connect(self._do_login)
        login_btn.setDefault(True)
        pl.addWidget(login_btn)
        pl.addSpacing(14)

        hint = QLabel("忘记密码？请联系系统管理员")
        hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        hint.setFont(QFont("Microsoft YaHei", 9))
        hint.setStyleSheet("color: rgba(255, 255, 255, 90);")
        pl.addWidget(hint)
        # 触发内部布局计算出真实高度, 供 move 定位
        self._login_panel.adjustSize()

        # ---------- 底栏: 状态 + 电源 (绝对定位, 最底部) ----------
        self._bottom_bar = QWidget(self)
        bottom = QHBoxLayout(self._bottom_bar)
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(0)
        status = QLabel(
            f"{sys_config.SYSTEM_NAME} {sys_config.SYSTEM_VERSION}"
            f"   ·   网络已连接")
        status.setFont(QFont("Microsoft YaHei", 9))
        status.setStyleSheet("color: rgba(255, 255, 255, 90);")
        bottom.addWidget(status)
        bottom.addStretch()
        power_btn = self._circle_button("⏻", "关机", size=46)
        power_btn.clicked.connect(self._power_off)
        bottom.addWidget(power_btn)

        # 初始定位 (后续窗口尺寸变化由 resizeEvent 重排)
        self._relayout()

        # 回车登录
        self._username_edit.returnPressed.connect(
            lambda: self._password_edit.setFocus())
        self._password_edit.returnPressed.connect(self._do_login)
        self._username_edit.setFocus()

    def _relayout(self):
        """按屏幕尺寸绝对定位三个区域: 顶栏 / 登录面板(时钟下方) / 底栏"""
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        # 顶栏: 顶部固定 22px
        self._top_bar.setGeometry(30, 22, w - 60, 40)
        # 登录面板: 水平居中, 垂直钉在屏幕 38% 处 (时钟/日期的下方安全区)
        px = (w - PANEL_W) // 2
        py = int(h * PANEL_TOP_Y_RATIO)
        self._login_panel.move(px, py)
        # 底栏: 底部固定留白
        self._bottom_bar.setGeometry(30, h - 62, w - 60, 46)

    def resizeEvent(self, event):
        """窗口尺寸变化 (如多屏切换) 时重排所有绝对定位元素"""
        super().resizeEvent(event)
        self._relayout()

    # ---------- 登录逻辑 ----------

    def _do_login(self):
        username = self._username_edit.text().strip()
        password = self._password_edit.text()

        if not username or not password:
            QMessageBox.warning(self, "登录失败", "请输入用户名和密码")
            return

        user = user_manager.verify_user(username, password)
        if user is None:
            QMessageBox.warning(self, "登录失败", "用户名或密码错误，请重试")
            self._password_edit.clear()
            self._password_edit.setFocus()
            return

        # 登录成功: 标记后写入全局登录状态并通知外部
        # (login_succeeded 信号携带 user_info, 由 main.py 触发桌面创建)
        self._login_accepted = True
        user_manager.set_current_user(user)
        self.login_succeeded.emit(dict(user))
        self.close()

    def _power_off(self):
        """关机: 退出系统"""
        QApplication.quit()

    def closeEvent(self, event):
        """关闭窗口时: 若是放弃登录(未成功登录就关闭)，安全退出系统"""
        if not self._login_accepted:
            QApplication.quit()
        event.accept()

    # ---------- 背景绘制 (桌面同款壁纸 + Windows 锁屏大时钟) ----------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 1) 桌面同款 Win11 蓝色波浪壁纸
        _paint_win11_wallpaper(painter, w, h)

        # 2) 压暗遮罩 (Windows 锁屏亚光效果, 保证前景可读)
        painter.fillRect(QRectF(0, 0, w, h), QColor(0, 0, 0, 100))

        # 3) 中央大时钟 + 日期 (Windows 锁屏样式)
        now = datetime.now()
        time_str = f"{now.hour:02d}:{now.minute:02d}"

        time_font = QFont("Segoe UI Light", 92)
        time_font.setWeight(QFont.Weight.Light)
        painter.setFont(time_font)
        fm = QFontMetrics(time_font)
        tx = (w - fm.horizontalAdvance(time_str)) // 2
        ty = int(h * CLOCK_BASE_Y_RATIO) + fm.ascent()

        # 文字阴影
        painter.setPen(QColor(0, 0, 0, 90))
        painter.drawText(tx + 2, ty + 2, time_str)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(tx, ty, time_str)

        date_str = f"{now.year}年{now.month:02d}月{now.day:02d}日  "
        date_str += f"星期{WEEK_CN[now.weekday()]}"
        date_font = QFont("Microsoft YaHei", 17)
        painter.setFont(date_font)
        dfm = QFontMetrics(date_font)
        dx = (w - dfm.horizontalAdvance(date_str)) // 2
        painter.setPen(QColor(255, 255, 255, 190))
        painter.drawText(dx, ty + 52, date_str)