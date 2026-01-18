"""KAGAMI STUDIO — Vision Analysis Module

SOTA video quality analysis with:
- Laplacian sharpness (edge detection)
- BRISQUE (no-reference quality)
- Frechet Video Distance concepts
- Temporal consistency
- Artifact detection (halo, ringing, hallucination)
- Face quality metrics
"""

from .vision_analyzer import (
    FrameMetrics,
    VideoMetrics,
    VisionAnalyzer,
    analyze_frame,
    analyze_video,
    compare_enhancements,
)

__all__ = [
    "FrameMetrics",
    "VideoMetrics",
    "VisionAnalyzer",
    "analyze_frame",
    "analyze_video",
    "compare_enhancements",
]
