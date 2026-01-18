"""CRDT-based state synchronization for chronOS colonies.

Per-colony μ state synchronization using Conflict-Free Replicated Data Types.
Enables distributed, eventually-consistent state sharing across 7 colonies × N instances.

ARCHITECTURE:
=============
- LWWRegister: Last-Writer-Wins register for z-states (timestamp-based)
- GSet: Grow-only set[Any] for action history (append-only)
- ColonyStateCRDT: Per-colony CRDT with Fano neighbor observation
- Etcd backend: Distributed KV store with leases and watches

CRDT PROPERTIES:
================
- Commutative: merge(A, B) = merge(B, A)
- Associative: merge(merge(A, B), C) = merge(A, merge(B, C))
- Idempotent: merge(A, A) = A
- Eventually consistent: All replicas converge to same state

SYNCHRONIZATION PATTERN:
========================
1. Each colony instance syncs its z-state via LWW semantics
2. Fano neighbors observe each other's states via etcd watches
3. Action logs accumulate via GSet (monotonic growth)
4. Leases ensure auto-expiry on crash (default TTL: 10s)

Created: December 15, 2025
"""

from __future__ import annotations

# Standard library imports
import asyncio
import base64
import io
import logging
import time
from collections.abc import Callable
from dataclasses import (
    dataclass,
    field,
)
from typing import (
    Any,
    cast,
)

# Third-party imports
import msgpack
import torch

# Local imports
from kagami.core.consensus.etcd_client import (
    EtcdConnectionError,
    etcd_operation,
    get_etcd_client,
)
from kagami.core.safety.decentralized_cbf import FANO_NEIGHBORS

logger = logging.getLogger(__name__)

# =============================================================================
# CRDT DATA STRUCTURES
# =============================================================================


@dataclass
class LWWRegister:
    """Last-Writer-Wins register for z-states.

    Conflict resolution: Timestamp ordering (higher timestamp wins).
    If timestamps equal, use lexicographic ordering of node IDs.
    """

    value: torch.Tensor | None = None
    timestamp: float = 0.0
    node_id: str = ""  # Tie-breaker for equal timestamps

    def update(self, value: torch.Tensor, timestamp: float, node_id: str = "") -> bool:
        """Update if timestamp newer (or node_id wins tie).

        Args:
            value: New z-state tensor
            timestamp: Update timestamp
            node_id: Node identifier for tie-breaking

        Returns:
            True if update applied, False if rejected (stale)
        """
        # Timestamp ordering
        if timestamp > self.timestamp:
            self.value = value
            self.timestamp = timestamp
            self.node_id = node_id
            return True
        elif timestamp == self.timestamp:
            # Tie-break via node_id (deterministic ordering)
            if node_id > self.node_id:
                self.value = value
                self.node_id = node_id
                return True
        return False

    def merge(self, other: LWWRegister) -> None:
        """Merge with another LWWRegister (CRDT merge semantics).

        Args:
            other: Another LWWRegister to merge
        """
        if other.value is not None:
            self.update(other.value, other.timestamp, other.node_id)


@dataclass
class GSet:
    """Grow-only set[Any] for action history.

    Elements can only be added, never removed (monotonic growth).
    Merge is set[Any] union.
    """

    elements: set[str] = field(default_factory=set[Any])

    def add(self, element: str) -> bool:
        """Add element (idempotent).

        Args:
            element: Action identifier to add

        Returns:
            True if newly added, False if already present
        """
        if element in self.elements:
            return False
        self.elements.add(element)
        return True

    def contains(self, element: str) -> bool:
        """Check if element is in set[Any].

        Args:
            element: Action identifier

        Returns:
            True if present
        """
        return element in self.elements

    def merge(self, other: GSet) -> None:
        """Merge with another GSet (set[Any] union).

        Args:
            other: Another GSet to merge
        """
        self.elements.update(other.elements)

    def size(self) -> int:
        """Get set[Any] size."""
        return len(self.elements)


# =============================================================================
# SERIALIZATION
# =============================================================================


