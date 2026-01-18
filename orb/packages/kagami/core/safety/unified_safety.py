# SPDX-License-Identifier: MIT
"""Unified Safety System - Single Entry Point for All Safety Checks.

ARCHITECTURE (December 22, 2025):
=================================
This is the CANONICAL entry point for ALL safety checks in KagamiOS.
All other safety paths are DEPRECATED and should route through here.

TIERED CACHING:
===============
1. Exact hash cache (~0.01ms)
2. Embedding centroid cache (~5ms)
3. Full WildGuard LLM inference (~900ms)

SAFETY GUARANTEE:
=================
- ALL paths use full LLM intelligence (no keyword heuristics)
- Caches store LLM results only
- Only SAFE results are cached
- h(x) >= 0 invariant enforced at all levels

USAGE:
======
    from kagami.core.safety.unified_safety import check_safety, warmup_safety

    # Warmup at startup
    await warmup_safety()

    # Check any operation
    result = await check_safety(
        text="user query",
        operation="api_request",
        context={"user_id": "123"},
    )

    if result.safe:
        # Proceed
    else:
        # Block with result.reason
"""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from kagami.core.safety.types import SafetyCheckResult

logger = logging.getLogger(__name__)

# Thread pool for running sync operations
_executor: ThreadPoolExecutor | None = None


# =============================================================================
# PERFORMANCE METRICS
# =============================================================================


class UnifiedSafetyMetrics:
    """Track unified safety system performance."""

    def __init__(self) -> None:
        self.exact_hits = 0
        self.embedding_hits = 0
        self.llm_calls = 0
        self.total_calls = 0
        self.total_latency_ms = 0.0

    def record(self, latency_ms: float, path: str) -> None:
        self.total_calls += 1
        self.total_latency_ms += latency_ms
        if path == "exact":
            self.exact_hits += 1
        elif path == "embedding":
            self.embedding_hits += 1
        elif path == "llm":
            self.llm_calls += 1

    def get_stats(self) -> dict[str, Any]:
        avg = self.total_latency_ms / self.total_calls if self.total_calls > 0 else 0
        return {
            "total_calls": self.total_calls,
            "exact_hits": self.exact_hits,
            "embedding_hits": self.embedding_hits,
            "llm_calls": self.llm_calls,
            "avg_latency_ms": avg,
            "cache_rate": (self.exact_hits + self.embedding_hits) / self.total_calls
            if self.total_calls > 0
            else 0,
        }


_metrics = UnifiedSafetyMetrics()


def get_safety_metrics() -> dict[str, Any]:
    """Get unified safety system metrics."""
    return _metrics.get_stats()


# =============================================================================
# UNIFIED SAFETY CHECK
# =============================================================================


async def check_safety(
    text: str,
    operation: str = "unknown",
    context: dict[str, Any] | None = None,
    action: str | None = None,
    bypass_cache: bool = False,
) -> SafetyCheckResult:
    """Unified safety check - single entry point for all safety operations.

    TIERED CACHING:
    1. Exact hash cache (~0.01ms)
    2. Embedding centroid cache (~5ms)
    3. Full WildGuard LLM (~900ms)

    Args:
        text: Text to check for safety
        operation: Operation identifier for logging/metrics
        context: Optional context dict[str, Any]
        action: Action being performed
        bypass_cache: Skip all caches (for testing)

    Returns:
        SafetyCheckResult with h_x and safe fields
    """
    global _executor
    start_time = time.perf_counter_ns()

    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="safety")

    # Run sync check in executor
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor,
        _check_safety_sync,
        text,
        operation,
        context or {},
        action,
        bypass_cache,
    )

    latency_ms = (time.perf_counter_ns() - start_time) / 1_000_000
    path = result.metadata.get("path", "unknown") if result.metadata else "unknown"
    _metrics.record(latency_ms, path)

    return result


