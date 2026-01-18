"""visionOS Body Tracking Adapter — Full Body Pose Estimation.

Provides body tracking capabilities via ARKit/RealityKit on Vision Pro,
with future parity planned for Meta Quest body tracking.

Body Tracking Features:
- Full skeleton tracking (20+ joints)
- Body pose estimation
- Movement detection
- Gesture recognition

Future Meta Quest Parity:
- Meta Movement SDK integration
- Cross-platform body tracking abstraction
- Unified pose format

Note: Body tracking on Vision Pro requires ARKit permissions and
may be limited compared to dedicated body tracking hardware.

Created: December 30, 2025
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class BodyJoint(Enum):
    """Body skeleton joints."""

    # Head
    HEAD = "head"
    NECK = "neck"

    # Torso
    SPINE_BASE = "spine_base"
    SPINE_MID = "spine_mid"
    SPINE_SHOULDER = "spine_shoulder"

    # Left Arm
    LEFT_SHOULDER = "left_shoulder"
    LEFT_ELBOW = "left_elbow"
    LEFT_WRIST = "left_wrist"
    LEFT_HAND = "left_hand"

    # Right Arm
    RIGHT_SHOULDER = "right_shoulder"
    RIGHT_ELBOW = "right_elbow"
    RIGHT_WRIST = "right_wrist"
    RIGHT_HAND = "right_hand"

    # Left Leg
    LEFT_HIP = "left_hip"
    LEFT_KNEE = "left_knee"
    LEFT_ANKLE = "left_ankle"
    LEFT_FOOT = "left_foot"

    # Right Leg
    RIGHT_HIP = "right_hip"
    RIGHT_KNEE = "right_knee"
    RIGHT_ANKLE = "right_ankle"
    RIGHT_FOOT = "right_foot"


class BodyPoseState(Enum):
    """Body pose states."""

    STANDING = "standing"
    SITTING = "sitting"
    LYING_DOWN = "lying_down"
    WALKING = "walking"
    REACHING = "reaching"
    BENDING = "bending"
    UNKNOWN = "unknown"


@dataclass
class JointPosition:
    """3D position of a body joint."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    confidence: float = 0.0

    def distance_to(self, other: JointPosition) -> float:
        """Calculate distance to another joint."""
        import math

        return math.sqrt(
            (self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2
        )


@dataclass
class BodySkeleton:
    """Full body skeleton with joint positions."""

    timestamp: float = field(default_factory=time.time)
    joints: dict[BodyJoint, JointPosition] = field(default_factory=dict)
    confidence: float = 0.0

    # Derived state
    pose_state: BodyPoseState = BodyPoseState.UNKNOWN
    is_tracked: bool = False

    def get_joint(self, joint: BodyJoint) -> JointPosition | None:
        """Get position of a specific joint."""
        return self.joints.get(joint)

    @property
    def head_position(self) -> JointPosition | None:
        """Get head position."""
        return self.joints.get(BodyJoint.HEAD)

    @property
    def left_hand_position(self) -> JointPosition | None:
        """Get left hand position."""
        return self.joints.get(BodyJoint.LEFT_HAND)

    @property
    def right_hand_position(self) -> JointPosition | None:
        """Get right hand position."""
        return self.joints.get(BodyJoint.RIGHT_HAND)


@dataclass
class BodyMovement:
    """Detected body movement."""

    movement_type: str
    velocity: float = 0.0
    direction: tuple[float, float, float] = (0.0, 0.0, 0.0)
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class BodyGesture:
    """Recognized body gesture."""

    gesture_name: str  # "wave", "point", "raise_hand", etc.
    hand: str = "either"  # "left", "right", "both", "either"
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)


SkeletonCallback = Callable[[BodySkeleton], Awaitable[None]]
MovementCallback = Callable[[BodyMovement], Awaitable[None]]
GestureCallback = Callable[[BodyGesture], Awaitable[None]]


