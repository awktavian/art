"""Consensus Performance Optimization — Sub-100ms latency target.

This module implements performance optimizations for the distributed
consensus system, targeting sub-100ms latency for most operations.

Architecture:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CONSENSUS PERFORMANCE LAYER                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Optimization Strategies:                                               │
│   ────────────────────────                                               │
│   1. Connection Pooling      - Reuse etcd/Redis connections              │
│   2. Batched Operations      - Group multiple ops into single round-trip │
│   3. Speculative Execution   - Start work before consensus complete      │
│   4. Adaptive Timeouts       - Dynamic timeout based on network health   │
│   5. Local Caching           - Cache consensus results locally           │
│   6. Pipelining              - Pipeline PBFT phases                      │
│                                                                          │
│   Latency Targets:                                                       │
│   ────────────────                                                       │
│   • Read operations:     < 10ms  (local cache hit)                       │
│   • Write operations:    < 50ms  (single etcd round-trip)                │
│   • Colony consensus:    < 100ms (soft consensus)                        │
│   • PBFT consensus:      < 500ms (critical operations only)              │
│                                                                          │
│   Metrics:                                                               │
│   ─────────                                                              │
│   • P50, P95, P99 latencies per operation type                           │
│   • Operation throughput (ops/sec)                                       │
│   • Cache hit rate                                                       │
│   • Network round-trip times                                             │
│                                                                          │
│   Colony: Forge (A₃) — Performance engineering and optimization          │
│   h(x) ≥ 0. Always.                                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import functools
import logging
import statistics
import time
from collections import deque
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from kagami.core.caching.redis import RedisClientFactory

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Latency Targets
# =============================================================================


class OperationType(str, Enum):
    """Types of consensus operations with different latency targets."""

    LOCAL_READ = "local_read"  # < 1ms  (memory cache)
    REDIS_READ = "redis_read"  # < 10ms (Redis)
    ETCD_READ = "etcd_read"  # < 20ms (etcd)
    REDIS_WRITE = "redis_write"  # < 20ms (Redis)
    ETCD_WRITE = "etcd_write"  # < 50ms (etcd)
    COLONY_CONSENSUS = "colony_consensus"  # < 100ms
    PBFT_CONSENSUS = "pbft_consensus"  # < 500ms


LATENCY_TARGETS_MS: dict[OperationType, float] = {
    OperationType.LOCAL_READ: 1.0,
    OperationType.REDIS_READ: 10.0,
    OperationType.ETCD_READ: 20.0,
    OperationType.REDIS_WRITE: 20.0,
    OperationType.ETCD_WRITE: 50.0,
    OperationType.COLONY_CONSENSUS: 100.0,
    OperationType.PBFT_CONSENSUS: 500.0,
}


# =============================================================================
# Latency Tracking
# =============================================================================


@dataclass
class LatencyStats:
    """Statistics for operation latencies."""

    operation_type: OperationType
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0
    recent_latencies: deque = field(default_factory=lambda: deque(maxlen=100))
    slo_violations: int = 0

    @property
    def avg_ms(self) -> float:
        """Average latency in milliseconds."""
        return self.total_ms / self.count if self.count > 0 else 0.0

    @property
    def p50_ms(self) -> float:
        """50th percentile latency."""
        if not self.recent_latencies:
            return 0.0
        sorted_latencies = sorted(self.recent_latencies)
        return sorted_latencies[len(sorted_latencies) // 2]

    @property
    def p95_ms(self) -> float:
        """95th percentile latency."""
        if not self.recent_latencies:
            return 0.0
        sorted_latencies = sorted(self.recent_latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def p99_ms(self) -> float:
        """99th percentile latency."""
        if not self.recent_latencies:
            return 0.0
        sorted_latencies = sorted(self.recent_latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def slo_compliance_pct(self) -> float:
        """Percentage of operations meeting SLO."""
        if self.count == 0:
            return 100.0
        return ((self.count - self.slo_violations) / self.count) * 100

    def record(self, latency_ms: float) -> None:
        """Record a latency measurement.

        Args:
            latency_ms: Latency in milliseconds.
        """
        self.count += 1
        self.total_ms += latency_ms
        self.min_ms = min(self.min_ms, latency_ms)
        self.max_ms = max(self.max_ms, latency_ms)
        self.recent_latencies.append(latency_ms)

        # Check SLO
        target = LATENCY_TARGETS_MS.get(self.operation_type, 100.0)
        if latency_ms > target:
            self.slo_violations += 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "operation_type": self.operation_type.value,
            "count": self.count,
            "avg_ms": round(self.avg_ms, 2),
            "min_ms": round(self.min_ms, 2) if self.min_ms != float("inf") else None,
            "max_ms": round(self.max_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "slo_target_ms": LATENCY_TARGETS_MS.get(self.operation_type, 100.0),
            "slo_compliance_pct": round(self.slo_compliance_pct, 1),
            "slo_violations": self.slo_violations,
        }


class LatencyTracker:
    """Tracks latency metrics across operation types.

    Thread-safe latency tracking with automatic SLO monitoring.

    Example:
        >>> tracker = LatencyTracker()
        >>> async with tracker.measure(OperationType.REDIS_READ):
        ...     result = await redis.get("key")
        >>> print(tracker.get_stats(OperationType.REDIS_READ).p95_ms)
    """

    def __init__(self) -> None:
        self._stats: dict[OperationType, LatencyStats] = {
            op: LatencyStats(operation_type=op) for op in OperationType
        }
        self._lock = asyncio.Lock()

    class _LatencyContext:
        """Context manager for latency measurement."""

        def __init__(
            self,
            tracker: LatencyTracker,
            operation_type: OperationType,
        ) -> None:
            self.tracker = tracker
            self.operation_type = operation_type
            self.start_time: float = 0.0

        async def __aenter__(self) -> LatencyTracker._LatencyContext:
            self.start_time = time.perf_counter()
            return self

        async def __aexit__(self, *args: Any) -> None:
            latency_ms = (time.perf_counter() - self.start_time) * 1000
            async with self.tracker._lock:
                self.tracker._stats[self.operation_type].record(latency_ms)

    def measure(self, operation_type: OperationType) -> _LatencyContext:
        """Create context manager for measuring latency.

        Args:
            operation_type: Type of operation.

        Returns:
            Context manager.
        """
        return self._LatencyContext(self, operation_type)

    async def record(self, operation_type: OperationType, latency_ms: float) -> None:
        """Record a latency measurement directly.

        Args:
            operation_type: Type of operation.
            latency_ms: Latency in milliseconds.
        """
        async with self._lock:
            self._stats[operation_type].record(latency_ms)

    def get_stats(self, operation_type: OperationType) -> LatencyStats:
        """Get statistics for an operation type.

        Args:
            operation_type: Type of operation.

        Returns:
            LatencyStats for the operation.
        """
        return self._stats[operation_type]

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get all statistics.

        Returns:
            Dictionary of all operation stats.
        """
        return {op.value: self._stats[op].to_dict() for op in OperationType}

    def check_slo_compliance(self) -> dict[str, bool]:
        """Check SLO compliance for all operation types.

        Returns:
            Dictionary mapping operation type to compliance status.
        """
        return {op.value: self._stats[op].slo_compliance_pct >= 95.0 for op in OperationType}


