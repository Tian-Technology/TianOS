"""
TianOS 文件管理器
读取真实本地文件系统，支持打开文件夹、打开文件、前后退/上级/刷新/地址栏跳转。
"""

APP_NAME = "文件管理器"
APP_ICON = "📁"
APP_ICON_FILE = "imageres 266.png"
APP_COLOR = "#ffcc00"

import os
import re
import zipfile

import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTreeView, QHBoxLayout, QPushButton,
    QLineEdit, QDialog, QPlainTextEdit, QScrollArea
)
from PyQt6.QtCore import QDir, Qt, QFileInfo
from PyQt6.QtGui import QFont, QFileSystemModel, QPixmap

# 内置可查看的文本类扩展名
_TEXT_EXTS = {".txt", ".md", ".py", ".json", ".ini", ".cfg", ".log",
              ".conf", ".csv", ".xml", ".html", ".css", ".js", ".sh",
              ".bat", ".cmd", ".reg", ".license"}
# 内置可查看的图片扩展名
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".ico",
               ".webp", ".tif", ".tiff"}
# Office 文档扩展名（用内置文本提取查看，不使用十六进制）
_OFFICE_EXTS = {".docx", ".docm", ".xlsx", ".xlsm", ".pptx", ".pptm",
                ".odt", ".ods", ".odp", ".doc", ".xls", ".ppt", ".rtf",
                ".pdf", ".zip", ".rar", ".7z"}


class TextViewer(QDialog):
    """简易文本查看器"""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(os.path.basename(file_path))
        self.resize(700, 520)
        layout = QVBoxLayout(self)
        head = QLabel(f"   {file_path}")
        head.setStyleSheet("color:#8888ff; font-size:12px;")
        layout.addWidget(head)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #101022;
                color: #00ff99;
                font-family: Consolas;
                font-size: 13px;
                border: 1px solid #334466;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.text, 1)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            try:
                with open(file_path, "r", encoding="gbk") as f:
                    content = f.read()
            except Exception as e:
                content = f"[无法读取文件] {e}"
        self.text.setPlainText(content)


class ImageViewer(QDialog):
    """内置图片查看器"""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"图片查看器 - {os.path.basename(file_path)}")
        self.resize(720, 560)
        layout = QVBoxLayout(self)
        head = QLabel(f"   {file_path}")
        head.setStyleSheet("color:#8888ff; font-size:12px;")
        layout.addWidget(head)

        pix = QPixmap(file_path)
        if pix.isNull():
            QLabel(f"无法加载图片: {os.path.basename(file_path)}").show()
        self.img = QLabel()
        self.img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scaled = pix.scaled(680, 500, Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
        self.img.setPixmap(scaled)
        self.img.setStyleSheet("background-color:#0a0a1a; border:1px solid #334466;")

        scroll = QScrollArea()
        scroll.setWidget(self.img)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:1px solid #334466; border-radius:6px; background:#0a0a1a; }")
        layout.addWidget(scroll, 1)

        info = QLabel(f"  {pix.width()} × {pix.height()} px")
        info.setStyleSheet("color:#556677; font-size:10px;")
        layout.addWidget(info)


class HexViewer(QDialog):
    """内置十六进制查看器"""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"十六进制查看器 - {os.path.basename(file_path)}")
        self.resize(760, 520)
        layout = QVBoxLayout(self)
        head = QLabel(f"   {file_path}")
        head.setStyleSheet("color:#8888ff; font-size:12px;")
        layout.addWidget(head)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #101022;
                color: #00ff99;
                font-family: Consolas;
                font-size: 12px;
                border: 1px solid #334466;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.text, 1)

        try:
            with open(file_path, "rb") as f:
                data = f.read()
            lines = []
            for i in range(0, len(data), 16):
                chunk = data[i:i + 16]
                hex_part = " ".join(f"{b:02X}" for b in chunk).ljust(48)
                asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                lines.append(f"{i:08X}   {hex_part}   |{asc}|")
            self.text.setPlainText("\n".join(lines) if lines else "(空文件)")
        except Exception as e:
            self.text.setPlainText(f"[无法读取文件] {e}")


