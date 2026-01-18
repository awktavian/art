"""Network Discovery for Kagami Tunnel.

Provides network discovery and NAT traversal capabilities:

- External IP detection (multiple methods)
- STUN client for NAT type detection
- Local network detection (same LAN as hub)
- mDNS hub discovery

STUN Protocol (RFC 5389):
```
Client                           STUN Server
   |                                 |
   |-------- Binding Request ------->|
   |                                 |
   |<------- Binding Response -------|
   |    (MAPPED-ADDRESS, XOR-MAPPED) |
   |                                 |
```

NAT Types:
- Full Cone: Easy peer-to-peer
- Restricted Cone: Need initiator info
- Port Restricted: Need exact port
- Symmetric: Requires relay

Colony: Crystal (D5) - Security verification
h(x) >= 0. Always.

Created: January 2026
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import random
import socket
import struct
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Public STUN servers
STUN_SERVERS = [
    ("stun.l.google.com", 19302),
    ("stun1.l.google.com", 19302),
    ("stun2.l.google.com", 19302),
    ("stun3.l.google.com", 19302),
    ("stun4.l.google.com", 19302),
    ("stun.cloudflare.com", 3478),
    ("stun.services.mozilla.com", 3478),
]

# External IP detection services
IP_SERVICES = [
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
    "https://icanhazip.com",
    "https://checkip.amazonaws.com",
    "https://api.myip.com",
]

# STUN message types
STUN_BINDING_REQUEST = 0x0001
STUN_BINDING_RESPONSE = 0x0101
STUN_BINDING_ERROR = 0x0111

# STUN attributes
STUN_ATTR_MAPPED_ADDRESS = 0x0001
STUN_ATTR_XOR_MAPPED_ADDRESS = 0x0020
STUN_ATTR_ERROR_CODE = 0x0009
STUN_ATTR_FINGERPRINT = 0x8028
STUN_ATTR_SOFTWARE = 0x8022

# STUN magic cookie
STUN_MAGIC_COOKIE = 0x2112A442

# Timeouts
STUN_TIMEOUT = 3.0
HTTP_TIMEOUT = 5.0


class NATType(Enum):
    """NAT type classification."""

    UNKNOWN = auto()
    OPEN = auto()  # No NAT, direct connection possible
    FULL_CONE = auto()  # Easy peer-to-peer
    RESTRICTED_CONE = auto()  # Need initiator info
    PORT_RESTRICTED_CONE = auto()  # Need exact port
    SYMMETRIC = auto()  # Requires relay


# =============================================================================
# STUN Protocol
# =============================================================================


@dataclass
class STUNMessage:
    """STUN protocol message."""

    message_type: int
    transaction_id: bytes
    attributes: dict[int, bytes] = field(default_factory=dict)

    @classmethod
    def binding_request(cls) -> STUNMessage:
        """Create a binding request."""
        # Generate 12-byte transaction ID
        transaction_id = os.urandom(12)
        return cls(
            message_type=STUN_BINDING_REQUEST,
            transaction_id=transaction_id,
        )

    def encode(self) -> bytes:
        """Encode message to bytes."""
        # Encode attributes
        attrs_data = b""
        for attr_type, attr_value in self.attributes.items():
            # Pad to 4-byte boundary
            padded_len = (len(attr_value) + 3) & ~3
            padding = b"\x00" * (padded_len - len(attr_value))
            attrs_data += struct.pack(">HH", attr_type, len(attr_value))
            attrs_data += attr_value + padding

        # Message header
        header = struct.pack(
            ">HHI",
            self.message_type,
            len(attrs_data),
            STUN_MAGIC_COOKIE,
        )
        header += self.transaction_id

        return header + attrs_data

    @classmethod
    def decode(cls, data: bytes) -> STUNMessage:
        """Decode message from bytes."""
        if len(data) < 20:
            raise ValueError("STUN message too short")

        # Parse header
        msg_type, _length, magic = struct.unpack(">HHI", data[:8])
        if magic != STUN_MAGIC_COOKIE:
            raise ValueError("Invalid STUN magic cookie")

        transaction_id = data[8:20]

        # Parse attributes
        attributes = {}
        offset = 20
        while offset < len(data):
            if offset + 4 > len(data):
                break

            attr_type, attr_len = struct.unpack(">HH", data[offset : offset + 4])
            offset += 4

            if offset + attr_len > len(data):
                break

            attr_value = data[offset : offset + attr_len]
            attributes[attr_type] = attr_value

            # Skip padding
            padded_len = (attr_len + 3) & ~3
            offset += padded_len

        return cls(
            message_type=msg_type,
            transaction_id=transaction_id,
            attributes=attributes,
        )

    def get_mapped_address(self) -> tuple[str, int] | None:
        """Extract mapped address from response.

        Returns:
            Tuple of (ip, port) or None.
        """
        # Prefer XOR-MAPPED-ADDRESS
        if STUN_ATTR_XOR_MAPPED_ADDRESS in self.attributes:
            return self._parse_xor_mapped_address(self.attributes[STUN_ATTR_XOR_MAPPED_ADDRESS])

        # Fall back to MAPPED-ADDRESS
        if STUN_ATTR_MAPPED_ADDRESS in self.attributes:
            return self._parse_mapped_address(self.attributes[STUN_ATTR_MAPPED_ADDRESS])

        return None

    def _parse_mapped_address(self, data: bytes) -> tuple[str, int] | None:
        """Parse MAPPED-ADDRESS attribute."""
        if len(data) < 8:
            return None

        family, port = struct.unpack(">xBH", data[:4])

        if family == 0x01:  # IPv4
            ip = socket.inet_ntoa(data[4:8])
            return (ip, port)
        elif family == 0x02:  # IPv6
            if len(data) >= 20:
                ip = socket.inet_ntop(socket.AF_INET6, data[4:20])
                return (ip, port)

        return None

    def _parse_xor_mapped_address(self, data: bytes) -> tuple[str, int] | None:
        """Parse XOR-MAPPED-ADDRESS attribute."""
        if len(data) < 8:
            return None

        family, xport = struct.unpack(">xBH", data[:4])

        # XOR port with magic cookie high bytes
        port = xport ^ (STUN_MAGIC_COOKIE >> 16)

        if family == 0x01:  # IPv4
            # XOR IP with magic cookie
            xip = struct.unpack(">I", data[4:8])[0]
            ip_int = xip ^ STUN_MAGIC_COOKIE
            ip = socket.inet_ntoa(struct.pack(">I", ip_int))
            return (ip, port)
        elif family == 0x02:  # IPv6
            if len(data) >= 20:
                # XOR with magic cookie + transaction ID
                xor_key = struct.pack(">I", STUN_MAGIC_COOKIE) + self.transaction_id
                ip_bytes = bytes(a ^ b for a, b in zip(data[4:20], xor_key, strict=False))
                ip = socket.inet_ntop(socket.AF_INET6, ip_bytes)
                return (ip, port)

        return None


# =============================================================================
# STUN Client
# =============================================================================


class STUNClient:
    """STUN client for NAT traversal.

    Performs STUN binding requests to determine external IP/port
    and NAT type.

    Example:
        client = STUNClient()
        result = await client.get_mapping()
        if result:
            ip, port = result
            print(f"External address: {ip}:{port}")

        nat_type = await client.detect_nat_type()
        print(f"NAT type: {nat_type}")
    """

    def __init__(
        self,
        servers: list[tuple[str, int]] | None = None,
        timeout: float = STUN_TIMEOUT,
    ) -> None:
        """Initialize STUN client.

        Args:
            servers: List of STUN server (host, port) tuples.
            timeout: Request timeout in seconds.
        """
        self.servers = servers or STUN_SERVERS.copy()
        self.timeout = timeout
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: asyncio.DatagramProtocol | None = None

    async def get_mapping(
        self,
        local_port: int = 0,
    ) -> tuple[str, int] | None:
        """Get external IP and port mapping.

        Args:
            local_port: Local port to bind (0 for random).

        Returns:
            Tuple of (external_ip, external_port) or None.
        """
        # Try each server
        random.shuffle(self.servers)

        for server_host, server_port in self.servers:
            try:
                result = await self._stun_request(server_host, server_port, local_port)
                if result:
                    return result
            except Exception as e:
                logger.debug(f"STUN request to {server_host} failed: {e}")

        return None

    async def detect_nat_type(self) -> NATType:
        """Detect NAT type using multiple STUN requests.

        Returns:
            Detected NAT type.
        """
        # Get initial mapping
        mapping1 = await self.get_mapping()
        if not mapping1:
            return NATType.UNKNOWN

        ext_ip1, ext_port1 = mapping1

        # Check if we're behind NAT
        local_ip = await self._get_local_ip()
        if local_ip == ext_ip1:
            return NATType.OPEN

        # Get mapping from different server
        if len(self.servers) < 2:
            return NATType.UNKNOWN

        # Try second server
        server2 = self.servers[1] if self.servers[0] != (ext_ip1, ext_port1) else self.servers[2]
        mapping2 = await self._stun_request(server2[0], server2[1], 0)

        if not mapping2:
            return NATType.UNKNOWN

        ext_ip2, ext_port2 = mapping2

        # If external IP differs, we have a problem
        if ext_ip1 != ext_ip2:
            return NATType.SYMMETRIC

        # If external port differs between servers, symmetric NAT
        if ext_port1 != ext_port2:
            return NATType.SYMMETRIC

        # Could be cone NAT - more tests would be needed
        # For now, assume port-restricted cone (most common)
        return NATType.PORT_RESTRICTED_CONE

    async def _stun_request(
        self,
        server_host: str,
        server_port: int,
        local_port: int,
    ) -> tuple[str, int] | None:
        """Send STUN binding request.

        Args:
            server_host: STUN server hostname.
            server_port: STUN server port.
            local_port: Local port to bind.

        Returns:
            Tuple of (external_ip, external_port) or None.
        """
        loop = asyncio.get_event_loop()

        # Resolve server address
        try:
            server_info = await loop.getaddrinfo(server_host, server_port, family=socket.AF_INET)
            if not server_info:
                return None
            server_addr = server_info[0][4]
        except Exception as e:
            logger.debug(f"Failed to resolve {server_host}: {e}")
            return None

        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)

        if local_port:
            sock.bind(("0.0.0.0", local_port))

        try:
            # Create request
            request = STUNMessage.binding_request()
            request_data = request.encode()

            # Send request
            await loop.sock_sendto(sock, request_data, server_addr)

            # Wait for response
            try:
                async with asyncio.timeout(self.timeout):
                    response_data, _ = await loop.sock_recvfrom(sock, 1024)
            except TimeoutError:
                return None

            # Parse response
            response = STUNMessage.decode(response_data)

            # Verify transaction ID
            if response.transaction_id != request.transaction_id:
                logger.warning("STUN transaction ID mismatch")
                return None

            # Extract mapped address
            return response.get_mapped_address()

        finally:
            sock.close()

    async def _get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            # Connect to public DNS to determine local interface
            loop = asyncio.get_event_loop()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            await loop.sock_connect(sock, ("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
            sock.close()
            return local_ip
        except Exception:
            return "127.0.0.1"


# =============================================================================
# External IP Detection
# =============================================================================


async def get_external_ip() -> str | None:
    """Get external IP address using HTTP services.

    Tries multiple IP detection services for reliability.

    Returns:
        External IP address string or None.
    """
    import aiohttp

    # Randomize order for load distribution
    services = IP_SERVICES.copy()
    random.shuffle(services)

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)) as session:
        for service_url in services:
            try:
                async with session.get(service_url) as response:
                    if response.status == 200:
                        ip = (await response.text()).strip()
                        # Validate IP format
                        try:
                            ipaddress.ip_address(ip)
                            return ip
                        except ValueError:
                            continue
            except Exception as e:
                logger.debug(f"IP service {service_url} failed: {e}")

    return None


async def get_external_ip_stun() -> str | None:
    """Get external IP using STUN.

    Alternative to HTTP services, uses UDP.

    Returns:
        External IP address string or None.
    """
    client = STUNClient()
    result = await client.get_mapping()
    return result[0] if result else None


# =============================================================================
# Local Network Detection
# =============================================================================


def is_private_ip(ip: str) -> bool:
    """Check if IP address is private (RFC 1918).

    Args:
        ip: IP address string.

    Returns:
        True if private IP.
    """
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private
    except ValueError:
        return False


def is_same_network(ip1: str, ip2: str, prefix_len: int = 24) -> bool:
    """Check if two IPs are on the same network.

    Args:
        ip1: First IP address.
        ip2: Second IP address.
        prefix_len: Network prefix length.

    Returns:
        True if same network.
    """
    try:
        network = ipaddress.ip_network(f"{ip1}/{prefix_len}", strict=False)
        return ipaddress.ip_address(ip2) in network
    except ValueError:
        return False


async def get_local_ip() -> str:
    """Get local IP address on default interface.

    Returns:
        Local IP address string.
    """
    try:
        # Connect to public DNS to determine local interface
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        await loop.sock_connect(sock, ("8.8.8.8", 80))
        local_ip = sock.getsockname()[0]
        sock.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


async def is_local_network(target_ip: str) -> bool:
    """Check if target is on local network.

    Args:
        target_ip: Target IP to check.

    Returns:
        True if on local network.
    """
    # Private IPs might be local
    if not is_private_ip(target_ip):
        return False

    local_ip = await get_local_ip()
    return is_same_network(local_ip, target_ip)


# =============================================================================
# Network Discovery Results
# =============================================================================


@dataclass
class NetworkInfo:
    """Network discovery results."""

    # Local addresses
    local_ip: str
    local_port: int = 0

    # External addresses (from STUN)
    external_ip: str | None = None
    external_port: int | None = None

    # NAT information
    nat_type: NATType = NATType.UNKNOWN

    # Discovery timestamp
    discovered_at: float = field(default_factory=time.time)

    def needs_tunnel(self) -> bool:
        """Check if tunnel is required for connectivity."""
        return self.nat_type in (NATType.SYMMETRIC, NATType.UNKNOWN)

    def supports_hole_punch(self) -> bool:
        """Check if NAT hole punching is possible."""
        return self.nat_type in (
            NATType.OPEN,
            NATType.FULL_CONE,
            NATType.RESTRICTED_CONE,
            NATType.PORT_RESTRICTED_CONE,
        )


async def discover_network(local_port: int = 0) -> NetworkInfo:
    """Perform network discovery.

    Detects local IP, external IP, and NAT type.

    Args:
        local_port: Local port to use for STUN.

    Returns:
        NetworkInfo with discovery results.
    """
    # Get local IP
    local_ip = await get_local_ip()

    # Create STUN client
    stun = STUNClient()

    # Get external mapping
    mapping = await stun.get_mapping(local_port)
    external_ip = mapping[0] if mapping else None
    external_port = mapping[1] if mapping else None

    # Detect NAT type
    nat_type = await stun.detect_nat_type()

    return NetworkInfo(
        local_ip=local_ip,
        local_port=local_port,
        external_ip=external_ip,
        external_port=external_port,
        nat_type=nat_type,
    )


# =============================================================================
# mDNS Hub Discovery
# =============================================================================


async def discover_hub_mdns(
    service_type: str = "_kagami._tcp.local.",
    timeout: float = 3.0,
) -> list[tuple[str, int]]:
    """Discover Kagami hubs via mDNS.

    Args:
        service_type: mDNS service type.
        timeout: Discovery timeout.

    Returns:
        List of (host, port) tuples.
    """
    try:
        from zeroconf import ServiceBrowser, Zeroconf
        from zeroconf.asyncio import AsyncZeroconf

        discovered: list[tuple[str, int]] = []

        class Listener:
            def add_service(self, zc, type_, name):
                info = zc.get_service_info(type_, name)
                if info:
                    for addr in info.parsed_addresses():
                        discovered.append((addr, info.port))

            def remove_service(self, zc, type_, name):
                pass

            def update_service(self, zc, type_, name):
                pass

        async with AsyncZeroconf() as azc:
            browser = ServiceBrowser(azc.zeroconf, service_type, Listener())
            await asyncio.sleep(timeout)
            browser.cancel()

        return discovered

    except ImportError:
        logger.warning("zeroconf not installed, mDNS discovery unavailable")
        return []
    except Exception as e:
        logger.error(f"mDNS discovery failed: {e}")
        return []


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "NATType",
    "NetworkInfo",
    "STUNClient",
    "STUNMessage",
    "discover_hub_mdns",
    "discover_network",
    "get_external_ip",
    "get_external_ip_stun",
    "get_local_ip",
    "is_local_network",
    "is_private_ip",
    "is_same_network",
]
