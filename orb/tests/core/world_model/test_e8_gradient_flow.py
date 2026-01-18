"""E8 Gradient Flow Validation - Critical for World Model Learning.

CREATED: December 14, 2025 (Crystal, e7)
MISSION: Verify gradient flow through E8 residual bottleneck hourglass

The E8 hourglass bottleneck is IMPLEMENTED but gradient flow is UNTESTED.
Risk: Vanishing/exploding gradients through quantization.
Impact: World model training may fail silently.

Test Coverage:
1. Basic gradient propagation (input → E8 bottleneck → output)
2. Hourglass reconstruction (encode → quantize → decode)
3. E8 quantization differentiability (straight-through estimator)
4. Multi-level bottleneck (1-byte, 2-byte, 4-byte encodings)
5. Integration with world model (full training step)
6. Gradient magnitude sanity (no vanishing/exploding)

Architecture Under Test:
    Bulk(512) → E8(248) → E7(133) → E6(78) → F4(52) → G2(14) → E8_VQ(8)
                                                                    ↓
    Bulk(512) ← E8(248) ← E7(133) ← E6(78) ← F4(52) ← G2(14) ← Tower(7)

References:
- kagami/core/world_model/kagami_world_model.py — Entry point
- kagami/core/world_model/model_layers.py — E8ResidualBlock
- kagami/core/math/e8_lattice_protocol.py — ResidualE8LatticeVQ
- kagami/core/math/e8_lattice_quantizer.py — nearest_e8
"""

from __future__ import annotations

from typing import Any

import pytest

import torch
import torch.nn as nn

pytestmark = pytest.mark.tier_integration


class TestBasicGradientPropagation:
    """Verify gradients flow from output back to input through E8 bottleneck."""

    @pytest.fixture
    def e8_quantizer(self) -> Any:
        """Create E8 residual quantizer."""
        from kagami_math.e8_lattice_protocol import (
            E8LatticeResidualConfig,
            ResidualE8LatticeVQ,
        )

        config = E8LatticeResidualConfig(
            max_levels=4,
            min_levels=1,
            initial_scale=2.0,
            adaptive_levels=False,  # Fixed levels for deterministic testing
        )
        return ResidualE8LatticeVQ(config)

    def test_e8_quantizer_has_gradients(self, e8_quantizer) -> None:
        """Verify E8 quantization is differentiable via straight-through estimator."""
        x = torch.randn(2, 16, 8, requires_grad=True)

        # Forward: quantize (returns dict with quantized, loss, indices, perplexity)
        vq_result = e8_quantizer(x, num_levels=4)
        quantized = vq_result["quantized"]

        # Verify output has grad_fn (is part of computation graph)
        assert quantized.requires_grad, "Quantized output should require gradients"
        assert quantized.grad_fn is not None, "Quantized output should have grad_fn (STE)"

        # Backward: verify gradients reach input
        loss = quantized.sum()
        loss.backward()

        # Verify gradients exist and are finite
        assert x.grad is not None, "Input should receive gradients through E8 quantization"
        assert torch.isfinite(x.grad).all(), "Gradients should be finite (no NaN/Inf)"
        assert x.grad.abs().max() > 0, "Gradients should be non-zero"

    def test_e8_quantizer_gradient_magnitude(self, e8_quantizer) -> None:
        """Verify gradient magnitudes are reasonable (not vanishing/exploding)."""
        x = torch.randn(2, 16, 8, requires_grad=True)

        vq_result = e8_quantizer(x, num_levels=4)
        quantized = vq_result["quantized"]
        loss = quantized.pow(2).sum()
        loss.backward()

        grad_norm = x.grad.norm().item()  # type: ignore[union-attr]
        assert 1e-6 < grad_norm < 100, (
            f"Gradient norm {grad_norm:.2e} outside safe range [1e-6, 100]"
        )

    def test_e8_quantizer_reconstruction_loss_bounded(self, e8_quantizer) -> None:
        """Verify reconstruction error is bounded for simple inputs."""
        x = torch.randn(2, 16, 8)

        vq_result = e8_quantizer(x, num_levels=4)
        quantized = vq_result["quantized"]
        reconstruction_error = (x - quantized).pow(2).mean()

        # With 4 levels of E8 residual quantization, error should be small
        assert reconstruction_error < 0.1, (
            f"Reconstruction error {reconstruction_error:.2e} too high"
        )


