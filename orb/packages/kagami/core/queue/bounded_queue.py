"""Bounded queue with backpressure and overflow handling.

P0 Mitigation: Unbounded queue growth → OOM → Crash
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class OverflowPolicy(Enum):
    """Policy for handling queue overflow."""

    DROP_OLDEST = "drop_oldest"  # Remove oldest item
    DROP_NEWEST = "drop_newest"  # Don't add new item
    BLOCK = "block"  # Wait for space (default asyncio behavior)


class BoundedQueue(Generic[T]):
    """Bounded queue with configurable overflow handling.

    P0 Mitigation: Prevents unbounded queue growth → OOM

    Features:
    - Hard size limit
    - Configurable overflow policy
    - Backpressure signals when approaching capacity
    - Metrics (size, drops, throughput)

    Usage:
        queue = BoundedQueue(
            maxsize=10000,
            overflow_policy=OverflowPolicy.DROP_OLDEST,
            backpressure_threshold=0.8,  # Signal at 80% full
        )

        # Put item (non-blocking with overflow handling)
        dropped = await queue.put_nowait_with_overflow(item)

        # Check if backpressure needed
        if queue.should_apply_backpressure():
            await send_backpressure_signal()
    """

    def __init__(
        self,
        maxsize: int,
        overflow_policy: OverflowPolicy = OverflowPolicy.DROP_OLDEST,
        backpressure_threshold: float = 0.8,
        name: str = "queue",
    ):
        """Initialize bounded queue.

        Args:
            maxsize: Maximum queue size
            overflow_policy: How to handle overflow
            backpressure_threshold: Trigger backpressure at this utilization (0.0-1.0)
            name: Queue name for logging
        """
        self.maxsize = maxsize
        self.overflow_policy = overflow_policy
        self.backpressure_threshold = backpressure_threshold
        self.name = name

        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)
        self._dropped_count = 0
        self._total_added = 0

    async def put(self, item: T, timeout: float | None = None) -> None:
        """Put item in queue (blocks if full).

        Args:
            item: Item to add
            timeout: Max seconds to wait (None = wait forever)

        Raises:
            asyncio.TimeoutError: If timeout exceeded
        """
        if timeout:
            await asyncio.wait_for(self._queue.put(item), timeout=timeout)
        else:
            await self._queue.put(item)

        self._total_added += 1

    async def put_nowait_with_overflow(self, item: T) -> bool:
        """Put item in queue, applying overflow policy if full.

        Args:
            item: Item to add

        Returns:
            True if item was dropped
        """
        try:
            self._queue.put_nowait(item)
            self._total_added += 1
            return False

        except asyncio.QueueFull:
            # Apply overflow policy
            if self.overflow_policy == OverflowPolicy.DROP_OLDEST:
                # Remove oldest item
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(item)
                    self._dropped_count += 1
                    self._total_added += 1

                    logger.warning(
                        f"Queue {self.name} full: dropped oldest item "
                        f"(total dropped: {self._dropped_count})"
                    )
                    return True
                except Exception:
                    pass

            elif self.overflow_policy == OverflowPolicy.DROP_NEWEST:
                # Don't add new item
                self._dropped_count += 1
                logger.warning(
                    f"Queue {self.name} full: dropped newest item "
                    f"(total dropped: {self._dropped_count})"
                )
                return True

            # BLOCK policy would raise QueueFull
            raise

    async def get(self, timeout: float | None = None) -> T:
        """Get item from queue.

        Args:
            timeout: Max seconds to wait (None = wait forever)

        Returns:
            Item from queue

        Raises:
            asyncio.TimeoutError: If timeout exceeded
        """
        if timeout:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        else:
            return await self._queue.get()

    def get_nowait(self) -> T:
        """Get item from queue (non-blocking).

        Raises:
            asyncio.QueueEmpty: If queue empty
        """
        return self._queue.get_nowait()

    def should_apply_backpressure(self) -> bool:
        """Check if backpressure should be applied.

        Returns:
            True if queue utilization above threshold
        """
        utilization = self.qsize() / self.maxsize
        return utilization >= self.backpressure_threshold

    def qsize(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()

    def full(self) -> bool:
        """Check if queue is full."""
        return self._queue.full()

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        current_size = self.qsize()
        utilization = current_size / self.maxsize if self.maxsize > 0 else 0

        return {
            "name": self.name,
            "current_size": current_size,
            "maxsize": self.maxsize,
            "utilization": utilization,
            "dropped_count": self._dropped_count,
            "total_added": self._total_added,
            "drop_rate": (self._dropped_count / self._total_added if self._total_added > 0 else 0),
            "overflow_policy": self.overflow_policy.value,
            "should_apply_backpressure": self.should_apply_backpressure(),
        }


class QueueManager:
    """Manages multiple bounded queues."""

    def __init__(self):
        self._queues: dict[str, BoundedQueue] = {}

    def create_queue(
        self,
        name: str,
        maxsize: int,
        overflow_policy: OverflowPolicy = OverflowPolicy.DROP_OLDEST,
    ) -> BoundedQueue:
        """Create and register a bounded queue.

        Args:
            name: Queue identifier
            maxsize: Maximum size
            overflow_policy: Overflow handling strategy

        Returns:
            Bounded queue instance
        """
        queue = BoundedQueue(
            maxsize=maxsize,
            overflow_policy=overflow_policy,
            name=name,
        )
        self._queues[name] = queue
        return queue

    def get_queue(self, name: str) -> BoundedQueue | None:
        """Get queue by name."""
        return self._queues.get(name)

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all queues."""
        return {name: queue.get_stats() for name, queue in self._queues.items()}


# Global manager
_global_manager: QueueManager | None = None


def get_queue_manager() -> QueueManager:
    """Get global queue manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = QueueManager()
    return _global_manager
