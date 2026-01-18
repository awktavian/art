"""ElevenLabs v3 Expressive Audio Tags — Emotional Speech Synthesis.

Provides structured access to ElevenLabs v3's text-based audio tags for
creating expressive, emotionally rich speech. These tags transform neutral
text into natural human expression with emotions, singing, pauses, and more.

Usage:
    from kagami.core.services.voice.expressive_tags import (
        Tag, emotion, whisper, pause, sing, laugh,
        build_expressive_text, Emotion, SpeechStyle
    )

    # Simple tags
    text = f"{emotion(Emotion.EXCITED)}That's amazing!{Tag.END}"
    text = f"{whisper()}This is a secret..."
    text = f"Hold on{pause('short')}let me think"

    # Singing
    text = f"{sing()}Happy birthday to you..."

    # Builder pattern for complex expressions
    text = build_expressive_text([
        ("excited", "Welcome to the BBC Symphony Orchestra showcase!"),
        ("pause", None),
        ("whisper", "Let me introduce you to something special..."),
        ("normal", "The first instrument is the violin."),
    ])

Reference: ElevenLabs v3 Audio Tags (January 2026)

Created: January 1, 2026
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class Emotion(str, Enum):
    """Emotional states supported by ElevenLabs v3."""

    # Positive
    HAPPY = "happy"
    EXCITED = "excited"
    CHEERFUL = "cheerfully"
    PLAYFUL = "playfully"

    # Negative
    SAD = "sad"
    ANGRY = "angry"
    NERVOUS = "nervous"

    # Curious/Thoughtful
    CURIOUS = "curious"
    MISCHIEVOUS = "mischievously"

    # Neutral/Subdued
    RESIGNED = "resigned tone"
    FLAT = "flatly"
    DEADPAN = "deadpan"


class SpeechStyle(str, Enum):
    """Speech style modifiers for v3."""

    WHISPER = "whispers"
    LAUGH = "laughs"
    GASP = "gasps"
    SIGH = "sighs"
    HESITATE = "hesitates"
    STAMMER = "stammers"


class PauseLength(str, Enum):
    """Pause duration options."""

    SHORT = "short pause"
    NORMAL = "pause"
    LONG = "long pause"


class Tag:
    """Raw tag strings for direct insertion."""

    # Singing
    SING = "[sings]"

    # Emotions
    HAPPY = "[happy]"
    SAD = "[sad]"
    EXCITED = "[excited]"
    ANGRY = "[angry]"
    NERVOUS = "[nervous]"
    CURIOUS = "[curious]"
    CHEERFUL = "[cheerfully]"
    PLAYFUL = "[playfully]"
    MISCHIEVOUS = "[mischievously]"
    RESIGNED = "[resigned tone]"
    FLAT = "[flatly]"
    DEADPAN = "[deadpan]"

    # Speech modifiers
    WHISPER = "[whispers]"
    LAUGH = "[laughs]"
    GASP = "[gasps]"
    SIGH = "[sighs]"
    HESITATE = "[hesitates]"
    STAMMER = "[stammers]"

    # Pauses
    PAUSE = "[pause]"
    SHORT_PAUSE = "[short pause]"
    LONG_PAUSE = "[long pause]"

    # No explicit end tag needed - effects apply to following text
    END = ""


def emotion(e: Emotion | str) -> str:
    """Create an emotion tag.

    Args:
        e: Emotion enum or string

    Returns:
        Formatted emotion tag

    Example:
        >>> emotion(Emotion.EXCITED) + "This is amazing!"
        '[excited]This is amazing!'
    """
    if isinstance(e, Emotion):
        e = e.value
    return f"[{e}]"


def whisper(text: str | None = None) -> str:
    """Create whispered speech.

    Args:
        text: Optional text to whisper (tag only if None)

    Returns:
        Whisper tag with optional text

    Example:
        >>> whisper("This is a secret")
        '[whispers] This is a secret'
    """
    if text:
        return f"[whispers] {text}"
    return "[whispers]"


def pause(length: Literal["short", "normal", "long"] = "normal") -> str:
    """Insert a pause.

    Args:
        length: Pause duration

    Returns:
        Pause tag

    Example:
        >>> f"Wait{pause('short')}okay"
        'Wait[short pause]okay'
    """
    if length == "short":
        return "[short pause]"
    elif length == "long":
        return "[long pause]"
    return "[pause]"


def sing(text: str | None = None) -> str:
    """Create singing speech.

    Args:
        text: Optional text to sing

    Returns:
        Singing tag with optional text

    Example:
        >>> sing("Happy birthday to you")
        '[sings] Happy birthday to you'
    """
    if text:
        return f"[sings] {text}"
    return "[sings]"


def laugh(text: str | None = None) -> str:
    """Add laughter.

    Args:
        text: Optional text after laugh

    Returns:
        Laugh tag with optional text
    """
    if text:
        return f"[laughs] {text}"
    return "[laughs]"


def sigh(text: str | None = None) -> str:
    """Add a sigh.

    Args:
        text: Optional text after sigh

    Returns:
        Sigh tag with optional text
    """
    if text:
        return f"[sighs] {text}"
    return "[sighs]"


def gasp(text: str | None = None) -> str:
    """Add a gasp.

    Args:
        text: Optional text after gasp

    Returns:
        Gasp tag with optional text
    """
    if text:
        return f"[gasps] {text}"
    return "[gasps]"


def hesitate(text: str | None = None) -> str:
    """Add hesitation.

    Args:
        text: Optional text after hesitation

    Returns:
        Hesitation tag
    """
    if text:
        return f"[hesitates] {text}"
    return "[hesitates]"


@dataclass(frozen=True)
class ExpressiveSegment:
    """A segment of expressive text with style annotation."""

    style: str  # emotion name, "whisper", "pause", "sing", "normal"
    text: str | None

    def render(self) -> str:
        """Render segment to tagged text."""
        if self.style == "normal":
            return self.text or ""
        elif self.style == "whisper":
            return whisper(self.text)
        elif self.style == "pause":
            return pause("normal")
        elif self.style == "short_pause":
            return pause("short")
        elif self.style == "long_pause":
            return pause("long")
        elif self.style == "sing":
            return sing(self.text)
        elif self.style == "laugh":
            return laugh(self.text)
        elif self.style == "sigh":
            return sigh(self.text)
        elif self.style == "gasp":
            return gasp(self.text)
        elif self.style == "hesitate":
            return hesitate(self.text)
        else:
            # Assume it's an emotion
            return f"{emotion(self.style)}{self.text or ''}"


def build_expressive_text(segments: list[tuple[str, str | None]]) -> str:
    """Build expressive text from a list of (style, text) segments.

    Args:
        segments: List of (style, text) tuples. Style can be:
            - Emotion name: "excited", "happy", "sad", etc.
            - Speech modifier: "whisper", "laugh", "sigh", etc.
            - Pause: "pause", "short_pause", "long_pause"
            - Singing: "sing"
            - Normal: "normal" (no tags)

    Returns:
        Complete expressive text string

    Example:
        >>> build_expressive_text([
        ...     ("excited", "Welcome!"),
        ...     ("pause", None),
        ...     ("whisper", "Listen carefully..."),
        ...     ("normal", "The concert begins."),
        ... ])
        '[excited]Welcome! [pause] [whispers] Listen carefully... The concert begins.'
    """
    parts = []
    for style, text in segments:
        segment = ExpressiveSegment(style, text)
        rendered = segment.render()
        if rendered:
            parts.append(rendered)
    return " ".join(parts)


# =============================================================================
# Instrument Narrations — One line. Let the music speak.
# =============================================================================

# Short, memorable narrations with one v3 tag each
INSTRUMENT_NARRATIONS: dict[str, str] = {
    # STRINGS
    "violins_1": "[whispers] The storyteller. [pause] Scheherazade.",
    "violins_2": "[curious] The harmony no one notices until it's gone.",
    "violas": "[playfully] Everyone's favorite punchline. [pause] And secretly, the soul.",
    "celli": "[sighs] Dvořák, homesick, in love. [pause] You'll hear it.",
    "basses": "[curious] Beethoven made them speak. [pause] Listen.",
    # WOODWINDS - Solo
    "flute": "[whispers] Debussy's faun, half-dreaming in summer heat.",
    "oboe": "[curious] The whole orchestra tunes to this. [pause] It can't adjust.",
    "clarinet": "[sighs] Rachmaninoff wrote this in therapy. [pause] It worked.",
    "bassoon": "[excited] This note started a riot. Paris, 1913.",
    "piccolo": "[laughs] The smallest instrument. Somehow the loudest.",
    "cor_anglais": "[whispers] The saddest sound in the orchestra. [pause] Dvořák, missing home.",
    "bass_clarinet": "[whispers] Villain music. [pause] Every film composer's secret weapon.",
    "contrabassoon": "[curious] So low you feel it more than hear it.",
    # WOODWINDS - Ensemble
    "flutes_a3": "[whispers] Three flutes. Like sunlight on water.",
    "oboes_a3": "[playfully] Pastoral. Very 'thinking in a meadow.'",
    "clarinets_a3": "[curious] Warmth without brass. [pause] Comfort food.",
    "bassoons_a3": "[whispers] Storm clouds gathering.",
    # BRASS - Solo
    "horn": "[excited] The hardest brass instrument. [pause] And the most beautiful.",
    "trumpet": "[whispers] Mahler's fate knocking. [pause] Three notes you never forget.",
    "tenor_trombone": "[curious] The trombone being romantic. [pause] Ravel knew.",
    "tuba": "[playfully] The ox-cart. Heavy, slow, unstoppable.",
    "cimbasso": "[whispers] Hans Zimmer's secret. [pause] Impending doom.",
    "contrabass_trombone": "[curious] When you need the floor to vibrate.",
    "contrabass_tuba": "[laughs] Because the regular tuba wasn't big enough.",
    # BRASS - Ensemble
    "horns_a4": "[excited] Four horns in unison. [pause] Sunrise.",
    "trumpets_a2": "[playfully] Royal decree energy.",
    "tenor_trombones_a3": "[excited] The musical equivalent of an avalanche.",
    "bass_trombones_a2": "[whispers] The reason you feel it in your chest.",
    # PERCUSSION
    "timpani": "[excited] The thunder. [pause] Beethoven's heartbeat.",
    "harp": "[whispers] Forty-seven strings. Starlight made audible.",
    "celeste": "[curious] Tchaikovsky kept this secret until opening night.",
    "glockenspiel": "[playfully] Magic bells. [pause] Mozart's.",
    "xylophone": "[whispers] Skeletons dancing. [pause] Saint-Saëns.",
    "marimba": "[curious] Four mallets. Sometimes six. [pause] Watch the hands.",
    "vibraphone": "[playfully] The jazziest instrument in the orchestra.",
    "crotales": "[whispers] Ancient. Otherworldly. [pause] The sound lingers.",
    "tubular_bells": "[curious] Church bells. [pause] Something primal responds.",
    "untuned_percussion": "[laughs] Beautiful chaos.",
}


def get_instrument_narration(instrument_key: str) -> str:
    """Get the narration for an instrument. One line, one thought."""
    return INSTRUMENT_NARRATIONS.get(
        instrument_key, f"[pause] The {instrument_key.replace('_', ' ')}."
    )


def generate_showcase_intro() -> str:
    """Short intro. Let the music speak."""
    return "[whispers] Eighty people. One breath. [pause] Let me show you."


def generate_section_intro(section: str) -> str:
    """One line per section."""
    intros = {
        "strings": "[pause] The strings. [short pause] Two-thirds of the orchestra.",
        "woodwinds": "[pause] Woodwinds. [short pause] Breath made music.",
        "brass": "[excited] The brass. [pause] Goosebumps territory.",
        "percussion": "[pause] Percussion. [short pause] Organized chaos.",
    }
    return intros.get(section, f"[pause] The {section}.")


def generate_showcase_finale() -> str:
    """Short outro."""
    return "[long pause] [sighs] Thirty-eight voices. [pause] The BBC Symphony Orchestra."


__all__ = [
    # Orchestral narrations
    "INSTRUMENT_NARRATIONS",
    "Emotion",
    # Builder
    "ExpressiveSegment",
    "PauseLength",
    "SpeechStyle",
    # Core tags
    "Tag",
    "build_expressive_text",
    # Tag functions
    "emotion",
    "gasp",
    "generate_section_intro",
    "generate_showcase_finale",
    "generate_showcase_intro",
    "get_instrument_narration",
    "hesitate",
    "laugh",
    "pause",
    "sigh",
    "sing",
    "whisper",
]
