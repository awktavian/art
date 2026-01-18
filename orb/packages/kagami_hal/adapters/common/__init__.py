"""Common HAL adapter utilities and cross-device abstractions.

Provides:
- Unified gesture vocabulary (cross-device)
- Common sensor interfaces
- Shared utilities
- Adapter mixins (volume, subscription, power)

Created: December 30, 2025
"""

from kagami_hal.adapters.common.mixins import (
    PowerModeMixin,
    SubscriptionMixin,
    VolumeMixin,
)
from kagami_hal.adapters.common.unified_gestures import (
    DeviceType,
    Gesture,
    GestureAction,
    GestureBinding,
    GestureRegistry,
    GestureSource,
    get_gesture_registry,
)

__all__ = [
    # Gestures
    "DeviceType",
    "Gesture",
    "GestureAction",
    "GestureBinding",
    "GestureRegistry",
    "GestureSource",
    "PowerModeMixin",
    # Mixins
    "SubscriptionMixin",
    "VolumeMixin",
    "get_gesture_registry",
]
