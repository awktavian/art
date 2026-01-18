"""Windows WASAPI Microphone Sensor.

Implements low-latency audio input using WASAPI (Windows Audio Session API).

Uses sounddevice library with WASAPI backend for minimal latency.

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import SensorReading, SensorType

logger = logging.getLogger(__name__)

WINDOWS_AVAILABLE = sys.platform == "win32"
SOUNDDEVICE_AVAILABLE = False

if WINDOWS_AVAILABLE:
    try:
        import sounddevice as sd

        SOUNDDEVICE_AVAILABLE = True
    except ImportError:
        logger.warning("sounddevice not available - install: pip install sounddevice numpy")


class WindowsWASAPIMicrophone:
    """Windows WASAPI microphone implementation.

    Provides low-latency audio input via WASAPI.
    """

    def __init__(self, device_id: int | None = None):
        """Initialize WASAPI microphone.

        Args:
            device_id: Optional device ID (None = default input)
        """
        self._device_id = device_id
        self._sample_rate = 48000
        self._channels = 1
        self._dtype = "int16"
        self._blocksize = 2048
        self._stream: Any | None = None

    async def initialize(self, config: dict[str, Any] | None = None) -> bool:
        """Initialize microphone with WASAPI.

        Args:
            config: Optional config with sample_rate, channels, blocksize

        Returns:
            True if initialization successful
        """
        if not WINDOWS_AVAILABLE:
            if is_test_mode():
                logger.info(
                    "Windows WASAPI microphone not available (wrong platform), gracefully degrading"
                )
                return False
            raise RuntimeError("Windows WASAPI microphone only available on Windows")

        if not SOUNDDEVICE_AVAILABLE:
            if is_test_mode():
                logger.info("sounddevice not available, gracefully degrading")
                return False
            raise RuntimeError("sounddevice not available. Install: pip install sounddevice numpy")

        try:
            # Parse config
            if config:
                self._sample_rate = config.get("sample_rate", 48000)
                self._channels = config.get("channels", 1)
                self._blocksize = config.get("blocksize", 2048)
                self._dtype = config.get("dtype", "int16")

            # Configure sounddevice defaults
            sd.default.samplerate = self._sample_rate
            sd.default.channels = self._channels
            sd.default.dtype = self._dtype
            sd.default.device = self._device_id

            # Test device access
            device_info = sd.query_devices(self._device_id, "input")

            logger.info(
                f"✅ WASAPI microphone initialized: {device_info['name']} "
                f"({self._sample_rate}Hz, {self._channels}ch)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize WASAPI microphone: {e}", exc_info=True)
            return False

    async def read(self, duration_ms: int = 100) -> SensorReading:
        """Record audio chunk.

        Args:
            duration_ms: Recording duration in milliseconds

        Returns:
            SensorReading with numpy audio array in value field

        Raises:
            RuntimeError: If microphone not initialized or recording fails
        """
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError("Microphone not initialized")

        try:
            # Calculate frames
            frames = int(self._sample_rate * duration_ms / 1000)

            # Record (blocking)
            recording = sd.rec(
                frames,
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype=self._dtype,
                device=self._device_id,
            )
            sd.wait()

            return SensorReading(
                sensor=SensorType.MICROPHONE,
                value=recording,  # numpy array (frames, channels)
                timestamp_ms=int(time.time() * 1000),
                accuracy=1.0,
            )

        except Exception as e:
            logger.error(f"Microphone read error: {e}")
            raise RuntimeError(f"Recording failed: {e}") from e

    async def record_stream(self, duration_ms: int) -> bytes:
        """Record audio and return as raw bytes.

        Args:
            duration_ms: Recording duration in milliseconds

        Returns:
            Raw PCM audio bytes
        """
        try:
            reading = await self.read(duration_ms)
            audio_array = reading.value
            return audio_array.tobytes()

        except Exception as e:
            logger.error(f"Stream recording error: {e}")
            return b""

    async def start_stream(self) -> None:
        """Start continuous audio stream.

        Use with callback for real-time processing.
        """
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError("Microphone not initialized")

        try:
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype=self._dtype,
                blocksize=self._blocksize,
                device=self._device_id,
            )
            self._stream.start()
            logger.info("Audio stream started")

        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            raise

    async def stop_stream(self) -> None:
        """Stop continuous audio stream."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            logger.info("Audio stream stopped")

    async def get_capabilities(self) -> dict[str, Any]:
        """Get microphone capabilities.

        Returns:
            Dict with sample rates, channels, latency info
        """
        if not SOUNDDEVICE_AVAILABLE:
            return {}

        try:
            device_info = sd.query_devices(self._device_id, "input")
            return {
                "name": device_info["name"],
                "hostapi": sd.query_hostapis(device_info["hostapi"])["name"],
                "max_input_channels": device_info["max_input_channels"],
                "default_samplerate": device_info["default_samplerate"],
                "default_low_input_latency": device_info["default_low_input_latency"],
                "default_high_input_latency": device_info["default_high_input_latency"],
            }

        except Exception as e:
            logger.error(f"Failed to get capabilities: {e}")
            return {}

    async def shutdown(self) -> None:
        """Release microphone resources."""
        if self._stream:
            await self.stop_stream()

        logger.info("✅ WASAPI microphone shutdown")

    @staticmethod
    def enumerate_devices() -> list[dict[str, Any]]:
        """Enumerate available WASAPI input devices.

        Returns:
            List of device info dicts
        """
        if not SOUNDDEVICE_AVAILABLE:
            return []

        try:
            devices = sd.query_devices()
            input_devices = []

            for i, device in enumerate(devices):
                if device["max_input_channels"] > 0:
                    input_devices.append(
                        {
                            "id": i,
                            "name": device["name"],
                            "hostapi": sd.query_hostapis(device["hostapi"])["name"],
                            "channels": device["max_input_channels"],
                            "default_samplerate": device["default_samplerate"],
                        }
                    )

            return input_devices

        except Exception as e:
            logger.error(f"Failed to enumerate devices: {e}")
            return []
