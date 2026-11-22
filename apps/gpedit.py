"""
TianOS 组策略编辑器
提供交互式的本地组策略配置。右侧以可勾选的策略树呈现；
策略状态写入虚拟注册表 HKEY_CURRENT_USER\\Software\\TianOS\\GroupPolicies。
"""

APP_NAME = "组策略"
APP_ICON = "🛡"
APP_ICON_FILE = "imageres 219.png"
APP_COLOR = "#00aaff"

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QSplitter, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from apps.registry import RegistryStore

# 组策略在注册表中的存储位置
GP_REG_PATH = ["HKEY_CURRENT_USER", "Software", "TianOS", "GroupPolicies"]

# 策略状态: 0=未配置 1=已启用 2=已禁用
STATE_NOT_CONFIGURED = 0
STATE_ENABLED = 1
STATE_DISABLED = 2
STATE_NAMES = {
    STATE_NOT_CONFIGURED: "未配置",
    STATE_ENABLED: "已启用",
    STATE_DISABLED: "已禁用",
}

# 模拟组策略结构: (分类, 子策略列表)  "管理模板" 下继续细分
GP_TREE = [
    ("计算机配置", [
        "软件设置",
        "Windows 设置",
        ("管理模板", ["系统", "网络", "Windows 组件", "控制面板"]),
    ]),
    ("用户配置", [
        "软件设置",
        "Windows 设置",
        ("管理模板", ["系统", "网络", "Windows 组件", "控制面板"]),
    ]),
]

POLICY_DETAILS = [
    "关闭系统自动播放",
    "禁止在开始菜单显示最近使用的项目",
    "不显示最后的登录用户名",
    "启用桌面清理向导",
    "限制用户安装软件",
]


# ---------------------------------------------------------------------------
# 注册表读写
# ---------------------------------------------------------------------------

def _path_node(root: dict, path: list, create=False):
    """在注册表 JSON 结构 root 中沿 path 导航，create=True 时自动创建缺失节点。
    path[0] 为顶层键（如 HKEY_CURRENT_USER），其下各级均为 children 节点。
    """
    node = root.get(path[0])
    if node is None:
        if not create:
            return None
        node = {"desc": "", "values": {}, "children": {}}
        root[path[0]] = node
    for part in path[1:]:
        children = node.get("children")
        if not isinstance(children, dict):
            if not create:
                return None
            children = {}
            node["children"] = children
        nxt = children.get(part)
        if nxt is None:
            if not create:
                return None
            nxt = {"desc": "由 TianOS 组策略编辑器写入",
                   "values": {}, "children": {}}
            children[part] = nxt
        node = nxt
    return node


def load_policy_states() -> dict:
    """从注册表读取所有策略的当前状态: {策略名: 0/1/2}"""
    store = RegistryStore()
    node = _path_node(store.data, GP_REG_PATH)
    states = {}
    if node is None:
        return states
    for name, val in (node.get("values") or {}).items():
        try:
            states[name] = int(val.get("value", STATE_NOT_CONFIGURED))
        except (TypeError, ValueError):
            states[name] = STATE_NOT_CONFIGURED
    return states


def save_policy_state(name: str, state: int):
    """把单个策略的状态写入注册表 (REG_DWORD)"""
    if state not in STATE_NAMES:
        state = STATE_NOT_CONFIGURED
    store = RegistryStore()
    node = _path_node(store.data, GP_REG_PATH, create=True)
    node["values"][name] = {"type": "REG_DWORD", "value": int(state)}
    store.save()


# ---------------------------------------------------------------------------
# 界面
# ---------------------------------------------------------------------------

