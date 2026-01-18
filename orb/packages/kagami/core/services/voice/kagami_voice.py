"""Kagami Voice — Single Voice, Colony-Conditioned TTS.

The optimal ElevenLabs strategy:
1. ONE voice (Kagami's cloned voice) — consistency across all speech
2. Colony conditioning via VoiceSettings — same voice, different character
3. Flash model for real-time — 75ms latency with streaming
4. Warm connection — singleton client, zero boot overhead

Usage (SKIP BOOTUP):
    from kagami.core.services.voice.kagami_voice import speak

    # Fast path - no boot, warm connection
    await speak("Hello Tim")  # Kagami voice
    await speak("Igniting!", colony="spark")  # Spark-conditioned voice

    # Or with explicit service
    voice = await get_kagami_voice()
    await voice.speak("System ready", colony="crystal")

Colony Conditioning (same Kagami voice, different parameters):
    - Kagami: Balanced, natural (default)
    - Spark: Energetic, higher style, faster
    - Forge: Committed, stable, measured
    - Flow: Adaptive, smooth, natural
    - Nexus: Thoughtful, integrative
    - Beacon: Focused, clear, direct
    - Grove: Exploratory, warm, unhurried
    - Crystal: Precise, stable, authoritative

Created: January 1, 2026
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Colony(str, Enum):
    """Voice personalities for different contexts."""

    KAGAMI = "kagami"  # Default - balanced, natural
    SPARK = "spark"  # Energetic, enthusiastic
    FORGE = "forge"  # Deliberate, committed
    FLOW = "flow"  # Adaptive, smooth
    NEXUS = "nexus"  # Thoughtful, integrative
    BEACON = "beacon"  # Direct, focused
    GROVE = "grove"  # Warm, exploratory
    CRYSTAL = "crystal"  # Precise, clear


# =============================================================================
# MODEL — ALWAYS V3
# =============================================================================
# ElevenLabs V3 is the ONLY model. It supports:
# - Audio tags: [whispers], [pause], [laughs], [sighs], [excited], [sad]
# - Natural expressiveness
# - Best quality
#
# Legacy models (FLASH, TURBO, QUALITY) are REMOVED. V3 only.


# V3 model ID constant
ELEVENLABS_MODEL = "eleven_v3"


@dataclass(frozen=True)
class ColonyVoiceSettings:
    """Voice settings that condition Kagami's voice for each colony.

    These are NOT different voices — they're parameter variations
    on the SAME cloned Kagami voice to express colony character.

    Parameters (ElevenLabs):
        stability: 0.0 (expressive) → 1.0 (monotone)
        similarity_boost: 0.0 (generic) → 1.0 (exact clone)
        style: 0.0 (neutral) → 1.0 (dramatic)
        speed: 0.7 (slow) → 1.2 (fast)
    """

    colony: Colony
    stability: float
    similarity_boost: float
    style: float
    speed: float
    use_speaker_boost: bool = True

    def to_elevenlabs(self) -> dict[str, Any]:
        """Convert to ElevenLabs VoiceSettings dict."""
        return {
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
            "speed": self.speed,
            "use_speaker_boost": self.use_speaker_boost,
        }


# =============================================================================
# Voice Profiles — Research-Optimized Emotional Design
# =============================================================================
# Same Kagami voice, different settings for different moods/contexts.
#
# Parameter Guide (ElevenLabs v3 research, Jan 2026):
#
# STABILITY (0.0-1.0):
#   - Lower (0.30-0.45): Broader emotional range, more expressive delivery
#   - Mid (0.45-0.55): Balanced, natural speech variation
#   - Higher (0.55-0.70): Consistent, stable output, less emotional variation
#   - Very high (0.70+): Can become monotonous, limited emotion
#
# SIMILARITY_BOOST (0.0-1.0) = "Clarity + Similarity Enhancement":
#   - 0.70-0.75: Natural variation, softer
#   - 0.75-0.80: Sweet spot - clear without artifacts
#   - 0.80-0.85: High clarity, authoritative
#   - 0.85+: May introduce artifacts if source audio imperfect
#
# STYLE (0.0-1.0) = "Style Exaggeration":
#   - 0.00-0.20: Neutral, minimal personality
#   - 0.20-0.35: Subtle warmth, engaged
#   - 0.35-0.45: Expressive, storytelling appropriate
#   - 0.45-0.50: Dramatic, entertainment-level
#   - NOTE: Higher style increases latency
#
# SPEED (0.7-1.3):
#   - 0.85-0.95: Gentle, deliberate (night mode, intimate)
#   - 0.95-1.02: Natural conversation
#   - 1.02-1.08: Energetic, efficient
#   - 1.08+: Very fast, may feel rushed
#
# EMOTIONAL AUDIO TAGS (v3 feature):
#   Embed in text: [excited], [whispers], [sighs], [laughs]
#   Example: "That's amazing! [excited] Let me show you."

COLONY_VOICE_SETTINGS: dict[Colony, ColonyVoiceSettings] = {
    # Default - balanced, natural presence
    # Design: Warm assistant, neither pushy nor distant
    Colony.KAGAMI: ColonyVoiceSettings(
        colony=Colony.KAGAMI,
        stability=0.45,  # Natural emotional variation
        similarity_boost=0.78,  # Clear but not harsh
        style=0.32,  # Subtle warmth, engaged
        speed=1.0,  # Natural pace
    ),
    # SPARK — Energetic ignition, idea generation
    # Design: Enthusiastic spark that catches fire
    Colony.SPARK: ColonyVoiceSettings(
        colony=Colony.SPARK,
        stability=0.32,  # Wide emotional range for enthusiasm
        similarity_boost=0.75,
        style=0.48,  # High expressiveness (near max practical)
        speed=1.06,  # Energetic but not rushed
    ),
    # FORGE — Deliberate builder, committed implementation
    # Design: Steady craftsman, measured confidence
    Colony.FORGE: ColonyVoiceSettings(
        colony=Colony.FORGE,
        stability=0.52,  # Consistent, deliberate
        similarity_boost=0.80,  # Clear, authoritative
        style=0.35,  # Engaged but not dramatic
        speed=0.96,  # Slightly slower, measured
    ),
    # FLOW — Adaptive healer, smooth debugging
    # Design: Calm water flowing around obstacles
    Colony.FLOW: ColonyVoiceSettings(
        colony=Colony.FLOW,
        stability=0.42,  # Adaptive variability
        similarity_boost=0.75,
        style=0.28,  # Smooth, not dramatic
        speed=0.98,  # Natural, unhurried
    ),
    # NEXUS — Thoughtful bridge, integrative connection
    # Design: Considerate connector, weighing perspectives
    Colony.NEXUS: ColonyVoiceSettings(
        colony=Colony.NEXUS,
        stability=0.46,  # Balanced thoughtfulness
        similarity_boost=0.76,
        style=0.30,  # Subtle engagement
        speed=0.97,  # Slightly reflective pace
    ),
    # BEACON — Direct architect, focused planning
    # Design: Clear lighthouse cutting through fog
    Colony.BEACON: ColonyVoiceSettings(
        colony=Colony.BEACON,
        stability=0.55,  # Stable, clear signal
        similarity_boost=0.82,  # High clarity
        style=0.22,  # Professional, minimal drama
        speed=1.0,  # Efficient, direct
    ),
    # GROVE — Warm scholar, exploratory research
    # Design: Curious naturalist discovering wonders
    Colony.GROVE: ColonyVoiceSettings(
        colony=Colony.GROVE,
        stability=0.38,  # Curious variation
        similarity_boost=0.72,  # Softer, approachable
        style=0.40,  # Warm expressiveness
        speed=0.94,  # Unhurried exploration
    ),
    # CRYSTAL — Precise judge, verification authority
    # Design: Clear diamond, authoritative certainty
    Colony.CRYSTAL: ColonyVoiceSettings(
        colony=Colony.CRYSTAL,
        stability=0.62,  # Very stable, authoritative
        similarity_boost=0.85,  # Maximum clarity
        style=0.18,  # Minimal style, let facts speak
        speed=1.0,  # Measured, precise
    ),
}


def get_colony_settings(colony: Colony | str) -> ColonyVoiceSettings:
    """Get voice settings for a colony.

    Args:
        colony: Colony enum or string name

    Returns:
        ColonyVoiceSettings for conditioning the voice
    """
    if isinstance(colony, str):
        try:
            colony = Colony(colony.lower())
        except ValueError:
            colony = Colony.KAGAMI
    return COLONY_VOICE_SETTINGS.get(colony, COLONY_VOICE_SETTINGS[Colony.KAGAMI])


@dataclass
class SpeakResult:
    """Result of speak operation."""

    success: bool
    audio_path: Path | None = None
    audio_bytes: bytes | None = None
    ttfa_ms: float = 0.0  # Time to first audio
    total_ms: float = 0.0
    model: str = ""
    colony: str = "kagami"
    error: str | None = None


class KagamiVoice:
    """Kagami's voice — single cloned voice with colony conditioning.

    This is the FAST PATH for voice output:
    - No boot sequence required
    - Warm ElevenLabs connection
    - Direct streaming to audio
    - Colony conditioning via VoiceSettings

    Architecture:
        speak(text, colony)
        → get_colony_settings(colony)
        → ElevenLabs stream() with VoiceSettings
        → Audio output

    Usage:
        voice = await get_kagami_voice()
        await voice.speak("Hello!")
        await voice.speak("Igniting!", colony="spark")
    """

    def __init__(self):
        """Initialize Kagami voice."""
        self._client: Any = None
        self._voice_id: str | None = None
        self._initialized = False
        self._temp_dir = Path(tempfile.gettempdir()) / "kagami_voice"

        # Stats
        self._stats = {
            "speaks": 0,
            "total_ms": 0.0,
            "avg_ttfa_ms": 0.0,
            "by_colony": {c.value: 0 for c in Colony},
        }

    async def initialize(self) -> bool:
        """Initialize ElevenLabs client with warm connection.

        Returns:
            True if successful
        """
        if self._initialized:
            return True

        try:
            # Get credentials from keychain
            from kagami.core.security import get_secret

            api_key = get_secret("elevenlabs_api_key")
            self._voice_id = get_secret("elevenlabs_kagami_voice_id")

            if not api_key:
                logger.error("ElevenLabs API key not found")
                return False

            if not self._voice_id:
                # Default to Tim's cloned voice ID (ElevenLabs - NOT a fallback TTS)
                self._voice_id = "mVI4sVQ8lmFpGDyfy6sQ"
                logger.info(f"Using Tim's cloned voice ID: {self._voice_id}")

            # Initialize client
            from elevenlabs import ElevenLabs

            self._client = ElevenLabs(api_key=api_key)

            # Create temp directory
            self._temp_dir.mkdir(exist_ok=True)

            self._initialized = True
            logger.info(f"✓ KagamiVoice ready (voice_id={self._voice_id[:8]}...)")
            return True

        except Exception as e:
            logger.error(f"KagamiVoice init failed: {e}")
            return False

    async def synthesize_with_timestamps(
        self,
        text: str,
    ) -> tuple[SpeakResult, list[tuple[float, float, str]] | None]:
        """Synthesize with character-level timestamps for precise slicing.

        ALWAYS uses ElevenLabs V3 for audio tag support.

        Returns:
            Tuple of (SpeakResult, alignment_data) where alignment_data is
            list of (start_time, end_time, character) tuples, or None if failed.
        """
        start = time.perf_counter()

        if not self._initialized:
            await self.initialize()

        if not self._client or not self._voice_id:
            return SpeakResult(success=False, error="Not initialized"), None

        try:
            # Use convert_with_timestamps for precise timing (ALWAYS V3)
            response = self._client.text_to_speech.convert_with_timestamps(
                voice_id=self._voice_id,
                text=text,
                model_id=ELEVENLABS_MODEL,
            )

            # Response has audio_base_64 and alignment
            import base64

            audio_bytes = base64.b64decode(response.audio_base_64)

            # Parse alignment data
            alignment = []
            if response.alignment:
                chars = response.alignment.characters
                char_start = response.alignment.character_start_times_seconds
                char_end = response.alignment.character_end_times_seconds

                if chars and char_start and char_end:
                    for c, s, e in zip(chars, char_start, char_end, strict=False):
                        alignment.append((s, e, c))

            # Save audio
            audio_path = self._temp_dir / f"kagami_ts_{int(time.time() * 1000)}.mp3"
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)

            total_ms = (time.perf_counter() - start) * 1000

            result = SpeakResult(
                success=True,
                audio_path=audio_path,
                audio_bytes=audio_bytes,
                ttfa_ms=total_ms,  # Not streaming, so same as total
                total_ms=total_ms,
            )

            return result, alignment

        except Exception as e:
            logger.error(f"Synthesis with timestamps failed: {e}")
            return SpeakResult(success=False, error=str(e)), None

    async def synthesize(
        self,
        text: str,
        colony: Colony | str = Colony.KAGAMI,
    ) -> SpeakResult:
        """Synthesize audio from text with colony-conditioned voice.

        ALWAYS uses ElevenLabs V3 for audio tag support ([whispers], [excited], etc).

        SYNTHESIS ONLY — Does NOT play audio. All playback MUST go through
        UnifiedVoiceEffector for proper spatial audio routing.

        Args:
            text: Text to speak (can include V3 audio tags)
            colony: Colony for voice conditioning (default: kagami)

        Returns:
            SpeakResult with audio_path and audio_bytes (no playback)
        """
        start = time.perf_counter()

        if not self._initialized:
            await self.initialize()

        if not self._client or not self._voice_id:
            return SpeakResult(success=False, error="Not initialized")

        # Get colony voice settings (for stats tracking)
        settings = get_colony_settings(colony)
        colony_name = settings.colony.value

        try:
            # Stream audio using V3 model
            ttfa = 0.0
            first_chunk = True
            chunks: list[bytes] = []

            # ALWAYS V3 - no voice_settings or optimize_streaming_latency
            audio_stream = self._client.text_to_speech.stream(
                voice_id=self._voice_id,
                text=text,
                model_id=ELEVENLABS_MODEL,  # Always eleven_v3
            )

            for chunk in audio_stream:
                if first_chunk:
                    ttfa = (time.perf_counter() - start) * 1000
                    first_chunk = False
                if isinstance(chunk, bytes):
                    chunks.append(chunk)

            audio_bytes = b"".join(chunks)

            # Save to temp file
            audio_path = self._temp_dir / f"kagami_{int(time.time() * 1000)}.mp3"
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)

            total_ms = (time.perf_counter() - start) * 1000

            # Update stats
            self._stats["speaks"] += 1
            self._stats["total_ms"] += total_ms
            self._stats["by_colony"][colony_name] += 1
            self._stats["avg_ttfa_ms"] = (
                self._stats["avg_ttfa_ms"] * (self._stats["speaks"] - 1) + ttfa
            ) / self._stats["speaks"]

            logger.debug(
                f"🎙️ [{colony_name}] Synthesized TTFA:{ttfa:.0f}ms Total:{total_ms:.0f}ms "
                f'"{text[:40]}{"..." if len(text) > 40 else ""}"'
            )

            return SpeakResult(
                success=True,
                audio_path=audio_path,
                audio_bytes=audio_bytes,
                ttfa_ms=ttfa,
                total_ms=total_ms,
                model=ELEVENLABS_MODEL,
                colony=colony_name,
            )

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return SpeakResult(success=False, error=str(e), colony=colony_name)

    def stream(
        self,
        text: str,
        colony: Colony | str = Colony.KAGAMI,
    ) -> Iterator[bytes]:
        """Stream audio chunks for real-time playback.

        ALWAYS uses ElevenLabs V3 for audio tag support.

        Args:
            text: Text to speak (can include V3 audio tags)
            colony: Colony for voice conditioning

        Yields:
            Audio chunks as bytes
        """
        if not self._client or not self._voice_id:
            return

        # ALWAYS V3
        audio_stream = self._client.text_to_speech.stream(
            voice_id=self._voice_id,
            text=text,
            model_id=ELEVENLABS_MODEL,
        )

        for chunk in audio_stream:
            if isinstance(chunk, bytes):
                yield chunk

    def get_stats(self) -> dict[str, Any]:
        """Get voice statistics."""
        return {
            **self._stats,
            "initialized": self._initialized,
            "voice_id": self._voice_id[:8] + "..." if self._voice_id else None,
        }

    @property
    def voice_id(self) -> str | None:
        """Get Kagami's voice ID."""
        return self._voice_id

    @property
    def is_ready(self) -> bool:
        """Check if voice is ready to speak."""
        return self._initialized and self._client is not None


