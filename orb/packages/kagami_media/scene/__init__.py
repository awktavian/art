"""Scene Context Extraction Module.

Extracts environment data from videos for scene reproduction.
Includes background extraction, lighting analysis, and scene classification.

Key Features:
- Background extraction (inpaint people out)
- Lighting analysis (color temperature, direction)
- Environment classification (indoor/outdoor, room type)
- Object detection for context

Usage:
    from kagami_media.scene import SceneAnalyzer

    analyzer = SceneAnalyzer()
    context = analyzer.analyze("video.mp4")
"""

from kagami_media.scene.context_extractor import (
    LightingInfo,
    SceneAnalyzer,
    SceneContext,
    analyze_scene,
)

__all__ = [
    "LightingInfo",
    "SceneAnalyzer",
    "SceneContext",
    "analyze_scene",
]
