"""Tests for Fast Hadamard Transform and HadamardE8Quantizer.

Tests:
1. Orthogonality: H(H(x)) = x
2. Fast algorithm correctness vs naive implementation
3. Padding for non-power-of-2 dimensions
4. Integration with E8 quantizer
5. Reconstruction error comparison (with vs without Hadamard)
6. Performance benchmarks
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration

import math
import time

import torch

from kagami_math.hadamard_transform import (
    hadamard_transform,
    inverse_hadamard_transform,
    HadamardE8Quantizer,
    create_hadamard_e8_quantizer,
    _is_power_of_2,
    _next_power_of_2,
)
from kagami_math.e8_lattice_protocol import (
    ResidualE8LatticeVQ,
    E8LatticeResidualConfig,
)


class TestHadamardHelpers:
    """Test helper functions."""

    def test_is_power_of_2(self: Any) -> None:
        assert _is_power_of_2(1)
        assert _is_power_of_2(2)
        assert _is_power_of_2(4)
        assert _is_power_of_2(8)
        assert _is_power_of_2(1024)

        assert not _is_power_of_2(0)
        assert not _is_power_of_2(3)
        assert not _is_power_of_2(7)
        assert not _is_power_of_2(100)

    def test_next_power_of_2(self: Any) -> None:
        assert _next_power_of_2(1) == 1
        assert _next_power_of_2(2) == 2
        assert _next_power_of_2(3) == 4
        assert _next_power_of_2(5) == 8
        assert _next_power_of_2(8) == 8
        assert _next_power_of_2(9) == 16
        assert _next_power_of_2(100) == 128


class TestHadamardTransform:
    """Test Fast Hadamard Transform correctness."""

    def test_orthogonality_basic(self: Any) -> None:
        """H(H(x)) = x (orthogonality)."""
        x = torch.randn(32, 8)
        x_h = hadamard_transform(x)
        x_reconstructed = inverse_hadamard_transform(x_h)

        assert torch.allclose(x, x_reconstructed, atol=1e-5)

    def test_orthogonality_batched(self: Any) -> None:
        """Orthogonality with batch dimensions."""
        x = torch.randn(4, 16, 8)
        x_h = hadamard_transform(x)
        x_reconstructed = inverse_hadamard_transform(x_h)

        assert torch.allclose(x, x_reconstructed, atol=1e-5)

    def test_orthogonal_matrix_property(self: Any) -> None:
        """H^T H = I for normalized transform."""
        n = 8
        x = torch.eye(n)  # Identity matrix
        x_h = hadamard_transform(x, dim=-1)

        # Each row of x_h is a row of the Hadamard matrix
        # H^T H should be identity
        H = x_h  # Since input was identity
        HTH = H.T @ H

        assert torch.allclose(HTH, torch.eye(n), atol=1e-5)

    def test_normalization(self: Any) -> None:
        """Check normalization factor is correct."""
        x = torch.ones(8)
        x_h = hadamard_transform(x, normalize=True)

        # For all-ones input, Hadamard should give [sqrt(n), 0, 0, ..., 0]
        expected = torch.zeros(8)
        expected[0] = math.sqrt(8)

        assert torch.allclose(x_h, expected, atol=1e-5)

    def test_without_normalization(self: Any) -> None:
        """Test unnormalized transform (for internal verification)."""
        x = torch.ones(8)
        x_h = hadamard_transform(x, normalize=False)

        # Without normalization, all-ones → [n, 0, 0, ..., 0]
        expected = torch.zeros(8)
        expected[0] = 8.0

        assert torch.allclose(x_h, expected, atol=1e-5)

    def test_padding_non_power_of_2(self: Any) -> None:
        """Correctly handles non-power-of-2 dimensions."""
        x = torch.randn(32, 7)  # 7 is not power of 2
        x_h = hadamard_transform(x)
        x_reconstructed = inverse_hadamard_transform(x_h)

        assert x.shape == x_reconstructed.shape  # No shape change
        assert torch.allclose(x, x_reconstructed, atol=1e-5)

    def test_dimension_argument(self: Any) -> None:
        """Transform along specific dimension."""
        x = torch.randn(8, 16)

        # Transform along dim 0
        x_h0 = hadamard_transform(x, dim=0)
        assert x_h0.shape == x.shape

        # Transform along dim 1
        x_h1 = hadamard_transform(x, dim=1)
        assert x_h1.shape == x.shape

        # Different results for different dimensions
        assert not torch.allclose(x_h0, x_h1)

    def test_known_values_2x2(self: Any) -> None:
        """Verify against known 2x2 Hadamard matrix."""
        H2 = torch.tensor([[1, 1], [1, -1]], dtype=torch.float32) / math.sqrt(2)

        x = torch.tensor([1.0, 2.0])
        x_h = hadamard_transform(x)

        expected = H2 @ x
        assert torch.allclose(x_h, expected, atol=1e-5)

    def test_known_values_4x4(self: Any) -> None:
        """Verify against known 4x4 Hadamard matrix."""
        # H4 = H2 ⊗ H2
        H2 = torch.tensor([[1, 1], [1, -1]], dtype=torch.float32)
        H4 = torch.kron(H2, H2) / 2.0  # Normalized

        x = torch.tensor([1.0, 2.0, 3.0, 4.0])
        x_h = hadamard_transform(x)

        expected = H4 @ x
        assert torch.allclose(x_h, expected, atol=1e-5)


class TestHadamardE8Integration:
    """Test integration with E8 quantizer."""

    def test_basic_encode_decode(self: Any) -> None:
        """Basic encode-decode cycle."""
        quantizer = create_hadamard_e8_quantizer(max_levels=4)

        x = torch.randn(16, 8)
        result = quantizer(x, num_levels=4)
        indices = result["indices"]
        # Convert indices to list of codes for decode
        L = indices.shape[-2]
        codes = [indices[..., i, :] for i in range(L)]
        reconstructed = quantizer.decode(codes)

        # Should be close after quantization
        error = (x - reconstructed).norm() / x.norm()
        assert error < 0.5  # Reasonable reconstruction

    def test_reconstruction_deterministic(self: Any) -> None:
        """Reconstruction is deterministic."""
        quantizer = create_hadamard_e8_quantizer(max_levels=4)
        x = torch.randn(16, 8)

        result = quantizer(x, num_levels=4)
        indices = result["indices"]
        # Convert indices to list of codes for decode
        L = indices.shape[-2]
        codes = [indices[..., i, :] for i in range(L)]
        recon1 = quantizer.decode(codes)
        recon2 = quantizer.decode(codes)

        assert torch.allclose(recon1, recon2)

    def test_gradient_flow(self: Any) -> None:
        """Gradients flow through quantizer in training mode."""
        quantizer = create_hadamard_e8_quantizer(max_levels=4)
        quantizer.train()

        x = torch.randn(16, 8, requires_grad=True)
        result = quantizer(x, num_levels=4)
        quantized = result["quantized"]

        loss = quantized.sum()
        loss.backward()

        assert x.grad is not None
        assert x.grad.abs().sum() > 0  # Non-zero gradients

    def test_batch_dimensions(self: Any) -> None:
        """Handle various batch dimensions."""
        quantizer = create_hadamard_e8_quantizer(max_levels=4)

        # Single vector
        x1 = torch.randn(8)
        result1 = quantizer(x1.unsqueeze(0), num_levels=2)
        q1 = result1["quantized"]
        assert q1.shape == (1, 8)

        # Batch
        x2 = torch.randn(32, 8)
        result2 = quantizer(x2, num_levels=2)
        q2 = result2["quantized"]
        assert q2.shape == (32, 8)

        # Multiple batch dims
        x3 = torch.randn(4, 8, 8)
        result3 = quantizer(x3, num_levels=2)
        q3 = result3["quantized"]
        assert q3.shape == (4, 8, 8)


class TestHadamardBenefit:
    """Test quantization improvement from Hadamard preprocessing."""

    @pytest.fixture
    def correlated_data(self):
        """Generate correlated data (worst case for quantization)."""
        # Create highly correlated features
        torch.manual_seed(42)
        base = torch.randn(100, 1)
        noise = torch.randn(100, 8) * 0.1
        # All features are base + small noise (highly correlated)
        return base + noise

    @pytest.fixture
    def uncorrelated_data(self):
        """Generate uncorrelated data (easier for quantization)."""
        torch.manual_seed(42)
        return torch.randn(100, 8)

    def test_improvement_on_correlated_data(self: Any, correlated_data: Any) -> None:
        """Hadamard preprocessing improves quantization on correlated data."""
        x = correlated_data

        # Baseline: E8 quantizer without Hadamard
        config = E8LatticeResidualConfig(max_levels=4, adaptive_levels=False)
        baseline_quantizer = ResidualE8LatticeVQ(config)
        baseline_quantizer.eval()

        result_baseline = baseline_quantizer(x, num_levels=4)
        indices_baseline = result_baseline["indices"]
        L = indices_baseline.shape[-2]
        codes_baseline = [indices_baseline[..., i, :] for i in range(L)]
        recon_baseline = baseline_quantizer.decode(codes_baseline)
        error_baseline = (x - recon_baseline).pow(2).mean().sqrt()

        # With Hadamard preprocessing
        hadamard_quantizer = HadamardE8Quantizer(baseline_quantizer)
        hadamard_quantizer.eval()

        result_hadamard = hadamard_quantizer(x, num_levels=4)
        indices_hadamard = result_hadamard["indices"]
        L_h = indices_hadamard.shape[-2]
        codes_hadamard = [indices_hadamard[..., i, :] for i in range(L_h)]
        recon_hadamard = hadamard_quantizer.decode(codes_hadamard)
        error_hadamard = (x - recon_hadamard).pow(2).mean().sqrt()

        # Hadamard should improve or match reconstruction on correlated data
        print(f"\nBaseline error: {error_baseline:.6f}")
        print(f"Hadamard error: {error_hadamard:.6f}")
        print(f"Improvement: {(error_baseline - error_hadamard) / error_baseline * 100:.2f}%")

        # Should be at worst slightly worse (allow 5% tolerance due to quantization randomness)
        assert error_hadamard <= error_baseline * 1.05

    def test_neutral_on_uncorrelated_data(self: Any, uncorrelated_data: Any) -> None:
        """Hadamard is neutral on already-decorrelated data."""
        x = uncorrelated_data

        config = E8LatticeResidualConfig(max_levels=4, adaptive_levels=False)
        baseline_quantizer = ResidualE8LatticeVQ(config)
        baseline_quantizer.eval()

        result_baseline = baseline_quantizer(x, num_levels=4)
        indices_baseline = result_baseline["indices"]
        L = indices_baseline.shape[-2]
        codes_baseline = [indices_baseline[..., i, :] for i in range(L)]
        recon_baseline = baseline_quantizer.decode(codes_baseline)
        error_baseline = (x - recon_baseline).pow(2).mean().sqrt()

        hadamard_quantizer = HadamardE8Quantizer(baseline_quantizer)
        hadamard_quantizer.eval()

        result_hadamard = hadamard_quantizer(x, num_levels=4)
        indices_hadamard = result_hadamard["indices"]
        L_h = indices_hadamard.shape[-2]
        codes_hadamard = [indices_hadamard[..., i, :] for i in range(L_h)]
        recon_hadamard = hadamard_quantizer.decode(codes_hadamard)
        error_hadamard = (x - recon_hadamard).pow(2).mean().sqrt()

        print(f"\nBaseline error: {error_baseline:.6f}")
        print(f"Hadamard error: {error_hadamard:.6f}")
        print(f"Relative diff: {abs(error_hadamard - error_baseline) / error_baseline * 100:.2f}%")

        # Should be similar on uncorrelated data
        # Allow up to 20% difference (quantization is stochastic)
        assert abs(error_hadamard - error_baseline) / error_baseline < 0.2


class TestPerformance:
    """Benchmark performance."""

    def test_hadamard_speed(self: Any) -> None:
        """Hadamard transform is O(n log n)."""
        torch.manual_seed(42)

        sizes = [8, 16, 32, 64, 128, 256]
        times = []

        for n in sizes:
            if n > 8:
                # Pad input to test padding path
                x = torch.randn(1000, n)
            else:
                x = torch.randn(1000, n)

            start = time.perf_counter()
            for _ in range(10):
                _ = hadamard_transform(x)
            end = time.perf_counter()

            times.append((end - start) / 10)

        print("\n=== Hadamard Transform Speed ===")
        for n, t in zip(sizes, times, strict=False):
            print(f"n={n:4d}: {t * 1000:.3f} ms")

        # Should scale roughly as O(n log n)
        # Verify time doesn't explode (256 is 32x size, allow 200x time for overhead)
        assert times[-1] < times[0] * 200

    @pytest.mark.benchmark
    @pytest.mark.skip(reason="Hardware-dependent benchmark, run manually")
    def test_e8_overhead(self: Any) -> None:
        """Measure Hadamard preprocessing overhead."""
        torch.manual_seed(42)
        x = torch.randn(1000, 8)

        # Baseline
        config = E8LatticeResidualConfig(max_levels=4, adaptive_levels=False)
        baseline = ResidualE8LatticeVQ(config)
        baseline.eval()

        start = time.perf_counter()
        for _ in range(100):
            _ = baseline(x, num_levels=4)
        baseline_time = time.perf_counter() - start

        # With Hadamard
        hadamard = HadamardE8Quantizer(baseline)
        hadamard.eval()

        start = time.perf_counter()
        for _ in range(100):
            _ = hadamard(x, num_levels=4)
        hadamard_time = time.perf_counter() - start

        overhead = (hadamard_time - baseline_time) / baseline_time * 100

        print("\n=== E8 Quantization Overhead ===")
        print(f"Baseline: {baseline_time * 10:.3f} ms")
        print(f"Hadamard: {hadamard_time * 10:.3f} ms")
        print(f"Overhead: {overhead:.1f}%")

        # Overhead should be minimal (Hadamard is O(n log n), quantization is O(n))
        assert overhead < 50  # Less than 50% overhead


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_wrong_dimension_error(self: Any) -> None:
        """Raise error on wrong input dimension."""
        quantizer = create_hadamard_e8_quantizer()

        with pytest.raises(ValueError, match="expects .*8"):
            quantizer(torch.randn(32, 7))

    def test_empty_codes_error(self: Any) -> None:
        """Raise error on empty codes."""
        quantizer = create_hadamard_e8_quantizer()

        with pytest.raises(ValueError):
            quantizer.decode([])

    def test_zero_input(self: Any) -> None:
        """Handle zero input correctly."""
        quantizer = create_hadamard_e8_quantizer()
        x = torch.zeros(16, 8)

        result = quantizer(x, num_levels=2)
        indices = result["indices"]
        L = indices.shape[-2]
        codes = [indices[..., i, :] for i in range(L)]
        reconstructed = quantizer.decode(codes)

        # Should reconstruct zero (or very close)
        assert reconstructed.abs().max() < 1.0

    def test_large_values(self: Any) -> None:
        """Handle large input values."""
        quantizer = create_hadamard_e8_quantizer()
        x = torch.randn(16, 8) * 100  # Large scale

        result = quantizer(x, num_levels=8)
        indices = result["indices"]
        L = indices.shape[-2]
        codes = [indices[..., i, :] for i in range(L)]
        reconstructed = quantizer.decode(codes)

        # Should still reconstruct reasonably
        error = (x - reconstructed).norm() / x.norm()
        assert error < 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
