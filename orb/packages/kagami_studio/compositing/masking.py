"""Adaptive Masking — Subject extraction and segmentation.

Provides intelligent masking for compositing:
- SAM2-based video segmentation
- Face detection with depth estimation
- Subject extraction for overlays

This module handles the "extraction" part of compositing,
separating subjects from backgrounds for clean overlays.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FaceRegion:
    """Detected face region with metadata."""

    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    center: tuple[int, int]
    area: int
    confidence: float
    depth_estimate: float = 0.5  # 0=far, 1=close
    mask: np.ndarray | None = None


@dataclass
class SegmentResult:
    """Result from video segmentation."""

    frame_idx: int
    mask: np.ndarray
    bbox: tuple[int, int, int, int] | None = None
    confidence: float = 1.0
    object_id: int = 0


class AdaptiveMasker:
    """Intelligent masking system with SAM2 integration.

    Provides depth-aware subject extraction for compositing.
    Falls back to traditional methods when SAM2 unavailable.
    """

    def __init__(
        self,
        use_sam2: bool = True,
        face_detector: str = "mediapipe",  # mediapipe, opencv
    ):
        """Initialize masker.

        Args:
            use_sam2: Use SAM2 for segmentation (requires kagami_media)
            face_detector: Face detection backend
        """
        self.use_sam2 = use_sam2
        self.face_detector = face_detector

        self._face_cascade = None
        self._mp_face = None
        self._segmenter = None
        self._initialized = False

    def _init_detectors(self) -> None:
        """Initialize detection backends."""
        if self._initialized:
            return

        # Face detection
        if self.face_detector == "mediapipe":
            try:
                import mediapipe as mp

                self._mp_face = mp.solutions.face_detection.FaceDetection(
                    model_selection=1, min_detection_confidence=0.5
                )
            except ImportError:
                logger.warning("MediaPipe not available, using OpenCV")
                self.face_detector = "opencv"

        if self.face_detector == "opencv" and self._face_cascade is None:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._face_cascade = cv2.CascadeClassifier(cascade_path)

        # SAM2 segmentation
        if self.use_sam2:
            try:
                from kagami_media.segmentation import VideoSegmenter

                self._segmenter = VideoSegmenter(sample_interval=0.1)
            except ImportError:
                logger.warning("SAM2 not available, using fallback masking")
                self.use_sam2 = False

        self._initialized = True

    def detect_faces(self, frame: np.ndarray) -> list[FaceRegion]:
        """Detect faces in frame with depth estimation.

        Args:
            frame: BGR image

        Returns:
            List of FaceRegion objects sorted by area (largest first)
        """
        self._init_detectors()

        h, w = frame.shape[:2]
        faces = []

        if self._mp_face is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._mp_face.process(rgb)

            if results.detections:
                for detection in results.detections:
                    bbox = detection.location_data.relative_bounding_box
                    x1 = int(bbox.xmin * w)
                    y1 = int(bbox.ymin * h)
                    x2 = x1 + int(bbox.width * w)
                    y2 = y1 + int(bbox.height * h)

                    # Clamp to frame
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)

                    area = (x2 - x1) * (y2 - y1)
                    center = ((x1 + x2) // 2, (y1 + y2) // 2)

                    # Depth from face size (larger = closer)
                    depth = min(1.0, area / (w * h * 0.2))

                    faces.append(
                        FaceRegion(
                            bbox=(x1, y1, x2, y2),
                            center=center,
                            area=area,
                            confidence=detection.score[0],
                            depth_estimate=depth,
                        )
                    )

        elif self._face_cascade is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detected = self._face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )

            for x, y, bw, bh in detected:
                area = bw * bh
                center = (x + bw // 2, y + bh // 2)
                depth = min(1.0, area / (w * h * 0.2))

                faces.append(
                    FaceRegion(
                        bbox=(x, y, x + bw, y + bh),
                        center=center,
                        area=area,
                        confidence=0.7,
                        depth_estimate=depth,
                    )
                )

        # Sort by area (largest first)
        faces.sort(key=lambda f: f.area, reverse=True)
        return faces

    def extract_subject_mask(
        self,
        video_path: Path | str,
        frame_idx: int = 0,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Extract subject mask from video frame.

        Uses SAM2 if available, otherwise falls back to
        face-based rough masking.

        Args:
            video_path: Path to video
            frame_idx: Frame to extract from

        Returns:
            (frame, mask) - Original frame and binary mask
        """
        self._init_detectors()

        video_path = Path(video_path)

        # Read frame
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise RuntimeError(f"Cannot read frame {frame_idx} from {video_path}")

        h, w = frame.shape[:2]

        # Try SAM2 first
        if self._segmenter is not None:
            try:
                segments = list(self._segmenter.segment_video(str(video_path), sample_interval=10))
                if segments and segments[0].segments:
                    return frame, segments[0].segments[0].mask
            except Exception as e:
                logger.warning(f"SAM2 segmentation failed: {e}")

        # Fallback: face-based mask
        faces = self.detect_faces(frame)
        if faces:
            mask = create_mask_from_face(frame, faces[0])
            return frame, mask

        # No face: return empty mask
        return frame, np.zeros((h, w), dtype=np.uint8)

    async def segment_video(
        self,
        video_path: Path | str,
        sample_interval: float = 0.5,
    ) -> list[SegmentResult]:
        """Segment entire video using SAM2.

        Args:
            video_path: Path to video
            sample_interval: Seconds between samples

        Returns:
            List of SegmentResult for each sampled frame
        """
        self._init_detectors()

        if self._segmenter is None:
            logger.warning("SAM2 not available, returning empty segments")
            return []

        results = []
        for segment in self._segmenter.segment_video(
            str(video_path), sample_interval=sample_interval
        ):
            for obj in segment.segments:
                results.append(
                    SegmentResult(
                        frame_idx=segment.frame_idx,
                        mask=obj.mask,
                        bbox=obj.bbox if hasattr(obj, "bbox") else None,
                        confidence=obj.confidence if hasattr(obj, "confidence") else 1.0,
                        object_id=obj.object_id if hasattr(obj, "object_id") else 0,
                    )
                )

        return results


def extract_subject(
    video_path: Path | str,
    frame_idx: int = 0,
    use_sam2: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Quick function to extract subject from video.

    Args:
        video_path: Path to video
        frame_idx: Frame index
        use_sam2: Use SAM2 segmentation

    Returns:
        (frame, mask)
    """
    masker = AdaptiveMasker(use_sam2=use_sam2)
    return masker.extract_subject_mask(video_path, frame_idx)


def create_mask_from_face(
    frame: np.ndarray,
    face: FaceRegion,
    expand_ratio: float = 2.5,
    feather: int = 21,
) -> np.ndarray:
    """Create rough body mask from face detection.

    Expands face region to approximate body bounds.

    Args:
        frame: Original frame
        face: Detected face region
        expand_ratio: How much to expand face bbox for body
        feather: Feathering amount for soft edges

    Returns:
        Binary mask (uint8, 0 or 255)
    """
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = face.bbox

    face_h = y2 - y1
    face_w = x2 - x1

    # Expand to include body (face to body ratio ~ 1:3.5)
    body_bottom = min(h, y2 + int(face_h * expand_ratio))
    body_left = max(0, x1 - int(face_w * 0.5))
    body_right = min(w, x2 + int(face_w * 0.5))

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(mask, (body_left, y1), (body_right, body_bottom), 255, -1)

    # Feather edges
    if feather > 0:
        mask = cv2.GaussianBlur(mask, (feather, feather), 0)
        mask = (mask > 128).astype(np.uint8) * 255

    return mask
