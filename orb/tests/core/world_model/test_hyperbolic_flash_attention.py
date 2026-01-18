"""Tests for Hyperbolic Flash Attention."""

from __future__ import annotations

import pytest

import torch

from kagami.core.world_model.layers.hyperbolic_flash_attention import (
    HyperbolicFlashAttention,
    create_hyperbolic_flash_attention,
)

pytestmark = pytest.mark.tier_integration


class TestHyperbolicFlashAttention:
    """Test Hyperbolic Flash Attention."""

    def test_init(self) -> None:
        """Test initialization."""
        attn = HyperbolicFlashAttention(dim=64, num_heads=4)

        assert attn.dim == 64
        assert attn.num_heads == 4
        assert attn.head_dim == 16

    def test_forward_shape(self) -> None:
        """Test output shape."""
        attn = HyperbolicFlashAttention(dim=64, num_heads=4)

        B, N, D = 4, 10, 64
        x = torch.randn(B, N, D)

        # Map to manifold first (exp0)
        from kagami.core.world_model.manifolds.poincare import PoincareManifold

        manifold = PoincareManifold(dim=64)
        x_manifold = manifold.exp0(x)

        output = attn(x_manifold)

        assert output.shape == (B, N, D)

    def test_forward_no_nan(self) -> None:
        """Test no NaN outputs."""
        attn = HyperbolicFlashAttention(dim=64, num_heads=4)
        x = torch.randn(4, 10, 64) * 0.5  # Smaller values to stay in ball

        from kagami.core.world_model.manifolds.poincare import PoincareManifold

        manifold = PoincareManifold(dim=64)
        x_manifold = manifold.exp0(x)

        output = attn(x_manifold)

        assert not torch.isnan(output).any()

    def test_attention_with_mask(self) -> None:
        """Test attention with masking."""
        attn = HyperbolicFlashAttention(dim=64, num_heads=4)

        B, N, D = 2, 10, 64
        x = torch.randn(B, N, D) * 0.5

        from kagami.core.world_model.manifolds.poincare import PoincareManifold

        manifold = PoincareManifold(dim=64)
        x_manifold = manifold.exp0(x)

        # Causal mask
        mask = torch.tril(torch.ones(B, N, N))

        output = attn(x_manifold, mask=mask)

        assert output.shape == (B, N, D)
        assert not torch.isnan(output).any()

    def test_return_attention_weights(self) -> None:
        """Test returning attention weights."""
        attn = HyperbolicFlashAttention(dim=64, num_heads=4, use_hyperbolic_distance=False)

        B, N, D = 2, 10, 64
        x = torch.randn(B, N, D) * 0.5

        from kagami.core.world_model.manifolds.poincare import PoincareManifold

        manifold = PoincareManifold(dim=64)
        x_manifold = manifold.exp0(x)

        output, weights = attn(x_manifold, return_attention=True)

        assert output.shape == (B, N, D)
        if weights is not None:
            assert weights.shape == (B, attn.num_heads, N, N)

    def test_hyperbolic_distance_scoring(self) -> None:
        """Test hyperbolic distance-based scoring."""
        attn = HyperbolicFlashAttention(dim=64, num_heads=4, use_hyperbolic_distance=True)

        x = torch.randn(2, 10, 64) * 0.5

        from kagami.core.world_model.manifolds.poincare import PoincareManifold

        manifold = PoincareManifold(dim=64)
        x_manifold = manifold.exp0(x)

        output = attn(x_manifold)

        assert output.shape == (2, 10, 64)
        assert not torch.isnan(output).any()

    def test_gradient_flow(self) -> None:
        """Test gradient flow through attention."""
        attn = HyperbolicFlashAttention(dim=64, num_heads=4)

        x = torch.randn(2, 10, 64, requires_grad=True) * 0.5

        from kagami.core.world_model.manifolds.poincare import PoincareManifold

        manifold = PoincareManifold(dim=64)

        x_manifold = manifold.exp0(x)
        x_manifold.retain_grad()  # Retain grad for non-leaf tensor

        output = attn(x_manifold)
        loss = output.sum()
        loss.backward()

        # Check gradients exist in the parameters
        has_grads = False
        for param in attn.parameters():
            if param.requires_grad and param.grad is not None:
                has_grads = True
                assert not torch.isnan(param.grad).any()
                break
        assert has_grads

    def test_factory_function(self) -> None:
        """Test factory function."""
        attn = create_hyperbolic_flash_attention(dim=64, num_heads=4)

        assert isinstance(attn, HyperbolicFlashAttention)
        assert attn.dim == 64


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
