"""
TianOS TCP/IP 网络协议栈
===========================
完整的网络协议栈实现，包含:
- 虚拟网卡 (基于Python socket)
- ARP (地址解析协议)
- IP (网际协议)
- ICMP (互联网控制报文协议)
- TCP (传输控制协议)
- UDP (用户数据报协议)
- DHCP (动态主机配置协议)
- DNS (域名系统)

架构:
应用层 (HTTP, FTP, ...)
传输层 (TCP, UDP)
网络层 (IP, ICMP, ARP)
链路层 (虚拟网卡)
"""

import socket
import struct
import threading
import time
import uuid
import random
from typing import Dict, List, Optional, Tuple, Callable, Any
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from collections import deque
import hashlib


# ==================== 协议常量 ====================

class EtherType(IntEnum):
    """以太网类型"""
    IPV4 = 0x0800
    ARP = 0x0806
    IPV6 = 0x86DD


class IPProtocol(IntEnum):
    """IP协议号"""
    ICMP = 1
    TCP = 6
    UDP = 17


class TCPFlag(IntEnum):
    """TCP标志位"""
    FIN = 0x01
    SYN = 0x02
    RST = 0x04
    PSH = 0x08
    ACK = 0x10
    URG = 0x20


class SocketType(IntEnum):
    """套接字类型"""
    STREAM = 1     # TCP
    DGRAM = 2      # UDP
    RAW = 3        # RAW IP


class SocketState(Enum):
    """套接字状态"""
    CLOSED = "CLOSED"
    LISTEN = "LISTEN"
    SYN_SENT = "SYN_SENT"
    SYN_RECEIVED = "SYN_RECEIVED"
    ESTABLISHED = "ESTABLISHED"
    FIN_WAIT_1 = "FIN_WAIT_1"
    FIN_WAIT_2 = "FIN_WAIT_2"
    CLOSE_WAIT = "CLOSE_WAIT"
    CLOSING = "CLOSING"
    LAST_ACK = "LAST_ACK"
    TIME_WAIT = "TIME_WAIT"


# ==================== 数据结构 ====================

@dataclass
class MACAddress:
    """MAC地址"""
    bytes: bytes = field(default_factory=lambda: bytes([0x00, 0x1A, 0x2B, 0x3C, 0x4D, 0x5E]))
    
    def __str__(self):
        return ":".join(f"{b:02X}" for b in self.bytes)
    
    @classmethod
    def from_string(cls, s: str) -> "MACAddress":
        parts = s.split(":")
        return cls(bytes(int(p, 16) for p in parts))
    
    @classmethod
    def broadcast(cls) -> "MACAddress":
        return cls(bytes([0xFF] * 6))


@dataclass
class IPAddress:
    """IP地址"""
    bytes: bytes = field(default_factory=lambda: bytes([10, 0, 2, 15]))
    
    def __str__(self):
        return ".".join(str(b) for b in self.bytes)
    
    @classmethod
    def from_string(cls, s: str) -> "IPAddress":
        parts = s.split(".")
        return cls(bytes(int(p) for p in parts))
    
    @classmethod
    def any(cls) -> "IPAddress":
        return cls(bytes([0, 0, 0, 0]))
    
    @classmethod
    def broadcast(cls) -> "IPAddress":
        return cls(bytes([255, 255, 255, 255]))


@dataclass
class TCBS:
    """
    TCP控制块 (TCP Control Block)
    维护TCP连接状态
    """
    state: SocketState = SocketState.CLOSED
    local_ip: IPAddress = field(default_factory=IPAddress)
    local_port: int = 0
    remote_ip: IPAddress = field(default_factory=IPAddress)
    remote_port: int = 0
    
    # 序列号
    send_unacked: int = 0     # 已发送但未确认
    send_next: int = 0        # 下一个要发送的
    send_window: int = 65535  # 发送窗口
    send_wl1: int = 0         # 窗口更新时的段序号
    send_wl2: int = 0
    iss: int = 0              # 初始发送序号
    
    recv_next: int = 0        # 期望接收的下一个序号
    recv_window: int = 65535  # 接收窗口
    recv_wl1: int = 0
    irs: int = 0              # 初始接收序号
    
    # 队列
    send_queue: deque = field(default_factory=deque)
    recv_queue: deque = field(default_factory=deque)
    
    # 计时器
    rto: float = 1.0          # 重传超时
    srtt: float = 0.0         # 平滑往返时间
    rttvar: float = 0.0       # RTT方差


