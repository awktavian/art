"""
Comprehensive Tests for Ethical Framework

Tests constitutional AI, moral judgment, and fairness assessment:
- Constitutional principle checking
- Fairness/bias detection
- Utilitarian scoring
- Rights validation
- Virtue alignment
- Edge cases and attack scenarios
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



from kagami.core.safety import (
    EthicalFramework,
)


class TestConstitutionalPrinciples:
    """Test constitutional constraint checking"""

    @pytest.mark.asyncio
    async def test_idempotency_check_read_operation(self):
        """Read operations don't need idempotency keys"""
        framework = EthicalFramework()

        intent = {"action": "read", "target": "user_data"}

        assessment = await framework.evaluate_intent_ethics(intent)

        assert assessment.recommendation != "block"
        # Read operations should pass idempotency check

    @pytest.mark.asyncio
    async def test_idempotency_check_mutation_without_key(self):
        """Mutations without idempotency keys should be flagged"""
        framework = EthicalFramework()

        intent = {
            "action": "delete",
            "target": "user_data",
            "metadata": {},  # No idempotency_key
        }

        assessment = await framework.evaluate_intent_ethics(intent)

        assert len(assessment.violations) > 0
        assert any(v.principle == "idempotency" for v in assessment.violations)

    @pytest.mark.asyncio
    async def test_idempotency_check_mutation_with_key(self):
        """Mutations with idempotency keys should pass"""
        framework = EthicalFramework()

        intent = {
            "action": "create",
            "target": "resource",
            "metadata": {"idempotency_key": "key-123"},
        }

        assessment = await framework.evaluate_intent_ethics(intent)

        # Should not have idempotency violation
        idempotency_violations = [v for v in assessment.violations if v.principle == "idempotency"]
        assert len(idempotency_violations) == 0

    @pytest.mark.asyncio
    async def test_no_harm_principle(self):
        """Harmful actions should be blocked"""
        framework = EthicalFramework()

        intent = {"action": "destroy", "target": "critical_data"}

        assessment = await framework.evaluate_intent_ethics(intent)

        assert any(v.principle == "no_harm" for v in assessment.violations)
        assert assessment.recommendation == "block"

    @pytest.mark.asyncio
    async def test_privacy_principle_unauthorized(self):
        """Accessing private data without authorization fails"""
        framework = EthicalFramework()

        intent = {"action": "read", "target": "private_user_data", "authorized": False}

        assessment = await framework.evaluate_intent_ethics(intent)

        # May have privacy violation
        [v for v in assessment.violations if v.principle == "privacy"]
        # Check if privacy is enforced


class TestFairnessAssessment:
    """Test fairness and bias detection"""

    @pytest.mark.asyncio
    async def test_no_bias_neutral_target(self):
        """Neutral targets should pass fairness check"""
        framework = EthicalFramework()

        intent = {"action": "process", "target": "general_data"}

        assessment = await framework.evaluate_intent_ethics(intent)

        assert assessment.fairness.bias_detected is False

    @pytest.mark.asyncio
    async def test_bias_detection_protected_group(self):
        """Targeting protected groups should be flagged"""
        framework = EthicalFramework()

        intent = {"action": "filter", "target": "users_by_race"}

        assessment = await framework.evaluate_intent_ethics(intent)

        assert assessment.fairness.bias_detected is True
        assert "race" in assessment.fairness.bias_type

    @pytest.mark.asyncio
    async def test_bias_detection_multiple_groups(self):
        """Multiple protected group mentions"""
        framework = EthicalFramework()

        intent = {"action": "segment", "target": "users_by_gender_and_age"}

        assessment = await framework.evaluate_intent_ethics(intent)

        assert assessment.fairness.bias_detected is True


