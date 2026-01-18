from __future__ import annotations

"""
Shared helpers for Forge API endpoints.

Centralizes workspace hash derivation, guardrail snapshots, and request metadata
so every Forge surface emits consistent receipts.
"""

import os
from pathlib import Path
from typing import Any, TypedDict

from fastapi import Request
from kagami.core.receipts import emit_receipt as _emit_receipt
from kagami.core.self_preservation.checkpoint import EigenselfSnapshot, _compute_workspace_hash
from kagami.core.utils.ids import generate_correlation_id


class ForgeMetadata(TypedDict, total=False):
    correlation_id: str
    idempotency_key: str
    workspace_hash: str
    self_pointer: str
    guardrails: dict[str, str]


def _resolve_workspace_path() -> Path:
    env_path = os.getenv("KAGAMI_WORKSPACE")
    if env_path:
        try:
            return Path(env_path).expanduser().resolve()
        except Exception:
            return Path(env_path).expanduser()
    return Path.cwd()


def build_forge_metadata(
    request: Request | None, payload: dict[str, Any] | None = None
) -> ForgeMetadata:
    """Derive workspace hash, correlation id, and guardrails snapshot for Forge operations."""

    payload = payload or {}
    metadata: ForgeMetadata = {}

    correlation_id = str(payload.get("correlation_id") or generate_correlation_id("forge"))
    metadata["correlation_id"] = correlation_id

    idem_key = None
    if request is not None:
        idem_key = request.headers.get("Idempotency-Key") or request.headers.get(
            "X-Idempotency-Key"
        )
    if not idem_key:
        idem_key = payload.get("idempotency_key")
    if isinstance(idem_key, str) and idem_key.strip():
        metadata["idempotency_key"] = idem_key.strip()

    workspace_path = _resolve_workspace_path()
    workspace_hash = _compute_workspace_hash(workspace_path)
    metadata["workspace_hash"] = workspace_hash

    self_pointer = EigenselfSnapshot.compute_self_pointer(
        workspace_path=workspace_path,
        correlation_id=correlation_id,
        loop_depth=int(payload.get("loop_depth") or 0),
    )
    metadata["self_pointer"] = self_pointer

    guardrails = {
        "rbac": "allow",
        "csrf": _infer_csrf_state(request),
        "rate_limit": "ok",
        "idempotency": "accepted" if metadata.get("idempotency_key") else "missing",
    }
    metadata["guardrails"] = guardrails
    return metadata


def _infer_csrf_state(request: Request | None) -> str:
    if request is None:
        return "n/a"
    hdrs = request.headers
    if hdrs.get("X-API-Key") or hdrs.get("Authorization", "").startswith("Bearer "):
        return "n/a"
    if hdrs.get("X-CSRF-Token") and hdrs.get("X-Session-ID"):
        return "validated"
    return "n/a"


def emit_forge_receipt(
    action: str,
    meta: ForgeMetadata,
    *,
    event_name: str,
    event_data: dict[str, Any],
    duration_ms: int = 0,
    status: str = "success",
    args: dict[str, Any] | None = None,
    guardrails_override: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Emit a Forge receipt using normalized metadata."""

    args_payload = {"@app": "forge"}
    if args:
        args_payload.update(args)
    idem = meta.get("idempotency_key")
    if idem:
        args_payload["idempotency_key"] = idem

    guardrails = dict(meta.get("guardrails") or {})
    if guardrails_override:
        guardrails.update(guardrails_override)

    event_payload = dict(event_data or {})
    event_payload.setdefault("phase", "verify")

    return _emit_receipt(
        correlation_id=meta["correlation_id"],
        action=action,
        app="Forge",
        args=args_payload,
        event_name=event_name,
        event_data=event_payload,
        duration_ms=duration_ms,
        status=status,
        guardrails=guardrails,
        workspace_hash=meta["workspace_hash"],
        self_pointer=meta["self_pointer"],
    )


__all__ = ["build_forge_metadata", "emit_forge_receipt"]
