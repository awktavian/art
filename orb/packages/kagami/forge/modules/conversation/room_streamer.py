"""Real-time Room Streaming for Multi-Colony Conversations.

Orchestrates real-time audio streaming to specific rooms during
multi-colony conversations with optimized Control4/Triad routing.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RoomStreamResult:
    """Result of streaming to a specific room."""

    room: str
    success: bool
    latency_ms: float
    error: str | None = None


@dataclass
class StreamMetrics:
    """Metrics for multi-room streaming performance."""

    total_rooms: int
    successful_rooms: int
    avg_latency_ms: float
    peak_latency_ms: float
    total_duration_ms: float


class RealtimeRoomStreamer:
    """Real-time audio streaming to multiple rooms for colony conversations."""

    def __init__(self, audio_bridge=None):
        self.audio_bridge = audio_bridge
        self._active_streams: dict[str, asyncio.Task] = {}
        self._room_state: dict[str, dict[str, Any]] = {}

    async def stream_colony_to_rooms(
        self,
        text: str,
        colony: str,
        rooms: list[str],
        priority: int = 1,
    ) -> tuple[bool, StreamMetrics]:
        """Stream colony speech to specified rooms with priority handling.

        Args:
            text: Speech text to synthesize
            colony: Speaking colony
            rooms: Target rooms for streaming
            priority: Stream priority (1=highest, 3=lowest)

        Returns:
            (success, metrics) tuple
        """
        start_time = time.perf_counter()

        if not self.audio_bridge:
            logger.warning("No audio bridge available for streaming")
            return False, self._create_empty_metrics(len(rooms))

        # Pre-configure rooms for optimal streaming
        await self._preconfigure_rooms(rooms, priority)

        try:
            # Use audio bridge's optimized parallel streaming
            success, playback_metrics = await self.audio_bridge.announce_parallel(
                text=text,
                rooms=rooms,
                colony=colony,
            )

            # Convert to room-specific metrics
            latencies = []
            successful_count = 0

            for _room in rooms:
                # Estimate per-room latency (actual implementation would track per-room)
                room_latency = playback_metrics.total_ms / len(rooms) if rooms else 0
                latencies.append(room_latency)
                if success:  # Simplified success tracking
                    successful_count += 1

            metrics = StreamMetrics(
                total_rooms=len(rooms),
                successful_rooms=successful_count,
                avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
                peak_latency_ms=max(latencies) if latencies else 0,
                total_duration_ms=(time.perf_counter() - start_time) * 1000,
            )

            logger.info(
                f"🎵 [{colony}] → {successful_count}/{len(rooms)} rooms "
                f'({metrics.avg_latency_ms:.0f}ms avg) | "{text[:30]}..."'
            )

            return success, metrics

        except Exception as e:
            logger.error(f"Room streaming failed: {e}")
            return False, self._create_empty_metrics(len(rooms))

    async def _preconfigure_rooms(self, rooms: list[str], priority: int) -> None:
        """Pre-configure rooms for optimal streaming performance."""
        if not self.audio_bridge or not hasattr(self.audio_bridge, "control4"):
            return

        tasks = []
        for room in rooms:
            if room not in self._room_state:
                self._room_state[room] = {}

            # Configure room for multi-colony conversation priority
            task = self._configure_room_priority(room, priority)
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _configure_room_priority(self, room: str, priority: int) -> None:
        """Configure room for conversation priority streaming."""
        try:
            # Skip configuration for Living Room (direct Denon path)
            if room.lower() == "living room":
                return

            # For Triad rooms, ensure Control4 Airplay is selected
            control4 = self.audio_bridge.control4
            room_ids = getattr(self.audio_bridge, "ROOM_IDS", {})
            room_id = room_ids.get(room)

            if room_id and control4:
                # Select Control4 Airplay source (ID 308)
                await control4.select_audio_source_for_room(room_id, 308)

                # Set priority-based volume
                priority_volumes = {1: 75, 2: 65, 3: 55}  # Higher priority = louder
                volume = priority_volumes.get(priority, 65)
                await control4.set_room_volume(room_id, volume)

                self._room_state[room]["priority"] = priority
                self._room_state[room]["configured_at"] = time.time()

        except Exception as e:
            logger.debug(f"Room {room} priority config failed: {e}")

    async def interrupt_room_streams(self, rooms: list[str]) -> None:
        """Interrupt active streams in specified rooms for priority speech."""
        for room in rooms:
            if room in self._active_streams:
                stream_task = self._active_streams[room]
                if not stream_task.done():
                    stream_task.cancel()
                    logger.debug(f"Interrupted stream in {room}")

    def get_room_state(self, room: str) -> dict[str, Any]:
        """Get current state for a specific room."""
        return self._room_state.get(room, {})

    def get_active_rooms(self) -> list[str]:
        """Get list of rooms with active streams."""
        return [room for room, task in self._active_streams.items() if not task.done()]

    def _create_empty_metrics(self, room_count: int) -> StreamMetrics:
        """Create empty metrics for failed streams."""
        return StreamMetrics(
            total_rooms=room_count,
            successful_rooms=0,
            avg_latency_ms=0,
            peak_latency_ms=0,
            total_duration_ms=0,
        )

    async def cleanup(self) -> None:
        """Clean up active streams and room state."""
        # Cancel active streams
        for task in self._active_streams.values():
            if not task.done():
                task.cancel()

        # Wait for cancellation
        if self._active_streams:
            await asyncio.gather(*self._active_streams.values(), return_exceptions=True)

        self._active_streams.clear()
        self._room_state.clear()
        logger.debug("Room streamer cleaned up")


class ConversationAudioRouter:
    """Advanced routing for multi-colony conversations."""

    def __init__(self, room_streamer: RealtimeRoomStreamer):
        self.streamer = room_streamer
        self._room_assignments: dict[str, list[str]] = {}
        self._colony_priorities: dict[str, int] = {
            "kagami": 1,  # Highest priority
            "beacon": 1,  # Highest priority
            "spark": 2,  # High priority
            "forge": 2,  # High priority
            "nexus": 2,  # High priority
            "flow": 3,  # Medium priority
            "grove": 3,  # Medium priority
            "crystal": 3,  # Medium priority
        }

    async def route_colony_speech(
        self,
        colony: str,
        text: str,
        conversation_rooms: list[str],
    ) -> tuple[bool, StreamMetrics]:
        """Route colony speech with conversation-aware priority."""

        # Get colony priority
        priority = self._colony_priorities.get(colony, 3)

        # If high priority, interrupt lower priority streams
        if priority <= 2:
            await self.streamer.interrupt_room_streams(conversation_rooms)

        # Stream to conversation rooms
        return await self.streamer.stream_colony_to_rooms(
            text=text,
            colony=colony,
            rooms=conversation_rooms,
            priority=priority,
        )

    def set_room_assignments(self, assignments: dict[str, list[str]]) -> None:
        """Set room assignments for conversation participants."""
        self._room_assignments = assignments

    def get_rooms_for_participants(self, participants: list[str]) -> list[str]:
        """Get all rooms that should hear specified participants."""
        all_rooms = set()
        for participant in participants:
            rooms = self._room_assignments.get(participant, [])
            all_rooms.update(rooms)
        return list(all_rooms)