class VisionOSBody:
    """Body tracking adapter for visionOS (Vision Pro).

    Provides full body pose estimation using ARKit's body tracking.

    Note: Body tracking on Vision Pro is currently limited compared
    to dedicated body tracking systems. This adapter is designed for
    future parity with Meta Quest body tracking.

    Usage:
        body = VisionOSBody()
        await body.initialize(api_url)

        # Get current skeleton
        skeleton = await body.get_skeleton()
        if skeleton.is_tracked:
            print(f"Pose: {skeleton.pose_state.value}")
            print(f"Head at: {skeleton.head_position}")

        # Register for updates
        body.on_skeleton(handle_skeleton)
        body.on_gesture(handle_gesture)
    """

    def __init__(self) -> None:
        self._api_base_url: str | None = None
        self._tracking = False

        # Current state
        self._current_skeleton: BodySkeleton | None = None
        self._last_skeleton_time = 0.0

        # Callbacks
        self._skeleton_callbacks: list[SkeletonCallback] = []
        self._movement_callbacks: list[MovementCallback] = []
        self._gesture_callbacks: list[GestureCallback] = []

        # Movement tracking
        self._previous_skeleton: BodySkeleton | None = None
        self._movement_threshold = 0.1  # meters

        # Gesture recognition
        self._gesture_recognizers: dict[str, Callable[[BodySkeleton], bool]] = {}
        self._register_default_gestures()

    async def initialize(self, api_base_url: str = "http://kagami.local:8001") -> bool:
        """Initialize body tracking adapter.

        Args:
            api_base_url: Base URL of Kagami API

        Returns:
            True if initialization successful
        """
        self._api_base_url = api_base_url

        # Register for body tracking updates from visionOS client
        logger.info("VisionOSBody initialized")
        return True

    async def start_tracking(self) -> bool:
        """Start body tracking.

        Returns:
            True if tracking started
        """
        if not self._api_base_url:
            logger.warning("Body tracking not initialized")
            return False

        self._tracking = True
        logger.info("Body tracking started")
        return True

    async def stop_tracking(self) -> None:
        """Stop body tracking."""
        self._tracking = False
        logger.info("Body tracking stopped")

    async def get_skeleton(self) -> BodySkeleton | None:
        """Get current body skeleton.

        Returns:
            BodySkeleton if tracking, None otherwise
        """
        if not self._tracking:
            return None

        # In real implementation, this would fetch from visionOS client
        # For now, return cached skeleton
        return self._current_skeleton

    def update_skeleton(self, data: dict[str, Any]) -> None:
        """Update skeleton from visionOS client data.

        Args:
            data: Skeleton data from visionOS client
        """
        skeleton = self._parse_skeleton_data(data)

        if skeleton:
            # Detect movement
            if self._previous_skeleton:
                self._detect_movement(self._previous_skeleton, skeleton)

            # Recognize gestures
            self._recognize_gestures(skeleton)

            # Update state
            self._previous_skeleton = self._current_skeleton
            self._current_skeleton = skeleton
            self._last_skeleton_time = time.time()

    def _parse_skeleton_data(self, data: dict[str, Any]) -> BodySkeleton | None:
        """Parse skeleton data from visionOS format."""
        joints_data = data.get("joints", {})
        if not joints_data:
            return None

        joints = {}
        for joint_name, joint_data in joints_data.items():
            try:
                joint = BodyJoint(joint_name)
                joints[joint] = JointPosition(
                    x=joint_data.get("x", 0.0),
                    y=joint_data.get("y", 0.0),
                    z=joint_data.get("z", 0.0),
                    confidence=joint_data.get("confidence", 0.0),
                )
            except ValueError:
                pass  # Unknown joint

        skeleton = BodySkeleton(
            timestamp=data.get("timestamp", time.time()),
            joints=joints,
            confidence=data.get("confidence", 0.0),
            is_tracked=len(joints) >= 10,  # Need at least 10 joints
        )

        # Infer pose state
        skeleton.pose_state = self._infer_pose_state(skeleton)

        return skeleton

    def _infer_pose_state(self, skeleton: BodySkeleton) -> BodyPoseState:
        """Infer body pose state from skeleton."""
        head = skeleton.get_joint(BodyJoint.HEAD)
        spine_base = skeleton.get_joint(BodyJoint.SPINE_BASE)

        if not head or not spine_base:
            return BodyPoseState.UNKNOWN

        # Check vertical distance between head and spine base
        vertical_dist = head.y - spine_base.y

        if vertical_dist < 0.3:
            return BodyPoseState.LYING_DOWN
        elif vertical_dist < 0.7:
            return BodyPoseState.SITTING
        else:
            # Check for arm extension (reaching)
            left_hand = skeleton.get_joint(BodyJoint.LEFT_HAND)
            right_hand = skeleton.get_joint(BodyJoint.RIGHT_HAND)
            spine_shoulder = skeleton.get_joint(BodyJoint.SPINE_SHOULDER)

            if spine_shoulder:
                if left_hand and left_hand.y > spine_shoulder.y + 0.2:
                    return BodyPoseState.REACHING
                if right_hand and right_hand.y > spine_shoulder.y + 0.2:
                    return BodyPoseState.REACHING

            return BodyPoseState.STANDING

    def _detect_movement(self, prev: BodySkeleton, curr: BodySkeleton) -> None:
        """Detect movement between skeleton frames."""
        prev_head = prev.get_joint(BodyJoint.HEAD)
        curr_head = curr.get_joint(BodyJoint.HEAD)

        if not prev_head or not curr_head:
            return

        distance = prev_head.distance_to(curr_head)
        if distance > self._movement_threshold:
            movement = BodyMovement(
                movement_type="walking" if distance > 0.3 else "moving",
                velocity=distance / (curr.timestamp - prev.timestamp),
                direction=(
                    curr_head.x - prev_head.x,
                    curr_head.y - prev_head.y,
                    curr_head.z - prev_head.z,
                ),
                confidence=min(curr.confidence, prev.confidence),
            )
            self._emit_movement(movement)

    def _emit_movement(self, movement: BodyMovement) -> None:
        """Emit movement to callbacks."""
        import asyncio

        for callback in self._movement_callbacks:
            try:
                asyncio.create_task(callback(movement))
            except Exception as e:
                logger.error(f"Movement callback error: {e}")

    def _register_default_gestures(self) -> None:
        """Register default gesture recognizers."""
        self._gesture_recognizers["raise_hand"] = self._recognize_raise_hand
        self._gesture_recognizers["wave"] = self._recognize_wave
        self._gesture_recognizers["point"] = self._recognize_point

    def _recognize_raise_hand(self, skeleton: BodySkeleton) -> bool:
        """Recognize raised hand gesture."""
        left_hand = skeleton.get_joint(BodyJoint.LEFT_HAND)
        right_hand = skeleton.get_joint(BodyJoint.RIGHT_HAND)
        head = skeleton.get_joint(BodyJoint.HEAD)

        if not head:
            return False

        if left_hand and left_hand.y > head.y:
            return True
        if right_hand and right_hand.y > head.y:
            return True

        return False

    def _recognize_wave(self, skeleton: BodySkeleton) -> bool:
        """Recognize wave gesture (requires motion history)."""
        # Simplified: hand above shoulder and moving
        # Real implementation would track hand position over time
        return False

    def _recognize_point(self, skeleton: BodySkeleton) -> bool:
        """Recognize pointing gesture."""
        right_hand = skeleton.get_joint(BodyJoint.RIGHT_HAND)
        right_elbow = skeleton.get_joint(BodyJoint.RIGHT_ELBOW)
        right_shoulder = skeleton.get_joint(BodyJoint.RIGHT_SHOULDER)

        if not all([right_hand, right_elbow, right_shoulder]):
            return False

        # Check if arm is extended
        arm_length = right_hand.distance_to(right_shoulder)
        return arm_length > 0.5

    def _recognize_gestures(self, skeleton: BodySkeleton) -> None:
        """Run all gesture recognizers."""
        import asyncio

        for gesture_name, recognizer in self._gesture_recognizers.items():
            try:
                if recognizer(skeleton):
                    gesture = BodyGesture(
                        gesture_name=gesture_name,
                        confidence=skeleton.confidence,
                    )
                    for callback in self._gesture_callbacks:
                        asyncio.create_task(callback(gesture))
            except Exception as e:
                logger.debug(f"Gesture recognition error: {e}")

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_skeleton(self, callback: SkeletonCallback) -> None:
        """Register callback for skeleton updates."""
        self._skeleton_callbacks.append(callback)

    def on_movement(self, callback: MovementCallback) -> None:
        """Register callback for movement detection."""
        self._movement_callbacks.append(callback)

    def on_gesture(self, callback: GestureCallback) -> None:
        """Register callback for gesture recognition."""
        self._gesture_callbacks.append(callback)

    def add_gesture_recognizer(
        self,
        name: str,
        recognizer: Callable[[BodySkeleton], bool],
    ) -> None:
        """Add custom gesture recognizer.

        Args:
            name: Gesture name
            recognizer: Function that takes skeleton and returns bool
        """
        self._gesture_recognizers[name] = recognizer

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def is_tracking(self) -> bool:
        """Check if body tracking is active."""
        return self._tracking

    @property
    def has_skeleton(self) -> bool:
        """Check if we have a valid skeleton."""
        return self._current_skeleton is not None and self._current_skeleton.is_tracked

    @property
    def current_pose(self) -> BodyPoseState:
        """Get current pose state."""
        if self._current_skeleton:
            return self._current_skeleton.pose_state
        return BodyPoseState.UNKNOWN

    async def shutdown(self) -> None:
        """Shutdown body tracking."""
        await self.stop_tracking()
        self._skeleton_callbacks.clear()
        self._movement_callbacks.clear()
        self._gesture_callbacks.clear()
        logger.info("VisionOSBody shutdown")


"""
Mirror
h(x) >= 0. Always.

The body is the interface.
Pose reveals intent.
Movement is communication.
"""
