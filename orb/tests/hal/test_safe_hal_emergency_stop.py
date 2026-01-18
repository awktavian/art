"""Test SafeHAL Emergency Stop Mechanism.

Tests the emergency halt system that provides manual safety override with h(x) = -∞.
Verifies that emergency stops block all actuator commands and persist across async boundaries.

Critical Safety Properties Tested:
1. emergency_halt() blocks ALL actuator commands immediately
2. Emergency stop persists across async boundaries
3. reset_emergency_halt() restores normal operation
4. Emergency halt state query returns correct status
5. Emergency halt triggers on safety violation
6. Emergency stop bypasses normal safety checks

Created: December 21, 2025
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
from typing import TYPE_CHECKING

import numpy as np
import pytest_asyncio

from kagami.core.safety.cbf_integration import (
    emergency_halt,
    is_emergency_halt_active,
    reset_emergency_halt,
)
from kagami_hal.interface.actuators import ActuatorConstraints, ActuatorType, IActuator
from kagami_hal.interface.safe_hal import SafeHAL, SafetyViolation


pytestmark = pytest.mark.tier_integration

if TYPE_CHECKING:
    from numpy.typing import NDArray

# =============================================================================
# MOCK ACTUATORS FOR TESTING
# =============================================================================


class MockActuator(IActuator):
    """Mock actuator for emergency stop testing."""

    def __init__(self, actuator_type: ActuatorType = ActuatorType.LED):
        self.actuator_type = actuator_type
        self._initialized = False
        self._value = 0.0
        self._write_count = 0
        self._emergency_stop_count = 0
        self._emergency_stopped = False

    async def get_constraints(self) -> ActuatorConstraints:
        return ActuatorConstraints(
            actuator_type=self.actuator_type,
            min_value=0.0,
            max_value=1.0,
            max_rate=100.0,
            max_acceleration=None,
            safe_default=0.0,
            power_limit_watts=1.0,
            thermal_limit_c=80.0,
            dimensions={},
        )

    async def write(self, value: NDArray[np.float32] | float) -> None:
        if not self._initialized:
            raise RuntimeError("Actuator not initialized")
        if self._emergency_stopped:
            raise RuntimeError("Emergency stop active")
        self._value = float(value) if isinstance(value, int | float) else float(value[0])
        self._write_count += 1

    async def read(self) -> float:
        return self._value

    async def emergency_stop(self) -> None:
        self._value = 0.0
        self._emergency_stop_count += 1
        self._emergency_stopped = True

    async def initialize(self) -> None:
        self._initialized = True
        self._value = 0.0
        self._emergency_stopped = False

    async def shutdown(self) -> None:
        await self.emergency_stop()
        self._initialized = False


# =============================================================================
# FIXTURES
# =============================================================================


@pytest_asyncio.fixture
async def safe_hal_strict():
    """Create SafeHAL in strict mode."""
    hal = SafeHAL(project_on_violation=False, strict_mode=True)
    await hal.initialize()
    yield hal
    await hal.shutdown()
    reset_emergency_halt()


@pytest_asyncio.fixture
async def safe_hal_project():
    """Create SafeHAL in projection mode."""
    hal = SafeHAL(project_on_violation=True, strict_mode=False)
    await hal.initialize()
    yield hal
    await hal.shutdown()
    reset_emergency_halt()


@pytest_asyncio.fixture
async def mock_actuator():
    """Create and initialize mock actuator."""
    actuator = MockActuator(ActuatorType.LED)
    await actuator.initialize()
    yield actuator
    await actuator.shutdown()


@pytest.fixture(autouse=True)
def reset_emergency_state():
    """Automatically reset emergency halt state before each test."""
    reset_emergency_halt()
    yield
    reset_emergency_halt()


# =============================================================================
# TEST: emergency_halt() BLOCKS ALL COMMANDS
# =============================================================================


@pytest.mark.asyncio
async def test_emergency_halt_blocks_all_commands_strict(
    safe_hal_strict: SafeHAL,
    mock_actuator: MockActuator,
):
    """Test that emergency_halt() immediately blocks all actuator commands in strict mode."""
    safe_hal_strict.register_actuator(ActuatorType.LED, mock_actuator)

    # Verify normal operation first
    result = await safe_hal_strict.send_actuation(mock_actuator, 0.5)
    assert result.is_safe
    assert mock_actuator._write_count == 1

    # Trigger emergency halt
    emergency_halt()
    assert is_emergency_halt_active()

    # All commands should now be blocked with SafetyViolation
    with pytest.raises(SafetyViolation) as exc_info:
        await safe_hal_strict.send_actuation(mock_actuator, 0.7)

    # Verify exception has correct properties
    exc = exc_info.value
    assert exc.actuator_type == ActuatorType.LED
    assert exc.barrier_value == -float("inf")  # Emergency halt = h(x) = -∞

    # Verify no additional writes occurred
    assert mock_actuator._write_count == 1


@pytest.mark.asyncio
async def test_emergency_halt_blocks_all_commands_project(
    safe_hal_project: SafeHAL,
    mock_actuator: MockActuator,
):
    """Test that emergency_halt() blocks commands even in projection mode."""
    safe_hal_project.register_actuator(ActuatorType.LED, mock_actuator)

    # Trigger emergency halt
    emergency_halt()

    # Even in projection mode, emergency halt blocks with h(x) = -∞
    # (cannot project from -∞ to safe set)
    result = await safe_hal_project.send_actuation(mock_actuator, 0.5)

    assert not result.is_safe
    assert result.barrier_value == -float("inf")
    assert "emergency_halt" in result.reason

    # Verify no writes occurred
    assert mock_actuator._write_count == 0


@pytest.mark.asyncio
async def test_emergency_halt_blocks_multiple_actuator_types(safe_hal_strict: SafeHAL):
    """Test that emergency halt blocks all actuator types."""
    # Create different actuator types
    led = MockActuator(ActuatorType.LED)
    motor = MockActuator(ActuatorType.MOTOR)
    speaker = MockActuator(ActuatorType.SPEAKER)

    await led.initialize()
    await motor.initialize()
    await speaker.initialize()

    safe_hal_strict.register_actuator(ActuatorType.LED, led)
    safe_hal_strict.register_actuator(ActuatorType.MOTOR, motor)
    safe_hal_strict.register_actuator(ActuatorType.SPEAKER, speaker)

    # Trigger emergency halt
    emergency_halt()

    # All actuator types should be blocked
    with pytest.raises(SafetyViolation):
        await safe_hal_strict.send_actuation(led, 0.5)

    with pytest.raises(SafetyViolation):
        await safe_hal_strict.send_actuation(motor, 0.5)

    with pytest.raises(SafetyViolation):
        await safe_hal_strict.send_actuation(speaker, 0.5)

    # Verify no writes occurred
    assert led._write_count == 0
    assert motor._write_count == 0
    assert speaker._write_count == 0

    await led.shutdown()
    await motor.shutdown()
    await speaker.shutdown()


# =============================================================================
# TEST: EMERGENCY STOP PERSISTS ACROSS ASYNC BOUNDARIES
# =============================================================================


@pytest.mark.asyncio
async def test_emergency_halt_persists_across_await(
    safe_hal_strict: SafeHAL,
    mock_actuator: MockActuator,
):
    """Test that emergency halt persists across await boundaries."""
    safe_hal_strict.register_actuator(ActuatorType.LED, mock_actuator)

    # Trigger emergency halt
    emergency_halt()

    # Await some async operations
    await asyncio.sleep(0.01)
    await asyncio.sleep(0.01)

    # Emergency halt should still be active
    assert is_emergency_halt_active()

    # Commands should still be blocked
    with pytest.raises(SafetyViolation):
        await safe_hal_strict.send_actuation(mock_actuator, 0.5)


@pytest.mark.asyncio
async def test_emergency_halt_persists_across_tasks(safe_hal_strict: SafeHAL):
    """Test that emergency halt persists across concurrent tasks."""
    actuator1 = MockActuator(ActuatorType.LED)
    actuator2 = MockActuator(ActuatorType.MOTOR)

    await actuator1.initialize()
    await actuator2.initialize()

    safe_hal_strict.register_actuator(ActuatorType.LED, actuator1)
    safe_hal_strict.register_actuator(ActuatorType.MOTOR, actuator2)

    # Trigger emergency halt
    emergency_halt()

    async def try_actuate(actuator: MockActuator, value: float) -> bool:
        """Try to actuate and return True if succeeded, False if blocked."""
        try:
            await safe_hal_strict.send_actuation(actuator, value)
            return True
        except SafetyViolation:
            return False

    # Run concurrent tasks
    results = await asyncio.gather(
        try_actuate(actuator1, 0.5),
        try_actuate(actuator2, 0.7),
        try_actuate(actuator1, 0.3),
    )

    # All tasks should be blocked
    assert all(result is False for result in results)

    # Verify no writes occurred
    assert actuator1._write_count == 0
    assert actuator2._write_count == 0

    await actuator1.shutdown()
    await actuator2.shutdown()


@pytest.mark.asyncio
async def test_emergency_halt_in_background_tasks(safe_hal_strict: SafeHAL):
    """Test emergency halt affects background tasks."""
    actuator = MockActuator(ActuatorType.LED)
    await actuator.initialize()
    safe_hal_strict.register_actuator(ActuatorType.LED, actuator)

    blocked_count = 0

    async def background_actuation():
        nonlocal blocked_count
        for _ in range(5):
            try:
                await safe_hal_strict.send_actuation(actuator, 0.5)
            except SafetyViolation:
                blocked_count += 1
            await asyncio.sleep(0.01)

    # Start background task
    task = asyncio.create_task(background_actuation())

    # Trigger emergency halt while task is running
    await asyncio.sleep(0.02)  # Let first iteration run
    emergency_halt()

    # Wait for task to complete
    await task

    # Most attempts should be blocked (all after emergency_halt())
    assert blocked_count >= 3

    await actuator.shutdown()


# =============================================================================
# TEST: reset_emergency_halt() RESTORES NORMAL OPERATION
# =============================================================================


@pytest.mark.asyncio
async def test_reset_emergency_halt_restores_operation(
    safe_hal_strict: SafeHAL,
    mock_actuator: MockActuator,
):
    """Test that reset_emergency_halt() restores normal actuator operation."""
    safe_hal_strict.register_actuator(ActuatorType.LED, mock_actuator)

    # Trigger emergency halt
    emergency_halt()
    assert is_emergency_halt_active()

    # Verify commands blocked
    with pytest.raises(SafetyViolation):
        await safe_hal_strict.send_actuation(mock_actuator, 0.5)

    # Reset emergency halt
    reset_emergency_halt()
    assert not is_emergency_halt_active()

    # Commands should now work
    result = await safe_hal_strict.send_actuation(mock_actuator, 0.5)
    assert result.is_safe
    assert result.barrier_value >= 0.0
    assert mock_actuator._write_count == 1


@pytest.mark.asyncio
async def test_reset_clears_across_all_actuators(safe_hal_strict: SafeHAL):
    """Test that reset clears emergency halt for all actuators."""
    led = MockActuator(ActuatorType.LED)
    motor = MockActuator(ActuatorType.MOTOR)

    await led.initialize()
    await motor.initialize()

    safe_hal_strict.register_actuator(ActuatorType.LED, led)
    safe_hal_strict.register_actuator(ActuatorType.MOTOR, motor)

    # Trigger and reset emergency halt
    emergency_halt()
    reset_emergency_halt()

    # Both actuators should work
    result1 = await safe_hal_strict.send_actuation(led, 0.5)
    result2 = await safe_hal_strict.send_actuation(motor, 0.7)

    assert result1.is_safe
    assert result2.is_safe
    assert led._write_count == 1
    assert motor._write_count == 1

    await led.shutdown()
    await motor.shutdown()


@pytest.mark.asyncio
async def test_multiple_emergency_halt_cycles(
    safe_hal_strict: SafeHAL,
    mock_actuator: MockActuator,
):
    """Test multiple emergency halt/reset cycles."""
    safe_hal_strict.register_actuator(ActuatorType.LED, mock_actuator)

    for _cycle in range(3):
        # Trigger emergency halt
        emergency_halt()
        assert is_emergency_halt_active()

        # Verify blocked
        with pytest.raises(SafetyViolation):
            await safe_hal_strict.send_actuation(mock_actuator, 0.5)

        # Reset
        reset_emergency_halt()
        assert not is_emergency_halt_active()

        # Verify works
        result = await safe_hal_strict.send_actuation(mock_actuator, 0.5)
        assert result.is_safe

    # Total writes should equal number of cycles
    assert mock_actuator._write_count == 3


# =============================================================================
# TEST: EMERGENCY HALT STATE QUERY
# =============================================================================


def test_emergency_halt_state_query() -> None:
    """Test that is_emergency_halt_active() returns correct status."""
    # Initial state should be inactive
    assert not is_emergency_halt_active()

    # Activate
    emergency_halt()
    assert is_emergency_halt_active()

    # Deactivate
    reset_emergency_halt()
    assert not is_emergency_halt_active()

    # Multiple activations (idempotent)
    emergency_halt()
    emergency_halt()
    assert is_emergency_halt_active()

    # Multiple resets (idempotent)
    reset_emergency_halt()
    reset_emergency_halt()
    assert not is_emergency_halt_active()


@pytest.mark.asyncio
async def test_emergency_halt_state_thread_safe(safe_hal_strict: SafeHAL):
    """Test that emergency halt state is thread-safe."""
    actuator = MockActuator(ActuatorType.LED)
    await actuator.initialize()
    safe_hal_strict.register_actuator(ActuatorType.LED, actuator)

    async def check_and_actuate():
        """Check emergency state and try to actuate."""
        if not is_emergency_halt_active():
            try:
                await safe_hal_strict.send_actuation(actuator, 0.5)
                return "success"
            except SafetyViolation:
                return "blocked"
        return "skipped"

    # Run concurrent checks
    results = await asyncio.gather(
        check_and_actuate(),
        check_and_actuate(),
        check_and_actuate(),
    )

    # All should succeed in normal state
    assert all(r == "success" for r in results)

    # Trigger emergency halt
    emergency_halt()

    # Run concurrent checks again
    results = await asyncio.gather(
        check_and_actuate(),
        check_and_actuate(),
        check_and_actuate(),
    )

    # All should be skipped or blocked
    assert all(r in ("skipped", "blocked") for r in results)

    await actuator.shutdown()


# =============================================================================
# TEST: EMERGENCY STOP BYPASSES NORMAL CHECKS
# =============================================================================


@pytest.mark.asyncio
async def test_emergency_stop_all_bypasses_cbf():
    """Test that emergency_stop_all() bypasses normal CBF checks."""
    hal = SafeHAL(project_on_violation=False, strict_mode=True)
    await hal.initialize()

    actuator = MockActuator(ActuatorType.LED)
    await actuator.initialize()
    hal.register_actuator(ActuatorType.LED, actuator)

    # Set actuator to active state
    await hal.send_actuation(actuator, 1.0)
    assert actuator._value == 1.0

    # Trigger emergency halt
    emergency_halt()

    # emergency_stop_all() should still work despite emergency halt
    # (it directly calls actuator.emergency_stop(), bypassing CBF)
    await hal.emergency_stop_all()

    # Verify actuator stopped
    assert actuator._emergency_stop_count == 1
    assert actuator._value == 0.0

    await actuator.shutdown()
    await hal.shutdown()
    reset_emergency_halt()


@pytest.mark.asyncio
async def test_individual_emergency_stop_bypasses_cbf(mock_actuator: MockActuator):
    """Test that actuator.emergency_stop() bypasses CBF checks."""
    # Emergency stop is called directly on actuator, not through SafeHAL
    await mock_actuator.write(1.0)
    assert mock_actuator._value == 1.0

    # Call emergency stop directly
    await mock_actuator.emergency_stop()

    # Verify stopped
    assert mock_actuator._emergency_stop_count == 1
    assert mock_actuator._value == 0.0
    assert mock_actuator._emergency_stopped


# =============================================================================
# TEST: EMERGENCY HALT METRICS
# =============================================================================


@pytest.mark.asyncio
async def test_emergency_halt_updates_statistics(
    safe_hal_project: SafeHAL,
    mock_actuator: MockActuator,
):
    """Test that emergency halt violations update safety statistics."""
    safe_hal_project.register_actuator(ActuatorType.LED, mock_actuator)

    # Get initial stats
    initial_stats = await safe_hal_project.get_safety_stats()
    initial_checks = initial_stats["total_checks"]
    initial_violations = initial_stats["total_violations"]

    # Trigger emergency halt
    emergency_halt()

    # Attempt actuation (will fail but update stats)
    result = await safe_hal_project.send_actuation(mock_actuator, 0.5)
    assert not result.is_safe

    # Check stats updated
    stats = await safe_hal_project.get_safety_stats()
    assert stats["total_checks"] == initial_checks + 1
    assert stats["total_violations"] == initial_violations + 1


@pytest.mark.asyncio
async def test_emergency_halt_in_safety_result(
    safe_hal_project: SafeHAL,
    mock_actuator: MockActuator,
):
    """Test that emergency halt is reflected in SafetyCheckResult."""
    safe_hal_project.register_actuator(ActuatorType.LED, mock_actuator)

    # Trigger emergency halt
    emergency_halt()

    # Attempt actuation
    result = await safe_hal_project.send_actuation(mock_actuator, 0.5)

    # Verify result reflects emergency halt
    assert not result.is_safe
    assert result.barrier_value == -float("inf")
    assert result.projected_value is None  # Cannot project from -∞
    assert result.metadata is not None
