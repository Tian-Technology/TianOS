#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TianOS 微内核操作系统 - 主入口
================================
完整的启动流程:
1. BIOS POST - 硬件检测
2. Bootloader - 引导加载
3. Kernel - 微内核启动
4. Network Stack - 网络协议栈
5. GUI Desktop - 桌面环境 (PyQt6)

启动命令:
    python main.py          # 正常启动 (含开机画面)
    python main.py --text   # 文本模式启动 (无GUI)
    python main.py --debug  # 调试模式 (详细日志)
"""

import sys
import os
import time
import argparse
import threading
import psutil
from typing import Optional, Dict, List

# 确保能找到模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from system.config import sys_config


# ==================== 解析命令行参数 ====================

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description=f"TianOS 微内核操作系统 {sys_config.SYSTEM_VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py              # 正常启动 (GUI模式)
  python main.py --text       # 文本模式
  python main.py --debug      # 调试模式
  python main.py --no-net     # 不启动网络
        """
    )
    parser.add_argument("--text", action="store_true", help="文本模式启动")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    parser.add_argument("--no-net", action="store_true", help="不启动网络")
    parser.add_argument("--quick", action="store_true", help="快速启动 (跳过POST)")
    parser.add_argument("--core", type=int, default=None, help="绑定到指定CPU核心 (例如 --core 1)")
    return parser.parse_args()


def bind_cpu_core(core_id: int):
    """将当前进程绑定到指定CPU核心"""
    try:
        p = psutil.Process()
        cpu_count = psutil.cpu_count(logical=True)
        
        if core_id < 0 or core_id >= cpu_count:
            print(f"⚠ 核心号 {core_id} 无效，可用核心: 0-{cpu_count - 1}")
            return False
        
        p.cpu_affinity([core_id])
        print(f"✔ 进程已绑定到 CPU 核心 #{core_id} (共 {cpu_count} 核心)")
        return True
    except Exception as e:
        print(f"⚠ CPU 亲和性设置失败: {e}")
        return False


# ==================== TianOS 系统 ====================

