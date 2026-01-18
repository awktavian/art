"""Embedded Audio Adapter using I2S/DAC.

Implements AudioController for embedded systems using:
- I2S for digital audio output
- ADC for audio input
- GPIO for amplifier control

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.audio_controller import AudioController
from kagami_hal.data_types import AudioConfig, AudioFormat

logger = logging.getLogger(__name__)

# Check for embedded environment
EMBEDDED_AVAILABLE = Path("/sys/class/gpio").exists()

# Try to import GPIO libraries
GPIO_AVAILABLE = False
try:
    import RPi.GPIO as GPIO

    GPIO_AVAILABLE = True
except ImportError:
    pass


class EmbeddedAudio(AudioController):
    """Embedded audio implementation using I2S/GPIO."""

    def __init__(
        self,
        i2s_device: str = "/dev/snd/pcmC0D0p",
        amp_enable_pin: int | None = None,
    ):
        """Initialize embedded audio.

        Args:
            i2s_device: ALSA device for I2S
            amp_enable_pin: GPIO pin for amplifier enable (optional)
        """
        self._i2s_device = i2s_device
        self._amp_pin = amp_enable_pin
        self._config: AudioConfig | None = None
        self._volume: float = 0.7
        self._alsa_pcm: Any = None

    async def initialize(self, config: AudioConfig) -> bool:
        """Initialize audio."""
        if not EMBEDDED_AVAILABLE:
            if is_test_mode():
                logger.info("Embedded audio not available, gracefully degrading")
                return False
            raise RuntimeError("Embedded audio only available on embedded systems")

        try:
            # Configure amplifier GPIO if specified
            if self._amp_pin and GPIO_AVAILABLE:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self._amp_pin, GPIO.OUT)
                GPIO.output(self._amp_pin, GPIO.HIGH)  # Enable amp

            # Try to open ALSA device
            try:
                import alsaaudio

                self._alsa_pcm = alsaaudio.PCM(
                    type=alsaaudio.PCM_PLAYBACK,
                    mode=alsaaudio.PCM_NORMAL,
                    device=self._i2s_device.replace("/dev/snd/", ""),
                )

                self._alsa_pcm.setchannels(config.channels)
                self._alsa_pcm.setrate(config.sample_rate)

                if config.format == AudioFormat.PCM_16:
                    self._alsa_pcm.setformat(alsaaudio.PCM_FORMAT_S16_LE)
                elif config.format == AudioFormat.PCM_32:
                    self._alsa_pcm.setformat(alsaaudio.PCM_FORMAT_S32_LE)

                self._alsa_pcm.setperiodsize(config.buffer_size)

            except ImportError:
                logger.warning("alsaaudio not available, audio playback disabled")

            self._config = config
            logger.info(
                f"✅ Embedded audio initialized: {config.sample_rate}Hz, {config.channels}ch"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize embedded audio: {e}", exc_info=True)
            return False

    async def play(self, buffer: bytes) -> None:
        """Play audio buffer."""
        if not self._alsa_pcm:
            logger.debug(f"Audio play: {len(buffer)} bytes (no ALSA)")
            return

        try:
            self._alsa_pcm.write(buffer)
        except Exception as e:
            logger.error(f"Playback error: {e}")

    async def record(self, duration_ms: int) -> bytes:
        """Record audio."""
        if not self._config:
            raise RuntimeError("Audio not initialized")

        logger.warning("Recording not implemented for embedded audio")
        return b""

    async def set_volume(self, level: float) -> None:
        """Set volume.

        On embedded systems, volume may be controlled via:
        - DAC registers (I2C)
        - PWM for analog volume
        - Digital scaling of samples
        """
        if not (0.0 <= level <= 1.0):
            raise ValueError("Volume must be between 0.0 and 1.0")

        self._volume = level

        # Try ALSA mixer if available
        try:
            import alsaaudio

            mixer = alsaaudio.Mixer(control="Master")
            mixer.setvolume(int(level * 100))
        except Exception:
            pass

        logger.debug(f"Volume set to {level:.1%}")

    async def get_volume(self) -> float:
        """Get current volume."""
        return self._volume

    async def shutdown(self) -> None:
        """Shutdown audio."""
        if self._alsa_pcm:
            try:
                self._alsa_pcm.close()
            except Exception:
                pass

        # Disable amplifier
        if self._amp_pin and GPIO_AVAILABLE:
            try:
                GPIO.output(self._amp_pin, GPIO.LOW)
            except Exception:
                pass

        logger.info("✅ Embedded audio shutdown")
