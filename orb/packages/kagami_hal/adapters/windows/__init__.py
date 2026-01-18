"""Windows HAL adapters.

Platform-specific implementations for Windows using Win32 APIs.

Architecture:
- Core adapters: Display, Audio, Input, Sensors, Power
- Sensor modules: Camera (DirectShow), Microphone (WASAPI), Thermal (WMI), Battery
- Actuator modules: Display (GDI), Speaker (WASAPI)
- Compute detection: CUDA, DirectML, Vulkan, OpenCL

Created: November 10, 2025
Updated: December 15, 2025 - Added specialized sensors, actuators, and compute detection
"""

# Core adapters (legacy compatibility)
# Actuators
from kagami_hal.adapters.windows.actuators.display import WindowsGDIDisplayActuator
from kagami_hal.adapters.windows.actuators.speaker import WindowsWASAPISpeaker
from kagami_hal.adapters.windows.audio import WindowsWASAPIAudio

# Compute detection
from kagami_hal.adapters.windows.compute import (
    ComputeCapabilities,
    WindowsComputeDetector,
)
from kagami_hal.adapters.windows.display import WindowsGDIDisplay
from kagami_hal.adapters.windows.input import WindowsInput
from kagami_hal.adapters.windows.power import WindowsPower
from kagami_hal.adapters.windows.sensor_adapter import WindowsSensors

# Specialized sensors
from kagami_hal.adapters.windows.sensors.camera import WindowsDirectShowCamera
from kagami_hal.adapters.windows.sensors.microphone import WindowsWASAPIMicrophone
from kagami_hal.adapters.windows.sensors.power import WindowsBatterySensor
from kagami_hal.adapters.windows.sensors.thermal import WindowsWMIThermal

__all__ = [
    "ComputeCapabilities",
    "WindowsBatterySensor",
    # Compute
    "WindowsComputeDetector",
    # Specialized sensors
    "WindowsDirectShowCamera",
    # Core adapters
    "WindowsGDIDisplay",
    # Actuators
    "WindowsGDIDisplayActuator",
    "WindowsInput",
    "WindowsPower",
    "WindowsSensors",
    "WindowsWASAPIAudio",
    "WindowsWASAPIMicrophone",
    "WindowsWASAPISpeaker",
    "WindowsWMIThermal",
]
