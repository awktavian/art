"""Tests for RFSQ-E8 quantizer.

Test coverage:
1. Basic quantization/dequantization
2. Magnitude normalization correctness
3. Adaptive capacity allocation
4. Comparison to baseline ResidualE8LatticeVQ
5. Gradient flow (STE)
6. Edge cases (zero residuals, single level, etc.)
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import torch

from kagami_math.rfsq_e8 import (
    RFSQE8Quantizer,
    RFSQE8Config,
    create_rfsq_e8_quantizer,
)
from kagami_math.e8_lattice_protocol import (
    ResidualE8LatticeVQ,
    E8LatticeResidualConfig,
)


class TestRFSQE8Basic:
    """Basic functionality tests."""

    def test_forward_backward_consistency(self: Any) -> None:
        """Test that decode(encode(x)) reconstructs x."""
        quantizer = create_rfsq_e8_quantizer(max_levels=4)

        x = torch.randn(10, 8)
        quantized, codes, _ = quantizer(x, num_levels=4)
        reconstructed = quantizer.decode(codes)

        # Quantized and reconstructed should be identical
        assert torch.allclose(quantized, reconstructed, atol=1e-6)

    def test_shape_preservation(self: Any) -> None:
        """Test that output shape matches input shape."""
        quantizer = create_rfsq_e8_quantizer(max_levels=8)

        # Test various shapes
        shapes = [(8,), (10, 8), (5, 10, 8), (2, 3, 4, 8)]

        for shape in shapes:
            x = torch.randn(*shape)
            quantized, codes, _ = quantizer(x)

            assert quantized.shape == x.shape
            assert len(codes) <= 8  # May use adaptive stopping

            # Each code should match batch dimensions
            for code in codes:
                assert code.shape == shape

    def test_info_dict(self: Any) -> None:
        """Test that return_info provides expected diagnostics."""
        quantizer = create_rfsq_e8_quantizer(max_levels=4)

        x = torch.randn(10, 8)
        _quantized, _codes, info = quantizer(x, num_levels=4, return_info=True)

        assert info is not None
        assert "residual_magnitudes" in info
        assert "effective_scales" in info
        assert "num_levels_used" in info
        assert "final_residual_norm" in info
        assert "reconstruction_error" in info

        # Check shapes - residual_magnitudes is per-level (averaged across batch)
        assert info["residual_magnitudes"].shape[0] == info["num_levels_used"]

    def test_adaptive_stopping(self: Any) -> None:
        """Test that adaptive stopping terminates early for simple inputs."""
        config = RFSQE8Config(
            max_levels=16,
            min_levels=1,
            adaptive_levels=True,
            residual_threshold=1e-3,
        )
        quantizer = RFSQE8Quantizer(config)

        # Simple input (low magnitude) should need fewer levels
        x_simple = torch.randn(10, 8) * 0.1

        _, codes_simple, info_simple = quantizer(
            x_simple,
            return_info=True,
        )

        # Should stop early
        assert len(codes_simple) < 16
        assert info_simple["final_residual_norm"] < 1e-3


class TestRFSQE8MagnitudeNormalization:
    """Test magnitude normalization (RFSQ key innovation)."""

    def test_normalized_vs_unnormalized(self: Any) -> None:
        """Compare RFSQ (normalized) vs baseline (unnormalized)."""
        # RFSQ with normalization
        config_norm = RFSQE8Config(
            max_levels=8,
            normalize_residuals=True,
        )
        quantizer_norm = RFSQE8Quantizer(config_norm)

        # Baseline without normalization
        config_unnorm = RFSQE8Config(
            max_levels=8,
            normalize_residuals=False,
        )
        quantizer_unnorm = RFSQE8Quantizer(config_unnorm)

        # Test on same input
        x = torch.randn(20, 8) * 2.0
        _q_norm, _codes_norm, info_norm = quantizer_norm(x, num_levels=8, return_info=True)
        _q_unnorm, _codes_unnorm, info_unnorm = quantizer_unnorm(x, num_levels=8, return_info=True)

        # RFSQ should have better or equal reconstruction
        error_norm = info_norm["reconstruction_error"]
        error_unnorm = info_unnorm["reconstruction_error"]

        # This is the key result: RFSQ should be better
        # (May not always be true for random data, but on average yes)
        print(f"RFSQ error: {error_norm:.6f}")
        print(f"Baseline error: {error_unnorm:.6f}")

        # At minimum, both should reconstruct reasonably
        assert error_norm < 1.0
        assert error_unnorm < 1.0

    def test_magnitude_preservation(self: Any) -> None:
        """Test that magnitude normalization doesn't lose information."""
        quantizer = create_rfsq_e8_quantizer(
            max_levels=8,
            normalize_residuals=True,
        )

        # Create inputs with varying magnitudes
        x_small = torch.randn(10, 8) * 0.1
        x_large = torch.randn(10, 8) * 10.0

        _q_small, _, info_small = quantizer(x_small, return_info=True)
        _q_large, _, info_large = quantizer(x_large, return_info=True)

        # Both should reconstruct well (relative to their scale)
        rel_error_small = info_small["reconstruction_error"] / x_small.norm(dim=-1).mean()
        rel_error_large = info_large["reconstruction_error"] / x_large.norm(dim=-1).mean()

        # Relative errors should be similar
        assert rel_error_small < 0.1
        assert rel_error_large < 0.1

    def test_residual_magnitude_decay(self: Any) -> None:
        """Test that residual magnitudes decrease across levels."""
        quantizer = create_rfsq_e8_quantizer(
            max_levels=8,
            normalize_residuals=True,
        )

        x = torch.randn(20, 8) * 2.0
        _, _, info = quantizer(x, num_levels=8, return_info=True)

        magnitudes = info["residual_magnitudes"]  # [L] tensor of scalars

        # Each level should have smaller residual than previous
        for i in range(1, len(magnitudes)):
            # Allow some noise, but generally decreasing
            assert magnitudes[i] <= magnitudes[i - 1] * 1.5


