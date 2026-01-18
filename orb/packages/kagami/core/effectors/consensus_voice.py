"""Consensus Voice — Distributed voice output with hub coordination.

This module implements coordinated voice output across multiple Kagami hubs,
ensuring that voice messages are delivered to the right location without
overlap or echo.

Architecture:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                      CONSENSUS VOICE SYSTEM                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Voice Request                     Hub Selection                        │
│   ─────────────                     ─────────────                        │
│   • Text content                    • Presence-aware routing             │
│   • Priority level                  • Room occupancy detection           │
│   • Target preference               • Distance-based selection           │
│   • Duration estimate               • Acoustic echo avoidance            │
│                                                                          │
│   ┌─────────────────┐   coordinate()  ┌─────────────────┐               │
│   │  VoiceRequest   │────────────────►│   HubSelection  │               │
│   │   (API/Hub)     │                 │   (PBFT vote)   │               │
│   └─────────────────┘                └─────────────────┘               │
│                                                                          │
│   Hub Mesh Coordination:                                                │
│   • Single hub speaks at a time (mutex)                                 │
│   • Presence-based hub selection                                        │
│   • Fallback to API server if no hub available                          │
│   • Echo cancellation via mesh sync                                     │
│                                                                          │
│   Colony: Nexus (A₅) — Voice coordination across distributed mesh       │
│   h(x) ≥ 0. Always.                                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import aiohttp

from kagami.core.caching.redis import RedisClientFactory
from kagami.core.cluster.service_registry import (
    ServiceInstance,
    ServiceType,
    get_service_registry,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Data Structures
# =============================================================================


class VoicePriority(Enum):
    """Priority levels for voice messages."""

    LOW = auto()  # Non-urgent information
    NORMAL = auto()  # Standard messages
    HIGH = auto()  # Important notifications
    URGENT = auto()  # Emergency alerts


class HubSelection(Enum):
    """Hub selection strategy for distributed voice.

    This determines WHICH HUB speaks, not WHERE audio plays.
    For output target (room, car, etc.), see effectors.voice.VoiceTarget.
    """

    AUTO = auto()  # Automatic selection based on presence
    NEAREST = auto()  # Nearest hub to user
    ALL = auto()  # All hubs (broadcast)
    SPECIFIC_ROOM = auto()  # Hub in specific room
    SPECIFIC_HUB = auto()  # Specific hub by ID
    API_ONLY = auto()  # API server only (no hubs)


# Alias for backwards compatibility (will be removed)
VoiceTarget = HubSelection


@dataclass
class VoiceRequest:
    """Request for voice output."""

    request_id: str
    text: str
    priority: VoicePriority = VoicePriority.NORMAL
    target: VoiceTarget = VoiceTarget.AUTO
    target_room: str | None = None
    target_hub_id: str | None = None
    requester_id: str = "api"
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "request_id": self.request_id,
            "text": self.text,
            "priority": self.priority.value,
            "target": self.target.value,
            "target_room": self.target_room,
            "target_hub_id": self.target_hub_id,
            "requester_id": self.requester_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoiceRequest:
        """Deserialize from dictionary."""
        return cls(
            request_id=data["request_id"],
            text=data["text"],
            priority=VoicePriority(data.get("priority", VoicePriority.NORMAL.value)),
            target=VoiceTarget(data.get("target", VoiceTarget.AUTO.value)),
            target_room=data.get("target_room"),
            target_hub_id=data.get("target_hub_id"),
            requester_id=data.get("requester_id", "api"),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class VoiceResult:
    """Result of a voice output operation."""

    success: bool
    request_id: str
    hub_id: str | None
    room: str | None
    duration_ms: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "success": self.success,
            "request_id": self.request_id,
            "hub_id": self.hub_id,
            "room": self.room,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class HubVoiceCapability:
    """Voice capability information for a hub."""

    hub_id: str
    rooms: list[str]  # Rooms this hub can serve
    is_available: bool
    current_volume: float
    last_speak_time: float
    speaker_type: str  # e.g., "led_ring", "speaker", "soundbar"

    @property
    def is_ready(self) -> bool:
        """Check if hub is ready to speak."""
        # Avoid speaking too soon after previous utterance
        cooldown = 2.0  # seconds
        return self.is_available and (time.time() - self.last_speak_time) > cooldown


# =============================================================================
# Voice Mutex (Distributed Lock)
# =============================================================================


class DistributedVoiceMutex:
    """Distributed mutex for coordinating voice output.

    Ensures only one hub speaks at a time to prevent acoustic echo
    and overlapping messages.
    """

    REDIS_MUTEX_KEY = "kagami:voice:mutex"
    REDIS_SPEAKING_KEY = "kagami:voice:speaking"
    DEFAULT_TTL = 30  # Maximum speaking time

    def __init__(self) -> None:
        self._redis = RedisClientFactory.get_client()
        self._local_lock = asyncio.Lock()

    async def acquire(
        self,
        hub_id: str,
        duration_estimate: float = 5.0,
    ) -> bool:
        """Acquire the voice mutex.

        Args:
            hub_id: Hub requesting the mutex.
            duration_estimate: Estimated speaking duration in seconds.

        Returns:
            True if mutex acquired.
        """
        ttl = max(int(duration_estimate * 2), self.DEFAULT_TTL)

        try:
            async with self._local_lock:
                # Try to set mutex (NX = only if not exists)
                result = await self._redis.set(
                    self.REDIS_MUTEX_KEY,
                    hub_id,
                    nx=True,
                    ex=ttl,
                )

                if result:
                    # Record speaking state
                    await self._redis.set(
                        self.REDIS_SPEAKING_KEY,
                        json.dumps(
                            {
                                "hub_id": hub_id,
                                "started": time.time(),
                                "estimated_duration": duration_estimate,
                            }
                        ),
                        ex=ttl,
                    )
                    logger.debug(f"Voice mutex acquired by {hub_id}")
                    return True

                # Check if we already hold the mutex
                current_holder = await self._redis.get(self.REDIS_MUTEX_KEY)
                if current_holder and current_holder.decode() == hub_id:
                    return True

                return False

        except Exception as e:
            logger.error(f"Failed to acquire voice mutex: {e}")
            return False

    async def release(self, hub_id: str) -> bool:
        """Release the voice mutex.

        Args:
            hub_id: Hub releasing the mutex.

        Returns:
            True if released successfully.
        """
        try:
            async with self._local_lock:
                # Only release if we hold it
                current_holder = await self._redis.get(self.REDIS_MUTEX_KEY)
                if current_holder and current_holder.decode() == hub_id:
                    await self._redis.delete(self.REDIS_MUTEX_KEY)
                    await self._redis.delete(self.REDIS_SPEAKING_KEY)
                    logger.debug(f"Voice mutex released by {hub_id}")
                    return True

                return False

        except Exception as e:
            logger.error(f"Failed to release voice mutex: {e}")
            return False

    async def is_locked(self) -> tuple[bool, str | None]:
        """Check if mutex is locked.

        Returns:
            (is_locked, holder_hub_id)
        """
        try:
            holder = await self._redis.get(self.REDIS_MUTEX_KEY)
            if holder:
                return True, holder.decode()
            return False, None
        except Exception:
            return False, None

    async def get_speaking_info(self) -> dict[str, Any] | None:
        """Get information about current speaking operation.

        Returns:
            Speaking info or None.
        """
        try:
            data = await self._redis.get(self.REDIS_SPEAKING_KEY)
            if data:
                return json.loads(data.decode())
            return None
        except Exception:
            return None


# =============================================================================
# Consensus Voice Coordinator
# =============================================================================


class ConsensusVoiceCoordinator:
    """Coordinates voice output across distributed Kagami hubs.

    Features:
    - Presence-aware hub selection
    - Distributed mutex for single-speaker
    - Priority-based queueing
    - Fallback handling

    Example:
        >>> coordinator = ConsensusVoiceCoordinator()
        >>> await coordinator.initialize()
        >>> result = await coordinator.speak("Hello", target=VoiceTarget.AUTO)
    """

    def __init__(self) -> None:
        self._service_registry = None
        self._voice_mutex = DistributedVoiceMutex()
        self._redis = RedisClientFactory.get_client()
        self._http_session: aiohttp.ClientSession | None = None
        self._hub_capabilities: dict[str, HubVoiceCapability] = {}
        self._initialized = False

        # Queue for pending voice requests
        self._request_queue: asyncio.Queue[VoiceRequest] = asyncio.Queue()
        self._processor_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """Initialize the voice coordinator."""
        if self._initialized:
            return

        logger.info("Initializing ConsensusVoiceCoordinator...")

        self._service_registry = await get_service_registry()
        self._http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))

        # Start request processor
        self._processor_task = asyncio.create_task(self._process_queue())

        self._initialized = True
        logger.info("✅ ConsensusVoiceCoordinator initialized")

    async def shutdown(self) -> None:
        """Shutdown the voice coordinator."""
        logger.info("Shutting down ConsensusVoiceCoordinator...")

        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        if self._http_session:
            await self._http_session.close()

        self._initialized = False
        logger.info("🛑 ConsensusVoiceCoordinator shutdown")

    async def speak(
        self,
        text: str,
        *,
        priority: VoicePriority = VoicePriority.NORMAL,
        target: VoiceTarget = VoiceTarget.AUTO,
        target_room: str | None = None,
        target_hub_id: str | None = None,
        requester_id: str = "api",
        wait: bool = True,
    ) -> VoiceResult:
        """Speak text through coordinated voice output.

        Args:
            text: Text to speak.
            priority: Message priority.
            target: Target selection mode.
            target_room: Target room (for SPECIFIC_ROOM).
            target_hub_id: Target hub ID (for SPECIFIC_HUB).
            requester_id: ID of the requester.
            wait: Whether to wait for completion.

        Returns:
            VoiceResult with outcome.
        """
        if not self._initialized:
            await self.initialize()

        # Create request
        request = VoiceRequest(
            request_id=self._generate_request_id(text),
            text=text,
            priority=priority,
            target=target,
            target_room=target_room,
            target_hub_id=target_hub_id,
            requester_id=requester_id,
        )

        if wait:
            return await self._execute_request(request)
        else:
            await self._request_queue.put(request)
            return VoiceResult(
                success=True,
                request_id=request.request_id,
                hub_id=None,
                room=None,
                duration_ms=0,
            )

    async def _execute_request(self, request: VoiceRequest) -> VoiceResult:
        """Execute a voice request.

        Args:
            request: Voice request to execute.

        Returns:
            VoiceResult.
        """
        start_time = time.time()

        # Select target hub
        hub = await self._select_hub(request)

        if hub is None:
            logger.warning(f"No hub available for voice request {request.request_id}")
            # Fallback to API-side TTS (if available)
            return await self._fallback_speak(request, start_time)

        # Acquire voice mutex
        duration_estimate = len(request.text) / 15  # ~15 chars/second
        if not await self._voice_mutex.acquire(hub.node_id, duration_estimate):
            # Wait briefly and retry
            await asyncio.sleep(0.5)
            if not await self._voice_mutex.acquire(hub.node_id, duration_estimate):
                return VoiceResult(
                    success=False,
                    request_id=request.request_id,
                    hub_id=None,
                    room=None,
                    duration_ms=(time.time() - start_time) * 1000,
                    error="Voice mutex unavailable",
                )

        try:
            # Send to hub
            result = await self._send_to_hub(hub, request)
            return VoiceResult(
                success=result.get("success", False),
                request_id=request.request_id,
                hub_id=hub.node_id,
                room=self._get_hub_room(hub),
                duration_ms=(time.time() - start_time) * 1000,
                error=result.get("error"),
            )

        finally:
            await self._voice_mutex.release(hub.node_id)

    async def _select_hub(self, request: VoiceRequest) -> ServiceInstance | None:
        """Select the appropriate hub for voice output.

        Args:
            request: Voice request.

        Returns:
            Selected hub or None.
        """
        if request.target == VoiceTarget.API_ONLY:
            return None

        # Get available hubs
        hubs = await self._service_registry.discover(ServiceType.HUB, healthy_only=True)

        if not hubs:
            return None

        if request.target == VoiceTarget.SPECIFIC_HUB and request.target_hub_id:
            # Find specific hub
            for hub in hubs:
                if hub.node_id == request.target_hub_id:
                    return hub
            return None

        if request.target == VoiceTarget.SPECIFIC_ROOM and request.target_room:
            # Find hub serving the room
            for hub in hubs:
                hub_rooms = hub.metadata.get("rooms", [])
                if request.target_room in hub_rooms:
                    return hub
            # Fallback to any hub
            return hubs[0] if hubs else None

        if request.target == VoiceTarget.AUTO:
            # Select based on presence
            return await self._select_presence_aware_hub(hubs)

        if request.target == VoiceTarget.NEAREST:
            # Select nearest (for now, just first healthy one)
            return hubs[0] if hubs else None

        if request.target == VoiceTarget.ALL:
            # For broadcast, return first hub (will need special handling)
            return hubs[0] if hubs else None

        return hubs[0] if hubs else None

    async def _select_presence_aware_hub(
        self,
        hubs: list[ServiceInstance],
    ) -> ServiceInstance | None:
        """Select hub based on presence detection.

        Args:
            hubs: Available hubs.

        Returns:
            Selected hub or None.
        """
        if not hubs:
            return None

        # Get presence data from Redis (simplified)
        try:
            presence_data = await self._redis.get("kagami:presence:current")
            if presence_data:
                presence = json.loads(presence_data.decode())
                current_room = presence.get("room")

                if current_room:
                    # Find hub serving current room
                    for hub in hubs:
                        hub_rooms = hub.metadata.get("rooms", [])
                        if current_room in hub_rooms:
                            return hub
        except Exception as e:
            logger.debug(f"Presence lookup failed: {e}")

        # Fallback to first available hub
        return hubs[0]

    async def _send_to_hub(
        self,
        hub: ServiceInstance,
        request: VoiceRequest,
    ) -> dict[str, Any]:
        """Send voice request to a hub.

        Args:
            hub: Target hub.
            request: Voice request.

        Returns:
            Response dictionary.
        """
        url = f"http://{hub.address}:{hub.port}/api/voice/speak"

        try:
            async with self._http_session.post(
                url,
                json=request.to_dict(),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return {
                        "success": False,
                        "error": f"Hub returned {resp.status}",
                    }
        except Exception as e:
            logger.error(f"Failed to send to hub {hub.node_id}: {e}")
            return {"success": False, "error": str(e)}

    async def _fallback_speak(
        self,
        request: VoiceRequest,
        start_time: float,
    ) -> VoiceResult:
        """Fallback to API-side TTS.

        Args:
            request: Voice request.
            start_time: Request start time.

        Returns:
            VoiceResult.
        """
        try:
            # Import voice effector for local TTS
            from kagami.core.effectors.voice import VoiceTarget as EffectorTarget
            from kagami.core.effectors.voice import speak

            result = await speak(
                request.text,
                target=EffectorTarget.DESKTOP,  # API server speakers
            )

            return VoiceResult(
                success=result.success,
                request_id=request.request_id,
                hub_id="api-fallback",
                room="api-server",
                duration_ms=(time.time() - start_time) * 1000,
                error=result.error if not result.success else None,
            )

        except Exception as e:
            logger.error(f"Fallback TTS failed: {e}")
            return VoiceResult(
                success=False,
                request_id=request.request_id,
                hub_id=None,
                room=None,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )

    async def _process_queue(self) -> None:
        """Background task to process voice request queue."""
        while True:
            try:
                request = await self._request_queue.get()
                await self._execute_request(request)
                self._request_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue processing error: {e}")
                await asyncio.sleep(1)

    def _generate_request_id(self, text: str) -> str:
        """Generate unique request ID."""
        content = f"{time.time()}-{text[:20]}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _get_hub_room(self, hub: ServiceInstance) -> str | None:
        """Get primary room for a hub."""
        rooms = hub.metadata.get("rooms", [])
        return rooms[0] if rooms else None

    def get_status(self) -> dict[str, Any]:
        """Get coordinator status.

        Returns:
            Status dictionary.
        """
        return {
            "initialized": self._initialized,
            "queue_size": self._request_queue.qsize(),
            "hub_count": len(self._hub_capabilities),
        }


# =============================================================================
# Singleton Factory
# =============================================================================

_coordinator: ConsensusVoiceCoordinator | None = None
_coordinator_lock = asyncio.Lock()


async def get_consensus_voice() -> ConsensusVoiceCoordinator:
    """Get or create the ConsensusVoiceCoordinator.

    Returns:
        ConsensusVoiceCoordinator singleton.
    """
    global _coordinator

    async with _coordinator_lock:
        if _coordinator is None:
            _coordinator = ConsensusVoiceCoordinator()
            await _coordinator.initialize()

    return _coordinator


async def shutdown_consensus_voice() -> None:
    """Shutdown the ConsensusVoiceCoordinator."""
    global _coordinator

    if _coordinator:
        await _coordinator.shutdown()
        _coordinator = None


# =============================================================================
# Convenience Functions
# =============================================================================


async def consensus_speak(
    text: str,
    *,
    priority: VoicePriority = VoicePriority.NORMAL,
    room: str | None = None,
) -> VoiceResult:
    """Speak text through consensus voice system.

    Convenience function for common use cases.

    Args:
        text: Text to speak.
        priority: Message priority.
        room: Target room (optional).

    Returns:
        VoiceResult.

    Example:
        >>> result = await consensus_speak("Dinner is ready", room="kitchen")
    """
    coordinator = await get_consensus_voice()

    target = VoiceTarget.AUTO
    if room:
        target = VoiceTarget.SPECIFIC_ROOM

    return await coordinator.speak(
        text,
        priority=priority,
        target=target,
        target_room=room,
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "ConsensusVoiceCoordinator",
    "DistributedVoiceMutex",
    "HubVoiceCapability",
    "VoicePriority",
    "VoiceRequest",
    "VoiceResult",
    "VoiceTarget",
    "consensus_speak",
    "get_consensus_voice",
    "shutdown_consensus_voice",
]


# =============================================================================
# 鏡
# Voice flows. Hubs coordinate. The organism speaks as one.
# h(x) ≥ 0. Always.
# =============================================================================
