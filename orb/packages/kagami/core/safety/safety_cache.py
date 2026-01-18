# SPDX-License-Identifier: MIT
"""Safety Classification Cache - LLM Result Caching.

ARCHITECTURE (December 22, 2025):
=================================
ALL safety checks use FULL LLM intelligence. No heuristics, no shortcuts.

This module provides caching for LLM inference results ONLY:
1. **Exact Match Cache**: Hash-based lookup for identical queries
2. **TTL Expiration**: Cached results expire after configurable TTL

DESIGN PRINCIPLE:
=================
- NO keyword matching
- NO pattern heuristics
- NO rule-based shortcuts
- ALL queries go through full LLM classification
- Cache only stores VERIFIED LLM results

Architecture:
    check_safety(text)
        │
        ├── [CACHE] exact_cache.get(hash(text)) → cached LLM result? Return
        │
        └── [LLM] wildguard_inference(text) → full intelligence → cache result
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Configuration
CACHE_ENABLED = os.getenv("KAGAMI_DISABLE_SAFETY_CACHE", "0") != "1"
CACHE_MAX_SIZE = int(os.getenv("KAGAMI_SAFETY_CACHE_SIZE", "10000"))
CACHE_TTL_SECONDS = float(os.getenv("KAGAMI_SAFETY_CACHE_TTL", "300.0"))  # 5 minutes


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class CachedSafetyResult:
    """Cached safety classification result from LLM."""

    h_value: float
    is_safe: bool
    risk_scores: dict[str, float]
    timestamp: float
    hit_count: int = 0
    # Store that this was an LLM result, not a heuristic
    source: str = "llm"


@dataclass
class SafetyCacheStats:
    """Cache performance statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    cache_size: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


# =============================================================================
# LRU CACHE WITH TTL
# =============================================================================


class SafetyClassificationCache:
    """LRU cache for LLM safety classifications with TTL expiration.

    Thread-safe implementation using OrderedDict + lock.
    Only caches SAFE results to maintain security.
    ALL cached results are from full LLM inference - no heuristics.
    """

    def __init__(
        self,
        max_size: int = CACHE_MAX_SIZE,
        ttl_seconds: float = CACHE_TTL_SECONDS,
    ):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CachedSafetyResult] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = SafetyCacheStats()

    def _compute_key(self, text: str) -> str:
        """Compute cache key from text."""
        # Use SHA256 for collision resistance
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

    def get(self, text: str) -> CachedSafetyResult | None:
        """Get cached LLM result if valid.

        Args:
            text: Input text

        Returns:
            CachedSafetyResult if valid cache hit, None otherwise
        """
        key = self._compute_key(text)

        with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None

            result = self._cache[key]

            # Check TTL expiration
            if time.time() - result.timestamp > self.ttl_seconds:
                del self._cache[key]
                self._stats.misses += 1
                return None

            # Move to end (LRU)
            self._cache.move_to_end(key)
            result.hit_count += 1
            self._stats.hits += 1
            return result

    def put(
        self,
        text: str,
        h_value: float,
        is_safe: bool,
        risk_scores: dict[str, float] | None = None,
    ) -> None:
        """Cache an LLM safety result (only if SAFE).

        Args:
            text: Input text
            h_value: Safety barrier value
            is_safe: Whether operation is safe
            risk_scores: Optional risk category scores
        """
        # SECURITY: Only cache SAFE results
        # Risky results must always be re-evaluated by LLM
        if not is_safe:
            return

        key = self._compute_key(text)

        with self._lock:
            # Evict oldest if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self._stats.evictions += 1

            self._cache[key] = CachedSafetyResult(
                h_value=h_value,
                is_safe=is_safe,
                risk_scores=risk_scores or {},
                timestamp=time.time(),
                source="llm",  # All cached results are from LLM
            )
            self._stats.cache_size = len(self._cache)

    def clear(self) -> None:
        """Clear all cached results."""
        with self._lock:
            self._cache.clear()
            self._stats.cache_size = 0

    def get_stats(self) -> SafetyCacheStats:
        """Get cache statistics."""
        with self._lock:
            self._stats.cache_size = len(self._cache)
            return SafetyCacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                cache_size=self._stats.cache_size,
            )


# =============================================================================
# SINGLETON CACHE INSTANCE
# =============================================================================

_safety_cache: SafetyClassificationCache | None = None
_cache_lock = threading.Lock()


def get_safety_cache() -> SafetyClassificationCache:
    """Get or create the singleton safety cache."""
    global _safety_cache

    if _safety_cache is not None:
        return _safety_cache

    with _cache_lock:
        if _safety_cache is None:
            _safety_cache = SafetyClassificationCache()
            logger.info(
                f"✅ SafetyClassificationCache initialized: "
                f"max_size={CACHE_MAX_SIZE}, ttl={CACHE_TTL_SECONDS}s, "
                f"source=LLM_ONLY (no heuristics)"
            )

    return _safety_cache


def cached_safety_check(
    text: str,
    full_check_fn: Any,  # Callable that runs full LLM inference
) -> dict[str, Any]:
    """Cached safety check - ALL checks use full LLM intelligence.

    NO HEURISTICS. NO SHORTCUTS. FULL INTELLIGENCE ONLY.

    Architecture:
    1. Check exact match cache for previous LLM result
    2. On miss: Run full LLM inference
    3. Cache safe LLM results for future queries

    Args:
        text: Text to check
        full_check_fn: Function to call for full LLM inference
            Should return dict[str, Any] with 'h_value', 'is_safe', 'risk_scores'

    Returns:
        Dict with safety check result (always from LLM, possibly cached)
    """
    if not CACHE_ENABLED:
        result: dict[str, Any] = full_check_fn(text)
        return result

    cache = get_safety_cache()

    # Check exact match cache (cached LLM results only)
    cached = cache.get(text)
    if cached is not None:
        logger.debug(f"📦 Safety cache hit (LLM result): h={cached.h_value}")
        return {
            "h_value": cached.h_value,
            "is_safe": cached.is_safe,
            "risk_scores": cached.risk_scores,
            "cached": True,
            "source": "llm_cached",
        }

    # FULL LLM INFERENCE - no shortcuts
    result = full_check_fn(text)

    # Cache LLM result if safe
    cache.put(
        text=text,
        h_value=result.get("h_value", 0.5),
        is_safe=result.get("is_safe", False),
        risk_scores=result.get("risk_scores", {}),
    )

    llm_result: dict[str, Any] = result
    llm_result["cached"] = False
    llm_result["source"] = "llm_fresh"
    return llm_result


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CACHE_ENABLED",
    "CachedSafetyResult",
    "SafetyCacheStats",
    "SafetyClassificationCache",
    "cached_safety_check",
    "get_safety_cache",
]
