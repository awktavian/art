"""WatchOS HAL adapters.

Platform-specific implementations for Apple Watch using WatchKit/HealthKit frameworks.

Supports:
- Apple Watch Series 4+ (watchOS 5.0+)
- Digital Crown input
- Heart rate, accelerometer, gyroscope sensors
- Taptic Engine haptics
- Always-on display (AOD)

Created: December 13, 2025
"""

from kagami_hal.adapters.watchos.audio import WatchOSAudio
from kagami_hal.adapters.watchos.display import WatchOSDisplay
from kagami_hal.adapters.watchos.input import WatchOSInput
from kagami_hal.adapters.watchos.power import WatchOSPower
from kagami_hal.adapters.watchos.sensors import WatchOSSensors

__all__ = [
    "WatchOSAudio",
    "WatchOSDisplay",
    "WatchOSInput",
    "WatchOSPower",
    "WatchOSSensors",
]
