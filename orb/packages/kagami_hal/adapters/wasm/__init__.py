"""WASM HAL adapters.

Platform-specific implementations for WebAssembly using Web APIs.

Created: November 10, 2025
"""

from kagami_hal.adapters.wasm.audio import WASMAudio
from kagami_hal.adapters.wasm.display import WASMDisplay
from kagami_hal.adapters.wasm.input import WASMInput
from kagami_hal.adapters.wasm.power import WASMPower
from kagami_hal.adapters.wasm.sensors import WASMSensors

__all__ = [
    "WASMAudio",
    "WASMDisplay",
    "WASMInput",
    "WASMPower",
    "WASMSensors",
]
