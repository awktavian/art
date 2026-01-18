"""Power Controller HAL for K os.

Unified interface for power management across platforms.

Features:
- Battery monitoring
- DVFS (Dynamic Voltage/Frequency Scaling)
- Sleep modes (light sleep, deep sleep)
- Wake-on-interrupt

Created: November 10, 2025
"""

from __future__ import annotations

from abc import ABC, abstractmethod

# Import types from centralized data_types to avoid duplication
from kagami_hal.data_types import (
    BatteryStatus,
    PowerMode,
    PowerStats,
    SleepMode,
)

# Re-export for backwards compatibility
__all__ = ["BatteryStatus", "PowerController", "PowerMode", "PowerStats", "SleepMode"]


class PowerController(ABC):
    """Abstract power controller interface."""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize power controller.

        Returns:
            True if successful
        """

    @abstractmethod
    async def get_battery_status(self) -> BatteryStatus:
        """Get battery status.

        Returns:
            Battery status
        """

    @abstractmethod
    async def set_power_mode(self, mode: PowerMode) -> None:
        """Set system power mode.

        Args:
            mode: Power mode
        """

    @abstractmethod
    async def get_power_mode(self) -> PowerMode:
        """Get current power mode.

        Returns:
            Current power mode
        """

    @abstractmethod
    async def set_cpu_frequency(self, freq_mhz: int) -> None:
        """Set CPU frequency (DVFS).

        Args:
            freq_mhz: Frequency in MHz
        """

    @abstractmethod
    async def enter_sleep(self, mode: SleepMode, duration_ms: int | None = None) -> None:
        """Enter sleep mode.

        Args:
            mode: Sleep mode
            duration_ms: Sleep duration (None = wake on interrupt)
        """

    @abstractmethod
    async def get_power_stats(self) -> PowerStats:
        """Get power consumption statistics.

        Returns:
            Power statistics
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown power controller."""
