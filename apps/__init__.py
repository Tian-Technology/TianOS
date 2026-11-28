"""
TianOS 应用注册系统
自动扫描 apps/ 目录下的所有应用文件
"""

import os
import importlib
import inspect
from typing import Dict, List, Optional, Type

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

# ---------------------------------------------------------------------------
# 图标系统
# 所有应用/快捷方式的图标图片统一存放在 programfiles/icons/ 目录。
# 每个应用可通过 APP_ICON_FILE 指定图标文件；未指定时按名称稳定分配一个。
# ---------------------------------------------------------------------------

ICONS_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "programfiles", "icons"))

_pixmap_cache: Dict[tuple, Optional[QPixmap]] = {}
_available_icons: Optional[List[str]] = None


def _list_icons():
    global _available_icons
    if _available_icons is None:
        try:
            _available_icons = sorted(
                f for f in os.listdir(ICONS_DIR)
                if f.lower().endswith(".png"))
        except Exception:
            _available_icons = []
    return _available_icons


def icon_full_path(icon_file: str) -> str:
    """返回图标文件的完整路径"""
    if not icon_file:
        return ""
    return os.path.join(ICONS_DIR, icon_file)


def icon_exists(icon_file: str) -> bool:
    """判断图标文件是否存在"""
    if not icon_file:
        return False
    return os.path.isfile(os.path.join(ICONS_DIR, icon_file))


def fallback_icon_file(name: str) -> str:
    """按名称稳定分配一个图标文件（散列到 icons 目录中的一个）"""
    files = _list_icons()
    if not files:
        return ""
    idx = sum(name.encode("utf-8")) % len(files)
    return files[idx]


def get_icon_pixmap(icon_file: str, size: int = 48) -> Optional[QPixmap]:
    """加载并缩放图标像素图（带缓存）"""
    if not icon_file:
        return None
    key = (icon_file, size)
    if key in _pixmap_cache:
        return _pixmap_cache[key]
    pix = QPixmap(os.path.join(ICONS_DIR, icon_file))
    if pix.isNull():
        _pixmap_cache[key] = None
        return None
    scaled = pix.scaled(size, size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)
    _pixmap_cache[key] = scaled
    return scaled


def get_icon_icon(icon_file: str, size: int = 64):
    """返回 QIcon（用于按钮/菜单）"""
    from PyQt6.QtGui import QIcon
    pix = get_icon_pixmap(icon_file, size)
    return QIcon(pix) if pix else QIcon()


def resolve_app_icon_file(module_name: str, explicit: str = "") -> str:
    """确定应用的图标文件：优先显式指定，否则稳定分配"""
    if explicit and icon_exists(explicit):
        return explicit
    return fallback_icon_file(module_name)