def serialize_tensor(tensor: torch.Tensor) -> bytes:
    """Serialize tensor to bytes using torch.save.

    Args:
        tensor: Tensor to serialize

    Returns:
        Serialized bytes
    """
    buffer = io.BytesIO()
    torch.save(tensor, buffer)
    return buffer.getvalue()


def deserialize_tensor(data: bytes) -> torch.Tensor:
    """Deserialize tensor from bytes.

    Args:
        data: Serialized tensor bytes

    Returns:
        Deserialized tensor
    """
    buffer = io.BytesIO(data)
    return cast(torch.Tensor, torch.load(buffer, weights_only=True))


def serialize_with_timestamp(lww: LWWRegister) -> bytes:
    """Serialize LWWRegister with timestamp for etcd storage.

    Uses msgpack for compact metadata + base64 for tensor bytes.

    Args:
        lww: LWWRegister to serialize

    Returns:
        Serialized bytes
    """
    if lww.value is None:
        return msgpack.packb({"timestamp": lww.timestamp, "node_id": lww.node_id, "value": None})  # type: ignore[no-any-return]

    tensor_bytes = serialize_tensor(lww.value)
    tensor_b64 = base64.b64encode(tensor_bytes).decode("ascii")

    payload = {
        "timestamp": lww.timestamp,
        "node_id": lww.node_id,
        "value": tensor_b64,
        "shape": list(lww.value.shape),
        "dtype": str(lww.value.dtype),
    }

    return msgpack.packb(payload)  # type: ignore[no-any-return]


def deserialize_with_timestamp(data: bytes) -> LWWRegister:
    """Deserialize LWWRegister from bytes.

    Args:
        data: Serialized bytes

    Returns:
        Deserialized LWWRegister
    """
    payload = msgpack.unpackb(data, raw=False)

    if payload["value"] is None:
        return LWWRegister(value=None, timestamp=payload["timestamp"], node_id=payload["node_id"])

    tensor_bytes = base64.b64decode(payload["value"].encode("ascii"))
    tensor = deserialize_tensor(tensor_bytes)

    return LWWRegister(value=tensor, timestamp=payload["timestamp"], node_id=payload["node_id"])


def serialize_gset(gset: GSet) -> bytes:
    """Serialize GSet to bytes.

    Args:
        gset: GSet to serialize

    Returns:
        Serialized bytes
    """
    return msgpack.packb({"elements": list(gset.elements)})  # type: ignore[no-any-return]


def deserialize_gset(data: bytes) -> GSet:
    """Deserialize GSet from bytes.

    Args:
        data: Serialized bytes

    Returns:
        Deserialized GSet
    """
    payload = msgpack.unpackb(data, raw=False)
    return GSet(elements=set(payload["elements"]))


# =============================================================================
# COLONY STATE CRDT
# =============================================================================