# =============================================================================
# Local Cache
# =============================================================================


@dataclass
class CacheEntry:
    """Entry in the local consensus cache."""

    value: Any
    timestamp: float
    ttl_seconds: float

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() - self.timestamp > self.ttl_seconds


class LocalConsensusCache:
    """Local cache for consensus values.

    Provides sub-millisecond reads for frequently accessed consensus data.
    Uses configurable TTL to balance freshness vs performance.

    Example:
        >>> cache = LocalConsensusCache()
        >>> await cache.set("key", {"value": 42}, ttl=10.0)
        >>> result = await cache.get("key")
    """

    DEFAULT_TTL = 5.0  # seconds
    MAX_SIZE = 10000  # Maximum cache entries

    def __init__(self, default_ttl: float = DEFAULT_TTL) -> None:
        self._cache: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> tuple[Any | None, bool]:
        """Get value from cache.

        Args:
            key: Cache key.

        Returns:
            (value, hit) tuple.
        """
        async with self._lock:
            entry = self._cache.get(key)

            if entry is None or entry.is_expired:
                self._misses += 1
                if entry and entry.is_expired:
                    del self._cache[key]
                return None, False

            self._hits += 1
            return entry.value, True

    async def set(
        self,
        key: str,
        value: Any,
        ttl: float | None = None,
    ) -> None:
        """Set value in cache.

        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Time-to-live in seconds.
        """
        async with self._lock:
            # Evict if full
            if len(self._cache) >= self.MAX_SIZE:
                await self._evict_expired()

            self._cache[key] = CacheEntry(
                value=value,
                timestamp=time.time(),
                ttl_seconds=ttl or self._default_ttl,
            )

    async def invalidate(self, key: str) -> bool:
        """Invalidate a cache entry.

        Args:
            key: Cache key.

        Returns:
            True if key existed.
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all keys with a prefix.

        Args:
            prefix: Key prefix.

        Returns:
            Number of keys invalidated.
        """
        async with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)

    async def _evict_expired(self) -> int:
        """Evict expired entries.

        Returns:
            Number of entries evicted.
        """
        expired = [k for k, v in self._cache.items() if v.is_expired]
        for key in expired:
            del self._cache[key]
        return len(expired)

    @property
    def hit_rate(self) -> float:
        """Cache hit rate."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Statistics dictionary.
        """
        return {
            "size": len(self._cache),
            "max_size": self.MAX_SIZE,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate * 100, 1),
            "default_ttl": self._default_ttl,
        }


