"""Tesla Service — Vehicle Control and Status.

Handles Tesla vehicle integration:
- Presence/geofencing (is car home)
- Battery status
- Preconditioning
- Charging control

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.integrations.tesla import TeslaIntegration

logger = logging.getLogger(__name__)


class TeslaService:
    """Service for Tesla vehicle control.

    Usage:
        tesla_svc = TeslaService(tesla_integration)
        if tesla_svc.is_car_home():
            print(f"Battery: {tesla_svc.get_car_battery()}%")
    """

    def __init__(self, tesla: TeslaIntegration | None = None) -> None:
        """Initialize Tesla service."""
        self._tesla = tesla

    def set_integration(self, tesla: TeslaIntegration) -> None:
        """Set or update Tesla integration."""
        self._tesla = tesla

    @property
    def is_available(self) -> bool:
        """Check if Tesla service is available."""
        return self._tesla is not None and self._tesla.is_connected

    def is_car_home(self) -> bool:
        """Check if Tesla is at home location."""
        if not self._tesla:
            return False
        return self._tesla.is_home()

    def get_car_battery(self) -> int:
        """Get current battery percentage."""
        if not self._tesla:
            return 0
        return self._tesla.get_battery_level()

    async def precondition_car(self, temp_c: float = 21.0) -> bool:
        """Start preconditioning the car.

        Args:
            temp_c: Target temperature in Celsius

        Returns:
            True if preconditioning started
        """
        if not self._tesla:
            return False
        # Set target temperature and start climate
        await self._tesla.set_temperature(temp_c)
        return await self._tesla.start_climate()

    async def start_car_charging(self) -> bool:
        """Start charging the car."""
        if not self._tesla:
            return False
        return await self._tesla.start_charging()

    async def stop_car_charging(self) -> bool:
        """Stop charging the car."""
        if not self._tesla:
            return False
        return await self._tesla.stop_charging()

    def get_car_state(self) -> dict[str, Any]:
        """Get comprehensive car state."""
        if not self._tesla:
            return {"available": False}
        return {
            "available": True,
            "is_home": self.is_car_home(),
            "battery": self.get_car_battery(),
            "charging": self._tesla.is_charging(),
            # Range not currently stored in TeslaState; would need Fleet Telemetry
            # fields (EstBatteryRange, IdealBatteryRange, RatedRange) to be added
            "range_km": None,
        }


__all__ = ["TeslaService"]
