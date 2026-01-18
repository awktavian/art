"""Pose Estimation using MediaPipe.

Extracts body pose data from video for motion capture and animation.
MediaPipe provides 33 body landmarks with 3D coordinates.

Landmarks include:
- Face (nose, eyes, ears, mouth)
- Torso (shoulders, hips)
- Arms (elbows, wrists, hands)
- Legs (knees, ankles, feet)

Usage:
    estimator = PoseEstimator()
    tracks = estimator.estimate_poses("video.mp4")

    for track in tracks:
        print(f"Track {track.track_id}: {track.frame_count} frames")
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

try:
    import mediapipe as mp

    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False


# MediaPipe Pose landmark names
LANDMARK_NAMES = [
    "nose",
    "left_eye_inner",
    "left_eye",
    "left_eye_outer",
    "right_eye_inner",
    "right_eye",
    "right_eye_outer",
    "left_ear",
    "right_ear",
    "mouth_left",
    "mouth_right",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_pinky",
    "right_pinky",
    "left_index",
    "right_index",
    "left_thumb",
    "right_thumb",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
]


@dataclass
class PoseFrame:
    """Pose data for a single frame."""

    frame_number: int
    timestamp_seconds: float

    # 33 landmarks, each with (x, y, z, visibility)
    landmarks: np.ndarray  # Shape: (33, 4)

    # World coordinates (3D)
    world_landmarks: np.ndarray | None = None  # Shape: (33, 4)

    # Detection confidence
    confidence: float = 0.0

    # Bounding box of detected person
    bbox: tuple[int, int, int, int] | None = None

    @property
    def is_valid(self) -> bool:
        return self.landmarks is not None and len(self.landmarks) == 33

    def get_landmark(self, name: str) -> tuple[float, float, float, float] | None:
        """Get landmark by name."""
        if name in LANDMARK_NAMES:
            idx = LANDMARK_NAMES.index(name)
            return tuple(self.landmarks[idx])
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        landmarks_dict = {}
        for i, name in enumerate(LANDMARK_NAMES):
            x, y, z, v = self.landmarks[i]
            landmarks_dict[name] = {
                "x": float(x),
                "y": float(y),
                "z": float(z),
                "visibility": float(v),
            }

        return {
            "frame_number": self.frame_number,
            "timestamp_seconds": self.timestamp_seconds,
            "confidence": self.confidence,
            "bbox": list(self.bbox) if self.bbox else None,
            "landmarks": landmarks_dict,
        }


@dataclass
class MotionTrack:
    """Motion data for a tracked person across frames."""

    track_id: int
    source_video: str

    # Pose frames
    frames: list[PoseFrame] = field(default_factory=list)

    # Statistics
    activity_level: str = "unknown"  # low, medium, high
    dominant_pose: str = "unknown"  # standing, sitting, walking, etc.

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    @property
    def duration_seconds(self) -> float:
        if len(self.frames) < 2:
            return 0.0
        return self.frames[-1].timestamp_seconds - self.frames[0].timestamp_seconds

    @property
    def average_confidence(self) -> float:
        if not self.frames:
            return 0.0
        return np.mean([f.confidence for f in self.frames])

    def add_frame(self, pose_frame: PoseFrame):
        """Add a pose frame to the track."""
        self.frames.append(pose_frame)

    def calculate_activity_level(self) -> str:
        """Calculate activity level based on motion."""
        if len(self.frames) < 2:
            return "unknown"

        # Calculate average movement between frames
        total_movement = 0.0

        for i in range(1, len(self.frames)):
            prev_frame = self.frames[i - 1]
            curr_frame = self.frames[i]

            # Sum of landmark position changes
            movement = np.sum(np.abs(curr_frame.landmarks[:, :2] - prev_frame.landmarks[:, :2]))
            total_movement += movement

        avg_movement = total_movement / (len(self.frames) - 1)

        if avg_movement < 0.01:
            self.activity_level = "low"
        elif avg_movement < 0.05:
            self.activity_level = "medium"
        else:
            self.activity_level = "high"

        return self.activity_level

    def detect_dominant_pose(self) -> str:
        """Detect the dominant pose type."""
        if not self.frames:
            return "unknown"

        # Analyze hip and shoulder positions
        poses = []

        for frame in self.frames:
            left_hip = frame.get_landmark("left_hip")
            right_hip = frame.get_landmark("right_hip")
            left_shoulder = frame.get_landmark("left_shoulder")
            right_shoulder = frame.get_landmark("right_shoulder")

            if all([left_hip, right_hip, left_shoulder, right_shoulder]):
                hip_y = (left_hip[1] + right_hip[1]) / 2
                shoulder_y = (left_shoulder[1] + right_shoulder[1]) / 2

                # Standing vs sitting based on relative positions
                torso_height = abs(hip_y - shoulder_y)

                if torso_height > 0.3:
                    poses.append("standing")
                else:
                    poses.append("sitting")

        if poses:
            # Most common pose
            from collections import Counter

            self.dominant_pose = Counter(poses).most_common(1)[0][0]

        return self.dominant_pose

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "track_id": self.track_id,
            "source_video": self.source_video,
            "frame_count": self.frame_count,
            "duration_seconds": self.duration_seconds,
            "average_confidence": self.average_confidence,
            "activity_level": self.activity_level,
            "dominant_pose": self.dominant_pose,
            "frames": [f.to_dict() for f in self.frames],
        }

    def export_for_animation(self, output_path: str):
        """Export motion data for animation software."""
        data = {
            "format": "kagami_motion_v1",
            "fps": 30.0,  # Assumed
            "landmark_names": LANDMARK_NAMES,
            "frames": [],
        }

        for frame in self.frames:
            frame_data = {
                "time": frame.timestamp_seconds,
                "landmarks": frame.landmarks.tolist(),
            }
            if frame.world_landmarks is not None:
                frame_data["world_landmarks"] = frame.world_landmarks.tolist()
            data["frames"].append(frame_data)

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)


class PoseEstimator:
    """Estimate body poses from video using MediaPipe.

    Extracts 33-point body landmarks for each detected person.
    """

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_complexity: int = 1,
        sample_interval: float = 0.1,
    ):
        """Initialize pose estimator.

        Args:
            min_detection_confidence: Minimum detection confidence
            min_tracking_confidence: Minimum tracking confidence
            model_complexity: 0=lite, 1=full, 2=heavy
            sample_interval: Seconds between processed frames
        """
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.model_complexity = model_complexity
        self.sample_interval = sample_interval

        self._pose = None
        self._init_model()

    def _init_model(self):
        """Initialize MediaPipe Pose model."""
        if MEDIAPIPE_AVAILABLE:
            self._mp_pose = mp.solutions.pose
            self._pose = self._mp_pose.Pose(
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                model_complexity=self.model_complexity,
            )

    def estimate_poses(
        self,
        video_path: str,
        output_dir: str | None = None,
        progress_callback: callable | None = None,
    ) -> list[MotionTrack]:
        """Estimate poses for all people in video.

        Args:
            video_path: Path to video file
            output_dir: Directory to save motion data
            progress_callback: Callback(current_frame, total_frames)

        Returns:
            List of MotionTrack objects
        """
        video_path = Path(video_path)
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = max(1, int(fps * self.sample_interval))

        # Single track for now (MediaPipe detects one person)
        # Multi-person would require running detector first
        track = MotionTrack(
            track_id=0,
            source_video=video_path.name,
        )

        frame_number = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_number % frame_interval == 0:
                timestamp = frame_number / fps

                pose_frame = self._process_frame(frame, frame_number, timestamp)

                if pose_frame is not None:
                    track.add_frame(pose_frame)

                if progress_callback:
                    progress_callback(frame_number, total_frames)

            frame_number += 1

        cap.release()

        # Calculate statistics
        if track.frame_count > 0:
            track.calculate_activity_level()
            track.detect_dominant_pose()

        tracks = [track] if track.frame_count > 0 else []

        # Save if output_dir specified
        if output_dir and tracks:
            self._save_motion_data(tracks, output_dir, video_path.name)

        return tracks

    def _process_frame(
        self,
        frame: np.ndarray,
        frame_number: int,
        timestamp: float,
    ) -> PoseFrame | None:
        """Process a single frame for pose estimation."""
        if self._pose is None:
            return None

        # Convert to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Process
        results = self._pose.process(rgb_frame)

        if results.pose_landmarks is None:
            return None

        # Extract landmarks
        h, w = frame.shape[:2]
        landmarks = np.zeros((33, 4))

        for i, landmark in enumerate(results.pose_landmarks.landmark):
            landmarks[i] = [
                landmark.x,
                landmark.y,
                landmark.z,
                landmark.visibility,
            ]

        # Extract world landmarks if available
        world_landmarks = None
        if results.pose_world_landmarks:
            world_landmarks = np.zeros((33, 4))
            for i, landmark in enumerate(results.pose_world_landmarks.landmark):
                world_landmarks[i] = [
                    landmark.x,
                    landmark.y,
                    landmark.z,
                    landmark.visibility,
                ]

        # Calculate bounding box from landmarks
        visible_landmarks = landmarks[landmarks[:, 3] > 0.5]
        if len(visible_landmarks) > 0:
            x_coords = visible_landmarks[:, 0] * w
            y_coords = visible_landmarks[:, 1] * h
            bbox = (
                int(np.min(x_coords)),
                int(np.min(y_coords)),
                int(np.max(x_coords)),
                int(np.max(y_coords)),
            )
        else:
            bbox = None

        # Calculate confidence as average visibility
        confidence = float(np.mean(landmarks[:, 3]))

        return PoseFrame(
            frame_number=frame_number,
            timestamp_seconds=timestamp,
            landmarks=landmarks,
            world_landmarks=world_landmarks,
            confidence=confidence,
            bbox=bbox,
        )

    def _save_motion_data(
        self,
        tracks: list[MotionTrack],
        output_dir: str,
        video_name: str,
    ):
        """Save motion data to files."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for track in tracks:
            # Save full motion data
            motion_path = output_path / f"motion_track_{track.track_id}.json"
            with open(motion_path, "w") as f:
                json.dump(track.to_dict(), f, indent=2)

            # Save animation-ready export
            anim_path = output_path / f"animation_track_{track.track_id}.json"
            track.export_for_animation(str(anim_path))

        # Save summary
        summary = {
            "source_video": video_name,
            "track_count": len(tracks),
            "tracks": [
                {
                    "track_id": t.track_id,
                    "frame_count": t.frame_count,
                    "duration": t.duration_seconds,
                    "activity": t.activity_level,
                    "pose": t.dominant_pose,
                }
                for t in tracks
            ],
        }

        summary_path = output_path / "motion_summary.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)


def estimate_poses(
    video_path: str,
    output_dir: str | None = None,
) -> list[MotionTrack]:
    """Convenience function to estimate poses from video.

    Args:
        video_path: Path to video file
        output_dir: Optional output directory

    Returns:
        List of MotionTrack objects
    """
    estimator = PoseEstimator()
    return estimator.estimate_poses(video_path, output_dir)
