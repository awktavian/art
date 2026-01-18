"""HAL Sensor Interfaces.

Defines protocols and data types for sensor reading.

Sensors are the "η → s" side of the Markov blanket - they observe the environment.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import numpy as np

from kagami_hal.interface.platform import PowerMode

if TYPE_CHECKING:
    from numpy.typing import NDArray


class SensorType(Enum):
    """Types of sensors supported by the HAL."""

    # Motion/Position
    accelerometer = "accelerometer"
    gyroscope = "gyroscope"
    magnetometer = "magnetometer"
    imu = "imu"
    gps = "gps"

    # Environmental
    temperature = "temperature"
    humidity = "humidity"
    pressure = "pressure"
    light = "light"

    # Vision
    camera = "camera"
    depth_camera = "depth_camera"
    infrared = "infrared"

    # Audio
    microphone = "microphone"

    # Smart home
    motion_detector = "motion_detector"

    # Aliases with standard naming
    ACCELEROMETER = "accelerometer"
    GYROSCOPE = "gyroscope"
    MAGNETOMETER = "magnetometer"
    IMU = "imu"
    GPS = "gps"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    PRESSURE = "pressure"
    LIGHT = "light"
    CAMERA = "camera"
    DEPTH_CAMERA = "depth_camera"
    INFRARED = "infrared"
    MICROPHONE = "microphone"
    MOTION_DETECTOR = "motion_detector"
    GENERIC = "generic"


@dataclass
class SensorCapability:
    """Capabilities and specifications of a sensor."""

    sensor_type: SensorType
    sample_rate_hz: float
    min_sample_rate_hz: float = 1.0
    resolution: float = 0.001  # Smallest measurable change
    range_min: float = -1.0
    range_max: float = 1.0
    accuracy: float = 0.01  # Typical error
    latency_ms: float = 10.0  # Measurement latency
    data_shape: tuple[int, ...] = (1,)  # Shape of each reading
    dtype: type = np.float32  # Data type
    power_modes: list[PowerMode] = field(default_factory=lambda: [PowerMode.BALANCED])
    units: str = ""  # Measurement units
    metadata: dict[str, Any] = field(default_factory=dict)

    def supports_power_mode(self, mode: PowerMode) -> bool:
        """Check if this sensor supports a power mode."""
        return mode in self.power_modes

    def validate_sample_rate(self, rate_hz: float) -> bool:
        """Check if a sample rate is valid for this sensor."""
        return self.min_sample_rate_hz <= rate_hz <= self.sample_rate_hz


@dataclass
class SensorReading:
    """A timestamped sensor reading."""

    sensor_type: SensorType
    timestamp: datetime
    values: NDArray[np.float32]  # Shape: data_shape
    quality: float = 1.0  # Signal quality 0-1
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def value(self) -> float:
        """Get scalar value for 1D sensors."""
        if self.values.size == 1:
            return float(self.values.flat[0])
        raise ValueError("Sensor has multiple dimensions, use .values")


@runtime_checkable
class ISensor(Protocol):
    """Protocol for sensor implementations.

    All sensors must implement this interface to work with HAL.
    """

    async def initialize(self) -> None:
        """Initialize the sensor hardware."""
        ...

    async def shutdown(self) -> None:
        """Shut down the sensor."""
        ...

    async def get_capabilities(self) -> SensorCapability:
        """Get the sensor's capabilities and specifications."""
        ...

    async def read_once(self) -> NDArray[np.float32]:
        """Read the current sensor value once.

        Returns:
            Array of sensor values
        """
        ...

    async def stream(
        self,
        rate_hz: float | None = None,
        buffer_size: int = 10,
    ) -> AsyncIterator[NDArray[np.float32]]:
        """Stream sensor readings at the specified rate.

        Args:
            rate_hz: Sample rate (uses sensor default if None)
            buffer_size: Buffer size for streaming

        Yields:
            Sensor readings as arrays
        """
        ...

    async def set_power_mode(self, mode: PowerMode) -> None:
        """Set the sensor's power mode."""
        ...

    async def get_power_mode(self) -> PowerMode:
        """Get the sensor's current power mode."""
        ...

    async def calibrate(self) -> bool:
        """Calibrate the sensor.

        Returns:
            True if calibration succeeded
        """
        ...
