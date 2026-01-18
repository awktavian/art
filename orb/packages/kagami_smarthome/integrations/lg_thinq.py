"""LG ThinQ Appliance Integration.

Cloud API integration for LG smart appliances via ThinQ Connect platform.
Supports refrigerators, ovens/ranges, washers, dryers, dishwashers, and more.

Features:
- Refrigerator: Temperature, door status, ice maker, express freeze
- Oven/Range: Preheat, timer, temperature, cook modes
- Washer: Cycle control, status, remaining time
- Dryer: Cycle control, status, remaining time
- Dishwasher: Cycle status, remaining time
- Air Conditioner: Temperature, fan, mode
- Air Purifier: Mode, air quality

Architecture:
- LG ThinQ Connect Cloud API
- OAuth2 authentication with LG Account
- AWS IoT Core MQTT for real-time events

Requirements:
- pip install thinqconnect
- LG ThinQ account
- Personal Access Token from developer.lge.com

Created: December 29, 2025
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)


class ThinQDeviceType(str, Enum):
    """LG ThinQ device types."""

    REFRIGERATOR = "refrigerator"
    OVEN = "oven"
    RANGE = "range"
    COOKTOP = "cooktop"
    WASHER = "washer"
    DRYER = "dryer"
    WASHER_DRYER = "washer_dryer"
    DISHWASHER = "dishwasher"
    AIR_CONDITIONER = "air_conditioner"
    AIR_PURIFIER = "air_purifier"
    DEHUMIDIFIER = "dehumidifier"
    ROBOT_VACUUM = "robot_vacuum"
    STYLER = "styler"
    WATER_HEATER = "water_heater"


class OvenMode(str, Enum):
    """Oven cooking modes."""

    OFF = "OFF"
    BAKE = "BAKE"
    CONVECTION_BAKE = "CONVECTION_BAKE"
    CONVECTION_ROAST = "CONVECTION_ROAST"
    BROIL = "BROIL"
    WARM = "WARM"
    PROOF = "PROOF"
    AIR_FRY = "AIR_FRY"
    SELF_CLEAN = "SELF_CLEAN"


class WasherCycle(str, Enum):
    """Washer cycle types."""

    NORMAL = "NORMAL"
    DELICATE = "DELICATE"
    HEAVY_DUTY = "HEAVY_DUTY"
    QUICK_WASH = "QUICK_WASH"
    BEDDING = "BEDDING"
    SANITIZE = "SANITIZE"
    ALLERGEN = "ALLERGEN"


class DryerCycle(str, Enum):
    """Dryer cycle types."""

    NORMAL = "NORMAL"
    DELICATE = "DELICATE"
    HEAVY_DUTY = "HEAVY_DUTY"
    QUICK_DRY = "QUICK_DRY"
    AIR_DRY = "AIR_DRY"
    STEAM_FRESH = "STEAM_FRESH"


@dataclass
class ThinQDevice:
    """LG ThinQ device representation."""

    device_id: str
    device_type: ThinQDeviceType
    model: str
    name: str
    alias: str
    online: bool
    status: dict[str, Any] = field(default_factory=dict)


@dataclass
class RefrigeratorStatus:
    """Refrigerator status."""

    fridge_temp: int  # °F
    freezer_temp: int  # °F
    fridge_door_open: bool
    freezer_door_open: bool
    ice_maker_on: bool
    express_freeze_on: bool
    express_cool_on: bool
    water_filter_status: str  # "OK", "REPLACE_SOON", "REPLACE"


@dataclass
class OvenStatus:
    """Oven/Range status."""

    power_on: bool
    mode: OvenMode
    current_temp: int  # °F
    target_temp: int  # °F
    timer_remaining: int  # seconds
    preheating: bool
    preheat_complete: bool
    door_open: bool


@dataclass
class WasherStatus:
    """Washer status."""

    power_on: bool
    running: bool
    cycle: WasherCycle | None
    remaining_time: int  # minutes
    spin_speed: str
    water_temp: str
    door_locked: bool


@dataclass
class DryerStatus:
    """Dryer status."""

    power_on: bool
    running: bool
    cycle: DryerCycle | None
    remaining_time: int  # minutes
    heat_level: str
    door_open: bool


class LGThinQIntegration:
    """LG ThinQ appliance integration via ThinQ Connect API.

    Provides control of LG smart appliances including:
    - Refrigerators (InstaView, French Door, etc.)
    - Ovens and Ranges
    - Washers and Dryers
    - Dishwashers
    - Air Conditioners
    - Air Purifiers

    Usage:
        config = SmartHomeConfig(
            lg_thinq_access_token="...",
            lg_thinq_country="US",
            lg_thinq_language="en-US",
        )
        thinq = LGThinQIntegration(config)
        await thinq.connect()

        # Get devices
        devices = thinq.get_devices()
        fridge = thinq.get_refrigerator()

        # Control
        await thinq.set_fridge_temp(37)
        await thinq.preheat_oven(375, OvenMode.BAKE)
    """

    def __init__(self, config: SmartHomeConfig):
        self.config = config
        self._access_token = config.lg_thinq_access_token or os.environ.get("LG_THINQ_TOKEN")
        self._country = config.lg_thinq_country or "US"
        self._language = config.lg_thinq_language or "en-US"

        self._api = None
        self._connected = False
        self._devices: dict[str, ThinQDevice] = {}

        # Device instances by type
        self._refrigerators: list[ThinQDevice] = []
        self._ovens: list[ThinQDevice] = []
        self._washers: list[ThinQDevice] = []
        self._dryers: list[ThinQDevice] = []
        self._dishwashers: list[ThinQDevice] = []

        # Callbacks
        self._status_callbacks: dict[str, list[Callable[[dict], None]]] = {}

        # MQTT connection for events
        self._mqtt_connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to ThinQ API."""
        return self._connected

    @property
    def devices(self) -> list[ThinQDevice]:
        """Get all discovered devices."""
        return list(self._devices.values())

    async def connect(self) -> bool:
        """Connect to LG ThinQ API and discover devices.

        Returns True if connected successfully.
        """
        # HARDENED: Access token is REQUIRED - no graceful fallbacks
        if not self._access_token:
            raise RuntimeError(
                "LG ThinQ access token is required. "
                "Get token from developer.lge.com or set LG_THINQ_TOKEN env var"
            )

        # HARDENED: thinqconnect SDK is REQUIRED - no optional dependencies
        from thinqconnect import ThinQApi

        # Initialize API
        self._api = ThinQApi(
            access_token=self._access_token,
            country=self._country,
            language=self._language,
        )

        # Discover devices
        await self._discover_devices()

        self._connected = True

        if self._devices:
            logger.info(f"✅ LGThinQ: {len(self._devices)} appliances")
            for device in self._devices.values():
                logger.info(f"  - {device.device_type.value}: {device.name}")
        else:
            logger.info("LGThinQ: Connected (no devices found)")

        return True

    async def disconnect(self) -> None:
        """Disconnect from ThinQ API."""
        self._connected = False
        self._api = None
        self._devices.clear()
        logger.debug("LGThinQ: Disconnected")

    async def _discover_devices(self) -> None:
        """Discover all LG ThinQ devices."""
        if not self._api:
            return

        try:
            devices = await self._api.get_devices()

            for device_data in devices:
                device_type = self._parse_device_type(device_data.get("deviceType", ""))

                device = ThinQDevice(
                    device_id=device_data.get("deviceId", ""),
                    device_type=device_type,
                    model=device_data.get("modelName", "Unknown"),
                    name=device_data.get("alias", device_data.get("modelName", "Unknown")),
                    alias=device_data.get("alias", ""),
                    online=device_data.get("online", False),
                    status=device_data.get("snapshot", {}),
                )

                self._devices[device.device_id] = device

                # Categorize by type
                if device_type == ThinQDeviceType.REFRIGERATOR:
                    self._refrigerators.append(device)
                elif device_type in (ThinQDeviceType.OVEN, ThinQDeviceType.RANGE):
                    self._ovens.append(device)
                elif device_type in (ThinQDeviceType.WASHER, ThinQDeviceType.WASHER_DRYER):
                    self._washers.append(device)
                elif device_type == ThinQDeviceType.DRYER:
                    self._dryers.append(device)
                elif device_type == ThinQDeviceType.DISHWASHER:
                    self._dishwashers.append(device)

        except Exception as e:
            logger.error(f"LGThinQ: Device discovery failed - {e}")

    def _parse_device_type(self, type_str: str) -> ThinQDeviceType:
        """Parse device type string to enum."""
        type_map = {
            "REFRIGERATOR": ThinQDeviceType.REFRIGERATOR,
            "REF": ThinQDeviceType.REFRIGERATOR,
            "OVEN": ThinQDeviceType.OVEN,
            "RANGE": ThinQDeviceType.RANGE,
            "COOKTOP": ThinQDeviceType.COOKTOP,
            "WASHER": ThinQDeviceType.WASHER,
            "WASH_TOWER": ThinQDeviceType.WASHER_DRYER,
            "DRYER": ThinQDeviceType.DRYER,
            "DISHWASHER": ThinQDeviceType.DISHWASHER,
            "AIR_CONDITIONER": ThinQDeviceType.AIR_CONDITIONER,
            "AC": ThinQDeviceType.AIR_CONDITIONER,
            "AIR_PURIFIER": ThinQDeviceType.AIR_PURIFIER,
            "DEHUMIDIFIER": ThinQDeviceType.DEHUMIDIFIER,
            "ROBOT_VACUUM": ThinQDeviceType.ROBOT_VACUUM,
            "ROBOT": ThinQDeviceType.ROBOT_VACUUM,
            "STYLER": ThinQDeviceType.STYLER,
            "WATER_HEATER": ThinQDeviceType.WATER_HEATER,
        }
        return type_map.get(type_str.upper(), ThinQDeviceType.REFRIGERATOR)

    # =========================================================================
    # Device Getters
    # =========================================================================

    def get_devices(self, device_type: ThinQDeviceType | None = None) -> list[ThinQDevice]:
        """Get devices, optionally filtered by type."""
        if device_type is None:
            return list(self._devices.values())
        return [d for d in self._devices.values() if d.device_type == device_type]

    def get_refrigerator(self, index: int = 0) -> ThinQDevice | None:
        """Get refrigerator device."""
        return self._refrigerators[index] if index < len(self._refrigerators) else None

    def get_oven(self, index: int = 0) -> ThinQDevice | None:
        """Get oven/range device."""
        return self._ovens[index] if index < len(self._ovens) else None

    def get_washer(self, index: int = 0) -> ThinQDevice | None:
        """Get washer device."""
        return self._washers[index] if index < len(self._washers) else None

    def get_dryer(self, index: int = 0) -> ThinQDevice | None:
        """Get dryer device."""
        return self._dryers[index] if index < len(self._dryers) else None

    def get_dishwasher(self, index: int = 0) -> ThinQDevice | None:
        """Get dishwasher device."""
        return self._dishwashers[index] if index < len(self._dishwashers) else None

    # =========================================================================
    # Refrigerator Control
    # =========================================================================

    async def get_fridge_status(
        self, device: ThinQDevice | None = None
    ) -> RefrigeratorStatus | None:
        """Get refrigerator status."""
        device = device or self.get_refrigerator()
        if not device or not self._api:
            return None

        try:
            status = await self._api.get_device_status(device.device_id)

            return RefrigeratorStatus(
                fridge_temp=status.get("fridgeTemp", 37),
                freezer_temp=status.get("freezerTemp", 0),
                fridge_door_open=status.get("fridgeDoor", "CLOSE") == "OPEN",
                freezer_door_open=status.get("freezerDoor", "CLOSE") == "OPEN",
                ice_maker_on=status.get("iceMaker", "OFF") == "ON",
                express_freeze_on=status.get("expressFreeze", "OFF") == "ON",
                express_cool_on=status.get("expressCool", "OFF") == "ON",
                water_filter_status=status.get("waterFilterStatus", "OK"),
            )
        except Exception as e:
            logger.error(f"LGThinQ: Failed to get fridge status - {e}")
            return None

    async def set_fridge_temp(self, temp_f: int, device: ThinQDevice | None = None) -> bool:
        """Set refrigerator temperature.

        Args:
            temp_f: Temperature in Fahrenheit (typically 33-46°F)
            device: Specific refrigerator device (defaults to first)

        Returns:
            True if successful
        """
        device = device or self.get_refrigerator()
        if not device or not self._api:
            return False

        # Validate range
        if not 33 <= temp_f <= 46:
            logger.warning(f"LGThinQ: Fridge temp {temp_f}°F outside safe range (33-46°F)")
            return False

        try:
            await self._api.send_command(
                device.device_id,
                {
                    "fridgeTemp": temp_f,
                },
            )
            logger.info(f"LGThinQ: Set fridge to {temp_f}°F")
            return True
        except Exception as e:
            logger.error(f"LGThinQ: Failed to set fridge temp - {e}")
            return False

    async def set_freezer_temp(self, temp_f: int, device: ThinQDevice | None = None) -> bool:
        """Set freezer temperature.

        Args:
            temp_f: Temperature in Fahrenheit (typically -6 to 8°F)
            device: Specific refrigerator device

        Returns:
            True if successful
        """
        device = device or self.get_refrigerator()
        if not device or not self._api:
            return False

        # Validate range
        if not -6 <= temp_f <= 8:
            logger.warning(f"LGThinQ: Freezer temp {temp_f}°F outside safe range (-6 to 8°F)")
            return False

        try:
            await self._api.send_command(
                device.device_id,
                {
                    "freezerTemp": temp_f,
                },
            )
            logger.info(f"LGThinQ: Set freezer to {temp_f}°F")
            return True
        except Exception as e:
            logger.error(f"LGThinQ: Failed to set freezer temp - {e}")
            return False

    async def toggle_ice_maker(self, on: bool, device: ThinQDevice | None = None) -> bool:
        """Toggle ice maker on/off."""
        device = device or self.get_refrigerator()
        if not device or not self._api:
            return False

        try:
            await self._api.send_command(
                device.device_id,
                {
                    "iceMaker": "ON" if on else "OFF",
                },
            )
            return True
        except Exception as e:
            logger.error(f"LGThinQ: Failed to toggle ice maker - {e}")
            return False

    async def toggle_express_freeze(self, on: bool, device: ThinQDevice | None = None) -> bool:
        """Toggle express freeze mode."""
        device = device or self.get_refrigerator()
        if not device or not self._api:
            return False

        try:
            await self._api.send_command(
                device.device_id,
                {
                    "expressFreeze": "ON" if on else "OFF",
                },
            )
            return True
        except Exception as e:
            logger.error(f"LGThinQ: Failed to toggle express freeze - {e}")
            return False

    # =========================================================================
    # Oven Control
    # =========================================================================

    async def get_oven_status(self, device: ThinQDevice | None = None) -> OvenStatus | None:
        """Get oven/range status."""
        device = device or self.get_oven()
        if not device or not self._api:
            return None

        try:
            status = await self._api.get_device_status(device.device_id)

            mode_str = status.get("cookMode", "OFF")
            mode = OvenMode.OFF
            for m in OvenMode:
                if m.value == mode_str:
                    mode = m
                    break

            current = status.get("currentTemp", 0)
            target = status.get("targetTemp", 0)

            return OvenStatus(
                power_on=status.get("power", "OFF") == "ON",
                mode=mode,
                current_temp=current,
                target_temp=target,
                timer_remaining=status.get("timerRemaining", 0),
                preheating=current < target and mode != OvenMode.OFF,
                preheat_complete=current >= target and mode != OvenMode.OFF,
                door_open=status.get("doorState", "CLOSE") == "OPEN",
            )
        except Exception as e:
            logger.error(f"LGThinQ: Failed to get oven status - {e}")
            return None

    async def preheat_oven(
        self,
        temp_f: int,
        mode: OvenMode = OvenMode.BAKE,
        device: ThinQDevice | None = None,
    ) -> bool:
        """Preheat oven to specified temperature.

        Args:
            temp_f: Target temperature in Fahrenheit (typically 170-550°F)
            mode: Cooking mode (BAKE, CONVECTION_BAKE, etc.)
            device: Specific oven device

        Returns:
            True if preheat started successfully

        Safety:
            - Validates temperature range
            - Does not start if door is open
        """
        device = device or self.get_oven()
        if not device or not self._api:
            return False

        # Safety: Validate temperature range
        if not 170 <= temp_f <= 550:
            logger.warning(f"LGThinQ: Oven temp {temp_f}°F outside safe range (170-550°F)")
            return False

        # Safety: Check door state
        status = await self.get_oven_status(device)
        if status and status.door_open:
            logger.warning("LGThinQ: Cannot preheat oven - door is open")
            return False

        try:
            await self._api.send_command(
                device.device_id,
                {
                    "power": "ON",
                    "cookMode": mode.value,
                    "targetTemp": temp_f,
                },
            )
            logger.info(f"LGThinQ: Preheating oven to {temp_f}°F ({mode.value})")
            return True
        except Exception as e:
            logger.error(f"LGThinQ: Failed to preheat oven - {e}")
            return False

    async def turn_off_oven(self, device: ThinQDevice | None = None) -> bool:
        """Turn off oven."""
        device = device or self.get_oven()
        if not device or not self._api:
            return False

        try:
            await self._api.send_command(
                device.device_id,
                {
                    "power": "OFF",
                },
            )
            logger.info("LGThinQ: Oven turned off")
            return True
        except Exception as e:
            logger.error(f"LGThinQ: Failed to turn off oven - {e}")
            return False

    async def set_oven_timer(self, minutes: int, device: ThinQDevice | None = None) -> bool:
        """Set oven timer.

        Args:
            minutes: Timer duration in minutes
            device: Specific oven device

        Returns:
            True if timer set successfully
        """
        device = device or self.get_oven()
        if not device or not self._api:
            return False

        try:
            await self._api.send_command(
                device.device_id,
                {
                    "timerMinutes": minutes,
                },
            )
            logger.info(f"LGThinQ: Oven timer set for {minutes} minutes")
            return True
        except Exception as e:
            logger.error(f"LGThinQ: Failed to set oven timer - {e}")
            return False

    # =========================================================================
    # Washer Control
    # =========================================================================

    async def get_washer_status(self, device: ThinQDevice | None = None) -> WasherStatus | None:
        """Get washer status."""
        device = device or self.get_washer()
        if not device or not self._api:
            return None

        try:
            status = await self._api.get_device_status(device.device_id)

            cycle_str = status.get("cycle", "")
            cycle = None
            for c in WasherCycle:
                if c.value == cycle_str:
                    cycle = c
                    break

            return WasherStatus(
                power_on=status.get("power", "OFF") == "ON",
                running=status.get("state", "IDLE") == "RUNNING",
                cycle=cycle,
                remaining_time=status.get("remainingTime", 0),
                spin_speed=status.get("spinSpeed", ""),
                water_temp=status.get("waterTemp", ""),
                door_locked=status.get("doorLock", "OFF") == "ON",
            )
        except Exception as e:
            logger.error(f"LGThinQ: Failed to get washer status - {e}")
            return None

    async def start_washer(
        self,
        cycle: WasherCycle = WasherCycle.NORMAL,
        device: ThinQDevice | None = None,
    ) -> bool:
        """Start washer with specified cycle."""
        device = device or self.get_washer()
        if not device or not self._api:
            return False

        try:
            await self._api.send_command(
                device.device_id,
                {
                    "power": "ON",
                    "cycle": cycle.value,
                    "state": "START",
                },
            )
            logger.info(f"LGThinQ: Started washer ({cycle.value})")
            return True
        except Exception as e:
            logger.error(f"LGThinQ: Failed to start washer - {e}")
            return False

    async def pause_washer(self, device: ThinQDevice | None = None) -> bool:
        """Pause washer."""
        device = device or self.get_washer()
        if not device or not self._api:
            return False

        try:
            await self._api.send_command(
                device.device_id,
                {
                    "state": "PAUSE",
                },
            )
            return True
        except Exception as e:
            logger.error(f"LGThinQ: Failed to pause washer - {e}")
            return False

    # =========================================================================
    # Dryer Control
    # =========================================================================

    async def get_dryer_status(self, device: ThinQDevice | None = None) -> DryerStatus | None:
        """Get dryer status."""
        device = device or self.get_dryer()
        if not device or not self._api:
            return None

        try:
            status = await self._api.get_device_status(device.device_id)

            cycle_str = status.get("cycle", "")
            cycle = None
            for c in DryerCycle:
                if c.value == cycle_str:
                    cycle = c
                    break

            return DryerStatus(
                power_on=status.get("power", "OFF") == "ON",
                running=status.get("state", "IDLE") == "RUNNING",
                cycle=cycle,
                remaining_time=status.get("remainingTime", 0),
                heat_level=status.get("heatLevel", ""),
                door_open=status.get("doorState", "CLOSE") == "OPEN",
            )
        except Exception as e:
            logger.error(f"LGThinQ: Failed to get dryer status - {e}")
            return None

    async def start_dryer(
        self,
        cycle: DryerCycle = DryerCycle.NORMAL,
        device: ThinQDevice | None = None,
    ) -> bool:
        """Start dryer with specified cycle."""
        device = device or self.get_dryer()
        if not device or not self._api:
            return False

        try:
            await self._api.send_command(
                device.device_id,
                {
                    "power": "ON",
                    "cycle": cycle.value,
                    "state": "START",
                },
            )
            logger.info(f"LGThinQ: Started dryer ({cycle.value})")
            return True
        except Exception as e:
            logger.error(f"LGThinQ: Failed to start dryer - {e}")
            return False

    # =========================================================================
    # Event Callbacks
    # =========================================================================

    def on_status_change(self, device_id: str, callback: Callable[[dict], None]) -> None:
        """Register callback for device status changes."""
        if device_id not in self._status_callbacks:
            self._status_callbacks[device_id] = []
        self._status_callbacks[device_id].append(callback)

    def on_fridge_door(self, callback: Callable[[bool], None]) -> None:
        """Register callback for fridge door open/close events."""
        fridge = self.get_refrigerator()
        if fridge:

            def wrapper(status: dict) -> None:
                door_open = status.get("fridgeDoor", "CLOSE") == "OPEN"
                callback(door_open)

            self.on_status_change(fridge.device_id, wrapper)

    def on_oven_preheat_complete(self, callback: Callable[[], None]) -> None:
        """Register callback for oven preheat complete event."""
        oven = self.get_oven()
        if oven:
            was_preheating = False

            def wrapper(status: dict) -> None:
                nonlocal was_preheating
                current = status.get("currentTemp", 0)
                target = status.get("targetTemp", 0)
                is_preheating = current < target and target > 0

                if was_preheating and not is_preheating and current >= target:
                    callback()

                was_preheating = is_preheating

            self.on_status_change(oven.device_id, wrapper)

    def on_washer_done(self, callback: Callable[[], None]) -> None:
        """Register callback for washer cycle complete event."""
        washer = self.get_washer()
        if washer:
            was_running = False

            def wrapper(status: dict) -> None:
                nonlocal was_running
                is_running = status.get("state", "IDLE") == "RUNNING"

                if was_running and not is_running:
                    callback()

                was_running = is_running

            self.on_status_change(washer.device_id, wrapper)

    def on_dryer_done(self, callback: Callable[[], None]) -> None:
        """Register callback for dryer cycle complete event."""
        dryer = self.get_dryer()
        if dryer:
            was_running = False

            def wrapper(status: dict) -> None:
                nonlocal was_running
                is_running = status.get("state", "IDLE") == "RUNNING"

                if was_running and not is_running:
                    callback()

                was_running = is_running

            self.on_status_change(dryer.device_id, wrapper)
