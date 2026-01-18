"""TOTO Neorest Smart Toilet Integration.

⚠️ IMPORTANT: TOTO Neorest toilets do NOT have WiFi or Bluetooth (US models).
They are controlled ONLY via IR remote. This integration provides:

1. INVENTORY TRACKING - Know what toilets you have and their features
2. IR CONTROL FRAMEWORK - If you install Control4 IR blasters
3. PRESENCE INTEGRATION - Trigger actions when someone enters bathroom

Toilet Inventory (7331 W Green Lake Dr N):
- Primary Bath: TOTO Neorest NX1 (MS902CUMFG#01) - flagship
- Powder Room: TOTO Neorest AS (MS8551CUMFG#01)
- Bath 2: TOTO Neorest AS (MS8551CUMFG#01)
- Bath 3: TOTO Neorest AS (MS8551CUMFG#01)
- Bath 4: TOTO Neorest AS (MS8551CUMFG#01)

Features (all controlled via IR remote):
- Auto lid open/close
- Heated seat (adjustable temperature)
- Bidet (front/rear wash, adjustable pressure & temp)
- Air dryer (adjustable temperature)
- Deodorizer
- Night light
- Auto/eco flush
- ACTILIGHT UV cleaning (NX1 only)
- EWATER+ electrolyzed water (NX1 only)

TO ENABLE AUTOMATION:
1. Install Control4 Z2iR IR module in each bathroom
2. Position IR blaster with line-of-sight to toilet
3. Capture IR codes from TOTO remote in Composer Pro
4. Configure device IDs in this file

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ToiletLocation(Enum):
    """Toilet locations in the home."""

    PRIMARY_BATH = "primary_bath"
    POWDER_ROOM = "powder_room"
    BATH_2 = "bath_2"
    BATH_3 = "bath_3"
    BATH_4 = "bath_4"


class ToiletModel(Enum):
    """TOTO Neorest models."""

    NX1 = "neorest_nx1"  # Primary Bath - flagship
    AS = "neorest_as"  # Secondary baths


@dataclass
class ToiletState:
    """Current state of a toilet."""

    location: ToiletLocation
    model: ToiletModel
    lid_open: bool = False
    seat_up: bool = False
    seat_temp: int = 3  # 1-5 scale
    water_temp: int = 3  # 1-5 scale
    dryer_temp: int = 3  # 1-5 scale
    pressure: int = 3  # 1-5 scale
    night_light: bool = True
    deodorizer: bool = True
    # NX1-only features
    actilight: bool = False  # UV cleaning
    ewater_plus: bool = True  # Electrolyzed water


# TOTO Neorest IR Command Codes
# These need to be captured from the actual remote using Control4 Composer Pro
# Format: (command_name, ir_code_hex)
NEOREST_IR_CODES = {
    # Lid/Seat Control
    "lid_open": "0x00",  # Placeholder - needs capture
    "lid_close": "0x01",
    "seat_up": "0x02",
    "seat_down": "0x03",
    # Bidet Functions
    "rear_wash": "0x10",
    "front_wash": "0x11",
    "oscillate": "0x12",
    "stop": "0x13",
    # Dryer
    "dryer_on": "0x20",
    "dryer_off": "0x21",
    # Flush
    "flush_full": "0x30",
    "flush_eco": "0x31",
    # Temperature - Seat
    "seat_temp_up": "0x40",
    "seat_temp_down": "0x41",
    # Temperature - Water
    "water_temp_up": "0x42",
    "water_temp_down": "0x43",
    # Temperature - Dryer
    "dryer_temp_up": "0x44",
    "dryer_temp_down": "0x45",
    # Pressure
    "pressure_up": "0x50",
    "pressure_down": "0x51",
    # Night Light
    "night_light_on": "0x60",
    "night_light_off": "0x61",
    # Deodorizer
    "deodorizer_on": "0x70",
    "deodorizer_off": "0x71",
    # NX1 Only
    "actilight_on": "0x80",
    "actilight_off": "0x81",
    "ewater_on": "0x82",
    "ewater_off": "0x83",
}

# Control4 device IDs for IR blasters (need to be configured)
# Each toilet needs an IR blaster with line-of-sight
TOILET_IR_DEVICE_IDS: dict[ToiletLocation, int | None] = {
    ToiletLocation.PRIMARY_BATH: None,  # Configure after IR setup
    ToiletLocation.POWDER_ROOM: None,
    ToiletLocation.BATH_2: None,
    ToiletLocation.BATH_3: None,
    ToiletLocation.BATH_4: None,
}


class TOTOIntegration:
    """TOTO Neorest toilet integration.

    This integration provides:
    1. Toilet inventory and feature tracking (always works)
    2. IR control via Control4 (requires hardware setup)

    The toilets themselves have NO WiFi/Bluetooth - IR only.
    """

    def __init__(self, control4_integration: Any = None):
        """Initialize TOTO integration.

        Args:
            control4_integration: Optional Control4Integration for IR control.
                                  If None, only inventory/tracking works.
        """
        self._control4 = control4_integration
        self._states: dict[ToiletLocation, ToiletState] = {}
        self._ir_configured = False

        # Initialize toilet states (this always works - it's just data)
        self._init_toilet_states()

        # Check IR capability
        self._check_ir_capability()

    def _init_toilet_states(self) -> None:
        """Initialize state for each toilet."""
        # Primary Bath - NX1 (flagship)
        self._states[ToiletLocation.PRIMARY_BATH] = ToiletState(
            location=ToiletLocation.PRIMARY_BATH,
            model=ToiletModel.NX1,
        )

        # Secondary baths - AS model
        for loc in [
            ToiletLocation.POWDER_ROOM,
            ToiletLocation.BATH_2,
            ToiletLocation.BATH_3,
            ToiletLocation.BATH_4,
        ]:
            self._states[loc] = ToiletState(
                location=loc,
                model=ToiletModel.AS,
            )

    def _check_ir_capability(self) -> None:
        """Check if IR control is configured."""
        configured = sum(1 for d in TOILET_IR_DEVICE_IDS.values() if d is not None)
        self._ir_configured = configured > 0

        if not self._ir_configured:
            logger.info(
                "TOTO: Inventory loaded (5 Neorest toilets). "
                "IR control not configured - toilets use IR remote only, no WiFi."
            )

    @property
    def is_connected(self) -> bool:
        """Check if inventory is loaded (always True after init)."""
        return len(self._states) > 0

    @property
    def ir_control_available(self) -> bool:
        """Check if IR control is configured."""
        return self._ir_configured and self._control4 is not None

    async def connect(self) -> bool:
        """Initialize the TOTO integration.

        Always succeeds for inventory. IR control requires hardware setup.
        """
        # Inventory always works
        logger.info("✅ TOTO: 5 Neorest toilets in inventory")

        # Check IR capability
        if self._control4 and self._control4.is_connected:
            configured = sum(1 for d in TOILET_IR_DEVICE_IDS.values() if d is not None)
            if configured > 0:
                logger.info(f"   IR control: {configured}/5 toilets configured")
            else:
                logger.info("   IR control: Not configured (requires Z2iR hardware)")
        else:
            logger.info("   IR control: Control4 not connected")

        return True  # Always return True - inventory works

    def get_inventory(self) -> dict[str, Any]:
        """Get toilet inventory (always works, no hardware needed).

        Returns:
            Complete inventory of all TOTO toilets with features.
        """
        return {
            "total_toilets": 5,
            "ir_control_available": self._ir_configured,
            "wifi_available": False,  # TOTO Neorest has NO WiFi
            "bluetooth_available": False,  # Not in US models
            "toilets": {
                "primary_bath": {
                    "model": "TOTO Neorest NX1",
                    "model_number": "MS902CUMFG#01",
                    "finish": "Cotton",
                    "features": [
                        "Auto lid open/close",
                        "Heated seat",
                        "Bidet (front/rear)",
                        "Air dryer",
                        "Deodorizer",
                        "Night light",
                        "Dual flush",
                        "ACTILIGHT UV (exclusive)",
                        "EWATER+ (exclusive)",
                    ],
                    "ir_configured": TOILET_IR_DEVICE_IDS.get(ToiletLocation.PRIMARY_BATH)
                    is not None,
                },
                "powder_room": {
                    "model": "TOTO Neorest AS",
                    "model_number": "MS8551CUMFG#01",
                    "finish": "White",
                    "features": [
                        "Auto lid open/close",
                        "Heated seat",
                        "Bidet (front/rear)",
                        "Air dryer",
                        "Deodorizer",
                        "Night light",
                        "Dual flush",
                    ],
                    "ir_configured": TOILET_IR_DEVICE_IDS.get(ToiletLocation.POWDER_ROOM)
                    is not None,
                },
                "bath_2": {
                    "model": "TOTO Neorest AS",
                    "model_number": "MS8551CUMFG#01",
                    "finish": "White",
                    "features": ["Auto lid", "Heated seat", "Bidet", "Dryer", "Night light"],
                    "ir_configured": TOILET_IR_DEVICE_IDS.get(ToiletLocation.BATH_2) is not None,
                },
                "bath_3": {
                    "model": "TOTO Neorest AS",
                    "model_number": "MS8551CUMFG#01",
                    "finish": "White",
                    "features": ["Auto lid", "Heated seat", "Bidet", "Dryer", "Night light"],
                    "ir_configured": TOILET_IR_DEVICE_IDS.get(ToiletLocation.BATH_3) is not None,
                },
                "bath_4": {
                    "model": "TOTO Neorest AS",
                    "model_number": "MS8551CUMFG#01",
                    "finish": "White",
                    "features": ["Auto lid", "Heated seat", "Bidet", "Dryer", "Night light"],
                    "ir_configured": TOILET_IR_DEVICE_IDS.get(ToiletLocation.BATH_4) is not None,
                },
            },
            "how_to_enable_control": {
                "step_1": "Purchase Control4 Z2iR IR modules (one per bathroom)",
                "step_2": "Install IR blaster with line-of-sight to toilet",
                "step_3": "Capture IR codes from TOTO remote in Composer Pro",
                "step_4": "Update TOILET_IR_DEVICE_IDS in this file",
                "estimated_cost": "$150-200 per bathroom for Z2iR module",
            },
        }

    async def _send_ir_command(self, location: ToiletLocation, command: str) -> bool:
        """Send an IR command to a toilet via Control4.

        Args:
            location: Which toilet
            command: Command name from NEOREST_IR_CODES

        Returns:
            True if command sent successfully
        """
        device_id = TOILET_IR_DEVICE_IDS.get(location)
        if device_id is None:
            logger.warning(f"TOTO: No IR device configured for {location.value}")
            return False

        ir_code = NEOREST_IR_CODES.get(command)
        if ir_code is None:
            logger.error(f"TOTO: Unknown command '{command}'")
            return False

        # Send via Control4 IR
        # This requires the custom driver to be set up in Composer Pro
        try:
            await self._control4._api_post(
                f"/items/{device_id}/commands", {"command": "SEND_IR", "params": {"code": ir_code}}
            )
            return True
        except Exception as e:
            logger.error(f"TOTO: Failed to send IR command: {e}")
            return False

    # =========================================================================
    # HIGH-LEVEL COMMANDS
    # =========================================================================

    async def open_lid(self, location: ToiletLocation = ToiletLocation.PRIMARY_BATH) -> bool:
        """Open the toilet lid."""
        success = await self._send_ir_command(location, "lid_open")
        if success:
            self._states[location].lid_open = True
        return success

    async def close_lid(self, location: ToiletLocation = ToiletLocation.PRIMARY_BATH) -> bool:
        """Close the toilet lid."""
        success = await self._send_ir_command(location, "lid_close")
        if success:
            self._states[location].lid_open = False
        return success

    async def flush(
        self, location: ToiletLocation = ToiletLocation.PRIMARY_BATH, eco: bool = False
    ) -> bool:
        """Flush the toilet.

        Args:
            location: Which toilet
            eco: Use eco flush (less water)
        """
        command = "flush_eco" if eco else "flush_full"
        return await self._send_ir_command(location, command)

    async def start_rear_wash(self, location: ToiletLocation = ToiletLocation.PRIMARY_BATH) -> bool:
        """Start rear bidet wash."""
        return await self._send_ir_command(location, "rear_wash")

    async def start_front_wash(
        self, location: ToiletLocation = ToiletLocation.PRIMARY_BATH
    ) -> bool:
        """Start front bidet wash."""
        return await self._send_ir_command(location, "front_wash")

    async def stop_wash(self, location: ToiletLocation = ToiletLocation.PRIMARY_BATH) -> bool:
        """Stop any active wash."""
        return await self._send_ir_command(location, "stop")

    async def start_dryer(self, location: ToiletLocation = ToiletLocation.PRIMARY_BATH) -> bool:
        """Start the air dryer."""
        return await self._send_ir_command(location, "dryer_on")

    async def stop_dryer(self, location: ToiletLocation = ToiletLocation.PRIMARY_BATH) -> bool:
        """Stop the air dryer."""
        return await self._send_ir_command(location, "dryer_off")

    async def set_night_light(
        self, on: bool, location: ToiletLocation = ToiletLocation.PRIMARY_BATH
    ) -> bool:
        """Turn night light on or off."""
        command = "night_light_on" if on else "night_light_off"
        success = await self._send_ir_command(location, command)
        if success:
            self._states[location].night_light = on
        return success

    async def set_deodorizer(
        self, on: bool, location: ToiletLocation = ToiletLocation.PRIMARY_BATH
    ) -> bool:
        """Turn deodorizer on or off."""
        command = "deodorizer_on" if on else "deodorizer_off"
        success = await self._send_ir_command(location, command)
        if success:
            self._states[location].deodorizer = on
        return success

    # =========================================================================
    # NX1-ONLY FEATURES (Primary Bath)
    # =========================================================================

    async def set_actilight(self, on: bool) -> bool:
        """Enable/disable ACTILIGHT UV cleaning (NX1 only).

        ACTILIGHT uses UV light to break down waste and reduce cleaning needs.
        """
        loc = ToiletLocation.PRIMARY_BATH
        if self._states[loc].model != ToiletModel.NX1:
            logger.warning("ACTILIGHT only available on NX1 model")
            return False

        command = "actilight_on" if on else "actilight_off"
        success = await self._send_ir_command(loc, command)
        if success:
            self._states[loc].actilight = on
        return success

    async def set_ewater_plus(self, on: bool) -> bool:
        """Enable/disable EWATER+ (NX1 only).

        EWATER+ uses electrolyzed water to keep the bowl clean between uses.
        """
        loc = ToiletLocation.PRIMARY_BATH
        if self._states[loc].model != ToiletModel.NX1:
            logger.warning("EWATER+ only available on NX1 model")
            return False

        command = "ewater_on" if on else "ewater_off"
        success = await self._send_ir_command(loc, command)
        if success:
            self._states[loc].ewater_plus = on
        return success

    # =========================================================================
    # STATE
    # =========================================================================

    def get_state(self, location: ToiletLocation = ToiletLocation.PRIMARY_BATH) -> dict[str, Any]:
        """Get current state of a toilet."""
        state = self._states.get(location)
        if not state:
            return {}

        return {
            "location": state.location.value,
            "model": state.model.value,
            "lid_open": state.lid_open,
            "seat_up": state.seat_up,
            "seat_temp": state.seat_temp,
            "water_temp": state.water_temp,
            "dryer_temp": state.dryer_temp,
            "pressure": state.pressure,
            "night_light": state.night_light,
            "deodorizer": state.deodorizer,
            "actilight": state.actilight if state.model == ToiletModel.NX1 else None,
            "ewater_plus": state.ewater_plus if state.model == ToiletModel.NX1 else None,
        }

    def get_all_toilets(self) -> dict[str, dict[str, Any]]:
        """Get state of all toilets."""
        return {loc.value: self.get_state(loc) for loc in ToiletLocation}

    # =========================================================================
    # SCENE SUPPORT
    # =========================================================================

    async def goodnight_mode(self) -> None:
        """Prepare all toilets for night.

        - Enable night lights
        - Enable deodorizers
        - Close all lids
        """

        # Prepare all toilets in parallel
        tasks = []
        for loc in ToiletLocation:
            tasks.extend(
                [
                    self.set_night_light(True, loc),
                    self.set_deodorizer(True, loc),
                    self.close_lid(loc),
                ]
            )
        await asyncio.gather(*tasks, return_exceptions=True)

    async def welcome_mode(self, location: ToiletLocation) -> None:
        """Prepare a toilet for use.

        - Open lid automatically
        - Ensure seat is warm
        """
        await self.open_lid(location)

    async def away_mode(self) -> None:
        """Set all toilets to away mode.

        - Close all lids
        - Reduce seat heating
        - Keep deodorizers on
        """

        # Close all lids in parallel
        await asyncio.gather(
            *[self.close_lid(loc) for loc in ToiletLocation], return_exceptions=True
        )


# =========================================================================
# SETUP INSTRUCTIONS
# =========================================================================
"""
TO ENABLE TOTO INTEGRATION:

1. Hardware Setup:
   - Install Control4 Z2iR IR modules near each toilet
   - Position IR blaster with line-of-sight to toilet's IR receiver
   - The IR receiver is typically on the toilet body, not the seat

2. Capture IR Codes in Control4 Composer Pro:
   - Use the TOTO remote that came with the toilet
   - In Composer Pro, go to Devices > Add Device > IR
   - Point remote at controller, press each button to capture codes
   - Save codes with the command names from NEOREST_IR_CODES

3. Create Custom Driver:
   - Create a custom device driver in Composer Pro
   - Map the captured IR codes to commands
   - Note the device ID for each toilet's IR blaster

4. Configure This Integration:
   - Update TOILET_IR_DEVICE_IDS with Control4 device IDs
   - Update NEOREST_IR_CODES with actual captured hex codes

5. Test:
   - Use this integration to send commands
   - Verify IR signals reach the toilet

ALTERNATIVE: TOTO Smart Remote App
- Some Neorest models support Bluetooth via TOTO app
- This integration focuses on Control4/IR for home automation
"""
