"""LG webOS TV Integration.

Direct WebSocket API implementation for LG OLED TVs.

Provides:
- Power control
- Volume/mute control
- Input switching
- App launching
- Screenshot capture
- Media control

API: LG webOS WebSocket (local, no cloud)
Library alternative: aiowebostv (but we implement key parts directly)

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from typing import Any

import aiohttp

from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)

# WebOS command URIs
COMMANDS = {
    "register": "ssap://pairing/setClientKey",
    "power_off": "ssap://system/turnOff",
    "volume_up": "ssap://audio/volumeUp",
    "volume_down": "ssap://audio/volumeDown",
    "set_volume": "ssap://audio/setVolume",
    "get_volume": "ssap://audio/getVolume",
    "mute": "ssap://audio/setMute",
    "get_mute": "ssap://audio/getMute",
    "play": "ssap://media.controls/play",
    "pause": "ssap://media.controls/pause",
    "stop": "ssap://media.controls/stop",
    "rewind": "ssap://media.controls/rewind",
    "fast_forward": "ssap://media.controls/fastForward",
    "list_apps": "ssap://com.webos.applicationManager/listApps",
    "launch_app": "ssap://com.webos.applicationManager/launch",
    "get_app_state": "ssap://com.webos.service.appstate/getAppState",
    "get_current_app": "ssap://com.webos.applicationManager/getForegroundAppInfo",
    "list_inputs": "ssap://tv/getExternalInputList",
    "set_input": "ssap://tv/switchInput",
    "get_input": "ssap://com.webos.applicationManager/getForegroundAppInfo",
    "channel_up": "ssap://tv/channelUp",
    "channel_down": "ssap://tv/channelDown",
    "get_channels": "ssap://tv/getChannelList",
    "set_channel": "ssap://tv/openChannel",
    "get_sw_info": "ssap://com.webos.service.update/getCurrentSWInformation",
    "notification": "ssap://system.notifications/createToast",
    "power_state": "ssap://com.webos.service.tvpower/power/getPowerState",
    "screen_off": "ssap://com.webos.service.tvpower/power/turnOffScreen",
    "screen_on": "ssap://com.webos.service.tvpower/power/turnOnScreen",
}

# Registration payload for pairing
REGISTRATION_PAYLOAD = {
    "forcePairing": False,
    "pairingType": "PROMPT",
    "manifest": {
        "manifestVersion": 1,
        "appVersion": "1.1",
        "signed": {
            "created": "20140509",
            "appId": "com.lge.test",
            "vendorId": "com.lge",
            "localizedAppNames": {"": "Kagami Smart Home"},
            "localizedVendorNames": {"": "Kagami"},
            "permissions": [
                "LAUNCH",
                "LAUNCH_WEBAPP",
                "APP_TO_APP",
                "CONTROL_AUDIO",
                "CONTROL_DISPLAY",
                "CONTROL_INPUT_JOYSTICK",
                "CONTROL_INPUT_MEDIA_PLAYBACK",
                "CONTROL_INPUT_MEDIA_RECORDING",
                "CONTROL_INPUT_TEXT",
                "CONTROL_INPUT_TV",
                "CONTROL_MOUSE_AND_KEYBOARD",
                "CONTROL_POWER",
                "READ_APP_STATUS",
                "READ_CURRENT_CHANNEL",
                "READ_INPUT_DEVICE_LIST",
                "READ_NETWORK_STATE",
                "READ_RUNNING_APPS",
                "READ_TV_CHANNEL_LIST",
                "WRITE_NOTIFICATION_TOAST",
            ],
            "serial": "2f930e2d2cfe083771f68e4fe3eb62e8",
        },
        "permissions": [
            "LAUNCH",
            "LAUNCH_WEBAPP",
            "APP_TO_APP",
            "CONTROL_AUDIO",
            "CONTROL_DISPLAY",
            "CONTROL_INPUT_JOYSTICK",
            "CONTROL_INPUT_MEDIA_PLAYBACK",
            "CONTROL_INPUT_MEDIA_RECORDING",
            "CONTROL_INPUT_TEXT",
            "CONTROL_INPUT_TV",
            "CONTROL_MOUSE_AND_KEYBOARD",
            "CONTROL_POWER",
            "READ_APP_STATUS",
            "READ_CURRENT_CHANNEL",
            "READ_INPUT_DEVICE_LIST",
            "READ_NETWORK_STATE",
            "READ_RUNNING_APPS",
            "READ_TV_CHANNEL_LIST",
            "WRITE_NOTIFICATION_TOAST",
        ],
        "signatures": [{"signatureVersion": 1, "signature": ""}],
    },
}


class LGTVIntegration:
    """LG webOS TV integration via WebSocket API.

    Uses aiohttp WebSocket for async communication.
    Requires initial pairing (accept prompt on TV).

    Features:
    - Automatic client key loading from Keychain
    - Automatic reconnection on disconnect
    - Persistent key storage after pairing
    """

    def __init__(self, config: SmartHomeConfig):
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._client_key: str | None = config.lg_tv_client_key
        self._initialized = False
        self._command_id = 0
        self._pending: dict[str, asyncio.Future[Any]] = {}

        # State
        self._power_on = False
        self._volume = 0
        self._muted = False
        self._current_app: str = ""
        self._current_input: str = ""
        self._apps: dict[str, str] = {}  # id -> title
        self._inputs: dict[str, str] = {}  # id -> label

        # Background tasks
        self._recv_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._auto_reconnect = True
        self._reconnect_delay = 5  # seconds

        # Load credentials from keychain
        self._load_credentials_from_keychain()

        # Load client key from keychain if not provided
        if not self._client_key:
            self._client_key = self._load_client_key()

    def _load_credentials_from_keychain(self) -> None:
        """Load LG TV host from macOS Keychain - REQUIRED."""
        # HARDENED: Secrets module is REQUIRED - no graceful fallbacks
        from kagami_smarthome.secrets import secrets

        if not self.config.lg_tv_host:
            host = secrets.get("lg_tv_host")
            if host:
                self.config.lg_tv_host = host
                logger.debug(f"✅ LG TV: Loaded host from Keychain: {host}")

    def _load_client_key(self) -> str | None:
        """Load client key from Keychain - REQUIRED for authenticated access."""
        # HARDENED: Secrets module is REQUIRED - no graceful fallbacks
        from kagami_smarthome.secrets import secrets

        key = secrets.get("lg_tv_client_key")
        if key:
            logger.debug("✅ LG TV: Loaded client key from Keychain")
        return key

    def _save_client_key(self, key: str) -> bool:
        """Save client key to Keychain for future use."""
        try:
            from kagami_smarthome.secrets import secrets

            if secrets.set("lg_tv_client_key", key):
                logger.info("LG TV: Client key saved to Keychain")
                return True
        except Exception as e:
            logger.error(f"LG TV: Could not save key to Keychain: {e}")
        return False

    @property
    def is_connected(self) -> bool:
        """Check if TV is connected and WebSocket is healthy."""
        return (
            self._initialized
            and self._ws is not None
            and not self._ws.closed
            and self._session is not None
            and not self._session.closed
        )

    @property
    def client_key(self) -> str | None:
        """Get client key (save this for future connections)."""
        return self._client_key

    async def connect(self, max_retries: int = 3) -> bool:
        """Connect to LG TV via WebSocket with retry logic.

        Args:
            max_retries: Number of connection attempts before giving up.

        Returns:
            True if connected and registered successfully.
        """
        # HARDENED: Host is REQUIRED - no graceful fallbacks
        if not self.config.lg_tv_host:
            raise RuntimeError("LG TV host is required - set lg_tv_host in config or Keychain")

        backoff = 2.0  # Start with 2 second backoff

        for attempt in range(max_retries):
            try:
                # Clean up any previous connection
                await self._cleanup_connection()

                # Create SSL context (TV uses self-signed cert)
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                self._session = aiohttp.ClientSession()

                # Connect WebSocket - prefer wss:// on 3001 (SSL)
                url = f"wss://{self.config.lg_tv_host}:3001"
                logger.debug(f"LG TV: Connecting to {url} (attempt {attempt + 1}/{max_retries})")
                try:
                    self._ws = await self._session.ws_connect(
                        url,
                        ssl=ssl_context,
                        timeout=10,
                        heartbeat=None,  # TV handles its own keepalive
                    )
                except Exception as e:
                    logger.debug(f"LG TV: SSL connection failed ({e}), trying non-SSL...")
                    # Try non-SSL fallback on port 3000
                    url = f"ws://{self.config.lg_tv_host}:3000"
                    self._ws = await self._session.ws_connect(url, timeout=10)

                # Start receiver task
                self._recv_task = asyncio.create_task(self._receive_loop())

                # Register/pair
                if not await self._register():
                    logger.warning("LG TV: Registration failed (TV may be off or needs pairing)")
                    return False

                # Get initial state
                await self._update_state()

                self._initialized = True
                self._power_on = True
                logger.info(f"LG TV: Connected to {self.config.lg_tv_host}")
                return True

            except TimeoutError:
                logger.warning(f"LG TV: Connection timeout (attempt {attempt + 1}/{max_retries})")
            except ConnectionRefusedError:
                logger.warning(f"LG TV: Connection refused (attempt {attempt + 1}/{max_retries})")
            except OSError as e:
                logger.warning(f"LG TV: Network error - {e} (attempt {attempt + 1}/{max_retries})")
            except Exception as e:
                logger.debug(f"LG TV: Connection failed - {e}")

            # Backoff before retry
            if attempt < max_retries - 1:
                await asyncio.sleep(min(backoff, 30.0))
                backoff *= 2

        # Clean up on final failure
        await self._cleanup_connection()
        logger.error(f"LG TV: Failed to connect after {max_retries} attempts")
        return False

    async def _register(self) -> bool:
        """Register/pair with TV."""
        if not self._ws:
            return False

        # Build registration message (different from normal request)
        payload = REGISTRATION_PAYLOAD.copy()
        if self._client_key:
            payload["client-key"] = self._client_key

        self._command_id += 1
        cmd_id = str(self._command_id)

        message = {
            "id": cmd_id,
            "type": "register",  # Not "request"!
            "payload": payload,
        }

        # Create future for response
        future: asyncio.Future[Any] = asyncio.Future()
        self._pending[cmd_id] = future

        try:
            await self._ws.send_json(message)

            # Wait for registration response (may need user to accept on TV)
            # Use shorter timeout if we have a key (just reconnecting)
            timeout = 10 if self._client_key else 60
            result = await asyncio.wait_for(future, timeout)

            if result and result.get("client-key"):
                new_key = result["client-key"]

                # Save key if it's new or different
                if new_key != self._client_key:
                    self._client_key = new_key
                    self._save_client_key(new_key)
                    logger.info("LG TV: Paired successfully, key saved")
                else:
                    logger.debug("LG TV: Reconnected with existing key")

                return True

            return False

        except TimeoutError:
            logger.debug("LG TV: Registration timeout")
            return False
        finally:
            self._pending.pop(cmd_id, None)

    async def _send_command(
        self,
        command: str,
        payload: dict[str, Any] | None = None,
        timeout: float = 10,
    ) -> dict[str, Any] | None:
        """Send command and wait for response."""
        if not self._ws:
            return None

        self._command_id += 1
        cmd_id = str(self._command_id)

        uri = COMMANDS.get(command, command)

        message = {
            "id": cmd_id,
            "type": "request",
            "uri": uri,
        }
        if payload:
            message["payload"] = payload

        # Create future for response
        future: asyncio.Future[Any] = asyncio.Future()
        self._pending[cmd_id] = future

        try:
            await self._ws.send_json(message)
            result = await asyncio.wait_for(future, timeout)
            return result
        except TimeoutError:
            logger.debug(f"LG TV: Command {command} timed out")
            return None
        finally:
            self._pending.pop(cmd_id, None)

    async def _receive_loop(self) -> None:
        """Background loop to receive WebSocket messages."""
        if not self._ws:
            return

        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    msg_type = data.get("type", "")
                    cmd_id = data.get("id")

                    # Handle registration response (type: "registered")
                    if (
                        msg_type == "registered"
                        and cmd_id
                        and cmd_id in self._pending
                        or msg_type == "response"
                        and cmd_id
                        and cmd_id in self._pending
                    ):
                        self._pending[cmd_id].set_result(data.get("payload", {}))

                    # Handle errors
                    elif msg_type == "error" and cmd_id and cmd_id in self._pending:
                        logger.debug(f"LG TV: Error response: {data}")
                        self._pending[cmd_id].set_result(None)

                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except Exception as e:
            logger.debug(f"LG TV: Receive loop error - {e}")

        self._initialized = False
        self._power_on = False

        # Trigger auto-reconnect if enabled
        if self._auto_reconnect and self._client_key:
            logger.info("LG TV: Connection lost, will auto-reconnect...")
            self._reconnect_task = asyncio.create_task(self._auto_reconnect_loop())

    async def _auto_reconnect_loop(self) -> None:
        """Automatically reconnect with exponential backoff and jitter."""
        import random

        attempt = 0
        base_delay = 1.0  # Start with 1 second
        max_delay = 60.0  # Cap at 60 seconds
        max_attempts = 50  # Keep trying much longer

        while self._auto_reconnect and attempt < max_attempts:
            attempt += 1

            # Exponential backoff with jitter
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            jitter = random.uniform(0, delay * 0.1)  # Add 0-10% jitter
            total_delay = delay + jitter

            logger.debug(f"LG TV: Reconnect attempt {attempt} in {total_delay:.1f}s")
            await asyncio.sleep(total_delay)

            if not self._auto_reconnect:
                break

            try:
                # Clean up old session properly
                await self._cleanup_connection()

                # Test if TV is reachable first
                if await self._ping_tv():
                    # Try to reconnect
                    if await self.connect():
                        logger.info(f"LG TV: Reconnected successfully after {attempt} attempts")
                        return
                else:
                    logger.debug("LG TV: Device unreachable, will retry...")

            except Exception as e:
                logger.debug(f"LG TV: Reconnect attempt {attempt} failed - {e}")

        if attempt >= max_attempts:
            logger.warning(f"LG TV: Auto-reconnect stopped after {max_attempts} attempts")

    async def _ping_tv(self) -> bool:
        """Quick connectivity test to TV."""
        import socket

        if not self.config.lg_tv_host:
            return False

        try:
            # Quick TCP connect test to WebSocket port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            result = sock.connect_ex((self.config.lg_tv_host, 3000))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def _cleanup_connection(self) -> None:
        """Properly clean up WebSocket and session."""
        if self._ws and not self._ws.closed:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._ws = None

        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception:
                pass
        self._session = None

    async def health_check(self) -> bool:
        """Health check for integration pool monitoring."""
        if not self.is_connected:
            return False

        try:
            # Quick non-intrusive health check
            volume_result = await asyncio.wait_for(self._send_command("get_volume"), timeout=3.0)
            return volume_result is not None
        except Exception:
            logger.debug("LG TV: Health check failed")
            return False

    def get_metrics(self) -> dict:
        """Return integration metrics for monitoring."""
        return {
            "connected": self.is_connected,
            "power_on": self._power_on,
            "current_app": self._current_app,
            "volume": self._volume,
            "muted": self._muted,
            "client_key_valid": self._client_key is not None,
            "auto_reconnect": self._auto_reconnect,
        }

    async def _update_state(self) -> None:
        """Update current TV state."""
        # Volume
        vol = await self._send_command("get_volume")
        if vol:
            self._volume = vol.get("volume", 0)
            self._muted = vol.get("muted", False)

        # Current app
        app = await self._send_command("get_current_app")
        if app:
            self._current_app = app.get("appId", "")

        # List apps
        apps = await self._send_command("list_apps")
        if apps and "apps" in apps:
            self._apps = {a["id"]: a["title"] for a in apps["apps"]}

        # List inputs
        inputs = await self._send_command("list_inputs")
        if inputs and "devices" in inputs:
            self._inputs = {d["id"]: d["label"] for d in inputs["devices"]}

    # =========================================================================
    # Power Control
    # =========================================================================

    async def power_off(self) -> bool:
        """Turn off TV."""
        result = await self._send_command("power_off")
        if result is not None:
            self._power_on = False
            return True
        return False

    async def screen_off(self) -> bool:
        """Turn off screen (TV stays on for audio)."""
        return await self._send_command("screen_off") is not None

    async def screen_on(self) -> bool:
        """Turn screen back on."""
        return await self._send_command("screen_on") is not None

    # =========================================================================
    # Volume Control
    # =========================================================================

    async def set_volume(self, level: int) -> bool:
        """Set volume (0-100)."""
        level = max(0, min(100, level))
        result = await self._send_command("set_volume", {"volume": level})
        if result is not None:
            self._volume = level
            return True
        return False

    async def volume_up(self) -> bool:
        """Increase volume."""
        return await self._send_command("volume_up") is not None

    async def volume_down(self) -> bool:
        """Decrease volume."""
        return await self._send_command("volume_down") is not None

    async def mute(self, mute: bool = True) -> bool:
        """Mute/unmute TV."""
        result = await self._send_command("mute", {"mute": mute})
        if result is not None:
            self._muted = mute
            return True
        return False

    # =========================================================================
    # Input Control
    # =========================================================================

    async def set_input(self, input_id: str) -> bool:
        """Switch to input (HDMI_1, HDMI_2, etc.)."""
        return await self._send_command("set_input", {"inputId": input_id}) is not None

    async def list_inputs(self) -> dict[str, str]:
        """Get available inputs."""
        return self._inputs.copy()

    # =========================================================================
    # App Control
    # =========================================================================

    async def launch_app(self, app_id: str, params: dict[str, Any] | None = None) -> bool:
        """Launch an app."""
        payload: dict[str, Any] = {"id": app_id}
        if params:
            payload["params"] = params
        return await self._send_command("launch_app", payload) is not None

    async def list_apps(self) -> dict[str, str]:
        """Get installed apps."""
        return self._apps.copy()

    async def launch_netflix(self) -> bool:
        """Launch Netflix."""
        return await self.launch_app("netflix")

    async def launch_youtube(self) -> bool:
        """Launch YouTube."""
        return await self.launch_app("youtube.leanback.v4")

    async def launch_prime_video(self) -> bool:
        """Launch Prime Video."""
        return await self.launch_app("amazon")

    async def launch_disney_plus(self) -> bool:
        """Launch Disney+."""
        return await self.launch_app("com.disney.disneyplus-prod")

    async def launch_plex(self) -> bool:
        """Launch Plex."""
        return await self.launch_app("cdp-30")

    # =========================================================================
    # Media Control
    # =========================================================================

    async def play(self) -> bool:
        """Play media."""
        return await self._send_command("play") is not None

    async def pause(self) -> bool:
        """Pause media."""
        return await self._send_command("pause") is not None

    async def stop(self) -> bool:
        """Stop media."""
        return await self._send_command("stop") is not None

    # =========================================================================
    # Notifications
    # =========================================================================

    async def show_notification(self, message: str) -> bool:
        """Show toast notification on TV."""
        return await self._send_command("notification", {"message": message}) is not None

    # =========================================================================
    # State
    # =========================================================================

    def get_state(self) -> dict[str, Any]:
        """Get current TV state."""
        return {
            "power": self._power_on,
            "volume": self._volume,
            "muted": self._muted,
            "current_app": self._current_app,
            "current_input": self._current_input,
        }

    def is_on(self) -> bool:
        """Check if TV is on."""
        return self._power_on

    async def disconnect(self) -> None:
        """Disconnect from TV."""
        self._initialized = False
        self._auto_reconnect = False  # Disable auto-reconnect on explicit disconnect

        # Cancel reconnect task
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None

        # Cancel receive task
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
            self._recv_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._session:
            await self._session.close()
            self._session = None

        logger.debug("LG TV: Disconnected")

    def enable_auto_reconnect(self, enabled: bool = True) -> None:
        """Enable or disable automatic reconnection."""
        self._auto_reconnect = enabled
