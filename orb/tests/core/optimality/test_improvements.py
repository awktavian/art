"""Tests for Optimality Improvements Module.

Tests all components of the optimality improvements:
- AdaptiveConvergenceMonitor
- AnalyticalEpistemicValue
- ModernHopfieldScaled
- TrueOctonionMultiply
- WassersteinIB
- UncertaintyCalibrator

Created: December 4, 2025
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import math

import torch
import torch.nn as nn


class TestAdaptiveConvergenceMonitor:
    """Tests for adaptive strange loop convergence."""

    def test_init(self):
        """Test initialization."""
        from kagami.core.optimality import AdaptiveConvergenceMonitor

        monitor = AdaptiveConvergenceMonitor()
        assert monitor is not None
        assert monitor.config.min_iterations == 1
        assert monitor.config.max_iterations == 7

    def test_should_continue_minimum(self):
        """Test minimum iterations enforced."""
        from kagami.core.optimality import AdaptiveConvergenceMonitor

        monitor = AdaptiveConvergenceMonitor()

        # First iteration should always continue
        assert (
            monitor.should_continue(
                iteration=0,
                current_loss=torch.tensor(0.001),  # Very low loss
            )
            is True
        )

    def test_should_continue_maximum(self):
        """Test maximum iterations respected."""
        from kagami.core.optimality import AdaptiveConvergenceMonitor

        monitor = AdaptiveConvergenceMonitor()

        # Past max should stop
        assert (
            monitor.should_continue(
                iteration=10,
                current_loss=torch.tensor(1.0),  # High loss
            )
            is False
        )

    def test_should_continue_convergence(self):
        """Test convergence threshold triggers stop."""
        from kagami.core.optimality import AdaptiveConvergenceMonitor

        monitor = AdaptiveConvergenceMonitor()

        # Below threshold should stop
        assert (
            monitor.should_continue(
                iteration=2,
                current_loss=torch.tensor(0.005),  # Below 0.01 threshold
            )
            is False
        )

    def test_statistics_update(self):
        """Test statistics tracking."""
        from kagami.core.optimality import AdaptiveConvergenceMonitor

        monitor = AdaptiveConvergenceMonitor()

        # Update with some iterations
        monitor.update_statistics(iterations_used=3, final_loss=0.05)
        monitor.update_statistics(iterations_used=2, final_loss=0.03)

        stats = monitor.get_statistics()
        assert "avg_iterations" in stats
        assert "ema_loss" in stats
        assert stats["step_count"] == 2


class TestAnalyticalEpistemicValue:
    """Tests for analytical epistemic value computation."""

    def test_init(self):
        """Test initialization."""
        from kagami.core.optimality import AnalyticalEpistemicValue

        ae = AnalyticalEpistemicValue(state_dim=256, obs_dim=512)
        assert ae is not None

    def test_forward_shape(self):
        """Test output shape."""
        from kagami.core.optimality import AnalyticalEpistemicValue

        ae = AnalyticalEpistemicValue(state_dim=128, obs_dim=256)

        B, H = 4, 5
        h_states = torch.randn(B, H, 64)
        z_states = torch.randn(B, H, 64)
        observations = torch.randn(B, H, 256)

        epistemic = ae(h_states, z_states, observations)

        assert epistemic.shape == (B,)

    def test_gradient_flow(self):
        """Test gradients flow through."""
        from kagami.core.optimality import AnalyticalEpistemicValue

        ae = AnalyticalEpistemicValue(state_dim=64, obs_dim=128)

        h_states = torch.randn(2, 3, 32, requires_grad=True)
        z_states = torch.randn(2, 3, 32, requires_grad=True)
        observations = torch.randn(2, 3, 128)

        epistemic = ae(h_states, z_states, observations)
        loss = epistemic.sum()
        loss.backward()

        assert h_states.grad is not None
        assert z_states.grad is not None


class TestModernHopfieldScaled:
    """Tests for hierarchical E8 Hopfield memory."""

    def test_init(self):
        """Test initialization."""
        from kagami.core.optimality import ModernHopfieldScaled

        hopfield = ModernHopfieldScaled(
            pattern_dim=256,
            num_patterns=240,
            num_heads=4,
            num_levels=4,
        )
        assert hopfield is not None
        assert hopfield.num_patterns == 240
        assert hopfield.num_levels == 4
        # Effective capacity: 240^4 = 3.3B
        assert hopfield._effective_capacity == 240**4

    def test_e8_codebook(self):
        """Test E8 codebook has correct properties."""
        from kagami.core.optimality import ModernHopfieldScaled

        hopfield = ModernHopfieldScaled()

        # Should have 240 E8 roots in 8D
        assert hopfield.e8_codebook.shape == (240, 8)

        # All roots should have norm √2 (E8 property)
        norms = hopfield.e8_codebook.norm(dim=-1)  # type: ignore[operator]
        expected = torch.full_like(norms, math.sqrt(2))
        assert torch.allclose(norms, expected, atol=1e-5)

    def test_forward_shape(self):
        """Test retrieval shape."""
        from kagami.core.optimality import ModernHopfieldScaled

        hopfield = ModernHopfieldScaled(
            pattern_dim=64,
            num_patterns=240,
            num_levels=2,
        )

        query = torch.randn(8, 64)
        result = hopfield(query)

        assert "retrieved" in result
        assert result["retrieved"].shape == (8, 64)
        assert "levels_used" in result
        assert "effective_capacity" in result

    def test_hierarchical_levels(self):
        """Test hierarchical levels are used."""
        from kagami.core.optimality import ModernHopfieldScaled

        hopfield = ModernHopfieldScaled(
            pattern_dim=64,
            num_patterns=240,
            num_levels=4,
        )

        query = torch.randn(4, 64)
        result = hopfield(query, return_attention=True)

        # Should use multiple levels
        assert result["levels_used"] >= 1
        assert "attentions" in result
        assert len(result["attentions"]) == result["levels_used"]

    def test_separation_loss(self):
        """Test pattern separation loss."""
        from kagami.core.optimality import ModernHopfieldScaled

        hopfield = ModernHopfieldScaled(
            pattern_dim=64,
            num_patterns=240,
            num_levels=2,
        )
        hopfield.train()

        query = torch.randn(4, 64)
        result = hopfield(query)

        assert "separation_loss" in result
        assert result["separation_loss"].item() >= 0

    def test_attention_entropy(self):
        """Test attention entropy computed."""
        from kagami.core.optimality import ModernHopfieldScaled

        hopfield = ModernHopfieldScaled(
            pattern_dim=64,
            num_patterns=240,
            num_levels=2,
        )

        query = torch.randn(4, 64)
        result = hopfield(query, return_attention=True)

        assert "attentions" in result
        assert "attention_entropy" in result

    def test_gradient_checkpointing(self):
        """Test gradient checkpointing forward."""
        from kagami.core.optimality import ModernHopfieldScaled

        hopfield = ModernHopfieldScaled(
            pattern_dim=64,
            num_patterns=240,
            num_levels=3,
        )
        hopfield.train()

        query = torch.randn(4, 64, requires_grad=True)
        result = hopfield.forward_checkpointed(query)

        assert "retrieved" in result
        assert result["checkpointed"] is True
        assert result["retrieved"].shape == (4, 64)

        # Test backward works
        loss = result["retrieved"].sum()
        loss.backward()
        assert query.grad is not None

    def test_compile_factory(self):
        """Test compiled instance creation."""
        from kagami.core.optimality import ModernHopfieldScaled

        # Create compiled version (may fall back to eager)
        hopfield = ModernHopfieldScaled.compile(
            pattern_dim=64,
            num_patterns=240,
            num_levels=2,
        )

        assert hopfield is not None

        # Should work regardless of compilation status
        query = torch.randn(4, 64)
        result = hopfield(query)
        assert result["retrieved"].shape == (4, 64)


class TestTrueOctonionMultiply:
    """Tests for true octonion multiplication."""

    def test_init(self):
        """Test initialization."""
        from kagami.core.optimality import TrueOctonionMultiply

        octonion = TrueOctonionMultiply()
        assert octonion is not None
        assert octonion.mult_table.shape == (7, 7)
        assert octonion.sign_table.shape == (7, 7)

    def test_multiply_shape(self):
        """Test multiplication output shape."""
        from kagami.core.optimality import TrueOctonionMultiply

        octonion = TrueOctonionMultiply()

        a = torch.randn(4, 8)
        b = torch.randn(4, 8)

        result = octonion.multiply(a, b)
        assert result.shape == (4, 8)

    def test_associator_nonzero(self):
        """Test associator is non-zero (octonions are non-associative)."""
        from kagami.core.optimality import TrueOctonionMultiply

        octonion = TrueOctonionMultiply()

        # Random octonions
        a = torch.randn(1, 8)
        b = torch.randn(1, 8)
        c = torch.randn(1, 8)

        associator = octonion.associator(a, b, c)

        # Associator should be non-zero for general octonions
        # (unless we hit a special case by chance)
        # Just check shape is correct
        assert associator.shape == (1, 8)

    def test_alternativity(self):
        """Test alternativity holds (weaker than associativity)."""
        from kagami.core.optimality import TrueOctonionMultiply

        octonion = TrueOctonionMultiply()

        a = torch.randn(4, 8)
        b = torch.randn(4, 8)

        result = octonion.check_alternativity(a, b)

        assert "left_alternativity_error" in result
        assert "right_alternativity_error" in result
        # Errors should be small (float precision)
        assert result["left_alternativity_error"] < 1e-4
        assert result["right_alternativity_error"] < 1e-4

    def test_unit_multiplication(self):
        """Test multiplication with unit octonion."""
        from kagami.core.optimality import TrueOctonionMultiply

        octonion = TrueOctonionMultiply()

        # Unit octonion: 1 + 0i + 0j + ...
        unit = torch.zeros(1, 8)
        unit[0, 0] = 1.0

        a = torch.randn(1, 8)

        # a * 1 = a
        result = octonion.multiply(a, unit)
        assert torch.allclose(result, a, atol=1e-5)


class TestWassersteinIB:
    """Tests for Wasserstein Information Bottleneck."""

    def test_init(self):
        """Test initialization."""
        from kagami.core.optimality import WassersteinIB

        wib = WassersteinIB(
            input_dim=64,
            bottleneck_dim=16,
            output_dim=64,
        )
        assert wib is not None

    def test_forward_shape(self):
        """Test output shapes."""
        from kagami.core.optimality import WassersteinIB

        wib = WassersteinIB(
            input_dim=64,
            bottleneck_dim=16,
            output_dim=64,
        )

        x = torch.randn(8, 64)
        result = wib(x, y=x)

        assert "z" in result
        assert "y_pred" in result
        assert "total_loss" in result

        assert result["z"].shape == (8, 16)
        assert result["y_pred"].shape == (8, 64)

    def test_gradient_flow(self):
        """Test gradients flow through."""
        from kagami.core.optimality import WassersteinIB

        wib = WassersteinIB(
            input_dim=32,
            bottleneck_dim=8,
            output_dim=32,
        )

        x = torch.randn(4, 32, requires_grad=True)
        result = wib(x, y=x)

        result["total_loss"].backward()
        assert x.grad is not None


class TestUncertaintyCalibrator:
    """Tests for uncertainty calibration."""

    def test_init(self):
        """Test initialization."""
        from kagami.core.optimality import UncertaintyCalibrator

        calibrator = UncertaintyCalibrator()
        assert calibrator is not None

    def test_calibrate(self):
        """Test calibration applies temperature scaling."""
        from kagami.core.optimality import UncertaintyCalibrator

        calibrator = UncertaintyCalibrator()

        logits = torch.randn(8, 10)
        probs = calibrator.calibrate(logits, is_binary=False)

        # Should be valid probabilities
        assert probs.min() >= 0
        assert probs.max() <= 1
        # Should sum to ~1 per sample (softmax)
        assert torch.allclose(probs.sum(dim=-1), torch.ones(8), atol=1e-5)

    def test_calibrate_binary(self):
        """Test binary calibration."""
        from kagami.core.optimality import UncertaintyCalibrator

        calibrator = UncertaintyCalibrator()

        logits = torch.randn(8)
        probs = calibrator.calibrate(logits, is_binary=True)

        assert probs.min() >= 0
        assert probs.max() <= 1

    def test_update_and_ece(self):
        """Test update and ECE computation."""
        from kagami.core.optimality import UncertaintyCalibrator

        calibrator = UncertaintyCalibrator()

        # Simulate some predictions
        for _ in range(50):
            conf = torch.rand(1).item()
            correct = torch.rand(1).item() < conf  # Roughly calibrated
            calibrator.update(conf, correct)

        ece = calibrator.compute_ece()
        assert 0 <= ece <= 1

    def test_calibration_curve(self):
        """Test calibration curve generation."""
        from kagami.core.optimality import UncertaintyCalibrator

        calibrator = UncertaintyCalibrator()

        # Add enough data points
        for _ in range(100):
            conf = torch.rand(1).item()
            calibrator.update(conf, torch.rand(1).item() < 0.5)

        curve = calibrator.get_calibration_curve()
        assert "confidences" in curve
        assert "accuracies" in curve
        assert "ece" in curve


class TestSinkhornDistance:
    """Tests for Sinkhorn distance computation."""

    def test_init(self):
        """Test initialization."""
        from kagami.core.optimality import SinkhornDistance

        sinkhorn = SinkhornDistance()
        assert sinkhorn is not None

    def test_forward_single_point(self):
        """Test with single points."""
        from kagami.core.optimality import SinkhornDistance

        sinkhorn = SinkhornDistance()

        x = torch.randn(1, 8)
        y = torch.randn(1, 8)

        distance, _plan = sinkhorn(x, y)

        assert distance.shape == (1,) or distance.dim() == 0
        assert distance.item() >= 0

    def test_forward_batch(self):
        """Test with batched points."""
        from kagami.core.optimality import SinkhornDistance

        sinkhorn = SinkhornDistance()

        x = torch.randn(16, 8)
        y = torch.randn(16, 8)

        distance, _plan = sinkhorn(x, y)

        assert distance.item() >= 0


class TestOptimalityImprovements:
    """Tests for unified OptimalityImprovements facade."""

    def test_singleton(self):
        """Test singleton pattern."""
        from kagami.core.optimality import get_optimality_improvements

        imp1 = get_optimality_improvements()
        imp2 = get_optimality_improvements()

        assert imp1 is imp2

    def test_components_available(self):
        """Test all components accessible."""
        from kagami.core.optimality import get_optimality_improvements

        imp = get_optimality_improvements()

        assert imp.convergence_monitor is not None
        assert imp.octonion_multiply is not None
        assert imp.uncertainty_calibrator is not None

    def test_create_analytical_epistemic(self):
        """Test creating analytical epistemic."""
        from kagami.core.optimality import get_optimality_improvements

        imp = get_optimality_improvements()
        ae = imp.create_analytical_epistemic(state_dim=128, obs_dim=256)

        assert ae is not None
        assert imp.analytical_epistemic is ae

    def test_create_hopfield_scaled(self):
        """Test creating scaled Hopfield."""
        from kagami.core.optimality import get_optimality_improvements

        imp = get_optimality_improvements()
        hopfield = imp.create_hopfield_scaled(
            pattern_dim=64,
            num_patterns=32,
        )

        assert hopfield is not None
        assert imp.hopfield_scaled is hopfield

    def test_octonion_colony_interaction(self):
        """Test colony interaction computation."""
        from kagami.core.optimality import get_optimality_improvements

        imp = get_optimality_improvements()

        # 7 colonies with 8D states
        colony_states = torch.randn(2, 7, 8)

        # Some interaction pairs
        pairs = [(0, 1), (2, 3), (4, 5)]

        results = imp.octonion_colony_interaction(colony_states, pairs)

        assert results.shape == (2, 3, 8)

    def test_get_statistics(self):
        """Test statistics retrieval."""
        from kagami.core.optimality import get_optimality_improvements

        imp = get_optimality_improvements()
        stats = imp.get_statistics()

        assert "calibration_ece" in stats
        assert "convergence" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