class OfficeViewer(QDialog):
    """内置 Office 文档查看器（提取 zip/XML 中的可读文本）"""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"文档查看器 - {os.path.basename(file_path)}")
        self.resize(720, 540)
        layout = QVBoxLayout(self)

        head = QLabel(f"   {file_path}  |  {self._fmt_size(file_path)}")
        head.setStyleSheet("color:#8888ff; font-size:12px;")
        layout.addWidget(head)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #101022;
                color: #00ff99;
                font-family: Microsoft YaHei;
                font-size: 13px;
                border: 1px solid #334466;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.text, 1)

        # 提取并显示较为可读的内容
        text = self._extract(file_path)
        self.text.setPlainText(text if text else "(未能在文档中提取到可读文本)")

        note = QLabel("  提示: TianOS 内置查看器仅提取文档文本内容，如需完整排版请使用支持的应用。")
        note.setStyleSheet("color:#556677; font-size:10px;")
        layout.addWidget(note)

    @staticmethod
    def _fmt_size(path: str) -> str:
        try:
            size = os.path.getsize(path)
            for unit in ("B", "KB", "MB", "GB"):
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024
            return f"{size:.1f} TB"
        except Exception:
            return ""

    @staticmethod
    def _extract(path: str) -> str:
        """从 zip 压缩的 Office 文档中提取文本"""
        try:
            with zipfile.ZipFile(path) as z:
                collected = []
                for name in z.namelist():
                    if not name.lower().endswith((".xml",)):
                        continue
                    try:
                        content = z.read(name).decode("utf-8", errors="ignore")
                    except Exception:
                        continue
                    # 提取 <t>...</t> 或 <a:t>...</a:t> 中的文本
                    parts = re.findall(
                        r"<[A-Za-z0-9_-]*:?t[^>]*>(.*?)</[A-Za-z0-9_-]*:?t>",
                        content, re.S | re.I)
                    if parts:
                        collected.append("\n".join(p.strip() for p in parts if p.strip()))
                return "\n\n".join(collected)
        except Exception:
            return ""


