"""Caching utilities for Forge LLM operations.

Consolidation (Dec 26, 2025): MemoryCache and CacheManager moved to
kagami.core.caching.memory_cache. This module re-exports for backward
compatibility and provides Forge-specific caching decorators.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

# Re-export canonical implementations from core
from kagami.core.caching.memory_cache import (
    _MISSING,
    CacheManager,
    MemoryCache,
    _generate_cache_key,
)

# Forge-specific caches (lazy initialized)
_llm_cache: MemoryCache | None = None
_visual_cache: MemoryCache | None = None


def _get_llm_cache() -> MemoryCache:
    """Get or create the LLM cache."""
    global _llm_cache
    if _llm_cache is None:
        _llm_cache = MemoryCache(name="llm_responses", max_size=1000, default_ttl=3600)
    return _llm_cache


def _get_visual_cache() -> MemoryCache:
    """Get or create the visual cache."""
    global _visual_cache
    if _visual_cache is None:
        _visual_cache = MemoryCache(name="visual_analysis", max_size=500, default_ttl=1800)
    return _visual_cache


def cache_llm_response(func: Callable) -> Callable:
    """Decorator to cache LLM responses."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        cache = _get_llm_cache()
        cache_key = _generate_cache_key(func.__name__, *args, **kwargs)

        cached = await cache.get(cache_key, default=_MISSING)
        if cached is not _MISSING:
            return cached

        result = await func(*args, **kwargs)
        await cache.set(cache_key, result)
        return result

    return wrapper


def cache_visual_analysis(func: Callable) -> Callable:
    """Decorator to cache visual analysis results."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        cache = _get_visual_cache()
        cache_key = _generate_cache_key(func.__name__, *args, **kwargs)

        cached = await cache.get(cache_key, default=_MISSING)
        if cached is not _MISSING:
            return cached

        result = await func(*args, **kwargs)
        await cache.set(cache_key, result)
        return result

    return wrapper


def clear_llm_cache() -> None:
    """Clear the LLM response cache."""
    cache = _get_llm_cache()
    cache.clear_sync()


def clear_visual_cache() -> None:
    """Clear the visual analysis cache."""
    cache = _get_visual_cache()
    cache.clear_sync()


__all__ = [
    "CacheManager",
    # Re-exported from core
    "MemoryCache",
    # Forge-specific
    "cache_llm_response",
    "cache_visual_analysis",
    "clear_llm_cache",
    "clear_visual_cache",
]
