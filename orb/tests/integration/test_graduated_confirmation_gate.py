
from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration


from kagami.core.safety.graduated_confirmation import GraduatedConfirmationGate


@pytest.mark.asyncio
async def test_low_risk_auto_approve():
    gate = GraduatedConfirmationGate()
    action = {"tool": "edit_file", "correlation_id": "c-test"}
    risk = {"risk_level": "low", "risk_score": 0.1}
    decision = await gate.apply_gate(action, risk)
    assert decision.proceed is True
    assert decision.confirmation_required is False
    assert decision.risk_level == "low"


@pytest.mark.asyncio
async def test_medium_risk_warning():
    gate = GraduatedConfirmationGate()
    action = {"tool": "run_terminal_cmd", "correlation_id": "c-test"}
    risk = {
        "risk_level": "medium",
        "risk_score": 0.5,
        "predicted_failures": ["timeout"],
    }
    decision = await gate.apply_gate(action, risk)
    assert decision.proceed is True
    assert decision.confirmation_required is False
    assert decision.risk_level == "medium"
    assert decision.warnings == ["timeout"]


@pytest.mark.asyncio
async def test_high_risk_requires_confirmation():
    gate = GraduatedConfirmationGate()
    action = {"tool": "delete_file", "correlation_id": "c-test"}
    risk = {
        "risk_level": "high",
        "risk_score": 0.9,
        "predicted_failures": ["data_loss"],
        "mitigations": ["backup"],
    }
    decision = await gate.apply_gate(action, risk)
    assert decision.proceed is False
    assert decision.confirmation_required is True
    assert decision.risk_level == "high"
    assert "data_loss" in (decision.message or "")
