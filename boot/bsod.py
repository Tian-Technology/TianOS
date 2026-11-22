"""
TianOS BlueScreen - 蓝屏错误界面与自动修复
==========================================
当系统发生致命错误时，显示 Windows 风格的蓝屏界面，
展示问题原因（停止代码），并自动尝试修复。

功能:
1. 错误诊断 - 分析异常，映射到停止代码
2. 蓝屏展示 - 全屏蓝底界面，显示错误信息
3. 自动修复 - 识别可修复项并按顺序尝试修复
4. 崩溃报告 - 将诊断与修复结果写入日志文件

支持两种场景:
- GUI 模式: 使用 PyQt6 绘制全屏蓝屏界面
- 文本模式: 使用控制台输出蓝屏信息
"""

import os
import sys
import json
import time
import traceback
from typing import Dict, Optional, List, Tuple, Any

from system.config import sys_config, SETTINGS_FILE

# ==================== 停止代码定义 ====================

# 停止代码 (STOP CODE)：根据错误阶段/关键字映射到标准停止代码
STOP_CODES: List[Tuple[str, str, str]] = [
    # (关键字, 停止代码, 原因说明)
    ("POST", "INACCESSIBLE_BOOT_DEVICE",
     "BIOS 自检失败，无法访问引导设备。可能是硬件配置异常。"),
    ("boot", "BOOT_LOADER_FAILURE",
     "引导加载程序异常，无法加载内核映像。"),
    ("内核启动", "KERNEL_INIT_FAILURE",
     "内核初始化失败，系统核心组件无法正常加载。"),
    ("network", "CRITICAL_NETWORK_FAILURE",
     "网络协议栈初始化失败，网络子系统异常。"),
    ("服务启动", "SYSTEM_SERVICE_EXCEPTION",
     "系统服务未能在预期时间内完成初始化。"),
    ("GUI", "GUI_INITIALIZATION_FAILURE",
     "图形界面初始化失败，桌面环境无法启动。"),
    ("内存", "MEMORY_MANAGEMENT",
     "内存管理异常，可能是内存布局配置损坏。"),
    ("硬件资源", "HARDWARE_LIMIT_EXCEEDED",
     "应用请求的硬件资源超过当前物理硬件上限，无法继续启动。"),
]

DEFAULT_STOP_CODE = "SYSTEM_THREAD_EXCEPTION_NOT_HANDLED"
DEFAULT_CAUSE = "发生未知系统错误，系统已经收集到错误信息并尝试自动修复。"


class DiagnosticResult:
    """诊断结果：包含停止代码与问题原因解析"""

    def __init__(self, stop_code: str, cause: str, error: Exception,
                 phase: str = "", traceback_text: str = ""):
        self.stop_code = stop_code
        self.cause = cause
        self.error = error
        self.phase = phase
        self.traceback_text = traceback_text
        self.error_message = str(error) if error else ""

    def to_dict(self) -> Dict:
        return {
            "stop_code": self.stop_code,
            "cause": self.cause,
            "phase": self.phase,
            "error_message": self.error_message,
            "traceback": self.traceback_text,
        }

    def __repr__(self):
        return f"<BSOD {self.stop_code}: {self.error_message}>"


# ==================== 自动修复策略 ====================

def _get_settings_path() -> str:
    """返回 settings.json 的绝对路径（与 config.py 保持一致）"""
    return SETTINGS_FILE

def _crash_report_path() -> str:
    """返回崩溃报告目录"""
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data", "crash_reports"))


def _repair_reset_settings() -> bool:
    """修复项1: 重置损坏的系统配置文件 settings.json"""
    settings_file = _get_settings_path()
    if not os.path.exists(settings_file):
        return True  # 无配置文件，视为已修复
    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            json.load(f)
        return True  # 配置文件可正常解析
    except Exception:
        # 备份损坏文件，然后重置
        try:
            os.makedirs(os.path.dirname(settings_file), exist_ok=True)
            backup = settings_file + ".corrupt"
            if os.path.exists(backup):
                os.remove(backup)
            os.rename(settings_file, backup)
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump({}, f)
            return True
        except Exception:
            return False


