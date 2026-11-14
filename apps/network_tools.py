"""
TianOS 网络工具应用
提供网络诊断和监控功能
"""

# 应用元数据 - 用于桌面图标自动发现
APP_NAME = "网络工具"
APP_ICON = "🌐"
APP_ICON_FILE = "imageres 021.png"
APP_COLOR = "#00ccff"

import time
import random
from typing import Dict, List, Optional, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QGridLayout, QFrame, QTabWidget,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush


class NetworkMonitor(QWidget):
    """网络监控工具"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TianOS 网络工具")
        self.setMinimumSize(700, 500)
        
        self._setup_ui()
        self._start_monitoring()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题
        title = QLabel("🌐 TianOS 网络协议栈")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ccff;")
        layout.addWidget(title)
        
        # 标签页
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                background-color: #1a1a2e;
                border: 1px solid #334466;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #151530;
                color: #888899;
                padding: 8px 20px;
                border: 1px solid #334466;
                border-bottom: none;
                border-radius: 4px 4px 0 0;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #1a1a2e;
                color: #00ccff;
            }
        """)
        
        # 状态页面
        status_page = self._create_status_page()
        tabs.addTab(status_page, "状态")
        
        # Ping页面
        ping_page = self._create_ping_page()
        tabs.addTab(ping_page, "Ping")
        
        # 连接页面
        conn_page = self._create_connections_page()
        tabs.addTab(conn_page, "连接")
        
        # 统计页面
        stats_page = self._create_statistics_page()
        tabs.addTab(stats_page, "统计")
        
        layout.addWidget(tabs, 1)

    def _create_status_page(self) -> QWidget:
        """创建状态页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        
        # 接口信息
        info_group = QGroupBox("网络接口")
        info_group.setStyleSheet("""
            QGroupBox {
                color: #00ccff;
                font-weight: bold;
                border: 1px solid #334466;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                padding: 0 10px;
            }
        """)
        info_layout = QGridLayout(info_group)
        
        info_data = [
            ("接口名称:", "eth0"),
            ("MAC 地址:", "00:1A:2B:3C:4D:5E"),
            ("IP 地址:", "10.0.2.15"),
            ("子网掩码:", "255.255.255.0"),
            ("默认网关:", "10.0.2.2"),
            ("MTU:", "1500"),
            ("状态:", "UP"),
        ]
        
        for i, (key, value) in enumerate(info_data):
            key_label = QLabel(key)
            key_label.setStyleSheet("color: #888899; font-weight: bold;")
            val_label = QLabel(value)
            val_label.setStyleSheet("color: #cccccc;")
            info_layout.addWidget(key_label, i, 0)
            info_layout.addWidget(val_label, i, 1)
        
        layout.addWidget(info_group)
        
        # 网络活动
        activity_group = QGroupBox("网络活动")
        activity_group.setStyleSheet(info_group.styleSheet())
        activity_layout = QVBoxLayout(activity_group)
        
        self.activity_text = QTextEdit()
        self.activity_text.setReadOnly(True)
        self.activity_text.setFont(QFont("Consolas", 10))
        self.activity_text.setStyleSheet("""
            QTextEdit {
                background-color: #0d0d1a;
                color: #00ff66;
                border: none;
            }
        """)
        self.activity_text.append("[NET] 网络协议栈初始化完成")
        self.activity_text.append("[NET] DHCP 租约获取成功: 10.0.2.15")
        self.activity_text.append("[NET] DNS 服务就绪")
        self.activity_text.append("[NET] TCP/IP 协议栈监听中...")
        activity_layout.addWidget(self.activity_text)
        
        layout.addWidget(activity_group)
        
        return page

    def _create_ping_page(self) -> QWidget:
        """创建Ping页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Ping说明
        info = QLabel('在终端中使用 "ping <IP地址>" 命令进行网络连通性测试')
        info.setStyleSheet("color: #888899; padding: 10px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # 模拟Ping结果
        result_group = QGroupBox("Ping 测试结果")
        result_group.setStyleSheet("""
            QGroupBox {
                color: #00ccff;
                font-weight: bold;
                border: 1px solid #334466;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                padding: 0 10px;
            }
        """)
        result_layout = QVBoxLayout(result_group)
        
        self.ping_result = QLabel()
        self.ping_result.setFont(QFont("Consolas", 10))
        self.ping_result.setStyleSheet("color: #00ff66; padding: 10px;")
        self.ping_result.setText(
            "--- 网关 10.0.2.2 ping 统计 ---\n"
            "4 packets transmitted, 4 received, 0% packet loss\n"
            "rtt min/avg/max/mdev = 0.023/0.035/0.048/0.009 ms"
        )
        result_layout.addWidget(self.ping_result)
        
        layout.addWidget(result_group, 1)
        
        return page

    def _create_connections_page(self) -> QWidget:
        """创建连接页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # 连接表格
        self.conn_table = QTableWidget()
        self.conn_table.setColumnCount(5)
        self.conn_table.setHorizontalHeaderLabels(["协议", "本地地址", "远程地址", "状态", "发送/接收"])
        self.conn_table.setStyleSheet("""
            QTableWidget {
                background-color: #0d0d1a;
                color: #cccccc;
                border: 1px solid #334466;
                gridline-color: #1a1a3a;
            }
            QHeaderView::section {
                background-color: #151530;
                color: #00ccff;
                padding: 5px;
                border: 1px solid #334466;
            }
        """)
        self.conn_table.horizontalHeader().setStretchLastSection(True)
        
        # 模拟连接数据
        connections = [
            ("TCP", "10.0.2.15:80", "0.0.0.0:0", "LISTEN", "0/0"),
            ("TCP", "10.0.2.15:443", "0.0.0.0:0", "LISTEN", "0/0"),
            ("UDP", "10.0.2.15:68", "0.0.0.0:0", "BOUND", "0/0"),
            ("TCP", "10.0.2.15:49152", "93.184.216.34:80", "ESTABLISHED", "1.2KB/3.4KB"),
        ]
        
        self.conn_table.setRowCount(len(connections))
        for i, (proto, local, remote, state, traffic) in enumerate(connections):
            self.conn_table.setItem(i, 0, QTableWidgetItem(proto))
            self.conn_table.setItem(i, 1, QTableWidgetItem(local))
            self.conn_table.setItem(i, 2, QTableWidgetItem(remote))
            self.conn_table.setItem(i, 3, QTableWidgetItem(state))
            self.conn_table.setItem(i, 4, QTableWidgetItem(traffic))
        
        layout.addWidget(self.conn_table, 1)
        
        return page

    def _create_statistics_page(self) -> QWidget:
        """创建统计页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        
        # 流量统计
        stats_group = QGroupBox("流量统计")
        stats_group.setStyleSheet("""
            QGroupBox {
                color: #00ccff;
                font-weight: bold;
                border: 1px solid #334466;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                padding: 0 10px;
            }
        """)
        stats_layout = QGridLayout(stats_group)
        
        stats_data = [
            ("接收数据包:", "1,284"),
            ("发送数据包:", "2,567"),
            ("接收字节:", "1,024,000 (1.0 MB)"),
            ("发送字节:", "2,048,000 (2.0 MB)"),
            ("接收错误:", "0"),
            ("发送错误:", "0"),
            ("ARP缓存:", "3 条目"),
            ("TCP连接:", "4 活跃"),
        ]
        
        for i, (key, value) in enumerate(stats_data):
            row = i // 2
            col = (i % 2) * 2
            key_label = QLabel(key)
            key_label.setStyleSheet("color: #888899;")
            val_label = QLabel(value)
            val_label.setStyleSheet("color: #00ff66; font-weight: bold;")
            stats_layout.addWidget(key_label, row, col)
            stats_layout.addWidget(val_label, row, col + 1)
        
        layout.addWidget(stats_group)
        
        # 协议栈信息
        stack_group = QGroupBox("协议栈信息")
        stack_group.setStyleSheet(stats_group.styleSheet())
        stack_layout = QVBoxLayout(stack_group)
        
        stack_info = QLabel(
            "TCP/IP 协议栈: TianOS NetStack v1.0\n"
            "支持的协议: TCP, UDP, ICMP, ARP, DHCP, DNS\n"
            "虚拟网卡模式: 模拟 (Simulated)\n"
            "最大连接数: 1024\n"
            "缓冲区大小: 64KB"
        )
        stack_info.setStyleSheet("color: #cccccc; padding: 10px;")
        stack_info.setFont(QFont("Consolas", 10))
        stack_layout.addWidget(stack_info)
        
        layout.addWidget(stack_group)
        layout.addStretch()
        
        return page

    def _start_monitoring(self):
        """开始监控"""
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._update_monitor)
        self.monitor_timer.start(2000)

    def _update_monitor(self):
        """更新监控数据"""
        # 模拟网络活动更新
        rx = random.randint(100, 1000)
        tx = random.randint(100, 1000)
        timestamp = time.strftime("%H:%M:%S")
        
        self.activity_text.append(f"[{timestamp}] RX: {rx} bytes | TX: {tx} bytes")
        # 保持最多100行
        if self.activity_text.document().blockCount() > 100:
            cursor = self.activity_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveOperation.KeepAnchor)
            cursor.removeSelectedText()