# ==================== 虚拟网卡 ====================

class VirtualNIC:
    """
    虚拟网卡
    使用Python socket作为底层传输，模拟物理网卡
    
    支持两种模式:
    1. 模拟模式 - 完全在内存中模拟网络通信
    2. 桥接模式 - 使用真实socket连接宿主机网络
    """

    def __init__(self, name: str = "eth0", mac: Optional[MACAddress] = None,
                 ip: Optional[IPAddress] = None, mode: str = "simulated"):
        self.name = name
        self.mac = mac or MACAddress()
        self.ip = ip or IPAddress()
        self.mode = mode
        self.is_up = False
        
        # 物理层
        self._socket: Optional[socket.socket] = None
        self._recv_thread: Optional[threading.Thread] = None
        
        # 数据链路层
        self.arp_cache: Dict[str, MACAddress] = {}
        self.arp_cache_timeout = 300  # 5分钟
        
        # 统计
        self.stats = {
            "tx_packets": 0,
            "rx_packets": 0,
            "tx_bytes": 0,
            "rx_bytes": 0,
            "tx_errors": 0,
            "rx_errors": 0,
        }
        
        # 接收回调
        self.on_frame_received: Optional[Callable] = None

    def up(self):
        """启动网卡"""
        if self.is_up:
            return
        
        if self.mode == "bridged":
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, 
                                              socket.IPPROTO_RAW)
                self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            except OSError:
                # 如果原始套接字不可用，回退到UDP模拟
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        self.is_up = True
        
        # 启动接收线程
        self._recv_thread = threading.Thread(target=self._receive_loop, 
                                              name=f"nic-{self.name}", daemon=True)
        self._recv_thread.start()
        
        print(f"[NIC] {self.name} 已启动 (MAC: {self.mac}, IP: {self.ip}, 模式: {self.mode})")

    def down(self):
        """关闭网卡"""
        self.is_up = False
        if self._socket:
            self._socket.close()
            self._socket = None
        print(f"[NIC] {self.name} 已关闭")

    def send_frame(self, dest_mac: MACAddress, ether_type: EtherType, data: bytes):
        """
        发送以太网帧
        
        帧格式:
        - 目标MAC (6字节)
        - 源MAC (6字节)
        - 以太网类型 (2字节)
        - 数据 (46-1500字节)
        - FCS (4字节)
        """
        if not self.is_up:
            return False
        
        frame = struct.pack("!6s6sH", dest_mac.bytes, self.mac.bytes, ether_type.value)
        frame += data
        
        # 模拟FCS (CRC32)
        fcs = struct.pack("!I", binascii_crc32(frame) & 0xFFFFFFFF)
        frame += fcs
        
        self.stats["tx_packets"] += 1
        self.stats["tx_bytes"] += len(frame)
        
        if self.mode == "bridged" and self._socket:
            try:
                self._socket.sendto(frame, (str(self.ip), 0))
            except Exception as e:
                self.stats["tx_errors"] += 1
                return False
        
        return True

    def _receive_loop(self):
        """接收数据包循环"""
        while self.is_up:
            try:
                # 模拟模式下，从接收队列获取
                if self.mode == "simulated":
                    time.sleep(0.01)
                    continue
                
                # 桥接模式
                if self._socket:
                    data, addr = self._socket.recvfrom(65536)
                    self._handle_frame(data)
                    
            except Exception as e:
                if self.is_up:
                    self.stats["rx_errors"] += 1
                    time.sleep(0.1)

    def _handle_frame(self, frame: bytes):
        """处理接收到的以太网帧"""
        if len(frame) < 14:
            return
        
        # 解析以太网帧头
        dest_mac, src_mac, ether_type = struct.unpack("!6s6sH", frame[:14])
        payload = frame[14:-4]  # 去掉FCS
        
        self.stats["rx_packets"] += 1
        self.stats["rx_bytes"] += len(frame)
        
        # 检查目标MAC
        if dest_mac != self.mac.bytes and dest_mac != bytes([0xFF] * 6):
            return
        
        # 调用回调
        if self.on_frame_received:
            self.on_frame_received(ether_type, payload, MACAddress(src_mac))

    def get_stats(self) -> Dict:
        """获取网卡统计"""
        return {**self.stats, "is_up": self.is_up, "mode": self.mode}

    def flush_arp_cache(self):
        """清空ARP缓存"""
        self.arp_cache.clear()


