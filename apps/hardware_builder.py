"""
TianOS 硬件配置器
扫描 hardware/ 目录下的硬件定义（每个 .py 文件包含 HARDWARE_INFO 字典），
可视化选择 CPU/GPU/内存/主板，并写入 data/active_hardware.json。
"""

APP_NAME = "硬件配置器"
APP_ICON = "🖥️"
APP_ICON_FILE = "imageres 095.png"
APP_COLOR = "#ff8800"

import os
import json
import ast

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QListWidget, QListWidgetItem, QSplitter,
    QTextEdit, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# ---------------------------------------------------------------------------
# 路径与常量
# ---------------------------------------------------------------------------

ROOT_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".."))
HARDWARE_DIR = os.path.join(ROOT_DIR, "hardware")
DATA_DIR = os.path.join(ROOT_DIR, "data")
ACTIVE_HARDWARE_FILE = os.path.join(DATA_DIR, "active_hardware.json")

# 配置包含的部件类别（顺序即中间列表的显示顺序）
CATEGORY_ORDER = ["cpu", "gpu", "memory", "motherboard"]
CATEGORY_LABELS = {
    "cpu": "CPU",
    "gpu": "GPU",
    "memory": "内存 (RAM)",
    "motherboard": "主板",
}

# 详情面板中显示为中文的字段
FIELD_LABELS = {
    "name": "名称",
    "model": "型号",
    "socket": "插槽",
    "cores": "核心数",
    "threads": "线程数",
    "frequency_mhz": "基础频率 (MHz)",
    "max_frequency_mhz": "睿频 (MHz)",
    "tdp_w": "功耗 (W)",
    "cache_l3": "三级缓存",
    "vram_mb": "显存 (MB)",
    "cuda_cores": "CUDA 核心",
    "core_clock_mhz": "核心频率 (MHz)",
    "memory_clock_mhz": "显存频率 (MHz)",
    "memory_type": "内存类型",
    "total_mb": "容量 (MB)",
    "modules": "条数",
    "chipset": "芯片组",
    "memory_types": "支持内存",
    "form_factor": "板型",
}


# ---------------------------------------------------------------------------
# 后台逻辑
# ---------------------------------------------------------------------------

