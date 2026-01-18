"""visionOS HAL adapters.

Platform-specific implementations for Apple Vision Pro.

Supports:
- Spatial computing APIs
- Eye tracking
- Hand tracking
- Body tracking (NEW - Meta Quest parity)
- Immersive spaces
- Spatial audio

Created: December 30, 2025
Updated: December 30, 2025 - Added body tracking for Meta Quest parity
"""

from kagami_hal.adapters.visionos.audio import VisionOSAudio
from kagami_hal.adapters.visionos.body import (
    BodyGesture,
    BodyJoint,
    BodyMovement,
    BodyPoseState,
    BodySkeleton,
    JointPosition,
    VisionOSBody,
)
from kagami_hal.adapters.visionos.gaze import VisionOSGaze
from kagami_hal.adapters.visionos.spatial import VisionOSSpatial

__all__ = [
    "BodyGesture",
    "BodyJoint",
    "BodyMovement",
    "BodyPoseState",
    "BodySkeleton",
    "JointPosition",
    "VisionOSAudio",
    # Body tracking
    "VisionOSBody",
    "VisionOSGaze",
    "VisionOSSpatial",
]