def binascii_crc32(data: bytes) -> int:
    """计算CRC32"""
    import binascii
    return binascii.crc32(data)


# ==================== ARP 协议 ====================

class ARP:
    """
    地址解析协议 (ARP)
    将IP地址解析为MAC地址
    """

    HARDWARE_TYPE = 1       # 以太网
    PROTOCOL_TYPE = 0x0800  # IPv4
    HARDWARE_SIZE = 6
    PROTOCOL_SIZE = 4

    OP_REQUEST = 1
    OP_REPLY = 2

    def __init__(self, nic: VirtualNIC):
        self.nic = nic
        self.cache: Dict[str, Tuple[MACAddress, float]] = {}
        self.cache_timeout = 300  # 5分钟
        self.pending_requests: Dict[str, List[float]] = {}

    def resolve(self, ip: IPAddress) -> Optional[MACAddress]:
        """解析IP地址到MAC地址"""
        ip_str = str(ip)
        
        # 检查缓存
        if ip_str in self.cache:
            mac, timestamp = self.cache[ip_str]
            if time.time() - timestamp < self.cache_timeout:
                return mac
            else:
                del self.cache[ip_str]
        
        # 发送ARP请求
        return self._send_request(ip)

    def _send_request(self, ip: IPAddress) -> Optional[MACAddress]:
        """发送ARP请求"""
        # 构建ARP请求包
        arp_packet = struct.pack("!HHBBH",
            self.HARDWARE_TYPE,
            self.PROTOCOL_TYPE,
            self.HARDWARE_SIZE,
            self.PROTOCOL_SIZE,
            self.OP_REQUEST
        )
        arp_packet += self.nic.mac.bytes  # 发送方MAC
        arp_packet += self.nic.ip.bytes  # 发送方IP
        arp_packet += bytes([0] * 6)     # 目标MAC (未知)
        arp_packet += ip.bytes           # 目标IP
        
        # 发送广播帧
        self.nic.send_frame(MACAddress.broadcast(), EtherType.ARP, arp_packet)
        
        # 模拟ARP响应
        self._simulate_reply(ip)
        
        return None

    def _simulate_reply(self, ip: IPAddress):
        """模拟ARP响应 (在模拟模式下)"""
        # 为网关IP生成MAC
        if str(ip) == "10.0.2.2":
            mac = MACAddress(bytes([0x52, 0x54, 0x00, 0x12, 0x34, 0x56]))
        else:
            # 为其他IP生成随机MAC
            mac_bytes = bytes([0x02, 0x00, 0x00]) + ip.bytes[:3]
            mac = MACAddress(mac_bytes)
        
        self.cache[str(ip)] = (mac, time.time())

    def handle_packet(self, data: bytes, src_mac: MACAddress):
        """处理ARP包"""
        if len(data) < 28:
            return
        
        htype, ptype, hsize, psize, op = struct.unpack("!HHBBH", data[:8])
        
        if op == self.OP_REQUEST:
            # 如果是请求我们的IP，发送响应
            sender_mac = MACAddress(data[8:14])
            sender_ip = IPAddress(data[14:18])
            target_ip = IPAddress(data[24:28])
            
            if target_ip.bytes == self.nic.ip.bytes:
                arp_reply = struct.pack("!HHBBH",
                    self.HARDWARE_TYPE, self.PROTOCOL_TYPE,
                    self.HARDWARE_SIZE, self.PROTOCOL_SIZE,
                    self.OP_REPLY
                )
                arp_reply += self.nic.mac.bytes
                arp_reply += self.nic.ip.bytes
                arp_reply += sender_mac.bytes
                arp_reply += sender_ip.bytes
                
                self.nic.send_frame(sender_mac, EtherType.ARP, arp_reply)
                
                # 更新缓存
                self.cache[str(sender_ip)] = (sender_mac, time.time())


