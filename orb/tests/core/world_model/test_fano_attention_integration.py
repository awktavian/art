"""Tests for Fano Attention Integration in KagamiWorldModel.

Tests the integration of Fano attention for cross-colony communication
in the world model forward pass.

Author: Forge (e₂) — The Builder
Date: December 20, 2025
"""

from __future__ import annotations

import pytest

import torch

from kagami.core.world_model.kagami_world_model import KagamiWorldModel
from kagami.core.world_model.model_config import KagamiWorldModelConfig


pytestmark = pytest.mark.tier_integration


class TestFanoAttentionIntegration:
    """Test suite for Fano attention integration in world model."""

    @pytest.fixture
    def config_without_fano(self) -> KagamiWorldModelConfig:
        """Create config with Fano attention disabled."""
        return KagamiWorldModelConfig(
            bulk_dim=64,
            device="cpu",
            use_fano_attention=False,  # Disabled
        )

    @pytest.fixture
    def config_with_fano(self) -> KagamiWorldModelConfig:
        """Create config with Fano attention enabled."""
        return KagamiWorldModelConfig(
            bulk_dim=64,
            device="cpu",
            use_fano_attention=True,  # Enabled
            fano_attention_num_heads=1,
            fano_attention_dropout=0.1,
        )

    @pytest.fixture
    def model_without_fano(self, config_without_fano: KagamiWorldModelConfig) -> KagamiWorldModel:
        """Create model without Fano attention."""
        model = KagamiWorldModel(config_without_fano)
        model.eval()
        return model

    @pytest.fixture
    def model_with_fano(self, config_with_fano: KagamiWorldModelConfig) -> KagamiWorldModel:
        """Create model with Fano attention."""
        model = KagamiWorldModel(config_with_fano)
        model.eval()
        return model

    @pytest.fixture
    def batch_input(self) -> torch.Tensor:
        """Create batch input tensor."""
        batch_size = 2
        seq_len = 4
        bulk_dim = 64
        return torch.randn(batch_size, seq_len, bulk_dim)

    def test_fano_attention_initialization_disabled(
        self, model_without_fano: KagamiWorldModel
    ) -> None:
        """Test that Fano attention is None when disabled."""
        assert model_without_fano.fano_attention is None
        assert not model_without_fano.config.use_fano_attention

    def test_fano_attention_initialization_enabled(self, model_with_fano: KagamiWorldModel) -> None:
        """Test that Fano attention is created when enabled."""
        assert model_with_fano.fano_attention is not None
        assert model_with_fano.config.use_fano_attention
        assert hasattr(model_with_fano.fano_attention, "num_colonies")
        assert model_with_fano.fano_attention.num_colonies == 7

    def test_forward_without_fano(
        self, model_without_fano: KagamiWorldModel, batch_input: torch.Tensor
    ) -> None:
        """Test forward pass without Fano attention."""
        output, metrics = model_without_fano(batch_input)

        # Basic shape check
        assert output.shape == batch_input.shape

        # Should not have fano_attention_applied metric
        assert "fano_attention_applied" not in metrics

        # Should have basic metrics
        assert "core_state" in metrics
        assert metrics["core_state"] is not None

    def test_forward_with_fano(
        self, model_with_fano: KagamiWorldModel, batch_input: torch.Tensor
    ) -> None:
        """Test forward pass with Fano attention."""
        output, metrics = model_with_fano(batch_input)

        # Basic shape check
        assert output.shape == batch_input.shape

        # Should have fano_attention_applied metric
        assert "fano_attention_applied" in metrics
        assert metrics["fano_attention_applied"] is True

        # Should have core_state with S7 phase
        assert "core_state" in metrics
        core_state = metrics["core_state"]
        assert core_state is not None
        assert core_state.s7_phase is not None

    def test_s7_phase_transformation(
        self, model_with_fano: KagamiWorldModel, batch_input: torch.Tensor
    ) -> None:
        """Test that Fano attention transforms S7 phase meaningfully."""
        # Forward pass
        _output, metrics = model_with_fano(batch_input)

        core_state = metrics["core_state"]
        assert core_state.s7_phase is not None

        # S7 phase should have correct shape
        B, S = batch_input.shape[:2]
        assert core_state.s7_phase.shape == (B, S, 7)

        # S7 phase should be finite
        assert torch.isfinite(core_state.s7_phase).all()

        # S7 phase should have non-zero values (attended)
        assert core_state.s7_phase.abs().max() > 1e-8

    def test_gradient_flow_through_fano_attention(
        self, model_with_fano: KagamiWorldModel, batch_input: torch.Tensor
    ) -> None:
        """Test gradients flow through Fano attention."""
        model_with_fano.train()

        # Create target
        target = torch.randn_like(batch_input)

        # Zero gradients
        model_with_fano.zero_grad()

        # Forward pass
        output, metrics = model_with_fano(batch_input)

        # Compute loss that depends on S7 phase
        core_state = metrics["core_state"]
        assert core_state.s7_phase is not None

        recon_loss = torch.nn.functional.mse_loss(output, target)
        s7_loss = core_state.s7_phase.pow(2).mean()
        total_loss = recon_loss + 0.1 * s7_loss

        # Backward pass
        total_loss.backward()

        # Check Fano attention parameters have gradients
        fano_params_with_grad = 0
        for name, param in model_with_fano.fano_attention.named_parameters():
            if param.requires_grad:
                assert param.grad is not None, f"No gradient for {name}"
                assert torch.isfinite(param.grad).all(), f"Non-finite gradient for {name}"
                if param.grad.abs().max() > 1e-8:
                    fano_params_with_grad += 1

        # At least some Fano attention parameters should have non-zero gradients
        assert fano_params_with_grad > 0, "No Fano attention parameters received gradients"

    def test_gradient_flow_end_to_end(
        self, model_with_fano: KagamiWorldModel, batch_input: torch.Tensor
    ) -> None:
        """Test end-to-end gradient flow through Fano attention."""
        model_with_fano.train()
        batch_input_with_grad = batch_input.clone().requires_grad_(True)

        # Forward pass
        output, _metrics = model_with_fano(batch_input_with_grad)

        # Compute loss on output
        loss = output.pow(2).mean()

        # Backward pass
        loss.backward()

        # Check input gradient exists (verifies full backprop)
        assert batch_input_with_grad.grad is not None
        assert torch.isfinite(batch_input_with_grad.grad).all()
        assert batch_input_with_grad.grad.abs().max() > 1e-8

    def test_fano_attention_affects_s7_phase(
        self, model_with_fano: KagamiWorldModel, batch_input: torch.Tensor
    ) -> None:
        """Test that Fano attention actually modifies S7 phase.

        This test verifies that enabling Fano attention produces different
        S7 phase values compared to disabling it (by temporarily disabling).
        """
        # Forward with Fano enabled
        _output_with, metrics_with = model_with_fano(batch_input)
        s7_with = metrics_with["core_state"].s7_phase

        # Temporarily disable Fano attention
        fano_backup = model_with_fano.fano_attention
        model_with_fano.fano_attention = None

        # Forward with Fano disabled
        _output_without, metrics_without = model_with_fano(batch_input)
        s7_without = metrics_without["core_state"].s7_phase

        # Restore Fano attention
        model_with_fano.fano_attention = fano_backup

        # S7 phases should differ (Fano attention modified them)
        assert not torch.allclose(s7_with, s7_without, atol=1e-6), (
            "Fano attention did not modify S7 phase"
        )

    def test_fano_attention_preserves_s7_dimension(
        self, model_with_fano: KagamiWorldModel, batch_input: torch.Tensor
    ) -> None:
        """Test that Fano attention preserves S7 dimension."""
        # Multiple forward passes with different inputs
        for _ in range(3):
            x = torch.randn_like(batch_input)
            _output, metrics = model_with_fano(x)

            core_state = metrics["core_state"]
            assert core_state.s7_phase is not None
            assert core_state.s7_phase.shape[-1] == 7, "S7 dimension not preserved"

    def test_fano_attention_with_variable_batch_size(
        self, model_with_fano: KagamiWorldModel
    ) -> None:
        """Test Fano attention with different batch sizes."""
        bulk_dim = model_with_fano.config.bulk_dim

        for batch_size in [1, 2, 4, 8]:
            x = torch.randn(batch_size, 4, bulk_dim)
            output, metrics = model_with_fano(x)

            assert output.shape == x.shape
            assert "fano_attention_applied" in metrics
            assert metrics["core_state"].s7_phase.shape == (batch_size, 4, 7)

    def test_fano_attention_with_variable_seq_len(self, model_with_fano: KagamiWorldModel) -> None:
        """Test Fano attention with different sequence lengths."""
        bulk_dim = model_with_fano.config.bulk_dim

        for seq_len in [1, 2, 4, 8, 16]:
            x = torch.randn(2, seq_len, bulk_dim)
            output, metrics = model_with_fano(x)

            assert output.shape == x.shape
            assert "fano_attention_applied" in metrics
            assert metrics["core_state"].s7_phase.shape == (2, seq_len, 7)

    def test_fano_attention_numerical_stability(self, model_with_fano: KagamiWorldModel) -> None:
        """Test numerical stability with extreme inputs."""
        bulk_dim = model_with_fano.config.bulk_dim

        # Test with very small values
        x_small = torch.randn(2, 4, bulk_dim) * 1e-6
        output_small, metrics_small = model_with_fano(x_small)
        assert torch.isfinite(output_small).all()
        assert torch.isfinite(metrics_small["core_state"].s7_phase).all()

        # Test with very large values
        x_large = torch.randn(2, 4, bulk_dim) * 1e3
        output_large, metrics_large = model_with_fano(x_large)
        assert torch.isfinite(output_large).all()
        assert torch.isfinite(metrics_large["core_state"].s7_phase).all()

    def test_backward_compatibility_config_default(self) -> None:
        """Test that use_fano_attention defaults to False (backward compatible)."""
        config = KagamiWorldModelConfig(bulk_dim=64)
        assert config.use_fano_attention is False, (
            "Default should be False for backward compatibility"
        )

    def test_parameter_count_increase_with_fano(
        self, model_without_fano: KagamiWorldModel, model_with_fano: KagamiWorldModel
    ) -> None:
        """Test that enabling Fano attention increases parameter count."""
        params_without = sum(p.numel() for p in model_without_fano.parameters())
        params_with = sum(p.numel() for p in model_with_fano.parameters())

        assert params_with > params_without, "Fano attention should add parameters"

        # Fano attention parameters should be a small fraction of total
        fano_params = sum(p.numel() for p in model_with_fano.fano_attention.parameters())
        fano_ratio = fano_params / params_with
        assert fano_ratio < 0.1, (
            f"Fano attention adds too many parameters: {fano_ratio:.1%} of total"
        )

    def test_training_step_with_fano(
        self, model_with_fano: KagamiWorldModel, batch_input: torch.Tensor
    ) -> None:
        """Test training_step method with Fano attention enabled."""
        model_with_fano.train()

        target = torch.randn_like(batch_input)

        # Training step
        loss_output = model_with_fano.training_step(batch_input, target)

        # Check loss output structure
        assert hasattr(loss_output, "total")
        assert hasattr(loss_output, "components")
        assert torch.isfinite(loss_output.total)

        # Check loss is a scalar
        assert loss_output.total.ndim == 0

        # Loss should be positive (MSE-based losses)
        assert loss_output.total.item() >= 0


