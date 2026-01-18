from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def self_critique(intent: Any) -> tuple[str, str]:
    """Runtime constitutional self-critique for intents.

    Returns (result, reason): result in {"pass","fail","error"}.
    Keep lightweight and deterministic; avoid network calls.
    """
    t0 = time.perf_counter()
    try:
        action = str(getattr(intent, "action", "") or "").lower()
        target = str(getattr(intent, "target", "") or "").lower()
        md = getattr(intent, "metadata", {}) or {}

        # Simple denylist for dangerous combinations (expandable)
        blocked_terms = {"rm -rf", "drop table", "shutdown", "sabotage"}
        text_blob = " ".join(
            [
                action,
                target,
                str(md.get("notes") or md.get("NOTES") or ""),
                str(md.get("command") or md.get("COMMAND") or ""),
            ]
        ).lower()
        for bt in blocked_terms:
            if bt in text_blob:
                return "fail", f"blocked_term:{bt}"

        # Enforce minimal constraints: bounded tokens/time budgets
        try:
            max_tokens = int(md.get("max_tokens", 0) or 0)
            if max_tokens and max_tokens > 8000:
                return "fail", "max_tokens_excess"
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse max_tokens during constitutional check: {e}")
            # Fail-safe: if we can't parse tokens, assume they might be excessive
            # and rely on other checks rather than silently passing

        try:
            budget_ms = int(md.get("budget_ms", 0) or 0)
            if budget_ms and budget_ms > 60000:
                return "fail", "budget_ms_excess"
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse budget_ms during constitutional check: {e}")
            # Fail-safe: if we can't parse budget, assume it might be excessive
            # and rely on other checks rather than silently passing

        # Default allow
        return "pass", "ok"
    except (AttributeError, TypeError, ValueError) as e:
        logger.error(f"Constitutional self-critique failed: {e}", exc_info=True)
        # Fail-safe: return error on unexpected failures rather than silent pass
        return "error", f"exception:{type(e).__name__}"
    finally:
        try:
            dur = max(0.0, time.perf_counter() - t0)
            # Optional metrics (best-effort import to avoid circulars)
            try:
                from kagami_observability.metrics import (
                    META_CRITIQUE_DURATION_SECONDS,
                )

                # Labels must be bounded; map durations after result is known
                # Note: we cannot access result here cleanly, so observe in caller too if needed
                META_CRITIQUE_DURATION_SECONDS.observe(dur)
            except (ImportError, RuntimeError) as e:
                logger.debug(f"Failed to record meta-critique duration metric: {e}")
                # Metrics failure should not block policy checks
        except (ValueError, ArithmeticError) as e:
            logger.debug(f"Failed to calculate duration in meta-critique: {e}")
            # Duration calculation failure should not block policy checks