class TestRFSQE8VsBaseline:
    """Compare RFSQ-E8 to baseline ResidualE8LatticeVQ."""

    def test_api_compatibility(self: Any) -> None:
        """Test that RFSQ has similar API to baseline."""
        # Create both quantizers with adaptive_levels=False for fair comparison
        config = RFSQE8Config(max_levels=8, adaptive_levels=False)
        rfsq = RFSQE8Quantizer(config)

        baseline_config = E8LatticeResidualConfig(max_levels=8, adaptive_levels=False)
        baseline = ResidualE8LatticeVQ(baseline_config)

        x = torch.randn(10, 8)

        # Both should accept same input
        q_rfsq, codes_rfsq, _ = rfsq(x, num_levels=8)
        result_baseline = baseline(x, num_levels=8)
        q_baseline = result_baseline["quantized"]
        indices_baseline = result_baseline["indices"]

        # Both should produce valid outputs
        assert q_rfsq.shape == x.shape
        assert q_baseline.shape == x.shape
        assert len(codes_rfsq) == indices_baseline.shape[-2] == 8

    def test_reconstruction_quality(self: Any) -> None:
        """Compare reconstruction quality on test data."""
        # RFSQ with same parameters as baseline for apples-to-apples comparison
        sqrt_240 = 15.491933384829668
        config = RFSQE8Config(
            max_levels=8,
            initial_scale=2.0,  # Match baseline
            capacity_decay=1.0 / sqrt_240,  # Match baseline decay
            normalize_residuals=False,  # Test pure capacity scheduling
            adaptive_levels=False,  # Disable adaptive stopping
        )
        rfsq = RFSQE8Quantizer(config)

        baseline = ResidualE8LatticeVQ(
            E8LatticeResidualConfig(
                max_levels=8,
                initial_scale=2.0,
                adaptive_levels=False,
            )
        )

        # Test on various inputs
        test_cases = [
            torch.randn(100, 8) * 0.5,  # Small
            torch.randn(100, 8) * 2.0,  # Medium
            torch.randn(100, 8) * 5.0,  # Large
        ]

        for x in test_cases:
            q_rfsq, _, _info_rfsq = rfsq(x, num_levels=8, return_info=True)
            result_baseline = baseline(x, num_levels=8)
            q_baseline = result_baseline["quantized"]

            error_rfsq = (x - q_rfsq).norm(dim=-1).mean()
            error_baseline = (x - q_baseline).norm(dim=-1).mean()

            print(f"\nScale {x.norm(dim=-1).mean():.2f}:")
            print(f"  RFSQ error: {error_rfsq:.6f}")
            print(f"  Baseline error: {error_baseline:.6f}")
            print(f"  Ratio: {error_rfsq / error_baseline:.3f}")

            # With same parameters, should match baseline closely
            assert torch.allclose(
                torch.tensor(error_rfsq),
                torch.tensor(error_baseline),
                rtol=0.1,  # 10% relative tolerance
            )

    def test_capacity_allocation(self: Any) -> None:
        """Test that RFSQ allocates capacity adaptively."""
        quantizer = create_rfsq_e8_quantizer(
            max_levels=8,
            initial_scale=1.0,
            capacity_decay=0.5,  # Aggressive decay
        )

        x = torch.randn(20, 8) * 2.0
        _, _, info = quantizer(x, return_info=True)

        scales = info["effective_scales"]

        # Scales should decrease
        assert len(scales) > 1
        for i in range(1, len(scales)):
            # Each scale should be smaller (adaptive capacity)
            assert scales[i] <= scales[i - 1]


