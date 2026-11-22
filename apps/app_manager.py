"""TianOS 应用安装器/卸载器"""
APP_NAME = "应用安装器"
APP_ICON = "🧰"
APP_COLOR = "#00e5a0"

import os
import sys
import shutil
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QFileDialog, QFrame, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS_DIR = os.path.join(ROOT, "apps")
SHORTCUTS_DIR = os.path.join(ROOT, "programfiles", "desktop")


def _purge_module(module_name: str):
    for key in list(sys.modules):
        if key == module_name or key == "shortcut_" + module_name:
            sys.modules.pop(key, None)


def _reset_app_registry():
    from apps import app_registry
    app_registry._scan_done = False
    app_registry._apps.clear()


def _find_desktop():
    from PyQt6.QtWidgets import QApplication
    from gui.desktop import DesktopEnvironment
    app = QApplication.instance()
    if app is None:
        return None
    for w in app.topLevelWidgets():
        if isinstance(w, DesktopEnvironment):
            return w
    return None


def read_app_meta(path: str) -> dict:
    """读取应用文件顶层的元数据（APP_NAME/APP_ICON/APP_COLOR 等）。

    注意：仅用于提取元数据声明，不实例化主窗口。
    提供 __file__/__name__ 避免依赖路径的文件无法被解析。
    """
    ns = {"__file__": path, "__name__": "app_meta_" + os.path.basename(path)[:-3]}
    try:
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        exec(compile(code, path, "exec"), ns)
    except Exception as e:
        print(f"[应用安装器] 解析应用元数据失败: {e}")
    return ns


def list_app_modules() -> list:
    names = []
    if os.path.isdir(APPS_DIR):
        for f in sorted(os.listdir(APPS_DIR)):
            if f.endswith(".py") and f != "__init__.py":
                names.append(f[:-3])
    return names


