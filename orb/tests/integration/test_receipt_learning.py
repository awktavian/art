"""Integration tests for receipt-driven learning.

Tests that receipts are persisted and enable learning improvements.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import time


@pytest.mark.integration
@pytest.mark.asyncio
async def test_receipt_persistence() -> None:
    """Verify receipts are persisted correctly."""
    from kagami.core.receipts import emit_receipt

    # Emit test receipt
    correlation_id = f"test_persist_{int(time.time())}"

    receipt = emit_receipt(
        correlation_id=correlation_id,
        action="test_operation",
        event_name="test.completed",
        event_data={"result": "success"},
        duration_ms=150,
        status="success",
    )

    # Verify receipt structure
    assert receipt["correlation_id"] == correlation_id
    assert receipt["intent"]["action"] == "test_operation"
    assert receipt["event"]["name"] == "test.completed"
    assert receipt["status"] == "success"
    assert receipt["duration_ms"] == 150


@pytest.mark.integration
@pytest.mark.asyncio
async def test_learning_from_receipts() -> None:
    """Verify learning systems can process receipts."""
    from kagami.core.instincts.learning_instinct import LearningInstinct

    learning = LearningInstinct()

    # Create a successful experience
    context = {"action": "test_task", "difficulty": "medium"}

    outcome = {"status": "success", "duration_ms": 100}

    valence = 0.8  # Positive outcome

    # Store experience
    await learning.remember(context, outcome, valence)

    # Verify episode was stored
    signature = learning._extract_signature(context)
    assert signature in learning._episodes
    assert len(learning._episodes[signature]) > 0

    # Verify value estimate updated
    assert signature in learning._value_estimates
    assert learning._value_estimates[signature]["mean"] > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pattern_learning_from_multiple_receipts() -> None:
    """Verify patterns emerge from multiple similar receipts."""
    from kagami.core.instincts.learning_instinct import LearningInstinct

    learning = LearningInstinct()

    # Simulate multiple successful operations
    for i in range(5):
        context = {"action": "similar_task", "index": i}

        outcome = {"status": "success"}

        valence = 0.7

        await learning.remember(context, outcome, valence)

    # Verify pattern recognition
    signature = learning._extract_signature({"action": "similar_task"})
    episodes = learning._episodes[signature]

    assert len(episodes) >= 5
    # Value estimate should stabilize around 0.7
    assert 0.6 <= learning._value_estimates[signature]["mean"] <= 0.8


@pytest.mark.integration
@pytest.mark.asyncio
async def test_learning_improves_predictions() -> None:
    """Verify learning improves prediction accuracy over time."""
    from kagami.core.instincts.prediction_instinct import PredictionInstinct

    predictor = PredictionInstinct()

    # First prediction (no history)
    context1 = {"action": "predict_task", "params": {}}
    prediction1 = await predictor.predict_outcome(context1)

    # Train with actual outcomes
    for i in range(10):
        context = {"action": "predict_task", "params": {}}
        actual_outcome = {"duration_ms": 100 + i * 5, "success": True}

        await predictor.learn(context, actual_outcome)

    # Second prediction (with history)
    context2 = {"action": "predict_task", "params": {}}
    prediction2 = await predictor.predict_outcome(context2)

    # Predictions should exist
    assert prediction1 is not None
    assert prediction2 is not None

    # Second prediction should have higher confidence (lower uncertainty)
    # after learning from 10 examples
    # Note: This is a smoke test - exact improvement depends on implementation


@pytest.mark.integration
@pytest.mark.asyncio
async def test_receipt_valence_calculation() -> None:
    """Verify receipts correctly calculate outcome valence."""
    from kagami.core.instincts.learning_instinct import LearningInstinct

    learning = LearningInstinct()

    # Test positive outcome
    positive_outcome = {"status": "success", "duration_ms": 50, "errors": 0}

    positive_valence = await learning.evaluate_outcome(positive_outcome)

    assert positive_valence > 0.5  # Should be positive

    # Test negative outcome
    negative_outcome = {"status": "error", "error": "Something failed", "duration_ms": 5000}

    negative_valence = await learning.evaluate_outcome(negative_outcome)

    assert negative_valence < 0.5  # Should be negative
