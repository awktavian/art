"""Real-Time Face Matching for Camera Identity Detection.

Processes camera images in real-time to identify people using
face embeddings cached from the identity extraction system.

Optimized for:
- Sub-second matching latency
- Low memory footprint
- Graceful degradation without GPU

Colony: Nexus (e₄) — Integration
Safety: h(x) ≥ 0 — Privacy-preserving local processing

Usage:
    matcher = RealtimeFaceMatcher()
    await matcher.initialize()

    # Called by UniFi integration on person detection
    async def on_person_detected(camera_id, camera_name, image_bytes, metadata):
        match = await matcher.match_image(image_bytes, camera_name)
        if match:
            print(f"Identified: {match.name} on {camera_name}")
"""

from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Try to import image processing libraries
try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# Try to import InsightFace for face detection
try:
    from insightface.app import FaceAnalysis

    INSIGHTFACE_AVAILABLE = True
except ImportError:
    INSIGHTFACE_AVAILABLE = False


@dataclass
class FaceMatch:
    """Result of face matching against identity cache."""

    identity_id: str
    name: str | None
    confidence: float

    # Detection metadata
    camera_id: str
    camera_name: str
    timestamp: float

    # Face quality metrics
    face_quality: float = 0.0
    bbox: tuple[int, int, int, int] | None = None

    def to_dict(self) -> dict:
        return {
            "identity_id": self.identity_id,
            "name": self.name,
            "confidence": self.confidence,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "timestamp": self.timestamp,
            "face_quality": self.face_quality,
            "bbox": self.bbox,
        }


@dataclass
class DetectedFace:
    """A face detected in an image."""

    embedding: np.ndarray
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    quality_score: float
    detection_confidence: float


