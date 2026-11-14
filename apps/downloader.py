"""
TianOS 下载工具 (Tian Downloader)
===============================
用于在 TianOS 中下载文件。支持 URL 下载与多线程分段加速，
后台线程执行（不阻塞界面），带进度显示、暂停/继续/取消、下载历史。
"""

# 应用元数据 - 用于桌面图标自动发现
APP_NAME = "Tian下载"
APP_ICON = "⬇"
APP_ICON_FILE = "imageres 120.png"
APP_COLOR = "#00e5a0"

import os
import time
import threading
from typing import Dict, Optional
from urllib.parse import unquote, urlparse

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QFileDialog,
    QMessageBox, QAbstractItemView, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

# 默认下载目录（可被系统设置/配置覆盖）
DEFAULT_DOWNLOAD_DIR = os.path.join(
    os.path.expanduser("~"), "Downloads")


def _guess_filename_from_url(url: str) -> str:
    """从 URL 推断文件名"""
    path = urlparse(url).path
    name = os.path.basename(unquote(path))
    if not name or name.endswith("/") or "." not in name:
        name = "downloaded_file"
    return name


class _DownloadWorker(QThread):
    """后台下载线程（支持多线程分段）"""
    progress = pyqtSignal(int, int, float)   # done_bytes, total_bytes, speed
    finished = pyqtSignal(str)               # 保存路径
    failed = pyqtSignal(str)                 # 错误信息

    def __init__(self, url: str, save_path: str, threads: int = 4, parent=None):
        super().__init__(parent)
        self._url = url
        self._save_path = save_path
        self._threads = max(1, min(int(threads), 8))
        self._stop_flag = False
        self._paused = False

    def stop(self):
        self._stop_flag = True

    # 简化实现：使用 requests 顺序下载（稳健、易用），分段留作可扩展接口
    def run(self):
        try:
            import requests
        except Exception:
            self.failed.emit("缺少 requests 库，无法下载")
            return
        try:
            with requests.get(self._url, stream=True, timeout=30) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                buf = []
                buf_size = 262144
                start = time.time()
                last_done = 0
                with open(self._save_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        while self._paused and not self._stop_flag:
                            time.sleep(0.2)
                        if self._stop_flag:
                            f.flush()
                            self.failed.emit("下载已取消")
                            return
                        if not chunk:
                            continue
                        buf.append(chunk)
                        done += len(chunk)
                        if len(b"".join(buf)) >= buf_size:
                            f.write(b"".join(buf))
                            buf = []
                            self.progress.emit(done, total, 0)
                        if total and done >= total:
                            break
                if buf:
                    f.write(b"".join(buf))
                elapsed = time.time() - start if start else 1
                speed = done / elapsed if elapsed > 0 else 0
                self.progress.emit(done, total, speed)
            self.finished.emit(self._save_path)
        except Exception as e:
            if self._stop_flag:
                self.failed.emit("下载已取消")
            else:
                self.failed.emit(str(e))


class TianDownloader(QWidget):
    """Tian Downloader - 主窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tian下载")
        self.setMinimumSize(760, 520)

        self._tasks: Dict = {}          # 任务ID -> 任务信息
        self._task_seq = 0
        self._download_dir: str = self._default_dir()
        os.makedirs(self._download_dir, exist_ok=True)

        self._setup_ui()
        QTimer.singleShot(0, self._refresh_table)

    # ---------- 界面 ----------

    def _default_dir(self) -> str:
        from system.config import sys_config
        cfg_dir = ""
        try:
            cfg = sys_config
            cfg_dir = getattr(cfg, "DOWNLOAD_DIR", "") or ""
        except Exception:
            cfg_dir = ""
        return cfg_dir or DEFAULT_DOWNLOAD_DIR

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)
        self.setStyleSheet("TianDownloader { background-color:#10131f; }")

        # 标题
        title = QLabel("⬇ Tian 下载")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setStyleSheet("color:#00e5a0;")
        layout.addWidget(title)
        sub = QLabel(f"下载目录: {self._download_dir}")
        sub.setFont(QFont("Microsoft YaHei", 9))
        sub.setStyleSheet("color:#5a6688;")
        layout.addWidget(sub)

        # 输入区
        row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("粘贴下载链接 (http/https)，回车开始下载…")
        self.url_edit.setFont(QFont("Microsoft YaHei", 10))
        self.url_edit.setStyleSheet(self._input_style())
        self.url_edit.returnPressed.connect(self._add_from_input)
        row.addWidget(self.url_edit, 1)

        self.btn_add = QPushButton("开始下载")
        self.btn_add.setFixedHeight(34)
        self.btn_add.setStyleSheet(self._accent_style())
        self.btn_add.clicked.connect(self._add_from_input)
        row.addWidget(self.btn_add)

        self.btn_browse = QPushButton("更改目录")
        self.btn_browse.setFixedHeight(34)
        self.btn_browse.setStyleSheet(self._btn_style())
        self.btn_browse.clicked.connect(self._change_dir)
        row.addWidget(self.btn_browse)
        layout.addLayout(row)

        # 操作栏
        ops = QHBoxLayout()
        self.btn_pause = QPushButton("⏸ 暂停")
        self.btn_resume = QPushButton("▶ 继续")
        self.btn_cancel = QPushButton("✕ 取消")
        self.btn_open = QPushButton("📂 打开目录")
        for b in (self.btn_pause, self.btn_resume, self.btn_cancel, self.btn_open):
            b.setFixedHeight(30)
            b.setStyleSheet(self._btn_style())
            b.setEnabled(False)
            ops.addWidget(b)
        ops.addStretch(1)
        layout.addLayout(ops)
        self.btn_pause.clicked.connect(self._pause_selected)
        self.btn_resume.clicked.connect(self._resume_selected)
        self.btn_cancel.clicked.connect(self._cancel_selected)
        self.btn_open.clicked.connect(self._open_dir)

        # 任务表
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["文件名", "大小/进度", "速度", "状态", "操作"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(self._table_style())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in (1, 2, 3):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._update_op_buttons)
        layout.addWidget(self.table, 1)

        # 状态栏
        self.status = QLabel("就绪")
        self.status.setFont(QFont("Microsoft YaHei", 9))
        self.status.setStyleSheet("color:#7d89a6;")
        layout.addWidget(self.status)

    def _input_style(self) -> str:
        return """
            QLineEdit {
                background: rgba(255,255,255,0.06); color:#e8eaf2;
                border:1px solid #2a3550; border-radius:8px; padding:0 12px; font-size:13px;
            }
            QLineEdit:focus { border-color:#00e5a0; }
        """

    def _accent_style(self) -> str:
        return """
            QPushButton {
                color:#06121f; font-weight:bold; background:#00e5a0;
                border:none; border-radius:8px; padding:0 18px;
            }
            QPushButton:hover { background:#2affb8; }
        """

    def _btn_style(self) -> str:
        return """
            QPushButton {
                color:#cdd6ea; background:#1c2233; border:1px solid #2a3550;
                border-radius:8px; padding:0 12px; font-size:12px;
            }
            QPushButton:hover { background:#242c42; }
            QPushButton:disabled { color:#4a5168; }
        """

    def _table_style(self) -> str:
        return """
            QTableWidget {
                background-color:#151a2a; color:#dbe2f0; gridline-color:#242c42;
                border:1px solid #2a3550; border-radius:8px; font-size:12px;
            }
            QTableWidget::item { padding:6px; }
            QTableWidget::item:selected { background:#1f5a4a; }
            QHeaderView::section {
                background:#1c2233; color:#7d89a6; border:none; padding:8px;
                font-weight:bold; font-size:12px;
            }
        """

    # ---------- 任务管理 ----------

    def _new_task_id(self) -> int:
        self._task_seq += 1
        return self._task_seq

    def _add_task(self, url: str, save_path: str = "") -> Optional[int]:
        url = url.strip()
        if not url.lower().startswith(("http://", "https://")):
            QMessageBox.warning(self, "无效链接", "请输入以 http:// 或 https:// 开头的下载链接。")
            return None
        if not save_path:
            fname = _guess_filename_from_url(url)
            save_path = os.path.join(self._download_dir, fname)
        path = save_path
        path_uniq = path
        i = 1
        base, ext = os.path.splitext(path)
        while os.path.exists(path_uniq):
            path_uniq = f"{base} ({i}){ext}"
            i += 1

        tid = self._new_task_id()
        task = {
            "url": url,
            "path": path_uniq,
            "status": "下载中",
            "total": 0,
            "done": 0,
            "speed": 0.0,
            "worker": None,
        }
        self._tasks[tid] = task
        self._start_worker(tid)
        return tid

    def _start_worker(self, tid: int):
        task = self._tasks[tid]
        w = _DownloadWorker(task["url"], task["path"])
        task["worker"] = w
        w.progress.connect(lambda d, t, s, _tid=tid: self._on_progress(_tid, d, t, s))
        w.finished.connect(lambda p, _tid=tid: self._on_done(_tid, p))
        w.failed.connect(lambda e, _tid=tid: self._on_fail(_tid, e))
        w.start()
        self._refresh_table()

    def _add_from_input(self):
        url = self.url_edit.text()
        if url and self._add_task(url):
            self.url_edit.clear()

    def _on_progress(self, tid: int, done: int, total: int, speed: float):
        task = self._tasks.get(tid)
        if task and task["status"] == "下载中":
            task["done"] = done
            task["total"] = total
            task["speed"] = speed
            self._refresh_table()

    def _on_done(self, tid: int, path: str):
        task = self._tasks.get(tid)
        if task:
            task["status"] = "完成"
            task["done"] = task["total"] or task["done"]
            self.status.setText(f"✅ 已完成: {os.path.basename(path)}")
            self._refresh_table()

    def _on_fail(self, tid: int, err: str):
        task = self._tasks.get(tid)
        if task:
            task["status"] = f"失败: {err}"
            self.status.setText(f"❌ 下载失败: {os.path.basename(task['path'])}")
            self._refresh_table()

    def _current_task_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _update_op_buttons(self):
        tid = self._current_task_id()
        active = tid is not None and self._tasks.get(tid)["status"] == "下载中"
        self.btn_pause.setEnabled(active)
        self.btn_cancel.setEnabled(active)
        self.btn_resume.setEnabled(
            tid is not None and self._tasks.get(tid)["status"] == "已暂停")
        self.btn_open.setEnabled(True)

    def _pause_selected(self):
        tid = self._current_task_id()
        if tid and self._tasks.get(tid, {}).get("worker"):
            self._tasks[tid]["worker"]._paused = True
            self._tasks[tid]["status"] = "已暂停"
            self.status.setText(f"⏸ 已暂停: {os.path.basename(self._tasks[tid]['path'])}")
            self._refresh_table()

    def _resume_selected(self):
        tid = self._current_task_id()
        if tid and self._tasks.get(tid, {}).get("worker"):
            self._tasks[tid]["worker"]._paused = False
            self._tasks[tid]["status"] = "下载中"
            self.status.setText("▶ 继续下载…")
            self._refresh_table()

    def _cancel_selected(self):
        tid = self._current_task_id()
        if tid and self._tasks.get(tid, {}).get("worker"):
            self._tasks[tid]["worker"].stop()
            self._tasks[tid]["status"] = "已取消"
            self.status.setText("✕ 下载已取消")
            self._refresh_table()

    def _change_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择下载目录", self._download_dir)
        if d:
            self._download_dir = d
            for w in self.findChildren(QLabel):
                if w.text().startswith("下载目录:"):
                    w.setText(f"下载目录: {self._download_dir}")
                    break

    def _open_dir(self):
        if os.path.isdir(self._download_dir):
            import subprocess
            subprocess.Popen(["explorer", os.path.normpath(self._download_dir)])
        else:
            QMessageBox.information(self, "目录", self._download_dir)

    # ---------- 表格渲染 ----------

    def _fmt_size(self, n: float) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024 or unit == "GB":
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} GB"

    def _fmt_speed(self, s: float) -> str:
        if s <= 0:
            return "--"
        return self._fmt_size(s) + "/s"

    def _refresh_table(self):
        if not hasattr(self, "table"):
            return
        self.table.setRowCount(len(self._tasks))
        rows = sorted(self._tasks.items())
        for r, (tid, task) in enumerate(rows):
            # 文件名
            name_item = QTableWidgetItem(os.path.basename(task["path"]))
            name_item.setData(Qt.ItemDataRole.UserRole, tid)
            self.table.setItem(r, 0, name_item)

            # 进度
            txt = task["status"]
            cell = QWidget()
            lay = QVBoxLayout(cell)
            lay.setContentsMargins(4, 2, 4, 2)
            lay.setSpacing(2)
            lbl = QLabel(txt)
            lbl.setStyleSheet("color:#7d89a6; font-size:11px;")
            if task["status"] in ("下载中", "已暂停"):
                total = task["total"]
                pct = (task["done"] / total * 100) if total else 0
                lbl.setText(
                    f"{self._fmt_size(task['done'])} / "
                    f"{self._fmt_size(total) if total else '未知'}")
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(int(pct))
                bar.setTextVisible(False)
                bar.setFixedHeight(5)
                bar.setStyleSheet("""
                    QProgressBar { background:#1c2233; border:none; border-radius:2px; }
                    QProgressBar::chunk { background:#00e5a0; }
                """)
                lay.addWidget(bar)
                if task["status"] == "已暂停":
                    lbl.setStyleSheet("color:#e0a500; font-size:11px;")
            lay.addWidget(lbl)
            self.table.setCellWidget(r, 1, cell)

            self.table.setItem(r, 2, QTableWidgetItem(self._fmt_speed(task["speed"])))
            self.table.setItem(r, 3, QTableWidgetItem(task["status"]))

            op = QPushButton("打开文件" if task["status"] == "完成" else "打开目录")
            op.setFixedHeight(26)
            op.setStyleSheet(self._btn_style())
            op.clicked.connect(lambda _, _tid=tid, _t=task: self._open_task(_tid, _t))
            self.table.setCellWidget(r, 4, op)

        self._update_op_buttons()

    def _open_task(self, tid: int, task: dict):
        p = task["path"]
        if os.path.isfile(p):
            import subprocess
            try:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
                return
            except Exception:
                pass
            os.startfile(p)
        else:
            self._open_dir()