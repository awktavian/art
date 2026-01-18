"""Face Extraction Pipeline.

Extracts faces from video files with full source tracking.
Each extracted face includes video path, timestamp, and quality metrics.

Usage:
    extractor = FaceExtractor()
    faces = extractor.extract_from_video("/path/to/video.mp4")

    for face in faces:
        print(f"Face at {face.timestamp_formatted} - quality: {face.quality_score}")
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

# Try to import insightface, fall back to basic detection if not available
try:
    import insightface
    from insightface.app import FaceAnalysis

    INSIGHTFACE_AVAILABLE = True
except ImportError:
    INSIGHTFACE_AVAILABLE = False
    print("Warning: insightface not available, using basic face detection")


@dataclass
class ExtractedFace:
    """A face extracted from video with full provenance tracking."""

    # Source tracking
    source_video: str
    source_drive: str
    timestamp_seconds: float
    frame_number: int

    # Face data
    face_image: np.ndarray  # Cropped face image
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    embedding: np.ndarray | None = None  # 512-dim face embedding

    # Quality metrics
    confidence: float = 0.0
    sharpness: float = 0.0
    face_size: int = 0
    pose_score: float = 0.0  # How frontal the face is

    # Metadata
    extraction_date: str = field(default_factory=lambda: datetime.now().isoformat())
    face_id: str = ""

    @property
    def timestamp_formatted(self) -> str:
        """Format timestamp as MM:SS."""
        minutes = int(self.timestamp_seconds // 60)
        seconds = int(self.timestamp_seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def quality_score(self) -> str:
        """Overall quality assessment."""
        score = (
            self.confidence * 0.3
            + min(self.sharpness / 1000, 1.0) * 0.3
            + min(self.face_size / 10000, 1.0) * 0.2
            + self.pose_score * 0.2
        )
        if score > 0.7:
            return "excellent"
        elif score > 0.5:
            return "good"
        elif score > 0.3:
            return "fair"
        return "poor"

    def generate_id(self) -> str:
        """Generate unique ID based on source and location."""
        data = f"{self.source_video}_{self.timestamp_seconds}_{self.bbox}"
        return hashlib.md5(data.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_video": self.source_video,
            "source_drive": self.source_drive,
            "timestamp_seconds": self.timestamp_seconds,
            "timestamp_formatted": self.timestamp_formatted,
            "frame_number": self.frame_number,
            "bbox": list(self.bbox),
            "confidence": self.confidence,
            "sharpness": self.sharpness,
            "face_size": self.face_size,
            "pose_score": self.pose_score,
            "quality_score": self.quality_score,
            "extraction_date": self.extraction_date,
            "face_id": self.face_id or self.generate_id(),
        }


class FaceExtractor:
    """Extract faces from video files with InsightFace.

    Tracks source video, timestamps, and quality metrics for each face.
    """

    def __init__(
        self,
        sample_interval: float = 2.0,  # Extract every N seconds
        min_face_size: int = 64,
        min_confidence: float = 0.5,
        max_faces_per_frame: int = 10,
    ):
        """Initialize face extractor.

        Args:
            sample_interval: Seconds between frame samples
            min_face_size: Minimum face size in pixels
            min_confidence: Minimum detection confidence
            max_faces_per_frame: Max faces to extract per frame
        """
        self.sample_interval = sample_interval
        self.min_face_size = min_face_size
        self.min_confidence = min_confidence
        self.max_faces_per_frame = max_faces_per_frame

        # Initialize face detector
        self._detector = None
        self._init_detector()

    def _init_detector(self):
        """Initialize InsightFace detector."""
        if INSIGHTFACE_AVAILABLE:
            try:
                self._detector = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
                self._detector.prepare(ctx_id=-1, det_size=(640, 640))
            except Exception as e:
                print(f"Failed to init InsightFace: {e}")
                self._detector = None

        if self._detector is None:
            # Fall back to OpenCV Haar cascade
            self._haar_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )

    def extract_from_video(
        self,
        video_path: str,
        output_dir: str | None = None,
        progress_callback: callable | None = None,
    ) -> list[ExtractedFace]:
        """Extract all faces from a video file.

        Args:
            video_path: Path to video file
            output_dir: Optional directory to save face images
            progress_callback: Optional callback(current, total) for progress

        Returns:
            List of ExtractedFace objects with full tracking info
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        # Determine source drive
        source_drive = str(video_path.parent)
        if "/Volumes/" in source_drive:
            source_drive = "/Volumes/" + source_drive.split("/Volumes/")[1].split("/")[0]

        # Open video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        total_frames / fps if fps > 0 else 0

        # Calculate frame interval
        frame_interval = int(fps * self.sample_interval) if fps > 0 else 30

        faces: list[ExtractedFace] = []
        frame_number = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Sample at interval
            if frame_number % frame_interval == 0:
                timestamp = frame_number / fps if fps > 0 else frame_number

                # Detect faces in frame
                frame_faces = self._detect_faces_in_frame(
                    frame=frame,
                    source_video=video_path.name,
                    source_drive=source_drive,
                    timestamp_seconds=timestamp,
                    frame_number=frame_number,
                )

                faces.extend(frame_faces)

                # Progress callback
                if progress_callback:
                    progress_callback(frame_number, total_frames)

            frame_number += 1

        cap.release()

        # Save faces if output_dir specified
        if output_dir:
            self._save_faces(faces, output_dir)

        return faces

    def _detect_faces_in_frame(
        self,
        frame: np.ndarray,
        source_video: str,
        source_drive: str,
        timestamp_seconds: float,
        frame_number: int,
    ) -> list[ExtractedFace]:
        """Detect faces in a single frame."""
        faces = []

        if self._detector is not None:
            # Use InsightFace
            try:
                results = self._detector.get(frame)
                for face in results[: self.max_faces_per_frame]:
                    bbox = face.bbox.astype(int)
                    x1, y1, x2, y2 = bbox

                    # Filter by size
                    face_width = x2 - x1
                    face_height = y2 - y1
                    if face_width < self.min_face_size or face_height < self.min_face_size:
                        continue

                    # Filter by confidence
                    if face.det_score < self.min_confidence:
                        continue

                    # Crop face with margin
                    margin = int(min(face_width, face_height) * 0.2)
                    y1_m = max(0, y1 - margin)
                    y2_m = min(frame.shape[0], y2 + margin)
                    x1_m = max(0, x1 - margin)
                    x2_m = min(frame.shape[1], x2 + margin)
                    face_img = frame[y1_m:y2_m, x1_m:x2_m].copy()

                    # Calculate quality metrics
                    sharpness = self._calculate_sharpness(face_img)
                    pose_score = self._calculate_pose_score(face)

                    extracted = ExtractedFace(
                        source_video=source_video,
                        source_drive=source_drive,
                        timestamp_seconds=timestamp_seconds,
                        frame_number=frame_number,
                        face_image=face_img,
                        bbox=(x1, y1, x2, y2),
                        embedding=face.embedding if hasattr(face, "embedding") else None,
                        confidence=float(face.det_score),
                        sharpness=sharpness,
                        face_size=face_width * face_height,
                        pose_score=pose_score,
                    )
                    extracted.face_id = extracted.generate_id()
                    faces.append(extracted)

            except Exception as e:
                print(f"InsightFace error at {timestamp_seconds}s: {e}")

        else:
            # Fall back to Haar cascade
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detections = self._haar_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(self.min_face_size, self.min_face_size),
            )

            for x, y, w, h in detections[: self.max_faces_per_frame]:
                face_img = frame[y : y + h, x : x + w].copy()
                sharpness = self._calculate_sharpness(face_img)

                extracted = ExtractedFace(
                    source_video=source_video,
                    source_drive=source_drive,
                    timestamp_seconds=timestamp_seconds,
                    frame_number=frame_number,
                    face_image=face_img,
                    bbox=(x, y, x + w, y + h),
                    confidence=0.7,  # Haar doesn't give confidence
                    sharpness=sharpness,
                    face_size=w * h,
                    pose_score=0.5,  # Unknown pose
                )
                extracted.face_id = extracted.generate_id()
                faces.append(extracted)

        return faces

    def _calculate_sharpness(self, image: np.ndarray) -> float:
        """Calculate image sharpness using Laplacian variance."""
        if image.size == 0:
            return 0.0
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    def _calculate_pose_score(self, face) -> float:
        """Calculate how frontal the face is (1.0 = perfectly frontal)."""
        if not hasattr(face, "pose"):
            return 0.5

        # pose is [yaw, pitch, roll] in degrees
        yaw, pitch, roll = face.pose

        # Score based on deviation from frontal
        yaw_score = 1.0 - min(abs(yaw) / 45.0, 1.0)
        pitch_score = 1.0 - min(abs(pitch) / 30.0, 1.0)
        roll_score = 1.0 - min(abs(roll) / 30.0, 1.0)

        return (yaw_score + pitch_score + roll_score) / 3.0

    def _save_faces(self, faces: list[ExtractedFace], output_dir: str):
        """Save extracted faces to directory with metadata."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        metadata = []

        for _i, face in enumerate(faces):
            # Save face image
            filename = f"face_{face.face_id}.jpg"
            filepath = output_path / filename
            cv2.imwrite(str(filepath), face.face_image)

            # Add to metadata
            face_meta = face.to_dict()
            face_meta["saved_file"] = filename
            metadata.append(face_meta)

        # Save metadata JSON
        meta_path = output_path / "extraction_metadata.json"
        with open(meta_path, "w") as f:
            json.dump(
                {
                    "extraction_date": datetime.now().isoformat(),
                    "total_faces": len(faces),
                    "faces": metadata,
                },
                f,
                indent=2,
            )


def extract_faces_from_video(
    video_path: str,
    output_dir: str | None = None,
    sample_interval: float = 2.0,
) -> list[ExtractedFace]:
    """Convenience function to extract faces from a video.

    Args:
        video_path: Path to video file
        output_dir: Optional directory to save faces
        sample_interval: Seconds between samples

    Returns:
        List of ExtractedFace objects
    """
    extractor = FaceExtractor(sample_interval=sample_interval)
    return extractor.extract_from_video(video_path, output_dir)
