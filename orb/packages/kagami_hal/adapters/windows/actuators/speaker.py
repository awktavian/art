"""Windows WASAPI Speaker Actuator.

Implements audio output using WASAPI (Windows Audio Session API).

Provides low-latency playback at 48kHz PCM-16, with volume control
and system integration.

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import AudioConfig, AudioFormat

logger = logging.getLogger(__name__)

WINDOWS_AVAILABLE = sys.platform == "win32"
SOUNDDEVICE_AVAILABLE = False
PYCAW_AVAILABLE = False

if WINDOWS_AVAILABLE:
    try:
        import numpy as np
        import sounddevice as sd

        SOUNDDEVICE_AVAILABLE = True
    except ImportError:
        logger.warning("sounddevice not available - install: pip install sounddevice numpy")

    try:
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        PYCAW_AVAILABLE = True
    except ImportError:
        logger.warning("pycaw not available - install: pip install pycaw comtypes")


class WindowsWASAPISpeaker:
    """Windows WASAPI speaker implementation.

    Implements IActuator protocol for audio output.
    """

    def __init__(self):
        """Initialize WASAPI speaker."""
        self._config: AudioConfig | None = None
        self._volume: float = 0.7
        self._endpoint_volume: Any = None

    async def initialize(self, config: AudioConfig | None = None) -> bool:
        """Initialize speaker with WASAPI.

        Args:
            config: Optional audio configuration (48kHz PCM-16 default)

        Returns:
            True if initialization successful
        """
        if not WINDOWS_AVAILABLE:
            if is_test_mode():
                logger.info(
                    "Windows WASAPI speaker not available (wrong platform), gracefully degrading"
                )
                return False
            raise RuntimeError("Windows WASAPI speaker only available on Windows")

        if not SOUNDDEVICE_AVAILABLE:
            if is_test_mode():
                logger.info("sounddevice not available, gracefully degrading")
                return False
            raise RuntimeError("sounddevice not available. Install: pip install sounddevice numpy")

        try:
            # Default config: 48kHz PCM-16 mono
            if config is None:
                config = AudioConfig(
                    sample_rate=48000,
                    channels=1,
                    format=AudioFormat.PCM_16,
                    buffer_size=2048,
                )

            self._config = config

            # Get system volume control if pycaw available
            if PYCAW_AVAILABLE:
                try:
                    devices = AudioUtilities.GetSpeakers()
                    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    self._endpoint_volume = interface.QueryInterface(IAudioEndpointVolume)
                    self._volume = self._endpoint_volume.GetMasterVolumeLevelScalar()
                except Exception as e:
                    logger.warning(f"Failed to get volume control: {e}")

            # Configure sounddevice
            sd.default.samplerate = config.sample_rate
            sd.default.channels = config.channels
            sd.default.blocksize = config.buffer_size

            # Set dtype
            if config.format == AudioFormat.PCM_16:
                sd.default.dtype = "int16"
            elif config.format == AudioFormat.PCM_32:
                sd.default.dtype = "int32"
            elif config.format == AudioFormat.FLOAT_32:
                sd.default.dtype = "float32"
            else:
                sd.default.dtype = "int16"

            logger.info(
                f"✅ WASAPI speaker initialized: {config.sample_rate}Hz, "
                f"{config.channels}ch, {config.format.value}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize WASAPI speaker: {e}", exc_info=True)
            return False

    async def actuate(self, data: bytes) -> None:
        """Play audio buffer.

        Args:
            data: Raw PCM audio bytes

        Raises:
            RuntimeError: If not initialized or playback fails
        """
        await self.play(data)

    async def play(self, buffer: bytes) -> None:
        """Play audio buffer via WASAPI.

        Args:
            buffer: Raw PCM audio bytes
        """
        if not self._config or not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError("Speaker not initialized")

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
            if self._config.channels == 2 and len(audio.shape) == 1:
                audio = audio.reshape(-1, 2)

            # Play (blocking)
            sd.play(audio, samplerate=self._config.sample_rate)
            sd.wait()

        except Exception as e:
            logger.error(f"Playback error: {e}")
            raise RuntimeError(f"Playback failed: {e}") from e

    async def play_pcm(
        self,
        audio_data: Any,
        sample_rate: int = 48000,
        channels: int = 1,
        blocking: bool = True,
    ) -> None:
        """Play PCM audio from numpy array.

        Args:
            audio_data: Numpy array (float32 or int16)
            sample_rate: Sample rate
            channels: Channel count
            blocking: Wait for playback to complete
        """
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError("Speaker not initialized")

        import numpy as np

        # Convert to numpy if needed
        if not isinstance(audio_data, np.ndarray):
            audio_data = np.array(audio_data)

        # Convert float32 to int16 if needed
        if audio_data.dtype in (np.float32, np.float64):
            max_val = np.abs(audio_data).max()
            if max_val > 0:
                audio_data = audio_data / max(max_val, 1.0)
            audio_data = (audio_data * 32767).astype(np.int16)

        # Play
        sd.play(audio_data, samplerate=sample_rate)

        if blocking:
            sd.wait()

    async def set_volume(self, level: float) -> None:
        """Set speaker volume.

        Args:
            level: Volume level 0.0-1.0
        """
        if not (0.0 <= level <= 1.0):
            raise ValueError("Volume must be between 0.0 and 1.0")

        self._volume = level

        if self._endpoint_volume:
            try:
                self._endpoint_volume.SetMasterVolumeLevelScalar(level, None)
                logger.debug(f"Volume set to {level:.1%}")
            except Exception as e:
                logger.warning(f"Failed to set volume: {e}")
        else:
            logger.debug(f"Volume cached: {level:.1%} (no hardware control)")

    async def get_volume(self) -> float:
        """Get current speaker volume.

        Returns:
            Volume level 0.0-1.0
        """
        if self._endpoint_volume:
            try:
                return self._endpoint_volume.GetMasterVolumeLevelScalar()
            except Exception:
                pass

        return self._volume

    async def get_capabilities(self) -> dict[str, Any]:
        """Get speaker capabilities.

        Returns:
            Dict with supported formats, sample rates, latency
        """
        if not SOUNDDEVICE_AVAILABLE:
            return {}

        try:
            device_info = sd.query_devices(kind="output")
            return {
                "name": device_info["name"],
                "hostapi": sd.query_hostapis(device_info["hostapi"])["name"],
                "max_output_channels": device_info["max_output_channels"],
                "default_samplerate": device_info["default_samplerate"],
                "default_low_output_latency": device_info["default_low_output_latency"],
                "default_high_output_latency": device_info["default_high_output_latency"],
            }

        except Exception as e:
            logger.error(f"Failed to get capabilities: {e}")
            return {}

    async def shutdown(self) -> None:
        """Release speaker resources."""
        try:
            if SOUNDDEVICE_AVAILABLE:
                sd.stop()
        except Exception:
            pass

        self._endpoint_volume = None
        logger.info("✅ WASAPI speaker shutdown")

    @staticmethod
    def enumerate_devices() -> list[dict[str, Any]]:
        """Enumerate available WASAPI output devices.

        Returns:
            List of device info dicts
        """
        if not SOUNDDEVICE_AVAILABLE:
            return []

        try:
            devices = sd.query_devices()
            output_devices = []

            for i, device in enumerate(devices):
                if device["max_output_channels"] > 0:
                    output_devices.append(
                        {
                            "id": i,
                            "name": device["name"],
                            "hostapi": sd.query_hostapis(device["hostapi"])["name"],
                            "channels": device["max_output_channels"],
                            "default_samplerate": device["default_samplerate"],
                        }
                    )

            return output_devices

        except Exception as e:
            logger.error(f"Failed to enumerate devices: {e}")
            return []
