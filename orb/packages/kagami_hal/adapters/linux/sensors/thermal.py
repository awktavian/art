"""Linux Thermal Zone Sensor.

Reads temperature from Linux thermal zones via sysfs.
Supports /sys/class/thermal/thermal_zone*/temp and lm-sensors.

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from kagami_hal.adapters.sensor_adapter_base import SensorAdapterBase
from kagami_hal.data_types import SensorReading, SensorType

logger = logging.getLogger(__name__)

THERMAL_ZONES_PATH = Path("/sys/class/thermal")


class LinuxThermal(SensorAdapterBase):
    """Linux thermal zone sensor implementation.

    Reads temperature from sysfs thermal zones.
    Each thermal zone appears as a separate TEMPERATURE sensor.
    """

    def __init__(self) -> None:
        """Initialize thermal sensor adapter."""
        super().__init__()
        self._thermal_zones: dict[int, Path] = {}

    async def initialize(self) -> bool:
        """Initialize thermal zone discovery."""
        if not THERMAL_ZONES_PATH.exists():
            logger.warning("Thermal zones not available (/sys/class/thermal missing)")
            return False

        try:
            # Discover thermal zones
            for zone_dir in THERMAL_ZONES_PATH.glob("thermal_zone*"):
                try:
                    zone_id = int(zone_dir.name.replace("thermal_zone", ""))
                    temp_file = zone_dir / "temp"

                    if temp_file.exists():
                        # Verify we can read it
                        with open(temp_file) as f:
                            _ = f.read().strip()

                        self._thermal_zones[zone_id] = temp_file
                        self._available_sensors.add(SensorType.TEMPERATURE)

                except (ValueError, OSError) as e:
                    logger.debug(f"Skipping thermal zone {zone_dir}: {e}")
                    continue

            if not self._thermal_zones:
                logger.warning("No readable thermal zones found")
                return False

            self._running = True
            logger.info(f"✅ Linux thermal zones initialized: {len(self._thermal_zones)} zones")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize thermal zones: {e}", exc_info=True)
            return False

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read temperature from first available thermal zone.

        Args:
            sensor: Must be SensorType.TEMPERATURE

        Returns:
            SensorReading with temperature in Celsius
        """
        if sensor != SensorType.TEMPERATURE:
            raise RuntimeError(f"Sensor {sensor} not supported by thermal adapter")

        if not self._thermal_zones:
            raise RuntimeError("No thermal zones available")

        try:
            # Read from first zone (usually CPU)
            zone_id = min(self._thermal_zones.keys())
            temp_file = self._thermal_zones[zone_id]

            with open(temp_file) as f:
                # Temperature is in millidegrees Celsius
                temp_millidegrees = int(f.read().strip())
                temp_celsius = temp_millidegrees / 1000.0

            return SensorReading(
                sensor=SensorType.TEMPERATURE,
                value=temp_celsius,
                timestamp_ms=int(time.time() * 1000),
                accuracy=1.0,
            )

        except Exception as e:
            logger.error(f"Failed to read thermal zone: {e}")
            raise

    async def read_zone(self, zone_id: int) -> SensorReading:
        """Read temperature from specific thermal zone.

        Args:
            zone_id: Thermal zone ID (e.g., 0 for thermal_zone0)

        Returns:
            SensorReading with temperature in Celsius

        Raises:
            RuntimeError: If zone not available
        """
        if zone_id not in self._thermal_zones:
            raise RuntimeError(f"Thermal zone {zone_id} not available")

        try:
            temp_file = self._thermal_zones[zone_id]

            with open(temp_file) as f:
                temp_millidegrees = int(f.read().strip())
                temp_celsius = temp_millidegrees / 1000.0

            return SensorReading(
                sensor=SensorType.TEMPERATURE,
                value=temp_celsius,
                timestamp_ms=int(time.time() * 1000),
                accuracy=1.0,
            )

        except Exception as e:
            logger.error(f"Failed to read thermal zone {zone_id}: {e}")
            raise

    def get_zone_info(self, zone_id: int) -> dict[str, Any]:
        """Get information about a thermal zone.

        Args:
            zone_id: Thermal zone ID

        Returns:
            Dict with keys: id, type, temp_path

        Raises:
            RuntimeError: If zone not available
        """
        if zone_id not in self._thermal_zones:
            raise RuntimeError(f"Thermal zone {zone_id} not available")

        zone_dir = THERMAL_ZONES_PATH / f"thermal_zone{zone_id}"
        type_file = zone_dir / "type"

        zone_type = "unknown"
        if type_file.exists():
            try:
                with open(type_file) as f:
                    zone_type = f.read().strip()
            except OSError:
                pass

        return {
            "id": zone_id,
            "type": zone_type,
            "temp_path": str(self._thermal_zones[zone_id]),
        }

    def list_zones(self) -> list[int]:
        """List available thermal zone IDs.

        Returns:
            List of thermal zone IDs
        """
        return sorted(self._thermal_zones.keys())


__all__ = ["LinuxThermal"]
