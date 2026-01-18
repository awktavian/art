"""Power Manager with DVFS and Sleep Mode Support.

Now uses HAL PowerController adapters instead of direct psutil calls.

Implements:
- Dynamic Voltage/Frequency Scaling (DVFS)
- CPU frequency governor control
- Sleep modes (light, deep, hibernate)
- Wake-on-interrupt
- Battery optimization

Created: November 10, 2025
Updated: November 10, 2025 - Refactored to use HAL
"""

from __future__ import annotations

import asyncio
import logging

from kagami_hal.power_controller import (
    BatteryStatus,
    PowerController,
    PowerMode,
    PowerStats,
    SleepMode,
)

logger = logging.getLogger(__name__)


class PowerManager(PowerController):
    """Power manager that delegates to HAL adapters."""

    """System power manager with DVFS.

    Platform support:
    - Linux: cpufreq, /sys/class/power_supply
    - macOS: IOKit (partial)
    - Mock mode for development
    """

    def __init__(self) -> None:
        """Initialize power manager."""
        self._hal_adapter: PowerController | None = None

    async def initialize(self) -> bool:
        """Initialize power manager using HAL adapter."""
        try:
            from kagami_hal.manager import get_hal_manager

            hal = await get_hal_manager()
            self._hal_adapter = hal.power  # type: ignore[assignment]

            if self._hal_adapter:
                logger.info("✅ Power manager initialized with HAL adapter")
                return True
            else:
                logger.warning("⚠️  No HAL power adapter available - limited functionality")
                return True  # Continue with limited functionality

        except Exception as e:
            logger.error(f"Failed to initialize power manager: {e}", exc_info=True)
            return False

    async def get_battery_status(self) -> BatteryStatus:
        """Get battery status via HAL adapter."""
        if self._hal_adapter:
            return await self._hal_adapter.get_battery_status()

        # Fallback to psutil if no HAL adapter
        try:
            import psutil

            battery = psutil.sensors_battery()
            if battery is None:
                return BatteryStatus(1.0, 0.0, True, True, None, None)
            return BatteryStatus(
                battery.percent / 100.0,
                0.0,
                battery.power_plugged,
                battery.power_plugged,
                battery.secsleft // 60 if battery.secsleft != -1 else None,
                None,
            )
        except Exception as e:
            logger.error(f"Battery status failed: {e}")
            return BatteryStatus(1.0, 0.0, True, True, None, None)

    async def set_power_mode(self, mode: PowerMode) -> None:
        """Set system power mode via HAL adapter."""
        if self._hal_adapter:
            await self._hal_adapter.set_power_mode(mode)
        else:
            logger.warning("No HAL power adapter - power mode not changed")

    async def get_power_mode(self) -> PowerMode:
        """Get current power mode via HAL adapter."""
        if self._hal_adapter:
            return await self._hal_adapter.get_power_mode()
        return PowerMode.FULL

    async def set_cpu_frequency(self, freq_mhz: int) -> None:
        """Set CPU frequency via HAL adapter."""
        if self._hal_adapter:
            await self._hal_adapter.set_cpu_frequency(freq_mhz)
        else:
            logger.warning("No HAL power adapter - CPU frequency not changed")

    async def enter_sleep(self, mode: SleepMode, duration_ms: int | None = None) -> None:
        """Enter sleep mode via HAL adapter."""
        if self._hal_adapter:
            await self._hal_adapter.enter_sleep(mode, duration_ms)
        else:
            if duration_ms:
                await asyncio.sleep(duration_ms / 1000.0)

    async def get_power_stats(self) -> PowerStats:
        """Get power stats via HAL adapter."""
        if self._hal_adapter:
            return await self._hal_adapter.get_power_stats()
        return PowerStats(0.0, 0.0, 0.0, 0.0)

    async def shutdown(self) -> None:
        """Shutdown power manager."""
        if self._hal_adapter:
            await self._hal_adapter.shutdown()
        logger.info("✅ Power manager shutdown")


# Global power manager
_POWER_MANAGER: PowerManager | None = None


async def get_power_manager() -> PowerManager:
    """Get global power manager."""
    global _POWER_MANAGER
    if _POWER_MANAGER is None:
        _POWER_MANAGER = PowerManager()
        await _POWER_MANAGER.initialize()
    return _POWER_MANAGER
