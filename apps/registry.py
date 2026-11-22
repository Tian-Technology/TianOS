"""
TianOS 注册表编辑器
支持新建/重命名/删除键，以及新建/修改/删除值，数据本地 JSON 持久化。
"""

APP_NAME = "注册表"
APP_ICON = "🧾"
APP_ICON_FILE = "imageres 075.png"
APP_COLOR = "#00ff99"

import os
import json
from typing import Dict, Any, Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QSplitter, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog,
    QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# 本地存储位置: TianOS/data/registry.json
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
STORAGE_FILE = os.path.join(DATA_DIR, "registry.json")

# 值类型
VALUE_TYPES = ["REG_SZ", "REG_DWORD", "REG_BINARY"]


def _default_data() -> Dict[str, Any]:
    """首次运行时生成的默认注册表结构"""
    return {
        "HKEY_CLASSES_ROOT": {
            "desc": "文件类型关联与 COM 对象注册信息",
            "values": {},
            "children": {
                ".txt": {"desc": "txtfile", "values": {}, "children": {}},
                ".jpg": {"desc": "jpegfile", "values": {}, "children": {}},
                "txtfile": {"desc": "文本文档", "values": {}, "children": {}},
            },
        },
        "HKEY_CURRENT_USER": {
            "desc": "当前登录用户的配置",
            "values": {},
            "children": {
                "Software": {"desc": "用户软件设置", "values": {}, "children": {}},
                "Control Panel": {"desc": "控制面板设置", "values": {}, "children": {}},
                "Environment": {"desc": "用户环境变量", "values": {}, "children": {}},
            },
        },
        "HKEY_LOCAL_MACHINE": {
            "desc": "本机所有用户的系统配置",
            "values": {},
            "children": {
                "HARDWARE": {"desc": "硬件信息", "values": {}, "children": {}},
                "SOFTWARE": {"desc": "软件安装信息", "values": {}, "children": {}},
                "SYSTEM": {"desc": "系统启动与控制设置", "values": {}, "children": {}},
            },
        },
        "HKEY_USERS": {
            "desc": "所有用户配置",
            "values": {},
            "children": {
                ".DEFAULT": {"desc": "默认用户配置", "values": {}, "children": {}},
            },
        },
        "HKEY_CURRENT_CONFIG": {
            "desc": "当前硬件配置",
            "values": {},
            "children": {
                "Software": {"desc": "系统配置软件设置", "values": {}, "children": {}},
                "System": {"desc": "系统默认配置", "values": {}, "children": {}},
            },
        },
    }


class RegistryStore:
    """注册表数据存取 - 本地 JSON 持久化"""

    def __init__(self, path: str = STORAGE_FILE):
        self.path = path
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return self._normalize(data, _root=True)
        except Exception as e:
            print(f"[Registry] 加载失败: {e}")
        data = _default_data()
        self._write(data)
        return data

    @staticmethod
    def _normalize(node, _root=False) -> Any:
        """递归修正结构，避免某个节点格式异常导致整个注册表崩溃"""
        if _root:
            # 顶层结构强制为 dict
            if not isinstance(node, dict):
                return _default_data()
            for k in list(node.keys()):
                node[k] = RegistryStore._normalize(node[k])
            return node
        if not isinstance(node, dict):
            # 非 dict 节点（损坏数据）→ 转成空节点，保留原值作为 desc
            return {"desc": str(node) if node is not None else "", "values": {}, "children": {}}
        node.setdefault("desc", "")
        node.setdefault("values", {})
        node.setdefault("children", {})
        if not isinstance(node["values"], dict):
            node["values"] = {}
        if not isinstance(node["children"], dict):
            node["children"] = {}
        for name in list(node["children"].keys()):
            node["children"][name] = RegistryStore._normalize(node["children"][name])
        return node

    def _write(self, data: Dict[str, Any]):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Registry] 保存失败: {e}")

    def save(self):
        self._write(self.data)