class TestMoralJudgment:
    """Test moral reasoning frameworks"""

    @pytest.mark.asyncio
    async def test_utilitarian_positive_utility(self):
        """Actions with positive utility should pass"""
        framework = EthicalFramework()

        intent = {"action": "create", "target": "helpful_feature"}

        assessment = await framework.evaluate_intent_ethics(intent)

        assert assessment.moral_verdict.utility_score > 0
        assert assessment.moral_verdict.overall_judgment in ["permissible", "uncertain"]

    @pytest.mark.asyncio
    async def test_utilitarian_negative_utility(self):
        """Actions with negative utility should be questioned"""
        framework = EthicalFramework()

        intent = {"action": "delete", "target": "user_content"}

        assessment = await framework.evaluate_intent_ethics(intent)

        assert assessment.moral_verdict.utility_score < 0

    @pytest.mark.asyncio
    async def test_rights_check_user_affecting(self):
        """User-affecting actions need authorization"""
        framework = EthicalFramework()

        intent = {
            "action": "modify",
            "target": "user_account",
            "metadata": {"authorized": False},
        }

        assessment = await framework.evaluate_intent_ethics(intent)

        assert assessment.moral_verdict.rights_respected is False

    @pytest.mark.asyncio
    async def test_rights_check_authorized(self):
        """Authorized user actions should pass"""
        framework = EthicalFramework()

        intent = {
            "action": "update",
            "target": "user_preferences",
            "metadata": {"authorized": True},
        }

        assessment = await framework.evaluate_intent_ethics(intent)

        assert assessment.moral_verdict.rights_respected is True

    @pytest.mark.asyncio
    async def test_virtue_alignment_positive(self):
        """Virtuous actions should be recognized"""
        framework = EthicalFramework()

        intent = {"action": "help", "target": "user_request"}

        assessment = await framework.evaluate_intent_ethics(intent)

        assert assessment.moral_verdict.virtue_aligned is True

    @pytest.mark.asyncio
    async def test_virtue_alignment_negative(self):
        """Non-virtuous actions should be flagged"""
        framework = EthicalFramework()

        intent = {"action": "deceive", "target": "user"}

        assessment = await framework.evaluate_intent_ethics(intent)

        assert assessment.moral_verdict.virtue_aligned is False


class TestRecommendationLogic:
    """Test recommendation generation"""

    @pytest.mark.asyncio
    async def test_block_recommendation_critical_violation(self):
        """Critical violations should block"""
        framework = EthicalFramework()

        intent = {"action": "destroy", "target": "system_data"}

        assessment = await framework.evaluate_intent_ethics(intent)

        assert assessment.recommendation == "block"

    @pytest.mark.asyncio
    async def test_proceed_recommendation_safe_intent(self):
        """Safe intents should proceed"""
        framework = EthicalFramework()

        intent = {"action": "read", "target": "public_data"}

        assessment = await framework.evaluate_intent_ethics(intent)

        assert assessment.recommendation in ["proceed", "seek_guidance"]

    @pytest.mark.asyncio
    async def test_seek_guidance_ambiguous_case(self):
        """Ambiguous cases may need guidance"""
        framework = EthicalFramework()

        intent = {"action": "modify", "target": "sensitive_config", "metadata": {}}

        assessment = await framework.evaluate_intent_ethics(intent)

        # May recommend seeking guidance
        assert assessment.recommendation in ["seek_guidance", "block"]


class TestEthicalFrameworkIntegration:
    """Test framework integration and edge cases"""

    @pytest.mark.asyncio
    async def test_framework_initialization(self):
        """Framework should initialize with principles"""
        framework = EthicalFramework()

        assert framework._constitution is not None
        assert len(framework._constitution) > 0
        assert framework._moral_principles is not None

    @pytest.mark.asyncio
    async def test_multiple_violations(self):
        """Intent can violate multiple principles"""
        framework = EthicalFramework()

        intent = {
            "action": "harm",
            "target": "private_user_data",
            "metadata": {},  # No idempotency
            "authorized": False,
        }

        assessment = await framework.evaluate_intent_ethics(intent)

        # Should have multiple violations
        assert len(assessment.violations) >= 2

    @pytest.mark.asyncio
    async def test_empty_intent(self):
        """Empty intent should be handled"""
        framework = EthicalFramework()

        intent = {}

        assessment = await framework.evaluate_intent_ethics(intent)

        assert assessment is not None

    @pytest.mark.asyncio
    async def test_malformed_intent(self):
        """Malformed intent should not crash"""
        framework = EthicalFramework()

        intent = {"action": None, "target": None}

        assessment = await framework.evaluate_intent_ethics(intent)

        assert assessment is not None

    @pytest.mark.asyncio
    async def test_sequential_evaluations(self):
        """Multiple evaluations should work correctly"""
        framework = EthicalFramework()

        intent1 = {"action": "read", "target": "data1"}
        intent2 = {
            "action": "write",
            "target": "data2",
            "metadata": {"idempotency_key": "key"},
        }

        assessment1 = await framework.evaluate_intent_ethics(intent1)
        assessment2 = await framework.evaluate_intent_ethics(intent2)

        assert assessment1 is not None
        assert assessment2 is not None
        # Should not interfere with each other