def _repair_safe_mode() -> bool:
    """修复项2: 启用安全模式启动（下次以安全配置启动）"""
    try:
        settings_file = _get_settings_path()
        os.makedirs(os.path.dirname(settings_file), exist_ok=True)
        data = {}
        if os.path.exists(settings_file):
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f) if f.read().strip() else {}
        data.setdefault("BOOT", {})["safe_mode"] = True
        data["BOOT"]["last_crash_recovery"] = True
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _repair_clear_cache() -> bool:
    """修复项3: 清理临时的字节码缓存 (__pycache__)"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    removed = 0
    for dirpath, dirnames, filenames in os.walk(base):
        cache_dir = os.path.join(dirpath, "__pycache__")
        if os.path.isdir(cache_dir):
            try:
                for name in os.listdir(cache_dir):
                    try:
                        os.remove(os.path.join(cache_dir, name))
                        removed += 1
                    except Exception:
                        pass
            except Exception:
                pass
    return True


def _repair_restore_defaults() -> bool:
    """修复项4: 恢复系统默认配置"""
    try:
        cfg = sys_config
        # 重新加载配置文件，清空持久化错误状态
        settings_file = _get_settings_path()
        if os.path.exists(settings_file):
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("BOOT", {}).pop("last_crash_recovery", None)
            data.setdefault("BOOT", {})["safe_mode"] = False
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# 修复项列表: (名称, 匹配预测, 执行函数, 是否关键)
REPAIR_ITEMS: List[Tuple[str, str, Any, bool]] = [
    ("重置系统配置文件", "config", _repair_reset_settings, False),
    ("启用安全启动模式", "boot", _repair_safe_mode, True),
    ("清理临时系统缓存", "cache", _repair_clear_cache, False),
    ("恢复系统默认配置", "default", _repair_restore_defaults, True),
]


def diagnose_error(error: Exception, phase: str = "",
                   include_traceback: bool = True) -> DiagnosticResult:
    """诊断异常，生成停止代码与原因说明"""
    combined = f"{phase} {str(error)}".lower()
    stop_code = DEFAULT_STOP_CODE
    cause = DEFAULT_CAUSE

    # 硬件过载异常：专用停止代码 + 展示具体原因
    try:
        from system.sandbox import HardwareOverloadError
        if isinstance(error, HardwareOverloadError):
            stop_code = "HARDWARE_LIMIT_EXCEEDED"
            cause = (
                f"系统在「{phase or '应用启动'}」时检测到硬件资源超限。\n\n"
                f"停止原因: {error}\n\n"
                "提示：请调整应用资源需求，或通过硬件配置器更换更高配置的硬件后重新启动系统。"
            )
            return DiagnosticResult(
                stop_code=stop_code,
                cause=cause,
                error=error,
                phase=phase,
                traceback_text=traceback_to_text(error) if include_traceback else "",
            )
    except ImportError:
        pass

    for keyword, code, desc in STOP_CODES:
        if keyword.lower() in combined:
            stop_code = code
            cause = desc
            break

    # 若错误信息本身很具体，补充到原因说明
    if str(error) and DEFAULT_CAUSE in cause:
        cause = f"系统在「{phase or '运行过程'}」中发生致命错误。\n" \
                f"错误信息: {error}\n\n{traceback_to_text(error) if include_traceback else ''}"

    return DiagnosticResult(
        stop_code=stop_code,
        cause=cause,
        error=error,
        phase=phase,
        traceback_text=traceback_to_text(error) if include_traceback else "",
    )


def traceback_to_text(error: Exception) -> str:
    """提取异常的堆栈文本"""
    return "".join(traceback.format_exception(type(error), error, error.__traceback__))


def save_crash_report(diag: DiagnosticResult) -> str:
    """将崩溃报告写入 data/crash_reports/TianOS_crash_<时间>.json"""
    try:
        report_dir = _crash_report_path()
        os.makedirs(report_dir, exist_ok=True)
        filename = os.path.join(
            report_dir,
            f"TianOS_crash_{time.strftime('%Y%m%d_%H%M%S')}.json",
        )
        payload = {
            "system": {
                "name": sys_config.SYSTEM_NAME,
                "version": sys_config.SYSTEM_VERSION,
                "build": sys_config.SYSTEM_BUILD,
            },
            "diagnosis": diag.to_dict(),
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return filename
    except Exception:
        return ""


def auto_repair(diag: DiagnosticResult, progress_callback: Optional[Callable] = None) -> Tuple[bool, List[Dict]]:
    """按顺序尝试自动修复

    返回:
        (是否完全修复, 每项修复的结果列表)
    """
    results: List[Dict] = []
    total = len(REPAIR_ITEMS)
    all_ok = True

    for idx, (name, fn_key, fn, critical) in enumerate(REPAIR_ITEMS):
        if progress_callback:
            progress_callback(idx, total, f"正在执行：{name}...")
        try:
            ok = bool(fn())
        except Exception:
            ok = False
        results.append({
            "name": name,
            "success": ok,
            "critical": critical,
        })
        if not ok:
            all_ok = False
        time.sleep(0.3)

    if progress_callback:
        progress_callback(total, total, "自动修复完成")
    return all_ok, results


def _text_bsod(diag: DiagnosticResult) -> None:
    """文本模式的蓝屏输出（控制台）"""
    line = "=" * 62
    print(f"\n{line}")
    print("  TianOS 蓝屏错误  :(")
    print("  发生错误，系统必须重新启动")
    print(line)
    print(f"  停止代码: {diag.stop_code}")
    print(f"  阶段    : {diag.phase or '运行'}")
    print(f"  原因    : {diag.cause}")
    print(f"  错误    : {diag.error}")
    print(line)
    if diag.traceback_text:
        print("  -------- 错误堆栈 --------")
        print(diag.traceback_text)
        print(line)

    print("\n[*] 正在自动修复系统...")
    success, results = auto_repair(
        diag,
        lambda cur, total, txt: print(f"    [{cur}/{total}] {txt}")
    )
    print("\n[结果]")
    for r in results:
        stat = "✔" if r["success"] else "✘"
        print(f"    {stat} {r['name']}")
    if success:
        print("\n[✓] 系统已自动修复，正在重新启动...")
    else:
        print("\n[✘] 无法自动修复，请手动处理系统错误。")
    time.sleep(1.0)


# ==================== GUI 蓝屏界面 ====================

class BlueScreenWidget:
    """GUI 蓝屏界面 (PyQt6 惰性实现，避免文本模式依赖)"""

    def __init__(self, diag: DiagnosticResult):
        from PyQt6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QApplication,
                                     QProgressBar, QPushButton)
        from PyQt6.QtCore import Qt, QTimer
        from PyQt6.QtGui import QFont, QColor, QPalette

        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)

        self.w = QWidget()
        self.w.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint)
        self.w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.w.setStyleSheet("background-color: #0a5c9e; color: #ffffff;")
        self.w.setWindowTitle("TianOS System Error")

        # 全屏
        screen = self.w.screen() or self.app.primaryScreen()
        self.w.setGeometry(screen.availableGeometry())

        layout = QVBoxLayout(self.w)
        layout.setContentsMargins(80, 60, 80, 60)
        layout.setSpacing(20)

        # 难过表情
        face = QLabel(":(")
        face.setFont(QFont("Segoe UI", 72, QFont.Weight.Bold))
        face.setStyleSheet("color: #ffffff;")
        layout.addWidget(face)

        title = QLabel("你的 TianOS 系统遇到一个问题，需要重新启动")
        title.setFont(QFont("Microsoft YaHei UI", 22, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel("我们只收集某些错误信息，然后为你重新启动。")
        desc.setFont(QFont("Microsoft YaHei UI", 12))
        desc.setStyleSheet("color: rgba(255,255,255,220);")
        layout.addWidget(desc)

        # 停止代码
        self.stop_label = QLabel(f"停止代码: {diag.stop_code}")
        self.stop_label.setFont(QFont("Consolas", 12))
        self.stop_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(self.stop_label)

        # 问题原因
        self.cause_label = QLabel(diag.cause)
        self.cause_label.setWordWrap(True)
        self.cause_label.setFont(QFont("Consolas", 11))
        self.cause_label.setStyleSheet("color: rgba(255,255,255,200);")
        layout.addWidget(self.cause_label)

        layout.addStretch()

        # 自动修复提示 + 进度
        self.repair_label = QLabel("正在自动修复系统错误...")
        self.repair_label.setFont(QFont("Microsoft YaHei UI", 12))
        layout.addWidget(self.repair_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255,255,255,40);
                border: none; border-radius: 4px;
                height: 14px; color: #ffffff;
                text-align: center; font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #ffffff; border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress)

        layout.addStretch()

        # 重新启动按钮
        self.reboot_btn = QPushButton("重新启动系统")
        self.reboot_btn.setFixedSize(220, 44)
        self.reboot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reboot_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,30);
                color: #ffffff; border: 1px solid rgba(255,255,255,80);
                border-radius: 6px; font-size: 14px;
            }
            QPushButton:hover { background-color: rgba(255,255,255,60); }
        """)
        self.reboot_btn.clicked.connect(self._on_reboot)
        layout.addWidget(self.reboot_btn)

        self._repair_pending = True
        self._repair_results: List[Dict] = []
        self._auto_repair_diag = diag

    def show(self):
        self.w.show()
        self.w.raise_()
        self.w.activateWindow()

    def start_repair(self):
        """在后台线程执行自动修复"""
        import threading

        def run():
            def progress(cur, total, txt):
                value = int(cur * 100 / total)
                self._set_progress(value, txt)

            success, results = auto_repair(self._auto_repair_diag, progress)
            self._repair_results = results
            self._repair_pending = False
            if success:
                self._set_progress(100, "修复成功，等待重新启动...")
                # 修复成功，3 秒后自动重启
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(3000, self._trigger_reboot)
            else:
                self._set_progress(100, "修复失败，请手动处理")

        threading.Thread(target=run, daemon=True).start()

    def _set_progress(self, value: int, text: str):
        try:
            self.progress.setValue(value)
            self.repair_label.setText(text)
        except Exception:
            pass

    def _on_reboot(self):
        self._trigger_reboot()

    def _trigger_reboot(self):
        self.w.close()
        restart_tianos()

    def close(self):
        self.w.close()


