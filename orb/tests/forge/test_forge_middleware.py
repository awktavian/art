from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.core.exceptions import ValidationError
from kagami.forge.schema import CharacterRequest


class _StubValidator:
    def __init__(self, errors: list[str] | None = None) -> None:
        self._errors = errors or []

    def validate_request(self, request: CharacterRequest) -> list[str]:
        return list(self._errors)

    async def moderate_content(self, text: str) -> dict[str, object]:
        return {"flagged": False, "reason": None, "categories": []}

    def validate_result(self, result: Any) -> Dict[str, Any]:
        return {"overall_score": 0.87}


class _StubSafetyGate:
    async def evaluate_ethical(self, context: Any) -> Dict[str, Any]:
        return {"permissible": True, "reason": None, "principle_violated": None}

    async def assess_threat(self, context: Any) -> Dict[str, Any]:
        return {"score": 0.2, "requires_confirmation": False, "reason": None}


@pytest.mark.asyncio
async def test_forge_operation_emits_receipts(monkeypatch: Any) -> Any:
    from kagami.forge import forge_middleware

    events: list[dict] = []

    def fake_emit_receipt(**payload) -> Any:
        events.append(payload)
        return payload

    monkeypatch.setattr(forge_middleware, "emit_receipt", fake_emit_receipt)
    monkeypatch.setattr(forge_middleware, "get_validator", lambda: _StubValidator())
    monkeypatch.setattr(forge_middleware, "get_safety_gate", lambda: _StubSafetyGate())

    class SampleService:
        @forge_middleware.forge_operation("unit_test", module="forge.test", aspect="sample")
        async def run(self, request: CharacterRequest):
            return {"status": "ok", "overall_quality": 0.91, "request_id": request.request_id}

    request = CharacterRequest(
        concept="Test avatar",
        metadata={"idempotency_key": "key-123", "correlation_id": "cor-1"},
    )

    service = SampleService()
    result = await service.run(request)

    assert result["validation"]["overall_score"] == pytest.approx(0.87)
    assert len(events) == 3
    assert [evt["event_name"] for evt in events] == [
        "forge.unit_test.plan",
        "forge.unit_test.execute",
        "forge.unit_test.verify",
    ]
    assert events[1]["event_data"]["guardrails"]["idempotency"] == "accepted"
    assert events[2]["event_data"]["validation"]["overall_score"] == pytest.approx(0.87)


@pytest.mark.asyncio
async def test_forge_operation_blocks_invalid_requests(monkeypatch: Any) -> None:
    from kagami.forge import forge_middleware

    monkeypatch.setattr(
        forge_middleware,
        "get_validator",
        lambda: _StubValidator(errors=["Concept must be at least 3 characters"]),
    )
    monkeypatch.setattr(forge_middleware, "get_safety_gate", lambda: _StubSafetyGate())
    monkeypatch.setattr(forge_middleware, "emit_receipt", lambda **_: {})

    class SampleService:
        def __init__(self) -> None:
            self.called = False

        @forge_middleware.forge_operation("unit_test", module="forge.test")
        async def run(self, request: CharacterRequest):
            self.called = True
            return {"status": "ok", "request_id": request.request_id}

    svc = SampleService()
    request = CharacterRequest(concept="no")

    with pytest.raises(ValidationError) as excinfo:
        await svc.run(request)

    assert "invalid" in str(excinfo.value).lower()
    assert svc.called is False
