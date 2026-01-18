"""Sub-Zero, Wolf, and Cove Appliance Integration.

Integration for premium Sub-Zero (refrigeration), Wolf (cooking),
and Cove (dishwasher) appliances via two methods:
1. Control4 driver (recommended - native integration)
2. Sub-Zero Group Owner's App cloud API (fallback)

Tim's Appliances:
- Wolf Range (cooking)
- Sub-Zero Refrigerator
- Cove Dishwasher

Control4 Integration:
The Sub-Zero Group provides official Control4 drivers that integrate
through their Owner's App. Since Tim already has Control4, this is
the preferred method - no additional API setup required.

Cloud API:
For direct integration without Control4, uses the Sub-Zero Group
cloud API (same backend as their Owner's App).

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import aiohttp

from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)


class WolfOvenMode(str, Enum):
    """Wolf oven/range cooking modes."""

    OFF = "off"
    BAKE = "bake"
    CONVECTION = "convection"
    CONVECTION_BAKE = "convection_bake"
    ROAST = "roast"
    CONVECTION_ROAST = "convection_roast"
    BROIL_HIGH = "broil_high"
    BROIL_LOW = "broil_low"
    WARM = "warm"
    PROOF = "proof"
    DEHYDRATE = "dehydrate"
    GOURMET = "gourmet"
    STONE = "stone"  # Pizza stone mode
    SELF_CLEAN = "self_clean"


class SubZeroMode(str, Enum):
    """Sub-Zero refrigerator modes."""

    NORMAL = "normal"
    VACATION = "vacation"
    SABBATH = "sabbath"
    MAX_COOL = "max_cool"  # Rapid cool


class CoveWashCycle(str, Enum):
    """Cove dishwasher wash cycles."""

    AUTO = "auto"
    HEAVY = "heavy"
    NORMAL = "normal"
    LIGHT = "light"
    QUICK = "quick"
    RINSE = "rinse"
    SANITIZE = "sanitize"


@dataclass
class WolfRangeStatus:
    """Wolf range/oven status."""

    power_on: bool
    oven_mode: WolfOvenMode
    oven_temp_current: int  # °F
    oven_temp_target: int  # °F
    oven_preheating: bool
    oven_preheat_complete: bool
    oven_door_open: bool
    timer_active: bool
    timer_remaining: int  # seconds
    # Burner status (for ranges)
    burners: dict[str, int] = field(default_factory=dict)  # name -> level (0-10)
    # Probe temperature
    probe_temp: int | None = None
    probe_target: int | None = None


@dataclass
class SubZeroStatus:
    """Sub-Zero refrigerator status."""

    power_on: bool
    mode: SubZeroMode
    fridge_temp_current: int  # °F
    fridge_temp_target: int  # °F
    freezer_temp_current: int  # °F
    freezer_temp_target: int  # °F
    fridge_door_open: bool
    freezer_door_open: bool
    ice_maker_on: bool
    water_filter_status: str  # "ok", "replace_soon", "replace"
    door_alarm_active: bool
    max_cool_active: bool
    vacation_mode: bool


@dataclass
class CoveDishwasherStatus:
    """Cove dishwasher status."""

    power_on: bool
    running: bool
    cycle: CoveWashCycle | None
    time_remaining: int  # minutes
    door_open: bool
    rinse_aid_low: bool
    salt_low: bool
    clean_filter_alert: bool
    delay_start_hours: int | None


class SubZeroWolfIntegration:
    """Sub-Zero, Wolf, and Cove appliance integration.

    Two integration paths:
    1. Via Control4 (recommended for Tim's setup)
    2. Via cloud API (direct)

    Since Tim has Control4, the Control4 driver handles the
    communication. This class provides a unified interface that
    can work with either method.

    Usage with Control4:
        # Control4 driver handles the connection
        # This integration reads/writes via Control4 API

        config = SmartHomeConfig(
            control4_host="192.168.1.2",
            control4_bearer_token="...",
        )
        szw = SubZeroWolfIntegration(config, use_control4=True)
        await szw.connect()

        status = await szw.get_wolf_status()
        await szw.preheat_wolf_oven(375, WolfOvenMode.CONVECTION_BAKE)

    Usage with Cloud API:
        config = SmartHomeConfig(
            subzero_wolf_email="...",
            subzero_wolf_password="...",
        )
        szw = SubZeroWolfIntegration(config, use_control4=False)
        await szw.connect()
    """

    # Sub-Zero Group OAuth endpoints
    AUTH_URL = "https://api.subzero-wolf.com/v1/auth/login"
    API_BASE = "https://api.subzero-wolf.com/v1"

    def __init__(
        self,
        config: SmartHomeConfig,
        use_control4: bool = True,
        control4_integration: Any = None,
    ):
        self.config = config
        self._use_control4 = use_control4
        self._control4 = control4_integration

        # Cloud API credentials
        self._email = config.subzero_wolf_email
        self._password = config.subzero_wolf_password

        self._session: aiohttp.ClientSession | None = None
        self._access_token: str | None = None
        self._connected = False

        # Discovered appliances
        self._wolf_id: str | None = None  # Wolf range device ID
        self._subzero_id: str | None = None  # Sub-Zero fridge device ID
        self._cove_id: str | None = None  # Cove dishwasher device ID

        # Control4 item IDs (if using Control4)
        self._c4_wolf_id: int | None = None
        self._c4_subzero_id: int | None = None
        self._c4_cove_id: int | None = None

        # Callbacks
        self._status_callbacks: list[Callable[[str, dict], None]] = []

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    @property
    def has_wolf(self) -> bool:
        """Check if Wolf range is available."""
        return self._wolf_id is not None or self._c4_wolf_id is not None

    @property
    def has_subzero(self) -> bool:
        """Check if Sub-Zero is available."""
        return self._subzero_id is not None or self._c4_subzero_id is not None

    @property
    def has_cove(self) -> bool:
        """Check if Cove dishwasher is available."""
        return self._cove_id is not None or self._c4_cove_id is not None

    async def connect(self) -> bool:
        """Connect to Sub-Zero/Wolf/Cove appliances.

        Uses Control4 if available, otherwise cloud API.
        """
        if self._use_control4 and self._control4:
            return await self._connect_via_control4()
        else:
            return await self._connect_via_cloud()

    async def disconnect(self) -> None:
        """Disconnect."""
        if self._session:
            await self._session.close()
            self._session = None

        self._connected = False
        logger.debug("SubZeroWolf: Disconnected")

    # =========================================================================
    # Control4 Integration
    # =========================================================================

    async def _connect_via_control4(self) -> bool:
        """Connect via Control4 driver.

        The Control4 driver for Sub-Zero/Wolf/Cove creates items
        in the Control4 project for each appliance.
        """
        if not self._control4:
            logger.warning("SubZeroWolf: Control4 integration not provided")
            return False

        try:
            # Search for Sub-Zero/Wolf/Cove items in Control4
            items = self._control4._items

            for item_id, item in items.items():
                name = item.get("name", "").lower()
                driver = item.get("driver", "").lower()

                # Wolf range/oven
                if "wolf" in name or "wolf" in driver:
                    if "range" in name or "oven" in name:
                        self._c4_wolf_id = item_id
                        logger.info(f"SubZeroWolf: Found Wolf range (C4 ID: {item_id})")

                # Sub-Zero refrigerator
                if "sub-zero" in name or "subzero" in name or "sub_zero" in driver:
                    if "refrigerator" in name or "fridge" in name:
                        self._c4_subzero_id = item_id
                        logger.info(f"SubZeroWolf: Found Sub-Zero fridge (C4 ID: {item_id})")

                # Cove dishwasher
                if "cove" in name or "cove" in driver:
                    if "dishwasher" in name:
                        self._c4_cove_id = item_id
                        logger.info(f"SubZeroWolf: Found Cove dishwasher (C4 ID: {item_id})")

            found = []
            if self._c4_wolf_id:
                found.append("Wolf")
            if self._c4_subzero_id:
                found.append("Sub-Zero")
            if self._c4_cove_id:
                found.append("Cove")

            if found:
                self._connected = True
                logger.info(f"✅ SubZeroWolf (Control4): {', '.join(found)}")
                return True
            else:
                logger.info("SubZeroWolf: No appliances found in Control4")
                logger.info("SubZeroWolf: Install the Sub-Zero Group driver via your dealer")
                return False

        except Exception as e:
            logger.error(f"SubZeroWolf: Control4 connection failed - {e}")
            return False

    # =========================================================================
    # Cloud API Integration
    # =========================================================================

    async def _connect_via_cloud(self) -> bool:
        """Connect via Sub-Zero Group cloud API."""
        if not self._email or not self._password:
            logger.warning("SubZeroWolf: No cloud credentials configured")
            return False

        try:
            self._session = aiohttp.ClientSession()

            # Authenticate
            auth_data = {
                "email": self._email,
                "password": self._password,
            }

            async with self._session.post(self.AUTH_URL, json=auth_data) as resp:
                if resp.status != 200:
                    logger.error("SubZeroWolf: Cloud authentication failed")
                    return False

                data = await resp.json()
                self._access_token = data.get("accessToken")

            # Discover appliances
            await self._discover_appliances()

            found = []
            if self._wolf_id:
                found.append("Wolf")
            if self._subzero_id:
                found.append("Sub-Zero")
            if self._cove_id:
                found.append("Cove")

            if found:
                self._connected = True
                logger.info(f"✅ SubZeroWolf (Cloud): {', '.join(found)}")
                return True
            else:
                logger.info("SubZeroWolf: No appliances found")
                return False

        except Exception as e:
            logger.error(f"SubZeroWolf: Cloud connection failed - {e}")
            return False

    async def _discover_appliances(self) -> None:
        """Discover appliances via cloud API."""
        if not self._session or not self._access_token:
            return

        headers = {"Authorization": f"Bearer {self._access_token}"}

        try:
            async with self._session.get(
                f"{self.API_BASE}/appliances",
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    return

                data = await resp.json()

                for appliance in data.get("appliances", []):
                    brand = appliance.get("brand", "").lower()
                    appliance_type = appliance.get("type", "").lower()
                    appliance_id = appliance.get("id")

                    if brand == "wolf" and "range" in appliance_type:
                        self._wolf_id = appliance_id
                    elif brand == "sub-zero" and "refrigerator" in appliance_type:
                        self._subzero_id = appliance_id
                    elif brand == "cove" and "dishwasher" in appliance_type:
                        self._cove_id = appliance_id

        except Exception as e:
            logger.error(f"SubZeroWolf: Discovery failed - {e}")

    async def _api_get(self, endpoint: str) -> dict | None:
        """Make authenticated GET request."""
        if not self._session or not self._access_token:
            return None

        headers = {"Authorization": f"Bearer {self._access_token}"}

        try:
            async with self._session.get(
                f"{self.API_BASE}{endpoint}",
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception:
            return None

    async def _api_post(self, endpoint: str, data: dict) -> bool:
        """Make authenticated POST request."""
        if not self._session or not self._access_token:
            return False

        headers = {"Authorization": f"Bearer {self._access_token}"}

        try:
            async with self._session.post(
                f"{self.API_BASE}{endpoint}",
                headers=headers,
                json=data,
            ) as resp:
                return resp.status in (200, 202)
        except Exception:
            return False

    # =========================================================================
    # Wolf Range Control
    # =========================================================================

    async def get_wolf_status(self) -> WolfRangeStatus | None:
        """Get Wolf range/oven status."""
        if self._use_control4 and self._c4_wolf_id and self._control4:
            return await self._get_wolf_status_c4()
        elif self._wolf_id:
            return await self._get_wolf_status_cloud()
        return None

    async def _get_wolf_status_c4(self) -> WolfRangeStatus | None:
        """Get Wolf status via Control4."""
        if not self._control4 or not self._c4_wolf_id:
            return None

        try:
            # Get item variables from Control4
            state = await self._control4._api_get(f"/items/{self._c4_wolf_id}/variables")
            if not state:
                return None

            # Parse Control4 variables
            mode_str = state.get("OVEN_MODE", "off").lower()
            mode = WolfOvenMode.OFF
            for m in WolfOvenMode:
                if m.value == mode_str:
                    mode = m
                    break

            return WolfRangeStatus(
                power_on=state.get("POWER", "OFF") == "ON",
                oven_mode=mode,
                oven_temp_current=state.get("OVEN_TEMP_CURRENT", 0),
                oven_temp_target=state.get("OVEN_TEMP_TARGET", 0),
                oven_preheating=state.get("OVEN_PREHEATING", False),
                oven_preheat_complete=state.get("OVEN_PREHEAT_DONE", False),
                oven_door_open=state.get("OVEN_DOOR", "CLOSED") == "OPEN",
                timer_active=state.get("TIMER_ACTIVE", False),
                timer_remaining=state.get("TIMER_REMAINING", 0),
                burners={},
                probe_temp=state.get("PROBE_TEMP"),
                probe_target=state.get("PROBE_TARGET"),
            )
        except Exception as e:
            logger.error(f"SubZeroWolf: Failed to get Wolf status - {e}")
            return None

    async def _get_wolf_status_cloud(self) -> WolfRangeStatus | None:
        """Get Wolf status via cloud API."""
        if not self._wolf_id:
            return None

        data = await self._api_get(f"/appliances/{self._wolf_id}/status")
        if not data:
            return None

        mode_str = data.get("ovenMode", "off").lower()
        mode = WolfOvenMode.OFF
        for m in WolfOvenMode:
            if m.value == mode_str:
                mode = m
                break

        return WolfRangeStatus(
            power_on=data.get("power", False),
            oven_mode=mode,
            oven_temp_current=data.get("ovenTempCurrent", 0),
            oven_temp_target=data.get("ovenTempTarget", 0),
            oven_preheating=data.get("ovenPreheating", False),
            oven_preheat_complete=data.get("ovenPreheatComplete", False),
            oven_door_open=data.get("ovenDoorOpen", False),
            timer_active=data.get("timerActive", False),
            timer_remaining=data.get("timerRemaining", 0),
            burners=data.get("burners", {}),
            probe_temp=data.get("probeTemp"),
            probe_target=data.get("probeTarget"),
        )

    async def preheat_wolf_oven(
        self,
        temp_f: int,
        mode: WolfOvenMode = WolfOvenMode.BAKE,
    ) -> bool:
        """Preheat Wolf oven.

        Args:
            temp_f: Target temperature in Fahrenheit (170-550°F)
            mode: Cooking mode

        Returns:
            True if preheat started

        Safety:
            - Validates temperature range
            - Does not start if door is open
        """
        # Safety: Validate temperature
        if not 170 <= temp_f <= 550:
            logger.warning(f"SubZeroWolf: Oven temp {temp_f}°F outside safe range (170-550°F)")
            return False

        # Safety: Check door
        status = await self.get_wolf_status()
        if status and status.oven_door_open:
            logger.warning("SubZeroWolf: Cannot preheat - oven door is open")
            return False

        if self._use_control4 and self._c4_wolf_id and self._control4:
            return await self._preheat_wolf_c4(temp_f, mode)
        elif self._wolf_id:
            return await self._preheat_wolf_cloud(temp_f, mode)
        return False

    async def _preheat_wolf_c4(self, temp_f: int, mode: WolfOvenMode) -> bool:
        """Preheat Wolf via Control4."""
        if not self._control4 or not self._c4_wolf_id:
            return False

        try:
            # Set mode
            await self._control4._api_post(
                f"/items/{self._c4_wolf_id}/commands",
                {"command": "SET_OVEN_MODE", "params": {"mode": mode.value}},
            )

            # Set temperature
            await self._control4._api_post(
                f"/items/{self._c4_wolf_id}/commands",
                {"command": "SET_OVEN_TEMP", "params": {"temp": temp_f}},
            )

            # Start preheat
            result = await self._control4._api_post(
                f"/items/{self._c4_wolf_id}/commands",
                {"command": "START_OVEN"},
            )

            if result:
                logger.info(f"SubZeroWolf: Preheating Wolf oven to {temp_f}°F ({mode.value})")
            return result

        except Exception as e:
            logger.error(f"SubZeroWolf: Failed to preheat Wolf - {e}")
            return False

    async def _preheat_wolf_cloud(self, temp_f: int, mode: WolfOvenMode) -> bool:
        """Preheat Wolf via cloud API."""
        if not self._wolf_id:
            return False

        data = {
            "command": "preheat",
            "mode": mode.value,
            "temperature": temp_f,
        }

        result = await self._api_post(f"/appliances/{self._wolf_id}/commands", data)
        if result:
            logger.info(f"SubZeroWolf: Preheating Wolf oven to {temp_f}°F ({mode.value})")
        return result

    async def turn_off_wolf_oven(self) -> bool:
        """Turn off Wolf oven."""
        if self._use_control4 and self._c4_wolf_id and self._control4:
            return await self._control4._api_post(
                f"/items/{self._c4_wolf_id}/commands",
                {"command": "STOP_OVEN"},
            )
        elif self._wolf_id:
            return await self._api_post(
                f"/appliances/{self._wolf_id}/commands",
                {"command": "stop"},
            )
        return False

    async def set_wolf_timer(self, minutes: int) -> bool:
        """Set Wolf oven timer."""
        if self._use_control4 and self._c4_wolf_id and self._control4:
            return await self._control4._api_post(
                f"/items/{self._c4_wolf_id}/commands",
                {"command": "SET_TIMER", "params": {"minutes": minutes}},
            )
        elif self._wolf_id:
            return await self._api_post(
                f"/appliances/{self._wolf_id}/commands",
                {"command": "setTimer", "minutes": minutes},
            )
        return False

    # =========================================================================
    # Sub-Zero Refrigerator Control
    # =========================================================================

    async def get_subzero_status(self) -> SubZeroStatus | None:
        """Get Sub-Zero refrigerator status."""
        if self._use_control4 and self._c4_subzero_id and self._control4:
            return await self._get_subzero_status_c4()
        elif self._subzero_id:
            return await self._get_subzero_status_cloud()
        return None

    async def _get_subzero_status_c4(self) -> SubZeroStatus | None:
        """Get Sub-Zero status via Control4."""
        if not self._control4 or not self._c4_subzero_id:
            return None

        try:
            state = await self._control4._api_get(f"/items/{self._c4_subzero_id}/variables")
            if not state:
                return None

            mode_str = state.get("MODE", "normal").lower()
            mode = SubZeroMode.NORMAL
            for m in SubZeroMode:
                if m.value == mode_str:
                    mode = m
                    break

            return SubZeroStatus(
                power_on=state.get("POWER", "ON") == "ON",
                mode=mode,
                fridge_temp_current=state.get("FRIDGE_TEMP_CURRENT", 37),
                fridge_temp_target=state.get("FRIDGE_TEMP_TARGET", 37),
                freezer_temp_current=state.get("FREEZER_TEMP_CURRENT", 0),
                freezer_temp_target=state.get("FREEZER_TEMP_TARGET", 0),
                fridge_door_open=state.get("FRIDGE_DOOR", "CLOSED") == "OPEN",
                freezer_door_open=state.get("FREEZER_DOOR", "CLOSED") == "OPEN",
                ice_maker_on=state.get("ICE_MAKER", "ON") == "ON",
                water_filter_status=state.get("WATER_FILTER", "ok"),
                door_alarm_active=state.get("DOOR_ALARM", False),
                max_cool_active=state.get("MAX_COOL", False),
                vacation_mode=mode == SubZeroMode.VACATION,
            )
        except Exception as e:
            logger.error(f"SubZeroWolf: Failed to get Sub-Zero status - {e}")
            return None

    async def _get_subzero_status_cloud(self) -> SubZeroStatus | None:
        """Get Sub-Zero status via cloud API."""
        if not self._subzero_id:
            return None

        data = await self._api_get(f"/appliances/{self._subzero_id}/status")
        if not data:
            return None

        mode_str = data.get("mode", "normal").lower()
        mode = SubZeroMode.NORMAL
        for m in SubZeroMode:
            if m.value == mode_str:
                mode = m
                break

        return SubZeroStatus(
            power_on=data.get("power", True),
            mode=mode,
            fridge_temp_current=data.get("fridgeTempCurrent", 37),
            fridge_temp_target=data.get("fridgeTempTarget", 37),
            freezer_temp_current=data.get("freezerTempCurrent", 0),
            freezer_temp_target=data.get("freezerTempTarget", 0),
            fridge_door_open=data.get("fridgeDoorOpen", False),
            freezer_door_open=data.get("freezerDoorOpen", False),
            ice_maker_on=data.get("iceMakerOn", True),
            water_filter_status=data.get("waterFilterStatus", "ok"),
            door_alarm_active=data.get("doorAlarmActive", False),
            max_cool_active=data.get("maxCoolActive", False),
            vacation_mode=data.get("vacationMode", False),
        )

    async def set_subzero_fridge_temp(self, temp_f: int) -> bool:
        """Set Sub-Zero refrigerator temperature.

        Args:
            temp_f: Temperature in Fahrenheit (34-42°F recommended)
        """
        if not 32 <= temp_f <= 46:
            logger.warning(f"SubZeroWolf: Fridge temp {temp_f}°F outside safe range")
            return False

        if self._use_control4 and self._c4_subzero_id and self._control4:
            return await self._control4._api_post(
                f"/items/{self._c4_subzero_id}/commands",
                {"command": "SET_FRIDGE_TEMP", "params": {"temp": temp_f}},
            )
        elif self._subzero_id:
            return await self._api_post(
                f"/appliances/{self._subzero_id}/commands",
                {"command": "setFridgeTemp", "temperature": temp_f},
            )
        return False

    async def set_subzero_freezer_temp(self, temp_f: int) -> bool:
        """Set Sub-Zero freezer temperature.

        Args:
            temp_f: Temperature in Fahrenheit (-5 to 5°F recommended)
        """
        if not -10 <= temp_f <= 10:
            logger.warning(f"SubZeroWolf: Freezer temp {temp_f}°F outside safe range")
            return False

        if self._use_control4 and self._c4_subzero_id and self._control4:
            return await self._control4._api_post(
                f"/items/{self._c4_subzero_id}/commands",
                {"command": "SET_FREEZER_TEMP", "params": {"temp": temp_f}},
            )
        elif self._subzero_id:
            return await self._api_post(
                f"/appliances/{self._subzero_id}/commands",
                {"command": "setFreezerTemp", "temperature": temp_f},
            )
        return False

    async def toggle_subzero_max_cool(self, on: bool) -> bool:
        """Toggle Sub-Zero max cool (rapid cool) mode."""
        if self._use_control4 and self._c4_subzero_id and self._control4:
            return await self._control4._api_post(
                f"/items/{self._c4_subzero_id}/commands",
                {"command": "MAX_COOL_ON" if on else "MAX_COOL_OFF"},
            )
        elif self._subzero_id:
            return await self._api_post(
                f"/appliances/{self._subzero_id}/commands",
                {"command": "setMaxCool", "enabled": on},
            )
        return False

    async def set_subzero_vacation_mode(self, on: bool) -> bool:
        """Set Sub-Zero vacation mode (reduces energy)."""
        if self._use_control4 and self._c4_subzero_id and self._control4:
            return await self._control4._api_post(
                f"/items/{self._c4_subzero_id}/commands",
                {"command": "VACATION_MODE_ON" if on else "VACATION_MODE_OFF"},
            )
        elif self._subzero_id:
            return await self._api_post(
                f"/appliances/{self._subzero_id}/commands",
                {"command": "setVacationMode", "enabled": on},
            )
        return False

    # =========================================================================
    # Cove Dishwasher Control
    # =========================================================================

    async def get_cove_status(self) -> CoveDishwasherStatus | None:
        """Get Cove dishwasher status."""
        if self._use_control4 and self._c4_cove_id and self._control4:
            return await self._get_cove_status_c4()
        elif self._cove_id:
            return await self._get_cove_status_cloud()
        return None

    async def _get_cove_status_c4(self) -> CoveDishwasherStatus | None:
        """Get Cove status via Control4."""
        if not self._control4 or not self._c4_cove_id:
            return None

        try:
            state = await self._control4._api_get(f"/items/{self._c4_cove_id}/variables")
            if not state:
                return None

            cycle_str = state.get("CYCLE", "").lower()
            cycle = None
            for c in CoveWashCycle:
                if c.value == cycle_str:
                    cycle = c
                    break

            return CoveDishwasherStatus(
                power_on=state.get("POWER", "OFF") == "ON",
                running=state.get("STATE", "IDLE") == "RUNNING",
                cycle=cycle,
                time_remaining=state.get("TIME_REMAINING", 0),
                door_open=state.get("DOOR", "CLOSED") == "OPEN",
                rinse_aid_low=state.get("RINSE_AID_LOW", False),
                salt_low=state.get("SALT_LOW", False),
                clean_filter_alert=state.get("CLEAN_FILTER", False),
                delay_start_hours=state.get("DELAY_START"),
            )
        except Exception as e:
            logger.error(f"SubZeroWolf: Failed to get Cove status - {e}")
            return None

    async def _get_cove_status_cloud(self) -> CoveDishwasherStatus | None:
        """Get Cove status via cloud API."""
        if not self._cove_id:
            return None

        data = await self._api_get(f"/appliances/{self._cove_id}/status")
        if not data:
            return None

        cycle_str = data.get("cycle", "").lower()
        cycle = None
        for c in CoveWashCycle:
            if c.value == cycle_str:
                cycle = c
                break

        return CoveDishwasherStatus(
            power_on=data.get("power", False),
            running=data.get("running", False),
            cycle=cycle,
            time_remaining=data.get("timeRemaining", 0),
            door_open=data.get("doorOpen", False),
            rinse_aid_low=data.get("rinseAidLow", False),
            salt_low=data.get("saltLow", False),
            clean_filter_alert=data.get("cleanFilterAlert", False),
            delay_start_hours=data.get("delayStart"),
        )

    async def start_cove_dishwasher(
        self,
        cycle: CoveWashCycle = CoveWashCycle.AUTO,
        delay_hours: int | None = None,
    ) -> bool:
        """Start Cove dishwasher.

        Args:
            cycle: Wash cycle to run
            delay_hours: Optional delay start in hours
        """
        # Check door
        status = await self.get_cove_status()
        if status and status.door_open:
            logger.warning("SubZeroWolf: Cannot start dishwasher - door is open")
            return False

        if self._use_control4 and self._c4_cove_id and self._control4:
            commands = [
                {"command": "SET_CYCLE", "params": {"cycle": cycle.value}},
            ]
            if delay_hours:
                commands.append({"command": "SET_DELAY", "params": {"hours": delay_hours}})
            commands.append({"command": "START"})

            # Send all commands in parallel
            if commands:
                await asyncio.gather(
                    *[
                        self._control4._api_post(f"/items/{self._c4_cove_id}/commands", cmd)
                        for cmd in commands
                    ],
                    return_exceptions=True,
                )

            logger.info(f"SubZeroWolf: Started Cove dishwasher ({cycle.value})")
            return True

        elif self._cove_id:
            data = {"command": "start", "cycle": cycle.value}
            if delay_hours:
                data["delayHours"] = delay_hours
            return await self._api_post(f"/appliances/{self._cove_id}/commands", data)

        return False

    async def stop_cove_dishwasher(self) -> bool:
        """Stop Cove dishwasher."""
        if self._use_control4 and self._c4_cove_id and self._control4:
            return await self._control4._api_post(
                f"/items/{self._c4_cove_id}/commands",
                {"command": "STOP"},
            )
        elif self._cove_id:
            return await self._api_post(
                f"/appliances/{self._cove_id}/commands",
                {"command": "stop"},
            )
        return False

    # =========================================================================
    # Event Callbacks
    # =========================================================================

    def on_status_change(self, callback: Callable[[str, dict], None]) -> None:
        """Register callback for appliance status changes.

        Callback receives (appliance_type, status_dict) where appliance_type
        is "wolf", "subzero", or "cove".
        """
        self._status_callbacks.append(callback)

    def on_wolf_preheat_complete(self, callback: Callable[[], None]) -> None:
        """Register callback for Wolf oven preheat complete."""
        was_preheating = False

        def wrapper(appliance_type: str, status: dict) -> None:
            nonlocal was_preheating
            if appliance_type != "wolf":
                return

            is_preheating = status.get("oven_preheating", False)
            preheat_done = status.get("oven_preheat_complete", False)

            if was_preheating and preheat_done:
                callback()

            was_preheating = is_preheating

        self.on_status_change(wrapper)

    def on_subzero_door_open(self, callback: Callable[[str], None]) -> None:
        """Register callback for Sub-Zero door open events.

        Callback receives door name ("fridge" or "freezer").
        """
        fridge_was_open = False
        freezer_was_open = False

        def wrapper(appliance_type: str, status: dict) -> None:
            nonlocal fridge_was_open, freezer_was_open
            if appliance_type != "subzero":
                return

            fridge_open = status.get("fridge_door_open", False)
            freezer_open = status.get("freezer_door_open", False)

            if fridge_open and not fridge_was_open:
                callback("fridge")
            if freezer_open and not freezer_was_open:
                callback("freezer")

            fridge_was_open = fridge_open
            freezer_was_open = freezer_open

        self.on_status_change(wrapper)

    def on_cove_complete(self, callback: Callable[[], None]) -> None:
        """Register callback for Cove dishwasher cycle complete."""
        was_running = False

        def wrapper(appliance_type: str, status: dict) -> None:
            nonlocal was_running
            if appliance_type != "cove":
                return

            is_running = status.get("running", False)

            if was_running and not is_running:
                callback()

            was_running = is_running

        self.on_status_change(wrapper)
