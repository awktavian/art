"""Windows Battery Sensor.

Implements battery monitoring using Win32 GetSystemPowerStatus API.

Provides detailed battery status including charge level, voltage estimates,
and time remaining.

Created: December 15, 2025
"""

from __future__ import annotations

import ctypes
import logging
import sys
import time

from kagami.core.boot_mode import is_test_mode

from kagami_hal.adapters.windows.common import SYSTEM_POWER_STATUS
from kagami_hal.data_types import BatteryStatus, SensorReading, SensorType

logger = logging.getLogger(__name__)

WINDOWS_AVAILABLE = sys.platform == "win32"


class WindowsBatterySensor:
    """Windows battery sensor implementation.

    Uses Win32 GetSystemPowerStatus for battery monitoring.
    """

    def __init__(self):
        """Initialize battery sensor."""
        pass

    async def initialize(self, config: dict | None = None) -> bool:
        """Initialize battery monitoring.

        Returns:
            True if initialization successful
        """
        if not WINDOWS_AVAILABLE:
            if is_test_mode():
                logger.info(
                    "Windows battery sensor not available (wrong platform), gracefully degrading"
                )
                return False
            raise RuntimeError("Windows battery sensor only available on Windows")

        try:
            # Test API access
            status = SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
                logger.info("✅ Windows battery sensor initialized")
                return True
            else:
                logger.warning("GetSystemPowerStatus failed")
                return False

        except Exception as e:
            logger.error(f"Failed to initialize battery sensor: {e}", exc_info=True)
            return False

    async def read(self) -> SensorReading:
        """Read battery status.

        Returns:
            SensorReading with BatteryStatus in value field

        Raises:
            RuntimeError: If read fails
        """
        try:
            status = SYSTEM_POWER_STATUS()
            ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))

            # Parse status
            level = float(status.BatteryLifePercent)
            if level > 100:
                level = 100.0

            # AC line status: 0=offline, 1=online, 255=unknown
            plugged = status.ACLineStatus == 1

            # Battery flag bits:
            # 1 = High (> 66%)
            # 2 = Low (< 33%)
            # 4 = Critical (< 5%)
            # 8 = Charging
            # 128 = No system battery
            # 255 = Unknown
            charging = (status.BatteryFlag & 8) != 0
            no_battery = (status.BatteryFlag & 128) != 0

            # Calculate time remaining
            time_remaining = None
            if status.BatteryLifeTime != 0xFFFFFFFF:
                time_remaining = int(status.BatteryLifeTime / 60)  # seconds to minutes

            # Estimate voltage (typical laptop battery voltages)
            # This is a rough estimate; actual voltage requires WMI or hardware access
            if level > 90:
                voltage = 12.6  # Full charge
            elif level > 50:
                voltage = 12.0 + (level - 50) * 0.015
            elif level > 20:
                voltage = 11.4 + (level - 20) * 0.02
            else:
                voltage = 10.8 + level * 0.03

            if no_battery:
                # Desktop system with no battery
                battery_status = BatteryStatus(
                    level=100.0,
                    voltage=0.0,
                    charging=False,
                    plugged=True,
                    time_remaining_minutes=None,
                    temperature_c=None,
                )
            else:
                battery_status = BatteryStatus(
                    level=level,
                    voltage=voltage,
                    charging=charging,
                    plugged=plugged,
                    time_remaining_minutes=time_remaining,
                    temperature_c=None,  # Not available via this API
                )

            return SensorReading(
                sensor=SensorType.BATTERY,
                value=battery_status,
                timestamp_ms=int(time.time() * 1000),
                accuracy=1.0,
            )

        except Exception as e:
            logger.error(f"Battery read error: {e}")
            raise RuntimeError(f"Battery read failed: {e}") from e

    async def shutdown(self) -> None:
        """Release battery sensor resources."""
        logger.info("✅ Windows battery sensor shutdown")
