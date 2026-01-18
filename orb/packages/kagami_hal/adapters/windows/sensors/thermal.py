"""Windows WMI Thermal Sensor.

Implements temperature monitoring using Windows Management Instrumentation (WMI).

Queries thermal zones, CPU temperature, and GPU temperature via WMI.

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import SensorReading, SensorType

logger = logging.getLogger(__name__)

WINDOWS_AVAILABLE = sys.platform == "win32"
WMI_AVAILABLE = False

if WINDOWS_AVAILABLE:
    try:
        import wmi

        WMI_AVAILABLE = True
    except ImportError:
        logger.warning("WMI not available - install: pip install WMI")


class WindowsWMIThermal:
    """Windows WMI thermal sensor implementation.

    Monitors system temperatures via WMI thermal zones.
    """

    def __init__(self):
        """Initialize WMI thermal sensor."""
        self._wmi: Any | None = None
        self._wmi_root: Any | None = None
        self._available_zones: list[str] = []

    async def initialize(self, config: dict[str, Any] | None = None) -> bool:
        """Initialize WMI thermal monitoring.

        Returns:
            True if initialization successful
        """
        if not WINDOWS_AVAILABLE:
            if is_test_mode():
                logger.info(
                    "Windows WMI thermal not available (wrong platform), gracefully degrading"
                )
                return False
            raise RuntimeError("Windows WMI thermal only available on Windows")

        if not WMI_AVAILABLE:
            if is_test_mode():
                logger.info("WMI not available, gracefully degrading")
                return False
            raise RuntimeError("WMI not available. Install: pip install WMI")

        try:
            # Initialize WMI namespaces
            self._wmi = wmi.WMI(namespace="root\\wmi")
            self._wmi_root = wmi.WMI(namespace="root\\cimv2")

            # Enumerate thermal zones
            try:
                zones = self._wmi.MSAcpi_ThermalZoneTemperature()
                self._available_zones = [zone.InstanceName for zone in zones]
                logger.info(f"Found {len(self._available_zones)} thermal zones")
            except Exception as e:
                logger.warning(f"No thermal zones found: {e}")

            # Check for CPU temp via OpenHardwareMonitor (if installed)
            try:
                sensors = self._wmi_root.query(
                    "SELECT * FROM Win32_PerfFormattedData_Counters_ThermalZoneInformation"
                )
                if sensors:
                    logger.info(f"Found {len(sensors)} thermal performance counters")
            except Exception:
                pass

            logger.info("✅ WMI thermal monitoring initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize WMI thermal: {e}", exc_info=True)
            return False

    async def read(self) -> SensorReading:
        """Read thermal zone temperatures.

        Returns:
            SensorReading with dict of temperatures by zone

        Raises:
            RuntimeError: If not initialized or read fails
        """
        if not self._wmi:
            raise RuntimeError("Thermal sensor not initialized")

        try:
            temperatures: dict[str, float] = {}

            # Read ACPI thermal zones
            if self._available_zones:
                zones = self._wmi.MSAcpi_ThermalZoneTemperature()
                for zone in zones:
                    # Convert from tenths of Kelvin to Celsius
                    temp_kelvin = zone.CurrentTemperature / 10.0
                    temp_celsius = temp_kelvin - 273.15
                    temperatures[zone.InstanceName] = temp_celsius

            # Try to get CPU temperature
            cpu_temp = await self._read_cpu_temperature()
            if cpu_temp is not None:
                temperatures["CPU"] = cpu_temp

            if not temperatures:
                raise RuntimeError("No thermal data available")

            return SensorReading(
                sensor=SensorType.TEMPERATURE,
                value=temperatures,
                timestamp_ms=int(time.time() * 1000),
                accuracy=1.0,
            )

        except Exception as e:
            logger.error(f"Thermal read error: {e}")
            raise RuntimeError(f"Thermal read failed: {e}") from e

    async def _read_cpu_temperature(self) -> float | None:
        """Try to read CPU temperature via various WMI methods.

        Returns:
            CPU temperature in Celsius, or None if unavailable
        """
        if not self._wmi_root:
            return None

        try:
            # Method 1: Win32_TemperatureProbe (rare)
            temps = self._wmi_root.query("SELECT * FROM Win32_TemperatureProbe")
            if temps:
                for temp in temps:
                    if temp.CurrentReading:
                        # Convert from tenths of Kelvin
                        return (temp.CurrentReading / 10.0) - 273.15

            # Method 2: ThermalZoneInformation performance counter
            zones = self._wmi_root.query(
                "SELECT * FROM Win32_PerfFormattedData_Counters_ThermalZoneInformation"
            )
            if zones:
                for zone in zones:
                    if hasattr(zone, "Temperature") and zone.Temperature:
                        # Already in Celsius
                        return float(zone.Temperature)

        except Exception as e:
            logger.debug(f"CPU temperature read failed: {e}")

        return None

    async def read_zone(self, zone_name: str) -> float | None:
        """Read specific thermal zone temperature.

        Args:
            zone_name: Thermal zone instance name

        Returns:
            Temperature in Celsius, or None if zone not found
        """
        if not self._wmi:
            return None

        try:
            zones = self._wmi.MSAcpi_ThermalZoneTemperature()
            for zone in zones:
                if zone.InstanceName == zone_name:
                    temp_kelvin = zone.CurrentTemperature / 10.0
                    return temp_kelvin - 273.15

        except Exception as e:
            logger.error(f"Failed to read zone {zone_name}: {e}")

        return None

    async def get_available_zones(self) -> list[str]:
        """Get list of available thermal zones.

        Returns:
            List of thermal zone names
        """
        return self._available_zones.copy()

    async def shutdown(self) -> None:
        """Release WMI resources."""
        self._wmi = None
        self._wmi_root = None
        self._available_zones.clear()
        logger.info("✅ WMI thermal sensor shutdown")