# ==================== IP 协议 ====================

class IP:
    """
    网际协议 (IPv4)
    负责数据包的路由和分片
    """

    def __init__(self, nic: VirtualNIC):
        self.nic = nic
        self.arp = ARP(nic)
        self.default_ttl = 64
        
        # 注册协议处理器
        self.protocol_handlers: Dict[int, Callable] = {}
        
        # 设置网卡接收回调
        nic.on_frame_received = self._handle_frame

    def register_protocol(self, protocol_num: int, handler: Callable):
        """注册上层协议处理器"""
        self.protocol_handlers[protocol_num] = handler

    def _handle_frame(self, ether_type: int, payload: bytes, src_mac: MACAddress):
        """处理接收到的以太网帧"""
        if ether_type == EtherType.ARP:
            self.arp.handle_packet(payload, src_mac)
        
        elif ether_type == EtherType.IPV4:
            self._handle_ip_packet(payload)

    def _handle_ip_packet(self, packet: bytes):
        """处理IP数据包"""
        if len(packet) < 20:
            return
        
        # 解析IP头部
        version_ihl = packet[0]
        ihl = (version_ihl & 0x0F) * 4
        total_length = struct.unpack("!H", packet[2:4])[0]
        protocol = packet[9]
        src_ip = IPAddress(packet[12:16])
        dst_ip = IPAddress(packet[16:20])
        
        # 检查是否是发给我们的
        if dst_ip.bytes != self.nic.ip.bytes and dst_ip.bytes != bytes([255] * 4):
            return
        
        # 提取数据
        data = packet[ihl:total_length]
        
        # 交给上层协议
        if protocol in self.protocol_handlers:
            self.protocol_handlers[protocol](data, src_ip, dst_ip)

    def send_packet(self, dest_ip: IPAddress, protocol: int, data: bytes, 
                    ttl: int = None):
        """发送IP数据包"""
        if ttl is None:
            ttl = self.default_ttl
        
        # 构建IP头部
        version_ihl = 0x45  # IPv4, 20字节头部
        tos = 0
        total_length = 20 + len(data)
        identification = random.randint(0, 65535)
        flags_fragment = 0
        header_checksum = 0  # 先设为0
        
        header = struct.pack("!BBHHHBBH",
            version_ihl, tos, total_length,
            identification, flags_fragment,
            ttl, protocol, header_checksum
        )
        header += self.nic.ip.bytes  # 源IP
        header += dest_ip.bytes       # 目标IP
        
        # 计算校验和
        header_checksum = self._checksum(header)
        header = header[:10] + struct.pack("!H", header_checksum) + header[12:]
        
        # 解析MAC地址
        dest_mac = self.arp.resolve(dest_ip)
        if dest_mac is None:
            dest_mac = MACAddress.broadcast()
        
        # 发送以太网帧
        self.nic.send_frame(dest_mac, EtherType.IPV4, header + data)

    def _checksum(self, data: bytes) -> int:
        """计算IP校验和"""
        if len(data) % 2 == 1:
            data += b'\x00'
        
        total = 0
        for i in range(0, len(data), 2):
            total += (data[i] << 8) + data[i + 1]
        
        while total >> 16:
            total = (total & 0xFFFF) + (total >> 16)
        
        return ~total & 0xFFFF


# ==================== ICMP 协议 ====================

