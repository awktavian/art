"""Tests for KagamiWorldModel (formerly OptimizedWorldModel).

UPDATED: Nov 30, 2025 - HARDENED: All features always enabled, no presets.
"""

from __future__ import annotations

import pytest

import torch

from kagami.core.world_model.kagami_world_model import KagamiWorldModelFactory



pytestmark = pytest.mark.tier_integration

def test_kagami_world_model_forward() -> None:
    """Verify that KagamiWorldModel forward pass works."""
    model = KagamiWorldModelFactory.create()  # HARDENED: no preset needed

    batch_size = 2
    seq_len = 10
    d_model = model.config.layer_dimensions[0]

    x = torch.randn(batch_size, seq_len, d_model)

    # Run forward pass
    outputs, metrics = model(x)

    # Check output shape matches input (hourglass architecture)
    assert outputs.shape == x.shape
    assert isinstance(metrics, dict)


def test_kagami_world_model_metrics() -> None:
    """Verify that KagamiWorldModel outputs expected metrics.

    Dec 13, 2025: Updated to check actual metrics from forward pass.
    e8_commitment_loss is computed by loss_module during training_step, not forward.
    """
    model = KagamiWorldModelFactory.create()  # HARDENED: no preset needed

    batch_size = 2
    seq_len = 10
    d_model = model.config.layer_dimensions[0]

    x = torch.randn(batch_size, seq_len, d_model)
    _outputs, metrics = model(x)

    # Forward pass metrics (Dec 13, 2025 update)
    # encoder_states contains intermediate representations
    assert "encoder_states" in metrics
    # bits_used tracks E8 quantization levels
    assert "bits_used" in metrics or "num_levels" in metrics
    # fano_coherence is computed from S7 phase
    assert "fano_coherence" in metrics or "loop_closure_loss" in metrics


def test_mu_self_is_on_model_device() -> None:
    """Ensure mu_self tensor stays on-device (no CPU leakage).

    Dec 13, 2025: Updated - get_state_for_configurator removed.
    Use mu_self property instead for strange loop fixed point.
    """
    model = KagamiWorldModelFactory.create()

    device = torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu")
    model = model.to(device)

    # Run a forward pass to initialize mu_self
    d_model = model.config.layer_dimensions[0]
    x = torch.randn(1, 5, d_model, device=device)
    _, _ = model(x)

    # Check mu_self is on correct device
    mu_self = model.mu_self
    assert isinstance(mu_self, torch.Tensor)
    assert mu_self.shape == (7,)  # S7 dimension
    assert mu_self.device.type == device.type


if __name__ == "__main__":
    test_kagami_world_model_forward()
    test_kagami_world_model_metrics()
    print("✅ KagamiWorldModel tests passed")