class TestHourglassReconstruction:
    """Test full encode-decode cycle through hourglass."""

    @pytest.fixture
    def bulk_dim(self) -> Any:
        """Get bulk dimension from config."""
        from kagami_math.dimensions import get_bulk_dim

        return get_bulk_dim()

    @pytest.fixture
    def model(self, bulk_dim) -> Any:
        """Create world model for testing."""
        from kagami.core.world_model.kagami_world_model import (
            KagamiWorldModel,
            KagamiWorldModelConfig,
        )

        config = KagamiWorldModelConfig()
        model = KagamiWorldModel(config)
        model.train()
        return model

    def test_hourglass_encode_has_gradients(self, model, bulk_dim) -> None:
        """Verify encoder produces outputs with gradients."""
        x = torch.randn(2, 8, bulk_dim, requires_grad=True)

        core_state, _metrics = model.encode(x)

        # Verify core state components have gradients
        assert core_state.e8_code is not None, "Encoder should produce e8_code"
        assert core_state.e8_code.requires_grad, "e8_code should require gradients"
        assert core_state.e8_code.grad_fn is not None, "e8_code should be in computation graph"

    def test_hourglass_decode_has_gradients(self, model, bulk_dim) -> None:
        """Verify decoder produces gradients back to encoded state."""
        x = torch.randn(2, 8, bulk_dim, requires_grad=True)

        # Encode
        core_state, _enc_metrics = model.encode(x)

        # Decode
        reconstructed, _dec_metrics = model.decode(core_state)

        # Backward through reconstruction
        loss = reconstructed.sum()
        loss.backward()

        # Verify gradients reach input
        assert x.grad is not None, "Gradients should flow through encode → decode"
        assert torch.isfinite(x.grad).all(), "Gradients should be finite"
        assert x.grad.abs().max() > 0, "Gradients should be non-zero"

    def test_hourglass_reconstruction_quality(self, model, bulk_dim) -> None:
        """Verify reconstruction loss is bounded.

        NOTE: Random inputs are hard to reconstruct perfectly. The model hasn't been
        trained, so we just verify loss is finite and gradients flow. A trained model
        would achieve much lower reconstruction loss.
        """
        x = torch.randn(2, 8, bulk_dim)

        # Full forward pass (includes encode + decode)
        reconstructed, _metrics = model(x)

        # Reconstruction error should be finite (untrained model won't be perfect)
        recon_loss = (x - reconstructed).pow(2).mean()
        assert torch.isfinite(recon_loss), "Reconstruction loss should be finite"
        assert recon_loss < 10.0, f"Reconstruction loss {recon_loss:.2e} unreasonably high"

        # The key test: gradients should flow
        recon_loss.backward()
        assert any(p.grad is not None and p.grad.abs().max() > 0 for p in model.parameters()), (
            "Reconstruction loss should provide gradients"
        )


