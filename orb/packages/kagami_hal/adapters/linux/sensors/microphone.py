"""Linux ALSA/PulseAudio Microphone Sensor.

Implements audio input via ALSA or PulseAudio using sounddevice library.

Created: December 15, 2025
"""

from __future__ import annotations

import importlib.util
import logging
import time
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.adapters.sensor_adapter_base import SensorAdapterBase
from kagami_hal.data_types import SensorReading, SensorType

logger = logging.getLogger(__name__)

# Lazy ALSA check (cached after first call)
import sys
from pathlib import Path

_alsa_available_cache: bool | None = None


def _check_alsa_available() -> bool:
    """Check ALSA availability (lazy, cached)."""
    global _alsa_available_cache
    if _alsa_available_cache is None:
        _alsa_available_cache = sys.platform.startswith("linux") and Path("/proc/asound").exists()
    return _alsa_available_cache


# Check for sounddevice
SOUNDDEVICE_AVAILABLE = importlib.util.find_spec("sounddevice") is not None

# Import if available
if SOUNDDEVICE_AVAILABLE:
    import sounddevice as sd  # noqa: F401


class LinuxMicrophone(SensorAdapterBase):
    """Linux microphone implementation using sounddevice.

    Supports ALSA and PulseAudio backends automatically.
    """

    def __init__(
        self, device_id: int | None = None, sample_rate: int = 16000, channels: int = 1
    ) -> None:
        """Initialize microphone adapter.

        Args:
            device_id: Audio device ID (None for default)
            sample_rate: Sample rate in Hz (default 16kHz for speech)
            channels: Number of channels (default 1 for mono)
        """
        super().__init__()
        self._device_id = device_id
        self._sample_rate = sample_rate
        self._channels = channels
        self._stream: Any = None

    async def initialize(self) -> bool:
        """Initialize microphone."""
        if not _check_alsa_available():
            if is_test_mode():
                logger.info("ALSA not available")
                return False
            raise RuntimeError("ALSA not available. Check /proc/asound exists.")

        if not SOUNDDEVICE_AVAILABLE:
            if is_test_mode():
                logger.info("sounddevice not available")
                return False
            raise RuntimeError("sounddevice not available. Install: pip install sounddevice")

        try:
            import sounddevice as sd

            # Query available devices
            devices = sd.query_devices()
            if isinstance(devices, dict):
                devices = [devices]

            # Find input devices
            input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]

            if not input_devices:
                logger.warning("No audio input devices found")
                return False

            # Use specified device or default
            if self._device_id is not None:
                device_info = sd.query_devices(self._device_id)
                if device_info["max_input_channels"] < self._channels:
                    logger.warning(f"Device {self._device_id} has insufficient input channels")
                    return False
            else:
                # Use default input device
                self._device_id = sd.default.device[0]

            self._available_sensors.add(SensorType.MICROPHONE)
            self._running = True

            device_name = sd.query_devices(self._device_id)["name"]
            logger.info(
                f"✅ ALSA microphone initialized: {self._sample_rate}Hz, "
                f"{self._channels}ch (device: {device_name})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize microphone: {e}", exc_info=True)
            return False

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read audio chunk.

        Returns:
            SensorReading with value as numpy array (float32)
        """
        if sensor != SensorType.MICROPHONE:
            raise RuntimeError(f"Sensor {sensor} not supported by microphone adapter")

        if not self._running:
            raise RuntimeError("Microphone not initialized")

        try:
            import sounddevice as sd

            # Record a short chunk (100ms)
            duration_sec = 0.1
            frames = int(self._sample_rate * duration_sec)

            # Record audio
            audio_data = sd.rec(
                frames,
                samplerate=self._sample_rate,
                channels=self._channels,
                device=self._device_id,
                dtype="float32",
            )
            sd.wait()  # Wait for recording to complete

            return SensorReading(
                sensor=SensorType.MICROPHONE,
                value=audio_data.flatten(),  # numpy array, shape (frames,), dtype float32
                timestamp_ms=int(time.time() * 1000),
                accuracy=1.0,
            )

        except Exception as e:
            logger.error(f"Microphone read failed: {e}")
            raise

    async def shutdown(self) -> None:
        """Shutdown microphone."""
        await super().shutdown()

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning(f"Error closing audio stream: {e}")
            finally:
                self._stream = None

        logger.info("✅ ALSA microphone shutdown complete")

    @staticmethod
    def enumerate_devices() -> list[dict[str, Any]]:
        """Enumerate available audio input devices.

        Returns:
            List of device info dicts with keys: id, name, channels, sample_rate
        """
        if not SOUNDDEVICE_AVAILABLE:
            return []

        try:
            import sounddevice as sd

            devices = sd.query_devices()
            if isinstance(devices, dict):
                devices = [devices]

            input_devices = []
            for idx, device in enumerate(devices):
                if device.get("max_input_channels", 0) > 0:
                    input_devices.append(
                        {
                            "id": idx,
                            "name": device["name"],
                            "channels": device["max_input_channels"],
                            "sample_rate": int(device["default_samplerate"]),
                        }
                    )

            return input_devices

        except Exception as e:
            logger.warning(f"Failed to enumerate audio devices: {e}")
            return []


__all__ = ["LinuxMicrophone"]
