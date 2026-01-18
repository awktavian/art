"""Merkle Tree Audit Log — Tamper-proof append-only logging.

Provides cryptographically verifiable audit logging with:
- SHA-256 Merkle tree for integrity
- Append-only structure (immutable history)
- Inclusion proofs for specific entries
- Consistency proofs between tree states
- Persistence to multiple backends

Architecture:
```
┌─────────────────────────────────────────────────────────────────┐
│                    MERKLE AUDIT LOG                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Entry 0   Entry 1   Entry 2   Entry 3   Entry 4   Entry 5    │
│     │         │         │         │         │         │         │
│     └────┬────┘         └────┬────┘         └────┬────┘         │
│          │                   │                   │               │
│       Hash 01             Hash 23             Hash 45            │
│          │                   │                   │               │
│          └─────────┬─────────┘                   │               │
│                    │                             │               │
│                Hash 0123                         │               │
│                    │                             │               │
│                    └──────────────┬──────────────┘               │
│                                   │                              │
│                              ROOT HASH                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

Properties:
- Tamper-evident: Any modification changes the root hash
- Efficient verification: O(log n) proof size
- Append-only: New entries don't modify existing ones
- Auditable: Third parties can verify without full log access

Colony: Crystal (D₅) — Verification and audit
h(x) ≥ 0. Always.

Created: January 2026
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class AuditBackend(Enum):
    """Audit log storage backend."""

    FILESYSTEM = auto()
    MEMORY = auto()
    SQLITE = auto()


@dataclass
class AuditLogConfig:
    """Audit log configuration.

    Attributes:
        storage_path: Base path for storage.
        backend: Storage backend type.
        max_entries_per_file: Entries per log segment file.
        sync_interval: Interval for syncing to disk (seconds).
        retention_days: Days to retain entries (0 = forever).
        hash_algorithm: Hash algorithm for Merkle tree.
    """

    storage_path: str = ""
    backend: AuditBackend = AuditBackend.FILESYSTEM
    max_entries_per_file: int = 10000
    sync_interval: float = 5.0
    retention_days: int = 0
    hash_algorithm: str = "sha256"

    def __post_init__(self) -> None:
        """Load from environment."""
        if not self.storage_path:
            self.storage_path = os.environ.get(
                "KAGAMI_AUDIT_STORAGE_PATH", str(Path.home() / ".kagami" / "audit")
            )

        self.max_entries_per_file = int(
            os.environ.get("KAGAMI_AUDIT_MAX_ENTRIES_PER_FILE", str(self.max_entries_per_file))
        )


@dataclass
class AuditEntry:
    """A single audit log entry.

    Attributes:
        id: Unique entry identifier (UUID).
        timestamp: Entry timestamp (Unix epoch).
        event_type: Type of event (e.g., "user.login").
        actor: Who performed the action.
        resource: Resource affected.
        action: Action performed.
        data: Additional event data.
        parent_hash: Hash of previous entry (chain).
        hash: SHA-256 hash of this entry.
    """

    id: str
    timestamp: float
    event_type: str
    actor: str
    resource: str = ""
    action: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    parent_hash: str = ""
    hash: str = ""

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of entry."""
        content = json.dumps(
            {
                "id": self.id,
                "timestamp": self.timestamp,
                "event_type": self.event_type,
                "actor": self.actor,
                "resource": self.resource,
                "action": self.action,
                "data": self.data,
                "parent_hash": self.parent_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "actor": self.actor,
            "resource": self.resource,
            "action": self.action,
            "data": self.data,
            "parent_hash": self.parent_hash,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEntry:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            event_type=data["event_type"],
            actor=data["actor"],
            resource=data.get("resource", ""),
            action=data.get("action", ""),
            data=data.get("data", {}),
            parent_hash=data.get("parent_hash", ""),
            hash=data.get("hash", ""),
        )


@dataclass
class MerkleNode:
    """A node in the Merkle tree.

    Attributes:
        hash: SHA-256 hash of this node.
        left: Left child hash (or entry hash for leaves).
        right: Right child hash (or None for leaves).
        level: Tree level (0 = leaves).
        index: Index at this level.
    """

    hash: str
    left: str = ""
    right: str = ""
    level: int = 0
    index: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "hash": self.hash,
            "left": self.left,
            "right": self.right,
            "level": self.level,
            "index": self.index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MerkleNode:
        """Deserialize from dictionary."""
        return cls(
            hash=data["hash"],
            left=data.get("left", ""),
            right=data.get("right", ""),
            level=data.get("level", 0),
            index=data.get("index", 0),
        )


@dataclass
class InclusionProof:
    """Proof that an entry is included in the Merkle tree.

    Attributes:
        entry_hash: Hash of the entry being proven.
        entry_index: Index of the entry in the log.
        root_hash: Root hash of the tree.
        tree_size: Number of entries in the tree.
        path: List of sibling hashes from leaf to root.
        path_directions: List of directions (0=left, 1=right).
    """

    entry_hash: str
    entry_index: int
    root_hash: str
    tree_size: int
    path: list[str] = field(default_factory=list)
    path_directions: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "entry_hash": self.entry_hash,
            "entry_index": self.entry_index,
            "root_hash": self.root_hash,
            "tree_size": self.tree_size,
            "path": self.path,
            "path_directions": self.path_directions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InclusionProof:
        """Deserialize from dictionary."""
        return cls(
            entry_hash=data["entry_hash"],
            entry_index=data["entry_index"],
            root_hash=data["root_hash"],
            tree_size=data["tree_size"],
            path=data.get("path", []),
            path_directions=data.get("path_directions", []),
        )


class AuditLogIntegrityError(Exception):
    """Raised when audit log integrity is compromised."""

    pass


# =============================================================================
# Merkle Tree Implementation
# =============================================================================


class MerkleTree:
    """Merkle tree for audit log integrity.

    Implements a complete binary Merkle tree with SHA-256 hashing.
    Supports incremental updates and inclusion proofs.
    """

    def __init__(self) -> None:
        self._leaves: list[str] = []
        self._nodes: dict[tuple[int, int], MerkleNode] = {}
        self._root_hash: str = ""

    @staticmethod
    def hash_pair(left: str, right: str) -> str:
        """Hash two nodes together."""
        combined = (left + right).encode()
        return hashlib.sha256(combined).hexdigest()

    def append(self, entry_hash: str) -> str:
        """Append a new leaf and rebuild affected nodes.

        Args:
            entry_hash: Hash of the new entry.

        Returns:
            New root hash.
        """
        self._leaves.append(entry_hash)
        self._rebuild_tree()
        return self._root_hash

    def _rebuild_tree(self) -> None:
        """Rebuild the Merkle tree from leaves."""
        if not self._leaves:
            self._root_hash = ""
            return

        self._nodes.clear()

        # Level 0: leaves
        current_level = self._leaves.copy()
        level = 0

        for i, hash in enumerate(current_level):
            self._nodes[(level, i)] = MerkleNode(
                hash=hash,
                left=hash,
                level=level,
                index=i,
            )

        # Build up the tree
        while len(current_level) > 1:
            next_level = []
            level += 1

            for i in range(0, len(current_level), 2):
                left = current_level[i]

                # If odd number, duplicate last
                right = current_level[i + 1] if i + 1 < len(current_level) else left

                parent_hash = self.hash_pair(left, right)
                next_level.append(parent_hash)

                self._nodes[(level, i // 2)] = MerkleNode(
                    hash=parent_hash,
                    left=left,
                    right=right,
                    level=level,
                    index=i // 2,
                )

            current_level = next_level

        self._root_hash = current_level[0] if current_level else ""

    @property
    def root_hash(self) -> str:
        """Get current root hash."""
        return self._root_hash

    @property
    def size(self) -> int:
        """Get number of leaves."""
        return len(self._leaves)

    def get_inclusion_proof(self, index: int) -> InclusionProof:
        """Generate inclusion proof for entry at index.

        Args:
            index: Entry index.

        Returns:
            Inclusion proof.

        Raises:
            IndexError: If index out of range.
        """
        if index < 0 or index >= len(self._leaves):
            raise IndexError(f"Index {index} out of range (size={len(self._leaves)})")

        path = []
        path_directions = []

        current_index = index
        level = 0
        level_size = len(self._leaves)

        while level_size > 1:
            # Determine sibling
            if current_index % 2 == 0:
                # We're on the left, sibling is on right
                sibling_index = current_index + 1
                path_directions.append(1)  # Sibling goes on right
            else:
                # We're on the right, sibling is on left
                sibling_index = current_index - 1
                path_directions.append(0)  # Sibling goes on left

            # Get sibling hash
            if sibling_index < level_size:
                sibling_node = self._nodes.get((level, sibling_index))
                if sibling_node:
                    path.append(sibling_node.hash)
                else:
                    # Duplicate current if no sibling
                    current_node = self._nodes.get((level, current_index))
                    if current_node:
                        path.append(current_node.hash)
            else:
                # No sibling, use duplicate
                current_node = self._nodes.get((level, current_index))
                if current_node:
                    path.append(current_node.hash)

            # Move to parent
            current_index //= 2
            level += 1
            level_size = (level_size + 1) // 2

        return InclusionProof(
            entry_hash=self._leaves[index],
            entry_index=index,
            root_hash=self._root_hash,
            tree_size=len(self._leaves),
            path=path,
            path_directions=path_directions,
        )

    @staticmethod
    def verify_inclusion(proof: InclusionProof) -> bool:
        """Verify an inclusion proof.

        Args:
            proof: Inclusion proof to verify.

        Returns:
            True if proof is valid.
        """
        current_hash = proof.entry_hash

        for sibling_hash, direction in zip(proof.path, proof.path_directions, strict=False):
            if direction == 0:
                # Sibling on left
                current_hash = MerkleTree.hash_pair(sibling_hash, current_hash)
            else:
                # Sibling on right
                current_hash = MerkleTree.hash_pair(current_hash, sibling_hash)

        return current_hash == proof.root_hash


# =============================================================================
# Storage Backends
# =============================================================================


class AuditBackendBase(ABC):
    """Abstract base for audit log backends."""

    @abstractmethod
    async def append_entry(self, entry: AuditEntry) -> None:
        """Append an entry."""
        ...

    @abstractmethod
    async def get_entry(self, entry_id: str) -> AuditEntry | None:
        """Get entry by ID."""
        ...

    @abstractmethod
    async def get_entry_by_index(self, index: int) -> AuditEntry | None:
        """Get entry by index."""
        ...

    @abstractmethod
    async def get_entries(
        self,
        start_index: int = 0,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Get range of entries."""
        ...

    @abstractmethod
    async def get_entry_count(self) -> int:
        """Get total entry count."""
        ...

    @abstractmethod
    async def save_tree_state(self, root_hash: str, size: int) -> None:
        """Save Merkle tree state."""
        ...

    @abstractmethod
    async def load_tree_state(self) -> tuple[str, int]:
        """Load Merkle tree state."""
        ...


class FilesystemAuditBackend(AuditBackendBase):
    """Filesystem audit log backend."""

    def __init__(self, base_path: str, max_entries_per_file: int = 10000) -> None:
        self.base_path = Path(base_path)
        self.max_entries_per_file = max_entries_per_file
        self.base_path.mkdir(parents=True, exist_ok=True)
        (self.base_path / "entries").mkdir(exist_ok=True)

        self._index: dict[str, int] = {}  # entry_id -> file_index
        self._count = 0
        self._load_index()

    def _load_index(self) -> None:
        """Load entry index from disk."""
        index_path = self.base_path / "index.json"
        if index_path.exists():
            data = json.loads(index_path.read_text())
            self._index = data.get("index", {})
            self._count = data.get("count", 0)

    def _save_index(self) -> None:
        """Save entry index to disk."""
        index_path = self.base_path / "index.json"
        data = {"index": self._index, "count": self._count}
        index_path.write_text(json.dumps(data))

    def _get_file_path(self, file_index: int) -> Path:
        """Get path for entry file."""
        return self.base_path / "entries" / f"entries_{file_index:06d}.jsonl"

    async def append_entry(self, entry: AuditEntry) -> None:
        """Append entry to log."""
        file_index = self._count // self.max_entries_per_file
        file_path = self._get_file_path(file_index)

        with file_path.open("a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

        self._index[entry.id] = self._count
        self._count += 1
        self._save_index()

    async def get_entry(self, entry_id: str) -> AuditEntry | None:
        """Get entry by ID."""
        if entry_id not in self._index:
            return None

        index = self._index[entry_id]
        return await self.get_entry_by_index(index)

    async def get_entry_by_index(self, index: int) -> AuditEntry | None:
        """Get entry by index."""
        if index < 0 or index >= self._count:
            return None

        file_index = index // self.max_entries_per_file
        line_index = index % self.max_entries_per_file

        file_path = self._get_file_path(file_index)
        if not file_path.exists():
            return None

        with file_path.open() as f:
            for i, line in enumerate(f):
                if i == line_index:
                    return AuditEntry.from_dict(json.loads(line))

        return None

    async def get_entries(
        self,
        start_index: int = 0,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Get range of entries."""
        entries = []

        for i in range(start_index, min(start_index + limit, self._count)):
            entry = await self.get_entry_by_index(i)
            if entry:
                entries.append(entry)

        return entries

    async def get_entry_count(self) -> int:
        """Get total entry count."""
        return self._count

    async def save_tree_state(self, root_hash: str, size: int) -> None:
        """Save Merkle tree state."""
        state_path = self.base_path / "tree_state.json"
        state_path.write_text(
            json.dumps(
                {
                    "root_hash": root_hash,
                    "size": size,
                    "timestamp": time.time(),
                }
            )
        )

    async def load_tree_state(self) -> tuple[str, int]:
        """Load Merkle tree state."""
        state_path = self.base_path / "tree_state.json"
        if not state_path.exists():
            return ("", 0)

        data = json.loads(state_path.read_text())
        return (data.get("root_hash", ""), data.get("size", 0))


class MemoryAuditBackend(AuditBackendBase):
    """In-memory audit log backend for testing."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._index: dict[str, int] = {}
        self._root_hash = ""
        self._tree_size = 0

    async def append_entry(self, entry: AuditEntry) -> None:
        """Append entry."""
        self._index[entry.id] = len(self._entries)
        self._entries.append(entry)

    async def get_entry(self, entry_id: str) -> AuditEntry | None:
        """Get entry by ID."""
        index = self._index.get(entry_id)
        if index is None:
            return None
        return self._entries[index]

    async def get_entry_by_index(self, index: int) -> AuditEntry | None:
        """Get entry by index."""
        if 0 <= index < len(self._entries):
            return self._entries[index]
        return None

    async def get_entries(
        self,
        start_index: int = 0,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Get range of entries."""
        return self._entries[start_index : start_index + limit]

    async def get_entry_count(self) -> int:
        """Get total entry count."""
        return len(self._entries)

    async def save_tree_state(self, root_hash: str, size: int) -> None:
        """Save tree state."""
        self._root_hash = root_hash
        self._tree_size = size

    async def load_tree_state(self) -> tuple[str, int]:
        """Load tree state."""
        return (self._root_hash, self._tree_size)


# =============================================================================
# Merkle Audit Log
# =============================================================================


class MerkleAuditLog:
    """Tamper-proof audit log with Merkle tree verification.

    Example:
        >>> config = AuditLogConfig()
        >>> log = MerkleAuditLog(config)
        >>> await log.initialize()
        >>>
        >>> # Append event
        >>> entry_id = await log.append(
        ...     event_type="user.login",
        ...     actor="user@example.com",
        ...     data={"ip": "192.168.1.1"},
        ... )
        >>>
        >>> # Verify entry
        >>> is_valid = await log.verify_entry(entry_id)
        >>>
        >>> # Get inclusion proof
        >>> proof = await log.get_inclusion_proof(entry_id)
        >>> assert MerkleTree.verify_inclusion(proof)
    """

    def __init__(self, config: AuditLogConfig | None = None) -> None:
        self.config = config or AuditLogConfig()
        self._backend: AuditBackendBase | None = None
        self._tree = MerkleTree()
        self._lock = asyncio.Lock()
        self._sync_task: asyncio.Task | None = None
        self._initialized = False
        self._pending_entries: list[AuditEntry] = []

    async def initialize(self) -> None:
        """Initialize the audit log."""
        if self._initialized:
            return

        # Initialize backend
        if self.config.backend == AuditBackend.FILESYSTEM:
            self._backend = FilesystemAuditBackend(
                self.config.storage_path,
                self.config.max_entries_per_file,
            )
        elif self.config.backend == AuditBackend.MEMORY:
            self._backend = MemoryAuditBackend()
        else:
            raise ValueError(f"Unsupported backend: {self.config.backend}")

        # Rebuild tree from existing entries
        await self._rebuild_tree()

        # Start sync task
        if self.config.sync_interval > 0:
            self._sync_task = asyncio.create_task(self._sync_loop())

        self._initialized = True
        logger.info(
            f"✅ MerkleAuditLog initialized ({self.config.backend.name}, {self._tree.size} entries)"
        )

    async def shutdown(self) -> None:
        """Shutdown the audit log."""
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        # Sync pending entries
        await self._sync_to_backend()

        self._initialized = False

    async def append(
        self,
        event_type: str,
        actor: str,
        resource: str = "",
        action: str = "",
        data: dict[str, Any] | None = None,
    ) -> str:
        """Append an event to the audit log.

        Args:
            event_type: Type of event.
            actor: Who performed the action.
            resource: Resource affected.
            action: Action performed.
            data: Additional event data.

        Returns:
            Entry ID (UUID).
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            # Get parent hash (previous entry)
            parent_hash = ""
            if self._tree.size > 0:
                count = await self._backend.get_entry_count()
                if count > 0:
                    prev_entry = await self._backend.get_entry_by_index(count - 1)
                    if prev_entry:
                        parent_hash = prev_entry.hash

            # Create entry
            entry = AuditEntry(
                id=str(uuid.uuid4()),
                timestamp=time.time(),
                event_type=event_type,
                actor=actor,
                resource=resource,
                action=action,
                data=data or {},
                parent_hash=parent_hash,
            )
            entry.hash = entry.compute_hash()

            # Add to tree
            self._tree.append(entry.hash)

            # Persist
            await self._backend.append_entry(entry)
            await self._backend.save_tree_state(
                self._tree.root_hash,
                self._tree.size,
            )

            logger.debug(f"Appended audit entry: {entry.id} ({event_type})")
            return entry.id

    async def verify_entry(self, entry_id: str) -> bool:
        """Verify an entry's integrity.

        Args:
            entry_id: Entry ID to verify.

        Returns:
            True if entry is valid and included in tree.
        """
        if not self._initialized:
            await self.initialize()

        entry = await self._backend.get_entry(entry_id)
        if not entry:
            return False

        # Verify entry hash
        computed_hash = entry.compute_hash()
        if computed_hash != entry.hash:
            logger.warning(f"Entry hash mismatch: {entry_id}")
            return False

        # Verify inclusion in tree
        index = await self._get_entry_index(entry_id)
        if index is None:
            return False

        proof = self._tree.get_inclusion_proof(index)
        return MerkleTree.verify_inclusion(proof)

    async def get_inclusion_proof(self, entry_id: str) -> InclusionProof | None:
        """Get inclusion proof for an entry.

        Args:
            entry_id: Entry ID.

        Returns:
            Inclusion proof or None if not found.
        """
        if not self._initialized:
            await self.initialize()

        index = await self._get_entry_index(entry_id)
        if index is None:
            return None

        return self._tree.get_inclusion_proof(index)

    async def get_entry(self, entry_id: str) -> AuditEntry | None:
        """Get an entry by ID.

        Args:
            entry_id: Entry ID.

        Returns:
            Audit entry or None.
        """
        if not self._initialized:
            await self.initialize()

        return await self._backend.get_entry(entry_id)

    async def get_entries(
        self,
        start_index: int = 0,
        limit: int = 100,
        event_type: str | None = None,
        actor: str | None = None,
    ) -> list[AuditEntry]:
        """Get range of entries with optional filtering.

        Args:
            start_index: Starting index.
            limit: Maximum entries to return.
            event_type: Filter by event type.
            actor: Filter by actor.

        Returns:
            List of audit entries.
        """
        if not self._initialized:
            await self.initialize()

        entries = await self._backend.get_entries(start_index, limit)

        # Apply filters
        if event_type:
            entries = [e for e in entries if e.event_type == event_type]
        if actor:
            entries = [e for e in entries if e.actor == actor]

        return entries

    async def verify_chain(self) -> tuple[bool, list[str]]:
        """Verify the entire audit log chain.

        Returns:
            Tuple of (is_valid, list of invalid entry IDs).
        """
        if not self._initialized:
            await self.initialize()

        invalid_entries = []
        count = await self._backend.get_entry_count()

        prev_hash = ""
        for i in range(count):
            entry = await self._backend.get_entry_by_index(i)
            if not entry:
                continue

            # Verify parent hash chain
            if entry.parent_hash != prev_hash:
                invalid_entries.append(entry.id)
                logger.warning(f"Chain broken at entry {i}: {entry.id}")

            # Verify entry hash
            computed = entry.compute_hash()
            if computed != entry.hash:
                invalid_entries.append(entry.id)
                logger.warning(f"Hash mismatch at entry {i}: {entry.id}")

            prev_hash = entry.hash

        return (len(invalid_entries) == 0, invalid_entries)

    @property
    def root_hash(self) -> str:
        """Get current Merkle root hash."""
        return self._tree.root_hash

    @property
    def size(self) -> int:
        """Get number of entries."""
        return self._tree.size

    async def get_stats(self) -> dict[str, Any]:
        """Get audit log statistics.

        Returns:
            Statistics dictionary.
        """
        if not self._initialized:
            await self.initialize()

        return {
            "entry_count": self._tree.size,
            "root_hash": self._tree.root_hash,
            "backend": self.config.backend.name,
            "storage_path": self.config.storage_path,
        }

    # =========================================================================
    # Private Methods
    # =========================================================================

    async def _rebuild_tree(self) -> None:
        """Rebuild Merkle tree from stored entries."""
        count = await self._backend.get_entry_count()

        for i in range(count):
            entry = await self._backend.get_entry_by_index(i)
            if entry:
                self._tree.append(entry.hash)

        logger.debug(f"Rebuilt Merkle tree with {count} entries")

    async def _get_entry_index(self, entry_id: str) -> int | None:
        """Get index of entry by ID."""
        count = await self._backend.get_entry_count()

        for i in range(count):
            entry = await self._backend.get_entry_by_index(i)
            if entry and entry.id == entry_id:
                return i

        return None

    async def _sync_loop(self) -> None:
        """Background sync loop."""
        while True:
            try:
                await asyncio.sleep(self.config.sync_interval)
                await self._sync_to_backend()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync error: {e}")

    async def _sync_to_backend(self) -> None:
        """Sync pending entries to backend."""
        if self._pending_entries:
            async with self._lock:
                for entry in self._pending_entries:
                    await self._backend.append_entry(entry)
                self._pending_entries.clear()

                await self._backend.save_tree_state(
                    self._tree.root_hash,
                    self._tree.size,
                )


# =============================================================================
# Factory Functions
# =============================================================================


_audit_log: MerkleAuditLog | None = None


async def get_audit_log(config: AuditLogConfig | None = None) -> MerkleAuditLog:
    """Get or create the singleton audit log.

    Args:
        config: Audit log configuration.

    Returns:
        MerkleAuditLog instance.

    Example:
        >>> log = await get_audit_log()
        >>> await log.append(event_type="test", actor="system")
    """
    global _audit_log

    if _audit_log is None:
        _audit_log = MerkleAuditLog(config)
        await _audit_log.initialize()

    return _audit_log


async def shutdown_audit_log() -> None:
    """Shutdown the audit log."""
    global _audit_log

    if _audit_log:
        await _audit_log.shutdown()
        _audit_log = None


__all__ = [
    "AuditBackend",
    "AuditBackendBase",
    "AuditEntry",
    "AuditLogConfig",
    "AuditLogIntegrityError",
    "FilesystemAuditBackend",
    "InclusionProof",
    "MemoryAuditBackend",
    "MerkleAuditLog",
    "MerkleNode",
    "MerkleTree",
    "get_audit_log",
    "shutdown_audit_log",
]
