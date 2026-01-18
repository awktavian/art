"""Shared HAL types to prevent circular dependencies.

Contains type definitions shared between hal.manager and hal.metrics_adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Platform(Enum):
    """Supported hardware platforms."""

    LINUX = "linux"
    MACOS = "darwin"
    WINDOWS = "windows"
    ANDROID = "android"
    IOS = "ios"
    WATCHOS = "watchos"  # Apple Watch
    WEAROS = "wearos"  # Wear OS (Google/Samsung)
    EMBEDDED = "embedded"
    WASM = "wasm"
    AGUI = "agui"
    VIRTUAL = "virtual"  # Virtual/mock adapters for testing
    UNKNOWN = "unknown"


@dataclass
class HALStatus:
    """HAL subsystem status for monitoring and metrics.

    Attributes:
        platform: Current operating platform
        display_available: Display adapter available
        audio_available: Audio adapter available
        input_available: Input adapter available
        sensors_available: Sensor adapter available
        power_available: Power adapter available
        gesture_available: IMU gesture recognizer available
        gestural_available: sEMG gestural interface available
        wake_word_available: Wake word detection available
        mock_mode: Running with mock adapters
        adapters_initialized: Count of successful adapter inits
        adapters_failed: Count of failed adapter inits
    """

    platform: Platform
    display_available: bool
    audio_available: bool
    input_available: bool
    sensors_available: bool
    power_available: bool
    gesture_available: bool = False
    gestural_available: bool = False
    wake_word_available: bool = False
    mock_mode: bool = False
    adapters_initialized: int = 0
    adapters_failed: int = 0


from kagami_hal.protocols import (
    AudioAdapterProtocol,
    DisplayAdapterProtocol,
    InputAdapterProtocol,
    PowerAdapterProtocol,
    SensorAdapterProtocol,
)

__all__ = [
    "AudioAdapterProtocol",
    "DisplayAdapterProtocol",
    "HALStatus",
    "InputAdapterProtocol",
    "Platform",
    "PowerAdapterProtocol",
    "SensorAdapterProtocol",
]
