"""
TianOS 任务管理器
实时监控虚拟内核进程、内存、硬件信息
"""

APP_NAME = "任务管理器"
APP_ICON = "⚡"
APP_ICON_FILE = "imageres 023.png"
APP_COLOR = "#ffcc00"

import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QFrame, QGridLayout, QSplitter, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from system.config import sys_config
from kernel.process import scheduler, ProcessState, Priority


# ==================== 进程颜色映射 ====================

STATE_COLORS = {
    ProcessState.NEW:        "#ffcc00",  # 黄色
    ProcessState.READY:      "#00ccff",  # 蓝色
    ProcessState.RUNNING:    "#00ff66",  # 绿色
    ProcessState.BLOCKED:    "#ff6644",  # 橙色
    ProcessState.WAITING:    "#ff8800",  # 深橙
    ProcessState.TERMINATED: "#ff4444",  # 红色
    ProcessState.SUSPENDED:  "#888888",  # 灰色
}

PRIORITY_LABELS = {
    Priority.IDLE:     "空闲",
    Priority.LOW:      "低",
    Priority.NORMAL:   "普通",
    Priority.HIGH:     "高",
    Priority.REALTIME: "实时",
}


class ProcessTab(QWidget):
    """进程列表标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(2000)  # 每2秒刷新
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # 统计信息栏
        self.stats_bar = QLabel()
        self.stats_bar.setFont(QFont("Consolas", 10))
        self.stats_bar.setStyleSheet("color: #888899; padding: 4px 0;")
        layout.addWidget(self.stats_bar)

        # 进程表格
        self.perf_tab_ref = None  # 由 TaskManager 设置，用于联动刷新

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["PID", "进程名称", "状态", "优先级", "CPU时间", "内存(KB)", "线程数"])
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #16162a;
                alternate-background-color: #1c1c34;
                color: #cccccc;
                border: 1px solid #2a2a4a;
                gridline-color: #2a2a4a;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #1e1e3a;
                color: #00ccff;
                padding: 6px;
                border: none;
                border-bottom: 2px solid #334466;
                font-weight: bold;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
            QTableWidget::item:selected {
                background-color: #005588;
            }
        """)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)

        # 列宽
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 60)
        self.table.setColumnWidth(4, 90)
        self.table.setColumnWidth(5, 100)
        self.table.setColumnWidth(6, 70)

        layout.addWidget(self.table)

    def refresh(self):
        """刷新进程列表"""
        processes = scheduler.list_processes()
        stats = scheduler.get_stats()

        # 更新统计栏
        running = sum(1 for p in processes if p.state == ProcessState.RUNNING)
        ready = sum(1 for p in processes if p.state == ProcessState.READY)
        blocked = sum(1 for p in processes if p.state == ProcessState.BLOCKED)
        self.stats_bar.setText(
            f"▸ 总进程: {len(processes)}  "
            f"<span style='color:#00ff66;'>● 运行: {running}</span>  "
            f"<span style='color:#00ccff;'>● 就绪: {ready}</span>  "
            f"<span style='color:#ff6644;'>● 阻塞: {blocked}</span>  "
            f"| 切换次数: {stats['total_switches']}"
        )

        # 填充表格
        self.table.setRowCount(len(processes))
        for row, proc in enumerate(processes):
            # PID
            pid_item = QTableWidgetItem(str(proc.pid))
            pid_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, pid_item)

            # 名称
            name_item = QTableWidgetItem(proc.name)
            name_item.setFont(QFont("Consolas", 11))
            self.table.setItem(row, 1, name_item)

            # 状态（带颜色）
            state_text = proc.state.value
            state_color = STATE_COLORS.get(proc.state, "#ffffff")
            state_item = QTableWidgetItem(state_text)
            state_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            state_item.setForeground(QColor(state_color))
            state_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            self.table.setItem(row, 2, state_item)

            # 优先级
            pri_text = PRIORITY_LABELS.get(proc.priority, str(proc.priority.value))
            pri_item = QTableWidgetItem(pri_text)
            pri_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, pri_item)

            # CPU时间
            cpu_item = QTableWidgetItem(f"{proc.cpu_time_ms:.1f}ms")
            cpu_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cpu_item.setFont(QFont("Consolas", 10))
            self.table.setItem(row, 4, cpu_item)

            # 内存
            mem_item = QTableWidgetItem(str(proc.memory_used_kb))
            mem_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            mem_item.setFont(QFont("Consolas", 10))
            self.table.setItem(row, 5, mem_item)

            # 线程数
            thread_item = QTableWidgetItem(str(proc.thread_count))
            thread_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 6, thread_item)

        # 更新内存统计到性能选项卡
        if self.perf_tab_ref:
            self.perf_tab_ref.refresh()


