"""Unified Memory Interface — Single API for All Memory Operations.

Provides a unified interface to episodic, semantic, and procedural memory,
hiding the complexity of multiple memory systems behind a clean API.

Architecture:
```
                UnifiedMemoryInterface
                        │
        ┌───────────────┼───────────────┐
        ↓               ↓               ↓
   EpisodicMemory  SemanticMemory  ProceduralMemory
   (experiences)   (knowledge)     (skills/patterns)
```

Colony: Nexus (e4) — Connections & Integration
Created: December 31, 2025
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)


# =============================================================================
# TYPE DEFINITIONS
# =============================================================================


class MemoryType(Enum):
    """Types of memory in the unified system."""

    EPISODIC = "episodic"  # Specific experiences with context
    SEMANTIC = "semantic"  # General knowledge and facts
    PROCEDURAL = "procedural"  # Skills and learned patterns


@dataclass
class MemoryEntry:
    """A single memory entry."""

    entry_id: str
    content: Any
    memory_type: MemoryType
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    importance: float = 0.5  # 0-1, affects consolidation
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryQuery:
    """Query for memory retrieval."""

    query: str | None = None  # Semantic search query
    memory_type: MemoryType | None = None  # Filter by type
    tags: list[str] | None = None  # Filter by tags
    min_importance: float = 0.0
    max_results: int = 10
    time_range: tuple[datetime, datetime] | None = None


@dataclass
class MemoryResult:
    """Result from memory query."""

    entries: list[MemoryEntry]
    total_count: int
    query_time_ms: float


@dataclass
class ConsolidationResult:
    """Result of memory consolidation."""

    memories_processed: int
    memories_consolidated: int
    memories_pruned: int
    duration_ms: float
    next_consolidation: datetime


# =============================================================================
# MEMORY BACKEND INTERFACE
# =============================================================================


T = TypeVar("T")


class MemoryBackend(ABC, Generic[T]):
    """Abstract base class for memory backends."""

    @abstractmethod
    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry, return ID."""
        pass

    @abstractmethod
    async def retrieve(self, id: str) -> MemoryEntry | None:
        """Retrieve a memory by ID."""
        pass

    @abstractmethod
    async def query(self, query: MemoryQuery) -> MemoryResult:
        """Query memories."""
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete a memory by ID."""
        pass

    @abstractmethod
    async def consolidate(self) -> ConsolidationResult:
        """Run memory consolidation."""
        pass


# =============================================================================
# IN-MEMORY BACKEND (Default)
# =============================================================================


class InMemoryBackend(MemoryBackend[MemoryEntry]):
    """Simple in-memory backend for development/testing."""

    def __init__(self) -> None:
        self._memories: dict[str, MemoryEntry] = {}
        self._counter = 0

    async def store(self, entry: MemoryEntry) -> str:
        if not entry.entry_id:
            self._counter += 1
            entry.entry_id = f"mem_{self._counter}"
        self._memories[entry.entry_id] = entry
        return entry.entry_id

    async def retrieve(self, entry_id: str) -> MemoryEntry | None:
        entry = self._memories.get(entry_id)
        if entry:
            entry.access_count += 1
            entry.last_accessed = datetime.now()
        return entry

    async def query(self, query: MemoryQuery) -> MemoryResult:
        """Query memories with optimized single-pass filtering.

        PERFORMANCE FIX (Jan 2026): Consolidated multiple list comprehensions
        into a single pass to reduce O(n*k) to O(n) complexity.
        """
        import time

        start = time.time()

        # OPTIMIZATION: Single-pass filter instead of multiple list comprehensions
        # Pre-extract query parameters to avoid repeated attribute access
        query_type = query.memory_type
        query_tags = set(query.tags) if query.tags else None
        min_importance = query.min_importance
        time_range = query.time_range
        start_time, end_time = time_range if time_range else (None, None)

        # Single-pass filter
        results = []
        for m in self._memories.values():
            # Check type filter
            if query_type and m.memory_type != query_type:
                continue
            # Check importance filter
            if m.importance < min_importance:
                continue
            # Check tags filter (any match)
            if query_tags and not query_tags.intersection(m.tags):
                continue
            # Check time range filter
            if start_time and end_time:
                if not (start_time <= m.created_at <= end_time):
                    continue
            results.append(m)

        total_count = len(results)

        # Sort by importance and recency
        results.sort(key=lambda m: (m.importance, m.last_accessed), reverse=True)

        # Limit results
        limited = results[: query.max_results]

        return MemoryResult(
            entries=limited,
            total_count=total_count,
            query_time_ms=(time.time() - start) * 1000,
        )

    async def delete(self, entry_id: str) -> bool:
        if entry_id in self._memories:
            del self._memories[entry_id]
            return True
        return False

    async def consolidate(self) -> ConsolidationResult:
        """Simple consolidation: prune low-importance, old memories."""
        import time

        start = time.time()

        # Find memories to prune
        now = datetime.now()
        to_prune = []
        for id, mem in self._memories.items():
            age_days = (now - mem.created_at).days
            # Prune if: low importance + old + rarely accessed
            if mem.importance < 0.3 and age_days > 30 and mem.access_count < 3:
                to_prune.append(id)

        for id in to_prune:
            del self._memories[id]

        return ConsolidationResult(
            memories_processed=len(self._memories),
            memories_consolidated=0,  # No consolidation in simple backend
            memories_pruned=len(to_prune),
            duration_ms=(time.time() - start) * 1000,
            next_consolidation=datetime.now(),
        )


# =============================================================================
# UNIFIED MEMORY INTERFACE
# =============================================================================


class UnifiedMemoryInterface:
    """Unified interface to all memory systems.

    Usage:
        memory = UnifiedMemoryInterface()

        # Store episodic memory
        await memory.remember(
            "User activated movie mode",
            memory_type=MemoryType.EPISODIC,
            tags=["scene", "movie"],
        )

        # Store procedural memory (pattern)
        await memory.learn_pattern(
            "friday_movie",
            {"time": "20:00", "day": "friday", "scene": "movie_mode"},
            confidence=0.85,
        )

        # Query
        results = await memory.recall("movie mode activation")

        # Consolidate (during "sleep")
        await memory.consolidate()
    """

    def __init__(self, backend: MemoryBackend | None = None) -> None:
        self._backend = backend or InMemoryBackend()
        self._consolidation_scheduled = False

    # -------------------------------------------------------------------------
    # High-Level API
    # -------------------------------------------------------------------------

    async def remember(
        self,
        content: Any,
        *,
        memory_type: MemoryType = MemoryType.EPISODIC,
        importance: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store a new memory.

        Args:
            content: The memory content
            memory_type: Type of memory (episodic, semantic, procedural)
            importance: 0-1, higher = more likely to be retained
            tags: Tags for categorization
            metadata: Additional metadata

        Returns:
            Memory ID
        """
        now = datetime.now()
        entry = MemoryEntry(
            id="",  # Will be assigned by backend
            content=content,
            memory_type=memory_type,
            created_at=now,
            last_accessed=now,
            access_count=0,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
        )
        return await self._backend.store(entry)

    async def recall(
        self,
        query: str | None = None,
        *,
        memory_type: MemoryType | None = None,
        tags: list[str] | None = None,
        max_results: int = 10,
    ) -> list[MemoryEntry]:
        """Recall memories matching query.

        Args:
            query: Semantic search query (optional)
            memory_type: Filter by type
            tags: Filter by tags
            max_results: Maximum results to return

        Returns:
            List of matching memory entries
        """
        q = MemoryQuery(
            query=query,
            memory_type=memory_type,
            tags=tags,
            max_results=max_results,
        )
        result = await self._backend.query(q)
        return result.entries

    async def forget(self, memory_id: str) -> bool:
        """Forget (delete) a specific memory.

        Args:
            memory_id: ID of memory to forget

        Returns:
            True if memory was deleted
        """
        return await self._backend.delete(memory_id)

    # -------------------------------------------------------------------------
    # Pattern-Specific API
    # -------------------------------------------------------------------------

    async def learn_pattern(
        self,
        pattern_id: str,
        pattern_data: dict[str, Any],
        *,
        confidence: float = 0.5,
        observations: int = 1,
    ) -> str:
        """Learn a new behavioral pattern.

        Args:
            pattern_id: Unique identifier for the pattern
            pattern_data: Pattern details (triggers, actions, etc.)
            confidence: How confident we are in this pattern
            observations: Number of times observed

        Returns:
            Memory ID
        """
        return await self.remember(
            pattern_data,
            memory_type=MemoryType.PROCEDURAL,
            importance=confidence,
            tags=["pattern", pattern_id],
            metadata={
                "pattern_id": pattern_id,
                "confidence": confidence,
                "observations": observations,
            },
        )

    async def get_patterns(
        self,
        min_confidence: float = 0.0,
        max_results: int = 50,
    ) -> list[MemoryEntry]:
        """Get learned patterns.

        Args:
            min_confidence: Minimum confidence threshold
            max_results: Maximum patterns to return

        Returns:
            List of pattern memories
        """
        return await self.recall(
            memory_type=MemoryType.PROCEDURAL,
            tags=["pattern"],
            max_results=max_results,
        )

    async def update_pattern_confidence(
        self,
        pattern_id: str,
        new_confidence: float,
    ) -> bool:
        """Update confidence in a learned pattern.

        Args:
            pattern_id: Pattern to update
            new_confidence: New confidence value

        Returns:
            True if updated
        """
        patterns = await self.recall(tags=[pattern_id])
        if patterns:
            pattern = patterns[0]
            pattern.importance = new_confidence
            pattern.metadata["confidence"] = new_confidence
            pattern.metadata["observations"] = pattern.metadata.get("observations", 1) + 1
            await self._backend.store(pattern)
            return True
        return False

    # -------------------------------------------------------------------------
    # Knowledge API
    # -------------------------------------------------------------------------

    async def store_knowledge(
        self,
        key: str,
        value: Any,
        *,
        tags: list[str] | None = None,
    ) -> str:
        """Store semantic knowledge.

        Args:
            key: Knowledge key
            value: Knowledge value
            tags: Additional tags

        Returns:
            Memory ID
        """
        return await self.remember(
            {"key": key, "value": value},
            memory_type=MemoryType.SEMANTIC,
            importance=0.7,  # Knowledge is generally important
            tags=["knowledge", key] + (tags or []),
        )

    async def get_knowledge(self, key: str) -> Any | None:
        """Retrieve semantic knowledge by key.

        Args:
            key: Knowledge key

        Returns:
            Knowledge value or None
        """
        results = await self.recall(
            memory_type=MemoryType.SEMANTIC,
            tags=["knowledge", key],
            max_results=1,
        )
        if results:
            return results[0].content.get("value")
        return None

    # -------------------------------------------------------------------------
    # Consolidation
    # -------------------------------------------------------------------------

    async def consolidate(self) -> ConsolidationResult:
        """Run memory consolidation.

        Should be called during idle periods ("sleep").
        Consolidates episodic → semantic, prunes low-importance memories.

        Returns:
            Consolidation statistics
        """
        logger.info("Starting memory consolidation...")
        result = await self._backend.consolidate()
        logger.info(
            f"Consolidation complete: {result.memories_consolidated} consolidated, "
            f"{result.memories_pruned} pruned"
        )
        return result

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    async def get_stats(self) -> dict[str, Any]:
        """Get memory system statistics."""
        episodic = await self._backend.query(
            MemoryQuery(memory_type=MemoryType.EPISODIC, max_results=0)
        )
        semantic = await self._backend.query(
            MemoryQuery(memory_type=MemoryType.SEMANTIC, max_results=0)
        )
        procedural = await self._backend.query(
            MemoryQuery(memory_type=MemoryType.PROCEDURAL, max_results=0)
        )

        return {
            "episodic_count": episodic.total_count,
            "semantic_count": semantic.total_count,
            "procedural_count": procedural.total_count,
            "total_count": episodic.total_count + semantic.total_count + procedural.total_count,
        }


# =============================================================================
# FACTORY
# =============================================================================

_default_memory: UnifiedMemoryInterface | None = None


def get_memory_interface() -> UnifiedMemoryInterface:
    """Get the default memory interface (singleton)."""
    global _default_memory
    if _default_memory is None:
        _default_memory = UnifiedMemoryInterface()
    return _default_memory


__all__ = [
    "ConsolidationResult",
    "MemoryBackend",
    "MemoryEntry",
    "MemoryQuery",
    "MemoryResult",
    "MemoryType",
    "UnifiedMemoryInterface",
    "get_memory_interface",
]
