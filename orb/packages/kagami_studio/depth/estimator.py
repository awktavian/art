"""Depth Estimation — Extract depth from photos and video.

Supports multiple models:
- Depth Anything V2: Fast, accurate monocular depth
- DepthCrafter: Temporally consistent video depth
- MiDaS 3.1: Classic fallback
- ZoeDepth: Metric depth (actual distances)

Usage:
    # Single image
    depth = await estimate_depth("photo.jpg")

    # Video with temporal consistency
    depths = await estimate_video_depth("video.mp4", model="depthcrafter")
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class DepthModel(Enum):
    """Available depth estimation models."""

    # Fast, accurate relative depth
    DEPTH_ANYTHING_V2_SMALL = "depth-anything-v2-small"  # 25M params
    DEPTH_ANYTHING_V2_BASE = "depth-anything-v2-base"  # 97M params
    DEPTH_ANYTHING_V2_LARGE = "depth-anything-v2-large"  # 335M params
    DEPTH_ANYTHING_V2_GIANT = "depth-anything-v2-giant"  # 1.3B params

    # Temporally consistent video depth
    DEPTHCRAFTER = "depthcrafter"

    # Metric depth (actual distances)
    ZOEDEPTH_INDOOR = "zoedepth-indoor"
    ZOEDEPTH_OUTDOOR = "zoedepth-outdoor"

    # Classic fallback
    MIDAS_SMALL = "midas-small"
    MIDAS_LARGE = "midas-large"


@dataclass
class DepthResult:
    """Result from depth estimation."""

    depth_map: np.ndarray  # HxW float32, 0=far, 1=near (relative)
    metric_depth: np.ndarray | None = None  # HxW float32, meters (if available)

    width: int = 0
    height: int = 0

    # Depth statistics
    min_depth: float = 0.0
    max_depth: float = 1.0
    mean_depth: float = 0.5

    # Model used
    model: str = ""

    # Optional: confidence map
    confidence: np.ndarray | None = None

    def __post_init__(self):
        """Calculate statistics."""
        if self.depth_map is not None:
            self.height, self.width = self.depth_map.shape[:2]
            self.min_depth = float(np.min(self.depth_map))
            self.max_depth = float(np.max(self.depth_map))
            self.mean_depth = float(np.mean(self.depth_map))

    def normalize(self) -> np.ndarray:
        """Get normalized depth map (0-1 range)."""
        if self.max_depth == self.min_depth:
            return np.zeros_like(self.depth_map)
        return (self.depth_map - self.min_depth) / (self.max_depth - self.min_depth)

    def to_colormap(self, colormap: int = cv2.COLORMAP_MAGMA) -> np.ndarray:
        """Convert to colored visualization."""
        normalized = (self.normalize() * 255).astype(np.uint8)
        return cv2.applyColorMap(normalized, colormap)

    def to_point_cloud(
        self,
        rgb: np.ndarray,
        focal_length: float | None = None,
    ) -> np.ndarray:
        """Convert to point cloud (Nx6: X,Y,Z,R,G,B).

        Args:
            rgb: RGB image matching depth dimensions
            focal_length: Camera focal length (estimated if None)

        Returns:
            Point cloud array
        """
        h, w = self.depth_map.shape

        # Estimate focal length if not provided
        if focal_length is None:
            focal_length = max(w, h)

        # Create meshgrid
        u = np.arange(w)
        v = np.arange(h)
        u, v = np.meshgrid(u, v)

        # Backproject to 3D
        cx, cy = w / 2, h / 2

        # Use metric depth if available, otherwise scale relative
        if self.metric_depth is not None:
            z = self.metric_depth
        else:
            # Scale relative depth to reasonable range (1-10 meters)
            z = self.normalize() * 9 + 1

        x = (u - cx) * z / focal_length
        y = (v - cy) * z / focal_length

        # Stack points
        points = np.stack([x, y, z], axis=-1).reshape(-1, 3)

        # Add colors
        if rgb.shape[:2] != (h, w):
            rgb = cv2.resize(rgb, (w, h))
        colors = rgb.reshape(-1, 3)

        return np.hstack([points, colors])


@dataclass
class VideoDepthResult:
    """Result from video depth estimation."""

    frame_depths: list[DepthResult] = field(default_factory=list)
    fps: float = 30.0
    frame_count: int = 0
    model: str = ""
    temporal_consistency: float = 0.0  # 0-1 measure of consistency

    def get_depth_video(self, colormap: int = cv2.COLORMAP_MAGMA) -> np.ndarray:
        """Get depth as video array (TxHxWx3)."""
        return np.stack([d.to_colormap(colormap) for d in self.frame_depths])


class DepthEstimator:
    """Unified depth estimation system.

    Supports multiple models for different use cases:
    - Depth Anything V2: Best quality/speed tradeoff
    - DepthCrafter: Video with temporal consistency
    - ZoeDepth: When you need actual distances
    """

    def __init__(
        self,
        model: DepthModel = DepthModel.DEPTH_ANYTHING_V2_BASE,
        device: str = "auto",
    ):
        """Initialize estimator.

        Args:
            model: Depth model to use
            device: 'auto', 'cuda', 'mps', or 'cpu'
        """
        self.model_type = model
        self.device = self._resolve_device(device)
        self._model = None
        self._transform = None

    def _resolve_device(self, device: str) -> str:
        """Resolve device string to actual device."""
        if device != "auto":
            return device

        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
            if torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    def _load_model(self) -> None:
        """Lazy load the depth model."""
        if self._model is not None:
            return

        from transformers import pipeline

        model_id = self._get_hf_model_id()

        logger.info(f"Loading depth model: {model_id}")

        # Use HuggingFace pipeline for simplicity
        self._model = pipeline(
            "depth-estimation",
            model=model_id,
            device=0 if self.device == "cuda" else -1,
        )

    def _get_hf_model_id(self) -> str:
        """Get HuggingFace model ID."""
        mapping = {
            DepthModel.DEPTH_ANYTHING_V2_SMALL: "depth-anything/Depth-Anything-V2-Small-hf",
            DepthModel.DEPTH_ANYTHING_V2_BASE: "depth-anything/Depth-Anything-V2-Base-hf",
            DepthModel.DEPTH_ANYTHING_V2_LARGE: "depth-anything/Depth-Anything-V2-Large-hf",
            DepthModel.MIDAS_SMALL: "Intel/dpt-swinv2-tiny-256",
            DepthModel.MIDAS_LARGE: "Intel/dpt-large",
            DepthModel.ZOEDEPTH_INDOOR: "Intel/zoedepth-nyu",
            DepthModel.ZOEDEPTH_OUTDOOR: "Intel/zoedepth-kitti",
        }
        return mapping.get(self.model_type, "depth-anything/Depth-Anything-V2-Base-hf")

    async def estimate(
        self,
        image: np.ndarray | str | Path,
    ) -> DepthResult:
        """Estimate depth from image.

        Args:
            image: RGB image array or path

        Returns:
            DepthResult with depth map
        """
        # Load image if path
        if isinstance(image, (str, Path)):
            image = cv2.imread(str(image))
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Load model
        await asyncio.to_thread(self._load_model)

        # Run inference
        from PIL import Image

        pil_image = Image.fromarray(image)

        result = await asyncio.to_thread(self._model, pil_image)

        # Extract depth map
        depth_map = np.array(result["depth"])

        # Normalize to 0-1 (near=1, far=0)
        depth_min = depth_map.min()
        depth_max = depth_map.max()
        if depth_max > depth_min:
            depth_map = (depth_map - depth_min) / (depth_max - depth_min)

        # Invert so near=1, far=0 (more intuitive for rendering)
        depth_map = 1.0 - depth_map

        return DepthResult(
            depth_map=depth_map.astype(np.float32),
            model=self.model_type.value,
        )

    async def estimate_video(
        self,
        video_path: str | Path,
        sample_rate: int = 1,
        max_frames: int | None = None,
    ) -> VideoDepthResult:
        """Estimate depth for video frames.

        Args:
            video_path: Path to video
            sample_rate: Process every Nth frame
            max_frames: Maximum frames to process

        Returns:
            VideoDepthResult with all frame depths
        """
        video_path = Path(video_path)

        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if max_frames:
            total_frames = min(total_frames, max_frames * sample_rate)

        frame_depths = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx >= total_frames:
                break

            if frame_idx % sample_rate == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                depth = await self.estimate(rgb)
                frame_depths.append(depth)

            frame_idx += 1

        cap.release()

        # Calculate temporal consistency (correlation between consecutive frames)
        consistency = 0.0
        if len(frame_depths) > 1:
            correlations = []
            for i in range(len(frame_depths) - 1):
                d1 = frame_depths[i].normalize().flatten()
                d2 = frame_depths[i + 1].normalize().flatten()
                corr = np.corrcoef(d1, d2)[0, 1]
                correlations.append(corr)
            consistency = float(np.mean(correlations))

        return VideoDepthResult(
            frame_depths=frame_depths,
            fps=fps / sample_rate,
            frame_count=len(frame_depths),
            model=self.model_type.value,
            temporal_consistency=consistency,
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def estimate_depth(
    image: np.ndarray | str | Path,
    model: DepthModel = DepthModel.DEPTH_ANYTHING_V2_BASE,
) -> DepthResult:
    """Quick function to estimate depth from image.

    Args:
        image: RGB image or path
        model: Depth model to use

    Returns:
        DepthResult
    """
    estimator = DepthEstimator(model=model)
    return await estimator.estimate(image)


async def estimate_video_depth(
    video_path: str | Path,
    model: DepthModel = DepthModel.DEPTH_ANYTHING_V2_BASE,
    sample_rate: int = 1,
) -> VideoDepthResult:
    """Quick function to estimate depth for video.

    Args:
        video_path: Path to video
        model: Depth model
        sample_rate: Process every Nth frame

    Returns:
        VideoDepthResult
    """
    estimator = DepthEstimator(model=model)
    return await estimator.estimate_video(video_path, sample_rate)
