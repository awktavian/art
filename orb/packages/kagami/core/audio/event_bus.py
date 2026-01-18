"""Low-Latency Audio Event Bus.

Redis PubSub-based audio event distribution for the Kagami ecosystem.

ARCHITECTURE:
=============

    ┌─────────────────────────────────────────────────────────────────┐
    │                        AudioEventBus                             │
    │                                                                  │
    │   Publishers:                     Subscribers:                   │
    │   - API Server                    - Hub (Raspberry Pi)          │
    │   - TTS Service                   - Desktop Client              │
    │   - Music Service                 - Watch App                   │
    │   - Alert System                  - Vision Pro                  │
    │                                                                  │
    │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
    │   │   Earcons    │    │ Audio Events │    │   Streams    │     │
    │   │   (<20ms)    │    │   (<50ms)    │    │  (<100ms)    │     │
    │   └──────────────┘    └──────────────┘    └──────────────┘     │
    │          │                   │                   │              │
    │          └───────────────────┴───────────────────┘              │
    │                              │                                   │
    │                      Redis PubSub                               │
    │                              │                                   │
    │          ┌───────────────────┴───────────────────┐              │
    │          │                   │                   │              │
    │      kagami:audio:       kagami:audio:      kagami:audio:      │
    │       earcons             events             streams            │
    └─────────────────────────────────────────────────────────────────┘

CHANNELS:
=========

- `kagami:audio:earcons` - Earcon triggers (name only)
- `kagami:audio:events` - Full audio events (URL or base64)
- `kagami:audio:streams:{stream_id}` - Stream chunks
- `kagami:audio:control` - Stop/volume commands

Created: January 4, 2026
Colony: ⚒️ Forge (e₂) — Building infrastructure
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from kagami.core.audio.protocol import (
    DEFAULT_SAMPLE_RATE,
    AudioEventMessage,
    AudioMetadata,
    AudioPriority,
    CacheEarconMessage,
    EarconMessage,
    StopMessage,
    StreamChunkMessage,
    StreamEndMessage,
    StreamStartMessage,
    VolumeMessage,
    chunk_audio,
    encode_pcm_f32,
)

logger = logging.getLogger(__name__)

# Redis channel prefixes
CHANNEL_EARCONS = "kagami:audio:earcons"
CHANNEL_EVENTS = "kagami:audio:events"
CHANNEL_STREAMS = "kagami:audio:streams"
CHANNEL_CONTROL = "kagami:audio:control"
CHANNEL_CACHE = "kagami:audio:cache"

# Message handler type
MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class AudioBusStats:
    """Statistics for the audio bus."""

    earcons_published: int = 0
    events_published: int = 0
    streams_started: int = 0
    streams_completed: int = 0
    chunks_sent: int = 0
    bytes_sent: int = 0
    subscribers: int = 0
    last_publish_time: float = 0.0
    latency_samples: list[float] = field(default_factory=list)

    @property
    def avg_latency_ms(self) -> float:
        """Average publish latency in milliseconds."""
        if not self.latency_samples:
            return 0.0
        return sum(self.latency_samples[-100:]) / len(self.latency_samples[-100:])


class AudioEventBus:
    """Redis PubSub-based audio event bus.

    Provides ultra-low-latency audio delivery across the Kagami ecosystem.

    Usage:
        bus = await get_audio_bus()

        # Publish earcon (receivers play from cache)
        await bus.publish_earcon("notification")

        # Publish full audio
        await bus.publish_audio(audio_data, metadata)

        # Stream audio in chunks
        async with bus.stream_audio(audio_data, metadata) as stream:
            await stream.wait_complete()

        # Subscribe to events
        await bus.subscribe_earcons(handler)
    """

    def __init__(self) -> None:
        """Initialize audio event bus."""
        self._redis: Any = None
        self._pubsub: Any = None
        self._running = False
        self._listener_task: asyncio.Task | None = None
        self._stats = AudioBusStats()

        # Handlers by channel
        self._earcon_handlers: list[MessageHandler] = []
        self._event_handlers: list[MessageHandler] = []
        self._stream_handlers: dict[str, MessageHandler] = {}
        self._control_handlers: list[MessageHandler] = []
        self._cache_handlers: list[MessageHandler] = []

        # Active streams
        self._active_streams: dict[str, StreamContext] = {}

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        if self._redis is not None:
            return

        try:
            from kagami.core.storage.redis_client import get_redis_client

            self._redis = await get_redis_client()
            logger.info("✓ AudioEventBus initialized with Redis")
        except Exception as e:
            logger.warning(f"Redis not available, using local mode: {e}")
            self._redis = None

    async def shutdown(self) -> None:
        """Shutdown the event bus."""
        self._running = False

        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()

        logger.info("AudioEventBus shutdown complete")

    # =========================================================================
    # PUBLISHING
    # =========================================================================

    async def publish_earcon(
        self,
        name: str,
        priority: AudioPriority = AudioPriority.NORMAL,
        volume: float = 1.0,
        room: str | None = None,
    ) -> str:
        """Publish earcon trigger.

        Receivers play the earcon from their local cache.

        Args:
            name: Earcon name (e.g., "notification", "success")
            priority: Playback priority
            volume: Volume (0.0-1.0)
            room: Target room (None for all)

        Returns:
            Request ID
        """
        request_id = str(uuid.uuid4())[:8]

        message = EarconMessage(
            name=name,
            priority=priority,
            volume=volume,
            room=room,
            request_id=request_id,
        )

        start = time.perf_counter()
        await self._publish(CHANNEL_EARCONS, message.to_dict())
        latency = (time.perf_counter() - start) * 1000

        self._stats.earcons_published += 1
        self._stats.latency_samples.append(latency)
        self._stats.last_publish_time = time.time()

        logger.debug(f"Published earcon '{name}' in {latency:.1f}ms")
        return request_id

    async def publish_audio(
        self,
        audio: np.ndarray | str,
        metadata: AudioMetadata | None = None,
        text: str | None = None,
        priority: AudioPriority = AudioPriority.NORMAL,
        volume: float = 1.0,
        room: str | None = None,
        as_url: str | None = None,
    ) -> str:
        """Publish full audio event.

        For audio that can't be pre-cached (TTS, generated).

        Args:
            audio: Audio array or base64-encoded string
            metadata: Audio metadata
            text: Original text (for TTS)
            priority: Playback priority
            volume: Volume (0.0-1.0)
            room: Target room
            as_url: If set, send URL instead of inline data

        Returns:
            Request ID
        """
        request_id = str(uuid.uuid4())[:8]

        if metadata is None:
            metadata = AudioMetadata()

        # Encode audio if array
        audio_data = None
        audio_url = as_url

        if audio_url is None:
            if isinstance(audio, np.ndarray):
                audio_data = encode_pcm_f32(audio)
                metadata.duration_ms = len(audio) / metadata.sample_rate * 1000
            else:
                audio_data = audio

        message = AudioEventMessage(
            audio_url=audio_url,
            audio_data=audio_data,
            metadata=metadata,
            text=text,
            priority=priority,
            volume=volume,
            room=room,
            request_id=request_id,
        )

        start = time.perf_counter()
        await self._publish(CHANNEL_EVENTS, message.to_dict())
        latency = (time.perf_counter() - start) * 1000

        self._stats.events_published += 1
        self._stats.latency_samples.append(latency)
        self._stats.last_publish_time = time.time()
        if audio_data:
            self._stats.bytes_sent += len(audio_data)

        logger.debug(f"Published audio event in {latency:.1f}ms")
        return request_id

    async def stream_audio(
        self,
        audio: np.ndarray,
        metadata: AudioMetadata | None = None,
        priority: AudioPriority = AudioPriority.NORMAL,
        volume: float = 1.0,
        room: str | None = None,
        chunk_ms: int = 20,
    ) -> StreamContext:
        """Start streaming audio.

        For long audio or real-time generation.

        Args:
            audio: Full audio array
            metadata: Audio metadata
            priority: Playback priority
            volume: Volume (0.0-1.0)
            room: Target room
            chunk_ms: Milliseconds per chunk

        Returns:
            StreamContext for tracking
        """
        stream_id = str(uuid.uuid4())[:8]

        if metadata is None:
            metadata = AudioMetadata()

        duration_ms = len(audio) / metadata.sample_rate * 1000

        # Send stream start
        start_msg = StreamStartMessage(
            stream_id=stream_id,
            metadata=metadata,
            total_duration_ms=duration_ms,
            priority=priority,
            volume=volume,
            room=room,
        )
        await self._publish(f"{CHANNEL_STREAMS}:{stream_id}", start_msg.to_dict())

        # Create context
        context = StreamContext(
            stream_id=stream_id,
            audio=audio,
            metadata=metadata,
            chunk_ms=chunk_ms,
            bus=self,
        )
        self._active_streams[stream_id] = context
        self._stats.streams_started += 1

        # Start streaming in background
        context._task = asyncio.create_task(context._stream_chunks())

        return context

    async def _send_chunk(
        self,
        stream_id: str,
        sequence: int,
        audio_data: str,
    ) -> None:
        """Send a stream chunk."""
        message = StreamChunkMessage(
            stream_id=stream_id,
            sequence=sequence,
            audio_data=audio_data,
        )
        await self._publish(f"{CHANNEL_STREAMS}:{stream_id}", message.to_dict())
        self._stats.chunks_sent += 1
        self._stats.bytes_sent += len(audio_data)

    async def _send_stream_end(
        self,
        stream_id: str,
        total_chunks: int,
        total_duration_ms: float,
    ) -> None:
        """Send stream end message."""
        message = StreamEndMessage(
            stream_id=stream_id,
            total_chunks=total_chunks,
            total_duration_ms=total_duration_ms,
        )
        await self._publish(f"{CHANNEL_STREAMS}:{stream_id}", message.to_dict())

        if stream_id in self._active_streams:
            del self._active_streams[stream_id]

        self._stats.streams_completed += 1

    async def stop_playback(
        self,
        stream_id: str | None = None,
        reason: str = "user",
    ) -> None:
        """Stop audio playback.

        Args:
            stream_id: Specific stream, or None for all
            reason: Stop reason
        """
        message = StopMessage(stream_id=stream_id, reason=reason)
        await self._publish(CHANNEL_CONTROL, message.to_dict())

    async def set_volume(
        self,
        volume: float,
        room: str | None = None,
    ) -> None:
        """Set playback volume.

        Args:
            volume: Volume (0.0-1.0)
            room: Specific room or None for all
        """
        message = VolumeMessage(volume=volume, room=room)
        await self._publish(CHANNEL_CONTROL, message.to_dict())

    async def cache_earcon(
        self,
        name: str,
        audio: np.ndarray,
        metadata: AudioMetadata | None = None,
    ) -> None:
        """Send earcon to be cached on clients.

        Called at startup to pre-populate client caches.

        Args:
            name: Earcon name
            audio: Audio data
            metadata: Audio metadata
        """
        if metadata is None:
            metadata = AudioMetadata()

        audio_data = encode_pcm_f32(audio)
        metadata.duration_ms = len(audio) / metadata.sample_rate * 1000

        message = CacheEarconMessage(
            name=name,
            audio_data=audio_data,
            metadata=metadata,
        )
        await self._publish(CHANNEL_CACHE, message.to_dict())
        logger.debug(f"Sent earcon '{name}' for caching")

    # =========================================================================
    # SUBSCRIBING
    # =========================================================================

    async def subscribe_earcons(self, handler: MessageHandler) -> None:
        """Subscribe to earcon events.

        Args:
            handler: Async function to handle earcon messages
        """
        self._earcon_handlers.append(handler)
        await self._ensure_subscribed(CHANNEL_EARCONS)

    async def subscribe_events(self, handler: MessageHandler) -> None:
        """Subscribe to full audio events.

        Args:
            handler: Async function to handle audio event messages
        """
        self._event_handlers.append(handler)
        await self._ensure_subscribed(CHANNEL_EVENTS)

    async def subscribe_stream(
        self,
        stream_id: str,
        handler: MessageHandler,
    ) -> None:
        """Subscribe to a specific stream.

        Args:
            stream_id: Stream to subscribe to
            handler: Async function to handle stream messages
        """
        self._stream_handlers[stream_id] = handler
        await self._ensure_subscribed(f"{CHANNEL_STREAMS}:{stream_id}")

    async def subscribe_control(self, handler: MessageHandler) -> None:
        """Subscribe to control messages (stop, volume).

        Args:
            handler: Async function to handle control messages
        """
        self._control_handlers.append(handler)
        await self._ensure_subscribed(CHANNEL_CONTROL)

    async def subscribe_cache(self, handler: MessageHandler) -> None:
        """Subscribe to cache messages (earcon pre-caching).

        Args:
            handler: Async function to handle cache messages
        """
        self._cache_handlers.append(handler)
        await self._ensure_subscribed(CHANNEL_CACHE)

    # =========================================================================
    # INTERNAL
    # =========================================================================

    async def _publish(self, channel: str, message: dict[str, Any]) -> None:
        """Publish message to Redis channel."""
        if self._redis is None:
            # Local mode - directly call handlers
            await self._dispatch(channel, message)
            return

        try:
            await self._redis.publish(channel, json.dumps(message))
        except Exception as e:
            logger.error(f"Redis publish failed: {e}")
            # Fallback to local dispatch
            await self._dispatch(channel, message)

    async def _ensure_subscribed(self, channel: str) -> None:
        """Ensure we're subscribed to a channel."""
        if self._redis is None:
            return

        if self._pubsub is None:
            self._pubsub = self._redis.pubsub()

        await self._pubsub.subscribe(channel)

        if not self._running:
            self._running = True
            self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        """Listen for Redis messages."""
        if self._pubsub is None:
            return

        try:
            async for message in self._pubsub.listen():
                if not self._running:
                    break

                if message["type"] != "message":
                    continue

                channel = message["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode()

                try:
                    data = json.loads(message["data"])
                    await self._dispatch(channel, data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON on {channel}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Redis listener error: {e}")

    async def _dispatch(self, channel: str, message: dict[str, Any]) -> None:
        """Dispatch message to handlers."""
        handlers: list[MessageHandler] = []

        if channel == CHANNEL_EARCONS:
            handlers = self._earcon_handlers
        elif channel == CHANNEL_EVENTS:
            handlers = self._event_handlers
        elif channel == CHANNEL_CONTROL:
            handlers = self._control_handlers
        elif channel == CHANNEL_CACHE:
            handlers = self._cache_handlers
        elif channel.startswith(CHANNEL_STREAMS):
            stream_id = channel.split(":")[-1]
            if stream_id in self._stream_handlers:
                handlers = [self._stream_handlers[stream_id]]

        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Handler error: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get bus statistics."""
        return {
            "earcons_published": self._stats.earcons_published,
            "events_published": self._stats.events_published,
            "streams_started": self._stats.streams_started,
            "streams_completed": self._stats.streams_completed,
            "chunks_sent": self._stats.chunks_sent,
            "bytes_sent": self._stats.bytes_sent,
            "active_streams": len(self._active_streams),
            "avg_latency_ms": self._stats.avg_latency_ms,
            "last_publish_time": self._stats.last_publish_time,
        }


@dataclass
class StreamContext:
    """Context for an active audio stream."""

    stream_id: str
    audio: np.ndarray
    metadata: AudioMetadata
    chunk_ms: int
    bus: AudioEventBus
    _task: asyncio.Task | None = None
    _complete: asyncio.Event = field(default_factory=asyncio.Event)
    _chunks_sent: int = 0
    _error: Exception | None = None

    async def _stream_chunks(self) -> None:
        """Stream audio in chunks."""
        try:
            chunks = chunk_audio(
                self.audio,
                self.metadata.sample_rate,
                self.chunk_ms,
            )

            for i, chunk in enumerate(chunks):
                audio_data = encode_pcm_f32(chunk)
                await self.bus._send_chunk(self.stream_id, i, audio_data)
                self._chunks_sent += 1

                # Pace to real-time (slightly faster to build buffer)
                await asyncio.sleep(self.chunk_ms / 1000 * 0.8)

            # Send end message
            duration_ms = len(self.audio) / self.metadata.sample_rate * 1000
            await self.bus._send_stream_end(
                self.stream_id,
                self._chunks_sent,
                duration_ms,
            )

        except Exception as e:
            self._error = e
            logger.error(f"Stream error: {e}")

        finally:
            self._complete.set()

    async def wait_complete(self) -> None:
        """Wait for stream to complete."""
        await self._complete.wait()
        if self._error:
            raise self._error

    async def cancel(self) -> None:
        """Cancel the stream."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await self.bus.stop_playback(self.stream_id, "cancelled")

    @property
    def is_complete(self) -> bool:
        """Check if stream is complete."""
        return self._complete.is_set()

    @property
    def chunks_sent(self) -> int:
        """Number of chunks sent."""
        return self._chunks_sent


# =============================================================================
# FACTORY (via centralized registry)
# =============================================================================

from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
get_audio_bus = _singleton_registry.register_async("audio_event_bus", AudioEventBus)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def play_earcon(
    name: str,
    priority: AudioPriority = AudioPriority.NORMAL,
    volume: float = 1.0,
    room: str | None = None,
    soul_aware: bool = False,
) -> str:
    """Play an earcon.

    Convenience function for quick earcon playback.

    Args:
        name: Earcon name
        priority: Playback priority
        volume: Volume (0.0-1.0)
        room: Target room
        soul_aware: If True, modulate based on current soul state

    Returns:
        Request ID
    """
    bus = await get_audio_bus()

    # Apply soul-based modulation if requested
    if soul_aware:
        try:
            from kagami.core.effectors.soul_to_music import soul_to_earcon_modulation

            modulation = await soul_to_earcon_modulation(name)
            # Apply modulation to volume
            volume = volume * modulation.get("velocity_scale", 1.0)
            volume = max(0.0, min(1.0, volume))
            logger.debug(f"Soul-modulated earcon '{name}': {modulation}")
        except Exception as e:
            logger.warning(f"Soul modulation failed, using defaults: {e}")

    return await bus.publish_earcon(name, priority, volume, room)


async def play_audio(
    audio: np.ndarray,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    room: str | None = None,
) -> str:
    """Play audio.

    Convenience function for quick audio playback.

    Args:
        audio: Audio array
        sample_rate: Sample rate
        room: Target room

    Returns:
        Request ID
    """
    bus = await get_audio_bus()
    metadata = AudioMetadata(sample_rate=sample_rate)
    return await bus.publish_audio(audio, metadata, room=room)


async def play_soul_earcon(
    name: str,
    room: str | None = None,
) -> str:
    """Play an earcon modulated by current soul state.

    This is the primary entry point for emotionally-aware audio feedback.
    The earcon's playback is influenced by Kagami's current emotional state.

    Args:
        name: Earcon name
        room: Target room

    Returns:
        Request ID
    """
    return await play_earcon(name, soul_aware=True, room=room)


__all__ = [
    "CHANNEL_CACHE",
    "CHANNEL_CONTROL",
    # Channel constants
    "CHANNEL_EARCONS",
    "CHANNEL_EVENTS",
    "CHANNEL_STREAMS",
    "AudioBusStats",
    "AudioEventBus",
    "StreamContext",
    "get_audio_bus",
    "play_audio",
    "play_earcon",
    "play_soul_earcon",
]
