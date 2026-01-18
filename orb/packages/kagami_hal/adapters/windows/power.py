"""Windows Power Adapter using Win32 API and WMI.

Implements PowerController for Windows using:
- GetSystemPowerStatus for battery
- SetSuspendState for sleep modes
- WMI for power management

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
"""

from __future__ import annotations

import ctypes
import logging
import sys

from kagami.core.boot_mode import is_test_mode

from kagami_hal.adapters.windows.common import SYSTEM_POWER_STATUS
from kagami_hal.data_types import (
    BatteryStatus,
    PowerMode,
    PowerStats,
    SleepMode,
)
from kagami_hal.power_controller import PowerController

logger = logging.getLogger(__name__)

WINDOWS_AVAILABLE = sys.platform == "win32"


class WindowsPower(PowerController):
    """Windows power management implementation."""

    def __init__(self):
        """Initialize Windows power adapter."""
        self._current_mode = PowerMode.BALANCED
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize power management."""
        if not WINDOWS_AVAILABLE:
            if is_test_mode():
                logger.info("Windows power not available (wrong platform), gracefully degrading")
                return False
            raise RuntimeError("Windows power only available on Windows")

        try:
            # Test power status access
            status = SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
                self._initialized = True
                logger.info("✅ Windows power initialized")
                return True
            else:
                logger.warning("GetSystemPowerStatus failed")
                return False

        except Exception as e:
            logger.error(f"Failed to initialize Windows power: {e}", exc_info=True)
            return False

    async def get_battery_status(self) -> BatteryStatus:
        """Get battery status."""
        try:
            status = SYSTEM_POWER_STATUS()
            ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))

            # Parse status
            level = float(status.BatteryLifePercent)
            if level > 100:
                level = 100.0

            plugged = status.ACLineStatus == 1
            charging = (status.BatteryFlag & 8) != 0  # Flag 8 = charging

            # Calculate time remaining
            time_remaining = None
            if status.BatteryLifeTime != 0xFFFFFFFF:
                time_remaining = int(status.BatteryLifeTime / 60)  # seconds to minutes

            return BatteryStatus(
                level=level,
                voltage=0.0,  # Not available via this API
                charging=charging,
                plugged=plugged,
                time_remaining_minutes=time_remaining,
                temperature_c=None,  # Not available via this API
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
        """Set system power mode via power scheme.

        Note: Requires appropriate privileges for full functionality.
        """
        self._current_mode = mode

        try:
            # Map mode to power scheme GUID
            # These are standard Windows power scheme GUIDs
            scheme_map = {
                PowerMode.FULL: "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",  # High Performance
                PowerMode.BALANCED: "381b4222-f694-41f0-9685-ff5bb260df2e",  # Balanced
                PowerMode.SAVER: "a1841308-3541-4fab-bc81-f71556f20b4a",  # Power Saver
                PowerMode.CRITICAL: "a1841308-3541-4fab-bc81-f71556f20b4a",  # Power Saver
            }

            scheme_guid = scheme_map.get(mode)
            if scheme_guid:
                import subprocess

                subprocess.run(
                    ["powercfg", "/setactive", scheme_guid],
                    capture_output=True,
                    check=False,
                )

            logger.debug(f"Power mode set to {mode.value}")

        except Exception as e:
            logger.error(f"Failed to set power mode: {e}")

    async def get_power_mode(self) -> PowerMode:
        """Get current power mode."""
        return self._current_mode

    async def set_cpu_frequency(self, freq_mhz: int) -> None:
        """Set CPU frequency.

        Note: Windows manages CPU frequency automatically based on power scheme.
        This sets the maximum processor state percentage as an approximation.
        """
        try:
            # Get typical max frequency (assume 4000 MHz max)
            max_freq = 4000
            percentage = min(100, int((freq_mhz / max_freq) * 100))

            import subprocess

            # Set max processor state
            subprocess.run(
                [
                    "powercfg",
                    "/setacvalueindex",
                    "SCHEME_CURRENT",
                    "SUB_PROCESSOR",
                    "PROCTHROTTLEMAX",
                    str(percentage),
                ],
                capture_output=True,
                check=False,
            )

            subprocess.run(
                ["powercfg", "/setactive", "SCHEME_CURRENT"],
                capture_output=True,
                check=False,
            )

            logger.debug(f"CPU max state set to {percentage}%")

        except Exception as e:
            logger.error(f"Failed to set CPU frequency: {e}")

    async def enter_sleep(self, mode: SleepMode, duration_ms: int | None = None) -> None:
        """Enter sleep mode.

        Args:
            mode: Sleep mode to enter
            duration_ms: Optional duration (wake timer)
        """
        try:
            if mode == SleepMode.NONE:
                return

            # Set wake timer if duration specified
            if duration_ms:
                # Would use CreateWaitableTimer and SetWaitableTimer
                # Simplified: just log warning
                logger.warning(f"Timed wake after {duration_ms}ms requested but not implemented")

            # Determine sleep type
            if mode == SleepMode.HIBERNATE:
                # Hibernate = SetSuspendState(TRUE, FALSE, FALSE)
                ctypes.windll.powrprof.SetSuspendState(True, False, False)
            elif mode in (SleepMode.LIGHT, SleepMode.DEEP):
                # Sleep = SetSuspendState(FALSE, FALSE, FALSE)
                ctypes.windll.powrprof.SetSuspendState(False, False, False)

            logger.info(f"Entering sleep mode: {mode.value}")

        except Exception as e:
            logger.error(f"Failed to enter sleep mode: {e}")

    async def get_power_stats(self) -> PowerStats:
        """Get power consumption statistics.

        Note: Detailed power stats require hardware monitoring libraries.
        """
        # Windows doesn't provide easy access to power consumption
        # Would need to use HWiNFO, Open Hardware Monitor, or similar

        return PowerStats(
            current_watts=0.0,
            avg_watts=0.0,
            peak_watts=0.0,
            total_wh=0.0,
        )

    async def shutdown(self) -> None:
        """Shutdown power controller."""
        self._initialized = False
        logger.info("✅ Windows power shutdown")