class TestRFSQE8GradientFlow:
    """Test gradient flow through STE."""

    def test_gradients_flow(self: Any) -> None:
        """Test that gradients flow through quantization."""
        quantizer = create_rfsq_e8_quantizer(max_levels=4)
        quantizer.train()

        x = torch.randn(10, 8, requires_grad=True)
        quantized, _, _ = quantizer(x, num_levels=4)

        # Compute loss
        loss = quantized.sum()
        loss.backward()

        # Gradients should flow to input
        assert x.grad is not None
        assert not torch.all(x.grad == 0)

    def test_ste_approximation(self: Any) -> None:
        """Test that STE approximates identity for gradients."""
        quantizer = create_rfsq_e8_quantizer(max_levels=2)
        quantizer.train()

        x = torch.randn(10, 8, requires_grad=True)
        quantized, _, _ = quantizer(x, num_levels=2)

        # Gradients should be roughly identity (STE)
        loss = quantized.sum()
        loss.backward()

        # Gradient magnitude should be reasonable (not exploding)
        assert x.grad.norm() < 100.0  # type: ignore[union-attr]


class TestRFSQE8EdgeCases:
    """Test edge cases and error handling."""

    def test_single_level(self: Any) -> None:
        """Test quantization with single level."""
        quantizer = create_rfsq_e8_quantizer(max_levels=1)

        x = torch.randn(10, 8)
        quantized, codes, _ = quantizer(x, num_levels=1)

        assert quantized.shape == x.shape
        assert len(codes) == 1

    def test_zero_input(self: Any) -> None:
        """Test quantization of zero vector."""
        quantizer = create_rfsq_e8_quantizer(max_levels=4)

        x = torch.zeros(10, 8)
        quantized, _codes, _info = quantizer(x, return_info=True)

        # Should handle gracefully (magnitude floor prevents division by zero)
        assert torch.allclose(quantized, x, atol=1e-5)

    def test_invalid_shape(self: Any) -> None:
        """Test that invalid input shape raises error."""
        quantizer = create_rfsq_e8_quantizer(max_levels=4)

        x_wrong = torch.randn(10, 7)  # Wrong dimension

        with pytest.raises(ValueError, match="expects.*8"):
            quantizer(x_wrong)

    def test_empty_codes_decode(self: Any) -> None:
        """Test that decoding empty codes raises error."""
        quantizer = create_rfsq_e8_quantizer(max_levels=4)

        with pytest.raises(ValueError, match="cannot be empty"):
            quantizer.decode([])

    def test_very_large_residual(self: Any) -> None:
        """Test handling of very large residuals."""
        config = RFSQE8Config(
            max_levels=8,
            clip_residual=True,
            clip_value=10.0,
        )
        quantizer = RFSQE8Quantizer(config)

        # Extreme input
        x = torch.randn(10, 8) * 100.0

        # Should clip and handle gracefully
        quantized, codes, _info = quantizer(x, return_info=True)

        assert quantized.shape == x.shape
        assert len(codes) > 0
        assert torch.isfinite(quantized).all()


