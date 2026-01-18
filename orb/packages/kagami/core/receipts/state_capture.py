"""State capture utilities for learning from receipts.

This module provides helpers to capture system state before/after operations,
enabling the world model to learn from actual operational data.

The learning loop:
1. Capture state_before intent execution
2. Execute intent
3. Capture state_after intent execution
4. Emit receipt with both states
5. World model trains on (state_before, action, state_after) tuples
6. Future predictions improve
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def capture_state_for_learning(
    intent: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Capture system state for learning.

    Encodes the current system state into a compact representation
    that can be embedded by the world model.

    Args:
        intent: The intent being executed
        context: Optional additional context

    Returns:
        State dictionary with:
        - action: Action being taken
        - params: Key parameters
        - timestamp: When captured
        - context_hash: Quick identifier for context similarity
    """
    try:
        action = intent.get("action") or intent.get("intent", "unknown")
        params = intent.get("params", {})
        app = intent.get("app", "unknown")
        metadata = intent.get("metadata", {})

        # Create compact state representation
        params_keys: list[str] = [str(k) for k in params.keys()] if isinstance(params, dict) else []
        state: dict[str, Any] = {
            "action": str(action),
            "app": str(app),
            "params_keys": params_keys,
            "timestamp": time.time(),
            "metadata": {
                "complexity": metadata.get("complexity", "normal"),
                "user_id": metadata.get("user_id"),
                "source": (
                    metadata.get("context", {}).get("source")
                    if isinstance(metadata.get("context"), dict)
                    else None
                ),
            },
        }

        # Add context if provided
        if context:
            state["context"] = context

        # Generate context hash for similarity matching
        # Simple hash of action + app + params structure
        context_str = f"{action}:{app}:{','.join(sorted(params_keys))}"
        state["context_hash"] = str(abs(hash(context_str)) % 10**8)

        # Emit metric
        try:
            from kagami_observability.metrics.intelligence import STATE_CAPTURE_TOTAL

            STATE_CAPTURE_TOTAL.labels(capture_type="before").inc()
        except Exception:
            pass  # Don't fail on metrics

        return state

    except Exception as e:
        logger.warning(f"State capture failed: {e}")
        try:
            from kagami_observability.metrics.receipts import RECEIPT_WRITE_ERRORS_TOTAL

            RECEIPT_WRITE_ERRORS_TOTAL.labels(error_type="state_capture_failed").inc()
        except Exception:
            pass
        # Return minimal state on failure
        return {
            "action": "unknown",
            "app": "unknown",
            "timestamp": time.time(),
            "context_hash": "0",
            "error": str(e),
        }


def extract_state_from_result(
    result: dict[str, Any],
    state_before: dict[str, Any],
) -> dict[str, Any]:
    """Extract state after operation from result.

    Args:
        result: The operation result
        state_before: The pre-operation state

    Returns:
        State dictionary representing post-operation state
    """
    try:
        # Copy base state structure
        state_after = {
            "action": state_before.get("action"),
            "app": state_before.get("app"),
            "timestamp": time.time(),
            "context_hash": state_before.get("context_hash"),
        }

        # Add outcome information
        if isinstance(result, dict):
            state_after["status"] = result.get("status", "unknown")
            state_after["success"] = result.get("status") in ("success", "accepted", "completed")

            # Capture key result properties
            if "error" in result:
                state_after["error"] = str(result["error"])[:200]  # Truncate long errors

            if "response" in result:
                # Capture response type/size, not full content
                response = result["response"]
                if isinstance(response, (str, bytes)):
                    state_after["response_size"] = len(response)
                    state_after["response_type"] = type(response).__name__
                elif isinstance(response, dict):
                    state_after["response_keys"] = list(response.keys())[:10]  # Max 10 keys

        # Emit metric
        try:
            from kagami_observability.metrics.intelligence import STATE_CAPTURE_TOTAL

            STATE_CAPTURE_TOTAL.labels(capture_type="after").inc()
        except Exception:
            pass  # Don't fail on metrics

        return state_after

    except Exception as e:
        logger.warning(f"State extraction from result failed: {e}")
        try:
            from kagami_observability.metrics.receipts import RECEIPT_WRITE_ERRORS_TOTAL

            RECEIPT_WRITE_ERRORS_TOTAL.labels(error_type="state_extraction_failed").inc()
        except Exception:
            pass
        return {
            **state_before,
            "timestamp": time.time(),
            "error": str(e),
        }


def should_capture_state(intent: dict[str, Any]) -> bool:
    """Determine if state should be captured for this intent.

    Skip state capture for:
    - Read-only operations (query, get, list[Any])
    - Health checks
    - Metrics endpoints

    Args:
        intent: The intent to check

    Returns:
        True if state should be captured
    """
    action = str(intent.get("action", "")).lower()

    # Skip read-only operations
    if action.startswith(("query.", "get.", "list[Any].", "search.", "read.")):
        return False

    # Skip infrastructure operations
    if action.startswith(("health.", "metrics.", "ping.")):
        try:
            from kagami_observability.metrics.intelligence import STATE_CAPTURE_SKIPPED_TOTAL

            STATE_CAPTURE_SKIPPED_TOTAL.labels(reason="infrastructure").inc()
        except Exception:
            pass
        return False

    # Capture for all other operations
    return True


__all__ = [
    "capture_state_for_learning",
    "extract_state_from_result",
    "should_capture_state",
]
