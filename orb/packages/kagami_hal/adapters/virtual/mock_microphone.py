"""Virtual Microphone Sensor.

Generates synthetic audio for testing without hardware.

Supports:
- Silence
- Sine waves (pure tones)
- White noise
- Deterministic generation
- Recording mode (save audio to disk)

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import random

import numpy as np

from .config import get_virtual_config

logger = logging.getLogger(__name__)


class VirtualMicrophone:
    """Virtual microphone for testing.

    Generates synthetic audio with configurable patterns.
    """

    def __init__(self, sample_rate: int | None = None, channels: int | None = None) -> None:
        """Initialize virtual microphone.

        Args:
            sample_rate: Audio sample rate (default from config)
            channels: Number of channels (default from config)
        """
        self._config = get_virtual_config()

        # Override audio settings if provided
        if sample_rate is not None:
            self._config.audio_sample_rate = sample_rate
        if channels is not None:
            self._config.audio_channels = channels

        self._sample_count = 0
        self._start_time = self._config.get_time()
        self._initialized = False

        # Seed RNG if deterministic mode
        if self._config.deterministic:
            random.seed(self._config.seed + 1000)  # Offset from camera seed
            np.random.seed(self._config.seed + 1000)

    async def initialize(self) -> bool:
        """Initialize microphone."""
        self._initialized = True
        logger.info(
            f"✅ Virtual microphone initialized: "
            f"{self._config.audio_sample_rate}Hz, {self._config.audio_channels}ch"
        )
        return True

    async def shutdown(self) -> None:
        """Shutdown microphone."""
        self._initialized = False
        logger.info("Virtual microphone shutdown")

    async def record(self, duration_ms: int, pattern: str = "silence") -> bytes:
        """Record synthetic audio (async version).

        Args:
            duration_ms: Duration in milliseconds
            pattern: Generation pattern (silence, sine, noise, etc.)

        Returns:
            PCM16 audio bytes
        """
        return self._record_sync(duration_ms, pattern)

    def _record_sync(self, duration_ms: int, pattern: str = "silence") -> bytes:
        """Record synthetic audio.

        Args:
            duration_ms: Duration in milliseconds
            pattern: Generation pattern:
                - "silence": All zeros
                - "sine": Pure tone (440 Hz)
                - "sine_sweep": Frequency sweep 200-2000 Hz
                - "noise": White noise
                - "pink_noise": Pink noise (1/f spectrum)

        Returns:
            PCM16 audio bytes
        """
        sample_rate = self._config.audio_sample_rate
        channels = self._config.audio_channels
        num_samples = int(sample_rate * duration_ms / 1000)

        if pattern == "silence":
            audio = np.zeros(num_samples, dtype=np.int16)

        elif pattern == "sine":
            # 440 Hz sine wave (A4 note)
            freq = 440.0
            t = np.arange(num_samples) / sample_rate
            audio = (32767 * 0.5 * np.sin(2 * np.pi * freq * t)).astype(np.int16)  # type: ignore[assignment]

        elif pattern == "sine_sweep":
            # Frequency sweep from 200 Hz to 2000 Hz
            t = np.arange(num_samples) / sample_rate
            freq_start = 200.0
            freq_end = 2000.0
            sweep_rate = (freq_end - freq_start) / (duration_ms / 1000)
            instantaneous_freq = freq_start + sweep_rate * t
            phase = 2 * np.pi * np.cumsum(instantaneous_freq) / sample_rate
            audio = (32767 * 0.5 * np.sin(phase)).astype(np.int16)  # type: ignore[assignment]

        elif pattern == "noise":
            # White noise
            if self._config.deterministic:
                rng = np.random.RandomState(self._config.seed + self._sample_count)
                audio = rng.randint(-32768, 32767, num_samples, dtype=np.int16)  # type: ignore[assignment]
            else:
                audio = np.random.randint(-32768, 32767, num_samples, dtype=np.int16)  # type: ignore[assignment]
            # Scale down to reasonable volume
            audio = (audio * 0.1).astype(np.int16)  # type: ignore[assignment]

        elif pattern == "pink_noise":
            # Pink noise (1/f spectrum)
            if self._config.deterministic:
                rng = np.random.RandomState(self._config.seed + self._sample_count)
                white = rng.randn(num_samples)
            else:
                white = np.random.randn(num_samples)

            # Simple pink noise filter (not perfect but sufficient for testing)
            b0 = 0.99765
            b1 = b0 * 0.0990460
            b2 = b0 * 0.2965164
            b3 = b0 * 0.0498159
            pink = np.zeros(num_samples)
            state = [0.0, 0.0, 0.0, 0.0]

            for i in range(num_samples):
                state[0] = b0 * state[0] + white[i] * 0.0555179
                state[1] = b1 * state[1] + white[i] * 0.0750759
                state[2] = b2 * state[2] + white[i] * 0.1538520
                state[3] = b3 * state[3] + white[i] * 0.3104856
                pink[i] = state[0] + state[1] + state[2] + state[3] + white[i] * 0.5362

            # Normalize and convert to int16
            pink = pink / np.max(np.abs(pink))
            audio = (pink * 32767 * 0.3).astype(np.int16)

        else:
            logger.warning(f"Unknown pattern '{pattern}', using silence")
            audio = np.zeros(num_samples, dtype=np.int16)

        # Convert to stereo if needed
        if channels == 2:
            audio = np.stack([audio, audio], axis=-1)  # type: ignore[assignment]

        # Convert to bytes
        audio_bytes = audio.tobytes()

        # Record if enabled
        if self._config.record_mode:
            self._record_audio(audio_bytes, pattern)

        self._sample_count += num_samples
        return audio_bytes

    def _record_audio(self, audio_bytes: bytes, pattern: str) -> None:
        """Record audio to disk.

        Args:
            audio_bytes: Audio data
            pattern: Generation pattern (for filename)
        """
        try:
            timestamp = int(self._config.get_time() * 1000)
            output_path = self._config.output_dir / "audio" / f"recording_{pattern}_{timestamp}.raw"
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
        except Exception as e:
            logger.warning(f"Failed to record audio: {e}")

    def get_sample_count(self) -> int:
        """Get number of samples generated."""
        return self._sample_count

    def get_duration_seconds(self) -> float:
        """Get total duration of generated audio."""
        return self._sample_count / self._config.audio_sample_rate
