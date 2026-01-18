"""Reflex Layer - Fast-Path Responses Before LLM Reasoning.

Like ant reflexes (pheromone response ~1ms vs deliberation ~100ms),
this provides instant responses for common situations without LLM overhead.

Bio-Inspiration:
- Ant reflexes: Pheromone detection → immediate following (no thinking)
- Bee navigation: Familiar landmarks → reflex flight path
- Result: 95% of operations use fast reflexes, 5% use deep reasoning

Usage:
    reflexes = get_reflex_layer()

    # Try reflex first
    response = reflexes.try_reflex(context)

    if response:
        # Instant! <1ms
        return response
    else:
        # Fall through to LLM reasoning
        return await llm_reason(context)
"""

import logging
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class ReflexLayer:
    """Fast reflex responses for common patterns."""

    def __init__(self) -> None:
        # pattern -> reflex_function
        self._reflexes: dict[str, Callable[[dict[str, Any]], Any]] = {}

        # Cache of recent responses
        self._response_cache: dict[str, tuple[Any, float]] = {}
        self._cache_ttl = 60.0  # 60 seconds

        # Track reflex usage
        self._reflex_hits = 0
        self._total_attempts = 0

        # Register built-in reflexes
        self._register_builtin_reflexes()

    def _register_builtin_reflexes(self) -> None:
        """Register common reflexes."""

        # Heartbeat check (instant response)
        self._reflexes["heartbeat"] = lambda ctx: {
            "status": "alive",
            "agent": ctx.get("agent", "unknown"),
            "timestamp": __import__("time").time(),
        }

        # Simple status query (cache lookup)
        self._reflexes["status_check"] = lambda ctx: {
            "status": "operational",
            "agent": ctx.get("agent", "unknown"),
        }

        # Repeat last action (memory-based reflex)
        self._reflexes["repeat_action"] = lambda ctx: ctx.get(
            "last_result", {"status": "no_history"}
        )

    def register_reflex(self, pattern: str, reflex_fn: Callable[[dict[str, Any]], Any]) -> None:
        """Register a new reflex pattern.

        Args:
            pattern: Pattern identifier
            reflex_fn: Function that returns instant response
        """
        self._reflexes[pattern] = reflex_fn
        logger.info(f"🧠 Registered reflex: {pattern}")

    def try_reflex(self, context: dict[str, Any]) -> Any | None:
        """Try instant reflex response (like ant pheromone response).

        Args:
            context: Situation context

        Returns:
            Instant response or None if no reflex applies
        """
        self._total_attempts += 1

        # Classify situation quickly
        situation_type = self._classify_simple(context)

        # Check cache first (even faster than reflex)
        cache_key = f"{situation_type}:{hash(str(context))}"
        if cache_key in self._response_cache:
            cached_response, cached_time = self._response_cache[cache_key]
            if (time.time() - cached_time) < self._cache_ttl:
                self._reflex_hits += 1
                logger.debug(f"⚡ Cache hit: {situation_type}")
                return cached_response

        # Try reflex
        reflex = self._reflexes.get(situation_type)
        if reflex:
            try:
                response = reflex(context)

                # Cache response
                self._response_cache[cache_key] = (response, __import__("time").time())

                # Limit cache size
                if len(self._response_cache) > 100:
                    # Remove oldest
                    oldest = min(self._response_cache.items(), key=lambda kv: kv[1][1])
                    del self._response_cache[oldest[0]]

                self._reflex_hits += 1

                # Emit metric

                logger.debug(f"⚡ Reflex: {situation_type} (<1ms)")
                return response

            except Exception as e:
                logger.debug(f"Reflex failed: {e}")
                return None

        return None  # No reflex - need LLM reasoning

    def _classify_simple(self, context: dict[str, Any]) -> str:
        """Classify situation quickly (pattern matching, not LLM).

        Args:
            context: Situation context

        Returns:
            Situation type string
        """
        action = str(context.get("action", "")).lower()

        # Simple pattern matching
        if "heartbeat" in action or "ping" in action:
            return "heartbeat"

        if "status" in action and "get" in action:
            return "status_check"

        if "repeat" in action or "again" in action:
            return "repeat_action"

        return "unknown"

    def get_hit_rate(self) -> float:
        """Get reflex hit rate (percentage of requests handled by reflexes).

        Returns:
            Hit rate 0.0-1.0
        """
        if self._total_attempts == 0:
            return 0.0

        return self._reflex_hits / self._total_attempts

    def get_stats(self) -> dict[str, Any]:
        """Get reflex statistics."""
        return {
            "total_attempts": self._total_attempts,
            "reflex_hits": self._reflex_hits,
            "hit_rate": self.get_hit_rate(),
            "registered_reflexes": len(self._reflexes),
            "cached_responses": len(self._response_cache),
        }


# Singleton
_REFLEX_LAYER: ReflexLayer | None = None


def get_reflex_layer() -> ReflexLayer:
    """Get singleton reflex layer."""
    global _REFLEX_LAYER
    if _REFLEX_LAYER is None:
        _REFLEX_LAYER = ReflexLayer()
    return _REFLEX_LAYER


__all__ = ["ReflexLayer", "get_reflex_layer"]
