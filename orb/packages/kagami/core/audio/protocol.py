"""Low-Latency Audio Protocol.

Wire format for ultra-low-latency audio delivery across Kagami ecosystem.

PROTOCOL OVERVIEW:
==================

Three delivery modes optimized for different latency requirements:

1. EARCON (name-based, <20ms)
   - Client pre-caches all earcons at startup
   - Server sends only event name
   - Client plays from local cache
   - Best for: notifications, confirmations, alerts

2. AUDIO_EVENT (Redis PubSub, <50ms)
   - Server publishes audio URL/data via Redis
   - All subscribed clients receive immediately
   - Supports base64-encoded audio for small files
   - Best for: TTS responses, generated audio

3. STREAM (WebSocket chunked, <100ms start)
   - Real-time chunked audio streaming
   - 20ms audio frames (Opus/PCM)
   - Client starts playing after first chunk
   - Best for: long audio, real-time generation

WIRE FORMAT:
============

All messages are JSON with `type` discriminator:

    {
        "type": "earcon" | "audio_event" | "stream_start" | "stream_chunk" | "stream_end",
        "timestamp": float,  // Unix timestamp ms
        "request_id": str,   // For correlation
        ...type-specific fields
    }

LATENCY TARGETS:
================

    Earcon:      <20ms  (network RTT + message parse)
    AudioEvent:  <50ms  (network RTT + Redis + message parse)
    Stream:      <100ms (first audio to speaker)

Created: January 4, 2026
Colony: ⚒️ Forge (e₂) — Building the wire
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

# Audio constants
DEFAULT_SAMPLE_RATE = 48000  # Hz - matches Denon/home theater
CHUNK_DURATION_MS = 20  # 20ms chunks for low latency
SAMPLES_PER_CHUNK = int(DEFAULT_SAMPLE_RATE * CHUNK_DURATION_MS / 1000)  # 960 samples


class AudioMessageType(Enum):
    """Audio message types."""

    # Name-based earcon playback (<20ms)
    EARCON = "earcon"

    # Full audio via Redis PubSub (<50ms)
    AUDIO_EVENT = "audio_event"

    # Chunked streaming
    STREAM_START = "stream_start"
    STREAM_CHUNK = "stream_chunk"
    STREAM_END = "stream_end"

    # Control
    STOP = "stop"
    VOLUME = "volume"

    # Cache management
    CACHE_EARCON = "cache_earcon"
    CACHE_CLEAR = "cache_clear"


class AudioFormat(Enum):
    """Audio encoding formats."""

    PCM_S16LE = "pcm_s16le"  # Raw 16-bit PCM (lowest latency)
    PCM_F32LE = "pcm_f32le"  # Raw 32-bit float PCM
    OPUS = "opus"  # Compressed (for bandwidth-constrained)
    WAV = "wav"  # Full WAV file
    MP3 = "mp3"  # Compressed


class AudioPriority(Enum):
    """Audio playback priority."""

    LOW = 1  # Background, can be interrupted
    NORMAL = 2  # Standard notifications
    HIGH = 3  # Important alerts
    URGENT = 4  # Critical - interrupts everything


@dataclass
class AudioMetadata:
    """Metadata for audio content."""

    sample_rate: int = DEFAULT_SAMPLE_RATE
    channels: int = 2  # Stereo
    format: AudioFormat = AudioFormat.PCM_F32LE
    duration_ms: float | None = None
    spatial: dict[str, Any] | None = None  # 3D position info


@dataclass
class EarconMessage:
    """Play pre-cached earcon by name.

    Latency target: <20ms

    The client maintains a cache of all earcons.
    Server sends only the name, client plays from cache.
    """

    name: str  # e.g., "notification", "success", "error"
    priority: AudioPriority = AudioPriority.NORMAL
    volume: float = 1.0  # 0.0-1.0
    room: str | None = None  # Target room (if multi-room)
    request_id: str = ""
    timestamp: float = field(default_factory=lambda: time.time() * 1000)

    def to_dict(self) -> dict[str, Any]:
        """Convert to wire format."""
        return {
            "type": AudioMessageType.EARCON.value,
            "name": self.name,
            "priority": self.priority.value,
            "volume": self.volume,
            "room": self.room,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EarconMessage:
        """Parse from wire format."""
        return cls(
            name=data["name"],
            priority=AudioPriority(data.get("priority", 2)),
            volume=data.get("volume", 1.0),
            room=data.get("room"),
            request_id=data.get("request_id", ""),
            timestamp=data.get("timestamp", time.time() * 1000),
        )


@dataclass
class AudioEventMessage:
    """Full audio delivery via Redis PubSub.

    Latency target: <50ms

    For TTS and generated audio that's too dynamic to cache.
    Supports both URL reference and inline base64 audio.
    """

    audio_url: str | None = None  # URL to audio file
    audio_data: str | None = None  # Base64-encoded audio (for small files)
    metadata: AudioMetadata = field(default_factory=AudioMetadata)
    text: str | None = None  # Original text (for TTS)
    priority: AudioPriority = AudioPriority.NORMAL
    volume: float = 1.0
    room: str | None = None
    request_id: str = ""
    timestamp: float = field(default_factory=lambda: time.time() * 1000)

    def to_dict(self) -> dict[str, Any]:
        """Convert to wire format."""
        return {
            "type": AudioMessageType.AUDIO_EVENT.value,
            "audio_url": self.audio_url,
            "audio_data": self.audio_data,
            "metadata": {
                "sample_rate": self.metadata.sample_rate,
                "channels": self.metadata.channels,
                "format": self.metadata.format.value,
                "duration_ms": self.metadata.duration_ms,
                "spatial": self.metadata.spatial,
            },
            "text": self.text,
            "priority": self.priority.value,
            "volume": self.volume,
            "room": self.room,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AudioEventMessage:
        """Parse from wire format."""
        meta_data = data.get("metadata", {})
        return cls(
            audio_url=data.get("audio_url"),
            audio_data=data.get("audio_data"),
            metadata=AudioMetadata(
                sample_rate=meta_data.get("sample_rate", DEFAULT_SAMPLE_RATE),
                channels=meta_data.get("channels", 2),
                format=AudioFormat(meta_data.get("format", "pcm_f32le")),
                duration_ms=meta_data.get("duration_ms"),
                spatial=meta_data.get("spatial"),
            ),
            text=data.get("text"),
            priority=AudioPriority(data.get("priority", 2)),
            volume=data.get("volume", 1.0),
            room=data.get("room"),
            request_id=data.get("request_id", ""),
            timestamp=data.get("timestamp", time.time() * 1000),
        )


@dataclass
class StreamStartMessage:
    """Start streaming audio.

    Latency target: <100ms to first audio

    Initiates a chunked audio stream. Client should start
    playback buffer and prepare for incoming chunks.
    """

    stream_id: str
    metadata: AudioMetadata = field(default_factory=AudioMetadata)
    total_duration_ms: float | None = None  # If known
    priority: AudioPriority = AudioPriority.NORMAL
    volume: float = 1.0
    room: str | None = None
    request_id: str = ""
    timestamp: float = field(default_factory=lambda: time.time() * 1000)

    def to_dict(self) -> dict[str, Any]:
        """Convert to wire format."""
        return {
            "type": AudioMessageType.STREAM_START.value,
            "stream_id": self.stream_id,
            "metadata": {
                "sample_rate": self.metadata.sample_rate,
                "channels": self.metadata.channels,
                "format": self.metadata.format.value,
                "duration_ms": self.metadata.duration_ms,
                "spatial": self.metadata.spatial,
            },
            "total_duration_ms": self.total_duration_ms,
            "priority": self.priority.value,
            "volume": self.volume,
            "room": self.room,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StreamStartMessage:
        """Parse from wire format."""
        meta_data = data.get("metadata", {})
        return cls(
            stream_id=data["stream_id"],
            metadata=AudioMetadata(
                sample_rate=meta_data.get("sample_rate", DEFAULT_SAMPLE_RATE),
                channels=meta_data.get("channels", 2),
                format=AudioFormat(meta_data.get("format", "pcm_f32le")),
                duration_ms=meta_data.get("duration_ms"),
                spatial=meta_data.get("spatial"),
            ),
            total_duration_ms=data.get("total_duration_ms"),
            priority=AudioPriority(data.get("priority", 2)),
            volume=data.get("volume", 1.0),
            room=data.get("room"),
            request_id=data.get("request_id", ""),
            timestamp=data.get("timestamp", time.time() * 1000),
        )


@dataclass
class StreamChunkMessage:
    """Audio stream chunk.

    20ms of audio data per chunk for optimal latency/overhead balance.
    """

    stream_id: str
    sequence: int  # Chunk sequence number
    audio_data: str  # Base64-encoded audio bytes
    timestamp: float = field(default_factory=lambda: time.time() * 1000)

    def to_dict(self) -> dict[str, Any]:
        """Convert to wire format."""
        return {
            "type": AudioMessageType.STREAM_CHUNK.value,
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "audio_data": self.audio_data,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StreamChunkMessage:
        """Parse from wire format."""
        return cls(
            stream_id=data["stream_id"],
            sequence=data["sequence"],
            audio_data=data["audio_data"],
            timestamp=data.get("timestamp", time.time() * 1000),
        )


@dataclass
class StreamEndMessage:
    """End audio stream."""

    stream_id: str
    total_chunks: int
    total_duration_ms: float
    timestamp: float = field(default_factory=lambda: time.time() * 1000)

    def to_dict(self) -> dict[str, Any]:
        """Convert to wire format."""
        return {
            "type": AudioMessageType.STREAM_END.value,
            "stream_id": self.stream_id,
            "total_chunks": self.total_chunks,
            "total_duration_ms": self.total_duration_ms,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StreamEndMessage:
        """Parse from wire format."""
        return cls(
            stream_id=data["stream_id"],
            total_chunks=data["total_chunks"],
            total_duration_ms=data["total_duration_ms"],
            timestamp=data.get("timestamp", time.time() * 1000),
        )


@dataclass
class StopMessage:
    """Stop audio playback."""

    stream_id: str | None = None  # Specific stream, or None for all
    reason: str = "user"
    timestamp: float = field(default_factory=lambda: time.time() * 1000)

    def to_dict(self) -> dict[str, Any]:
        """Convert to wire format."""
        return {
            "type": AudioMessageType.STOP.value,
            "stream_id": self.stream_id,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class VolumeMessage:
    """Set playback volume."""

    volume: float  # 0.0-1.0
    room: str | None = None  # Specific room or None for all
    timestamp: float = field(default_factory=lambda: time.time() * 1000)

    def to_dict(self) -> dict[str, Any]:
        """Convert to wire format."""
        return {
            "type": AudioMessageType.VOLUME.value,
            "volume": self.volume,
            "room": self.room,
            "timestamp": self.timestamp,
        }


@dataclass
class CacheEarconMessage:
    """Pre-cache an earcon on client.

    Sent at startup to populate client earcon cache.
    """

    name: str
    audio_data: str  # Base64-encoded audio
    metadata: AudioMetadata = field(default_factory=AudioMetadata)
    timestamp: float = field(default_factory=lambda: time.time() * 1000)

    def to_dict(self) -> dict[str, Any]:
        """Convert to wire format."""
        return {
            "type": AudioMessageType.CACHE_EARCON.value,
            "name": self.name,
            "audio_data": self.audio_data,
            "metadata": {
                "sample_rate": self.metadata.sample_rate,
                "channels": self.metadata.channels,
                "format": self.metadata.format.value,
                "duration_ms": self.metadata.duration_ms,
            },
            "timestamp": self.timestamp,
        }


# =============================================================================
# ENCODING UTILITIES
# =============================================================================


def encode_pcm_f32(audio: np.ndarray) -> str:
    """Encode float32 audio to base64.

    Args:
        audio: Audio array (samples x channels) in float32

    Returns:
        Base64-encoded PCM bytes
    """
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
    return base64.b64encode(audio.tobytes()).decode("ascii")


def decode_pcm_f32(data: str, channels: int = 2) -> np.ndarray:
    """Decode base64 PCM to float32 array.

    Args:
        data: Base64-encoded PCM bytes
        channels: Number of audio channels

    Returns:
        Audio array (samples x channels) in float32
    """
    raw = base64.b64decode(data)
    audio = np.frombuffer(raw, dtype=np.float32)
    if channels > 1:
        audio = audio.reshape(-1, channels)
    return audio


def encode_pcm_s16(audio: np.ndarray) -> str:
    """Encode int16 audio to base64.

    Args:
        audio: Audio array in int16 or float (will be converted)

    Returns:
        Base64-encoded PCM bytes
    """
    if audio.dtype == np.float32 or audio.dtype == np.float64:
        # Convert float [-1, 1] to int16
        audio = (audio * 32767).astype(np.int16)
    elif audio.dtype != np.int16:
        audio = audio.astype(np.int16)
    return base64.b64encode(audio.tobytes()).decode("ascii")


def decode_pcm_s16(data: str, channels: int = 2) -> np.ndarray:
    """Decode base64 PCM to int16 array.

    Args:
        data: Base64-encoded PCM bytes
        channels: Number of audio channels

    Returns:
        Audio array (samples x channels) in int16
    """
    raw = base64.b64decode(data)
    audio = np.frombuffer(raw, dtype=np.int16)
    if channels > 1:
        audio = audio.reshape(-1, channels)
    return audio


def chunk_audio(
    audio: np.ndarray,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    chunk_ms: int = CHUNK_DURATION_MS,
) -> list[np.ndarray]:
    """Split audio into chunks for streaming.

    Args:
        audio: Full audio array
        sample_rate: Sample rate
        chunk_ms: Milliseconds per chunk

    Returns:
        List of audio chunks
    """
    samples_per_chunk = int(sample_rate * chunk_ms / 1000)
    chunks = []
    for i in range(0, len(audio), samples_per_chunk):
        chunk = audio[i : i + samples_per_chunk]
        if len(chunk) > 0:
            chunks.append(chunk)
    return chunks


def parse_message(data: dict[str, Any]) -> Any:
    """Parse incoming audio message.

    Args:
        data: Message dict with 'type' field

    Returns:
        Appropriate message dataclass
    """
    msg_type = data.get("type")

    parsers = {
        AudioMessageType.EARCON.value: EarconMessage.from_dict,
        AudioMessageType.AUDIO_EVENT.value: AudioEventMessage.from_dict,
        AudioMessageType.STREAM_START.value: StreamStartMessage.from_dict,
        AudioMessageType.STREAM_CHUNK.value: StreamChunkMessage.from_dict,
        AudioMessageType.STREAM_END.value: StreamEndMessage.from_dict,
    }

    parser = parsers.get(msg_type)
    if parser:
        return parser(data)

    raise ValueError(f"Unknown message type: {msg_type}")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CHUNK_DURATION_MS",
    # Constants
    "DEFAULT_SAMPLE_RATE",
    "SAMPLES_PER_CHUNK",
    "AudioEventMessage",
    "AudioFormat",
    # Enums
    "AudioMessageType",
    # Data classes
    "AudioMetadata",
    "AudioPriority",
    "CacheEarconMessage",
    "EarconMessage",
    "StopMessage",
    "StreamChunkMessage",
    "StreamEndMessage",
    "StreamStartMessage",
    "VolumeMessage",
    "chunk_audio",
    "decode_pcm_f32",
    "decode_pcm_s16",
    # Utilities
    "encode_pcm_f32",
    "encode_pcm_s16",
    "parse_message",
]
