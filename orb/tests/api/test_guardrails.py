from __future__ import annotations


from types import SimpleNamespace

from kagami_api.guardrails import (
    GuardrailSnapshot,
    ensure_guardrail_snapshot,
    guardrails_dict,
    update_guardrails,
)


class DummyRequest:
    def __init__(self) -> None:
        self.state = SimpleNamespace()


def test_guardrail_snapshot_defaults() -> None:
    request = DummyRequest()
    snapshot = ensure_guardrail_snapshot(request)

    assert isinstance(snapshot, GuardrailSnapshot)
    assert guardrails_dict(request) == {
        "rbac": "unknown",
        "csrf": "unknown",
        "rate_limit": "unknown",
        "idempotency": "unknown",
        "feature_gate": "unknown",
    }


def test_update_guardrails_records_fields() -> None:
    request = DummyRequest()
    update_guardrails(request, rate_limit="enforced", idempotency="blocked")
    assert guardrails_dict(request)["rate_limit"] == "enforced"
    assert guardrails_dict(request)["idempotency"] == "blocked"
