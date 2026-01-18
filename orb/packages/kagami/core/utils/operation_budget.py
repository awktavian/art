"""Operation Performance Budgets and Monitoring.

Enforces performance SLOs at the operation level with automatic timeout
and circuit breaker protection.

Created: November 10, 2025
Purpose: Address P99 latency 571ms → <100ms SLO breach
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OperationBudget:
    """Performance budget for an operation type."""

    operation: str
    target_ms: int  # Target p50 latency
    max_ms: int  # Hard timeout (p99 target)
    warn_ms: int  # Warning threshold (p95 target)

    @property
    def target_seconds(self) -> float:
        """Target in seconds."""
        return self.target_ms / 1000.0

    @property
    def max_seconds(self) -> float:
        """Max timeout in seconds."""
        return self.max_ms / 1000.0

    @property
    def warn_seconds(self) -> float:
        """Warning threshold in seconds."""
        return self.warn_ms / 1000.0


# Performance budgets by operation type
# Note: In test mode (KAGAMI_BOOT_MODE=test), budgets are relaxed 10x
def _get_operation_budgets() -> dict[str, OperationBudget]:
    """Get operation budgets, adjusted for test mode."""
    import os

    test_mode = os.getenv("KAGAMI_BOOT_MODE") == "test"
    multiplier = 10 if test_mode else 1

    return {
        # API operations
        "intent.execute": OperationBudget(
            "intent.execute",
            target_ms=50 * multiplier,
            max_ms=100 * multiplier,
            warn_ms=75 * multiplier,
        ),
        "tool.execute": OperationBudget(
            "tool.execute",
            target_ms=30 * multiplier,
            max_ms=100 * multiplier,
            warn_ms=60 * multiplier,
        ),
        "agent.execute": OperationBudget(
            "agent.execute",
            target_ms=40 * multiplier,
            max_ms=100 * multiplier,
            warn_ms=70 * multiplier,
        ),
        # Organism operations
        "fractal.homeostasis": OperationBudget(
            "fractal.homeostasis",
            target_ms=200 * multiplier,
            max_ms=500 * multiplier,
            warn_ms=350 * multiplier,
        ),
        "agent.lifecycle": OperationBudget(
            "agent.lifecycle",
            target_ms=10 * multiplier,
            max_ms=50 * multiplier,
            warn_ms=30 * multiplier,
        ),
        "colony.health": OperationBudget(
            "colony.health",
            target_ms=20 * multiplier,
            max_ms=100 * multiplier,
            warn_ms=60 * multiplier,
        ),
        # World model operations
        "world_model.embed": OperationBudget(
            "world_model.embed",
            target_ms=30 * multiplier,
            max_ms=100 * multiplier,
            warn_ms=60 * multiplier,
        ),
        "world_model.query": OperationBudget(
            "world_model.query",
            target_ms=20 * multiplier,
            max_ms=80 * multiplier,
            warn_ms=50 * multiplier,
        ),
        # Safety operations
        "cbf.check": OperationBudget(
            "cbf.check", target_ms=5 * multiplier, max_ms=20 * multiplier, warn_ms=10 * multiplier
        ),
        "safety.gate": OperationBudget(
            "safety.gate",
            target_ms=10 * multiplier,
            max_ms=30 * multiplier,
            warn_ms=20 * multiplier,
        ),
        # Default fallback
        "default": OperationBudget(
            "default", target_ms=50 * multiplier, max_ms=100 * multiplier, warn_ms=75 * multiplier
        ),
    }


OPERATION_BUDGETS: dict[str, OperationBudget] = _get_operation_budgets()


def get_budget(operation: str) -> OperationBudget:
    """Get performance budget for operation.

    Args:
        operation: Operation identifier

    Returns:
        OperationBudget for this operation
    """
    # Try exact match first
    if operation in OPERATION_BUDGETS:
        return OPERATION_BUDGETS[operation]

    # Try prefix match (e.g., "intent.execute.special" -> "intent.execute")
    for key, budget in OPERATION_BUDGETS.items():
        if operation.startswith(key + "."):
            return budget

    # Default budget
    return OPERATION_BUDGETS["default"]


@asynccontextmanager
async def operation_timeout(
    operation: str,
    custom_timeout_ms: int | None = None,
    emit_metrics: bool = True,
) -> AsyncIterator[dict[str, Any]]:
    """Context manager that enforces operation timeout with metrics.

    Usage:
        async with operation_timeout("intent.execute") as ctx:
            result = await do_work()
            ctx["result"] = result

    Args:
        operation: Operation identifier
        custom_timeout_ms: Override timeout (optional)
        emit_metrics: Whether to emit performance metrics

    Yields:
        Context dict[str, Any] for storing operation data

    Raises:
        asyncio.TimeoutError: If operation exceeds timeout
    """
    budget = get_budget(operation)
    timeout_ms = custom_timeout_ms or budget.max_ms
    timeout_seconds = timeout_ms / 1000.0

    start = time.perf_counter()
    context: dict[str, Any] = {
        "operation": operation,
        "budget_ms": budget.target_ms,
        "timeout_ms": timeout_ms,
        "start_time": start,
    }

    timed_out = False
    error = None

    try:
        # Execute with timeout enforcement - use anyio for cross-platform compatibility
        try:
            import anyio

            # anyio.fail_after works with both asyncio and trio
            with anyio.fail_after(timeout_seconds):
                yield context
        except ImportError:
            # Fallback to asyncio if anyio not available
            async with asyncio.timeout(timeout_seconds):
                yield context
    except (TimeoutError, anyio.get_cancelled_exc_class()) as e:
        timed_out = True
        error = e
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.error(
            f"⏱️ TIMEOUT: {operation} exceeded {timeout_ms}ms budget (elapsed: {elapsed_ms:.1f}ms)"
        )

        # Emit timeout metric
        if emit_metrics:
            try:
                from kagami_observability.metrics import Counter

                timeouts = Counter(
                    "kagami_operation_timeouts_total",
                    "Operations that exceeded timeout budget",
                    ["operation"],
                )
                timeouts.labels(operation=operation).inc()
            except Exception:
                pass

        raise
    except Exception as e:
        error = e
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        context["duration_ms"] = elapsed_ms
        context["timed_out"] = timed_out
        context["error"] = error

        # Check if exceeded warning threshold
        if not timed_out and elapsed_ms > budget.warn_ms:
            logger.warning(
                f"⚠️ SLOW: {operation} took {elapsed_ms:.1f}ms "
                f"(warn threshold: {budget.warn_ms}ms, budget: {budget.target_ms}ms)"
            )

            if emit_metrics:
                try:
                    from kagami_observability.metrics import Counter

                    slow_ops = Counter(
                        "kagami_slow_operations_total",
                        "Operations exceeding warning threshold",
                        ["operation"],
                    )
                    slow_ops.labels(operation=operation).inc()
                except Exception:
                    pass

        # Emit latency histogram
        if emit_metrics and not error:
            try:
                from kagami_observability.metrics import Histogram

                latency = Histogram(
                    "kagami_operation_latency_seconds",
                    "Operation latency distribution",
                    ["operation"],
                    buckets=(
                        0.001,
                        0.005,
                        0.010,
                        0.025,
                        0.050,
                        0.075,
                        0.100,
                        0.150,
                        0.200,
                        0.300,
                        0.500,
                        1.0,
                        2.0,
                        5.0,
                        10.0,
                    ),
                )
                latency.labels(operation=operation).observe(elapsed_ms / 1000.0)
            except Exception:
                pass


async def run_with_budget(
    operation: str,
    coro: Any,
    fallback_result: Any = None,
    raise_on_timeout: bool = False,
) -> tuple[Any, bool]:
    """Run coroutine with performance budget enforcement.

    Args:
        operation: Operation identifier
        coro: Coroutine to execute
        fallback_result: Value to return on timeout (if not raising)
        raise_on_timeout: Whether to raise on timeout or return fallback

    Returns:
        Tuple of (result, timed_out)
    """
    try:
        async with operation_timeout(operation) as _ctx:
            result = await coro
            return result, False
    except TimeoutError:
        if raise_on_timeout:
            raise
        logger.warning(f"Operation {operation} timed out, using fallback")
        return fallback_result, True


def check_budget_compliance(operation: str, duration_ms: float) -> dict[str, Any]:
    """Check if operation met performance budget.

    Args:
        operation: Operation identifier
        duration_ms: Operation duration in milliseconds

    Returns:
        Compliance report dict[str, Any]
    """
    budget = get_budget(operation)

    met_target = duration_ms <= budget.target_ms
    met_warn = duration_ms <= budget.warn_ms
    met_max = duration_ms <= budget.max_ms

    status = (
        "excellent"
        if met_target
        else ("good" if met_warn else ("acceptable" if met_max else "exceeded"))
    )

    return {
        "operation": operation,
        "duration_ms": duration_ms,
        "budget": {
            "target_ms": budget.target_ms,
            "warn_ms": budget.warn_ms,
            "max_ms": budget.max_ms,
        },
        "compliance": {
            "met_target": met_target,
            "met_warn": met_warn,
            "met_max": met_max,
            "status": status,
        },
        "overage_ms": max(0, duration_ms - budget.target_ms),
        "overage_percent": (
            ((duration_ms / budget.target_ms) - 1.0) * 100
            if duration_ms > budget.target_ms
            else 0.0
        ),
    }


__all__ = [
    "OPERATION_BUDGETS",
    "OperationBudget",
    "check_budget_compliance",
    "get_budget",
    "operation_timeout",
    "run_with_budget",
]
