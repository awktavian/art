"""Virtual Sensors Adapter for testing/headless environments.

Implements SensorManager with simulated sensor data.

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
Updated: December 8, 2025 - Refactored to use SensorAdapterBase
Updated: December 15, 2025 - Configurable generation, recording mode
"""

from __future__ import annotations

import json
import logging
import math
import random

from kagami_hal.adapters.sensor_adapter_base import SensorAdapterBase
from kagami_hal.data_types import (
    AccelReading,
    GPSReading,
    GyroReading,
    SensorReading,
    SensorType,
)

from .config import get_virtual_config

logger = logging.getLogger(__name__)


class VirtualSensors(SensorAdapterBase):
    """Virtual sensor implementation for testing.

    Supports:
    - Deterministic data generation (reproducible tests)
    - Multiple generation modes (sine, random walk, constant)
    - Recording mode (save sensor data to JSONL)
    """

    def __init__(self) -> None:
        """Initialize virtual sensors."""
        super().__init__()
        self._config = get_virtual_config()

        # Pre-populate available sensors for virtual adapter
        self._available_sensors = {
            SensorType.ACCELEROMETER,
            SensorType.GYROSCOPE,
            SensorType.TEMPERATURE,
            SensorType.LIGHT,
            SensorType.GPS,
            SensorType.BATTERY,
            SensorType.SEMG,  # Virtual sEMG for gesture testing
        }
        self._simulated_values: dict[
            SensorType, float | AccelReading | GyroReading | GPSReading
        ] = {}
        self._start_time = self._config.get_time()

        # Seed RNG if deterministic mode
        if self._config.deterministic:
            random.seed(self._config.seed + 2000)  # Offset from other virtual devices

    async def initialize(self) -> bool:
        """Initialize sensors."""
        self._running = True
        self._start_time = self._config.get_time()
        logger.info("✅ Virtual sensors initialized")
        return True

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read sensor value with simulated data."""
        if sensor not in self._available_sensors:
            raise RuntimeError(f"Sensor {sensor} not available")

        timestamp = int(self._config.get_time() * 1000)
        elapsed = self._config.get_time() - self._start_time

        # Use simulated value if set, otherwise generate
        value = self._simulated_values.get(sensor)

        if value is None:
            if sensor == SensorType.ACCELEROMETER:
                # Simulate slight vibration with gravity on Z
                value = AccelReading(
                    x=0.1 * math.sin(elapsed * 2),
                    y=0.1 * math.cos(elapsed * 2),
                    z=9.81 + 0.05 * math.sin(elapsed * 10),
                )

            elif sensor == SensorType.GYROSCOPE:
                # Simulate slow rotation
                value = GyroReading(
                    x=0.01 * math.sin(elapsed),
                    y=0.01 * math.cos(elapsed),
                    z=0.005 * math.sin(elapsed * 0.5),
                )

            elif sensor == SensorType.TEMPERATURE:
                # Simulate room temperature with slight variation
                value = 22.0 + 0.5 * math.sin(elapsed * 0.1)

            elif sensor == SensorType.LIGHT:
                # Simulate day/night cycle (sped up)
                value = 500.0 + 400.0 * math.sin(elapsed * 0.01)
                value = max(0.0, value)

            elif sensor == SensorType.GPS:
                # Simulate slight GPS drift
                base_lat = 37.7749
                base_lon = -122.4194
                value = GPSReading(
                    latitude=base_lat + 0.0001 * math.sin(elapsed * 0.1),
                    longitude=base_lon + 0.0001 * math.cos(elapsed * 0.1),
                    altitude=10.0,
                    accuracy=5.0,
                )

            elif sensor == SensorType.BATTERY:
                # Simulate slow battery drain
                value = max(0, 100 - (elapsed / 3600) * 10)  # 10% per hour

            elif sensor == SensorType.SEMG:
                # Simulate 8-channel sEMG with muscle noise patterns
                # Typical neural wristband has 8 channels
                channels = []
                for ch in range(8):
                    # Base noise + channel-specific signal
                    base = 0.1 * math.sin(elapsed * 5 + ch * 0.5)
                    noise = 0.05 * (random.random() - 0.5)
                    channels.append(max(0.0, min(1.0, 0.3 + base + noise)))
                value = channels  # type: ignore[assignment]

            else:
                value = 0.0

        reading = SensorReading(
            sensor=sensor,
            value=value,
            timestamp_ms=timestamp,
            accuracy=1.0,
        )

        # Record if enabled
        if self._config.record_mode:
            self._record_reading(reading)

        return reading

    async def read_accelerometer(self) -> AccelReading:
        """Read accelerometer data."""
        reading = await self.read(SensorType.ACCELEROMETER)
        return reading.value

    async def read_gyroscope(self) -> GyroReading:
        """Read gyroscope data."""
        reading = await self.read(SensorType.GYROSCOPE)
        return reading.value

    async def read_gps(self) -> GPSReading:
        """Read GPS data."""
        reading = await self.read(SensorType.GPS)
        return reading.value

    def _record_reading(self, reading: SensorReading) -> None:
        """Record sensor reading to disk (JSONL format).

        Args:
            reading: Sensor reading to record
        """
        try:
            output_path = self._config.output_dir / "sensors" / f"{reading.sensor.value}.jsonl"

            # Convert reading to dict for JSON serialization
            value_dict: dict
            if isinstance(reading.value, AccelReading | GyroReading | GPSReading):
                value_dict = reading.value.__dict__
            else:
                value_dict = {"value": reading.value}

            record = {
                "sensor": reading.sensor.value,
                "timestamp_ms": reading.timestamp_ms,
                "accuracy": reading.accuracy,
                **value_dict,
            }

            with open(output_path, "a") as f:
                f.write(json.dumps(record) + "\n")

        except Exception as e:
            logger.warning(f"Failed to record sensor reading: {e}")

    def set_simulated_value(
        self, sensor: SensorType, value: float | AccelReading | GyroReading | GPSReading
    ) -> None:
        """Set a simulated value for testing."""
        self._simulated_values[sensor] = value

    def clear_simulated_value(self, sensor: SensorType) -> None:
        """Clear simulated value, return to generated."""
        self._simulated_values.pop(sensor, None)
