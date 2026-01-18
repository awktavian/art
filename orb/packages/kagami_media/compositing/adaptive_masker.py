"""Adaptive Masking System with SAM2 Integration.

Depth-aware segmentation and placement for compositing.
Supports DCC-style templates: giant face, split panel, full frame.

Architecture:
    Video Input → SAM2 Segmentation → Depth Analysis → Template Placement → Output
                                                      ↓
                                             Web Artifact Generation

Integrates with core compositor for:
- Chromakey (green screen removal)
- Spatial audio mixing
- Layer-based compositing

Usage:
    from kagami_media.compositing import AdaptiveMasker, CompositeTemplate

    masker = AdaptiveMasker()

    # Basic composite
    result = masker.create_composite(
        background_video=Path("bella.mov"),
        overlay_video=Path("bellatrix.mp4"),
        template=CompositeTemplate.GIANT_FACE_CORNER,
    )

    # With chromakey (green screen overlay)
    result = masker.create_chromakey_composite(
        background_video=Path("bella.mov"),
        greenscreen_video=Path("bellatrix_greenscreen.mp4"),
        output_path=Path("output.mp4"),
    )

    # With spatial audio mixing
    result = masker.create_composite_with_spatial_audio(
        background_video=Path("bella.mov"),
        overlay_video=Path("bellatrix.mp4"),
        output_path=Path("output.mp4"),
        background_audio_volume=0.7,
        overlay_audio_pan=0.5,  # Pan overlay to right
    )
"""

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

import cv2
import numpy as np


class CompositeTemplate(Enum):
    """Predefined composition templates inspired by DCC documentary."""

    # Giant face in corner - dominant overlay
    GIANT_FACE_CORNER = auto()
    GIANT_FACE_LEFT = auto()
    GIANT_FACE_RIGHT = auto()

    # Split panel layouts
    SPLIT_VERTICAL = auto()  # Side by side
    SPLIT_HORIZONTAL = auto()  # Top/bottom
    SPLIT_DIAGONAL = auto()  # Diagonal cut

    # Full frame with overlay
    FULL_FRAME_PIP = auto()  # Small PiP overlay
    FULL_FRAME_FLOAT = auto()  # Floating glassmorphism panel

    # DCC-style word sync
    DCC_WORD_SYNC = auto()  # Word-by-word overlay

    # Depth-aware
    DEPTH_COMPOSITE = auto()  # Layer by depth


class DepthLayer(Enum):
    """Depth layers for compositing."""

    BACKGROUND = 0
    MID_GROUND = 1
    FOREGROUND = 2
    OVERLAY = 3


@dataclass
class CompositeResult:
    """Result of compositing operation."""

    success: bool
    output_path: Path | None = None
    web_artifact_path: Path | None = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class FaceRegion:
    """Detected face region with depth info."""

    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    center: tuple[int, int]
    area: int
    confidence: float
    depth_layer: DepthLayer = DepthLayer.FOREGROUND
    mask: np.ndarray | None = None


