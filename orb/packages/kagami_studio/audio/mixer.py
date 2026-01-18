"""Audio Mixer — Multi-channel audio mixing.

Professional audio mixer with:
- Multiple input channels
- Per-channel volume, pan, mute
- Master output with limiting
- Real-time level metering
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MixerConfig:
    """Audio mixer configuration."""

    sample_rate: int = 48000
    channels: int = 2
    buffer_size: int = 1024
    max_inputs: int = 16
    enable_limiter: bool = True
    limiter_threshold: float = 0.95


@dataclass
class AudioChannel:
    """A single audio channel in the mixer."""

    id: str
    name: str
    volume: float = 1.0  # 0.0 - 2.0
    pan: float = 0.0  # -1.0 (left) to 1.0 (right)
    muted: bool = False
    solo: bool = False
    level: float = 0.0  # Current level (read-only)

    # Filters
    low_cut: float = 0.0  # Hz, 0 = disabled
    high_cut: float = 0.0  # Hz, 0 = disabled
    gain: float = 0.0  # dB

    def process(self, samples: np.ndarray) -> np.ndarray:
        """Process samples through channel settings.

        Args:
            samples: Input samples (mono or stereo)

        Returns:
            Processed stereo samples
        """
        if self.muted:
            return np.zeros_like(samples)

        # Apply gain
        if self.gain != 0:
            gain_linear = 10 ** (self.gain / 20)
            samples = samples * gain_linear

        # Apply volume
        samples = samples * self.volume

        # Ensure stereo
        if samples.ndim == 1:
            samples = np.stack([samples, samples], axis=-1)

        # Apply pan (constant power)
        if self.pan != 0:
            left_gain = np.cos((self.pan + 1) * np.pi / 4)
            right_gain = np.sin((self.pan + 1) * np.pi / 4)
            samples[:, 0] *= left_gain
            samples[:, 1] *= right_gain

        # Update level meter
        self.level = float(np.sqrt(np.mean(samples**2)))

        return samples


class AudioMixer:
    """Multi-channel audio mixer.

    Features:
    - 16+ input channels
    - Per-channel volume, pan, mute/solo
    - Master output with limiter
    - Real-time level metering
    - Low-latency processing
    """

    def __init__(self, config: MixerConfig | None = None):
        self.config = config or MixerConfig()
        self._channels: dict[str, AudioChannel] = {}
        self._master_volume: float = 1.0
        self._master_level: float = 0.0
        self._solo_active: bool = False

    def add_channel(self, channel_id: str, name: str) -> AudioChannel:
        """Add a new channel to the mixer.

        Args:
            channel_id: Unique channel identifier
            name: Display name

        Returns:
            AudioChannel object
        """
        if len(self._channels) >= self.config.max_inputs:
            raise RuntimeError(f"Maximum channels ({self.config.max_inputs}) reached")

        channel = AudioChannel(id=channel_id, name=name)
        self._channels[channel_id] = channel
        return channel

    def remove_channel(self, channel_id: str) -> None:
        """Remove a channel."""
        if channel_id in self._channels:
            del self._channels[channel_id]

    def get_channel(self, channel_id: str) -> AudioChannel | None:
        """Get a channel by ID."""
        return self._channels.get(channel_id)

    def set_volume(self, channel_id: str, volume: float) -> None:
        """Set channel volume (0.0 - 2.0)."""
        if channel := self._channels.get(channel_id):
            channel.volume = max(0.0, min(2.0, volume))

    def set_pan(self, channel_id: str, pan: float) -> None:
        """Set channel pan (-1.0 to 1.0)."""
        if channel := self._channels.get(channel_id):
            channel.pan = max(-1.0, min(1.0, pan))

    def set_mute(self, channel_id: str, muted: bool) -> None:
        """Set channel mute state."""
        if channel := self._channels.get(channel_id):
            channel.muted = muted

    def set_solo(self, channel_id: str, solo: bool) -> None:
        """Set channel solo state."""
        if channel := self._channels.get(channel_id):
            channel.solo = solo
            self._update_solo_state()

    def _update_solo_state(self) -> None:
        """Update solo state tracking."""
        self._solo_active = any(ch.solo for ch in self._channels.values())

    def set_master_volume(self, volume: float) -> None:
        """Set master output volume (0.0 - 2.0)."""
        self._master_volume = max(0.0, min(2.0, volume))

    def mix(self, channel_samples: dict[str, np.ndarray]) -> np.ndarray:
        """Mix multiple channel inputs to stereo output.

        Args:
            channel_samples: Dict of channel_id -> samples

        Returns:
            Mixed stereo samples
        """
        # Initialize output buffer
        buffer_size = self.config.buffer_size
        output = np.zeros((buffer_size, 2), dtype=np.float32)

        # Process each channel
        for channel_id, samples in channel_samples.items():
            channel = self._channels.get(channel_id)
            if not channel:
                continue

            # Skip if solo is active and this channel isn't soloed
            if self._solo_active and not channel.solo:
                continue

            # Process through channel
            processed = channel.process(samples.astype(np.float32))

            # Ensure correct shape
            if len(processed) < buffer_size:
                padded = np.zeros((buffer_size, 2), dtype=np.float32)
                padded[: len(processed)] = processed
                processed = padded
            elif len(processed) > buffer_size:
                processed = processed[:buffer_size]

            # Add to output
            output += processed

        # Apply master volume
        output *= self._master_volume

        # Apply limiter
        if self.config.enable_limiter:
            output = self._apply_limiter(output)

        # Update master level
        self._master_level = float(np.sqrt(np.mean(output**2)))

        return output

    def _apply_limiter(self, samples: np.ndarray) -> np.ndarray:
        """Apply soft limiter to prevent clipping."""
        threshold = self.config.limiter_threshold

        # Soft knee limiting
        abs_samples = np.abs(samples)
        mask = abs_samples > threshold

        if np.any(mask):
            # Soft clip above threshold
            excess = abs_samples[mask] - threshold
            compressed = threshold + np.tanh(excess * 2) * (1 - threshold)
            samples[mask] = np.sign(samples[mask]) * compressed

        return samples

    def get_levels(self) -> dict[str, float]:
        """Get all channel levels.

        Returns:
            Dict of channel_id -> level (0.0 - 1.0)
        """
        levels = {ch.id: ch.level for ch in self._channels.values()}
        levels["master"] = self._master_level
        return levels

    def list_channels(self) -> list[dict]:
        """List all channels with their settings."""
        return [
            {
                "id": ch.id,
                "name": ch.name,
                "volume": ch.volume,
                "pan": ch.pan,
                "muted": ch.muted,
                "solo": ch.solo,
                "level": ch.level,
            }
            for ch in self._channels.values()
        ]
