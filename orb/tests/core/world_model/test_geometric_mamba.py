"""Tests for Geometric Mamba (SSM on manifolds)."""

from __future__ import annotations

import pytest

import torch

from kagami.core.world_model.layers.geometric_mamba import (
    GeometricMamba,
    GeometricMambaBlock,
    SelectiveScan,
    create_geometric_mamba,
    parallel_associative_scan,
    _sequential_scan_fast,
)

pytestmark = pytest.mark.tier_integration


class TestSelectiveScan:
    """Test the selective scan operation."""

    def test_forward_shape(self) -> None:
        """Test output shape is correct."""
        d_state = 16
        d_model = 128
        scan = SelectiveScan(d_state=d_state, d_model=d_model)

        B, L, D = 4, 10, d_model
        x = torch.randn(B, L, D)

        output = scan(x)

        assert output.shape == (B, L, D)

    def test_forward_no_nan(self) -> None:
        """Test output contains no NaN values."""
        scan = SelectiveScan(d_state=16, d_model=128)
        x = torch.randn(4, 10, 128)

        output = scan(x)

        assert not torch.isnan(output).any()


class TestGeometricMambaBlock:
    """Test the Geometric Mamba block."""

    def test_init(self) -> None:
        """Test initialization."""
        block = GeometricMambaBlock(
            d_model=128,
            d_state=16,
            hyperbolic_dim=14,
            num_oct_heads=1,
        )

        assert block.d_model == 128
        assert block.d_state == 16
        assert block.hyperbolic_dim == 14
        assert block.num_oct_heads == 1

    def test_forward_shape(self) -> None:
        """Test forward pass produces correct output shape."""
        block = GeometricMambaBlock(d_model=128, hyperbolic_dim=14)

        B, L, D = 4, 10, 128
        x = torch.randn(B, L, D)

        output = block(x)

        assert output.shape == (B, L, D)

    def test_forward_no_nan(self) -> None:
        """Test forward pass produces no NaN values."""
        block = GeometricMambaBlock(d_model=128, hyperbolic_dim=14)
        x = torch.randn(4, 10, 128)

        output = block(x)

        assert not torch.isnan(output).any()

    def test_residual_connection(self) -> None:
        """Test residual connection is working."""
        block = GeometricMambaBlock(d_model=128, hyperbolic_dim=14)
        x = torch.randn(4, 10, 128)

        output = block(x)

        # Output should be related to input (residual maintains information)
        # Just check that output isn't all zeros or NaN
        assert not torch.allclose(output, torch.zeros_like(output))
        assert not torch.isnan(output).any()


class TestGeometricMamba:
    """Test the full Geometric Mamba model."""

    def test_init(self) -> None:
        """Test initialization with default parameters."""
        model = GeometricMamba(d_model=128, n_layers=4)

        assert model.d_model == 128
        assert len(model.layers) == 4

    def test_forward_shape(self) -> None:
        """Test forward pass shape."""
        model = GeometricMamba(d_model=128, n_layers=2, hyperbolic_dim=14)

        B, L, D = 4, 10, 128
        x = torch.randn(B, L, D)

        output = model(x)

        assert output.shape == (B, L, D)

    def test_forward_deterministic(self) -> None:
        """Test that forward pass is deterministic (same input → same output)."""
        model = GeometricMamba(d_model=128, n_layers=2)
        model.eval()

        x = torch.randn(4, 10, 128)

        output1 = model(x)
        output2 = model(x)

        torch.testing.assert_close(output1, output2)

    def test_create_factory(self) -> None:
        """Test factory function."""
        model = create_geometric_mamba(d_model=128, n_layers=2)

        assert isinstance(model, GeometricMamba)
        assert model.d_model == 128


