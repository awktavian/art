"""kagami.present — One function. Maximum impact.

The simplest way to create AI-native video presentations.

Usage:
    from kagami import present

    # Simple
    video = await present("Kagami Hub")

    # With options
    video = await present(
        topic="Kagami Hub",
        style="announcement",
        character="lamp",
        mood="warm",
        duration="medium",
    )

    print(f"Video: {video.video_path}")
    print(f"Duration: {video.duration_s}s")
    print(f"Text overlays: {video.text_overlays_count}")
    print(f"Transitions: {video.transitions_count}")

Features:
    - Kinetic typography synced to word timings
    - Scene transitions (fade, dissolve, zoom, wipe)
    - Style presets (warm, professional, playful, dramatic)
    - Avatar integration (HeyGen)
    - Spatial audio (ElevenLabs V3)
"""

from kagami.present.engine import (
    Beat,
    CharacterType,
    Mood,
    # Engine (for advanced use)
    PresentationEngine,
    PresentationResult,
    # Types
    PresentationStyle,
    Script,
    # Main API
    present,
)

__all__ = [
    "Beat",
    "CharacterType",
    "Mood",
    # Engine
    "PresentationEngine",
    "PresentationResult",
    # Types
    "PresentationStyle",
    "Script",
    # Main
    "present",
]
