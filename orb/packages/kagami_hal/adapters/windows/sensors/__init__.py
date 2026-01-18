"""Windows sensor adapters.

Platform-specific sensor implementations for Windows.

Created: December 15, 2025
"""

from kagami_hal.adapters.windows.sensors.camera import WindowsDirectShowCamera
from kagami_hal.adapters.windows.sensors.microphone import WindowsWASAPIMicrophone
from kagami_hal.adapters.windows.sensors.power import WindowsBatterySensor
from kagami_hal.adapters.windows.sensors.thermal import WindowsWMIThermal

__all__ = [
    "WindowsBatterySensor",
    "WindowsDirectShowCamera",
    "WindowsWASAPIMicrophone",
    "WindowsWMIThermal",
]
