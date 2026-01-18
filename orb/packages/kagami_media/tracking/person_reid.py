"""Person Tracking and Re-Identification.

Tracks people across video frames and matches identities across videos.
Uses DeepSORT for tracking and TorchReID for re-identification embeddings.

Each tracked person includes:
- Unique track ID within video
- Bounding box trajectory
- ReID embedding (2048-dim)
- Appearance features

Usage:
    tracker = PersonTracker()
    tracks = tracker.track_video("video.mp4")

    reid = PersonReID()
    matches = reid.match_across_videos([tracks1, tracks2])
"""

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

# Try to import tracking libraries
try:
    from deep_sort_realtime.deepsort_tracker import DeepSort

    DEEPSORT_AVAILABLE = True
except ImportError:
    DEEPSORT_AVAILABLE = False

try:
    import torchreid

    TORCHREID_AVAILABLE = True
except ImportError:
    TORCHREID_AVAILABLE = False

try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


@dataclass
class TrackedPerson:
    """A person tracked across video frames."""

    track_id: int
    source_video: str

    # Trajectory
    bboxes: list[tuple[int, int, int, int]] = field(default_factory=list)
    timestamps: list[float] = field(default_factory=list)
    frame_numbers: list[int] = field(default_factory=list)

    # Embeddings
    reid_embedding: np.ndarray | None = None  # 2048-dim
    appearance_features: list[np.ndarray] = field(default_factory=list)

    # Best crop for identification
    best_crop: np.ndarray | None = None
    best_crop_score: float = 0.0

    @property
    def duration_seconds(self) -> float:
        if len(self.timestamps) < 2:
            return 0.0
        return self.timestamps[-1] - self.timestamps[0]

    @property
    def frame_count(self) -> int:
        return len(self.frame_numbers)

    @property
    def average_bbox_size(self) -> tuple[int, int]:
        if not self.bboxes:
            return (0, 0)
        widths = [b[2] - b[0] for b in self.bboxes]
        heights = [b[3] - b[1] for b in self.bboxes]
        return (int(np.mean(widths)), int(np.mean(heights)))

    def add_detection(
        self,
        bbox: tuple[int, int, int, int],
        timestamp: float,
        frame_number: int,
        crop: np.ndarray | None = None,
        crop_score: float = 0.0,
    ):
        """Add a detection to this track."""
        self.bboxes.append(bbox)
        self.timestamps.append(timestamp)
        self.frame_numbers.append(frame_number)

        # Update best crop if this one is better
        if crop is not None and crop_score > self.best_crop_score:
            self.best_crop = crop
            self.best_crop_score = crop_score

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "track_id": self.track_id,
            "source_video": self.source_video,
            "frame_count": self.frame_count,
            "duration_seconds": self.duration_seconds,
            "average_bbox_size": list(self.average_bbox_size),
            "first_frame": self.frame_numbers[0] if self.frame_numbers else None,
            "last_frame": self.frame_numbers[-1] if self.frame_numbers else None,
            "first_timestamp": self.timestamps[0] if self.timestamps else None,
            "last_timestamp": self.timestamps[-1] if self.timestamps else None,
            "has_reid_embedding": self.reid_embedding is not None,
            "best_crop_score": self.best_crop_score,
        }


