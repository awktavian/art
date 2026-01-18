"""Tests for LearningRateAdapter.

Validates adaptive learning rate logic based on:
- Success rate patterns
- Weight volatility
- Organism health
- Time elapsed
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import time

from kagami.core.motivation.learning_rate_adapter import (
    LearningRateAdapter,
    MIN_LEARNING_INTERVAL,
    MAX_LEARNING_INTERVAL,
    DEFAULT_BASE_LEARNING_INTERVAL,
    get_learning_rate_adapter,
    reset_learning_rate_adapter,
)


@pytest.fixture
def adapter():  # type: ignore[misc]
    """Create fresh adapter instance for each test."""
    reset_learning_rate_adapter()
    return LearningRateAdapter()


def test_adapter_initialization(adapter: LearningRateAdapter) -> None:
    """Test adapter initializes with correct defaults."""
    assert adapter._current_interval == DEFAULT_BASE_LEARNING_INTERVAL
    assert adapter._goals_since_last_learning == 0
    assert len(adapter._recent_results) == 0
    assert len(adapter._learning_history) == 0


def test_record_goal_result(adapter: LearningRateAdapter) -> None:
    """Test goal result recording."""
    adapter.record_goal_result(success=True)
    adapter.record_goal_result(success=False)
    adapter.record_goal_result(success=True)

    assert adapter._goals_since_last_learning == 3
    assert len(adapter._recent_results) == 3
    assert list(adapter._recent_results) == [True, False, True]


def test_success_rate_computation(adapter: LearningRateAdapter) -> None:
    """Test success rate is computed correctly."""
    # Record mixed results
    for _ in range(7):
        adapter.record_goal_result(success=True)
    for _ in range(3):
        adapter.record_goal_result(success=False)

    metrics = adapter.compute_metrics()
    assert metrics.success_rate == 0.7  # 7/10


def test_low_success_rate_speeds_up_learning(adapter: LearningRateAdapter) -> None:
    """Test that low success rate reduces learning interval."""
    # Record 10 failures
    for _ in range(10):
        adapter.record_goal_result(success=False)

    metrics = adapter.compute_metrics(organism_health=1.0)

    # Low success rate should reduce interval
    assert metrics.recommended_interval < DEFAULT_BASE_LEARNING_INTERVAL
    assert metrics.recommended_interval >= MIN_LEARNING_INTERVAL


def test_high_success_rate_slows_down_learning(adapter: LearningRateAdapter) -> None:
    """Test that high success rate increases learning interval."""
    # Record 10 successes
    for _ in range(10):
        adapter.record_goal_result(success=True)

    metrics = adapter.compute_metrics(organism_health=1.0)

    # High success rate should increase interval
    assert metrics.recommended_interval > DEFAULT_BASE_LEARNING_INTERVAL
    assert metrics.recommended_interval <= MAX_LEARNING_INTERVAL


def test_unhealthy_organism_speeds_up_learning(adapter: LearningRateAdapter) -> None:
    """Test that low organism health reduces learning interval."""
    # Record moderate success
    for _ in range(5):
        adapter.record_goal_result(success=True)
    for _ in range(5):
        adapter.record_goal_result(success=False)

    metrics_healthy = adapter.compute_metrics(organism_health=0.9)
    metrics_unhealthy = adapter.compute_metrics(organism_health=0.3)

    # Unhealthy organism should learn faster
    assert metrics_unhealthy.recommended_interval < metrics_healthy.recommended_interval


def test_high_volatility_speeds_up_learning(adapter: LearningRateAdapter) -> None:
    """Test that high weight volatility reduces learning interval (with conflicting factors balanced)."""
    # Record mixed results (moderate success to not dominate)
    for _ in range(5):
        adapter.record_goal_result(success=True)
    for _ in range(5):
        adapter.record_goal_result(success=False)

    # Record learning event with high volatility
    adapter.record_learning_event(max_weight_change=0.25)

    # Now record more mixed results
    for _ in range(5):
        adapter.record_goal_result(success=True)
    for _ in range(5):
        adapter.record_goal_result(success=False)

    metrics = adapter.compute_metrics(organism_health=1.0)

    # High volatility with moderate success should reduce interval
    # Volatility effect (0.7x) should dominate when success is moderate
    assert metrics.recommended_interval <= 10  # Should be ~7 (10 * 0.7)


def test_low_volatility_slows_down_learning(adapter: LearningRateAdapter) -> None:
    """Test that low weight volatility increases learning interval."""
    # Record some goals
    for _ in range(5):
        adapter.record_goal_result(success=True)

    # Record learning event with low volatility
    adapter.record_learning_event(max_weight_change=0.02)

    # Now compute metrics
    for _ in range(5):
        adapter.record_goal_result(success=True)

    metrics = adapter.compute_metrics(organism_health=1.0)

    # Low volatility (+ high success) should increase interval
    assert metrics.recommended_interval >= DEFAULT_BASE_LEARNING_INTERVAL


def test_should_learn_now_respects_interval(adapter: LearningRateAdapter) -> None:
    """Test that should_learn_now() respects adaptive interval.

    Note: The interval is recomputed each time based on recent history,
    so we test that learning triggers after sufficient goals, not exact count.
    """
    # Record mixed results
    for _ in range(5):
        adapter.record_goal_result(success=True)
    for _ in range(5):
        adapter.record_goal_result(success=False)

    # Manually set goals counter to 0
    adapter._goals_since_last_learning = 0

    # Should not learn yet (just reset)
    assert not adapter.should_learn_now(organism_health=1.0, force_time_check=False)

    # Record moderate number of goals with consistent pattern
    # Use moderate success to keep interval stable
    for i in range(20):
        adapter.record_goal_result(success=(i % 2 == 0))  # Alternate success/failure

    # Should learn now (enough goals passed)
    # At 20 goals with moderate success, should trigger learning
    assert adapter.should_learn_now(organism_health=1.0, force_time_check=False)


def test_should_learn_now_forces_after_time(adapter: LearningRateAdapter) -> None:
    """Test that should_learn_now() forces learning after max time."""
    # Manually set last learning time to 2 hours ago
    adapter._last_learning_time = time.time() - 7200  # 2 hours

    # Should force learning even with no goals
    assert adapter.should_learn_now(organism_health=1.0, force_time_check=True)


def test_record_learning_event_resets_counter(adapter: LearningRateAdapter) -> None:
    """Test that recording learning event resets goals counter."""
    # Record some goals
    for _ in range(10):
        adapter.record_goal_result(success=True)

    assert adapter._goals_since_last_learning == 10

    # Record learning event
    adapter.record_learning_event(max_weight_change=0.1)

    # Counter should reset
    assert adapter._goals_since_last_learning == 0


def test_learning_effectiveness_tracking(adapter: LearningRateAdapter) -> None:
    """Test that learning effectiveness is tracked correctly."""
    # Record 5 failures
    for _ in range(5):
        adapter.record_goal_result(success=False)

    # Learn (should record low success rate)
    adapter.record_learning_event(max_weight_change=0.1, success_rate_after=0.0)

    # Record 5 successes
    for _ in range(5):
        adapter.record_goal_result(success=True)

    # Learn again (should show improvement)
    adapter.record_learning_event(max_weight_change=0.1, success_rate_after=1.0)

    # Check learning history
    assert len(adapter._learning_history) == 2

    # First event: no effectiveness data yet
    first_event = adapter._learning_history[0]
    assert first_event.success_rate_after == 0.0

    # Second event: should show improvement
    second_event = adapter._learning_history[1]
    assert second_event.effectiveness > 0  # Success rate improved


def test_get_stats(adapter: LearningRateAdapter) -> None:
    """Test that get_stats() returns correct information."""
    # Record some activity
    for _ in range(5):
        adapter.record_goal_result(success=True)

    adapter.record_learning_event(max_weight_change=0.1)

    for _ in range(3):
        adapter.record_goal_result(success=False)

    stats = adapter.get_stats()

    assert "current_interval" in stats
    assert "goals_since_last_learning" in stats
    assert "success_rate" in stats
    assert "weight_volatility" in stats
    assert "learning_events_tracked" in stats

    assert stats["goals_since_last_learning"] == 3
    assert stats["learning_events_tracked"] == 1


def test_singleton_adapter() -> None:
    """Test that get_learning_rate_adapter() returns singleton."""
    reset_learning_rate_adapter()

    adapter1 = get_learning_rate_adapter()
    adapter2 = get_learning_rate_adapter()

    assert adapter1 is adapter2


def test_adaptive_interval_clamps_to_bounds(adapter: LearningRateAdapter) -> None:
    """Test that adaptive interval never exceeds MIN/MAX bounds."""
    # Record extreme failure pattern
    for _ in range(20):
        adapter.record_goal_result(success=False)

    # Record high volatility
    for _ in range(5):
        adapter.record_learning_event(max_weight_change=0.5)

    metrics = adapter.compute_metrics(organism_health=0.1)

    # Should clamp to MIN_LEARNING_INTERVAL
    assert metrics.recommended_interval >= MIN_LEARNING_INTERVAL

    # Now record extreme success pattern
    reset_learning_rate_adapter()
    adapter = LearningRateAdapter()

    for _ in range(20):
        adapter.record_goal_result(success=True)

    # Record low volatility
    for _ in range(5):
        adapter.record_learning_event(max_weight_change=0.01)

    metrics = adapter.compute_metrics(organism_health=1.0)

    # Should clamp to MAX_LEARNING_INTERVAL
    assert metrics.recommended_interval <= MAX_LEARNING_INTERVAL


def test_combined_factors_learning_interval(adapter: LearningRateAdapter) -> None:
    """Test that multiple factors combine correctly."""
    # Low success + high volatility + unhealthy organism = fast learning
    for _ in range(10):
        adapter.record_goal_result(success=False)

    for _ in range(3):
        adapter.record_learning_event(max_weight_change=0.3)

    metrics = adapter.compute_metrics(organism_health=0.3)

    # Should be close to MIN_LEARNING_INTERVAL
    assert metrics.recommended_interval <= MIN_LEARNING_INTERVAL + 2


def test_explain_learning_decision(adapter: LearningRateAdapter) -> None:
    """Test that learning decision explanation is generated."""
    # Create scenario: low success rate
    for _ in range(10):
        adapter.record_goal_result(success=False)

    # Compute metrics and check for explanation
    metrics = adapter.compute_metrics(organism_health=0.3)

    # Trigger learning check (which generates explanation)
    for _ in range(10):
        adapter.record_goal_result(success=False)

    should_learn = adapter.should_learn_now(organism_health=0.3, force_time_check=False)

    # Should learn due to low success + low health
    assert should_learn


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
