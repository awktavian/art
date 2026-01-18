"""Sensor Manager HAL for K os.

Unified interface for sensor access across platforms.

Sensors:
- IMU: Accelerometer, Gyroscope
- Biometric: Heart rate, SpO2, ECG
- Environmental: GPS, Temperature, Pressure
- Power: Battery level, charging status

Created: November 10, 2025
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from kagami_hal.data_types import (
    AccelReading,
    GPSReading,
    GyroReading,
    HeartRateReading,
    SensorReading,
    SensorType,
)

__all__ = [
    "AccelReading",
    "GPSReading",
    "GyroReading",
    "HeartRateReading",
    "SensorManager",
    "SensorReading",
    "SensorType",
]


class SensorManager(ABC):
    """Abstract sensor manager interface."""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize sensor subsystem.

        Returns:
            True if successful
        """

    @abstractmethod
    async def list_sensors(self) -> list[SensorType]:
        """List available sensors.

        Returns:
            List of available sensor types
        """

    @abstractmethod
    async def read(self, sensor: SensorType) -> SensorReading:
        """Read sensor value.

        Args:
            sensor: Sensor to read

        Returns:
            Sensor reading
        """

    @abstractmethod
    async def subscribe(
        self,
        sensor: SensorType,
        callback: Callable[[SensorReading], Awaitable[None]],
        rate_hz: int = 10,
    ) -> None:
        """Subscribe to sensor updates.

        Args:
            sensor: Sensor to subscribe to
            callback: Async callback for readings
            rate_hz: Sampling rate (Hz)
        """

    @abstractmethod
    async def unsubscribe(self, sensor: SensorType) -> None:
        """Unsubscribe from sensor.

        Args:
            sensor: Sensor to unsubscribe from
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown sensor manager."""
