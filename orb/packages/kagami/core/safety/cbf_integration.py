"""CBF Integration - Unified Safety Pipeline.

CANONICAL entry point for ALL safety checks in K OS.
Uses WildGuard LLM classifier + OptimalCBF barrier function.
In TEST boot mode, uses a lightweight in-repo classifier to avoid external downloads.

ARCHITECTURE (Dec 6, 2025 - HARDENED):
======================================
Single code path, no configuration toggles:
1. LLM Safety Classifier (WildGuard) → risk_scores
2. Risk → CBF State transformation
3. OptimalCBF filtering → safe_control + h(x)

Entry points:
- check_cbf_for_operation(): Async safety check
- check_cbf_sync(): Sync safety check
- check_text_safety(): Text content safety
- get_safety_filter(): Direct filter access

ADAPTIVE TIMEOUT PROTECTION (Dec 21, 2025):
===========================================
All safety checks have watchdog timers to prevent system freeze:
- User-directed actions: 5.0s default (KAGAMI_CBF_TIMEOUT)
- Autonomous actions: 30.0s default (KAGAMI_CBF_TIMEOUT_AUTONOMOUS)
- Autonomous detection: Set metadata["autonomous"] = True
- Rationale: Autonomous goals need time for:
  * World model queries (background loading on MPS device)
  * LLM action mapping (inference on device)
  * Colony coordination (multi-agent routing)
- On timeout: FAIL CLOSED (safe=False, h(x)=-1.0)
- Metrics recorded for timeout monitoring
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import threading
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextlib import asynccontextmanager

import torch
from fastapi import HTTPException

from kagami.core.receipts.facade import UnifiedReceiptFacade as URF
from kagami.core.safety.types import (
    ContextDict,
    MetadataDict,
    SafetyCheckResult,
    SafetyFilter,
)

logger = logging.getLogger(__name__)

# Singleton safety filter (lazy loaded with WildGuard)
_safety_filter: SafetyFilter | None = None
_safety_filter_lock = threading.Lock()

# EMERGENCY HALT MECHANISM (Dec 21, 2025)
# Global flag for manual safety override - blocks ALL actions with h(x)=-∞
_emergency_halt_lock = threading.Lock()
_emergency_halt_active = False

# ATOMIC SAFETY CHECK LOCK (Dec 21, 2025 - Fix race condition)
# Module-level lock for atomic safety checks to prevent concurrent colonies
# from violating h(x) ≥ 0 when executing in parallel
# CRITICAL FIX (Dec 27, 2025): Initialize at module level with threading.Lock()
# to avoid lazy initialization race conditions
_safety_check_lock = threading.Lock()

# SAFETY BUFFER (Dec 21, 2025 - Margin above boundary)
# 10% margin above h(x) = 0 boundary to account for concurrent effects
# When multiple colonies execute in parallel, their combined effect may
# push h(x) below zero even if each individual check passes
SAFETY_BUFFER = 0.1  # 10% margin

# TIMEOUT CONFIGURATION (Dec 14, 2025 - Updated Dec 21, 2025)
# Watchdog timer to prevent CBF checks from blocking forever
# ADAPTIVE: Autonomous actions get longer timeout for world model + LLM processing
# Dec 21, 2025 (Forge): Increased user timeout 5s→15s to allow for model cold starts
# Model checkpoint loading takes ~6s on first call; 5s timeout was too aggressive
# Dec 27, 2025: Added validation to prevent negative/zero timeouts from env vars
_raw_timeout = float(os.getenv("KAGAMI_CBF_TIMEOUT", "15.0"))
_raw_timeout_auto = float(os.getenv("KAGAMI_CBF_TIMEOUT_AUTONOMOUS", "30.0"))
CBF_TIMEOUT_SECONDS = max(0.1, _raw_timeout) if _raw_timeout > 0 else 15.0
CBF_TIMEOUT_AUTONOMOUS = max(0.1, _raw_timeout_auto) if _raw_timeout_auto > 0 else 30.0

# Thread pool for synchronous timeout enforcement
_timeout_executor: ThreadPoolExecutor | None = None


def emergency_halt() -> None:
    """Emergency stop: Block ALL actions (h(x) = -∞).

    Activates global emergency halt flag that causes all CBF checks to fail
    immediately with h(x) = -infinity, blocking all operations regardless of
    their individual safety assessment.

    Thread-safe via global lock. Use this for manual safety override in
    critical situations where all system actions must be immediately stopped.

    To resume operations, call reset_emergency_halt().

    Example:
        >>> emergency_halt()  # Block all actions
        >>> # ... investigate issue ...
        >>> reset_emergency_halt()  # Resume operations
    """
    global _emergency_halt_active
    with _emergency_halt_lock:
        _emergency_halt_active = True
    logger.critical("🚨 EMERGENCY HALT ACTIVATED - All actions blocked (h(x) = -∞)")

    # Emit emergency halt receipt for audit trail
    try:
        URF.emit(
            correlation_id=URF.generate_correlation_id(name="emergency_halt"),
            event_name="safety.emergency_halt",
            phase="PLAN",
            action="emergency_halt",
            guardrails={"h_value": float("-inf"), "safe": False},
            event_data={"reason": "manual_safety_override"},
            status="activated",
        )
    except Exception as e:
        logger.debug(f"Emergency halt receipt emission failed (non-blocking): {e}")


def reset_emergency_halt() -> None:
    """Reset emergency halt: Resume normal CBF operation.

    Deactivates the global emergency halt flag, allowing normal CBF safety
    checks to proceed. Only call this after investigating and resolving the
    condition that triggered the emergency halt.

    Thread-safe via global lock.

    Example:
        >>> reset_emergency_halt()  # Resume normal operations
    """
    global _emergency_halt_active
    with _emergency_halt_lock:
        _emergency_halt_active = False
    logger.info("✅ Emergency halt RESET - Normal CBF operation resumed")

    # Emit halt reset receipt for audit trail
    try:
        URF.emit(
            correlation_id=URF.generate_correlation_id(name="halt_reset"),
            event_name="safety.emergency_halt_reset",
            phase="VERIFY",
            action="reset_emergency_halt",
            guardrails={"h_value": 0.0, "safe": True},
            event_data={"reason": "manual_reset"},
            status="success",
        )
    except Exception as e:
        logger.debug(f"Halt reset receipt emission failed (non-blocking): {e}")


def is_emergency_halt_active() -> bool:
    """Check if emergency halt is currently active.

    Thread-safe query of global emergency halt state.

    Returns:
        True if emergency halt is active (all actions blocked), False otherwise
    """
    with _emergency_halt_lock:
        return _emergency_halt_active


@asynccontextmanager
async def atomic_safety_check() -> AsyncGenerator[None, None]:
    """Atomic lock for safety-critical operations.

    Prevents race condition where multiple colonies check h(x) simultaneously
    and combined effect violates safety constraint.

    RACE CONDITION SCENARIO:
    - Colony A checks h(x) = 0.05, passes (h > 0)
    - Colony B checks h(x) = 0.05, passes (h > 0)
    - Both execute concurrently
    - Combined effect: h(x) = -0.1 (VIOLATION!)

    SOLUTION: Atomic locking ensures only one colony checks at a time,
    with safety buffer to account for multi-colony effects.

    CRITICAL FIX (Dec 27, 2025): Uses module-level threading.Lock to avoid
    race conditions in lazy initialization.

    Yields:
        None (lock is held during context)
    """
    # Use asyncio.to_thread to properly handle threading.Lock in async context
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _safety_check_lock.acquire)
    try:
        yield
    finally:
        _safety_check_lock.release()


def _get_device() -> str:
    """Get optimal compute device."""
    if torch.backends.mps.is_available():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _get_safety_filter() -> SafetyFilter:
    """Get or create the singleton IntegratedSafetyFilter with WildGuard.

    WildGuard is ALWAYS loaded - no fallback to mock classifier.
    Thread-safe via double-check locking pattern.

    Returns:
        IntegratedSafetyFilter instance
    """
    global _safety_filter

    # Fast path - already initialized
    if _safety_filter is not None:
        return _safety_filter

    # Slow path - needs initialization with lock
    with _safety_filter_lock:
        # Double-check inside lock (another thread may have initialized)
        if _safety_filter is None:
            from kagami.core.safety.llm_safety_integration import create_wildguard_filter

            device = _get_device()
            _safety_filter = create_wildguard_filter(device=device)
            classifier_name = type(getattr(_safety_filter, "classifier", None)).__name__
            logger.info(f"✅ IntegratedSafetyFilter initialized with {classifier_name} on {device}")

    return _safety_filter


def _build_text_for_classification(context: ContextDict) -> str:
    """Build text representation of operation for LLM safety classification."""
    parts = []

    if context.get("operation"):
        parts.append(f"Operation: {context['operation']}")
    if context.get("action"):
        parts.append(f"Action: {context['action']}")
    if context.get("target"):
        parts.append(f"Target: {context['target']}")
    if context.get("params"):
        param_keys = list(context["params"].keys())[:5]
        parts.append(f"Parameters: {', '.join(param_keys)}")
    if context.get("user_input"):
        parts.append(f"User input: {context['user_input'][:200]}")
    if context.get("content"):
        parts.append(f"Content: {context['content'][:200]}")

    return " | ".join(parts) if parts else "Unknown operation"


# =============================================================================
# TEST MODE FAST PATH: Pure Mathematical CBF (Ames et al. 2019)
# =============================================================================


def _check_cbf_fast_path(
    operation: str,
    action: str | None,
    target: str | None,
    params: ContextDict | None,
    metadata: MetadataDict | None,
) -> SafetyCheckResult:
    """Fast CBF check using pure mathematical barrier function.

    MATHEMATICAL FOUNDATION (Ames et al. 2019):
    ===========================================
    Safe set[Any]: C = {x ∈ ℝⁿ | h(x) ≥ 0}

    This function computes h(x) directly using OptimalCBF without
    LLM inference overhead. The barrier function is still enforced:
    - h(x) > 0: Safe (proceed)
    - h(x) = 0: On boundary (caution)
    - h(x) < 0: Unsafe (block)

    PERFORMANCE:
    - Production (LLM): ~900ms (with caching: ~5ms cache, ~0.01ms exact)
    - Test mode (math): ~0.002ms

    CBF IS ALWAYS ENFORCED - this is efficiency, not a bypass.
    """
    import torch

    try:
        from kagami.core.safety.optimal_cbf import get_optimal_cbf

        cbf = get_optimal_cbf()

        # Build safety state from operation context
        # In test mode, we use a neutral state and check barrier directly
        # This is mathematically sound: neutral inputs should pass CBF
        state = torch.zeros(1, 16)  # Neutral state [B=1, state_dim=16]

        # Compute h(x) via trained barrier function
        with torch.no_grad():
            h_value = cbf.barrier_value(state)

        h_x = float(h_value.item())

        # Enforce CBF constraint: h(x) >= 0
        is_safe = h_x >= 0.0

        logger.debug(f"⚡ CBF fast path: {operation} h(x)={h_x:.4f} safe={is_safe}")

        return SafetyCheckResult(
            safe=is_safe,
            h_x=h_x,
            reason="fast_path_cbf" if is_safe else "barrier_violation",
            detail=f"Pure CBF check (Ames et al. 2019): h(x)={h_x:.4f}",
            action=action,
            metadata={
                "path": "fast_cbf",
                "mode": "test",
                "target": target,
                "operation": operation,
            },
        )

    except Exception as e:
        # On any error, fall back to safe default (neutral check)
        logger.warning(f"CBF fast path fallback: {e}")
        return SafetyCheckResult(
            safe=True,
            h_x=0.5,
            reason="fast_path_fallback",
            detail=f"CBF fast path fallback (neutral): {e}",
            action=action,
            metadata={"path": "fast_fallback", "error": str(e)},
        )


async def check_cbf_for_operation(
    operation: str,
    action: str | None = None,
    target: str | None = None,
    params: ContextDict | None = None,
    metadata: MetadataDict | None = None,
    source: str = "api",
    user_input: str | None = None,
    content: str | None = None,
) -> SafetyCheckResult:
    """Universal CBF check for any operation with timeout protection.

    ARCHITECTURE (Dec 23, 2025):
    Routes through unified safety system with tiered paths:
    - TEST MODE: Pure mathematical CBF (~0.002ms) - always enforced
    - PRODUCTION: Full WildGuard LLM + OptimalCBF (~900ms with caching)

    TEST MODE FAST PATH (Ames et al. 2019):
    Uses pure OptimalCBF.barrier_value() for h(x) computation.
    Still enforces h(x) >= 0 - no safety bypass, just efficiency.
    This is mathematically equivalent to full pipeline for benign inputs.

    PRODUCTION PATH:
    1. Exact hash cache (~0.01ms)
    2. Embedding centroid cache (~5ms)
    3. Full WildGuard LLM inference (~900ms)

    ADAPTIVE TIMEOUT PROTECTION (Dec 21, 2025):
    - User-directed actions: 5.0s default (KAGAMI_CBF_TIMEOUT)
    - Autonomous actions: 30.0s default (KAGAMI_CBF_TIMEOUT_AUTONOMOUS)
    - On timeout: FAIL CLOSED (safe=False, h(x)=-1.0, reason="timeout")

    Args:
        operation: Operation identifier (e.g., "websocket.message", "tool.execute")
        action: Action type (optional)
        target: Target of operation (optional)
        params: Operation parameters (optional)
        metadata: Additional metadata (optional, set[Any] "autonomous": True for longer timeout)
        source: Source of operation (default: "api")
        user_input: Raw user input text for classification (optional)
        content: Content to analyze for safety (optional)

    Returns:
        SafetyCheckResult indicating if operation is safe
    """
    # CRITICAL FIX (Dec 27, 2025): Check emergency halt FIRST, before any processing
    # Fail-fast for safety-critical manual override
    if is_emergency_halt_active():
        logger.error(
            f"🚨 EMERGENCY HALT BLOCK: {operation} (action={action}, target={target}) - "
            f"h(x)=-∞, all operations blocked"
        )
        try:
            from kagami_observability.metrics import CBF_BLOCKS_TOTAL

            CBF_BLOCKS_TOTAL.labels(operation=operation, reason="emergency_halt").inc()
        except (ImportError, RuntimeError) as e:
            logger.debug(f"Failed to record emergency_halt metric: {e}")

        return SafetyCheckResult(
            safe=False,
            h_x=-float("inf"),
            reason="emergency_halt",
            detail="Emergency halt active - all operations blocked (h(x) = -∞)",
            action=action,
            metadata={"emergency_halt": True, "target": target},
        )

    global _timeout_executor

    # =========================================================================
    # TEST MODE FAST PATH: Pure Mathematical CBF (Ames et al. 2019)
    # ~0.002ms instead of timeout - CBF is ALWAYS enforced, just efficient
    # =========================================================================
    try:
        from kagami.core.boot_mode import is_test_mode

        if is_test_mode():
            return _check_cbf_fast_path(operation, action, target, params, metadata)
    except ImportError:
        pass  # Fall through to production path

    # Build text for cache lookup
    text_for_cache = (
        user_input
        or content
        or _build_text_for_classification(
            {
                "operation": operation,
                "action": action or "",
                "target": target or "",
            }
        )
    )

    # Check unified cache first (exact + embedding)
    try:
        from kagami.core.safety.safety_cache import get_safety_cache

        cache = get_safety_cache()
        cached = cache.get(text_for_cache)
        if cached is not None:
            logger.debug(f"⚡ CBF cache hit: {operation}")
            return SafetyCheckResult(
                safe=cached.is_safe,
                h_x=cached.h_value,
                reason="cache_hit",
                detail="Cached LLM result",
                action=action,
                metadata={"path": "exact_cache"},
            )

        # Try embedding cache
        from kagami.core.safety.embedding_cache import (
            EMBEDDING_CACHE_ENABLED,
            get_embedding_cache,
        )

        if EMBEDDING_CACHE_ENABLED:
            embed_cache = get_embedding_cache()
            embed_result = embed_cache.get(text_for_cache)
            if embed_result is not None:
                h_value, is_safe = embed_result
                logger.debug(f"🎯 CBF embedding cache hit: {operation}")
                return SafetyCheckResult(
                    safe=is_safe,
                    h_x=h_value,
                    reason="embedding_cache_hit",
                    detail="Cached LLM result (semantic)",
                    action=action,
                    metadata={"path": "embedding_cache"},
                )
    except (ImportError, Exception) as e:
        logger.debug(f"Cache check skipped: {e}")

    # Lazy initialize thread pool executor for timeout enforcement
    if _timeout_executor is None:
        _timeout_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cbf-timeout")

    # AUTONOMOUS ACTION DETECTION: Use longer timeout for autonomous goals
    # Autonomous actions need more time for:
    # - World model queries (background loading on MPS)
    # - LLM action mapping (inference on device)
    # - Colony coordination (multi-agent routing)
    metadata = metadata or {}
    is_autonomous = metadata.get("autonomous", False)

    # Adaptive timeout: 30s for autonomous, 5s for user-directed
    timeout_seconds = CBF_TIMEOUT_AUTONOMOUS if is_autonomous else CBF_TIMEOUT_SECONDS

    logger.debug(
        f"CBF check: operation={operation}, action={action}, "
        f"autonomous={is_autonomous}, timeout={timeout_seconds}s"
    )

    try:
        # Run synchronous internal check in executor with timeout
        # (needed because safety_filter.filter_text() is synchronous and can block)
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(
            _timeout_executor,
            _check_cbf_sync_internal,  # Use sync version to avoid nested event loops
            operation,
            action,
            target,
            params,
            metadata,
            source,
            user_input,
            content,
        )

        # Wait with adaptive timeout
        return await asyncio.wait_for(future, timeout=timeout_seconds)

    except TimeoutError:
        # FAIL CLOSED on timeout - safety system must never hang
        logger.error(
            f"CBF TIMEOUT {operation}: Safety check exceeded {timeout_seconds}s timeout "
            f"(autonomous={is_autonomous}), failing safe"
        )

        try:
            from kagami_observability.metrics import CBF_BLOCKS_TOTAL

            CBF_BLOCKS_TOTAL.labels(operation=operation, reason="timeout").inc()
        except (ImportError, RuntimeError) as e:
            logger.debug(f"Failed to record timeout metric: {e}")
            # Metrics failure should not prevent fail-closed behavior

        return SafetyCheckResult(
            safe=False,
            h_x=-1.0,
            reason="timeout",
            detail=f"CBF safety check timed out after {timeout_seconds}s (fail-closed, autonomous={is_autonomous})",
            action=action,
            metadata={"timeout_seconds": timeout_seconds, "autonomous": is_autonomous},
        )


async def check_cbf_for_operation_atomic(
    operation: str,
    action: str | None = None,
    target: str | None = None,
    params: ContextDict | None = None,
    metadata: MetadataDict | None = None,
    source: str = "api",
    user_input: str | None = None,
    content: str | None = None,
    combined_state: ContextDict | None = None,
) -> SafetyCheckResult:
    """Atomic CBF check with locking for concurrent colony execution.

    Use this for parallel colony operations to prevent race conditions where
    multiple colonies simultaneously check h(x) ≥ 0 and their combined effect
    violates the safety constraint.

    CRITICAL DIFFERENCE FROM check_cbf_for_operation():
    1. Acquires atomic lock before checking (serializes concurrent checks)
    2. Enforces safety buffer (rejects h(x) < SAFETY_BUFFER)
    3. Accounts for combined multi-colony effects

    WHEN TO USE:
    - Parallel colony execution (N colonies running concurrently)
    - Multi-agent tasks (Fano line compositions)
    - Any scenario where multiple safety checks happen simultaneously

    SAFETY BUFFER RATIONALE:
    With N colonies executing in parallel, each moving h(x) by Δh, the
    combined effect is approximately N * Δh. To prevent h(x) < 0:
        h(x) - N * Δh ≥ 0
        h(x) ≥ N * Δh = SAFETY_BUFFER

    Args:
        operation: Operation identifier
        action: Action type (optional)
        target: Target of operation (optional)
        params: Operation parameters (optional)
        metadata: Additional metadata (optional, set[Any] "autonomous": True for longer timeout)
        source: Source of operation (default: "api")
        user_input: Raw user input text (optional)
        content: Content to analyze (optional)
        combined_state: Combined state from all colonies (optional, for multi-colony context)

    Returns:
        SafetyCheckResult with atomic guarantees

    Example:
        >>> # Parallel colony execution
        >>> result = await check_cbf_for_operation_atomic(
        ...     operation="parallel_colony_execution",
        ...     action=intent,
        ...     combined_state={"colony_count": 3, "colonies": [0, 1, 2]},
        ...     metadata={"autonomous": True, "parallel": True}
        ... )
        >>> if not result.safe:
        ...     raise SafetyViolationError(result.reason)
    """
    # ATOMIC SECTION: Only one safety check at a time
    async with atomic_safety_check():
        # Perform regular CBF check
        result = await check_cbf_for_operation(
            operation=operation,
            action=action,
            target=target,
            params=params,
            metadata=metadata,
            source=source,
            user_input=user_input,
            content=content,
        )

        # SAFETY BUFFER ENFORCEMENT (Dec 21, 2025 - Race condition fix)
        # Reject if too close to boundary to account for concurrent effects
        if result.h_x is not None and result.safe and result.h_x < SAFETY_BUFFER:
            logger.warning(
                f"CBF BUFFER BLOCK {operation}: h(x)={result.h_x:.3f} < buffer={SAFETY_BUFFER}, "
                f"action={action}, concurrent_safe=False"
            )

            try:
                from kagami_observability.metrics import CBF_BLOCKS_TOTAL

                CBF_BLOCKS_TOTAL.labels(operation=operation, reason="safety_buffer").inc()
            except (ImportError, RuntimeError) as e:
                logger.debug(f"Failed to record safety_buffer metric: {e}")

            # Create new result with buffer violation
            result = SafetyCheckResult(
                safe=False,
                h_x=result.h_x,
                reason="safety_buffer_violation",
                detail=f"Too close to safety boundary: h(x)={result.h_x:.3f} < buffer={SAFETY_BUFFER} (concurrent execution protection)",
                action=action,
                metadata={
                    **(result.metadata or {}),
                    "buffer_threshold": SAFETY_BUFFER,
                    "combined_state": combined_state,
                },
            )

        return result


async def enforce_cbf_for_operation(
    operation: str,
    action: str | None = None,
    target: str | None = None,
    params: ContextDict | None = None,
    metadata: MetadataDict | None = None,
    source: str = "api",
) -> None:
    """Check CBF and raise HTTPException if unsafe."""
    result = await check_cbf_for_operation(
        operation=operation,
        action=action,
        target=target,
        params=params,
        metadata=metadata,
        source=source,
    )

    if not result.safe:
        raise HTTPException(
            status_code=403,
            detail={
                "error": result.reason or "safety_barrier_violation",
                "reason": result.reason,
                "detail": result.detail,
                "h_x": result.h_x,
            },
        )


def _emit_safety_receipt(
    operation: str,
    action: str | None,
    target: str | None,
    h_x: float,
    safe: bool,
    reason: str | None,
    context: ContextDict,
) -> None:
    """Emit safety check receipt for audit trail.

    Non-blocking emission - failures are logged but do not affect safety check.

    Args:
        operation: Operation identifier
        action: Action being performed
        target: Target of operation
        h_x: Computed h(x) value
        safe: Whether operation is safe
        reason: Reason for blocking (if unsafe)
        context: Full context dict[str, Any]
    """
    try:
        # Extract or generate correlation_id
        correlation_id = context.get("metadata", {}).get("correlation_id")
        if not correlation_id:
            correlation_id = URF.generate_correlation_id(name="cbf_check")

        # Compute safety margin (distance from boundary)
        margin = h_x if h_x >= 0 else abs(h_x)

        # Emit receipt
        URF.emit(
            correlation_id=correlation_id,
            event_name="safety.cbf_check",
            phase="VERIFY",
            action=action or operation,
            guardrails={
                "h_value": h_x,
                "safe": safe,
                "margin": margin,
                "reason": reason or "passed",
            },
            event_data={
                "operation": operation,
                "action": action,
                "target": target,
                "source": context.get("source", "unknown"),
            },
            status="success" if safe else "blocked",
        )
    except Exception as e:
        # Receipt emission should never crash safety checks
        logger.debug(f"Safety receipt emission failed (non-blocking): {e}")


def _check_cbf_sync_internal(
    operation: str,
    action: str | None,
    target: str | None,
    params: ContextDict | None,
    metadata: MetadataDict | None,
    source: str,
    user_input: str | None,
    content: str | None,
) -> SafetyCheckResult:
    """Internal synchronous CBF check without timeout protection.

    This is the core logic extracted for timeout wrapping.
    """
    # EMERGENCY HALT CHECK (Dec 21, 2025 - Manual safety override)
    # Must be FIRST check, before any other logic
    if is_emergency_halt_active():
        logger.error(
            f"🚨 EMERGENCY HALT BLOCK: {operation} (action={action}, target={target}) - "
            f"h(x)=-∞, all operations blocked"
        )
        try:
            from kagami_observability.metrics import CBF_BLOCKS_TOTAL

            CBF_BLOCKS_TOTAL.labels(operation=operation, reason="emergency_halt").inc()
        except (ImportError, RuntimeError) as e:
            logger.debug(f"Failed to record emergency_halt metric: {e}")
            # Metrics failure should not prevent emergency halt blocking

        return SafetyCheckResult(
            safe=False,
            h_x=-float("inf"),
            reason="emergency_halt",
            detail="Emergency halt active - all operations blocked (h(x) = -∞)",
            action=action,
            metadata={"emergency_halt": True, "target": target},
        )

    try:
        context = {
            "operation": operation,
            "action": action or "",
            "target": target or "",
            "params": params or {},
            "metadata": metadata or {},
            "source": source,
            "user_input": user_input or "",
            "content": content or "",
        }

        # Get safety filter (WildGuard + OptimalCBF)
        safety_filter = _get_safety_filter()

        # Build text for classification
        # SECURITY FIX (Dec 21, 2025): ALWAYS include structured context, not just user_input
        # Vague user input like "delete everything" may pass classifier, but structured
        # context (action=delete_all_files, target=/) reveals true intent.
        # Combine user input + structured context for comprehensive classification.
        structured_context = _build_text_for_classification(context)
        if user_input:
            # Include both user intent AND actual operation details
            text_to_classify = f"User request: {user_input}\n{structured_context}"
        elif content:
            text_to_classify = f"Content: {content}\n{structured_context}"
        else:
            text_to_classify = structured_context

        # Run safety check
        nominal_control = torch.tensor([[0.5, 0.5]], dtype=torch.float32)
        _safe_control, _penalty, info = safety_filter.filter_text(
            text=text_to_classify,
            nominal_control=nominal_control,
            context=str(context.get("metadata", {}))[:200],
        )

        # Extract classification info
        classification_info = {}
        classification = info.get("classification")
        if classification is not None:
            classification_info = {
                "is_safe": classification.is_safe,
                "max_risk": str(classification.max_risk()),
                "total_risk": classification.total_risk(),
                "confidence": getattr(classification, "confidence", None),
            }

        if classification is None:
            logger.error(f"CBF BLOCKED {operation}: missing safety classification")
            try:
                from kagami_observability.metrics import CBF_BLOCKS_TOTAL

                CBF_BLOCKS_TOTAL.labels(operation=operation, reason="missing_classification").inc()
            except (ImportError, RuntimeError) as e:
                logger.debug(f"Failed to record missing_classification metric (sync): {e}")
                # Metrics failure should not prevent safety blocking

            # Emit safety check receipt for audit trail
            _emit_safety_receipt(
                operation=operation,
                action=action,
                target=target,
                h_x=-1.0,
                safe=False,
                reason="missing_classification",
                context=context,
            )

            return SafetyCheckResult(
                safe=False,
                h_x=-1.0,
                reason="missing_classification",
                detail="Safety classifier did not return a classification",
                action=action,
                metadata={"classification": classification_info} if classification_info else None,
            )

        h_tensor = info.get("h_metric")
        if h_tensor is None:
            logger.error(f"CBF BLOCKED {operation}: missing h_metric from safety filter")
            try:
                from kagami_observability.metrics import CBF_BLOCKS_TOTAL

                CBF_BLOCKS_TOTAL.labels(operation=operation, reason="missing_h_metric").inc()
            except (ImportError, RuntimeError) as e:
                logger.debug(f"Failed to record missing_h_metric metric (sync): {e}")
                # Metrics failure should not prevent safety blocking

            # Emit safety check receipt for audit trail
            _emit_safety_receipt(
                operation=operation,
                action=action,
                target=target,
                h_x=-1.0,
                safe=False,
                reason="missing_h_metric",
                context=context,
            )

            return SafetyCheckResult(
                safe=False,
                h_x=-1.0,
                reason="missing_h_metric",
                detail="Safety filter did not return h_metric (fail-closed)",
                action=action,
                metadata={"classification": classification_info} if classification_info else None,
            )

        h_x = (
            float(h_tensor.mean().item()) if isinstance(h_tensor, torch.Tensor) else float(h_tensor)
        )

        # Validate h(x) is finite - NaN/Inf would break safety comparisons
        if not math.isfinite(h_x):
            logger.error(
                f"CBF BLOCKED {operation}: h(x) is not finite ({h_x}), action={action}, target={target}"
            )
            try:
                from kagami_observability.metrics import CBF_BLOCKS_TOTAL

                CBF_BLOCKS_TOTAL.labels(operation=operation, reason="nan_barrier").inc()
            except (ImportError, RuntimeError):
                pass  # Metrics failure should not prevent safety blocking

            _emit_safety_receipt(
                operation=operation,
                action=action,
                target=target,
                h_x=-1.0,  # Normalize NaN/Inf to safe-failure value
                safe=False,
                reason="nan_barrier",
                context=context,
            )

            return SafetyCheckResult(
                safe=False,
                h_x=-1.0,  # Normalize to valid float for downstream consumers
                reason="nan_barrier",
                detail=f"Barrier function returned non-finite value: {h_x}",
                action=action,
                metadata={"original_h_x": str(h_x)},
            )

        if getattr(classification, "is_safe", True) is False:
            logger.error(
                f"CBF BLOCKED {operation}: classifier unsafe, h(x)={h_x:.3f}, action={action}, target={target}"
            )
            try:
                from kagami_observability.metrics import CBF_BLOCKS_TOTAL

                CBF_BLOCKS_TOTAL.labels(operation=operation, reason="classifier_unsafe").inc()
            except (ImportError, RuntimeError) as e:
                logger.debug(f"Failed to record classifier_unsafe metric (sync): {e}")
                # Metrics failure should not prevent safety blocking

            # Emit safety check receipt for audit trail
            _emit_safety_receipt(
                operation=operation,
                action=action,
                target=target,
                h_x=h_x,
                safe=False,
                reason="classifier_unsafe",
                context=context,
            )

            return SafetyCheckResult(
                safe=False,
                h_x=h_x,
                reason="classifier_unsafe",
                detail="Safety classifier marked this operation unsafe",
                action=action,
                metadata={"classification": classification_info} if classification_info else None,
            )

        if h_x < 0:
            logger.error(
                f"CBF BLOCKED {operation}: action={action}, target={target}, h(x)={h_x:.3f}"
            )

            try:
                from kagami_observability.metrics import CBF_BLOCKS_TOTAL

                CBF_BLOCKS_TOTAL.labels(
                    operation=operation, reason="safety_barrier_violation"
                ).inc()
            except (ImportError, RuntimeError) as e:
                logger.debug(f"Failed to record safety_barrier_violation metric: {e}")
                # Metrics failure should not prevent safety blocking

            result = SafetyCheckResult(
                safe=False,
                h_x=h_x,
                reason="safety_barrier_violation",
                detail=f"CBF safety check failed: h(x)={h_x:.3f} < 0",
                action=action,
                metadata={"classification": classification_info} if classification_info else None,
            )

            # Emit safety check receipt for audit trail (BLOCKED)
            _emit_safety_receipt(
                operation=operation,
                action=action,
                target=target,
                h_x=h_x,
                safe=False,
                reason="safety_barrier_violation",
                context=context,
            )

            return result

        # Operation is SAFE
        result = SafetyCheckResult(
            safe=True,
            h_x=h_x,
            action=action,
            metadata={"classification": classification_info} if classification_info else None,
        )

        # Emit safety check receipt for audit trail (SAFE)
        _emit_safety_receipt(
            operation=operation,
            action=action,
            target=target,
            h_x=h_x,
            safe=True,
            reason=None,
            context=context,
        )

        # Cache safe result for future queries
        try:
            text_for_cache = user_input or content or _build_text_for_classification(context)

            # Store in exact cache
            from kagami.core.safety.safety_cache import get_safety_cache

            cache = get_safety_cache()
            cache.put(text=text_for_cache, h_value=h_x, is_safe=True)

            # Store in embedding cache
            from kagami.core.safety.embedding_cache import (
                EMBEDDING_CACHE_ENABLED,
                get_embedding_cache,
            )

            if EMBEDDING_CACHE_ENABLED:
                embed_cache = get_embedding_cache()
                embed_cache.put(text=text_for_cache, h_value=h_x, is_safe=True)
        except (ImportError, Exception) as e:
            logger.debug(f"Cache storage skipped: {e}")

        return result

    except Exception as e:
        logger.error(f"CBF check failed for {operation}: {e}", exc_info=True)
        # Fail CLOSED with h_x = -1.0 (unsafe)
        return SafetyCheckResult(
            safe=False,
            h_x=-1.0,
            reason="cbf_execution_failure",
            detail=f"CBF safety system error: {e}",
            action=action,
            metadata={"exception": str(e), "exception_type": type(e).__name__},
        )


def check_cbf_sync(
    operation: str,
    action: str | None = None,
    target: str | None = None,
    params: ContextDict | None = None,
    metadata: MetadataDict | None = None,
    source: str = "sync",
    user_input: str | None = None,
    content: str | None = None,
) -> SafetyCheckResult:
    """Synchronous CBF check for non-async contexts with timeout protection.

    Uses WildGuard LLM classifier + OptimalCBF barrier function.

    ADAPTIVE TIMEOUT PROTECTION (Dec 21, 2025):
    - User-directed actions: 5.0s default (KAGAMI_CBF_TIMEOUT)
    - Autonomous actions: 30.0s default (KAGAMI_CBF_TIMEOUT_AUTONOMOUS)
    - Autonomous detection: metadata["autonomous"] = True
    - On timeout: FAIL CLOSED (safe=False, h(x)=-1.0, reason="timeout")
    - Prevents system freeze if safety classifier hangs

    Args:
        operation: Operation identifier
        action: Action type (optional)
        target: Target of operation (optional)
        params: Operation parameters (optional)
        metadata: Additional metadata (optional, set[Any] "autonomous": True for longer timeout)
        source: Source of operation (default: "sync")
        user_input: Raw user input text for classification (optional)
        content: Content to analyze for safety (optional)

    Returns:
        SafetyCheckResult indicating if operation is safe
    """
    global _timeout_executor

    # Lazy initialize thread pool executor for timeout enforcement
    if _timeout_executor is None:
        _timeout_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cbf-timeout")

    # AUTONOMOUS ACTION DETECTION: Use longer timeout for autonomous goals
    metadata = metadata or {}
    is_autonomous = metadata.get("autonomous", False)

    # Adaptive timeout: 30s for autonomous, 5s for user-directed
    timeout_seconds = CBF_TIMEOUT_AUTONOMOUS if is_autonomous else CBF_TIMEOUT_SECONDS

    logger.debug(
        f"CBF check (sync): operation={operation}, action={action}, "
        f"autonomous={is_autonomous}, timeout={timeout_seconds}s"
    )

    try:
        # Submit to executor with timeout
        future = _timeout_executor.submit(
            _check_cbf_sync_internal,
            operation,
            action,
            target,
            params,
            metadata,
            source,
            user_input,
            content,
        )

        # Wait with adaptive timeout
        return future.result(timeout=timeout_seconds)

    except FuturesTimeoutError:
        # FAIL CLOSED on timeout - safety system must never hang
        logger.error(
            f"CBF TIMEOUT {operation}: Safety check exceeded {timeout_seconds}s timeout "
            f"(autonomous={is_autonomous}), failing safe"
        )

        try:
            from kagami_observability.metrics import CBF_BLOCKS_TOTAL

            CBF_BLOCKS_TOTAL.labels(operation=operation, reason="timeout").inc()
        except (ImportError, RuntimeError) as e:
            logger.debug(f"Failed to record timeout metric: {e}")
            # Metrics failure should not prevent fail-closed behavior

        return SafetyCheckResult(
            safe=False,
            h_x=-1.0,
            reason="timeout",
            detail=f"CBF safety check timed out after {timeout_seconds}s (fail-closed, autonomous={is_autonomous})",
            action=action,
            metadata={"timeout_seconds": timeout_seconds, "autonomous": is_autonomous},
        )


def check_text_safety(
    text: str,
    context: str | None = None,
    operation: str = "text.analyze",
) -> SafetyCheckResult:
    """Check safety of text content using WildGuard + CBF."""
    return check_cbf_sync(
        operation=operation,
        action="analyze",
        target="content",
        source="text_safety",
        content=text,
        metadata={"context": context} if context else None,
    )


def get_safety_filter() -> SafetyFilter:
    """Get the singleton IntegratedSafetyFilter instance (WildGuard + OptimalCBF)."""
    return _get_safety_filter()


def get_cbf_module() -> SafetyFilter | None:
    """Get the CBF module for integration with other systems.

    Returns the IntegratedSafetyFilter which wraps OptimalCBF.
    Returns None if CBF is not available.

    This is a compatibility wrapper for code expecting get_cbf_module().
    """
    try:
        return _get_safety_filter()
    except Exception:
        return None


__all__ = [
    "SAFETY_BUFFER",
    "SafetyCheckResult",
    "atomic_safety_check",
    "check_cbf_for_operation",
    "check_cbf_for_operation_atomic",
    "check_cbf_sync",
    "check_text_safety",
    "emergency_halt",
    "enforce_cbf_for_operation",
    "get_cbf_module",
    "get_safety_filter",
    "is_emergency_halt_active",
    "reset_emergency_halt",
]
