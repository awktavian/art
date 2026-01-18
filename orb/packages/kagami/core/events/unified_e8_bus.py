"""Unified E8 Event Bus - All Events via Fano-Routed E8 Protocol.

CONSOLIDATION (Dec 2, 2025):
============================
This module consolidates ALL event systems onto the E8 Fano-routed protocol:

DELETED/DEPRECATED:
- ExperienceBus → Use UnifiedE8Bus.publish_experience()
- AppEventBus → Use UnifiedE8Bus.publish()
- DistributedEventBus → Use UnifiedE8Bus with Redis mode
- EventBus (core/event_bus.py) → Use UnifiedE8Bus

KEPT (internal use only):
- ECS EventBus (kagami/core/world/ecs.py) - entity-component internal

ARCHITECTURE:
=============

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                      UNIFIED E8 EVENT BUS                                │
    │                                                                          │
    │   ALL EVENTS → E8 Protocol → Fano Routing → 7 Colonies                  │
    │                                                                          │
    │   ┌─────────────────────────────────────────────────────────────────────┐│
    │   │  Control Tokens:                                                    ││
    │   │  - DATA (0x02): Normal data                                        ││
    │   │  - QUERY (0x03): Memory query                                      ││
    │   │  - EXPERIENCE (0x10): Learning outcomes (was ExperienceBus)        ││
    │   │  - APP_EVENT (0x11): App events (was AppEventBus)                  ││
    │   │  - BROADCAST (0x05): All colonies                                  ││
    │   │  - FANO (0x06): Fano-aligned (3 colonies)                          ││
    │   │  - CHARACTER (0x12): Character feedback                            ││
    │   │  - SYNC (0x07): Synchronization                                    ││
    │   └─────────────────────────────────────────────────────────────────────┘│
    │                                                                          │
    │   FANO ROUTING: eᵢ × eⱼ = ±eₖ                                           │
    │   7 lines → 7 colonies → Cyclic routing                                 │
    │                                                                          │
    │   E8 SEMANTIC ROUTING:                                                   │
    │   - 240 E8 roots partitioned across 7 colonies (~34 each)              │
    │   - Topic prefix → Colony mapping (semantic, not random)                │
    │   - Within-colony hash for sub-distribution                             │
    │                                                                          │
    └─────────────────────────────────────────────────────────────────────────┘

USAGE:
======
    from kagami.core.events.unified_e8_bus import get_unified_bus

    bus = get_unified_bus()

    # Publish event (replaces AppEventBus)
    await bus.publish("topic.name", {"key": "value"})

    # Publish experience (replaces ExperienceBus)
    await bus.publish_experience(outcome)

    # Subscribe
    bus.subscribe("topic.name", handler)

Created: December 2, 2025
Updated: December 8, 2025 - Semantic E8 routing (replaces random MD5 hash)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
import zlib
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import torch

logger = logging.getLogger(__name__)


# =============================================================================
# SEMANTIC E8 ROUTING
# =============================================================================
#
# E8 has 240 roots. We partition these semantically across 7 colonies:
#
#   Colony 0 (Spark):   roots   0-33  - Creation, generation, ideation
#   Colony 1 (Forge):   roots  34-67  - Implementation, execution, building
#   Colony 2 (Flow):    roots  68-101 - Debugging, recovery, health
#   Colony 3 (Nexus):   roots 102-135 - Memory, integration, storage
#   Colony 4 (Beacon):  roots 136-169 - Planning, routing, orchestration
#   Colony 5 (Grove):   roots 170-203 - Research, learning, documentation
#   Colony 6 (Crystal): roots 204-239 - Verification, testing, receipts
#
# Topic prefixes map to colonies based on semantic meaning.
# Within each colony's partition, we use fast hash for distribution.

# Colony root partitions: (start, end) for each colony
_E8_COLONY_PARTITIONS: list[tuple[int, int]] = [
    (0, 34),  # Spark: create, generate
    (34, 68),  # Forge: build, execute
    (68, 102),  # Flow: debug, fix, recover
    (102, 136),  # Nexus: memory, store, experience
    (136, 170),  # Beacon: plan, route, config
    (170, 204),  # Grove: research, learn, query
    (204, 240),  # Crystal: test, verify, receipt
]

# Topic prefix → Colony mapping (semantic routing)
_TOPIC_COLONY_MAP: dict[str, int] = {
    # Colony 0 - Spark (Creation)
    "create": 0,
    "generate": 0,
    "ideate": 0,
    "new": 0,
    "brainstorm": 0,
    "imagine": 0,
    "design": 0,
    "spark": 0,
    "init": 0,
    # Colony 1 - Forge (Implementation)
    "build": 1,
    "implement": 1,
    "execute": 1,
    "forge": 1,
    "character": 1,
    "render": 1,
    "compile": 1,
    "process": 1,
    "transform": 1,
    "action": 1,
    # Colony 2 - Flow (Recovery)
    "debug": 2,
    "fix": 2,
    "recover": 2,
    "error": 2,
    "health": 2,
    "heal": 2,
    "repair": 2,
    "fallback": 2,
    "retry": 2,
    "flow": 2,
    # Colony 3 - Nexus (Integration)
    "memory": 3,
    "connect": 3,
    "integrate": 3,
    "store": 3,
    "experience": 3,
    "bind": 3,
    "link": 3,
    "nexus": 3,
    "cache": 3,
    "persist": 3,
    # Colony 4 - Beacon (Planning)
    "plan": 4,
    "schedule": 4,
    "route": 4,
    "orchestrate": 4,
    "config": 4,
    "beacon": 4,
    "coordinate": 4,
    "dispatch": 4,
    "intent": 4,
    "goal": 4,
    # Colony 5 - Grove (Research)
    "research": 5,
    "search": 5,
    "query": 5,
    "document": 5,
    "learn": 5,
    "explore": 5,
    "grove": 5,
    "discover": 5,
    "analyze": 5,
    "study": 5,
    # Colony 6 - Crystal (Verification)
    "test": 6,
    "verify": 6,
    "validate": 6,
    "receipt": 6,
    "audit": 6,
    "crystal": 6,
    "check": 6,
    "assert": 6,
    "confirm": 6,
    "proof": 6,
}


def semantic_e8_index(topic: str, source_colony: int | None = None) -> tuple[int, int]:
    """Compute E8 index from topic using semantic routing.

    Returns (e8_index, colony) where:
    - e8_index is in [0, 240) within the colony's partition
    - colony is in [0, 7)

    Args:
        topic: Event topic string (e.g., "experience.app_name", "forge.character")
        source_colony: Override colony (if known). If None, inferred from topic.

    Returns:
        Tuple of (e8_index, colony)
    """
    # Determine colony from topic prefix or use override
    if source_colony is not None and 0 <= source_colony < 7:
        colony = source_colony
    else:
        # Extract first segment of topic
        prefix = topic.split(".")[0].lower() if "." in topic else topic.lower()

        # Look up colony from semantic map
        colony = _TOPIC_COLONY_MAP.get(prefix, 3)  # Default to Nexus (integration)

    # Get partition range for this colony
    start, end = _E8_COLONY_PARTITIONS[colony]
    partition_size = end - start  # 34 or 36

    # Fast deterministic hash within partition (not cryptographic).
    #
    # IMPORTANT: Python's built-in hash() is *process-randomized* by default, which
    # breaks cross-instance determinism unless PYTHONHASHSEED is fixed. We use a
    # stable 32-bit checksum so topic → E8 index mapping is consistent across nodes.
    topic_hash = zlib.crc32(topic.encode("utf-8")) & 0xFFFFFFFF
    local_offset = topic_hash % partition_size

    e8_index = start + local_offset
    return e8_index, colony


# =============================================================================
# EXTENDED CONTROL TOKENS
# =============================================================================


class E8ControlToken(IntEnum):
    """Extended control tokens for unified E8 bus.

    Consolidates all event types into E8 protocol.
    """

    # Core protocol (from E8MessageBus)
    START = 0x00
    END = 0x01
    DATA = 0x02
    QUERY = 0x03
    RESPONSE = 0x04
    BROADCAST = 0x05
    FANO = 0x06
    SYNC = 0x07
    HEARTBEAT = 0x08
    ERROR = 0xFF

    # Extended (consolidation)
    EXPERIENCE = 0x10  # Learning outcomes (was ExperienceBus)
    APP_EVENT = 0x11  # App events (was AppEventBus)
    CHARACTER = 0x12  # Character feedback
    RECEIPT = 0x13  # Receipt emission
    DISTRIBUTED = 0x14  # Cross-instance (was DistributedEventBus)


# Fano plane lines (CANONICAL SOURCE: kagami_math/fano_plane.py)
# These are derived from the G₂ 3-form φ for mathematical correctness.
# 0-indexed for colony routing (colonies 0-6 map to octonion imaginaries e₁-e₇)
from kagami_math.catastrophe_constants import COLONY_NAMES
from kagami_math.fano_plane import get_fano_lines_zero_indexed

FANO_LINES = get_fano_lines_zero_indexed()


# =============================================================================
# EVENT STRUCTURES
# =============================================================================


@dataclass
class E8Event:
    """Unified E8-encoded event."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    token: E8ControlToken = E8ControlToken.DATA
    topic: str = ""

    # Routing
    source_colony: int = 0
    target_colony: int = -1  # -1 = broadcast
    fano_route: tuple[int, int, int] | None = None

    # E8 encoding
    e8_index: int = 0  # Primary E8 root (0-239)
    e8_residuals: list[int] = field(default_factory=list[Any])

    # Payload
    payload: dict[str, Any] = field(default_factory=dict[str, Any])
    data_8d: torch.Tensor | None = None

    # Metadata
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = ""
    source_instance: str = ""

    def to_bytes(self) -> bytes:
        """Serialize to E8 byte format."""
        result = bytearray()

        # Byte 0: Control token
        result.append(self.token.value)

        # Byte 1: Routing (src[3] | tgt[3] | levels[2])
        # The header has only 2 bits for levels, so we can represent:
        # - 1 base index + up to 3 residual bytes (4 total levels)
        target = self.target_colony if self.target_colony >= 0 else 7
        residuals = self.e8_residuals[:3]
        num_levels = len(residuals) + 1
        packed = (self.source_colony & 0x07) << 5 | (target & 0x07) << 2 | ((num_levels - 1) & 0x03)
        result.append(packed)

        # E8 indices
        result.append(self.e8_index & 0xFF)
        for idx in residuals:
            result.append(idx & 0xFF)

        return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes, payload: dict[str, Any] | None = None) -> E8Event:
        """Deserialize from E8 byte format."""
        if len(data) < 2:
            raise ValueError("E8Event too short")

        token = E8ControlToken(data[0])
        packed = data[1]
        source = (packed >> 5) & 0x07
        target = (packed >> 2) & 0x07
        target = target if target < 7 else -1
        num_levels = (packed & 0x03) + 1

        e8_index = data[2] if len(data) > 2 else 0
        e8_residuals = list(data[3 : 3 + num_levels - 1]) if len(data) > 3 else []

        return cls(
            token=token,
            source_colony=source,
            target_colony=target,
            e8_index=e8_index,
            e8_residuals=e8_residuals,
            payload=payload or {},
        )

    def to_json(self) -> str:
        """Serialize to JSON for Redis."""
        return json.dumps(
            {
                "id": self.event_id,
                "token": self.token.value,
                "topic": self.topic,
                "source": self.source_colony,
                "target": self.target_colony,
                "e8_index": self.e8_index,
                "e8_residuals": self.e8_residuals,
                "payload": self.payload,
                "ts": self.timestamp,
                "correlation_id": self.correlation_id,
                "source_instance": self.source_instance,
            },
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, data: str) -> E8Event:
        """Deserialize from JSON."""
        d = json.loads(data)
        return cls(
            event_id=d.get("id", ""),
            token=E8ControlToken(d.get("token", 2)),
            topic=d.get("topic", ""),
            source_colony=d.get("source", 0),
            target_colony=d.get("target", -1),
            e8_index=d.get("e8_index", 0),
            e8_residuals=d.get("e8_residuals", []),
            payload=d.get("payload", {}),
            timestamp=d.get("ts", time.time()),
            correlation_id=d.get("correlation_id", ""),
            source_instance=d.get("source_instance", ""),
        )


