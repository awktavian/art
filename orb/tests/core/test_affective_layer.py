"""Tests for affective computing layer."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



from kagami.core.affective import (
    AffectiveLayer,
    ArousalRegulator,
    SocialEmotionProcessor,
    ThreatAssessment,
    ValenceEvaluator,
)


@pytest.mark.asyncio
async def test_threat_assessment_high_risk():
    """Test threat assessment detects high-risk intents."""
    threat = ThreatAssessment()

    # High-risk intent: delete production database
    intent = {
        "action": "delete",
        "target": "production.database",
        "app": "admin",
    }

    score = await threat.evaluate_incoming_intent(intent)

    assert score.value > 0.5  # Should be flagged as risky
    assert score.recommendation in ["block", "monitor"]
    assert any("destructive" in comp[0] for comp in score.components)


@pytest.mark.asyncio
async def test_threat_assessment_low_risk():
    """Test threat assessment allows low-risk intents."""
    threat = ThreatAssessment()

    # Low-risk intent: read data
    intent = {
        "action": "read",
        "target": "user.profile",
        "app": "users",
    }

    score = await threat.evaluate_incoming_intent(intent)

    assert score.value < 0.5  # Should be low risk
    assert score.recommendation in [
        "allow",
        "monitor",
    ]  # Low risk can be allow or monitor


@pytest.mark.asyncio
async def test_valence_evaluator_success():
    """Test valence evaluation for successful outcomes."""
    valence = ValenceEvaluator()

    # Fast success
    receipt = {
        "status": "success",
        "duration_ms": 50,
        "correlation_id": "test-123",
    }

    score = await valence.evaluate_outcome(receipt)

    assert score > 0.5  # Positive valence for fast success


@pytest.mark.asyncio
async def test_valence_evaluator_failure():
    """Test valence evaluation for failures."""
    valence = ValenceEvaluator()

    # Error
    receipt = {
        "status": "error",
        "duration_ms": 1000,
        "correlation_id": "test-456",
    }

    score = await valence.evaluate_outcome(receipt)

    assert score < 0  # Negative valence for errors


@pytest.mark.asyncio
async def test_arousal_regulator():
    """Test arousal regulation based on context."""
    arousal = ArousalRegulator()

    # High urgency context
    high_urgency = {
        "user_waiting": True,
        "critical_path": True,
    }

    score = await arousal.compute_arousal_level(high_urgency)
    assert score > 0.6  # Should be high arousal

    # Low priority context
    low_priority = {
        "background_task": True,
        "low_priority": True,
    }

    score = await arousal.compute_arousal_level(low_priority)
    assert score < 0.4  # Should be low arousal


@pytest.mark.asyncio
async def test_social_emotion_frustration():
    """Test detection of user frustration."""
    social = SocialEmotionProcessor()

    interaction = {
        "message": "This is still broken again! Not working!",
    }

    sentiment = await social.assess_user_sentiment(interaction)

    assert sentiment.frustration is True
    assert social.get_response_mode() == "empathetic_problem_solving"


@pytest.mark.asyncio
async def test_social_emotion_satisfaction():
    """Test detection of user satisfaction."""
    social = SocialEmotionProcessor()

    interaction = {
        "message": "This is great! Perfect, thanks!",
    }

    sentiment = await social.assess_user_sentiment(interaction)

    assert sentiment.satisfaction is True
    assert social.get_response_mode() == "collaborative_exploration"


@pytest.mark.asyncio
async def test_affective_layer_integration():
    """Test full affective layer integration."""
    layer = AffectiveLayer()

    # Test threat assessment
    intent = {"action": "delete", "target": "important.data"}
    threat = await layer.assess_threat(intent)
    assert threat.value > 0

    # Test arousal computation
    context = {"user_waiting": True}
    arousal = await layer.compute_arousal(context)
    assert 0.0 <= arousal <= 1.0

    # Test outcome evaluation
    receipt = {"status": "success", "duration_ms": 100, "correlation_id": "test"}
    valence = await layer.evaluate_outcome(receipt)
    assert -1.0 <= valence <= 1.0

    # Test state snapshot
    state = layer.get_affective_state()
    assert "arousal" in state
    assert "recent_valence" in state
    assert "response_mode" in state


@pytest.mark.asyncio
async def test_empathetic_response_generation():
    """Test empathetic response adaptation."""
    social = SocialEmotionProcessor()

    # Frustrated user
    frustrated = await social.assess_user_sentiment({"message": "Still not working!"})

    base_response = "The issue has been resolved."
    empathetic = await social.generate_empathetic_response(frustrated, base_response)

    assert "frustrat" in empathetic.lower()
    assert base_response in empathetic