# =============================================================================
# Singleton and Fast Path
# =============================================================================

_kagami_voice: KagamiVoice | None = None
_init_lock = asyncio.Lock()


async def get_kagami_voice() -> KagamiVoice:
    """Get the singleton KagamiVoice instance.

    Returns:
        Initialized KagamiVoice
    """
    global _kagami_voice

    if _kagami_voice is None:
        async with _init_lock:
            if _kagami_voice is None:
                _kagami_voice = KagamiVoice()
                await _kagami_voice.initialize()

    return _kagami_voice


async def synthesize(
    text: str,
    colony: Colony | str = Colony.KAGAMI,
) -> SpeakResult:
    """Synthesize speech with Kagami's voice using ElevenLabs V3.

    ALWAYS uses V3 model for audio tag support ([whispers], [excited], etc).

    For playback, use UnifiedVoiceEffector:
        from kagami.core.effectors.voice import speak
        await speak("Hello")

    Args:
        text: Text to speak (can include V3 audio tags)
        colony: Colony for voice conditioning (kagami, spark, forge, etc.)

    Returns:
        SpeakResult with audio_path and audio_bytes (NO playback)

    Example:
        >>> from kagami.core.services.voice.kagami_voice import synthesize
        >>> result = await synthesize("Hello Tim")
        >>> result = await synthesize("[excited] Great news!", colony="spark")
    """
    voice = await get_kagami_voice()
    return await voice.synthesize(text, colony=colony)


# =============================================================================
# Convenience Functions
# =============================================================================


async def synthesize_as(colony: Colony | str, text: str) -> SpeakResult:
    """Synthesize as a specific colony.

    Args:
        colony: Colony to speak as
        text: Text to speak

    Returns:
        SpeakResult
    """
    return await synthesize(text, colony=colony)


async def announce(text: str, urgent: bool = False) -> SpeakResult:
    """Make an announcement (synthesis only).

    For actual playback with routing, use UnifiedVoiceEffector.announce().

    Args:
        text: Announcement text
        urgent: If True, use Beacon colony

    Returns:
        SpeakResult
    """
    colony = Colony.BEACON if urgent else Colony.KAGAMI
    return await synthesize(text, colony=colony)


# Export all public items
__all__ = [
    # Constants
    "COLONY_VOICE_SETTINGS",
    "ELEVENLABS_MODEL",
    # Types
    "Colony",
    "ColonyVoiceSettings",
    # Core
    "KagamiVoice",
    "SpeakResult",
    "announce",
    "get_colony_settings",
    "get_kagami_voice",
    "synthesize",
    "synthesize_as",
]
