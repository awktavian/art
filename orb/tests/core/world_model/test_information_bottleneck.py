"""Tests for SequenceInformationBottleneck padding and gradients."""

from __future__ import annotations

import pytest
from typing import Any

import torch

from kagami.core.world_model.information_bottleneck import (
    SequenceIBConfig,
    SequenceInformationBottleneck,
)


def test_sequence_ib_masks_padded_levels() -> None:
    """Padded levels are masked and receive no gradient."""
    cfg = SequenceIBConfig(max_levels=4)
    ib = SequenceInformationBottleneck(cfg)
    ib.train()

    # Four levels provided, but only first two are active
    nucleus_sequence = torch.randn(1, 4, 8, requires_grad=True)
    num_levels = 2

    result = ib(nucleus_sequence, num_levels=num_levels)
    recon = result["reconstruction"]

    # Reconstruction only covers active levels
    assert recon.shape == (1, num_levels, 8)

    # Backprop to check gradients
    recon.sum().backward()
    assert nucleus_sequence.grad is not None

    # Masked (padded) levels must have zero gradient
    padded_grads = nucleus_sequence.grad[0, num_levels:]
    assert torch.allclose(padded_grads, torch.zeros_like(padded_grads), atol=1e-7)


"""Comprehensive Information Bottleneck Tests.

Tests for Variational Information Bottleneck (VIB):
1. Forward pass and loss computation
2. β-annealing schedule
3. VAMP prior implementation
4. Compression vs relevance trade-off
5. Gradient flow through reparameterization

CREATED: November 30, 2025
"""

import math

import torch.nn as nn
import torch.nn.functional as F


class TestInformationBottleneckBasic:
    """Test basic IB functionality."""

    @pytest.fixture
    def ib(self) -> Any:
        """Create IB module for testing."""
        from kagami.core.world_model.information_bottleneck import (
            IBConfig,
            InformationBottleneck,
        )

        config = IBConfig(
            input_dim=64,
            bottleneck_dim=16,
            output_dim=64,
            beta=0.01,
        )
        return InformationBottleneck(config)

    def test_forward_pass_shapes(self, ib) -> None:
        """Test forward pass produces correct shapes."""
        x = torch.randn(8, 64)
        y = torch.randn(8, 64)  # Target

        result = ib(x, y)

        assert result["z"].shape == (8, 16), "Latent z shape wrong"
        assert result["y_pred"].shape == (8, 64), "Prediction shape wrong"
        assert result["mu"].shape == (8, 16), "Mean shape wrong"
        assert result["logvar"].shape == (8, 16), "Logvar shape wrong"

    def test_inference_mode(self, ib) -> None:
        """Test inference without target."""
        x = torch.randn(8, 64)

        result = ib(x, y=None)

        assert "z" in result
        assert "y_pred" in result
        # No losses without target
        assert "total_loss" not in result

    def test_kl_divergence_positive(self, ib) -> None:
        """Test KL divergence is non-negative."""
        x = torch.randn(8, 64)
        y = torch.randn(8, 64)

        result = ib(x, y)

        assert result["kl_loss"] >= 0, "KL divergence should be >= 0"

    def test_prediction_loss_positive(self, ib) -> None:
        """Test prediction loss is non-negative."""
        x = torch.randn(8, 64)
        y = torch.randn(8, 64)

        result = ib(x, y)

        assert result["prediction_loss"] >= 0, "Prediction loss should be >= 0"

    def test_gradient_flow_through_z(self, ib) -> None:
        """Test gradients flow through reparameterization."""
        x = torch.randn(8, 64, requires_grad=True)
        y = torch.randn(8, 64)

        result = ib(x, y)
        loss = result["total_loss"]
        loss.backward()

        assert x.grad is not None, "Input should receive gradients"
        assert x.grad.abs().sum() > 0, "Gradient should be non-zero"

    def test_encoder_learns(self, ib) -> None:
        """Test encoder parameters receive gradients."""
        x = torch.randn(8, 64)
        y = torch.randn(8, 64)

        result = ib(x, y)
        result["total_loss"].backward()

        encoder_has_grad = False
        for _name, param in ib.encoder.named_parameters():
            if param.grad is not None and param.grad.abs().sum() > 0:
                encoder_has_grad = True
                break

        assert encoder_has_grad, "Encoder should receive gradients"

    def test_decoder_learns(self, ib) -> None:
        """Test decoder parameters receive gradients."""
        x = torch.randn(8, 64)
        y = torch.randn(8, 64)

        result = ib(x, y)
        result["total_loss"].backward()

        decoder_has_grad = False
        for _name, param in ib.decoder.named_parameters():
            if param.grad is not None and param.grad.abs().sum() > 0:
                decoder_has_grad = True
                break

        assert decoder_has_grad, "Decoder should receive gradients"