class AppInfo:
    """应用信息"""
    def __init__(self, module_name: str, file_path: str):
        self.module_name = module_name
        self.file_path = file_path
        self.name: str = module_name  # 默认用文件名
        self.icon: str = "📄"
        self.color: str = "#00ccff"
        self.icon_file: str = ""   # 图标文件名（programfiles/icons/ 内）
        self.widget_class: Optional[Type[QWidget]] = None
        self.loaded = False
        
    def load(self) -> bool:
        """加载应用模块"""
        if self.loaded:
            return True
        try:
            spec = importlib.util.spec_from_file_location(self.module_name, self.file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # 读取应用元数据
                self.name = getattr(module, 'APP_NAME', self.module_name.replace('_', ' ').title())
                self.icon = getattr(module, 'APP_ICON', '📄')
                self.color = getattr(module, 'APP_COLOR', '#00ccff')
                explicit = getattr(module, 'APP_ICON_FILE', '')
                self.icon_file = resolve_app_icon_file(self.module_name, explicit)
                
                # 查找主窗口类（必须是本模块中定义的 QWidget 子类，跳过导入的类如 QLabel）。
                # 一个模块里可能有多个辅助控件类，因此优先选择其类名与模块名/应用名匹配的类，
                # 否则退回到最后一个候选（通常主窗口类定义在文件末尾）。
                candidates: List[tuple] = []
                for name, obj in inspect.getmembers(module):
                    if (isinstance(obj, type) and
                        issubclass(obj, QWidget) and
                        obj is not QWidget and
                        name != 'AppInfo' and
                        getattr(obj, '__module__', '') == module.__name__):
                        candidates.append((name, obj))

                if candidates:
                    app_name = getattr(module, 'APP_NAME', '')
                    flat_module = self.module_name.replace('_', '').lower()
                    flat_app = app_name.replace(' ', '').lower()
                    chosen = None
                    for name, obj in candidates:
                        if name.lower() == flat_module or name.lower() == flat_app:
                            chosen = obj
                            break
                    if chosen is None:
                        # 兜底：单类取唯一类，多类取最后一个（约定主类写在末尾）
                        chosen = candidates[-1][1]
                    self.widget_class = chosen
                
                self.loaded = True
                return True
        except Exception as e:
            print(f"[APPS] 加载 '{self.module_name}' 失败: {e}")
        return False


class AppRegistry:
    """应用注册表 - 扫描 apps 目录发现应用"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._apps: Dict[str, AppInfo] = {}
            cls._instance._scan_done = False
        return cls._instance
    
    def scan(self) -> List[AppInfo]:
        """扫描 apps 目录"""
        if self._scan_done:
            return list(self._apps.values())
        
        apps_dir = os.path.dirname(os.path.abspath(__file__))
        self._apps.clear()
        
        for filename in sorted(os.listdir(apps_dir)):
            if filename == '__init__.py':
                continue
            if filename.endswith('.py'):
                module_name = filename[:-3]  # 去掉 .py
                file_path = os.path.join(apps_dir, filename)
                app_info = AppInfo(module_name, file_path)
                if app_info.load():
                    self._apps[module_name] = app_info
        
        self._scan_done = True
        return list(self._apps.values())
    
    def get_app(self, name: str) -> Optional[AppInfo]:
        """按名称获取应用"""
        if not self._scan_done:
            self.scan()
        return self._apps.get(name)
    
    def launch(self, name: str) -> Optional[QWidget]:
        """启动应用，返回窗口实例"""
        app_info = self.get_app(name)
        if app_info and app_info.widget_class:
            # 沙箱硬件检查：应用资源需求超出当前硬件上限时触发蓝屏
            try:
                from system.sandbox import assert_application_resources
                assert_application_resources(name)
            except Exception as e:
                print(f"[APPS] 启动 '{name}' 触发硬件限制: {e}")
                try:
                    from boot.bsod import handle_crash
                    handle_crash(e, phase=f"启动应用 {app_info.name}")
                except Exception as bsod_err:
                    print(f"[APPS] 蓝屏处理失败: {bsod_err}")
                return None
            try:
                widget = app_info.widget_class()
            except Exception as e:
                print(f"[APPS] 启动 '{name}' 失败: {e}")
                return None
            # 权限等校验未通过: __init__ 内已弹窗提示并被标记为拒绝加载, 不创建窗口
            if getattr(widget, "_permission_denied", False):
                return None
            return widget
        return None
    
    def launch_by_name(self, display_name: str) -> Optional[QWidget]:
        """按显示名称启动应用"""
        if not self._scan_done:
            self.scan()
        for app_info in self._apps.values():
            if app_info.name == display_name:
                return self.launch(app_info.module_name)
        return None


# 全局单例
app_registry = AppRegistry()


# ---------------------------------------------------------------------------
# 桌面快捷方式系统
# 快捷方式存放于 programfiles/desktop/，每个快捷方式是一个独立的 .py 文件，
# 通过 TARGET 指向 apps/ 中已安装的应用模块名。
# ---------------------------------------------------------------------------

DESKTOP_SHORTCUTS_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "programfiles", "desktop"))


class DesktopShortcut:
    """桌面快捷方式"""
    def __init__(self, name: str, icon: str, color: str, target: str,
                 file_path: str = "", icon_file: str = ""):
        self.name = name          # 桌面上显示的名称
        self.icon = icon
        self.color = color
        self.target = target      # 指向 apps/ 里的模块名
        self.file_path = file_path
        self.icon_file = icon_file   # 图标文件名（programfiles/icons/ 内）


def load_desktop_shortcuts() -> List[DesktopShortcut]:
    """扫描 programfiles/desktop/ 目录，加载所有快捷方式 .py 文件"""
    shortcuts: List[DesktopShortcut] = []
    if not os.path.isdir(DESKTOP_SHORTCUTS_DIR):
        return shortcuts

    for filename in sorted(os.listdir(DESKTOP_SHORTCUTS_DIR)):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(DESKTOP_SHORTCUTS_DIR, filename)
        module_name = "shortcut_" + filename[:-3]
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            target = getattr(module, "TARGET", filename[:-3])
            explicit = getattr(module, 'SHORTCUT_ICON_FILE', '')
            # 优先用显式指定；否则继承目标应用的图标文件
            if explicit and icon_exists(explicit):
                icon_file = explicit
            else:
                info = app_registry.get_app(target)
                icon_file = info.icon_file if info else resolve_app_icon_file(target, "")
            shortcuts.append(DesktopShortcut(
                name=getattr(module, "SHORTCUT_NAME",
                             getattr(module, "APP_NAME", filename[:-3])),
                icon=getattr(module, "APP_ICON", "📄"),
                color=getattr(module, "APP_COLOR", "#00ccff"),
                target=target,
                file_path=path,
                icon_file=icon_file,
            ))
        except Exception as e:
            print(f"[SHORTCUTS] 加载 '{filename}' 失败: {e}")
    return shortcuts


def resolve_shortcut(name: str) -> Optional[DesktopShortcut]:
    """按桌面显示名称查找快捷方式，未找到返回 None"""
    for sc in load_desktop_shortcuts():
        if sc.name == name:
            return sc
    return None


# ---------------------------------------------------------------------------
# 用户桌面文件夹
# 右键“新建文件夹”创建的文件夹存放在 programfiles/desktop/ 下，
# 与快捷方式 .py 并存，会以 imageres 154.png 图标显示在桌面上。
# ---------------------------------------------------------------------------

USER_DESKTOP_DIR = DESKTOP_SHORTCUTS_DIR
FOLDER_ICON = "imageres 154.png"


def _folder_dirs():
    """programfiles/desktop 下的真实文件夹名（排除 __pycache__ 等）"""
    if not os.path.isdir(USER_DESKTOP_DIR):
        return []
    return [e for e in sorted(os.listdir(USER_DESKTOP_DIR))
            if e != "__pycache__" and
            os.path.isdir(os.path.join(USER_DESKTOP_DIR, e))]


def load_desktop_folders() -> List[str]:
    """返回用户桌面文件夹名列表"""
    return _folder_dirs()


def create_desktop_folder(name: str = "新建文件夹") -> str:
    """在桌面目录创建文件夹，返回唯一路径"""
    os.makedirs(USER_DESKTOP_DIR, exist_ok=True)
    base = os.path.join(USER_DESKTOP_DIR, name)
    path, i = base, 1
    while os.path.exists(path):
        path = f"{base} ({i})"
        i += 1
    os.makedirs(path)
    return path


def desktop_folder_path(name: str) -> Optional[str]:
    """返回名为 name 的桌面文件夹路径，不存在返回 None"""
    p = os.path.join(USER_DESKTOP_DIR, name)
    return p if os.path.isdir(p) else None


# ---------------------------------------------------------------------------
# 应用注册表注册
# 将所有已安装应用写入虚拟注册表，供注册表编辑器查看。
# 注册路径: HKEY_CURRENT_USER\Software\TianOS\Apps\<模块名>
# 每个键包含名称、图标、路径、主类等值。
# ---------------------------------------------------------------------------

REG_DESC_KEY = "desc"
REG_VALUES_KEY = "values"
REG_CHILDREN_KEY = "children"


def _ensure_reg_node(parent: dict, name: str, desc: str = "") -> dict:
    """确保子键存在并返回其节点"""
    node = parent[REG_CHILDREN_KEY].get(name)
    if node is None:
        node = {REG_DESC_KEY: desc, REG_VALUES_KEY: {}, REG_CHILDREN_KEY: {}}
        parent[REG_CHILDREN_KEY][name] = node
    return node


def _make_value(value: str, vtype: str = "REG_SZ") -> dict:
    return {"type": vtype, "value": value}


def _register_app_to_registry(root: dict, app: "AppInfo") -> None:
    """把单个应用写入注册表"""
    node = _ensure_reg_node(
        root, app.module_name,
        desc="TianOS 已安装应用")
    values = node[REG_VALUES_KEY]
    values.clear()
    values["DisplayName"] = _make_value(app.name)
    values["Name"] = _make_value(app.module_name)
    values["Icon"] = _make_value(app.icon, "REG_SZ")
    values["IconFile"] = _make_value(app.icon_file)
    values["Color"] = _make_value(app.color)
    values["Module"] = _make_value(app.module_name)
    values["Path"] = _make_value(app.file_path)
    values["MainClass"] = _make_value(
        app.widget_class.__name__ if app.widget_class else "")
    values["Status"] = _make_value("已注册")
    values["Version"] = _make_value("1.0.0")


def register_all_apps(save: bool = True) -> int:
    """扫描并注册所有应用，返回注册数量。save=False 时不写盘（仅内存）"""
    from apps.registry import RegistryStore
    store = RegistryStore()
    data = store.data

    # HKEY_CURRENT_USER\Software 根键
    cu = data.setdefault("HKEY_CURRENT_USER", {
        REG_DESC_KEY: "当前登录用户的配置",
        REG_VALUES_KEY: {}, REG_CHILDREN_KEY: {},
    })
    software = _ensure_reg_node(cu, "Software", desc="用户软件设置")
    tianos = _ensure_reg_node(software, "TianOS", desc="TianOS 系统配置")
    apps_node = _ensure_reg_node(tianos, "Apps", desc="已安装应用")

    apps = app_registry.scan()
    reg_count = 0
    for app in apps:
        _register_app_to_registry(apps_node, app)
        reg_count += 1

    if save:
        store.save()
    return reg_count