def _check_safety_sync(
    text: str,
    operation: str,
    context: dict[str, Any],
    action: str | None,
    bypass_cache: bool,
) -> SafetyCheckResult:
    """Synchronous safety check with tiered caching."""
    start_time = time.perf_counter_ns()

    # === TIER 1: Exact hash cache ===
    if not bypass_cache:
        from kagami.core.safety.safety_cache import get_safety_cache

        exact_cache = get_safety_cache()
        cached = exact_cache.get(text)
        if cached is not None:
            latency_ms = (time.perf_counter_ns() - start_time) / 1_000_000
            logger.debug(f"⚡ Exact cache hit: {operation} in {latency_ms:.4f}ms")
            return SafetyCheckResult(
                safe=cached.is_safe,
                h_x=cached.h_value,
                reason="exact_cache_hit",
                detail="Cached LLM result (exact match)",
                action=action,
                metadata={"path": "exact", "latency_ms": latency_ms},
            )

    # === TIER 2: Embedding centroid cache ===
    if not bypass_cache:
        try:
            from kagami.core.safety.embedding_cache import (
                EMBEDDING_CACHE_ENABLED,
                get_embedding_cache,
            )

            if EMBEDDING_CACHE_ENABLED:
                embed_cache = get_embedding_cache()
                embed_result = embed_cache.get(text)
                if embed_result is not None:
                    h_value, is_safe = embed_result
                    latency_ms = (time.perf_counter_ns() - start_time) / 1_000_000
                    logger.debug(f"🎯 Embedding cache hit: {operation} in {latency_ms:.2f}ms")
                    return SafetyCheckResult(
                        safe=is_safe,
                        h_x=h_value,
                        reason="embedding_cache_hit",
                        detail="Cached LLM result (semantic similarity)",
                        action=action,
                        metadata={"path": "embedding", "latency_ms": latency_ms},
                    )
        except ImportError:
            # sentence-transformers not installed
            pass
        except Exception as e:
            logger.warning(f"Embedding cache error: {e}")

    # === TIER 3: Full LLM inference ===
    result = _run_llm_safety_check(text, context, operation, action)

    latency_ms = (time.perf_counter_ns() - start_time) / 1_000_000
    logger.debug(f"🤖 LLM safety check: {operation} in {latency_ms:.2f}ms")

    # Update caches with LLM result
    if not bypass_cache and result.safe:
        # Update exact cache
        from kagami.core.safety.safety_cache import get_safety_cache

        exact_cache = get_safety_cache()
        exact_cache.put(
            text=text,
            h_value=result.h_x or 1.0,
            is_safe=True,
        )

        # Update embedding cache
        try:
            from kagami.core.safety.embedding_cache import (
                EMBEDDING_CACHE_ENABLED,
                get_embedding_cache,
            )

            if EMBEDDING_CACHE_ENABLED:
                embed_cache = get_embedding_cache()
                embed_cache.put(
                    text=text,
                    h_value=result.h_x or 1.0,
                    is_safe=True,
                )
        except ImportError:
            # sentence-transformers not installed
            pass
        except (RuntimeError, ValueError, AttributeError, OSError) as e:
            # Specific exceptions from cache operations
            logger.debug(f"Embedding cache update failed: {e}")

    result.metadata = result.metadata or {}
    result.metadata["path"] = "llm"
    result.metadata["latency_ms"] = latency_ms

    return result


def _run_llm_safety_check(
    text: str,
    context: dict[str, Any],
    operation: str,
    action: str | None,
) -> SafetyCheckResult:
    """Run full WildGuard LLM safety check."""
    import torch

    from kagami.core.safety.cbf_integration import (
        _build_text_for_classification,
        _get_safety_filter,
    )

    try:
        safety_filter = _get_safety_filter()

        # Build text for classification
        if context:
            structured = _build_text_for_classification(context)
            text_to_classify = f"{text}\n{structured}" if text else structured
        else:
            text_to_classify = text

        # Full LLM inference
        nominal_control = torch.tensor([[0.5, 0.5]], dtype=torch.float32)
        _safe_control, _penalty, info = safety_filter.filter_text(
            text=text_to_classify,
            nominal_control=nominal_control,
            context=str(context.get("metadata", {}))[:200] if context else "",
        )

        # Extract h_metric
        h_tensor = info.get("h_metric")
        if h_tensor is None:
            return SafetyCheckResult(
                safe=False,
                h_x=-1.0,
                reason="missing_h_metric",
                detail="LLM safety filter did not return h_metric",
                action=action,
            )

        h_x = (
            float(h_tensor.mean().item()) if isinstance(h_tensor, torch.Tensor) else float(h_tensor)
        )

        # Check classification
        classification = info.get("classification")
        if classification is not None and not classification.is_safe:
            return SafetyCheckResult(
                safe=False,
                h_x=h_x,
                reason="classifier_unsafe",
                detail="LLM safety classifier marked operation unsafe",
                action=action,
            )

        is_safe = h_x >= 0

        return SafetyCheckResult(
            safe=is_safe,
            h_x=h_x,
            reason="safe" if is_safe else "safety_barrier_violation",
            detail="LLM safety check passed" if is_safe else f"h(x) = {h_x:.3f} < 0",
            action=action,
        )

    except Exception as e:
        logger.error(f"LLM safety check failed: {e}")
        return SafetyCheckResult(
            safe=False,
            h_x=-1.0,
            reason="error",
            detail=f"LLM safety check error: {e}",
            action=action,
        )


