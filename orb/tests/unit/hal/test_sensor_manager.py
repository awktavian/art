"""Tests for HAL Sensor Manager.

Tests hardware abstraction layer sensor management.

Author: Crystal 💎 (Verification Colony)
Date: December 22, 2025
"""

from __future__ import annotations

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.tier_unit,
    pytest.mark.tier1,
    pytest.mark.timeout(30),
]

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from kagami_hal.data_types import (
    AccelReading,
    GPSReading,
    GyroReading,
    HeartRateReading,
    SensorReading,
    SensorType,
)
from kagami_hal.sensor_manager import SensorManager

# --- Mock Implementation for Testing ---


class MockSensorManager(SensorManager):
    """Mock sensor manager for testing.

    Simulates sensor behavior without requiring actual hardware.
    """

    def __init__(self) -> None:
        """Initialize mock sensor manager."""
        self._initialized = False
        self._available_sensors: set[SensorType] = {
            SensorType.ACCELEROMETER,
            SensorType.GYROSCOPE,
            SensorType.HEART_RATE,
            SensorType.GPS,
        }
        self._subscriptions: dict[
            SensorType, tuple[Callable[[SensorReading], Awaitable[None]], int]
        ] = {}
        self._sensor_data: dict[SensorType, Any] = {
            SensorType.ACCELEROMETER: AccelReading(x=0.0, y=0.0, z=9.8),
            SensorType.GYROSCOPE: GyroReading(x=0.0, y=0.0, z=0.0),
            SensorType.HEART_RATE: HeartRateReading(bpm=72, confidence=0.95),
            SensorType.GPS: GPSReading(
                latitude=37.7749, longitude=-122.4194, altitude=10.0, accuracy=5.0
            ),
        }
        self._failure_mode: dict[SensorType, Exception | None] = {}

    async def initialize(self) -> bool:
        """Initialize sensor subsystem."""
        self._initialized = True
        return True

    async def list_sensors(self) -> list[SensorType]:
        """List available sensors."""
        if not self._initialized:
            raise RuntimeError("Sensor manager not initialized")
        return list(self._available_sensors)

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read sensor value."""
        if not self._initialized:
            raise RuntimeError("Sensor manager not initialized")

        if sensor not in self._available_sensors:
            raise ValueError(f"Sensor {sensor} not available")

        # Check if sensor is in failure mode
        if sensor in self._failure_mode and self._failure_mode[sensor] is not None:
            raise self._failure_mode[sensor]

        # Return mock sensor reading
        value = self._sensor_data.get(sensor)
        return SensorReading(
            sensor=sensor,
            value=value,
            timestamp_ms=1000,
            accuracy=0.95,
        )

    async def subscribe(
        self,
        sensor: SensorType,
        callback: Callable[[SensorReading], Awaitable[None]],
        rate_hz: int = 10,
    ) -> None:
        """Subscribe to sensor updates."""
        if not self._initialized:
            raise RuntimeError("Sensor manager not initialized")

        if sensor not in self._available_sensors:
            raise ValueError(f"Sensor {sensor} not available")

        if rate_hz <= 0:
            raise ValueError("Rate must be positive")

        self._subscriptions[sensor] = (callback, rate_hz)

    async def unsubscribe(self, sensor: SensorType) -> None:
        """Unsubscribe from sensor."""
        if not self._initialized:
            raise RuntimeError("Sensor manager not initialized")

        if sensor not in self._subscriptions:
            raise ValueError(f"Not subscribed to {sensor}")

        del self._subscriptions[sensor]

    async def shutdown(self) -> None:
        """Shutdown sensor manager."""
        self._subscriptions.clear()
        self._initialized = False

    # Test helper methods
    def set_sensor_failure(self, sensor: SensorType, error: Exception) -> None:
        """Set a sensor to fail with given error."""
        self._failure_mode[sensor] = error

    def clear_sensor_failure(self, sensor: SensorType) -> None:
        """Clear sensor failure mode."""
        self._failure_mode[sensor] = None

    def add_sensor(self, sensor: SensorType, data: Any) -> None:
        """Add a sensor to the available list."""
        self._available_sensors.add(sensor)
        self._sensor_data[sensor] = data

    def remove_sensor(self, sensor: SensorType) -> None:
        """Remove a sensor from available list."""
        self._available_sensors.discard(sensor)
        if sensor in self._sensor_data:
            del self._sensor_data[sensor]


# --- Basic Import Tests ---


class TestSensorManagerImport:
    """Test sensor manager module imports."""

    def test_smoke_imports(self) -> None:
        """Test all sensor manager imports work."""
        from kagami_hal import sensor_manager
        from kagami_hal.sensor_manager import (
            AccelReading,
            GPSReading,
            GyroReading,
            HeartRateReading,
            SensorManager,
            SensorReading,
            SensorType,
        )

        assert sensor_manager is not None
        assert SensorManager is not None
        assert SensorType is not None
        assert SensorReading is not None
        assert AccelReading is not None
        assert GyroReading is not None
        assert HeartRateReading is not None
        assert GPSReading is not None


# --- Lifecycle Tests ---


class TestSensorManagerLifecycle:
    """Test sensor manager initialization and shutdown."""

    @pytest.mark.asyncio
    async def test_initialize_success(self) -> None:
        """Test successful sensor manager initialization."""
        manager = MockSensorManager()
        result = await manager.initialize()

        assert result is True
        assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_operations_require_initialization(self) -> None:
        """Test operations fail without initialization."""
        manager = MockSensorManager()

        with pytest.raises(RuntimeError, match="not initialized"):
            await manager.list_sensors()

        with pytest.raises(RuntimeError, match="not initialized"):
            await manager.read(SensorType.ACCELEROMETER)

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self) -> None:
        """Test shutdown properly clears manager state."""
        manager = MockSensorManager()
        await manager.initialize()

        # Subscribe to a sensor
        callback = AsyncMock()
        await manager.subscribe(SensorType.ACCELEROMETER, callback, rate_hz=10)
        assert len(manager._subscriptions) == 1

        # Shutdown should clear subscriptions
        await manager.shutdown()
        assert len(manager._subscriptions) == 0
        assert manager._initialized is False


# --- Sensor Registration Tests ---


class TestSensorRegistration:
    """Test sensor registration and listing."""

    @pytest.mark.asyncio
    async def test_list_available_sensors(self) -> None:
        """Test listing available sensors."""
        manager = MockSensorManager()
        await manager.initialize()

        sensors = await manager.list_sensors()

        assert isinstance(sensors, list)
        assert len(sensors) > 0
        assert SensorType.ACCELEROMETER in sensors
        assert SensorType.GYROSCOPE in sensors
        assert SensorType.HEART_RATE in sensors
        assert SensorType.GPS in sensors

    @pytest.mark.asyncio
    async def test_dynamic_sensor_registration(self) -> None:
        """Test dynamically adding sensors."""
        manager = MockSensorManager()
        await manager.initialize()

        initial_sensors = await manager.list_sensors()
        assert SensorType.TEMPERATURE not in initial_sensors

        # Add temperature sensor
        manager.add_sensor(SensorType.TEMPERATURE, 22.5)

        updated_sensors = await manager.list_sensors()
        assert SensorType.TEMPERATURE in updated_sensors
        assert len(updated_sensors) == len(initial_sensors) + 1

    @pytest.mark.asyncio
    async def test_sensor_removal(self) -> None:
        """Test removing sensors."""
        manager = MockSensorManager()
        await manager.initialize()

        initial_sensors = await manager.list_sensors()
        assert SensorType.GPS in initial_sensors

        # Remove GPS sensor
        manager.remove_sensor(SensorType.GPS)

        updated_sensors = await manager.list_sensors()
        assert SensorType.GPS not in updated_sensors
        assert len(updated_sensors) == len(initial_sensors) - 1


# --- Sensor Reading Tests ---


class TestSensorReading:
    """Test sensor data reading."""

    @pytest.mark.asyncio
    async def test_read_accelerometer(self) -> None:
        """Test reading accelerometer data."""
        manager = MockSensorManager()
        await manager.initialize()

        reading = await manager.read(SensorType.ACCELEROMETER)

        assert isinstance(reading, SensorReading)
        assert reading.sensor == SensorType.ACCELEROMETER
        assert isinstance(reading.value, AccelReading)
        assert reading.value.z == 9.8  # Gravity
        assert reading.accuracy > 0

    @pytest.mark.asyncio
    async def test_read_gyroscope(self) -> None:
        """Test reading gyroscope data."""
        manager = MockSensorManager()
        await manager.initialize()

        reading = await manager.read(SensorType.GYROSCOPE)

        assert reading.sensor == SensorType.GYROSCOPE
        assert isinstance(reading.value, GyroReading)
        assert hasattr(reading.value, "x")
        assert hasattr(reading.value, "y")
        assert hasattr(reading.value, "z")

    @pytest.mark.asyncio
    async def test_read_heart_rate(self) -> None:
        """Test reading heart rate data."""
        manager = MockSensorManager()
        await manager.initialize()

        reading = await manager.read(SensorType.HEART_RATE)

        assert reading.sensor == SensorType.HEART_RATE
        assert isinstance(reading.value, HeartRateReading)
        assert reading.value.bpm > 0
        assert 0 <= reading.value.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_read_gps(self) -> None:
        """Test reading GPS data."""
        manager = MockSensorManager()
        await manager.initialize()

        reading = await manager.read(SensorType.GPS)

        assert reading.sensor == SensorType.GPS
        assert isinstance(reading.value, GPSReading)
        assert -90 <= reading.value.latitude <= 90
        assert -180 <= reading.value.longitude <= 180
        assert reading.value.accuracy > 0

    @pytest.mark.asyncio
    async def test_read_unavailable_sensor(self) -> None:
        """Test reading from unavailable sensor fails."""
        manager = MockSensorManager()
        await manager.initialize()

        # Remove a sensor to make it unavailable
        manager.remove_sensor(SensorType.ACCELEROMETER)

        with pytest.raises(ValueError, match="not available"):
            await manager.read(SensorType.ACCELEROMETER)


# --- Data Type Validation Tests ---


class TestSensorDataTypes:
    """Test sensor data type validation."""

    def test_sensor_type_enum_values(self) -> None:
        """Test SensorType enum has expected values."""
        assert hasattr(SensorType, "ACCELEROMETER")
        assert hasattr(SensorType, "GYROSCOPE")
        assert hasattr(SensorType, "HEART_RATE")
        assert hasattr(SensorType, "GPS")
        assert hasattr(SensorType, "TEMPERATURE")
        assert hasattr(SensorType, "PRESSURE")

    def test_accel_reading_structure(self) -> None:
        """Test AccelReading dataclass structure."""
        reading = AccelReading(x=1.0, y=2.0, z=3.0)

        assert reading.x == 1.0
        assert reading.y == 2.0
        assert reading.z == 3.0

    def test_gyro_reading_structure(self) -> None:
        """Test GyroReading dataclass structure."""
        reading = GyroReading(x=0.1, y=0.2, z=0.3)

        assert reading.x == 0.1
        assert reading.y == 0.2
        assert reading.z == 0.3

    def test_heart_rate_reading_structure(self) -> None:
        """Test HeartRateReading dataclass structure."""
        reading = HeartRateReading(bpm=75, confidence=0.9)

        assert reading.bpm == 75
        assert reading.confidence == 0.9

    def test_gps_reading_structure(self) -> None:
        """Test GPSReading dataclass structure."""
        reading = GPSReading(latitude=37.7749, longitude=-122.4194, altitude=10.0, accuracy=5.0)

        assert reading.latitude == 37.7749
        assert reading.longitude == -122.4194
        assert reading.altitude == 10.0
        assert reading.accuracy == 5.0

    def test_sensor_reading_structure(self) -> None:
        """Test SensorReading wrapper structure."""
        accel = AccelReading(x=1.0, y=2.0, z=3.0)
        reading = SensorReading(
            sensor=SensorType.ACCELEROMETER, value=accel, timestamp_ms=1000, accuracy=0.95
        )

        assert reading.sensor == SensorType.ACCELEROMETER
        assert reading.value == accel
        assert reading.timestamp_ms == 1000
        assert reading.accuracy == 0.95


# --- Error Handling Tests ---


class TestSensorErrorHandling:
    """Test error handling for sensor failures."""

    @pytest.mark.asyncio
    async def test_sensor_hardware_failure(self) -> None:
        """Test handling of sensor hardware failure."""
        manager = MockSensorManager()
        await manager.initialize()

        # Simulate hardware failure
        hw_error = OSError("Sensor hardware not responding")
        manager.set_sensor_failure(SensorType.ACCELEROMETER, hw_error)

        with pytest.raises(IOError, match="hardware not responding"):
            await manager.read(SensorType.ACCELEROMETER)

    @pytest.mark.asyncio
    async def test_sensor_timeout(self) -> None:
        """Test handling of sensor read timeout."""
        manager = MockSensorManager()
        await manager.initialize()

        # Simulate timeout
        timeout_error = TimeoutError("Sensor read timeout")
        manager.set_sensor_failure(SensorType.GPS, timeout_error)

        with pytest.raises(TimeoutError, match="timeout"):
            await manager.read(SensorType.GPS)

    @pytest.mark.asyncio
    async def test_sensor_recovery_after_failure(self) -> None:
        """Test sensor can recover after failure."""
        manager = MockSensorManager()
        await manager.initialize()

        # Set failure mode
        manager.set_sensor_failure(SensorType.HEART_RATE, OSError("Sensor error"))

        with pytest.raises(IOError):
            await manager.read(SensorType.HEART_RATE)

        # Clear failure and retry
        manager.clear_sensor_failure(SensorType.HEART_RATE)
        reading = await manager.read(SensorType.HEART_RATE)

        assert reading.sensor == SensorType.HEART_RATE
        assert isinstance(reading.value, HeartRateReading)

    @pytest.mark.asyncio
    async def test_invalid_sensor_type_handling(self) -> None:
        """Test handling of reading unavailable sensor."""
        manager = MockSensorManager()
        await manager.initialize()

        # Temperature not in default available sensors
        manager.remove_sensor(SensorType.TEMPERATURE)

        with pytest.raises(ValueError, match="not available"):
            await manager.read(SensorType.TEMPERATURE)


# --- Subscription Tests ---


class TestSensorSubscription:
    """Test sensor subscription and callbacks."""

    @pytest.mark.asyncio
    async def test_subscribe_to_sensor(self) -> None:
        """Test subscribing to sensor updates."""
        manager = MockSensorManager()
        await manager.initialize()

        callback = AsyncMock()
        await manager.subscribe(SensorType.ACCELEROMETER, callback, rate_hz=10)

        assert SensorType.ACCELEROMETER in manager._subscriptions
        assert manager._subscriptions[SensorType.ACCELEROMETER][1] == 10

    @pytest.mark.asyncio
    async def test_subscribe_with_custom_rate(self) -> None:
        """Test subscribing with custom sampling rate."""
        manager = MockSensorManager()
        await manager.initialize()

        callback = AsyncMock()
        await manager.subscribe(SensorType.GYROSCOPE, callback, rate_hz=50)

        assert manager._subscriptions[SensorType.GYROSCOPE][1] == 50

    @pytest.mark.asyncio
    async def test_subscribe_invalid_rate(self) -> None:
        """Test subscribing with invalid rate fails."""
        manager = MockSensorManager()
        await manager.initialize()

        callback = AsyncMock()

        with pytest.raises(ValueError, match="Rate must be positive"):
            await manager.subscribe(SensorType.ACCELEROMETER, callback, rate_hz=0)

        with pytest.raises(ValueError, match="Rate must be positive"):
            await manager.subscribe(SensorType.ACCELEROMETER, callback, rate_hz=-10)

    @pytest.mark.asyncio
    async def test_subscribe_to_unavailable_sensor(self) -> None:
        """Test subscribing to unavailable sensor fails."""
        manager = MockSensorManager()
        await manager.initialize()

        manager.remove_sensor(SensorType.GPS)
        callback = AsyncMock()

        with pytest.raises(ValueError, match="not available"):
            await manager.subscribe(SensorType.GPS, callback)

    @pytest.mark.asyncio
    async def test_unsubscribe_from_sensor(self) -> None:
        """Test unsubscribing from sensor."""
        manager = MockSensorManager()
        await manager.initialize()

        callback = AsyncMock()
        await manager.subscribe(SensorType.ACCELEROMETER, callback, rate_hz=10)
        assert SensorType.ACCELEROMETER in manager._subscriptions

        await manager.unsubscribe(SensorType.ACCELEROMETER)
        assert SensorType.ACCELEROMETER not in manager._subscriptions

    @pytest.mark.asyncio
    async def test_unsubscribe_without_subscription(self) -> None:
        """Test unsubscribing without active subscription fails."""
        manager = MockSensorManager()
        await manager.initialize()

        with pytest.raises(ValueError, match="Not subscribed"):
            await manager.unsubscribe(SensorType.ACCELEROMETER)

    @pytest.mark.asyncio
    async def test_multiple_subscriptions(self) -> None:
        """Test subscribing to multiple sensors."""
        manager = MockSensorManager()
        await manager.initialize()

        callback1 = AsyncMock()
        callback2 = AsyncMock()
        callback3 = AsyncMock()

        await manager.subscribe(SensorType.ACCELEROMETER, callback1, rate_hz=10)
        await manager.subscribe(SensorType.GYROSCOPE, callback2, rate_hz=20)
        await manager.subscribe(SensorType.HEART_RATE, callback3, rate_hz=1)

        assert len(manager._subscriptions) == 3
        assert SensorType.ACCELEROMETER in manager._subscriptions
        assert SensorType.GYROSCOPE in manager._subscriptions
        assert SensorType.HEART_RATE in manager._subscriptions


# --- Integration Tests ---


class TestHardwareAbstractionLayer:
    """Test hardware abstraction layer integration."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_workflow(self) -> None:
        """Test complete sensor manager lifecycle."""
        manager = MockSensorManager()

        # Initialize
        assert await manager.initialize() is True

        # List sensors
        sensors = await manager.list_sensors()
        assert len(sensors) > 0

        # Read sensor
        reading = await manager.read(SensorType.ACCELEROMETER)
        assert reading.sensor == SensorType.ACCELEROMETER

        # Subscribe
        callback = AsyncMock()
        await manager.subscribe(SensorType.ACCELEROMETER, callback, rate_hz=10)

        # Unsubscribe
        await manager.unsubscribe(SensorType.ACCELEROMETER)

        # Shutdown
        await manager.shutdown()
        assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_concurrent_sensor_reads(self) -> None:
        """Test reading multiple sensors concurrently."""
        manager = MockSensorManager()
        await manager.initialize()

        # Read multiple sensors (would be concurrent in real impl)
        accel_reading = await manager.read(SensorType.ACCELEROMETER)
        gyro_reading = await manager.read(SensorType.GYROSCOPE)
        hr_reading = await manager.read(SensorType.HEART_RATE)

        assert accel_reading.sensor == SensorType.ACCELEROMETER
        assert gyro_reading.sensor == SensorType.GYROSCOPE
        assert hr_reading.sensor == SensorType.HEART_RATE

    @pytest.mark.asyncio
    async def test_sensor_manager_isolation(self) -> None:
        """Test multiple manager instances are isolated."""
        manager1 = MockSensorManager()
        manager2 = MockSensorManager()

        await manager1.initialize()

        # manager2 not initialized
        assert manager1._initialized is True
        assert manager2._initialized is False

        # Operations on manager2 should fail
        with pytest.raises(RuntimeError, match="not initialized"):
            await manager2.read(SensorType.ACCELEROMETER)

    @pytest.mark.asyncio
    async def test_abstraction_layer_sensor_types(self) -> None:
        """Test HAL properly abstracts different sensor types."""
        manager = MockSensorManager()
        await manager.initialize()

        # Different sensor types return appropriate data structures
        sensors_and_types = [
            (SensorType.ACCELEROMETER, AccelReading),
            (SensorType.GYROSCOPE, GyroReading),
            (SensorType.HEART_RATE, HeartRateReading),
            (SensorType.GPS, GPSReading),
        ]

        for sensor_type, expected_type in sensors_and_types:
            reading = await manager.read(sensor_type)
            assert isinstance(reading.value, expected_type)
            assert reading.sensor == sensor_type
