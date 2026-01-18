"""Speech-to-Text providers for Kagami.

Provides:
- BaseSTTProvider: Abstract base class
- FasterWhisperProvider: Local Whisper inference
- get_stt_provider: Factory function

Usage:
    from kagami.core.services.voice.stt import get_stt_provider

    provider = get_stt_provider()
    session = await provider.start_session("session-1")
    await provider.accept_chunk(session, audio_bytes)
    transcript = await provider.finalize(session)
"""

from kagami.core.services.voice.stt.base import BaseSTTProvider, STTSession

# Try to import FasterWhisper provider
try:
    from kagami.core.services.voice.stt.faster_whisper_provider import (
        FasterWhisperProvider,
    )

    WHISPER_AVAILABLE = True
except ImportError:
    FasterWhisperProvider = None  # type: ignore
    WHISPER_AVAILABLE = False


def get_stt_provider(provider_name: str = "whisper") -> BaseSTTProvider:
    """Get an STT provider by name.

    Args:
        provider_name: Provider to use ("whisper" default)

    Returns:
        STT provider instance
    """
    if provider_name == "whisper" and WHISPER_AVAILABLE and FasterWhisperProvider:
        return FasterWhisperProvider()

    # Fallback to base provider (returns empty transcript)
    return BaseSTTProvider()


__all__ = [
    "WHISPER_AVAILABLE",
    "BaseSTTProvider",
    "FasterWhisperProvider",
    "STTSession",
    "get_stt_provider",
]
