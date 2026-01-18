"""Tests for kagami.forge.safety (SafetyGate)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kagami.forge.safety import SafetyGate, get_safety_gate

pytestmark = pytest.mark.tier_integration


@pytest.fixture
def safety_gate():
    """Create SafetyGate instance."""
    return SafetyGate()


@pytest.fixture
def mock_ethical_instinct():
    """Create mock JailbreakDetector."""
    detector = MagicMock()
    verdict = MagicMock()
    verdict.permissible = True
    verdict.reasoning = "Operation is safe"
    verdict.principle_violated = None
    verdict.severity = "low"
    detector.evaluate = AsyncMock(return_value=verdict)
    return detector


@pytest.fixture
def mock_threat_instinct():
    """Create mock threat assessment."""
    threat = MagicMock()
    assessment = MagicMock()
    assessment.value = 0.3
    assessment.components = {"destructive": 0.1, "irreversible": 0.2}
    assessment.recommendation = "Proceed with caution"
    threat.evaluate_incoming_intent = AsyncMock(return_value=assessment)
    return threat


class TestSafetyGateInitialization:
    """Test SafetyGate initialization."""

    def test_init(self):
        """Test SafetyGate initialization."""
        gate = SafetyGate()
        assert gate._ethical_instinct is None
        assert gate._threat_instinct is None

    @pytest.mark.asyncio
    async def test_lazy_load_ethical_instinct(self, safety_gate):
        """Test lazy loading of ethical instinct."""
        with patch("kagami.core.security.jailbreak_detector.JailbreakDetector") as mock:
            mock.return_value = MagicMock()

            instinct = await safety_gate._get_ethical_instinct()
            assert instinct is not None
            assert safety_gate._ethical_instinct is not None

    @pytest.mark.asyncio
    async def test_lazy_load_threat_instinct(self, safety_gate):
        """Test lazy loading of threat instinct."""
        with patch("kagami.core.affective.AffectiveLayer") as mock:
            affective = MagicMock()
            affective.threat = MagicMock()
            mock.return_value = affective

            instinct = await safety_gate._get_threat_instinct()
            assert instinct is not None
            assert safety_gate._threat_instinct is not None


class TestEthicalEvaluation:
    """Test ethical evaluation."""

    @pytest.mark.asyncio
    async def test_evaluate_ethical_permissible(self, safety_gate, mock_ethical_instinct):
        """Test ethical evaluation when operation is permissible."""
        safety_gate._ethical_instinct = mock_ethical_instinct

        context = {
            "action": "generate_character",
            "concept": "warrior",
            "estimated_cost": 0.5,
        }

        result = await safety_gate.evaluate_ethical(context)

        assert result["permissible"] is True
        assert result["reason"] == "Operation is safe"
        assert result["principle_violated"] is None

    @pytest.mark.asyncio
    async def test_evaluate_ethical_not_permissible(self, safety_gate):
        """Test ethical evaluation when operation is not permissible."""
        mock_detector = MagicMock()
        verdict = MagicMock()
        verdict.permissible = False
        verdict.reasoning = "Violates ethical guidelines"
        verdict.principle_violated = "harm_prevention"
        verdict.severity = "high"
        mock_detector.evaluate = AsyncMock(return_value=verdict)

        safety_gate._ethical_instinct = mock_detector

        context = {"action": "dangerous_operation"}

        result = await safety_gate.evaluate_ethical(context)

        assert result["permissible"] is False
        assert "Violates ethical" in result["reason"]
        assert result["principle_violated"] == "harm_prevention"
        assert result["severity"] == "high"

    @pytest.mark.asyncio
    async def test_evaluate_ethical_with_metrics(self, safety_gate, mock_ethical_instinct):
        """Test that ethical evaluation records metrics."""
        mock_detector = MagicMock()
        verdict = MagicMock()
        verdict.permissible = False
        verdict.principle_violated = "test_principle"
        mock_detector.evaluate = AsyncMock(return_value=verdict)

        safety_gate._ethical_instinct = mock_detector

        with patch("kagami.forge.safety.ETHICAL_BLOCKS_TOTAL") as mock_metric:
            await safety_gate.evaluate_ethical({"action": "test"})

            # Should record blocked operation
            mock_metric.labels.assert_called()

    @pytest.mark.asyncio
    async def test_evaluate_ethical_exception_handling(self, safety_gate):
        """Test ethical evaluation handles exceptions (fail closed)."""
        mock_detector = MagicMock()
        mock_detector.evaluate = AsyncMock(side_effect=RuntimeError("Evaluation failed"))

        safety_gate._ethical_instinct = mock_detector

        result = await safety_gate.evaluate_ethical({"action": "test"})

        # Should fail closed (not permissible)
        assert result["permissible"] is False
        assert "Evaluation failed" in result["reason"]
        assert result["principle_violated"] == "evaluation_failure"
        assert result["severity"] == "high"


class TestThreatAssessment:
    """Test threat assessment."""

    @pytest.mark.asyncio
    async def test_assess_threat_low_risk(self, safety_gate, mock_threat_instinct):
        """Test threat assessment for low-risk operation."""
        safety_gate._threat_instinct = mock_threat_instinct

        context = {
            "action": "generate_character",
            "destructive": False,
            "irreversible": False,
            "scope": "local",
            "privilege": "user",
        }

        result = await safety_gate.assess_threat(context)

        assert result["score"] == 0.3
        assert result["requires_confirmation"] is False
        assert "components" in result

    @pytest.mark.asyncio
    async def test_assess_threat_high_risk(self, safety_gate):
        """Test threat assessment for high-risk operation."""
        mock_threat = MagicMock()
        assessment = MagicMock()
        assessment.value = 0.85  # High threat score
        assessment.components = {"destructive": 0.9, "irreversible": 0.8}
        assessment.recommendation = "Requires confirmation"
        mock_threat.evaluate_incoming_intent = AsyncMock(return_value=assessment)

        safety_gate._threat_instinct = mock_threat

        context = {
            "action": "delete_data",
            "destructive": True,
            "irreversible": True,
        }

        result = await safety_gate.assess_threat(context)

        assert result["score"] == 0.85
        assert result["requires_confirmation"] is True

    @pytest.mark.asyncio
    async def test_assess_threat_confirmation_threshold(self, safety_gate, mock_threat_instinct):
        """Test threat assessment confirmation threshold."""
        mock_threat = MagicMock()
        assessment = MagicMock()
        assessment.value = 0.71  # Just above threshold (0.7)
        assessment.components = {}
        assessment.recommendation = "Caution advised"
        mock_threat.evaluate_incoming_intent = AsyncMock(return_value=assessment)

        safety_gate._threat_instinct = mock_threat

        result = await safety_gate.assess_threat({"action": "test"})

        assert result["requires_confirmation"] is True

    @pytest.mark.asyncio
    async def test_assess_threat_with_metrics(self, safety_gate, mock_threat_instinct):
        """Test that threat assessment records metrics."""
        safety_gate._threat_instinct = mock_threat_instinct

        with patch("kagami.forge.safety.THREAT_SCORE") as mock_metric:
            await safety_gate.assess_threat({"action": "test_action"})

            # Should record threat score
            mock_metric.labels.assert_called()

    @pytest.mark.asyncio
    async def test_assess_threat_exception_handling(self, safety_gate):
        """Test threat assessment handles exceptions (fail safe)."""
        mock_threat = MagicMock()
        mock_threat.evaluate_incoming_intent = AsyncMock(
            side_effect=RuntimeError("Assessment failed")
        )

        safety_gate._threat_instinct = mock_threat

        result = await safety_gate.assess_threat({"action": "test"})

        # Should fail safe (high threat, requires confirmation)
        assert result["score"] == 0.9
        assert result["requires_confirmation"] is True
        assert "Assessment failed" in result["reason"]


class TestIntegration:
    """Test integrated safety checks."""

    @pytest.mark.asyncio
    async def test_combined_safety_checks(self, safety_gate, mock_ethical_instinct, mock_threat_instinct):
        """Test combined ethical and threat checks."""
        safety_gate._ethical_instinct = mock_ethical_instinct
        safety_gate._threat_instinct = mock_threat_instinct

        context = {"action": "generate_character", "concept": "warrior"}

        ethical_result = await safety_gate.evaluate_ethical(context)
        threat_result = await safety_gate.assess_threat(context)

        assert ethical_result["permissible"] is True
        assert threat_result["score"] < 0.5

    @pytest.mark.asyncio
    async def test_high_risk_operation_flow(self, safety_gate):
        """Test full safety flow for high-risk operation."""
        # Setup high-risk scenario
        mock_ethical = MagicMock()
        ethical_verdict = MagicMock()
        ethical_verdict.permissible = False
        ethical_verdict.reasoning = "Potentially harmful"
        ethical_verdict.principle_violated = "harm_prevention"
        mock_ethical.evaluate = AsyncMock(return_value=ethical_verdict)

        mock_threat = MagicMock()
        threat_assessment = MagicMock()
        threat_assessment.value = 0.9
        threat_assessment.components = {}
        threat_assessment.recommendation = "Block operation"
        mock_threat.evaluate_incoming_intent = AsyncMock(return_value=threat_assessment)

        safety_gate._ethical_instinct = mock_ethical
        safety_gate._threat_instinct = mock_threat

        context = {
            "action": "dangerous_operation",
            "destructive": True,
            "irreversible": True,
        }

        ethical_result = await safety_gate.evaluate_ethical(context)
        threat_result = await safety_gate.assess_threat(context)

        # Both should indicate high risk
        assert ethical_result["permissible"] is False
        assert threat_result["requires_confirmation"] is True


class TestSingletonAccess:
    """Test singleton access pattern."""

    def test_get_safety_gate(self):
        """Test get_safety_gate singleton."""
        gate1 = get_safety_gate()
        gate2 = get_safety_gate()

        assert gate1 is gate2


class TestContextValidation:
    """Test context parameter validation."""

    @pytest.mark.asyncio
    async def test_empty_context(self, safety_gate, mock_ethical_instinct):
        """Test safety checks with empty context."""
        safety_gate._ethical_instinct = mock_ethical_instinct

        result = await safety_gate.evaluate_ethical({})

        # Should still evaluate, even with empty context
        assert "permissible" in result

    @pytest.mark.asyncio
    async def test_context_with_extra_fields(self, safety_gate, mock_ethical_instinct):
        """Test context with additional fields."""
        safety_gate._ethical_instinct = mock_ethical_instinct

        context = {
            "action": "test",
            "extra_field_1": "value1",
            "extra_field_2": "value2",
            "metadata": {"key": "value"},
        }

        result = await safety_gate.evaluate_ethical(context)

        assert "permissible" in result