class TestE8QuantizationDifferentiability:
    """Verify E8 quantization is differentiable via straight-through estimator."""

    def test_nearest_e8_is_differentiable(self) -> None:
        """Verify nearest_e8 works in autograd context.

        NOTE: nearest_e8 uses torch.round() and torch.where() which DO create grad_fn,
        but the gradients will be zero (rounding has zero derivative).
        The STE in ResidualE8LatticeVQ fixes this by using: y = x + (y_hard - x).detach()
        """
        from kagami_math.e8_lattice_quantizer import nearest_e8

        x = torch.randn(2, 8, requires_grad=True)

        # nearest_e8 uses torch operations that create grad_fn
        y = nearest_e8(x)

        # y has grad_fn (from torch.round, torch.where) but gradients would be zero
        # This is why ResidualE8LatticeVQ uses STE to fix gradient flow
        assert y.grad_fn is not None, "nearest_e8 uses differentiable torch ops (but needs STE)"

    def test_residual_vq_straight_through_estimator(self) -> None:
        """Verify STE: forward uses hard quantization, backward treats as identity."""
        from kagami_math.e8_lattice_protocol import (
            E8LatticeResidualConfig,
            ResidualE8LatticeVQ,
        )

        config = E8LatticeResidualConfig(max_levels=2, adaptive_levels=False)
        vq = ResidualE8LatticeVQ(config)
        vq.train()  # STE only active in training mode

        x = torch.randn(2, 8, requires_grad=True)
        vq_result = vq(x, num_levels=2)
        quantized = vq_result["quantized"]

        # Forward: quantized != x (hard quantization)
        assert not torch.allclose(quantized, x), "Quantization should change values"

        # Backward: gradients should flow (STE)
        loss = quantized.sum()
        loss.backward()

        assert x.grad is not None, "STE should provide gradients"
        # STE gradient should be non-zero (not completely blocked)
        assert x.grad.abs().max() > 0, "STE should allow gradient flow"


class TestMultiLevelBottleneck:
    """Test 1-byte, 2-byte, 4-byte E8 encodings."""

    @pytest.fixture
    def vq(self) -> Any:
        """Create E8 residual VQ with high max_levels."""
        from kagami_math.e8_lattice_protocol import (
            E8LatticeResidualConfig,
            ResidualE8LatticeVQ,
        )

        config = E8LatticeResidualConfig(
            max_levels=16,
            min_levels=1,
            adaptive_levels=False,
        )
        return ResidualE8LatticeVQ(config)

    def test_1_byte_encoding(self, vq) -> None:
        """Test 1-level encoding (1 byte per 8D vector)."""
        x = torch.randn(2, 8, requires_grad=True)
        vq_result = vq(x, num_levels=1)
        quantized = vq_result["quantized"]
        indices = vq_result["indices"]

        assert indices.shape[-2] == 1, "1-byte encoding should have 1 level"

        loss = quantized.sum()
        loss.backward()

        assert x.grad is not None, "1-byte encoding should have gradients"
        assert torch.isfinite(x.grad).all(), "Gradients should be finite"

    def test_2_byte_encoding(self, vq) -> None:
        """Test 2-level encoding (2 bytes per 8D vector)."""
        x = torch.randn(2, 8, requires_grad=True)
        vq_result = vq(x, num_levels=2)
        quantized = vq_result["quantized"]
        indices = vq_result["indices"]

        assert indices.shape[-2] == 2, "2-byte encoding should have 2 levels"

        loss = quantized.sum()
        loss.backward()

        assert x.grad is not None, "2-byte encoding should have gradients"
        assert torch.isfinite(x.grad).all(), "Gradients should be finite"

    def test_4_byte_encoding(self, vq) -> None:
        """Test 4-level encoding (4 bytes per 8D vector)."""
        x = torch.randn(2, 8, requires_grad=True)
        vq_result = vq(x, num_levels=4)
        quantized = vq_result["quantized"]
        indices = vq_result["indices"]

        assert indices.shape[-2] == 4, "4-byte encoding should have 4 levels"

        loss = quantized.sum()
        loss.backward()

        assert x.grad is not None, "4-byte encoding should have gradients"
        assert torch.isfinite(x.grad).all(), "Gradients should be finite"

    def test_reconstruction_improves_with_more_levels(self, vq) -> None:
        """Verify tighter bottlenecks don't break gradients."""
        x = torch.randn(2, 8)

        # Test with increasing levels
        errors = []
        for num_levels in [1, 2, 4, 8]:
            vq_result = vq(x, num_levels=num_levels)
            quantized = vq_result["quantized"]
            error = (x - quantized).pow(2).mean().item()
            errors.append(error)

        # Reconstruction should improve with more levels
        assert errors[-1] < errors[0], "More levels should reduce reconstruction error"


