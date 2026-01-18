"""CALM — Consistency as Logical Monotonicity.

Implements partition-tolerant operations based on the CALM theorem:
- Monotonic operations are safe under network partitions
- Uses CRDTs for eventually-consistent state
- Identifies and handles non-monotonic operations specially

CALM Theorem: A program is eventually consistent (safe under partitions)
if and only if it is monotonic (adding information never invalidates
previous conclusions).

Architecture:
```
┌─────────────────────────────────────────────────────────────────┐
│                    CALM PARTITION TOLERANCE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Operations                                                     │
│       │                                                         │
│       ▼                                                         │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │           Monotonicity Classifier                        │  │
│   │                                                          │  │
│   │   Monotonic Operations      Non-Monotonic Operations     │  │
│   │   • Add to set              • Delete from set            │  │
│   │   • Max/min update          • Conditional update         │  │
│   │   • Union/intersection      • Exact count                │  │
│   │   • Append to log           • Balance transfer           │  │
│   │                                                          │  │
│   └────────┬───────────────────────────────┬────────────────┘  │
│            │                               │                    │
│            ▼                               ▼                    │
│   ┌─────────────────┐           ┌─────────────────────────┐   │
│   │     CRDTs       │           │   Coordination Required  │   │
│   │  (Safe Offline) │           │   (Requires Consensus)   │   │
│   │                 │           │                          │   │
│   │  • G-Counter    │           │  • PBFT for commits      │   │
│   │  • PN-Counter   │           │  • 2PC for transactions  │   │
│   │  • G-Set        │           │  • Paxos for ordering    │   │
│   │  • OR-Set       │           │                          │   │
│   │  • LWW-Register │           │                          │   │
│   └─────────────────┘           └─────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

CRDTs (Conflict-free Replicated Data Types):
- Automatically merge without coordination
- Guarantee eventual consistency
- Support offline operation and partition tolerance

Colony: Crystal (D₅) — Partition tolerance verification
h(x) ≥ 0. Always.

Created: January 2026
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Operation Classification
# =============================================================================


class Monotonicity(Enum):
    """Operation monotonicity classification."""

    MONOTONIC = auto()  # Safe under partitions
    NON_MONOTONIC = auto()  # Requires coordination
    CONDITIONALLY_MONOTONIC = auto()  # Depends on context


@dataclass
class OperationMetadata:
    """Metadata for an operation.

    Attributes:
        name: Operation name.
        monotonicity: Monotonicity classification.
        crdt_compatible: Whether a CRDT can handle this.
        requires_ordering: Whether global ordering is required.
        description: Human-readable description.
    """

    name: str
    monotonicity: Monotonicity
    crdt_compatible: bool = False
    requires_ordering: bool = False
    description: str = ""


# Standard operation classifications
OPERATION_METADATA: dict[str, OperationMetadata] = {
    # Monotonic (safe)
    "add": OperationMetadata(
        "add", Monotonicity.MONOTONIC, True, False, "Add element to collection"
    ),
    "increment": OperationMetadata(
        "increment", Monotonicity.MONOTONIC, True, False, "Increment counter"
    ),
    "max": OperationMetadata("max", Monotonicity.MONOTONIC, True, False, "Update to maximum value"),
    "min": OperationMetadata("min", Monotonicity.MONOTONIC, True, False, "Update to minimum value"),
    "union": OperationMetadata("union", Monotonicity.MONOTONIC, True, False, "Union of sets"),
    "append": OperationMetadata("append", Monotonicity.MONOTONIC, True, True, "Append to log"),
    # Non-monotonic (requires coordination)
    "delete": OperationMetadata(
        "delete", Monotonicity.NON_MONOTONIC, True, False, "Delete element (OR-Set handles this)"
    ),
    "decrement": OperationMetadata(
        "decrement",
        Monotonicity.NON_MONOTONIC,
        True,
        False,
        "Decrement counter (PN-Counter handles this)",
    ),
    "compare_and_swap": OperationMetadata(
        "compare_and_swap", Monotonicity.NON_MONOTONIC, False, True, "Atomic compare and swap"
    ),
    "transfer": OperationMetadata(
        "transfer", Monotonicity.NON_MONOTONIC, False, True, "Transfer between accounts"
    ),
    "exact_count": OperationMetadata(
        "exact_count", Monotonicity.NON_MONOTONIC, False, True, "Get exact count"
    ),
}


def classify_operation(operation: str) -> OperationMetadata:
    """Classify an operation for partition tolerance.

    Args:
        operation: Operation name.

    Returns:
        OperationMetadata with classification.
    """
    return OPERATION_METADATA.get(
        operation,
        OperationMetadata(
            operation,
            Monotonicity.NON_MONOTONIC,
            False,
            True,
            "Unknown operation (defaulting to non-monotonic)",
        ),
    )


def is_partition_safe(operation: str) -> bool:
    """Check if operation is safe under network partitions.

    Args:
        operation: Operation name.

    Returns:
        True if operation can proceed safely during partitions.
    """
    metadata = classify_operation(operation)
    return metadata.monotonicity == Monotonicity.MONOTONIC


# =============================================================================
# CRDTs — Conflict-free Replicated Data Types
# =============================================================================


class CRDT(ABC, Generic[T]):
    """Abstract base for CRDTs."""

    @abstractmethod
    def value(self) -> T:
        """Get current value."""
        pass

    @abstractmethod
    def merge(self, other: CRDT[T]) -> CRDT[T]:
        """Merge with another CRDT of same type."""
        pass

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        pass


class GCounter(CRDT[int]):
    """Grow-only Counter CRDT.

    Only supports increments. Always converges.

    Example:
        >>> c = GCounter("node1")
        >>> c.increment(5)
        >>> c.value()
        5
        >>> c2 = GCounter("node2")
        >>> c2.increment(3)
        >>> merged = c.merge(c2)
        >>> merged.value()
        8
    """

    def __init__(self, node_id: str, state: dict[str, int] | None = None) -> None:
        self.node_id = node_id
        self._state = state or {node_id: 0}

    def increment(self, amount: int = 1) -> None:
        """Increment the counter."""
        if amount < 0:
            raise ValueError("GCounter only supports positive increments")
        self._state[self.node_id] = self._state.get(self.node_id, 0) + amount

    def value(self) -> int:
        """Get current count."""
        return sum(self._state.values())

    def merge(self, other: GCounter) -> GCounter:
        """Merge with another GCounter."""
        new_state = dict(self._state)
        for node, count in other._state.items():
            new_state[node] = max(new_state.get(node, 0), count)
        return GCounter(self.node_id, new_state)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "g-counter", "state": self._state}

    @classmethod
    def from_dict(cls, data: dict[str, Any], node_id: str) -> GCounter:
        return cls(node_id, data.get("state", {}))


class PNCounter(CRDT[int]):
    """Positive-Negative Counter CRDT.

    Supports both increments and decrements.

    Example:
        >>> c = PNCounter("node1")
        >>> c.increment(10)
        >>> c.decrement(3)
        >>> c.value()
        7
    """

    def __init__(
        self,
        node_id: str,
        positive: dict[str, int] | None = None,
        negative: dict[str, int] | None = None,
    ) -> None:
        self.node_id = node_id
        self._positive = positive or {node_id: 0}
        self._negative = negative or {node_id: 0}

    def increment(self, amount: int = 1) -> None:
        """Increment the counter."""
        if amount < 0:
            raise ValueError("Use decrement for negative values")
        self._positive[self.node_id] = self._positive.get(self.node_id, 0) + amount

    def decrement(self, amount: int = 1) -> None:
        """Decrement the counter."""
        if amount < 0:
            raise ValueError("Use increment for positive values")
        self._negative[self.node_id] = self._negative.get(self.node_id, 0) + amount

    def value(self) -> int:
        """Get current count."""
        return sum(self._positive.values()) - sum(self._negative.values())

    def merge(self, other: PNCounter) -> PNCounter:
        """Merge with another PNCounter."""
        new_positive = dict(self._positive)
        new_negative = dict(self._negative)

        for node, count in other._positive.items():
            new_positive[node] = max(new_positive.get(node, 0), count)
        for node, count in other._negative.items():
            new_negative[node] = max(new_negative.get(node, 0), count)

        return PNCounter(self.node_id, new_positive, new_negative)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "pn-counter",
            "positive": self._positive,
            "negative": self._negative,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], node_id: str) -> PNCounter:
        return cls(
            node_id,
            data.get("positive", {}),
            data.get("negative", {}),
        )


class GSet(CRDT[set]):
    """Grow-only Set CRDT.

    Only supports additions. Always converges.

    Example:
        >>> s = GSet()
        >>> s.add("a")
        >>> s.add("b")
        >>> s.value()
        {'a', 'b'}
    """

    def __init__(self, elements: set | None = None) -> None:
        self._elements = elements or set()

    def add(self, element: Any) -> None:
        """Add element to set."""
        self._elements.add(element)

    def contains(self, element: Any) -> bool:
        """Check if element is in set."""
        return element in self._elements

    def value(self) -> set:
        """Get current set."""
        return set(self._elements)

    def merge(self, other: GSet) -> GSet:
        """Merge with another GSet."""
        return GSet(self._elements | other._elements)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "g-set", "elements": list(self._elements)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GSet:
        return cls(set(data.get("elements", [])))


class ORSet(CRDT[set]):
    """Observed-Remove Set CRDT.

    Supports both additions and removals. Uses unique tags to track
    additions, allowing safe removal of observed elements.

    Example:
        >>> s = ORSet("node1")
        >>> s.add("a")
        >>> s.add("b")
        >>> s.remove("a")
        >>> s.value()
        {'b'}
    """

    def __init__(
        self,
        node_id: str,
        elements: dict[Any, set[str]] | None = None,
        tombstones: set[str] | None = None,
    ) -> None:
        self.node_id = node_id
        self._elements = elements or {}  # element -> set of tags
        self._tombstones = tombstones or set()  # removed tags

    def add(self, element: Any) -> None:
        """Add element to set."""
        tag = f"{self.node_id}:{uuid.uuid4().hex[:8]}"
        if element not in self._elements:
            self._elements[element] = set()
        self._elements[element].add(tag)

    def remove(self, element: Any) -> None:
        """Remove element from set."""
        if element in self._elements:
            self._tombstones.update(self._elements[element])
            del self._elements[element]

    def contains(self, element: Any) -> bool:
        """Check if element is in set."""
        if element not in self._elements:
            return False
        # Element is present if it has non-tombstoned tags
        live_tags = self._elements[element] - self._tombstones
        return len(live_tags) > 0

    def value(self) -> set:
        """Get current set."""
        result = set()
        for element, tags in self._elements.items():
            if tags - self._tombstones:
                result.add(element)
        return result

    def merge(self, other: ORSet) -> ORSet:
        """Merge with another ORSet."""
        new_elements: dict[Any, set[str]] = {}
        new_tombstones = self._tombstones | other._tombstones

        # Merge element tags
        all_elements = set(self._elements.keys()) | set(other._elements.keys())
        for element in all_elements:
            tags = set()
            if element in self._elements:
                tags.update(self._elements[element])
            if element in other._elements:
                tags.update(other._elements[element])

            # Remove tombstoned tags
            live_tags = tags - new_tombstones
            if live_tags:
                new_elements[element] = live_tags

        return ORSet(self.node_id, new_elements, new_tombstones)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "or-set",
            "elements": {str(k): list(v) for k, v in self._elements.items()},
            "tombstones": list(self._tombstones),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], node_id: str) -> ORSet:
        elements = {k: set(v) for k, v in data.get("elements", {}).items()}
        tombstones = set(data.get("tombstones", []))
        return cls(node_id, elements, tombstones)


class LWWRegister(CRDT[Any]):
    """Last-Writer-Wins Register CRDT.

    Simple register where last write (by timestamp) wins.

    Example:
        >>> r = LWWRegister("node1")
        >>> r.set("hello")
        >>> r.value()
        'hello'
    """

    def __init__(
        self,
        node_id: str,
        value: Any = None,
        timestamp: float = 0.0,
    ) -> None:
        self.node_id = node_id
        self._value = value
        self._timestamp = timestamp

    def set(self, value: Any, timestamp: float | None = None) -> None:
        """Set register value."""
        ts = timestamp or time.time()
        if ts >= self._timestamp:
            self._value = value
            self._timestamp = ts

    def value(self) -> Any:
        """Get current value."""
        return self._value

    def merge(self, other: LWWRegister) -> LWWRegister:
        """Merge with another LWWRegister."""
        if other._timestamp > self._timestamp:
            return LWWRegister(self.node_id, other._value, other._timestamp)
        return LWWRegister(self.node_id, self._value, self._timestamp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "lww-register",
            "value": self._value,
            "timestamp": self._timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], node_id: str) -> LWWRegister:
        return cls(
            node_id,
            data.get("value"),
            data.get("timestamp", 0.0),
        )


class MVRegister(CRDT[set]):
    """Multi-Value Register CRDT.

    Tracks concurrent writes, returning all concurrent values.
    Application must resolve conflicts.

    Example:
        >>> r = MVRegister("node1")
        >>> r.set("hello")
        >>> r2 = MVRegister("node2")
        >>> r2.set("world")
        >>> merged = r.merge(r2)
        >>> merged.value()  # Returns set of concurrent values
        {'hello', 'world'}
    """

    def __init__(
        self,
        node_id: str,
        values: dict[str, tuple[Any, dict[str, int]]] | None = None,
        vector_clock: dict[str, int] | None = None,
    ) -> None:
        self.node_id = node_id
        self._values = values or {}  # id -> (value, vector_clock)
        self._vector_clock = vector_clock or {node_id: 0}

    def set(self, value: Any) -> None:
        """Set register value."""
        # Increment local clock
        self._vector_clock[self.node_id] = self._vector_clock.get(self.node_id, 0) + 1

        # Create new entry with current vector clock
        entry_id = f"{self.node_id}:{uuid.uuid4().hex[:8]}"
        self._values = {entry_id: (value, dict(self._vector_clock))}

    def value(self) -> set:
        """Get all concurrent values."""
        return {v for v, _ in self._values.values()}

    def merge(self, other: MVRegister) -> MVRegister:
        """Merge with another MVRegister."""
        # Merge vector clocks
        new_clock = dict(self._vector_clock)
        for node, count in other._vector_clock.items():
            new_clock[node] = max(new_clock.get(node, 0), count)

        # Keep values that aren't dominated
        new_values: dict[str, tuple[Any, dict[str, int]]] = {}
        all_values = list(self._values.items()) + list(other._values.items())

        for entry_id, (value, clock) in all_values:
            dominated = False
            for other_id, (_, other_clock) in all_values:
                if entry_id != other_id:
                    if self._dominates(other_clock, clock):
                        dominated = True
                        break
            if not dominated:
                new_values[entry_id] = (value, clock)

        return MVRegister(self.node_id, new_values, new_clock)

    @staticmethod
    def _dominates(a: dict[str, int], b: dict[str, int]) -> bool:
        """Check if vector clock a dominates b."""
        all_nodes = set(a.keys()) | set(b.keys())
        greater = False
        for node in all_nodes:
            a_val = a.get(node, 0)
            b_val = b.get(node, 0)
            if a_val < b_val:
                return False
            if a_val > b_val:
                greater = True
        return greater

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "mv-register",
            "values": {k: [v, c] for k, (v, c) in self._values.items()},
            "vector_clock": self._vector_clock,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], node_id: str) -> MVRegister:
        values = {k: (v[0], v[1]) for k, v in data.get("values", {}).items()}
        return cls(node_id, values, data.get("vector_clock", {}))


# =============================================================================
# CALM Coordinator
# =============================================================================


class CALMCoordinator:
    """Coordinator for partition-tolerant operations.

    Automatically routes operations to appropriate handling:
    - Monotonic ops: Use CRDTs, safe offline
    - Non-monotonic ops: Route to consensus

    Example:
        >>> coord = CALMCoordinator("node1")
        >>>
        >>> # Safe operation - uses CRDT
        >>> await coord.execute("add", "my-set", "element")
        >>>
        >>> # Unsafe operation - requires consensus
        >>> await coord.execute("transfer", "account", {"from": "a", "to": "b", "amount": 100})
    """

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self._crdts: dict[str, CRDT] = {}
        self._consensus = None  # Lazy load PBFT

    async def execute(
        self,
        operation: str,
        key: str,
        data: Any = None,
    ) -> Any:
        """Execute an operation with appropriate coordination.

        Args:
            operation: Operation type.
            key: Resource key.
            data: Operation data.

        Returns:
            Operation result.
        """
        metadata = classify_operation(operation)

        if metadata.monotonicity == Monotonicity.MONOTONIC and metadata.crdt_compatible:
            return await self._execute_crdt(operation, key, data)
        else:
            return await self._execute_consensus(operation, key, data)

    async def _execute_crdt(self, operation: str, key: str, data: Any) -> Any:
        """Execute operation using CRDT."""
        # Get or create CRDT
        if key not in self._crdts:
            self._crdts[key] = self._create_crdt_for_operation(operation)

        crdt = self._crdts[key]

        # Apply operation
        if operation == "add" and isinstance(crdt, (GSet, ORSet)):
            crdt.add(data)
            return True
        elif operation == "increment" and isinstance(crdt, (GCounter, PNCounter)):
            crdt.increment(data or 1)
            return crdt.value()
        elif operation == "decrement" and isinstance(crdt, PNCounter):
            crdt.decrement(data or 1)
            return crdt.value()
        elif operation in ("max", "min") and isinstance(crdt, LWWRegister):
            current = crdt.value()
            if current is None:
                crdt.set(data)
            elif operation == "max":
                crdt.set(max(current, data))
            else:
                crdt.set(min(current, data))
            return crdt.value()

        return crdt.value()

    async def _execute_consensus(self, operation: str, key: str, data: Any) -> Any:
        """Execute operation using consensus."""
        if self._consensus is None:
            from kagami.core.consensus.pbft import get_pbft_node

            self._consensus = await get_pbft_node()

        result = await self._consensus.submit_request(
            operation=operation,
            data={"key": key, "data": data},
        )

        return result.result if result.success else None

    def _create_crdt_for_operation(self, operation: str) -> CRDT:
        """Create appropriate CRDT for operation."""
        if operation in ("add", "union"):
            return ORSet(self.node_id)
        elif operation in ("increment",):
            return GCounter(self.node_id)
        elif operation in ("decrement",):
            return PNCounter(self.node_id)
        else:
            return LWWRegister(self.node_id)

    async def sync(self, peer_state: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Synchronize CRDTs with peer.

        Args:
            peer_state: Peer's CRDT state.

        Returns:
            Merged state to send back.
        """
        result: dict[str, dict[str, Any]] = {}

        # Merge peer state
        for key, state_dict in peer_state.items():
            if key in self._crdts:
                peer_crdt = self._deserialize_crdt(state_dict)
                self._crdts[key] = self._crdts[key].merge(peer_crdt)
            else:
                self._crdts[key] = self._deserialize_crdt(state_dict)

            result[key] = self._crdts[key].to_dict()

        # Add local state
        for key, crdt in self._crdts.items():
            if key not in result:
                result[key] = crdt.to_dict()

        return result

    def _deserialize_crdt(self, state: dict[str, Any]) -> CRDT:
        """Deserialize CRDT from dictionary."""
        crdt_type = state.get("type", "")

        if crdt_type == "g-counter":
            return GCounter.from_dict(state, self.node_id)
        elif crdt_type == "pn-counter":
            return PNCounter.from_dict(state, self.node_id)
        elif crdt_type == "g-set":
            return GSet.from_dict(state)
        elif crdt_type == "or-set":
            return ORSet.from_dict(state, self.node_id)
        elif crdt_type == "lww-register":
            return LWWRegister.from_dict(state, self.node_id)
        elif crdt_type == "mv-register":
            return MVRegister.from_dict(state, self.node_id)
        else:
            raise ValueError(f"Unknown CRDT type: {crdt_type}")

    def get_state(self) -> dict[str, dict[str, Any]]:
        """Get all CRDT state for synchronization."""
        return {key: crdt.to_dict() for key, crdt in self._crdts.items()}


# =============================================================================
# Factory Functions
# =============================================================================


_calm_coordinator: CALMCoordinator | None = None


async def get_calm_coordinator(node_id: str | None = None) -> CALMCoordinator:
    """Get or create singleton CALM coordinator.

    Args:
        node_id: Node identifier.

    Returns:
        CALMCoordinator instance.
    """
    global _calm_coordinator

    if _calm_coordinator is None:
        import os
        import socket

        if node_id is None:
            node_id = os.environ.get("KAGAMI_NODE_ID", f"{socket.gethostname()}-{os.getpid()}")

        _calm_coordinator = CALMCoordinator(node_id)
        logger.info(f"✅ CALM Coordinator initialized (node={node_id})")

    return _calm_coordinator


__all__ = [
    "CRDT",
    "CALMCoordinator",
    "GCounter",
    "GSet",
    "LWWRegister",
    "MVRegister",
    "Monotonicity",
    "ORSet",
    "OperationMetadata",
    "PNCounter",
    "classify_operation",
    "get_calm_coordinator",
    "is_partition_safe",
]
