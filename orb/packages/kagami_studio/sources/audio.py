"""Audio Source — Audio input capture."""

from __future__ import annotations

import asyncio
import logging

import numpy as np

from kagami_studio.sources.base import Source, SourceState, SourceType

logger = logging.getLogger(__name__)


class AudioSource(Source):
    """Audio input source using PyAudio."""

    def __init__(
        self,
        source_id: str,
        name: str,
        device_id: int = 0,
        sample_rate: int = 48000,
        channels: int = 2,
        chunk_size: int = 1024,
    ):
        super().__init__(source_id, name, SourceType.AUDIO)
        self.device_id = device_id
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size

        self._stream = None
        self._audio_buffer: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._task = None

    async def start(self) -> None:
        """Start audio capture."""
        self.state = SourceState.STARTING

        try:
            import pyaudio

            self._pa = pyaudio.PyAudio()

            self._stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_id if self.device_id >= 0 else None,
                frames_per_buffer=self.chunk_size,
            )

            # Start capture loop
            self._task = asyncio.create_task(self._capture_loop())
            self.state = SourceState.ACTIVE

            logger.info(f"Audio capture started: {self.sample_rate}Hz, {self.channels}ch")

        except ImportError:
            logger.warning("PyAudio not available, audio source disabled")
            self.state = SourceState.ERROR
        except Exception as e:
            logger.error(f"Audio capture failed: {e}")
            self.state = SourceState.ERROR

    async def stop(self) -> None:
        """Stop audio capture."""
        self.state = SourceState.INACTIVE

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None

        if hasattr(self, "_pa") and self._pa:
            self._pa.terminate()

    async def _capture_loop(self) -> None:
        """Continuous capture loop."""
        while self.state == SourceState.ACTIVE:
            try:
                data = self._stream.read(self.chunk_size, exception_on_overflow=False)
                samples = np.frombuffer(data, dtype=np.int16)

                # Try to put in buffer, drop if full
                try:
                    self._audio_buffer.put_nowait(samples)
                except asyncio.QueueFull:
                    pass

            except Exception as e:
                logger.error(f"Audio capture error: {e}")

            await asyncio.sleep(0.001)  # Small sleep to prevent busy loop

    async def get_frame(self) -> np.ndarray | None:
        """Not applicable for audio source."""
        return None

    async def get_audio(self) -> np.ndarray | None:
        """Get current audio samples."""
        try:
            return self._audio_buffer.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def get_level(self) -> float:
        """Get current audio level (0.0 - 1.0)."""
        try:
            samples = self._audio_buffer.get_nowait()
            # Put it back
            try:
                self._audio_buffer.put_nowait(samples)
            except asyncio.QueueFull:
                pass
            # Calculate RMS level
            rms = np.sqrt(np.mean(samples.astype(float) ** 2))
            return min(1.0, rms / 32768)
        except asyncio.QueueEmpty:
            return 0.0
