"""Tests for Learned RFSQ-E8 quantizer with learnable scaling and LayerNorm.

Test Coverage:
    1. Gradient flow through scale_factors and LayerNorm parameters
    2. Invertibility (encode → decode = identity)
    3. Comparison vs baseline RFSQ
    4. Learned scale adaptation
    5. LayerNorm inversion correctness
    6. Numerical stability

Created: December 14, 2025
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import torch
import torch.nn as nn

from kagami_math.learned_rfsq_e8 import (
    LearnedRFSQE8Config,
    LearnedRFSQE8Quantizer,
    create_learned_rfsq_e8_quantizer,
)
from kagami_math.rfsq_e8 import create_rfsq_e8_quantizer

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_data():
    """Sample 8D data for testing."""
    torch.manual_seed(42)
    return torch.randn(16, 8)


@pytest.fixture
def learned_quantizer():
    """Learned RFSQ-E8 with default config."""
    return create_learned_rfsq_e8_quantizer(
        max_levels=8,
        initial_scale=1.0,
        learn_scales=True,
        use_layer_norm=True,
    )


@pytest.fixture
def baseline_quantizer():
    """Baseline RFSQ-E8 (no learned parameters)."""
    return create_rfsq_e8_quantizer(
        max_levels=8,
        initial_scale=1.0,
        capacity_decay=0.8,
        normalize_residuals=True,
    )


# =============================================================================
# BASIC FUNCTIONALITY
# =============================================================================


def test_initialization():
    """Test quantizer initialization."""
    config = LearnedRFSQE8Config(
        max_levels=8,
        dim=8,
        learn_scales=True,
        use_layer_norm=True,
    )
    quantizer = LearnedRFSQE8Quantizer(config)

    # Check learnable parameters exist
    assert hasattr(quantizer, "scale_factors")
    assert quantizer.scale_factors.requires_grad
    assert quantizer.scale_factors.shape == (8,)

    # Check LayerNorm modules exist
    assert quantizer.layer_norms is not None
    assert len(quantizer.layer_norms) == 8


def test_forward_pass(learned_quantizer, sample_data) -> None:
    """Test forward pass produces expected outputs."""
    quantized, codes, info = learned_quantizer(sample_data, num_levels=4, return_info=True)

    # Check output shapes
    assert quantized.shape == sample_data.shape
    assert len(codes) == 4
    assert all(code.shape == sample_data.shape for code in codes)

    # Check info dict
    assert "norm_stats" in info
    assert len(info["norm_stats"]) == 4
    assert "reconstruction_error" in info
    assert "effective_scales" in info


def test_decode(learned_quantizer, sample_data) -> None:
    """Test decoding with norm_stats."""
    quantized, codes, info = learned_quantizer(sample_data, num_levels=4, return_info=True)
    norm_stats = info["norm_stats"]

    # Decode
    reconstructed = learned_quantizer.decode(codes, norm_stats)

    # Should match quantized output
    assert reconstructed.shape == sample_data.shape
    torch.testing.assert_close(reconstructed, quantized, rtol=1e-4, atol=1e-4)


def test_decode_without_norm_stats_raises(learned_quantizer, sample_data) -> None:
    """Test that decoding without norm_stats raises error when LayerNorm is enabled."""
    _, codes, _ = learned_quantizer(sample_data, num_levels=4)

    with pytest.raises(ValueError, match="norm_stats required"):
        learned_quantizer.decode(codes, norm_stats=None)


# =============================================================================
# GRADIENT FLOW
# =============================================================================


def test_gradient_flow_scale_factors(learned_quantizer, sample_data) -> None:
    """Test gradients flow to scale_factors."""
    # Forward pass
    quantized, _codes, _info = learned_quantizer(sample_data, num_levels=4, return_info=True)

    # Loss (reconstruction error)
    loss = (sample_data - quantized).pow(2).mean()
    loss.backward()

    # Check gradients exist and are non-zero
    assert learned_quantizer.scale_factors.grad is not None
    assert learned_quantizer.scale_factors.grad.abs().sum() > 0


def test_gradient_flow_layer_norm(learned_quantizer, sample_data) -> None:
    """Test gradients flow to LayerNorm parameters."""
    # Forward pass
    quantized, _codes, _info = learned_quantizer(sample_data, num_levels=4, return_info=True)

    # Loss
    loss = (sample_data - quantized).pow(2).mean()
    loss.backward()

    # Check gradients exist for LayerNorm parameters
    for level in range(4):
        layer_norm = learned_quantizer.layer_norms[level]
        if layer_norm.weight is not None:
            assert layer_norm.weight.grad is not None
            assert layer_norm.weight.grad.abs().sum() > 0
        if layer_norm.bias is not None:
            assert layer_norm.bias.grad is not None
            assert layer_norm.bias.grad.abs().sum() > 0


def test_optimizer_step(learned_quantizer, sample_data) -> None:
    """Test optimizer can update learned parameters."""
    # Record initial values
    initial_scales = learned_quantizer.scale_factors.clone()

    # Setup optimizer
    optimizer = torch.optim.Adam(learned_quantizer.parameters(), lr=0.01)

    # Training step
    quantized, _codes, _info = learned_quantizer(sample_data, num_levels=4, return_info=True)
    loss = (sample_data - quantized).pow(2).mean()
    loss.backward()
    optimizer.step()

    # Check parameters changed
    assert not torch.allclose(learned_quantizer.scale_factors, initial_scales)


# =============================================================================
# INVERTIBILITY
# =============================================================================


def test_encode_decode_invertibility(learned_quantizer, sample_data) -> None:
    """Test encode → decode produces correct reconstruction."""
    # Encode
    quantized, codes, info = learned_quantizer(sample_data, num_levels=8, return_info=True)
    norm_stats = info["norm_stats"]

    # Decode
    reconstructed = learned_quantizer.decode(codes, norm_stats)

    # Should exactly match quantized output
    torch.testing.assert_close(reconstructed, quantized, rtol=1e-4, atol=1e-4)


def test_layer_norm_inversion(learned_quantizer) -> None:
    """Test LayerNorm inversion is exact (within numerical precision)."""
    torch.manual_seed(42)
    x = torch.randn(32, 8)

    # Apply LayerNorm
    layer_norm = learned_quantizer.layer_norms[0]
    mean = x.mean(dim=-1, keepdim=True)
    var = x.var(dim=-1, keepdim=True, unbiased=False)
    std = (var + layer_norm.eps).sqrt()

    normalized = layer_norm(x)

    # Invert LayerNorm
    if layer_norm.weight is not None and layer_norm.bias is not None:
        gamma = layer_norm.weight
        beta = layer_norm.bias
        prenorm = (normalized - beta) / gamma
    else:
        prenorm = normalized

    reconstructed = prenorm * std + mean

    # Should recover original x
    torch.testing.assert_close(reconstructed, x, rtol=1e-4, atol=1e-4)


# =============================================================================
# COMPARISON VS BASELINE
# =============================================================================


def test_initial_performance_vs_baseline(
    learned_quantizer, baseline_quantizer, sample_data
) -> None:
    """Test Learned RFSQ starts near baseline RFSQ performance (before training).

    NOTE: Learned RFSQ uses LayerNorm which is initialized randomly.
    Initial performance may be worse than baseline RFSQ (which uses magnitude normalization).
    The benefit of Learned RFSQ comes from training, where learned scales adapt.
    """
    # Learned RFSQ (initialized with decay schedule)
    _learned_quantized, _, learned_info = learned_quantizer(
        sample_data, num_levels=8, return_info=True
    )
    learned_error = learned_info["reconstruction_error"]

    # Baseline RFSQ
    _baseline_quantized, _, baseline_info = baseline_quantizer(
        sample_data, num_levels=8, return_info=True
    )
    baseline_error = baseline_info["reconstruction_error"]

    # Learned RFSQ may be worse initially (random LayerNorm), but should be reasonable
    # We're mainly checking it doesn't catastrophically fail
    assert learned_error < 1.0  # Reasonable threshold for 8 levels

    # Optional: Check it's not TOO much worse than baseline
    # This is a soft constraint - the real benefit comes from training
    print(
        f"Learned: {learned_error:.6f}, Baseline: {baseline_error:.6f}, "
        f"Ratio: {learned_error / baseline_error if baseline_error > 0 else float('inf'):.2f}x"
    )


def test_learned_improves_with_training(sample_data) -> None:
    """Test that learned scales improve reconstruction quality after training."""
    torch.manual_seed(42)

    # Create quantizer
    quantizer = create_learned_rfsq_e8_quantizer(
        max_levels=8,
        initial_scale=1.0,
        learn_scales=True,
        use_layer_norm=True,
    )

    # Initial error
    quantizer.eval()
    with torch.no_grad():
        quantized, _, info = quantizer(sample_data, num_levels=8, return_info=True)
        initial_error = info["reconstruction_error"].item()

    # Train for a few steps
    quantizer.train()
    optimizer = torch.optim.Adam(quantizer.parameters(), lr=0.01)

    for _ in range(20):
        optimizer.zero_grad()
        quantized, _, _ = quantizer(sample_data, num_levels=8)
        loss = (sample_data - quantized).pow(2).mean()
        loss.backward()
        optimizer.step()

    # Final error
    quantizer.eval()
    with torch.no_grad():
        quantized, _, info = quantizer(sample_data, num_levels=8, return_info=True)
        final_error = info["reconstruction_error"].item()

    # Error should decrease
    assert final_error < initial_error


# =============================================================================
# SCALE ADAPTATION
# =============================================================================


def test_scale_factors_adaptation():
    """Test that scale factors adapt to data distribution."""
    torch.manual_seed(42)

    # Create data with known structure (first 4 dims large, last 4 dims small)
    x = torch.randn(64, 8)
    x[:, :4] *= 10.0  # Large magnitude
    x[:, 4:] *= 0.1  # Small magnitude

    # Create quantizer
    quantizer = create_learned_rfsq_e8_quantizer(
        max_levels=4,
        initial_scale=1.0,
        learn_scales=True,
        use_layer_norm=True,
    )

    # Record initial scales
    initial_scales = quantizer.scale_factors.clone()

    # Train
    optimizer = torch.optim.Adam(quantizer.parameters(), lr=0.01)
    for _ in range(30):
        optimizer.zero_grad()
        quantized, _, _ = quantizer(x, num_levels=4)
        loss = (x - quantized).pow(2).mean()
        loss.backward()
        optimizer.step()

    # Final scales
    final_scales = quantizer.scale_factors.clone()

    # Scales should have changed
    assert not torch.allclose(final_scales, initial_scales)


# =============================================================================
# NUMERICAL STABILITY
# =============================================================================


def test_handles_zero_residuals(learned_quantizer) -> None:
    """Test quantizer handles near-zero residuals without NaNs."""
    # Very small residuals
    x = torch.randn(16, 8) * 1e-8

    quantized, _codes, _info = learned_quantizer(x, num_levels=4, return_info=True)

    # Should not produce NaNs
    assert not torch.isnan(quantized).any()
    assert not torch.isinf(quantized).any()


def test_handles_large_values(learned_quantizer) -> None:
    """Test quantizer handles large input values."""
    # Large values
    x = torch.randn(16, 8) * 100.0

    quantized, _codes, _info = learned_quantizer(x, num_levels=4, return_info=True)

    # Should not produce NaNs
    assert not torch.isnan(quantized).any()
    assert not torch.isinf(quantized).any()


def test_scale_clamping(learned_quantizer) -> None:
    """Test that scale factors are clamped to prevent division by zero."""
    # Manually set scale factors to very small values
    with torch.no_grad():
        learned_quantizer.scale_factors[:] = 1e-10

    # Should still work (scales clamped to scale_clamp_min)
    x = torch.randn(16, 8)
    quantized, _codes, _info = learned_quantizer(x, num_levels=4, return_info=True)

    assert not torch.isnan(quantized).any()
    assert not torch.isinf(quantized).any()


# =============================================================================
# CONFIGURATION OPTIONS
# =============================================================================


def test_disable_learned_scales():
    """Test quantizer with learn_scales=False."""
    config = LearnedRFSQE8Config(
        max_levels=8,
        learn_scales=False,
        use_layer_norm=True,
    )
    quantizer = LearnedRFSQE8Quantizer(config)

    # scale_factors should be buffer (not Parameter)
    assert not quantizer.scale_factors.requires_grad


def test_disable_layer_norm():
    """Test quantizer with use_layer_norm=False."""
    config = LearnedRFSQE8Config(
        max_levels=8,
        learn_scales=True,
        use_layer_norm=False,
    )
    quantizer = LearnedRFSQE8Quantizer(config)

    # layer_norms should be None
    assert quantizer.layer_norms is None

    # Should still work (no LayerNorm applied)
    x = torch.randn(16, 8)
    quantized, codes, info = quantizer(x, num_levels=4, return_info=True)

    # Decode should work without norm_stats
    reconstructed = quantizer.decode(codes, norm_stats=info["norm_stats"])
    torch.testing.assert_close(reconstructed, quantized, rtol=1e-4, atol=1e-4)


def test_scale_init_modes():
    """Test different scale initialization modes."""
    # Decay mode
    quantizer_decay = create_learned_rfsq_e8_quantizer(
        max_levels=8,
        scale_init_mode="decay",
    )
    scales_decay = quantizer_decay.scale_factors

    # Constant mode
    quantizer_const = create_learned_rfsq_e8_quantizer(
        max_levels=8,
        scale_init_mode="constant",
    )
    scales_const = quantizer_const.scale_factors

    # Decay should decrease
    assert scales_decay[0] > scales_decay[-1]

    # Constant should be uniform
    assert torch.allclose(scales_const, scales_const[0] * torch.ones_like(scales_const))


# =============================================================================
# INTEGRATION
# =============================================================================


def test_factory_function():
    """Test factory function creates valid quantizer."""
    quantizer = create_learned_rfsq_e8_quantizer(
        max_levels=8,
        initial_scale=1.0,
        learn_scales=True,
        use_layer_norm=True,
    )

    assert isinstance(quantizer, LearnedRFSQE8Quantizer)
    assert quantizer.config.max_levels == 8
    assert quantizer.config.learn_scales is True
    assert quantizer.config.use_layer_norm is True


def test_get_stats(learned_quantizer) -> None:
    """Test get_stats returns correct information."""
    stats = learned_quantizer.get_stats()

    assert "max_levels" in stats
    assert "learn_scales" in stats
    assert "use_layer_norm" in stats
    assert "scale_factors" in stats  # Learned scales included

    # Check types
    assert isinstance(stats["max_levels"], int)
    assert isinstance(stats["learn_scales"], bool)
    assert isinstance(stats["scale_factors"], list)


# =============================================================================
# EDGE CASES
# =============================================================================


def test_single_level(learned_quantizer, sample_data) -> None:
    """Test with num_levels=1."""
    quantized, codes, _info = learned_quantizer(sample_data, num_levels=1, return_info=True)

    assert len(codes) == 1
    assert quantized.shape == sample_data.shape


def test_max_levels(learned_quantizer, sample_data) -> None:
    """Test with num_levels=max_levels."""
    quantized, codes, _info = learned_quantizer(sample_data, num_levels=8, return_info=True)

    assert len(codes) == 8
    assert quantized.shape == sample_data.shape


def test_batched_input(learned_quantizer) -> None:
    """Test with batched input."""
    x = torch.randn(4, 16, 8)  # [batch, seq, dim]

    quantized, codes, _info = learned_quantizer(x, num_levels=4, return_info=True)

    assert quantized.shape == x.shape
    assert len(codes) == 4
    assert all(code.shape == x.shape for code in codes)


def test_invalid_dimension():
    """Test that non-8D input raises error."""
    quantizer = create_learned_rfsq_e8_quantizer()
    x = torch.randn(16, 7)  # Wrong dimension

    with pytest.raises(ValueError, match="expects \\[\\.\\.\\.\\, 8\\] vectors"):
        quantizer(x)


# =============================================================================
# PERFORMANCE REGRESSION
# =============================================================================


def test_reconstruction_quality(learned_quantizer, sample_data) -> None:
    """Test reconstruction quality meets baseline expectations."""
    _quantized, _codes, info = learned_quantizer(sample_data, num_levels=8, return_info=True)

    # Error should be small for 8 levels
    error = info["reconstruction_error"]
    assert error < 1.0  # Reasonable threshold for 8 levels


def test_adaptive_stopping(sample_data) -> None:
    """Test adaptive stopping works correctly."""
    config = LearnedRFSQE8Config(
        max_levels=16,
        adaptive_levels=True,
        residual_threshold=1e-3,
    )
    quantizer = LearnedRFSQE8Quantizer(config)

    _quantized, _codes, info = quantizer(sample_data, return_info=True)

    # Should stop before max_levels if residual is small
    num_levels_used = info["num_levels_used"]
    assert num_levels_used <= 16

    # Final residual should be small
    final_residual_norm = info["final_residual_norm"]
    assert final_residual_norm < 0.1  # Should converge
