"""Neural Input Adapters for HAL.

Provides abstraction layer for neural wristband input devices:
- Meta Neural Band (sEMG-based wrist control)
- Future neural input devices

Neural input captures muscle signals from the wrist to enable:
- Thumb microgestures (tap, swipe)
- Finger-based EMG commands
- Low-effort interaction without cameras

Created: January 2026
"""

from kagami_hal.adapters.neural.meta_emg import (
    EMGCalibrationState,
    EMGConnectionState,
    EMGGesture,
    MetaEMGAdapter,
    MetaEMGConfig,
    MetaEMGEvent,
    get_meta_emg_adapter,
)

__all__ = [
    "EMGCalibrationState",
    "EMGConnectionState",
    "EMGGesture",
    "MetaEMGAdapter",
    "MetaEMGConfig",
    "MetaEMGEvent",
    "get_meta_emg_adapter",
]