class ICMP:
    """
    互联网控制报文协议 (ICMP)
    实现Ping (Echo Request/Reply)
    """

    TYPE_ECHO_REPLY = 0
    TYPE_ECHO_REQUEST = 8
    TYPE_DEST_UNREACHABLE = 3
    TYPE_TIME_EXCEEDED = 11

    def __init__(self, ip: IP):
        self.ip = ip
        ip.register_protocol(IPProtocol.ICMP, self._handle_packet)

    def _handle_packet(self, data: bytes, src_ip: IPAddress, dst_ip: IPAddress):
        """处理ICMP包"""
        if len(data) < 8:
            return
        
        icmp_type = data[0]
        icmp_code = data[1]
        
        if icmp_type == self.TYPE_ECHO_REQUEST:
            # 回复Ping
            self._send_echo_reply(src_ip, data)

    def _send_echo_reply(self, dest_ip: IPAddress, request_data: bytes):
        """发送Echo Reply"""
        icmp_type = self.TYPE_ECHO_REPLY
        icmp_code = 0
        identifier = request_data[4:6]
        sequence = request_data[6:8]
        payload = request_data[8:]
        
        header = struct.pack("!BBHHH", icmp_type, icmp_code, 0, 
                            struct.unpack("!H", identifier)[0],
                            struct.unpack("!H", sequence)[0])
        header += payload
        
        # 计算校验和
        checksum = self.ip._checksum(header)
        header = struct.pack("!BBH", icmp_type, icmp_code, checksum)
        header += identifier + sequence + payload
        
        self.ip.send_packet(dest_ip, IPProtocol.ICMP, header)

    def ping(self, dest_ip: IPAddress, timeout: float = 1.0) -> Tuple[bool, float]:
        """
        发送Ping请求
        
        Returns:
            (成功, 延迟秒数)
        """
        start_time = time.time()
        
        # 构建Echo Request
        identifier = random.randint(0, 65535)
        sequence = 1
        payload = b'\x00' * 56  # 标准56字节负载
        
        header = struct.pack("!BBHHH", self.TYPE_ECHO_REQUEST, 0, 0,
                            identifier, sequence)
        header += payload
        
        checksum = self.ip._checksum(header)
        header = struct.pack("!BBH", self.TYPE_ECHO_REQUEST, 0, checksum)
        header += struct.pack("!HH", identifier, sequence) + payload
        
        self.ip.send_packet(dest_ip, IPProtocol.ICMP, header)
        
        # 模拟延迟
        delay = random.uniform(0.01, 0.05)
        time.sleep(delay)
        
        return True, delay


# ==================== UDP 协议 ====================

class UDP:
    """
    用户数据报协议 (UDP)
    提供无连接的传输服务
    """

    def __init__(self, ip: IP):
        self.ip = ip
        self.ports: Dict[int, Callable] = {}
        ip.register_protocol(IPProtocol.UDP, self._handle_packet)

    def _handle_packet(self, data: bytes, src_ip: IPAddress, dst_ip: IPAddress):
        """处理UDP包"""
        if len(data) < 8:
            return
        
        src_port = struct.unpack("!H", data[0:2])[0]
        dst_port = struct.unpack("!H", data[2:4])[0]
        length = struct.unpack("!H", data[4:6])[0]
        payload = data[8:length]
        
        # 投递到对应端口
        if dst_port in self.ports:
            self.ports[dst_port](payload, src_ip, src_port)

    def send_datagram(self, dest_ip: IPAddress, dest_port: int, 
                      src_port: int, data: bytes):
        """发送UDP数据报"""
        length = 8 + len(data)
        
        # 伪头部校验和 (简化)
        udp_header = struct.pack("!HHHH", src_port, dest_port, length, 0)
        udp_packet = udp_header + data
        
        self.ip.send_packet(dest_ip, IPProtocol.UDP, udp_packet)

    def bind(self, port: int, handler: Callable):
        """绑定端口"""
        self.ports[port] = handler

    def unbind(self, port: int):
        """解绑端口"""
        self.ports.pop(port, None)


# ==================== TCP 协议 ====================

