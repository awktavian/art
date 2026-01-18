"""Android HAL adapters.

Platform-specific implementations for Android using Android APIs.

Created: November 10, 2025
"""

from kagami_hal.adapters.android.audio import AndroidAudio
from kagami_hal.adapters.android.display import AndroidDisplay
from kagami_hal.adapters.android.input import AndroidInput
from kagami_hal.adapters.android.power import AndroidPower
from kagami_hal.adapters.android.sensors import AndroidSensors

__all__ = [
    "AndroidAudio",
    "AndroidDisplay",
    "AndroidInput",
    "AndroidPower",
    "AndroidSensors",
]
