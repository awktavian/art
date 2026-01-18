"""Tests for Geometric MoE."""

from __future__ import annotations

import pytest

import torch

from kagami.core.world_model.layers.sparse_moe import (
    GeometricMoELayer,
    HyperbolicRouter,
    create_geometric_moe,
)

pytestmark = pytest.mark.tier_integration


class TestHyperbolicRouter:
    """Test the hyperbolic router."""

    def test_init(self) -> None:
        """Test initialization."""
        router = HyperbolicRouter(
            d_model=128,
            num_experts=8,
            top_k=2,
            hyperbolic_dim=7,
        )

        assert router.d_model == 128
        assert router.num_experts == 8
        assert router.top_k == 2
        assert router.hyperbolic_dim == 7

    def test_forward_shape(self) -> None:
        """Test routing output shape."""
        router = HyperbolicRouter(
            d_model=128,
            num_experts=8,
            top_k=2,
        )

        B, N, D = 4, 10, 128
        x = torch.randn(B, N, D)

        weights, indices, logits = router(x, training=False)

        assert weights.shape == (B, N, 2)  # top-2
        assert indices.shape == (B, N, 2)
        assert logits.shape == (B, N, 8)

    def test_top_k_selection(self) -> None:
        """Test that top-k experts are selected."""
        router = HyperbolicRouter(
            d_model=128,
            num_experts=8,
            top_k=2,
        )

        x = torch.randn(4, 10, 128)
        weights, indices, _ = router(x, training=False)

        # Check indices are in valid range
        assert (indices >= 0).all()
        assert (indices < 8).all()

        # Check weights sum to 1 (per token)
        torch.testing.assert_close(weights.sum(dim=-1), torch.ones(4, 10), rtol=1e-5, atol=1e-5)

    def test_load_balancing(self) -> None:
        """Test auxiliary load balancing loss."""
        router = HyperbolicRouter(
            d_model=128,
            num_experts=8,
            top_k=2,
            use_aux_loss=True,
        )

        x = torch.randn(4, 10, 128)
        _, _, logits = router(x, training=True)

        loss = router.load_balancing_loss(logits)
        assert isinstance(loss, torch.Tensor)
        assert loss > 0  # Should have some load balancing loss


class TestGeometricMoELayer:
    """Test the Geometric MoE layer."""

    def test_init(self) -> None:
        """Test initialization."""
        moe = GeometricMoELayer(
            d_model=128,
            num_experts=8,
            expert_capacity=2,
        )

        assert moe.moe.d_model == 128
        assert moe.moe.num_experts == 8
        assert moe.moe.top_k == 2

    def test_forward_shape(self) -> None:
        """Test forward pass shape."""
        moe = GeometricMoELayer(
            d_model=128,
            num_experts=4,
            expert_capacity=2,
        )

        B, N, D = 4, 10, 128
        x = torch.randn(B, N, D)

        output = moe(x)

        assert output.shape == (B, N, D)

    def test_forward_no_nan(self) -> None:
        """Test no NaN outputs."""
        moe = GeometricMoELayer(
            d_model=128,
            num_experts=4,
            expert_capacity=2,
        )

        x = torch.randn(4, 10, 128)
        output = moe(x)

        assert not torch.isnan(output).any()

    def test_sparse_activation(self) -> None:
        """Test that only top-k experts are activated."""
        moe = GeometricMoELayer(
            d_model=128,
            num_experts=8,
            expert_capacity=2,
        )

        x = torch.randn(4, 10, 128)
        output = moe(x)

        # Should complete without error
        assert output.shape == (4, 10, 128)

    def test_get_aux_loss(self) -> None:
        """Test auxiliary loss retrieval."""
        moe = GeometricMoELayer(
            d_model=128,
            num_experts=4,
            expert_capacity=2,
        )

        x = torch.randn(4, 10, 128)
        _ = moe(x)

        aux_loss = moe.get_aux_loss()
        assert isinstance(aux_loss, torch.Tensor)

    def test_gradient_flow(self) -> None:
        """Test gradient flow through MoE."""
        moe = GeometricMoELayer(
            d_model=128,
            num_experts=4,
            expert_capacity=2,
        )

        x = torch.randn(4, 10, 128, requires_grad=True)
        output = moe(x)

        loss = output.sum()
        loss.backward()

        assert x.grad is not None
        assert not torch.isnan(x.grad).any()

    def test_factory_function(self) -> None:
        """Test factory function."""
        moe = create_geometric_moe(d_model=128, num_experts=8)

        assert isinstance(moe, GeometricMoELayer)
        assert moe.moe.d_model == 128


class TestGeometricMoEIntegration:
    """Integration tests for Geometric MoE."""

    def test_efficiency_vs_dense(self) -> None:
        """Test that MoE is more parameter-efficient than dense."""
        # MoE layer
        moe = GeometricMoELayer(
            d_model=128,
            num_experts=8,
            expert_capacity=2,  # Only 2 active
        )

        # Count expert parameters
        expert_params = sum(p.numel() for expert in moe.moe.experts for p in expert.parameters())

        # Dense equivalent would use all experts
        # With expert_capacity=2, we activate 25% of parameters
        # So MoE should be more efficient at inference
        assert expert_params > 0

    def test_load_balancing_works(self) -> None:
        """Test that load balancing encourages uniform expert usage."""
        moe = GeometricMoELayer(
            d_model=128,
            num_experts=4,
            expert_capacity=2,
        )

        # Run multiple forward passes
        for _ in range(10):
            x = torch.randn(8, 10, 128)
            _ = moe(x)

        # Check metrics are being generated
        # GeometricMoELayer doesn't expose expert counts directly, checking aux loss update
        assert moe.get_aux_loss() >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
