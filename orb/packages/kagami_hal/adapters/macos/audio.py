"""macOS CoreAudio Adapter.

Implements AudioController for macOS using native audio.
Uses afplay for reliable playback (handles sample rate conversion automatically).

Created: November 10, 2025
Updated: December 6, 2025 - Use afplay for reliable cross-format playback
"""

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import AudioConfig, AudioFormat

logger = logging.getLogger(__name__)

# Check if running on macOS
MACOS_AVAILABLE = sys.platform == "darwin"

# PyAudio is optional - we prefer afplay for output
PYAUDIO_AVAILABLE = False
pyaudio = None
if MACOS_AVAILABLE:
    try:
        import pyaudio  # type: ignore[no-redef]

        PYAUDIO_AVAILABLE = True
    except ImportError:
        pyaudio = None
        logger.debug("PyAudio not available. Install with: pip install pyaudio")


from kagami_hal.adapters.common import VolumeMixin


class MacOSCoreAudio(VolumeMixin):
    """macOS audio implementation using native afplay.

    Uses afplay for output (handles sample rate conversion automatically).
    Uses PyAudio for input if available.
    """

    def __init__(self) -> None:
        """Initialize audio adapter."""
        VolumeMixin.__init__(self)
        self._py_audio: Any | None = None
        self._stream_in: Any | None = None
        self._config: AudioConfig | None = None
        self._temp_dir = Path(tempfile.gettempdir()) / "kagami_audio"
        self._temp_dir.mkdir(exist_ok=True)
        self._playback_process: subprocess.Popen | None = None
        # self._volume managed by VolumeMixin

    async def initialize(self, config: AudioConfig) -> bool:
        """Initialize audio."""
        self._config = config

        # afplay is always available on macOS - no dependencies needed for output
        if not MACOS_AVAILABLE:
            if is_test_mode():
                logger.info("macOS audio not available (wrong platform)")
                return False
            raise RuntimeError("macOS audio only available on macOS")

        # Try to initialize PyAudio for input (optional)
        if PYAUDIO_AVAILABLE:
            try:
                import pyaudio

                self._py_audio = pyaudio.PyAudio()

                # Determine format
                if config.format == AudioFormat.PCM_16:
                    pa_format = pyaudio.paInt16
                elif config.format == AudioFormat.FLOAT_32:
                    pa_format = pyaudio.paFloat32
                else:
                    pa_format = pyaudio.paInt16

                # Try to open input stream
                try:
                    self._stream_in = self._py_audio.open(
                        format=pa_format,
                        channels=config.channels,
                        rate=config.sample_rate,
                        input=True,
                        frames_per_buffer=config.buffer_size,
                    )
                    logger.info("Audio input available via PyAudio")
                except OSError as e:
                    logger.info(f"Audio input unavailable: {e}")
                    self._stream_in = None
            except Exception as e:
                logger.debug(f"PyAudio init failed (input disabled): {e}")

        logger.info(
            f"✅ macOS audio initialized: {config.sample_rate}Hz, "
            f"{config.channels}ch (output via afplay)"
        )
        return True

    async def play(self, buffer: bytes) -> None:
        """Play raw PCM audio buffer using afplay.

        Writes to temp WAV file and plays with afplay (handles all format conversion).
        """
        if not self._config:
            raise RuntimeError("Audio not initialized") from None

        await self.play_pcm_bytes(buffer, self._config.sample_rate, self._config.channels)

    async def play_pcm(
        self,
        audio_data: Any,
        sample_rate: int = 24000,
        channels: int = 1,
        blocking: bool = True,
    ) -> None:
        """Play PCM audio using macOS native afplay.

        Args:
            audio_data: numpy float32 or int16 array
            sample_rate: Sample rate of audio
            channels: Number of channels
            blocking: Wait for playback to complete
        """
        import wave

        import numpy as np

        # Convert to numpy if needed
        if not isinstance(audio_data, np.ndarray):
            audio_data = np.array(audio_data)

        # Convert float32 to int16
        if audio_data.dtype in (np.float32, np.float64):
            max_val = np.abs(audio_data).max()
            if max_val > 0:
                audio_data = audio_data / max(max_val, 1.0)
            audio_data = (audio_data * 32767).astype(np.int16)

        # Write to temp WAV file
        temp_wav = self._temp_dir / f"play_{id(audio_data)}.wav"
        with wave.open(str(temp_wav), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)  # int16
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data.tobytes())

        try:
            # Play with afplay (handles sample rate conversion automatically)
            if blocking:
                subprocess.run(["afplay", str(temp_wav)], check=True)
            else:
                self._playback_process = subprocess.Popen(["afplay", str(temp_wav)])
        finally:
            # Clean up temp file
            if blocking and temp_wav.exists():
                temp_wav.unlink()

    async def play_pcm_bytes(
        self,
        audio_bytes: bytes,
        sample_rate: int = 24000,
        channels: int = 1,
        blocking: bool = True,
    ) -> None:
        """Play raw PCM bytes using afplay."""
        import wave

        temp_wav = self._temp_dir / f"play_{hash(audio_bytes) % 100000}.wav"
        with wave.open(str(temp_wav), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)  # int16
            wf.setframerate(sample_rate)
            wf.writeframes(audio_bytes)

        try:
            if blocking:
                subprocess.run(["afplay", str(temp_wav)], check=True)
            else:
                self._playback_process = subprocess.Popen(["afplay", str(temp_wav)])
        finally:
            if blocking and temp_wav.exists():
                temp_wav.unlink()

    async def play_wav(self, wav_path: str, blocking: bool = True) -> None:
        """Play a WAV file directly using afplay."""
        if blocking:
            subprocess.run(["afplay", wav_path], check=True)
        else:
            self._playback_process = subprocess.Popen(["afplay", wav_path])

    async def stream_audio(
        self,
        audio_iterator: Iterator,
        sample_rate: int = 24000,
        channels: int = 1,
    ) -> None:
        """Stream audio chunks.

        Note: For streaming, we accumulate chunks and play.
        True low-latency streaming would require AudioQueue or AVAudioEngine.
        """
        import numpy as np

        chunks = []
        for chunk in audio_iterator:
            if chunk is not None and isinstance(chunk, np.ndarray):
                chunks.append(chunk)

        if chunks:
            audio_data = np.concatenate(chunks)
            await self.play_pcm(audio_data, sample_rate, channels)

    async def record(self, duration_ms: int) -> bytes:
        """Record audio."""
        if not self._stream_in or not self._config:
            raise RuntimeError("Audio not initialized") from None

        try:
            # Calculate frames to record
            frames = int(self._config.sample_rate * duration_ms / 1000)

            # Record
            data = self._stream_in.read(frames)

            return data

        except Exception as e:
            logger.error(f"Recording error: {e}")
            return b""

    async def set_volume(self, level: float) -> None:
        """Set volume via osascript."""
        self._volume = max(0.0, min(1.0, level))

        # Volume 0-100
        vol_val = int(self._volume * 100)

        try:
            import subprocess

            # 'set volume output volume X'
            subprocess.run(
                ["osascript", "-e", f"set volume output volume {vol_val}"],
                check=False,
                capture_output=True,
                timeout=1,
            )
            logger.debug(f"Volume set: {level:.1%} via osascript")
        except Exception as e:
            logger.warning(f"Failed to set volume: {e}")

    async def get_volume(self) -> float:
        """Get current volume via osascript."""
        try:
            import subprocess

            # 'output volume of (get volume settings)'
            result = subprocess.run(
                ["osascript", "-e", "output volume of (get volume settings)"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0:
                vol_val = int(result.stdout.strip())
                self._volume = vol_val / 100.0
                return self._volume
        except Exception as e:
            logger.warning(f"Failed to get volume: {e}")

        return self._volume

    async def shutdown(self) -> None:
        """Shutdown audio."""
        # Stop any playing audio
        if self._playback_process:
            self._playback_process.terminate()
            self._playback_process = None

        # Close input stream
        if self._stream_in:
            self._stream_in.stop_stream()
            self._stream_in.close()
            self._stream_in = None

        if self._py_audio:
            self._py_audio.terminate()
            self._py_audio = None

        # Clean up temp files
        try:
            import shutil

            if self._temp_dir.exists():
                shutil.rmtree(self._temp_dir, ignore_errors=True)
        except Exception:
            pass

        logger.info("✅ macOS audio shutdown")