@dataclass
class OperationOutcome:
    """Operation outcome for experience learning.

    Unified from ExperienceBus.OperationOutcome.
    """

    operation: str
    success: bool
    app: str | None = None
    correlation_id: str = ""
    duration_ms: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_e8_event(self) -> E8Event:
        """Convert to E8Event for bus transmission."""
        topic = f"experience.{self.app or 'unknown'}"
        # Semantic E8 routing: experiences → Nexus colony (memory/integration)
        e8_index, colony = semantic_e8_index(topic, source_colony=3)

        return E8Event(
            token=E8ControlToken.EXPERIENCE,
            topic=topic,
            source_colony=colony,
            e8_index=e8_index,
            payload={
                "operation": self.operation,
                "success": self.success,
                "app": self.app,
                "duration_ms": self.duration_ms,
                "error": self.error,
                **self.metadata,
            },
            correlation_id=self.correlation_id,
        )


# =============================================================================
# UNIFIED E8 BUS
# =============================================================================


Subscriber = Callable[[E8Event], Awaitable[None]]


class UnifiedE8Bus:
    """Unified event bus using E8 Fano-routed protocol.

    Consolidates ALL event systems:
    - ExperienceBus → publish_experience()
    - AppEventBus → publish()
    - DistributedEventBus → publish() with redis_broadcast=True
    - EventBus → subscribe/publish

    All events are encoded as E8 indices and routed via Fano plane.
    """

    def __init__(
        self,
        instance_id: str | None = None,
        use_redis: bool = False,
        redis_channel: str = "kagami:e8:events",
        queue_size: int = 1000,
        high_water_mark: int = 800,
        low_water_mark: int = 200,
    ):
        """Initialize unified E8 bus.

        Args:
            instance_id: Unique instance ID (for distributed mode)
            use_redis: Enable Redis distribution
            redis_channel: Redis channel prefix
            queue_size: Maximum queue size
            high_water_mark: Start backpressure when queue exceeds this
            low_water_mark: Stop backpressure when queue drops below this
        """
        self.instance_id = instance_id or str(uuid.uuid4())[:8]
        self.use_redis = use_redis
        self.redis_channel = redis_channel

        # Subscribers by topic
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list[Any])

        # Colony-specific subscribers
        self._colony_subscribers: dict[int, list[Subscriber]] = defaultdict(list[Any])

        # Recent events ring buffer
        self._recent_events: list[E8Event] = []
        self._recent_max = 256

        # Fano routing table
        self._fano_table = self._build_fano_table()

        # E8 roots (lazy loaded)
        self._e8_roots: torch.Tensor | None = None

        # Processing with backpressure
        self._queue_size = queue_size
        self._high_water_mark = high_water_mark
        self._low_water_mark = low_water_mark
        self._event_queue: asyncio.Queue[E8Event] = asyncio.Queue(maxsize=queue_size)
        self._running = False
        self._processor_task: asyncio.Task | None = None

        # Backpressure state
        self._backpressure_active = False
        self._backpressure_event = asyncio.Event()
        self._backpressure_event.set()  # Initially not under pressure

        # Backpressure statistics
        self._stats = {
            "events_published": 0,
            "events_dropped": 0,
            "backpressure_activations": 0,
            "high_priority_bypasses": 0,
        }

        # Redis (lazy)
        self._redis = None
        self._redis_task: asyncio.Task | None = None

        logger.info(
            f"✅ UnifiedE8Bus initialized: instance={self.instance_id}, backpressure={high_water_mark}/{low_water_mark}"
        )

    def _build_fano_table(self) -> dict[int, list[tuple[int, int]]]:
        """Build Fano routing lookup."""
        table: dict[int, list[tuple[int, int]]] = {i: [] for i in range(7)}
        for i, j, k in FANO_LINES:
            table[i].append((j, k))
            table[j].append((k, i))
            table[k].append((i, j))
        return table

    @property
    def e8_roots(self) -> torch.Tensor:
        """Lazy load E8 roots."""
        if self._e8_roots is None:
            from kagami_math.dimensions import generate_e8_roots

            self._e8_roots = generate_e8_roots()
        return self._e8_roots

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    async def start(self) -> None:
        """Start event processing."""
        if self._running:
            return

        self._running = True
        self._processor_task = asyncio.create_task(
            self._process_events(),
            name="e8_bus_processor",
        )

        if self.use_redis:
            await self._start_redis()

        logger.info("✅ UnifiedE8Bus started")

    async def stop(self) -> None:
        """Stop event processing."""
        self._running = False

        if self._processor_task and not self._processor_task.done():
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        if self._redis_task and not self._redis_task.done():
            self._redis_task.cancel()
            try:
                await self._redis_task
            except asyncio.CancelledError:
                pass

        logger.info("✅ UnifiedE8Bus stopped")

    # =========================================================================
    # SUBSCRIPTION
    # =========================================================================

    def subscribe(self, topic: str, handler: Subscriber) -> None:
        """Subscribe to a topic.

        Args:
            topic: Topic pattern (e.g., "experience.*", "character.feedback")
            handler: Async handler function
        """
        if handler not in self._subscribers[topic]:
            self._subscribers[topic].append(handler)
            logger.debug(f"📡 Subscribed to {topic}: {handler.__name__}")

    def subscribe_colony(self, colony: int, handler: Subscriber) -> None:
        """Subscribe to all events for a specific colony.

        Args:
            colony: Colony index (0-6)
            handler: Async handler function
        """
        if handler not in self._colony_subscribers[colony]:
            self._colony_subscribers[colony].append(handler)
            logger.debug(f"📡 Colony {COLONY_NAMES[colony]} subscriber added")

    def unsubscribe(self, topic: str, handler: Subscriber) -> bool:
        """Unsubscribe from a topic."""
        if topic in self._subscribers and handler in self._subscribers[topic]:
            self._subscribers[topic].remove(handler)
            return True
        return False

    # =========================================================================
    # PUBLISHING
    # =========================================================================

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        token: E8ControlToken = E8ControlToken.APP_EVENT,
        source_colony: int = 0,
        target_colony: int = -1,
        use_fano: bool = False,
        correlation_id: str | None = None,
    ) -> E8Event:
        """Publish an event.

        This replaces AppEventBus.publish() and EventBus.publish().

        Args:
            topic: Event topic
            payload: Event payload
            token: Control token type
            source_colony: Source colony (0-6)
            target_colony: Target colony (-1 for broadcast)
            use_fano: Use Fano-aligned routing
            correlation_id: Optional correlation ID

        Returns:
            The published E8Event
        """
        # Semantic E8 routing: topic → colony → partitioned E8 index
        e8_index, inferred_colony = semantic_e8_index(
            topic, source_colony if source_colony > 0 else None
        )

        # Use inferred colony if source wasn't specified
        if source_colony == 0:
            source_colony = inferred_colony

        # Determine Fano route if requested
        fano_route = None
        if use_fano and source_colony < 7:
            partners = self._fano_table.get(source_colony, [])
            if partners:
                j, k = partners[0]
                fano_route = (source_colony, j, k)

        event = E8Event(
            token=token,
            topic=topic,
            source_colony=source_colony,
            target_colony=target_colony,
            fano_route=fano_route,
            e8_index=e8_index,
            payload=payload,
            correlation_id=correlation_id or "",
            source_instance=self.instance_id,
        )

        await self._enqueue(event)
        return event

    async def publish_experience(
        self,
        outcome: OperationOutcome,
    ) -> E8Event:
        """Publish a learning experience outcome.

        This replaces ExperienceBus.publish().

        Args:
            outcome: Operation outcome

        Returns:
            The published E8Event
        """
        event = outcome.to_e8_event()
        event.source_instance = self.instance_id
        await self._enqueue(event)
        return event

    async def broadcast(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        source_colony: int = 0,
    ) -> E8Event:
        """Broadcast to all colonies.

        Args:
            topic: Event topic
            payload: Event payload
            source_colony: Source colony

        Returns:
            The published E8Event
        """
        return await self.publish(
            topic=topic,
            payload=payload,
            token=E8ControlToken.BROADCAST,
            source_colony=source_colony,
            target_colony=-1,
        )

    async def send_fano(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        source_colony: int,
    ) -> E8Event:
        """Send via Fano-aligned routing (3 colonies).

        Args:
            topic: Event topic
            payload: Event payload
            source_colony: Source colony (determines Fano line)

        Returns:
            The published E8Event
        """
        return await self.publish(
            topic=topic,
            payload=payload,
            token=E8ControlToken.FANO,
            source_colony=source_colony,
            use_fano=True,
        )

    # =========================================================================
    # PROCESSING
    # =========================================================================

    async def _enqueue(self, event: E8Event) -> None:
        """Add event to processing queue with backpressure management.

        Backpressure strategy:
        - High-priority events (EXPERIENCE, SYNC, ERROR) bypass backpressure
        - Normal events wait when queue exceeds high_water_mark
        - Backpressure releases when queue drops below low_water_mark
        """
        # Auto-start the bus on first publish.
        if not self._running:
            await self.start()

        queue_size = self._event_queue.qsize()

        # Check if this is a high-priority event that bypasses backpressure
        high_priority_tokens = {
            E8ControlToken.EXPERIENCE,
            E8ControlToken.SYNC,
            E8ControlToken.ERROR,
            E8ControlToken.HEARTBEAT,
        }
        is_high_priority = event.token in high_priority_tokens

        # Manage backpressure state
        if queue_size >= self._high_water_mark and not self._backpressure_active:
            self._backpressure_active = True
            self._backpressure_event.clear()
            self._stats["backpressure_activations"] += 1
            logger.warning(f"⚠️ E8Bus backpressure ON: queue={queue_size}/{self._queue_size}")
        elif queue_size <= self._low_water_mark and self._backpressure_active:
            self._backpressure_active = False
            self._backpressure_event.set()
            logger.info(f"✅ E8Bus backpressure OFF: queue={queue_size}/{self._queue_size}")

        # Apply backpressure (high-priority events bypass)
        if self._backpressure_active and not is_high_priority:
            try:
                # Wait up to 100ms for backpressure to clear
                await asyncio.wait_for(self._backpressure_event.wait(), timeout=0.1)
            except TimeoutError:
                # Still under pressure after timeout - drop non-critical events
                self._stats["events_dropped"] += 1
                logger.debug(f"E8Bus: Dropped event {event.topic} (backpressure)")
                return

        if is_high_priority and self._backpressure_active:
            self._stats["high_priority_bypasses"] += 1

        try:
            self._event_queue.put_nowait(event)
            self._stats["events_published"] += 1

            # Track recent
            self._recent_events.append(event)
            if len(self._recent_events) > self._recent_max:
                self._recent_events.pop(0)

        except asyncio.QueueFull:
            self._stats["events_dropped"] += 1
            logger.warning(f"⚠️ E8Bus queue full, dropped: {event.topic}")

    async def _process_events(self) -> None:
        """Background event processor."""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0,
                )
                await self._dispatch(event)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"E8Bus processor error: {e}")

    async def _dispatch(self, event: E8Event) -> None:
        """Dispatch event to subscribers (parallel for performance)."""
        tasks = []

        def _wrap_handler(handler: Subscriber, ev: E8Event) -> Awaitable[None]:
            """Wrap handler to ensure it returns an awaitable."""
            result = handler(ev)
            # If handler is sync (returns None or non-awaitable), wrap it
            if result is None:

                async def _noop() -> None:
                    pass

                return _noop()
            if not asyncio.iscoroutine(result) and not asyncio.isfuture(result):

                async def _wrap() -> None:
                    return result  # type: ignore

                return _wrap()
            return result

        # Topic subscribers
        for topic_pattern, handlers in self._subscribers.items():
            if self._matches_topic(event.topic, topic_pattern):
                tasks.extend([_wrap_handler(handler, event) for handler in handlers])

        # Colony subscribers
        if event.target_colony >= 0:
            tasks.extend(
                [
                    _wrap_handler(handler, event)
                    for handler in self._colony_subscribers.get(event.target_colony, [])
                ]
            )

        # Broadcast to all colonies
        if event.target_colony == -1 or event.token == E8ControlToken.BROADCAST:
            for colony in range(7):
                tasks.extend(
                    [
                        _wrap_handler(handler, event)
                        for handler in self._colony_subscribers.get(colony, [])
                    ]
                )

        # Fano routing
        if event.fano_route:
            for colony in event.fano_route:
                if colony != event.source_colony:
                    tasks.extend(
                        [
                            _wrap_handler(handler, event)
                            for handler in self._colony_subscribers.get(colony, [])
                        ]
                    )

        # Execute all handlers in parallel
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for _i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Handler error for {event.topic}: {result}")

        # Redis distribution
        if self.use_redis and event.source_instance == self.instance_id:
            await self._publish_redis(event)

    def _matches_topic(self, topic: str, pattern: str) -> bool:
        """Check if topic matches pattern (supports * wildcard)."""
        if pattern == topic:
            return True
        if pattern.endswith(".*"):
            return topic.startswith(pattern[:-1])
        if pattern == "*":
            return True
        return False

    # =========================================================================
    # REDIS DISTRIBUTION
    # =========================================================================

    async def _start_redis(self) -> None:
        """Start Redis listener."""
        try:
            from kagami.core.caching.redis import RedisClientFactory

            self._redis = RedisClientFactory.get_client(
                purpose="events",  # type: ignore[arg-type]
                async_mode=True,
            )
            self._redis_task = asyncio.create_task(
                self._listen_redis(),
                name="e8_bus_redis",
            )
            logger.info("✅ E8Bus Redis listener started")
        except Exception as e:
            logger.warning(f"⚠️ Redis not available: {e}")
            self.use_redis = False

    async def _publish_redis(self, event: E8Event) -> None:
        """Publish event to Redis."""
        if self._redis is None:
            return
        try:  # type: ignore[unreachable]
            channel = f"{self.redis_channel}:{event.topic}"
            await self._redis.publish(channel, event.to_json())
        except Exception as e:
            logger.debug(f"Redis publish failed: {e}")

    async def _listen_redis(self) -> None:
        """Listen for Redis events."""
        if self._redis is None:
            return

        try:  # type: ignore[unreachable]
            pubsub = self._redis.pubsub()
            await pubsub.psubscribe(f"{self.redis_channel}:*")

            while self._running:
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    if message and message["type"] == "pmessage":
                        data = message["data"]
                        if isinstance(data, bytes):
                            data = data.decode()
                        event = E8Event.from_json(data)

                        # Don't process own events
                        if event.source_instance != self.instance_id:
                            await self._dispatch(event)

                except TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break

        except Exception as e:
            logger.error(f"Redis listener error: {e}")

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def recent_events(self, limit: int = 100) -> list[E8Event]:
        """Get recent events."""
        return self._recent_events[-limit:]

    def list_subscribers(self) -> dict[str, int]:
        """List subscriber counts by topic."""
        return {topic: len(handlers) for topic, handlers in self._subscribers.items()}

    def get_stats(self) -> dict[str, Any]:
        """Get bus statistics (for vitals/health endpoints)."""
        queue_size = self._event_queue.qsize()
        return {
            "instance_id": self.instance_id,
            "running": self._running,
            "use_redis": self.use_redis,
            "redis_channel": self.redis_channel,
            "queued": queue_size,
            "queue_capacity": self._queue_size,
            "queue_utilization": queue_size / self._queue_size if self._queue_size > 0 else 0,
            "recent_events": len(self._recent_events),
            "recent_max": self._recent_max,
            "subscribers": self.list_subscribers(),
            "colony_subscribers": {
                COLONY_NAMES[i]: len(self._colony_subscribers.get(i, [])) for i in range(7)
            },
            # Backpressure stats
            "backpressure": {
                "active": self._backpressure_active,
                "high_water_mark": self._high_water_mark,
                "low_water_mark": self._low_water_mark,
                "events_published": self._stats["events_published"],
                "events_dropped": self._stats["events_dropped"],
                "activations": self._stats["backpressure_activations"],
                "high_priority_bypasses": self._stats["high_priority_bypasses"],
                "drop_rate": (
                    self._stats["events_dropped"] / self._stats["events_published"]
                    if self._stats["events_published"] > 0
                    else 0
                ),
            },
        }

    @property
    def backpressure_active(self) -> bool:
        """Check if backpressure is currently active."""
        return self._backpressure_active

    def reset_stats(self) -> None:
        """Reset backpressure statistics."""
        self._stats = {
            "events_published": 0,
            "events_dropped": 0,
            "backpressure_activations": 0,
            "high_priority_bypasses": 0,
        }


# =============================================================================
# SINGLETON
# =============================================================================

_unified_bus: UnifiedE8Bus | None = None


def get_unified_bus(
    instance_id: str | None = None,
    use_redis: bool = False,
) -> UnifiedE8Bus:
    """Get or create the singleton unified E8 bus.

    Args:
        instance_id: Instance ID (only used on first call)
        use_redis: Enable Redis (only used on first call)

    Returns:
        UnifiedE8Bus singleton
    """
    global _unified_bus
    if _unified_bus is None:
        _unified_bus = UnifiedE8Bus(
            instance_id=instance_id,
            use_redis=use_redis,
        )
    return _unified_bus


__all__ = [
    "COLONY_NAMES",
    "FANO_LINES",
    "E8ControlToken",
    "E8Event",
    "OperationOutcome",
    "UnifiedE8Bus",
    "get_unified_bus",
    "semantic_e8_index",
]