class TestGeometricMambaIntegration:
    """Integration tests for Geometric Mamba."""

    def test_linear_complexity(self) -> None:
        """Test that computation scales linearly with sequence length."""
        import time

        model = GeometricMamba(d_model=128, n_layers=2)

        model.eval()

        # Test on different sequence lengths
        times = []
        lengths = [10, 20, 40]

        for L in lengths:
            x = torch.randn(1, L, 128)

            # Warmup
            with torch.no_grad():
                _ = model(x)

            start = time.time()
            with torch.no_grad():
                _ = model(x)
            times.append(time.time() - start)

        # Check that it doesn't scale quadratically (very lenient test)
        # For O(n²), time would scale by 4× when length doubles
        # For O(n), time would scale by 2× when length doubles
        ratio_time = times[2] / times[0]  # L=40 vs L=10
        ratio_length = lengths[2] / lengths[0]  # 4×

        # If quadratic, expect ~16× time, if linear expect ~4× time
        # So check it's closer to linear (< 8× time for 4× length)
        assert ratio_time < ratio_length * 2  # Very lenient bound

    def test_gradient_flow(self) -> None:
        """Test that gradients flow through the model."""
        model = GeometricMamba(d_model=128, n_layers=2)

        x = torch.randn(4, 10, 128, requires_grad=True)
        output = model(x)

        # Backward pass
        loss = output.sum()
        loss.backward()

        # Check gradients exist
        assert x.grad is not None
        assert not torch.isnan(x.grad).any()

        # Check model parameters have gradients
        for param in model.parameters():
            if param.requires_grad:
                assert param.grad is not None


class TestParallelScan:
    """Tests for parallel associative scan with in-place index_copy_ optimization."""

    def test_parallel_scan_correctness(self) -> None:
        """Test parallel scan produces same results as sequential scan."""
        B, L, D = 2, 1024, 32  # L > 512 to trigger parallel path
        A = torch.rand(B, L, D) * 0.9 + 0.05  # Decay in (0.05, 0.95)
        Bu = torch.randn(B, L, D)

        # Sequential reference
        h_seq = _sequential_scan_fast(A, Bu)

        # Parallel implementation
        h_par = parallel_associative_scan(A, Bu)

        torch.testing.assert_close(h_par, h_seq, rtol=1e-4, atol=1e-4)

    def test_parallel_scan_gradient_flow(self) -> None:
        """Test gradients flow correctly through index_copy_ optimization."""
        B, L, D = 2, 1024, 32  # L > 512 to trigger parallel path

        # Create leaf tensors first, then scale (so we can check leaf grads)
        A_raw = torch.rand(B, L, D)
        A = (A_raw * 0.9 + 0.05).clone().detach().requires_grad_(True)
        Bu = torch.randn(B, L, D, requires_grad=True)

        # Forward
        h = parallel_associative_scan(A, Bu)
        loss = h.sum()

        # Backward
        loss.backward()

        # Gradients should exist and be non-zero
        assert A.grad is not None, "A should have gradients"
        assert Bu.grad is not None, "Bu should have gradients"
        assert not torch.isnan(A.grad).any(), "A gradients should not be NaN"
        assert not torch.isnan(Bu.grad).any(), "Bu gradients should not be NaN"
        assert A.grad.abs().sum() > 0, "A gradients should be non-zero"
        assert Bu.grad.abs().sum() > 0, "Bu gradients should be non-zero"

    def test_parallel_scan_gradient_matches_sequential(self) -> None:
        """Test parallel scan gradients match sequential scan gradients."""
        B, L, D = 2, 64, 16  # Smaller for numerical comparison

        # Create inputs that require grad
        A_base = torch.rand(B, L, D) * 0.9 + 0.05
        Bu_base = torch.randn(B, L, D)

        # Sequential reference
        A_seq = A_base.clone().requires_grad_(True)
        Bu_seq = Bu_base.clone().requires_grad_(True)
        h_seq = _sequential_scan_fast(A_seq, Bu_seq)
        loss_seq = h_seq.sum()
        loss_seq.backward()

        # Parallel implementation
        A_par = A_base.clone().requires_grad_(True)
        Bu_par = Bu_base.clone().requires_grad_(True)
        h_par = parallel_associative_scan(A_par, Bu_par)
        loss_par = h_par.sum()
        loss_par.backward()

        # Gradients should match (within tolerance)
        torch.testing.assert_close(A_par.grad, A_seq.grad, rtol=1e-3, atol=1e-3)
        torch.testing.assert_close(Bu_par.grad, Bu_seq.grad, rtol=1e-3, atol=1e-3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
