"""Helper functions for socketio_server.py IntentNamespace.on_execute.

Extracted from on_execute (complexity 94 → <30).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_idempotency_key(data: dict[str, Any]) -> str | None:
    """Extract idempotency key from WebSocket message data.

    Args:
        data: Message data dict

    Returns:
        Idempotency key string or None
    """
    try:
        return str(data.get("Idempotency-Key") or data.get("idempotency_key") or "").strip() or None
    except Exception:
        return None


def is_mutation_intent(intent: Any) -> bool:
    """Determine if intent is a mutation requiring idempotency.

    Args:
        intent: Intent data (string or dict)

    Returns:
        True if mutation, False if read-only
    """
    try:
        if isinstance(intent, str):
            return True
        elif isinstance(intent, dict):
            return not bool(intent.get("preview"))
        return True
    except Exception:
        return True


async def emit_idempotency_blocked_receipt(intent: Any, sid: str) -> None:
    """Emit receipt for blocked WebSocket mutation (missing idempotency key).

    Args:
        intent: Intent that was blocked
        sid: Session ID
    """
    try:
        import uuid

        from kagami.core.receipts import emit_receipt

        intent_dict = intent if isinstance(intent, dict) else {}
        blocked_cid = intent_dict.get("correlation_id") or uuid.uuid4().hex
        intent_dict["correlation_id"] = blocked_cid
        emit_receipt(
            correlation_id=blocked_cid,
            action=str(intent_dict.get("action") or "ws.intent.execute"),
            app=str(intent_dict.get("app") or "socketio"),
            args={"source": "websocket", "sid": sid},
            event_name="operation.verified",
            event_data={
                "phase": "verify",
                "status": "blocked",
                "reason": "idempotency_key_required",
            },
            status="blocked",
        )
    except Exception:
        pass


def build_error_response(
    code: str, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build standardized error response for WebSocket.

    Args:
        code: Error code
        message: Error message
        details: Optional additional details

    Returns:
        Error response dict
    """
    response = {"code": code, "message": message}
    if details:
        response["details"] = details  # type: ignore[assignment]
    return response


def parse_intent_to_orch_format(intent: Any) -> dict[str, Any]:
    """Parse intent into orchestrator format.

    Args:
        intent: Raw intent (string or dict)

    Returns:
        Orchestrator-compatible intent dict

    Raises:
        ValueError: If intent format is unsupported
    """
    if isinstance(intent, str):
        # LANG/2 string format
        return {"action": intent, "app": "chat", "metadata": {}}
    elif isinstance(intent, dict):
        action = str(intent.get("action") or intent.get("command") or "").strip()
        app = str(intent.get("app") or "").strip()
        target = intent.get("target")
        metadata = dict(intent.get("metadata") or {})
        return {"action": action, "app": app, "target": target, "metadata": metadata}
    else:
        raise ValueError("Unsupported intent payload")


async def handle_ws_idempotency(
    idem_key: str | None, user_id: str, is_mutation: bool
) -> tuple[str, str | None]:
    """Handle WebSocket idempotency check.

    Args:
        idem_key: Idempotency key from request
        user_id: User ID
        is_mutation: Whether this is a mutation operation

    Returns:
        Tuple of (status, error_message) where status is 'ok', 'missing', 'duplicate', or 'error'
    """
    if not is_mutation:
        return ("ok", None)

    if not idem_key:
        _inc_ws_metric("missing_key")
        return ("missing", "Mutations require Idempotency-Key")

    try:
        from kagami.core.receipts import ensure_ws_idempotency as _ws_idem

        session_key = f"{user_id}:socketio.intent"
        result = await _ws_idem(session_key, idem_key, ttl_seconds=300)
        if result == "duplicate":
            _inc_ws_metric("duplicate")
            return ("duplicate", "duplicate_request")
        _inc_ws_metric("accepted")
        return ("ok", None)
    except Exception:
        _inc_ws_metric("backend_unavailable")
        return ("ok", None)  # Fail-open


def _inc_ws_metric(label: str) -> None:
    """Increment WebSocket idempotency metric with error handling."""
    try:
        from kagami.observability.metrics import WS_IDEMPOTENCY_CHECKS_TOTAL

        WS_IDEMPOTENCY_CHECKS_TOTAL.labels(label).inc()
    except Exception:
        pass


class PolicyWrapper:
    """Lightweight wrapper for policy modules."""

    def __init__(self, intent: dict[str, Any]):
        self.action = intent.get("action")
        self.target = intent.get("app") or intent.get("target")
        self.metadata = intent.get("metadata") or {}


