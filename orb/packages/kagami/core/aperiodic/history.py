from __future__ import annotations

"""Thought History Tracker — Rolling window for novelty detection WITH cleanup.

Maintains recent thought history to detect repetition and enforce diversity.
Uses rolling buffer with configurable window size (default 100 thoughts ≈ 1 hour).

NOW INTEGRATED WITH HYPERDIMENSIONAL MEMORY:
- Stores FULL 384D embeddings (no compression)
- Uses 4D manifold for fast navigation
- Backward compatible API
- Automatic cleanup prevents unbounded growth
"""
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np

from kagami.core.infra.singleton_cleanup_mixin import SingletonCleanupMixin

logger = logging.getLogger(__name__)


@dataclass
class ThoughtRecord:
    """Single thought with metadata."""

    content: str  # The thought/response text
    embedding: list[float] | None  # Cached embedding
    timestamp: float  # When generated
    correlation_id: str | None  # Receipt correlation
    metadata: dict[str, Any] | None = None


class ThoughtHistory(SingletonCleanupMixin):
    """Thread-safe rolling buffer of recent thoughts WITH automatic cleanup.

    Maintains fixed-size window of recent thoughts for novelty detection.
    Automatically evicts oldest when buffer full.

    NOW USES HYPERDIMENSIONAL MEMORY:
    - Stores full 384D embeddings (no compression)
    - Fast navigation via 4D manifold indexing
    - Backward compatible API
    - Automatic cleanup prevents unbounded growth

    Example:
        history = ThoughtHistory(window_size=100)
        history.add("First thought", embedding=[0.1, 0.2, ...])
        recent = history.get_recent(n=10)
    """

    def __init__(self, window_size: int = 100, use_hyperdimensional: bool = True) -> None:
        """Initialize thought history.

        Args:
            window_size: Maximum number of thoughts to retain (default 100)
            use_hyperdimensional: Use hyperdimensional memory backend (default True)
        """
        self.window_size = window_size
        self.use_hyperdimensional = use_hyperdimensional

        # Legacy buffer (for backward compatibility)
        self._buffer: deque[ThoughtRecord] = deque(maxlen=window_size)
        self._lock = threading.RLock()

        # Hyperdimensional memory backend
        if use_hyperdimensional:
            try:
                from kagami.core.hyperdimensional_memory import (
                    get_hyperdimensional_memory,
                )

                self._hyperdim = get_hyperdimensional_memory()
                logger.info("ThoughtHistory using hyperdimensional memory backend")
            except Exception as e:
                logger.warning(
                    f"Failed to initialize hyperdimensional memory: {e}, falling back to buffer"
                )
                self._hyperdim: Any | None = None  # type: ignore[assignment, no-redef]
        else:
            self._hyperdim: Any | None = None  # type: ignore[assignment, no-redef]

        # Configure cleanup
        self._cleanup_interval = 1800.0  # 30 minutes
        self._register_cleanup_on_exit()

    def add(
        self,
        content: str,
        embedding: list[float] | None = None,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add thought to history.

        Args:
            content: The thought text
            embedding: Optional pre-computed embedding (list[Any] or ndarray[Any, Any])
            correlation_id: Optional receipt correlation ID
            metadata: Optional additional metadata
        """
        with self._lock:
            # Legacy buffer
            record = ThoughtRecord(
                content=content,
                embedding=embedding,
                timestamp=time.time(),
                correlation_id=correlation_id,
                metadata=metadata or {},
            )
            self._buffer.append(record)

            # Hyperdimensional memory (stores full 384D)
            if self._hyperdim and correlation_id:
                try:
                    self._hyperdim.add(
                        content=content,
                        correlation_id=correlation_id,
                        metadata=metadata,
                    )
                except Exception as e:
                    logger.debug(f"Hyperdimensional memory add failed: {e}")

            # Emit metric

    def get_recent(self, n: int | None = None) -> list[ThoughtRecord]:
        """Get N most recent thoughts (newest first).

        Args:
            n: Number of thoughts to retrieve (None = all)

        Returns:
            List of recent thoughts, newest first
        """
        with self._lock:
            if n is None:
                return list(reversed(self._buffer))
            return list(reversed(list(self._buffer)[-n:]))

    def get_embeddings(self, n: int | None = None) -> list[list[float] | np.ndarray[Any, Any]]:
        """Get embeddings of N most recent thoughts.

        NOW RETURNS FULL 384D EMBEDDINGS from hyperdimensional memory when available.

        Args:
            n: Number of thoughts (None = all)

        Returns:
            List of embeddings (non-None only), FULL 384D when available
        """
        # Try hyperdimensional memory first (has full 384D)
        if self._hyperdim:
            try:
                recent_thoughts = self._hyperdim.get_recent(n or self.window_size)
                embeddings = [t.embedding_384d for t in recent_thoughts]
                if embeddings:
                    return embeddings  # type: ignore[return-value]
            except Exception as e:
                logger.debug(f"Hyperdimensional embeddings failed: {e}, falling back")

        # Fallback to legacy buffer
        recent = self.get_recent(n)
        return [r.embedding for r in recent if r.embedding is not None]

    def count(self) -> int:
        """Alias for size() (for hyperdimensional compatibility)."""
        return self.size()

    def size(self) -> int:
        """Current buffer size."""
        with self._lock:
            return len(self._buffer)

    def clear(self) -> None:
        """Clear all history (for testing)."""
        with self._lock:
            self._buffer.clear()
            if self._hyperdim:
                try:
                    self._hyperdim.clear()
                except Exception as e:
                    logger.debug(f"Hyperdimensional clear failed: {e}")
            logger.info("Thought history cleared")

    def _cleanup_internal_state(self) -> dict[str, int]:
        """Clean up buffer (implements SingletonCleanupMixin)."""
        # Buffer is already bounded by deque[Any] maxlen, but enforce for safety
        with self._lock:
            current_size = len(self._buffer)
            # Deque automatically evicts, so just report status
            return {
                "buffer_size": current_size,
                "buffer_capacity": self.window_size,
                "hyperdim_enabled": self._hyperdim is not None,
            }


# Global singleton
_global_history: ThoughtHistory | None = None
_history_lock = threading.Lock()


def get_thought_history(window_size: int = 100) -> ThoughtHistory:
    """Get or create global thought history singleton.

    Args:
        window_size: Buffer size (only used on first call)

    Returns:
        Global ThoughtHistory instance
    """
    global _global_history

    if _global_history is None:
        with _history_lock:
            if _global_history is None:
                _global_history = ThoughtHistory(window_size=window_size)
                logger.info(f"Initialized global thought history (window={window_size})")

    return _global_history
