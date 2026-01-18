"""Virtual Audio Adapter for testing/headless environments.

Implements AudioController with in-memory buffering and recording mode.

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
Updated: December 15, 2025 - Recording mode, mock microphone
"""

from __future__ import annotations

import logging
from typing import Any

from kagami_hal.audio_controller import AudioController
from kagami_hal.data_types import AudioConfig

from .config import get_virtual_config
from .mock_microphone import VirtualMicrophone

logger = logging.getLogger(__name__)


class VirtualAudio(AudioController):
    """Virtual audio implementation for testing.

    Supports:
    - Mock microphone with configurable patterns
    - Recording mode (save all audio to disk)
    - In-memory buffering
    """

    def __init__(self) -> None:
        """Initialize virtual audio."""
        self._hal_config = get_virtual_config()
        self._config: AudioConfig | None = None
        self._volume: float = 0.7
        self._playback_buffer: bytes = b""
        self._recording_buffer: bytes = b""
        self._microphone = VirtualMicrophone()

    async def initialize(self, config: AudioConfig) -> bool:
        """Initialize audio."""
        self._config = config
        logger.info(f"✅ Virtual audio initialized: {config.sample_rate}Hz, {config.channels}ch")
        return True

    async def play(self, buffer: bytes) -> None:
        """Play audio buffer (stores in memory)."""
        self._playback_buffer = buffer
        logger.debug(f"Virtual audio: played {len(buffer)} bytes")

        # Record if enabled
        if self._hal_config.record_mode:
            self._record_playback(buffer)

    async def play_pcm(
        self,
        audio_data: Any,
        sample_rate: int = 24000,
        channels: int = 1,
        blocking: bool = True,
    ) -> None:
        """Play PCM audio (virtual - just stores in memory)."""
        import numpy as np

        if isinstance(audio_data, np.ndarray):
            if audio_data.dtype in (np.float32, np.float64):
                audio_data = (audio_data * 32767).astype(np.int16)
            self._playback_buffer = audio_data.tobytes()
        else:
            self._playback_buffer = bytes(audio_data)

        logger.debug(f"Virtual audio: played {len(self._playback_buffer)} bytes PCM")

    async def record(self, duration_ms: int) -> bytes:
        """Record audio (returns synthetic audio from mock microphone)."""
        if not self._config:
            return b""

        # Use mock microphone to generate audio
        # Pattern can be controlled via environment variable
        import os

        pattern = os.getenv("KAGAMI_VIRTUAL_MIC_PATTERN", "silence")
        return await self._microphone.record(duration_ms, pattern=pattern)

    async def set_volume(self, level: float) -> None:
        """Set volume."""
        self._volume = max(0.0, min(1.0, level))
        logger.debug(f"Virtual audio: volume set to {level:.1%}")

    async def get_volume(self) -> float:
        """Get current volume."""
        return self._volume

    async def shutdown(self) -> None:
        """Shutdown audio."""
        self._playback_buffer = b""
        logger.info("Virtual audio shutdown")

    def _record_playback(self, buffer: bytes) -> None:
        """Record playback audio to disk.

        Args:
            buffer: Audio data to save
        """
        try:
            timestamp = int(self._hal_config.get_time() * 1000)
            output_path = self._hal_config.output_dir / "audio" / f"playback_{timestamp}.raw"
            with open(output_path, "wb") as f:
                f.write(buffer)
        except Exception as e:
            logger.warning(f"Failed to record playback audio: {e}")
