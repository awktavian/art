"""Electrolux Appliance Integration.

Cloud API integration for Electrolux smart appliances via their OneApp API.
Supports washers, dryers, and other Electrolux/AEG/Frigidaire appliances.

Tim's Appliances:
- Electrolux Washer
- Electrolux Dryer

SDK Options:
1. pyelectroluxocp (OneApp API) - recommended, actively maintained
2. pyelectroluxconnect - older API

This integration uses pyelectroluxocp for the OneApp API.

Requirements:
- pip install pyelectroluxocp
- Electrolux account (same as used in Electrolux app)

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

from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)


class ElectroluxWasherCycle(str, Enum):
    """Electrolux washer cycles."""

    NORMAL = "Normal"
    DELICATE = "Delicate"
    HEAVY_DUTY = "Heavy Duty"
    QUICK_WASH = "Quick Wash"
    WHITES = "Whites"
    COLORS = "Colors"
    TOWELS = "Towels"
    BEDDING = "Bedding"
    ACTIVEWEAR = "Activewear"
    ALLERGEN = "Allergen"
    SANITIZE = "Sanitize"
    STEAM_CLEAN = "Steam Clean"
    RINSE_SPIN = "Rinse & Spin"
    SPIN_ONLY = "Spin Only"


class ElectroluxDryerCycle(str, Enum):
    """Electrolux dryer cycles."""

    NORMAL = "Normal"
    DELICATE = "Delicate"
    HEAVY_DUTY = "Heavy Duty"
    QUICK_DRY = "Quick Dry"
    TOWELS = "Towels"
    BEDDING = "Bedding"
    ACTIVEWEAR = "Activewear"
    SANITIZE = "Sanitize"
    STEAM_REFRESH = "Steam Refresh"
    AIR_DRY = "Air Dry"
    WRINKLE_RELEASE = "Wrinkle Release"


class ElectroluxDryLevel(str, Enum):
    """Electrolux dryer dryness levels."""

    DAMP = "Damp"
    LESS_DRY = "Less Dry"
    NORMAL = "Normal"
    MORE_DRY = "More Dry"
    VERY_DRY = "Very Dry"


class ElectroluxSpinSpeed(str, Enum):
    """Electrolux washer spin speeds."""

    NO_SPIN = "No Spin"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    MAX = "Max"


class ElectroluxWaterTemp(str, Enum):
    """Electrolux washer water temperatures."""

    TAP_COLD = "Tap Cold"
    COLD = "Cold"
    WARM = "Warm"
    HOT = "Hot"
    SANITIZE = "Sanitize"


@dataclass
class ElectroluxWasherStatus:
    """Electrolux washer status."""

    power_on: bool
    running: bool
    paused: bool
    cycle: ElectroluxWasherCycle | None
    time_remaining: int  # minutes
    spin_speed: ElectroluxSpinSpeed | None
    water_temp: ElectroluxWaterTemp | None
    soil_level: str | None
    door_locked: bool
    remote_start_enabled: bool
    # Steam features
    steam_option: bool
    # Alerts
    clean_washer_reminder: bool
    add_clothes_light: bool


@dataclass
class ElectroluxDryerStatus:
    """Electrolux dryer status."""

    power_on: bool
    running: bool
    paused: bool
    cycle: ElectroluxDryerCycle | None
    time_remaining: int  # minutes
    dry_level: ElectroluxDryLevel | None
    heat_level: str | None
    door_open: bool
    remote_start_enabled: bool
    # Steam features
    steam_option: bool
    # Alerts
    clean_lint_filter: bool
    wrinkle_prevent_active: bool


@dataclass
class ElectroluxAppliance:
    """Electrolux appliance representation."""

    appliance_id: str
    name: str
    model: str
    appliance_type: str  # "washer", "dryer", etc.
    serial_number: str
    firmware_version: str
    online: bool
    status: dict[str, Any] = field(default_factory=dict)


class ElectroluxIntegration:
    """Electrolux appliance integration via OneApp API.

    Supports Electrolux, AEG, and Frigidaire branded appliances.

    Usage:
        config = SmartHomeConfig(
            electrolux_email="your@email.com",
            electrolux_password="your_password",
        )
        elux = ElectroluxIntegration(config)
        await elux.connect()

        # Get status
        washer_status = await elux.get_washer_status()

        # Start cycle
        await elux.start_washer(ElectroluxWasherCycle.NORMAL)
    """

    def __init__(self, config: SmartHomeConfig):
        self.config = config
        self._email = config.electrolux_email or os.environ.get("ELECTROLUX_EMAIL")
        self._password = config.electrolux_password or os.environ.get("ELECTROLUX_PASSWORD")
        self._country = config.electrolux_country or "US"

        self._api = None
        self._connected = False
        self._appliances: dict[str, ElectroluxAppliance] = {}

        # Device instances
        self._washer: ElectroluxAppliance | None = None
        self._dryer: ElectroluxAppliance | None = None

        # Callbacks
        self._status_callbacks: dict[str, list[Callable[[dict], None]]] = {}

    @property
    def is_connected(self) -> bool:
        """Check if connected to Electrolux API."""
        return self._connected

    @property
    def appliances(self) -> list[ElectroluxAppliance]:
        """Get all discovered appliances."""
        return list(self._appliances.values())

    async def connect(self) -> bool:
        """Connect to Electrolux OneApp API and discover appliances.

        Returns True if connected successfully.
        """
        if not self._email or not self._password:
            logger.warning("Electrolux: No credentials configured")
            logger.info("Electrolux: Set ELECTROLUX_EMAIL and ELECTROLUX_PASSWORD env vars")
            return False

        try:
            # HARDENED: pyelectroluxocp is REQUIRED - no optional dependencies
            from pyelectroluxocp import OneAppApi

            # Initialize API
            self._api = OneAppApi(
                username=self._email,
                password=self._password,
                country=self._country.lower(),
            )

            # Connect and authenticate
            await self._api.__aenter__()

            # Discover appliances
            await self._discover_appliances()

            self._connected = True

            if self._appliances:
                logger.info(f"✅ Electrolux: {len(self._appliances)} appliances")
                for appliance in self._appliances.values():
                    logger.info(f"  - {appliance.appliance_type}: {appliance.name}")
            else:
                logger.info("Electrolux: Connected (no appliances found)")

            return True

        except Exception as e:
            logger.error(f"Electrolux: Connection failed - {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Electrolux API."""
        if self._api:
            try:
                await self._api.__aexit__(None, None, None)
            except Exception:
                pass
            self._api = None

        self._connected = False
        self._appliances.clear()
        logger.debug("Electrolux: Disconnected")

    async def _discover_appliances(self) -> None:
        """Discover all Electrolux appliances."""
        if not self._api:
            return

        try:
            appliances_data = await self._api.get_appliances_list()

            for data in appliances_data:
                appliance_data = data.get("applianceData", {})
                appliance_id = data.get("applianceId", "")

                appliance_type = self._parse_appliance_type(
                    appliance_data.get("applianceType", ""),
                    appliance_data.get("applianceName", ""),
                )

                appliance = ElectroluxAppliance(
                    appliance_id=appliance_id,
                    name=appliance_data.get("applianceName", "Unknown"),
                    model=appliance_data.get("modelName", "Unknown"),
                    appliance_type=appliance_type,
                    serial_number=appliance_data.get("serialNumber", ""),
                    firmware_version=appliance_data.get("firmwareVersion", ""),
                    online=data.get("connectionState", "") == "Connected",
                    status={},
                )

                self._appliances[appliance_id] = appliance

                # Categorize
                if appliance_type == "washer":
                    self._washer = appliance
                elif appliance_type == "dryer":
                    self._dryer = appliance

        except Exception as e:
            logger.error(f"Electrolux: Discovery failed - {e}")

    def _parse_appliance_type(self, type_str: str, name: str) -> str:
        """Parse appliance type from API data."""
        type_lower = type_str.lower()
        name_lower = name.lower()

        if "wash" in type_lower or "wash" in name_lower:
            if "dry" in type_lower or "dry" in name_lower:
                return "washer_dryer"
            return "washer"
        elif "dry" in type_lower or "dry" in name_lower:
            return "dryer"
        elif "dish" in type_lower or "dish" in name_lower:
            return "dishwasher"
        elif "fridge" in type_lower or "refrigerator" in name_lower:
            return "refrigerator"
        elif "oven" in type_lower or "range" in name_lower:
            return "oven"

        return "unknown"

    # =========================================================================
    # Device Getters
    # =========================================================================

    def get_washer(self) -> ElectroluxAppliance | None:
        """Get washer appliance."""
        return self._washer

    def get_dryer(self) -> ElectroluxAppliance | None:
        """Get dryer appliance."""
        return self._dryer

    # =========================================================================
    # Washer Control
    # =========================================================================

    async def get_washer_status(self) -> ElectroluxWasherStatus | None:
        """Get washer status."""
        if not self._washer or not self._api:
            return None

        try:
            status = await self._api.get_appliance_state(self._washer.appliance_id)

            # Parse cycle
            cycle_str = status.get("cycle", "")
            cycle = None
            for c in ElectroluxWasherCycle:
                if c.value.lower() == cycle_str.lower():
                    cycle = c
                    break

            # Parse spin speed
            spin_str = status.get("spinSpeed", "")
            spin = None
            for s in ElectroluxSpinSpeed:
                if s.value.lower() == spin_str.lower():
                    spin = s
                    break

            # Parse water temp
            temp_str = status.get("waterTemp", "")
            temp = None
            for t in ElectroluxWaterTemp:
                if t.value.lower() == temp_str.lower():
                    temp = t
                    break

            return ElectroluxWasherStatus(
                power_on=status.get("applianceState", "") != "Off",
                running=status.get("applianceState", "") == "Running",
                paused=status.get("applianceState", "") == "Paused",
                cycle=cycle,
                time_remaining=status.get("timeToEnd", 0),
                spin_speed=spin,
                water_temp=temp,
                soil_level=status.get("soilLevel"),
                door_locked=status.get("doorLock", False),
                remote_start_enabled=status.get("remoteStart", False),
                steam_option=status.get("steamOption", False),
                clean_washer_reminder=status.get("cleanWasherReminder", False),
                add_clothes_light=status.get("addClothes", False),
            )
        except Exception as e:
            logger.error(f"Electrolux: Failed to get washer status - {e}")
            return None

    async def start_washer(
        self,
        cycle: ElectroluxWasherCycle = ElectroluxWasherCycle.NORMAL,
        spin_speed: ElectroluxSpinSpeed | None = None,
        water_temp: ElectroluxWaterTemp | None = None,
        steam: bool = False,
    ) -> bool:
        """Start washer with specified settings.

        Note: Remote start must be enabled on the washer (door closed,
        detergent loaded, remote start button pressed).

        Args:
            cycle: Wash cycle to run
            spin_speed: Optional spin speed override
            water_temp: Optional water temperature override
            steam: Enable steam option if available
        """
        if not self._washer or not self._api:
            logger.warning("Electrolux: Washer not available")
            return False

        try:
            # Check remote start enabled
            status = await self.get_washer_status()
            if status and not status.remote_start_enabled:
                logger.warning("Electrolux: Remote start not enabled on washer")
                logger.info("Electrolux: Load washer, close door, and press Remote Start button")
                return False

            # Build command
            command = {
                "cycle": cycle.value,
            }
            if spin_speed:
                command["spinSpeed"] = spin_speed.value
            if water_temp:
                command["waterTemp"] = water_temp.value
            if steam:
                command["steamOption"] = True

            await self._api.send_command(self._washer.appliance_id, "start", command)
            logger.info(f"Electrolux: Started washer ({cycle.value})")
            return True

        except Exception as e:
            logger.error(f"Electrolux: Failed to start washer - {e}")
            return False

    async def pause_washer(self) -> bool:
        """Pause washer."""
        if not self._washer or not self._api:
            return False

        try:
            await self._api.send_command(self._washer.appliance_id, "pause", {})
            return True
        except Exception as e:
            logger.error(f"Electrolux: Failed to pause washer - {e}")
            return False

    async def resume_washer(self) -> bool:
        """Resume paused washer."""
        if not self._washer or not self._api:
            return False

        try:
            await self._api.send_command(self._washer.appliance_id, "resume", {})
            return True
        except Exception as e:
            logger.error(f"Electrolux: Failed to resume washer - {e}")
            return False

    # =========================================================================
    # Dryer Control
    # =========================================================================

    async def get_dryer_status(self) -> ElectroluxDryerStatus | None:
        """Get dryer status."""
        if not self._dryer or not self._api:
            return None

        try:
            status = await self._api.get_appliance_state(self._dryer.appliance_id)

            # Parse cycle
            cycle_str = status.get("cycle", "")
            cycle = None
            for c in ElectroluxDryerCycle:
                if c.value.lower() == cycle_str.lower():
                    cycle = c
                    break

            # Parse dry level
            level_str = status.get("dryLevel", "")
            level = None
            for l in ElectroluxDryLevel:
                if l.value.lower() == level_str.lower():
                    level = l
                    break

            return ElectroluxDryerStatus(
                power_on=status.get("applianceState", "") != "Off",
                running=status.get("applianceState", "") == "Running",
                paused=status.get("applianceState", "") == "Paused",
                cycle=cycle,
                time_remaining=status.get("timeToEnd", 0),
                dry_level=level,
                heat_level=status.get("heatLevel"),
                door_open=status.get("doorState", "") == "Open",
                remote_start_enabled=status.get("remoteStart", False),
                steam_option=status.get("steamOption", False),
                clean_lint_filter=status.get("cleanLintFilter", False),
                wrinkle_prevent_active=status.get("wrinklePrevent", False),
            )
        except Exception as e:
            logger.error(f"Electrolux: Failed to get dryer status - {e}")
            return None

    async def start_dryer(
        self,
        cycle: ElectroluxDryerCycle = ElectroluxDryerCycle.NORMAL,
        dry_level: ElectroluxDryLevel | None = None,
        steam: bool = False,
    ) -> bool:
        """Start dryer with specified settings.

        Note: Remote start must be enabled on the dryer.

        Args:
            cycle: Dry cycle to run
            dry_level: Optional dryness level override
            steam: Enable steam option if available
        """
        if not self._dryer or not self._api:
            logger.warning("Electrolux: Dryer not available")
            return False

        try:
            # Check door
            status = await self.get_dryer_status()
            if status and status.door_open:
                logger.warning("Electrolux: Cannot start dryer - door is open")
                return False

            if status and not status.remote_start_enabled:
                logger.warning("Electrolux: Remote start not enabled on dryer")
                return False

            command = {
                "cycle": cycle.value,
            }
            if dry_level:
                command["dryLevel"] = dry_level.value
            if steam:
                command["steamOption"] = True

            await self._api.send_command(self._dryer.appliance_id, "start", command)
            logger.info(f"Electrolux: Started dryer ({cycle.value})")
            return True

        except Exception as e:
            logger.error(f"Electrolux: Failed to start dryer - {e}")
            return False

    async def pause_dryer(self) -> bool:
        """Pause dryer."""
        if not self._dryer or not self._api:
            return False

        try:
            await self._api.send_command(self._dryer.appliance_id, "pause", {})
            return True
        except Exception as e:
            logger.error(f"Electrolux: Failed to pause dryer - {e}")
            return False

    async def resume_dryer(self) -> bool:
        """Resume paused dryer."""
        if not self._dryer or not self._api:
            return False

        try:
            await self._api.send_command(self._dryer.appliance_id, "resume", {})
            return True
        except Exception as e:
            logger.error(f"Electrolux: Failed to resume dryer - {e}")
            return False

    async def extend_tumble(self) -> bool:
        """Extend tumble time on dryer (wrinkle prevention)."""
        if not self._dryer or not self._api:
            return False

        try:
            await self._api.send_command(self._dryer.appliance_id, "extendTumble", {})
            return True
        except Exception:
            return False

    # =========================================================================
    # Event Callbacks
    # =========================================================================

    def on_washer_done(self, callback: Callable[[], None]) -> None:
        """Register callback for washer cycle complete."""
        if not self._washer:
            return

        was_running = False

        async def check_status():
            nonlocal was_running
            status = await self.get_washer_status()
            if status:
                is_running = status.running
                if was_running and not is_running:
                    callback()
                was_running = is_running

        # Note: Would need to set up polling or use API's watch functionality
        self._status_callbacks.setdefault(self._washer.appliance_id, []).append(
            lambda s: callback() if not s.get("running") else None
        )

    def on_dryer_done(self, callback: Callable[[], None]) -> None:
        """Register callback for dryer cycle complete."""
        if not self._dryer:
            return

        self._status_callbacks.setdefault(self._dryer.appliance_id, []).append(
            lambda s: callback() if not s.get("running") else None
        )

    async def watch_for_updates(
        self,
        callback: Callable[[str, dict], None],
        poll_interval: float = 60.0,
    ) -> asyncio.Task:
        """Start watching for appliance status updates.

        Args:
            callback: Function called with (appliance_id, status) on changes
            poll_interval: Seconds between status checks

        Returns:
            Task that can be cancelled to stop watching
        """

        async def poll_loop():
            while True:
                try:
                    for appliance_id in self._appliances:
                        if self._api:
                            status = await self._api.get_appliance_state(appliance_id)
                            callback(appliance_id, status)
                except Exception as e:
                    logger.error(f"Electrolux: Watch error - {e}")

                await asyncio.sleep(poll_interval)

        return asyncio.create_task(poll_loop())
