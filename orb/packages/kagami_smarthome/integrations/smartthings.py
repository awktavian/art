"""Samsung SmartThings Cloud Integration.

Cloud API integration for Samsung SmartThings-connected devices.
Supports Samsung appliances (fridges, ovens, washers, etc.) and third-party devices.

Features:
- Device discovery and control
- Samsung Family Hub refrigerator
- Samsung smart ovens and ranges
- Samsung washers and dryers
- Third-party SmartThings devices
- Real-time device status via subscriptions

Architecture:
- SmartThings Cloud REST API
- Personal Access Token (PAT) authentication
- Optional webhook for real-time events

Requirements:
- SmartThings account
- Personal Access Token from https://my.smartthings.com/advanced/tokens

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import aiohttp

from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)


# SmartThings API base URL
SMARTTHINGS_API = "https://api.smartthings.com/v1"


class SmartThingsCapability(str, Enum):
    """SmartThings device capabilities."""

    # Core
    SWITCH = "switch"
    SWITCH_LEVEL = "switchLevel"
    POWER_METER = "powerMeter"

    # Temperature
    TEMPERATURE_MEASUREMENT = "temperatureMeasurement"
    THERMOSTAT_COOLING_SETPOINT = "thermostatCoolingSetpoint"
    THERMOSTAT_HEATING_SETPOINT = "thermostatHeatingSetpoint"

    # Refrigerator
    REFRIGERATION = "refrigeration"
    CONTACT_SENSOR = "contactSensor"  # Door

    # Oven
    OVEN_MODE = "ovenMode"
    OVEN_SETPOINT = "ovenSetpoint"
    OVEN_OPERATING_STATE = "ovenOperatingState"

    # Washer/Dryer
    WASHER_MODE = "washerMode"
    WASHER_OPERATING_STATE = "washerOperatingState"
    DRYER_MODE = "dryerMode"
    DRYER_OPERATING_STATE = "dryerOperatingState"

    # Dishwasher
    DISHWASHER_MODE = "dishwasherMode"
    DISHWASHER_OPERATING_STATE = "dishwasherOperatingState"

    # Robot Vacuum
    ROBOT_CLEANER_MODE = "robotCleanerMode"
    ROBOT_CLEANER_MOVEMENT = "robotCleanerMovement"

    # TV
    TV_CHANNEL = "tvChannel"
    AUDIO_VOLUME = "audioVolume"
    MEDIA_PLAYBACK = "mediaPlayback"


class SmartThingsDeviceType(str, Enum):
    """SmartThings device categories."""

    REFRIGERATOR = "Refrigerator"
    OVEN = "Oven"
    RANGE = "Range"
    COOKTOP = "Cooktop"
    WASHER = "Washer"
    DRYER = "Dryer"
    DISHWASHER = "Dishwasher"
    TV = "Television"
    AIR_CONDITIONER = "AirConditioner"
    AIR_PURIFIER = "AirPurifier"
    ROBOT_VACUUM = "RobotCleaner"
    LIGHT = "Light"
    SWITCH = "Switch"
    THERMOSTAT = "Thermostat"
    OTHER = "Other"


@dataclass
class SmartThingsDevice:
    """SmartThings device representation."""

    device_id: str
    name: str
    label: str
    device_type: SmartThingsDeviceType
    manufacturer: str
    model: str
    capabilities: list[str]
    components: list[str]
    room: str | None
    status: dict[str, Any] = field(default_factory=dict)


@dataclass
class SmartThingsLocation:
    """SmartThings location (home)."""

    location_id: str
    name: str
    latitude: float | None
    longitude: float | None
    temperature_scale: str  # "F" or "C"


class SmartThingsIntegration:
    """Samsung SmartThings cloud integration.

    Provides control of Samsung and SmartThings-connected devices including:
    - Samsung Family Hub refrigerators
    - Samsung smart ovens and ranges
    - Samsung washers and dryers
    - Third-party SmartThings devices

    Usage:
        config = SmartHomeConfig(
            smartthings_token="your-personal-access-token",
        )
        st = SmartThingsIntegration(config)
        await st.connect()

        # List devices
        devices = st.get_devices()

        # Control
        await st.set_fridge_temp(device_id, 37)
        await st.preheat_oven(device_id, 375)
    """

    def __init__(self, config: SmartHomeConfig):
        self.config = config
        self._token = config.smartthings_token or os.environ.get("SMARTTHINGS_TOKEN")

        # Fall back to Keychain if not configured
        if not self._token:
            self._load_credentials_from_keychain()

        self._session: aiohttp.ClientSession | None = None
        self._connected = False

        self._locations: dict[str, SmartThingsLocation] = {}
        self._devices: dict[str, SmartThingsDevice] = {}

        # Device categories
        self._refrigerators: list[SmartThingsDevice] = []
        self._ovens: list[SmartThingsDevice] = []
        self._washers: list[SmartThingsDevice] = []
        self._dryers: list[SmartThingsDevice] = []
        self._tvs: list[SmartThingsDevice] = []

        # Callbacks
        self._event_callbacks: list[Callable[[dict], None]] = []

    def _load_credentials_from_keychain(self) -> None:
        """Load SmartThings token from macOS Keychain."""
        if self._token:
            return  # Already configured

        try:
            from kagami_smarthome.secrets import secrets

            token = secrets.get("smartthings_token")
            if token:
                self._token = token
                logger.debug("SmartThings: Loaded token from Keychain")
        except Exception as e:
            logger.debug(f"SmartThings: Could not load from Keychain: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if connected to SmartThings API."""
        return self._connected

    @property
    def devices(self) -> list[SmartThingsDevice]:
        """Get all discovered devices."""
        return list(self._devices.values())

    async def connect(self) -> bool:
        """Connect to SmartThings API and discover devices.

        Returns True if connected successfully.
        """
        if not self._token:
            logger.warning("SmartThings: No access token configured")
            logger.info("SmartThings: Get token from https://my.smartthings.com/advanced/tokens")
            return False

        try:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                }
            )

            # Test connection by getting locations
            locations = await self._get_locations()
            if not locations:
                logger.warning("SmartThings: Could not get locations (check token)")
                await self._session.close()
                self._session = None
                return False

            self._locations = {loc.location_id: loc for loc in locations}

            # Discover devices
            await self._discover_devices()

            self._connected = True

            if self._devices:
                logger.info(f"✅ SmartThings: {len(self._devices)} devices")
                for device in self._devices.values():
                    logger.debug(f"  - {device.device_type.value}: {device.label}")
            else:
                logger.info("SmartThings: Connected (no devices found)")

            return True

        except Exception as e:
            logger.error(f"SmartThings: Connection failed - {e}")
            if self._session:
                await self._session.close()
                self._session = None
            return False

    async def disconnect(self) -> None:
        """Disconnect from SmartThings API."""
        if self._session:
            await self._session.close()
            self._session = None

        self._connected = False
        self._devices.clear()
        self._locations.clear()
        logger.debug("SmartThings: Disconnected")

    async def _api_get(self, endpoint: str) -> dict | list | None:
        """Make GET request to SmartThings API."""
        if not self._session:
            return None

        url = f"{SMARTTHINGS_API}{endpoint}"

        try:
            async with self._session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 401:
                    logger.error("SmartThings: Invalid or expired token")
                else:
                    logger.warning(f"SmartThings: API error {resp.status} on {endpoint}")
                return None
        except Exception as e:
            logger.error(f"SmartThings: Request failed - {e}")
            return None

    async def _api_post(self, endpoint: str, data: dict) -> bool:
        """Make POST request to SmartThings API."""
        if not self._session:
            return False

        url = f"{SMARTTHINGS_API}{endpoint}"

        try:
            async with self._session.post(url, json=data) as resp:
                if resp.status in (200, 202):
                    return True
                else:
                    logger.warning(f"SmartThings: API error {resp.status} on {endpoint}")
                    return False
        except Exception as e:
            logger.error(f"SmartThings: Request failed - {e}")
            return False

    async def _get_locations(self) -> list[SmartThingsLocation]:
        """Get SmartThings locations (homes)."""
        data = await self._api_get("/locations")
        if not data or "items" not in data:
            return []

        locations = []
        for item in data["items"]:
            locations.append(
                SmartThingsLocation(
                    location_id=item.get("locationId", ""),
                    name=item.get("name", "Home"),
                    latitude=item.get("latitude"),
                    longitude=item.get("longitude"),
                    temperature_scale=item.get("temperatureScale", "F"),
                )
            )
        return locations

    async def _discover_devices(self) -> None:
        """Discover all SmartThings devices."""
        data = await self._api_get("/devices")
        if not data or "items" not in data:
            return

        for item in data["items"]:
            device_type = self._parse_device_type(item)

            device = SmartThingsDevice(
                device_id=item.get("deviceId", ""),
                name=item.get("name", "Unknown"),
                label=item.get("label", item.get("name", "Unknown")),
                device_type=device_type,
                manufacturer=item.get("manufacturerName", ""),
                model=item.get("model", ""),
                capabilities=[c.get("id", "") for c in item.get("capabilities", [])],
                components=[c.get("id", "") for c in item.get("components", [])],
                room=item.get("roomId"),
                status={},
            )

            self._devices[device.device_id] = device

            # Categorize by type
            if device_type == SmartThingsDeviceType.REFRIGERATOR:
                self._refrigerators.append(device)
            elif device_type in (SmartThingsDeviceType.OVEN, SmartThingsDeviceType.RANGE):
                self._ovens.append(device)
            elif device_type == SmartThingsDeviceType.WASHER:
                self._washers.append(device)
            elif device_type == SmartThingsDeviceType.DRYER:
                self._dryers.append(device)
            elif device_type == SmartThingsDeviceType.TV:
                self._tvs.append(device)

    def _parse_device_type(self, item: dict) -> SmartThingsDeviceType:
        """Parse device type from SmartThings device data."""
        # Check categories first
        categories = item.get("components", [{}])[0].get("categories", [])
        for cat in categories:
            cat_name = cat.get("name", "").lower()
            if "refrigerator" in cat_name:
                return SmartThingsDeviceType.REFRIGERATOR
            elif "oven" in cat_name:
                return SmartThingsDeviceType.OVEN
            elif "range" in cat_name:
                return SmartThingsDeviceType.RANGE
            elif "washer" in cat_name:
                return SmartThingsDeviceType.WASHER
            elif "dryer" in cat_name:
                return SmartThingsDeviceType.DRYER
            elif "dishwasher" in cat_name:
                return SmartThingsDeviceType.DISHWASHER
            elif "tv" in cat_name or "television" in cat_name:
                return SmartThingsDeviceType.TV
            elif "air conditioner" in cat_name:
                return SmartThingsDeviceType.AIR_CONDITIONER
            elif "air purifier" in cat_name:
                return SmartThingsDeviceType.AIR_PURIFIER
            elif "robot" in cat_name:
                return SmartThingsDeviceType.ROBOT_VACUUM
            elif "light" in cat_name:
                return SmartThingsDeviceType.LIGHT
            elif "switch" in cat_name:
                return SmartThingsDeviceType.SWITCH
            elif "thermostat" in cat_name:
                return SmartThingsDeviceType.THERMOSTAT

        # Check capabilities
        capabilities = [c.get("id", "") for c in item.get("capabilities", [])]
        if SmartThingsCapability.REFRIGERATION.value in capabilities:
            return SmartThingsDeviceType.REFRIGERATOR
        elif SmartThingsCapability.OVEN_MODE.value in capabilities:
            return SmartThingsDeviceType.OVEN
        elif SmartThingsCapability.WASHER_MODE.value in capabilities:
            return SmartThingsDeviceType.WASHER
        elif SmartThingsCapability.DRYER_MODE.value in capabilities:
            return SmartThingsDeviceType.DRYER
        elif SmartThingsCapability.TV_CHANNEL.value in capabilities:
            return SmartThingsDeviceType.TV

        return SmartThingsDeviceType.OTHER

    # =========================================================================
    # Device Getters
    # =========================================================================

    def get_devices(
        self, device_type: SmartThingsDeviceType | None = None
    ) -> list[SmartThingsDevice]:
        """Get devices, optionally filtered by type."""
        if device_type is None:
            return list(self._devices.values())
        return [d for d in self._devices.values() if d.device_type == device_type]

    def get_refrigerator(self, index: int = 0) -> SmartThingsDevice | None:
        """Get refrigerator device."""
        return self._refrigerators[index] if index < len(self._refrigerators) else None

    def get_oven(self, index: int = 0) -> SmartThingsDevice | None:
        """Get oven device."""
        return self._ovens[index] if index < len(self._ovens) else None

    def get_washer(self, index: int = 0) -> SmartThingsDevice | None:
        """Get washer device."""
        return self._washers[index] if index < len(self._washers) else None

    def get_dryer(self, index: int = 0) -> SmartThingsDevice | None:
        """Get dryer device."""
        return self._dryers[index] if index < len(self._dryers) else None

    # =========================================================================
    # Generic Command Interface
    # =========================================================================

    async def execute_command(
        self,
        device_id: str,
        capability: str,
        command: str,
        args: list[Any] | None = None,
        component: str = "main",
    ) -> bool:
        """Execute a command on a device.

        Args:
            device_id: Device ID
            capability: Capability name (e.g., "switch")
            command: Command name (e.g., "on")
            args: Command arguments
            component: Component ID (default "main")

        Returns:
            True if command executed successfully
        """
        data = {
            "commands": [
                {
                    "component": component,
                    "capability": capability,
                    "command": command,
                    "arguments": args or [],
                }
            ]
        }

        return await self._api_post(f"/devices/{device_id}/commands", data)

    async def get_device_status(self, device_id: str) -> dict[str, Any]:
        """Get full device status."""
        data = await self._api_get(f"/devices/{device_id}/status")
        return data if data else {}

    async def get_device_health(self, device_id: str) -> dict[str, Any]:
        """Get device health/online status."""
        data = await self._api_get(f"/devices/{device_id}/health")
        return data if data else {}

    # =========================================================================
    # Refrigerator Control
    # =========================================================================

    async def get_fridge_status(self, device_id: str) -> dict[str, Any]:
        """Get refrigerator status including temperatures and door states."""
        status = await self.get_device_status(device_id)

        result = {}
        components = status.get("components", {})
        main = components.get("main", {})

        # Temperature
        if "refrigeration" in main:
            result["fridge_temp"] = main["refrigeration"].get("fridgeTemperature", {}).get("value")
            result["freezer_temp"] = (
                main["refrigeration"].get("freezerTemperature", {}).get("value")
            )

        # Door sensors
        if "contactSensor" in main:
            result["door_open"] = main["contactSensor"].get("contact", {}).get("value") == "open"

        return result

    async def set_fridge_temp(self, device_id: str, temp_f: int) -> bool:
        """Set refrigerator temperature.

        Args:
            device_id: Device ID
            temp_f: Temperature in Fahrenheit (typically 33-46°F)

        Returns:
            True if successful
        """
        if not 33 <= temp_f <= 46:
            logger.warning(f"SmartThings: Fridge temp {temp_f}°F outside safe range")
            return False

        return await self.execute_command(
            device_id,
            "refrigeration",
            "setFridgeTemperature",
            [temp_f],
        )

    async def set_freezer_temp(self, device_id: str, temp_f: int) -> bool:
        """Set freezer temperature.

        Args:
            device_id: Device ID
            temp_f: Temperature in Fahrenheit (typically -6 to 8°F)

        Returns:
            True if successful
        """
        if not -6 <= temp_f <= 8:
            logger.warning(f"SmartThings: Freezer temp {temp_f}°F outside safe range")
            return False

        return await self.execute_command(
            device_id,
            "refrigeration",
            "setFreezerTemperature",
            [temp_f],
        )

    # =========================================================================
    # Oven Control
    # =========================================================================

    async def get_oven_status(self, device_id: str) -> dict[str, Any]:
        """Get oven status."""
        status = await self.get_device_status(device_id)

        result = {}
        components = status.get("components", {})
        main = components.get("main", {})

        if "ovenOperatingState" in main:
            state = main["ovenOperatingState"]
            result["machine_state"] = state.get("machineState", {}).get("value")
            result["job_state"] = state.get("ovenJobState", {}).get("value")
            result["completion_time"] = state.get("completionTime", {}).get("value")

        if "ovenSetpoint" in main:
            result["target_temp"] = main["ovenSetpoint"].get("ovenSetpoint", {}).get("value")

        if "ovenMode" in main:
            result["mode"] = main["ovenMode"].get("ovenMode", {}).get("value")

        return result

    async def preheat_oven(self, device_id: str, temp_f: int, mode: str = "bake") -> bool:
        """Preheat oven.

        Args:
            device_id: Device ID
            temp_f: Target temperature in Fahrenheit
            mode: Cooking mode (bake, convectionBake, roast, etc.)

        Returns:
            True if preheat started
        """
        if not 170 <= temp_f <= 550:
            logger.warning(f"SmartThings: Oven temp {temp_f}°F outside safe range")
            return False

        # Set mode
        mode_success = await self.execute_command(
            device_id,
            "ovenMode",
            "setOvenMode",
            [mode],
        )

        # Set temperature
        temp_success = await self.execute_command(
            device_id,
            "ovenSetpoint",
            "setOvenSetpoint",
            [temp_f],
        )

        return mode_success and temp_success

    async def turn_off_oven(self, device_id: str) -> bool:
        """Turn off oven."""
        return await self.execute_command(
            device_id,
            "ovenOperatingState",
            "stop",
        )

    # =========================================================================
    # Washer/Dryer Control
    # =========================================================================

    async def get_washer_status(self, device_id: str) -> dict[str, Any]:
        """Get washer status."""
        status = await self.get_device_status(device_id)

        result = {}
        components = status.get("components", {})
        main = components.get("main", {})

        if "washerOperatingState" in main:
            state = main["washerOperatingState"]
            result["machine_state"] = state.get("machineState", {}).get("value")
            result["job_state"] = state.get("washerJobState", {}).get("value")
            result["completion_time"] = state.get("completionTime", {}).get("value")

        if "washerMode" in main:
            result["mode"] = main["washerMode"].get("washerMode", {}).get("value")

        return result

    async def get_dryer_status(self, device_id: str) -> dict[str, Any]:
        """Get dryer status."""
        status = await self.get_device_status(device_id)

        result = {}
        components = status.get("components", {})
        main = components.get("main", {})

        if "dryerOperatingState" in main:
            state = main["dryerOperatingState"]
            result["machine_state"] = state.get("machineState", {}).get("value")
            result["job_state"] = state.get("dryerJobState", {}).get("value")
            result["completion_time"] = state.get("completionTime", {}).get("value")

        if "dryerMode" in main:
            result["mode"] = main["dryerMode"].get("dryerMode", {}).get("value")

        return result

    # =========================================================================
    # TV Control
    # =========================================================================

    async def tv_power(self, device_id: str, on: bool) -> bool:
        """Turn TV on/off."""
        return await self.execute_command(
            device_id,
            "switch",
            "on" if on else "off",
        )

    async def tv_set_volume(self, device_id: str, level: int) -> bool:
        """Set TV volume (0-100)."""
        return await self.execute_command(
            device_id,
            "audioVolume",
            "setVolume",
            [level],
        )

    async def tv_mute(self, device_id: str, mute: bool) -> bool:
        """Mute/unmute TV."""
        return await self.execute_command(
            device_id,
            "audioMute",
            "setMute" if mute else "unmute",
            [mute] if mute else [],
        )

    async def tv_set_channel(self, device_id: str, channel: int) -> bool:
        """Set TV channel."""
        return await self.execute_command(
            device_id,
            "tvChannel",
            "setTvChannel",
            [channel],
        )

    # =========================================================================
    # Event Handling
    # =========================================================================

    def on_event(self, callback: Callable[[dict], None]) -> None:
        """Register callback for device events."""
        self._event_callbacks.append(callback)

    async def poll_device_status(
        self,
        device_id: str,
        interval: float = 30.0,
        callback: Callable[[dict], None] | None = None,
    ) -> asyncio.Task:
        """Start polling device status.

        Args:
            device_id: Device to poll
            interval: Poll interval in seconds
            callback: Optional callback for status updates

        Returns:
            Polling task (cancel to stop)
        """

        async def poll_loop():
            while True:
                try:
                    status = await self.get_device_status(device_id)
                    if callback:
                        callback(status)
                    for cb in self._event_callbacks:
                        cb({"device_id": device_id, "status": status})
                except Exception as e:
                    logger.error(f"SmartThings: Poll error - {e}")

                await asyncio.sleep(interval)

        return asyncio.create_task(poll_loop())
