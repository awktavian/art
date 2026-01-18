"""iOS Power Adapter using UIDevice and IOKit.

Implements PowerController for iOS using:
- UIDevice for battery status
- IOKit for power management (limited)

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import (
    BatteryStatus,
    PowerMode,
    PowerStats,
    SleepMode,
)
from kagami_hal.power_controller import PowerController

logger = logging.getLogger(__name__)

IOS_AVAILABLE = sys.platform == "darwin" and (
    os.uname().machine.startswith("iP") or os.environ.get("KAGAMI_PLATFORM") == "ios"
)


class iOSPower(PowerController):
    """iOS power management implementation."""

    def __init__(self):
        """Initialize iOS power adapter."""
        self._current_mode = PowerMode.BALANCED
        self._device: Any = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize power management."""
        if not IOS_AVAILABLE:
            if is_test_mode():
                logger.info("iOS power not available, gracefully degrading")
                return False
            raise RuntimeError("iOS power only available on iOS")

        try:
            from UIKit import UIDevice

            self._device = UIDevice.currentDevice()
            self._device.setBatteryMonitoringEnabled_(True)

            self._initialized = True
            logger.info("✅ iOS power initialized")
            return True

        except ImportError:
            logger.error("UIKit not available")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize iOS power: {e}", exc_info=True)
            return False

    async def get_battery_status(self) -> BatteryStatus:
        """Get battery status."""
        if not self._device:
            return BatteryStatus(
                level=100.0,
                voltage=0.0,
                charging=False,
                plugged=True,
                time_remaining_minutes=None,
                temperature_c=None,
            )

        try:
            # Battery level (-1 if unknown, 0-1 otherwise)
            level = self._device.batteryLevel()
            if level < 0:
                level = 1.0
            level = level * 100

            # Battery state
            state = self._device.batteryState()
            # 0 = Unknown, 1 = Unplugged, 2 = Charging, 3 = Full
            charging = state == 2
            plugged = state in (2, 3)

            return BatteryStatus(
                level=level,
                voltage=0.0,  # Not available on iOS
                charging=charging,
                plugged=plugged,
                time_remaining_minutes=None,  # Not available on iOS
                temperature_c=None,  # Not available via UIDevice
            )

        except Exception as e:
            logger.error(f"Failed to get battery status: {e}")
            return BatteryStatus(
                level=100.0,
                voltage=0.0,
                charging=False,
                plugged=True,
                time_remaining_minutes=None,
                temperature_c=None,
            )

    async def set_power_mode(self, mode: PowerMode) -> None:
        """Set system power mode.

        Note: iOS manages power automatically. Apps cannot directly control
        system power mode, but can request Low Power Mode.
        """
        self._current_mode = mode

        if mode == PowerMode.SAVER:
            # Could present UI to enable Low Power Mode
            logger.debug("Power saver mode requested (iOS manages automatically)")
        else:
            logger.debug(f"Power mode {mode.value} (iOS manages automatically)")

    async def get_power_mode(self) -> PowerMode:
        """Get current power mode."""
        try:
            from Foundation import NSProcessInfo

            info = NSProcessInfo.processInfo()
            if info.isLowPowerModeEnabled():
                return PowerMode.SAVER
        except Exception:
            pass

        return self._current_mode

    async def set_cpu_frequency(self, freq_mhz: int) -> None:
        """Set CPU frequency.

        Note: iOS does not allow apps to control CPU frequency.
        """
        logger.warning("CPU frequency control not available on iOS")

    async def enter_sleep(self, mode: SleepMode, duration_ms: int | None = None) -> None:
        """Enter sleep mode.

        Note: iOS apps cannot put the device to sleep.
        They can only respond to system sleep events.
        """
        logger.warning("Sleep mode control not available on iOS apps")

    async def get_power_stats(self) -> PowerStats:
        """Get power consumption statistics.

        Note: Detailed power stats not available on iOS.
        """
        return PowerStats(
            current_watts=0.0,
            avg_watts=0.0,
            peak_watts=0.0,
            total_wh=0.0,
        )

    async def shutdown(self) -> None:
        """Shutdown power controller."""
        if self._device:
            try:
                self._device.setBatteryMonitoringEnabled_(False)
            except Exception:
                pass

        self._initialized = False
        logger.info("✅ iOS power shutdown")
