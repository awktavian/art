"""Climate Service — HVAC and Temperature Control.

Handles climate control through:
- Mitsubishi: Mini-split HVAC zones (Kumo Cloud)
- Eight Sleep: Smart bed temperature

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.integrations.eight_sleep import EightSleepIntegration
    from kagami_smarthome.integrations.mitsubishi import MitsubishiIntegration

logger = logging.getLogger(__name__)


class ClimateService:
    """Service for climate and temperature control.

    Coordinates HVAC zones and bed temperature for comfort.

    Usage:
        climate_svc = ClimateService(mitsubishi, eight_sleep)
        await climate_svc.set_room_temp("Office", 72)
        await climate_svc.set_bed_temperature(2, side="left")
    """

    def __init__(
        self,
        mitsubishi: MitsubishiIntegration | None = None,
        eight_sleep: EightSleepIntegration | None = None,
    ) -> None:
        """Initialize climate service."""
        self._mitsubishi = mitsubishi
        self._eight_sleep = eight_sleep
        self._room_hvac_map: dict[str, str] = {}

    def set_integrations(
        self,
        mitsubishi: MitsubishiIntegration | None = None,
        eight_sleep: EightSleepIntegration | None = None,
    ) -> None:
        """Update integrations."""
        if mitsubishi:
            self._mitsubishi = mitsubishi
        if eight_sleep:
            self._eight_sleep = eight_sleep

    def set_room_hvac_map(self, mapping: dict[str, str]) -> None:
        """Set room name to HVAC zone ID mapping.

        Args:
            mapping: Dict of room_name -> zone_id
        """
        self._room_hvac_map = mapping

    # =========================================================================
    # HVAC Control
    # =========================================================================

    async def set_room_temp(self, room_name: str, temp_f: float) -> bool:
        """Set temperature for a room.

        Args:
            room_name: Room name
            temp_f: Target temperature in Fahrenheit

        Returns:
            True if successful
        """
        if not self._mitsubishi:
            return False

        zone_id = self._room_hvac_map.get(room_name)
        if not zone_id:
            logger.warning(f"No HVAC zone mapped for room: {room_name}")
            return False

        return await self._mitsubishi.set_temperature(zone_id, temp_f)

    async def set_room_hvac_mode(self, room_name: str, mode: str) -> bool:
        """Set HVAC mode for a room.

        Args:
            room_name: Room name
            mode: HVAC mode (heat, cool, auto, off, dry, fan)

        Returns:
            True if successful
        """
        if not self._mitsubishi:
            return False

        zone_id = self._room_hvac_map.get(room_name)
        if not zone_id:
            return False

        from kagami_smarthome.integrations.mitsubishi import HVACMode

        mode_map = {
            "heat": HVACMode.HEAT,
            "cool": HVACMode.COOL,
            "auto": HVACMode.AUTO,
            "off": HVACMode.OFF,
            "dry": HVACMode.DRY,
            "fan": HVACMode.FAN,
        }
        hvac_mode = mode_map.get(mode.lower())
        if not hvac_mode:
            return False

        return await self._mitsubishi.set_mode(zone_id, hvac_mode)

    async def set_all_temps(self, temp_f: float) -> bool:
        """Set all HVAC zones to same temperature.

        Args:
            temp_f: Target temperature in Fahrenheit

        Returns:
            True if any zones were set
        """
        if not self._mitsubishi:
            return False

        results = []
        for zone_id in self._mitsubishi.get_zones():
            results.append(await self._mitsubishi.set_temperature(zone_id, temp_f))
        return any(results)

    async def set_away_hvac(self, setback_temp: float = 62.0) -> bool:
        """Set HVAC to away/setback mode.

        Args:
            setback_temp: Energy-saving setback temperature

        Returns:
            True if successful
        """
        return await self.set_all_temps(setback_temp)

    def get_hvac_temps(self) -> dict[str, tuple[float, float]]:
        """Get all HVAC zone temperatures.

        Returns:
            Dict of zone_name -> (current_temp, setpoint)
        """
        if not self._mitsubishi:
            return {}

        result = {}
        for zone_id, status in self._mitsubishi.get_all_status().items():
            name = status.get("name", zone_id)
            current = status.get("room_temp", 0)
            setpoint = status.get("sp_heat", status.get("sp_cool", 0))
            result[name] = (current, setpoint)
        return result

    def get_average_temp(self) -> float:
        """Get average temperature across all zones.

        Returns:
            Average temperature in Fahrenheit
        """
        temps = self.get_hvac_temps()
        if not temps:
            return 0.0
        current_temps = [t[0] for t in temps.values() if t[0] > 0]
        return sum(current_temps) / len(current_temps) if current_temps else 0.0

    # =========================================================================
    # Eight Sleep (Bed Temperature)
    # =========================================================================

    def is_anyone_in_bed(self) -> bool:
        """Check if anyone is in bed."""
        if not self._eight_sleep:
            return False
        return self._eight_sleep.is_anyone_in_bed()

    def is_anyone_asleep(self) -> bool:
        """Check if anyone is asleep."""
        if not self._eight_sleep:
            return False
        return self._eight_sleep.is_anyone_asleep()

    async def set_bed_temperature(self, level: int, side: str = "both") -> bool:
        """Set bed temperature level.

        Args:
            level: Temperature level (-10 to +10)
            side: "left", "right", or "both"

        Returns:
            True if successful
        """
        if not self._eight_sleep:
            return False

        from kagami_smarthome.integrations.eight_sleep import BedSide

        if side == "both":
            left_result = await self._eight_sleep.set_temperature(level, BedSide.LEFT)
            right_result = await self._eight_sleep.set_temperature(level, BedSide.RIGHT)
            return left_result or right_result
        else:
            bed_side = BedSide.LEFT if side.lower() == "left" else BedSide.RIGHT
            return await self._eight_sleep.set_temperature(level, bed_side)

    def get_sleep_state(self) -> dict[str, Any]:
        """Get current sleep state from Eight Sleep.

        Returns:
            Dict with sleep state for each side
        """
        if not self._eight_sleep:
            return {}

        return {
            "left": self._eight_sleep.get_side_state("left"),
            "right": self._eight_sleep.get_side_state("right"),
            "anyone_in_bed": self.is_anyone_in_bed(),
            "anyone_asleep": self.is_anyone_asleep(),
        }


__all__ = ["ClimateService"]