class GroupPolicy(QWidget):
    """组策略编辑器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("本地组策略编辑器")
        self.setMinimumSize(720, 500)
        self._loading = False
        self._setup_ui()
        self._show_overview()

    # ---------- 界面 ----------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("TianOS 本地组策略编辑器")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #00aaff;")
        layout.addWidget(title)

        tip = QLabel("提示：勾选策略后会自动写入注册表（HKEY_CURRENT_USER\\Software\\TianOS\\GroupPolicies）")
        tip.setStyleSheet("color: #556677; font-size: 11px;")
        layout.addWidget(tip)

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
        self._build_left_tree()
        self.tree.expandToDepth(2)
        self.tree.currentItemChanged.connect(self._on_select)
        split.addWidget(self.tree)

        # 右侧: 策略明细 (可勾选)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 0, 0)
        rl.setSpacing(6)

        self.scope_label = QLabel("当前: 概览")
        self.scope_label.setStyleSheet("color: #00aaff; font-size: 12px; padding: 2px 0;")
        rl.addWidget(self.scope_label)

        self.policy_tree = QTreeWidget()
        self.policy_tree.setColumnCount(2)
        self.policy_tree.setHeaderLabels(["策略", "状态"])
        self.policy_tree.setRootIsDecorated(False)
        self.policy_tree.setIndentation(0)
        self.policy_tree.setColumnWidth(0, 280)
        self.policy_tree.setStyleSheet("""
            QTreeWidget {
                background-color: rgba(255,255,255,0.04);
                color: #cccccc;
                border: 1px solid #334466;
                border-radius: 6px;
                font-family: Microsoft YaHei;
            }
            QHeaderView::section {
                background-color: rgba(20,25,50,240);
                color: #8888ff;
                border: none;
                border-bottom: 1px solid #334466;
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background-color: rgba(0,170,255,0.15);
                color: #ffffff;
            }
        """)
        self.policy_tree.itemChanged.connect(self._on_policy_changed)
        rl.addWidget(self.policy_tree, 1)

        # 工具栏 (批量操作)
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.btn_enable_all = self._btn("全部启用")
        self.btn_disable_all = self._btn("全部禁用")
        self.btn_clear_all = self._btn("全部未配置")
        self.btn_refresh = self._btn("刷新")
        for b in (self.btn_enable_all, self.btn_disable_all,
                  self.btn_clear_all, self.btn_refresh):
            bar.addWidget(b)
        bar.addStretch()
        rl.addLayout(bar)

        self.status = QLabel("就绪")
        self.status.setStyleSheet("color:#556677; font-size:11px;")
        rl.addWidget(self.status)

        split.addWidget(right)
        split.setSizes([280, 440])

        layout.addWidget(split, 1)

        self.btn_enable_all.clicked.connect(
            lambda: self._apply_all_state(Qt.CheckState.Checked))
        self.btn_disable_all.clicked.connect(
            lambda: self._apply_all_state(Qt.CheckState.Unchecked))
        self.btn_clear_all.clicked.connect(
            lambda: self._apply_all_state(Qt.CheckState.PartiallyChecked))
        self.btn_refresh.clicked.connect(self._refresh)

    @staticmethod
    def _btn(text: str) -> QPushButton:
        b = QPushButton(text)
        b.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.06);
                color: #cccccc;
                border: 1px solid #334466;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: rgba(0,170,255,0.15); border-color: #00aaff; }
            QPushButton:pressed { background-color: rgba(0,170,255,0.25); }
            QPushButton:disabled { color: #556677; }
        """)
        return b

    def _build_left_tree(self):
        for root, children in GP_TREE:
            top = QTreeWidgetItem([root])
            for child in children:
                if isinstance(child, tuple):
                    folder = QTreeWidgetItem([child[0]])
                    for sub in child[1]:
                        folder.addChild(QTreeWidgetItem([sub]))
                    top.addChild(folder)
                else:
                    top.addChild(QTreeWidgetItem([child]))
            self.tree.addTopLevelItem(top)

    # ---------- 交互 ----------

    def _on_select(self, current, previous):
        if current is None:
            return
        parent = current.parent()
        # 管理模板 下的具体文件夹 → 展示可勾选的策略列表
        if parent is not None and parent.text(0) == "管理模板":
            scope = f"{parent.parent().text(0)} › 管理模板 › {current.text(0)}"
            self._show_policies(scope)
        elif current.text(0) == "管理模板":
            self._show_overview("选择「管理模板」下的具体策略文件夹即可配置")
        elif current.text(0) in ("计算机配置", "用户配置"):
            self._show_overview(f"展开 [{current.text(0)}]，在「管理模板」下选择策略文件夹")
        else:
            self._show_overview(f"[{current.text(0)}]\n请在左侧「管理模板」下选择具体的策略文件夹")

    def _show_overview(self, text: str = "在左侧选择策略文件夹以查看和配置"):
        self._loading = True
        self.scope_label.setText("当前: 概览")
        self.policy_tree.clear()
        self.policy_tree.setColumnCount(1)
        self.policy_tree.setHeaderLabels(["说明"])
        item = QTreeWidgetItem([text])
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.policy_tree.addTopLevelItem(item)
        self._loading = False
        self.status.setText("请选择左侧的策略目录")

    def _show_policies(self, scope: str):
        self._loading = True
        self.scope_label.setText(f"当前: {scope}")
        self.policy_tree.clear()
        self.policy_tree.setColumnCount(2)
        self.policy_tree.setHeaderLabels(["策略", "状态"])
        states = load_policy_states()
        for name in POLICY_DETAILS:
            state = states.get(name, STATE_NOT_CONFIGURED)
            item = QTreeWidgetItem([name, STATE_NAMES[state]])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if state == STATE_ENABLED:
                item.setCheckState(0, Qt.CheckState.Checked)
            elif state == STATE_DISABLED:
                item.setCheckState(0, Qt.CheckState.Unchecked)
            else:
                item.setCheckState(0, Qt.CheckState.PartiallyChecked)
            item.setData(0, Qt.ItemDataRole.UserRole, name)
            self.policy_tree.addTopLevelItem(item)
        self._loading = False
        self.status.setText(f"已加载 {len(POLICY_DETAILS)} 条策略（勾选即保存到注册表）")

    def _on_policy_changed(self, item, column):
        if self._loading or column != 0:
            return
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if not name:
            return
        state = self._check_state_to_int(item.checkState(0))
        item.setText(1, STATE_NAMES[state])
        save_policy_state(name, state)
        self.status.setText(f"已保存 [{name}: {STATE_NAMES[state]}] 到注册表")

    def _apply_all_state(self, check_state):
        count = self.policy_tree.topLevelItemCount()
        if count == 0:
            return
        self._loading = True
        for i in range(count):
            item = self.policy_tree.topLevelItem(i)
            state = self._check_state_to_int(check_state)
            item.setCheckState(0, check_state)
            item.setText(1, STATE_NAMES[state])
            name = item.data(0, Qt.ItemDataRole.UserRole)
            if name:
                save_policy_state(name, state)
        self._loading = False
        self.status.setText(f"已将 {count} 条策略批量写入注册表")

    def _refresh(self):
        self._on_select(self.tree.currentItem(), None)

    @staticmethod
    def _check_state_to_int(check_state) -> int:
        if check_state == Qt.CheckState.Checked:
            return STATE_ENABLED
        if check_state == Qt.CheckState.Unchecked:
            return STATE_DISABLED
        return STATE_NOT_CONFIGURED