class TestFanoAttentionMultiHead:
    """Test multi-head Fano attention."""

    @pytest.fixture
    def config_multi_head(self) -> KagamiWorldModelConfig:
        """Create config with multi-head Fano attention."""
        return KagamiWorldModelConfig(
            bulk_dim=64,
            device="cpu",
            use_fano_attention=True,
            fano_attention_num_heads=2,  # Multi-head
            fano_attention_dropout=0.0,  # No dropout for deterministic testing
        )

    @pytest.fixture
    def model_multi_head(self, config_multi_head: KagamiWorldModelConfig) -> KagamiWorldModel:
        """Create model with multi-head Fano attention."""
        model = KagamiWorldModel(config_multi_head)
        model.eval()
        return model

    def test_multi_head_initialization(self, model_multi_head: KagamiWorldModel) -> None:
        """Test multi-head Fano attention initialization."""
        assert model_multi_head.fano_attention is not None
        assert model_multi_head.fano_attention.num_heads == 2

    def test_multi_head_forward(self, model_multi_head: KagamiWorldModel) -> None:
        """Test forward pass with multi-head Fano attention."""
        batch_size = 2
        seq_len = 4
        bulk_dim = model_multi_head.config.bulk_dim

        x = torch.randn(batch_size, seq_len, bulk_dim)
        output, metrics = model_multi_head(x)

        assert output.shape == x.shape
        assert "fano_attention_applied" in metrics
        assert metrics["core_state"].s7_phase.shape == (batch_size, seq_len, 7)

    def test_multi_head_gradient_flow(self, model_multi_head: KagamiWorldModel) -> None:
        """Test gradient flow with multi-head Fano attention."""
        model_multi_head.train()

        batch_size = 2
        seq_len = 4
        bulk_dim = model_multi_head.config.bulk_dim

        x = torch.randn(batch_size, seq_len, bulk_dim)
        target = torch.randn_like(x)

        # Zero gradients
        model_multi_head.zero_grad()

        # Forward + backward
        output, metrics = model_multi_head(x)

        # Loss that depends on S7 phase (to ensure gate gradients)
        core_state = metrics["core_state"]
        recon_loss = torch.nn.functional.mse_loss(output, target)
        s7_loss = core_state.s7_phase.pow(2).mean()
        loss = recon_loss + 0.1 * s7_loss

        loss.backward()

        # Check gradients in gate projection (now a single batched Linear)
        gate_proj = model_multi_head.fano_attention.gate_proj
        assert gate_proj.weight.grad is not None, "No gradient for gate projection"
        assert torch.isfinite(gate_proj.weight.grad).all(), (
            "Non-finite gradient for gate projection"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