def _load_hardware_info(file_path: str):
    """安全提取 HARDWARE_INFO 字典。

    仅解析源文件的 AST 并求值 HARDWARE_INFO 字面量，
    绝不执行文件中的其它代码，保证扫描安全性。
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "HARDWARE_INFO":
                        info = ast.literal_eval(node.value)
                        return info if isinstance(info, dict) else None
    except Exception:
        return None
    return None


def scan_hardware() -> dict:
    """扫描 hardware/ 目录，返回 {category: [设备信息 dict, ...]}。

    每个分类为 hardware/ 下的一个子目录；分类中的每个 .py 文件是一个设备。
    """
    result: dict = {}
    if not os.path.isdir(HARDWARE_DIR):
        return result
    for cat in sorted(os.listdir(HARDWARE_DIR)):
        cat_dir = os.path.join(HARDWARE_DIR, cat)
        if not os.path.isdir(cat_dir):
            continue
        devices = []
        for filename in sorted(os.listdir(cat_dir)):
            if not filename.endswith(".py"):
                continue
            file_path = os.path.join(cat_dir, filename)
            info = _load_hardware_info(file_path)
            if not info:
                continue
            info = dict(info)
            info.setdefault("id", filename[:-3])
            info.setdefault("category", cat)
            info.setdefault("name", filename[:-3])
            devices.append(info)
        if devices:
            result[cat] = devices
    return result


def load_active_config() -> dict:
    """读取 data/active_hardware.json；不存在或损坏时返回空 dict。"""
    if not os.path.isfile(ACTIVE_HARDWARE_FILE):
        return {}
    try:
        with open(ACTIVE_HARDWARE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_active_config(selection: dict) -> bool:
    """把用户选择写入 data/active_hardware.json，成功返回 True。"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(ACTIVE_HARDWARE_FILE, "w", encoding="utf-8") as f:
            json.dump(selection, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _find_device(devices: dict, category: str, device_id: str):
    for dev in devices.get(category, []):
        if dev.get("id") == device_id:
            return dev
    return None


def check_compatibility(devices: dict, selection: dict) -> str:
    """简易兼容性检测。返回空字符串表示通过，否则返回错误说明。

    规则：内存的 DDR 版本必须被主板支持（例如 DDR4 内存 + 仅支持 DDR5 的主板 → 不兼容）。
    """
    mem = _find_device(devices, "memory", selection.get("memory") or "")
    mobo = _find_device(devices, "motherboard", selection.get("motherboard") or "")
    if not mem or not mobo:
        return ""
    mem_type = str(mem.get("memory_type", "")).upper()
    supported = [str(t).upper() for t in (mobo.get("memory_types") or [])]
    if mem_type and mem_type not in supported:
        return (f"兼容性错误：所选的 {CATEGORY_LABELS['memory']} "
                f"[{mem.get('id')}] 为 {mem_type}，而 {CATEGORY_LABELS['motherboard']} "
                f"[{mobo.get('id')}] 仅支持 {'/'.join(supported) or '未知类型'}。\n"
                f"请更换内存或主板后重试。")
    return ""


# ---------------------------------------------------------------------------
# 界面
# ---------------------------------------------------------------------------

class HardwareBuilder(QWidget):
    """硬件配置器主窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("硬件配置器")
        self.setMinimumSize(860, 520)
        self._devices: dict = {}
        self._selection: dict = {}
        self._row_items: dict = {}
        self._setup_ui()
        self.refresh()

    # ---------- UI ----------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("TianOS 硬件配置器")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #ff8800;")
        layout.addWidget(title)

        tip = QLabel("在左侧双击硬件即可加入中间配置；右侧显示所选硬件详情。"
                     "点击“应用配置”写入 data/active_hardware.json。")
        tip.setStyleSheet("color: #556677; font-size: 11px;")
        layout.addWidget(tip)

        split = QSplitter(Qt.Orientation.Horizontal)

        # 左侧: 可用硬件树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["可用硬件"])
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: rgba(255,255,255,0.05);
                color: #cccccc;
                border: 1px solid #334466;
                border-radius: 6px;
            }
            QTreeWidget::item:selected { background-color: rgba(255,136,0,0.25); }
        """)
        self.tree.currentItemChanged.connect(self._on_tree_select)
        self.tree.itemDoubleClicked.connect(self._on_tree_assign)
        split.addWidget(self.tree)

        # 中间: 当前已选配置
        self.list = QListWidget()
        self.list.setFixedWidth(220)
        self.list.setStyleSheet("""
            QListWidget {
                background-color: rgba(255,255,255,0.05);
                color: #cccccc;
                border: 1px solid #334466;
                border-radius: 6px;
            }
            QListWidget::item:selected { background-color: rgba(255,136,0,0.25); }
        """)
        for cat in CATEGORY_ORDER:
            item = QListWidgetItem(f"{CATEGORY_LABELS[cat]}: 未选择")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.list.addItem(item)
            self._row_items[cat] = item
        split.addWidget(self.list)

        # 右侧: 详细信息
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setStyleSheet("""
            QTextEdit {
                background-color: rgba(16,22,38,220);
                color: #cccccc;
                border: 1px solid #334466;
                border-radius: 6px;
                font-family: Microsoft YaHei;
                font-size: 13px;
            }
        """)
        self.details.setPlaceholderText("在左侧选择一个硬件以查看详细信息")
        split.addWidget(self.details)
        split.setSizes([280, 220, 360])

        layout.addWidget(split, 1)

        # 底部: 状态 + 按钮
        bar = QHBoxLayout()
        self.status = QLabel("就绪")
        self.status.setStyleSheet("color: #556677; font-size: 11px;")
        bar.addWidget(self.status, 1)

        self.btn_save = self._btn("应用配置")
        self.btn_refresh = self._btn("刷新")
        for b in (self.btn_save, self.btn_refresh):
            bar.addWidget(b)
        layout.addLayout(bar)

        self.btn_save.clicked.connect(self._on_save)
        self.btn_refresh.clicked.connect(self.refresh)

    @staticmethod
    def _btn(text: str) -> QPushButton:
        b = QPushButton(text)
        b.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.06);
                color: #cccccc;
                border: 1px solid #334466;
                border-radius: 4px;
                padding: 5px 16px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: rgba(255,136,0,0.15); border-color: #ff8800; }
            QPushButton:pressed { background-color: rgba(255,136,0,0.25); }
        """)
        return b

    # ---------- 扫描与填充 ----------

    def refresh(self):
        """重新扫描硬件目录、重建树、并恢复已保存的选择。"""
        self._devices = scan_hardware()
        self._selection = load_active_config()

        self.tree.clear()
        for cat in CATEGORY_ORDER:
            devices = self._devices.get(cat, [])
            if not devices:
                continue
            top = QTreeWidgetItem([CATEGORY_LABELS[cat]])
            for dev in devices:
                child = QTreeWidgetItem([str(dev.get("name", dev.get("id", "")))])
                child.setData(0, Qt.ItemDataRole.UserRole, dev.get("id"))
                child.setData(0, Qt.ItemDataRole.UserRole + 1, cat)
                top.addChild(child)
            self.tree.addTopLevelItem(top)
        self.tree.expandAll()

        self._update_list()
        total = sum(len(v) for v in self._devices.values())
        self.status.setText(f"已扫描到 {total} 个硬件设备" if self._devices
                            else "未在 hardware/ 目录中发现硬件")

    # ---------- 交互 ----------

    def _device_name(self, category: str, device_id: str) -> str:
        dev = _find_device(self._devices, category, device_id or "")
        if dev:
            return str(dev.get("name", dev.get("id", "")))
        return ""

    def _update_list(self):
        for cat in CATEGORY_ORDER:
            item = self._row_items.get(cat)
            if item is None:
                continue
            name = self._device_name(cat, self._selection.get(cat))
            item.setText(f"{CATEGORY_LABELS[cat]}: {name or '未选择'}")

    def _on_tree_select(self, current, previous):
        if current is None:
            return
        device_id = current.data(0, Qt.ItemDataRole.UserRole)
        category = current.data(0, Qt.ItemDataRole.UserRole + 1)
        if not device_id or not category:
            self.details.setPlaceholderText("在左侧选择一个硬件以查看详细信息")
            return
        dev = _find_device(self._devices, category, device_id)
        if dev:
            self._show_details(dev)

    def _on_tree_assign(self, item, column):
        """双击树中的硬件 → 加入当前配置。"""
        device_id = item.data(0, Qt.ItemDataRole.UserRole)
        category = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not device_id or not category:
            return
        self._selection[category] = device_id
        self._update_list()
        dev = _find_device(self._devices, category, device_id)
        if dev:
            self.status.setText(f"已选择 {CATEGORY_LABELS[category]}: "
                                f"{dev.get('name', dev.get('id', ''))}")

    def _show_details(self, dev: dict):
        lines = [f"{CATEGORY_LABELS.get(dev.get('category', ''), '硬件')}: "
                 f"{dev.get('name', dev.get('id', ''))}",
                 "-" * 40]
        for key, value in dev.items():
            if key in ("id", "category", "name"):
                continue
            label = FIELD_LABELS.get(key, key)
            if key == "memory_types" and isinstance(value, list):
                value = " / ".join(str(v) for v in value)
            if key == "features" and isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            lines.append(f"{label}: {value}")
        self.details.setPlainText("\n".join(lines))

    # ---------- 保存 ----------

    def _on_save(self):
        selection = {cat: self._selection.get(cat) for cat in CATEGORY_ORDER
                     if self._selection.get(cat)}
        # CPU / GPU / 内存为必选，主板可选
        required = ["cpu", "gpu", "memory"]
        missing = [CATEGORY_LABELS[c] for c in required if not selection.get(c)]
        if missing:
            QMessageBox.warning(self, "配置不完整",
                                "以下部件尚未选择：\n" + "、".join(missing))
            return

        error = check_compatibility(self._devices, selection)
        if error:
            QMessageBox.critical(self, "兼容性检查未通过", error)
            self.status.setText("已拦截保存：当前配置存在兼容性问题")
            return

        if save_active_config(selection):
            # 刷新全局硬件管理器缓存，让任务管理器/关于界面/沙箱立即使用新配置
            try:
                from system.hardware_manager import hardware_manager
                hardware_manager.reload()
            except Exception:
                pass
            QMessageBox.information(
                self, "配置已保存",
                "配置已保存，重启 TianOS 后完全生效。\n"
                "当前会话硬件信息已即时同步到任务管理器与关于界面。")
            self.status.setText("配置已保存，重启生效")
        else:
            QMessageBox.critical(self, "保存失败",
                                 f"无法写入 {ACTIVE_HARDWARE_FILE}")