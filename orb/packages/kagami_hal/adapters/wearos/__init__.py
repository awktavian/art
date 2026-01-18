"""WearOS HAL adapters.

Platform-specific implementations for Wear OS smartwatches using Android APIs.

Supports:
- Wear OS 3.0+ (Galaxy Watch 4+, Pixel Watch, etc.)
- Rotary input (crown/bezel)
- Health Services (heart rate, SpO2, steps)
- Always-on display (AOD)
- Haptic feedback

Created: December 13, 2025
"""

from kagami_hal.adapters.wearos.audio import WearOSAudio
from kagami_hal.adapters.wearos.display import WearOSDisplay
from kagami_hal.adapters.wearos.input import WearOSInput
from kagami_hal.adapters.wearos.power import WearOSPower
from kagami_hal.adapters.wearos.sensors import WearOSSensors

__all__ = [
    "WearOSAudio",
    "WearOSDisplay",
    "WearOSInput",
    "WearOSPower",
    "WearOSSensors",
]