class ColonyStateCRDT:
    """CRDT for colony state synchronization.

    Manages per-colony z-state (LWW) and action log (GSet) with etcd backend.
    Supports Fano neighbor observation via etcd watches.

    Architecture:
        colony_i → etcd → colony_j (via watch)
        Lease-based TTL: 10s (auto-expiry on crash)
    """

    def __init__(
        self,
        colony_id: int,
        node_id: str,
        lease_ttl: int = 10,
        sync_interval: float = 1.0,
    ):
        """Initialize colony state CRDT.

        Args:
            colony_id: Colony index (0-6)
            node_id: Node identifier (e.g., "node-0-colony-0-replica-1")
            lease_ttl: Lease TTL in seconds (auto-expiry)
            sync_interval: Background sync interval in seconds
        """
        if colony_id < 0 or colony_id > 6:
            raise ValueError(f"Invalid colony_id: {colony_id}. Must be in [0, 6].")

        self.colony_id = colony_id
        self.node_id = node_id
        self.lease_ttl = lease_ttl
        self.sync_interval = sync_interval

        # CRDT state
        self.z_state_lww = LWWRegister()
        self.action_log = GSet()

        # Fano neighbors
        self.neighbors = FANO_NEIGHBORS[colony_id]

        # Etcd client (lazy initialization)
        self._etcd_client: Any = None
        self._lease_id: int | None = None

        # Watch tasks
        self._watch_tasks: list[asyncio.Task] = []
        self._sync_task: asyncio.Task | None = None
        self._running = False

        logger.info(
            f"ColonyStateCRDT initialized: colony={colony_id}, node={node_id}, "
            f"neighbors={self.neighbors}, lease_ttl={lease_ttl}s"
        )

    def _get_etcd_client(self) -> Any:
        """Get etcd client (lazy initialization)."""
        if self._etcd_client is None:
            self._etcd_client = get_etcd_client()
        return self._etcd_client

    def _get_z_state_key(self, colony_id: int) -> str:
        """Get etcd key for colony z-state."""
        return f"kagami:colony:{colony_id}:z_state"

    def _get_action_log_key(self, colony_id: int) -> str:
        """Get etcd key for colony action log."""
        return f"kagami:colony:{colony_id}:action_log"

    def _get_lease(self) -> int:
        """Get or create etcd lease.

        Returns:
            Lease ID
        """
        if self._lease_id is None:
            try:
                with etcd_operation("create_lease") as client:
                    lease = client.lease(ttl=self.lease_ttl)
                    self._lease_id = lease.id
                    logger.debug(
                        f"Created etcd lease: colony={self.colony_id}, lease_id={self._lease_id}"
                    )
            except Exception as e:
                logger.error(f"Failed to create etcd lease: {e}")
                raise EtcdConnectionError(f"Lease creation failed: {e}") from e
        return self._lease_id

    # =========================================================================
    # SYNC OPERATIONS
    # =========================================================================

    async def sync_z_state(self) -> bool:
        """Push local z-state to etcd for Fano neighbors.

        Returns:
            True if sync succeeded
        """
        if self.z_state_lww.value is None:
            logger.debug(f"Colony {self.colony_id}: No z-state to sync")
            return False

        key = self._get_z_state_key(self.colony_id)

        try:
            # Serialize with timestamp
            data = serialize_with_timestamp(self.z_state_lww)

            # Store with lease
            with etcd_operation("put_z_state") as client:
                lease_id = self._get_lease()
                client.put(key, data, lease=lease_id)

            logger.debug(
                f"Colony {self.colony_id}: Synced z-state "
                f"(timestamp={self.z_state_lww.timestamp:.3f})"
            )
            return True

        except Exception as e:
            logger.error(f"Colony {self.colony_id}: z-state sync failed: {e}")
            return False

    async def sync_action_log(self) -> bool:
        """Push action log to etcd.

        Returns:
            True if sync succeeded
        """
        if self.action_log.size() == 0:
            return False

        key = self._get_action_log_key(self.colony_id)

        try:
            data = serialize_gset(self.action_log)

            with etcd_operation("put_action_log") as client:
                lease_id = self._get_lease()
                client.put(key, data, lease=lease_id)

            logger.debug(
                f"Colony {self.colony_id}: Synced action log (size={self.action_log.size()})"
            )
            return True

        except Exception as e:
            logger.error(f"Colony {self.colony_id}: action log sync failed: {e}")
            return False

    async def observe_neighbors(self) -> dict[int, torch.Tensor]:
        """Read Fano neighbors' z-states from etcd.

        Returns:
            Dict mapping neighbor_id → z_tensor
        """
        neighbor_states: dict[int, torch.Tensor] = {}

        for neighbor_id in self.neighbors:
            key = self._get_z_state_key(neighbor_id)

            try:
                with etcd_operation("get_z_state") as client:
                    value, _metadata = client.get(key)

                if value is None:
                    logger.debug(f"Colony {self.colony_id}: No z-state for neighbor {neighbor_id}")
                    continue

                # Deserialize
                lww = deserialize_with_timestamp(value)
                if lww.value is not None:
                    neighbor_states[neighbor_id] = lww.value

            except Exception as e:
                logger.warning(
                    f"Colony {self.colony_id}: Failed to read neighbor {neighbor_id}: {e}"
                )
                continue

        return neighbor_states

    async def observe_neighbor_action_logs(self) -> dict[int, GSet]:
        """Read Fano neighbors' action logs from etcd.

        Returns:
            Dict mapping neighbor_id → GSet
        """
        neighbor_logs: dict[int, GSet] = {}

        for neighbor_id in self.neighbors:
            key = self._get_action_log_key(neighbor_id)

            try:
                with etcd_operation("get_action_log") as client:
                    value, _metadata = client.get(key)

                if value is None:
                    continue

                gset = deserialize_gset(value)
                neighbor_logs[neighbor_id] = gset

            except Exception as e:
                logger.warning(
                    f"Colony {self.colony_id}: Failed to read neighbor log {neighbor_id}: {e}"
                )
                continue

        return neighbor_logs

    # =========================================================================
    # LOCAL UPDATES
    # =========================================================================

    def update_z_state(self, z: torch.Tensor) -> None:
        """Update local z-state with current timestamp.

        Args:
            z: New z-state tensor
        """
        timestamp = time.time()
        self.z_state_lww.update(z, timestamp, self.node_id)
        logger.debug(f"Colony {self.colony_id}: Updated local z-state (t={timestamp:.3f})")

    def add_action(self, action_id: str) -> bool:
        """Add action to local log.

        Args:
            action_id: Action identifier (e.g., "forge-compile-12345")

        Returns:
            True if newly added
        """
        added = self.action_log.add(action_id)
        if added:
            logger.debug(f"Colony {self.colony_id}: Added action {action_id}")
        return added

    def merge_neighbor_state(self, neighbor_id: int, lww: LWWRegister) -> bool:
        """Merge neighbor's z-state into local state (CRDT merge).

        Args:
            neighbor_id: Neighbor colony ID
            lww: Neighbor's LWWRegister

        Returns:
            True if local state changed
        """
        if neighbor_id not in self.neighbors:
            logger.warning(
                f"Colony {self.colony_id}: Ignoring non-neighbor {neighbor_id} (not on Fano line)"
            )
            return False

        old_timestamp = self.z_state_lww.timestamp
        self.z_state_lww.merge(lww)

        if self.z_state_lww.timestamp > old_timestamp:
            logger.debug(
                f"Colony {self.colony_id}: Merged neighbor {neighbor_id} state "
                f"(t={lww.timestamp:.3f})"
            )
            return True
        return False

    def merge_neighbor_log(self, neighbor_id: int, gset: GSet) -> int:
        """Merge neighbor's action log (CRDT merge).

        Args:
            neighbor_id: Neighbor colony ID
            gset: Neighbor's GSet

        Returns:
            Number of new actions added
        """
        if neighbor_id not in self.neighbors:
            return 0

        old_size = self.action_log.size()
        self.action_log.merge(gset)
        new_actions = self.action_log.size() - old_size

        if new_actions > 0:
            logger.debug(
                f"Colony {self.colony_id}: Merged {new_actions} actions from neighbor {neighbor_id}"
            )

        return new_actions

    # =========================================================================
    # WATCH API
    # =========================================================================

    async def watch_neighbor_updates(self, callback: Callable[[int, torch.Tensor], Any]) -> None:
        """Watch for neighbor z-state updates.

        Spawns watch tasks for all Fano neighbors.

        Args:
            callback: Async callback(neighbor_id, z_tensor)
        """
        for neighbor_id in self.neighbors:
            task = asyncio.create_task(self._watch_neighbor(neighbor_id, callback))
            self._watch_tasks.append(task)

        logger.info(f"Colony {self.colony_id}: Watching {len(self.neighbors)} neighbors")

    async def _watch_neighbor(
        self, neighbor_id: int, callback: Callable[[int, torch.Tensor], Any]
    ) -> None:
        """Watch a single neighbor's z-state.

        Args:
            neighbor_id: Neighbor colony ID
            callback: Callback for updates
        """
        key = self._get_z_state_key(neighbor_id)

        logger.debug(f"Colony {self.colony_id}: Starting watch on neighbor {neighbor_id}")

        while self._running:
            try:
                with etcd_operation("watch") as client:
                    events_iterator, cancel = client.watch(key)

                    for event in events_iterator:
                        if not self._running:
                            cancel()  # type: ignore[unreachable]
                            break

                        try:
                            # Deserialize update
                            lww = deserialize_with_timestamp(event.value)
                            if lww.value is not None:
                                # Invoke callback
                                result = callback(neighbor_id, lww.value)
                                if asyncio.iscoroutine(result):
                                    await result

                        except Exception as e:
                            logger.error(
                                f"Colony {self.colony_id}: Watch callback failed "
                                f"for neighbor {neighbor_id}: {e}"
                            )

            except Exception as e:
                logger.error(
                    f"Colony {self.colony_id}: Watch failed for neighbor {neighbor_id}: {e}"
                )
                if self._running:
                    await asyncio.sleep(1.0)  # Backoff before retry

    # =========================================================================
    # BACKGROUND SYNC
    # =========================================================================

    async def start_sync_loop(self) -> None:
        """Start background sync loop."""
        if self._running:
            logger.warning(f"Colony {self.colony_id}: Sync loop already running")
            return

        self._running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info(f"Colony {self.colony_id}: Started sync loop (interval={self.sync_interval}s)")

    async def _sync_loop(self) -> None:
        """Background sync loop."""
        while self._running:
            try:
                # Sync z-state
                await self.sync_z_state()

                # Sync action log
                await self.sync_action_log()

                # Refresh lease
                if self._lease_id is not None:
                    try:
                        with etcd_operation("refresh_lease") as client:
                            client.refresh_lease(self._lease_id)
                    except Exception as e:
                        logger.warning(f"Colony {self.colony_id}: Lease refresh failed: {e}")
                        self._lease_id = None  # Force recreation

            except Exception as e:
                logger.error(f"Colony {self.colony_id}: Sync loop error: {e}")

            await asyncio.sleep(self.sync_interval)

    async def stop_sync_loop(self) -> None:
        """Stop background sync loop and watches."""
        self._running = False

        # Cancel sync task
        if self._sync_task is not None:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        # Cancel watch tasks
        for task in self._watch_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Revoke lease
        if self._lease_id is not None:
            try:
                with etcd_operation("revoke_lease") as client:
                    client.revoke_lease(self._lease_id)
            except Exception:
                pass

        logger.info(f"Colony {self.colony_id}: Stopped sync loop")

    # =========================================================================
    # STATUS
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get sync status.

        Returns:
            Status dict[str, Any]
        """
        return {
            "colony_id": self.colony_id,
            "node_id": self.node_id,
            "running": self._running,
            "z_state_timestamp": self.z_state_lww.timestamp,
            "action_log_size": self.action_log.size(),
            "neighbors": self.neighbors,
            "lease_id": self._lease_id,
        }


# =============================================================================
# FACTORY
# =============================================================================


def create_colony_state_crdt(
    colony_id: int,
    node_id: str,
    lease_ttl: int = 10,
    sync_interval: float = 1.0,
) -> ColonyStateCRDT:
    """Factory for creating ColonyStateCRDT.

    Args:
        colony_id: Colony index (0-6)
        node_id: Node identifier
        lease_ttl: Lease TTL in seconds
        sync_interval: Background sync interval

    Returns:
        Configured ColonyStateCRDT
    """
    return ColonyStateCRDT(
        colony_id=colony_id,
        node_id=node_id,
        lease_ttl=lease_ttl,
        sync_interval=sync_interval,
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ColonyStateCRDT",
    "GSet",
    "LWWRegister",
    "create_colony_state_crdt",
    "deserialize_gset",
    "deserialize_tensor",
    "deserialize_with_timestamp",
    "serialize_gset",
    "serialize_tensor",
    "serialize_with_timestamp",
]
