"""Android Sensors Adapter using SensorManager.

Implements SensorManager for Android using Pyjnius (JNI).

Supports:
- Accelerometer (TYPE_ACCELEROMETER)
- Gyroscope (TYPE_GYROSCOPE)
- Magnetometer (TYPE_MAGNETIC_FIELD)
- Light (TYPE_LIGHT)
- Proximity (TYPE_PROXIMITY)
- Gravity (TYPE_GRAVITY)
- Linear Acceleration (TYPE_LINEAR_ACCELERATION)
- Rotation Vector (TYPE_ROTATION_VECTOR)

Created: November 10, 2025
Updated: January 12, 2026 - Added magnetometer, gravity, and rotation vector support
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, ClassVar

from kagami.core.boot_mode import is_test_mode

from kagami_hal.adapters.sensor_adapter_base import SensorAdapterBase
from kagami_hal.data_types import (
    AccelReading,
    GyroReading,
    SensorReading,
    SensorType,
)

logger = logging.getLogger(__name__)

ANDROID_AVAILABLE = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ
JNI_AVAILABLE = False

# Android sensor type constants (fallback if JNI not available)
SENSOR_TYPE_ACCELEROMETER = 1
SENSOR_TYPE_MAGNETIC_FIELD = 2
SENSOR_TYPE_GYROSCOPE = 4
SENSOR_TYPE_LIGHT = 5
SENSOR_TYPE_PROXIMITY = 8
SENSOR_TYPE_GRAVITY = 9
SENSOR_TYPE_LINEAR_ACCELERATION = 10
SENSOR_TYPE_ROTATION_VECTOR = 11

if ANDROID_AVAILABLE:
    try:
        from jnius import PythonJavaClass, autoclass, java_method

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        Sensor = autoclass("android.hardware.Sensor")
        SensorManagerAndroid = autoclass("android.hardware.SensorManager")
        JNI_AVAILABLE = True

        # Update constants from actual Android API
        SENSOR_TYPE_ACCELEROMETER = Sensor.TYPE_ACCELEROMETER
        SENSOR_TYPE_MAGNETIC_FIELD = Sensor.TYPE_MAGNETIC_FIELD
        SENSOR_TYPE_GYROSCOPE = Sensor.TYPE_GYROSCOPE
        SENSOR_TYPE_LIGHT = Sensor.TYPE_LIGHT
        SENSOR_TYPE_PROXIMITY = Sensor.TYPE_PROXIMITY
        SENSOR_TYPE_GRAVITY = Sensor.TYPE_GRAVITY
        SENSOR_TYPE_LINEAR_ACCELERATION = Sensor.TYPE_LINEAR_ACCELERATION
        SENSOR_TYPE_ROTATION_VECTOR = Sensor.TYPE_ROTATION_VECTOR
    except ImportError:
        logger.warning("Pyjnius not available")


@dataclass
class MagnetometerReading:
    """Magnetometer reading in microtesla (uT)."""

    x: float
    y: float
    z: float

    @property
    def magnitude(self) -> float:
        """Return the magnitude of the magnetic field vector."""
        return (self.x**2 + self.y**2 + self.z**2) ** 0.5


@dataclass
class RotationReading:
    """Rotation vector reading (quaternion components)."""

    x: float  # x * sin(θ/2)
    y: float  # y * sin(θ/2)
    z: float  # z * sin(θ/2)
    w: float  # cos(θ/2) (scalar component)


@dataclass
class GravityReading:
    """Gravity vector reading in m/s²."""

    x: float
    y: float
    z: float


class AndroidSensors(SensorAdapterBase):
    """Android sensor adapter using SensorAdapterBase for common functionality.

    Provides direct JNI access to Android hardware sensors via Pyjnius.
    Supports accelerometer, gyroscope, magnetometer, light, proximity,
    gravity, linear acceleration, and rotation vector sensors.
    """

    def __init__(self) -> None:
        super().__init__()
        self._sensors: dict[SensorType, Any] = {}
        self._sensor_manager: Any = None
        self._sensor_listener: Any = None
        self._android_to_kagami: dict[int, SensorType] = {}

    async def initialize(self) -> bool:
        """Initialize Android sensors using SensorAdapterBase pattern."""
        if not ANDROID_AVAILABLE:
            if is_test_mode():
                logger.info("Android Sensors not available (wrong platform), gracefully degrading")
                return False
            raise RuntimeError("Android Sensors only available on Android")

        if not JNI_AVAILABLE:
            if is_test_mode():
                logger.info("Pyjnius not available, gracefully degrading")
                return False
            raise RuntimeError("Pyjnius not available")

        try:
            activity = PythonActivity.mActivity
            self._sensor_manager = activity.getSystemService(Context.SENSOR_SERVICE)

            # Build mapping of Android sensor types to Kagami types
            sensor_map = [
                (SENSOR_TYPE_ACCELEROMETER, SensorType.ACCELEROMETER),
                (SENSOR_TYPE_GYROSCOPE, SensorType.GYROSCOPE),
                (SENSOR_TYPE_MAGNETIC_FIELD, SensorType.MAGNETOMETER),
                (SENSOR_TYPE_LIGHT, SensorType.LIGHT),
                (SENSOR_TYPE_PROXIMITY, SensorType.PROXIMITY),
                (SENSOR_TYPE_GRAVITY, SensorType.GRAVITY),
                (SENSOR_TYPE_LINEAR_ACCELERATION, SensorType.LINEAR_ACCELERATION),
                (SENSOR_TYPE_ROTATION_VECTOR, SensorType.ROTATION),
            ]

            # Check which sensors are available
            for android_type, kagami_type in sensor_map:
                sensor = self._sensor_manager.getDefaultSensor(android_type)
                if sensor:
                    self._available_sensors.add(kagami_type)
                    self._android_to_kagami[android_type] = kagami_type
                    self._sensors[kagami_type] = sensor
                    logger.debug(f"Found sensor: {kagami_type.name}")

            # Define listener class for sensor events
            class SensorListener(PythonJavaClass):
                __javainterfaces__: ClassVar[list[str]] = ["android/hardware/SensorEventListener"]

                def __init__(self, parent):
                    super().__init__()
                    self.parent = parent

                @java_method("(Landroid/hardware/SensorEvent;)V")
                def onSensorChanged(self, event):  # noqa: N802 (Java interface requirement)
                    self.parent._on_sensor_changed(event)

                @java_method("(Landroid/hardware/Sensor;I)V")
                def onAccuracyChanged(self, sensor, accuracy):  # noqa: N802 (Java interface requirement)
                    self.parent._on_accuracy_changed(sensor, accuracy)

            self._sensor_listener = SensorListener(self)

            self._running = True
            logger.info(
                f"✅ Android sensors initialized: {[s.name for s in self._available_sensors]}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Android sensors: {e}", exc_info=True)
            return False

    def _on_accuracy_changed(self, sensor: Any, accuracy: int) -> None:
        """Handle accuracy changes for sensors."""
        s_type = sensor.getType()
        if s_type in self._android_to_kagami:
            kagami_type = self._android_to_kagami[s_type]
            logger.debug(f"Sensor {kagami_type.name} accuracy changed to {accuracy}")

    def _on_sensor_changed(self, event):
        """Handle Java sensor event.

        Converts Android sensor events to Kagami SensorReading objects
        and dispatches to subscribers.
        """
        s_type = event.sensor.getType()

        # Skip if we don't have a mapping for this sensor type
        if s_type not in self._android_to_kagami:
            return

        c_type = self._android_to_kagami[s_type]
        values = event.values
        value: (
            AccelReading
            | GyroReading
            | MagnetometerReading
            | GravityReading
            | RotationReading
            | float
            | None
        ) = None

        # Parse values based on sensor type
        if s_type == SENSOR_TYPE_ACCELEROMETER:
            value = AccelReading(x=values[0], y=values[1], z=values[2])

        elif s_type == SENSOR_TYPE_GYROSCOPE:
            value = GyroReading(x=values[0], y=values[1], z=values[2])

        elif s_type == SENSOR_TYPE_MAGNETIC_FIELD:
            value = MagnetometerReading(x=values[0], y=values[1], z=values[2])

        elif s_type == SENSOR_TYPE_LIGHT:
            value = float(values[0])  # lux

        elif s_type == SENSOR_TYPE_PROXIMITY:
            value = float(values[0])  # cm (often binary: 0 or max range)

        elif s_type == SENSOR_TYPE_GRAVITY:
            value = GravityReading(x=values[0], y=values[1], z=values[2])

        elif s_type == SENSOR_TYPE_LINEAR_ACCELERATION:
            # Linear acceleration excludes gravity
            value = AccelReading(x=values[0], y=values[1], z=values[2])

        elif s_type == SENSOR_TYPE_ROTATION_VECTOR:
            # Rotation vector as quaternion (x, y, z, w)
            # Note: values[3] may not exist on older devices
            w = (
                values[3]
                if len(values) > 3
                else (1.0 - values[0] ** 2 - values[1] ** 2 - values[2] ** 2) ** 0.5
            )
            value = RotationReading(x=values[0], y=values[1], z=values[2], w=w)

        if value is not None:
            reading = SensorReading(
                sensor=c_type,
                value=value,
                timestamp_ms=int(event.timestamp / 1000000),  # ns to ms
                accuracy=float(event.accuracy),
            )

            # Update cache - use base class _last_readings
            self._last_readings[c_type] = reading

            # Dispatch to subscribers - use base class _subscribers
            if c_type in self._subscribers:
                for callback in self._subscribers[c_type]:
                    try:
                        import asyncio

                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            coro = callback(reading)
                            _ = asyncio.create_task(coro)  # type: ignore[arg-type]  # noqa: RUF006
                        else:
                            loop.run_until_complete(callback(reading))
                    except Exception as e:
                        logger.error(f"Error in sensor callback: {e}")

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read sensor value - uses base class implementation."""
        if sensor not in self._available_sensors:
            raise RuntimeError(f"Sensor {sensor} not available")

        # Return last cached value if available
        if sensor in self._last_readings:
            return self._last_readings[sensor]

        raise RuntimeError("No sensor data yet, call subscribe() first")

    async def subscribe(
        self,
        sensor: SensorType,
        callback,
        rate_hz: int = 10,
    ) -> None:
        """Subscribe to sensor updates - register Android listener before base class.

        Args:
            sensor: The sensor type to subscribe to
            callback: Async callback function to receive SensorReading updates
            rate_hz: Desired update rate in Hz (actual rate depends on hardware)
        """
        if sensor not in self._available_sensors:
            raise RuntimeError(f"Sensor {sensor} not available")

        # Register Android listener if first subscriber for this sensor
        if sensor not in self._subscribers:
            a_sensor = self._sensors.get(sensor)

            if a_sensor:
                # Determine delay based on rate_hz
                # DELAY_FASTEST = 0 (as fast as possible)
                # DELAY_GAME = 1 (~20ms / 50Hz)
                # DELAY_UI = 2 (~60ms / 16Hz)
                # DELAY_NORMAL = 3 (~200ms / 5Hz)
                if rate_hz >= 50:
                    delay = SensorManagerAndroid.SENSOR_DELAY_FASTEST
                elif rate_hz >= 30:
                    delay = SensorManagerAndroid.SENSOR_DELAY_GAME
                elif rate_hz >= 10:
                    delay = SensorManagerAndroid.SENSOR_DELAY_UI
                else:
                    delay = SensorManagerAndroid.SENSOR_DELAY_NORMAL

                self._sensor_manager.registerListener(self._sensor_listener, a_sensor, delay)
                logger.debug(f"Registered listener for {sensor.name} at delay level {delay}")

        # Use base class subscribe
        await super().subscribe(sensor, callback, rate_hz)

    async def read_magnetometer(self) -> MagnetometerReading:
        """Convenience method to read magnetometer directly.

        Returns:
            MagnetometerReading with x, y, z values in microtesla

        Raises:
            RuntimeError: If magnetometer is not available
        """
        if SensorType.MAGNETOMETER not in self._available_sensors:
            raise RuntimeError("Magnetometer not available")

        reading = await self.read(SensorType.MAGNETOMETER)
        if isinstance(reading.value, MagnetometerReading):
            return reading.value
        raise RuntimeError("Unexpected value type for magnetometer")

    async def read_gravity(self) -> GravityReading:
        """Convenience method to read gravity vector directly.

        Returns:
            GravityReading with x, y, z values in m/s²

        Raises:
            RuntimeError: If gravity sensor is not available
        """
        if SensorType.GRAVITY not in self._available_sensors:
            raise RuntimeError("Gravity sensor not available")

        reading = await self.read(SensorType.GRAVITY)
        if isinstance(reading.value, GravityReading):
            return reading.value
        raise RuntimeError("Unexpected value type for gravity")

    async def read_rotation(self) -> RotationReading:
        """Convenience method to read rotation vector directly.

        Returns:
            RotationReading as quaternion (x, y, z, w)

        Raises:
            RuntimeError: If rotation vector sensor is not available
        """
        if SensorType.ROTATION not in self._available_sensors:
            raise RuntimeError("Rotation vector sensor not available")

        reading = await self.read(SensorType.ROTATION)
        if isinstance(reading.value, RotationReading):
            return reading.value
        raise RuntimeError("Unexpected value type for rotation")

    async def shutdown(self) -> None:
        """Shutdown Android sensors - unregister listeners then base class cleanup."""
        if self._sensor_manager and self._sensor_listener:
            self._sensor_manager.unregisterListener(self._sensor_listener)
        await super().shutdown()