def create_shortcut_from_app(module_name: str) -> str:
    """为应用生成桌面快捷方式，返回提示信息"""
    app_path = os.path.join(APPS_DIR, module_name + ".py")
    if not os.path.exists(app_path):
        return "应用文件不存在"
    meta = read_app_meta(app_path)
    name = meta.get("APP_NAME", module_name.replace("_", " ").title())
    icon = meta.get("APP_ICON", "📦")
    color = meta.get("APP_COLOR", "#00ccff")
    icon_file = meta.get("APP_ICON_FILE", "") or ""
    sc_path = os.path.join(SHORTCUTS_DIR, module_name + ".py")
    if os.path.exists(sc_path):
        return f"快捷方式已存在：{name}"
    lines = [
        f'"""TianOS 桌面快捷方式：{name}"""',
        f'SHORTCUT_NAME = "{name}"',
        f'APP_ICON = "{icon}"',
        f'APP_COLOR = "{color}"',
        f'TARGET = "{module_name}"',
    ]
    if icon_file:
        lines.append(f'SHORTCUT_ICON_FILE = "{icon_file}"')
    os.makedirs(SHORTCUTS_DIR, exist_ok=True)
    with open(sc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return f"已生成桌面快捷方式：{name}"


def remove_shortcut_from_app(module_name: str) -> str:
    """删除应用的桌面快捷方式，返回提示信息"""
    app_path = os.path.join(APPS_DIR, module_name + ".py")
    if not os.path.exists(app_path):
        return "应用文件不存在"
    sc_path = os.path.join(SHORTCUTS_DIR, module_name + ".py")
    if not os.path.exists(sc_path):
        return f"该应用没有桌面快捷方式：{module_name}"
    os.remove(sc_path)
    try:
        os.remove(os.path.join(SHORTCUTS_DIR, "__pycache__",
                               f"shortcut_{module_name}.pyc"))
    except OSError:
        pass
    return f"已移除桌面快捷方式：{module_name}"


def has_desktop_shortcut(module_name: str) -> bool:
    """判断应用当前是否在桌面生成了快捷方式"""
    return os.path.exists(os.path.join(SHORTCUTS_DIR, module_name + ".py"))


def remove_registry_app(module_name: str):
    try:
        from apps.registry import RegistryStore
        st = RegistryStore()
        cu = st.data.get("HKEY_CURRENT_USER", {})
        children = cu.get("children")
        if not isinstance(children, dict):
            return
        software = children.get("Software")
        if not isinstance(software, dict):
            return
        sc = software.get("children")
        if not isinstance(sc, dict):
            return
        tianos = sc.get("TianOS")
        if not isinstance(tianos, dict):
            return
        apps_node = tianos.get("children", {}).get("Apps", {})
        app_children = apps_node.get("children")
        if isinstance(app_children, dict) and module_name in app_children:
            del app_children[module_name]
            st.save()
    except Exception as e:
        print(f"[应用安装器] 清理注册表失败: {e}")


def refresh_system(module_name: str):
    _purge_module(module_name)
    _reset_app_registry()
    try:
        from apps import register_all_apps
        register_all_apps(save=True)
    except Exception as e:
        print(f"[应用安装器] 刷新注册表失败: {e}")
    de = _find_desktop()
    if de is not None:
        try:
            de._init_desktop_icons()
            de.desktop.update()
        except Exception as e:
            print(f"[应用安装器] 刷新桌面图标失败: {e}")


def _same_path(a: str, b: str) -> bool:
    """比较两个路径是否指向同一位置（Windows 忽略大小写）"""
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def install_app(src_path: str, create_shortcut: bool = True) -> str:
    if not src_path or not src_path.endswith(".py"):
        return "请选择 .py 应用文件"
    basename = os.path.basename(src_path)
    dest = os.path.join(APPS_DIR, basename)
    module_name = basename[:-3]
    if _same_path(src_path, dest):
        msg = (create_shortcut_from_app(module_name) if create_shortcut
               else "未创建桌面快捷方式")
        if not create_shortcut:
            remove_shortcut_from_app(module_name)
        refresh_system(module_name)
        return f"已注册本地应用：{module_name}\n{msg}"
    if os.path.exists(dest):
        return f"安装失败：apps/ 已存在同名应用 {basename}"
    os.makedirs(APPS_DIR, exist_ok=True)
    shutil.copy2(src_path, dest)
    msg = (create_shortcut_from_app(module_name) if create_shortcut
           else "未创建桌面快捷方式")
    refresh_system(module_name)
    return f"安装成功：{basename}\n{msg}"


def uninstall_app(module_name: str) -> str:
    if module_name in ("app_manager",):
        return "系统应用（应用安装器）不可卸载"
    removed = []
    app_path = os.path.join(APPS_DIR, module_name + ".py")
    if os.path.exists(app_path):
        os.remove(app_path)
        removed.append(app_path)
    sc_path = os.path.join(SHORTCUTS_DIR, module_name + ".py")
    if os.path.exists(sc_path):
        os.remove(sc_path)
        removed.append(sc_path)
    remove_registry_app(module_name)
    refresh_system(module_name)
    if removed:
        return f"已卸载应用：{module_name}"
    return f"未找到应用：{module_name}"


class AppManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("应用安装器")
        self.setMinimumSize(640, 460)
        self._build_ui()
        self._reload_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("🧰 应用安装器 / 卸载器")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #00e5a0;")
        layout.addWidget(title)

        desc = QLabel("对 apps/ 目录中的应用进行添加或移除，自动生成桌面快捷方式并刷新图标。")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaaaaa;")
        layout.addWidget(desc)

        self.list = QListWidget()
        self.list.setStyleSheet("""
            QListWidget {
                background-color: #14141f;
                border: 1px solid #334466;
                border-radius: 8px;
                color: #ffffff;
                font-family: 'Microsoft YaHei';
                font-size: 13px;
            }
            QListWidget::item { padding: 8px 10px; border-radius: 4px; }
            QListWidget::item:selected { background-color: rgba(0, 212, 255, 0.25); }
            QListWidget::item:hover { background-color: rgba(255,255,255,0.08); }
        """)
        layout.addWidget(self.list, 1)

        opt_row = QHBoxLayout()
        self.sc_check = QCheckBox("安装时在桌面创建快捷方式")
        self.sc_check.setChecked(True)
        self.sc_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sc_check.setStyleSheet("color: #cccccc; font-family: 'Microsoft YaHei';")
        opt_row.addWidget(self.sc_check)
        opt_row.addStretch(1)
        layout.addLayout(opt_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.install_btn = QPushButton("＋ 安装新应用")
        self.uninstall_btn = QPushButton("－ 卸载选中应用")
        self.sc_toggle_btn = QPushButton("⌗ 切换快捷方式")
        self.refresh_btn = QPushButton("↻ 刷新列表")

        for b in (self.install_btn, self.uninstall_btn,
                  self.sc_toggle_btn, self.refresh_btn):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(36)
            b.setStyleSheet("""
                QPushButton {
                    background-color: #22305a;
                    color: #ffffff;
                    border: 1px solid #334466;
                    border-radius: 6px;
                    font-family: 'Microsoft YaHei';
                }
                QPushButton:hover { background-color: #2c3d70; }
            """)
            btn_row.addWidget(b)

        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #00e5a0;")
        layout.addWidget(self.status)

        self.install_btn.clicked.connect(self._on_install)
        self.uninstall_btn.clicked.connect(self._on_uninstall)
        self.sc_toggle_btn.clicked.connect(self._on_toggle_shortcut)
        self.refresh_btn.clicked.connect(self._reload_list)

    def _reload_list(self):
        self.list.clear()
        for module_name in list_app_modules():
            app_path = os.path.join(APPS_DIR, module_name + ".py")
            meta = read_app_meta(app_path)
            display = meta.get("APP_NAME", module_name)
            sc = os.path.join(SHORTCUTS_DIR, module_name + ".py")
            sc_txt = "✓ 已生成快捷方式" if os.path.exists(sc) else "✗ 无快捷方式"
            item = QListWidgetItem(f"{display}   ·   {module_name}   ({sc_txt})")
            item.setData(Qt.ItemDataRole.UserRole, module_name)
            self.list.addItem(item)

    def _selected_module(self) -> Optional[str]:
        item = self.list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_install(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 TianOS 应用文件", ROOT, "TianOS 应用 (*.py)")
        if not path:
            return
        result = install_app(path, create_shortcut=self.sc_check.isChecked())
        self.status.setText(result)
        self._reload_list()

    def _on_uninstall(self):
        module_name = self._selected_module()
        if module_name is None:
            QMessageBox.information(self, "提示", "请先在列表中选择要卸载的应用。")
            return
        ret = QMessageBox.question(
            self, "确认卸载",
            f"确定要卸载应用“{module_name}”吗？\n将删除 apps 目录中的文件及其桌面快捷方式。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        result = uninstall_app(module_name)
        self.status.setText(result)
        self._reload_list()

    def _on_toggle_shortcut(self):
        """切换选中应用的桌面快捷方式（有则删、无则建）"""
        module_name = self._selected_module()
        if module_name is None:
            QMessageBox.information(self, "提示", "请先在列表中选择要操作的应用。")
            return
        if has_desktop_shortcut(module_name):
            sc_path = os.path.join(SHORTCUTS_DIR, module_name + ".py")
            meta = read_app_meta(os.path.join(APPS_DIR, module_name + ".py"))
            name = meta.get("APP_NAME", module_name)
            ret = QMessageBox.question(
                self, "移除快捷方式",
                f"确定要移除“{name}”在桌面的快捷方式吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if ret != QMessageBox.StandardButton.Yes:
                return
            result = remove_shortcut_from_app(module_name)
        else:
            result = create_shortcut_from_app(module_name)
        refresh_system(module_name)
        self.status.setText(result)
        self._reload_list()