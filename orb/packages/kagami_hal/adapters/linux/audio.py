"""Linux Audio Adapter.

Implements audio I/O for Linux via ALSA/PulseAudio using sounddevice.

Created: December 15, 2025
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import AudioConfig, AudioFormat

logger = logging.getLogger(__name__)

# Lazy ALSA check (cached after first call)
_alsa_available_cache: bool | None = None


def _check_alsa_available() -> bool:
    """Check ALSA availability (lazy, cached)."""
    global _alsa_available_cache
    if _alsa_available_cache is None:
        _alsa_available_cache = sys.platform.startswith("linux") and Path("/proc/asound").exists()
    return _alsa_available_cache


# Check for sounddevice and numpy
SOUNDDEVICE_AVAILABLE = importlib.util.find_spec("sounddevice") is not None
NUMPY_AVAILABLE = importlib.util.find_spec("numpy") is not None

# Import if available
if SOUNDDEVICE_AVAILABLE:
    import sounddevice as sd  # noqa: F401

if NUMPY_AVAILABLE:
    import numpy as np  # noqa: F401


class LinuxAudio:
    """Linux audio implementation using sounddevice.

    Supports ALSA and PulseAudio backends automatically.
    Optimized for low-latency streaming playback.
    """

    def __init__(self) -> None:
        """Initialize audio adapter."""
        self._initialized = False
        self._config: AudioConfig | None = None
        self._output_stream: Any = None
        self._input_stream: Any = None
        self._volume = 0.8
        self._stream_queue: Any = None  # For streaming playback
        self._stream_thread: Any = None
        self._streaming = False

    async def initialize(self, config: AudioConfig | None = None) -> bool:
        """Initialize audio.

        Args:
            config: Audio configuration (optional, uses defaults if None)

        Returns:
            True if initialization successful
        """
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

        if not NUMPY_AVAILABLE:
            if is_test_mode():
                logger.info("numpy not available")
                return False
            raise RuntimeError("numpy not available. Install: pip install numpy")

        # Use provided config or create default
        if config is None:
            config = AudioConfig(
                sample_rate=24000,
                channels=1,
                format=AudioFormat.PCM_16,
                buffer_size=1024,
            )

        self._config = config

        try:
            import sounddevice as sd

            # Query available devices
            devices = sd.query_devices()
            if isinstance(devices, dict):
                devices = [devices]

            # Check for output and input devices
            has_output = any(d.get("max_output_channels", 0) > 0 for d in devices)
            has_input = any(d.get("max_input_channels", 0) > 0 for d in devices)

            if not has_output:
                logger.warning("No audio output devices found")
                return False

            self._initialized = True

            # Get default device info
            default_output = sd.query_devices(kind="output")
            logger.info(
                f"✅ Linux audio initialized: {config.sample_rate}Hz, "
                f"{config.channels}ch (device: {default_output['name']})"
            )
            logger.debug(f"Input available: {has_input}")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize audio: {e}", exc_info=True)
            return False

    async def play(self, buffer: bytes) -> None:
        """Play audio buffer.

        Args:
            buffer: Raw PCM audio data
        """
        if not self._initialized or not self._config:
            raise RuntimeError("Audio not initialized")

        try:
            import numpy as np
            import sounddevice as sd

            # Convert bytes to numpy array based on format
            if self._config.format == AudioFormat.PCM_16:
                audio_data = np.frombuffer(buffer, dtype=np.int16)
                # Convert to float32 for sounddevice
                audio_data = audio_data.astype(np.float32) / 32768.0  # type: ignore[assignment]
            elif self._config.format == AudioFormat.FLOAT_32:
                audio_data = np.frombuffer(buffer, dtype=np.float32)
            else:
                raise RuntimeError(f"Unsupported audio format: {self._config.format}")

            # Reshape for channels
            if self._config.channels > 1:
                audio_data = audio_data.reshape(-1, self._config.channels)

            # Apply volume
            audio_data = audio_data * self._volume  # type: ignore[assignment]

            # Play audio (blocking)
            sd.play(audio_data, samplerate=self._config.sample_rate)
            sd.wait()

        except Exception as e:
            logger.error(f"Audio playback failed: {e}")
            raise

    async def play_pcm(
        self,
        audio_data: Any,
        sample_rate: int = 24000,
        channels: int = 1,
        blocking: bool = True,
    ) -> None:
        """Play PCM audio with minimal latency.

        Args:
            audio_data: numpy float32 or int16 array
            sample_rate: Sample rate of audio
            channels: Number of channels
            blocking: Wait for playback to complete
        """
        if not SOUNDDEVICE_AVAILABLE or not NUMPY_AVAILABLE:
            raise RuntimeError("sounddevice/numpy not available")

        import numpy as np
        import sounddevice as sd

        # Convert to numpy if needed
        if not isinstance(audio_data, np.ndarray):
            audio_data = np.array(audio_data)

        # Ensure float32 for sounddevice
        if audio_data.dtype == np.int16:
            audio_data = audio_data.astype(np.float32) / 32768.0
        elif audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        # Apply volume
        audio_data = audio_data * self._volume

        # Reshape for channels if needed
        if channels > 1 and audio_data.ndim == 1:
            audio_data = audio_data.reshape(-1, channels)

        sd.play(audio_data, samplerate=sample_rate)
        if blocking:
            sd.wait()

    async def play_pcm_streaming(
        self,
        audio_chunks: Any,
        sample_rate: int = 44100,
        channels: int = 1,
        buffer_size: int = 2048,
    ) -> None:
        """Stream PCM audio chunks with minimal latency.

        Uses a callback-based approach for true streaming.

        Args:
            audio_chunks: Async iterator yielding numpy float32 arrays
            sample_rate: Sample rate of audio
            channels: Number of channels
            buffer_size: Buffer size in samples (lower = less latency)
        """
        if not SOUNDDEVICE_AVAILABLE or not NUMPY_AVAILABLE:
            raise RuntimeError("sounddevice/numpy not available")

        import asyncio
        import queue

        import numpy as np
        import sounddevice as sd

        # Create a thread-safe queue for audio chunks
        audio_queue: queue.Queue = queue.Queue(maxsize=16)
        finished = asyncio.Event()

        def audio_callback(outdata: Any, frames: int, time_info: Any, status: Any) -> None:
            """Callback for streaming playback."""
            if status:
                logger.debug(f"Audio stream status: {status}")

            try:
                data = audio_queue.get_nowait()
                if data is None:
                    raise queue.Empty()
                # Pad or truncate to match frame size
                if len(data) < frames:
                    data = np.pad(data, (0, frames - len(data)))
                elif len(data) > frames:
                    # Put back the remainder
                    remainder = data[frames:]
                    data = data[:frames]
                    try:
                        audio_queue.put_nowait(remainder)
                    except queue.Full:
                        pass
                outdata[:, 0] = data[:frames] * self._volume
            except queue.Empty:
                outdata.fill(0)

        # Start the output stream
        stream = sd.OutputStream(
            samplerate=sample_rate,
            channels=channels,
            blocksize=buffer_size,
            callback=audio_callback,
            dtype=np.float32,
        )

        async def feed_audio() -> None:
            """Feed audio chunks to the queue."""
            try:
                async for chunk in audio_chunks:
                    if chunk is not None and len(chunk) > 0:
                        # Convert to float32 if needed
                        if chunk.dtype != np.float32:
                            chunk = chunk.astype(np.float32)
                        # Wait for space in queue
                        while audio_queue.full():
                            await asyncio.sleep(0.001)
                        audio_queue.put(chunk)
                # Signal end
                audio_queue.put(None)
            finally:
                finished.set()

        try:
            stream.start()
            # Feed audio in background
            feed_task = asyncio.create_task(feed_audio())
            await finished.wait()
            await feed_task
            # Wait for queue to drain
            while not audio_queue.empty():
                await asyncio.sleep(0.01)
            # Small delay to let final buffer play
            await asyncio.sleep(buffer_size / sample_rate)
        finally:
            stream.stop()
            stream.close()

    async def record(self, duration_ms: int) -> bytes:
        """Record audio.

        Args:
            duration_ms: Recording duration in milliseconds

        Returns:
            Raw PCM audio data
        """
        if not self._initialized or not self._config:
            raise RuntimeError("Audio not initialized")

        try:
            import numpy as np
            import sounddevice as sd

            # Calculate frames
            duration_sec = duration_ms / 1000.0
            frames = int(self._config.sample_rate * duration_sec)

            # Record audio
            audio_data = sd.rec(
                frames,
                samplerate=self._config.sample_rate,
                channels=self._config.channels,
                dtype="float32",
            )
            sd.wait()

            # Convert to bytes based on format
            if self._config.format == AudioFormat.PCM_16:
                # Convert float32 to int16
                audio_data = (audio_data * 32768.0).astype(np.int16)
                return audio_data.tobytes()
            elif self._config.format == AudioFormat.FLOAT_32:
                return audio_data.tobytes()
            else:
                raise RuntimeError(f"Unsupported audio format: {self._config.format}")

        except Exception as e:
            logger.error(f"Audio recording failed: {e}")
            raise

    async def set_volume(self, level: float) -> None:
        """Set volume.

        Args:
            level: Volume level 0.0-1.0
        """
        self._volume = max(0.0, min(1.0, level))
        logger.debug(f"Volume set to {self._volume:.1%}")

        # Try to set system volume via amixer (ALSA)
        try:
            import subprocess

            volume_percent = int(self._volume * 100)
            subprocess.run(
                ["amixer", "sset", "Master", f"{volume_percent}%"],
                capture_output=True,
                timeout=1,
            )
        except Exception as e:
            logger.debug(f"Failed to set system volume: {e}")

    async def get_volume(self) -> float:
        """Get current volume.

        Returns:
            Volume level 0.0-1.0
        """
        # Try to read system volume via amixer
        try:
            import re
            import subprocess

            result = subprocess.run(
                ["amixer", "sget", "Master"],
                capture_output=True,
                text=True,
                timeout=1,
            )

            if result.returncode == 0:
                # Parse output like "[80%]"
                match = re.search(r"\[(\d+)%\]", result.stdout)
                if match:
                    volume_percent = int(match.group(1))
                    self._volume = volume_percent / 100.0

        except Exception as e:
            logger.debug(f"Failed to read system volume: {e}")

        return self._volume

    async def shutdown(self) -> None:
        """Shutdown audio."""
        self._initialized = False

        # Stop any playing audio
        try:
            if SOUNDDEVICE_AVAILABLE:
                import sounddevice as sd

                sd.stop()
        except Exception:
            pass

        if self._output_stream:
            try:
                self._output_stream.close()
            except Exception:
                pass
            self._output_stream = None

        if self._input_stream:
            try:
                self._input_stream.close()
            except Exception:
                pass
            self._input_stream = None

        logger.info("✅ Linux audio shutdown complete")

    @staticmethod
    def enumerate_devices() -> list[dict[str, Any]]:
        """Enumerate available audio devices.

        Returns:
            List of device info dicts with keys: id, name, inputs, outputs, sample_rate
        """
        if not SOUNDDEVICE_AVAILABLE:
            return []

        try:
            import sounddevice as sd

            devices = sd.query_devices()
            if isinstance(devices, dict):
                devices = [devices]

            device_list = []
            for idx, device in enumerate(devices):
                device_list.append(
                    {
                        "id": idx,
                        "name": device["name"],
                        "inputs": device["max_input_channels"],
                        "outputs": device["max_output_channels"],
                        "sample_rate": int(device["default_samplerate"]),
                    }
                )

            return device_list

        except Exception as e:
            logger.warning(f"Failed to enumerate audio devices: {e}")
            return []


__all__ = ["LinuxAudio"]