def restart_tianos():
    """重新启动 TianOS 系统（启动新的 Python 进程执行 main.py）。

    通过 subprocess.Popen 先启动新进程，再退出当前进程，
    避免 os.execv 在 Windows 下不可靠、子进程无法接管的问题。
    """
    import subprocess

    print("\n[重启] 正在重新启动 TianOS...")
    main_module = os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py"))
    # 保留原始命令行参数，使重启后与当前会话使用相同启动选项
    cmd = [sys.executable, main_module] + list(sys.argv[1:])
    try:
        # Windows 下为子进程创建独立控制台窗口，避免随父进程一同关闭
        flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        proc = subprocess.Popen(
            cmd,
            cwd=os.path.dirname(main_module),
            creationflags=flags,
        )
        print(f"[重启] 新进程已启动 PID={proc.pid}")
    except Exception as e:
        print(f"[重启] 重新启动失败: {e}")
        sys.exit(1)

    # 退出当前进程，让位于新的 TianOS 进程
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.quit()
    except Exception:
        pass
    os._exit(0)


def handle_crash(error: Exception, phase: str = "", text_mode: bool = False,
                 show_ui: bool = True, exec_loop: bool = False) -> DiagnosticResult:
    """
    统一切口：诊断错误 → 保存报告 → 显示蓝屏 → 自动修复

    Args:
        error: 异常对象
        phase: 出错阶段描述
        text_mode: 是否为文本模式
        show_ui: 是否显示蓝屏界面
        exec_loop: 是否启动事件循环并阻塞等待（仅当主事件循环尚未运行时使用）

    Returns:
        DiagnosticResult 诊断结果
    """
    diag = diagnose_error(error, phase)

    # 写入崩溃报告
    report = save_crash_report(diag)
    if report:
        print(f"[BSOD] 崩溃报告已保存: {report}")

    if not show_ui:
        return diag

    if text_mode:
        _text_bsod(diag)
    else:
        widget = BlueScreenWidget(diag)
        widget.show()
        widget.start_repair()
        try:
            if exec_loop:
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                if app is None:
                    app = QApplication(sys.argv)
                # 覆盖旧的例外处理，避免蓝屏界面自身报错时再触发蓝屏
                app.exec()
        except Exception:
            _text_bsod(diag)

    return diag