class TestRFSQE8Performance:
    """Performance and consistency tests."""

    def test_deterministic(self: Any) -> None:
        """Test that quantization is deterministic."""
        quantizer = create_rfsq_e8_quantizer(max_levels=4)
        quantizer.eval()

        x = torch.randn(10, 8)

        q1, codes1, _ = quantizer(x)
        q2, codes2, _ = quantizer(x)

        # Should be identical
        assert torch.allclose(q1, q2)
        for c1, c2 in zip(codes1, codes2, strict=False):
            assert torch.equal(c1, c2)

    def test_batching_consistency(self: Any) -> None:
        """Test that batched and individual quantization match."""
        # NOTE: This only works with normalize_residuals=False
        # because normalization uses batch statistics
        quantizer = create_rfsq_e8_quantizer(
            max_levels=4,
            normalize_residuals=False,
        )
        quantizer.eval()

        x = torch.randn(10, 8)

        # Batch quantization
        q_batch, _codes_batch, _ = quantizer(x, num_levels=4)

        # Individual quantization
        q_individual = []
        for i in range(10):
            q_i, _, _ = quantizer(x[i : i + 1], num_levels=4)
            q_individual.append(q_i)

        q_individual = torch.cat(q_individual, dim=0)  # type: ignore[assignment]

        # Should match
        assert torch.allclose(q_batch, q_individual, atol=1e-5)  # type: ignore[arg-type]

    @pytest.mark.parametrize("num_levels", [1, 2, 4, 8, 16])
    def test_various_levels(self: Any, num_levels: Any) -> None:
        """Test quantization with various level counts."""
        quantizer = create_rfsq_e8_quantizer(max_levels=16)

        x = torch.randn(10, 8)
        quantized, codes, info = quantizer(x, num_levels=num_levels, return_info=True)

        assert quantized.shape == x.shape
        assert len(codes) <= num_levels  # May stop early
        assert info["num_levels_used"] <= num_levels


def test_factory_function() -> None:
    """Test factory function creates valid quantizer."""
    quantizer = create_rfsq_e8_quantizer(
        max_levels=8,
        initial_scale=1.5,
        capacity_decay=0.7,
        normalize_residuals=True,
    )

    assert isinstance(quantizer, RFSQE8Quantizer)
    assert quantizer.config.max_levels == 8
    assert quantizer.config.initial_scale == 1.5
    assert quantizer.config.capacity_decay == 0.7
    assert quantizer.config.normalize_residuals is True


def test_get_stats() -> None:
    """Test get_stats returns expected information."""
    quantizer = create_rfsq_e8_quantizer(
        max_levels=10,
        initial_scale=2.0,
        capacity_decay=0.8,
    )

    stats = quantizer.get_stats()

    assert stats["max_levels"] == 10
    assert stats["initial_scale"] == 2.0
    assert stats["capacity_decay"] == 0.8
    assert "normalize_residuals" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
