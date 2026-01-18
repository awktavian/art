"""Subtitle Generation — Kinetic and static subtitle rendering.

Provides:
- ASS subtitle generation with word-by-word animations (DCC-style)
- Emotion-based word styling (power, heart, wisdom, energy)
- Multi-language support
- FFmpeg burn-in integration
"""

from kagami_studio.subtitles.kinetic import (
    EmotionStyle,
    KineticSubtitleGenerator,
    WordTiming,
)

__all__ = [
    "EmotionStyle",
    "KineticSubtitleGenerator",
    "WordTiming",
]
