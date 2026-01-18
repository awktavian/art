"""Video Segmentation Module.

Uses SAM2 (Segment Anything Model 2) for video object segmentation.
Extracts pixel-perfect masks of all people in videos.

Key Features:
- Automatic person detection and segmentation
- Frame-to-frame tracking of segmented objects
- Alpha matte export for compositing
- Confidence scoring and reasoning

Usage:
    from kagami_media.segmentation import VideoSegmenter

    segmenter = VideoSegmenter()
    segments = segmenter.segment_video("/path/to/video.mp4")
"""

from kagami_media.segmentation.sam2_segmenter import (
    FrameSegmentation,
    PersonSegment,
    VideoSegmenter,
    segment_video,
)

__all__ = [
    "FrameSegmentation",
    "PersonSegment",
    "VideoSegmenter",
    "segment_video",
]
