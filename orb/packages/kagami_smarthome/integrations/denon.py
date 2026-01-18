"""Denon AVR Home Theater Integration.

Direct control via Denon's telnet protocol.

Provides:
- Power control (Main, Zone2, Zone3)
- Volume control (-80dB to 0dB)
- Input source selection
- Sound mode control
- Mute control

Architecture:
- AVR-A10H at 192.168.1.12
- Telnet API on port 23 (primary control)
- Web interface on port 11080 (info only)
- HEOS API on port 1255 (streaming)

NOTE: Multi-room audio is handled by Control4 Triad AMS matrix.
The Denon is the home theater receiver for surround sound in the Living Room.

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar

from kagami_smarthome.core.integration_base import HealthStatus, IntegrationBase
from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)

# Denon AVR command reference (telnet protocol)
# Query commands end with ?
# Volume: MV00-98 (0=-80dB, 98=+18dB), MVUP, MVDOWN, MV?
# Mute: MUON, MUOFF, MU?
# Power: PWON, PWSTANDBY, PW? (Main), Z2ON, Z2OFF, Z3ON, Z3OFF
# Source: SICD, SIBD, SIGAME, SI?, etc.
# Sound mode: MSAUTO, MSMOVIE, MSMUSIC, MSGAME, MSPURE, MS?

TELNET_PORT = 23


class DenonIntegration(IntegrationBase):
    """Denon AVR home theater control via telnet protocol.

    Uses direct TCP connection for reliable, low-latency control.
    No external library dependencies.

    Keep-Alive:
        The telnet connection includes an automatic keep-alive mechanism
        that sends a status query every 60 seconds to prevent the receiver
        from closing the connection due to inactivity.
    """

    # IntegrationBase class variables
    integration_name: ClassVar[str] = "Denon"
    credential_keys: ClassVar[list[tuple[str, str]]] = [
        ("denon_host", "host"),
    ]

    KEEPALIVE_INTERVAL = 60.0  # Seconds between keep-alive queries
    CONNECTION_TIMEOUT = 300.0  # Max idle time before reconnecting

    def __init__(self, config: SmartHomeConfig):
        super().__init__(config)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._keepalive_task: asyncio.Task | None = None
        self._last_activity: float = 0.0

        # Cached state
        self._power: str = "OFF"
        self._volume: float = -80.0
        self._muted: bool = False
        self._source: str = ""
        self._sound_mode: str = ""
        self._zones: dict[str, dict[str, Any]] = {
            "Main": {"power": "OFF", "volume": -80.0, "source": ""},
            "Zone2": {"power": "OFF", "volume": -80.0, "source": ""},
            "Zone3": {"power": "OFF", "volume": -80.0, "source": ""},
        }

        # Input mapping (Denon codes to friendly names)
        self._input_map = {
            "CD": "Control4",  # HDMI 1
            "BD": "Steam Deck",  # HDMI 2
            "GAME": "Apple TV",  # HDMI 3
            "CBL/SAT": "Xbox",  # HDMI 4
            "DVD": "Control4 OSD",  # HDMI 5
            "MPLAY": "Mac",  # HDMI 6
            "AUX2": "AUX2",  # HDMI 7
            "TV": "TV Audio",  # Optical 1
            "TUNER": "Tuner",
            "BT": "Bluetooth",
            "NET": "Network",
            "USB": "USB",
        }
        self._reverse_input_map = {v: k for k, v in self._input_map.items()}

    @property
    def is_connected(self) -> bool:
        """Check if connected to Denon AVR."""
        return self._connected and self._writer is not None

    async def connect(self, max_retries: int = 3) -> bool:
        """Connect to Denon AVR via telnet with retry logic.

        Args:
            max_retries: Number of connection attempts before giving up.
        """
        # Load credentials from keychain using base class method
        await self.load_credentials()

        if not self.config.denon_host:
            logger.warning("Denon: host not configured")
            self._record_failure("host not configured")
            return False

        self._last_connect_attempt = time.time()
        backoff = 2.0  # Start with 2 second backoff

        for attempt in range(max_retries):
            try:
                # Open telnet connection with generous timeout
                # (network may be congested during parallel init)
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.config.denon_host, TELNET_PORT),
                    timeout=20,
                )

                # Query initial status
                await self._update_status()

                self._connected = True
                self._initialized = True
                self._last_activity = time.monotonic()
                self._record_success()

                # Start keep-alive task
                await self._start_keepalive()

                logger.info(
                    f"Denon: {self.config.denon_host} | "
                    f"Power: {self._power} | Volume: {self._volume}dB | Source: {self._source}"
                )
                return True

            except TimeoutError:
                self._record_failure(f"Connection timeout (attempt {attempt + 1})")
                logger.warning(f"Denon: Connection timeout (attempt {attempt + 1}/{max_retries})")
            except ConnectionRefusedError:
                self._record_failure(f"Connection refused (attempt {attempt + 1})")
                logger.warning(f"Denon: Connection refused (attempt {attempt + 1}/{max_retries})")
            except OSError as e:
                self._record_failure(f"Network error: {e}")
                logger.warning(f"Denon: Network error - {e} (attempt {attempt + 1}/{max_retries})")
            except Exception as e:
                self._record_failure(f"Connection failed: {e}")
                logger.error(f"Denon: Connection failed - {e}")
                return False  # Don't retry on unknown errors

            # Wait before retrying (except on last attempt)
            if attempt < max_retries - 1:
                logger.debug(f"Denon: Waiting {backoff}s before retry...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)  # Max 30 second backoff

        logger.error(f"Denon: Failed to connect after {max_retries} attempts")
        return False

    async def _send_command(self, command: str, expect_response: bool = False) -> str | None:
        """Send command via telnet and optionally read response."""
        if not self._writer or not self._reader:
            return None

        async with self._lock:
            try:
                # Send command with carriage return
                self._writer.write(f"{command}\r".encode())
                await self._writer.drain()

                if expect_response:
                    # Read response (ends with CR)
                    await asyncio.sleep(0.1)  # Brief delay for response
                    response = ""
                    try:
                        # Read available data
                        data = await asyncio.wait_for(
                            self._reader.read(1024),
                            timeout=1.0,
                        )
                        response = data.decode().strip()
                    except TimeoutError:
                        pass
                    return response

                return ""

            except Exception as e:
                logger.debug(f"Denon: Command error: {e}")
                return None

    async def _query(self, command: str) -> str:
        """Send query command and get response."""
        response = await self._send_command(command, expect_response=True)
        self._last_activity = time.monotonic()
        return response or ""

    # =========================================================================
    # Keep-Alive Mechanism
    # =========================================================================

    async def _start_keepalive(self) -> None:
        """Start the keep-alive background task."""
        # Cancel any existing task
        await self._stop_keepalive()

        self._keepalive_task = asyncio.create_task(self._keepalive_loop(), name="denon_keepalive")
        logger.debug("Denon: Keep-alive started")

    async def _stop_keepalive(self) -> None:
        """Stop the keep-alive background task."""
        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            self._keepalive_task = None

    async def _keepalive_loop(self) -> None:
        """Background loop that sends periodic keep-alive queries.

        Sends a power status query every KEEPALIVE_INTERVAL seconds
        to prevent the receiver from closing the connection due to inactivity.

        If the connection appears dead (no response), triggers a reconnect.
        """
        while self._connected:
            try:
                await asyncio.sleep(self.KEEPALIVE_INTERVAL)

                if not self._connected:
                    break

                # Check if we've had activity recently
                idle_time = time.monotonic() - self._last_activity

                if idle_time >= self.KEEPALIVE_INTERVAL:
                    # Send keep-alive query (power status is lightweight)
                    response = await self._query("PW?")

                    if response:
                        logger.debug(f"Denon: Keep-alive OK (idle {idle_time:.0f}s)")
                    else:
                        # No response - connection may be dead
                        logger.warning("Denon: Keep-alive failed, reconnecting...")
                        await self._reconnect()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Denon: Keep-alive error: {e}")
                # Try to reconnect on any error
                await self._reconnect()

    async def _reconnect(self) -> bool:
        """Attempt to reconnect to the Denon AVR.

        Returns:
            True if reconnection successful
        """
        # Close existing connection
        self._connected = False
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

        # Try to reconnect
        logger.info("Denon: Attempting reconnection...")
        return await self.connect(max_retries=2)

    async def _update_status(self) -> bool:
        """Update receiver status via telnet queries."""
        try:
            # Query power
            response = await self._query("PW?")
            if "PWON" in response:
                self._power = "ON"
            elif "PWSTANDBY" in response:
                self._power = "STANDBY"
            else:
                self._power = "OFF"

            # Query volume
            response = await self._query("MV?")
            if response:
                # Parse MV50 or MV505 format
                for line in response.split("\r"):
                    if line.startswith("MV") and not line.startswith("MVMAX"):
                        vol_str = line[2:].strip()
                        if vol_str.isdigit():
                            vol = int(vol_str)
                            # Convert Denon scale to dB
                            if len(vol_str) == 3:
                                vol = vol / 10  # e.g., 505 -> 50.5
                            self._volume = vol - 80  # Denon 0=-80dB, 80=0dB
                            break

            # Query mute
            response = await self._query("MU?")
            self._muted = "MUON" in response

            # Query source
            response = await self._query("SI?")
            if response:
                for line in response.split("\r"):
                    if line.startswith("SI"):
                        source_code = line[2:].strip()
                        self._source = self._input_map.get(source_code, source_code)
                        break

            # Query sound mode
            response = await self._query("MS?")
            if response:
                for line in response.split("\r"):
                    if line.startswith("MS"):
                        self._sound_mode = line[2:].strip()
                        break

            # Update Main zone cache
            self._zones["Main"] = {
                "power": self._power,
                "volume": self._volume,
                "source": self._source,
                "muted": self._muted,
                "sound_mode": self._sound_mode,
            }

            return True

        except Exception as e:
            logger.debug(f"Denon: Status update error: {e}")
            return False

    async def health_check(self) -> HealthStatus:
        """Perform a health check on the Denon integration.

        Sends a power query command to verify the connection is alive
        and measures round-trip latency.

        Returns:
            HealthStatus with current health information
        """
        if not self._initialized:
            return HealthStatus.unknown("Denon not initialized")

        if not self.is_connected:
            return HealthStatus.unhealthy(
                "Denon not connected",
                reachable=False,
                consecutive_failures=self._consecutive_failures,
                host=self.config.denon_host,
            )

        # Measure latency with a power status query
        start_time = time.monotonic()
        try:
            response = await self._query("PW?")
            latency_ms = (time.monotonic() - start_time) * 1000

            if response:
                self._record_success()
                return HealthStatus.healthy(
                    f"Denon connected | Power: {self._power}",
                    latency_ms=latency_ms,
                    host=self.config.denon_host,
                    power=self._power,
                    source=self._source,
                    volume_db=self._volume,
                )
            else:
                self._record_failure("No response to health check query")
                return HealthStatus.degraded(
                    "Denon connected but not responding to queries",
                    latency_ms=latency_ms,
                    host=self.config.denon_host,
                    consecutive_failures=self._consecutive_failures,
                )

        except Exception as e:
            self._record_failure(str(e))
            return HealthStatus.unhealthy(
                f"Health check failed: {e}",
                reachable=False,
                consecutive_failures=self._consecutive_failures,
                host=self.config.denon_host,
            )

    # =========================================================================
    # Power Control
    # =========================================================================

    async def power_on(self, zone: str = "Main") -> bool:
        """Power on zone."""
        if zone == "Main":
            result = await self._send_command("PWON")
        elif zone == "Zone2":
            result = await self._send_command("Z2ON")
        elif zone == "Zone3":
            result = await self._send_command("Z3ON")
        else:
            return False

        if result is not None:
            self._zones[zone]["power"] = "ON"
            if zone == "Main":
                self._power = "ON"
            return True
        return False

    async def power_off(self, zone: str = "Main") -> bool:
        """Power off zone (standby)."""
        if zone == "Main":
            result = await self._send_command("PWSTANDBY")
        elif zone == "Zone2":
            result = await self._send_command("Z2OFF")
        elif zone == "Zone3":
            result = await self._send_command("Z3OFF")
        else:
            return False

        if result is not None:
            self._zones[zone]["power"] = "OFF"
            if zone == "Main":
                self._power = "STANDBY"
            return True
        return False

    # =========================================================================
    # Volume Control
    # =========================================================================

    async def set_volume(self, level: int, zone: str = "Main") -> bool:
        """Set volume (0-100 scale).

        Maps 0-100 to Denon's 0-98 scale (which is -80dB to +18dB).
        """
        # Map 0-100 to Denon 0-80 range (comfortable listening)
        denon_level = int(level * 0.8)
        denon_level = max(0, min(80, denon_level))

        if zone == "Main":
            cmd = f"MV{denon_level:02d}"
        elif zone == "Zone2":
            cmd = f"Z2{denon_level:02d}"
        elif zone == "Zone3":
            cmd = f"Z3{denon_level:02d}"
        else:
            return False

        result = await self._send_command(cmd)
        if result is not None:
            self._zones[zone]["volume"] = denon_level - 80
            if zone == "Main":
                self._volume = denon_level - 80
            return True
        return False

    async def set_volume_db(self, db: float, zone: str = "Main") -> bool:
        """Set volume in dB (-80 to +18)."""
        denon_level = int(db + 80)
        denon_level = max(0, min(98, denon_level))

        if zone == "Main":
            cmd = f"MV{denon_level:02d}"
        elif zone == "Zone2":
            cmd = f"Z2{denon_level:02d}"
        elif zone == "Zone3":
            cmd = f"Z3{denon_level:02d}"
        else:
            return False

        result = await self._send_command(cmd)
        if result is not None:
            self._zones[zone]["volume"] = db
            if zone == "Main":
                self._volume = db
            return True
        return False

    async def volume_up(self, zone: str = "Main") -> bool:
        """Increase volume."""
        if zone == "Main":
            return await self._send_command("MVUP") is not None
        elif zone == "Zone2":
            return await self._send_command("Z2UP") is not None
        elif zone == "Zone3":
            return await self._send_command("Z3UP") is not None
        return False

    async def volume_down(self, zone: str = "Main") -> bool:
        """Decrease volume."""
        if zone == "Main":
            return await self._send_command("MVDOWN") is not None
        elif zone == "Zone2":
            return await self._send_command("Z2DOWN") is not None
        elif zone == "Zone3":
            return await self._send_command("Z3DOWN") is not None
        return False

    async def mute(self, mute: bool = True, zone: str = "Main") -> bool:
        """Mute/unmute."""
        cmd = "MUON" if mute else "MUOFF"
        result = await self._send_command(cmd)
        if result is not None:
            self._muted = mute
            return True
        return False

    # =========================================================================
    # Source Selection
    # =========================================================================

    async def set_source(self, source: str, zone: str = "Main") -> bool:
        """Set input source.

        Args:
            source: Friendly name (e.g., "Control4", "Apple TV") or Denon code
            zone: "Main", "Zone2", or "Zone3"
        """
        # Get Denon code
        denon_code = self._reverse_input_map.get(source, source)

        if zone == "Main":
            cmd = f"SI{denon_code}"
        elif zone == "Zone2":
            cmd = f"Z2{denon_code}"
        elif zone == "Zone3":
            cmd = f"Z3{denon_code}"
        else:
            return False

        result = await self._send_command(cmd)
        if result is not None:
            self._zones[zone]["source"] = source
            if zone == "Main":
                self._source = source
            return True
        return False

    # =========================================================================
    # Sound Mode
    # =========================================================================

    async def set_sound_mode(self, mode: str) -> bool:
        """Set surround sound mode.

        Args:
            mode: "auto", "movie", "music", "game", "pure", "stereo", "direct"
        """
        mode_map = {
            "auto": "MSAUTO",
            "movie": "MSMOVIE",
            "music": "MSMUSIC",
            "game": "MSGAME",
            "pure": "MSPURE DIRECT",
            "direct": "MSDIRECT",
            "stereo": "MSSTEREO",
            "dolby": "MSDOLBY SURROUND",
            "neural": "MSNEURAL:X",
            "virtual": "MSVIRTUAL",
        }

        cmd = mode_map.get(mode.lower())
        if not cmd:
            # Try sending the mode directly
            cmd = f"MS{mode.upper()}"

        result = await self._send_command(cmd)
        if result is not None:
            self._sound_mode = mode
            return True
        return False

    # =========================================================================
    # State
    # =========================================================================

    def get_state(self) -> dict[str, Any]:
        """Get current receiver state."""
        return {
            "power": self._power,
            "volume": self._volume,
            "volume_percent": int((self._volume + 80) / 0.8),
            "muted": self._muted,
            "source": self._source,
            "sound_mode": self._sound_mode,
        }

    def get_zones(self) -> dict[str, dict[str, Any]]:
        """Get all zone states."""
        return self._zones.copy()

    def get_sources(self) -> dict[str, str]:
        """Get available input sources (code -> friendly name)."""
        return self._input_map.copy()

    async def refresh_status(self) -> bool:
        """Refresh current status from receiver."""
        return await self._update_status()

    async def disconnect(self) -> None:
        """Disconnect and cleanup."""
        self._connected = False

        # Stop keep-alive task
        await self._stop_keepalive()

        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception as e:
                logger.debug(f"Denon: Writer close error (non-fatal): {e}")
            self._writer = None
            self._reader = None

        logger.debug("Denon: Disconnected")


# =============================================================================
# HEOS REAL-TIME EVENTS (Dec 30, 2025)
# =============================================================================

HEOS_PORT = 1255

# Event types from HEOS API
HEOS_EVENTS = {
    "player_state_changed": "Player playback state changed",
    "player_now_playing_changed": "Now playing content changed",
    "player_now_playing_progress": "Playback progress update",
    "player_volume_changed": "Volume level changed",
    "player_playback_error": "Playback error occurred",
    "player_queue_changed": "Queue contents changed",
    "group_changed": "Group membership changed",
    "sources_changed": "Available sources changed",
    "speakers_changed": "Speaker configuration changed",
}

# Type for event callbacks: (event_type, data) -> None
HeosEventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class HeosEventHandler:
    """HEOS event handler for real-time Denon AVR notifications.

    Provides sub-second latency for state changes via HEOS CLI protocol.

    Usage:
        heos = HeosEventHandler(denon_integration)
        heos.on_event(callback)
        await heos.connect()

        # Events will fire your callback:
        # async def callback(event_type, data):
        #     print(f"HEOS event: {event_type} = {data}")

    Architecture:
        - Connects to HEOS CLI on port 1255
        - Registers for change events
        - Parses JSON event notifications
        - Dispatches to callbacks
        - Auto-reconnects on disconnect

    HEOS Event Types:
        - player_state_changed: Play/pause/stop
        - player_volume_changed: Volume up/down/mute
        - player_now_playing_changed: Track change
        - player_now_playing_progress: Playback position
        - group_changed: Speaker grouping

    Created: December 30, 2025
    """

    RECONNECT_DELAY = 5.0  # Seconds between reconnect attempts

    def __init__(self, integration: DenonIntegration):
        self._integration = integration
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._running = False
        self._listener_task: asyncio.Task | None = None
        self._callbacks: list[HeosEventCallback] = []
        self._player_id: int | None = None  # Primary player ID

        # Statistics
        self._stats = {
            "events_received": 0,
            "reconnects": 0,
            "last_event_time": 0.0,
        }

    def on_event(self, callback: HeosEventCallback) -> None:
        """Register callback for HEOS events."""
        self._callbacks.append(callback)

    def off_event(self, callback: HeosEventCallback) -> None:
        """Unregister event callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    @property
    def is_connected(self) -> bool:
        """Check if HEOS connection is active."""
        return self._writer is not None

    async def connect(self) -> bool:
        """Connect to HEOS CLI and register for events.

        Returns:
            True if connected and registered successfully
        """
        if not self._integration.config.denon_host:
            logger.warning("HEOS: No Denon host configured")
            return False

        try:
            host = self._integration.config.denon_host

            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(host, HEOS_PORT), timeout=10.0
            )

            logger.info(f"✅ HEOS: Connected to {host}:{HEOS_PORT}")

            # Register for change events
            await self._send_command("system/register_for_change_events?enable=on")

            # Get player ID
            await self._discover_player()

            # Start listener
            self._running = True
            self._listener_task = asyncio.create_task(
                self._listen_loop(), name="heos_event_listener"
            )

            return True

        except TimeoutError:
            logger.error("HEOS: Connection timeout")
            return False
        except ConnectionRefusedError:
            logger.error("HEOS: Connection refused (is HEOS enabled?)")
            return False
        except Exception as e:
            logger.error(f"HEOS: Connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from HEOS."""
        self._running = False

        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        # Unregister events
        if self._writer:
            try:
                await self._send_command("system/register_for_change_events?enable=off")
            except Exception:
                pass

            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

        self._writer = None
        self._reader = None
        logger.info("HEOS: Disconnected")

    async def _send_command(self, cmd: str) -> dict[str, Any] | None:
        """Send HEOS command and return response."""
        if not self._writer:
            return None

        try:
            # HEOS commands are sent as: heos://group/command?params\r\n
            full_cmd = f"heos://{cmd}\r\n"
            self._writer.write(full_cmd.encode())
            await self._writer.drain()

            # Read response (JSON terminated by \r\n)
            if self._reader:
                line = await asyncio.wait_for(self._reader.readline(), timeout=5.0)
                return self._parse_response(line.decode().strip())

        except Exception as e:
            logger.debug(f"HEOS: Command error: {e}")

        return None

    async def _discover_player(self) -> None:
        """Discover primary HEOS player."""
        response = await self._send_command("player/get_players")
        if response and "payload" in response:
            players = response.get("payload", [])
            if players:
                self._player_id = players[0].get("pid")
                logger.debug(f"HEOS: Primary player ID: {self._player_id}")

    def _parse_response(self, raw: str) -> dict[str, Any] | None:
        """Parse HEOS JSON response."""
        try:
            data = json.loads(raw)
            return data
        except json.JSONDecodeError:
            return None

    def _parse_message(self, msg_str: str) -> dict[str, Any]:
        """Parse HEOS message string (key=value&key=value format)."""
        result = {}
        if not msg_str:
            return result

        for pair in msg_str.split("&"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                # Try to parse numeric values
                try:
                    result[key] = int(value)
                except ValueError:
                    result[key] = value
            else:
                result[pair] = True

        return result

    async def _listen_loop(self) -> None:
        """Main HEOS event listener loop."""
        while self._running:
            try:
                if not self._reader:
                    # Reconnect
                    await asyncio.sleep(self.RECONNECT_DELAY)
                    self._stats["reconnects"] += 1
                    if not await self.connect():
                        continue

                # Read line (events are newline-terminated JSON)
                line = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=300.0,  # 5 min timeout
                )

                if not line:
                    # Connection closed
                    logger.warning("HEOS: Connection closed, will reconnect")
                    self._reader = None
                    self._writer = None
                    continue

                await self._handle_message(line.decode().strip())

            except TimeoutError:
                # Ping to keep connection alive
                await self._send_command("system/heart_beat")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"HEOS: Listen error: {e}")
                self._reader = None
                self._writer = None
                await asyncio.sleep(self.RECONNECT_DELAY)

    async def _handle_message(self, raw: str) -> None:
        """Handle incoming HEOS message."""
        data = self._parse_response(raw)
        if not data:
            return

        heos_data = data.get("heos", {})
        command = heos_data.get("command", "")
        message = heos_data.get("message", "")

        # Check if this is an event
        if "event/" in command:
            event_type = command.replace("event/", "")
            event_data = self._parse_message(message)

            self._stats["events_received"] += 1
            self._stats["last_event_time"] = asyncio.get_event_loop().time()

            logger.debug(f"HEOS event: {event_type} = {event_data}")

            # Dispatch to callbacks
            for callback in self._callbacks:
                try:
                    await callback(event_type, event_data)
                except Exception as e:
                    logger.error(f"HEOS: Callback error: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get HEOS event statistics."""
        return {
            **self._stats,
            "connected": self.is_connected,
            "player_id": self._player_id,
            "callbacks": len(self._callbacks),
        }
