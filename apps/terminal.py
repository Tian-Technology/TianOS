"""
TianOS 终端应用
内置命令行终端，支持基本Linux命令
"""

# 应用元数据 - 用于桌面图标自动发现
APP_NAME = "终端"
APP_ICON = ">_"
APP_ICON_FILE = "imageres 264.png"
APP_COLOR = "#00ff66"

import os
import sys
import time
from typing import Dict, List, Optional, Tuple

from system.config import sys_config
from gui.run_dialog import resolve_run_command

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QLineEdit, QLabel, QHBoxLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat, QPainter


class Terminal(QWidget):
    """终端模拟器"""

    command_executed = pyqtSignal(str, str)  # command, output
    launch_requested = pyqtSignal(str)  # 请求启动应用 (应用显示名)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TianOS 终端")
        self.setMinimumSize(600, 400)
        
        # 终端状态
        self.current_directory = "/home/user"
        self.hostname = "tianos"
        self.username = "user"
        self.command_history: List[str] = []
        self.history_index = 0
        self.current_command = ""
        
        # 内置命令表
        self.commands: Dict[str, callable] = {
            "help": self.cmd_help,
            "ls": self.cmd_ls,
            "cd": self.cmd_cd,
            "pwd": self.cmd_pwd,
            "cat": self.cmd_cat,
            "echo": self.cmd_echo,
            "clear": self.cmd_clear,
            "date": self.cmd_date,
            "whoami": self.cmd_whoami,
            "uname": self.cmd_uname,
            "ping": self.cmd_ping,
            "ifconfig": self.cmd_ifconfig,
            "ps": self.cmd_ps,
            "neofetch": self.cmd_neofetch,
            "shutdown": self.cmd_shutdown,
            "reboot": self.cmd_reboot,
            "run": self.cmd_run,
            "mkdir": self.cmd_mkdir,
            "touch": self.cmd_touch,
            "rm": self.cmd_rm,
            "df": self.cmd_df,
            "tree": self.cmd_tree,
            "panic": self.cmd_panic,
        }
        
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 终端输出
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 11))
        self.output.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a2e;
                color: #00ff66;
                border: none;
                padding: 10px;
                selection-background-color: #334466;
            }
        """)
        layout.addWidget(self.output, 1)
        
        # 输入行
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(10, 2, 10, 2)
        input_layout.setSpacing(5)
        
        self.prompt_label = QLabel()
        self.prompt_label.setFont(QFont("Consolas", 11))
        self.prompt_label.setStyleSheet("color: #00ff66; background: transparent;")
        input_layout.addWidget(self.prompt_label)
        
        self.input = QLineEdit()
        self.input.setFont(QFont("Consolas", 11))
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: #ffffff;
                border: none;
                padding: 5px 0px;
            }
            QLineEdit:focus {
                border: none;
            }
        """)
        self.input.returnPressed.connect(self.execute_command)
        input_layout.addWidget(self.input, 1)
        
        layout.addLayout(input_layout)
        
        # 显示欢迎信息
        self._show_welcome()

    def _show_welcome(self):
        """显示欢迎信息"""
        welcome = f"""
╔══════════════════════════════════════════╗
║         TianOS Terminal                  ║
║   {sys_config.SYSTEM_VERSION:<30}║
║       微内核操作系统命令行环境              ║
╚══════════════════════════════════════════╝

输入 'help' 查看可用命令。
输入 'neofetch' 查看系统信息。

        """
        self._append_output(welcome.strip(), "#00ff66")
        self._update_prompt()

    def _update_prompt(self):
        """更新提示符"""
        self.prompt_label.setText(
            f"\u001b[32m{self.username}@{self.hostname}\u001b[0m:\u001b[34m{self.current_directory}\u001b[0m$ "
        )
        self.prompt_label.setText(
            f'<span style="color:#00ff66;">{self.username}@{self.hostname}</span>:'
            f'<span style="color:#0088ff;">{self.current_directory}</span>$'
        )

    def _append_output(self, text: str, color: str = "#cccccc"):
        """添加输出文本"""
        self.output.append(f'<span style="color: {color};">{text}</span>')
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.output.setTextCursor(cursor)

    def execute_command(self):
        """执行命令"""
        command = self.input.text().strip()
        self.input.clear()
        
        if not command:
            self._update_prompt()
            return
        
        # 添加到历史
        self.command_history.append(command)
        self.history_index = len(self.command_history)
        
        # 显示命令
        self._append_output(
            f"\u001b[32m{self.username}@{self.hostname}\u001b[0m:\u001b[34m{self.current_directory}\u001b[0m$ {command}",
            "#888888"
        )
        
        # 解析命令
        parts = command.split()
        cmd = parts[0]
        args = parts[1:]
        
        if cmd in self.commands:
            try:
                output = self.commands[cmd](args)
                if output:
                    self._append_output(output, "#cccccc")
            except Exception as e:
                self._append_output(f"错误: {e}", "#ff4444")
        elif self._try_launch(cmd):
            pass  # 已启动应用
        else:
            self._append_output(f"命令未找到: {cmd} (输入 'help' 查看可用命令)", "#ff6644")
        
        self._update_prompt()

    # ===== 内置命令 =====

    def cmd_run(self, args: List[str]) -> str:
        """启动应用(如 run regedit / run explorer)"""
        if not args:
            from gui.run_dialog import _build_index
            names = sorted({v for k, v in _build_index().items() if k in (
                "regedit", "taskmgr", "explorer", "gpedit", "settings",
                "terminal", "系统信息", "网络工具", "关于")})
            return "用法: run <程序名>\n可运行: " + ", ".join(names)
        app = resolve_run_command(args[0])
        if app:
            self.launch_requested.emit(app)
            return f"正在启动: {app}"
        return f"未找到可运行的程序: {args[0]} (输入 'run' 查看可用列表)"

    def _try_launch(self, cmd: str) -> bool:
        """尝试把命令当作运行别名启动应用"""
        app = resolve_run_command(cmd)
        if app:
            self._append_output(f"正在启动: {app}", "#00ccff")
            self.launch_requested.emit(app)
            return True
        return False

    def cmd_help(self, args: List[str]) -> str:
        """显示帮助信息"""
        help_text = "可用命令:\n"
        for cmd in sorted(self.commands.keys()):
            help_text += f"  {cmd:12} - {self.commands[cmd].__doc__ or ''}\n"
        return help_text

    def cmd_ls(self, args: List[str]) -> str:
        """列出目录内容"""
        return "Desktop  Documents  Downloads  README.md"

    def cmd_cd(self, args: List[str]) -> str:
        """切换目录"""
        if args:
            self.current_directory = os.path.normpath(
                os.path.join(self.current_directory, args[0])
            )
        return ""

    def cmd_pwd(self, args: List[str]) -> str:
        """显示当前目录"""
        return self.current_directory

    def cmd_cat(self, args: List[str]) -> str:
        """显示文件内容"""
        if args:
            return f"[文件: {args[0]}] (虚拟文件系统)"
        return "用法: cat <文件名>"

    def cmd_echo(self, args: List[str]) -> str:
        """回显文本"""
        return " ".join(args)

    def cmd_clear(self, args: List[str]) -> str:
        """清屏"""
        self.output.clear()
        return ""

    def cmd_date(self, args: List[str]) -> str:
        """显示日期"""
        return time.strftime("%a %b %d %H:%M:%S %Y")

    def cmd_whoami(self, args: List[str]) -> str:
        """显示当前用户"""
        return self.username

    def cmd_uname(self, args: List[str]) -> str:
        """显示系统信息"""
        return f"TianOS {sys_config.SYSTEM_VERSION} x86_64 GNU/TianOS"

    def cmd_ping(self, args: List[str]) -> str:
        """Ping 测试"""
        if args:
            target = args[0]
            result = f"PING {target} (模拟) 56(84) bytes of data.\n"
            for i in range(4):
                delay = 10 + hash(str(i)) % 40
                result += f"64 bytes from {target}: icmp_seq={i+1} ttl=64 time={delay}.0 ms\n"
            result += f"\n--- {target} ping statistics ---\n4 packets transmitted, 4 received, 0% packet loss"
            return result
        return "用法: ping <主机名/IP>"

    def cmd_ifconfig(self, args: List[str]) -> str:
        """显示网络接口"""
        return """eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 10.0.2.15  netmask 255.255.255.0  broadcast 10.0.2.255
        inet6 fe80::21a:2bff:fe3c:4d5e  prefixlen 64  scopeid 0x20<link>
        ether 00:1a:2b:3c:4d:5e  txqueuelen 1000  (Ethernet)
        RX packets 128  bytes 10240 (10.0 MB)
        TX packets 256  bytes 20480 (20.0 MB)"""

    def cmd_ps(self, args: List[str]) -> str:
        """显示进程列表"""
        return ("PID  PPID  STATE    NAME\n"
                "1    0     RUNNING  kernel\n"
                "2    1     RUNNING  memory_manager\n"
                "3    1     RUNNING  ipc_manager\n"
                "4    1     RUNNING  driver_manager\n"
                "5    1     RUNNING  filesystem\n"
                "6    1     RUNNING  network_stack\n"
                "7    1     RUNNING  gui_desktop")

    def cmd_neofetch(self, args: List[str]) -> str:
        """显示系统信息"""
        return f"""
            .-+++:.             {self.username}@{self.hostname}
          :+++++++++.          ------------------------
        :+++++++++++++:        OS: {sys_config.SYSTEM_NAME} {sys_config.SYSTEM_VERSION}
       .+++++++++++++++.       Kernel: TianOS Microkernel {sys_config.SYSTEM_VERSION}
      .+++++++++++++++++:      Uptime: {int(time.time()) % 86400 // 3600} hours
      :+++++++++++++++++'      Shell: TianOS Terminal
      :++++:.  .:+++++++'      Resolution: 1280x720
      :+++'      '+++++++'     WM: TianOS Window Manager
      :++++:.  .:+++++++'      Theme: TianOS-Default
      :+++++++++++++++++'      Terminal: TianOS Terminal
      .+++++++++++++++++:      CPU: TianOS-VCPU @ 2.40GHz
       .+++++++++++++++.       Memory: 1024MB
        :+++++++++++++:
         .+++++++++++.
           .-+++-.
        """

    def cmd_shutdown(self, args: List[str]) -> str:
        """关闭系统"""
        self._append_output("正在关闭系统...", "#ff6644")
        QTimer.singleShot(2000, lambda: sys.exit(0))
        return ""

    def cmd_reboot(self, args: List[str]) -> str:
        """重启系统"""
        self._append_output("正在重启系统...", "#ff6644")

        def _reboot():
            try:
                from boot.bsod import restart_tianos
                restart_tianos()
            except Exception:
                sys.exit(0)
        QTimer.singleShot(2000, _reboot)
        return ""

    def cmd_panic(self, args: List[str]) -> str:
        """手动触发系统蓝屏 (PANIC)"""
        self._append_output("正在手动触发系统 PANIC...", "#ff6644")

        def _panic():
            try:
                from boot.bsod import handle_crash
                handle_crash(
                    RuntimeError("KERNEL_PANIC: 终端手动触发 (panic 命令)"),
                    phase="系统命令",
                    text_mode=False,
                )
            except Exception as e:
                self._append_output(f"PANIC 触发失败: {e}", "#ff6644")

        QTimer.singleShot(300, _panic)
        return ""

    def cmd_mkdir(self, args: List[str]) -> str:
        """创建目录"""
        if args:
            return f"已创建目录: {args[0]}"
        return "用法: mkdir <目录名>"

    def cmd_touch(self, args: List[str]) -> str:
        """创建文件"""
        if args:
            return f"已创建文件: {args[0]}"
        return "用法: touch <文件名>"

    def cmd_rm(self, args: List[str]) -> str:
        """删除文件"""
        if args:
            return f"已删除: {args[0]}"
        return "用法: rm <文件名>"

    def cmd_df(self, args: List[str]) -> str:
        """显示磁盘使用"""
        return ("Filesystem      Size  Used  Avail  Use%  Mounted on\n"
                "dev/hda1       5.0G  1.2G  3.8G   24%   /\n"
                "tmpfs          512M  4.0K  512M    1%   /tmp")

    def cmd_tree(self, args: List[str]) -> str:
        """显示目录树"""
        return ("/\n"
                "├── boot/\n"
                "├── bin/\n"
                "├── dev/\n"
                "├── etc/\n"
                "├── home/\n"
                "│   └── user/\n"
                "├── lib/\n"
                "├── mnt/\n"
                "├── proc/\n"
                "├── sys/\n"
                "├── tmp/\n"
                "├── usr/\n"
                "└── var/")