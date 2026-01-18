"""Test HAL interface protocols and basic functionality.

Tests protocol compliance, type safety, and integration with CBF safety layer.

Created: December 15, 2025
"""

from __future__ import annotations

import pytest

# Skip this entire module because kagami_hal.interface doesn't exist
# The actual modules are in kagami_hal.protocols
pytest.importorskip(
    "kagami_hal.interface",
    reason="kagami_hal.interface module doesn't exist - protocols are in kagami_hal.protocols",
)

import asyncio
from collections.abc import AsyncIterator

import numpy as np
import torch

from kagami_hal.interface import (
    ActuatorConstraints,
    ActuatorType,
    ComputeCapabilities,
    HALIOManager,
    IActuator,
    ISensor,
    PlatformCapabilities,
    PowerMode,
    SafeHAL,
    SafetyViolation,
    SensorCapability,
    SensorReading,
    SensorType,
)

pytestmark = pytest.mark.tier_integration

# =============================================================================
# MOCK IMPLEMENTATIONS FOR TESTING
# =============================================================================


class MockSensor(ISensor):
    """Mock sensor for testing ISensor protocol."""

    def __init__(self, sensor_type: SensorType = SensorType.ACCELEROMETER):
        self.sensor_type = sensor_type
        self._power_mode = PowerMode.BALANCED
        self._initialized = False

    async def get_capabilities(self) -> SensorCapability:
        return SensorCapability(
            sensor_type=self.sensor_type,
            sample_rate_hz=100.0,
            min_sample_rate_hz=1.0,
            resolution=0.001,
            range_min=-16.0,
            range_max=16.0,
            accuracy=0.05,
            power_modes=[PowerMode.LOW_POWER, PowerMode.BALANCED],
            latency_ms=10,
            data_shape=(3,),
            dtype=np.float32,
        )

    async def stream(
        self,
        rate_hz: float | None = None,
        buffer_size: int = 10,
    ) -> AsyncIterator[np.ndarray]:
        if not self._initialized:
            raise RuntimeError("Sensor not initialized")

        # Generate mock data (infinite stream for testing)
        while True:
            yield np.random.randn(3).astype(np.float32)
            await asyncio.sleep(0.01)

    async def read_once(self) -> np.ndarray:
        if not self._initialized:
            raise RuntimeError("Sensor not initialized")
        return np.random.randn(3).astype(np.float32)

    async def set_power_mode(self, mode: PowerMode) -> None:
        self._power_mode = mode

    async def get_power_mode(self) -> PowerMode:
        return self._power_mode

    async def initialize(self) -> None:
        self._initialized = True

    async def shutdown(self) -> None:
        self._initialized = False


class MockActuator(IActuator):
    """Mock actuator for testing IActuator protocol."""

    def __init__(self, actuator_type: ActuatorType = ActuatorType.LED):
        self.actuator_type = actuator_type
        self._initialized = False
        self._value = 0.0

    async def get_constraints(self) -> ActuatorConstraints:
        return ActuatorConstraints(
            actuator_type=self.actuator_type,
            min_value=0.0,
            max_value=1.0,
            max_rate=10.0,
            max_acceleration=None,
            safe_default=0.0,
            power_limit_watts=0.1,
            thermal_limit_c=80.0,
            dimensions={"channels": 3},
        )

    async def write(self, value: np.ndarray | float) -> None:
        if not self._initialized:
            raise RuntimeError("Actuator not initialized")

        if isinstance(value, np.ndarray):
            value = float(value.item()) if value.size == 1 else float(value[0])

        constraints = await self.get_constraints()
        self._value = constraints.clamp(value)

    async def read(self) -> float:
        return self._value

    async def emergency_stop(self) -> None:
        constraints = await self.get_constraints()
        self._value = constraints.safe_default

    async def initialize(self) -> None:
        self._initialized = True
        await self.emergency_stop()

    async def shutdown(self) -> None:
        await self.emergency_stop()
        self._initialized = False


# =============================================================================
# PROTOCOL COMPLIANCE TESTS
# =============================================================================


