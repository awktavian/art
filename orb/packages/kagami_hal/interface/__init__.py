"""HAL Interface Module.

Provides protocol definitions and safety-wrapped interfaces for hardware access.

This module defines the contracts that all HAL adapters must implement,
as well as the SafeHAL layer that enforces CBF safety constraints.

Key Components:
- Actuator interfaces (IActuator, ActuatorType, ActuatorConstraints)
- Sensor interfaces (ISensor, SensorType, SensorCapability, SensorReading)
- Platform capabilities (PlatformCapabilities, ComputeCapabilities, PowerMode)
- Safety layer (SafeHAL, SafetyViolation, SafetyZone, SafetyStats)
- I/O management (HALIOManager)

Safety Guarantee:
All actuator commands pass through SafeHAL which enforces h(x) >= 0.
This ensures the system remains in the safe set C = {x | h(x) >= 0}.
"""

# Actuator interfaces
from kagami_hal.interface.actuators import (
    ActuatorConstraints,
    ActuatorType,
    IActuator,
)

# I/O management
from kagami_hal.interface.io_manager import (
    HALIOManager,
    IOEvent,
    StreamHandle,
    StreamStats,
)

# Platform capabilities
from kagami_hal.interface.platform import (
    ComputeBackend,
    ComputeCapabilities,
    PlatformCapabilities,
    PlatformType,
    PowerMode,
)

# Safety layer
from kagami_hal.interface.safe_hal import (
    ActuationResult,
    ProjectionResult,
    SafeHAL,
    SafetyStats,
    SafetyViolation,
    SafetyZone,
)

# Sensor interfaces
from kagami_hal.interface.sensors import (
    ISensor,
    SensorCapability,
    SensorReading,
    SensorType,
)

__all__ = [
    # Safety
    "ActuationResult",
    # Actuators
    "ActuatorConstraints",
    "ActuatorType",
    # Platform
    "ComputeBackend",
    "ComputeCapabilities",
    # I/O Manager
    "HALIOManager",
    "IActuator",
    "IOEvent",
    # Sensors
    "ISensor",
    "PlatformCapabilities",
    "PlatformType",
    "PowerMode",
    "ProjectionResult",
    "SafeHAL",
    "SafetyStats",
    "SafetyViolation",
    "SafetyZone",
    "SensorCapability",
    "SensorReading",
    "SensorType",
    "StreamHandle",
    "StreamStats",
]
