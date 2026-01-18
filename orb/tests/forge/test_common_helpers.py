from __future__ import annotations


from typing import Any

from starlette.requests import Request

from kagami_api.routes.forge_common import build_forge_metadata, emit_forge_receipt


def _make_request(headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": "POST",
        "scheme": "https",
        "path": "/api/forge/generate",
        "headers": [
            (key.lower().encode("latin-1"), value.encode("latin-1"))
            for key, value in (headers or {}).items()
        ],
    }
    return Request(scope)


def test_build_forge_metadata_with_idempotency():
    req = _make_request({"Idempotency-Key": "forge-test-123"})
    meta = build_forge_metadata(req, {"correlation_id": "forge-cid-1"})

    assert meta["correlation_id"] == "forge-cid-1"
    assert meta["idempotency_key"] == "forge-test-123"
    assert meta["guardrails"]["idempotency"] == "accepted"
    assert len(meta["workspace_hash"]) == 16
    assert len(meta["self_pointer"]) == 16


def test_build_forge_metadata_without_request_marks_missing():
    meta = build_forge_metadata(None, {})

    assert "idempotency_key" not in meta
    assert meta["guardrails"]["idempotency"] == "missing"
    assert len(meta["workspace_hash"]) == 16
    assert len(meta["self_pointer"]) == 16
    assert meta["correlation_id"]


def test_emit_forge_receipt_uses_metadata(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_emit_receipt(**kwargs) -> Dict[str, Any]:
        captured["payload"] = kwargs
        return {"receipt": "ok"}

    # Patch the import reference in forge_common module directly
    import kagami_api.routes.forge_common as forge_common_module

    monkeypatch.setattr(forge_common_module, "_emit_receipt", fake_emit_receipt)

    meta = build_forge_metadata(None, {"correlation_id": "forge-test"})
    meta["guardrails"]["csrf"] = "validated"

    receipt = emit_forge_receipt(
        action="forge.test.action",
        meta=meta,
        event_name="forge.test.action.verify",
        event_data={"status": "success"},
        duration_ms=42,
        args={"foo": "bar"},
        guardrails_override={"idempotency": "accepted"},
    )

    assert receipt == {"receipt": "ok"}
    payload = captured["payload"]
    assert payload["action"] == "forge.test.action"
    assert payload["guardrails"]["idempotency"] == "accepted"
    assert payload["args"]["foo"] == "bar"
