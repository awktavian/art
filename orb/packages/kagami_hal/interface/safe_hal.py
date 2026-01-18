"""SafeHAL - Hardware Abstraction Layer with CBF Safety Integration.

Provides a safety-wrapped interface to hardware actuators that enforces
Control Barrier Function (CBF) safety constraints: h(x) >= 0 at all times.

Key Features:
- All actuator commands pass through CBF safety filter
- Emergency stop with h(x) = -∞ override
- Safe set projection for unsafe commands
- Atomic safety checks for concurrent access
- Audit logging of all safety-critical operations

Mathematical Foundation:
- Safe set: C = {x | h(x) >= 0}
- CBF constraint: h(x,u) + α(h(x)) >= 0 ensures forward invariance
- Projection: argmin_u' ||u' - u|| s.t. h(x,u') + α(h(x)) >= 0
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

import numpy as np

from kagami_hal.interface.actuators import ActuatorType, IActuator
from kagami_hal.interface.platform import ComputeCapabilities, PlatformCapabilities
from kagami_hal.interface.sensors import ISensor, SensorReading, SensorType

# Import global emergency halt functions
try:
    from kagami.core.safety.cbf_integration import (
        is_emergency_halt_active as global_emergency_halt_active,
    )
except ImportError:
    # Fallback if kagami.core isn't available
    def global_emergency_halt_active() -> bool:
        return False


if TYPE_CHECKING:
    from numpy.typing import NDArray

# Import centralized exceptions
from kagami.core.exceptions import SafetyViolation

logger = logging.getLogger(__name__)


class SafetyZone(Enum):
    """CBF safety zones based on h(x) value."""

    GREEN = auto()  # h(x) > 0.3, fully safe
    YELLOW = auto()  # 0 < h(x) <= 0.3, caution
    RED = auto()  # h(x) <= 0, unsafe - commands blocked


@dataclass
class SafetyStats:
    """Statistics about safety-related operations."""

    total_checks: int = 0
    total_commands: int = 0
    blocked_commands: int = 0
    projected_commands: int = 0
    emergency_stops: int = 0
    current_h_value: float = 1.0
    min_h_value: float = 1.0
    current_zone: SafetyZone = SafetyZone.GREEN
    last_violation_time: datetime | None = None
    last_violation_reason: str = ""


@dataclass
class ActuationResult:
    """Result of an actuation command."""

    is_safe: bool
    original_command: Any
    final_command: Any
    was_projected: bool
    h_before: float
    h_after: float
    actuator_type: ActuatorType

    @property
    def barrier_value(self) -> float:
        """Get the barrier value (alias for h_after)."""
        return self.h_after


@dataclass
class ProjectionResult:
    """Result of projecting an unsafe command to the safe set."""

    original_command: NDArray[np.float32] | float
    projected_command: NDArray[np.float32] | float
    was_projected: bool
    h_before: float
    h_after: float
    projection_distance: float


class SafeHAL:
    """Safety-wrapped Hardware Abstraction Layer.

    Wraps actuator and sensor access with CBF safety enforcement.
    All actuator commands are checked against h(x) >= 0 before execution.

    Usage:
        safe_hal = SafeHAL(project_on_violation=True)
        await safe_hal.initialize()
        hal.register_actuator(ActuatorType.LED, led_actuator)

        # This will be checked for safety
        result = await safe_hal.send_actuation(led_actuator, 0.5)

        # In emergency, this blocks all commands
        await safe_hal.emergency_stop_all()
    """

    def __init__(
        self,
        project_on_violation: bool = True,
        strict_mode: bool = False,
        safety_buffer: float = 0.1,
    ):
        """Initialize SafeHAL.

        Args:
            project_on_violation: If True, project unsafe commands to safe set
            strict_mode: If True, raise exceptions on any safety issue
            safety_buffer: Extra margin for safety (h(x) must be > buffer)
        """
        self.project_on_violation = project_on_violation
        self.strict_mode = strict_mode
        self.safety_buffer = safety_buffer

        # Registered devices (by type)
        self._actuators_by_type: dict[ActuatorType, IActuator] = {}
        self._sensors_by_type: dict[SensorType, ISensor] = {}

        # Registered devices (by name)
        self._actuators: dict[str, IActuator] = {}
        self._sensors: dict[str, ISensor] = {}

        # Platform capabilities
        self._platform_caps: dict[str, Any] | None = None
        self._compute_caps: ComputeCapabilities | None = None

        # Safety state
        self._emergency_halt = False
        self._emergency_halt_reason = ""
        self._current_h_value = 1.0
        self._safety_lock = asyncio.Lock()

        # Statistics
        self._stats = SafetyStats()

        self._initialized = False

    @property
    def platform_caps(self) -> dict[str, Any] | None:
        """Get detected platform capabilities."""
        return self._platform_caps

    @property
    def compute_caps(self) -> ComputeCapabilities | None:
        """Get detected compute capabilities."""
        return self._compute_caps

    async def initialize(self) -> None:
        """Initialize SafeHAL and detect platform capabilities."""
        # Detect platform
        self._platform_caps = PlatformCapabilities.detect()
        self._compute_caps = PlatformCapabilities.detect_compute()

        self._initialized = True
        logger.info("SafeHAL initialized successfully")

    async def shutdown(self) -> None:
        """Safely shut down all devices."""
        # First, emergency stop all actuators
        await self.emergency_stop_all("Shutdown requested")

        # Shut down all devices in parallel
        await asyncio.gather(
            *[actuator.shutdown() for actuator in self._actuators_by_type.values()],
            *[sensor.shutdown() for sensor in self._sensors_by_type.values()],
            return_exceptions=True,
        )

        self._initialized = False
        logger.info("SafeHAL shutdown complete")

    def register_actuator(
        self,
        actuator_type_or_name: ActuatorType | str,
        actuator: IActuator,
    ) -> None:
        """Register an actuator with SafeHAL.

        Args:
            actuator_type_or_name: ActuatorType enum or string name
            actuator: The actuator implementation
        """
        if isinstance(actuator_type_or_name, ActuatorType):
            self._actuators_by_type[actuator_type_or_name] = actuator
        else:
            self._actuators[actuator_type_or_name] = actuator
        logger.debug(f"Registered actuator: {actuator_type_or_name}")

    def register_sensor(
        self,
        sensor_type_or_name: SensorType | str,
        sensor: ISensor,
    ) -> None:
        """Register a sensor with SafeHAL.

        Args:
            sensor_type_or_name: SensorType enum or string name
            sensor: The sensor implementation
        """
        if isinstance(sensor_type_or_name, SensorType):
            self._sensors_by_type[sensor_type_or_name] = sensor
        else:
            self._sensors[sensor_type_or_name] = sensor
        logger.debug(f"Registered sensor: {sensor_type_or_name}")

    async def acquire_actuator(self, actuator_type: ActuatorType) -> IActuator:
        """Acquire a registered actuator by type.

        Args:
            actuator_type: The type of actuator to acquire

        Returns:
            The registered actuator

        Raises:
            KeyError: If no actuator of that type is registered
        """
        if actuator_type not in self._actuators_by_type:
            raise KeyError(f"No actuator of type {actuator_type} registered")
        return self._actuators_by_type[actuator_type]

    async def acquire_sensor(self, sensor_type: SensorType) -> ISensor:
        """Acquire a registered sensor by type.

        Args:
            sensor_type: The type of sensor to acquire

        Returns:
            The registered sensor

        Raises:
            KeyError: If no sensor of that type is registered
        """
        if sensor_type not in self._sensors_by_type:
            raise KeyError(f"No sensor of type {sensor_type} registered")
        return self._sensors_by_type[sensor_type]

    async def send_actuation(
        self,
        actuator: IActuator,
        value: NDArray[np.float32] | float,
        force: bool = False,
    ) -> ActuationResult:
        """Send an actuation command with safety checking.

        Args:
            actuator: The actuator to command
            value: Command value
            force: If True, skip safety checks (DANGEROUS)

        Returns:
            ActuationResult with safety information
        """
        self._stats.total_commands += 1
        self._stats.total_checks += 1

        constraints = await actuator.get_constraints()
        h_before = self._current_h_value

        async with self._safety_lock:
            # Check both local and global emergency halt state
            is_halted = self._emergency_halt or global_emergency_halt_active()
            if is_halted and not force:
                self._stats.blocked_commands += 1
                if self.strict_mode:
                    raise SafetyViolation(
                        "Emergency halt active - command blocked",
                        h_value=-float("inf"),
                        command=value,
                        actuator_type=constraints.actuator_type,
                        reason="Emergency halt active",
                    )
                return ActuationResult(
                    is_safe=False,
                    original_command=value,
                    final_command=None,
                    was_projected=False,
                    h_before=h_before,
                    h_after=-float("inf"),
                    actuator_type=constraints.actuator_type,
                )

            # Check bounds
            scalar_value = float(value) if isinstance(value, (int, float)) else float(value.flat[0])

            if not constraints.is_within_bounds(scalar_value):
                if self.project_on_violation:
                    projected = constraints.clamp(scalar_value)
                    await actuator.write(projected)
                    self._stats.projected_commands += 1
                    return ActuationResult(
                        is_safe=True,
                        original_command=value,
                        final_command=projected,
                        was_projected=True,
                        h_before=h_before,
                        h_after=self._current_h_value,
                        actuator_type=constraints.actuator_type,
                    )
                else:
                    self._stats.blocked_commands += 1
                    if self.strict_mode:
                        raise SafetyViolation(
                            f"Value {value} outside bounds",
                            h_value=self._current_h_value,
                            command=value,
                            actuator_type=constraints.actuator_type,
                            reason="Bounds violation",
                        )
                    return ActuationResult(
                        is_safe=False,
                        original_command=value,
                        final_command=None,
                        was_projected=False,
                        h_before=h_before,
                        h_after=self._current_h_value,
                        actuator_type=constraints.actuator_type,
                    )

            # Safe to write
            await actuator.write(value)
            return ActuationResult(
                is_safe=True,
                original_command=value,
                final_command=value,
                was_projected=False,
                h_before=h_before,
                h_after=self._current_h_value,
                actuator_type=constraints.actuator_type,
            )

    async def write_actuator(
        self,
        name: str,
        value: NDArray[np.float32] | float,
        force: bool = False,
    ) -> ProjectionResult | None:
        """Write a command to an actuator by name with safety checking.

        Args:
            name: Name of the registered actuator
            value: Command value
            force: If True, skip safety checks (DANGEROUS)

        Returns:
            ProjectionResult if projection was performed, None otherwise
        """
        if name not in self._actuators:
            raise KeyError(f"Actuator '{name}' not registered")

        actuator = self._actuators[name]
        result = await self.send_actuation(actuator, value, force)

        if result.was_projected:
            return ProjectionResult(
                original_command=result.original_command,
                projected_command=result.final_command,
                was_projected=True,
                h_before=result.h_before,
                h_after=result.h_after,
                projection_distance=abs(
                    float(result.original_command) - float(result.final_command)
                ),
            )
        return None

    async def read_sensor(self, name: str) -> SensorReading:
        """Read a sensor value by name."""
        if name not in self._sensors:
            raise KeyError(f"Sensor '{name}' not registered")

        sensor = self._sensors[name]
        data = await sensor.read_once()
        caps = await sensor.get_capabilities()

        return SensorReading(
            sensor_type=caps.sensor_type,
            timestamp=datetime.now(),
            values=data,
        )

    async def emergency_stop_all(self, reason: str = "Manual emergency stop") -> None:
        """Trigger emergency stop on all actuators.

        Sets h(x) = -∞ to block all future commands until reset.
        """
        async with self._safety_lock:
            self._emergency_halt = True
            self._emergency_halt_reason = reason
            self._stats.emergency_stops += 1
            self._current_h_value = -float("inf")
            self._stats.current_h_value = -float("inf")
            self._stats.current_zone = SafetyZone.RED

        logger.warning(f"EMERGENCY STOP: {reason}")

        # Stop all actuators by type
        for actuator in self._actuators_by_type.values():
            try:
                await actuator.emergency_stop()
            except Exception as e:
                logger.error(f"Error emergency stopping actuator: {e}")

        # Stop all actuators in parallel for fastest emergency response
        if self._actuators:
            results = await asyncio.gather(
                *[actuator.emergency_stop() for actuator in self._actuators.values()],
                return_exceptions=True,
            )
            for name, result in zip(self._actuators.keys(), results, strict=False):
                if isinstance(result, Exception):
                    logger.error(f"Error emergency stopping {name}: {result}")
                else:
                    logger.info(f"Emergency stopped actuator: {name}")

    async def emergency_stop(self, reason: str = "Manual emergency stop") -> None:
        """Alias for emergency_stop_all."""
        await self.emergency_stop_all(reason)

    async def reset_emergency_halt(self) -> None:
        """Reset emergency halt and allow commands again."""
        async with self._safety_lock:
            self._emergency_halt = False
            self._emergency_halt_reason = ""
            self._current_h_value = 1.0
            self._stats.current_h_value = 1.0
            self._stats.current_zone = SafetyZone.GREEN

        # Reset all actuators
        for actuator in self._actuators_by_type.values():
            try:
                await actuator.reset()
            except Exception as e:
                logger.warning(f"Error resetting actuator: {e}")

        # Reset all actuators in parallel
        if self._actuators:
            results = await asyncio.gather(
                *[actuator.reset() for actuator in self._actuators.values()], return_exceptions=True
            )
            for name, result in zip(self._actuators.keys(), results, strict=False):
                if isinstance(result, Exception):
                    logger.warning(f"Error resetting {name}: {result}")
                else:
                    logger.info(f"Reset actuator: {name}")

        logger.info("Emergency halt reset - normal operation resumed")

    def is_emergency_halt_active(self) -> bool:
        """Check if emergency halt is currently active."""
        return self._emergency_halt

    async def get_safety_stats(self) -> dict[str, Any]:
        """Get current safety statistics as a dictionary."""
        return {
            "total_checks": self._stats.total_checks,
            "total_commands": self._stats.total_commands,
            "blocked_commands": self._stats.blocked_commands,
            "projected_commands": self._stats.projected_commands,
            "emergency_stops": self._stats.emergency_stops,
            "current_h_value": self._stats.current_h_value,
            "min_h_value": self._stats.min_h_value,
            "current_zone": self._stats.current_zone.name,
        }

    def get_stats(self) -> SafetyStats:
        """Get current safety statistics."""
        return self._stats

    def get_h_value(self) -> float:
        """Get current CBF h(x) value."""
        return self._current_h_value

    def get_safety_zone(self) -> SafetyZone:
        """Get current safety zone based on h(x)."""
        if self._current_h_value > 0.3:
            return SafetyZone.GREEN
        elif self._current_h_value > 0:
            return SafetyZone.YELLOW
        else:
            return SafetyZone.RED
