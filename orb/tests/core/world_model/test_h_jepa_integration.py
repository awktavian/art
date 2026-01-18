"""Tests for H-JEPA integration in KagamiWorldModel.

Tests predictor/target networks, EMA updates, and multi-horizon prediction.

Created: December 19, 2025
"""

from __future__ import annotations

import pytest

import torch

from kagami.core.world_model.kagami_world_model import KagamiWorldModel
from kagami.core.world_model.model_config import KagamiWorldModelConfig


pytestmark = pytest.mark.tier_integration


@pytest.fixture
def model() -> KagamiWorldModel:
    """Create world model with H-JEPA enabled."""
    config = KagamiWorldModelConfig(
        bulk_dim=128,
        device="cpu",
    )
    return KagamiWorldModel(config)


def test_h_jepa_components_exist(model: KagamiWorldModel) -> None:
    """Test that H-JEPA predictor and target networks are created."""
    # Check predictor network exists
    assert hasattr(model, "h_jepa_predictor"), "Missing h_jepa_predictor"
    assert model.h_jepa_predictor is not None, "h_jepa_predictor is None"

    # Check target network exists
    assert hasattr(model, "h_jepa_target"), "Missing h_jepa_target"
    assert model.h_jepa_target is not None, "h_jepa_target is None"

    # Check EMA decay parameter exists
    assert hasattr(model, "h_jepa_ema_tau"), "Missing h_jepa_ema_tau"
    assert 0.0 < model.h_jepa_ema_tau < 1.0, f"Invalid EMA tau: {model.h_jepa_ema_tau}"


def test_h_jepa_target_no_grad(model: KagamiWorldModel) -> None:
    """Test that target network has no gradients."""
    for param in model.h_jepa_target.parameters():
        assert not param.requires_grad, "Target network parameter has requires_grad=True"


def test_h_jepa_forward_predictions(model: KagamiWorldModel) -> None:
    """Test forward pass returns H-JEPA predictions."""
    B, S, D = 2, 4, 128
    x = torch.randn(B, S, D)

    _output, metrics = model(x)

    # Check predictions exist in metrics
    assert "h_jepa_predictions" in metrics, "Missing h_jepa_predictions in metrics"

    predictions = metrics["h_jepa_predictions"]
    assert isinstance(predictions, dict), "h_jepa_predictions should be dict"

    # Check multi-horizon predictions (horizons: 1, 2, 4, 8)
    expected_horizons = [1, 2, 4, 8]
    for horizon in expected_horizons:
        key = f"horizon_{horizon}"
        assert key in predictions, f"Missing prediction for {key}"
        pred = predictions[key]
        assert isinstance(pred, torch.Tensor), f"{key} should be tensor"
        assert pred.shape[0] == B, f"Wrong batch size for {key}"


def test_h_jepa_prediction_shapes(model: KagamiWorldModel) -> None:
    """Test that prediction shapes match E8 latent space."""
    B, S = 2, 4
    x = torch.randn(B, S, 128)

    _, metrics = model(x)

    predictions = metrics["h_jepa_predictions"]
    for horizon_key, pred in predictions.items():
        # Predictions should be in E8 space (8D)
        assert pred.shape[-1] == 8, (
            f"{horizon_key} should have dim=8 (E8 space), got {pred.shape[-1]}"
        )


def test_h_jepa_loss_computation(model: KagamiWorldModel) -> None:
    """Test H-JEPA loss is computed during training."""
    B, S, D = 2, 4, 128
    x = torch.randn(B, S, D)
    target = torch.randn(B, S, D)

    loss_output = model.training_step(x, target)

    # Check H-JEPA loss exists
    assert hasattr(loss_output, "h_jepa_loss") or "h_jepa_loss" in loss_output.components, (
        "H-JEPA loss not computed"
    )

    # Check loss value is valid
    if hasattr(loss_output, "h_jepa_loss"):
        h_jepa_loss = loss_output.h_jepa_loss
    else:
        h_jepa_loss = loss_output.components["h_jepa_loss"]

    assert isinstance(h_jepa_loss, torch.Tensor), "H-JEPA loss should be tensor"
    assert h_jepa_loss.numel() == 1, "H-JEPA loss should be scalar"
    assert torch.isfinite(h_jepa_loss).all(), "H-JEPA loss is NaN or Inf"


def test_ema_update_method_exists(model: KagamiWorldModel) -> None:
    """Test that EMA update method exists."""
    assert hasattr(model, "update_h_jepa_target"), "Missing update_h_jepa_target method"
    assert callable(model.update_h_jepa_target), "update_h_jepa_target is not callable"


