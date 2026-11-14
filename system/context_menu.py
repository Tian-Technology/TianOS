"""
TianOS 右键菜单配置系统
菜单内容结构化的存储于:
  1. data/contextmenus.json   (本地持久化)
  2. 注册表 (data/registry.json, HKEY_CURRENT_USER\\Software\\TianOS\\ContextMenus)
读取优先级: 注册表 > JSON > 默认结构
"""

import os
import json
import shutil

APP_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DATA_DIR = os.path.join(APP_ROOT, "data")
MENU_FILE = os.path.join(DATA_DIR, "contextmenus.json")

# 注册表存储位置
REG_KEY = ["HKEY_CURRENT_USER", "Software", "TianOS", "ContextMenus"]
REG_VALUE_NAME = "menu_config"

# 默认菜单结构
DEFAULT_MENUS = {
    "desktop": [
        {"action": "new", "label": "新建", "submenu": [
            {"action": "new_folder", "label": "文件夹"},
            {"action": "new_text", "label": "文本文件"},
        ]},
        {"action": "copy", "label": "复制"},
        {"action": "paste", "label": "粘贴"},
        {"separator": True},
        {"action": "refresh", "label": "刷新桌面"},
        {"action": "settings", "label": "显示设置"},
        {"action": "terminal", "label": "在终端中打开"},
    ],
    "file": [
        {"action": "open", "label": "打开"},
        {"action": "edit", "label": "编辑"},
        {"separator": True},
        {"action": "copy", "label": "复制"},
        {"action": "cut", "label": "剪切"},
        {"action": "rename", "label": "重命名"},
        {"action": "delete", "label": "删除"},
        {"separator": True},
        {"action": "properties", "label": "属性"},
    ],
    "taskbar": [
        {"action": "run", "label": "运行..."},
        {"action": "terminal", "label": "在终端中打开"},
        {"action": "task_manager", "label": "任务管理器"},
        {"action": "system_info", "label": "系统"},
        {"separator": True},
        {"action": "settings", "label": "显示设置"},
        {"action": "taskbar_settings", "label": "任务栏设置"},
    ],
}

# 文件剪贴板（跨模块共享复制/剪切的文件路径）
_clipboard_path: str = None
_clipboard_mode: str = None   # "copy" 或 "cut"


# ---------------------------------------------------------------------------
# 文件剪贴板
# ---------------------------------------------------------------------------

def set_clipboard(path: str, mode: str):
    global _clipboard_path, _clipboard_mode
    _clipboard_path = path
    _clipboard_mode = mode


def get_clipboard():
    return _clipboard_path, _clipboard_mode


# ---------------------------------------------------------------------------
# 存储
# ---------------------------------------------------------------------------

def _registry_store():
    from apps.registry import RegistryStore
    return RegistryStore()


def _write_registry(data: dict):
    """把菜单配置写入注册表数据 (data/registry.json)"""
    from apps.registry import RegistryStore
    store = _registry_store()
    node = store.data
    # 逐级创建键
    for part in REG_KEY[:-1]:
        part_node = node.get(part)
        if part_node is None:
            part_node = {"desc": "", "values": {}, "children": {}}
            node[part] = part_node
        node = part_node["children"]
    # 确保目标键存在
    target = node.get(REG_KEY[-1])
    if target is None:
        target = {"desc": "TianOS 右键菜单配置", "values": {}, "children": {}}
        node[REG_KEY[-1]] = target
    values = target.setdefault("values", {})
    values[REG_VALUE_NAME] = {
        "type": "REG_SZ",
        "value": json.dumps(data, ensure_ascii=False, indent=2),
    }
    store.save()


def _read_registry():
    try:
        store = _registry_store()
    except Exception as e:
        print(f"[ContextMenu] 读取注册表失败: {e}")
        return None
    node = store.data
    for part in REG_KEY[:-1]:
        part_node = node.get(part)
        if not part_node:
            return None
        node = part_node["children"]
    target = node.get(REG_KEY[-1])
    if not target:
        return None
    info = target.get("values", {}).get(REG_VALUE_NAME)
    if not info:
        return None
    try:
        d = json.loads(info.get("value", ""))
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return None


def _read_json():
    if not os.path.exists(MENU_FILE):
        return None
    try:
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def load_menus() -> dict:
    """读取菜单配置（优先级: 注册表 > JSON > 默认）"""
    data = _read_registry()
    if data is None:
        data = _read_json()
    if data is None:
        data = {}
    # 合并默认结构，确保新增的菜单类型（如 taskbar）在旧配置缺失时仍然存在
    merged = json.loads(json.dumps(DEFAULT_MENUS))
    for key, val in data.items():
        merged[key] = val
    return merged


def save_menus(data: dict):
    """保存菜单配置: 写入 JSON + 注册表"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(MENU_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ContextMenu] JSON 保存失败: {e}")
    try:
        _write_registry(data)
    except Exception as e:
        print(f"[ContextMenu] 注册表写入失败: {e}")


def get_desktop_menus() -> list:
    return load_menus().get("desktop", [])


def get_file_menus() -> list:
    return load_menus().get("file", [])


# ---------------------------------------------------------------------------
# 构建 QMenu
# ---------------------------------------------------------------------------

def build_menu(items: list, parent, on_action) -> "QMenu":
    """根据菜单配置构建 QMenu，action 触发时回调 on_action(action)"""
    from PyQt6.QtWidgets import QMenu

    menu = QMenu(parent)
    menu.setStyleSheet("""
        QMenu { background-color: #1a1a3a; color: #ffffff;
                border: 1px solid #334466; border-radius: 6px; padding: 4px; }
        QMenu::item { padding: 6px 26px; border-radius: 3px; background: transparent; }
        QMenu::item:selected { background-color: #00ccff; color: #000000; }
        QMenu::item:disabled { color: #556677; }
        QMenu::separator { height: 1px; background: #334466; margin: 4px 8px; }
        QMenu::indicator { width: 14px; }
    """)

    def _build(m, list_items, handler):
        for it in list_items:
            if it.get("separator"):
                m.addSeparator()
                continue
            label = it.get("label", it.get("action", ""))
            action_key = it.get("action", "")
            if it.get("submenu"):
                sub = QMenu(label, m)
                sub.setStyleSheet(m.styleSheet())
                _build(sub, it["submenu"], handler)
                m.addMenu(sub)
            else:
                act = m.addAction(label)
                if it.get("enabled") is False:
                    act.setEnabled(False)
                act.triggered.connect(lambda _=False, a=action_key: handler(a))

    _build(menu, items, on_action)
    return menu