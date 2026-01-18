"""Audio Controller HAL for K os.

Unified interface for audio I/O across platforms.

Supported:
- Linux: ALSA
- macOS: CoreAudio
- Embedded: I2S codec

Created: November 10, 2025
"""

from __future__ import annotations

from abc import ABC, abstractmethod

# Import from shared data_types to avoid duplicate definitions and LSP violations
from kagami_hal.data_types import AudioConfig


class AudioController(ABC):
    """Abstract audio controller interface."""

    @abstractmethod
    async def initialize(self, config: AudioConfig) -> bool:
        """Initialize audio.

        Args:
            config: Audio configuration

        Returns:
            True if successful
        """

    @abstractmethod
    async def play(self, buffer: bytes) -> None:
        """Play audio buffer.

        Args:
            buffer: Raw PCM audio data
        """

    @abstractmethod
    async def record(self, duration_ms: int) -> bytes:
        """Record audio.

        Args:
            duration_ms: Recording duration in milliseconds

        Returns:
            Raw PCM audio data
        """

    @abstractmethod
    async def set_volume(self, level: float) -> None:
        """Set volume.

        Args:
            level: Volume (0.0-1.0)
        """

    @abstractmethod
    async def get_volume(self) -> float:
        """Get current volume.

        Returns:
            Volume (0.0-1.0)
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown audio."""
