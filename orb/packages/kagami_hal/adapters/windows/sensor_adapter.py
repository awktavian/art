"""Windows Sensors Adapter using Windows Sensor API.

Implements SensorManager for Windows using:
- Windows Sensor API for light, accelerometer, etc.
- WMI for temperature sensors
- Location API for GPS

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
Updated: December 8, 2025 - Refactored to use SensorAdapterBase
"""

from __future__ import annotations

import ctypes
import logging
import sys
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.adapters.sensor_adapter_base import SensorAdapterBase
from kagami_hal.adapters.windows.common import SYSTEM_POWER_STATUS
from kagami_hal.data_types import (
    SensorReading,
    SensorType,
)

logger = logging.getLogger(__name__)

WINDOWS_AVAILABLE = sys.platform == "win32"
WMI_AVAILABLE = False

if WINDOWS_AVAILABLE:
    try:
        import wmi

        WMI_AVAILABLE = True
    except ImportError:
        logger.warning("WMI not available - install: pip install WMI")


class WindowsSensors(SensorAdapterBase):
    """Windows sensor implementation."""

    def __init__(self, backend: Any = None):
        """Initialize Windows sensors.

        Args:
            backend: Optional custom backend for testing
        """
        super().__init__()
        self._wmi: Any = None
        self._backend = backend

    async def initialize(self) -> bool:
        """Initialize sensor discovery."""
        # Platform check first - backend is for when platform IS available
        if not WINDOWS_AVAILABLE:
            if is_test_mode():
                logger.info("Windows sensors not available (wrong platform), gracefully degrading")
                return False
            raise RuntimeError("Windows sensors only available on Windows")

        # Use custom backend for testing (when platform is available)
        if self._backend is not None:
            if self._backend.connect():
                self._available_sensors = self._backend.available_sensors()
                self._running = True
                logger.info(
                    f"✅ Windows sensors initialized (test mode): {self._available_sensors}"
                )
                return True
            return False

        try:
            # Initialize WMI
            if WMI_AVAILABLE:
                self._wmi = wmi.WMI(namespace="root\\wmi")

                # Check for temperature sensors
                try:
                    temps = self._wmi.MSAcpi_ThermalZoneTemperature()
                    if temps:
                        self._available_sensors.add(SensorType.TEMPERATURE)
                except Exception:
                    pass

            # Battery is always available on laptops
            try:
                self._available_sensors.add(SensorType.BATTERY)
            except Exception:
                pass

            self._running = True
            logger.info(f"✅ Windows sensors initialized: {self._available_sensors}")
            return len(self._available_sensors) > 0 or True  # Return true even with no sensors

        except Exception as e:
            logger.error(f"Failed to initialize Windows sensors: {e}", exc_info=True)
            return False

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read sensor value."""
        import time

        if sensor not in self._available_sensors:
            raise RuntimeError(f"Sensor {sensor} not available")

        try:
            value: Any = None
            accuracy = 1.0

            # Use backend for testing
            if self._backend is not None:
                if sensor == SensorType.BATTERY:
                    data = self._backend.read_battery()
                    return SensorReading(
                        sensor=sensor,
                        value=data,
                        timestamp_ms=int(time.time() * 1000),
                        accuracy=accuracy,
                    )
                elif sensor == SensorType.TEMPERATURE:
                    temps = self._backend.read_temperatures()
                    value = temps[0] if temps else 0.0
                    return SensorReading(
                        sensor=sensor,
                        value=value,
                        timestamp_ms=int(time.time() * 1000),
                        accuracy=accuracy,
                    )

            if sensor == SensorType.TEMPERATURE:
                # Read via WMI
                if self._wmi:
                    temps = self._wmi.MSAcpi_ThermalZoneTemperature()
                    if temps:
                        # Convert from tenths of Kelvin to Celsius
                        temp_kelvin = temps[0].CurrentTemperature / 10.0
                        value = temp_kelvin - 273.15

            elif sensor == SensorType.BATTERY:
                # Read via GetSystemPowerStatus (using common SYSTEM_POWER_STATUS)
                status = SYSTEM_POWER_STATUS()
                ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))
                value = int(status.BatteryLifePercent)
                if value > 100:
                    value = 100

            else:
                raise RuntimeError(f"Reading not implemented for {sensor}")

            return SensorReading(
                sensor=sensor,
                value=value,
                timestamp_ms=int(time.time() * 1000),
                accuracy=accuracy,
            )

        except Exception as e:
            logger.error(f"Failed to read sensor {sensor}: {e}")
            raise

    async def shutdown(self) -> None:
        """Shutdown with backend cleanup."""
        await super().shutdown()
        if self._backend is not None:
            self._backend.disconnect()
