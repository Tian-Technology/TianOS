"""
TianOS 应用商店 (App Store)
============================
联网浏览官方应用商店（http://tiantech.zjjsw.com/TianOS/AppStore/），
列出其中的可用应用（读取对应 .py 文件内的说明信息），
可搜索、下载（使用 TianOS 自带下载器）并安装（使用 TianOS 应用安装器）。
"""

APP_NAME = "应用商店"
APP_ICON = "🛒"
APP_COLOR = "#ff9900"

import os
import re
import json
from urllib.parse import urljoin, unquote

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

STORE_URL = "http://tiantech.zjjsw.com/TianOS/AppStore/"


# ---------------------------------------------------------------------------
# 后台线程：抓取商店目录 → 解析 .py 文件 → 读取元数据
# ---------------------------------------------------------------------------

class _StoreFetchWorker(QThread):
    progress = pyqtSignal(int, int)      # current, total
    done = pyqtSignal(list)              # list[dict]
    failed = pyqtSignal(str)

    def __init__(self, url: str = STORE_URL, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            import requests
            self._requests = requests
        except Exception:
            self.failed.emit("缺少 requests 库，无法连接应用商店")
            return

        # 1) 尝试解析开放式目录列表中的 *.py 链接
        seen = self._parse_dir_listing(self.url)
        source = "目录列表"

        # 2) 目录列表禁用/为空 → 回退到清单文件（apps.json / index.json ...）
        if not seen:
            seen, source = self._parse_manifest()
            if seen:
                self.progress.emit(0, len(seen))

        if not seen:
            self.failed.emit(
                "无法获取应用列表：服务器目录列表已禁用且未找到清单文件。\n"
                "根目录: " + self.url + "\n"
                "请在服务端开启目录索引，或在目录中放置 apps.json 清单文件。")
            return

        items = []
        total = len(seen)
        for i, fn in enumerate(sorted(seen)):
            meta = self._fetch_meta(seen[fn], fn)
            items.append(meta)
            self.progress.emit(i + 1, total)
        self.done.emit(items)

    def _parse_dir_listing(self, url: str) -> dict:
        """解析目录列表 HTML 中的 *.py 链接，{文件名: 绝对URL}"""
        seen = {}
        try:
            r = self._requests.get(url, timeout=20)
            html = r.text
        except Exception:
            return seen
        for link in re.findall(r'href=[\'"]([^\'"]+)[\'"]', html, re.I):
            href = link.split("#")[0].split("?")[0]
            fn = os.path.basename(unquote(href))
            if fn.endswith(".py"):
                seen[fn] = urljoin(url, href)
        return seen

    def _parse_manifest(self) -> dict:
        """从清单文件读取应用列表，{文件名: 绝对URL}"""
        for mf in ("apps.json", "index.json", "manifest.json",
                   "apps.txt", "index.txt", "list.txt"):
            url = urljoin(self.url, mf)
            try:
                r = self._requests.get(url, timeout=15)
                if r.status_code != 200:
                    continue
                text = r.text
            except Exception:
                continue

            result = {}
            if mf.endswith(".json"):
                try:
                    data = json.loads(text)
                except Exception:
                    data = None
                if isinstance(data, list):
                    for entry in data:
                        if isinstance(entry, dict):
                            fn = entry.get("file") or entry.get("name")
                            if fn and str(fn).endswith(".py"):
                                result[str(fn)] = urljoin(self.url, str(fn))
                elif isinstance(data, dict):
                    for key, entry in data.items():
                        if isinstance(entry, dict):
                            fn = entry.get("file") or key
                            if str(fn).endswith(".py"):
                                result[str(fn)] = urljoin(self.url, str(fn))
                            elif isinstance(key, str) and key.endswith(".py"):
                                result[key] = urljoin(self.url, key)
            else:
                for line in text.splitlines():
                    fn = line.strip().strip('"').strip("'")
                    if not fn:
                        continue
                    if not fn.endswith(".py"):
                        fn += ".py"
                    result[fn] = urljoin(self.url, fn)
            if result:
                return result, f"清单({mf})"
        return {}, ""

    def _fetch_meta(self, url: str, fn: str) -> dict:
        """获取 .py 源码并提取应用说明信息（不执行远程代码）"""
        meta = {
            "name": os.path.splitext(fn)[0],
            "icon": "📦",
            "color": "#00ccff",
            "desc": "",
            "file": fn,
            "url": url,
        }
        try:
            import requests
            src = requests.get(url, timeout=15).text
        except Exception:
            src = ""

        def pick(pattern):
            m = re.search(pattern, src)
            return m.group(1).strip() if m else ""

        name = pick(r'APP_NAME\s*=\s*["\']([^"\']+)["\']')
        icon = pick(r'APP_ICON\s*=\s*["\']([^"\']+)["\']')
        color = pick(r'APP_COLOR\s*=\s*["\']([^"\']+)["\']')
        desc = pick(r'APP_DESCRIPTION\s*=\s*["\']([^"\']+)["\']')
        if not desc:
            dm = re.search(r'"""[ \t]*\n?[ \t]*(.*?)"""', src, re.S)
            if dm and dm.group(1).strip():
                desc = dm.group(1).strip().splitlines()[0]
        if name:
            meta["name"] = name
        if icon:
            meta["icon"] = icon
        if color and color.startswith("#"):
            meta["color"] = color[:7]
        if desc:
            meta["desc"] = desc
        return meta


# ---------------------------------------------------------------------------
# 应用商店主窗口
# ---------------------------------------------------------------------------

class AppStore(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("应用商店")
        self.setMinimumSize(720, 540)

        self._items: list = []
        self._install_worker = None

        self._build_ui()
        QTimer.singleShot(0, self._load)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        self.setStyleSheet("background-color:#151824;")

        title = QLabel("🛒 应用商店")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setStyleSheet("color:#ff9900;")
        layout.addWidget(title)

        sub = QLabel(f"来源：{STORE_URL}")
        sub.setStyleSheet("color:#5a6688;")
        layout.addWidget(sub)

        # 搜索栏
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索应用…")
        self.search.setClearButtonEnabled(True)
        self.search.setStyleSheet(self._input_style())
        self.search.textChanged.connect(self._apply_filter)
        row.addWidget(self.search, 1)

        self.refresh_btn = QPushButton("↻ 刷新")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setStyleSheet(self._btn_style())
        self.refresh_btn.clicked.connect(self._load)
        row.addWidget(self.refresh_btn)

        self.install_btn = QPushButton("⬇ 下载并安装")
        self.install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_btn.setStyleSheet(self._accent_style())
        self.install_btn.clicked.connect(self._install_current)
        row.addWidget(self.install_btn)
        layout.addLayout(row)

        # 应用列表
        self.list = QListWidget()
        self.list.setStyleSheet("""
            QListWidget {
                background-color:#14141f;
                border:1px solid #334466; border-radius:8px;
                color:#ffffff; font-family:'Microsoft YaHei'; font-size:13px;
            }
            QListWidget::item { padding:8px 10px; border-radius:4px; }
            QListWidget::item:selected { background-color:rgba(255,153,0,0.22); }
            QListWidget::item:hover { background-color:rgba(255,255,255,0.08); }
        """)
        self.list.itemDoubleClicked.connect(lambda _i: self._install_current())
        layout.addWidget(self.list, 1)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setStyleSheet("""
            QProgressBar { border:none; border-radius:3px; background:#242c42; text-align:center; }
            QProgressBar::chunk { background:#ff9900; border-radius:3px; }
        """)
        layout.addWidget(self.progress)

        self.status = QLabel("点击“刷新”连接应用商店…")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#ff9900;")
        layout.addWidget(self.status)

    # ---------- 样式 ----------

    def _input_style(self) -> str:
        return """
            QLineEdit { background:rgba(255,255,255,0.06); color:#e8eaf2;
                border:1px solid #2a3550; border-radius:8px; padding:0 12px; }
            QLineEdit:focus { border-color:#ff9900; }
        """

    def _btn_style(self) -> str:
        return """
            QPushButton { color:#cdd6ea; background:#1c2233; border:1px solid #2a3550;
                border-radius:8px; padding:0 14px; }
            QPushButton:hover { background:#242c42; }
        """

    def _accent_style(self) -> str:
        return """
            QPushButton { color:#231100; font-weight:bold; background:#ff9900;
                border:none; border-radius:8px; padding:0 16px; }
            QPushButton:hover { background:#ffb33d; }
            QPushButton:disabled { background:#6b5630; color:#3a2c15; }
        """

    # ---------- 数据加载 ----------

    def _load(self):
        self._items = []
        self._apply_filter(clear=True)
        self._set_busy(True, "正在连接应用商店…")
        self._fetch = _StoreFetchWorker(STORE_URL, self)
        self._fetch.progress.connect(self._on_fetch_progress)
        self._fetch.done.connect(self._on_fetch_done)
        self._fetch.failed.connect(self._on_fetch_failed)
        self._fetch.start()

    def _on_fetch_progress(self, now, total):
        self.progress.setVisible(True)
        self.progress.setMaximum(total)
        self.progress.setValue(now)
        self._set_status(f"正在读取应用信息 {now}/{total} …")

    def _on_fetch_done(self, items):
        self._set_busy(False)
        self._items = items
        self._apply_filter()

    def _on_fetch_failed(self, err):
        self._set_busy(False)
        self._set_status("❌ " + err)
        QMessageBox.warning(self, "应用商店", err)

    def _set_busy(self, busy: bool, msg: str = ""):
        self.refresh_btn.setEnabled(not busy)
        self.install_btn.setEnabled(not busy)
        if msg:
            self._set_status(msg)
        if not busy:
            self.progress.setVisible(False)

    def _set_status(self, msg: str):
        self.status.setText(msg)

    # ---------- 列表 ----------

    def _installed(self, module: str) -> bool:
        try:
            from apps import app_registry
            return app_registry.get_app(module) is not None
        except Exception:
            return False

    def _apply_filter(self, _t=None, clear: bool = False):
        if clear:
            self.list.clear()
            return
        kw = self.search.text().strip().lower()
        self.list.clear()
        for meta in self._items:
            hay = f"{meta.get('name', '')} {meta.get('file', '')}".lower()
            if kw and kw not in hay:
                continue
            self.list.addItem(self._make_item(meta))

    def _make_item(self, meta) -> QListWidgetItem:
        module = os.path.splitext(meta["file"])[0]
        installed = self._installed(module)
        icon = meta.get("icon", "📦")
        name = meta.get("name", module)
        desc = meta.get("desc", "（暂无简介）")
        flag = "✓ 已安装" if installed else "未安装"
        text = f"{icon}  {name}   ·   {desc}   ·   [{flag}]"
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, meta)
        if installed:
            item.setForeground(Qt.GlobalColor.gray)
        return item

    def _selected_meta(self):
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ---------- 下载并安装（使用 TianOS 下载器 + 应用安装器） ----------

    def _install_current(self):
        meta = self._selected_meta()
        if not meta:
            QMessageBox.information(self, "提示", "请先在列表中选择要安装的应用。")
            return
        module = os.path.splitext(meta["file"])[0]
        if self._installed(module):
            QMessageBox.information(self, "已安装", f"应用“{meta['name']}”已经安装。")
            return

        from apps.downloader import TianDownloader, _DownloadWorker
        dl = TianDownloader()
        dl_dir = dl._default_dir()
        os.makedirs(dl_dir, exist_ok=True)
        dest = self._unique_path(os.path.join(dl_dir, meta["file"]))

        self._set_busy(True, f"正在通过 Tian 下载器下载 “{meta['name']}”…")
        self.progress.setVisible(True)
        self.progress.setMaximum(0)
        self.progress.setValue(0)

        self._install_worker = _DownloadWorker(meta["url"], dest)
        self._install_worker.finished.connect(
            lambda p, m=meta: self._on_download_finished(p, m))
        self._install_worker.failed.connect(self._on_download_failed)
        self._install_worker.start()

    def _on_download_finished(self, path, meta):
        self._set_busy(False, f"下载完成，正在使用应用安装器安装…")
        self.progress.setVisible(False)
        try:
            from apps.app_manager import install_app
            result = install_app(path)
        except Exception as e:
            result = f"安装失败：{e}"
        self._set_status(result)
        self._apply_filter()
        QMessageBox.information(self, "安装结果", result)

    def _on_download_failed(self, err):
        self._set_busy(False, "❌ 下载失败：" + err)
        self.progress.setVisible(False)
        QMessageBox.warning(self, "下载失败", err)

    def _unique_path(self, path):
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        i = 1
        while True:
            cand = f"{base} ({i}){ext}"
            if not os.path.exists(cand):
                return cand
            i += 1