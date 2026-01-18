"""Samsung Smart TV Integration.

Direct local REST/WebSocket API for Samsung Tizen TVs.
Supports Frame TV, QLED, Neo QLED, and other Samsung Smart TVs.

Features:
- Power on/off (Wake-on-LAN + API)
- Input/source selection
- App launching
- Remote control simulation
- Art Mode (Frame TV)
- Volume control
- Media playback info

Architecture:
- REST API at http://{ip}:8001/api/v2/
- WebSocket at ws://{ip}:8002/api/v2/channels/samsung.remote.control
- Token auth required after first connection (user must confirm on TV)

Your TV: Samsung Frame 75" QN75LS03FWFXZA at 192.168.1.146

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import aiohttp

from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)


class SamsungTVKey(str, Enum):
    """Samsung TV remote control keys."""

    # Power
    POWER = "KEY_POWER"
    POWER_OFF = "KEY_POWEROFF"

    # Navigation
    UP = "KEY_UP"
    DOWN = "KEY_DOWN"
    LEFT = "KEY_LEFT"
    RIGHT = "KEY_RIGHT"
    ENTER = "KEY_ENTER"
    RETURN = "KEY_RETURN"
    EXIT = "KEY_EXIT"
    HOME = "KEY_HOME"

    # Volume
    VOLUME_UP = "KEY_VOLUP"
    VOLUME_DOWN = "KEY_VOLDOWN"
    MUTE = "KEY_MUTE"

    # Channel
    CHANNEL_UP = "KEY_CHUP"
    CHANNEL_DOWN = "KEY_CHDOWN"

    # Playback
    PLAY = "KEY_PLAY"
    PAUSE = "KEY_PAUSE"
    STOP = "KEY_STOP"
    REWIND = "KEY_REWIND"
    FAST_FORWARD = "KEY_FF"

    # Numbers
    NUM_0 = "KEY_0"
    NUM_1 = "KEY_1"
    NUM_2 = "KEY_2"
    NUM_3 = "KEY_3"
    NUM_4 = "KEY_4"
    NUM_5 = "KEY_5"
    NUM_6 = "KEY_6"
    NUM_7 = "KEY_7"
    NUM_8 = "KEY_8"
    NUM_9 = "KEY_9"

    # Colors
    RED = "KEY_RED"
    GREEN = "KEY_GREEN"
    YELLOW = "KEY_YELLOW"
    BLUE = "KEY_BLUE"

    # Source
    SOURCE = "KEY_SOURCE"
    HDMI = "KEY_HDMI"
    HDMI1 = "KEY_HDMI1"
    HDMI2 = "KEY_HDMI2"
    HDMI3 = "KEY_HDMI3"
    HDMI4 = "KEY_HDMI4"

    # Smart features
    SMART_HUB = "KEY_CONTENTS"
    AMBIENT = "KEY_AMBIENT"  # Frame TV art mode


@dataclass
class SamsungTVInfo:
    """Samsung TV device information."""

    name: str
    model: str
    model_name: str
    ip: str
    mac: str
    firmware: str
    power_state: str
    is_frame_tv: bool
    resolution: str
    network_type: str
    device_id: str


class SamsungTVIntegration:
    """Samsung Smart TV integration via local REST/WebSocket API.

    Supports Samsung Tizen-based TVs (2016+) including:
    - Frame TV (with Art Mode support)
    - QLED
    - Neo QLED
    - Crystal UHD

    Usage:
        config = SmartHomeConfig(samsung_tv_host="192.168.1.146")
        tv = SamsungTVIntegration(config)
        await tv.connect()

        await tv.power_on()
        await tv.launch_app("Netflix")
        await tv.send_key(SamsungTVKey.VOLUME_UP)
    """

    # Well-known app IDs
    APPS = {
        "netflix": "3201907018807",
        "youtube": "111299001912",
        "prime": "3201910019365",
        "disney": "3201901017640",
        "hulu": "3201601007625",
        "apple_tv": "3201807016597",
        "plex": "3201512006963",
        "spotify": "3201606009684",
        "twitch": "3201911019184",
        "art_mode": "com.samsung.art-mode",  # Frame TV
        "ambient": "com.samsung.ambient-mode",  # Frame TV
    }

    def __init__(self, config: SmartHomeConfig):
        self.config = config

        # Load from keychain if not configured
        self._load_credentials_from_keychain()

        self._host = config.samsung_tv_host
        self._port = 8001
        self._ws_port = 8002
        self._token = config.samsung_tv_token

        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._connected = False
        self._info: SamsungTVInfo | None = None

        # Callbacks
        self._power_callbacks: list[Callable[[bool], None]] = []

        # Client name (shown on TV when pairing)
        self._client_name = "Kagami"

    def _load_credentials_from_keychain(self) -> None:
        """Load Samsung TV credentials from macOS Keychain."""
        try:
            from kagami_smarthome.secrets import load_integration_credentials

            load_integration_credentials(
                "SamsungTV",
                self.config,
                [
                    ("samsung_tv_host", "samsung_tv_host"),
                    ("samsung_tv_token", "samsung_tv_token"),
                ],
            )
        except Exception as e:
            logger.debug(f"SamsungTV: Could not load from Keychain: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if connected to TV."""
        return self._connected

    @property
    def info(self) -> SamsungTVInfo | None:
        """Get TV information."""
        return self._info

    @property
    def is_frame_tv(self) -> bool:
        """Check if this is a Frame TV."""
        return self._info.is_frame_tv if self._info else False

    async def connect(self) -> bool:
        """Connect to Samsung TV.

        Returns True if connected successfully.
        First connection requires user confirmation on TV.
        """
        if not self._host:
            logger.debug("SamsungTV: No host configured")
            return False

        try:
            self._session = aiohttp.ClientSession()

            # Get device info via REST API
            info = await self._get_device_info()
            if not info:
                logger.warning("SamsungTV: Could not get device info")
                await self._session.close()
                self._session = None
                return False

            self._info = info

            # Try to establish WebSocket connection for remote control
            ws_connected = await self._connect_websocket()

            if ws_connected:
                self._connected = True
                logger.info(f"✅ SamsungTV: {info.name} ({info.model_name})")
                return True
            else:
                # REST API only (limited functionality)
                self._connected = True
                logger.info(f"⚠️ SamsungTV: REST only - {info.name}")
                return True

        except Exception as e:
            logger.error(f"SamsungTV: Connection failed - {e}")
            if self._session:
                await self._session.close()
                self._session = None
            return False

    async def disconnect(self) -> None:
        """Disconnect from TV."""
        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._session:
            await self._session.close()
            self._session = None

        self._connected = False
        logger.debug("SamsungTV: Disconnected")

    async def _get_device_info(self) -> SamsungTVInfo | None:
        """Get device information via REST API."""
        if not self._session:
            return None

        url = f"http://{self._host}:{self._port}/api/v2/"

        try:
            async with self._session.get(url, timeout=5) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                device = data.get("device", {})

                return SamsungTVInfo(
                    name=data.get("name", "Samsung TV").replace("&quot;", '"'),
                    model=device.get("model", "Unknown"),
                    model_name=device.get("modelName", "Unknown"),
                    ip=device.get("ip", self._host),
                    mac=device.get("wifiMac", ""),
                    firmware=device.get("firmwareVersion", "Unknown"),
                    power_state=device.get("PowerState", "unknown"),
                    is_frame_tv=device.get("FrameTVSupport", "false") == "true",
                    resolution=device.get("resolution", "Unknown"),
                    network_type=device.get("networkType", "Unknown"),
                    device_id=device.get("id", ""),
                )

        except TimeoutError:
            logger.debug("SamsungTV: Timeout getting device info (TV might be off)")
            return None
        except Exception as e:
            logger.debug(f"SamsungTV: Error getting device info - {e}")
            return None

    async def _connect_websocket(self) -> bool:
        """Connect WebSocket for remote control."""
        if not self._session:
            return False

        # Encode client name for URL
        name_b64 = base64.b64encode(self._client_name.encode()).decode()

        # Build WebSocket URL with optional token
        ws_url = f"wss://{self._host}:{self._ws_port}/api/v2/channels/samsung.remote.control"
        ws_url += f"?name={name_b64}"
        if self._token:
            ws_url += f"&token={self._token}"

        try:
            # Samsung TVs use self-signed certs
            ssl_context = False  # Skip SSL verification

            self._ws = await self._session.ws_connect(
                ws_url,
                ssl=ssl_context,
                timeout=10,
            )

            # Wait for connection confirmation
            msg = await asyncio.wait_for(self._ws.receive(), timeout=5)

            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                event = data.get("event")

                if event == "ms.channel.connect":
                    # Extract token for future connections
                    token = data.get("data", {}).get("token")
                    if token and not self._token:
                        self._token = token
                        logger.info("SamsungTV: Got auth token - save to config")
                    return True

                elif event == "ms.channel.clientDisconnect":
                    logger.warning("SamsungTV: Connection denied (user rejected on TV?)")
                    return False

            return False

        except TimeoutError:
            logger.debug("SamsungTV: WebSocket timeout (TV might be off)")
            return False
        except Exception as e:
            logger.debug(f"SamsungTV: WebSocket error - {e}")
            return False

    async def send_key(self, key: SamsungTVKey | str) -> bool:
        """Send remote control key press.

        Args:
            key: Key to send (SamsungTVKey enum or string)

        Returns:
            True if sent successfully
        """
        if not self._ws:
            logger.warning("SamsungTV: Not connected via WebSocket")
            return False

        key_str = key.value if isinstance(key, SamsungTVKey) else key

        payload = {
            "method": "ms.remote.control",
            "params": {
                "Cmd": "Click",
                "DataOfCmd": key_str,
                "Option": "false",
                "TypeOfRemote": "SendRemoteKey",
            },
        }

        try:
            await self._ws.send_json(payload)
            return True
        except Exception as e:
            logger.error(f"SamsungTV: Failed to send key {key_str} - {e}")
            return False

    async def power_on(self) -> bool:
        """Turn on TV via Wake-on-LAN.

        Requires MAC address from device info.
        """
        if not self._info or not self._info.mac:
            logger.warning("SamsungTV: No MAC address for WoL")
            return False

        try:
            await self._send_wol(self._info.mac)
            logger.info("SamsungTV: Sent Wake-on-LAN")
            return True
        except Exception as e:
            logger.error(f"SamsungTV: WoL failed - {e}")
            return False

    async def power_off(self) -> bool:
        """Turn off TV."""
        return await self.send_key(SamsungTVKey.POWER_OFF)

    async def _send_wol(self, mac: str) -> None:
        """Send Wake-on-LAN magic packet."""
        import socket

        # Normalize MAC address
        mac = mac.replace(":", "").replace("-", "").upper()

        # Build magic packet
        mac_bytes = bytes.fromhex(mac)
        magic = b"\xff" * 6 + mac_bytes * 16

        # Send via UDP broadcast
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic, ("255.255.255.255", 9))
        sock.close()

    async def volume_up(self) -> bool:
        """Increase volume."""
        return await self.send_key(SamsungTVKey.VOLUME_UP)

    async def volume_down(self) -> bool:
        """Decrease volume."""
        return await self.send_key(SamsungTVKey.VOLUME_DOWN)

    async def mute(self) -> bool:
        """Toggle mute."""
        return await self.send_key(SamsungTVKey.MUTE)

    async def launch_app(self, app_name: str) -> bool:
        """Launch an app by name or ID.

        Args:
            app_name: App name (netflix, youtube, etc.) or app ID

        Returns:
            True if launched successfully
        """
        app_id = self.APPS.get(app_name.lower(), app_name)

        if not self._session:
            return False

        url = f"http://{self._host}:{self._port}/api/v2/applications/{app_id}"

        try:
            async with self._session.post(url, timeout=5) as resp:
                if resp.status == 200:
                    logger.info(f"SamsungTV: Launched {app_name}")
                    return True
                else:
                    logger.warning(f"SamsungTV: Failed to launch {app_name} - {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"SamsungTV: Error launching {app_name} - {e}")
            return False

    async def launch_netflix(self) -> bool:
        """Launch Netflix."""
        return await self.launch_app("netflix")

    async def launch_youtube(self) -> bool:
        """Launch YouTube."""
        return await self.launch_app("youtube")

    async def launch_prime_video(self) -> bool:
        """Launch Prime Video."""
        return await self.launch_app("prime")

    async def launch_disney_plus(self) -> bool:
        """Launch Disney+."""
        return await self.launch_app("disney")

    async def launch_plex(self) -> bool:
        """Launch Plex."""
        return await self.launch_app("plex")

    async def enter_art_mode(self) -> bool:
        """Enter Art Mode (Frame TV only)."""
        if not self.is_frame_tv:
            logger.warning("SamsungTV: Art Mode only available on Frame TV")
            return False

        return await self.send_key(SamsungTVKey.AMBIENT)

    async def exit_art_mode(self) -> bool:
        """Exit Art Mode (Frame TV only)."""
        return await self.send_key(SamsungTVKey.POWER)

    async def set_source(self, source: str) -> bool:
        """Set input source.

        Args:
            source: Source name (hdmi1, hdmi2, etc.)

        Returns:
            True if set successfully
        """
        source_keys = {
            "hdmi1": SamsungTVKey.HDMI1,
            "hdmi2": SamsungTVKey.HDMI2,
            "hdmi3": SamsungTVKey.HDMI3,
            "hdmi4": SamsungTVKey.HDMI4,
        }

        key = source_keys.get(source.lower())
        if key:
            return await self.send_key(key)

        # Generic source button
        return await self.send_key(SamsungTVKey.SOURCE)

    async def get_installed_apps(self) -> list[dict[str, Any]]:
        """Get list of installed apps."""
        if not self._session:
            return []

        url = f"http://{self._host}:{self._port}/api/v2/applications"

        try:
            async with self._session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", {}).get("applications", [])
                return []
        except Exception:
            return []

    def on_power_change(self, callback: Callable[[bool], None]) -> None:
        """Register callback for power state changes."""
        self._power_callbacks.append(callback)

    async def is_on(self) -> bool:
        """Check if TV is currently on."""
        try:
            info = await self._get_device_info()
            return info is not None and info.power_state == "on"
        except Exception:
            return False