class Registry(QWidget):
    """注册表编辑器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("注册表编辑器")
        self.setMinimumSize(720, 500)
        self.store = RegistryStore()
        self.data = self.store.data
        self._setup_ui()
        self._rebuild_tree()

    # ---------- 界面 ----------

    def _btn(self, text):
        b = QPushButton(text)
        b.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.06);
                color: #cccccc;
                border: 1px solid #334466;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: rgba(0,255,153,0.15); border-color: #00ff99; }
        """)
        return b

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("TianOS 注册表编辑器")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ff99;")
        top.addWidget(title)
        top.addStretch()
        self.path_label = QLabel()
        self.path_label.setStyleSheet("color:#556677; font-size:11px;")
        top.addWidget(self.path_label)
        layout.addLayout(top)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(5)
        self.btn_new_key = self._btn("＋ 新建项")
        self.btn_rename = self._btn("✎ 重命名")
        self.btn_delete_key = self._btn("🗑 删除项")
        self.btn_new_value = self._btn("＋ 新建值")
        self.btn_edit_value = self._btn("✎ 修改值")
        self.btn_delete_value = self._btn("🗑 删除值")
        self.btn_save = self._btn("💾 保存")
        for b in (self.btn_new_key, self.btn_rename, self.btn_delete_key,
                  self.btn_new_value, self.btn_edit_value, self.btn_delete_value):
            toolbar.addWidget(b)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_save)
        layout.addLayout(toolbar)

        # 左右
        split = QSplitter(Qt.Orientation.Horizontal)

        # 左: 键树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["注册表项"])
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: rgba(255,255,255,0.05);
                color: #cccccc;
                border: 1px solid #334466;
                border-radius: 6px;
                font-family: Consolas;
            }
            QTreeWidget::item:selected { background-color: rgba(0,255,153,0.2); }
            QTreeWidget::item:hover { background-color: rgba(0,255,153,0.08); }
        """)
        self.tree.currentItemChanged.connect(self._on_select)
        split.addWidget(self.tree)

        # 右: 键详情
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        rl.setSpacing(6)

        desc_row = QHBoxLayout()
        desc_lbl = QLabel("说明:")
        desc_lbl.setStyleSheet("color:#8888ff; font-size:11px;")
        desc_row.addWidget(desc_lbl)
        self.desc_edit = QLineEdit()
        self.desc_edit.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255,255,255,0.06);
                color: #cccccc;
                border: 1px solid #334466;
                border-radius: 4px;
                padding: 3px 8px;
            }
        """)
        self.desc_edit.setPlaceholderText("(默认值)")
        self.desc_edit.editingFinished.connect(self._save_desc)
        desc_row.addWidget(self.desc_edit, 1)
        rl.addLayout(desc_row)

        # 数值表
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["名称", "类型", "数据"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(255,255,255,0.05);
                color: #00ff99;
                border: 1px solid #334466;
                border-radius: 6px;
                gridline-color: #334466;
                font-family: Consolas;
            }
            QHeaderView::section {
                background-color: rgba(20,25,50,240);
                color: #8888ff;
                border: none;
                border-bottom: 1px solid #334466;
                padding: 4px;
            }
            QTableWidget::item:selected { background-color: rgba(0,255,153,0.2); }
        """)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self._edit_value_selected)
        rl.addWidget(self.table, 1)

        split.addWidget(right)
        split.setSizes([360, 360])
        layout.addWidget(split, 1)

        # 底部状态
        self.status = QLabel("就绪")
        self.status.setStyleSheet("color:#556677; font-size:11px;")
        layout.addWidget(self.status)

        # 信号连接
        self.btn_new_key.clicked.connect(self._new_key)
        self.btn_rename.clicked.connect(self._rename_key)
        self.btn_delete_key.clicked.connect(self._delete_key)
        self.btn_new_value.clicked.connect(self._new_value)
        self.btn_edit_value.clicked.connect(self._edit_value_selected)
        self.btn_delete_value.clicked.connect(self._delete_value)
        self.btn_save.clicked.connect(self.save)

    # ---------- 树构建 ----------

    def _node_path(self, item: Optional[QTreeWidgetItem]) -> List[str]:
        path = []
        while item is not None:
            path.insert(0, item.text(0))
            item = item.parent()
        return path

    def _get_node(self, path: List[str]) -> Optional[Dict[str, Any]]:
        node = self.data
        for part in path:
            n = node.get(part)
            if n is None:
                return None
            node = n["children"]
        return node

    def _rebuild_tree(self, select_path: Optional[List[str]] = None):
        """根据 self.data 重建键树"""
        self.tree.blockSignals(True)
        self.tree.clear()

        def build(parent_item, children_dict):
            for name in sorted(children_dict.keys()):
                child = children_dict[name]
                item = QTreeWidgetItem([name])
                parent_item.addChild(item)
                build(item, child.get("children", {}))

        for name in sorted(self.data.keys()):
            top = QTreeWidgetItem([name])
            self.tree.addTopLevelItem(top)
            build(top, self.data[name].get("children", {}))

        self.tree.blockSignals(False)
        self.tree.expandAll()

        # 尝试恢复选中
        if select_path:
            found = self._find_item(select_path, self.tree.invisibleRootItem())
            if found:
                self.tree.setCurrentItem(found)

    def _find_item(self, path, root):
        def walk(parent_item, depth, found):
            if found[0]:
                return
            for i in range(parent_item.childCount()):
                item = parent_item.child(i)
                if item.text(0) == path[depth]:
                    if depth == len(path) - 1:
                        found[0] = item
                        return
                    walk(item, depth + 1, found)
        found = [None]
        walk(root, 0, found)
        return found[0]

    # ---------- 选中 ----------

    def _on_select(self, current, previous):
        self._refresh_detail()

    def _refresh_detail(self):
        item = self.tree.currentItem()
        if item is None:
            return
        self.path_list = self._node_path(item)
        node = self._get_node(self.path_list)
        if node is None:
            return
        self.current_node = node
        self.path_label.setText("\\".join(self.path_list))
        # 说明
        self.desc_edit.blockSignals(True)
        self.desc_edit.setText(node.get("desc", ""))
        self.desc_edit.blockSignals(False)
        # 值表
        values = node.get("values", {})
        self.table.setRowCount(0)
        for name, info in sorted(values.items()):
            self._append_value_row(name, info)
        self.status.setText(f"路径: {'\\'.join(self.path_list)}")

    def _append_value_row(self, name, info):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(info.get("type", "REG_SZ")))
        self.table.setItem(row, 2, QTableWidgetItem(str(info.get("value", ""))))

    # ---------- 编辑操作 ----------

    def _save_desc(self):
        if not hasattr(self, "current_node"):
            return
        self.current_node["desc"] = self.desc_edit.text().strip()
        self.status.setText("已更新说明")

    def _new_key(self):
        item = self.tree.currentItem()
        if item is None:
            QMessageBox.information(self, "新建项", "请先选中一个项。")
            return
        name, ok = QInputDialog.getText(self, "新建项", "输入新项名称:")
        name = (name or "").strip()
        if not ok or not name:
            return
        path = self._node_path(item)
        node = self._get_node(path)
        if name in node["children"]:
            QMessageBox.warning(self, "新建项", "已存在同名项。")
            return
        node["children"][name] = {"desc": "", "values": {}, "children": {}}
        self._rebuild_tree(path + [name])
        self._refresh_detail()

    def _rename_key(self):
        item = self.tree.currentItem()
        if item is None:
            return
        old_name = item.text(0)
        path = self._node_path(item)
        if len(path) == 1:
            QMessageBox.information(self, "重命名", "根项不能重命名。")
            return
        new_name, ok = QInputDialog.getText(self, "重命名", "新名称:", text=old_name)
        new_name = (new_name or "").strip()
        if not ok or not new_name or new_name == old_name:
            return
        parent = path[:-1]
        parent_node = self._get_node(parent)
        if new_name in parent_node["children"]:
            QMessageBox.warning(self, "重命名", "已存在同名项。")
            return
        parent_node["children"][new_name] = parent_node["children"].pop(old_name)
        self._rebuild_tree(parent + [new_name])

    def _delete_key(self):
        item = self.tree.currentItem()
        if item is None:
            return
        path = self._node_path(item)
        if len(path) == 1:
            QMessageBox.information(self, "删除", "根项不能删除。")
            return
        if QMessageBox.question(self, "删除项", f"确定删除 {path[-1]} 及其所有子项？") == QMessageBox.StandardButton.Yes:
            parent = path[:-1]
            parent_node = self._get_node(parent)
            parent_node["children"].pop(path[-1], None)
            self._rebuild_tree()

    def _new_value(self):
        if not hasattr(self, "current_node"):
            return
        name, ok1 = QInputDialog.getText(self, "新建值", "值名称:", text="NewValue")
        name = (name or "").strip()
        if not ok1 or not name:
            return
        value_type, ok2 = QInputDialog.getItem(self, "新建值", "类型:", VALUE_TYPES, 0, False)
        if not ok2:
            return
        value, ok3 = QInputDialog.getText(self, "新建值", "数据:")
        if not ok3:
            return
        self._add_value(name, value_type, self._parse_value(value_type, value))
        self.status.setText(f"已新建值: {name}")

    def _add_value(self, name, value_type, value):
        values = self.current_node.setdefault("values", {})
        values[name] = {"type": value_type, "value": value}
        self._refresh_detail()

    def _selected_value(self):
        if self.table.currentRow() < 0:
            return None
        name = self.table.item(self.table.currentRow(), 0).text()
        values = self.current_node.get("values", {})
        return name, values.get(name)

    def _edit_value_selected(self, *args):
        if not hasattr(self, "current_node"):
            return
        sel = self._selected_value()
        if not sel:
            QMessageBox.information(self, "修改值", "请先单击选中一个值。")
            return
        name, info = sel
        values = self.current_node.setdefault("values", {})
        value_type, ok = QInputDialog.getItem(self, "修改值", "类型:", VALUE_TYPES,
                                              VALUE_TYPES.index(info["type"]) if info["type"] in VALUE_TYPES else 0, False)
        if not ok:
            return
        cur = str(info.get("value", ""))
        value, ok2 = QInputDialog.getText(self, "修改值", "数据:", text=cur)
        if not ok2:
            return
        values[name] = {"type": value_type, "value": self._parse_value(value_type, value)}
        self._refresh_detail()
        self.status.setText(f"已修改值: {name}")

    def _delete_value(self):
        if not hasattr(self, "current_node"):
            return
        sel = self._selected_value()
        if not sel:
            QMessageBox.information(self, "删除值", "请先单击选中一个值。")
            return
        name, _ = sel
        values = self.current_node.get("values", {})
        if QMessageBox.question(self, "删除值", f"确定删除值 {name}？") == QMessageBox.StandardButton.Yes:
            values.pop(name, None)
            self._refresh_detail()

    def _parse_value(self, value_type, text: str):
        if value_type == "REG_DWORD":
            try:
                return int(text.strip(), 0) if text.strip().startswith("0x") else int(text.strip())
            except (ValueError, TypeError):
                return 0
        return text

    def save(self):
        self._save_desc()
        self.store.save()
        self.status.setText("已保存到本地 (data/registry.json)")

    def closeEvent(self, event):
        self.store.save()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# 开机注册
# 每次开机时把所有已安装应用自动写入注册表
# 路径: HKEY_CURRENT_USER\Software\TianOS\Apps\<模块名>
# 供注册表编辑器 / 应用管理器 / 右键菜单等系统组件读取。
# ---------------------------------------------------------------------------

APPS_REG_PATH = ["HKEY_CURRENT_USER", "Software", "TianOS", "Apps"]


def register_all_apps_on_boot() -> int:
    """开机注册：扫描所有已安装应用并写入 HKEY_CURRENT_USER\\Software\\TianOS\\Apps。
    返回本次注册的应用数量。任何异常都不会阻塞系统启动。
    """
    try:
        from apps import register_all_apps
        count = register_all_apps(save=True)
        print(f"[Registry] 应用注册完成: {count} 个应用 -> "
              f"{chr(92).join(APPS_REG_PATH)}")
        return count
    except Exception as e:
        print(f"[Registry] 开机应用注册失败(忽略): {e}")
        return 0