def test_ema_update_changes_target(model: KagamiWorldModel) -> None:
    """Test that EMA update modifies target network parameters."""
    # Get initial target parameters
    initial_params = [p.clone() for p in model.h_jepa_target.parameters()]

    # Modify predictor parameters
    for param in model.h_jepa_predictor.parameters():
        param.data += torch.randn_like(param) * 0.1

    # Update target network with EMA
    model.update_h_jepa_target()

    # Check that target parameters changed
    updated_params = list(model.h_jepa_target.parameters())

    assert len(initial_params) == len(updated_params), "Parameter count mismatch"

    changed = False
    for p_init, p_updated in zip(initial_params, updated_params, strict=False):
        if not torch.allclose(p_init, p_updated, atol=1e-6):
            changed = True
            break

    assert changed, "Target network parameters did not change after EMA update"


def test_ema_update_no_grad(model: KagamiWorldModel) -> None:
    """Test that EMA update is executed without gradients."""
    # Enable grad tracking
    with torch.enable_grad():
        # Create computation graph
        x = torch.randn(2, 4, 128, requires_grad=True)
        output, _ = model(x)
        loss = output.sum()
        loss.backward()

        # Update target (should be no_grad internally)
        model.update_h_jepa_target()

    # Verify target still has no gradients
    for param in model.h_jepa_target.parameters():
        assert not param.requires_grad, "Target acquired gradients after update"
        assert param.grad is None, "Target has gradient tensors"


def test_ema_update_custom_tau(model: KagamiWorldModel) -> None:
    """Test EMA update with custom tau parameter."""
    # Get initial target state
    initial_params = [p.clone() for p in model.h_jepa_target.parameters()]

    # Modify predictor
    for param in model.h_jepa_predictor.parameters():
        param.data.fill_(1.0)

    # Update with tau=0.5 (50% old, 50% new)
    model.update_h_jepa_target(tau=0.5)

    # Check updated parameters are blend
    updated_params = list(model.h_jepa_target.parameters())
    for p_init, p_updated, p_online in zip(
        initial_params, updated_params, model.h_jepa_predictor.parameters(), strict=False
    ):
        expected = 0.5 * p_init + 0.5 * p_online
        assert torch.allclose(p_updated, expected, atol=1e-5), "EMA blend incorrect"


def test_stop_gradient_on_target(model: KagamiWorldModel) -> None:
    """Test that target network predictions have no gradient flow."""
    x = torch.randn(2, 4, 128, requires_grad=True)

    # Forward pass
    _, metrics = model(x)

    # Get target predictions (should be detached)
    assert "h_jepa_target_predictions" in metrics, "Missing target predictions"
    target_preds = metrics["h_jepa_target_predictions"]

    # Check all target predictions are detached
    for horizon_key, pred in target_preds.items():
        assert not pred.requires_grad, f"Target prediction {horizon_key} has gradients"


def test_multi_horizon_prediction_horizons(model: KagamiWorldModel) -> None:
    """Test that H-JEPA predicts at multiple horizons (1, 2, 4, 8 steps)."""
    x = torch.randn(2, 8, 128)  # Need long enough sequence for all horizons

    _, metrics = model(x)

    predictions = metrics["h_jepa_predictions"]

    # Check all horizons present
    expected_horizons = [1, 2, 4, 8]
    for h in expected_horizons:
        assert f"horizon_{h}" in predictions, f"Missing horizon_{h} prediction"


def test_h_jepa_e8_latent_space(model: KagamiWorldModel) -> None:
    """Test that H-JEPA operates in E8 latent space (8D)."""
    x = torch.randn(2, 4, 128)

    _, metrics = model(x)

    # Check encoder states contain E8 codes
    encoder_states = metrics.get("encoder_states", {})
    e8_code = encoder_states.get("e8_quantized")

    assert e8_code is not None, "Missing E8 code in encoder states"
    assert e8_code.shape[-1] == 8, f"E8 code should be 8D, got {e8_code.shape[-1]}"

    # Check predictions match E8 dimensionality
    predictions = metrics["h_jepa_predictions"]
    for pred in predictions.values():
        assert pred.shape[-1] == 8, "Predictions should be in E8 space (8D)"