# =============================================================================
# Batched Operations
# =============================================================================


class BatchedWriter:
    """Batches write operations for efficiency.

    Collects writes and flushes them in batches to reduce round-trips.

    Example:
        >>> writer = BatchedWriter(redis)
        >>> await writer.write("key1", "value1")
        >>> await writer.write("key2", "value2")
        >>> await writer.flush()  # Single batch operation
    """

    DEFAULT_BATCH_SIZE = 50
    DEFAULT_FLUSH_INTERVAL = 0.1  # seconds

    def __init__(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
    ) -> None:
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._pending: list[tuple[str, Any]] = []
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._redis = RedisClientFactory.get_client()

    async def write(self, key: str, value: Any) -> None:
        """Add a write to the batch.

        Args:
            key: Redis key.
            value: Value to write.
        """
        async with self._lock:
            self._pending.append((key, value))

            # Flush if batch is full
            if len(self._pending) >= self._batch_size:
                await self._flush_internal()
            elif self._flush_task is None:
                # Start flush timer
                self._flush_task = asyncio.create_task(self._flush_timer())

    async def flush(self) -> int:
        """Flush pending writes.

        Returns:
            Number of writes flushed.
        """
        async with self._lock:
            return await self._flush_internal()

    async def _flush_internal(self) -> int:
        """Internal flush implementation."""
        if not self._pending:
            return 0

        count = len(self._pending)

        # Use pipeline for batch write
        try:
            pipe = self._redis.pipeline()
            for key, value in self._pending:
                if isinstance(value, (dict, list)):
                    import json

                    pipe.set(key, json.dumps(value))
                else:
                    pipe.set(key, value)
            await pipe.execute()

        except Exception as e:
            logger.error(f"Batch write failed: {e}")
            raise

        finally:
            self._pending.clear()
            if self._flush_task:
                self._flush_task.cancel()
                self._flush_task = None

        return count

    async def _flush_timer(self) -> None:
        """Timer task for automatic flushing."""
        try:
            await asyncio.sleep(self._flush_interval)
            await self.flush()
        except asyncio.CancelledError:
            pass


# =============================================================================
# Speculative Execution
# =============================================================================


async def speculative_execute(
    operation: Callable[[], Coroutine[Any, Any, T]],
    *,
    timeout: float = 0.1,
    rollback: Callable[[], Coroutine[Any, Any, None]] | None = None,
) -> tuple[T | None, bool]:
    """Execute operation speculatively with timeout.

    Starts operation immediately and waits for consensus.
    If consensus fails, rolls back.

    Args:
        operation: Async operation to execute.
        timeout: Maximum time to wait for consensus.
        rollback: Optional rollback operation.

    Returns:
        (result, succeeded) tuple.

    Example:
        >>> async def update_state():
        ...     await redis.set("key", "value")
        ...     return "value"
        >>> result, ok = await speculative_execute(update_state)
    """
    try:
        result = await asyncio.wait_for(operation(), timeout=timeout)
        return result, True
    except TimeoutError:
        if rollback:
            try:
                await rollback()
            except Exception as e:
                logger.error(f"Rollback failed: {e}")
        return None, False
    except Exception as e:
        logger.error(f"Speculative execution failed: {e}")
        if rollback:
            try:
                await rollback()
            except Exception as re:
                logger.error(f"Rollback failed: {re}")
        return None, False


# =============================================================================
# Adaptive Timeouts
# =============================================================================


class AdaptiveTimeout:
    """Dynamically adjusts timeout based on network performance.

    Uses exponential moving average of recent latencies to set timeout.

    Example:
        >>> timeout = AdaptiveTimeout(base_ms=50)
        >>> timeout.record_latency(45)
        >>> current = timeout.get_timeout()  # ~50ms
    """

    def __init__(
        self,
        base_ms: float = 50.0,
        min_ms: float = 10.0,
        max_ms: float = 1000.0,
        alpha: float = 0.1,
    ) -> None:
        self._base_ms = base_ms
        self._min_ms = min_ms
        self._max_ms = max_ms
        self._alpha = alpha  # EMA smoothing factor
        self._ema_ms = base_ms
        self._stddev_ms = base_ms * 0.2
        self._recent: deque = deque(maxlen=100)

    def record_latency(self, latency_ms: float) -> None:
        """Record a latency measurement.

        Args:
            latency_ms: Measured latency in ms.
        """
        self._recent.append(latency_ms)

        # Update EMA
        self._ema_ms = self._alpha * latency_ms + (1 - self._alpha) * self._ema_ms

        # Update stddev
        if len(self._recent) > 1:
            self._stddev_ms = statistics.stdev(self._recent)

    def get_timeout(self, safety_factor: float = 2.0) -> float:
        """Get current adaptive timeout.

        Args:
            safety_factor: Multiplier for safety margin.

        Returns:
            Timeout in milliseconds.
        """
        # Timeout = EMA + safety_factor * stddev
        timeout = self._ema_ms + safety_factor * self._stddev_ms
        return max(self._min_ms, min(self._max_ms, timeout))

    def get_timeout_seconds(self, safety_factor: float = 2.0) -> float:
        """Get timeout in seconds.

        Args:
            safety_factor: Multiplier for safety margin.

        Returns:
            Timeout in seconds.
        """
        return self.get_timeout(safety_factor) / 1000


