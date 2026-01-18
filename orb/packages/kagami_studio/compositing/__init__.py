"""🎬 Kagami Studio Compositing — Unified video composition.

Consolidates all compositing capabilities:
- Adaptive masking (SAM2 + face detection)
- Depth-aware layering
- Template-based composition (DCC-style, PIP, split)
- Chromakey (green screen)
- Glassmorphism effects
- Web artifact generation
- OBS real-time compositing

This module supersedes kagami_media.compositing (deprecated).

Quick Start - Offline Compositing:
    from kagami_studio.compositing import (
        create_pip_composite,
        create_documentary_composite,
        create_chromakey_composite,
    )

    # Simple PIP
    result = await create_pip_composite(
        background="gameplay.mp4",
        overlay="webcam.mp4",
        output="output.mp4",
    )

    # DCC-style documentary
    result = await create_documentary_composite(
        video="interview.mp4",
        transcript=[
            {"text": "This is the dream.", "start": 0.5, "end": 2.0},
            ...
        ],
        output="documentary.mp4",
    )

Quick Start - Real-time OBS:
    from kagami_studio.obs import connect_obs, OBSCompositor

    async with connect_obs() as obs:
        compositor = OBSCompositor(obs)
        await compositor.create_pip(
            main_source="GameCapture",
            pip_source="Webcam",
        )

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │              kagami_studio.compositing                      │
    │                                                             │
    │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
    │  │ Adaptive    │  │ Templates    │  │ Web Artifacts    │  │
    │  │ Masker      │  │ (DCC, PIP)   │  │ (HTML gen)       │  │
    │  │ (SAM2)      │  │              │  │                  │  │
    │  └──────┬──────┘  └──────┬───────┘  └────────┬─────────┘  │
    │         │                │                   │             │
    │         └────────────────┴───────────────────┘             │
    │                          │                                 │
    │              CompositeEngine (unified)                     │
    │                          │                                 │
    │         ┌────────────────┴────────────────┐                │
    │         │                                 │                │
    │         ▼                                 ▼                │
    │   Offline (FFmpeg)              Real-time (OBS)            │
    └─────────────────────────────────────────────────────────────┘

Version: 1.0.0
"""

from kagami_studio.compositing.chromakey import (
    ChromakeyConfig,
    apply_chromakey,
    detect_key_color,
)
from kagami_studio.compositing.engine import (
    CompositeConfig,
    CompositeEngine,
    CompositeResult,
    CompositeTemplate,
    DepthLayer,
)
from kagami_studio.compositing.masking import (
    AdaptiveMasker,
    FaceRegion,
    SegmentResult,
    create_mask_from_face,
    extract_subject,
)
from kagami_studio.compositing.templates import (
    DCCTemplate,
    InterviewTemplate,
    PIPTemplate,
    SplitTemplate,
    StreamingTemplate,
)
from kagami_studio.compositing.web_artifacts import (
    create_dcc_artifact,
    create_gallery_artifact,
    create_web_artifact,
)

__all__ = [
    # Masking
    "AdaptiveMasker",
    # Chromakey
    "ChromakeyConfig",
    "CompositeConfig",
    # Engine
    "CompositeEngine",
    "CompositeResult",
    "CompositeTemplate",
    # Templates
    "DCCTemplate",
    "DepthLayer",
    "FaceRegion",
    "InterviewTemplate",
    "PIPTemplate",
    "SegmentResult",
    "SplitTemplate",
    "StreamingTemplate",
    "apply_chromakey",
    "create_dcc_artifact",
    "create_gallery_artifact",
    "create_mask_from_face",
    # Web artifacts
    "create_web_artifact",
    "detect_key_color",
    "extract_subject",
]


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def create_pip_composite(
    background: str,
    overlay: str,
    output: str,
    corner: str = "bottom-right",
    overlay_scale: float = 0.3,
    glassmorphism: bool = True,
) -> CompositeResult:
    """Create picture-in-picture composite.

    Args:
        background: Background video path
        overlay: Overlay video path
        output: Output path
        corner: PIP corner position
        overlay_scale: Overlay size (0.0-1.0)
        glassmorphism: Add frosted glass effect

    Returns:
        CompositeResult with output path
    """
    engine = CompositeEngine()
    return await engine.composite(
        background=background,
        overlay=overlay,
        output=output,
        template=CompositeTemplate.PIP,
        template_config={
            "corner": corner,
            "scale": overlay_scale,
            "glassmorphism": glassmorphism,
        },
    )


async def create_documentary_composite(
    video: str,
    transcript: list[dict],
    output: str,
    style: str = "dcc",
) -> CompositeResult:
    """Create DCC-style documentary composite.

    Args:
        video: Video path
        transcript: Word-by-word transcript with timing
        output: Output path
        style: Visual style ('dcc', 'minimal', 'cinematic')

    Returns:
        CompositeResult with output path and web artifact
    """
    engine = CompositeEngine()
    return await engine.composite(
        background=video,
        output=output,
        template=CompositeTemplate.DOCUMENTARY,
        template_config={
            "transcript": transcript,
            "style": style,
        },
    )


async def create_chromakey_composite(
    background: str,
    greenscreen: str,
    output: str,
    key_color: str = "green",
    position: tuple[int, int] | None = None,
    scale: float = 1.0,
) -> CompositeResult:
    """Create chromakey (green screen) composite.

    Args:
        background: Background video
        greenscreen: Green screen video
        output: Output path
        key_color: 'green', 'blue', or hex color
        position: (x, y) position for overlay
        scale: Overlay scale

    Returns:
        CompositeResult
    """
    engine = CompositeEngine()
    return await engine.composite(
        background=background,
        overlay=greenscreen,
        output=output,
        template=CompositeTemplate.CHROMAKEY,
        template_config={
            "key_color": key_color,
            "position": position,
            "scale": scale,
        },
    )


async def create_split_composite(
    left_video: str,
    right_video: str,
    output: str,
    split_ratio: float = 0.5,
    direction: str = "vertical",
) -> CompositeResult:
    """Create split-screen composite.

    Args:
        left_video: Left/top video
        right_video: Right/bottom video
        output: Output path
        split_ratio: Split position (0.5 = center)
        direction: 'vertical' (side-by-side) or 'horizontal' (top/bottom)

    Returns:
        CompositeResult
    """
    engine = CompositeEngine()
    return await engine.composite(
        background=left_video,
        overlay=right_video,
        output=output,
        template=CompositeTemplate.SPLIT,
        template_config={
            "ratio": split_ratio,
            "direction": direction,
        },
    )
