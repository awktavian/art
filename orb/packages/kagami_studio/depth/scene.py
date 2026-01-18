"""Scene Analysis — Extract 3D structure from depth.

Analyze depth maps to understand scene geometry:
- Layer segmentation (foreground/midground/background)
- Plane detection
- Object boundaries
- Occlusion relationships

Usage:
    from kagami_studio.depth import analyze_scene, segment_by_depth

    # Get scene structure
    geometry = await analyze_scene(image, depth)

    # Segment into depth layers
    layers = segment_by_depth(depth, num_layers=3)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from kagami_studio.depth.estimator import DepthResult

logger = logging.getLogger(__name__)


class LayerType(Enum):
    """Semantic layer types."""

    BACKGROUND = auto()  # Sky, distant objects
    FAR = auto()  # Far background objects
    MID = auto()  # Middle ground
    NEAR = auto()  # Near foreground
    FOREGROUND = auto()  # Closest objects
    SUBJECT = auto()  # Main subject (detected)


@dataclass
class DepthLayer:
    """A single depth-based layer."""

    layer_type: LayerType
    mask: np.ndarray  # Binary mask (HxW, uint8)
    depth_range: tuple[float, float]  # (min, max) depth values
    area_ratio: float = 0.0  # Fraction of image area

    # Optional: extracted RGB
    rgb: np.ndarray | None = None

    # Optional: bounding box
    bbox: tuple[int, int, int, int] | None = None  # x1, y1, x2, y2

    def extract_rgb(self, image: np.ndarray) -> np.ndarray:
        """Extract RGB for this layer with alpha."""
        h, w = image.shape[:2]
        if self.mask.shape != (h, w):
            mask = cv2.resize(self.mask, (w, h))
        else:
            mask = self.mask

        # Create RGBA
        rgba = cv2.cvtColor(image, cv2.COLOR_RGB2RGBA)
        rgba[:, :, 3] = mask
        return rgba


@dataclass
class Plane:
    """Detected plane in scene."""

    normal: np.ndarray  # 3D normal vector
    distance: float  # Distance from camera
    mask: np.ndarray  # Pixels belonging to plane
    area_ratio: float = 0.0
    plane_type: str = "unknown"  # floor, wall, ceiling, table


@dataclass
class SceneGeometry:
    """Complete scene geometry analysis."""

    # Depth layers
    layers: list[DepthLayer] = field(default_factory=list)

    # Detected planes
    planes: list[Plane] = field(default_factory=list)

    # Scene statistics
    depth_histogram: np.ndarray | None = None
    median_depth: float = 0.5
    depth_variance: float = 0.0

    # Scene type estimation
    scene_type: str = "unknown"  # indoor, outdoor, portrait, landscape
    has_subject: bool = False
    subject_depth: float = 0.0

    # Occlusion map (which pixels occlude which)
    occlusion_edges: np.ndarray | None = None

    def get_layer(self, layer_type: LayerType) -> DepthLayer | None:
        """Get layer by type."""
        for layer in self.layers:
            if layer.layer_type == layer_type:
                return layer
        return None

    def get_foreground_mask(self) -> np.ndarray:
        """Get combined foreground mask."""
        masks = []
        for layer in self.layers:
            if layer.layer_type in (LayerType.FOREGROUND, LayerType.SUBJECT, LayerType.NEAR):
                masks.append(layer.mask)

        if not masks:
            return np.zeros((100, 100), dtype=np.uint8)

        combined = masks[0].copy()
        for m in masks[1:]:
            combined = cv2.bitwise_or(combined, m)
        return combined

    def get_background_mask(self) -> np.ndarray:
        """Get combined background mask."""
        masks = []
        for layer in self.layers:
            if layer.layer_type in (LayerType.BACKGROUND, LayerType.FAR):
                masks.append(layer.mask)

        if not masks:
            return np.zeros((100, 100), dtype=np.uint8)

        combined = masks[0].copy()
        for m in masks[1:]:
            combined = cv2.bitwise_or(combined, m)
        return combined


def segment_by_depth(
    depth: DepthResult,
    num_layers: int = 3,
    method: str = "quantile",
) -> list[DepthLayer]:
    """Segment image into depth layers.

    Args:
        depth: Depth estimation result
        num_layers: Number of layers to create
        method: 'quantile' (equal area) or 'linear' (equal depth range)

    Returns:
        List of DepthLayer objects
    """
    depth_map = depth.normalize()
    h, w = depth_map.shape

    layers = []

    if method == "quantile":
        # Equal area in each layer
        flat = depth_map.flatten()
        percentiles = np.linspace(0, 100, num_layers + 1)
        thresholds = np.percentile(flat, percentiles)
    else:
        # Linear depth ranges
        thresholds = np.linspace(0, 1, num_layers + 1)

    layer_types = [
        LayerType.BACKGROUND,
        LayerType.FAR,
        LayerType.MID,
        LayerType.NEAR,
        LayerType.FOREGROUND,
    ]

    for i in range(num_layers):
        d_min = thresholds[i]
        d_max = thresholds[i + 1]

        # Create mask
        mask = ((depth_map >= d_min) & (depth_map < d_max)).astype(np.uint8) * 255

        # Calculate area
        area_ratio = np.sum(mask > 0) / (h * w)

        # Determine layer type
        if num_layers <= len(layer_types):
            layer_type = layer_types[min(i, len(layer_types) - 1)]
        else:
            layer_type = LayerType.MID

        # Get bounding box
        coords = np.where(mask > 0)
        if len(coords[0]) > 0:
            y1, y2 = coords[0].min(), coords[0].max()
            x1, x2 = coords[1].min(), coords[1].max()
            bbox = (x1, y1, x2, y2)
        else:
            bbox = None

        layers.append(
            DepthLayer(
                layer_type=layer_type,
                mask=mask,
                depth_range=(d_min, d_max),
                area_ratio=area_ratio,
                bbox=bbox,
            )
        )

    return layers


def detect_subject(
    image: np.ndarray,
    depth: DepthResult,
) -> DepthLayer | None:
    """Detect main subject using depth + saliency.

    Args:
        image: RGB image
        depth: Depth result

    Returns:
        DepthLayer for subject, or None if not found
    """
    depth_map = depth.normalize()
    h, w = depth_map.shape

    # Simple saliency: assume subject is:
    # 1. In the center-ish region
    # 2. Closer than average
    # 3. Has distinct depth from surroundings

    # Create center weight
    y_center = h // 2
    x_center = w // 2
    y, x = np.ogrid[:h, :w]
    center_dist = np.sqrt((x - x_center) ** 2 + (y - y_center) ** 2)
    center_weight = 1 - (center_dist / np.max(center_dist))

    # Combine depth (prefer close) with center weight
    score = depth_map * 0.7 + center_weight * 0.3

    # Threshold to get subject region
    threshold = np.percentile(score, 80)
    subject_mask = (score > threshold).astype(np.uint8) * 255

    # Clean up with morphology
    kernel = np.ones((5, 5), np.uint8)
    subject_mask = cv2.morphologyEx(subject_mask, cv2.MORPH_CLOSE, kernel)
    subject_mask = cv2.morphologyEx(subject_mask, cv2.MORPH_OPEN, kernel)

    if np.sum(subject_mask > 0) < 100:
        return None

    # Get depth range
    subject_depths = depth_map[subject_mask > 0]
    d_min, d_max = float(np.min(subject_depths)), float(np.max(subject_depths))

    # Bounding box
    coords = np.where(subject_mask > 0)
    y1, y2 = coords[0].min(), coords[0].max()
    x1, x2 = coords[1].min(), coords[1].max()

    return DepthLayer(
        layer_type=LayerType.SUBJECT,
        mask=subject_mask,
        depth_range=(d_min, d_max),
        area_ratio=np.sum(subject_mask > 0) / (h * w),
        bbox=(x1, y1, x2, y2),
    )


def detect_edges(depth: DepthResult) -> np.ndarray:
    """Detect depth discontinuity edges (occlusion boundaries).

    Args:
        depth: Depth result

    Returns:
        Edge map (HxW uint8)
    """
    depth_map = depth.normalize()

    # Compute gradient magnitude
    grad_x = cv2.Sobel(depth_map, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(depth_map, cv2.CV_64F, 0, 1, ksize=3)
    grad_mag = np.sqrt(grad_x**2 + grad_y**2)

    # Threshold to get significant depth edges
    threshold = np.percentile(grad_mag, 90)
    edges = (grad_mag > threshold).astype(np.uint8) * 255

    return edges


async def analyze_scene(
    image: np.ndarray,
    depth: DepthResult,
    num_layers: int = 3,
) -> SceneGeometry:
    """Complete scene geometry analysis.

    Args:
        image: RGB image
        depth: Depth result

    Returns:
        SceneGeometry with layers, planes, statistics
    """
    depth_map = depth.normalize()

    # Segment into layers
    layers = segment_by_depth(depth, num_layers=num_layers)

    # Detect subject
    subject = detect_subject(image, depth)
    if subject:
        layers.append(subject)

    # Depth statistics
    depth_histogram = np.histogram(depth_map.flatten(), bins=50)[0]
    median_depth = float(np.median(depth_map))
    depth_variance = float(np.var(depth_map))

    # Occlusion edges
    occlusion_edges = detect_edges(depth)

    # Estimate scene type
    if depth_variance < 0.05:
        scene_type = "flat"  # Very uniform depth (document, etc.)
    elif median_depth > 0.7:
        scene_type = "portrait"  # Subject close, background far
    elif median_depth < 0.3:
        scene_type = "landscape"  # Most things far
    else:
        scene_type = "general"

    return SceneGeometry(
        layers=layers,
        depth_histogram=depth_histogram,
        median_depth=median_depth,
        depth_variance=depth_variance,
        scene_type=scene_type,
        has_subject=subject is not None,
        subject_depth=subject.depth_range[0] if subject else 0.0,
        occlusion_edges=occlusion_edges,
    )