class TianOS:
    """
    TianOS 系统主类
    
    管理完整的系统启动流程:
    POST → Bootloader → Kernel → Services → Network → Desktop
    """

    def __init__(self, args):
        self.args = args
        self.is_text_mode = args.text
        self.is_debug = args.debug
        self.no_net = args.no_net
        
        # 系统组件
        self.bios = None
        self.bootloader = None
        self.kernel = None
        self.net_stack = None
        self.vfs = None
        
        # 状态
        self.boot_phase = "power_on"
        self.boot_progress = 0
        self.is_running = False
        self.boot_log: List[str] = []
        
        # GUI
        self.splash_screen = None
        self.desktop = None
        self.app = None

    def log(self, message: str, level: str = "INFO"):
        """记录启动日志"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.boot_log.append(log_entry)
        print(log_entry)

    # ==================== 启动阶段 ====================

    def phase_1_bios_post(self, callback=None) -> bool:
        """
        阶段1: BIOS POST
        执行上电自检，检测硬件
        """
        self.boot_phase = "bios_post"
        self.log("BIOS POST 开始...")
        
        from boot.bios import BIOS
        
        self.bios = BIOS()
        
        def post_callback(stage, progress, desc):
            self.boot_progress = int(progress * 0.15)  # 0-15%
            if callback:
                callback("BIOS POST", self.boot_progress, desc)
            if self.is_debug:
                self.log(f"POST {stage}: {desc}", "DEBUG")
        
        success = self.bios.post(post_callback)
        
        if success:
            self.log(f"BIOS POST 完成 - 检测到 {len(self.bios.detected_hardware)} 个设备")
        else:
            self.log("BIOS POST 失败!", "ERROR")
        
        return success

    def phase_2_bootloader(self, callback=None) -> bool:
        """
        阶段2: 引导加载程序
        加载内核到内存
        """
        self.boot_phase = "bootloader"
        self.log("引导加载程序启动...")
        
        from boot.bootloader import Bootloader
        
        self.bootloader = Bootloader(self.bios)
        
        def boot_callback(stage, progress, desc):
            self.boot_progress = 15 + int(progress * 0.20)  # 15-35%
            if callback:
                callback("BOOT", self.boot_progress, desc)
        
        success = self.bootloader.boot(boot_callback)
        
        if success:
            self.log(f"内核加载完成 - 入口: 0x{self.bootloader.kernel_info['entry_point']:08X}")
        else:
            self.log("引导加载失败!", "ERROR")
        
        return success

    def phase_3_kernel_init(self, callback=None) -> bool:
        """
        阶段3: 内核初始化
        启动微内核核心
        """
        self.boot_phase = "kernel_init"
        self.log("内核初始化...")
        
        from kernel.kernel import Kernel, kernel
        
        self.kernel = kernel
        
        def kernel_callback(entry):
            self.boot_progress = 35 + int(entry["time"] and 0)
        
        self.kernel.on_kernel_log = lambda entry: (
            self.log(entry["message"], entry["level"])
        )
        
        success = self.kernel.start()
        
        if success:
            self.boot_progress = 50
            if callback:
                callback("KERNEL", 50, "内核初始化完成")
            self.log("微内核启动成功")
        else:
            self.log("内核启动失败!", "ERROR")
        
        return success

    def phase_4_network_init(self, callback=None) -> bool:
        """
        阶段4: 网络协议栈初始化
        启动TCP/IP协议栈
        """
        if self.no_net:
            self.log("网络服务已跳过 (--no-net)", "WARN")
            return True
        
        self.boot_phase = "network_init"
        self.log("网络协议栈初始化...")
        
        from net.tcpip import NetworkStack, net_stack
        
        self.net_stack = net_stack
        
        def net_callback(progress, desc):
            self.boot_progress = 50 + int(progress * 0.15)  # 50-65%
            if callback:
                callback("NET", self.boot_progress, desc)
        
        self.net_stack.initialize(
            host_ip="10.0.2.15",
            mac="00:1A:2B:3C:4D:5E",
            mode="simulated"
        )
        
        self.boot_progress = 65
        if callback:
            callback("NET", 65, "TCP/IP 协议栈就绪")
        
        self.log("网络协议栈就绪")
        return True

    def phase_5_services(self, callback=None) -> bool:
        """
        阶段5: 系统服务启动
        启动文件系统、网络服务等
        """
        self.boot_phase = "services"
        self.log("系统服务启动...")
        
        # 文件系统
        from fs.vfs import vfs
        self.vfs = vfs
        self.log("虚拟文件系统已挂载")
        
        # 网络服务
        if not self.no_net and self.net_stack:
            from net.services import NetworkServices
            net_services = NetworkServices(self.net_stack)
            net_services.initialize()
        
        self.boot_progress = 75
        if callback:
            callback("SERVICES", 75, "系统服务启动完成")
        
        self.log("系统服务就绪")
        return True

    def phase_6_gui(self, callback=None) -> bool:
        """
        阶段6: GUI桌面环境
        启动PyQt6桌面
        """
        if self.is_text_mode:
            self.boot_progress = 100
            self.log("文本模式 - 跳过GUI")
            return True
        
        self.boot_phase = "gui"
        self.log("桌面环境加载...")
        
        self.boot_progress = 85
        if callback:
            callback("GUI", 85, "窗口管理器启动")
        
        self.boot_progress = 95
        if callback:
            callback("GUI", 95, "桌面环境就绪")
        
        self.log("桌面环境就绪")
        return True

    def phase_7_complete(self, callback=None):
        """阶段7: 启动完成"""
        self.boot_phase = "complete"
        self.boot_progress = 100
        
        self.is_running = True
        
        if callback:
            callback("COMPLETE", 100, "✓ TianOS 系统就绪!")
        
        self.log("=" * 50)
        self.log(f"{sys_config.SYSTEM_NAME} 启动完成!")
        self.log(f"启动用时: {time.time() - self._start_time:.2f} 秒")
        self.log(f"模式: {'GUI' if not self.is_text_mode else '文本'}")
        self.log("=" * 50)

    # ==================== 完整启动 ====================

    def boot(self, progress_callback=None) -> bool:
        """
        执行完整的系统启动流程
        
        Args:
            progress_callback: 进度回调 (phase, progress, description)
            
        Returns:
            bool: 启动是否成功
        """
        self._start_time = time.time()
        
        self.log("TianOS 微内核操作系统 启动中...")
        self.log(f"版本: {sys_config.SYSTEM_VERSION} | 架构: {sys_config.SYSTEM_ARCH}")
        self.log("-" * 50)
        
        try:
            # 阶段0: 全局硬件管理器
            # 读取 data/active_hardware.json，动态加载硬件配置并同步到 sys_config.HARDWARE，
            # 确保 BIOS 自检、内存管理器等底层组件使用同一套动态硬件。
            from system.hardware_manager import hardware_manager
            hardware_manager.reload()
            _cpu = hardware_manager.get_cpu_info()
            _ram = hardware_manager.get_ram_info()
            self.log(
                f"硬件管理器就绪: {_cpu.get('name') or _cpu.get('model', '默认CPU')}"
                f" | {_ram.get('memory_type') or _ram.get('type', '默认内存')} "
                f"{int(_ram.get('total_mb') or 0) // 1024}GB"
            )
            if not hardware_manager.is_active_config_present():
                self.log("未检测到主动硬件配置 (active_hardware.json)，使用默认硬件参数", "WARN")

            # 阶段1: BIOS POST
            if not self.args.quick:
                if not self.phase_1_bios_post(progress_callback):
                    raise RuntimeError("BIOS POST 失败")
            
            # 阶段2: 引导加载
            if not self.phase_2_bootloader(progress_callback):
                raise RuntimeError("引导加载失败")
            
            # 阶段3: 内核初始化
            if not self.phase_3_kernel_init(progress_callback):
                raise RuntimeError("内核初始化失败")
            
            # 阶段4: 网络协议栈
            if not self.phase_4_network_init(progress_callback):
                raise RuntimeError("网络初始化失败")
            
            # 阶段5: 系统服务
            if not self.phase_5_services(progress_callback):
                raise RuntimeError("服务启动失败")

            # 应用注册表: 把所有已安装应用写入 HKEY_CURRENT_USER\Software\TianOS\Apps
            if not self.args.quick:
                try:
                    from apps.registry import register_all_apps_on_boot
                    count = register_all_apps_on_boot()
                    self.log(f"应用注册表已更新: {count} 个应用")
                except Exception as e:
                    self.log(f"应用注册失败(非致命): {e}", "WARN")
            
            # 阶段6: GUI
            if not self.phase_6_gui(progress_callback):
                raise RuntimeError("GUI启动失败")
            
            # 阶段7: 完成
            self.phase_7_complete(progress_callback)
            
            return True
            
        except Exception as e:
            self.log(f"启动失败: {e}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            # 显示蓝屏并自动尝试修复
            self._handle_fatal_crash(e, phase=self.boot_phase)
            return False

    def _handle_fatal_crash(self, error: Exception, phase: str = ""):
        """系统致命错误处理：显示蓝屏界面并自动修复"""
        from boot.bsod import handle_crash
        self.log(f"系统出现致命错误，进入蓝屏处理: {error}", "ERROR")
        handle_crash(error, phase=phase, text_mode=self.is_text_mode)

    def _register_force_quit_shortcut(self):
        """
        注册全局强制退出快捷键 Ctrl+Shift+F1
        在任何界面按下均可强制关闭程序
        """
        from PyQt6.QtGui import QShortcut, QKeySequence, QAction
        from PyQt6.QtCore import Qt
        
        # 方案1: QShortcut 绑定到 QApplication (全局生效)
        shortcut = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_F1), self.app)
        shortcut.activated.connect(self._force_quit)
        
        # 方案2: 绑定到开机画面
        shortcut2 = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_F1), self.splash_screen)
        shortcut2.activated.connect(self._force_quit)
        
        # 方案3: 绑定到桌面窗口
        shortcut3 = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_F1), self.desktop)
        shortcut3.activated.connect(self._force_quit)
        
        self.log("全局强制退出快捷键已注册: Ctrl+Shift+F1", "INFO")

    def _force_quit(self):
        """强制关闭系统"""
        from PyQt6.QtWidgets import QApplication
        
        self.log("=" * 50, "WARN")
        self.log("系统强制关闭 (Ctrl+Shift+F1)", "WARN")
        self.log("正在终止所有进程...", "WARN")
        self.log("=" * 50, "WARN")
        
        # 关闭内核
        if hasattr(self, 'kernel') and self.kernel:
            self.kernel.shutdown()
        
        # 关闭网络
        if hasattr(self, 'net_stack') and self.net_stack:
            self.net_stack.shutdown()
        
        # 强制退出
        QApplication.quit()
        sys.exit(0)

    def run_gui(self):
        """运行GUI模式"""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt as _Qt
        from PyQt6.QtGui import QFont
        from gui.splash import BootSplashScreen
        from gui.desktop import DesktopEnvironment

        # QtWebEngine (Chromium) 要求：必须在创建 QApplication 之前启用共享 OpenGL 上下文
        QApplication.setAttribute(_Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

        # 创建QApplication
        self.app = QApplication(sys.argv)
        self.app.setStyle("Fusion")

        # 全局指定备用字体，避免 Qt 回退解析 Fixedsys 等不可用字体
        self.app.setFont(QFont("Microsoft YaHei", 9))
        
        # 设置应用样式
        self.app.setStyleSheet("""
            QToolTip {
                background-color: #1a1a3a;
                color: #ffffff;
                border: 1px solid #334466;
                padding: 5px;
            }
        """)
        
        # 开机画面
        self.splash_screen = BootSplashScreen()
        if self.args.quick:
            self.splash_screen.skip_animation()
        
        # 桌面
        self.desktop = DesktopEnvironment()
        
        # 连接信号: 开机完成 → 显示桌面
        if self.args.quick:
            BOOT_TOTAL_TIME = 0.0
        else:
            BOOT_TOTAL_TIME = sys_config.get("BOOT.splash_time_s", 1.2)
        boot_start_time = time.time()

        def show_desktop_under():
            # 淡出开始：先把桌面放到开机画面下层（作为被淡出揭示的内容），
            # 这样淡出露出的是桌面而不是宿主机界面
            self.desktop.show()

        def raise_desktop():
            # 淡出结束：置顶桌面并关闭开机画面
            self.desktop.raise_()
            self.desktop.activateWindow()
            self.splash_screen.close()

        def on_boot_complete():
            raise_desktop()

        self.splash_screen.fade_started.connect(show_desktop_under)
        self.splash_screen.boot_complete.connect(on_boot_complete)
        
        # 启动线程执行引导
        def boot_thread():
            def progress_callback(phase, progress, desc):
                # 更新启动动画的文字
                self.splash_screen.set_boot_progress(phase, progress, desc)
            
            success = self.boot(progress_callback)
            if success:
                # 根据配置的展示时长，让开机画面延后淡出
                elapsed = time.time() - boot_start_time
                remaining = max(0, BOOT_TOTAL_TIME - elapsed)
                self.splash_screen._fade_delay_ms = int(remaining * 1000)
                self.splash_screen.boot_finished()
            else:
                self.log("系统启动失败!", "ERROR")
        
        # 显示开机画面
        self.splash_screen.show()
        
        # 启动线程
        threading.Thread(target=boot_thread, daemon=True).start()
        
        # 注册全局强制退出快捷键 (Ctrl+Shift+F1)
        self._register_force_quit_shortcut()
        
        # 进入事件循环
        return self.app.exec()

    def run_text_mode(self):
        """运行文本模式"""
        print("\n" + "=" * 60)
        print(f"  {sys_config.SYSTEM_NAME} {sys_config.SYSTEM_VERSION}")
        print("  文本模式启动")
        print("=" * 60 + "\n")
        
        # 执行启动
        def progress_callback(phase, progress, desc):
            bar_length = 40
            filled = int(progress * bar_length / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            print(f"\r[{bar}] {progress:3d}% - {desc}", end="", flush=True)
        
        success = self.boot(progress_callback)
        print("\n")
        
        if success:
            print("\n✓ TianOS 系统就绪!")
            print("输入 'exit' 或 'shutdown' 关闭系统\n")
            
            # 简易Shell
            self._text_shell()
        else:
            print("\n✗ 系统启动失败!")
            sys.exit(1)

    def _text_shell(self):
        """文本模式Shell"""
        import shlex
        
        while self.is_running:
            try:
                cmd = input(f"\u001b[32muser@tianos\u001b[0m:\u001b[34m~\u001b[0m$ ").strip()
                
                if not cmd:
                    continue
                
                if cmd in ("exit", "quit", "shutdown"):
                    print("正在关闭系统...")
                    self.is_running = False
                    break
                
                elif cmd == "help":
                    print("可用命令: help, ls, pwd, echo, date, uname, neofetch, ping, ifconfig, ps, panic, clear, exit")

                elif cmd == "panic":
                    print("\n[!] 手动触发系统 PANIC，进入蓝屏诊断界面...")
                    from boot.bsod import handle_crash
                    handle_crash(
                        RuntimeError("KERNEL_PANIC: 用户手动触发 (panic 命令)"),
                        phase="系统命令",
                        text_mode=self.is_text_mode,
                    )
                    print("\n[!] 系统 PANIC 处理完毕，已返回 Shell.")
                
                elif cmd == "ls":
                    print("Desktop  Documents  Downloads")
                
                elif cmd == "pwd":
                    print("/home/user")
                
                elif cmd.startswith("echo"):
                    print(cmd[5:])
                
                elif cmd == "date":
                    print(time.strftime("%a %b %d %H:%M:%S %Y"))
                
                elif cmd == "uname":
                    print(f"{sys_config.SYSTEM_VERSION} {sys_config.SYSTEM_ARCH} GNU/TianOS")
                
                elif cmd == "neofetch":
                    print(f"""
            .-+++:.             user@tianos
          :+++++++++.          --------------
        :+++++++++++++:        OS: {sys_config.SYSTEM_NAME} {sys_config.SYSTEM_VERSION}
       .+++++++++++++++.       Kernel: Microkernel {sys_config.SYSTEM_VERSION}
      .+++++++++++++++++:      Mode: Text
      :+++++++++++++++++'
                    """)
                
                elif cmd == "ifconfig":
                    print("eth0: flags=4163<UP>  mtu 1500")
                    print("      inet 10.0.2.15  netmask 255.255.255.0")
                    print("      ether 00:1a:2b:3c:4d:5e")
                
                elif cmd == "ps":
                    print("PID  STATE    NAME")
                    print("1    RUNNING  kernel")
                    print("2    RUNNING  memory_mgr")
                    print("6    RUNNING  network_stack")
                
                elif cmd == "clear":
                    os.system("cls" if os.name == "nt" else "clear")
                
                elif cmd == "ping":
                    print("PING 10.0.2.2 (模拟) 56(84) bytes of data.")
                    print("64 bytes from 10.0.2.2: icmp_seq=1 ttl=64 time=0.035 ms")
                    print("64 bytes from 10.0.2.2: icmp_seq=2 ttl=64 time=0.028 ms")
                    print("64 bytes from 10.0.2.2: icmp_seq=3 ttl=64 time=0.042 ms")
                    print("64 bytes from 10.0.2.2: icmp_seq=4 ttl=64 time=0.031 ms")
                
                else:
                    print(f"命令未找到: {cmd}")
                    
            except KeyboardInterrupt:
                print("\n正在关闭系统...")
                self.is_running = False
                break
            except EOFError:
                break


# ==================== 主入口 ====================

def main():
    """TianOS 主入口"""
    args = parse_args()

    # 全局未捕获异常 → 蓝屏处理
    def _excepthook(exc_type, exc_value, exc_tb):
        from boot.bsod import handle_crash
        err = exc_value if isinstance(exc_value, Exception) else Exception(exc_value)
        handle_crash(err, phase="运行过程", text_mode=args.text, exec_loop=True)
        sys.exit(1)
    sys.excepthook = _excepthook
    
    # CPU 核心绑定
    if args.core is not None:
        bind_cpu_core(args.core)
    else:
        # 默认自动绑定到最后一个核心（把 0 号核心留给系统）
        cpu_count = psutil.cpu_count(logical=True)
        bind_cpu_core(cpu_count - 1)
    
    # 显示横幅
    banner = f"""
╔══════════════════════════════════════════════════════╗
║                  {sys_config.SYSTEM_NAME:<28}║
║            TianOS Microkernel Operating System        ║
║              {sys_config.SYSTEM_VERSION:<33}║
║                Build: {sys_config.SYSTEM_BUILD:<20}║
╚══════════════════════════════════════════════════════╝
    """
    print(banner)
    
    # 创建系统实例
    tianos = TianOS(args)
    
    if args.text:
        # 文本模式
        tianos.run_text_mode()
    else:
        try:
            # GUI模式
            exit_code = tianos.run_gui()
            sys.exit(exit_code)
        except ImportError as e:
            print(f"PyQt6 未安装: {e}")
            print("回退到文本模式...")
            tianos.is_text_mode = True
            tianos.run_text_mode()
        except Exception as e:
            print(f"GUI启动失败: {e}")
            from boot.bsod import handle_crash
            handle_crash(e, phase="GUI启动", text_mode=True)
            print("回退到文本模式...")
            tianos.is_text_mode = True
            tianos.run_text_mode()


if __name__ == "__main__":
    main()