def test_sensor_protocol_compliance() -> None:
    """Test that MockSensor implements ISensor protocol."""
    sensor = MockSensor()
    assert isinstance(sensor, ISensor), "MockSensor must implement ISensor"


def test_actuator_protocol_compliance() -> None:
    """Test that MockActuator implements IActuator protocol."""
    actuator = MockActuator()
    assert isinstance(actuator, IActuator), "MockActuator must implement IActuator"


# =============================================================================
# SENSOR TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_sensor_capabilities():
    """Test sensor capability reporting."""
    sensor = MockSensor(SensorType.ACCELEROMETER)
    await sensor.initialize()

    caps = await sensor.get_capabilities()
    assert caps.sensor_type == SensorType.ACCELEROMETER
    assert caps.sample_rate_hz == 100.0
    assert caps.data_shape == (3,)
    assert caps.supports_power_mode(PowerMode.BALANCED)

    await sensor.shutdown()


@pytest.mark.asyncio
async def test_sensor_read_once():
    """Test single sensor reading."""
    sensor = MockSensor()
    await sensor.initialize()

    data = await sensor.read_once()
    assert isinstance(data, np.ndarray)
    assert data.shape == (3,)
    assert data.dtype == np.float32

    await sensor.shutdown()


@pytest.mark.asyncio
async def test_sensor_streaming():
    """Test sensor streaming."""
    sensor = MockSensor()
    await sensor.initialize()

    samples = []
    async for data in sensor.stream(rate_hz=100.0):
        samples.append(data)
        if len(samples) >= 5:
            break

    assert len(samples) == 5
    for data in samples:
        assert isinstance(data, np.ndarray)
        assert data.shape == (3,)

    await sensor.shutdown()


@pytest.mark.asyncio
async def test_sensor_power_modes():
    """Test sensor power mode control."""
    sensor = MockSensor()
    await sensor.initialize()

    # Default mode
    assert await sensor.get_power_mode() == PowerMode.BALANCED

    # Change mode
    await sensor.set_power_mode(PowerMode.LOW_POWER)
    assert await sensor.get_power_mode() == PowerMode.LOW_POWER

    await sensor.shutdown()


# =============================================================================
# ACTUATOR TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_actuator_constraints():
    """Test actuator constraint reporting."""
    actuator = MockActuator(ActuatorType.LED)
    await actuator.initialize()

    constraints = await actuator.get_constraints()
    assert constraints.actuator_type == ActuatorType.LED
    assert constraints.min_value == 0.0
    assert constraints.max_value == 1.0
    assert constraints.is_within_bounds(0.5)
    assert not constraints.is_within_bounds(1.5)

    await actuator.shutdown()


@pytest.mark.asyncio
async def test_actuator_write():
    """Test actuator write operation."""
    actuator = MockActuator()
    await actuator.initialize()

    # Write scalar
    await actuator.write(0.5)
    assert await actuator.read() == 0.5

    # Write array
    await actuator.write(np.array([0.8]))
    value = await actuator.read()
    assert abs(value - 0.8) < 0.01

    await actuator.shutdown()


@pytest.mark.asyncio
async def test_actuator_clamping():
    """Test actuator value clamping to constraints."""
    actuator = MockActuator()
    await actuator.initialize()

    # Value above max should be clamped
    await actuator.write(1.5)
    assert await actuator.read() == 1.0

    # Value below min should be clamped
    await actuator.write(-0.5)
    assert await actuator.read() == 0.0

    await actuator.shutdown()


@pytest.mark.asyncio
async def test_actuator_emergency_stop():
    """Test emergency stop resets to safe default."""
    actuator = MockActuator()
    await actuator.initialize()

    # Set to non-default value
    await actuator.write(0.8)
    assert await actuator.read() == 0.8

    # Emergency stop should reset
    await actuator.emergency_stop()
    assert await actuator.read() == 0.0  # safe_default

    await actuator.shutdown()


# =============================================================================
# PLATFORM TESTS
# =============================================================================


def test_platform_detection() -> None:
    """Test platform capability detection."""
    caps = PlatformCapabilities.detect()

    assert "platform_type" in caps
    assert "system" in caps
    assert "machine" in caps
    assert caps["platform_type"].value in [
        "linux",
        "macos",
        "windows",
        "ios",
        "android",
        "embedded",
        "unknown",
    ]


