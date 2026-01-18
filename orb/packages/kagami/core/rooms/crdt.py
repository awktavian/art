from __future__ import annotations

"""CRDT (Conflict-free Replicated Data Type) for Collaborative Room State.

Implements a practical JSON-like CRDT for real-time collaborative state
management. All clients applying the same operations (in any order)
will converge to the same final state.

Design Goals:
    - Conflict-free convergence under out-of-order delivery
    - Idempotent application of operations (safe retries)
    - Deterministic tie-breaking (no undefined merges)
    - Materialized state is plain JSON (no CRDT metadata leaks)

Operation Types:
    - SET: LWW register for scalar/JSON values at a path
    - ADD: LWW element upsert into a collection at path
    - REMOVE: LWW element tombstone or register delete
    - INCREMENT: Idempotent counter increment at path

LWW (Last-Writer-Wins):
    Conflicts are resolved by comparing (timestamp, client_id, version, op_id)
    tuples. This provides a total order for deterministic tie-breaking.

Clock Tuple Ordering:
    (timestamp_ms, client_id, version, op_id)
    - Higher timestamp wins
    - On tie: lexicographically higher client_id wins
    - On tie: higher version wins
    - On tie: lexicographically higher op_id wins

Collections:
    Collections support two modes:
    - dict mode: Elements keyed by element_id
    - list mode: Elements stored in array, matched by element_id

Counters:
    INCREMENT operations are tracked per-op_id for idempotency.
    Multiple applications of the same INCREMENT are collapsed.

Persistence:
    Rooms are server-mediated and persisted in Redis. This CRDT is
    designed so multiple workers can apply the same ops (even out of
    order) and converge to identical state.

Example:
    >>> crdt = RoomStateCRDT("room-123")
    >>> op = Operation(
    ...     op_id="op-1",
    ...     type=OperationType.SET,
    ...     path="users.alice.name",
    ...     value="Alice",
    ...     element_id=None,
    ...     client_id="client-1",
    ...     version=1,
    ...     timestamp_ms=1234567890000,
    ... )
    >>> result = crdt.apply_operation(op)
    >>> crdt.get_state()
    {'users': {'alice': {'name': 'Alice'}}}

See Also:
    - https://crdt.tech/ — CRDT introduction
    - https://en.wikipedia.org/wiki/Conflict-free_replicated_data_type
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import logging  # Error logging
import time  # Default timestamps
import uuid  # Operation ID generation
from dataclasses import dataclass, field  # Clean data structures
from enum import Enum  # Operation types
from typing import Any  # Type hints

logger = logging.getLogger(__name__)


# =============================================================================
# OPERATION TYPES
# =============================================================================


class OperationType(str, Enum):
    """Types of CRDT operations.

    Each type has different merge semantics:
    - SET: Last-writer-wins register (overwrites previous)
    - ADD: Upsert element into collection
    - REMOVE: Tombstone element (or delete register if no element_id)
    - INCREMENT: Idempotent counter increment
    """

    SET = "set[Any]"  # LWW register: set value at path
    ADD = "add"  # LWW element: upsert into collection at path
    REMOVE = "remove"  # LWW tombstone: remove element or delete register
    INCREMENT = "increment"  # Counter: idempotent increment at path


# =============================================================================
# OPERATION DATACLASS
# =============================================================================


@dataclass
class Operation:
    """Single CRDT operation with causality tracking.

    Represents one atomic change to room state. Operations are
    identified by op_id and ordered by clock tuple.

    Attributes:
        op_id: Unique operation identifier (UUID hex).
        type: Operation type (SET, ADD, REMOVE, INCREMENT).
        path: Dot-separated path in state tree (e.g., "users.alice.name").
        value: Value to set/add/increment.
        element_id: Collection element ID (for ADD/REMOVE on collections).
        client_id: ID of client that created operation.
        version: Client-local version counter.
        timestamp_ms: Wall-clock timestamp in milliseconds.
        dependencies: Map of client_id → version for causal ordering.

    Clock Tuple:
        Operations are ordered by (timestamp_ms, client_id, version, op_id).
        This provides total ordering for LWW conflict resolution.

    Example:
        >>> op = Operation(
        ...     op_id="abc123",
        ...     type=OperationType.SET,
        ...     path="config.theme",
        ...     value="dark",
        ...     element_id=None,
        ...     client_id="client-1",
        ...     version=5,
        ...     timestamp_ms=1234567890000,
        ... )
    """

    op_id: str  # Unique operation identifier
    type: OperationType  # Operation type enum
    path: str  # Dot-separated state path
    value: Any  # Value to set/add/increment
    element_id: str | None  # Collection element ID (if applicable)
    client_id: str  # Originating client
    version: int  # Client version counter
    timestamp_ms: int  # Wall-clock timestamp (ms)
    dependencies: dict[str, int] = field(default_factory=dict[str, Any])  # Causal deps

    def to_dict(self) -> dict[str, Any]:
        """Convert operation to dictionary for serialization.

        Returns:
            Dict with all operation fields, suitable for JSON.
        """
        return {
            "op_id": self.op_id,
            "type": self.type.value,
            "path": self.path,
            "value": self.value,
            "element_id": self.element_id,
            "client_id": self.client_id,
            "version": self.version,
            "timestamp_ms": self.timestamp_ms,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Operation:
        """Create Operation from dictionary (deserialization).

        Handles missing/invalid fields gracefully with sensible defaults.

        Args:
            data: Dictionary with operation fields.

        Returns:
            Operation instance.
        """
        raw_type = data.get("type")
        try:
            op_type = OperationType(str(raw_type))
        except Exception:
            op_type = OperationType.SET

        try:
            ts = int(data.get("timestamp_ms") or 0)
        except Exception:
            ts = 0
        if ts <= 0:
            # Server-friendly default: accept ops that omit timestamps.
            ts = int(time.time() * 1000)

        try:
            ver = int(data.get("version") or 0)
        except Exception:
            ver = 0

        op_id = str(data.get("op_id") or "").strip() or uuid.uuid4().hex
        element_id = data.get("element_id")
        if element_id is not None:
            element_id = str(element_id).strip() or None

        return cls(
            op_id=op_id,
            type=op_type,
            path=str(data.get("path") or ""),
            value=data.get("value"),
            element_id=element_id,
            client_id=str(data.get("client_id") or ""),
            version=ver,
            timestamp_ms=ts,
            dependencies=dict(data.get("dependencies") or {}),
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _clock_tuple(ts_ms: int, client_id: str, version: int, op_id: str) -> tuple[int, str, int, str]:
    """Create clock tuple for LWW comparison.

    The tuple provides deterministic total ordering:
    1. Higher timestamp wins
    2. On tie: lexicographically higher client_id
    3. On tie: higher version
    4. On tie: lexicographically higher op_id

    Args:
        ts_ms: Timestamp in milliseconds.
        client_id: Client identifier string.
        version: Client version counter.
        op_id: Operation identifier.

    Returns:
        Tuple for comparison (timestamp, client_id, version, op_id).
    """
    return (int(ts_ms), str(client_id), int(version), str(op_id))


def _is_newer(stored_clock: list[Any] | None, candidate: tuple[int, str, int, str]) -> bool:
    """Check if candidate clock is newer than stored clock.

    Used for LWW conflict resolution — newer clock wins.

    Args:
        stored_clock: Current stored clock (or None if unset).
        candidate: New operation's clock tuple.

    Returns:
        True if candidate should replace stored, False otherwise.
    """
    # No stored clock → candidate wins
    if not stored_clock:
        return True
    # Parse stored clock into tuple for comparison
    try:
        cur = (
            int(stored_clock[0]),
            str(stored_clock[1]),
            int(stored_clock[2]),
            str(stored_clock[3]),
        )
    except Exception:
        # Malformed stored clock → candidate wins
        return True
    # Tuple comparison (Python compares element-by-element)
    return cur < candidate


def _split_path(path: str) -> list[str]:
    """Split dot-separated path into components.

    Args:
        path: Dot-separated path (e.g., "users.alice.name").

    Returns:
        List of path components (e.g., ["users", "alice", "name"]).
    """
    return [p for p in str(path or "").split(".") if p]


def _get_container(
    root: dict[str, Any], parts: list[str], *, create: bool
) -> tuple[dict[str, Any] | None, str]:
    """Navigate to container dict for a nested path.

    Args:
        root: Root state dictionary.
        parts: Path components from _split_path().
        create: If True, create intermediate dicts as needed.

    Returns:
        Tuple of (parent_dict, final_key) or (None, key) if not found.

    Example:
        >>> state = {"users": {}}
        >>> parent, key = _get_container(state, ["users", "alice", "name"], create=True)
        >>> parent[key] = "Alice"  # Sets state["users"]["alice"]["name"]
    """
    if not parts:
        return (root, "")

    cur: Any = root
    # Navigate through all but the last path component
    for p in parts[:-1]:
        if not isinstance(cur, dict):
            return (None, parts[-1])
        if p not in cur:
            if not create:
                return (None, parts[-1])
            cur[p] = {}  # Create intermediate dict
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            if not create:
                return (None, parts[-1])
            nxt = {}
            cur[p] = nxt
        cur = nxt

    if not isinstance(cur, dict):
        return (None, parts[-1])
    return (cur, parts[-1])


def _extract_element_id(value: Any) -> str | None:
    """Extract element ID from collection item.

    Tries common ID field names in order of priority.

    Args:
        value: Collection element (typically a dict).

    Returns:
        Element ID string, or None if not found.
    """
    if not isinstance(value, dict):
        return None
    # Try common ID field names
    for k in ("id", "request_id", "anchor_id", "entity_id", "user_id"):
        v = value.get(k)
        if v is not None:
            s = str(v).strip()
            if s:
                return s
    return None


# =============================================================================
# ROOM STATE CRDT
# =============================================================================


class RoomStateCRDT:
    """CRDT for room state with automatic conflict resolution.

    Main CRDT implementation that maintains room state and metadata.
    Applies operations idempotently with LWW conflict resolution.

    Attributes:
        room_id: Room identifier.
        vector_clock: Map of client_id → highest version seen.
        state: Materialized JSON state (no CRDT metadata).
        operation_count: Total operations applied.
        meta: CRDT metadata (registers, collections, increments).

    Metadata Structure:
        - registers: path → {clock, deleted} for SET operations
        - collections: path → {element_id → {clock, deleted}}
        - increments: path → {ops: {op_id → delta}, base, base_clock}

    Example:
        >>> crdt = RoomStateCRDT("room-123")
        >>> op = Operation(...)
        >>> result = crdt.apply_operation(op)
        >>> state = crdt.get_state()  # Plain JSON, no metadata
    """

    def __init__(
        self,
        room_id: str,
        *,
        state: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ):
        """Initialize CRDT for a room.

        Args:
            room_id: Room identifier.
            state: Initial state (optional, for hydration).
            meta: Initial metadata (optional, for hydration).
        """
        self.room_id = room_id
        self.vector_clock: dict[str, int] = {}  # Causality tracking
        self.state: dict[str, Any] = dict(state or {})  # Materialized state
        self.operation_count = 0  # Stats counter

        # Initialize metadata for each CRDT type
        self.meta: dict[str, Any] = dict(meta or {})
        self.meta.setdefault("registers", {})  # LWW registers
        self.meta.setdefault("collections", {})  # LWW element sets
        self.meta.setdefault("increments", {})  # Idempotent counters

    def apply_operation(self, op: Operation) -> dict[str, Any]:
        """Apply an operation to the CRDT.

        Dispatches to appropriate handler based on operation type.
        Updates vector clock and operation count.

        Args:
            op: Operation to apply.

        Returns:
            Dict with status, changed (bool), operation_count.
        """

        # Dispatch to appropriate handler based on operation type.
        # Each handler returns True if operation was applied (newer clock).
        changed = False
        if op.type == OperationType.SET:
            # LWW register write — set value at path
            changed = self._apply_lww_set(op)
        elif op.type == OperationType.ADD:
            # LWW element — upsert into collection
            changed = self._apply_add(op)
        elif op.type == OperationType.INCREMENT:
            # Idempotent counter — add delta to counter
            changed = self._apply_increment(op)
        elif op.type == OperationType.REMOVE:
            if op.element_id:
                # LWW tombstone — remove element from collection
                changed = self._apply_remove(op)
            else:
                # LWW register delete — delete value at path
                changed = self._apply_lww_delete(op)

        # Update vector clock: track highest version seen per client.
        # This is used for causal ordering in future ops.
        self.vector_clock[op.client_id] = max(self.vector_clock.get(op.client_id, 0), op.version)

        # Stats counter for monitoring
        self.operation_count += 1

        # Return result for client feedback
        return {
            "status": "applied",
            "changed": bool(changed),  # True if op was newer and applied
            "operation_count": self.operation_count,
        }

    # =========================================================================
    # LWW REGISTERS
    # =========================================================================
    # Registers are simple key-value pairs with last-writer-wins semantics.
    # SET operations create/update registers, REMOVE (without element_id) deletes.

    def _apply_lww_set(self, op: Operation) -> bool:
        """Apply SET operation (LWW register write).

        Creates or updates a value at the given path.
        Only applies if operation is newer than existing value.

        Args:
            op: SET operation with path and value.

        Returns:
            True if operation was applied, False if older.
        """
        # Normalize and validate path
        path = str(op.path or "").strip()
        if not path:
            return False  # Empty path — reject operation

        # Create clock tuple for LWW comparison
        clock = _clock_tuple(op.timestamp_ms, op.client_id, op.version, op.op_id)

        # Get or initialize registers metadata
        regs = self.meta.get("registers")
        if not isinstance(regs, dict):
            regs = {}
            self.meta["registers"] = regs

        # Check if there's an existing clock for this path
        prev = regs.get(path) if isinstance(regs, dict) else None
        prev_clock = prev.get("clock") if isinstance(prev, dict) else None

        # LWW check: only apply if this operation is newer
        if not _is_newer(prev_clock, clock):
            return False  # Older operation — reject

        # Navigate to parent container, creating intermediate dicts
        parts = _split_path(path)
        parent, key = _get_container(self.state, parts, create=True)
        if parent is None or key == "":
            return False  # Invalid path structure

        # Apply the value to materialized state
        parent[key] = op.value

        # Update metadata with new clock and cleared tombstone
        regs[path] = {"clock": list(clock), "deleted": False}

        # Maintain counter invariants if this path has INCREMENT history.
        # A SET can reset a counter, so we need to recompute total.
        try:
            if isinstance(self.meta.get("increments"), dict) and path in self.meta["increments"]:
                self._recompute_counter(path)
        except Exception:
            pass  # Silently handle counter recompute errors

        # "changed" means CRDT accepted the op (meta advanced).
        # Note: does NOT mean materialized value differs.
        return True

    def _apply_lww_delete(self, op: Operation) -> bool:
        """Apply REMOVE operation (LWW register delete).

        Deletes a value at the given path (marks as tombstone).
        Only applies if operation is newer than existing value.

        Args:
            op: REMOVE operation with path (no element_id).

        Returns:
            True if operation was applied, False if older.
        """
        # Normalize and validate path
        path = str(op.path or "").strip()
        if not path:
            return False  # Empty path — reject operation

        # Create clock tuple for LWW comparison
        clock = _clock_tuple(op.timestamp_ms, op.client_id, op.version, op.op_id)

        # Get or initialize registers metadata
        regs = self.meta.get("registers")
        if not isinstance(regs, dict):
            regs = {}
            self.meta["registers"] = regs

        # Check existing clock for this path
        prev = regs.get(path) if isinstance(regs, dict) else None
        prev_clock = prev.get("clock") if isinstance(prev, dict) else None

        # LWW check: only apply if newer
        if not _is_newer(prev_clock, clock):
            return False  # Older operation — reject

        # Navigate to container (don't create — we're deleting)
        parts = _split_path(path)
        parent, key = _get_container(self.state, parts, create=False)

        # Actually delete from materialized state if it exists
        existed = False
        if parent is not None and key and key in parent:
            existed = True
            try:
                del parent[key]  # Remove from state
            except Exception:
                parent[key] = None  # Fallback: set to None

        # Mark as tombstone in metadata (clock + deleted=True)
        regs[path] = {"clock": list(clock), "deleted": True}

        # Clear any counter metadata for this path.
        # Deleting a counter should remove its increment history.
        try:
            inc = self.meta.get("increments")
            if isinstance(inc, dict) and path in inc:
                del inc[path]
        except Exception:
            pass  # Silently handle cleanup errors

        _ = existed  # For future metrics (track actual deletions)
        return True

    # =========================================================================
    # LWW COLLECTIONS
    # =========================================================================
    # Collections are sets of elements identified by element_id.
    # ADD upserts an element, REMOVE tombstones it.
    # Supports both dict mode (keyed by element_id) and list mode.

    def _collection_mode(self, path: str) -> str:
        """Determine collection storage mode for a path.

        Args:
            path: Collection path (e.g., "characters").

        Returns:
            "list[Any]" for array storage, "dict[str, Any]" for map storage.
        """
        base = _split_path(path)[:1]
        root = base[0] if base else str(path)
        # Canonical list[Any] collection today.
        if root in {"characters"}:
            return "list[Any]"  # Array storage
        return "dict[str, Any]"  # Map storage (default)

    def _apply_add(self, op: Operation) -> bool:
        """Apply ADD operation (collection upsert).

        Adds or updates an element in a collection.
        Element is identified by element_id (from op or extracted from value).

        Args:
            op: ADD operation with path, value, and optional element_id.

        Returns:
            True if operation was applied, False if older.
        """
        # Normalize and validate collection path
        collection_path = str(op.path or "").strip()
        if not collection_path:
            return False  # Empty path — reject

        # Get element ID (from operation or extracted from value dict)
        element_id = op.element_id or _extract_element_id(op.value)
        if not element_id:
            return False  # No element ID — can't track in collection

        # Create clock tuple for LWW comparison
        clock = _clock_tuple(op.timestamp_ms, op.client_id, op.version, op.op_id)

        # Get or initialize collections metadata
        cols = self.meta.get("collections")
        if not isinstance(cols, dict):
            cols = {}
            self.meta["collections"] = cols

        # Get collection for this path
        col = cols.get(collection_path)
        if not isinstance(col, dict):
            col = {}  # New collection

        # Check existing clock for this element
        prev = col.get(element_id)
        prev_clock = prev.get("clock") if isinstance(prev, dict) else None

        # LWW check: only apply if newer
        if not _is_newer(prev_clock, clock):
            return False  # Older operation — reject

        # Navigate to collection container in materialized state
        parts = _split_path(collection_path)
        parent, key = _get_container(self.state, parts, create=True)
        if parent is None or key == "":
            return False  # Invalid path structure

        # Determine storage mode for this collection
        mode = self._collection_mode(collection_path)
        changed = False

        # Apply element based on storage mode
        if mode == "dict[str, Any]":
            # Dict mode: keyed by element_id
            cur = parent.get(key)
            if not isinstance(cur, dict):
                cur = {}  # Initialize as dict
                parent[key] = cur
            prev_val = cur.get(element_id)
            cur[element_id] = op.value  # Upsert element
            changed = prev_val != op.value
        else:
            # List mode: array of elements, matched by element_id
            cur = parent.get(key)
            if not isinstance(cur, list):
                cur = []  # Initialize as list
                parent[key] = cur

            # Search for existing element with matching ID
            idx = None
            for i, item in enumerate(list(cur)):
                if isinstance(item, dict) and _extract_element_id(item) == element_id:
                    idx = i  # Found existing element
                    break

            if idx is None:
                # New element: append to list
                cur.append(op.value)
                changed = True
            else:
                # Existing element: update in place
                changed = cur[idx] != op.value
                cur[idx] = op.value

        # Update metadata: mark element as present (not deleted)
        col[element_id] = {"clock": list(clock), "deleted": False}
        cols[collection_path] = col
        _ = changed  # For future metrics (track actual changes)
        return True

    def _apply_remove(self, op: Operation) -> bool:
        """Apply REMOVE operation (collection element tombstone).

        Removes an element from a collection by element_id.
        Creates a tombstone in metadata to prevent resurrection on
        out-of-order ADD operations.

        Tombstone vs Immediate Deletion:
            We mark elements as deleted in metadata rather than just
            removing from state. This ensures that if a concurrent ADD
            arrives later (out of order), the DELETE wins based on
            clock comparison.

        Args:
            op: REMOVE operation with path and element_id.

        Returns:
            True if operation was applied, False if older.
        """
        # ─────────────────────────────────────────────────────────────────
        # Validate: Need both collection path and element ID
        # ─────────────────────────────────────────────────────────────────
        collection_path = str(op.path or "").strip()
        element_id = op.element_id
        if not collection_path or not element_id:
            return False  # Missing required fields

        # Create clock tuple for LWW comparison
        clock = _clock_tuple(op.timestamp_ms, op.client_id, op.version, op.op_id)

        # ─────────────────────────────────────────────────────────────────
        # Get/Create Collection Metadata
        # ─────────────────────────────────────────────────────────────────
        cols = self.meta.get("collections")
        if not isinstance(cols, dict):
            cols = {}
            self.meta["collections"] = cols

        col = cols.get(collection_path)
        if not isinstance(col, dict):
            col = {}  # New collection metadata

        # ─────────────────────────────────────────────────────────────────
        # LWW Check: Only apply if this is a newer operation
        # ─────────────────────────────────────────────────────────────────
        prev = col.get(element_id)
        prev_clock = prev.get("clock") if isinstance(prev, dict) else None

        if not _is_newer(prev_clock, clock):
            return False  # Older operation — ignore

        # ─────────────────────────────────────────────────────────────────
        # Materialize: Remove from visible state
        # ─────────────────────────────────────────────────────────────────
        parts = _split_path(collection_path)
        parent, key = _get_container(self.state, parts, create=False)
        removed = False

        if parent is not None and key:
            mode = self._collection_mode(collection_path)
            cur = parent.get(key)

            if mode == "dict[str, Any]":
                # Dict mode: simple key deletion
                if isinstance(cur, dict) and element_id in cur:
                    removed = True
                    try:
                        del cur[element_id]
                    except Exception:
                        cur[element_id] = None  # Fallback
            else:
                # List mode: filter out matching element
                if isinstance(cur, list):
                    before = len(cur)
                    # In-place filter: keep only non-matching elements
                    cur[:] = [
                        it
                        for it in cur
                        if not (isinstance(it, dict) and _extract_element_id(it) == element_id)
                    ]
                    removed = len(cur) != before

        # ─────────────────────────────────────────────────────────────────
        # Record Tombstone: Mark element as deleted in metadata
        # ─────────────────────────────────────────────────────────────────
        col[element_id] = {"clock": list(clock), "deleted": True}
        cols[collection_path] = col
        _ = removed  # For future metrics (track actual removals)
        return True

    # =========================================================================
    # IDEMPOTENT COUNTERS
    # =========================================================================
    # Counters track per-operation increments for idempotency.
    # Each op_id can only increment once, preventing double-counting
    # on retries or out-of-order delivery.

    def _apply_increment(self, op: Operation) -> bool:
        """Apply INCREMENT operation (idempotent counter).

        Adds delta to counter at path. Each op_id can only be
        applied once, making this idempotent for retries and
        duplicates.

        Counter Design:
            Unlike registers, counters don't use simple LWW. Instead,
            we track each unique op_id and its delta. The counter value
            is sum(base + all deltas). This allows concurrent increments
            from multiple clients without conflict.

        Idempotency:
            If the same op_id arrives twice (retry, duplicate), we
            only count it once. This is achieved by tracking op_id → delta
            in the ops_map.

        Args:
            op: INCREMENT operation with path and numeric value (delta).

        Returns:
            True if operation was applied, False if already seen or invalid.
        """
        # ─────────────────────────────────────────────────────────────────
        # Validate Path and Delta
        # ─────────────────────────────────────────────────────────────────
        path = str(op.path or "").strip()
        if not path:
            return False  # Empty path — reject

        try:
            delta = float(op.value)  # Must be numeric
        except Exception:
            return False  # Non-numeric value — reject

        # ─────────────────────────────────────────────────────────────────
        # Get/Create Counter Metadata
        # ─────────────────────────────────────────────────────────────────
        inc = self.meta.get("increments")
        if not isinstance(inc, dict):
            inc = {}
            self.meta["increments"] = inc

        entry = inc.get(path)
        if not isinstance(entry, dict):
            # Initialize new counter structure
            entry = {"ops": {}, "base_clock": [0, "", 0, ""], "base": 0.0}
            inc[path] = entry

        ops_map = entry.get("ops")
        if not isinstance(ops_map, dict):
            ops_map = {}
            entry["ops"] = ops_map

        # ─────────────────────────────────────────────────────────────────
        # Idempotency Check: Have we seen this op_id before?
        # ─────────────────────────────────────────────────────────────────
        if op.op_id in ops_map:
            return False  # Duplicate operation — already counted

        # ─────────────────────────────────────────────────────────────────
        # Clock Check: Reject operations older than base_clock
        # ─────────────────────────────────────────────────────────────────
        clock = _clock_tuple(op.timestamp_ms, op.client_id, op.version, op.op_id)

        base_clock = entry.get("base_clock") or [0, "", 0, ""]
        try:
            base_clock_t = (
                int(base_clock[0]),
                str(base_clock[1]),
                int(base_clock[2]),
                str(base_clock[3]),
            )
        except Exception:
            base_clock_t = (0, "", 0, "")

        if clock < base_clock_t:
            return False  # Operation predates base — ignore

        # ─────────────────────────────────────────────────────────────────
        # Record This Increment (for idempotency + recomputation)
        # ─────────────────────────────────────────────────────────────────
        ops_map[op.op_id] = {"delta": delta, "clock": list(clock)}

        # ─────────────────────────────────────────────────────────────────
        # Materialize: Update counter value in state
        # ─────────────────────────────────────────────────────────────────
        parts = _split_path(path)
        parent, key = _get_container(self.state, parts, create=True)
        if parent is None or key == "":
            return False  # Invalid path structure

        # Get current value (or base if not set)
        cur = parent.get(key)
        cur_val = float(cur) if isinstance(cur, (int, float)) else float(entry.get("base") or 0.0)

        # Apply delta
        parent[key] = cur_val + delta
        return True

    def _recompute_counter(self, path: str) -> None:
        """Recompute counter value from all recorded increments.

        Called after SET operations to maintain counter invariants.
        When a SET overwrites a counter path, we need to update
        base and base_clock, then sum only newer increments.

        Algorithm:
            total = base + sum(delta for op where op.clock >= base_clock)

        This ensures that SET operations can "reset" counters while
        preserving any concurrent increments from other clients.

        Args:
            path: Counter path to recompute.
        """
        # ─────────────────────────────────────────────────────────────────
        # Get Counter Metadata
        # ─────────────────────────────────────────────────────────────────
        inc = self.meta.get("increments")
        if not isinstance(inc, dict):
            return  # No counter metadata

        entry = inc.get(path)
        if not isinstance(entry, dict):
            return  # No entry for this path

        ops_map = entry.get("ops")
        if not isinstance(ops_map, dict):
            ops_map = {}

        # ─────────────────────────────────────────────────────────────────
        # Parse Base Clock (threshold for counting increments)
        # ─────────────────────────────────────────────────────────────────
        base_clock = entry.get("base_clock") or [0, "", 0, ""]
        try:
            base_clock_t = (
                int(base_clock[0]),
                str(base_clock[1]),
                int(base_clock[2]),
                str(base_clock[3]),
            )
        except Exception:
            base_clock_t = (0, "", 0, "")

        # ─────────────────────────────────────────────────────────────────
        # Sum All Valid Increments (newer than or equal to base_clock)
        # ─────────────────────────────────────────────────────────────────
        total = float(entry.get("base") or 0.0)  # Start with base value

        for rec in ops_map.values():
            if not isinstance(rec, dict):
                continue

            # Parse increment's clock
            c = rec.get("clock") or []
            try:
                ct = (int(c[0]), str(c[1]), int(c[2]), str(c[3]))
            except Exception:
                continue  # Malformed clock — skip

            # Only count increments at or after base_clock
            if ct >= base_clock_t:
                try:
                    total += float(rec.get("delta") or 0.0)
                except Exception:
                    continue  # Non-numeric delta — skip

        # ─────────────────────────────────────────────────────────────────
        # Materialize: Update counter in state
        # ─────────────────────────────────────────────────────────────────
        parts = _split_path(path)
        parent, key = _get_container(self.state, parts, create=True)
        if parent is None or key == "":
            return  # Invalid path
        parent[key] = total

    # =========================================================================
    # PUBLIC ACCESSORS
    # =========================================================================

    def get_state(self) -> dict[str, Any]:
        """Get the materialized state (no CRDT metadata).

        Returns:
            Plain JSON state dictionary.
        """
        return self.state

    def get_vector_clock(self) -> dict[str, int]:
        """Get the current vector clock.

        Returns:
            Dict mapping client_id → highest version seen.
        """
        return dict(self.vector_clock)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def create_operation(
    *,
    op_type: OperationType,
    path: str,
    value: Any,
    client_id: str,
    version: int,
    dependencies: dict[str, int] | None = None,
    timestamp_ms: int | None = None,
    element_id: str | None = None,
    op_id: str | None = None,
) -> Operation:
    """Create a CRDT operation with sensible defaults.

    Factory function that generates op_id and timestamp if not provided.
    Used by API routes for operation creation.

    Args:
        op_type: Type of operation (SET, ADD, REMOVE, INCREMENT).
        path: Dot-separated path in state tree.
        value: Value to set/add/increment.
        client_id: ID of client creating operation.
        version: Client-local version counter.
        dependencies: Optional causal dependencies.
        timestamp_ms: Optional timestamp (defaults to now).
        element_id: Optional collection element ID.
        op_id: Optional operation ID (defaults to UUID).

    Returns:
        Operation instance with all fields populated.

    Example:
        >>> op = create_operation(
        ...     op_type=OperationType.SET,
        ...     path="users.alice.status",
        ...     value="online",
        ...     client_id="client-1",
        ...     version=1,
        ... )
    """
    # Default timestamp to current wall-clock time
    ts = int(time.time() * 1000) if timestamp_ms is None else int(timestamp_ms)

    return Operation(
        op_id=str(op_id or "").strip() or uuid.uuid4().hex,  # Generate UUID if not provided
        type=op_type,
        path=str(path),
        value=value,
        element_id=(str(element_id).strip() if element_id is not None else None),
        client_id=str(client_id),
        version=int(version),
        timestamp_ms=ts,
        dependencies=dict(dependencies or {}),
    )


# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    # Operation dataclass
    "Operation",
    # Operation type enum
    "OperationType",
    # Main CRDT class
    "RoomStateCRDT",
    # Factory function
    "create_operation",
]
