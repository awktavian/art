from __future__ import annotations

from dataclasses import asdict, dataclass
from types import SimpleNamespace
from typing import Any


@dataclass
class GuardrailSnapshot:
    """Mutable snapshot stored on Request.state."""

    rbac: str = "unknown"
    csrf: str = "unknown"
    rate_limit: str = "unknown"
    idempotency: str = "unknown"
    feature_gate: str = "unknown"


def ensure_guardrail_snapshot(request: Any) -> GuardrailSnapshot:
    """Ensure a guardrail snapshot is attached to the request state."""

    state = getattr(request, "state", None)
    if state is None:
        state = SimpleNamespace()
        request.state = state

    snapshot = getattr(state, "_guardrail_snapshot", None)
    if snapshot is None:
        snapshot = GuardrailSnapshot()
        state._guardrail_snapshot = snapshot
    return snapshot


def update_guardrails(request: Any, **fields: str | None) -> GuardrailSnapshot:
    """Update guardrail fields on the request snapshot.

    Args:
        request: The request object to update
        **fields: Field names and values (None values are skipped)
    """
    snapshot = ensure_guardrail_snapshot(request)
    for key, value in fields.items():
        if value is None:
            continue
        if hasattr(snapshot, key):
            setattr(snapshot, key, str(value))
    return snapshot


def guardrails_dict(request: Any) -> dict[str, str]:
    """Return the current guardrail snapshot as a dict."""

    snapshot = ensure_guardrail_snapshot(request)
    return asdict(snapshot)


__all__ = ["GuardrailSnapshot", "ensure_guardrail_snapshot", "guardrails_dict", "update_guardrails"]