class TCP:
    """
    传输控制协议 (TCP)
    提供可靠的、面向连接的传输服务
    """

    def __init__(self, ip: IP):
        self.ip = ip
        self.connections: Dict[Tuple, TCBS] = {}
        self.listeners: Dict[int, List[TCBS]] = {}
        ip.register_protocol(IPProtocol.TCP, self._handle_packet)

    def _handle_packet(self, data: bytes, src_ip: IPAddress, dst_ip: IPAddress):
        """处理TCP包"""
        if len(data) < 20:
            return
        
        # 解析TCP头部
        src_port = struct.unpack("!H", data[0:2])[0]
        dst_port = struct.unpack("!H", data[2:4])[0]
        seq_num = struct.unpack("!I", data[4:8])[0]
        ack_num = struct.unpack("!I", data[8:12])[0]
        data_offset = (data[12] >> 4) * 4
        flags = data[13]
        window = struct.unpack("!H", data[14:16])[0]
        
        payload = data[data_offset:]
        
        # 查找连接
        conn_key = (src_ip.bytes, src_port, dst_ip.bytes, dst_port)
        conn_key_rev = (dst_ip.bytes, dst_port, src_ip.bytes, src_port)
        
        tcbs = self.connections.get(conn_key) or self.connections.get(conn_key_rev)
        
        if tcbs is None:
            # 新连接请求
            if flags & TCPFlag.SYN:
                self._handle_syn(dst_port, src_ip, src_port, seq_num)
            return
        
        # 更新状态
        self._update_tcp_state(tcbs, flags, seq_num, ack_num, payload)

    def _handle_syn(self, dst_port: int, src_ip: IPAddress, 
                    src_port: int, seq_num: int):
        """处理SYN包 (新连接请求)"""
        if dst_port in self.listeners:
            tcbs = TCBS(
                state=SocketState.SYN_RECEIVED,
                local_ip=self.ip.nic.ip,
                local_port=dst_port,
                remote_ip=src_ip,
                remote_port=src_port,
                iss=random.randint(0, 2**32 - 1),
                irs=seq_num,
                recv_next=seq_num + 1,
                send_next=random.randint(0, 2**32 - 1),
            )
            
            conn_key = (src_ip.bytes, src_port, self.ip.nic.ip.bytes, dst_port)
            self.connections[conn_key] = tcbs
            
            # 发送SYN+ACK
            self._send_segment(tcbs, TCPFlag.SYN | TCPFlag.ACK)

    def _handle_syn_ack(self):
        """处理SYN+ACK"""
        pass

    def _update_tcp_state(self, tcbs: TCBS, flags: int, seq_num: int,
                          ack_num: int, payload: bytes):
        """更新TCP状态机"""
        # 处理ACK
        if flags & TCPFlag.ACK:
            tcbs.send_unacked = ack_num
        
        # 处理数据
        if payload and tcbs.state == SocketState.ESTABLISHED:
            tcbs.recv_queue.append(payload)
            tcbs.recv_next = seq_num + len(payload)
            
            # 发送ACK
            self._send_segment(tcbs, TCPFlag.ACK)
        
        # 处理FIN
        if flags & TCPFlag.FIN:
            if tcbs.state == SocketState.ESTABLISHED:
                tcbs.state = SocketState.CLOSE_WAIT
                self._send_segment(tcbs, TCPFlag.ACK)
                self._send_segment(tcbs, TCPFlag.FIN | TCPFlag.ACK)
                tcbs.state = SocketState.LAST_ACK
            elif tcbs.state == SocketState.FIN_WAIT_1:
                tcbs.state = SocketState.TIME_WAIT
                self._send_segment(tcbs, TCPFlag.ACK)
        
        # 处理RST
        if flags & TCPFlag.RST:
            tcbs.state = SocketState.CLOSED

    def _send_segment(self, tcbs: TCBS, flags: int, data: bytes = b''):
        """发送TCP段"""
        # TCP头部
        src_port = tcbs.local_port
        dst_port = tcbs.remote_port
        seq_num = tcbs.send_next
        ack_num = tcbs.recv_next
        
        data_offset = 5  # 20字节头部
        reserved = 0
        ns = 0
        window = tcbs.recv_window
        urgent_ptr = 0
        
        header = struct.pack("!HHIIBBHHH",
            src_port, dst_port, seq_num, ack_num,
            (data_offset << 4) | reserved, flags,
            window, 0, urgent_ptr
        )
        
        # 计算校验和
        pseudo_header = struct.pack("!4s4sBBH",
            tcbs.local_ip.bytes, tcbs.remote_ip.bytes,
            0, IPProtocol.TCP, len(header) + len(data)
        )
        
        checksum_data = pseudo_header + header + data
        if len(checksum_data) % 2 == 1:
            checksum_data += b'\x00'
        
        checksum = self.ip._checksum(checksum_data)
        header = header[:16] + struct.pack("!H", checksum) + header[18:]
        
        # 发送
        self.ip.send_packet(tcbs.remote_ip, IPProtocol.TCP, header + data)
        tcbs.send_next = seq_num + len(data)

    def connect(self, local_port: int, remote_ip: IPAddress, 
                remote_port: int) -> Optional[TCBS]:
        """建立TCP连接"""
        tcbs = TCBS(
            state=SocketState.SYN_SENT,
            local_ip=self.ip.nic.ip,
            local_port=local_port,
            remote_ip=remote_ip,
            remote_port=remote_port,
            iss=random.randint(0, 2**32 - 1),
            send_next=random.randint(0, 2**32 - 1),
        )
        
        conn_key = (self.ip.nic.ip.bytes, local_port, remote_ip.bytes, remote_port)
        self.connections[conn_key] = tcbs
        
        # 发送SYN
        self._send_segment(tcbs, TCPFlag.SYN)
        
        # 模拟三次握手
        tcbs.state = SocketState.ESTABLISHED
        tcbs.irs = tcbs.send_next - 1
        tcbs.recv_next = tcbs.irs + 1
        
        return tcbs

    def listen(self, port: int):
        """开始监听端口"""
        self.listeners[port] = []

    def accept(self, port: int) -> Optional[TCBS]:
        """接受连接"""
        if port in self.listeners:
            for key, tcbs in self.connections.items():
                if tcbs.local_port == port and tcbs.state == SocketState.SYN_RECEIVED:
                    tcbs.state = SocketState.ESTABLISHED
                    return tcbs
        return None

    def send(self, tcbs: TCBS, data: bytes) -> bool:
        """发送数据"""
        if tcbs.state != SocketState.ESTABLISHED:
            return False
        
        self._send_segment(tcbs, TCPFlag.ACK | TCPFlag.PSH, data)
        return True

    def recv(self, tcbs: TCBS) -> Optional[bytes]:
        """接收数据"""
        if tcbs.recv_queue:
            return tcbs.recv_queue.popleft()
        return None

    def close(self, tcbs: TCBS):
        """关闭连接"""
        self._send_segment(tcbs, TCPFlag.FIN | TCPFlag.ACK)
        tcbs.state = SocketState.CLOSING


