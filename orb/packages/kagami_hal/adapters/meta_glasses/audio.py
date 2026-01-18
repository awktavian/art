"""Meta Glasses Audio Adapter — Spatial Audio I/O.

Provides access to the Ray-Ban Meta audio system:
- Microphone array (5-mic spatial audio capture)
- Open-ear speakers (directional audio output)

Audio Features:
- Voice activity detection
- Noise cancellation
- Spatial audio positioning
- Low-latency streaming

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AudioFormat(Enum):
    """Audio encoding format."""

    PCM_16 = "pcm_16"  # 16-bit PCM
    PCM_32 = "pcm_32"  # 32-bit PCM float
    OPUS = "opus"  # Opus codec (compressed)
    AAC = "aac"  # AAC codec


class AudioQuality(Enum):
    """Audio quality presets."""

    LOW = "low"  # 8kHz, mono - voice only
    MEDIUM = "medium"  # 16kHz, mono - clear voice
    HIGH = "high"  # 24kHz, stereo - high fidelity


@dataclass
class OpenEarAudioConfig:
    """Configuration for open-ear speaker output."""

    volume: float = 0.7  # 0.0 - 1.0
    spatial: bool = True  # Enable spatial audio
    priority: int = 5  # 1-10, higher interrupts lower
    ducking: bool = True  # Duck other audio when speaking


@dataclass
class MicrophoneConfig:
    """Configuration for microphone input."""

    quality: AudioQuality = AudioQuality.MEDIUM
    format: AudioFormat = AudioFormat.OPUS
    noise_cancellation: bool = True
    voice_activity_detection: bool = True
    beam_forming: bool = True  # Focus on speaker direction


@dataclass
class AudioBuffer:
    """A buffer of audio samples."""

    timestamp: float
    sample_rate: int
    channels: int
    data: bytes  # Encoded audio data
    format: AudioFormat = AudioFormat.OPUS
    duration_ms: int = 0

    # Voice activity
    is_voice: bool = False
    voice_confidence: float = 0.0

    @property
    def size_bytes(self) -> int:
        """Get buffer size in bytes."""
        return len(self.data)


@dataclass
class SpeechSegment:
    """A segment of detected speech."""

    start_timestamp: float
    end_timestamp: float
    audio_data: bytes
    transcript: str | None = None  # If STT was performed
    confidence: float = 0.0


AudioCallback = Callable[[AudioBuffer], Awaitable[None]]
SpeechCallback = Callable[[SpeechSegment], Awaitable[None]]


class MetaGlassesAudio:
    """Audio adapter for Meta Ray-Ban smart glasses.

    Provides bidirectional audio:
    - Microphone input with VAD and spatial processing
    - Open-ear speaker output for private notifications

    Usage:
        audio = MetaGlassesAudio(protocol)
        await audio.initialize()

        # Listen to microphone
        async for buffer in audio.listen():
            if buffer.is_voice:
                process_voice(buffer)

        # Play audio to glasses
        await audio.speak("Hello Tim", voice="kagami")

        # Play raw audio
        await audio.play(audio_data, sample_rate=24000)
    """

    def __init__(self, protocol: Any = None) -> None:
        """Initialize audio adapter.

        Args:
            protocol: MetaGlassesProtocol instance (optional, can set later)
        """
        self._protocol = protocol
        self._listening = False
        self._mic_config: MicrophoneConfig | None = None
        self._audio_callbacks: list[AudioCallback] = []
        self._speech_callbacks: list[SpeechCallback] = []

        # Audio buffer for listening
        self._audio_queue: asyncio.Queue[AudioBuffer] = asyncio.Queue(maxsize=100)

        # Speech accumulation for VAD
        self._speech_buffers: list[AudioBuffer] = []
        self._speech_start: float | None = None
        self._silence_duration: float = 0.0
        self._speech_timeout: float = 1.5  # Seconds of silence to end speech

    def set_protocol(self, protocol: Any) -> None:
        """Set or update the protocol handler.

        Args:
            protocol: MetaGlassesProtocol instance
        """
        self._protocol = protocol

    async def initialize(self) -> bool:
        """Initialize audio adapter.

        Returns:
            True if initialization successful
        """
        if not self._protocol:
            logger.warning("No protocol set")
            return False

        # Register for audio events
        self._protocol.on_event(self._handle_event)

        logger.info("MetaGlassesAudio initialized")
        return True

    async def start_listening(self, config: MicrophoneConfig | None = None) -> bool:
        """Start microphone input.

        Args:
            config: Microphone configuration

        Returns:
            True if started successfully
        """
        if self._listening:
            logger.warning("Already listening")
            return True

        if not self._protocol or not self._protocol.is_connected:
            logger.error("Glasses not connected")
            return False

        self._mic_config = config or MicrophoneConfig()

        from kagami_hal.adapters.meta_glasses.protocol import GlassesCommand

        result = await self._protocol.send_command(
            GlassesCommand.START_AUDIO,
            params={
                "quality": self._mic_config.quality.value,
                "format": self._mic_config.format.value,
                "noise_cancellation": self._mic_config.noise_cancellation,
                "vad": self._mic_config.voice_activity_detection,
                "beam_forming": self._mic_config.beam_forming,
            },
            wait_response=True,
        )

        if result and result.get("success"):
            self._listening = True
            logger.info(f"Microphone started ({self._mic_config.quality.value})")
            return True

        logger.error("Failed to start microphone")
        return False

    async def stop_listening(self) -> None:
        """Stop microphone input."""
        if not self._listening:
            return

        if self._protocol and self._protocol.is_connected:
            from kagami_hal.adapters.meta_glasses.protocol import GlassesCommand

            await self._protocol.send_command(GlassesCommand.STOP_AUDIO)

        self._listening = False
        self._mic_config = None

        # Flush any pending speech
        await self._flush_speech()

        # Clear audio queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        logger.info("Microphone stopped")

    async def listen(self, config: MicrophoneConfig | None = None) -> AsyncIterator[AudioBuffer]:
        """Stream microphone input as async iterator.

        Args:
            config: Microphone configuration

        Yields:
            AudioBuffer objects
        """
        if not await self.start_listening(config):
            return

        try:
            while self._listening:
                try:
                    buffer = await asyncio.wait_for(self._audio_queue.get(), timeout=5.0)
                    yield buffer
                except TimeoutError:
                    if not self._listening:
                        break
                    continue

        finally:
            await self.stop_listening()

    async def speak(
        self,
        text: str,
        voice: str = "kagami",
        config: OpenEarAudioConfig | None = None,
    ) -> bool:
        """Speak text through open-ear speakers via TTS.

        This sends the text to the Kagami API for TTS synthesis,
        then streams the audio to the glasses.

        Args:
            text: Text to speak
            voice: TTS voice to use
            config: Audio output configuration

        Returns:
            True if speech started
        """
        if not self._protocol or not self._protocol.is_connected:
            logger.error("Glasses not connected")
            return False

        cfg = config or OpenEarAudioConfig()

        # Request TTS synthesis and playback
        # This goes through the companion app which handles TTS
        from kagami_hal.adapters.meta_glasses.protocol import GlassesCommand

        result = await self._protocol.send_command(
            GlassesCommand.PLAY_AUDIO,
            params={
                "type": "tts",
                "text": text,
                "voice": voice,
                "volume": cfg.volume,
                "spatial": cfg.spatial,
                "priority": cfg.priority,
                "ducking": cfg.ducking,
            },
            wait_response=True,
            timeout=30.0,  # TTS may take time
        )

        if result and result.get("success"):
            logger.info(f"Speaking: {text[:50]}...")
            return True

        logger.error("Failed to speak")
        return False

    async def play(
        self,
        audio_data: bytes,
        sample_rate: int = 24000,
        channels: int = 1,
        format: AudioFormat = AudioFormat.PCM_16,
        config: OpenEarAudioConfig | None = None,
    ) -> bool:
        """Play raw audio through open-ear speakers.

        Args:
            audio_data: Raw audio bytes
            sample_rate: Sample rate in Hz
            channels: Number of channels
            format: Audio format
            config: Audio output configuration

        Returns:
            True if playback started
        """
        if not self._protocol or not self._protocol.is_connected:
            logger.error("Glasses not connected")
            return False

        cfg = config or OpenEarAudioConfig()

        import base64

        from kagami_hal.adapters.meta_glasses.protocol import GlassesCommand

        result = await self._protocol.send_command(
            GlassesCommand.PLAY_AUDIO,
            params={
                "type": "raw",
                "data": base64.b64encode(audio_data).decode(),
                "sample_rate": sample_rate,
                "channels": channels,
                "format": format.value,
                "volume": cfg.volume,
                "spatial": cfg.spatial,
                "priority": cfg.priority,
                "ducking": cfg.ducking,
            },
            wait_response=True,
        )

        if result and result.get("success"):
            logger.info(f"Playing {len(audio_data)} bytes of audio")
            return True

        logger.error("Failed to play audio")
        return False

    async def play_notification(
        self,
        sound: str = "notification",
        volume: float = 0.5,
    ) -> bool:
        """Play a notification sound.

        Args:
            sound: Sound name (notification, alert, success, error)
            volume: Volume level 0.0-1.0

        Returns:
            True if played
        """
        if not self._protocol or not self._protocol.is_connected:
            return False

        from kagami_hal.adapters.meta_glasses.protocol import GlassesCommand

        result = await self._protocol.send_command(
            GlassesCommand.PLAY_AUDIO,
            params={
                "type": "notification",
                "sound": sound,
                "volume": volume,
            },
        )

        return result is not None

    def on_audio(self, callback: AudioCallback) -> None:
        """Register audio buffer callback.

        Args:
            callback: Async function to call with audio buffers
        """
        self._audio_callbacks.append(callback)

    def off_audio(self, callback: AudioCallback) -> None:
        """Unregister audio callback.

        Args:
            callback: Previously registered callback
        """
        if callback in self._audio_callbacks:
            self._audio_callbacks.remove(callback)

    def on_speech(self, callback: SpeechCallback) -> None:
        """Register speech segment callback.

        Called when a complete speech segment is detected (voice followed by silence).

        Args:
            callback: Async function to call with speech segments
        """
        self._speech_callbacks.append(callback)

    def off_speech(self, callback: SpeechCallback) -> None:
        """Unregister speech callback.

        Args:
            callback: Previously registered callback
        """
        if callback in self._speech_callbacks:
            self._speech_callbacks.remove(callback)

    async def _handle_event(self, event: Any) -> None:
        """Handle events from protocol."""
        if event.event_type == "audio_buffer":
            await self._handle_audio(event.data)

    async def _handle_audio(self, data: dict[str, Any]) -> None:
        """Handle incoming audio buffer."""
        import time

        audio_data = data.get("audio_data", b"")
        if isinstance(audio_data, str):
            import base64

            try:
                audio_data = base64.b64decode(audio_data)
            except Exception:
                audio_data = b""

        buffer = AudioBuffer(
            timestamp=data.get("timestamp", time.time()),
            sample_rate=data.get("sample_rate", 16000),
            channels=data.get("channels", 1),
            data=audio_data,
            format=AudioFormat(data.get("format", "opus")),
            duration_ms=data.get("duration_ms", 20),
            is_voice=data.get("is_voice", False),
            voice_confidence=data.get("voice_confidence", 0.0),
        )

        # Add to queue for listen() consumers
        try:
            self._audio_queue.put_nowait(buffer)
        except asyncio.QueueFull:
            try:
                self._audio_queue.get_nowait()
                self._audio_queue.put_nowait(buffer)
            except asyncio.QueueEmpty:
                pass

        # Process VAD for speech segments
        await self._process_vad(buffer)

        # Notify audio callbacks
        for callback in self._audio_callbacks:
            try:
                await callback(buffer)
            except Exception as e:
                logger.error(f"Audio callback error: {e}")

    async def _process_vad(self, buffer: AudioBuffer) -> None:
        """Process voice activity detection for speech segmentation."""
        import time

        time.time()

        if buffer.is_voice:
            # Voice detected
            if self._speech_start is None:
                self._speech_start = buffer.timestamp
                self._speech_buffers = []

            self._speech_buffers.append(buffer)
            self._silence_duration = 0.0

        elif self._speech_start is not None:
            # Silence during speech
            self._silence_duration += buffer.duration_ms / 1000.0
            self._speech_buffers.append(buffer)  # Include trailing silence

            if self._silence_duration >= self._speech_timeout:
                # Speech ended, flush segment
                await self._flush_speech()

    async def _flush_speech(self) -> None:
        """Flush accumulated speech buffers as a segment."""
        if not self._speech_buffers or self._speech_start is None:
            self._speech_buffers = []
            self._speech_start = None
            return

        # Combine audio data
        audio_data = b"".join(b.data for b in self._speech_buffers)

        segment = SpeechSegment(
            start_timestamp=self._speech_start,
            end_timestamp=self._speech_buffers[-1].timestamp,
            audio_data=audio_data,
            confidence=max(b.voice_confidence for b in self._speech_buffers),
        )

        self._speech_buffers = []
        self._speech_start = None

        # Notify speech callbacks
        for callback in self._speech_callbacks:
            try:
                await callback(segment)
            except Exception as e:
                logger.error(f"Speech callback error: {e}")

    @property
    def is_listening(self) -> bool:
        """Check if microphone is active."""
        return self._listening

    async def shutdown(self) -> None:
        """Shutdown audio adapter."""
        await self.stop_listening()
        self._audio_callbacks.clear()
        self._speech_callbacks.clear()

        if self._protocol:
            self._protocol.off_event(self._handle_event)

        logger.info("MetaGlassesAudio shutdown")


"""
Mirror
h(x) >= 0. Always.

Audio flows both ways.
I hear what you hear.
You hear what I know.
"""
