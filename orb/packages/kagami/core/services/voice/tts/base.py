"""Base TTS provider interface.

Defines the contract for all TTS implementations.

Created: January 1, 2026
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TTSConfig:
    """TTS configuration.

    Optimized for natural, emotive speech with v3 capabilities:
    - eleven_v3 model for audio tags ([sings], [whispers], etc.)
    - Lower stability for emotional range
    - Natural speed (1.0)
    - Style for warmth and engagement

    Audio tags (v3 only):
    - [sings] - Singing voice
    - [whispers] - Whispering
    - [hums] - Humming
    - [laughs], [sighs], [excited], etc.

    Based on ElevenLabs best practices:
    https://elevenlabs.io/docs/best-practices/prompting
    """

    # Voice settings
    voice_id: str = "kagami"
    model_id: str = "eleven_v3"  # v3 for audio tags + singing

    # Audio settings
    sample_rate: int = 44100
    output_format: str = "mp3_44100_128"

    # Performance
    streaming: bool = True
    cache_enabled: bool = True

    # Voice character - natural, emotive
    stability: float = 0.45  # Lower = emotional range while maintaining clarity
    similarity_boost: float = 0.75  # Consistent voice characteristics
    style: float = 0.35  # Expressiveness and warmth
    use_speaker_boost: bool = True  # Clarity and presence
    speed: float = 1.0  # Natural pacing (don't slow down!)

    # Volume/presence
    volume_db: float = -3.0  # Slight reduction for ambient use


@dataclass
class TTSResult:
    """Result of TTS synthesis."""

    success: bool
    audio_path: Path | None = None
    audio_data: bytes | None = None
    sample_rate: int = 44100
    duration_ms: float = 0
    ttfa_ms: float = 0  # Time to first audio
    synthesis_ms: float = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class TTSProvider(ABC):
    """Abstract TTS provider interface."""

    def __init__(self, config: TTSConfig | None = None):
        """Initialize provider.

        Args:
            config: TTS configuration
        """
        self.config = config or TTSConfig()
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the provider.

        Returns:
            True if successful
        """
        ...

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        **kwargs: Any,
    ) -> TTSResult:
        """Synthesize text to speech.

        Args:
            text: Text to synthesize
            voice_id: Optional voice override
            **kwargs: Provider-specific options

        Returns:
            TTSResult with audio data or path
        """
        ...

    @abstractmethod
    async def stream_synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Stream synthesize text to speech.

        Args:
            text: Text to synthesize
            voice_id: Optional voice override
            **kwargs: Provider-specific options

        Yields:
            Audio chunks as bytes
        """
        ...
        yield b""  # For type checker

    @abstractmethod
    async def list_voices(self) -> list[dict[str, Any]]:
        """List available voices.

        Returns:
            List of voice info dicts
        """
        ...

    @property
    def is_initialized(self) -> bool:
        """Check if provider is initialized."""
        return self._initialized
