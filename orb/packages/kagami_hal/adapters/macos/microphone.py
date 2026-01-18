"""macOS Microphone Sensor via CoreAudio.

Provides streaming audio input on macOS:
- PyAudio (portaudio) for CoreAudio access
- sounddevice as alternative
- 48kHz, 16-bit, mono/stereo
- Async streaming via callbacks

Created: December 15, 2025
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

import numpy as np

from kagami_hal.data_types import SensorReading, SensorType

logger = logging.getLogger(__name__)

# Platform check
MACOS_AVAILABLE = sys.platform == "darwin"

# Try backends
PYAUDIO_AVAILABLE = False
SOUNDDEVICE_AVAILABLE = False
pyaudio = None
sounddevice = None

if MACOS_AVAILABLE:
    try:
        import pyaudio  # type: ignore[no-redef]

        PYAUDIO_AVAILABLE = True
    except ImportError:
        pyaudio = None
        logger.debug("PyAudio not available. Install with: pip install pyaudio")

    try:
        import sounddevice  # type: ignore[no-redef]

        SOUNDDEVICE_AVAILABLE = True
    except ImportError:
        sounddevice = None
        logger.debug("sounddevice not available. Install with: pip install sounddevice")


class MacOSMicrophone:
    """macOS microphone implementation using PyAudio or sounddevice."""

    def __init__(self) -> None:
        """Initialize microphone."""
        self._initialized = False
        self._backend: str | None = None

        # Audio config
        self._sample_rate = 48000
        self._channels = 1
        self._chunk_size = 1024

        # PyAudio backend
        self._pyaudio_instance: Any | None = None
        self._pyaudio_stream: Any | None = None

        # sounddevice backend
        self._sd_stream: Any | None = None

        # Streaming state
        self._streaming = False
        self._stream_queue: asyncio.Queue[np.ndarray] | None = None
        self._permission_granted = False

    async def initialize(
        self,
        sample_rate: int = 48000,
        channels: int = 1,
        chunk_size: int = 1024,
    ) -> bool:
        """Initialize microphone.

        Args:
            sample_rate: Sample rate in Hz (default 48000)
            channels: Number of channels (1=mono, 2=stereo)
            chunk_size: Buffer size in frames

        Returns:
            True if microphone initialized successfully
        """
        if not MACOS_AVAILABLE:
            logger.warning("Microphone only available on macOS")
            return False

        self._sample_rate = sample_rate
        self._channels = channels
        self._chunk_size = chunk_size

        # Check permissions
        if not await self._check_microphone_permission():
            logger.warning(
                "Microphone permission not granted. "
                "Go to System Preferences > Security & Privacy > Microphone"
            )
            return False

        # Try backends
        if PYAUDIO_AVAILABLE:
            if await self._init_pyaudio():
                self._backend = "pyaudio"
                logger.info(
                    f"✅ Microphone initialized via PyAudio: "
                    f"{sample_rate}Hz, {channels}ch, {chunk_size} frames"
                )
                self._initialized = True
                return True

        if SOUNDDEVICE_AVAILABLE:
            if await self._init_sounddevice():
                self._backend = "sounddevice"
                logger.info(
                    f"✅ Microphone initialized via sounddevice: "
                    f"{sample_rate}Hz, {channels}ch, {chunk_size} frames"
                )
                self._initialized = True
                return True

        logger.error("No microphone backend available (need PyAudio or sounddevice)")
        return False

    async def _check_microphone_permission(self) -> bool:
        """Check microphone permission status.

        Returns:
            True if permission granted or not required
        """
        # macOS microphone permission is checked at runtime
        # Assume granted (will fail gracefully if not)
        self._permission_granted = True
        return True

    async def _init_pyaudio(self) -> bool:
        """Initialize PyAudio backend."""
        try:
            import pyaudio

            self._pyaudio_instance = pyaudio.PyAudio()

            # Check default input device
            default_input = self._pyaudio_instance.get_default_input_device_info()
            logger.debug(f"Default input device: {default_input['name']}")

            # Verify support for requested config
            try:
                is_supported = self._pyaudio_instance.is_format_supported(
                    self._sample_rate,
                    input_device=default_input["index"],
                    input_channels=self._channels,
                    input_format=pyaudio.paInt16,
                )
                if not is_supported:
                    logger.warning(
                        f"Format not supported: {self._sample_rate}Hz, {self._channels}ch"
                    )
            except Exception:
                # Some devices don't report format support accurately
                pass

            return True

        except Exception as e:
            logger.error(f"Failed to initialize PyAudio: {e}")
            return False

    async def _init_sounddevice(self) -> bool:
        """Initialize sounddevice backend."""
        try:
            import sounddevice as sd

            # Check default input device
            default_input = sd.query_devices(kind="input")
            logger.debug(f"Default input device: {default_input['name']}")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize sounddevice: {e}")
            return False

    async def record_chunk(self) -> np.ndarray | None:
        """Record a single audio chunk.

        Returns:
            numpy array of shape (chunk_size, channels) as float32, or None on error
        """
        if not self._initialized:
            raise RuntimeError("Microphone not initialized")

        if self._backend == "pyaudio":
            return await self._record_pyaudio()
        elif self._backend == "sounddevice":
            return await self._record_sounddevice()
        else:
            raise RuntimeError(f"Unknown backend: {self._backend}")

    async def _record_pyaudio(self) -> np.ndarray | None:
        """Record chunk using PyAudio."""
        try:
            import pyaudio

            if self._pyaudio_instance is None:
                return None

            # Open stream for single read
            stream = self._pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=self._channels,
                rate=self._sample_rate,
                input=True,
                frames_per_buffer=self._chunk_size,
            )

            # Read chunk
            data = stream.read(self._chunk_size, exception_on_overflow=False)
            stream.close()

            # Convert to numpy
            audio_data = np.frombuffer(data, dtype=np.int16)

            # Reshape for channels
            if self._channels > 1:
                audio_data = audio_data.reshape(-1, self._channels)

            # Convert to float32 [-1.0, 1.0]
            audio_float = audio_data.astype(np.float32) / 32768.0

            return audio_float

        except Exception as e:
            logger.error(f"Failed to record chunk: {e}")
            return None

    async def _record_sounddevice(self) -> np.ndarray | None:
        """Record chunk using sounddevice."""
        try:
            import sounddevice as sd

            # Record chunk
            audio_data = sd.rec(
                self._chunk_size,
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype=np.float32,
            )
            sd.wait()  # Wait for recording to complete

            return audio_data

        except Exception as e:
            logger.error(f"Failed to record chunk: {e}")
            return None

    async def start_streaming(self) -> None:
        """Start streaming audio from microphone.

        Use stream_audio() to receive chunks.
        """
        if not self._initialized:
            raise RuntimeError("Microphone not initialized")

        if self._streaming:
            logger.warning("Microphone already streaming")
            return

        self._streaming = True
        self._stream_queue = asyncio.Queue(maxsize=10)

        if self._backend == "pyaudio":
            await self._start_pyaudio_stream()
        elif self._backend == "sounddevice":
            await self._start_sounddevice_stream()

        logger.info("🎤 Microphone streaming started")

    async def _start_pyaudio_stream(self) -> None:
        """Start PyAudio streaming."""
        import pyaudio

        def callback(in_data: bytes, frame_count: int, time_info: dict, status: int) -> tuple:
            """Audio callback (runs in separate thread)."""
            if status:
                logger.warning(f"PyAudio callback status: {status}")

            # Convert to numpy
            audio_data = np.frombuffer(in_data, dtype=np.int16)

            # Reshape for channels
            if self._channels > 1:
                audio_data = audio_data.reshape(-1, self._channels)

            # Convert to float32
            audio_float = audio_data.astype(np.float32) / 32768.0

            # Put in queue (non-blocking)
            if self._stream_queue is not None:
                try:
                    self._stream_queue.put_nowait(audio_float)
                except asyncio.QueueFull:
                    logger.debug("Stream queue full, dropping frame")

            return (in_data, pyaudio.paContinue)

        if self._pyaudio_instance is None:
            return

        self._pyaudio_stream = self._pyaudio_instance.open(
            format=pyaudio.paInt16,
            channels=self._channels,
            rate=self._sample_rate,
            input=True,
            frames_per_buffer=self._chunk_size,
            stream_callback=callback,
        )

        self._pyaudio_stream.start_stream()

    async def _start_sounddevice_stream(self) -> None:
        """Start sounddevice streaming."""
        import sounddevice as sd

        def callback(indata: Any, frames: int, time: Any, status: Any) -> None:
            """Audio callback (runs in separate thread)."""
            if status:
                logger.warning(f"sounddevice callback status: {status}")

            # Copy data (indata is a view)
            audio_data = indata.copy()

            # Put in queue (non-blocking)
            if self._stream_queue is not None:
                try:
                    self._stream_queue.put_nowait(audio_data)
                except asyncio.QueueFull:
                    logger.debug("Stream queue full, dropping frame")

        self._sd_stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            blocksize=self._chunk_size,
            dtype=np.float32,
            callback=callback,
        )

        self._sd_stream.start()

    async def stop_streaming(self) -> None:
        """Stop audio streaming."""
        if not self._streaming:
            return

        self._streaming = False

        if self._pyaudio_stream:
            self._pyaudio_stream.stop_stream()
            self._pyaudio_stream.close()
            self._pyaudio_stream = None

        if self._sd_stream:
            self._sd_stream.stop()
            self._sd_stream.close()
            self._sd_stream = None

        self._stream_queue = None
        logger.info("🎤 Microphone streaming stopped")

    async def stream_audio(self) -> asyncio.AsyncIterator[np.ndarray]:  # type: ignore[name-defined]
        """Stream audio chunks as async iterator.

        Yields:
            numpy arrays of shape (chunk_size, channels) as float32
        """
        if not self._streaming or not self._stream_queue:
            raise RuntimeError("Microphone not streaming. Call start_streaming() first.")

        while self._streaming:
            try:
                # Wait for next chunk with timeout
                chunk = await asyncio.wait_for(self._stream_queue.get(), timeout=1.0)
                yield chunk
            except TimeoutError:
                # No data available, check if still streaming
                if not self._streaming:
                    break
                continue

    async def read_sensor(self) -> SensorReading:
        """Read microphone as sensor (for HAL sensor interface compatibility).

        Returns:
            SensorReading with audio chunk as value
        """
        chunk = await self.record_chunk()

        if chunk is None:
            raise RuntimeError("Failed to record audio chunk")

        import time

        return SensorReading(
            sensor=SensorType.MICROPHONE,
            value=chunk,
            timestamp_ms=int(time.time() * 1000),
            accuracy=1.0 if chunk is not None else 0.0,
        )

    def get_config(self) -> dict[str, Any]:
        """Get current microphone configuration.

        Returns:
            Dict with sample_rate, channels, chunk_size
        """
        return {
            "sample_rate": self._sample_rate,
            "channels": self._channels,
            "chunk_size": self._chunk_size,
            "backend": self._backend,
        }

    async def shutdown(self) -> None:
        """Shutdown microphone."""
        await self.stop_streaming()

        if self._pyaudio_instance:
            self._pyaudio_instance.terminate()
            self._pyaudio_instance = None

        self._initialized = False
        logger.info("✅ Microphone shutdown")


__all__ = ["PYAUDIO_AVAILABLE", "SOUNDDEVICE_AVAILABLE", "MacOSMicrophone"]
