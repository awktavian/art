"""Shared data models for video production pipeline.

This module contains the core dataclasses used across the production system.

Usage:
    from kagami_studio.production.models import SlideContent, Presentation

    slide = SlideContent(
        title="The Science of Farts",
        spoken_text="Ever wondered what's really going on...",
        layout="hero_full",
        image_prompt="Playful cartoon clouds...",
    )

    presentation = Presentation(
        title="The Science of Farts",
        topic="farts",
        tone="educational_funny",
        slides=[slide],
    )

Created: 2026-01-09
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PresentationTone(str, Enum):
    """Tone presets for generated presentations."""

    EDUCATIONAL = "educational"  # Clear, informative, professional
    EDUCATIONAL_FUNNY = "educational_funny"  # Informative with humor (TED meets comedy)
    ENTERTAINING = "entertaining"  # Fun, engaging, light
    PROFESSIONAL = "professional"  # Corporate, serious
    INSPIRATIONAL = "inspirational"  # Motivational, uplifting
    STORYTELLING = "storytelling"  # Narrative arc, emotional
    SCIENTIFIC = "scientific"  # Data-driven, technical


# Color palettes by tone
COLOR_PALETTES: dict[PresentationTone, dict[str, str]] = {
    PresentationTone.EDUCATIONAL_FUNNY: {
        "primary": "#00f0ff",
        "secondary": "#ffd700",
        "background": "#0d1117",
        "text": "#ffffff",
    },
    PresentationTone.PROFESSIONAL: {
        "primary": "#4a9eff",
        "secondary": "#ffffff",
        "background": "#1a1a2e",
        "text": "#f4f1ea",
    },
    PresentationTone.SCIENTIFIC: {
        "primary": "#00ff88",
        "secondary": "#4a9eff",
        "background": "#0a0f1a",
        "text": "#ffffff",
    },
    PresentationTone.INSPIRATIONAL: {
        "primary": "#ffd700",
        "secondary": "#ff6b6b",
        "background": "#1a1a2e",
        "text": "#ffffff",
    },
    PresentationTone.STORYTELLING: {
        "primary": "#ff9f43",
        "secondary": "#ee5a24",
        "background": "#0d1117",
        "text": "#f4f1ea",
    },
}


@dataclass
class SlideContent:
    """Content for a single presentation slide.

    Attributes:
        title: Short title (max 6 words for TED-style)
        spoken_text: Full narration for TTS
        layout: Visual layout type (hero_full, stat_focus, etc.)
        display_text: Text shown on slide (if different from title)
        image_prompt: AI image generation prompt (for hero layouts)
        stat_value: For STAT_FOCUS layout (e.g., "14x")
        stat_label: For STAT_FOCUS layout (e.g., "times per day")
        quote_text: For QUOTE layout
        quote_author: For QUOTE layout
        icon_items: For ICON_GRID layout [{"icon": "🔬", "label": "Science"}]
        recap_points: For RECAP layout ["Point 1", "Point 2"]
        background_color: Slide background hex color
        accent_color: Accent color hex
    """

    title: str
    spoken_text: str
    layout: str  # SlideLayoutType value
    display_text: str | None = None
    image_prompt: str | None = None
    stat_value: str | None = None
    stat_label: str | None = None
    quote_text: str | None = None
    quote_author: str | None = None
    icon_items: list[dict[str, str]] | None = None
    recap_points: list[str] | None = None
    background_color: str = "#0d1117"
    accent_color: str = "#00f0ff"

    def needs_image(self) -> bool:
        """Check if this slide's layout requires a hero image."""
        return self.layout in ("hero_full", "hero_split", "hero_left", "hero_right")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "spoken_text": self.spoken_text,
            "layout": self.layout,
            "display_text": self.display_text,
            "image_prompt": self.image_prompt,
            "stat_value": self.stat_value,
            "stat_label": self.stat_label,
            "quote_text": self.quote_text,
            "quote_author": self.quote_author,
            "icon_items": self.icon_items,
            "recap_points": self.recap_points,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlideContent:
        """Create from dictionary."""
        return cls(
            title=data.get("title", ""),
            spoken_text=data.get("spoken_text", data.get("spoken", "")),
            layout=data.get("layout", "hero_split"),
            display_text=data.get("display_text"),
            image_prompt=data.get("image_prompt"),
            stat_value=data.get("stat_value"),
            stat_label=data.get("stat_label"),
            quote_text=data.get("quote_text"),
            quote_author=data.get("quote_author"),
            icon_items=data.get("icon_items"),
            recap_points=data.get("recap_points"),
            background_color=data.get("background_color", "#0d1117"),
            accent_color=data.get("accent_color", "#00f0ff"),
        )


@dataclass
class Presentation:
    """A complete presentation with metadata and slides.

    Attributes:
        title: Presentation title
        topic: Original topic/subject
        tone: Presentation tone preset
        slides: List of slide content
        target_duration_seconds: Target video length
        speaker: Speaker identity for TTS
    """

    title: str
    topic: str
    tone: PresentationTone
    slides: list[SlideContent] = field(default_factory=list)
    target_duration_seconds: int = 90
    speaker: str = "tim"

    def get_colors(self) -> dict[str, str]:
        """Get color palette for this presentation's tone."""
        return COLOR_PALETTES.get(self.tone, COLOR_PALETTES[PresentationTone.EDUCATIONAL_FUNNY])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "topic": self.topic,
            "tone": self.tone.value,
            "slides": [s.to_dict() for s in self.slides],
            "target_duration_seconds": self.target_duration_seconds,
            "speaker": self.speaker,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Presentation:
        """Create from dictionary."""
        tone_str = data.get("tone", "educational_funny")
        try:
            tone = PresentationTone(tone_str)
        except ValueError:
            tone = PresentationTone.EDUCATIONAL_FUNNY

        slides = [
            SlideContent.from_dict(s) if isinstance(s, dict) else s for s in data.get("slides", [])
        ]

        return cls(
            title=data.get("title", ""),
            topic=data.get("topic", ""),
            tone=tone,
            slides=slides,
            target_duration_seconds=data.get("target_duration_seconds", 90),
            speaker=data.get("speaker", "tim"),
        )


@dataclass
class SlideTiming:
    """Timing information for a single slide.

    Derived from TTS word timings (the ground truth).
    """

    index: int
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        """Duration in milliseconds."""
        return self.end_ms - self.start_ms

    @property
    def duration_s(self) -> float:
        """Duration in seconds."""
        return self.duration_ms / 1000

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "index": self.index,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_s": self.duration_s,
        }


@dataclass
class WordTiming:
    """Timing for a single word from TTS.

    This is the ground truth for all synchronization.
    """

    text: str
    start_ms: int
    end_ms: int
    slide_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "slide": self.slide_index,
        }


__all__ = [
    "COLOR_PALETTES",
    "Presentation",
    "PresentationTone",
    "SlideContent",
    "SlideTiming",
    "WordTiming",
]