class AdaptiveMasker:
    """Adaptive masking system with SAM2 integration.

    Creates depth-aware composites with various templates.
    Generates web artifacts with glassmorphism effects.
    """

    def __init__(
        self,
        use_sam2: bool = True,
        face_detector: str = "mediapipe",  # or "opencv"
        quality: str = "high",  # low, medium, high, ultra
    ):
        self.use_sam2 = use_sam2
        self.face_detector = face_detector
        self.quality = quality

        # Quality presets
        self._quality_presets = {
            "low": {"scale": 0.5, "crf": 28, "preset": "veryfast"},
            "medium": {"scale": 0.75, "crf": 23, "preset": "medium"},
            "high": {"scale": 1.0, "crf": 18, "preset": "slow"},
            "ultra": {"scale": 1.5, "crf": 15, "preset": "veryslow"},
        }

        self._face_cascade = None
        self._mp_face = None
        self._segmenter = None

    def _init_face_detector(self):
        """Initialize face detection."""
        if self._face_cascade is not None or self._mp_face is not None:
            return

        if self.face_detector == "mediapipe":
            try:
                import mediapipe as mp

                self._mp_face = mp.solutions.face_detection.FaceDetection(
                    model_selection=1, min_detection_confidence=0.5
                )
            except ImportError:
                self.face_detector = "opencv"

        if self.face_detector == "opencv":
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._face_cascade = cv2.CascadeClassifier(cascade_path)

    def _init_segmenter(self):
        """Initialize SAM2 segmenter if available."""
        if self._segmenter is not None:
            return

        if self.use_sam2:
            try:
                from kagami_media.segmentation import VideoSegmenter

                self._segmenter = VideoSegmenter(sample_interval=0.1)
            except ImportError:
                print("SAM2 not available, using basic masking")
                self.use_sam2 = False

    def detect_faces(self, frame: np.ndarray) -> list[FaceRegion]:
        """Detect faces in a frame with depth estimation."""
        self._init_face_detector()

        h, w = frame.shape[:2]
        faces = []

        if self._mp_face is not None:
            # MediaPipe detection
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._mp_face.process(rgb)

            if results.detections:
                for detection in results.detections:
                    bbox_data = detection.location_data.relative_bounding_box
                    x1 = int(bbox_data.xmin * w)
                    y1 = int(bbox_data.ymin * h)
                    x2 = x1 + int(bbox_data.width * w)
                    y2 = y1 + int(bbox_data.height * h)

                    # Clamp to frame bounds
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)

                    area = (x2 - x1) * (y2 - y1)
                    center = ((x1 + x2) // 2, (y1 + y2) // 2)

                    # Estimate depth by face size (larger = closer)
                    face_ratio = area / (w * h)
                    if face_ratio > 0.15:
                        depth = DepthLayer.FOREGROUND
                    elif face_ratio > 0.05:
                        depth = DepthLayer.MID_GROUND
                    else:
                        depth = DepthLayer.BACKGROUND

                    faces.append(
                        FaceRegion(
                            bbox=(x1, y1, x2, y2),
                            center=center,
                            area=area,
                            confidence=detection.score[0],
                            depth_layer=depth,
                        )
                    )

        elif self._face_cascade is not None:
            # OpenCV Haar cascade
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detected = self._face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )

            for x, y, bw, bh in detected:
                x1, y1, x2, y2 = x, y, x + bw, y + bh
                area = bw * bh
                center = (x + bw // 2, y + bh // 2)

                face_ratio = area / (w * h)
                if face_ratio > 0.15:
                    depth = DepthLayer.FOREGROUND
                elif face_ratio > 0.05:
                    depth = DepthLayer.MID_GROUND
                else:
                    depth = DepthLayer.BACKGROUND

                faces.append(
                    FaceRegion(
                        bbox=(x1, y1, x2, y2),
                        center=center,
                        area=area,
                        confidence=0.7,
                        depth_layer=depth,
                    )
                )

        # Sort by area (largest first)
        faces.sort(key=lambda f: f.area, reverse=True)
        return faces

    def extract_subject_mask(
        self, video_path: Path, frame_idx: int = 0
    ) -> tuple[np.ndarray, np.ndarray]:
        """Extract subject mask using SAM2 or fallback.

        Returns:
            (frame, mask) - Original frame and binary mask
        """
        self._init_segmenter()

        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise RuntimeError(f"Could not read frame {frame_idx} from {video_path}")

        h, w = frame.shape[:2]

        if self._segmenter is not None:
            # Use SAM2 segmentation
            segments = list(self._segmenter.segment_video(str(video_path), sample_interval=10))
            if segments and segments[0].segments:
                # Use first person's mask
                mask = segments[0].segments[0].mask
                return frame, mask

        # Fallback: Use face detection to create rough mask
        faces = self.detect_faces(frame)
        if faces:
            # Create mask around largest face
            face = faces[0]
            x1, y1, x2, y2 = face.bbox

            # Expand to include likely body area
            face_h = y2 - y1
            body_bottom = min(h, y2 + int(face_h * 3))
            body_left = max(0, x1 - int((x2 - x1) * 0.5))
            body_right = min(w, x2 + int((x2 - x1) * 0.5))

            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.rectangle(mask, (body_left, y1), (body_right, body_bottom), 255, -1)

            # Soften edges
            mask = cv2.GaussianBlur(mask, (21, 21), 0)
            mask = (mask > 128).astype(np.uint8)

            return frame, mask

        # No face found, return empty mask
        return frame, np.zeros((h, w), dtype=np.uint8)

    def create_composite(
        self,
        background_video: Path,
        overlay_video: Path,
        output_path: Path,
        template: CompositeTemplate = CompositeTemplate.GIANT_FACE_CORNER,
        corner: str = "bottom-right",  # top-left, top-right, bottom-left, bottom-right
        overlay_scale: float = 0.6,  # 0.0-1.0, how big the overlay is
        glassmorphism: bool = True,
        audio_mode: str = "overlay",  # background, overlay, mix
    ) -> CompositeResult:
        """Create composite video with template.

        Args:
            background_video: Main video (plays in background)
            overlay_video: Overlay video (face/character)
            output_path: Where to save result
            template: Composition template to use
            corner: Which corner for overlay (if applicable)
            overlay_scale: Size of overlay (0.0-1.0)
            glassmorphism: Add frosted glass effect
            audio_mode: Which audio to use

        Returns:
            CompositeResult with success status
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get video info
        bg_info = self._get_video_info(background_video)
        ov_info = self._get_video_info(overlay_video)

        if not bg_info or not ov_info:
            return CompositeResult(success=False, error="Could not read video info")

        bg_w, bg_h = bg_info["width"], bg_info["height"]

        # Calculate overlay dimensions based on template
        if template == CompositeTemplate.GIANT_FACE_CORNER:
            # Giant face: takes up significant portion of screen
            ov_w = int(bg_w * overlay_scale)
            ov_h = int(bg_h * overlay_scale)

            # Position based on corner
            positions = {
                "top-left": (20, 20),
                "top-right": (bg_w - ov_w - 20, 20),
                "bottom-left": (20, bg_h - ov_h - 20),
                "bottom-right": (bg_w - ov_w - 20, bg_h - ov_h - 20),
            }
            ov_x, ov_y = positions.get(corner, positions["bottom-right"])

        elif template == CompositeTemplate.SPLIT_VERTICAL:
            # Side by side
            ov_w = bg_w // 2
            ov_h = bg_h
            ov_x = bg_w // 2
            ov_y = 0

        elif template == CompositeTemplate.FULL_FRAME_FLOAT:
            # Floating panel (smaller, with glassmorphism)
            ov_w = int(bg_w * 0.35)
            ov_h = int(bg_h * 0.4)
            ov_x = bg_w - ov_w - 40
            ov_y = bg_h - ov_h - 40

        else:
            # Default: corner PiP
            ov_w = int(bg_w * 0.3)
            ov_h = int(bg_h * 0.35)
            ov_x = bg_w - ov_w - 30
            ov_y = bg_h - ov_h - 30

        # Build FFmpeg filter
        if glassmorphism and template in (
            CompositeTemplate.GIANT_FACE_CORNER,
            CompositeTemplate.FULL_FRAME_FLOAT,
        ):
            # Glassmorphism: blur background behind overlay, add white tint
            filter_complex = f"""
            [0:v]scale={bg_w}:{bg_h}[bg];
            [1:v]scale={ov_w}:{ov_h}[ov];

            [bg]crop={ov_w + 40}:{ov_h + 40}:{max(0, ov_x - 20)}:{max(0, ov_y - 20)},
               boxblur=15:3,
               colorchannelmixer=rr=1:gg=1:bb=1:aa=0.3[blur_region];

            [bg][blur_region]overlay={max(0, ov_x - 20)}:{max(0, ov_y - 20)}[with_blur];

            [with_blur]drawbox=x={ov_x - 3}:y={ov_y - 3}:w={ov_w + 6}:h={ov_h + 6}:color=white@0.5:t=3[with_border];

            [with_border][ov]overlay={ov_x}:{ov_y}:shortest=1[vout]
            """
        else:
            # Simple overlay
            filter_complex = f"""
            [0:v]scale={bg_w}:{bg_h}[bg];
            [1:v]scale={ov_w}:{ov_h}[ov];
            [bg][ov]overlay={ov_x}:{ov_y}:shortest=1[vout]
            """

        # Audio mapping
        audio_map = "1:a" if audio_mode == "overlay" else "0:a"

        # Get quality preset
        preset = self._quality_presets.get(self.quality, self._quality_presets["high"])

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(background_video),
            "-i",
            str(overlay_video),
            "-filter_complex",
            filter_complex.strip().replace("\n", " "),
            "-map",
            "[vout]",
            "-map",
            audio_map,
            "-c:v",
            "libx264",
            "-preset",
            preset["preset"],
            "-crf",
            str(preset["crf"]),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t",
            str(min(bg_info.get("duration", 10), ov_info.get("duration", 10))),
            str(output_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return CompositeResult(success=False, error=f"FFmpeg failed: {result.stderr[-500:]}")

        return CompositeResult(
            success=True,
            output_path=output_path,
            metadata={
                "template": template.name,
                "overlay_size": (ov_w, ov_h),
                "overlay_position": (ov_x, ov_y),
                "glassmorphism": glassmorphism,
            },
        )

    def _get_video_info(self, video_path: Path) -> dict | None:
        """Get video dimensions and duration."""
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,duration",
            "-of",
            "json",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return None

        try:
            data = json.loads(result.stdout)
            stream = data.get("streams", [{}])[0]
            return {
                "width": stream.get("width", 1280),
                "height": stream.get("height", 720),
                "duration": float(stream.get("duration", 10)),
            }
        except (json.JSONDecodeError, IndexError, ValueError):
            return None

    def create_chromakey_composite(
        self,
        background_video: Path,
        greenscreen_video: Path,
        output_path: Path,
        chroma_color: str = "0x00FF00",
        chroma_similarity: float = 0.3,
        chroma_blend: float = 0.2,
        position: tuple[int, int] | None = None,
        scale: float = 1.0,
    ) -> CompositeResult:
        """Create composite with chromakey (green screen removal).

        Args:
            background_video: Background video
            greenscreen_video: Video with green screen to overlay
            output_path: Output path
            chroma_color: Green screen color (hex)
            chroma_similarity: Color matching threshold
            chroma_blend: Edge blend amount
            position: (x, y) position, or None for center
            scale: Scale factor for overlay

        Returns:
            CompositeResult
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        bg_info = self._get_video_info(background_video)
        ov_info = self._get_video_info(greenscreen_video)

        if not bg_info or not ov_info:
            return CompositeResult(success=False, error="Could not read video info")

        bg_w, bg_h = bg_info["width"], bg_info["height"]
        ov_w = int(ov_info["width"] * scale)
        ov_h = int(ov_info["height"] * scale)

        if position is None:
            # Center
            ov_x = (bg_w - ov_w) // 2
            ov_y = (bg_h - ov_h) // 2
        else:
            ov_x, ov_y = position

        # Chromakey filter
        filter_complex = f"""
        [0:v]scale={bg_w}:{bg_h}[bg];
        [1:v]colorkey={chroma_color}:{chroma_similarity}:{chroma_blend},scale={ov_w}:{ov_h}[fg];
        [bg][fg]overlay={ov_x}:{ov_y}:shortest=1[vout]
        """

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(background_video),
            "-i",
            str(greenscreen_video),
            "-filter_complex",
            filter_complex.strip().replace("\n", " "),
            "-map",
            "[vout]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return CompositeResult(success=False, error=f"FFmpeg failed: {result.stderr[-500:]}")

        return CompositeResult(
            success=True,
            output_path=output_path,
            metadata={"chromakey": True, "chroma_color": chroma_color},
        )

    def create_composite_with_spatial_audio(
        self,
        background_video: Path,
        overlay_video: Path,
        output_path: Path,
        template: CompositeTemplate = CompositeTemplate.GIANT_FACE_CORNER,
        overlay_scale: float = 0.55,
        corner: str = "bottom-right",
        # Audio mixing
        background_audio_volume: float = 0.7,
        overlay_audio_volume: float = 1.0,
        overlay_audio_pan: float = 0.0,  # -1.0 (left) to 1.0 (right)
        ducking: bool = True,
    ) -> CompositeResult:
        """Create composite with spatialized audio mixing.

        Mixes both audio sources:
        - Background audio (original video sound)
        - Overlay audio (inner voice, dialogue)

        Args:
            background_video: Main video with its audio
            overlay_video: Overlay video with its audio
            output_path: Output path
            template: Composition template
            overlay_scale: Size of overlay
            corner: Position corner
            background_audio_volume: Volume of background (0.0-1.0)
            overlay_audio_volume: Volume of overlay (0.0-1.0)
            overlay_audio_pan: Stereo pan for overlay (-1.0 left, 1.0 right)
            ducking: Reduce background when overlay speaks

        Returns:
            CompositeResult
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = output_path.parent / "temp"
        temp_dir.mkdir(exist_ok=True)

        bg_info = self._get_video_info(background_video)
        ov_info = self._get_video_info(overlay_video)

        if not bg_info or not ov_info:
            return CompositeResult(success=False, error="Could not read video info")

        bg_w, bg_h = bg_info["width"], bg_info["height"]

        # Calculate overlay dimensions
        if template == CompositeTemplate.GIANT_FACE_CORNER:
            ov_h = int(bg_h * overlay_scale)
            ov_w = int(ov_h * (ov_info["width"] / ov_info["height"]))

            margin = 40
            positions = {
                "top-left": (margin, margin),
                "top-right": (bg_w - ov_w - margin, margin),
                "bottom-left": (margin, bg_h - ov_h - margin),
                "bottom-right": (bg_w - ov_w - margin, bg_h - ov_h - margin),
            }
            ov_x, ov_y = positions.get(corner, positions["bottom-right"])
        else:
            ov_w = int(bg_w * 0.3)
            ov_h = int(bg_h * 0.35)
            ov_x = bg_w - ov_w - 30
            ov_y = bg_h - ov_h - 30

        # Glassmorphism with audio mixing
        glow = 20
        border = 3

        crop_x = max(0, ov_x - glow)
        crop_y = max(0, ov_y - glow)
        crop_w = min(ov_w + glow * 2, bg_w - crop_x)
        crop_h = min(ov_h + glow * 2, bg_h - crop_y)

        # Video filter
        video_filter = f"""
        [0:v]scale={bg_w}:{bg_h}[bg];
        [1:v]scale={ov_w}:{ov_h}[face];

        [bg]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},
           boxblur=20:5,
           colorchannelmixer=rr=1.1:gg=1.1:bb=1.1:aa=0.85[blur_region];

        [bg][blur_region]overlay={crop_x}:{crop_y}[with_blur];

        [with_blur]drawbox=x={ov_x - border}:y={ov_y - border}:w={ov_w + border * 2}:h={ov_h + border * 2}:color=white@0.6:t={border}[with_border];

        [with_border][face]overlay={ov_x}:{ov_y}:shortest=1[vout]
        """

        # Audio filter with spatial mixing
        # Background audio: volume control
        # Overlay audio: volume + stereo pan + optional ducking
        if overlay_audio_pan != 0:
            # Stereo pan
            left = max(0, 1 - overlay_audio_pan) if overlay_audio_pan > 0 else 1
            right = max(0, 1 + overlay_audio_pan) if overlay_audio_pan < 0 else 1
            pan_filter = f"pan=stereo|c0={left}*c0+{1 - left}*c1|c1={1 - right}*c0+{right}*c1"
            overlay_audio_chain = f"volume={overlay_audio_volume},{pan_filter}"
        else:
            overlay_audio_chain = f"volume={overlay_audio_volume}"

        if ducking:
            # Simple ducking: reduce background volume slightly
            bg_vol = background_audio_volume * 0.6
        else:
            bg_vol = background_audio_volume

        audio_filter = f"""
        [0:a]volume={bg_vol}[bg_audio];
        [1:a]{overlay_audio_chain}[ov_audio];
        [bg_audio][ov_audio]amix=inputs=2:duration=shortest:normalize=0[aout]
        """

        duration = min(bg_info.get("duration", 10), ov_info.get("duration", 10), 30)

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(background_video),
            "-i",
            str(overlay_video),
            "-filter_complex",
            (video_filter + ";" + audio_filter).strip().replace("\n", " "),
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t",
            str(duration),
            str(output_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return CompositeResult(success=False, error=f"FFmpeg failed: {result.stderr[-500:]}")

        # Cleanup temp
        shutil.rmtree(temp_dir, ignore_errors=True)

        return CompositeResult(
            success=True,
            output_path=output_path,
            metadata={
                "template": template.name,
                "spatial_audio": True,
                "overlay_pan": overlay_audio_pan,
                "ducking": ducking,
            },
        )


def create_giant_face_composite(
    background: Path,
    face_video: Path,
    output: Path,
    scale: float = 0.55,
    corner: str = "bottom-right",
) -> CompositeResult:
    """Quick function to create giant face in corner composite.

    Args:
        background: Main video
        face_video: Face/character video
        output: Output path
        scale: How big the face is (0.0-1.0)
        corner: Which corner

    Returns:
        CompositeResult
    """
    masker = AdaptiveMasker(quality="high")
    return masker.create_composite(
        background_video=background,
        overlay_video=face_video,
        output_path=output,
        template=CompositeTemplate.GIANT_FACE_CORNER,
        corner=corner,
        overlay_scale=scale,
        glassmorphism=True,
    )


def create_web_artifact(
    video_path: Path,
    overlay_path: Path | None = None,
    output_dir: Path = Path("/tmp/web_artifact"),
    template: str = "dcc",  # dcc, minimal, split
    title: str = "Video Showcase",
    subtitle: str = "",
) -> Path:
    """Generate a web artifact (HTML page) with video.

    Creates a DCC-style interactive page with:
    - Full-frame video background
    - Glassmorphism overlays
    - Optional floating character panel

    Args:
        video_path: Main video
        overlay_path: Optional overlay video
        output_dir: Where to save HTML and assets
        template: Style template
        title: Page title
        subtitle: Optional subtitle

    Returns:
        Path to generated index.html
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy video(s) to output dir
    import shutil

    main_video = output_dir / "main.mp4"
    shutil.copy(video_path, main_video)

    overlay_video = None
    if overlay_path and overlay_path.exists():
        overlay_video = output_dir / "overlay.mp4"
        shutil.copy(overlay_path, overlay_video)

    # Generate HTML
    html = _generate_dcc_html(
        main_video_name="main.mp4",
        overlay_video_name="overlay.mp4" if overlay_video else None,
        title=title,
        subtitle=subtitle,
    )

    html_path = output_dir / "index.html"
    html_path.write_text(html)

    return html_path


