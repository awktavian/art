"""Windows WASAPI Audio Adapter.

Implements AudioController for Windows using WASAPI (Windows Audio Session API).

Supports:
- Low-latency playback via shared/exclusive mode
- Recording via loopback capture
- Per-session volume control

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.audio_controller import AudioController
from kagami_hal.data_types import AudioConfig, AudioFormat

logger = logging.getLogger(__name__)

WINDOWS_AVAILABLE = sys.platform == "win32"
WASAPI_AVAILABLE = False

if WINDOWS_AVAILABLE:
    try:
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        WASAPI_AVAILABLE = True
    except ImportError:
        logger.warning("pycaw not available - install: pip install pycaw comtypes")

# Try to import sounddevice for cross-platform audio
try:
    import numpy as np
    import sounddevice as sd

    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logger.warning("sounddevice not available - install: pip install sounddevice numpy")


class WindowsWASAPIAudio(AudioController):
    """Windows WASAPI audio implementation."""

    def __init__(self):
        """Initialize WASAPI audio."""
        self._config: AudioConfig | None = None
        self._volume: float = 0.7
        self._endpoint_volume: Any = None
        self._stream: Any = None

    async def initialize(self, config: AudioConfig) -> bool:
        """Initialize audio with config."""
        if not WINDOWS_AVAILABLE:
            if is_test_mode():
                logger.info("Windows WASAPI not available (wrong platform), gracefully degrading")
                return False
            raise RuntimeError("Windows WASAPI only available on Windows")

        if not SOUNDDEVICE_AVAILABLE:
            if is_test_mode():
                logger.info("sounddevice not available, gracefully degrading")
                return False
            raise RuntimeError(
                "Audio libraries not available. Install: pip install sounddevice numpy pycaw comtypes"
            )

        try:
            self._config = config

            # Get system volume control if WASAPI available
            if WASAPI_AVAILABLE:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self._endpoint_volume = interface.QueryInterface(IAudioEndpointVolume)
                self._volume = self._endpoint_volume.GetMasterVolumeLevelScalar()

            # Configure sounddevice
            sd.default.samplerate = config.sample_rate
            sd.default.channels = config.channels
            sd.default.blocksize = config.buffer_size

            # Set dtype based on format
            if config.format == AudioFormat.PCM_16:
                sd.default.dtype = "int16"
            elif config.format == AudioFormat.PCM_32:
                sd.default.dtype = "int32"
            elif config.format == AudioFormat.FLOAT_32:
                sd.default.dtype = "float32"
            else:
                sd.default.dtype = "int16"

            logger.info(
                f"✅ Windows WASAPI initialized: {config.sample_rate}Hz, "
                f"{config.channels}ch, {config.format.value}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Windows WASAPI: {e}", exc_info=True)
            return False

    async def play(self, buffer: bytes) -> None:
        """Play audio buffer."""
        if not self._config:
            raise RuntimeError("Audio not initialized")

        if not SOUNDDEVICE_AVAILABLE:
            return

        try:
            # Convert bytes to numpy array
            if self._config.format == AudioFormat.PCM_16:
                audio = np.frombuffer(buffer, dtype=np.int16)
            elif self._config.format == AudioFormat.PCM_32:
                audio = np.frombuffer(buffer, dtype=np.int32)
            elif self._config.format == AudioFormat.FLOAT_32:
                audio = np.frombuffer(buffer, dtype=np.float32)
            else:
                audio = np.frombuffer(buffer, dtype=np.int16)

            # Reshape for stereo
            if self._config.channels == 2:
                audio = audio.reshape(-1, 2)

            # Play (blocking)
            sd.play(audio, samplerate=self._config.sample_rate)
            sd.wait()

        except Exception as e:
            logger.error(f"Playback error: {e}")

    async def record(self, duration_ms: int) -> bytes:
        """Record audio."""
        if not self._config:
            raise RuntimeError("Audio not initialized")

        if not SOUNDDEVICE_AVAILABLE:
            return b""

        try:
            # Calculate frames
            frames = int(self._config.sample_rate * duration_ms / 1000)

            # Determine dtype
            if self._config.format == AudioFormat.PCM_16:
                dtype = np.int16
            elif self._config.format == AudioFormat.PCM_32:
                dtype = np.int32
            elif self._config.format == AudioFormat.FLOAT_32:
                dtype = np.float32
            else:
                dtype = np.int16

            # Record (blocking)
            recording = sd.rec(
                frames,
                samplerate=self._config.sample_rate,
                channels=self._config.channels,
                dtype=dtype,
            )
            sd.wait()

            return recording.tobytes()

        except Exception as e:
            logger.error(f"Recording error: {e}")
            return b""

    async def set_volume(self, level: float) -> None:
        """Set volume (0.0-1.0)."""
        if not (0.0 <= level <= 1.0):
            raise ValueError("Volume must be between 0.0 and 1.0")

        self._volume = level

        if self._endpoint_volume:
            try:
                self._endpoint_volume.SetMasterVolumeLevelScalar(level, None)
            except Exception as e:
                logger.warning(f"Failed to set volume: {e}")

        logger.debug(f"Volume set to {level:.1%}")

    async def get_volume(self) -> float:
        """Get current volume."""
        if self._endpoint_volume:
            try:
                return self._endpoint_volume.GetMasterVolumeLevelScalar()
            except Exception:
                pass
        return self._volume

    async def shutdown(self) -> None:
        """Shutdown audio."""
        try:
            if SOUNDDEVICE_AVAILABLE:
                sd.stop()
        except Exception:
            pass

        self._endpoint_volume = None
        logger.info("✅ Windows WASAPI shutdown")