async def apply_policy_gates(orch_intent: dict[str, Any]) -> tuple[str, str, str | None]:
    """Apply constitution and CBF policy gates.

    Args:
        orch_intent: Orchestrator intent dict

    Returns:
        Tuple of (constitution_verdict, cbf_decision, cbf_reason)
    """
    constitution_verdict = "pass"
    cbf_decision = "ok"
    cbf_reason = None

    try:
        from kagami.observability.metrics import CBF_BLOCKS_TOTAL, META_CRITIQUES_TOTAL
        from kagami.policy.cbf import enforce as _cbf_enforce
        from kagami.policy.constitution import self_critique as _self_crit

        wrapper = PolicyWrapper(orch_intent)

        # Constitution check
        verdict, reason = _self_crit(wrapper)
        constitution_verdict = verdict
        try:
            META_CRITIQUES_TOTAL.labels(verdict).inc()
        except Exception:
            pass
        if verdict == "fail":
            return (verdict, "blocked", reason)

        # CBF enforcement
        decision, changes = _cbf_enforce(wrapper)
        cbf_decision = decision
        cbf_reason = str(changes.get("reason")) if isinstance(changes, dict) else None

        if decision in {"adjusted", "blocked"}:
            try:
                CBF_BLOCKS_TOTAL.labels(
                    decision,
                    cbf_reason
                    or ("adjusted" if decision == "adjusted" else "constraint_violation"),
                ).inc()
            except Exception:
                pass

        # Update metadata from wrapper
        try:
            orch_intent["metadata"] = dict(getattr(wrapper, "metadata", {}) or {})
        except Exception:
            pass

    except Exception:
        pass  # Fail-open

    return (constitution_verdict, cbf_decision, cbf_reason)


def emit_intent_plan_receipt(orch_intent: dict[str, Any], sid: str, idem_key: str | None) -> str:
    """Emit PLAN receipt for WebSocket intent.

    Args:
        orch_intent: Orchestrator intent
        sid: Session ID
        idem_key: Idempotency key

    Returns:
        Correlation ID
    """
    import uuid

    from kagami.core.receipts import emit_receipt

    cid = orch_intent.get("correlation_id") or uuid.uuid4().hex
    orch_intent["correlation_id"] = cid

    try:
        emit_receipt(
            correlation_id=cid,
            action=orch_intent.get("action", "ws.intent.execute"),
            app=orch_intent.get("app", "socketio"),
            args={"source": "websocket", "sid": sid},
            event_name="PLAN",
            event_data={"status": "planning"},
            guardrails={
                "rbac": "allow",
                "csrf": "n/a",
                "rate_limit": "ok",
                "idempotency": "accepted" if idem_key else "n/a",
            },
        )
    except Exception:
        pass

    return cid


def emit_intent_execute_receipt(
    orch_intent: dict[str, Any],
    result: Any,
    sid: str,
    idem_key: str | None,
    constitution_verdict: str,
    cbf_decision: str,
    cbf_reason: str | None,
    duration_ms: int,
) -> str:
    """Emit EXECUTE receipt for completed intent.

    Returns:
        Correlation ID
    """
    import uuid

    from kagami.core.receipts import emit_receipt

    correlation_id = (
        str(result.get("correlation_id")) if isinstance(result, dict) else None
    ) or uuid.uuid4().hex

    try:
        emit_receipt(
            correlation_id=correlation_id,
            action="intent.execute",
            app=orch_intent.get("app") or None,
            args={
                "source": "socketio",
                "sid": sid,
                "payload_type": "dict",
            },
            event_name="intent.executed",
            event_data={
                "status": result.get("status") if isinstance(result, dict) else None,
                "action": orch_intent.get("action"),
                "app": orch_intent.get("app"),
            },
            duration_ms=duration_ms,
            guardrails={
                "rbac": "allow",
                "csrf": "validated",
                "rate_limit": "ok",
                "idempotency": "accepted" if idem_key else "n/a",
                "constitution": constitution_verdict,
                "cbf": cbf_decision if not cbf_reason else f"{cbf_decision}:{cbf_reason}",
            },
        )
    except Exception:
        pass

    return correlation_id


def emit_blocked_verify_receipt(orch_intent: dict[str, Any], sid: str, reason: str) -> None:
    """Emit VERIFY receipt for blocked intent."""
    try:
        from kagami.core.receipts import emit_receipt

        emit_receipt(
            correlation_id=str(orch_intent.get("correlation_id")),
            action=str(orch_intent.get("action") or "ws.intent.execute"),
            app=str(orch_intent.get("app") or "socketio"),
            args={"source": "websocket", "sid": sid},
            event_name="operation.verified",
            event_data={"phase": "verify", "status": "blocked", "reason": reason},
            status="blocked",
        )
    except Exception:
        pass
