"""Kagami Rooms Module — Collaborative Real-Time State Management.

Provides infrastructure for multi-user collaborative state with
automatic conflict resolution, efficient synchronization, and
seamless reconnection handling.

Core Concepts:
    - **CRDT**: Conflict-free Replicated Data Types ensure all clients
      converge to the same state regardless of operation order.
    - **LWW (Last-Writer-Wins)**: Deterministic tie-breaking using
      timestamps, client IDs, and operation IDs.
    - **Vector Clocks**: Track causality for conflict detection.
    - **Compression**: MessagePack reduces state size by 50-70%.
    - **Smart Reconnection**: Delta catchup for small gaps, full
      snapshot for large gaps.

Architecture:
    Client → Operation → CRDT → Materialized State → Snapshot
                ↓
        Vector Clock Update
                ↓
        Delta Broadcast to Other Clients

Components:
    CRDT (crdt.py):
        - OperationType: SET, ADD, REMOVE, INCREMENT
        - Operation: Single operation with causality tracking
        - RoomStateCRDT: Main CRDT implementation

    Compression (compression.py):
        - compress_state: State → MessagePack bytes
        - decompress_state: MessagePack bytes → State

    Reconnection (reconnection.py):
        - ReconnectionManager: Smart catchup logic
        - ReconnectionResult: Catchup result (deltas or snapshot)

    State Service (state_service.py):
        - Room state persistence and retrieval
        - Delta history tracking

Example:
    >>> from kagami.core.rooms import RoomStateCRDT, Operation, OperationType
    >>>
    >>> # Create CRDT for a room
    >>> crdt = RoomStateCRDT("room-123")
    >>>
    >>> # Apply operations from clients
    >>> op = Operation(
    ...     op_id="op-1",
    ...     type=OperationType.SET,
    ...     path="users.alice.status",
    ...     value="online",
    ...     element_id=None,
    ...     client_id="client-1",
    ...     version=1,
    ...     timestamp_ms=1234567890000,
    ... )
    >>> result = crdt.apply_operation(op)
    >>>
    >>> # Get materialized state
    >>> state = crdt.get_state()
    >>> print(state["users"]["alice"]["status"])
    'online'

Thread Safety:
    CRDT operations are NOT thread-safe. Use locks or ensure
    single-threaded access per room.

Persistence:
    - Snapshots stored in Redis with MessagePack compression
    - Delta history stored for catchup (pruned after threshold)
    - Vector clocks persisted for causality tracking

See Also:
    - docs/architecture.md: System architecture
    - kagami.core.caching.redis: Redis integration
"""

# =============================================================================
# IMPORTS
# =============================================================================
# Re-export key classes and functions for convenient access.

from kagami.core.rooms.compression import compress_state, decompress_state
from kagami.core.rooms.crdt import Operation, OperationType, RoomStateCRDT
from kagami.core.rooms.reconnection import ReconnectionManager

# =============================================================================
# PUBLIC API
# =============================================================================
# These are the primary exports for external consumers.
# Internal functions (prefixed with _) are NOT exported.

__all__ = [
    # CRDT Operation Types
    "Operation",  # Single operation with causality tracking
    "OperationType",  # SET, ADD, REMOVE, INCREMENT enum
    # Reconnection Handling
    "ReconnectionManager",  # Smart catchup logic
    "RoomStateCRDT",  # Main CRDT implementation
    # Compression Functions
    "compress_state",  # State → MessagePack bytes
    "decompress_state",  # MessagePack bytes → State
]
