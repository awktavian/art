"""
Visual Design Module - Character appearance and visual characteristics generation
Includes character profiling and SOTA 3D generation integration
"""

# Lazy imports to avoid heavy deps (e.g., torch) when only utilities are needed
try:
    from .character_profiler import CharacterVisualProfiler
except Exception:  # pragma: no cover
    CharacterVisualProfiler = None  # type: ignore  # Misc+assign

try:
    from .intelligent_visual_designer import (
        IntelligentVisualDesigner,
    )
except Exception:  # pragma: no cover
    IntelligentVisualDesigner = None  # type: ignore  # Misc+assign

__all__: list[str] = [
    "CharacterVisualProfiler",
    "IntelligentVisualDesigner",
]
