"""Motion Capture and Pose Estimation Module.

Uses MediaPipe for body pose estimation and motion tracking.
Captures 33 body landmarks per frame for animation reproduction.

Key Features:
- Full body pose estimation (33 landmarks)
- Motion tracking across frames
- Activity level analysis
- Gesture pattern detection
- Export to animation-ready format

Usage:
    from kagami_media.motion import PoseEstimator

    estimator = PoseEstimator()
    poses = estimator.estimate_poses("video.mp4")
"""

from kagami_media.motion.pose_estimator import (
    MotionTrack,
    PoseEstimator,
    PoseFrame,
    estimate_poses,
)

__all__ = [
    "MotionTrack",
    "PoseEstimator",
    "PoseFrame",
    "estimate_poses",
]