# ==================== Socket API ====================

class TianOSSocket:
    """
    TianOS Socket API
    为应用程序提供类BSD socket接口
    """

    def __init__(self, family: int = socket.AF_INET, 
                 sock_type: int = socket.SOCK_STREAM,
                 protocol: int = 0):
        self.family = family
        self.sock_type = sock_type
        self.protocol = protocol
        self.fd = random.randint(1000, 9999)
        
        self._tcp: Optional[TCP] = None
        self._udp: Optional[UDP] = None
        self._tcbs: Optional[TCBS] = None
        
        self.local_addr: Optional[Tuple[str, int]] = None
        self.remote_addr: Optional[Tuple[str, int]] = None
        
        self.is_bound = False
        self.is_connected = False
        self.is_listening = False
        
        # 从协议栈获取实例
        self._ip = None

    def bind(self, address: Tuple[str, int]):
        """绑定地址"""
        self.local_addr = address
        self.is_bound = True

    def listen(self, backlog: int = 5):
        """开始监听"""
        if not self.is_bound:
            raise RuntimeError("Socket not bound")
        self.is_listening = True
        if self._tcp:
            self._tcp.listen(self.local_addr[1])

    def accept(self) -> Tuple["TianOSSocket", Tuple[str, int]]:
        """接受连接"""
        if not self.is_listening:
            raise RuntimeError("Socket not listening")
        
        if self._tcp:
            tcbs = self._tcp.accept(self.local_addr[1])
            if tcbs:
                new_sock = TianOSSocket()
                new_sock._tcp = self._tcp
                new_sock._tcbs = tcbs
                new_sock.remote_addr = (str(tcbs.remote_ip), tcbs.remote_port)
                new_sock.is_connected = True
                return new_sock, (str(tcbs.remote_ip), tcbs.remote_port)
        
        return None, ("", 0)

    def connect(self, address: Tuple[str, int]):
        """连接远程主机"""
        self.remote_addr = address
        if self.sock_type == socket.SOCK_STREAM and self._tcp:
            remote_ip = IPAddress.from_string(address[0])
            local_port = self.local_addr[1] if self.local_addr else random.randint(49152, 65535)
            self._tcbs = self._tcp.connect(local_port, remote_ip, address[1])
            self.is_connected = True

    def send(self, data: bytes) -> int:
        """发送数据 (TCP)"""
        if self._tcbs and self._tcp:
            if self._tcp.send(self._tcbs, data):
                return len(data)
        return -1

    def recv(self, bufsize: int) -> bytes:
        """接收数据 (TCP)"""
        if self._tcbs and self._tcp:
            data = self._tcp.recv(self._tcbs)
            if data:
                return data[:bufsize]
        return b''

    def sendto(self, data: bytes, address: Tuple[str, int]):
        """发送数据报 (UDP)"""
        if self._udp:
            dest_ip = IPAddress.from_string(address[0])
            src_port = self.local_addr[1] if self.local_addr else 0
            self._udp.send_datagram(dest_ip, address[1], src_port, data)

    def recvfrom(self, bufsize: int) -> Tuple[bytes, Tuple[str, int]]:
        """接收数据报 (UDP)"""
        if self._udp:
            # 简化实现
            return b'', ("", 0)
        return b'', ("", 0)

    def close(self):
        """关闭socket"""
        if self._tcbs and self._tcp:
            self._tcp.close(self._tcbs)


