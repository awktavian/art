"""Cross-Hub CRDT Synchronization — Distributed state across Kagami mesh.

This module extends the colony-level CRDT system to work across multiple
Kagami Hubs in a mesh network. It provides:

1. Vector clocks for causality tracking across hubs
2. Delta-state synchronization for bandwidth efficiency
3. Bidirectional sync with Rust hub CRDTs
4. Conflict resolution following CALM principles

Architecture:
```
┌─────────────────────────────────────────────────────────────────────┐
│                   CROSS-HUB CRDT SYNCHRONIZATION                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Python API Server                        Rust Hubs (Mesh)          │
│   ──────────────────                       ────────────────          │
│   • CrossHubCRDT                          • CRDTState (sync.rs)     │
│   • VectorClock                           • VectorClock              │
│   • LWW, GSet, ORSet                      • LWW, GCounter, ORSet    │
│                                                                      │
│   ┌─────────────────┐      HTTP/WS        ┌─────────────────┐       │
│   │  CrossHubCRDT   │◄──────────────────►│  StateSyncProto │       │
│   │  (Python)       │     /api/mesh/      │  (Rust)         │       │
│   └─────────────────┘     crdt-state      └─────────────────┘       │
│           │                                       │                  │
│           ▼                                       ▼                  │
│   ┌─────────────────┐                     ┌─────────────────┐       │
│   │  Redis/etcd     │                     │  Local StateCache│       │
│   │  (persistence)  │                     │  (in-memory)     │       │
│   └─────────────────┘                     └─────────────────┘       │
│                                                                      │
│   Sync Flow:                                                        │
│   1. Hub sends CRDTState to API via WebSocket/HTTP                  │
│   2. Python merges using vector clock comparison                    │
│   3. Python broadcasts merged state to other hubs                   │
│   4. All nodes converge to same state (CRDT guarantees)            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

Colony: Nexus (e₄) — Connection and bridge across locations
h(x) ≥ 0. Always.

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Generic, TypeVar

from kagami.core.caching.redis import RedisClientFactory

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Vector Clock for Causality Tracking
# =============================================================================


class ClockOrdering(Enum):
    """Ordering relationship between vector clocks."""

    BEFORE = auto()  # This clock happened before the other
    AFTER = auto()  # This clock happened after the other
    CONCURRENT = auto()  # Clocks are concurrent (no causal relationship)
    EQUAL = auto()  # Clocks are equal


@dataclass
class VectorClock:
    """Vector clock for tracking causality across hubs.

    Provides partial ordering of events across distributed hubs.
    Each hub maintains its own logical clock, and the vector clock
    tracks the maximum observed timestamp from each hub.

    Properties:
        - If VC(A) < VC(B), then A happened before B
        - If VC(A) || VC(B), then A and B are concurrent
        - Merge: VC(A ⊔ B) = max(VC(A), VC(B)) for each component

    Example:
        >>> clock = VectorClock()
        >>> clock.increment("hub-1")
        >>> clock.get("hub-1")
        1
        >>> clock.get("hub-2")  # Unknown hub
        0
    """

    clocks: dict[str, int] = field(default_factory=dict)

    def increment(self, hub_id: str) -> int:
        """Increment the clock for a specific hub.

        Args:
            hub_id: Hub identifier.

        Returns:
            New timestamp for the hub.
        """
        self.clocks[hub_id] = self.clocks.get(hub_id, 0) + 1
        return self.clocks[hub_id]

    def get(self, hub_id: str) -> int:
        """Get the timestamp for a specific hub.

        Args:
            hub_id: Hub identifier.

        Returns:
            Timestamp (0 if never seen).
        """
        return self.clocks.get(hub_id, 0)

    def merge(self, other: VectorClock) -> None:
        """Merge with another vector clock (take max of each).

        Args:
            other: Vector clock to merge with.
        """
        for hub_id, ts in other.clocks.items():
            self.clocks[hub_id] = max(self.clocks.get(hub_id, 0), ts)

    def compare(self, other: VectorClock) -> ClockOrdering:
        """Compare this clock with another.

        Args:
            other: Vector clock to compare with.

        Returns:
            ClockOrdering indicating relationship.
        """
        self_greater = False
        other_greater = False

        # Check all keys from both clocks
        all_keys = set(self.clocks.keys()) | set(other.clocks.keys())

        for key in all_keys:
            self_ts = self.get(key)
            other_ts = other.get(key)

            if self_ts > other_ts:
                self_greater = True
            elif other_ts > self_ts:
                other_greater = True

        if self_greater and other_greater:
            return ClockOrdering.CONCURRENT
        elif self_greater:
            return ClockOrdering.AFTER
        elif other_greater:
            return ClockOrdering.BEFORE
        else:
            return ClockOrdering.EQUAL

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {"clocks": dict(self.clocks)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VectorClock:
        """Deserialize from dictionary."""
        return cls(clocks=dict(data.get("clocks", {})))


# =============================================================================
# Last-Writer-Wins Register (LWW)
# =============================================================================


@dataclass
class LWWRegister(Generic[T]):
    """Last-Writer-Wins Register — simple CRDT for single values.

    Uses wall-clock timestamp for ordering, with writer ID as tie-breaker.
    Higher timestamp wins; if timestamps are equal, lexicographically higher
    writer ID wins.

    Example:
        >>> reg = LWWRegister(value=10, writer="hub-1")
        >>> reg.update(20, time.time() + 1, "hub-2")  # Later write
        >>> reg.value
        20
    """

    value: T
    timestamp: float = field(default_factory=time.time)
    writer: str = "local"

    def update(self, value: T, timestamp: float, writer: str) -> bool:
        """Update the value if this write is newer.

        Args:
            value: New value.
            timestamp: Write timestamp.
            writer: Writer hub ID.

        Returns:
            True if value was updated.
        """
        # Last-Writer-Wins: higher timestamp wins
        # Tie-breaker: lexicographically higher writer ID
        if timestamp > self.timestamp or (timestamp == self.timestamp and writer > self.writer):
            self.value = value
            self.timestamp = timestamp
            self.writer = writer
            return True
        return False

    def merge(self, other: LWWRegister[T]) -> bool:
        """Merge with another register.

        Args:
            other: Register to merge with.

        Returns:
            True if local value was updated.
        """
        return self.update(other.value, other.timestamp, other.writer)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "value": self.value,
            "timestamp": self.timestamp,
            "writer": self.writer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LWWRegister:
        """Deserialize from dictionary."""
        return cls(
            value=data["value"],
            timestamp=data.get("timestamp", 0),
            writer=data.get("writer", "unknown"),
        )


# =============================================================================
# G-Counter (Grow-only Counter)
# =============================================================================


@dataclass
class GCounter:
    """Grow-only Counter CRDT — only increases, never decreases.

    Each hub has its own counter, and the value is the sum of all counters.
    Merge takes the maximum of each hub's counter.

    Example:
        >>> counter = GCounter()
        >>> counter.increment("hub-1")
        >>> counter.increment("hub-1")
        >>> counter.value()
        2
    """

    counts: dict[str, int] = field(default_factory=dict)

    def increment(self, hub_id: str, amount: int = 1) -> int:
        """Increment the counter for this hub.

        Args:
            hub_id: Hub identifier.
            amount: Amount to increment by.

        Returns:
            New count for this hub.
        """
        self.counts[hub_id] = self.counts.get(hub_id, 0) + amount
        return self.counts[hub_id]

    def value(self) -> int:
        """Get the total count across all hubs.

        Returns:
            Sum of all hub counts.
        """
        return sum(self.counts.values())

    def merge(self, other: GCounter) -> None:
        """Merge with another G-Counter (take max of each hub's count).

        Args:
            other: Counter to merge with.
        """
        for hub_id, count in other.counts.items():
            self.counts[hub_id] = max(self.counts.get(hub_id, 0), count)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {"counts": dict(self.counts)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GCounter:
        """Deserialize from dictionary."""
        return cls(counts=dict(data.get("counts", {})))


# =============================================================================
# PN-Counter (Positive-Negative Counter)
# =============================================================================


@dataclass
class PNCounter:
    """Positive-Negative Counter — supports increment and decrement.

    Internally uses two G-Counters: one for increments, one for decrements.
    Value is P - N.

    Example:
        >>> counter = PNCounter()
        >>> counter.increment("hub-1")
        >>> counter.decrement("hub-1")
        >>> counter.value()
        0
    """

    p_counts: dict[str, int] = field(default_factory=dict)
    n_counts: dict[str, int] = field(default_factory=dict)

    def increment(self, hub_id: str, amount: int = 1) -> None:
        """Increment the counter.

        Args:
            hub_id: Hub identifier.
            amount: Amount to increment by.
        """
        self.p_counts[hub_id] = self.p_counts.get(hub_id, 0) + amount

    def decrement(self, hub_id: str, amount: int = 1) -> None:
        """Decrement the counter.

        Args:
            hub_id: Hub identifier.
            amount: Amount to decrement by.
        """
        self.n_counts[hub_id] = self.n_counts.get(hub_id, 0) + amount

    def value(self) -> int:
        """Get the counter value.

        Returns:
            P - N (can be negative).
        """
        return sum(self.p_counts.values()) - sum(self.n_counts.values())

    def merge(self, other: PNCounter) -> None:
        """Merge with another PN-Counter.

        Args:
            other: Counter to merge with.
        """
        for hub_id, count in other.p_counts.items():
            self.p_counts[hub_id] = max(self.p_counts.get(hub_id, 0), count)
        for hub_id, count in other.n_counts.items():
            self.n_counts[hub_id] = max(self.n_counts.get(hub_id, 0), count)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "p_counts": dict(self.p_counts),
            "n_counts": dict(self.n_counts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PNCounter:
        """Deserialize from dictionary."""
        return cls(
            p_counts=dict(data.get("p_counts", {})),
            n_counts=dict(data.get("n_counts", {})),
        )


# =============================================================================
# OR-Set (Observed-Remove Set)
# =============================================================================


@dataclass(frozen=True)
class ORSetElement:
    """Element in an OR-Set with unique tag."""

    value: str
    tag: str  # Unique tag (hub_id:timestamp)


@dataclass
class ORSet:
    """Observed-Remove Set CRDT — supports add and remove with eventual consistency.

    Each add creates a unique tag. Remove marks all existing tags for a value
    as tombstones. Concurrent add-remove resolves in favor of add.

    Example:
        >>> s = ORSet()
        >>> s.add("room-1", "hub-1")
        >>> s.add("room-2", "hub-1")
        >>> s.remove("room-1")
        >>> s.values()
        ["room-2"]
    """

    elements: set[ORSetElement] = field(default_factory=set)
    tombstones: set[str] = field(default_factory=set)

    def add(self, value: str, hub_id: str) -> str:
        """Add an element to the set.

        Args:
            value: Value to add.
            hub_id: Hub identifier.

        Returns:
            Tag for the added element.
        """
        tag = f"{hub_id}:{time.time()}"
        self.elements.add(ORSetElement(value=value, tag=tag))
        return tag

    def remove(self, value: str) -> int:
        """Remove an element from the set.

        Args:
            value: Value to remove.

        Returns:
            Number of tags tombstoned.
        """
        tags_to_remove = [e.tag for e in self.elements if e.value == value]
        for tag in tags_to_remove:
            self.tombstones.add(tag)
            self.elements = {e for e in self.elements if e.tag != tag}
        return len(tags_to_remove)

    def contains(self, value: str) -> bool:
        """Check if an element is in the set.

        Args:
            value: Value to check.

        Returns:
            True if value is in set.
        """
        return any(e.value == value for e in self.elements)

    def values(self) -> list[str]:
        """Get all current values.

        Returns:
            List of unique values.
        """
        return list({e.value for e in self.elements})

    def merge(self, other: ORSet) -> None:
        """Merge with another OR-Set.

        Args:
            other: OR-Set to merge with.
        """
        # Add all tombstones
        self.tombstones |= other.tombstones

        # Add elements that aren't tombstoned
        for element in other.elements:
            if element.tag not in self.tombstones:
                self.elements.add(element)

        # Remove tombstoned elements from our set
        self.elements = {e for e in self.elements if e.tag not in self.tombstones}

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "elements": [{"value": e.value, "tag": e.tag} for e in self.elements],
            "tombstones": list(self.tombstones),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ORSet:
        """Deserialize from dictionary."""
        elements = {ORSetElement(value=e["value"], tag=e["tag"]) for e in data.get("elements", [])}
        tombstones = set(data.get("tombstones", []))
        return cls(elements=elements, tombstones=tombstones)


# =============================================================================
# Cross-Hub CRDT State
# =============================================================================


@dataclass
class CrossHubCRDTState:
    """Full CRDT-backed state for cross-hub synchronization.

    Compatible with Rust hub's CRDTState (sync.rs).

    Attributes:
        clock: Vector clock for causality.
        presence: LWW register for presence state.
        home_state: LWW register for home state snapshot.
        active_rooms: OR-Set of active rooms.
        sync_count: G-Counter for sync operations.
        source_hub: Hub that originated this state.
        timestamp: Wall-clock timestamp.
    """

    clock: VectorClock = field(default_factory=VectorClock)
    presence: LWWRegister[dict[str, Any]] = field(default_factory=lambda: LWWRegister(value={}))
    home_state: LWWRegister[dict[str, Any]] | None = None
    tesla_state: LWWRegister[dict[str, Any]] | None = None
    weather_state: LWWRegister[dict[str, Any]] | None = None
    active_rooms: ORSet = field(default_factory=ORSet)
    sync_count: GCounter = field(default_factory=GCounter)
    source_hub: str = "local"
    timestamp: float = field(default_factory=time.time)

    def merge(self, other: CrossHubCRDTState) -> None:
        """Merge with another CRDT state.

        All CRDT merges are commutative, associative, and idempotent,
        guaranteeing eventual consistency.

        Args:
            other: State to merge with.
        """
        # Merge vector clock
        self.clock.merge(other.clock)

        # Merge LWW registers
        self.presence.merge(other.presence)

        if other.home_state is not None:
            if self.home_state is None:
                self.home_state = other.home_state
            else:
                self.home_state.merge(other.home_state)

        if other.tesla_state is not None:
            if self.tesla_state is None:
                self.tesla_state = other.tesla_state
            else:
                self.tesla_state.merge(other.tesla_state)

        if other.weather_state is not None:
            if self.weather_state is None:
                self.weather_state = other.weather_state
            else:
                self.weather_state.merge(other.weather_state)

        # Merge OR-Set
        self.active_rooms.merge(other.active_rooms)

        # Merge counters
        self.sync_count.merge(other.sync_count)

        # Update timestamp
        self.timestamp = time.time()

        logger.debug(f"Merged state from {other.source_hub} (clock: {self.clock.clocks})")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary (compatible with Rust hub)."""
        return {
            "clock": self.clock.to_dict(),
            "presence": self.presence.to_dict(),
            "home_state": self.home_state.to_dict() if self.home_state else None,
            "tesla_state": self.tesla_state.to_dict() if self.tesla_state else None,
            "weather_state": (self.weather_state.to_dict() if self.weather_state else None),
            "active_rooms": self.active_rooms.to_dict(),
            "sync_count": self.sync_count.to_dict(),
            "source_hub": self.source_hub,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossHubCRDTState:
        """Deserialize from dictionary (compatible with Rust hub)."""
        return cls(
            clock=VectorClock.from_dict(data.get("clock", {})),
            presence=LWWRegister.from_dict(data.get("presence", {"value": {}})),
            home_state=(
                LWWRegister.from_dict(data["home_state"]) if data.get("home_state") else None
            ),
            tesla_state=(
                LWWRegister.from_dict(data["tesla_state"]) if data.get("tesla_state") else None
            ),
            weather_state=(
                LWWRegister.from_dict(data["weather_state"]) if data.get("weather_state") else None
            ),
            active_rooms=ORSet.from_dict(data.get("active_rooms", {})),
            sync_count=GCounter.from_dict(data.get("sync_count", {})),
            source_hub=data.get("source_hub", "unknown"),
            timestamp=data.get("timestamp", 0),
        )


# =============================================================================
# Cross-Hub CRDT Manager
# =============================================================================


class CrossHubCRDTManager:
    """Manages cross-hub CRDT state synchronization.

    Responsibilities:
    - Maintain local CRDT state
    - Merge incoming state from hubs
    - Persist state to Redis
    - Calculate deltas for efficient sync
    - Track sync status and health

    Example:
        >>> manager = CrossHubCRDTManager("api-server-1")
        >>> await manager.initialize()
        >>> await manager.merge_hub_state(incoming_state)
        >>> state = manager.get_state()
    """

    # Redis keys
    REDIS_STATE_KEY = "kagami:crdt:cross_hub_state"
    REDIS_SYNC_STATUS_KEY = "kagami:crdt:sync_status"

    def __init__(self, node_id: str) -> None:
        """Initialize the manager.

        Args:
            node_id: Unique identifier for this node.
        """
        self.node_id = node_id
        self._state: CrossHubCRDTState | None = None
        self._redis = RedisClientFactory.get_client()
        self._lock = asyncio.Lock()
        self._initialized = False

        # Sync status
        self._sync_count = 0
        self._last_sync_time: float | None = None
        self._known_hubs: set[str] = set()

    async def initialize(self) -> None:
        """Initialize the manager and load persisted state."""
        if self._initialized:
            return

        logger.info(f"Initializing CrossHubCRDTManager for node {self.node_id}")

        # Try to load persisted state
        try:
            persisted = await self._redis.get(self.REDIS_STATE_KEY)
            if persisted:
                data = json.loads(persisted.decode())
                self._state = CrossHubCRDTState.from_dict(data)
                logger.info(f"Loaded persisted CRDT state (clock: {self._state.clock.clocks})")
        except Exception as e:
            logger.warning(f"Could not load persisted CRDT state: {e}")

        # Create fresh state if needed
        if self._state is None:
            self._state = CrossHubCRDTState(source_hub=self.node_id)
            self._state.clock.increment(self.node_id)
            logger.info("Created fresh CRDT state")

        self._initialized = True
        logger.info("✅ CrossHubCRDTManager initialized")

    async def shutdown(self) -> None:
        """Shutdown and persist final state."""
        if self._state:
            await self._persist_state()
        self._initialized = False
        logger.info("🛑 CrossHubCRDTManager shutdown")

    def get_state(self) -> CrossHubCRDTState:
        """Get the current CRDT state.

        Returns:
            Current state (creates new if not initialized).
        """
        if self._state is None:
            self._state = CrossHubCRDTState(source_hub=self.node_id)
            self._state.clock.increment(self.node_id)
        return self._state

    async def merge_hub_state(self, hub_state: CrossHubCRDTState) -> None:
        """Merge incoming state from a hub.

        Args:
            hub_state: State from another hub.
        """
        async with self._lock:
            state = self.get_state()
            state.merge(hub_state)
            state.sync_count.increment(self.node_id)
            state.clock.increment(self.node_id)

            # Track known hubs
            self._known_hubs.add(hub_state.source_hub)
            self._sync_count += 1
            self._last_sync_time = time.time()

            # Persist merged state
            await self._persist_state()

            logger.info(
                f"Merged state from {hub_state.source_hub} (total syncs: {self._sync_count})"
            )

    async def merge_hub_state_dict(self, data: dict[str, Any]) -> None:
        """Merge incoming state from a hub (dictionary format).

        Args:
            data: State dictionary from hub.
        """
        hub_state = CrossHubCRDTState.from_dict(data)
        await self.merge_hub_state(hub_state)

    async def update_presence(self, presence_data: dict[str, Any]) -> None:
        """Update local presence state.

        Args:
            presence_data: Presence information.
        """
        async with self._lock:
            state = self.get_state()
            state.presence = LWWRegister(
                value=presence_data, timestamp=time.time(), writer=self.node_id
            )
            state.clock.increment(self.node_id)
            await self._persist_state()

    async def update_home_state(self, home_data: dict[str, Any]) -> None:
        """Update local home state.

        Args:
            home_data: Home state information.
        """
        async with self._lock:
            state = self.get_state()
            state.home_state = LWWRegister(
                value=home_data, timestamp=time.time(), writer=self.node_id
            )
            state.clock.increment(self.node_id)
            await self._persist_state()

    async def add_active_room(self, room_id: str) -> None:
        """Mark a room as active.

        Args:
            room_id: Room identifier.
        """
        async with self._lock:
            state = self.get_state()
            state.active_rooms.add(room_id, self.node_id)
            state.clock.increment(self.node_id)
            await self._persist_state()

    async def remove_active_room(self, room_id: str) -> None:
        """Mark a room as inactive.

        Args:
            room_id: Room identifier.
        """
        async with self._lock:
            state = self.get_state()
            state.active_rooms.remove(room_id)
            state.clock.increment(self.node_id)
            await self._persist_state()

    def calculate_delta(self, since_clock: VectorClock) -> CrossHubCRDTState | None:
        """Calculate delta since a given vector clock.

        Args:
            since_clock: Vector clock to compare against.

        Returns:
            State delta, or None if no updates needed.
        """
        state = self.get_state()

        # If their clock is not before ours, no delta needed
        if since_clock.compare(state.clock) != ClockOrdering.BEFORE:
            return None

        # Return full state as delta
        # (In production, track and return only changed fields)
        return state

    def get_sync_status(self) -> dict[str, Any]:
        """Get synchronization status.

        Returns:
            Status dictionary.
        """
        state = self.get_state()
        return {
            "node_id": self.node_id,
            "sync_count": self._sync_count,
            "last_sync_time": self._last_sync_time,
            "known_hubs": list(self._known_hubs),
            "vector_clock": state.clock.clocks,
            "active_rooms": state.active_rooms.values(),
            "total_syncs": state.sync_count.value(),
        }

    async def _persist_state(self) -> None:
        """Persist current state to Redis."""
        if self._state is None:
            return

        try:
            data = json.dumps(self._state.to_dict())
            await self._redis.set(self.REDIS_STATE_KEY, data)
        except Exception as e:
            logger.error(f"Failed to persist CRDT state: {e}")


# =============================================================================
# Singleton Factory
# =============================================================================

_crdt_manager: CrossHubCRDTManager | None = None
_crdt_manager_lock = asyncio.Lock()


async def get_cross_hub_crdt_manager(node_id: str | None = None) -> CrossHubCRDTManager:
    """Get or create the global CrossHubCRDTManager.

    Args:
        node_id: Node identifier (required for first call).

    Returns:
        CrossHubCRDTManager singleton instance.
    """
    global _crdt_manager

    async with _crdt_manager_lock:
        if _crdt_manager is None:
            import os
            import socket

            if node_id is None:
                node_id = os.environ.get("KAGAMI_NODE_ID", f"{socket.gethostname()}-api")
            _crdt_manager = CrossHubCRDTManager(node_id)
            await _crdt_manager.initialize()

    return _crdt_manager


async def shutdown_cross_hub_crdt() -> None:
    """Shutdown the global CrossHubCRDTManager."""
    global _crdt_manager

    if _crdt_manager:
        await _crdt_manager.shutdown()
        _crdt_manager = None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "ClockOrdering",
    # Manager
    "CrossHubCRDTManager",
    # State
    "CrossHubCRDTState",
    "GCounter",
    # CRDTs
    "LWWRegister",
    "ORSet",
    "ORSetElement",
    "PNCounter",
    # Vector clock
    "VectorClock",
    "get_cross_hub_crdt_manager",
    "shutdown_cross_hub_crdt",
]


# =============================================================================
# 鏡
# State flows. CRDTs merge. The mesh converges.
# h(x) ≥ 0. Always.
# =============================================================================
