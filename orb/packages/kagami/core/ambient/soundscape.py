"""Soundscape Generator for Ambient OS.

Generates ambient audio that expresses system state:
- Base drone synced to breath
- Colony accent tones
- Safety alert sounds
- Spatial audio positioning

Uses the HAL AudioController for actual playback.

Created: December 5, 2025
"""

from __future__ import annotations

import asyncio
import logging
import math
import struct
from dataclasses import dataclass, field
from typing import Any

from kagami.core.ambient.data_types import (
    Colony,
    SoundLayer,
    SoundscapeConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class SoundscapeState:
    """Current soundscape state."""

    playing: bool = False
    master_volume: float = 0.3
    breath_modulation: float = 0.5  # Current breath value 0-1
    active_layers: set[SoundLayer] = field(default_factory=set)
    colony_activations: dict[Colony, float] = field(default_factory=dict)


class SoundGenerator:
    """Generates audio samples for the soundscape."""

    def __init__(self, sample_rate: int = 44100):
        """Initialize sound generator.

        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate
        self._phase: dict[str, float] = {}  # Phase accumulators per oscillator

    def generate_sine(
        self,
        frequency: float,
        duration_ms: int,
        amplitude: float = 0.3,
        oscillator_id: str = "default",
    ) -> bytes:
        """Generate sine wave audio.

        Args:
            frequency: Frequency in Hz
            duration_ms: Duration in milliseconds
            amplitude: Volume 0-1
            oscillator_id: ID for phase continuity

        Returns:
            Raw PCM audio bytes (16-bit signed, mono)
        """
        num_samples = int(self.sample_rate * duration_ms / 1000)
        phase = self._phase.get(oscillator_id, 0.0)

        samples = []
        phase_increment = 2 * math.pi * frequency / self.sample_rate

        for _ in range(num_samples):
            value = math.sin(phase) * amplitude
            # Convert to 16-bit signed integer
            sample = int(value * 32767)
            samples.append(struct.pack("<h", max(-32767, min(32767, sample))))
            phase += phase_increment

        # Store phase for continuity
        self._phase[oscillator_id] = phase % (2 * math.pi)

        return b"".join(samples)

    def generate_noise(
        self,
        duration_ms: int,
        amplitude: float = 0.1,
        filter_cutoff: float = 0.3,
    ) -> bytes:
        """Generate filtered noise (pink-ish).

        Args:
            duration_ms: Duration in milliseconds
            amplitude: Volume 0-1
            filter_cutoff: Low-pass filter cutoff (0-1)

        Returns:
            Raw PCM audio bytes
        """
        import random

        num_samples = int(self.sample_rate * duration_ms / 1000)
        samples = []

        # Simple one-pole low-pass filter
        prev = 0.0
        alpha = filter_cutoff

        for _ in range(num_samples):
            # White noise
            white = random.uniform(-1, 1)
            # Low-pass filter
            filtered = alpha * white + (1 - alpha) * prev
            prev = filtered

            value = filtered * amplitude
            sample = int(value * 32767)
            samples.append(struct.pack("<h", max(-32767, min(32767, sample))))

        return b"".join(samples)

    def generate_breath_modulated_tone(
        self,
        base_frequency: float,
        breath_value: float,
        duration_ms: int,
        base_amplitude: float = 0.2,
    ) -> bytes:
        """Generate tone modulated by breath.

        Args:
            base_frequency: Base frequency
            breath_value: Current breath value 0-1
            duration_ms: Duration
            base_amplitude: Base amplitude

        Returns:
            Raw PCM audio bytes
        """
        # Modulate amplitude with breath
        amplitude = base_amplitude * (0.3 + 0.7 * breath_value)

        # Slight pitch modulation
        frequency = base_frequency * (1 + 0.02 * breath_value)

        return self.generate_sine(frequency, duration_ms, amplitude, "breath_tone")

    def generate_colony_tone(
        self,
        colony: Colony,
        activation: float,
        duration_ms: int,
    ) -> bytes:
        """Generate tone for colony expression.

        Args:
            colony: Colony to express
            activation: Activation level 0-1
            duration_ms: Duration

        Returns:
            Raw PCM audio bytes
        """
        # Colony frequencies from colony_expressor
        colony_frequencies = {
            Colony.SPARK: 523.25,
            Colony.FORGE: 293.66,
            Colony.FLOW: 392.00,
            Colony.NEXUS: 349.23,
            Colony.BEACON: 440.00,
            Colony.GROVE: 329.63,
            Colony.CRYSTAL: 261.63,
        }

        frequency = colony_frequencies.get(colony, 440.0)
        amplitude = 0.1 + 0.2 * activation  # Scale amplitude with activation

        return self.generate_sine(
            frequency,
            duration_ms,
            amplitude,
            f"colony_{colony.value}",
        )

    def generate_safety_alert(
        self,
        h_value: float,
        duration_ms: int,
    ) -> bytes:
        """Generate safety alert sound.

        Args:
            h_value: Safety barrier value (positive = safe)
            duration_ms: Duration

        Returns:
            Raw PCM audio bytes
        """
        if h_value >= 0.5:
            # Safe: No sound or gentle hum
            return self.generate_sine(200, duration_ms, 0.05, "safety")

        elif h_value >= 0:
            # Warning: Faster oscillation
            amplitude = 0.1 + 0.2 * (0.5 - h_value)
            num_samples = int(self.sample_rate * duration_ms / 1000)
            samples = []

            # Pulsing warning tone
            pulse_rate = 2 + 4 * (0.5 - h_value)  # Faster as danger increases
            for i in range(num_samples):
                t = i / self.sample_rate
                # AM modulation for pulsing
                modulation = 0.5 + 0.5 * math.sin(2 * math.pi * pulse_rate * t)
                value = math.sin(2 * math.pi * 300 * t) * amplitude * modulation
                sample = int(value * 32767)
                samples.append(struct.pack("<h", max(-32767, min(32767, sample))))

            return b"".join(samples)

        else:
            # DANGER: Sharp alarm
            return self._generate_alarm(duration_ms)

    def _generate_alarm(self, duration_ms: int) -> bytes:
        """Generate alarm sound for h(x) < 0."""
        num_samples = int(self.sample_rate * duration_ms / 1000)
        samples = []

        for i in range(num_samples):
            t = i / self.sample_rate
            # Two-tone siren
            freq = 600 if int(t * 4) % 2 == 0 else 800
            value = math.sin(2 * math.pi * freq * t) * 0.4
            sample = int(value * 32767)
            samples.append(struct.pack("<h", max(-32767, min(32767, sample))))

        return b"".join(samples)


class Soundscape:
    """Manages the ambient soundscape.

    Coordinates multiple sound layers and provides
    breath-synchronized, colony-reactive ambient audio.
    """

    def __init__(self, config: SoundscapeConfig | None = None):
        """Initialize soundscape.

        Args:
            config: Soundscape configuration
        """
        self.config = config or SoundscapeConfig(elements=[])
        self._state = SoundscapeState()
        self._generator = SoundGenerator()

        # Audio buffer
        self._buffer: bytes = b""
        self._buffer_duration_ms = 100  # Generate 100ms chunks

        # Control
        self._running = False
        self._task: asyncio.Task | None = None
        self._audio_adapter: Any = None

    async def initialize(self) -> bool:
        """Initialize soundscape with HAL audio.

        Returns:
            True if successful
        """
        try:
            from kagami_hal import get_hal_manager

            hal = await get_hal_manager()
            self._audio_adapter = hal.audio

            if self._audio_adapter is None:
                logger.warning("No audio adapter available - soundscape in silent mode")
                return True  # Continue without audio

            logger.info("🔊 Soundscape initialized")
            return True

        except Exception as e:
            logger.warning(f"Soundscape init failed: {e} - continuing in silent mode")
            return True

    def set_breath(self, breath_value: float) -> None:
        """Update breath modulation.

        Args:
            breath_value: Current breath value 0-1
        """
        self._state.breath_modulation = breath_value

    def set_colony_activation(self, colony: Colony, activation: float) -> None:
        """Update colony activation.

        Args:
            colony: Colony to update
            activation: Activation level 0-1
        """
        self._state.colony_activations[colony] = activation

    def set_volume(self, volume: float) -> None:
        """Set master volume.

        Args:
            volume: Volume 0-1
        """
        self._state.master_volume = max(0.0, min(1.0, volume))

    async def _generate_frame(self) -> bytes:
        """Generate one frame of audio.

        Returns:
            Raw PCM audio bytes
        """
        duration = self._buffer_duration_ms
        frame_samples: list[bytes] = []

        # Base layer: breath-modulated drone
        if SoundLayer.BASE in self._state.active_layers:
            base = self._generator.generate_breath_modulated_tone(
                base_frequency=65.41,  # C2 - deep foundation
                breath_value=self._state.breath_modulation,
                duration_ms=duration,
                base_amplitude=0.15,
            )
            frame_samples.append(base)

        # Texture layer: filtered noise
        if SoundLayer.TEXTURE in self._state.active_layers:
            texture = self._generator.generate_noise(
                duration_ms=duration,
                amplitude=0.05 * self._state.breath_modulation,
                filter_cutoff=0.2,
            )
            frame_samples.append(texture)

        # Accent layer: colony tones
        if SoundLayer.ACCENT in self._state.active_layers:
            for colony, activation in self._state.colony_activations.items():
                if activation > 0.3:  # Threshold for audible expression
                    accent = self._generator.generate_colony_tone(
                        colony=colony,
                        activation=activation,
                        duration_ms=duration,
                    )
                    frame_samples.append(accent)

        # Mix samples
        if not frame_samples:
            # Silent frame
            return b"\x00" * (44100 * duration // 1000 * 2)

        return self._mix_samples(frame_samples)

    def _mix_samples(self, samples: list[bytes]) -> bytes:
        """Mix multiple audio samples.

        Args:
            samples: List of raw PCM samples

        Returns:
            Mixed audio
        """
        if not samples:
            return b""

        # Find minimum length
        min_len = min(len(s) for s in samples)

        # Mix by averaging
        mixed = []
        for i in range(0, min_len, 2):  # 2 bytes per sample
            total = 0
            for sample in samples:
                value = struct.unpack("<h", sample[i : i + 2])[0]
                total += value

            # Average and scale by master volume
            avg = int((total / len(samples)) * self._state.master_volume)
            avg = max(-32767, min(32767, avg))
            mixed.append(struct.pack("<h", avg))

        return b"".join(mixed)

    async def _playback_loop(self) -> None:
        """Background audio generation and playback loop."""
        logger.info("🔊 Soundscape playback started")

        # Enable default layers
        self._state.active_layers = {SoundLayer.BASE, SoundLayer.TEXTURE, SoundLayer.ACCENT}

        while self._running:
            try:
                # Generate audio frame
                frame = await self._generate_frame()

                # Play through HAL
                if self._audio_adapter and frame:
                    try:
                        await self._audio_adapter.play(frame)
                    except Exception as e:
                        logger.debug(f"Audio play failed: {e}")

                # Frame duration
                await asyncio.sleep(self._buffer_duration_ms / 1000)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Soundscape error: {e}", exc_info=True)
                await asyncio.sleep(1.0)

        logger.info("🔊 Soundscape playback stopped")

    async def start(self) -> None:
        """Start soundscape playback."""
        if self._running:
            return

        self._running = True
        self._state.playing = True

        from kagami.core.async_utils import safe_create_task

        self._task = safe_create_task(
            self._playback_loop(),
            name="soundscape",
            error_callback=lambda e: logger.error(f"Soundscape crashed: {e}"),
        )

    async def stop(self) -> None:
        """Stop soundscape playback."""
        self._running = False
        self._state.playing = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def enable_layer(self, layer: SoundLayer) -> None:
        """Enable a sound layer."""
        self._state.active_layers.add(layer)

    def disable_layer(self, layer: SoundLayer) -> None:
        """Disable a sound layer."""
        self._state.active_layers.discard(layer)


# =============================================================================
# Global Instance
# =============================================================================

_SOUNDSCAPE: Soundscape | None = None


async def get_soundscape() -> Soundscape:
    """Get global soundscape instance."""
    global _SOUNDSCAPE
    if _SOUNDSCAPE is None:
        _SOUNDSCAPE = Soundscape()
        await _SOUNDSCAPE.initialize()
    return _SOUNDSCAPE
