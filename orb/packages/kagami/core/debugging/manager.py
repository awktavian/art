from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from kagami_observability.metrics import (
    REFLECTION_DURATION_SECONDS,
    REFLECTIONS_TOTAL,
)

from kagami.core.async_utils import safe_create_task

"""Introspection Manager

Non-blocking post-intent reflection pipeline that:
- Queues a lightweight reflection task after an intent runs
- Emits reflection metrics and receipts (best-effort)
- Uses GAIA ReflectionEngine when available; otherwise no-ops gracefully

Design goals:
- Never block API request paths
- Best-effort; swallow errors
- Stable labels and low-cardinality metrics
"""

logger = logging.getLogger(__name__)


def _is_enabled() -> bool:
    try:
        v = (os.getenv("KAGAMI_REFLECTION_ENABLED") or "1").strip().lower()
        return v in ("1", "true", "yes", "on")
    except Exception:
        return True


async def reflect_post_intent(intent: Any, receipt: dict[str, Any] | None) -> None:
    """Queue a post-intent reflection task (non-blocking)."""
    try:
        try:
            REFLECTIONS_TOTAL.labels("post_intent", "queued").inc()
        except Exception as e:
            logger.debug(f"Metric recording failed: {e}")
            # Metrics are non-critical
        if not _is_enabled():
            try:
                REFLECTIONS_TOTAL.labels("post_intent", "skipped").inc()
            except Exception:
                pass
            return
        _ = intent  # Future: attach intent context to reflection
        safe_create_task(
            _run_reflection(kind="post_intent", correlation_id=_get_cid_from_receipt(receipt)),
            name="reflection_post_intent",
        )
    except Exception:
        try:
            REFLECTIONS_TOTAL.labels("post_intent", "error").inc()
        except Exception:
            pass


def _get_cid_from_receipt(receipt: dict[str, Any] | None) -> str | None:
    try:
        if isinstance(receipt, dict):
            cid = receipt.get("correlation_id")
            if isinstance(cid, str) and cid.strip():
                return cid.strip()
    except Exception:
        return None
    return None


async def _run_reflection(kind: str, correlation_id: str | None = None) -> None:
    t0 = time.perf_counter()
    try:
        # Canonical reflection path (Dec 2025): derive a lightweight "reflection" from the
        # UnifiedDebuggingSystem traces/stats. This keeps reflection functional without
        # depending on legacy GAIA ReflectionEngine.
        result_summary: dict[str, Any] | None = None
        try:
            from kagami.core.debugging.unified_debugging_system import get_unified_debugging_system

            dbg = get_unified_debugging_system()
            if kind == "post_intent" and correlation_id:
                trace = dbg.get_trace(correlation_id)
                if trace is not None:
                    errors = getattr(trace, "detected_errors", None) or []
                    uncertainties = getattr(trace, "uncertainties", None) or []
                    result_summary = {
                        "confidence": float(getattr(trace, "confidence", 0.5)),
                        "insights_count": int(len(errors) + len(uncertainties)),
                    }
            elif kind == "periodic":
                stats = dbg.get_stats()
                acc = dbg.get_error_detection_accuracy()
                result_summary = {
                    "confidence": acc.get("accuracy"),
                    "insights_count": int(stats.get("errors_detected", 0)),
                    "active_traces": int(stats.get("active_traces", 0)),
                }
        except Exception:
            result_summary = None

        try:
            outcome = "completed" if result_summary is not None else "skipped"
            REFLECTIONS_TOTAL.labels(kind, outcome).inc()
        except Exception:
            pass

        try:
            from kagami.core.receipts.ingestor import add_receipt as _add_receipt

            _add_receipt(
                {
                    "correlation_id": correlation_id or "",
                    "action": f"reflection.{kind}",
                    "app": "introspection",
                    "args": {
                        "has_engine": bool(result_summary is not None),
                    },
                    "event": {
                        "name": (
                            "reflection.completed" if result_summary else "reflection.skipped"
                        ),
                        "data": {
                            "insights_count": (result_summary or {}).get("insights_count", 0),
                            "confidence": (result_summary or {}).get("confidence"),
                        },
                    },
                    "duration_ms": int(max(0.0, (time.perf_counter() - t0) * 1000)),
                }
            )
        except Exception:
            pass
    except Exception:
        try:
            REFLECTIONS_TOTAL.labels(kind, "error").inc()
        except Exception:
            pass
    finally:
        try:
            REFLECTION_DURATION_SECONDS.labels(kind).observe(max(0.0, time.perf_counter() - t0))
        except Exception:
            pass


_periodic_task: asyncio.Task | None = None


async def start_periodic_reflection_loop(interval_seconds: float = 600.0) -> None:
    """Start a periodic reflection loop (idempotent)."""
    global _periodic_task
    try:
        if _periodic_task and not _periodic_task.done():
            return

        async def _loop() -> None:
            try:
                while True:
                    await asyncio.sleep(max(1.0, float(interval_seconds)))
                    if not _is_enabled():
                        try:
                            REFLECTIONS_TOTAL.labels("periodic", "skipped").inc()
                        except Exception:
                            pass
                        continue
                    await _run_reflection(kind="periodic")
            except asyncio.CancelledError:
                return
            except Exception:
                # Best-effort: keep the loop resilient
                await asyncio.sleep(5.0)
                return

        _periodic_task = safe_create_task(_loop(), name="periodic_reflection_loop")
        try:
            REFLECTIONS_TOTAL.labels("periodic", "queued").inc()
        except Exception:
            pass
    except Exception:
        # non-fatal
        pass


async def stop_periodic_reflection_loop() -> None:
    """Stop the periodic reflection loop if running."""
    global _periodic_task
    try:
        if _periodic_task and not _periodic_task.done():
            _periodic_task.cancel()
            try:
                await _periodic_task
            except asyncio.CancelledError:
                pass
        _periodic_task = None
    except Exception:
        pass


__all__ = [
    "reflect_post_intent",
    "start_periodic_reflection_loop",
    "stop_periodic_reflection_loop",
]
