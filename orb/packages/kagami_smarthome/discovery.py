"""Dynamic Device Discovery via UniFi.

Uses UniFi Network as the source of truth for all device IPs.
No hardcoded IP addresses - everything is discovered by MAC or hostname.

Architecture:
- UniFi provides real-time DHCP/client data
- Devices are identified by MAC address or hostname pattern
- IPs are resolved dynamically and cached with TTL
- Changes are detected and propagated to integrations

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """Known device types for smart home integration."""

    CONTROL4_DIRECTOR = "control4_director"
    CONTROL4_CONTROLLER = "control4_controller"
    CONTROL4_AMS = "control4_ams"
    DENON_AVR = "denon_avr"
    LG_TV = "lg_tv"
    SAMSUNG_TV = "samsung_tv"
    EIGHT_SLEEP = "eight_sleep"
    OELO = "oelo"
    LUTRON = "lutron"
    APPLE_TV = "apple_tv"
    USER_PHONE = "user_phone"
    USER_LAPTOP = "user_laptop"
    UNIFI_CAMERA = "unifi_camera"
    # Appliances (typically cloud-connected but may have local presence)
    SAMSUNG_APPLIANCE = "samsung_appliance"
    LG_APPLIANCE = "lg_appliance"
    SMARTTHINGS_HUB = "smartthings_hub"
    UNKNOWN = "unknown"


@dataclass
class DiscoveredDevice:
    """A device discovered on the network."""

    mac: str
    ip: str | None
    hostname: str | None
    name: str | None  # Friendly name from UniFi
    device_type: DeviceType
    manufacturer: str | None
    model: str | None
    is_online: bool
    last_seen: float
    connection_type: str  # "wired" or "wireless"
    metadata: dict[str, Any] = field(default_factory=dict)


# Device identification rules
# Priority: MAC prefix > exact hostname > hostname pattern > manufacturer
# Rules are checked in order; first match wins
DEVICE_RULES: list[dict[str, Any]] = [
    # ==========================================================================
    # Control4 (identified by MAC prefix 00:0F:FF)
    # ==========================================================================
    {
        "mac_prefix": "00:0f:ff",
        "hostname_contains": "core5",
        "device_type": DeviceType.CONTROL4_DIRECTOR,  # Main Director
    },
    {
        "mac_prefix": "00:0f:ff",
        "hostname_contains": "ams",
        "device_type": DeviceType.CONTROL4_AMS,  # Audio matrix switch
    },
    {
        "mac_prefix": "00:0f:ff",
        "device_type": DeviceType.CONTROL4_CONTROLLER,  # Other C4 devices
    },
    # ==========================================================================
    # Denon/Marantz (D&M Holdings)
    # ==========================================================================
    {
        "mac_prefix": "00:06:78",  # D&M Holdings OUI
        "device_type": DeviceType.DENON_AVR,
    },
    {
        "mac_prefix": "00:05:cd",  # Older Denon OUI
        "device_type": DeviceType.DENON_AVR,
    },
    {
        "hostname_pattern": r"denon|avr[-_]?[axs]|marantz",
        "device_type": DeviceType.DENON_AVR,
    },
    # ==========================================================================
    # LG TV (multiple OUIs)
    # ==========================================================================
    {
        "mac_prefix": "58:96:0a",  # Your specific LG TV
        "device_type": DeviceType.LG_TV,
    },
    {
        "mac_prefix": "00:e0:4c",
        "device_type": DeviceType.LG_TV,
    },
    {
        "mac_prefix": "a8:23:fe",
        "device_type": DeviceType.LG_TV,
    },
    {
        "mac_prefix": "38:8c:50",
        "device_type": DeviceType.LG_TV,
    },
    {
        "mac_prefix": "78:5d:c8",
        "device_type": DeviceType.LG_TV,
    },
    {
        "mac_prefix": "c4:36:c0",
        "device_type": DeviceType.LG_TV,
    },
    {
        "hostname_pattern": r"lg[-_]?(tv|oled)|webos|oled\d{2}",
        "device_type": DeviceType.LG_TV,
    },
    # ==========================================================================
    # Samsung TV (Tizen Smart TVs including Frame, QLED, Neo QLED)
    # ==========================================================================
    {
        "mac_prefix": "04:e4:b6",  # Your Samsung Frame TV
        "device_type": DeviceType.SAMSUNG_TV,
    },
    {
        "mac_prefix": "f4:7b:09",  # Samsung Electronics
        "device_type": DeviceType.SAMSUNG_TV,
    },
    {
        "mac_prefix": "50:85:69",  # Samsung Electronics
        "device_type": DeviceType.SAMSUNG_TV,
    },
    {
        "mac_prefix": "c0:97:27",  # Samsung Electronics
        "device_type": DeviceType.SAMSUNG_TV,
    },
    {
        "mac_prefix": "bc:d1:1f",  # Samsung Electronics
        "device_type": DeviceType.SAMSUNG_TV,
    },
    {
        "mac_prefix": "64:b5:c6",  # Samsung Electronics
        "device_type": DeviceType.SAMSUNG_TV,
    },
    {
        "hostname_pattern": r"samsung|frame[-_]?tv|qled|neo[-_]?qled",
        "device_type": DeviceType.SAMSUNG_TV,
    },
    # ==========================================================================
    # Samsung SmartThings Hub
    # ==========================================================================
    {
        "hostname_pattern": r"smartthings[-_]?hub|st[-_]?hub",
        "device_type": DeviceType.SMARTTHINGS_HUB,
    },
    # ==========================================================================
    # LG Appliances (fridges, ovens, washers - same OUI as LG Electronics)
    # Distinguish from TV by hostname pattern
    # ==========================================================================
    {
        "hostname_pattern": r"lg[-_]?(fridge|refrigerator|range|oven|washer|dryer|dishwasher)",
        "device_type": DeviceType.LG_APPLIANCE,
    },
    # ==========================================================================
    # Samsung Appliances (Family Hub, smart ovens, washers)
    # ==========================================================================
    {
        "hostname_pattern": r"samsung[-_]?(fridge|refrigerator|range|oven|washer|dryer|family[-_]?hub)",
        "device_type": DeviceType.SAMSUNG_APPLIANCE,
    },
    # ==========================================================================
    # Lutron
    # ==========================================================================
    {
        "mac_prefix": "b8:3d:f6",  # Your Lutron bridge
        "device_type": DeviceType.LUTRON,
    },
    {
        "mac_prefix": "00:1d:c9",
        "device_type": DeviceType.LUTRON,
    },
    {
        "mac_prefix": "04:c8:07",
        "device_type": DeviceType.LUTRON,
    },
    {
        "hostname_pattern": r"lutron|caseta|ra[23]",
        "device_type": DeviceType.LUTRON,
    },
    # ==========================================================================
    # Oelo (outdoor lighting)
    # ==========================================================================
    {
        "mac_prefix": "a0:b7:65",  # Your Oelo
        "device_type": DeviceType.OELO,
    },
    {
        "hostname_pattern": r"oelo",
        "device_type": DeviceType.OELO,
    },
    # ==========================================================================
    # Eight Sleep
    # ==========================================================================
    {
        "mac_prefix": "70:b3:d5",
        "device_type": DeviceType.EIGHT_SLEEP,
    },
    {
        "mac_prefix": "70:b6:51",  # Your Eight Sleep Pod
        "device_type": DeviceType.EIGHT_SLEEP,
    },
    {
        "hostname_pattern": r"eight[-_]?(sleep|pod)|pod[0-9]",
        "device_type": DeviceType.EIGHT_SLEEP,
    },
    # ==========================================================================
    # Apple TV
    # ==========================================================================
    {
        "mac_prefix": "8c:26:aa",  # Your Apple TV (home-theater)
        "device_type": DeviceType.APPLE_TV,
    },
    {
        "hostname_pattern": r"apple[-_]?tv|home[-_]?theater",
        "device_type": DeviceType.APPLE_TV,
    },
    # ==========================================================================
    # Philips Hue
    # ==========================================================================
    {
        "mac_prefix": "ec:b5:fa",
        "device_type": DeviceType.UNKNOWN,  # Hue bridge - handled by Lutron in this setup
    },
    {
        "mac_prefix": "00:17:88",
        "device_type": DeviceType.UNKNOWN,  # Older Philips
    },
    # ==========================================================================
    # User devices (for presence detection)
    # Generic patterns - user-specific patterns loaded from secrets
    # ==========================================================================
    {
        "hostname_pattern": r"iphone",  # Generic iPhone pattern
        "device_type": DeviceType.USER_PHONE,
    },
    {
        "hostname_pattern": r"macbook|mac[-_]?studio|imac",  # Generic Mac pattern
        "device_type": DeviceType.USER_LAPTOP,
    },
    {
        "hostname_pattern": r"ipad",  # Generic iPad pattern
        "device_type": DeviceType.USER_LAPTOP,
    },
]


def _get_user_device_signatures() -> list[dict[str, Any]]:
    """Get user-specific device signatures from secrets.

    Store as comma-separated patterns in keychain:
        secrets.set("user_device_patterns", "pattern1,pattern2")

    Returns additional signature rules for user devices.
    """
    try:
        from kagami_smarthome.secrets import secrets

        patterns_str = secrets.get("user_device_patterns")
        if patterns_str:
            patterns = [p.strip() for p in patterns_str.split(",") if p.strip()]
            return [
                {"hostname_pattern": pattern, "device_type": DeviceType.USER_LAPTOP}
                for pattern in patterns
            ]
    except Exception as e:
        logger.debug(f"DeviceDiscovery: Could not load user device patterns: {e}")
    return []


@dataclass
class DeviceRegistry:
    """Registry of discovered devices with caching."""

    devices: dict[str, DiscoveredDevice] = field(default_factory=dict)  # MAC -> Device
    ip_cache: dict[str, str] = field(default_factory=dict)  # device_type -> IP
    last_refresh: float = 0.0
    cache_ttl: int = 300  # 5 minutes

    def get_by_type(self, device_type: DeviceType) -> list[DiscoveredDevice]:
        """Get all devices of a specific type."""
        return [d for d in self.devices.values() if d.device_type == device_type]

    def get_ip(self, device_type: DeviceType, index: int = 0) -> str | None:
        """Get IP for a device type (first match or by index)."""
        devices = self.get_by_type(device_type)
        online_devices = [d for d in devices if d.is_online and d.ip]
        if index < len(online_devices):
            return online_devices[index].ip
        return None

    def get_by_mac(self, mac: str) -> DiscoveredDevice | None:
        """Get device by MAC address."""
        return self.devices.get(mac.lower())

    def is_stale(self) -> bool:
        """Check if cache needs refresh."""
        return time.time() - self.last_refresh > self.cache_ttl


class DeviceDiscovery:
    """Dynamic device discovery using UniFi as source of truth.

    Resolves all device IPs dynamically - no hardcoded addresses.
    """

    def __init__(
        self,
        unifi_host: str,
        unifi_username: str,
        unifi_password: str,
        cache_ttl: int = 300,
    ):
        self.unifi_host = unifi_host
        self.unifi_username = unifi_username
        self.unifi_password = unifi_password
        self.cache_ttl = cache_ttl

        self._session: aiohttp.ClientSession | None = None
        self._csrf_token: str | None = None
        self._cookies: dict[str, str] = {}
        self._registry = DeviceRegistry(cache_ttl=cache_ttl)
        self._callbacks: list[Callable[[DeviceRegistry], None]] = []
        self._running = False
        self._monitor_task: asyncio.Task | None = None

    @property
    def registry(self) -> DeviceRegistry:
        """Get current device registry."""
        return self._registry

    async def connect(self) -> bool:
        """Connect and start discovery (alias for start)."""
        return await self.start()

    async def start(self) -> bool:
        """Start discovery and monitoring.

        Attempts UniFi API auth first, falls back to ARP discovery.
        """
        self._session = aiohttp.ClientSession()

        # Try to authenticate with UniFi
        unifi_auth = await self._authenticate()

        if unifi_auth:
            # Full UniFi discovery
            await self.refresh()
            logger.info(f"✅ DeviceDiscovery (UniFi): {len(self._registry.devices)} devices")
        else:
            # Fallback to ARP-based discovery
            logger.warning("DeviceDiscovery: UniFi auth failed, using ARP fallback")
            await self._fallback_discovery()

            if not self._registry.devices:
                logger.error("DeviceDiscovery: No devices found")
                return False

        # Start background monitoring
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        return True

    async def stop(self) -> None:
        """Stop discovery."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        if self._session:
            await self._session.close()

    async def _authenticate(self) -> bool:
        """Authenticate with UniFi controller using local admin.

        Uses local admin credentials (bypasses cloud 2FA).
        """
        if not self._session:
            return False

        # Local admin auth endpoint
        url = f"https://{self.unifi_host}/api/auth/login"
        payload = {
            "username": self.unifi_username,
            "password": self.unifi_password,
            "rememberMe": True,
        }

        try:
            async with self._session.post(url, json=payload, ssl=False, timeout=10) as resp:
                if resp.status == 200:
                    self._csrf_token = resp.headers.get("X-CSRF-Token")
                    logger.info(f"✅ DeviceDiscovery: '{self.unifi_username}' auth OK")
                    return True
                else:
                    logger.debug(f"DeviceDiscovery: Auth failed ({resp.status})")
        except TimeoutError:
            logger.debug("DeviceDiscovery: Auth timeout")
        except Exception as e:
            logger.debug(f"DeviceDiscovery: Auth error: {e}")

        return False

    async def refresh(self) -> None:
        """Refresh device list from UniFi."""
        if not self._session:
            return

        try:
            # Get all clients from UniFi
            clients = await self._get_clients()

            # Update registry
            for client in clients:
                mac = client.get("mac", "").lower()
                if not mac:
                    continue

                device = DiscoveredDevice(
                    mac=mac,
                    ip=client.get("ip"),
                    hostname=client.get("hostname"),
                    name=client.get("name") or client.get("hostname"),
                    device_type=self._identify_device(client),
                    manufacturer=client.get("oui"),
                    model=client.get("model"),
                    is_online=not client.get("is_wired", False) or client.get("ip") is not None,
                    last_seen=client.get("last_seen", time.time()),
                    connection_type="wired" if client.get("is_wired") else "wireless",
                    metadata=client,
                )

                self._registry.devices[mac] = device

            self._registry.last_refresh = time.time()

            # Log discovered smart home devices
            smart_devices = [
                d for d in self._registry.devices.values() if d.device_type != DeviceType.UNKNOWN
            ]
            if smart_devices:
                logger.debug(f"DeviceDiscovery: {len(smart_devices)} smart home devices")
                for d in smart_devices:
                    logger.debug(f"  {d.device_type.value}: {d.ip} ({d.name})")

            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(self._registry)
                except Exception as e:
                    logger.error(f"DeviceDiscovery: Callback error - {e}")

        except Exception as e:
            logger.error(f"DeviceDiscovery: Refresh error - {e}")

    async def _get_clients(self) -> list[dict[str, Any]]:
        """Get all clients from UniFi."""
        if not self._session:
            return []

        # UDM local API endpoint
        url = f"https://{self.unifi_host}/proxy/network/api/s/default/stat/sta"

        headers = {}
        if self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token

        try:
            async with self._session.get(
                url,
                headers=headers,
                ssl=False,
                timeout=30,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", [])

                # Try alternate endpoint for older controllers
                url = f"https://{self.unifi_host}/api/s/default/stat/sta"
                async with self._session.get(url, headers=headers, ssl=False) as resp2:
                    if resp2.status == 200:
                        data = await resp2.json()
                        return data.get("data", [])

        except Exception as e:
            logger.debug(f"DeviceDiscovery: Get clients error - {e}")

        return []

    def _identify_device(self, client: dict[str, Any]) -> DeviceType:
        """Identify device type from UniFi client data."""
        mac = client.get("mac", "").lower()
        hostname = (client.get("hostname") or "").lower()
        name = (client.get("name") or "").lower()
        oui = (client.get("oui") or "").lower()  # Manufacturer

        # Combine static rules with user-specific patterns from secrets
        all_rules = DEVICE_RULES + _get_user_device_signatures()

        for rule in all_rules:
            # Check MAC prefix
            if "mac_prefix" in rule:
                if not mac.startswith(rule["mac_prefix"].lower()):
                    continue

            # Check hostname contains
            if "hostname_contains" in rule:
                search = rule["hostname_contains"].lower()
                if search not in hostname and search not in name:
                    continue

            # Check hostname pattern
            if "hostname_pattern" in rule:
                pattern = rule["hostname_pattern"]
                if not (re.search(pattern, hostname, re.I) or re.search(pattern, name, re.I)):
                    continue

            # Check manufacturer
            if "manufacturer_contains" in rule:
                if rule["manufacturer_contains"].lower() not in oui:
                    continue

            # All conditions passed
            return rule["device_type"]

        return DeviceType.UNKNOWN

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                await asyncio.sleep(self.cache_ttl)
                if self._running:
                    await self.refresh()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"DeviceDiscovery: Monitor error - {e}")

    def on_change(self, callback: Callable[[DeviceRegistry], None]) -> None:
        """Register callback for device changes."""
        self._callbacks.append(callback)

    async def _discover_via_arp(self) -> list[dict[str, Any]]:
        """Discover devices via ARP table (fallback when UniFi auth fails).

        This method:
        1. Pings common smart home IPs to populate ARP cache
        2. Reads the local ARP table to find devices

        Less information than UniFi but works without authentication.
        """
        devices = []

        try:
            # First, ping common IP ranges to populate ARP cache
            # This helps discover devices that haven't communicated recently
            await self._populate_arp_cache()

            # Wait a moment for ARP entries to populate
            await asyncio.sleep(0.5)

            # Read ARP table
            proc = await asyncio.create_subprocess_exec(
                "arp",
                "-a",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            # Parse ARP output (format varies by OS)
            # macOS: host.local (192.168.1.10) at aa:bb:cc:dd:ee:ff on en0 ifscope [ethernet]
            # macOS truncated: host.local (192.168.1.10) at 0:f:ff:9f:26:f4 on en0
            # Linux: host (192.168.1.10) at aa:bb:cc:dd:ee:ff [ether] on eth0
            for line in stdout.decode().split("\n"):
                # Skip incomplete entries
                if "(incomplete)" in line:
                    continue

                # Extract IP
                ip_match = re.search(r"\((\d+\.\d+\.\d+\.\d+)\)", line)
                if not ip_match:
                    continue
                ip = ip_match.group(1)

                # Extract MAC - handle both full (aa:bb:cc:dd:ee:ff) and truncated (a:b:c:d:e:f)
                mac_match = re.search(r"at\s+([0-9a-fA-F:]+)\s", line)
                if not mac_match:
                    continue

                # Normalize MAC address (pad each octet to 2 digits)
                raw_mac = mac_match.group(1).lower()
                mac_parts = raw_mac.split(":")
                if len(mac_parts) != 6:
                    continue
                mac = ":".join(part.zfill(2) for part in mac_parts)

                # Skip broadcast
                if mac == "ff:ff:ff:ff:ff:ff":
                    continue

                # Try to get hostname
                hostname = None
                host_match = re.match(r"^(\S+)", line)
                if host_match and host_match.group(1) != "?":
                    hostname = host_match.group(1).rstrip(".")

                devices.append(
                    {
                        "mac": mac,
                        "ip": ip,
                        "hostname": hostname,
                        "name": hostname,
                        "oui": self._lookup_oui(mac),
                    }
                )

            logger.debug(f"DeviceDiscovery: Found {len(devices)} devices via ARP")

        except Exception as e:
            logger.debug(f"DeviceDiscovery: ARP discovery failed: {e}")

        return devices

    async def _populate_arp_cache(self) -> None:
        """Ping common IPs to populate ARP cache."""
        # Get subnet from UniFi host (e.g., 192.168.1.x)
        parts = self.unifi_host.split(".")
        if len(parts) != 4:
            return

        base = ".".join(parts[:3])

        # Common smart device IP suffixes to check
        # Focus on typical ranges where devices are usually assigned
        targets = [
            # Router/gateway
            f"{base}.1",
            # Common DHCP ranges
            *[f"{base}.{i}" for i in range(2, 30)],
            *[f"{base}.{i}" for i in range(100, 130)],
            *[f"{base}.{i}" for i in range(200, 256)],
        ]

        # Ping in parallel (very fast, just to populate ARP)
        async def quick_ping(ip: str) -> None:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "ping",
                    "-c",
                    "1",
                    "-W",
                    "100",
                    ip,  # 100ms timeout
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(proc.wait(), timeout=0.2)
            except Exception:
                pass

        # Run pings in batches to avoid overwhelming
        batch_size = 50
        for i in range(0, len(targets), batch_size):
            batch = targets[i : i + batch_size]
            await asyncio.gather(*[quick_ping(ip) for ip in batch], return_exceptions=True)

    def _lookup_oui(self, mac: str) -> str:
        """Lookup manufacturer from MAC prefix (OUI)."""
        # Common OUI prefixes for smart home devices
        # Format: first 3 bytes (6 chars + 2 colons)
        oui_map = {
            # Control4
            "00:0f:ff": "Control4",
            # Denon/Marantz
            "00:05:cd": "Denon",
            "00:06:78": "Denon",  # D&M Holdings
            # LG Electronics
            "00:e0:4c": "LG Electronics",
            "a8:23:fe": "LG Electronics",
            "38:8c:50": "LG Electronics",
            "78:5d:c8": "LG Electronics",
            "58:96:0a": "LG Electronics",  # Your LG TV
            "c4:36:c0": "LG Electronics",
            # Philips/Signify (Hue)
            "00:17:88": "Philips",
            "ec:b5:fa": "Philips",
            # Lutron
            "00:1d:c9": "Lutron",
            "04:c8:07": "Lutron",
            "b8:3d:f6": "Lutron",  # Your Lutron bridge
            # Apple
            "18:b4:30": "Apple",
            "3c:06:30": "Apple",
            "f0:18:98": "Apple",
            "28:6a:ba": "Apple",
            "a4:83:e7": "Apple",
            "8c:26:aa": "Apple",  # Apple TV (home-theater)
            # Ubiquiti
            "0c:ea:14": "Ubiquiti",
            "74:83:c2": "Ubiquiti",
            "f4:92:bf": "Ubiquiti",
            # Eight Sleep
            "70:b3:d5": "Eight Sleep",
            "70:b6:51": "Eight Sleep",  # Your Eight Sleep Pod
            # Oelo (uses various)
            "a0:b7:65": "Oelo",
            # WattBox
            "14:3f:c3": "WattBox",
            # MantleMount
            "d8:3a:f5": "MantleMount",
            # Tesla (wall connector, etc)
            "4c:fc:aa": "Tesla",
        }

        prefix = mac[:8].lower()
        return oui_map.get(prefix, "Unknown")

    async def _fallback_discovery(self) -> None:
        """Fallback discovery using ARP when UniFi auth fails."""
        devices = await self._discover_via_arp()

        for client in devices:
            mac = client.get("mac", "").lower()
            if not mac:
                continue

            device = DiscoveredDevice(
                mac=mac,
                ip=client.get("ip"),
                hostname=client.get("hostname"),
                name=client.get("name") or client.get("hostname"),
                device_type=self._identify_device(client),
                manufacturer=client.get("oui"),
                model=None,
                is_online=True,  # If in ARP, it's online
                last_seen=time.time(),
                connection_type="unknown",
                metadata=client,
            )

            self._registry.devices[mac] = device

        self._registry.last_refresh = time.time()

        # Log discovered smart devices
        smart_devices = [
            d for d in self._registry.devices.values() if d.device_type != DeviceType.UNKNOWN
        ]
        if smart_devices:
            logger.info(f"DeviceDiscovery (ARP): {len(smart_devices)} smart devices")
            for d in smart_devices:
                logger.info(f"  {d.device_type.value}: {d.ip} ({d.name or d.mac})")

    # =========================================================================
    # Convenience methods for getting specific device IPs
    # =========================================================================

    def get_control4_director_ip(self) -> str | None:
        """Get Control4 Director IP (for API access)."""
        return self._registry.get_ip(DeviceType.CONTROL4_DIRECTOR)

    def get_denon_ip(self) -> str | None:
        """Get Denon AVR IP."""
        return self._registry.get_ip(DeviceType.DENON_AVR)

    def get_lg_tv_ip(self) -> str | None:
        """Get LG TV IP."""
        return self._registry.get_ip(DeviceType.LG_TV)

    def get_eight_sleep_ip(self) -> str | None:
        """Get Eight Sleep IP."""
        return self._registry.get_ip(DeviceType.EIGHT_SLEEP)

    def get_oelo_ip(self) -> str | None:
        """Get Oelo controller IP."""
        return self._registry.get_ip(DeviceType.OELO)

    def get_lutron_ip(self) -> str | None:
        """Get Lutron bridge IP."""
        return self._registry.get_ip(DeviceType.LUTRON)

    def get_user_device_macs(self) -> list[str]:
        """Get MAC addresses of user devices (for presence detection)."""
        macs = []
        for d in self._registry.get_by_type(DeviceType.USER_PHONE):
            macs.append(d.mac)
        for d in self._registry.get_by_type(DeviceType.USER_LAPTOP):
            macs.append(d.mac)
        return macs

    def is_user_home(self) -> bool:
        """Check if any user device is online."""
        for d in self._registry.get_by_type(DeviceType.USER_PHONE):
            if d.is_online:
                return True
        for d in self._registry.get_by_type(DeviceType.USER_LAPTOP):
            if d.is_online:
                return True
        return False

    def get_samsung_tv_ip(self) -> str | None:
        """Get Samsung TV IP."""
        return self._registry.get_ip(DeviceType.SAMSUNG_TV)

    def get_all_smart_devices(self) -> dict[str, str | None]:
        """Get all discovered smart device IPs."""
        return {
            "control4_director": self.get_control4_director_ip(),
            "denon": self.get_denon_ip(),
            "lg_tv": self.get_lg_tv_ip(),
            "samsung_tv": self.get_samsung_tv_ip(),
            "eight_sleep": self.get_eight_sleep_ip(),
            "oelo": self.get_oelo_ip(),
            "lutron": self.get_lutron_ip(),
        }

    # =========================================================================
    # Network Health Monitoring
    # =========================================================================

    async def check_network_health(self) -> dict[str, dict[str, Any]]:
        """Check network health for all discovered smart home devices.

        Returns:
            Dict mapping device_type to health metrics:
            {
                "control4_director": {
                    "reachable": True,
                    "response_time_ms": 15.2,
                    "ip": "192.168.1.2",
                    "last_check": timestamp
                }
            }
        """
        health_status = {}
        smart_devices = self.get_all_smart_devices()

        # Check each device in parallel for speed
        tasks = []
        for device_type, ip in smart_devices.items():
            if ip:
                tasks.append(self._check_device_health(device_type, ip))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, dict):
                    device_type = result.get("device_type")
                    if device_type:
                        health_status[device_type] = result

        return health_status

    async def _check_device_health(self, device_type: str, ip: str) -> dict[str, Any]:
        """Check health of a specific device.

        Args:
            device_type: Type of device (e.g., "control4_director")
            ip: IP address to check

        Returns:
            Health metrics for the device
        """
        start_time = time.time()
        reachable = False
        response_time_ms = 0.0

        try:
            # Ping test for basic reachability
            proc = await asyncio.create_subprocess_exec(
                "ping",
                "-c",
                "1",
                "-W",
                "2000",
                ip,  # 2 second timeout
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=3.0)

            if proc.returncode == 0:
                reachable = True
                response_time_ms = (time.time() - start_time) * 1000

                # Parse ping response for more accurate timing
                output = stdout.decode()
                import re

                time_match = re.search(r"time=(\d+(?:\.\d+)?) ms", output)
                if time_match:
                    response_time_ms = float(time_match.group(1))

        except Exception as e:
            logger.debug(f"Health check failed for {device_type} ({ip}): {e}")

        return {
            "device_type": device_type,
            "reachable": reachable,
            "response_time_ms": response_time_ms,
            "ip": ip,
            "last_check": time.time(),
        }

    def get_unreachable_devices(self) -> list[str]:
        """Get list of device types that are currently unreachable."""
        # This would be called after check_network_health()
        # For now, return empty list as this requires state tracking
        return []

    async def verify_device_connectivity(self, device_type: str) -> bool:
        """Verify connectivity to a specific device type.

        Args:
            device_type: Device type to check (e.g., "control4_director")

        Returns:
            True if device is reachable
        """
        ip = self.get_all_smart_devices().get(device_type)
        if not ip:
            return False

        health = await self._check_device_health(device_type, ip)
        return health.get("reachable", False)

    async def force_refresh_device(self, device_type: str) -> str | None:
        """Force refresh discovery for a specific device type.

        Useful when an integration reports connectivity issues.

        Args:
            device_type: Device type to refresh

        Returns:
            New IP address if found, None otherwise
        """
        try:
            # Force immediate refresh
            await self.refresh()

            # Return updated IP
            return self.get_all_smart_devices().get(device_type)

        except Exception as e:
            logger.error(f"Force refresh failed for {device_type}: {e}")
            return None