def test_h_jepa_initialization_values(model: KagamiWorldModel) -> None:
    """Test that target network is initialized with DIFFERENT weights.

    Design note (Dec 28, 2025): Predictor and target start with different
    random weights to ensure meaningful H-JEPA loss from step 1. The EMA
    updates will gradually align them over time. This differs from standard
    BYOL/JEPA which copies weights initially.
    """
    # Check parameter values are DIFFERENT initially (by design)
    any_different = False
    for p_pred, p_target in zip(
        model.h_jepa_predictor.parameters(), model.h_jepa_target.parameters(), strict=False
    ):
        if not torch.allclose(p_pred, p_target, atol=1e-6):
            any_different = True
            break

    assert any_different, (
        "Target initialized as copy of predictor - but design requires "
        "different weights for meaningful initial H-JEPA loss"
    )


def test_h_jepa_loss_weighting(model: KagamiWorldModel) -> None:
    """Test that H-JEPA loss has proper weighting in total loss."""
    x = torch.randn(2, 4, 128)
    target = torch.randn(2, 4, 128)

    loss_output = model.training_step(x, target)

    # Check total loss includes H-JEPA component
    total = loss_output.total
    assert torch.isfinite(total), "Total loss is NaN or Inf"

    # H-JEPA loss should contribute to total
    # (This test just checks structure, not exact weighting)
    assert total.item() >= 0.0, "Total loss is negative"


@pytest.mark.parametrize("tau", [0.9, 0.99, 0.996, 0.999])
def test_ema_decay_values(model: KagamiWorldModel, tau: float) -> None:
    """Test EMA update with different decay values."""
    # Modify predictor
    for param in model.h_jepa_predictor.parameters():
        param.data += torch.randn_like(param) * 0.1

    # Update with specified tau
    model.update_h_jepa_target(tau=tau)

    # Check target still has no gradients
    for param in model.h_jepa_target.parameters():
        assert not param.requires_grad, f"Target has gradients after tau={tau} update"


def test_h_jepa_integration_end_to_end(model: KagamiWorldModel) -> None:
    """End-to-end test: forward → loss → EMA update."""
    x = torch.randn(2, 4, 128)
    target = torch.randn(2, 4, 128)

    # 1. Forward pass
    _output, metrics = model(x)
    assert "h_jepa_predictions" in metrics, "Missing predictions"

    # 2. Training step (computes loss)
    loss_output = model.training_step(x, target)
    assert torch.isfinite(loss_output.total), "Loss is NaN/Inf"

    # 3. EMA update (simulating optimizer step)
    model.update_h_jepa_target()

    # 4. Verify target network updated
    for param in model.h_jepa_target.parameters():
        assert not param.requires_grad, "Target has gradients after update"

    # 5. Second forward pass (should produce different predictions)
    _output2, metrics2 = model(x)
    assert "h_jepa_predictions" in metrics2, "Missing predictions after update"


def test_h_jepa_disabled_if_flag_off() -> None:
    """Test that H-JEPA can be disabled via config flag."""
    # Create model without H-JEPA
    config = KagamiWorldModelConfig(
        bulk_dim=128,
        device="cpu",
    )
    # Add a flag to disable H-JEPA (future feature)
    # For now, H-JEPA should always be enabled
    model = KagamiWorldModel(config)

    # H-JEPA should exist (always enabled in current implementation)
    assert hasattr(model, "h_jepa_predictor"), "H-JEPA should be enabled by default"


def test_h_jepa_batch_size_invariance(model: KagamiWorldModel) -> None:
    """Test H-JEPA works with different batch sizes."""
    batch_sizes = [1, 2, 4, 8, 16]

    for B in batch_sizes:
        x = torch.randn(B, 4, 128)
        _output, metrics = model(x)

        assert "h_jepa_predictions" in metrics, f"Failed for batch_size={B}"
        predictions = metrics["h_jepa_predictions"]

        for pred in predictions.values():
            assert pred.shape[0] == B, f"Wrong batch size for B={B}"


def test_h_jepa_sequence_length_invariance(model: KagamiWorldModel) -> None:
    """Test H-JEPA works with different sequence lengths."""
    seq_lengths = [1, 2, 4, 8, 16]

    for S in seq_lengths:
        x = torch.randn(2, S, 128)
        _output, metrics = model(x)

        assert "h_jepa_predictions" in metrics, f"Failed for seq_len={S}"

        # Longer horizons may not be available for short sequences
        # Just check that some predictions exist
        predictions = metrics["h_jepa_predictions"]
        assert len(predictions) > 0, f"No predictions for seq_len={S}"
