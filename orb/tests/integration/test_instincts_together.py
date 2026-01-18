"""
Integration test: Instincts working together.
Validates that prediction errors influence learning values.
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



from kagami.core.instincts.learning_instinct import LearningInstinct
from kagami.core.instincts.prediction_instinct import PredictionInstinct


@pytest.mark.asyncio
async def test_prediction_influences_learning():
    """Test that prediction errors influence learning instinct values."""
    pred_instinct = PredictionInstinct()
    learn_instinct = LearningInstinct()

    context = {"app": "test", "action": "operation", "complexity": "simple"}

    # Phase 1: Train prediction instinct
    print("\n📊 Phase 1: Training prediction instinct...")
    for _i in range(10):
        # Fast successful operations
        outcome = {"duration_ms": 50, "status": "success"}
        await pred_instinct.learn(context, outcome)

    prediction = await pred_instinct.predict(context)
    print(f"   Prediction confidence: {prediction.confidence:.2f}")
    assert prediction.confidence > 0.1, "Prediction should have learned"

    # Phase 2: Learning instinct learns from same outcomes
    print("\n📊 Phase 2: Training learning instinct...")
    for _i in range(10):
        outcome = {"duration_ms": 50, "status": "success"}
        valence = await learn_instinct.evaluate_outcome(outcome)
        await learn_instinct.remember(context, outcome, valence)

    should_try, confidence = await learn_instinct.should_try(context)
    print(f"   Learning confidence: {confidence:.2f}")
    print(f"   Should try: {should_try}")

    # Phase 3: Verify both learned the same pattern
    assert should_try, "Learning instinct should recommend trying"
    assert prediction.confidence > 0, "Prediction should be confident"

    print("\n✅ Both instincts learned from experience")
    print(f"   Prediction: {prediction.confidence:.2f} confidence")
    print(f"   Learning: {confidence:.2f} confidence, try={should_try}")


@pytest.mark.asyncio
async def test_instincts_distinguish_contexts():
    """Test that instincts can distinguish between different operation contexts."""
    pred_instinct = PredictionInstinct()
    learn_instinct = LearningInstinct()

    # Two different contexts
    fast_context = {"app": "test", "action": "read", "complexity": "simple"}
    slow_context = {"app": "test", "action": "write", "complexity": "complex"}

    # Train on fast operations
    print("\n📊 Training on fast operations...")
    for _i in range(10):
        outcome = {"duration_ms": 50, "status": "success"}
        await pred_instinct.learn(fast_context, outcome)
        valence = await learn_instinct.evaluate_outcome(outcome)
        await learn_instinct.remember(fast_context, outcome, valence)

    # Train on slow operations
    print("📊 Training on slow operations...")
    for _i in range(10):
        outcome = {"duration_ms": 200, "status": "success"}
        await pred_instinct.learn(slow_context, outcome)
        valence = await learn_instinct.evaluate_outcome(outcome)
        await learn_instinct.remember(slow_context, outcome, valence)

    # Verify different predictions
    fast_pred = await pred_instinct.predict(fast_context)
    slow_pred = await pred_instinct.predict(slow_context)

    print("\n✅ Instincts distinguish contexts:")
    print(f"   Fast context: {fast_pred.expected_outcome.get('duration_ms', 0)}ms")
    print(f"   Slow context: {slow_pred.expected_outcome.get('duration_ms', 0)}ms")

    # Predictions should be different
    fast_duration = fast_pred.expected_outcome.get("duration_ms", 0)
    slow_duration = slow_pred.expected_outcome.get("duration_ms", 0)

    assert slow_duration > fast_duration, "Slow context should predict longer duration"


@pytest.mark.asyncio
async def test_instincts_adapt_to_changes():
    """Test that instincts adapt when patterns change."""
    pred_instinct = PredictionInstinct()
    learn_instinct = LearningInstinct()

    context = {"app": "test", "action": "operation", "complexity": "simple"}

    # Phase 1: Train on fast operations
    print("\n📊 Phase 1: Fast operations (50ms)...")
    for _i in range(10):
        outcome = {"duration_ms": 50, "status": "success"}
        await pred_instinct.learn(context, outcome)
        valence = await learn_instinct.evaluate_outcome(outcome)
        await learn_instinct.remember(context, outcome, valence)

    pred_before = await pred_instinct.predict(context)
    duration_before = pred_before.expected_outcome.get("duration_ms", 0)
    print(f"   Prediction: {duration_before}ms")

    # Phase 2: Pattern changes - now slow
    print("\n📊 Phase 2: Pattern changed - now slow (200ms)...")
    for _i in range(10):
        outcome = {"duration_ms": 200, "status": "success"}
        await pred_instinct.learn(context, outcome)
        valence = await learn_instinct.evaluate_outcome(outcome)
        await learn_instinct.remember(context, outcome, valence)

    pred_after = await pred_instinct.predict(context)
    duration_after = pred_after.expected_outcome.get("duration_ms", 0)
    print(f"   Prediction: {duration_after}ms")

    # Verify adaptation
    assert duration_after > duration_before, "Prediction should adapt to new pattern"

    print("\n✅ Instincts adapted to pattern change:")
    print(f"   Before: {duration_before}ms → After: {duration_after}ms")


@pytest.mark.asyncio
async def test_learning_from_failure():
    """Test that instincts learn from failures."""
    pred_instinct = PredictionInstinct()
    learn_instinct = LearningInstinct()

    context = {"app": "test", "action": "operation", "complexity": "simple"}

    # Train on failures
    print("\n📊 Training on failures...")
    for _i in range(10):
        outcome = {"duration_ms": 100, "status": "error"}
        await pred_instinct.learn(context, outcome)
        valence = await learn_instinct.evaluate_outcome(outcome)
        await learn_instinct.remember(context, outcome, valence)

    should_try, confidence = await learn_instinct.should_try(context)

    # After many failures, learning instinct might recommend against trying
    # (depending on value estimate)
    print("\n📊 After 10 failures:")
    print(f"   Should try: {should_try}")
    print(f"   Confidence: {confidence:.2f}")

    # Prediction should still have data
    prediction = await pred_instinct.predict(context)
    assert prediction.confidence > 0, "Prediction should learn from failures too"

    print("✅ Instincts learned from failures")
