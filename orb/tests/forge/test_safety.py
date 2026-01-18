"""Comprehensive tests for forge safety module.

Tests SafetyGate class and safety evaluation methods.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.forge.safety import SafetyGate, get_safety_gate


class TestSafetyGate:
    """Test SafetyGate class."""

    @pytest.fixture
    def safety_gate(self):
        return SafetyGate()

    @pytest.mark.asyncio
    async def test_evaluate_ethical_permissible(self, safety_gate: Any, monkeypatch: Any) -> None:
        """Test ethical evaluation permits safe operations."""

        class MockVerdict:
            permissible = True
            reasoning = "Operation is safe"
            principle_violated = None
            severity = "low"

        class MockEthicalInstinct:
            async def evaluate(self, context: Any) -> Any:
                return MockVerdict()

        # Mock the lazy loading
        async def mock_get_ethical():
            return MockEthicalInstinct()

        monkeypatch.setattr(safety_gate, "_get_ethical_instinct", mock_get_ethical)

        result = await safety_gate.evaluate_ethical({"action": "generate_character"})

        assert result["permissible"] is True
        assert result["reason"] == "Operation is safe"

    @pytest.mark.asyncio
    async def test_evaluate_ethical_blocked(self, safety_gate: Any, monkeypatch: Any) -> Any:
        """Test ethical evaluation blocks unsafe operations."""

        class MockVerdict:
            permissible = False
            reasoning = "Violates principle"
            principle_violated = "harm_prevention"
            severity = "high"

        class MockEthicalInstinct:
            async def evaluate(self, context: Any) -> Any:
                return MockVerdict()

        async def mock_get_ethical():
            return MockEthicalInstinct()

        monkeypatch.setattr(safety_gate, "_get_ethical_instinct", mock_get_ethical)

        result = await safety_gate.evaluate_ethical({"action": "harmful_action"})

        assert result["permissible"] is False
        assert result["principle_violated"] == "harm_prevention"

    @pytest.mark.asyncio
    async def test_evaluate_ethical_failure_fails_safe(
        self, safety_gate: Any, monkeypatch: Any
    ) -> Any:
        """Test ethical evaluation fails safe on error."""

        class FailingEthical:
            async def evaluate(self, context: Any) -> None:
                raise Exception("Evaluation failed")

        async def mock_get_ethical():
            return FailingEthical()

        monkeypatch.setattr(safety_gate, "_get_ethical_instinct", mock_get_ethical)

        result = await safety_gate.evaluate_ethical({"action": "test"})

        assert result["permissible"] is False
        assert "failing safe" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_assess_threat_low(self, safety_gate: Any, monkeypatch: Any) -> None:
        """Test threat assessment for low-risk operations."""

        class MockAssessment:
            value = 0.2
            components = ["scope_limited"]
            recommendation = "Proceed normally"

        class MockThreatInstinct:
            async def evaluate_incoming_intent(self, context: Any) -> Any:
                return MockAssessment()

        class MockAffectiveLayer:
            threat = MockThreatInstinct()

        async def mock_get_threat():
            return MockThreatInstinct()

        monkeypatch.setattr(safety_gate, "_get_threat_instinct", mock_get_threat)

        result = await safety_gate.assess_threat({"action": "read_only", "destructive": False})

        assert result["score"] == 0.2
        assert result["requires_confirmation"] is False

    @pytest.mark.asyncio
    async def test_assess_threat_high(self, safety_gate: Any, monkeypatch: Any) -> Any:
        """Test threat assessment for high-risk operations."""

        class MockAssessment:
            value = 0.9
            components = ["destructive", "irreversible"]
            recommendation = "Requires confirmation"

        class MockThreatInstinct:
            async def evaluate_incoming_intent(self, context: Any) -> Any:
                return MockAssessment()

        async def mock_get_threat():
            return MockThreatInstinct()

        monkeypatch.setattr(safety_gate, "_get_threat_instinct", mock_get_threat)

        result = await safety_gate.assess_threat(
            {"action": "delete_all", "destructive": True, "irreversible": True}
        )

        assert result["score"] == 0.9
        assert result["requires_confirmation"] is True

    @pytest.mark.asyncio
    async def test_assess_threat_failure_fails_safe(
        self, safety_gate: Any, monkeypatch: Any
    ) -> Any:
        """Test threat assessment fails safe on error."""

        class FailingThreat:
            async def evaluate_incoming_intent(self, context: Any) -> None:
                raise Exception("Assessment failed")

        async def mock_get_threat():
            return FailingThreat()

        monkeypatch.setattr(safety_gate, "_get_threat_instinct", mock_get_threat)

        result = await safety_gate.assess_threat({"action": "test"})

        assert result["score"] == 0.9
        assert result["requires_confirmation"] is True
        assert "failing safe" in result["reason"].lower()


class TestGetSafetyGate:
    """Test safety gate singleton."""

    def test_get_safety_gate_singleton(self) -> None:
        """Test get_safety_gate returns same instance."""
        g1 = get_safety_gate()
        g2 = get_safety_gate()
        assert g1 is g2

    def test_get_safety_gate_type(self) -> None:
        """Test get_safety_gate returns SafetyGate."""
        g = get_safety_gate()
        assert isinstance(g, SafetyGate)