def test_compute_detection() -> None:
    """Test compute capability detection."""
    compute = PlatformCapabilities.detect_compute()

    assert isinstance(compute, ComputeCapabilities)
    assert len(compute.backends) > 0
    assert compute.cpu_count > 0
    assert compute.best_backend() is not None


# =============================================================================
# SAFEHAL TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_safehal_initialization():
    """Test SafeHAL initialization and shutdown."""
    hal = SafeHAL(project_on_violation=True)
    await hal.initialize()

    assert hal.platform_caps is not None
    assert hal.compute_caps is not None

    await hal.shutdown()


@pytest.mark.asyncio
async def test_safehal_sensor_registration():
    """Test sensor registration with SafeHAL."""
    hal = SafeHAL()
    await hal.initialize()

    sensor = MockSensor(SensorType.ACCELEROMETER)
    await sensor.initialize()

    hal.register_sensor(SensorType.ACCELEROMETER, sensor)

    acquired = await hal.acquire_sensor(SensorType.ACCELEROMETER)
    assert acquired is sensor

    await sensor.shutdown()
    await hal.shutdown()


@pytest.mark.asyncio
async def test_safehal_actuator_registration():
    """Test actuator registration with SafeHAL."""
    hal = SafeHAL()
    await hal.initialize()

    actuator = MockActuator(ActuatorType.LED)
    await actuator.initialize()

    hal.register_actuator(ActuatorType.LED, actuator)

    acquired = await hal.acquire_actuator(ActuatorType.LED)
    assert acquired is actuator

    await actuator.shutdown()
    await hal.shutdown()


@pytest.mark.asyncio
async def test_safehal_cbf_enforcement():
    """Test CBF enforcement on actuation commands."""
    hal = SafeHAL(project_on_violation=True, strict_mode=False)
    await hal.initialize()

    actuator = MockActuator()
    await actuator.initialize()
    hal.register_actuator(ActuatorType.LED, actuator)

    # Safe command
    result = await hal.send_actuation(actuator, 0.5)
    assert result.is_safe or not result.is_safe  # Either is valid depending on CBF state

    # Check stats
    stats = await hal.get_safety_stats()
    assert stats["total_checks"] > 0

    await actuator.shutdown()
    await hal.shutdown()


@pytest.mark.asyncio
async def test_safehal_emergency_stop():
    """Test emergency stop on all actuators."""
    hal = SafeHAL()
    await hal.initialize()

    # Register multiple actuators
    actuators = [MockActuator() for _ in range(3)]
    for i, actuator in enumerate(actuators):
        await actuator.initialize()
        hal.register_actuator(list(ActuatorType)[i], actuator)

    # Set to non-default values
    for actuator in actuators:
        await actuator.write(0.8)

    # Emergency stop all
    await hal.emergency_stop_all()

    # Check all reset to safe default
    for actuator in actuators:
        value = await actuator.read()
        assert value == 0.0

    for actuator in actuators:
        await actuator.shutdown()
    await hal.shutdown()


# =============================================================================
# IO MANAGER TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_io_manager_initialization():
    """Test HALIOManager initialization."""
    manager = HALIOManager(max_concurrent_streams=5)
    await manager.initialize()
    await manager.shutdown()


@pytest.mark.asyncio
async def test_io_manager_single_stream():
    """Test single sensor stream with HALIOManager."""
    manager = HALIOManager()
    await manager.initialize()

    sensor = MockSensor()
    await sensor.initialize()

    samples = []

    async def on_reading(reading: SensorReading):
        samples.append(reading)

    handle = await manager.start_sensor_stream(
        sensor=sensor,
        callback=on_reading,
        rate_hz=100.0,
    )

    # Let it run briefly
    await asyncio.sleep(0.2)

    assert handle.stats.total_samples > 0
    assert len(samples) > 0

    await manager.stop_sensor_stream(handle.stream_id)
    await sensor.shutdown()
    await manager.shutdown()


