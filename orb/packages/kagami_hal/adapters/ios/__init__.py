"""iOS HAL adapters.

Platform-specific implementations for iOS using iOS frameworks.

Created: November 10, 2025
Updated: January 12, 2026 - Added compute detection for Metal/Neural Engine
"""

from kagami_hal.adapters.ios.audio import iOSAudio
from kagami_hal.adapters.ios.compute import (
    ComputeCapabilityTier,
    ComputeProfile,
    IOSCompute,
    MetalCapabilities,
    MetalGPUFamily,
    NeuralEngineCapabilities,
    NeuralEngineGeneration,
    get_compute,
)
from kagami_hal.adapters.ios.display import iOSDisplay
from kagami_hal.adapters.ios.input import iOSInput
from kagami_hal.adapters.ios.power import iOSPower
from kagami_hal.adapters.ios.sensors import iOSSensors

__all__ = [
    "ComputeCapabilityTier",
    "ComputeProfile",
    "IOSCompute",
    "MetalCapabilities",
    "MetalGPUFamily",
    "NeuralEngineCapabilities",
    "NeuralEngineGeneration",
    "get_compute",
    "iOSAudio",
    "iOSDisplay",
    "iOSInput",
    "iOSPower",
    "iOSSensors",
]