class PerformanceTab(QWidget):
    """性能监控标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(2000)
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # ===== CPU 信息 =====
        cpu_group = QFrame()
        cpu_group.setStyleSheet("""
            QFrame {
                background-color: #16162a;
                border: 1px solid #2a2a4a;
                border-radius: 8px;
            }
        """)
        cpu_layout = QVBoxLayout(cpu_group)
        cpu_layout.setContentsMargins(15, 12, 15, 12)

        cpu_title = QLabel("🧠 中央处理器 (CPU)")
        cpu_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        cpu_title.setStyleSheet("color: #00ccff; background: transparent;")
        cpu_layout.addWidget(cpu_title)

        self.cpu_info = QLabel()
        self.cpu_info.setFont(QFont("Consolas", 10))
        self.cpu_info.setStyleSheet("color: #aaaaaa; background: transparent;")
        self.cpu_info.setWordWrap(True)
        cpu_layout.addWidget(self.cpu_info)

        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setValue(0)
        self.cpu_bar.setFixedHeight(18)
        self.cpu_bar.setTextVisible(True)
        self.cpu_bar.setFormat("进程占用: %p%")
        self.cpu_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1a1a34;
                border: 1px solid #2a2a4a;
                border-radius: 4px;
                text-align: center;
                color: #cccccc;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00cc66, stop:1 #00ff88);
                border-radius: 3px;
            }
        """)
        cpu_layout.addWidget(self.cpu_bar)

        layout.addWidget(cpu_group)

        # ===== 内存信息 =====
        mem_group = QFrame()
        mem_group.setStyleSheet("""
            QFrame {
                background-color: #16162a;
                border: 1px solid #2a2a4a;
                border-radius: 8px;
            }
        """)
        mem_layout = QVBoxLayout(mem_group)
        mem_layout.setContentsMargins(15, 12, 15, 12)

        mem_title = QLabel("💾 内存 (Memory)")
        mem_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        mem_title.setStyleSheet("color: #ffcc00; background: transparent;")
        mem_layout.addWidget(mem_title)

        self.mem_info = QLabel()
        self.mem_info.setFont(QFont("Consolas", 10))
        self.mem_info.setStyleSheet("color: #aaaaaa; background: transparent;")
        self.mem_info.setWordWrap(True)
        mem_layout.addWidget(self.mem_info)

        self.mem_bar = QProgressBar()
        self.mem_bar.setRange(0, 100)
        self.mem_bar.setValue(0)
        self.mem_bar.setFixedHeight(18)
        self.mem_bar.setTextVisible(True)
        self.mem_bar.setFormat("已使用: %p%")
        self.mem_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1a1a34;
                border: 1px solid #2a2a4a;
                border-radius: 4px;
                text-align: center;
                color: #cccccc;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff8800, stop:1 #ffcc00);
                border-radius: 3px;
            }
        """)
        mem_layout.addWidget(self.mem_bar)

        # 内存详情网格
        mem_grid = QGridLayout()
        mem_grid.setSpacing(8)
        self.mem_labels = {}
        fields = [
            ("total", "总计", "#888899"),
            ("used", "已用", "#ff8800"),
            ("free", "空闲", "#00cc66"),
            ("kernel", "内核", "#ff6644"),
            ("user", "用户", "#4488ff"),
        ]
        for i, (key, label, color) in enumerate(fields):
            col = i % 3
            row = i // 3
            lbl = QLabel(f"<span style='color:{color};'>{label}:</span> <span style='color:#cccccc;' id='mem_{key}'>0 MB</span>")
            lbl.setFont(QFont("Consolas", 10))
            lbl.setStyleSheet("background: transparent;")
            mem_grid.addWidget(lbl, row, col)
            self.mem_labels[key] = lbl

        mem_layout.addLayout(mem_grid)
        layout.addWidget(mem_group)

        # ===== 系统运行信息 =====
        sys_group = QFrame()
        sys_group.setStyleSheet("""
            QFrame {
                background-color: #16162a;
                border: 1px solid #2a2a4a;
                border-radius: 8px;
            }
        """)
        sys_layout = QVBoxLayout(sys_group)
        sys_layout.setContentsMargins(15, 12, 15, 12)

        sys_title = QLabel("⏱ 系统运行信息")
        sys_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        sys_title.setStyleSheet("color: #66ffcc; background: transparent;")
        sys_layout.addWidget(sys_title)

        self.sys_info = QLabel()
        self.sys_info.setFont(QFont("Consolas", 10))
        self.sys_info.setStyleSheet("color: #aaaaaa; background: transparent;")
        self.sys_info.setWordWrap(True)
        sys_layout.addWidget(self.sys_info)

        layout.addWidget(sys_group)

        # 弹簧
        layout.addStretch()

    def refresh(self):
        """刷新性能数据"""
        from kernel.kernel import kernel
        from kernel.memory import memory_manager

        # CPU 信息（动态读取硬件管理器）
        from system.hardware_manager import hardware_manager
        cpu_config = hardware_manager.get_cpu_info()
        mem_config = hardware_manager.get_ram_info()
        gpu_config = hardware_manager.get_gpu_info()
        gpu_name = gpu_config.get("model") or gpu_config.get("name") or "无"
        self.cpu_info.setText(
            f"型号: {cpu_config.get('name') or cpu_config.get('model', '未知')}  |  "
            f"核心数: {cpu_config.get('cores', '?')}  |  "
            f"线程数: {cpu_config.get('threads', cpu_config.get('cores', '?'))}  |  "
            f"频率: {cpu_config.get('frequency_mhz', '?')} MHz  |  "
            f"GPU: {gpu_name}  |  "
            f"特性: {', '.join((cpu_config.get('features') or [])[:4])}..."
        )

        # 模拟 CPU 占用率 (基于进程数量)
        processes = scheduler.list_processes()
        active = sum(1 for p in processes if p.state in [
            ProcessState.RUNNING, ProcessState.READY])
        total = len(processes)
        cpu_pct = min(int((active / max(total, 1)) * 100), 100)
        self.cpu_bar.setValue(max(cpu_pct, 5))

        # 内存信息
        mem_stats = memory_manager.get_memory_stats()
        total_mb = mem_stats["total_mb"]
        used_mb = mem_stats["used_mb"]
        free_mb = mem_stats["free_mb"]
        kernel_mb = mem_stats["kernel_mb"]
        user_mb = mem_stats["user_mb"]

        self.mem_info.setText(
            f"类型: {mem_config.get('type') or mem_config.get('memory_type', 'DDR5')}  |  "
            f"物理容量: {mem_config.get('total_mb', total_mb):.0f} MB  |  "
            f"已用: {used_mb:.1f} MB  |  "
            f"空闲: {free_mb:.1f} MB  |  "
            f"页帧: {mem_stats['total_frames']} 帧"
        )
        mem_pct = int((used_mb / max(total_mb, 1)) * 100)
        self.mem_bar.setValue(mem_pct)

        # 更新详情
        self.mem_labels["total"].setText(
            f"<span style='color:#888899;'>总计:</span> "
            f"<span style='color:#cccccc;'>{total_mb:.0f} MB</span>")
        self.mem_labels["used"].setText(
            f"<span style='color:#ff8800;'>已用:</span> "
            f"<span style='color:#cccccc;'>{used_mb:.1f} MB</span>")
        self.mem_labels["free"].setText(
            f"<span style='color:#00cc66;'>空闲:</span> "
            f"<span style='color:#cccccc;'>{free_mb:.1f} MB</span>")
        self.mem_labels["kernel"].setText(
            f"<span style='color:#ff6644;'>内核:</span> "
            f"<span style='color:#cccccc;'>{kernel_mb:.1f} MB</span>")
        self.mem_labels["user"].setText(
            f"<span style='color:#4488ff;'>用户:</span> "
            f"<span style='color:#cccccc;'>{user_mb:.1f} MB</span>")

        # 系统信息
        uptime = kernel.uptime_seconds if kernel.is_running else 0
        uptime_str = f"{int(uptime // 3600):02d}:{int((uptime % 3600) // 60):02d}:{int(uptime % 60):02d}"
        self.sys_info.setText(
            f"系统版本: {sys_config.SYSTEM_NAME}  |  "
            f"运行时间: {uptime_str}  |  "
            f"进程数: {total}  |  "
            f"服务数: {len(kernel.services)}"
        )


class HardwareTab(QWidget):
    """硬件信息标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # ===== 系统概览 =====
        overview = QFrame()
        overview.setStyleSheet("""
            QFrame {
                background-color: #16162a;
                border: 1px solid #2a2a4a;
                border-radius: 8px;
            }
        """)
        ov_layout = QVBoxLayout(overview)
        ov_layout.setContentsMargins(15, 12, 15, 12)

        ov_title = QLabel("🔧 系统概览")
        ov_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        ov_title.setStyleSheet("color: #66ffcc; background: transparent;")
        ov_layout.addWidget(ov_title)

        ov_lines = [
            ("操作系统", f"{sys_config.SYSTEM_NAME}"),
            ("内部版本", sys_config.SYSTEM_VERSION),
            ("系统架构", sys_config.SYSTEM_ARCH),
            ("构建日期", sys_config.SYSTEM_BUILD),
            ("内核类型", "微内核 (Microkernel)"),
            ("桌面环境", "TianOS Desktop (PyQt6)"),
            ("网络协议栈", "TCP/IP v4"),
        ]
        for k, v in ov_lines:
            row = QLabel(
                f"<b style='color:#8888ff; font-size:12px;'>{k}:</b>  "
                f"<span style='color:#cccccc; font-size:12px;'>{v}</span>"
            )
            row.setFont(QFont("Consolas", 10))
            row.setStyleSheet("background: transparent;")
            ov_layout.addWidget(row)

        layout.addWidget(overview)

        # ===== 硬件设备表 =====
        hw_frame = QFrame()
        hw_frame.setStyleSheet("""
            QFrame {
                background-color: #16162a;
                border: 1px solid #2a2a4a;
                border-radius: 8px;
            }
        """)
        hw_layout = QVBoxLayout(hw_frame)
        hw_layout.setContentsMargins(15, 12, 15, 12)

        hw_title = QLabel("🖥 硬件设备清单 (模拟)")
        hw_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        hw_title.setStyleSheet("color: #00ccff; background: transparent;")
        hw_layout.addWidget(hw_title)

        from system.hardware_manager import hardware_manager
        hw_config = sys_config.HARDWARE
        cpu = hardware_manager.get_cpu_info()
        mem = hardware_manager.get_ram_info()
        gpu = hardware_manager.get_gpu_info()
        mobo = hardware_manager.get_motherboard_info()

        # 设备清单（CPU/GPU/内存/主板来自硬件管理器，其余保留系统默认）
        gpu_name = gpu.get("model") or gpu.get("name") or "无"
        gpu_desc = f"{gpu_name}  {gpu.get('vram_mb', 0)//1024}GB VRAM" if gpu else "无"
        mem_type = mem.get("type") or mem.get("memory_type", "DDR5")
        mem_total = int(mem.get("total_mb") or hw_config['memory']['total_mb'])
        mem_reserved = int(hw_config['memory'].get("reserved_mb", 512))
        cpu_name = cpu.get("name") or cpu.get("model") or "未知"
        cpu_cores = cpu.get("cores", "?")
        cpu_freq = cpu.get("frequency_mhz", "?")
        cpu_threads = cpu.get("threads", cpu_cores)
        mobo_name = mobo.get("name") or mobo.get("model") or ""
        mobo_types = "/".join(mobo.get("memory_types") or []) or "?"
        hw_items = [
            ("CPU", f"{cpu_name}  {cpu_cores}核{cpu_threads}线程  {cpu_freq}MHz",
             "#00ff66"),
            ("内存", f"{mem_type}  {mem_total//1024}GB (保留{mem_reserved}MB)",
             "#ffcc00"),
            ("显卡", gpu_desc,
             "#66ff99"),
            ("主板", f"{mobo_name}  支持内存: {mobo_types}" if mobo_name else "未配置",
             "#88ccff"),
            ("显示适配器", f"{hw_config['display']['gpu_model']}  {hw_config['display']['width']}x{hw_config['display']['height']}@{hw_config['display']['refresh_rate']}Hz",
             "#4488ff"),
            ("键盘", "PS/2 标准键盘 (US 布局)", "#aaaaaa"),
            ("鼠标", "PS/2 兼容鼠标 (3键)", "#aaaaaa"),
            ("存储设备", f"{hw_config['storage']['disk_label']}  {hw_config['storage']['disk_size_mb']}MB",
             "#ff66cc"),
            ("网卡", f"{hw_config['network']['nic_model']}  MAC: {hw_config['network']['mac_address']}",
             "#00dddd"),
        ]
        for name, desc, color in hw_items:
            item = QLabel(
                f"<span style='color:{color}; font-size:14px;'>●</span>  "
                f"<b style='color:#ffffff; font-size:12px;'>{name}:</b>  "
                f"<span style='color:#aaaaaa; font-size:12px;'>{desc}</span>"
            )
            item.setFont(QFont("Consolas", 10))
            item.setStyleSheet("background: transparent; padding: 3px 0;")
            hw_layout.addWidget(item)

        layout.addWidget(hw_frame)

        # ===== 网络配置 =====
        net_frame = QFrame()
        net_frame.setStyleSheet("""
            QFrame {
                background-color: #16162a;
                border: 1px solid #2a2a4a;
                border-radius: 8px;
            }
        """)
        net_layout = QVBoxLayout(net_frame)
        net_layout.setContentsMargins(15, 12, 15, 12)

        net_title = QLabel("🌐 网络配置")
        net_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        net_title.setStyleSheet("color: #00dddd; background: transparent;")
        net_layout.addWidget(net_title)

        net_config = sys_config.NETWORK
        net_items = [
            ("IP 地址", net_config["host_ip"]),
            ("子网掩码", net_config["netmask"]),
            ("默认网关", net_config["gateway"]),
            ("DNS 主", net_config["dns_primary"]),
            ("DNS 次", net_config["dns_secondary"]),
            ("MTU", str(net_config["mtu"])),
        ]
        for k, v in net_items:
            row = QLabel(
                f"<b style='color:#88dddd; font-size:12px;'>{k}:</b>  "
                f"<span style='color:#cccccc; font-size:12px;'>{v}</span>"
            )
            row.setFont(QFont("Consolas", 10))
            row.setStyleSheet("background: transparent;")
            net_layout.addWidget(row)

        layout.addWidget(net_frame)
        layout.addStretch()