# =============================================================================
# Performance Monitor
# =============================================================================


class ConsensusPerformanceMonitor:
    """Central performance monitor for consensus system.

    Aggregates latency tracking, caching, and adaptive timeouts.

    Example:
        >>> monitor = ConsensusPerformanceMonitor()
        >>> async with monitor.track(OperationType.REDIS_READ):
        ...     result = await redis.get("key")
        >>> print(monitor.get_dashboard())
    """

    def __init__(self) -> None:
        self.latency_tracker = LatencyTracker()
        self.local_cache = LocalConsensusCache()
        self._adaptive_timeouts: dict[OperationType, AdaptiveTimeout] = {
            op: AdaptiveTimeout(base_ms=target) for op, target in LATENCY_TARGETS_MS.items()
        }

    def track(self, operation_type: OperationType) -> LatencyTracker._LatencyContext:
        """Track operation latency.

        Args:
            operation_type: Type of operation.

        Returns:
            Context manager.
        """
        return self.latency_tracker.measure(operation_type)

    def get_timeout(
        self,
        operation_type: OperationType,
        safety_factor: float = 2.0,
    ) -> float:
        """Get adaptive timeout for operation.

        Args:
            operation_type: Type of operation.
            safety_factor: Safety multiplier.

        Returns:
            Timeout in seconds.
        """
        return self._adaptive_timeouts[operation_type].get_timeout_seconds(safety_factor)

    def record_and_adapt(
        self,
        operation_type: OperationType,
        latency_ms: float,
    ) -> None:
        """Record latency and update adaptive timeout.

        Args:
            operation_type: Type of operation.
            latency_ms: Measured latency.
        """
        self._adaptive_timeouts[operation_type].record_latency(latency_ms)
        asyncio.create_task(self.latency_tracker.record(operation_type, latency_ms))

    def get_dashboard(self) -> dict[str, Any]:
        """Get performance dashboard.

        Returns:
            Dashboard dictionary.
        """
        return {
            "latency": self.latency_tracker.get_all_stats(),
            "cache": self.local_cache.get_stats(),
            "slo_compliance": self.latency_tracker.check_slo_compliance(),
            "adaptive_timeouts": {
                op.value: {
                    "current_ms": self._adaptive_timeouts[op].get_timeout(),
                    "ema_ms": self._adaptive_timeouts[op]._ema_ms,
                }
                for op in OperationType
            },
        }


# =============================================================================
# Singleton
# =============================================================================

_monitor: ConsensusPerformanceMonitor | None = None


def get_performance_monitor() -> ConsensusPerformanceMonitor:
    """Get or create the global performance monitor.

    Returns:
        ConsensusPerformanceMonitor singleton.
    """
    global _monitor

    if _monitor is None:
        _monitor = ConsensusPerformanceMonitor()

    return _monitor


# =============================================================================
# Decorator for Performance Tracking
# =============================================================================


def track_latency(operation_type: OperationType):
    """Decorator to track function latency.

    Args:
        operation_type: Type of operation.

    Example:
        >>> @track_latency(OperationType.REDIS_READ)
        ... async def get_value(key):
        ...     return await redis.get(key)
    """

    def decorator(
        func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            monitor = get_performance_monitor()
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                latency_ms = (time.perf_counter() - start) * 1000
                monitor.record_and_adapt(operation_type, latency_ms)

        return wrapper

    return decorator


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "LATENCY_TARGETS_MS",
    "AdaptiveTimeout",
    "BatchedWriter",
    "ConsensusPerformanceMonitor",
    "LatencyStats",
    "LatencyTracker",
    "LocalConsensusCache",
    "OperationType",
    "get_performance_monitor",
    "speculative_execute",
    "track_latency",
]


# =============================================================================
# 鏡
# Performance flows. Latency shrinks. The organism thinks faster.
# h(x) ≥ 0. Always.
# =============================================================================
