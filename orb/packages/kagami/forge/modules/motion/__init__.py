"""
Motion Module - Real character movement, animation, and retargeting
Includes motion retargeting, gesture generation, and facial animation.
Integrated with LLM for intelligent motion generation.
"""

from .facial_animator import (
    EmotionMapping,
    FacialAnimator,
    FacialExpression,
)
from .gesture_engine import GestureEngine
from .motion_retargeting import (
    BoneTransform,
    MotionClip,
    MotionFrame,
    MotionRetargeting,
)

__all__: list[str] = [
    "BoneTransform",
    "EmotionMapping",
    "FacialAnimator",
    "FacialExpression",
    "GestureEngine",
    "MotionClip",
    "MotionFrame",
    "MotionRetargeting",
]