class PersonTracker:
    """Track people across frames in a video.

    Uses DeepSORT for robust multi-object tracking.
    """

    def __init__(
        self,
        max_age: int = 30,
        n_init: int = 3,
        max_iou_distance: float = 0.7,
    ):
        """Initialize person tracker.

        Args:
            max_age: Max frames to keep track alive without detection
            n_init: Min detections to confirm track
            max_iou_distance: Max IOU distance for matching
        """
        self.max_age = max_age
        self.n_init = n_init
        self.max_iou_distance = max_iou_distance

        self._tracker = None
        self._detector = None
        self._init_tracker()

    def _init_tracker(self):
        """Initialize DeepSORT tracker."""
        if DEEPSORT_AVAILABLE:
            self._tracker = DeepSort(
                max_age=self.max_age,
                n_init=self.n_init,
                max_iou_distance=self.max_iou_distance,
            )

        # Initialize person detector (use Haar cascade as fallback)
        cascade_path = cv2.data.haarcascades + "haarcascade_fullbody.xml"
        self._detector = cv2.CascadeClassifier(cascade_path)

    def track_video(
        self,
        video_path: str,
        sample_interval: float = 0.1,
        progress_callback: callable | None = None,
    ) -> dict[int, TrackedPerson]:
        """Track all people in a video.

        Args:
            video_path: Path to video file
            sample_interval: Seconds between processed frames
            progress_callback: Callback(current_frame, total_frames)

        Returns:
            Dictionary mapping track_id to TrackedPerson
        """
        video_path = Path(video_path)
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = max(1, int(fps * sample_interval))

        tracks: dict[int, TrackedPerson] = {}
        frame_number = 0

        # Reset tracker for new video
        if DEEPSORT_AVAILABLE:
            self._tracker = DeepSort(
                max_age=self.max_age,
                n_init=self.n_init,
                max_iou_distance=self.max_iou_distance,
            )

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_number % frame_interval == 0:
                timestamp = frame_number / fps

                # Detect people
                detections = self._detect_people(frame)

                # Update tracker
                tracked = self._update_tracker(frame, detections)

                # Update track records
                for track_id, bbox in tracked:
                    if track_id not in tracks:
                        tracks[track_id] = TrackedPerson(
                            track_id=track_id,
                            source_video=video_path.name,
                        )

                    # Calculate crop quality score
                    x1, y1, x2, y2 = bbox
                    crop = frame[y1:y2, x1:x2].copy()
                    crop_score = self._calculate_crop_quality(crop)

                    tracks[track_id].add_detection(
                        bbox=bbox,
                        timestamp=timestamp,
                        frame_number=frame_number,
                        crop=crop,
                        crop_score=crop_score,
                    )

                if progress_callback:
                    progress_callback(frame_number, total_frames)

            frame_number += 1

        cap.release()
        return tracks

    def _detect_people(self, frame: np.ndarray) -> list[tuple]:
        """Detect people in frame.

        Returns list of (bbox, confidence, class) tuples.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Use Haar cascade for person detection
        bodies = self._detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=3,
            minSize=(50, 100),
        )

        detections = []
        for x, y, w, h in bodies:
            # Format: ([x1, y1, w, h], confidence, class)
            detections.append(([x, y, w, h], 0.8, "person"))

        return detections

    def _update_tracker(
        self,
        frame: np.ndarray,
        detections: list[tuple],
    ) -> list[tuple[int, tuple]]:
        """Update tracker with new detections.

        Returns list of (track_id, bbox) tuples.
        """
        if not detections:
            return []

        if DEEPSORT_AVAILABLE and self._tracker is not None:
            # Use DeepSORT
            tracks = self._tracker.update_tracks(detections, frame=frame)

            result = []
            for track in tracks:
                if not track.is_confirmed():
                    continue

                track_id = track.track_id
                ltrb = track.to_ltrb()  # [left, top, right, bottom]
                bbox = (int(ltrb[0]), int(ltrb[1]), int(ltrb[2]), int(ltrb[3]))
                result.append((track_id, bbox))

            return result

        else:
            # Simple fallback: assign sequential IDs
            result = []
            for i, (det, _conf, _cls) in enumerate(detections):
                x, y, w, h = det
                bbox = (x, y, x + w, y + h)
                result.append((i, bbox))
            return result

    def _calculate_crop_quality(self, crop: np.ndarray) -> float:
        """Calculate quality score for a person crop."""
        if crop.size == 0:
            return 0.0

        # Factors: size, sharpness, aspect ratio
        h, w = crop.shape[:2]

        # Size score (prefer larger crops)
        size_score = min(1.0, (w * h) / 50000)

        # Sharpness score
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness_score = min(1.0, laplacian_var / 500)

        # Aspect ratio score (prefer human-like ratios)
        aspect = h / w if w > 0 else 0
        aspect_score = 1.0 - abs(aspect - 2.0) / 2.0  # Ideal ~2:1
        aspect_score = max(0.0, min(1.0, aspect_score))

        return size_score * 0.4 + sharpness_score * 0.4 + aspect_score * 0.2


class PersonReID:
    """Person Re-Identification for cross-video identity matching.

    Generates 2048-dim embeddings for each tracked person and
    matches identities across different videos.
    """

    def __init__(
        self,
        model_name: str = "osnet_x1_0",
        device: str = "cpu",
    ):
        """Initialize ReID model.

        Args:
            model_name: TorchReID model name
            device: 'cpu' or 'cuda'
        """
        self.model_name = model_name
        self.device = device

        self._model = None
        self._init_model()

    def _init_model(self):
        """Initialize TorchReID model."""
        if TORCHREID_AVAILABLE and TORCH_AVAILABLE:
            try:
                self._model = torchreid.models.build_model(
                    name=self.model_name,
                    num_classes=1000,
                    pretrained=True,
                )
                self._model.eval()

                if self.device == "cuda" and torch.cuda.is_available():
                    self._model = self._model.cuda()
            except Exception as e:
                print(f"TorchReID model init failed: {e}")
                self._model = None

    def extract_embedding(self, crop: np.ndarray) -> np.ndarray | None:
        """Extract ReID embedding from person crop.

        Args:
            crop: Person image crop (BGR)

        Returns:
            2048-dim embedding or None if extraction fails
        """
        if self._model is None or crop.size == 0:
            return None

        try:
            # Preprocess
            img = cv2.resize(crop, (128, 256))  # Standard ReID size
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = img.astype(np.float32) / 255.0
            img = (img - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
            img = img.transpose(2, 0, 1)  # HWC -> CHW

            # Convert to tensor
            tensor = torch.from_numpy(img).unsqueeze(0).float()
            if self.device == "cuda" and torch.cuda.is_available():
                tensor = tensor.cuda()

            # Extract features
            with torch.no_grad():
                features = self._model(tensor)

            return features.cpu().numpy().flatten()

        except Exception as e:
            print(f"Embedding extraction failed: {e}")
            return None

    def extract_embeddings_for_tracks(
        self,
        tracks: dict[int, TrackedPerson],
    ) -> dict[int, TrackedPerson]:
        """Extract ReID embeddings for all tracked persons.

        Args:
            tracks: Dictionary of TrackedPerson objects

        Returns:
            Same dictionary with reid_embedding populated
        """
        for _track_id, person in tracks.items():
            if person.best_crop is not None:
                embedding = self.extract_embedding(person.best_crop)
                person.reid_embedding = embedding

        return tracks

    def match_across_videos(
        self,
        all_tracks: list[dict[int, TrackedPerson]],
        threshold: float = 0.7,
    ) -> list[list[tuple[int, int, int]]]:
        """Match identities across multiple videos.

        Args:
            all_tracks: List of track dictionaries from different videos
            threshold: Cosine similarity threshold for matching

        Returns:
            List of identity groups, each containing (video_idx, track_id) tuples
        """
        # Collect all embeddings
        all_embeddings = []
        embedding_to_track = []  # (video_idx, track_id)

        for video_idx, tracks in enumerate(all_tracks):
            for track_id, person in tracks.items():
                if person.reid_embedding is not None:
                    all_embeddings.append(person.reid_embedding)
                    embedding_to_track.append((video_idx, track_id))

        if len(all_embeddings) < 2:
            return [[et] for et in embedding_to_track]

        # Compute pairwise cosine similarities
        embeddings = np.array(all_embeddings)

        # Normalize embeddings
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings_normalized = embeddings / (norms + 1e-8)

        # Compute similarity matrix
        similarity = embeddings_normalized @ embeddings_normalized.T

        # Cluster using simple greedy matching
        n = len(embeddings)
        used = [False] * n
        identity_groups = []

        for i in range(n):
            if used[i]:
                continue

            group = [embedding_to_track[i]]
            used[i] = True

            for j in range(i + 1, n):
                if not used[j] and similarity[i, j] > threshold:
                    group.append(embedding_to_track[j])
                    used[j] = True

            identity_groups.append(group)

        return identity_groups

    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
    ) -> float:
        """Compute cosine similarity between two embeddings."""
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(embedding1, embedding2) / (norm1 * norm2))


def track_persons_in_video(
    video_path: str,
    sample_interval: float = 0.1,
    extract_embeddings: bool = True,
) -> dict[int, TrackedPerson]:
    """Convenience function to track persons in a video.

    Args:
        video_path: Path to video file
        sample_interval: Seconds between processed frames
        extract_embeddings: Whether to extract ReID embeddings

    Returns:
        Dictionary mapping track_id to TrackedPerson
    """
    tracker = PersonTracker()
    tracks = tracker.track_video(video_path, sample_interval)

    if extract_embeddings:
        reid = PersonReID()
        tracks = reid.extract_embeddings_for_tracks(tracks)

    return tracks
