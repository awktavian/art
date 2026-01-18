"""Mitsubishi HVAC Integration via Kumo Cloud V3 API.

Integration for Mitsubishi mini-split HVAC systems using the new Comfort app
cloud API (V3). Direct HTTP implementation - no pykumo dependency.

Tim's System: 5 Mitsubishi mini-split zones at Veridian (Green Lake)

Features:
- Zone discovery via Kumo Cloud V3 API
- Real-time temperature monitoring
- Operating status (power, mode, setpoints)
- FULL CLOUD CONTROL via POST /v3/devices/send-command
- JWT token management with auto-refresh

Requirements:
- Kumo Cloud / Mitsubishi Comfort account credentials in Keychain
- PAC-USWHS002-WF-2 or similar WiFi adapter on each unit

Control API (discovered Dec 30, 2025):
  POST /v3/devices/send-command
  Payload: {"deviceSerial": "...", "commands": {"operationMode": "heat", "spHeat": 21}}

  Commands:
  - operationMode: "off", "heat", "cool", "auto", "dry", "vent"
  - spHeat: setpoint in Celsius (float)
  - spCool: setpoint in Celsius (float)
  - fanSpeed: "auto", "low", "medium", "high"
  - airDirection: "horizontal", "vertical", "swing"

Created: December 29, 2025
Updated: December 30, 2025 - FULL CLOUD CONTROL WORKING!
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import aiohttp

from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)

# Kumo Cloud V3 API endpoints
KUMO_API_BASE = "https://app-prod.kumocloud.com"
KUMO_LOGIN_URL = f"{KUMO_API_BASE}/v3/login"
KUMO_REFRESH_URL = f"{KUMO_API_BASE}/v3/refresh"
KUMO_SITES_URL = f"{KUMO_API_BASE}/v3/sites/"
KUMO_APP_VERSION = "3.0.9"

# Control endpoint (discovered Dec 30, 2025)
KUMO_COMMAND_URL = f"{KUMO_API_BASE}/v3/devices/send-command"


class HVACMode(str, Enum):
    """HVAC operating modes."""

    OFF = "off"
    HEAT = "heat"
    COOL = "cool"
    AUTO = "auto"  # Heat or cool as needed
    DRY = "dry"  # Dehumidify
    FAN = "vent"  # Fan only, no heating/cooling


class FanSpeed(str, Enum):
    """Fan speed settings."""

    AUTO = "auto"
    QUIET = "quiet"  # Lowest
    LOW = "low"
    MEDIUM = "medium"  # Labeled "powerful" on some units
    HIGH = "high"
    SUPER_HIGH = "superHigh"  # Maximum


class VaneDirection(str, Enum):
    """Vertical vane direction."""

    AUTO = "auto"
    SWING = "swing"
    HORIZONTAL = "horizontal"
    MID_HORIZONTAL = "midHorizontal"
    MID = "mid"
    MID_VERTICAL = "midVertical"
    VERTICAL = "vertical"


@dataclass
class HVACZoneStatus:
    """Current status of an HVAC zone."""

    power_on: bool
    mode: HVACMode
    current_temp: float  # Current room temperature (°F)
    target_temp: float  # Set point (°F)
    fan_speed: FanSpeed
    vane_direction: VaneDirection

    # Runtime info
    is_heating: bool = False
    is_cooling: bool = False
    is_defrosting: bool = False
    filter_dirty: bool = False
    standby: bool = False

    # Connection info
    online: bool = True
    wifi_rssi: int | None = None

    # Energy
    run_hours: float | None = None


@dataclass
class HVACZone:
    """An HVAC zone (individual mini-split unit)."""

    zone_id: str  # Kumo Cloud zone GUID
    name: str  # "Living Room", "Primary Bedroom", etc.
    serial: str  # Unit serial number (device serial)
    model: str  # Unit model

    # Current status
    status: HVACZoneStatus | None = None

    # Capabilities
    has_heat: bool = True
    has_cool: bool = True
    has_dry: bool = True
    auto_mode_enabled: bool = True
    min_temp: float = 60.0  # Minimum setpoint (°F)
    max_temp: float = 88.0  # Maximum setpoint (°F)

    # Room mapping (set by user)
    room_name: str | None = None

    def __repr__(self) -> str:
        if self.status and self.status.current_temp:
            temp = f"{self.status.current_temp:.0f}°F"
        else:
            temp = "offline"
        return f"HVACZone({self.name}, {temp})"


class MitsubishiIntegration:
    """Mitsubishi mini-split HVAC integration via Kumo Cloud V3 API.

    Uses direct HTTP requests to the Mitsubishi Comfort cloud API.
    This replaces the broken pykumo library.

    Usage:
        config = SmartHomeConfig(
            kumo_username="your@email.com",
            kumo_password="your_password",
        )
        hvac = MitsubishiIntegration(config)
        await hvac.connect()

        # List zones
        zones = hvac.get_zones()

        # Control
        await hvac.set_zone_temp("living_room", 72)
        await hvac.set_zone_mode("living_room", HVACMode.COOL)

        # Map zones to rooms
        hvac.map_zone_to_room("zone_guid", "Living Room")
    """

    def __init__(self, config: SmartHomeConfig):
        self.config = config

        # Load from keychain if not configured
        self._load_credentials_from_keychain()

        self._username = config.kumo_username or os.environ.get("KUMO_USERNAME")
        self._password = config.kumo_password or os.environ.get("KUMO_PASSWORD")

        # API state
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: float = 0  # Unix timestamp
        self._session: aiohttp.ClientSession | None = None

        # Site info
        self._site_id: str | None = None
        self._site_name: str | None = None

        # Zone registry
        self._zones: dict[str, HVACZone] = {}  # zone_id -> HVACZone
        self._serial_to_zone: dict[str, str] = {}  # serial -> zone_id
        self._connected = False

        # Room mapping: room_name -> zone_id
        self._room_to_zone: dict[str, str] = {}

        # Callbacks
        self._status_callbacks: list[Callable[[str, HVACZoneStatus], None]] = []

        # Polling
        self._poll_task: asyncio.Task | None = None
        self._poll_interval = 60.0  # seconds

    def _load_credentials_from_keychain(self) -> None:
        """Load Mitsubishi Kumo Cloud credentials from macOS Keychain."""
        try:
            from kagami_smarthome.secrets import load_integration_credentials

            load_integration_credentials(
                "Mitsubishi",
                self.config,
                [
                    ("kumo_username", "kumo_username"),
                    ("kumo_password", "kumo_password"),
                ],
            )
        except Exception as e:
            logger.debug(f"Mitsubishi: Could not load from Keychain: {e}")

    def _get_base_headers(self) -> dict[str, str]:
        """Get base headers for API requests."""
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-app-version": KUMO_APP_VERSION,
        }

    def _get_auth_headers(self) -> dict[str, str]:
        """Get headers with authorization."""
        headers = self._get_base_headers()
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    @property
    def is_connected(self) -> bool:
        """Check if connected to Kumo Cloud."""
        return self._connected

    @property
    def zones(self) -> list[HVACZone]:
        """Get all discovered zones."""
        return list(self._zones.values())

    @property
    def site_name(self) -> str | None:
        """Get the site name (e.g., 'Veridian')."""
        return self._site_name

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an active aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _login(self) -> bool:
        """Authenticate with Kumo Cloud V3 API."""
        session = await self._ensure_session()

        payload = {
            "username": self._username,
            "password": self._password,
            "appVersion": KUMO_APP_VERSION,
        }

        try:
            async with session.post(
                KUMO_LOGIN_URL,
                json=payload,
                headers=self._get_base_headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.error(f"Mitsubishi: Login failed ({resp.status}): {error}")
                    return False

                data = await resp.json()

                # Extract tokens
                token_data = data.get("token", {})
                self._access_token = token_data.get("access")
                self._refresh_token = token_data.get("refresh")

                # Token expires in ~20 minutes, refresh at 15
                self._token_expiry = time.time() + (15 * 60)

                user_name = f"{data.get('firstName', '')} {data.get('lastName', '')}".strip()
                logger.info(f"✅ Mitsubishi: Logged in as {user_name}")

                return True

        except Exception as e:
            logger.error(f"Mitsubishi: Login error - {e}")
            return False

    async def _refresh_tokens(self) -> bool:
        """Refresh access token using refresh token."""
        if not self._refresh_token:
            return await self._login()

        session = await self._ensure_session()

        headers = self._get_base_headers()
        headers["Authorization"] = f"Bearer {self._refresh_token}"

        try:
            async with session.post(
                KUMO_REFRESH_URL,
                json={"refresh": self._refresh_token},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    # Refresh token expired, do full login
                    logger.debug("Mitsubishi: Refresh token expired, re-authenticating")
                    return await self._login()

                data = await resp.json()
                self._access_token = data.get("access")
                self._refresh_token = data.get("refresh")
                self._token_expiry = time.time() + (15 * 60)

                logger.debug("Mitsubishi: Tokens refreshed")
                return True

        except Exception as e:
            logger.error(f"Mitsubishi: Token refresh error - {e}")
            return await self._login()

    async def _ensure_auth(self) -> bool:
        """Ensure we have valid authentication."""
        if not self._access_token or time.time() >= self._token_expiry:
            return await self._refresh_tokens()
        return True

    async def _api_get(self, url: str) -> dict | list | None:
        """Make authenticated GET request to Kumo API."""
        if not await self._ensure_auth():
            return None

        session = await self._ensure_session()

        try:
            async with session.get(
                url,
                headers=self._get_auth_headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 401:
                    # Token invalid, try refresh
                    if await self._refresh_tokens():
                        return await self._api_get(url)
                    return None

                if resp.status != 200:
                    logger.error(f"Mitsubishi: API GET {url} failed ({resp.status})")
                    return None

                return await resp.json()

        except Exception as e:
            logger.error(f"Mitsubishi: API GET error - {e}")
            return None

    async def _api_post(self, url: str, data: dict) -> dict | None:
        """Make authenticated POST request to Kumo API."""
        if not await self._ensure_auth():
            return None

        session = await self._ensure_session()

        try:
            async with session.post(
                url,
                json=data,
                headers=self._get_auth_headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 401:
                    if await self._refresh_tokens():
                        return await self._api_post(url, data)
                    return None

                if resp.status not in (200, 201, 204):
                    error = await resp.text()
                    logger.error(f"Mitsubishi: API POST failed ({resp.status}): {error}")
                    return None

                if resp.content_type == "application/json":
                    return await resp.json()
                return {}

        except Exception as e:
            logger.error(f"Mitsubishi: API POST error - {e}")
            return None

    async def _send_command(self, serial: str, commands: dict) -> bool:
        """Send control command to device via cloud API.

        Uses POST /v3/devices/send-command endpoint.
        Commands propagate to device within 30-60 seconds.

        Args:
            serial: Device serial number
            commands: Dict of commands (operationMode, spHeat, spCool, fanSpeed, etc.)

        Returns:
            True if command was accepted by cloud
        """
        payload = {
            "deviceSerial": serial,
            "commands": commands,
        }

        result = await self._api_post(KUMO_COMMAND_URL, payload)

        if result is not None:
            devices = result.get("devices", [])
            if serial in devices:
                logger.debug(f"Mitsubishi: Command sent to {serial}: {commands}")
                return True
            logger.warning("Mitsubishi: Command accepted but device not in response")
            return True  # Still successful

        return False

    async def connect(self) -> bool:
        """Connect to Kumo Cloud and discover zones.

        Returns True if connected successfully.
        """
        if not self._username or not self._password:
            logger.warning("Mitsubishi: No Kumo Cloud credentials configured")
            logger.info("Mitsubishi: Set kumo_username and kumo_password in Keychain")
            return False

        # Login
        if not await self._login():
            return False

        # Get sites
        sites = await self._api_get(KUMO_SITES_URL)
        if not sites:
            logger.error("Mitsubishi: No sites found")
            return False

        # Use first site (most users have one)
        site = sites[0] if isinstance(sites, list) else sites
        self._site_id = site.get("id")
        self._site_name = site.get("name", "Unknown")

        logger.info(f"Mitsubishi: Site '{self._site_name}'")

        # Get zones for this site
        zones_url = f"{KUMO_API_BASE}/v3/sites/{self._site_id}/zones"
        zones_data = await self._api_get(zones_url)

        if not zones_data:
            logger.warning("Mitsubishi: No zones found")
            return False

        # Build zone registry from zones data (includes adapter with status!)
        for zone_data in zones_data:
            zone_id = zone_data.get("id")
            zone_name = zone_data.get("name", "Unknown")

            adapter = zone_data.get("adapter", {})
            device_serial = adapter.get("deviceSerial", "")

            zone = HVACZone(
                zone_id=zone_id,
                name=zone_name,
                serial=device_serial,
                model="",
            )

            # Parse status directly from adapter in zones response
            zone.status = self._parse_adapter_status(adapter)

            self._zones[zone_id] = zone
            if device_serial:
                self._serial_to_zone[device_serial] = zone_id

        self._connected = True

        logger.info(f"✅ Mitsubishi: {len(self._zones)} HVAC zones discovered")
        for zone in self._zones.values():
            status = "online" if zone.status and zone.status.online else "offline"
            temp = (
                f"{zone.status.current_temp:.0f}°F"
                if zone.status and zone.status.current_temp
                else "N/A"
            )
            logger.info(f"  - {zone.name}: {temp} ({status})")

        return True

    async def disconnect(self) -> None:
        """Disconnect from Kumo Cloud."""
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

        self._connected = False
        self._zones.clear()
        self._access_token = None
        self._refresh_token = None
        logger.debug("Mitsubishi: Disconnected")

    async def _refresh_zone_status(self, zone: HVACZone) -> bool:
        """Refresh status for a single zone from cloud API.

        Uses /v3/zones/{zone_id} endpoint which contains adapter data
        with operational status (roomTemp, power, operationMode, etc.)
        """
        if not zone.zone_id:
            return False

        # Get zone data (includes adapter with operational status)
        zone_url = f"{KUMO_API_BASE}/v3/zones/{zone.zone_id}"
        zone_data = await self._api_get(zone_url)

        if not zone_data:
            zone.status = HVACZoneStatus(
                power_on=False,
                mode=HVACMode.OFF,
                current_temp=0,
                target_temp=72,
                fan_speed=FanSpeed.AUTO,
                vane_direction=VaneDirection.AUTO,
                online=False,
            )
            return False

        # Parse adapter data (this is where the real status lives!)
        adapter = zone_data.get("adapter", {})
        zone.status = self._parse_adapter_status(adapter)

        # Update zone name if changed
        if zone_data.get("name"):
            zone.name = zone_data.get("name")

        return True

    def _parse_adapter_status(self, adapter: dict) -> HVACZoneStatus:
        """Parse status from adapter object in /v3/zones/{id} response.

        The adapter object contains the real operational data:
        - roomTemp: Current temperature (Celsius)
        - spCool/spHeat: Setpoints (Celsius)
        - power: 0/1
        - operationMode: "heat", "cool", "auto", "autoHeat", "autoCool", "dry", "vent"
        - connected: true/false
        """
        # Temperature (API returns Celsius)
        room_temp_c = adapter.get("roomTemp")
        sp_cool_c = adapter.get("spCool")
        sp_heat_c = adapter.get("spHeat")

        # Convert to Fahrenheit
        current_temp = (room_temp_c * 9 / 5 + 32) if room_temp_c is not None else 0

        # Determine target temp based on mode
        op_mode = adapter.get("operationMode", "off")
        if "cool" in str(op_mode).lower() and sp_cool_c is not None:
            target_temp = sp_cool_c * 9 / 5 + 32
        elif sp_heat_c is not None:
            target_temp = sp_heat_c * 9 / 5 + 32
        elif sp_cool_c is not None:
            target_temp = sp_cool_c * 9 / 5 + 32
        else:
            target_temp = 72.0

        # Parse power and mode
        power = adapter.get("power")
        power_on = power == 1 or power == "on" or power is True

        mode = HVACMode.OFF
        if power_on:
            # Map operationMode values
            mode_map = {
                "heat": HVACMode.HEAT,
                "cool": HVACMode.COOL,
                "auto": HVACMode.AUTO,
                "autoheat": HVACMode.AUTO,  # Auto currently heating
                "autocool": HVACMode.AUTO,  # Auto currently cooling
                "dry": HVACMode.DRY,
                "vent": HVACMode.FAN,
                "fan": HVACMode.FAN,
            }
            mode = mode_map.get(str(op_mode).lower(), HVACMode.AUTO)

        # Parse fan speed (may not be in adapter, use default)
        fan_str = adapter.get("fanSpeed", "auto")
        fan_map = {
            "auto": FanSpeed.AUTO,
            "quiet": FanSpeed.QUIET,
            "low": FanSpeed.LOW,
            "medium": FanSpeed.MEDIUM,
            "powerful": FanSpeed.MEDIUM,
            "high": FanSpeed.HIGH,
            "superHigh": FanSpeed.SUPER_HIGH,
        }
        fan_speed = fan_map.get(str(fan_str).lower(), FanSpeed.AUTO)

        # Parse vane direction
        vane_str = adapter.get("vaneDir", "auto")
        vane_map = {
            "auto": VaneDirection.AUTO,
            "swing": VaneDirection.SWING,
            "horizontal": VaneDirection.HORIZONTAL,
            "midHorizontal": VaneDirection.MID_HORIZONTAL,
            "mid": VaneDirection.MID,
            "midVertical": VaneDirection.MID_VERTICAL,
            "vertical": VaneDirection.VERTICAL,
        }
        vane_direction = vane_map.get(str(vane_str), VaneDirection.AUTO)

        # Connection status
        connected = adapter.get("connected", False)
        online = connected and room_temp_c is not None

        # Check if heating or cooling
        is_heating = "heat" in str(op_mode).lower() and power_on
        is_cooling = "cool" in str(op_mode).lower() and power_on

        return HVACZoneStatus(
            power_on=power_on,
            mode=mode,
            current_temp=current_temp,
            target_temp=target_temp,
            fan_speed=fan_speed,
            vane_direction=vane_direction,
            is_heating=is_heating,
            is_cooling=is_cooling,
            online=online,
        )

    # =========================================================================
    # Zone Mapping
    # =========================================================================

    def map_zone_to_room(self, zone_id: str, room_name: str) -> bool:
        """Map a zone to a room name."""
        if zone_id not in self._zones:
            logger.warning(f"Mitsubishi: Zone '{zone_id}' not found")
            return False

        self._zones[zone_id].room_name = room_name
        self._room_to_zone[room_name.lower()] = zone_id
        logger.debug(f"Mitsubishi: Mapped zone '{zone_id}' to room '{room_name}'")
        return True

    def get_zone_for_room(self, room_name: str) -> HVACZone | None:
        """Get HVAC zone for a room."""
        zone_id = self._room_to_zone.get(room_name.lower())
        if zone_id:
            return self._zones.get(zone_id)

        # Try fuzzy match on zone names
        for zone in self._zones.values():
            if room_name.lower() in zone.name.lower():
                return zone

        return None

    # =========================================================================
    # Zone Getters
    # =========================================================================

    def get_zones(self) -> list[HVACZone]:
        """Get all zones."""
        return list(self._zones.values())

    def get_zone(self, zone_id: str) -> HVACZone | None:
        """Get zone by ID."""
        return self._zones.get(zone_id)

    def get_zone_by_name(self, name: str) -> HVACZone | None:
        """Get zone by name (case-insensitive)."""
        for zone in self._zones.values():
            if zone.name.lower() == name.lower():
                return zone
        return None

    def get_zone_by_serial(self, serial: str) -> HVACZone | None:
        """Get zone by device serial."""
        zone_id = self._serial_to_zone.get(serial)
        return self._zones.get(zone_id) if zone_id else None

    # =========================================================================
    # Zone Control (Cloud API)
    # =========================================================================

    async def refresh_zone(self, zone_id: str) -> HVACZoneStatus | None:
        """Refresh status for a single zone."""
        zone = self._zones.get(zone_id)
        if not zone:
            return None

        await self._refresh_zone_status(zone)
        return zone.status

    async def refresh_all(self) -> None:
        """Refresh status for all zones in parallel."""
        if self._zones:
            await asyncio.gather(
                *[self._refresh_zone_status(zone) for zone in self._zones.values()],
                return_exceptions=True,
            )

    async def set_zone_temp(self, zone_id: str, temp_f: float) -> bool:
        """Set zone temperature setpoint via cloud API.

        Args:
            zone_id: Zone ID, serial, or room name
            temp_f: Target temperature in Fahrenheit

        Returns:
            True if command was sent (propagates in 30-60s)
        """
        # Find zone
        zone = (
            self.get_zone(zone_id)
            or self.get_zone_by_serial(zone_id)
            or self.get_zone_for_room(zone_id)
        )
        if not zone:
            logger.warning(f"Mitsubishi: Zone '{zone_id}' not found")
            return False

        # Validate range
        if not zone.min_temp <= temp_f <= zone.max_temp:
            logger.warning(f"Mitsubishi: Temp {temp_f}°F outside range")
            return False

        # Convert to Celsius (API uses Celsius)
        temp_c = round((temp_f - 32) * 5 / 9, 1)

        # Get current setpoints to preserve them
        current_sp_heat = None
        if zone.status:
            # Convert back to C if we have F values
            if zone.status.target_temp:
                current_sp_heat = round((zone.status.target_temp - 32) * 5 / 9, 1)

        # Build commands based on mode
        mode = zone.status.mode if zone.status else HVACMode.AUTO

        commands = {}
        if mode == HVACMode.COOL:
            commands["spCool"] = temp_c
            if current_sp_heat is not None:
                commands["spHeat"] = current_sp_heat
        elif mode == HVACMode.HEAT:
            commands["spHeat"] = temp_c
            # Keep current cool setpoint
            commands["spCool"] = 24  # Default reasonable value
        else:
            # For auto, set both
            commands["spHeat"] = temp_c
            commands["spCool"] = temp_c + 2  # Small hysteresis

        success = await self._send_command(zone.serial, commands)

        if success:
            logger.info(f"Mitsubishi: Set {zone.name} to {temp_f:.0f}°F (command sent)")
            if zone.status:
                zone.status.target_temp = temp_f

        return success

    async def set_zone_mode(self, zone_id: str, mode: HVACMode) -> bool:
        """Set zone operating mode via cloud API.

        Args:
            zone_id: Zone ID, serial, or room name
            mode: Target mode (OFF, HEAT, COOL, AUTO, DRY, FAN)

        Returns:
            True if command was sent
        """
        zone = (
            self.get_zone(zone_id)
            or self.get_zone_by_serial(zone_id)
            or self.get_zone_for_room(zone_id)
        )
        if not zone:
            logger.warning(f"Mitsubishi: Zone '{zone_id}' not found")
            return False

        # Build command
        if mode == HVACMode.OFF:
            commands = {"operationMode": "off"}
        else:
            commands = {"operationMode": mode.value}

            # Include current setpoints to maintain them
            if zone.status:
                # Get setpoints in Celsius
                if zone.status.target_temp:
                    sp_c = round((zone.status.target_temp - 32) * 5 / 9, 1)
                    commands["spHeat"] = sp_c
                    commands["spCool"] = sp_c + 2

        success = await self._send_command(zone.serial, commands)

        if success:
            logger.info(f"Mitsubishi: Set {zone.name} mode to {mode.value}")
            if zone.status:
                zone.status.mode = mode
                zone.status.power_on = mode != HVACMode.OFF

        return success

    async def set_zone_fan(self, zone_id: str, speed: FanSpeed) -> bool:
        """Set zone fan speed via cloud API."""
        zone = (
            self.get_zone(zone_id)
            or self.get_zone_by_serial(zone_id)
            or self.get_zone_for_room(zone_id)
        )
        if not zone:
            return False

        success = await self._send_command(zone.serial, {"fanSpeed": speed.value})

        if success and zone.status:
            zone.status.fan_speed = speed
            logger.info(f"Mitsubishi: Set {zone.name} fan to {speed.value}")

        return success

    async def set_zone_vane(self, zone_id: str, direction: VaneDirection) -> bool:
        """Set zone vane direction via cloud API."""
        zone = (
            self.get_zone(zone_id)
            or self.get_zone_by_serial(zone_id)
            or self.get_zone_for_room(zone_id)
        )
        if not zone:
            return False

        success = await self._send_command(zone.serial, {"airDirection": direction.value})

        if success and zone.status:
            zone.status.vane_direction = direction
            logger.info(f"Mitsubishi: Set {zone.name} vane to {direction.value}")

        return success

    async def turn_on_zone(self, zone_id: str, mode: HVACMode = HVACMode.AUTO) -> bool:
        """Turn on a zone."""
        return await self.set_zone_mode(zone_id, mode)

    async def turn_off_zone(self, zone_id: str) -> bool:
        """Turn off a zone."""
        return await self.set_zone_mode(zone_id, HVACMode.OFF)

    # =========================================================================
    # Multi-Zone Operations
    # =========================================================================

    async def set_all_zones_temp(self, temp_f: float) -> bool:
        """Set temperature for all zones."""
        results = await asyncio.gather(
            *[self.set_zone_temp(z.zone_id, temp_f) for z in self._zones.values()]
        )
        return all(results)

    async def set_all_zones_mode(self, mode: HVACMode) -> bool:
        """Set mode for all zones."""
        results = await asyncio.gather(
            *[self.set_zone_mode(z.zone_id, mode) for z in self._zones.values()]
        )
        return all(results)

    async def turn_off_all(self) -> bool:
        """Turn off all zones (away/vacation mode)."""
        return await self.set_all_zones_mode(HVACMode.OFF)

    async def set_away_mode(self, setback_temp: float = 62.0) -> bool:
        """Enter away mode - all zones to setback temperature."""
        results = await asyncio.gather(
            *[self.set_zone_temp(z.zone_id, setback_temp) for z in self._zones.values()]
        )
        return all(results)

    # =========================================================================
    # Comfort Operations
    # =========================================================================

    async def boost_zone(self, zone_id: str, delta_f: float = 3.0) -> bool:
        """Temporarily boost a zone's temperature."""
        zone = self.get_zone(zone_id) or self.get_zone_for_room(zone_id)
        if not zone or not zone.status:
            return False

        new_temp = zone.status.target_temp + delta_f
        return await self.set_zone_temp(zone.zone_id, new_temp)

    async def cool_down_zone(self, zone_id: str, delta_f: float = 3.0) -> bool:
        """Temporarily cool down a zone."""
        zone = self.get_zone(zone_id) or self.get_zone_for_room(zone_id)
        if not zone or not zone.status:
            return False

        new_temp = zone.status.target_temp - delta_f
        return await self.set_zone_temp(zone.zone_id, new_temp)

    # =========================================================================
    # Status and Monitoring
    # =========================================================================

    def get_zone_status(self, zone_id: str) -> HVACZoneStatus | None:
        """Get cached status for a zone."""
        zone = self.get_zone(zone_id) or self.get_zone_for_room(zone_id)
        return zone.status if zone else None

    def get_all_temps(self) -> dict[str, tuple[float, float]]:
        """Get current and target temps for all zones."""
        temps = {}
        for zone in self._zones.values():
            if zone.status and zone.status.current_temp:
                temps[zone.name] = (zone.status.current_temp, zone.status.target_temp)
        return temps

    def get_average_temp(self) -> float:
        """Get average temperature across all online zones."""
        temps = []
        for zone in self._zones.values():
            if zone.status and zone.status.online and zone.status.current_temp:
                temps.append(zone.status.current_temp)
        return sum(temps) / len(temps) if temps else 72.0

    def get_online_zones(self) -> list[HVACZone]:
        """Get zones that are currently online."""
        return [z for z in self._zones.values() if z.status and z.status.online]

    def get_offline_zones(self) -> list[HVACZone]:
        """Get zones that are currently offline."""
        return [z for z in self._zones.values() if not z.status or not z.status.online]

    # =========================================================================
    # Event Handling
    # =========================================================================

    def on_status_change(self, callback: Callable[[str, HVACZoneStatus], None]) -> None:
        """Register callback for zone status changes."""
        self._status_callbacks.append(callback)

    async def start_polling(self, interval: float = 60.0) -> None:
        """Start background polling for status updates."""
        self._poll_interval = interval
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info(f"Mitsubishi: Started polling (every {interval}s)")

    async def stop_polling(self) -> None:
        """Stop background polling."""
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

    async def _poll_loop(self) -> None:
        """Background polling loop."""
        while True:
            try:
                for zone in self._zones.values():
                    old_status = zone.status
                    await self._refresh_zone_status(zone)
                    new_status = zone.status

                    # Check for changes and notify
                    if new_status and old_status:
                        if (
                            new_status.current_temp != old_status.current_temp
                            or new_status.target_temp != old_status.target_temp
                            or new_status.mode != old_status.mode
                            or new_status.online != old_status.online
                        ):
                            for callback in self._status_callbacks:
                                try:
                                    callback(zone.zone_id, new_status)
                                except Exception as e:
                                    logger.error(f"Mitsubishi: Callback error - {e}")

                await asyncio.sleep(self._poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Mitsubishi: Poll error - {e}")
                await asyncio.sleep(self._poll_interval)
