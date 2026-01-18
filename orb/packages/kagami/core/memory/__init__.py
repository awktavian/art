"""Memory subsystem for K OS.

Multi-level memory system:
- HierarchicalMemory: Working → Short-Term → Long-Term → Semantic
- Prioritized replay for experience replay
- Spaced repetition for knowledge retention
- Consolidation for automatic compression
- Memory pressure management and prediction

Created: K OS Core
Updated: December 2025 - Consolidated memory management
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

from kagami.core.memory.hierarchical_memory import (
    CompressedEpisode,
    HierarchicalMemory,
    LongTermPattern,
    get_hierarchical_memory,
)
from kagami.core.memory.integration import MemoryHub, get_memory_hub, reset_memory_hub
from kagami.core.memory.interface import (
    InMemoryBackend,
    MemoryBackend,
    MemoryEntry,
    MemoryType,
    UnifiedMemoryInterface,
    get_memory_interface,
)
from kagami.core.memory.manager import ModelMemoryManager
from kagami.core.memory.pressure_coordinator import (
    MemoryConsumer,
    MemoryPressureCoordinator,
    MemoryPressureLevel,
)
from kagami.core.memory.pressure_predictor import (
    MemoryPressureForecast,
    MemoryPressurePredictor,
)
from kagami.core.memory.types import (
    Experience,
    MemorySnapshot,
    ReplayConfig,
)

logger = logging.getLogger(__name__)

# In-memory store for transient memories
_MEMORY_STORE: list[dict[str, Any]] = []


async def remember(
    content: str,
    *,
    metadata: dict[str, Any] | None = None,
    importance: float = 0.5,
    tags: list[str] | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Store a memory with optional metadata.

    Simple memory storage interface that integrates with hierarchical memory.

    Args:
        content: The content to remember
        metadata: Optional metadata to attach
        importance: Importance score (0.0 - 1.0)
        tags: Optional tags for categorization
        correlation_id: Optional correlation ID for receipt tracking

    Returns:
        Memory entry with generated ID and timestamp
    """
    memory_id = str(uuid.uuid4())
    timestamp = time.time()

    entry = {
        "id": memory_id,
        "content": content,
        "metadata": metadata or {},
        "importance": max(0.0, min(1.0, importance)),
        "tags": tags or [],
        "timestamp": timestamp,
        "correlation_id": correlation_id,
    }

    _MEMORY_STORE.append(entry)

    # Persist to hierarchical memory if available
    try:
        mem = get_hierarchical_memory()
        if mem:
            base_meta = entry.get("metadata")
            base_meta_dict: dict[str, Any] = base_meta if isinstance(base_meta, dict) else {}
            experience: dict[str, Any] = {
                "content": content,
                "timestamp": timestamp,
                "valence": float(importance),
                "metadata": {
                    **base_meta_dict,
                    "memory_id": memory_id,
                    "importance": float(importance),
                    "tags": tags or [],
                    "correlation_id": correlation_id,
                },
            }
            await mem.store(experience)
            logger.debug(f"Stored memory {memory_id} in hierarchical memory")
    except Exception as e:
        logger.debug(f"Hierarchical memory unavailable: {e}")

    # Emit receipt for mutation tracking
    if correlation_id:
        try:
            from kagami.core.receipts import emit_receipt

            emit_receipt(
                correlation_id=correlation_id,
                action="memory.store",
                app="memory",
                args={"memory_id": memory_id},
                event_name="EXECUTE",
                event_data={"phase": "execute", "memory_id": memory_id},
            )
        except Exception:
            pass

    return entry


async def recall(
    query: str,
    *,
    k: int = 10,
    tags: list[str] | None = None,
    min_importance: float = 0.0,
) -> list[dict[str, Any]]:
    """Recall memories matching the query.

    Args:
        query: Search query (substring match)
        k: Maximum number of results
        tags: Optional tag filter
        min_importance: Minimum importance threshold

    Returns:
        List of matching memory entries
    """
    results = []

    for entry in _MEMORY_STORE:
        if entry.get("importance", 0) < min_importance:
            continue
        if tags:
            entry_tags = set(entry.get("tags", []))
            if not entry_tags.intersection(tags):
                continue
        if query.lower() in entry.get("content", "").lower():
            results.append(entry)

    results.sort(key=lambda x: (-x.get("importance", 0), -x.get("timestamp", 0)))
    return results[:k]


def clear_memory_store() -> int:
    """Clear the in-memory store (for testing)."""
    global _MEMORY_STORE
    count = len(_MEMORY_STORE)
    _MEMORY_STORE = []
    return count


class SemanticStore:
    """Simple file-based semantic store for testing/memory.

    Uses lazy loading to avoid blocking I/O during initialization.
    File is loaded on first access (upsert or search).
    """

    def __init__(self, path: Path) -> None:
        from pathlib import Path

        self.path = Path(path)
        self._data: list[dict[str, Any]] | None = None

    def _ensure_loaded(self) -> None:
        """Lazy load data from disk on first access."""
        if self._data is not None:
            return

        import json

        self._data = []
        if self.path.exists():
            try:
                with open(self.path) as f:
                    self._data = json.load(f)
            except Exception:
                pass

    @property
    def data(self) -> list[dict[str, Any]]:
        """Access data with lazy loading."""
        self._ensure_loaded()
        assert self._data is not None
        return self._data

    def upsert(self, text: str, metadata: dict[str, Any]) -> None:
        import json

        self._ensure_loaded()
        assert self._data is not None
        self._data.append({"text": text, "metadata": metadata})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f)

    def search(self, query: str, k: int = 10) -> list[dict[str, Any]]:
        self._ensure_loaded()
        assert self._data is not None
        results = [item for item in self._data if query in item["text"]]
        return results[:k]


__all__ = [
    "CompressedEpisode",
    # Types
    "Experience",
    # Hierarchical Memory
    "HierarchicalMemory",
    # Unified Interface (December 31, 2025)
    "InMemoryBackend",
    "LongTermPattern",
    "MemoryBackend",
    "MemoryConsumer",
    "MemoryEntry",
    # Integration
    "MemoryHub",
    "MemoryPressureCoordinator",
    "MemoryPressureForecast",
    # Pressure Management
    "MemoryPressureLevel",
    "MemoryPressurePredictor",
    "MemorySnapshot",
    "MemoryType",
    # Manager
    "ModelMemoryManager",
    "ReplayConfig",
    "SemanticStore",
    "UnifiedMemoryInterface",
    "clear_memory_store",
    "get_hierarchical_memory",
    "get_memory_hub",
    "get_memory_interface",
    "recall",
    # Convenience functions (migrated from legacy kagami.memory)
    "remember",
    "reset_memory_hub",
]
