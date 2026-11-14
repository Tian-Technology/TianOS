"""
TianOS 网络服务
高层网络服务: DHCP, DNS, HTTP等
"""

import time
import struct
import random
import threading
from typing import Dict, Optional, Tuple, Callable, Any
from dataclasses import dataclass

from net.tcpip import (
    NetworkStack, IPAddress, SocketType,
    TianOSSocket, IPProtocol
)


@dataclass
class DHCPLease:
    """DHCP租约"""
    ip: str
    netmask: str
    gateway: str
    dns_servers: list
    lease_time: int
    acquired_at: float


class DHCPService:
    """
    DHCP服务 (动态主机配置协议)
    自动获取IP地址配置
    """

    def __init__(self, stack: NetworkStack):
        self.stack = stack
        self.lease: Optional[DHCPLease] = None
        self.server_ip = "10.0.2.2"
        self.dhcp_port = 67
        self.client_port = 68

    def discover(self) -> Optional[DHCPLease]:
        """
        DHCP发现 - 获取IP租约
        模拟DHCP交互: Discover → Offer → Request → Ack
        """
        print("[DHCP] 正在发现DHCP服务器...")
        
        # 模拟DHCP交互
        time.sleep(0.5)
        
        # 模拟获取租约
        self.lease = DHCPLease(
            ip=self.stack.nic.ip if self.stack.nic else "10.0.2.15",
            netmask="255.255.255.0",
            gateway="10.0.2.2",
            dns_servers=["8.8.8.8", "8.8.4.4"],
            lease_time=86400,  # 24小时
            acquired_at=time.time()
        )
        
        print(f"[DHCP] 租约获取成功:")
        print(f"[DHCP]   IP: {self.lease.ip}")
        print(f"[DHCP]   子网掩码: {self.lease.netmask}")
        print(f"[DHCP]   网关: {self.lease.gateway}")
        print(f"[DHCP]   DNS: {', '.join(self.lease.dns_servers)}")
        
        return self.lease

    def release(self):
        """释放租约"""
        if self.lease:
            print(f"[DHCP] 释放IP: {self.lease.ip}")
            self.lease = None

    def renew(self) -> bool:
        """续约"""
        if self.lease:
            self.lease.acquired_at = time.time()
            return True
        return False


class DNSService:
    """
    DNS服务 (域名系统)
    域名解析
    """

    def __init__(self, stack: NetworkStack):
        self.stack = stack
        self.cache: Dict[str, Tuple[str, float]] = {}
        self.cache_timeout = 300  # 5分钟
        self.dns_servers = ["8.8.8.8", "8.8.4.4"]

    def resolve(self, hostname: str) -> Optional[str]:
        """
        解析域名到IP地址
        
        Args:
            hostname: 域名 (如 "www.example.com")
            
        Returns:
            IP地址字符串, 失败返回None
        """
        # 检查缓存
        if hostname in self.cache:
            ip, timestamp = self.cache[hostname]
            if time.time() - timestamp < self.cache_timeout:
                print(f"[DNS] 缓存命中: {hostname} -> {ip}")
                return ip
        
        # 模拟DNS解析
        print(f"[DNS] 正在解析: {hostname}")
        time.sleep(0.3)
        
        # 模拟解析结果
        dns_table = {
            "localhost": "127.0.0.1",
            "tianos.local": "10.0.2.15",
            "www.example.com": "93.184.216.34",
            "www.google.com": "142.250.80.36",
            "www.baidu.com": "39.156.66.10",
            "github.com": "140.82.121.3",
            "api.github.com": "140.82.121.5",
        }
        
        ip = dns_table.get(hostname)
        if ip:
            # 加入缓存
            self.cache[hostname] = (ip, time.time())
            print(f"[DNS] 解析成功: {hostname} -> {ip}")
        else:
            # 模拟随机解析
            ip = f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 255)}"
            self.cache[hostname] = (ip, time.time())
            print(f"[DNS] 解析成功 (模拟): {hostname} -> {ip}")
        
        return ip

    def flush_cache(self):
        """清空DNS缓存"""
        self.cache.clear()
        print("[DNS] 缓存已清空")


class HTTPService:
    """
    HTTP服务 (模拟)
    提供简单的HTTP客户端功能
    """

    def __init__(self, stack: NetworkStack):
        self.stack = stack

    def get(self, url: str) -> Dict:
        """
        HTTP GET 请求 (模拟)
        
        Args:
            url: URL地址
            
        Returns:
            响应信息
        """
        print(f"[HTTP] 正在请求: {url}")
        time.sleep(0.5)
        
        # 模拟HTTP响应
        return {
            "status": 200,
            "status_text": "OK",
            "headers": {
                "Content-Type": "text/html",
                "Server": "TianOS HTTP Server/0.1",
                "Content-Length": "1234",
            },
            "body": f"<html><body><h1>TianOS 网络测试</h1><p>请求URL: {url}</p></body></html>"
        }


class NetworkServices:
    """
    网络服务管理器
    整合所有高层网络服务
    """

    def __init__(self, stack: NetworkStack):
        self.stack = stack
        self.dhcp = DHCPService(stack)
        self.dns = DNSService(stack)
        self.http = HTTPService(stack)

    def initialize(self) -> bool:
        """初始化网络服务"""
        # DHCP获取IP
        lease = self.dhcp.discover()
        if lease:
            print("[NET] 网络服务初始化完成")
            return True
        return False

    def test_connectivity(self) -> Dict:
        """测试网络连通性"""
        results = {}
        
        # Ping网关
        success, delay = self.stack.ping("10.0.2.2")
        results["gateway"] = {"success": success, "delay_ms": round(delay * 1000, 1)}
        
        # Ping外网
        success, delay = self.stack.ping("8.8.8.8")
        results["internet"] = {"success": success, "delay_ms": round(delay * 1000, 1)}
        
        # DNS解析
        ip = self.dns.resolve("www.example.com")
        results["dns"] = {"success": ip is not None, "ip": ip}
        
        return results

    def get_status(self) -> Dict:
        """获取网络状态"""
        return {
            "interface": self.stack.get_interface_info(),
            "dhcp": {
                "has_lease": self.dhcp.lease is not None,
                "ip": self.dhcp.lease.ip if self.dhcp.lease else None
            },
            "dns_cache_size": len(self.dns.cache),
        }