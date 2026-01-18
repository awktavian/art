"""Audio Ducking — Automatic volume reduction.

Audio ducking automatically reduces the volume of background audio
(like music) when foreground audio (like speech) is detected.
Essential for podcasts, streams, and professional broadcasts.

Usage:
    ducker = AudioDucker()

    # Duck music when voice is active
    music_samples = ducker.process(
        music_samples,
        trigger_samples=voice_samples,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DuckingConfig:
    """Audio ducking configuration."""

    # Trigger detection
    threshold: float = -30.0  # dB, trigger level
    hold_time: float = 0.3  # seconds to hold duck after trigger stops

    # Ducking behavior
    duck_amount: float = -12.0  # dB reduction when ducking
    attack_time: float = 0.05  # seconds to ramp down
    release_time: float = 0.3  # seconds to ramp up

    # Sample rate for time calculations
    sample_rate: int = 48000


class AudioDucker:
    """Automatic audio ducking processor.

    Monitors a trigger signal (like voice) and reduces
    the volume of another signal (like music) when
    the trigger is active.
    """

    def __init__(self, config: DuckingConfig | None = None):
        self.config = config or DuckingConfig()
        self._ducking = False
        self._duck_gain = 1.0
        self._hold_samples = 0
        self._target_gain = 1.0

    def process(
        self,
        audio: np.ndarray,
        trigger: np.ndarray,
    ) -> np.ndarray:
        """Process audio with ducking.

        Args:
            audio: Audio to duck (music, ambient, etc.)
            trigger: Trigger signal (voice, etc.)

        Returns:
            Ducked audio
        """
        # Calculate trigger level in dB
        trigger_rms = np.sqrt(np.mean(trigger.astype(np.float32) ** 2))
        if trigger_rms > 0:
            trigger_db = 20 * np.log10(trigger_rms / 32768)
        else:
            trigger_db = -100

        # Check if trigger exceeds threshold
        is_triggered = trigger_db > self.config.threshold

        # Update ducking state
        if is_triggered:
            self._ducking = True
            self._hold_samples = int(self.config.hold_time * self.config.sample_rate)
            self._target_gain = 10 ** (self.config.duck_amount / 20)
        elif self._hold_samples > 0:
            self._hold_samples -= len(audio)
        else:
            self._ducking = False
            self._target_gain = 1.0

        # Smooth gain transition
        if self._ducking:
            # Attack (ramp down)
            attack_samples = int(self.config.attack_time * self.config.sample_rate)
            ramp_rate = (self._target_gain - self._duck_gain) / max(attack_samples, 1)
        else:
            # Release (ramp up)
            release_samples = int(self.config.release_time * self.config.sample_rate)
            ramp_rate = (self._target_gain - self._duck_gain) / max(release_samples, 1)

        # Apply ramped gain
        output = audio.astype(np.float32)
        gains = np.zeros(len(output))

        for i in range(len(output)):
            self._duck_gain += ramp_rate
            self._duck_gain = max(self._target_gain, min(1.0, self._duck_gain))
            gains[i] = self._duck_gain

        if output.ndim == 2:
            output *= gains[:, np.newaxis]
        else:
            output *= gains

        return output.astype(audio.dtype)

    def reset(self) -> None:
        """Reset ducking state."""
        self._ducking = False
        self._duck_gain = 1.0
        self._hold_samples = 0
        self._target_gain = 1.0

    @property
    def is_ducking(self) -> bool:
        """Check if currently ducking."""
        return self._ducking

    @property
    def current_gain(self) -> float:
        """Get current gain reduction (0.0 - 1.0)."""
        return self._duck_gain


class SidechainCompressor:
    """Sidechain compressor for more advanced ducking.

    Uses a full compressor with sidechain input for
    professional-grade ducking with more control.
    """

    def __init__(
        self,
        threshold: float = -20.0,
        ratio: float = 4.0,
        attack_ms: float = 10.0,
        release_ms: float = 100.0,
        sample_rate: int = 48000,
    ):
        self.threshold = threshold
        self.ratio = ratio
        self.attack_ms = attack_ms
        self.release_ms = release_ms
        self.sample_rate = sample_rate

        self._envelope = 0.0

    def process(
        self,
        audio: np.ndarray,
        sidechain: np.ndarray,
    ) -> np.ndarray:
        """Process audio with sidechain compression.

        Args:
            audio: Audio to compress
            sidechain: Sidechain input (controls compression)

        Returns:
            Compressed audio
        """
        # Convert times to coefficients
        attack_coef = np.exp(-1.0 / (self.attack_ms * self.sample_rate / 1000))
        release_coef = np.exp(-1.0 / (self.release_ms * self.sample_rate / 1000))

        output = audio.astype(np.float32).copy()

        for i in range(len(sidechain)):
            # Get sidechain level
            sc_sample = abs(float(sidechain[i])) / 32768
            sc_db = 20 * np.log10(sc_sample + 1e-10)

            # Update envelope
            if sc_db > self._envelope:
                self._envelope = attack_coef * self._envelope + (1 - attack_coef) * sc_db
            else:
                self._envelope = release_coef * self._envelope + (1 - release_coef) * sc_db

            # Calculate gain reduction
            if self._envelope > self.threshold:
                gain_reduction = (self._envelope - self.threshold) * (1 - 1 / self.ratio)
                gain = 10 ** (-gain_reduction / 20)
            else:
                gain = 1.0

            # Apply gain
            if audio.ndim == 2:
                output[i] *= gain
            else:
                output[i] *= gain

        return output.astype(audio.dtype)
