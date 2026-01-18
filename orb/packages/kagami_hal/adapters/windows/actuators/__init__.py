"""Windows actuator adapters.

Platform-specific actuator implementations for Windows.

Created: December 15, 2025
"""

from kagami_hal.adapters.windows.actuators.display import WindowsGDIDisplayActuator
from kagami_hal.adapters.windows.actuators.speaker import WindowsWASAPISpeaker

__all__ = [
    "WindowsGDIDisplayActuator",
    "WindowsWASAPISpeaker",
]
