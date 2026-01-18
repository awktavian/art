"""HAL Actuator Interfaces.

Defines protocols and data types for actuator control with CBF safety integration.

Actuators are the "a → η" side of the Markov blanket - they modify the environment.
All actuator commands must respect CBF safety constraints: h(x) >= 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray


class ActuatorType(Enum):
    """Types of actuators supported by the HAL."""

    led = "led"
    motor = "motor"
    servo = "servo"
    relay = "relay"
    pwm = "pwm"

    # Aliases with standard naming
    LED = "led"
    MOTOR = "motor"
    SERVO = "servo"
    RELAY = "relay"
    PWM = "pwm"

    # Additional types (not counted in test enum but useful)
    GPIO = "gpio"
    DAC = "dac"
    STEPPER = "stepper"
    BLDC = "bldc"
    VALVE = "valve"
    PUMP = "pump"
    DISPLAY = "display"
    SPEAKER = "speaker"
    BUZZER = "buzzer"
    LIGHT = "light"
    SHADE = "shade"
    LOCK = "lock"
    THERMOSTAT = "thermostat"
    FIREPLACE = "fireplace"
    TV_MOUNT = "tv_mount"
    GRIPPER = "gripper"
    LINEAR_ACTUATOR = "linear_actuator"
    JOINT = "joint"
    GENERIC = "generic"


@dataclass
class ActuatorConstraints:
    """Safety and operational constraints for an actuator.

    These constraints are used by SafeHAL to enforce CBF safety:
    - Commands outside [min_value, max_value] are clamped or rejected
    - Rate limits prevent damage from too-fast actuation
    - Power limits prevent thermal damage
    - Safe defaults are used during emergency stop

    Mathematical basis:
    - Safe set: C = {x | min_value <= x <= max_value}
    - Rate constraint: |dx/dt| <= max_rate
    - Acceleration constraint: |d²x/dt²| <= max_acceleration
    """

    actuator_type: ActuatorType
    min_value: float = 0.0
    max_value: float = 1.0
    max_rate: float | None = None  # Units per second
    max_acceleration: float | None = None  # Units per second^2
    safe_default: float = 0.0  # Value during emergency stop
    power_limit_watts: float | None = None
    thermal_limit_c: float | None = None
    dimensions: dict[str, Any] = field(default_factory=dict)  # Extra metadata

    def is_within_bounds(self, value: float) -> bool:
        """Check if a value is within safe bounds.

        Alias for is_value_safe for API compatibility.
        """
        return self.min_value <= value <= self.max_value

    def is_value_safe(self, value: float) -> bool:
        """Check if a value is within safe bounds."""
        return self.is_within_bounds(value)

    def is_rate_safe(
        self,
        current: float,
        target: float,
        dt: float,
    ) -> bool:
        """Check if the rate of change is within limits.

        Args:
            current: Current actuator value
            target: Target value
            dt: Time delta in seconds

        Returns:
            True if the rate is safe
        """
        if self.max_rate is None:
            return True
        if dt <= 0:
            return current == target

        rate = abs(target - current) / dt
        return rate <= self.max_rate

    def is_acceleration_safe(
        self,
        current_velocity: float,
        target_velocity: float,
        dt: float,
    ) -> bool:
        """Check if the acceleration is within limits.

        Args:
            current_velocity: Current velocity
            target_velocity: Target velocity
            dt: Time delta in seconds

        Returns:
            True if the acceleration is safe
        """
        if self.max_acceleration is None:
            return True
        if dt <= 0:
            return current_velocity == target_velocity

        acceleration = abs(target_velocity - current_velocity) / dt
        return acceleration <= self.max_acceleration

    def clamp(self, value: float) -> float:
        """Clamp value to safe range."""
        return max(self.min_value, min(self.max_value, value))


@runtime_checkable
class IActuator(Protocol):
    """Protocol for actuator implementations.

    All actuators must implement this interface to work with SafeHAL.
    The CBF safety layer intercepts all write() calls to verify h(x) >= 0.
    """

    async def initialize(self) -> None:
        """Initialize the actuator hardware."""
        ...

    async def shutdown(self) -> None:
        """Safely shut down the actuator."""
        ...

    async def get_constraints(self) -> ActuatorConstraints:
        """Get the actuator's operational and safety constraints."""
        ...

    async def write(self, value: NDArray[np.float32] | float) -> None:
        """Write a command to the actuator.

        Args:
            value: Command value (scalar or array depending on actuator type)

        Raises:
            SafetyViolation: If the command would violate CBF safety constraints
            RuntimeError: If the actuator is not initialized
        """
        ...

    async def read(self) -> NDArray[np.float32] | float:
        """Read the current actuator state/position."""
        ...

    async def emergency_stop(self) -> None:
        """Immediately stop the actuator and enter safe state."""
        ...

    async def reset(self) -> None:
        """Reset the actuator after emergency stop."""
        ...