# =============================================================================
# WARMUP
# =============================================================================


async def warmup_safety() -> dict[str, float]:
    """Warmup all safety components.

    Returns:
        Dict with warmup times for each component
    """
    times = {}

    # Warmup LLM
    logger.info("⏳ Warming up LLM safety classifier...")
    start = time.time()
    from kagami.core.safety.cbf_integration import _get_safety_filter

    _ = _get_safety_filter()
    times["llm_load"] = time.time() - start

    # Warmup embedding model
    try:
        logger.info("⏳ Warming up embedding model...")
        start = time.time()
        from kagami.core.safety.embedding_cache import compute_embedding

        _ = compute_embedding("warmup test")
        times["embedding_load"] = time.time() - start
    except ImportError:
        logger.info("ℹ️ Embedding cache not available (sentence-transformers not installed)")
        times["embedding_load"] = 0.0

    # Run test inference
    logger.info("⏳ Running test inference...")
    start = time.time()
    _ = await check_safety("warmup test query", operation="warmup", bypass_cache=True)
    times["test_inference"] = time.time() - start

    total = sum(times.values())
    logger.info(f"✅ Safety warmup complete in {total:.1f}s")
    logger.info(f"   LLM: {times['llm_load']:.1f}s, Embed: {times['embedding_load']:.1f}s")

    return times


# =============================================================================
# BATCH PROCESSING
# =============================================================================


async def check_safety_batch(
    texts: list[str],
    operation: str = "batch",
    contexts: list[dict[str, Any]] | None = None,
) -> list[SafetyCheckResult]:
    """Batch safety check for multiple texts.

    Uses tiered caching, then batches remaining LLM calls.

    Args:
        texts: List of texts to check
        operation: Operation identifier
        contexts: Optional list[Any] of contexts

    Returns:
        List of SafetyCheckResult (same order as input)
    """
    if not texts:
        return []

    contexts = contexts or [{}] * len(texts)
    results: list[SafetyCheckResult | None] = [None] * len(texts)
    llm_indices: list[int] = []

    # Check caches first
    from kagami.core.safety.safety_cache import get_safety_cache

    exact_cache = get_safety_cache()

    try:
        from kagami.core.safety.embedding_cache import (
            EMBEDDING_CACHE_ENABLED,
            get_embedding_cache,
        )

        embed_cache = get_embedding_cache() if EMBEDDING_CACHE_ENABLED else None
    except ImportError:
        embed_cache = None

    for i, text in enumerate(texts):
        # Tier 1: Exact cache
        cached = exact_cache.get(text)
        if cached is not None:
            results[i] = SafetyCheckResult(
                safe=cached.is_safe,
                h_x=cached.h_value,
                reason="exact_cache_hit",
                detail="Batch exact cache hit",
                metadata={"path": "exact"},
            )
            continue

        # Tier 2: Embedding cache
        if embed_cache is not None:
            embed_result = embed_cache.get(text)
            if embed_result is not None:
                h_value, is_safe = embed_result
                results[i] = SafetyCheckResult(
                    safe=is_safe,
                    h_x=h_value,
                    reason="embedding_cache_hit",
                    detail="Batch embedding cache hit",
                    metadata={"path": "embedding"},
                )
                continue

        llm_indices.append(i)

    # Tier 3: Batch LLM for remaining
    if llm_indices:
        logger.info(f"🤖 Batch safety: {len(llm_indices)}/{len(texts)} need LLM")

        for idx in llm_indices:
            result = await check_safety(
                text=texts[idx],
                operation=operation,
                context=contexts[idx],
            )
            results[idx] = result

    return results  # type: ignore


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "UnifiedSafetyMetrics",
    "check_safety",
    "check_safety_batch",
    "get_safety_metrics",
    "warmup_safety",
]
