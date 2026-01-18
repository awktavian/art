"""Text-to-Speech services for Kagami.

Two APIs available:

1. FAST PATH (recommended) — kagami_voice module:
    from kagami.core.services.voice.kagami_voice import speak
    await speak("Hello Tim")  # 75ms TTFA, no boot
    await speak("Alert!", colony="crystal")  # Colony-conditioned

2. Legacy path — this module:
    from kagami.core.services.voice.tts import get_tts_service
    tts = await get_tts_service()
    result = await tts.synthesize("Hello Tim")

The fast path uses a single Kagami voice with colony conditioning.
No boot sequence required, warm ElevenLabs connection.

Created: January 1, 2026
"""

import logging

from kagami.core.services.voice.tts.base import (
    TTSConfig,
    TTSProvider,
    TTSResult,
)
from kagami.core.services.voice.tts.elevenlabs_provider import (
    ElevenLabsTTS,
    get_elevenlabs_tts,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ElevenLabsTTS",
    "TTSConfig",
    "TTSProvider",
    "TTSResult",
    "get_elevenlabs_tts",
    "get_tts_service",
    "speak",
    "speak_fast",
]


# Module-level singleton
_tts_service: TTSProvider | None = None


async def get_tts_service() -> TTSProvider:
    """Get the default TTS service (ElevenLabs).

    Returns:
        TTSProvider instance
    """
    global _tts_service
    if _tts_service is None:
        _tts_service = await get_elevenlabs_tts()
    return _tts_service


async def speak_fast(
    text: str,
    colony: str = "kagami",
    play: bool = True,
) -> TTSResult:
    """FAST PATH: Speak with colony conditioning, no boot required.

    This is the recommended way to speak — 75ms TTFA with streaming.

    Args:
        text: Text to speak
        colony: Colony for voice conditioning (kagami, spark, forge, etc.)
        play: Whether to play immediately

    Returns:
        SpeakResult with timing and audio
    """
    from kagami.core.services.voice.kagami_voice import SpeakResult
    from kagami.core.services.voice.kagami_voice import speak as _speak

    return await _speak(text, colony=colony, play=play)


async def speak(
    text: str,
    play: bool = True,
    emotion: str | None = None,
) -> TTSResult:
    """Speak text using the default TTS service.

    NOTE: For lower latency, use speak_fast() instead.

    Args:
        text: Text to speak
        play: Whether to play audio immediately
        emotion: Optional emotion hint (unused, for API compat)

    Returns:
        TTSResult with audio path and metrics
    """
    tts = await get_tts_service()
    result = await tts.synthesize(text)

    if play and result.success and result.audio_path:
        # Route through unified spatial audio stack
        try:
            import soundfile as sf

            from kagami.core.effectors.spatial_audio import (
                generate_voice_presence,
                get_spatial_engine,
            )

            engine = await get_spatial_engine()

            # Get audio duration for trajectory
            audio, sr = sf.read(str(result.audio_path))
            duration = len(audio) / sr

            # Use subtle voice presence animation
            trajectory = generate_voice_presence(duration)

            # Play through spatial engine (auto-detects Denon or stereo)
            await engine.play_spatial(result.audio_path, trajectory=trajectory)
        except Exception as e:
            # NO FALLBACK - spatial engine is canonical
            # If it fails, the error should propagate
            logger.error(f"Spatial engine playback failed: {e}")
            raise

    return result
