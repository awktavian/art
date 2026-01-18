"""Intent Parsing and Execution Cache.

Caches parsed intents and execution results to reduce latency for repeated operations.

Created: November 10, 2025
Purpose: Optimize intent execution from 463ms to <100ms
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class IntentCache:
    """LRU cache for intent parsing and execution results."""

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 300.0):
        """Initialize intent cache.

        Args:
            max_size: Maximum cache entries
            ttl_seconds: TTL for cache entries (default: 5 minutes)
        """
        self._parse_cache: dict[str, tuple[Any, float]] = {}
        self._result_cache: dict[str, tuple[Any, float]] = {}
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    def _make_key(self, data: Any) -> str:
        """Create cache key from data.

        Args:
            data: Intent data, string, or tuple[Any, ...] (command, context)

        Returns:
            Cache key (hash)
        """
        if isinstance(data, str):
            content = data
        elif isinstance(data, (tuple, list)):
            # Handle (command, context) tuples
            import json

            # Convert simple types to string for hashing
            content = json.dumps(data, sort_keys=True, default=str)
        else:
            # Hash only stable intent fields (exclude metadata, timestamps)
            stable_fields = {
                "action": data.get("action"),
                "target": data.get("target"),
                "params": data.get("params"),
                "app": data.get("app"),
            }
            import json

            content = json.dumps(stable_fields, sort_keys=True)

        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _is_expired(self, timestamp: float) -> bool:
        """Check if cache entry is expired.

        Args:
            timestamp: Entry timestamp

        Returns:
            True if expired
        """
        return (time.time() - timestamp) > self._ttl

    def _evict_if_needed(self, cache: dict[str, Any]) -> None:
        """Evict oldest entries if cache is full.

        Args:
            cache: Cache dict[str, Any] to evict from
        """
        if len(cache) >= self._max_size:
            # Remove 10% oldest entries
            to_remove = int(self._max_size * 0.1)
            sorted_items = sorted(cache.items(), key=lambda x: x[1][1])
            for key, _ in sorted_items[:to_remove]:
                del cache[key]

    def get_parsed(self, lang_command: Any) -> Any | None:
        """Get cached parsed intent.

        Args:
            lang_command: Command string or (command, context) tuple[Any, ...]

        Returns:
            Parsed intent or None if not cached
        """
        key = self._make_key(lang_command)

        if key in self._parse_cache:
            value, timestamp = self._parse_cache[key]
            if not self._is_expired(timestamp):
                self._hits += 1
                logger.debug(f"Intent parse cache HIT: {str(lang_command)[:50]}")
                return value
            else:
                # Expired - remove
                del self._parse_cache[key]

        self._misses += 1
        return None

    def set_parsed(self, lang_command: Any, parsed_intent: Any) -> None:
        """Cache parsed intent.

        Args:
            lang_command: Command string or (command, context) tuple[Any, ...]
            parsed_intent: Parsed intent object
        """
        key = self._make_key(lang_command)
        self._evict_if_needed(self._parse_cache)
        self._parse_cache[key] = (parsed_intent, time.time())
        logger.debug(f"Intent parse cached: {str(lang_command)[:50]}")

    def get_result(self, intent: dict[str, Any]) -> Any | None:
        """Get cached execution result (idempotent operations only).

        Args:
            intent: Intent dict[str, Any]

        Returns:
            Cached result or None
        """
        # Only cache safe read-only operations
        action = intent.get("action", "")
        if not any(
            safe in action.lower()
            for safe in ["get", "list[Any]", "read", "query", "search", "fetch"]
        ):
            return None  # Don't cache mutations

        key = self._make_key(intent)

        if key in self._result_cache:
            value, timestamp = self._result_cache[key]
            if not self._is_expired(timestamp):
                self._hits += 1
                logger.debug(f"Intent result cache HIT: {action}")
                return value
            else:
                del self._result_cache[key]

        self._misses += 1
        return None

    def set_result(self, intent: dict[str, Any], result: Any) -> None:
        """Cache execution result.

        Args:
            intent: Intent dict[str, Any]
            result: Execution result
        """
        # Only cache safe read-only operations
        action = intent.get("action", "")
        if not any(
            safe in action.lower()
            for safe in ["get", "list[Any]", "read", "query", "search", "fetch"]
        ):
            return  # Don't cache mutations

        key = self._make_key(intent)
        self._evict_if_needed(self._result_cache)
        self._result_cache[key] = (result, time.time())
        logger.debug(f"Intent result cached: {action}")

    def invalidate_all(self) -> None:
        """Clear all cache entries."""
        self._parse_cache.clear()
        self._result_cache.clear()
        logger.info("Intent cache cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Stats dict[str, Any]
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "parse_cache_size": len(self._parse_cache),
            "result_cache_size": len(self._result_cache),
            "total_size": len(self._parse_cache) + len(self._result_cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "ttl_seconds": self._ttl,
        }


# Global singleton
_intent_cache: IntentCache | None = None


def get_intent_cache() -> IntentCache:
    """Get singleton intent cache.

    Returns:
        IntentCache instance
    """
    global _intent_cache
    if _intent_cache is None:
        _intent_cache = IntentCache()
    return _intent_cache


__all__ = ["IntentCache", "get_intent_cache"]