class FileManager(QWidget):
    """文件管理器 - 真实文件系统"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("文件管理器")
        self.setMinimumSize(720, 500)

        self._history: list = []   # 访问历史
        self._history_pos = -1

        # 系统根目录 = 项目根目录 (apps/ 的上级)，只允许访问该目录及其子目录
        self._root = os.path.normpath(os.path.abspath(
            os.path.dirname(os.path.dirname(__file__))))

        # 文件系统模型
        self.model = QFileSystemModel()
        self.model.setFilter(QDir.Filter.NoDotAndDotDot |
                             QDir.Filter.AllDirs |
                             QDir.Filter.Files)
        try:
            self.model.setReadOnly(True)
            self.model.setOptions(QFileSystemModel.Option.DontUseCustomDirectoryIcons)
        except Exception:
            pass

        self._setup_ui()

        # 初始目录: 系统根目录 (项目根)
        self._navigate(self._root)

    # ---------- 界面 ----------

    def _btn(self, text, tooltip=""):
        b = QPushButton(text)
        b.setToolTip(tooltip)
        b.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.08);
                color: #cccccc;
                border: 1px solid #334466;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: rgba(0,180,255,0.15); }
            QPushButton:disabled { color: #445566; }
        """)
        return b

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("TianOS 文件管理器")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffcc00;")
        layout.addWidget(title)

        # 工具栏: 后退/前进/上级/刷新 | 地址栏 | 前往
        toolbar = QHBoxLayout()
        self.btn_back = self._btn("←", "后退")
        self.btn_forward = self._btn("→", "前进")
        self.btn_up = self._btn("↑", "上级")
        self.btn_refresh = self._btn("↻", "刷新")
        for b in (self.btn_back, self.btn_forward, self.btn_up, self.btn_refresh):
            toolbar.addWidget(b)

        self.address = QLineEdit()
        self.address.setPlaceholderText("输入目录路径后回车")
        self.address.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255,255,255,0.07);
                color: #ffffff;
                border: 1px solid #334466;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #00ccff; }
        """)
        self.address.returnPressed.connect(self._go_to_address)
        toolbar.addWidget(self.address, 1)

        go_btn = self._btn("前往")
        go_btn.clicked.connect(self._go_to_address)
        toolbar.addWidget(go_btn)
        layout.addLayout(toolbar)

        # 文件列表
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        for col in (0, 1, 2, 3):
            self.tree.setColumnWidth(col, 200 if col == 0 else 90)
        self.tree.setIndentation(20)
        self.tree.setSortingEnabled(True)
        self.tree.setStyleSheet("""
            QTreeView {
                background-color: #151530;
                color: #cccccc;
                border: 1px solid #334466;
                border-radius: 6px;
                font-size: 12px;
                alternate-background-color: #181838;
            }
            QTreeView::item:hover { background-color: rgba(0,180,255,0.1); }
            QTreeView::item:selected { background-color: rgba(0,180,255,0.25); color: #ffffff; }
        """)
        self.tree.setAlternatingRowColors(True)
        self.tree.doubleClicked.connect(self._on_activated)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_context_menu)
        layout.addWidget(self.tree, 1)

        # 状态栏
        self.status = QLabel()
        self.status.setStyleSheet("color: #666688; font-size: 10px; padding: 4px;")
        layout.addWidget(self.status)

        # 信号
        self.btn_back.clicked.connect(self._go_back)
        self.btn_forward.clicked.connect(self._go_forward)
        self.btn_up.clicked.connect(self._go_up)
        self.btn_refresh.clicked.connect(self._refresh)

    # ---------- 导航 ----------

    def _is_within_root(self, path: str) -> bool:
        """判断 path 是否在系统根目录内"""
        try:
            root = os.path.normcase(os.path.abspath(self._root))
            p = os.path.normcase(os.path.abspath(path))
            return os.path.commonpath([root, p]) == root
        except ValueError:
            return False

    def _navigate(self, path: str):
        """跳转到 path 目录（限制在系统根目录内）"""
        if not os.path.isdir(path):
            return False
        path = os.path.abspath(path)
        if not self._is_within_root(path):
            self.status.setText("⚠ 只能访问系统目录（TianOS 根目录）以内，已阻止越界访问")
            return False
        self.model.setRootPath(path)
        idx = self.model.index(path)
        self.tree.setRootIndex(idx)

        # 记录历史
        if (self._history_pos < 0 or
                self._history[self._history_pos] != path):
            # 丢弃当前位置之后的历史
            self._history = self._history[: self._history_pos + 1] + [path]
            self._history_pos = len(self._history) - 1

        self.address.setText(path)
        self._update_status()
        self._update_buttons()
        return True

    def _go_to_address(self):
        path = self.address.text().strip().strip('"')
        if not path:
            return
        if not self._is_within_root(path):
            self.status.setText("⚠ 只能访问系统目录（TianOS 根目录）以内的路径")
            return
        if os.path.isdir(path):
            self._navigate(path)
        else:
            self.status.setText(f"路径不存在: {path}")

    def _go_up(self):
        if self._history_pos < 0:
            return
        parent = os.path.dirname(self._history[self._history_pos])
        if parent and parent != self._current_path():
            self._navigate(parent)

    def _current_path(self):
        if self._history_pos >= 0:
            return self._history[self._history_pos]
        return os.path.abspath(os.sep)

    def _go_back(self):
        if self._history_pos > 0:
            self._history_pos -= 1
            self._apply_history()

    def _go_forward(self):
        if self._history_pos < len(self._history) - 1:
            self._history_pos += 1
            self._apply_history()

    def _apply_history(self):
        path = self._history[self._history_pos]
        self.model.setRootPath(path)
        self.tree.setRootIndex(self.model.index(path))
        self.address.setText(path)
        self._update_status()
        self._update_buttons()

    def _refresh(self):
        self._apply_history()

    def _update_status(self):
        path = self._current_path()
        try:
            items = os.listdir(path)
            dirs = sum(1 for i in items if os.path.isdir(os.path.join(path, i)))
            files = len(items) - dirs
            self.status.setText(f"  {path}  |  {len(items)} 项  ({dirs} 文件夹, {files} 文件)")
        except PermissionError:
            self.status.setText(f"  {path}  |  无权限访问")

    def _update_buttons(self):
        self.btn_back.setEnabled(self._history_pos > 0)
        self.btn_forward.setEnabled(self._history_pos < len(self._history) - 1)
        self.btn_up.setEnabled(self._current_path() != os.path.dirname(self._current_path()))

    # ---------- 打开 ----------

    def _on_activated(self, index):
        path = self.model.filePath(index)
        if self.model.isDir(index):
            if os.path.isdir(path):
                self._navigate(path)
        else:
            self._open_file(path)

    def _open_file(self, path: str):
        """在 TianOS 内部打开文件，不调用宿主机软件"""
        ext = os.path.splitext(path)[1].lower()
        if ext in _TEXT_EXTS:
            viewer = TextViewer(path, self)
            viewer.exec()
        elif ext in _IMAGE_EXTS:
            viewer = ImageViewer(path, self)
            viewer.exec()
        elif ext in _OFFICE_EXTS:
            viewer = OfficeViewer(path, self)
            viewer.exec()
        else:
            viewer = HexViewer(path, self)
            viewer.exec()

    def _show_text(self, path: str):
        viewer = TextViewer(path, self)
        viewer.exec()

    # ---------- 文件右键菜单 ----------

    def _tree_context_menu(self, pos):
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        from system.context_menu import build_menu, get_file_menus, set_clipboard

        index = self.tree.indexAt(pos)
        path = self.model.filePath(index) if index.isValid() else None
        if not path or not os.path.exists(path):
            # 空白区域 → 显示当前目录级右键菜单（任意位置右击都有菜单）
            self._folder_context_menu(self.tree.viewport().mapToGlobal(pos))
            return
        is_dir = os.path.isdir(path)

        def on_action(action: str):
            try:
                self._perform_file_action(action, path, is_dir)
            except Exception as e:
                QMessageBox.warning(self, "操作失败", str(e))

        menu = build_menu(get_file_menus(), self, on_action)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _perform_file_action(self, action: str, path: str, is_dir: bool):
        import shutil
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        from system.context_menu import get_clipboard, set_clipboard

        if action == "open":
            if is_dir:
                self._navigate(path)
            else:
                self._open_file(path)
        elif action == "edit":
            self._open_file(path)
        elif action == "copy":
            set_clipboard(path, "copy")
            self.status.setText(f"  已复制: {os.path.basename(path)}")
        elif action == "cut":
            set_clipboard(path, "cut")
            self.status.setText(f"  已剪切: {os.path.basename(path)}")
        elif action == "delete":
            ret = QMessageBox.question(
                self, "删除", f"确定删除“{os.path.basename(path)}”吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret == QMessageBox.StandardButton.Yes:
                try:
                    if is_dir:
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    parent = os.path.dirname(path)
                    if self._current_path() == parent:
                        self._refresh()
                    self.status.setText(f"  已删除: {os.path.basename(path)}")
                except Exception as e:
                    QMessageBox.warning(self, "删除失败", str(e))
        elif action == "rename":
            new, ok = QInputDialog.getText(
                self, "重命名", "新名称:", text=os.path.basename(path))
            if ok and new and new != os.path.basename(path):
                new_path = os.path.join(os.path.dirname(path), new)
                try:
                    os.rename(path, new_path)
                    self._refresh()
                    self.status.setText(f"  已重命名为: {new}")
                except Exception as e:
                    QMessageBox.warning(self, "重命名失败", str(e))
        elif action == "properties":
            size = self._dir_size(path) if is_dir else os.path.getsize(path)
            info = QFileInfo(path)
            QMessageBox.information(
                self, "属性",
                f"名称: {os.path.basename(path)}\n"
                f"位置: {path}\n"
                f"类型: {'文件夹' if is_dir else '文件'}\n"
                f"大小: {self._fmt_bytes(size)}\n"
                f"修改时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info.lastModified().toSecsSinceEpoch()))}")

    def _folder_context_menu(self, global_pos):
        """文件区空白处右键：显示当前目录级右键菜单（新建 / 粘贴 / 刷新 / 属性）"""
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        from system.context_menu import build_menu, get_clipboard

        current_dir = self._current_path()

        def on_action(action: str):
            try:
                self._perform_folder_action(action)
            except Exception as e:
                QMessageBox.warning(self, "操作失败", str(e))

        # 剪贴板中有可用的复制/剪切内容时，"粘贴"才可用
        clip_path, _clip_mode = get_clipboard()
        has_paste = bool(clip_path and os.path.exists(clip_path))

        items = [
            {"action": "new", "label": "新建", "submenu": [
                {"action": "new_folder", "label": "文件夹"},
                {"action": "new_text", "label": "文本文件"},
            ]},
            {"action": "paste", "label": "粘贴", "enabled": has_paste},
            {"separator": True},
            {"action": "refresh", "label": "刷新"},
            {"separator": True},
            {"action": "properties", "label": f"属性: {os.path.basename(current_dir)}"},
        ]

        menu = build_menu(items, self, on_action)
        menu.exec(global_pos)

    def _perform_folder_action(self, action: str):
        """处理当前目录级右键菜单的动作"""
        import shutil
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        from system.context_menu import set_clipboard, get_clipboard

        current_dir = self._current_path()

        if action == "new_folder":
            name, ok = QInputDialog.getText(self, "新建文件夹", "文件夹名称:")
            if ok and name:
                path = os.path.join(current_dir, name)
                try:
                    os.makedirs(path, exist_ok=False)
                    self._refresh()
                    self.status.setText(f"  已创建文件夹: {name}")
                except Exception as e:
                    QMessageBox.warning(self, "创建失败", str(e))

        elif action == "new_text":
            name, ok = QInputDialog.getText(
                self, "新建文本文件", "文件名:", text="新建文本文件.txt")
            if ok and name:
                path = os.path.join(current_dir, name)
                try:
                    with open(path, "w", encoding="utf-8"):
                        pass
                    self._refresh()
                    self.status.setText(f"  已创建文件: {name}")
                except Exception as e:
                    QMessageBox.warning(self, "创建失败", str(e))

        elif action == "paste":
            clip_path, _clip_mode = get_clipboard()
            if not clip_path or not os.path.exists(clip_path):
                return
            dst = os.path.join(current_dir, os.path.basename(clip_path))
            if os.path.abspath(dst) == os.path.abspath(clip_path):
                self.status.setText("  粘贴源与目标相同，已跳过")
                return
            try:
                if os.path.isdir(clip_path):
                    shutil.copytree(clip_path, dst)
                else:
                    shutil.copy2(clip_path, dst)
                set_clipboard(None, None)
                self._refresh()
                self.status.setText(f"  已粘贴: {os.path.basename(clip_path)}")
            except Exception as e:
                QMessageBox.warning(self, "粘贴失败", str(e))

        elif action == "refresh":
            self._refresh()

        elif action == "properties":
            size = self._dir_size(current_dir)
            info = QFileInfo(current_dir)
            QMessageBox.information(
                self, "属性",
                f"名称: {os.path.basename(current_dir)}\n"
                f"位置: {current_dir}\n"
                f"类型: 文件夹\n"
                f"占用空间: {self._fmt_bytes(size)}\n"
                f"修改时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info.lastModified().toSecsSinceEpoch()))}")

    @staticmethod
    def _fmt_bytes(num: float) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if num < 1024:
                return f"{num:.1f} {unit}"
            num /= 1024
        return f"{num:.1f} TB"

    @staticmethod
    def _dir_size(path: str) -> int:
        total = 0
        for root, dirs, files in os.walk(path):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except Exception:
                    pass
        return total