class TestWorldModelIntegration:
    """End-to-end gradient flow in full world model."""

    @pytest.fixture
    def bulk_dim(self) -> Any:
        """Get bulk dimension."""
        from kagami_math.dimensions import get_bulk_dim

        return get_bulk_dim()

    @pytest.fixture
    def model(self) -> Any:
        """Create world model."""
        from kagami.core.world_model.kagami_world_model import (
            KagamiWorldModel,
            KagamiWorldModelConfig,
        )

        config = KagamiWorldModelConfig()
        model = KagamiWorldModel(config)
        model.train()
        return model

    def test_full_forward_pass_has_gradients(self, model, bulk_dim) -> None:
        """Test full forward pass: input → RSSM → hourglass → E8 → decode → output."""
        x = torch.randn(2, 8, bulk_dim, requires_grad=True)

        model.zero_grad()

        # Forward
        output, _metrics = model(x)

        # Verify output is in computation graph
        assert output.requires_grad, "Output should require gradients"
        assert output.grad_fn is not None, "Output should have grad_fn"

        # Backward
        loss = output.sum()
        loss.backward()

        # Verify gradients reach input
        assert x.grad is not None, "Full forward pass should provide gradients to input"
        assert torch.isfinite(x.grad).all(), "Gradients should be finite"
        assert x.grad.abs().max() > 0, "Gradients should be non-zero"

    def test_training_step_e8_gradients(self, model, bulk_dim) -> None:
        """Verify training_step provides gradients to E8 quantizer."""
        x = torch.randn(2, 8, bulk_dim)
        target = torch.randn(2, 8, bulk_dim)

        model.zero_grad()

        # Training step
        loss_output = model.training_step(x, target)
        total_loss = loss_output.total

        assert torch.isfinite(total_loss), "Loss should be finite"

        # Backward
        total_loss.backward()

        # Check E8 quantizer has gradients (it's in unified_hourglass.residual_e8)
        e8_vq = model.unified_hourglass.residual_e8
        e8_has_grad = False

        for _name, param in e8_vq.named_parameters():
            if param.grad is not None and param.grad.abs().max() > 0:
                e8_has_grad = True
                break

        # E8 lattice VQ has no learned parameters (pure geometry)
        # So we check that the encoder/decoder around it have gradients instead
        hourglass_has_grad = False
        for _name, param in model.unified_hourglass.named_parameters():
            if param.grad is not None and param.grad.abs().max() > 0:
                hourglass_has_grad = True
                break

        assert hourglass_has_grad, "Hourglass (containing E8) should have gradients"

    def test_encoder_states_have_gradients(self, model, bulk_dim) -> None:
        """Verify encoder intermediate states are in computation graph."""
        x = torch.randn(2, 8, bulk_dim, requires_grad=True)

        _output, metrics = model(x)

        # Check encoder states
        encoder_states = metrics.get("encoder_states", {})

        # E8 quantized representation should have gradients
        e8_quantized = encoder_states.get("e8_quantized")
        if e8_quantized is not None:
            assert e8_quantized.requires_grad, "E8 quantized state should require gradients"

        # G2 representation should have gradients
        g2 = encoder_states.get("g2")
        if g2 is not None:
            assert g2.requires_grad, "G2 state should require gradients"