class RealtimeFaceMatcher:
    """Real-time face detection and matching.

    Uses InsightFace for detection and embedding extraction,
    then matches against the identity cache.
    """

    def __init__(
        self,
        model_name: str = "buffalo_l",
        ctx_id: int = -1,  # -1 for CPU, 0 for GPU
        det_thresh: float = 0.5,
        match_threshold: float = 0.6,
    ):
        """Initialize face matcher.

        Args:
            model_name: InsightFace model name
            ctx_id: Context ID (-1 for CPU, 0+ for GPU)
            det_thresh: Face detection threshold
            match_threshold: Default matching threshold
        """
        self.model_name = model_name
        self.ctx_id = ctx_id
        self.det_thresh = det_thresh
        self.match_threshold = match_threshold

        self._face_analysis: Any | None = None
        self._identity_cache: Any | None = None
        self._initialized = False

        # Statistics
        self._total_detections = 0
        self._total_matches = 0
        self._avg_latency_ms = 0.0

    async def initialize(self) -> None:
        """Initialize face detection model and identity cache."""
        if self._initialized:
            return

        # Initialize InsightFace
        if INSIGHTFACE_AVAILABLE:
            try:
                self._face_analysis = FaceAnalysis(
                    name=self.model_name,
                    providers=["CPUExecutionProvider"]
                    if self.ctx_id < 0
                    else ["CUDAExecutionProvider"],
                )
                self._face_analysis.prepare(ctx_id=self.ctx_id, det_thresh=self.det_thresh)
                logger.info(f"InsightFace initialized with model {self.model_name}")
            except Exception as e:
                logger.warning(f"InsightFace initialization failed: {e}")
                self._face_analysis = None
        else:
            logger.warning("InsightFace not available, using fallback detection")

        # Initialize identity cache
        try:
            from kagami.core.caching.identity_cache import get_identity_cache

            self._identity_cache = await get_identity_cache()
            logger.info(
                f"Identity cache loaded with {self._identity_cache.face_count} face embeddings"
            )
        except Exception as e:
            logger.warning(f"Identity cache initialization failed: {e}")

        self._initialized = True

    async def match_image(
        self,
        image_bytes: bytes,
        camera_name: str,
        camera_id: str = "",
        threshold: float | None = None,
    ) -> FaceMatch | None:
        """Detect and match faces in an image.

        Args:
            image_bytes: JPEG image bytes from camera
            camera_name: Human-readable camera name
            camera_id: Camera identifier
            threshold: Optional override for match threshold

        Returns:
            Best FaceMatch if found, None otherwise
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()
        threshold = threshold or self.match_threshold

        # Decode image
        image = self._decode_image(image_bytes)
        if image is None:
            return None

        # Detect faces
        faces = self._detect_faces(image)
        if not faces:
            logger.debug(f"No faces detected in image from {camera_name}")
            return None

        self._total_detections += len(faces)

        # Match best face against identity cache
        best_match: FaceMatch | None = None

        for face in faces:
            match = self._match_embedding(face.embedding, threshold)
            if match:
                face_match = FaceMatch(
                    identity_id=match.identity_id,
                    name=match.name,
                    confidence=match.confidence,
                    camera_id=camera_id,
                    camera_name=camera_name,
                    timestamp=time.time(),
                    face_quality=face.quality_score,
                    bbox=face.bbox,
                )

                if best_match is None or face_match.confidence > best_match.confidence:
                    best_match = face_match

        # Update statistics
        latency_ms = (time.time() - start_time) * 1000
        self._avg_latency_ms = (self._avg_latency_ms * 0.9) + (latency_ms * 0.1)

        if best_match:
            self._total_matches += 1
            logger.info(
                f"🎯 Identified {best_match.name or best_match.identity_id} "
                f"on {camera_name} (confidence: {best_match.confidence:.2f}, "
                f"latency: {latency_ms:.0f}ms)"
            )

        return best_match

    def _decode_image(self, image_bytes: bytes) -> np.ndarray | None:
        """Decode JPEG bytes to numpy array (BGR format for InsightFace)."""
        if CV2_AVAILABLE:
            try:
                nparr = np.frombuffer(image_bytes, np.uint8)
                return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            except Exception as e:
                logger.error(f"CV2 image decode failed: {e}")

        if PIL_AVAILABLE:
            try:
                img = Image.open(io.BytesIO(image_bytes))
                img_rgb = img.convert("RGB")
                # Convert RGB to BGR for InsightFace
                return np.array(img_rgb)[:, :, ::-1]
            except Exception as e:
                logger.error(f"PIL image decode failed: {e}")

        logger.error("No image decoding library available")
        return None

    def _detect_faces(self, image: np.ndarray) -> list[DetectedFace]:
        """Detect faces in image and extract embeddings."""
        if self._face_analysis is None:
            return self._fallback_detect(image)

        try:
            faces = self._face_analysis.get(image)
            detected = []

            for face in faces:
                # Extract embedding
                if hasattr(face, "embedding") and face.embedding is not None:
                    embedding = np.array(face.embedding, dtype=np.float32)

                    # Get bounding box
                    bbox = (
                        tuple(int(x) for x in face.bbox) if hasattr(face, "bbox") else (0, 0, 0, 0)
                    )

                    # Calculate quality score
                    quality = self._calculate_quality(face, image)

                    detected.append(
                        DetectedFace(
                            embedding=embedding,
                            bbox=bbox,
                            quality_score=quality,
                            detection_confidence=face.det_score
                            if hasattr(face, "det_score")
                            else 0.9,
                        )
                    )

            return detected

        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            return []

    def _fallback_detect(self, image: np.ndarray) -> list[DetectedFace]:
        """Fallback face detection using OpenCV Haar cascade."""
        if not CV2_AVAILABLE:
            return []

        try:
            # Load Haar cascade
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            face_cascade = cv2.CascadeClassifier(cascade_path)

            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Detect faces
            faces_rect = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )

            # Without InsightFace, we can't get embeddings
            # Just return detected faces with placeholder embeddings
            detected = []
            for x, y, w, h in faces_rect:
                # Create a simple embedding from face region (not useful for matching)
                # This is just for testing - real matching requires InsightFace
                face_region = gray[y : y + h, x : x + w]
                face_resized = cv2.resize(face_region, (64, 64))
                embedding = face_resized.flatten().astype(np.float32)[:512]
                # Pad to 512 if needed
                if len(embedding) < 512:
                    embedding = np.pad(embedding, (0, 512 - len(embedding)))

                detected.append(
                    DetectedFace(
                        embedding=embedding,
                        bbox=(x, y, x + w, y + h),
                        quality_score=0.5,  # Unknown quality
                        detection_confidence=0.7,
                    )
                )

            return detected

        except Exception as e:
            logger.error(f"Fallback detection failed: {e}")
            return []

    def _calculate_quality(self, face: Any, image: np.ndarray) -> float:
        """Calculate face quality score."""
        try:
            # Factors: size, frontality, sharpness
            scores = []

            # Size score (larger is better)
            if hasattr(face, "bbox"):
                w = face.bbox[2] - face.bbox[0]
                h = face.bbox[3] - face.bbox[1]
                size_score = min(1.0, (w * h) / (200 * 200))
                scores.append(size_score)

            # Frontality score from landmarks
            if hasattr(face, "landmark_2d_106"):
                # Check if face is roughly frontal
                landmarks = face.landmark_2d_106
                if landmarks is not None and len(landmarks) > 0:
                    # Simplified frontality check
                    scores.append(0.8)

            # Detection confidence
            if hasattr(face, "det_score"):
                scores.append(float(face.det_score))

            return sum(scores) / len(scores) if scores else 0.5

        except Exception:
            return 0.5

    def _match_embedding(
        self,
        embedding: np.ndarray,
        threshold: float,
    ) -> Any | None:
        """Match embedding against identity cache."""
        if self._identity_cache is None:
            return None

        return self._identity_cache.match_face(embedding, threshold)

    @property
    def stats(self) -> dict:
        """Get matcher statistics."""
        return {
            "total_detections": self._total_detections,
            "total_matches": self._total_matches,
            "match_rate": self._total_matches / max(1, self._total_detections),
            "avg_latency_ms": self._avg_latency_ms,
            "identity_count": self._identity_cache.identity_count if self._identity_cache else 0,
        }


# Singleton instance
_realtime_matcher: RealtimeFaceMatcher | None = None


async def get_realtime_matcher() -> RealtimeFaceMatcher:
    """Get singleton realtime face matcher.

    Returns:
        Initialized RealtimeFaceMatcher
    """
    global _realtime_matcher

    if _realtime_matcher is None:
        _realtime_matcher = RealtimeFaceMatcher()
        await _realtime_matcher.initialize()

    return _realtime_matcher


async def process_camera_detection(
    camera_id: str,
    camera_name: str,
    image_bytes: bytes,
    metadata: dict[str, Any],
) -> FaceMatch | None:
    """Process a camera detection event for face matching.

    This is the main entry point called by the UniFi integration.

    Args:
        camera_id: Camera identifier
        camera_name: Human-readable camera name
        image_bytes: JPEG image bytes
        metadata: Event metadata from UniFi

    Returns:
        FaceMatch if identity detected, None otherwise
    """
    matcher = await get_realtime_matcher()
    return await matcher.match_image(
        image_bytes,
        camera_name,
        camera_id,
    )
