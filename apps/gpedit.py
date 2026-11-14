"""
TianOS 组策略编辑器
展示模拟的本地组策略配置
"""

APP_NAME = "组策略"
APP_ICON = "🛡"
APP_ICON_FILE = "imageres 219.png"
APP_COLOR = "#00aaff"

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QSplitter, QPlainTextEdit, QCheckBox, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


# 模拟组策略结构: (分类, 子策略列表)
GP_TREE = [
    ("计算机配置", [
        "软件设置",
        "Windows 设置",
        "管理模板",
    ]),
    ("用户配置", [
        "软件设置",
        "Windows 设置",
        "管理模板",
    ]),
]

POLICY_DETAILS = [
    "关闭系统自动播放",
    "禁止在开始菜单显示最近使用的项目",
    "不显示最后的登录用户名",
    "启用桌面清理向导",
    "限制用户安装软件",
]


class GroupPolicy(QWidget):
    """组策略编辑器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("本地组策略编辑器")
        self.setMinimumSize(620, 460)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("TianOS 本地组策略编辑器")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #00aaff;")
        layout.addWidget(title)

        split = QSplitter(Qt.Orientation.Horizontal)

        # 左侧: 策略树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["类别"])
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: rgba(255,255,255,0.05);
                color: #cccccc;
                border: 1px solid #334466;
                border-radius: 6px;
            }
            QTreeWidget::item:selected { background-color: rgba(0,170,255,0.2); }
        """)
        for root, children in GP_TREE:
            top = QTreeWidgetItem([root])
            for child in children:
                top.addChild(QTreeWidgetItem([child]))
            self.tree.addTopLevelItem(top)
        self.tree.expandAll()
        self.tree.currentItemChanged.connect(self._on_select)
        split.addWidget(self.tree)

        # 右侧: 策略明细
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setStyleSheet("""
            QPlainTextEdit {
                background-color: rgba(255,255,255,0.04);
                color: #cccccc;
                border: 1px solid #334466;
                border-radius: 6px;
                font-family: Consolas;
            }
        """)
        split.addWidget(self.details)
        split.setSizes([280, 340])

        layout.addWidget(split, 1)

    def _on_select(self, current, previous):
        if current is None:
            return
        text = current.text(0)
        if text in ("计算机配置", "用户配置", "软件设置", "Windows 设置", "管理模板"):
            self.details.setPlainText(
                f"[{text}]\n\n请选择下面的具体策略项。"
            )
        else:
            # 模拟一组可用策略开关
            lines = [f"[{text}]\n", "可用的策略项:"]
            for i, policy in enumerate(POLICY_DETAILS):
                state = "已启用" if i % 3 == 0 else ("已禁用" if i % 3 == 1 else "未配置")
                lines.append(f"  {'●' if i == 0 else '○'} {policy}  —  {state}")
            self.details.setPlainText("\n".join(lines))