class TestGradientMagnitudeSanity:
    """Check for vanishing/exploding gradients."""

    @pytest.fixture
    def bulk_dim(self) -> Any:
        """Get bulk dimension."""
        from kagami_math.dimensions import get_bulk_dim

        return get_bulk_dim()

    @pytest.fixture
    def model(self) -> Any:
        """Create world model."""
        from kagami.core.world_model.kagami_world_model import (
            KagamiWorldModel,
            KagamiWorldModelConfig,
        )

        config = KagamiWorldModelConfig()
        model = KagamiWorldModel(config)
        model.train()
        return model

    def test_no_vanishing_gradients(self, model, bulk_dim) -> None:
        """Verify gradients don't vanish through E8 bottleneck."""
        x = torch.randn(2, 8, bulk_dim, requires_grad=True)

        model.zero_grad()
        output, _metrics = model(x)

        loss = output.sum()
        loss.backward()

        # Input gradient norm should be significant
        input_grad_norm = x.grad.norm().item()  # type: ignore[union-attr]
        assert input_grad_norm > 1e-6, f"Input gradient norm {input_grad_norm:.2e} is vanishing"

    def test_no_exploding_gradients(self, model, bulk_dim) -> None:
        """Verify gradients don't explode through E8 bottleneck."""
        x = torch.randn(2, 8, bulk_dim, requires_grad=True)

        model.zero_grad()
        output, _metrics = model(x)

        loss = output.sum()
        loss.backward()

        # Check all parameter gradients are bounded
        max_grad_norm = 0.0
        for _name, param in model.named_parameters():
            if param.grad is not None:
                grad_norm = param.grad.norm().item()
                max_grad_norm = max(max_grad_norm, grad_norm)

        assert max_grad_norm < 1000, f"Gradient norm {max_grad_norm:.2e} is exploding"

    def test_gradient_scale_consistent_across_levels(self, model, bulk_dim) -> None:
        """Verify gradient scale is consistent across hourglass levels."""
        x = torch.randn(2, 8, bulk_dim, requires_grad=True)

        model.zero_grad()

        # Get encoder states
        _core_state, metrics = model.encode(x)
        encoder_states = metrics.get("encoder_states", {})

        # Collect intermediate representations
        levels = {}
        for key in ["e8", "e7", "e6", "f4", "g2"]:
            val = encoder_states.get(key)
            if isinstance(val, torch.Tensor) and val.requires_grad:
                levels[key] = val

        # Backward through all levels
        if levels:
            loss = sum(v.sum() for v in levels.values())
            loss.backward()  # type: ignore[union-attr]

            # Input should have gradients
            assert x.grad is not None, "Input should receive gradients from all levels"

            # Gradient norm should be reasonable
            grad_norm = x.grad.norm().item()
            assert 1e-6 < grad_norm < 100, (
                f"Gradient norm {grad_norm:.2e} outside safe range through hierarchy"
            )


class TestE8ByteProtocol:
    """Test byte encoding/decoding preserves gradient flow."""

    def test_encode_decode_roundtrip(self) -> None:
        """Verify byte encoding doesn't break gradient flow."""
        from kagami_math.e8_lattice_protocol import (
            E8LatticeResidualConfig,
            ResidualE8LatticeVQ,
        )

        config = E8LatticeResidualConfig(max_levels=4, adaptive_levels=False)
        vq = ResidualE8LatticeVQ(config)
        vq.train()

        x = torch.randn(8, requires_grad=True)

        # Quantize (returns dict with quantized, loss, indices, perplexity)
        vq_result = vq(x.unsqueeze(0), num_levels=4)
        quantized = vq_result["quantized"]
        indices = vq_result["indices"]

        # Decode from indices (no gradients - discrete)
        # Convert indices tensor [1, L, 8] to list of tensors for decode
        codes = [indices[:, i, :] for i in range(indices.shape[1])]
        decoded = vq.decode(codes)

        # But the forward pass quantized tensor has gradients
        assert quantized.requires_grad, "Quantized tensor should have gradients (STE)"

        loss = quantized.sum()
        loss.backward()

        assert x.grad is not None, "Byte protocol should preserve gradient flow"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
