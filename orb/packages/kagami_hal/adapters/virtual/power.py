"""Virtual Power Adapter for testing/headless environments.

Implements PowerController with simulated battery.

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
"""

from __future__ import annotations

import logging

from kagami_hal.data_types import (
    BatteryStatus,
    PowerMode,
    PowerStats,
    SleepMode,
)
from kagami_hal.power_controller import PowerController

from .config import get_virtual_config

logger = logging.getLogger(__name__)


class VirtualPower(PowerController):
    """Virtual power management implementation for testing."""

    def __init__(self) -> None:
        """Initialize virtual power."""
        self._config = get_virtual_config()
        self._current_mode = PowerMode.BALANCED
        self._battery_level = 100.0
        self._charging = True
        self._plugged = True
        self._start_time = self._config.get_time()
        self._total_wh = 0.0
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize power management."""
        self._start_time = self._config.get_time()
        self._initialized = True
        logger.info("✅ Virtual power initialized")
        return True

    async def get_battery_status(self) -> BatteryStatus:
        """Get battery status."""
        # Simulate battery behavior
        elapsed = self._config.get_time() - self._start_time

        if not self._charging and not self._plugged:
            # Simulate discharge (5% per hour)
            drain = (elapsed / 3600) * 5
            self._battery_level = max(0, 100 - drain)
        elif self._charging:
            # Simulate charging (10% per hour)
            charge = (elapsed / 3600) * 10
            self._battery_level = min(100, self._battery_level + charge)

        return BatteryStatus(
            level=self._battery_level,
            voltage=3.7 + 0.5 * (self._battery_level / 100),  # 3.7-4.2V
            charging=self._charging,
            plugged=self._plugged,
            time_remaining_minutes=int((self._battery_level / 5) * 60)
            if not self._plugged
            else None,
            temperature_c=25.0 + (5.0 if self._charging else 0.0),
        )

    async def get_battery_level(self) -> float:
        """Get current battery level percentage."""
        status = await self.get_battery_status()
        return status.level

    def set_battery_state(
        self,
        level: float | None = None,
        charging: bool | None = None,
        plugged: bool | None = None,
    ) -> None:
        """Set battery state for testing."""
        if level is not None:
            self._battery_level = level
        if charging is not None:
            self._charging = charging
        if plugged is not None:
            self._plugged = plugged
        self._start_time = self._config.get_time()

    async def set_power_mode(self, mode: PowerMode) -> None:
        """Set system power mode."""
        self._current_mode = mode
        logger.debug(f"Virtual power mode: {mode.value}")

    async def get_power_mode(self) -> PowerMode:
        """Get current power mode."""
        return self._current_mode

    async def set_cpu_frequency(self, freq_mhz: int) -> None:
        """Set CPU frequency (simulated)."""
        logger.debug(f"Virtual CPU frequency: {freq_mhz} MHz")

    async def sleep(
        self, duration_ms: int | None = None, mode: SleepMode = SleepMode.LIGHT
    ) -> None:
        """Enter sleep mode (simulated)."""
        logger.info(f"Virtual sleep mode: {mode.value} for {duration_ms}ms")
        # In a real implementation, could pause processing

    async def enter_sleep(self, mode: SleepMode, duration_ms: int | None = None) -> None:
        """Enter sleep mode (simulated)."""
        await self.sleep(duration_ms, mode)

    async def get_power_stats(self) -> PowerStats:
        """Get power consumption statistics."""
        elapsed = self._config.get_time() - self._start_time

        # Simulate power consumption based on mode
        base_watts = {
            PowerMode.FULL: 15.0,
            PowerMode.BALANCED: 8.0,
            PowerMode.SAVER: 4.0,
            PowerMode.CRITICAL: 2.0,
        }.get(self._current_mode, 8.0)

        current_watts = base_watts + 2.0 * (self._battery_level / 100)
        self._total_wh += current_watts * (elapsed / 3600)

        return PowerStats(
            current_watts=current_watts,
            avg_watts=base_watts,
            peak_watts=base_watts * 1.5,
            total_wh=self._total_wh,
        )

    async def shutdown(self) -> None:
        """Shutdown power controller."""
        self._initialized = False
        logger.info("Virtual power shutdown")
