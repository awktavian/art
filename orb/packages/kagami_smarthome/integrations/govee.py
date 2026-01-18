"""Govee Smart Light Integration.

Supports both Cloud API and LAN API for Govee RGB lights.

Cloud API (primary):
- REST API at openapi.api.govee.com
- Requires API key from Govee Home app
- 10,000 requests/day limit
- Works anywhere with internet

LAN API (optional, faster):
- UDP multicast on local network
- Discovery: 239.255.255.250:4001
- Commands: port 4003
- No rate limits, lower latency
- Requires same network as devices

Supports the unified SpectrumEngine for music-reactive lighting.

API Reference: https://developer.govee.com/
Created: January 3, 2026
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import aiohttp

from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

GOVEE_API_BASE = "https://openapi.api.govee.com"
GOVEE_API_VERSION = "v1"

# LAN API
LAN_MULTICAST_IP = "239.255.255.250"
LAN_DISCOVERY_PORT = 4001
LAN_RECEIVE_PORT = 4002
LAN_COMMAND_PORT = 4003
LAN_DISCOVERY_INTERVAL = 10  # seconds


# =============================================================================
# Types
# =============================================================================


class GoveeCapability(str, Enum):
    """Govee device capabilities."""

    ON_OFF = "devices.capabilities.on_off"
    COLOR_SETTING = "devices.capabilities.color_setting"
    RANGE = "devices.capabilities.range"
    SEGMENT_COLOR = "devices.capabilities.segment_color_setting"
    MODE = "devices.capabilities.mode"
    WORK_MODE = "devices.capabilities.work_mode"


@dataclass
class GoveeDevice:
    """Govee device representation."""

    device_id: str  # MAC address
    sku: str  # Model (e.g., H6160, H61A0)
    name: str
    capabilities: list[dict[str, Any]] = field(default_factory=list)
    is_online: bool = True
    last_seen: float = 0.0

    # State
    is_on: bool = False
    brightness: int = 100
    color_rgb: int = 0xFFFFFF  # 24-bit RGB
    color_temp_k: int = 4000

    # LAN support
    ip_address: str | None = None
    supports_lan: bool = False

    def has_capability(self, cap_type: str, instance: str | None = None) -> bool:
        """Check if device has a capability."""
        for cap in self.capabilities:
            if cap.get("type") == cap_type:
                if instance is None:
                    return True
                if cap.get("instance") == instance:
                    return True
        return False

    @property
    def color_tuple(self) -> tuple[int, int, int]:
        """Get RGB as tuple."""
        return (
            (self.color_rgb >> 16) & 0xFF,
            (self.color_rgb >> 8) & 0xFF,
            self.color_rgb & 0xFF,
        )


@dataclass
class GoveeColor:
    """RGB color helper."""

    r: int
    g: int
    b: int

    def to_int(self) -> int:
        """Convert to 24-bit integer (0-16777215)."""
        return (self.r << 16) | (self.g << 8) | self.b

    @classmethod
    def from_int(cls, value: int) -> GoveeColor:
        """Create from 24-bit integer."""
        return cls(
            r=(value >> 16) & 0xFF,
            g=(value >> 8) & 0xFF,
            b=value & 0xFF,
        )

    @classmethod
    def from_tuple(cls, rgb: tuple[int, int, int]) -> GoveeColor:
        """Create from RGB tuple."""
        return cls(r=rgb[0], g=rgb[1], b=rgb[2])

    def __str__(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"


# =============================================================================
# Cloud API Integration
# =============================================================================


class GoveeIntegration:
    """Govee smart light integration.

    Supports both Cloud API and LAN API with automatic fallback.

    Usage:
        govee = GoveeIntegration(config)
        await govee.connect()

        # List devices
        devices = govee.devices

        # Control
        await govee.turn_on("device_id")
        await govee.set_color("device_id", GoveeColor(255, 0, 0))
        await govee.set_brightness("device_id", 80)

        # Spectrum integration
        from kagami_smarthome.spectrum import SpectrumOutput
        await govee.apply_spectrum(output)
    """

    def __init__(self, config: SmartHomeConfig) -> None:
        """Initialize Govee integration."""
        self.config = config
        self._api_key: str | None = None
        self._session: aiohttp.ClientSession | None = None
        self._devices: dict[str, GoveeDevice] = {}
        self._initialized = False
        self._request_count = 0
        self._last_request_reset = time.time()

        # LAN support
        self._lan_enabled = False
        self._lan_socket: socket.socket | None = None
        self._lan_discovery_task: asyncio.Task | None = None

        # Load API key
        self._load_api_key()

    def _load_api_key(self) -> None:
        """Load Govee API key from keychain."""
        # Try config first
        if hasattr(self.config, "govee_api_key") and self.config.govee_api_key:
            self._api_key = self.config.govee_api_key
            return

        # Try keychain
        try:
            from kagami_smarthome.secrets import secrets

            key = secrets.get("govee_api_key")
            if key:
                self._api_key = key
                logger.debug("Govee: Loaded API key from Keychain")
        except Exception as e:
            logger.debug(f"Govee: Could not load API key: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._initialized and self._api_key is not None

    @property
    def devices(self) -> list[GoveeDevice]:
        """Get all discovered devices."""
        return list(self._devices.values())

    @property
    def lan_enabled(self) -> bool:
        """Check if LAN API is enabled."""
        return self._lan_enabled

    # =========================================================================
    # Connection
    # =========================================================================

    async def connect(self) -> bool:
        """Connect to Govee API and discover devices."""
        if not self._api_key:
            logger.warning("Govee: No API key configured")
            return False

        try:
            self._session = aiohttp.ClientSession()

            # Discover devices
            await self._discover_devices()

            if self._devices:
                logger.info(f"Govee: Connected with {len(self._devices)} devices")
                self._initialized = True

                # Try to enable LAN API
                await self._enable_lan_api()

                return True
            else:
                logger.warning("Govee: No devices found")
                return False

        except Exception as e:
            logger.error(f"Govee connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Govee."""
        self._initialized = False

        # Stop LAN discovery
        if self._lan_discovery_task:
            self._lan_discovery_task.cancel()
            try:
                await self._lan_discovery_task
            except asyncio.CancelledError:
                pass

        if self._lan_socket:
            self._lan_socket.close()
            self._lan_socket = None

        if self._session:
            await self._session.close()
            self._session = None

    async def _discover_devices(self) -> None:
        """Discover all Govee devices via Cloud API."""
        try:
            result = await self._api_get("/router/api/v1/user/devices")
            if result and "data" in result:
                for device_data in result["data"]:
                    device = GoveeDevice(
                        device_id=device_data.get("device", ""),
                        sku=device_data.get("sku", ""),
                        name=device_data.get("deviceName", "Govee Light"),
                        capabilities=device_data.get("capabilities", []),
                        is_online=device_data.get("online", True),
                        last_seen=time.time(),
                    )
                    self._devices[device.device_id] = device
                    logger.debug(f"Govee: Found {device.name} ({device.sku})")
        except Exception as e:
            logger.error(f"Govee device discovery failed: {e}")

    # =========================================================================
    # Cloud API
    # =========================================================================

    async def _api_get(self, endpoint: str) -> dict[str, Any] | None:
        """Make GET request to Govee API."""
        if not self._session or not self._api_key:
            return None

        self._check_rate_limit()

        url = f"{GOVEE_API_BASE}{endpoint}"
        headers = {
            "Govee-API-Key": self._api_key,
            "Content-Type": "application/json",
        }

        try:
            async with self._session.get(url, headers=headers, timeout=10) as response:
                self._request_count += 1
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    logger.warning("Govee: Rate limit exceeded")
                else:
                    logger.debug(f"Govee API error: {response.status}")
        except Exception as e:
            logger.debug(f"Govee API request failed: {e}")

        return None

    async def _api_post(self, endpoint: str, data: dict[str, Any]) -> bool:
        """Make POST request to Govee API."""
        if not self._session or not self._api_key:
            return False

        self._check_rate_limit()

        url = f"{GOVEE_API_BASE}{endpoint}"
        headers = {
            "Govee-API-Key": self._api_key,
            "Content-Type": "application/json",
        }

        try:
            async with self._session.post(url, headers=headers, json=data, timeout=10) as response:
                self._request_count += 1
                if response.status == 200:
                    return True
                elif response.status == 429:
                    logger.warning("Govee: Rate limit exceeded")
                else:
                    result = await response.json()
                    logger.debug(f"Govee API error: {response.status} - {result}")
        except Exception as e:
            logger.debug(f"Govee API request failed: {e}")

        return False

    def _check_rate_limit(self) -> None:
        """Check and reset rate limit counter."""
        now = time.time()
        # Reset counter daily
        if now - self._last_request_reset > 86400:
            self._request_count = 0
            self._last_request_reset = now

        if self._request_count >= 9500:  # Leave buffer
            logger.warning(f"Govee: Approaching daily rate limit ({self._request_count}/10000)")

    async def _send_command(
        self,
        device_id: str,
        capability_type: str,
        instance: str,
        value: Any,
    ) -> bool:
        """Send control command to device."""
        device = self._devices.get(device_id)
        if not device:
            logger.warning(f"Govee: Device not found: {device_id}")
            return False

        # Try LAN first if available
        if self._lan_enabled and device.supports_lan and device.ip_address:
            success = await self._lan_send_command(device, capability_type, instance, value)
            if success:
                return True
            # Fall through to cloud API

        # Cloud API
        import uuid

        data = {
            "requestId": str(uuid.uuid4()),
            "payload": {
                "sku": device.sku,
                "device": device.device_id,
                "capability": {
                    "type": capability_type,
                    "instance": instance,
                    "value": value,
                },
            },
        }

        return await self._api_post("/router/api/v1/device/control", data)

    # =========================================================================
    # LAN API
    # =========================================================================

    async def _enable_lan_api(self) -> None:
        """Try to enable LAN API for faster local control."""
        try:
            # Create UDP socket for discovery
            self._lan_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._lan_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._lan_socket.setblocking(False)

            # Join multicast group
            group = socket.inet_aton(LAN_MULTICAST_IP)
            mreq = struct.pack("4sL", group, socket.INADDR_ANY)
            self._lan_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

            self._lan_socket.bind(("", LAN_RECEIVE_PORT))

            # Start discovery task
            self._lan_discovery_task = asyncio.create_task(self._lan_discovery_loop())
            self._lan_enabled = True
            logger.info("Govee: LAN API enabled")

        except Exception as e:
            logger.debug(f"Govee: LAN API not available: {e}")
            self._lan_enabled = False

    async def _lan_discovery_loop(self) -> None:
        """Periodically discover LAN devices."""
        while self._lan_enabled:
            try:
                await self._lan_discover()
            except Exception as e:
                logger.debug(f"Govee LAN discovery error: {e}")

            await asyncio.sleep(LAN_DISCOVERY_INTERVAL)

    async def _lan_discover(self) -> None:
        """Send LAN discovery packet."""
        if not self._lan_socket:
            return

        # Discovery message format
        msg = json.dumps({"msg": {"cmd": "scan", "data": {"account_topic": "reserve"}}})

        try:
            self._lan_socket.sendto(msg.encode(), (LAN_MULTICAST_IP, LAN_DISCOVERY_PORT))

            # Wait for responses
            loop = asyncio.get_event_loop()
            for _ in range(10):  # Check for 1 second
                try:
                    data, addr = await asyncio.wait_for(
                        loop.sock_recvfrom(self._lan_socket, 1024), timeout=0.1
                    )
                    self._process_lan_response(data, addr)
                except TimeoutError:
                    continue
        except Exception as e:
            logger.debug(f"Govee LAN discovery failed: {e}")

    def _process_lan_response(self, data: bytes, addr: tuple[str, int]) -> None:
        """Process LAN discovery response."""
        try:
            response = json.loads(data.decode())
            if "msg" in response and response["msg"].get("cmd") == "devStatus":
                device_id = response["msg"]["data"].get("device")
                if device_id in self._devices:
                    self._devices[device_id].ip_address = addr[0]
                    self._devices[device_id].supports_lan = True
                    logger.debug(f"Govee: LAN device found at {addr[0]}")
        except Exception:
            pass

    async def _lan_send_command(
        self,
        device: GoveeDevice,
        capability_type: str,
        instance: str,
        value: Any,
    ) -> bool:
        """Send command via LAN API."""
        if not device.ip_address:
            return False

        # Build LAN command
        cmd_data: dict[str, Any] = {}

        if instance == "powerSwitch":
            cmd_data = {"cmd": "turn", "data": {"value": value}}
        elif instance == "brightness":
            cmd_data = {"cmd": "brightness", "data": {"value": value}}
        elif instance == "colorRgb":
            r = (value >> 16) & 0xFF
            g = (value >> 8) & 0xFF
            b = value & 0xFF
            cmd_data = {"cmd": "color", "data": {"color": {"r": r, "g": g, "b": b}}}
        elif instance == "colorTemperatureK":
            cmd_data = {"cmd": "colorTem", "data": {"color": {"tem": value}}}
        else:
            return False

        msg = json.dumps({"msg": cmd_data})

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            sock.sendto(msg.encode(), (device.ip_address, LAN_COMMAND_PORT))
            sock.close()
            return True
        except Exception as e:
            logger.debug(f"Govee LAN command failed: {e}")
            return False

    # =========================================================================
    # Control Methods
    # =========================================================================

    async def turn_on(self, device_id: str) -> bool:
        """Turn device on."""
        success = await self._send_command(
            device_id, GoveeCapability.ON_OFF.value, "powerSwitch", 1
        )
        if success and device_id in self._devices:
            self._devices[device_id].is_on = True
        return success

    async def turn_off(self, device_id: str) -> bool:
        """Turn device off."""
        success = await self._send_command(
            device_id, GoveeCapability.ON_OFF.value, "powerSwitch", 0
        )
        if success and device_id in self._devices:
            self._devices[device_id].is_on = False
        return success

    async def set_brightness(self, device_id: str, brightness: int) -> bool:
        """Set brightness (1-100)."""
        brightness = max(1, min(100, brightness))
        success = await self._send_command(
            device_id, GoveeCapability.RANGE.value, "brightness", brightness
        )
        if success and device_id in self._devices:
            self._devices[device_id].brightness = brightness
        return success

    async def set_color(self, device_id: str, color: GoveeColor | tuple[int, int, int]) -> bool:
        """Set RGB color."""
        if isinstance(color, tuple):
            color = GoveeColor.from_tuple(color)

        color_int = color.to_int()
        success = await self._send_command(
            device_id, GoveeCapability.COLOR_SETTING.value, "colorRgb", color_int
        )
        if success and device_id in self._devices:
            self._devices[device_id].color_rgb = color_int
        return success

    async def set_color_temp(self, device_id: str, kelvin: int) -> bool:
        """Set color temperature (2000-9000K)."""
        kelvin = max(2000, min(9000, kelvin))
        success = await self._send_command(
            device_id, GoveeCapability.COLOR_SETTING.value, "colorTemperatureK", kelvin
        )
        if success and device_id in self._devices:
            self._devices[device_id].color_temp_k = kelvin
        return success

    async def set_segment_color(
        self,
        device_id: str,
        segments: list[tuple[int, tuple[int, int, int]]],
    ) -> bool:
        """Set colors on individual segments (for light strips).

        Args:
            device_id: Device ID
            segments: List of (segment_index, (r, g, b)) tuples

        Returns:
            True if successful
        """
        device = self._devices.get(device_id)
        if not device or not device.has_capability(
            GoveeCapability.SEGMENT_COLOR.value, "segmentedColorRgb"
        ):
            return False

        # Build segment data
        segment_data = []
        for seg_idx, (r, g, b) in segments:
            color_int = (r << 16) | (g << 8) | b
            segment_data.append({"segment": seg_idx, "color": color_int})

        return await self._send_command(
            device_id,
            GoveeCapability.SEGMENT_COLOR.value,
            "segmentedColorRgb",
            segment_data,
        )

    # =========================================================================
    # Spectrum Integration
    # =========================================================================

    async def apply_spectrum(
        self,
        output: Any,  # SpectrumOutput
        device_ids: list[str] | None = None,
    ) -> bool:
        """Apply SpectrumEngine output to Govee devices.

        LIGHT IS MUSIC IS SPECTRUM.

        Args:
            output: SpectrumOutput from spectrum engine
            device_ids: Specific devices (None = all)

        Returns:
            True if any device updated
        """
        targets = device_ids or list(self._devices.keys())
        success = False

        # Get primary color from spectrum output
        primary_rgb = output.primary_rgb()

        for device_id in targets:
            device = self._devices.get(device_id)
            if not device:
                continue

            # Set color
            if await self.set_color(device_id, primary_rgb):
                success = True

            # Set brightness from spectrum
            brightness = int(output.brightness * 100)
            await self.set_brightness(device_id, brightness)

            # For light strips with segments, apply color palette
            if device.has_capability(GoveeCapability.SEGMENT_COLOR.value, "segmentedColorRgb"):
                if output.colors and len(output.colors) > 1:
                    # Map palette colors to segments
                    segments = [
                        (i, output.colors[i % len(output.colors)])
                        for i in range(min(10, len(output.colors) * 3))
                    ]
                    await self.set_segment_color(device_id, segments)

        return success

    async def apply_spectrum_all(self, output: Any) -> bool:
        """Apply spectrum to all devices."""
        return await self.apply_spectrum(output, None)

    # =========================================================================
    # State
    # =========================================================================

    def get_device(self, device_id: str) -> GoveeDevice | None:
        """Get device by ID."""
        return self._devices.get(device_id)

    def get_devices_by_sku(self, sku: str) -> list[GoveeDevice]:
        """Get devices by model SKU."""
        return [d for d in self._devices.values() if d.sku == sku]

    def get_state(self) -> dict[str, Any]:
        """Get integration state."""
        return {
            "connected": self._initialized,
            "lan_enabled": self._lan_enabled,
            "device_count": len(self._devices),
            "request_count": self._request_count,
            "devices": [
                {
                    "id": d.device_id,
                    "name": d.name,
                    "sku": d.sku,
                    "online": d.is_online,
                    "lan": d.supports_lan,
                }
                for d in self._devices.values()
            ],
        }


__all__ = [
    "GoveeCapability",
    "GoveeColor",
    "GoveeDevice",
    "GoveeIntegration",
]