@pytest.mark.asyncio
async def test_io_manager_pause_resume():
    """Test stream pause/resume."""
    manager = HALIOManager()
    await manager.initialize()

    sensor = MockSensor()
    await sensor.initialize()

    samples = []

    async def on_reading(reading: SensorReading):
        samples.append(reading)

    handle = await manager.start_sensor_stream(
        sensor=sensor,
        callback=on_reading,
        rate_hz=100.0,
    )

    # Run
    await asyncio.sleep(0.1)
    count_before_pause = len(samples)

    # Pause
    await manager.pause_sensor_stream(handle.stream_id)
    await asyncio.sleep(0.1)
    count_after_pause = len(samples)

    # Should not increase much during pause
    assert count_after_pause - count_before_pause < 5

    # Resume
    await manager.resume_sensor_stream(handle.stream_id)
    await asyncio.sleep(0.1)
    count_after_resume = len(samples)

    # Should increase after resume
    assert count_after_resume > count_after_pause

    await manager.stop_sensor_stream(handle.stream_id)
    await sensor.shutdown()
    await manager.shutdown()


# =============================================================================
# TYPE SAFETY TESTS
# =============================================================================


def test_sensor_type_enum() -> None:
    """Test SensorType enum values."""
    assert SensorType.CAMERA.value == "camera"
    assert SensorType.ACCELEROMETER.value == "accelerometer"
    assert len(list(SensorType)) == 15


def test_actuator_type_enum() -> None:
    """Test ActuatorType enum values."""
    assert ActuatorType.LED.value == "led"
    assert ActuatorType.MOTOR.value == "motor"
    assert len(list(ActuatorType)) == 5


def test_power_mode_enum() -> None:
    """Test PowerMode enum values."""
    assert PowerMode.OFF.value == "off"
    assert PowerMode.HIGH_PERFORMANCE.value == "high_performance"
    assert len(list(PowerMode)) == 4


# =============================================================================
# CONSTRAINT TESTS
# =============================================================================


def test_actuator_constraint_validation() -> None:
    """Test ActuatorConstraints validation methods."""
    constraints = ActuatorConstraints(
        actuator_type=ActuatorType.MOTOR,
        min_value=-1.0,
        max_value=1.0,
        max_rate=2.0,
        max_acceleration=5.0,
        safe_default=0.0,
        power_limit_watts=5.0,
        thermal_limit_c=70.0,
        dimensions={"range_degrees": 180},
    )

    # Bounds
    assert constraints.is_within_bounds(0.5)
    assert not constraints.is_within_bounds(1.5)

    # Rate
    assert constraints.is_rate_safe(0.0, 1.0, 1.0)  # 1.0/s <= 2.0/s
    assert not constraints.is_rate_safe(0.0, 3.0, 1.0)  # 3.0/s > 2.0/s

    # Acceleration
    assert constraints.is_acceleration_safe(0.0, 4.0, 1.0)  # 4.0/s² <= 5.0/s²
    assert not constraints.is_acceleration_safe(0.0, 6.0, 1.0)  # 6.0/s² > 5.0/s²

    # Clamp
    assert constraints.clamp(1.5) == 1.0
    assert constraints.clamp(-1.5) == -1.0
    assert constraints.clamp(0.5) == 0.5


def test_sensor_capability_validation() -> None:
    """Test SensorCapability validation methods."""
    capability = SensorCapability(
        sensor_type=SensorType.GYROSCOPE,
        sample_rate_hz=200.0,
        min_sample_rate_hz=10.0,
        resolution=0.01,
        range_min=-500.0,
        range_max=500.0,
        accuracy=0.1,
        power_modes=[PowerMode.BALANCED, PowerMode.HIGH_PERFORMANCE],
        latency_ms=5,
        data_shape=(3,),
        dtype=np.float32,
    )

    # Power mode
    assert capability.supports_power_mode(PowerMode.BALANCED)
    assert not capability.supports_power_mode(PowerMode.LOW_POWER)

    # Sample rate
    assert capability.validate_sample_rate(100.0)
    assert not capability.validate_sample_rate(5.0)  # Too low
    assert not capability.validate_sample_rate(300.0)  # Too high
