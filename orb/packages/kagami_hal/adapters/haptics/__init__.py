"""Unified Haptics Adapters for HAL.

Provides cross-device haptic feedback abstraction:
- Wrist haptics (Meta Neural Band, Apple Watch)
- Controller haptics (Quest, Spatial controllers)
- Device haptics (Phone, tablet vibration)

Haptic feedback design principles:
- Functional over novelty: well-tested patterns for user tasks
- Balanced intensity: not too strong, not too weak
- Context-appropriate: different patterns for different actions
- User-adjustable: respect preferences and accessibility

References:
- Interhaptics XR Best Practices: https://interhaptics.medium.com/haptics-best-practices-use-cases-in-xr
- Haptics Industry Forum Guidelines: https://hapticsindustryforum.medium.com/haptics-in-xr-design-implementation-guidelines

Created: January 2026
"""

from kagami_hal.adapters.haptics.unified_haptics import (
    HapticDevice,
    HapticFeedback,
    HapticIntensity,
    HapticPattern,
    UnifiedHapticsController,
    get_haptics_controller,
)

__all__ = [
    "HapticDevice",
    "HapticFeedback",
    "HapticIntensity",
    "HapticPattern",
    "UnifiedHapticsController",
    "get_haptics_controller",
]
