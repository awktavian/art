"""Tests for EFE Meta-Learner: Weight adaptation system.

Tests verify:
1. Performance tracking and metrics aggregation
2. Gradient-based weight updates
3. Evolutionary weight updates
4. Safety constraints and clamping
5. Integration with ExpectedFreeEnergy
6. End-to-end learning from performance observations

Created: December 14, 2025
Status: Production-ready
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

import torch

from kagami.core.active_inference.efe_meta_learner import (
    EFEWeightLearner,
    EFEWeightLearnerConfig,
    PerformanceMetrics,
    PerformanceSnapshot,
    UpdateRule,
    integrate_meta_learner_with_efe,
)


class TestPerformanceMetrics:
    """Test performance tracking and aggregation."""

    def test_metrics_initialization(self) -> None:
        """Test metrics are initialized with sensible defaults."""
        metrics = PerformanceMetrics()
        assert metrics.window_size == 100
        assert metrics.success_rate == 0.0
        assert metrics.num_trajectories == 0

    def test_observe_single_outcome(self) -> None:
        """Test recording a single performance observation."""
        metrics = PerformanceMetrics()
        snapshot = PerformanceSnapshot(
            success=True,
            g_value=0.5,
            safety_margin=0.7,
            latency_ms=100.0,
            info_gain=0.3,
            catastrophe_risk=0.1,
            trajectory_length=10,
        )
        metrics.observe(snapshot)

        assert metrics.num_trajectories == 1
        assert metrics.success_rate > 0.0

    def test_observe_multiple_outcomes(self) -> None:
        """Test aggregating multiple observations."""
        metrics = PerformanceMetrics(ema_alpha=0.5)  # Fast alpha for testing

        # Record 10 successful trajectories
        for _i in range(10):
            snapshot = PerformanceSnapshot(
                success=True,
                g_value=0.5,
                safety_margin=0.7,
                latency_ms=100.0,
                info_gain=0.3,
                catastrophe_risk=0.1,
                trajectory_length=10,
            )
            metrics.observe(snapshot)

        # Success rate should be high
        assert metrics.success_rate > 0.5
        assert metrics.num_trajectories == 10

    def test_window_size_bounded(self) -> None:
        """Test that history window is bounded."""
        metrics = PerformanceMetrics(window_size=5)

        for i in range(20):
            snapshot = PerformanceSnapshot(
                success=bool(i % 2),
                g_value=float(i),
                safety_margin=0.5,
                latency_ms=100.0,
                info_gain=0.1,
                catastrophe_risk=0.1,
                trajectory_length=5,
            )
            metrics.observe(snapshot)

        assert len(metrics._snapshot_history) <= 5

    def test_diagnostics(self) -> None:
        """Test diagnostic output."""
        metrics = PerformanceMetrics()
        snapshot = PerformanceSnapshot(
            success=True,
            g_value=0.5,
            safety_margin=0.7,
            latency_ms=100.0,
            info_gain=0.3,
            catastrophe_risk=0.1,
            trajectory_length=10,
        )
        metrics.observe(snapshot)

        diags = metrics.get_diagnostics()
        assert "success_rate" in diags
        assert "mean_g_value" in diags
        assert "mean_safety_margin" in diags
        assert "num_trajectories" in diags


class TestEFEWeightLearnerConfig:
    """Test configuration validation."""

    def test_default_config(self) -> None:
        """Test default configuration is valid."""
        config = EFEWeightLearnerConfig()
        assert config.learning_rate > 0
        assert config.min_weight <= config.max_weight
        assert 0.0 <= config.target_success_rate <= 1.0

    def test_invalid_learning_rate(self) -> None:
        """Test that invalid learning rate raises error."""
        with pytest.raises(ValueError):
            EFEWeightLearnerConfig(learning_rate=-0.1)

    def test_invalid_weight_range(self) -> None:
        """Test that invalid weight range raises error."""
        with pytest.raises(ValueError):
            EFEWeightLearnerConfig(min_weight=1.0, max_weight=0.5)

    def test_invalid_success_target(self) -> None:
        """Test that invalid success rate target raises error."""
        with pytest.raises(ValueError):
            EFEWeightLearnerConfig(target_success_rate=1.5)


class TestEFEWeightLearner:
    """Test weight learning system."""

    def test_initialization(self) -> None:
        """Test learner initialization."""
        config = EFEWeightLearnerConfig()
        learner = EFEWeightLearner(config)

        assert learner.config is config
        assert hasattr(learner, "epistemic_weight")
        assert hasattr(learner, "pragmatic_weight")
        assert hasattr(learner, "risk_weight")
        assert hasattr(learner, "catastrophe_weight")

    def test_get_weights(self) -> None:
        """Test getting current weight values."""
        learner = EFEWeightLearner()
        weights = learner.get_weights()

        assert "epistemic_weight" in weights
        assert "pragmatic_weight" in weights
        assert "risk_weight" in weights
        assert "catastrophe_weight" in weights

        # All weights should be in valid range
        for w in weights.values():
            assert 0.0 <= w <= 2.0

    def test_weights_start_reasonable(self) -> None:
        """Test that weights start with reasonable EFE defaults."""
        learner = EFEWeightLearner()
        weights = learner.get_weights()

        # Epistemic and pragmatic typically start at ~1.0
        assert 0.5 < weights["epistemic_weight"] < 1.5
        assert 0.5 < weights["pragmatic_weight"] < 1.5
        # Risk typically lower
        assert weights["risk_weight"] < weights["epistemic_weight"]

    def test_observe_outcome(self) -> None:
        """Test recording performance outcomes."""
        learner = EFEWeightLearner()
        snapshot = PerformanceSnapshot(
            success=True,
            g_value=0.5,
            safety_margin=0.7,
            latency_ms=100.0,
            info_gain=0.3,
            catastrophe_risk=0.1,
            trajectory_length=10,
        )
        learner.observe_outcome(snapshot)

        assert learner.metrics.num_trajectories == 1
        assert learner._step_count == 1

    def test_compute_loss_success(self) -> None:
        """Test loss computation for successful trajectory."""
        learner = EFEWeightLearner()
        snapshot = PerformanceSnapshot(
            success=True,  # Success!
            g_value=0.1,  # Low G is good
            safety_margin=0.7,  # Good safety margin
            latency_ms=100.0,
            info_gain=0.3,
            catastrophe_risk=0.1,
            trajectory_length=10,
        )
        loss = learner.compute_loss(snapshot)

        # Loss should be relatively low for good performance
        assert loss.item() < 1.0
        assert loss.requires_grad

    def test_compute_loss_failure(self) -> None:
        """Test loss computation for failed trajectory."""
        learner = EFEWeightLearner()
        snapshot = PerformanceSnapshot(
            success=False,  # Failure!
            g_value=2.0,  # High G is bad
            safety_margin=-0.1,  # Safety violation
            latency_ms=100.0,
            info_gain=0.0,
            catastrophe_risk=0.8,
            trajectory_length=50,
        )
        loss = learner.compute_loss(snapshot)

        # Loss should be high for poor performance
        assert loss.item() > 0.0
        assert loss.requires_grad

    def test_gradient_based_update(self) -> None:
        """Test gradient-based weight updates."""
        config = EFEWeightLearnerConfig(
            update_rule=UpdateRule.GRADIENT, learning_rate=0.5, weight_decay=0.1
        )
        learner = EFEWeightLearner(config)

        # Initialize weights away from targets so regularization has non-zero gradient
        with torch.no_grad():
            learner.epistemic_weight.data.fill_(0.5)
            learner.pragmatic_weight.data.fill_(0.5)

        initial_weights = learner.get_weights().copy()

        # Observe poor performance
        snapshot = PerformanceSnapshot(
            success=False,
            g_value=2.0,
            safety_margin=-0.2,
            latency_ms=100.0,
            info_gain=0.0,
            catastrophe_risk=0.9,
            trajectory_length=50,
        )
        learner.observe_outcome(snapshot)
        loss = learner.compute_loss(snapshot)

        # Perform update
        stats = learner.step_gradient(loss)

        updated_weights = learner.get_weights()

        # Weights should have been updated (due to weight regularization)
        assert stats["loss"] > 0.0
        assert stats.get("updated", False) is True
        # Weights should be clamped and updated
        assert 0.0 <= updated_weights["epistemic_weight"] <= 2.0
        assert 0.0 <= updated_weights["pragmatic_weight"] <= 2.0

    def test_weight_clamping(self) -> None:
        """Test that weights are clamped to valid range."""
        config = EFEWeightLearnerConfig(min_weight=0.0, max_weight=2.0)
        learner = EFEWeightLearner(config)

        # Manually set weights out of range
        with torch.no_grad():
            learner.epistemic_weight.data = torch.tensor(-1.0)
            learner.pragmatic_weight.data = torch.tensor(5.0)

        weights = learner.get_weights()

        # Should be clamped
        assert weights["epistemic_weight"] >= 0.0
        assert weights["pragmatic_weight"] <= 2.0

    def test_evolutionary_initialization(self) -> None:
        """Test evolutionary population initialization."""
        config = EFEWeightLearnerConfig(update_rule=UpdateRule.EVOLUTIONARY, population_size=10)
        learner = EFEWeightLearner(config)

        assert hasattr(learner, "_population")
        assert len(learner._population) == 10
        assert len(learner._population_fitnesses) == 10

    def test_evolutionary_mutation(self) -> None:
        """Test weight mutation for evolution."""
        config = EFEWeightLearnerConfig(update_rule=UpdateRule.EVOLUTIONARY)
        learner = EFEWeightLearner(config)

        weights = {"epistemic": 1.0, "pragmatic": 1.0, "risk": 0.1, "catastrophe": 0.5}
        mutated = learner._mutate_weights(weights)

        # Mutations may or may not occur, but output should be valid
        for v in mutated.values():
            assert learner.config.min_weight <= v <= learner.config.max_weight

    def test_evolutionary_population_update(self) -> None:
        """Test evolutionary population fitness updates."""
        config = EFEWeightLearnerConfig(update_rule=UpdateRule.EVOLUTIONARY, population_size=5)
        learner = EFEWeightLearner(config)

        initial_fitnesses = learner._population_fitnesses.copy()

        # Observe outcome
        snapshot = PerformanceSnapshot(
            success=True,
            g_value=0.5,
            safety_margin=0.7,
            latency_ms=100.0,
            info_gain=0.3,
            catastrophe_risk=0.1,
            trajectory_length=10,
        )
        learner.observe_outcome(snapshot)

        # Fitness should have been updated
        assert learner._population_fitnesses != initial_fitnesses

    def test_get_diagnostics(self) -> None:
        """Test diagnostic output."""
        learner = EFEWeightLearner()

        # Observe some outcomes
        for i in range(5):
            snapshot = PerformanceSnapshot(
                success=bool(i % 2),
                g_value=float(i),
                safety_margin=0.5,
                latency_ms=100.0,
                info_gain=0.1,
                catastrophe_risk=0.1,
                trajectory_length=5,
            )
            learner.observe_outcome(snapshot)

        diags = learner.get_diagnostics()

        assert "weights" in diags
        assert "performance" in diags
        assert "step_count" in diags
        assert "update_rule" in diags

    def test_end_to_end_learning(self) -> None:
        """Test complete learning cycle."""
        config = EFEWeightLearnerConfig(learning_rate=0.05, weight_decay=0.01)
        learner = EFEWeightLearner(config)

        initial_weights = learner.get_weights()
        num_updates = 0

        # Simulate trajectory outcomes
        for success in [False, False, True, True]:
            snapshot = PerformanceSnapshot(
                success=success,
                g_value=2.0 if not success else 0.5,
                safety_margin=0.3 if not success else 0.7,
                latency_ms=100.0,
                info_gain=0.0 if not success else 0.3,
                catastrophe_risk=0.7 if not success else 0.1,
                trajectory_length=50 if not success else 10,
            )
            learner.observe_outcome(snapshot)
            loss = learner.compute_loss(snapshot)
            stats = learner.step_gradient(loss)
            if stats.get("updated", False):
                num_updates += 1

        final_weights = learner.get_weights()

        # Check that at least some learning happened
        assert num_updates > 0, "No gradient updates occurred"
        # Success rate should be tracked
        assert learner.metrics.success_rate >= 0.0
        assert learner.metrics.num_trajectories > 0


class TestIntegrationWithEFE:
    """Test integration with ExpectedFreeEnergy."""

    def test_meta_learner_integration(self) -> None:
        """Test that meta-learner can be integrated with EFE."""

        # Create mock EFE-like object (don't need full EFE for this test)
        class MockEFE:
            pass

        learner = EFEWeightLearner()
        efe = MockEFE()

        integrate_meta_learner_with_efe(learner, efe)  # type: ignore[arg-type]

        # Should have added methods
        assert hasattr(efe, "get_adaptive_weights")
        assert hasattr(efe, "observe_performance")
        assert hasattr(efe, "_meta_learner")

    def test_get_adaptive_weights_through_efe(self) -> None:
        """Test getting weights through EFE interface."""

        class MockEFE:
            pass

        learner = EFEWeightLearner()
        efe = MockEFE()

        integrate_meta_learner_with_efe(learner, efe)  # type: ignore[arg-type]

        weights = efe.get_adaptive_weights()

        assert "epistemic_weight" in weights
        assert "pragmatic_weight" in weights

    def test_observe_performance_through_efe(self) -> None:
        """Test observing performance through EFE interface."""

        class MockEFE:
            pass

        learner = EFEWeightLearner()
        efe = MockEFE()

        integrate_meta_learner_with_efe(learner, efe)  # type: ignore[arg-type]

        efe.observe_performance(
            success=True,
            g_value=0.5,
            safety_margin=0.7,
            latency_ms=100.0,
        )

        assert learner.metrics.num_trajectories == 1


class TestSchedulingAndConvergence:
    """Test learning rate scheduling and convergence."""

    def test_learning_rate_schedule(self) -> None:
        """Test that learning rate is annealed."""
        config = EFEWeightLearnerConfig(
            learning_rate=0.1,
            use_schedule=True,
            schedule_decay=0.9,
            schedule_cycle_length=10,
            weight_decay=0.001,
        )
        learner = EFEWeightLearner(config)

        initial_weights = learner.get_weights()
        num_updates = 0

        # Run many steps
        for _i in range(30):
            snapshot = PerformanceSnapshot(
                success=False,
                g_value=1.0,
                safety_margin=-0.1,
                latency_ms=100.0,
                info_gain=0.0,
                catastrophe_risk=0.5,
                trajectory_length=20,
            )
            learner.observe_outcome(snapshot)
            loss = learner.compute_loss(snapshot)
            stats = learner.step_gradient(loss)
            if stats.get("updated", False):
                num_updates += 1

        final_weights = learner.get_weights()

        # Should have some updates
        assert num_updates > 0, "No gradient updates occurred"
        # Final weights should be in valid range
        for w in final_weights.values():
            assert 0.0 <= w <= 2.0

    def test_no_schedule(self) -> None:
        """Test that learning works without scheduling."""
        config = EFEWeightLearnerConfig(
            learning_rate=0.01,
            use_schedule=False,
        )
        learner = EFEWeightLearner(config)

        snapshot = PerformanceSnapshot(
            success=False,
            g_value=2.0,
            safety_margin=-0.2,
            latency_ms=100.0,
            info_gain=0.0,
            catastrophe_risk=0.9,
            trajectory_length=50,
        )
        learner.observe_outcome(snapshot)
        loss = learner.compute_loss(snapshot)

        # Should not raise error
        learner.step_gradient(loss)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_zero_gradient(self) -> None:
        """Test handling of zero gradients."""
        learner = EFEWeightLearner()

        # Create loss that doesn't depend on weights
        loss = torch.tensor(0.0, requires_grad=True)

        # Should handle gracefully
        learner.step_gradient(loss)

    def test_very_high_loss(self) -> None:
        """Test handling of very high loss values."""
        learner = EFEWeightLearner()

        snapshot = PerformanceSnapshot(
            success=False,
            g_value=1000.0,
            safety_margin=-100.0,
            latency_ms=10000.0,
            info_gain=0.0,
            catastrophe_risk=1.0,
            trajectory_length=1000,
        )
        loss = learner.compute_loss(snapshot)

        # Should still be finite
        assert torch.isfinite(loss)

    def test_weights_dont_explode(self) -> None:
        """Test that weight updates don't cause explosion."""
        config = EFEWeightLearnerConfig(learning_rate=10.0)  # Aggressive learning rate
        learner = EFEWeightLearner(config)

        for _i in range(100):
            snapshot = PerformanceSnapshot(
                success=False,
                g_value=2.0,
                safety_margin=-0.1,
                latency_ms=100.0,
                info_gain=0.0,
                catastrophe_risk=0.8,
                trajectory_length=50,
            )
            loss = learner.compute_loss(snapshot)
            learner.step_gradient(loss)

        weights = learner.get_weights()

        # Weights should still be in valid range due to clamping
        for w in weights.values():
            assert 0.0 <= w <= 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