class TaskManager(QWidget):
    """任务管理器主窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TianOS 任务管理器")
        self.setMinimumSize(720, 520)
        self.resize(750, 560)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("""
            background-color: #12122a;
            border-bottom: 2px solid #ffcc00;
        """)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 15, 0)

        icon = QLabel("⚡")
        icon.setFont(QFont("Consolas", 18))
        title_layout.addWidget(icon)

        title = QLabel("TianOS 任务管理器")
        title.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffcc00; background: transparent;")
        title_layout.addWidget(title)

        title_layout.addStretch()

        self.status_label = QLabel("实时监控")
        self.status_label.setFont(QFont("Consolas", 9))
        self.status_label.setStyleSheet("color: #00cc66; background: transparent;")
        title_layout.addWidget(self.status_label)

        layout.addWidget(title_bar)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                background-color: #13132a;
                border: none;
                border-top: 1px solid #2a2a4a;
            }
            QTabBar::tab {
                background-color: #1a1a34;
                color: #888899;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #13132a;
                color: #ffcc00;
                border-bottom: 2px solid #ffcc00;
            }
            QTabBar::tab:hover:!selected {
                background-color: #222244;
                color: #cccccc;
            }
        """)

        # 进程标签页
        self.proc_tab = ProcessTab()
        self.tabs.addTab(self.proc_tab, "📋 进程")

        # 性能标签页
        self.perf_tab = PerformanceTab()
        self.tabs.addTab(self.perf_tab, "📊 性能")

        # 硬件标签页
        self.hw_tab = HardwareTab()
        self.tabs.addTab(self.hw_tab, "🖥 硬件")

        # 关联进程标签到性能标签（刷新联动）
        self.proc_tab.perf_tab_ref = self.perf_tab

        layout.addWidget(self.tabs, 1)

    def closeEvent(self, event):
        """关闭时停止定时器"""
        # 停止所有定时器
        if hasattr(self, 'proc_tab') and hasattr(self.proc_tab, '_refresh_timer'):
            self.proc_tab._refresh_timer.stop()
        if hasattr(self, 'perf_tab') and hasattr(self.perf_tab, '_refresh_timer'):
            self.perf_tab._refresh_timer.stop()
        super().closeEvent(event)