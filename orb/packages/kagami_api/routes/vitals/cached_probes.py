"""Cached health check helpers for performance optimization.

This module provides caching layer for expensive health checks to reduce latency.

Performance improvements:
- Health check caching: 5s TTL reduces redundant database/Redis/etcd checks
- Async-aware caching: Uses asyncio-safe locking
- Memory efficient: Fixed-size cache with automatic eviction

Created: December 2025
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from kagami_api.schemas.vitals import DependencyCheck

# Type variable for generic cache decorator
T = TypeVar("T")

# Cache storage: {cache_key: (result, expiry_time)}
_CACHE: dict[str, tuple[Any, float]] = {}
_CACHE_LOCK = asyncio.Lock()
_MAX_CACHE_SIZE = 100  # Prevent unbounded growth


def _cache_key(func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
    """Generate cache key from function name and arguments."""
    # Simple key: function name + stringified args
    args_str = "_".join(str(arg) for arg in args)
    kwargs_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return f"{func.__name__}:{args_str}:{kwargs_str}"


def async_cached(ttl_seconds: float = 5.0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Async-aware cache decorator with TTL.

    Args:
        ttl_seconds: Time-to-live for cached results in seconds

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _cache_key(func, *args, **kwargs)
            now = time.time()

            # Check cache (fast path - no lock for reads)
            if key in _CACHE:
                result, expiry = _CACHE[key]
                if now < expiry:
                    return result

            # Cache miss or expired - acquire lock
            async with _CACHE_LOCK:
                # Double-check after acquiring lock (another task may have updated)
                if key in _CACHE:
                    result, expiry = _CACHE[key]
                    if now < expiry:
                        return result

                # Execute function
                result = await func(*args, **kwargs)

                # Store in cache
                _CACHE[key] = (result, now + ttl_seconds)

                # Evict oldest entries if cache is too large
                if len(_CACHE) > _MAX_CACHE_SIZE:
                    # Remove 10% of oldest entries
                    sorted_keys = sorted(_CACHE.items(), key=lambda x: x[1][1])
                    for old_key, _ in sorted_keys[: _MAX_CACHE_SIZE // 10]:
                        _CACHE.pop(old_key, None)

                return result

        return wrapper

    return decorator


# Pre-import expensive modules to avoid import overhead in hot paths
try:
    from kagami.core.database.async_connection import get_async_engine
    from sqlalchemy import text

    _DB_IMPORTS_AVAILABLE = True
except ImportError:
    _DB_IMPORTS_AVAILABLE = False

try:
    from kagami.core.caching.redis import RedisClientFactory

    _REDIS_IMPORTS_AVAILABLE = True
except ImportError:
    _REDIS_IMPORTS_AVAILABLE = False

try:
    from kagami.core.consensus.etcd_client import get_etcd_client

    _ETCD_IMPORTS_AVAILABLE = True
except ImportError:
    _ETCD_IMPORTS_AVAILABLE = False


@async_cached(ttl_seconds=5.0)
async def cached_database_health() -> DependencyCheck:
    """Cached database health check with 5s TTL."""
    start = time.perf_counter()

    if not _DB_IMPORTS_AVAILABLE:
        return DependencyCheck(status="unavailable", error="Database imports not available")

    try:
        engine = get_async_engine()
        if not engine:
            return DependencyCheck(status="unavailable", error="No engine configured")

        # Test actual connectivity with a simple query
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()

        latency_ms = (time.perf_counter() - start) * 1000
        return DependencyCheck(status="healthy", latency_ms=round(latency_ms, 2))
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return DependencyCheck(status="unhealthy", error=str(e), latency_ms=round(latency_ms, 2))


@async_cached(ttl_seconds=5.0)
async def cached_redis_health() -> DependencyCheck:
    """Cached Redis health check with 5s TTL."""
    start = time.perf_counter()

    if not _REDIS_IMPORTS_AVAILABLE:
        return DependencyCheck(status="unavailable", error="Redis imports not available")

    try:
        redis = RedisClientFactory.get_client()
        if not redis:
            return DependencyCheck(status="unavailable", error="No Redis client configured")

        # Test ping
        pong = redis.ping()
        if not pong:
            return DependencyCheck(status="degraded", error="Ping failed")

        # Test basic get/set
        test_key = "_kagami_health_check"
        redis.set(test_key, "ok", ex=10)
        value = redis.get(test_key)

        latency_ms = (time.perf_counter() - start) * 1000
        status = "healthy" if value == "ok" else "degraded"

        return DependencyCheck(status=status, latency_ms=round(latency_ms, 2))

    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return DependencyCheck(status="unhealthy", error=str(e), latency_ms=round(latency_ms, 2))


@async_cached(ttl_seconds=5.0)
async def cached_etcd_health() -> DependencyCheck:
    """Cached etcd health check with 5s TTL."""
    start = time.perf_counter()

    if not _ETCD_IMPORTS_AVAILABLE:
        return DependencyCheck(status="unavailable", error="etcd imports not available")

    try:
        client = get_etcd_client()
        if not client:
            return DependencyCheck(status="unavailable", error="No etcd client configured")

        # Try to get cluster status
        try:
            status = await client.status()
            latency_ms = (time.perf_counter() - start) * 1000
            return DependencyCheck(
                status="healthy",
                latency_ms=round(latency_ms, 2),
                note=f"leader={getattr(status, 'leader', 'unknown')}",
            )
        except Exception:
            latency_ms = (time.perf_counter() - start) * 1000
            return DependencyCheck(
                status="healthy", latency_ms=round(latency_ms, 2), note="connected"
            )
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return DependencyCheck(status="unhealthy", error=str(e), latency_ms=round(latency_ms, 2))


def clear_health_cache() -> None:
    """Clear all cached health check results.

    Useful for testing or when you need fresh results immediately.
    """
    _CACHE.clear()


def get_cache_stats() -> dict[str, int]:
    """Get cache statistics for monitoring.

    Returns:
        Dictionary with cache size and max size
    """
    return {"size": len(_CACHE), "max_size": _MAX_CACHE_SIZE}


__all__ = [
    "async_cached",
    "cached_database_health",
    "cached_etcd_health",
    "cached_redis_health",
    "clear_health_cache",
    "get_cache_stats",
]
