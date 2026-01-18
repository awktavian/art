from __future__ import annotations

from typing import Any


def _canonicalize_phase(value: Any) -> str | None:
    """Map common phase synonyms to canonical plan/execute/verify."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    if s in {"plan", "planned", "simulate", "simulation"}:
        return "PLAN"
    if s in {"execute", "executed", "exec", "act", "acted", "action"}:
        return "EXECUTE"
    if s in {"verify", "verified", "valid", "validate", "validated", "complete", "completed"}:
        return "VERIFY"
    return str(value)


def infer_phase_from_receipt(receipt: dict[str, Any]) -> str:
    """Infer phase from receipt data if missing."""
    existing = _canonicalize_phase(receipt.get("phase"))
    if existing is not None and str(existing).strip():
        return str(existing)

    # Prefer explicit phase in event payload when present.
    event = receipt.get("event")
    if isinstance(event, dict):
        data = event.get("data")
        if isinstance(data, dict):
            payload_phase = _canonicalize_phase(data.get("phase"))
            if payload_phase is not None and str(payload_phase).strip():
                return str(payload_phase)

    # Fall back to event name heuristics.
    # CRITICAL: Check in order of specificity (VERIFY → EXECUTE → PLAN)
    # to avoid "intent.execute.verify" matching "execute" before "verify"
    event_name = str(
        (receipt.get("event") or {}).get("name") or receipt.get("event_name") or ""
    ).lower()

    # Check VERIFY first (most specific)
    if any(
        tok in event_name
        for tok in ("verify", "verified", "valid", "validated", "complete", "completed")
    ):
        return "VERIFY"

    # Then EXECUTE
    if any(tok in event_name for tok in ("exec", "execute", "executed", "act", "acted", "run")):
        return "EXECUTE"

    # Finally PLAN
    if any(tok in event_name for tok in ("plan", "planned")):
        return "PLAN"

    return "EXECUTE"  # Default


def infer_status_from_receipt(receipt: dict[str, Any]) -> str:
    """Infer status from receipt data."""
    if "status" in receipt:
        return str(receipt["status"])

    event = receipt.get("event", {})
    if event.get("status"):
        return str(event["status"])

    # Infer from error field
    if receipt.get("error") or event.get("error"):
        return "error"

    return "success"


def promote_phase_to_toplevel(receipt: dict[str, Any], phase: str) -> None:
    """Ensure phase is present at top level."""
    receipt["phase"] = phase


def promote_status_to_toplevel(receipt: dict[str, Any], status: str) -> None:
    """Ensure status is present at top level."""
    receipt["status"] = status