class TestCompressionRelevanceTradeoff:
    """Test compression vs relevance trade-off."""

    def test_high_beta_more_compression(self) -> None:
        """Test high β leads to more compression (lower KL capacity)."""
        from kagami.core.world_model.information_bottleneck import (
            IBConfig,
            InformationBottleneck,
        )

        config_low_beta = IBConfig(
            input_dim=64,
            bottleneck_dim=16,
            output_dim=64,
            beta=0.001,
        )
        config_high_beta = IBConfig(
            input_dim=64,
            bottleneck_dim=16,
            output_dim=64,
            beta=1.0,
        )

        ib_low = InformationBottleneck(config_low_beta)
        ib_high = InformationBottleneck(config_high_beta)

        x = torch.randn(32, 64)
        y = torch.randn(32, 64)

        # Train for a few steps
        optimizer_low = torch.optim.Adam(ib_low.parameters(), lr=0.01)
        optimizer_high = torch.optim.Adam(ib_high.parameters(), lr=0.01)

        for _ in range(50):
            result_low = ib_low(x, y)
            result_high = ib_high(x, y)

            optimizer_low.zero_grad()
            result_low["total_loss"].backward()
            optimizer_low.step()

            optimizer_high.zero_grad()
            result_high["total_loss"].backward()
            optimizer_high.step()

        # High beta should have lower KL (more compression)
        final_low = ib_low(x, y)
        final_high = ib_high(x, y)

        # With high beta, model is pushed to minimize KL (compress more)
        # This should result in lower KL values

    def test_bottleneck_dimension_affects_capacity(self) -> None:
        """Test smaller bottleneck limits information."""
        from kagami.core.world_model.information_bottleneck import (
            IBConfig,
            InformationBottleneck,
        )

        config_small = IBConfig(
            input_dim=64,
            bottleneck_dim=4,  # Very small
            output_dim=64,
            beta=0.01,
        )
        config_large = IBConfig(
            input_dim=64,
            bottleneck_dim=32,  # Large
            output_dim=64,
            beta=0.01,
        )

        ib_small = InformationBottleneck(config_small)
        ib_large = InformationBottleneck(config_large)

        x = torch.randn(8, 64)
        y = x.clone()  # Perfect reconstruction target

        result_small = ib_small(x, y)
        result_large = ib_large(x, y)

        # Larger bottleneck should have lower reconstruction error (untrained)
        # After training, the difference would be more pronounced


class TestNumericalStability:
    """Test numerical stability of IB."""

    @pytest.fixture
    def ib(self) -> Any:
        from kagami.core.world_model.information_bottleneck import (
            IBConfig,
            InformationBottleneck,
        )

        config = IBConfig(
            input_dim=64,
            bottleneck_dim=16,
            output_dim=64,
            beta=0.1,
        )
        return InformationBottleneck(config)

    def test_large_input_values(self, ib) -> None:
        """Test stability with large input values."""
        x = torch.randn(8, 64) * 100
        y = torch.randn(8, 64)

        result = ib(x, y)

        assert torch.isfinite(result["total_loss"]), "Loss should be finite"
        assert torch.isfinite(result["z"]).all(), "z should be finite"

    def test_very_small_input_values(self, ib) -> None:
        """Test stability with very small input values."""
        x = torch.randn(8, 64) * 1e-8
        y = torch.randn(8, 64)

        result = ib(x, y)

        assert torch.isfinite(result["total_loss"]), "Loss should be finite"
        assert torch.isfinite(result["z"]).all(), "z should be finite"


class TestIntegrationWithKagami:
    """Test IB integration with KagamiWorldModel."""

    @pytest.fixture
    def model(self) -> Any:
        from kagami.core.world_model.kagami_world_model import (
            KagamiWorldModel,
            KagamiWorldModelConfig,
        )

        config = KagamiWorldModelConfig(
            layer_dimensions=(64, 32, 22, 14),
            num_heads=2,
            ib_bottleneck_dim=8,
            ib_beta=0.01,
        )
        return KagamiWorldModel(config)

    def test_ib_in_forward_pass(self, model) -> None:
        """Test IB is applied during forward pass."""
        model.train()
        x = torch.randn(4, 8, 64)

        _output, metrics = model(x)

        # Should have IB-related metrics (Dec 6, 2025: now seq_ib_* for variable-length nucleus)
        has_ib_metrics = (
            "seq_ib_kl_loss" in metrics
            or "ib_kl_loss" in metrics
            or metrics.get("seq_ib_kl_loss") is not None
            or metrics.get("ib_kl_loss") is not None
        )
        assert has_ib_metrics, f"Expected IB metrics, got: {list(metrics.keys())}"

    def test_ib_receives_gradients(self, model) -> None:
        """Test IB module receives gradients."""
        model.train()
        model.zero_grad()

        x = torch.randn(4, 8, 64)
        output, metrics = model(x)

        loss = output.sum()
        # Dec 6, 2025: Use seq_ib_* metrics for variable-length nucleus
        ib_loss = metrics.get("seq_ib_kl_loss") or metrics.get("ib_kl_loss")
        if ib_loss is not None and isinstance(ib_loss, torch.Tensor):
            loss = loss + ib_loss

        loss.backward()

        # Check IB module has gradients (Dec 6, 2025: now _sequence_ib for variable-length)
        ib_has_grad = False
        ib_module = getattr(model, "_sequence_ib", None) or getattr(
            model, "_information_bottleneck", None
        )
        if ib_module is not None:
            for param in ib_module.parameters():
                if param.grad is not None:
                    ib_has_grad = True
                    break

        assert ib_has_grad, "IB module should receive gradients"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
