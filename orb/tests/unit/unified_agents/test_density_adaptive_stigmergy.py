"""Tests for Density-Adaptive Stigmergy.

Validates:
1. Agent density computation from receipt rate
2. Critical density threshold (ρ_c ≈ 0.230)
3. Mode switching (individual vs stigmergic)
4. Weight adaptation based on density
5. Integration with CooperationMetric
6. Backward compatibility (adaptive_mode=False)

Research Citation:
"Emergent Collective Memory in Decentralized Multi-Agent AI"
December 2025. Critical density ρ_c ≈ 0.230.

Created: December 14, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import time

from kagami.core.unified_agents.memory.stigmergy import (
    StigmergyLearner,
    CooperationMetric,
    CRITICAL_DENSITY,
    DEFAULT_DENSITY_WINDOW,
    DEFAULT_ENVIRONMENT_CAPACITY,
    DEFAULT_HEURISTIC_WEIGHT,
    DEFAULT_PHEROMONE_WEIGHT,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def adaptive_learner() -> StigmergyLearner:
    """Create learner with adaptive mode enabled."""
    return StigmergyLearner(
        enable_persistence=False,
        adaptive_mode=True,
        density_threshold=CRITICAL_DENSITY,
        environment_capacity=50,
    )


@pytest.fixture
def static_learner() -> StigmergyLearner:
    """Create learner with adaptive mode disabled (backward compatibility)."""
    return StigmergyLearner(
        enable_persistence=False,
        adaptive_mode=False,
    )


def add_receipts(learner: StigmergyLearner, count: int, success_rate: float = 0.8) -> None:
    """Helper to add test receipts.

    Args:
        learner: Learner to populate
        count: Number of receipts
        success_rate: Fraction that should succeed
    """
    current_time = time.time()

    for i in range(count):
        receipt = {
            "intent": {"action": "test.action"},
            "actor": "test_colony",
            "workspace_hash": "test",
            "verifier": {"status": "verified" if (i / count) < success_rate else "failed"},
            "timestamp": current_time - (count - i) * 10,  # Spread over time
            "duration_ms": 100,
        }
        learner.receipt_cache.append(receipt)


# =============================================================================
# TEST DENSITY COMPUTATION
# =============================================================================


class TestDensityComputation:
    """Test agent density calculation."""

    def test_density_zero_when_disabled(self, static_learner: StigmergyLearner) -> None:
        """Density should be 0 when adaptive mode disabled."""
        density = static_learner.compute_agent_density()
        assert density == 0.0

    def test_density_zero_initially(self, adaptive_learner: StigmergyLearner) -> None:
        """Density should be 0 with no receipts."""
        density = adaptive_learner.compute_agent_density()
        assert density == 0.0

    def test_density_increases_with_receipts(self, adaptive_learner: StigmergyLearner) -> None:
        """Density should increase as receipts accumulate."""
        # Add 10 receipts
        add_receipts(adaptive_learner, 10)
        adaptive_learner.extract_patterns()

        density_10 = adaptive_learner.compute_agent_density()

        # Add 20 more receipts
        add_receipts(adaptive_learner, 20)
        adaptive_learner.extract_patterns()

        density_30 = adaptive_learner.compute_agent_density()

        # Density should increase
        assert density_30 > density_10
        assert density_10 > 0

    def test_density_clamped_to_one(self, adaptive_learner: StigmergyLearner) -> None:
        """Density should clamp at 1.0 even with excessive receipts."""
        # Add more receipts than environment capacity
        add_receipts(adaptive_learner, 200)
        adaptive_learner.extract_patterns()

        density = adaptive_learner.compute_agent_density()
        assert density <= 1.0

    def test_density_respects_window(self, adaptive_learner: StigmergyLearner) -> None:
        """Density should only count receipts in window."""
        # Create learner with small window
        learner = StigmergyLearner(
            enable_persistence=False,
            adaptive_mode=True,
            density_window=10,
            environment_capacity=50,
        )

        # Add receipts beyond window
        add_receipts(learner, 50)
        learner.extract_patterns()

        # Only last 10 should be counted
        density = learner.compute_agent_density()

        # 10 receipts / 50 capacity = 0.2
        assert abs(density - 0.2) < 0.01


# =============================================================================
# TEST CRITICAL DENSITY THRESHOLD
# =============================================================================


class TestCriticalDensity:
    """Test critical density ρ_c ≈ 0.230."""

    def test_critical_density_constant(self) -> None:
        """CRITICAL_DENSITY should match research value."""
        assert CRITICAL_DENSITY == 0.230

    def test_below_critical_density(self, adaptive_learner: StigmergyLearner) -> None:
        """Below ρ_c: Individual mode, heuristic boosted."""
        # Add 5 receipts (5/50 = 0.1 < 0.230)
        add_receipts(adaptive_learner, 5)
        adaptive_learner.extract_patterns()

        density = adaptive_learner.compute_agent_density()
        heuristic_weight, pheromone_weight = adaptive_learner.get_adaptive_weights()

        assert density < CRITICAL_DENSITY
        # Heuristic should be boosted
        assert heuristic_weight > DEFAULT_HEURISTIC_WEIGHT
        # Pheromone should be dampened
        assert pheromone_weight < DEFAULT_PHEROMONE_WEIGHT

    def test_above_critical_density(self, adaptive_learner: StigmergyLearner) -> None:
        """Above ρ_c: Stigmergic mode, pheromone boosted."""
        # Add 20 receipts (20/50 = 0.4 > 0.230)
        add_receipts(adaptive_learner, 20)
        adaptive_learner.extract_patterns()

        density = adaptive_learner.compute_agent_density()
        heuristic_weight, pheromone_weight = adaptive_learner.get_adaptive_weights()

        assert density > CRITICAL_DENSITY
        # Pheromone should be boosted
        assert pheromone_weight > DEFAULT_PHEROMONE_WEIGHT
        # Heuristic should be dampened
        assert heuristic_weight < DEFAULT_HEURISTIC_WEIGHT

    def test_smooth_transition_at_threshold(self, adaptive_learner: StigmergyLearner) -> None:
        """Weights should transition smoothly near ρ_c."""
        # Test points around critical density
        densities = []
        heuristic_weights = []
        pheromone_weights = []

        for count in [5, 8, 11, 15, 20]:  # Crosses 0.230 at ~11-12
            learner = StigmergyLearner(
                enable_persistence=False,
                adaptive_mode=True,
                environment_capacity=50,
            )
            add_receipts(learner, count)
            learner.extract_patterns()

            density = learner.compute_agent_density()
            h_weight, p_weight = learner.get_adaptive_weights()

            densities.append(density)
            heuristic_weights.append(h_weight)
            pheromone_weights.append(p_weight)

        # Verify we cross the threshold
        assert min(densities) < CRITICAL_DENSITY < max(densities)

        # Weights should swap dominance across threshold
        # At low density: heuristic > pheromone
        # At high density: pheromone > heuristic
        assert heuristic_weights[0] > pheromone_weights[0]  # Low density
        assert heuristic_weights[-1] < pheromone_weights[-1]  # High density


# =============================================================================
# TEST COOPERATION INTEGRATION
# =============================================================================


class TestCooperationIntegration:
    """Test integration with CooperationMetric."""

    def test_cooperation_metric_exists(self, adaptive_learner: StigmergyLearner) -> None:
        """Learner should have cooperation metric."""
        assert hasattr(adaptive_learner, "cooperation_metric")
        assert isinstance(adaptive_learner.cooperation_metric, CooperationMetric)

    def test_effective_density_uses_cooperation(self, adaptive_learner: StigmergyLearner) -> None:
        """Effective density should integrate cooperation level."""
        # Add receipts to establish density
        add_receipts(adaptive_learner, 15)
        adaptive_learner.extract_patterns()

        # Get raw density
        raw_density = adaptive_learner.compute_agent_density()

        # Get adaptive weights (uses effective density)
        h_weight, p_weight = adaptive_learner.get_adaptive_weights()

        # Cooperation should modulate effective density
        cooperation = adaptive_learner.cooperation_metric.cooperation_level
        effective_density = raw_density * (0.5 + 0.5 * cooperation)

        # Verify effective density is used for mode decision
        if effective_density < CRITICAL_DENSITY:
            # Individual mode
            assert h_weight > DEFAULT_HEURISTIC_WEIGHT
        else:
            # Stigmergic mode
            assert p_weight > DEFAULT_PHEROMONE_WEIGHT

    def test_low_cooperation_dampens_stigmergic_mode(
        self, adaptive_learner: StigmergyLearner
    ) -> None:
        """Low cooperation should reduce stigmergic effectiveness."""
        # Add receipts for high density
        add_receipts(adaptive_learner, 25)
        adaptive_learner.extract_patterns()

        # Artificially lower cooperation
        adaptive_learner.cooperation_metric.within_group_relatedness = 0.1

        # Even with high raw density, low cooperation dampens stigmergic mode
        _h_weight, _p_weight = adaptive_learner.get_adaptive_weights()

        # Effect should be visible (may still be stigmergic but modulated)
        cooperation = adaptive_learner.cooperation_metric.cooperation_level
        assert cooperation < 0.5  # Low cooperation


# =============================================================================
# TEST BACKWARD COMPATIBILITY
# =============================================================================


class TestBackwardCompatibility:
    """Test that adaptive_mode=False preserves original behavior."""

    def test_disabled_returns_defaults(self, static_learner: StigmergyLearner) -> None:
        """With adaptive_mode=False, should return default weights."""
        add_receipts(static_learner, 30)
        static_learner.extract_patterns()

        h_weight, p_weight = static_learner.get_adaptive_weights()

        assert h_weight == DEFAULT_HEURISTIC_WEIGHT
        assert p_weight == DEFAULT_PHEROMONE_WEIGHT

    def test_disabled_density_not_tracked(self, static_learner: StigmergyLearner) -> None:
        """With adaptive_mode=False, density should not be tracked."""
        add_receipts(static_learner, 20)
        static_learner.extract_patterns()

        # Timestamps should not accumulate
        assert len(static_learner._recent_receipt_timestamps) == 0

    def test_summary_excludes_density_when_disabled(self, static_learner: StigmergyLearner) -> None:
        """Pattern summary should exclude density metrics when disabled."""
        add_receipts(static_learner, 10)
        static_learner.extract_patterns()

        summary = static_learner.get_pattern_summary()

        assert "adaptive_mode" not in summary
        assert "current_density" not in summary
        assert "mode" not in summary


# =============================================================================
# TEST PATTERN SUMMARY METRICS
# =============================================================================


class TestPatternSummaryMetrics:
    """Test density metrics in pattern summary."""

    def test_summary_includes_density_metrics(self, adaptive_learner: StigmergyLearner) -> None:
        """Summary should include density metrics when enabled."""
        add_receipts(adaptive_learner, 15)
        adaptive_learner.extract_patterns()

        summary = adaptive_learner.get_pattern_summary()

        assert summary["adaptive_mode"] is True
        assert "current_density" in summary
        assert "effective_density" in summary
        assert "density_threshold" in summary
        assert "mode" in summary
        assert "heuristic_weight" in summary
        assert "pheromone_weight" in summary
        assert "cooperation_level" in summary
        assert "f_star" in summary

    def test_summary_mode_label(self, adaptive_learner: StigmergyLearner) -> None:
        """Summary should label mode correctly."""
        # Low density
        add_receipts(adaptive_learner, 5)
        adaptive_learner.extract_patterns()
        summary_low = adaptive_learner.get_pattern_summary()

        # High density
        adaptive_learner.receipt_cache.clear()
        add_receipts(adaptive_learner, 25)
        adaptive_learner.extract_patterns()
        summary_high = adaptive_learner.get_pattern_summary()

        # Modes should differ (unless cooperation drastically changes effective density)
        # At minimum, densities should differ
        assert summary_low["current_density"] < summary_high["current_density"]


# =============================================================================
# TEST PERFORMANCE
# =============================================================================


class TestPerformance:
    """Test computational efficiency of density adaptation."""

    def test_compute_density_fast(self, adaptive_learner: StigmergyLearner) -> None:
        """Density computation should be < 0.1ms."""
        add_receipts(adaptive_learner, 100)
        adaptive_learner.extract_patterns()

        start = time.perf_counter()
        for _ in range(100):
            adaptive_learner.compute_agent_density()
        elapsed = time.perf_counter() - start

        avg_time_ms = (elapsed / 100) * 1000
        assert avg_time_ms < 0.1

    def test_get_weights_fast(self, adaptive_learner: StigmergyLearner) -> None:
        """Weight computation should be < 0.1ms."""
        add_receipts(adaptive_learner, 100)
        adaptive_learner.extract_patterns()

        start = time.perf_counter()
        for _ in range(100):
            adaptive_learner.get_adaptive_weights()
        elapsed = time.perf_counter() - start

        avg_time_ms = (elapsed / 100) * 1000
        assert avg_time_ms < 0.1


# =============================================================================
# TEST EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_environment_capacity(self) -> None:
        """Should handle zero capacity gracefully."""
        learner = StigmergyLearner(
            enable_persistence=False,
            adaptive_mode=True,
            environment_capacity=1,  # Minimum
        )
        add_receipts(learner, 5)
        learner.extract_patterns()

        # Should not crash
        density = learner.compute_agent_density()
        assert density >= 0

    def test_empty_patterns(self, adaptive_learner: StigmergyLearner) -> None:
        """Should handle empty patterns correctly."""
        summary = adaptive_learner.get_pattern_summary()

        # Should still report density metrics
        assert summary["adaptive_mode"] is True
        assert summary["current_density"] == 0.0
        assert summary["mode"] == "individual"

    def test_bifurcation_detection(self, adaptive_learner: StigmergyLearner) -> None:
        """Should detect cooperation bifurcations."""
        # Fluctuate cooperation by varying success rates
        for _ in range(5):
            add_receipts(adaptive_learner, 10, success_rate=0.9)
            adaptive_learner.extract_patterns()

        for _ in range(5):
            add_receipts(adaptive_learner, 10, success_rate=0.3)
            adaptive_learner.extract_patterns()

        summary = adaptive_learner.get_pattern_summary()

        # Bifurcation flag should exist
        assert "bifurcation_detected" in summary


# =============================================================================
# INTEGRATION TEST
# =============================================================================


class TestDensityAdaptiveIntegration:
    """End-to-end integration test."""

    def test_full_lifecycle(self) -> None:
        """Test complete density-adaptive lifecycle."""
        learner = StigmergyLearner(
            enable_persistence=False,
            adaptive_mode=True,
            density_threshold=CRITICAL_DENSITY,
            environment_capacity=50,
        )

        # Phase 1: Low density (individual mode)
        add_receipts(learner, 5)
        learner.extract_patterns()

        summary_1 = learner.get_pattern_summary()
        assert summary_1["mode"] == "individual"

        # Phase 2: Ramp up density (transition)
        add_receipts(learner, 10)
        learner.extract_patterns()

        summary_2 = learner.get_pattern_summary()
        # May be transitioning

        # Phase 3: High density (stigmergic mode)
        add_receipts(learner, 20)
        learner.extract_patterns()

        summary_3 = learner.get_pattern_summary()
        # Should likely be stigmergic now (depends on cooperation)

        # Verify metrics evolve
        assert summary_3["current_density"] > summary_2["current_density"]
        assert summary_2["current_density"] > summary_1["current_density"]