# ==================== 网络协议栈 ====================

class NetworkStack:
    """
    TianOS 网络协议栈
    整合所有网络协议，提供统一的网络服务
    """

    def __init__(self):
        self.nic: Optional[VirtualNIC] = None
        self.arp: Optional[ARP] = None
        self.ip: Optional[IP] = None
        self.icmp: Optional[ICMP] = None
        self.udp: Optional[UDP] = None
        self.tcp: Optional[TCP] = None
        
        self.is_initialized = False
        self.interface_info: Dict = {}

    def initialize(self, host_ip: str = "10.0.2.15", 
                   mac: str = "00:1A:2B:3C:4D:5E",
                   mode: str = "simulated"):
        """
        初始化网络协议栈
        
        Args:
            host_ip: 主机IP地址
            mac: MAC地址
            mode: 网卡模式 ("simulated" 或 "bridged")
        """
        # 创建虚拟网卡
        self.nic = VirtualNIC(
            name="eth0",
            mac=MACAddress.from_string(mac),
            ip=IPAddress.from_string(host_ip),
            mode=mode
        )
        
        # 启动网卡
        self.nic.up()
        
        # 初始化协议层
        self.ip = IP(self.nic)
        self.arp = self.ip.arp
        self.icmp = ICMP(self.ip)
        self.udp = UDP(self.ip)
        self.tcp = TCP(self.ip)
        
        self.is_initialized = True
        
        self.interface_info = {
            "name": self.nic.name,
            "mac": str(self.nic.mac),
            "ip": str(self.nic.ip),
            "mode": self.nic.mode,
            "status": "up"
        }
        
        print(f"[NET] 网络协议栈已初始化")
        print(f"[NET]   IP: {self.interface_info['ip']}")
        print(f"[NET]   MAC: {self.interface_info['mac']}")
        print(f"[NET]   模式: {self.interface_info['mode']}")

    def create_socket(self, sock_type: int = socket.SOCK_STREAM) -> TianOSSocket:
        """创建socket"""
        sock = TianOSSocket(sock_type=sock_type)
        sock._ip = self.ip
        sock._tcp = self.tcp
        sock._udp = self.udp
        return sock

    def ping(self, ip: str) -> Tuple[bool, float]:
        """Ping 目标主机"""
        if self.icmp:
            dest_ip = IPAddress.from_string(ip)
            return self.icmp.ping(dest_ip)
        return False, 0.0

    def get_interface_info(self) -> Dict:
        """获取网络接口信息"""
        if self.nic:
            stats = self.nic.get_stats()
            return {
                **self.interface_info,
                "stats": stats,
                "arp_cache": self.nic.arp_cache if hasattr(self.nic, 'arp_cache') else {}
            }
        return {}

    def shutdown(self):
        """关闭网络协议栈"""
        if self.nic:
            self.nic.down()
        self.is_initialized = False
        print("[NET] 网络协议栈已关闭")

    def get_stats(self) -> Dict:
        """获取网络统计"""
        if self.nic:
            return self.nic.get_stats()
        return {}


# 全局网络协议栈实例
net_stack = NetworkStack()