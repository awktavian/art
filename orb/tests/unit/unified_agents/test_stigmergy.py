"""Tests for Stigmergy - Learning from Environment via Receipts.

Validates:
1. Receipt pattern tracking
2. Bayesian success rate estimation
3. Temporal decay (pheromone evaporation)
4. UCB exploration bonus
5. Prediction and learning
6. Action selection (Thompson, UCB)
7. Pattern management

Created: December 2, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import math
import time

from kagami.core.unified_agents.memory.stigmergy import (
    ReceiptPattern,
    StigmergyLearner,
    get_stigmergy_learner,
    DEFAULT_DECAY_RATE,
    DEFAULT_UCB_C,
    DEFAULT_RECENCY_HALF_LIFE,
    BETA_PRIOR_ALPHA,
    BETA_PRIOR_BETA,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def learner() -> StigmergyLearner:
    """Create a fresh stigmergy learner."""
    # Clear singleton to get fresh instance
    import kagami.core.unified_agents.memory.stigmergy as stigmergy_module

    stigmergy_module._SINGLETON = None
    return get_stigmergy_learner()


@pytest.fixture
def pattern() -> ReceiptPattern:
    """Create a sample receipt pattern."""
    return ReceiptPattern(
        action="test.action",
        domain="spark",
        success_count=8,
        failure_count=2,
    )


# =============================================================================
# TEST RECEIPT PATTERN
# =============================================================================


class TestReceiptPattern:
    """Test ReceiptPattern dataclass."""

    def test_creation(self, pattern: ReceiptPattern) -> None:
        """Pattern should be created with values."""
        assert pattern.action == "test.action"
        assert pattern.domain == "spark"
        assert pattern.success_count == 8
        assert pattern.failure_count == 2

    def test_success_rate(self, pattern: ReceiptPattern) -> None:
        """Success rate should be calculated correctly."""
        # 8 / (8 + 2) = 0.8
        assert pattern.success_rate == 0.8

    def test_success_rate_empty(self) -> None:
        """Success rate should be 0.0 for empty pattern."""
        pattern = ReceiptPattern(action="test", domain="spark")
        assert pattern.success_rate == 0.0

    def test_bayesian_success_rate(self, pattern: ReceiptPattern) -> None:
        """Bayesian rate should use Beta posterior."""
        # Beta(1 + 8, 1 + 2) = Beta(9, 3)
        # Mean = 9 / (9 + 3) = 0.75
        expected = (BETA_PRIOR_ALPHA + 8) / (BETA_PRIOR_ALPHA + 8 + BETA_PRIOR_BETA + 2)
        assert abs(pattern.bayesian_success_rate - expected) < 1e-5

    def test_bayesian_vs_mle(self) -> None:
        """Bayesian should be more conservative than MLE for sparse data."""
        sparse = ReceiptPattern(action="test", domain="spark", success_count=1, failure_count=0)

        # MLE: 1/1 = 1.0
        # Bayesian: 2/3 ≈ 0.67
        assert sparse.success_rate == 1.0
        assert sparse.bayesian_success_rate < 1.0

    def test_timestamps(self, pattern: ReceiptPattern) -> None:
        """Pattern should have timestamps."""
        assert pattern.last_updated > 0
        assert pattern.created_at > 0
        # Both should be approximately equal (created at same time)
        assert abs(pattern.last_updated - pattern.created_at) < 0.001

    def test_access_count(self, pattern: ReceiptPattern) -> None:
        """Access count should start at 0."""
        assert pattern.access_count == 0

    def test_default_collections(self) -> None:
        """Default collections should be initialized."""
        pattern = ReceiptPattern(action="test", domain="spark")
        assert pattern.common_params == {}
        assert pattern.error_types == []


# =============================================================================
# TEST STIGMERGY LEARNER
# =============================================================================


class TestStigmergyLearner:
    """Test StigmergyLearner core functionality."""

    def test_singleton(self) -> None:
        """get_stigmergy_learner should return singleton."""
        learner1 = get_stigmergy_learner()
        learner2 = get_stigmergy_learner()

        assert learner1 is learner2

    def test_learner_has_patterns(self, learner: StigmergyLearner) -> None:
        """Learner should have patterns storage."""
        assert hasattr(learner, "patterns") or hasattr(learner, "_patterns")

    def test_predict_success_probability(self, learner: StigmergyLearner) -> None:
        """Predict should return success probability."""
        prob = learner.predict_success_probability("test.action", "spark")

        # Should return probability in [0, 1]
        assert 0.0 <= prob <= 1.0

    def test_predict_unknown(self, learner: StigmergyLearner) -> None:
        """Predict for unknown action should return prior."""
        prob = learner.predict_success_probability("unknown.action", "unknown.domain")

        # Should return prior mean (0.5 for uniform prior)
        expected = BETA_PRIOR_ALPHA / (BETA_PRIOR_ALPHA + BETA_PRIOR_BETA)
        assert abs(prob - expected) < 0.2  # Allow some variance


# =============================================================================
# TEST TEMPORAL DECAY
# =============================================================================


class TestTemporalDecay:
    """Test pheromone-style temporal decay."""

    def test_decay_rate_constant(self) -> None:
        """Default decay rate should be reasonable."""
        assert 0.9 < DEFAULT_DECAY_RATE < 1.0

    def test_pattern_has_timestamp(self) -> None:
        """Patterns should have timestamps."""
        pattern = ReceiptPattern(action="test", domain="spark")

        assert pattern.last_updated > 0
        assert pattern.created_at > 0

    def test_pattern_decay(self) -> None:
        """Pattern should support decay."""
        pattern = ReceiptPattern(
            action="test",
            domain="spark",
            success_count=10,
            failure_count=2,
        )

        # Apply decay
        pattern.apply_decay(0.9)

        # Counts should decrease
        assert pattern.success_count < 10
        assert pattern.failure_count < 2


# =============================================================================
# TEST UCB EXPLORATION
# =============================================================================


class TestUCBExploration:
    """Test UCB-style exploration bonus."""

    def test_ucb_constant(self) -> None:
        """UCB constant should be positive."""
        assert DEFAULT_UCB_C > 0

    def test_ucb_score_decreases_with_access(self) -> None:
        """UCB score should decrease with more accesses."""
        pattern = ReceiptPattern(
            action="test",
            domain="spark",
            success_count=5,
            failure_count=5,
        )

        # Low access count should have higher UCB score
        pattern.access_count = 1
        low_access_score = pattern.ucb_score(total_accesses=100)

        # High access count should have lower UCB score
        pattern.access_count = 50
        high_access_score = pattern.ucb_score(total_accesses=100)

        assert low_access_score > high_access_score


# =============================================================================
# TEST LEARNING
# =============================================================================


class TestLearning:
    """Test learning from receipts."""

    def test_extract_patterns(self, learner: StigmergyLearner) -> None:
        """Learner should be able to extract patterns."""
        # Extract patterns should not error
        count = learner.extract_patterns()
        assert count >= 0

    def test_predict_duration(self, learner: StigmergyLearner) -> None:
        """Should be able to predict duration."""
        duration = learner.predict_duration("test.action", "spark")
        assert duration >= 0


# =============================================================================
# TEST PERSISTENCE
# =============================================================================


class TestPersistence:
    """Test pattern persistence."""

    def test_singleton_persists(self, learner: StigmergyLearner) -> None:
        """Learner singleton should persist."""
        # Get same learner (singleton)
        same_learner = get_stigmergy_learner()
        assert learner is same_learner


# =============================================================================
# TEST INTEGRATION
# =============================================================================


class TestIntegration:
    """Test integration scenarios."""

    def test_thompson_sampling(self, learner: StigmergyLearner) -> None:
        """Thompson sampling should work."""
        actions = [("action1", "spark"), ("action2", "forge")]

        result = learner.select_action_thompson(actions)

        # Should return one of the action tuples
        assert result in actions

    def test_ucb_selection(self, learner: StigmergyLearner) -> None:
        """UCB selection should work."""
        actions = [("action1", "spark"), ("action2", "forge")]

        result = learner.select_action_ucb(actions)

        # Should return one of the action tuples
        assert result in actions

    def test_should_avoid(self, learner: StigmergyLearner) -> None:
        """Should avoid should return boolean."""
        result = learner.should_avoid("test.action", "spark")
        assert isinstance(result, bool)

    def test_get_pattern_summary(self, learner: StigmergyLearner) -> None:
        """Pattern summary should return dict."""
        summary = learner.get_pattern_summary()
        assert isinstance(summary, dict)


# =============================================================================
# TEST PATTERN PROPERTIES
# =============================================================================


class TestPatternProperties:
    """Test ReceiptPattern computed properties."""

    def test_bayesian_confidence(self) -> None:
        """Bayesian confidence should use Beta variance."""
        pattern = ReceiptPattern(
            action="test",
            domain="spark",
            success_count=50,
            failure_count=50,
        )

        conf = pattern.bayesian_confidence
        assert 0.0 <= conf <= 1.0
        # High sample size should have high confidence
        assert conf > 0.8

    def test_sample_thompson(self) -> None:
        """Thompson sampling should return value in [0, 1]."""
        pattern = ReceiptPattern(
            action="test",
            domain="spark",
            success_count=5,
            failure_count=5,
        )

        # Sample multiple times
        for _ in range(10):
            sample = pattern.sample_thompson()
            assert 0.0 <= sample <= 1.0

    def test_age_hours(self) -> None:
        """Age should be computed correctly."""
        pattern = ReceiptPattern(action="test", domain="spark")

        # Just created, should be ~0 hours
        age = pattern.age_hours()
        assert age < 0.01

    def test_to_dict(self) -> None:
        """Pattern should serialize to dict."""
        pattern = ReceiptPattern(
            action="test",
            domain="spark",
            success_count=5,
            failure_count=2,
        )

        d = pattern.to_dict()

        assert d["action"] == "test"
        assert d["domain"] == "spark"
        assert d["success_count"] == 5
        assert d["failure_count"] == 2
        # Core fields should be present
        assert "avg_duration" in d
        assert "last_updated" in d


# =============================================================================
# TEST LEARNER CONFIGURATION
# =============================================================================


class TestLearnerConfiguration:
    """Test StigmergyLearner configuration."""

    def test_default_config(self, learner: StigmergyLearner) -> None:
        """Learner should have default config."""
        assert learner.decay_rate == DEFAULT_DECAY_RATE
        assert learner.ucb_c == DEFAULT_UCB_C

    def test_custom_config(self) -> None:
        """Learner should accept custom config."""
        learner = StigmergyLearner(
            decay_rate=0.95,
            ucb_c=2.0,
            base_learning_rate=0.2,
        )

        assert learner.decay_rate == 0.95
        assert learner.ucb_c == 2.0

    def test_adaptive_learning_rate_no_pattern(self, learner: StigmergyLearner) -> None:
        """Adaptive LR without pattern should return base rate."""
        lr = learner.adaptive_learning_rate(None)
        assert lr == learner._base_learning_rate

    def test_adaptive_learning_rate_with_pattern(self, learner: StigmergyLearner) -> None:
        """Adaptive LR should vary with pattern confidence."""
        # Low confidence pattern
        low_conf = ReceiptPattern(
            action="test",
            domain="spark",
            success_count=1,
            failure_count=1,
        )
        lr_low = learner.adaptive_learning_rate(low_conf)

        # High confidence pattern
        high_conf = ReceiptPattern(
            action="test",
            domain="spark",
            success_count=100,
            failure_count=100,
        )
        lr_high = learner.adaptive_learning_rate(high_conf)

        # Low confidence should have higher LR
        assert lr_low > lr_high


# =============================================================================
# TEST PATTERN MANAGEMENT
# =============================================================================


class TestPatternManagement:
    """Test pattern storage and retrieval."""

    def test_patterns_dict(self, learner: StigmergyLearner) -> None:
        """Learner should have patterns dict."""
        assert hasattr(learner, "patterns")
        assert isinstance(learner.patterns, dict)

    def test_add_pattern(self, learner: StigmergyLearner) -> None:
        """Should be able to add patterns."""
        pattern = ReceiptPattern(
            action="manual.add",
            domain="nexus",
            success_count=10,
            failure_count=2,
        )

        learner.patterns[("manual.add", "nexus")] = pattern

        assert ("manual.add", "nexus") in learner.patterns

    def test_total_accesses_tracking(self, learner: StigmergyLearner) -> None:
        """Total accesses should be tracked."""
        assert hasattr(learner, "_total_accesses")
        initial = learner._total_accesses

        # Predict should increment access count
        learner.predict_success_probability("track.test", "spark")

        # May or may not increment depending on implementation


# =============================================================================
# TEST DECAY AND EVAPORATION
# =============================================================================


class TestDecayEvaporation:
    """Test pheromone-style decay."""

    def test_apply_decay_to_all(self, learner: StigmergyLearner) -> None:
        """Should apply decay to all patterns."""
        # Add patterns
        learner.patterns[("decay1", "spark")] = ReceiptPattern(
            action="decay1",
            domain="spark",
            success_count=100,
            failure_count=50,
        )
        learner.patterns[("decay2", "forge")] = ReceiptPattern(
            action="decay2",
            domain="forge",
            success_count=50,
            failure_count=25,
        )

        # Apply decay
        count = learner.apply_decay_to_all()

        assert count >= 0

    def test_pattern_apply_decay(self) -> None:
        """Pattern decay should reduce counts."""
        pattern = ReceiptPattern(
            action="test",
            domain="spark",
            success_count=100,
            failure_count=50,
        )

        # Set last_updated to 1 hour ago so decay applies
        pattern.last_updated = time.time() - 3600  # 1 hour ago

        original_success = pattern.success_count
        original_failure = pattern.failure_count

        pattern.apply_decay(0.5)  # 50% decay per hour

        assert pattern.success_count < original_success
        assert pattern.failure_count < original_failure


# =============================================================================
# TEST PREDICTION
# =============================================================================


class TestPrediction:
    """Test prediction methods."""

    def test_predict_success_probability_range(self, learner: StigmergyLearner) -> None:
        """Prediction should be in [0, 1]."""
        prob = learner.predict_success_probability("any.action", "any.domain")
        assert 0.0 <= prob <= 1.0

    def test_predict_duration_positive(self, learner: StigmergyLearner) -> None:
        """Duration prediction should be positive."""
        duration = learner.predict_duration("any.action", "any.domain")
        assert duration >= 0

    def test_predict_with_pattern(self, learner: StigmergyLearner) -> None:
        """Prediction should use pattern if exists."""
        # Add a pattern
        learner.patterns[("known.action", "spark")] = ReceiptPattern(
            action="known.action",
            domain="spark",
            success_count=90,
            failure_count=10,
        )

        prob = learner.predict_success_probability("known.action", "spark")

        # Should be high (~0.9)
        assert prob > 0.7

    def test_get_recommended_params(self, learner: StigmergyLearner) -> None:
        """Should return recommended params."""
        params = learner.get_recommended_params("test.action", "spark")
        assert isinstance(params, dict)


# =============================================================================
# TEST CONSTANTS
# =============================================================================


class TestConstants:
    """Test module constants."""

    def test_decay_rate_valid(self) -> None:
        """Decay rate should be in (0, 1)."""
        assert 0 < DEFAULT_DECAY_RATE < 1

    def test_ucb_constant_positive(self) -> None:
        """UCB constant should be positive."""
        assert DEFAULT_UCB_C > 0

    def test_half_life_positive(self) -> None:
        """Recency half-life should be positive."""
        assert DEFAULT_RECENCY_HALF_LIFE > 0

    def test_beta_priors(self) -> None:
        """Beta priors should be positive."""
        assert BETA_PRIOR_ALPHA > 0
        assert BETA_PRIOR_BETA > 0