def _generate_dcc_html(
    main_video_name: str,
    overlay_video_name: str | None,
    title: str,
    subtitle: str,
) -> str:
    """Generate DCC-style HTML page."""

    overlay_section = ""
    if overlay_video_name:
        overlay_section = f"""
        <!-- Floating Character Panel -->
        <div class="character-panel">
            <video class="character-video" autoplay loop muted playsinline>
                <source src="{overlay_video_name}" type="video/mp4">
            </video>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #000;
            color: #fff;
            overflow: hidden;
            height: 100vh;
            width: 100vw;
        }}

        .container {{
            position: relative;
            width: 100%;
            height: 100%;
            display: flex;
        }}

        /* Main Video - Full Frame */
        .video-panel {{
            flex: 1;
            position: relative;
            overflow: hidden;
        }}

        .main-video {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            object-position: center 30%;
        }}

        /* Gradient Overlay */
        .gradient-overlay {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(
                to right,
                rgba(0, 0, 0, 0.3) 0%,
                rgba(0, 0, 0, 0) 30%,
                rgba(0, 0, 0, 0) 70%,
                rgba(0, 0, 0, 0.5) 100%
            );
            pointer-events: none;
        }}

        /* Character Panel - Giant Face in Corner */
        .character-panel {{
            position: absolute;
            bottom: 40px;
            right: 40px;
            width: 45vw;
            max-width: 600px;
            aspect-ratio: 1 / 1;
            border-radius: 24px;
            overflow: hidden;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 2px solid rgba(255, 255, 255, 0.3);
            box-shadow:
                0 8px 32px rgba(0, 0, 0, 0.3),
                0 0 80px rgba(255, 255, 255, 0.1);
            animation: float 6s ease-in-out infinite;
        }}

        .character-video {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        @keyframes float {{
            0%, 100% {{ transform: translateY(0); }}
            50% {{ transform: translateY(-10px); }}
        }}

        /* Title Overlay */
        .title-overlay {{
            position: absolute;
            top: 40px;
            left: 40px;
            z-index: 10;
        }}

        .title {{
            font-size: clamp(2rem, 5vw, 4rem);
            font-weight: 700;
            letter-spacing: -0.02em;
            text-shadow: 0 2px 20px rgba(0, 0, 0, 0.5);
            background: linear-gradient(135deg, #fff 0%, #ccc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .subtitle {{
            font-size: clamp(1rem, 2vw, 1.5rem);
            opacity: 0.8;
            margin-top: 0.5em;
            font-weight: 400;
        }}

        /* Controls */
        .controls {{
            position: absolute;
            bottom: 40px;
            left: 40px;
            display: flex;
            gap: 16px;
            z-index: 10;
        }}

        .control-btn {{
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            color: white;
            font-size: 20px;
        }}

        .control-btn:hover {{
            background: rgba(255, 255, 255, 0.25);
            transform: scale(1.1);
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .character-panel {{
                width: 60vw;
                bottom: 20px;
                right: 20px;
            }}

            .title-overlay {{
                top: 20px;
                left: 20px;
            }}

            .controls {{
                bottom: 20px;
                left: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="video-panel">
            <video class="main-video" autoplay loop muted playsinline id="mainVideo">
                <source src="{main_video_name}" type="video/mp4">
            </video>
            <div class="gradient-overlay"></div>
        </div>

        {overlay_section}

        <div class="title-overlay">
            <h1 class="title">{title}</h1>
            {"<p class='subtitle'>" + subtitle + "</p>" if subtitle else ""}
        </div>

        <div class="controls">
            <button class="control-btn" onclick="togglePlay()" id="playBtn">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                    <path id="playIcon" d="M8 5v14l11-7z"/>
                </svg>
            </button>
            <button class="control-btn" onclick="toggleMute()" id="muteBtn">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                    <path id="muteIcon" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
                </svg>
            </button>
        </div>
    </div>

    <script>
        const video = document.getElementById('mainVideo');
        const playBtn = document.getElementById('playBtn');
        const playIcon = document.getElementById('playIcon');
        const muteBtn = document.getElementById('muteBtn');
        const muteIcon = document.getElementById('muteIcon');

        function togglePlay() {{
            if (video.paused) {{
                video.play();
                playIcon.setAttribute('d', 'M6 19h4V5H6v14zm8-14v14h4V5h-4z'); // Pause icon
            }} else {{
                video.pause();
                playIcon.setAttribute('d', 'M8 5v14l11-7z'); // Play icon
            }}
        }}

        function toggleMute() {{
            video.muted = !video.muted;
            if (video.muted) {{
                muteIcon.setAttribute('d', 'M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z');
            }} else {{
                muteIcon.setAttribute('d', 'M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z');
            }}
        }}

        // Auto-play handling
        video.play().catch(() => {{
            // Autoplay blocked, show play button
            playIcon.setAttribute('d', 'M8 5v14l11-7z');
        }});
    </script>
</body>
</html>
"""
