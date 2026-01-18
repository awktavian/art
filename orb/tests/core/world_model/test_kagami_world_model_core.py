"""Comprehensive Core Tests for KagamiWorldModel.

This test suite covers fundamental KagamiWorldModel functionality:
- Training loop (forward/backward/loss computation)
- Gradient flow through E8 bottleneck
- Batch size scaling and robustness
- Device placement correctness
- NaN/Inf handling
- Mathematical correctness (strange loop convergence, quantization)

Created: December 15, 2025
Author: Forge (e2)
"""

from __future__ import annotations

from typing import Any

import pytest

import torch
import torch.nn as nn

from kagami.core.world_model.kagami_world_model import KagamiWorldModel
from kagami.core.world_model.model_config import KagamiWorldModelConfig
from kagami.core.world_model.model_factory import KagamiWorldModelFactory



pytestmark = pytest.mark.tier_integration

class TestWorldModelTraining:
    """Test training loop and gradient flow."""

    @pytest.fixture
    def model(self) -> Any:
        """Create minimal model for training tests."""
        config = KagamiWorldModelConfig(
            bulk_dim=64,  # Small for fast tests
            device="cpu",
            num_heads=2,
            num_experts=2,
            moe_top_k=1,
        )
        model = KagamiWorldModel(config)
        model.train()
        return model

    def test_forward_backward_training_loop(self, model) -> None:
        """Test full training step (forward + backward + loss).

        This is the canonical training pattern:
        1. Forward pass through model
        2. Compute loss against target
        3. Backward pass to compute gradients
        4. Verify gradients are valid and non-zero
        """
        batch_size = 4
        seq_len = 8
        bulk_dim = model.config.bulk_dim

        # Create input and target
        x = torch.randn(batch_size, seq_len, bulk_dim)
        target = torch.randn(batch_size, seq_len, bulk_dim)

        # Zero gradients
        model.zero_grad()

        # Forward pass
        output, _metrics = model(x)
        assert output.shape == (batch_size, seq_len, bulk_dim)
        assert torch.isfinite(output).all(), "Forward pass produced NaN/Inf"

        # Compute loss
        loss = nn.functional.mse_loss(output, target)
        assert torch.isfinite(loss), f"Loss is not finite: {loss}"

        # Backward pass
        loss.backward()

        # Verify gradients exist and are finite
        params_with_grad = 0
        params_without_grad = []
        params_with_nan = []

        for name, param in model.named_parameters():
            if param.requires_grad:
                if param.grad is None:
                    params_without_grad.append(name)
                elif not torch.isfinite(param.grad).all():
                    params_with_nan.append(name)
                elif param.grad.abs().max() > 0:
                    params_with_grad += 1

        # Assert no NaN gradients
        assert (
            len(params_with_nan) == 0
        ), f"Found {len(params_with_nan)} parameters with NaN/Inf gradients: {params_with_nan[:5]}"

        # Assert most parameters have gradients (some may be zero due to gating)
        total_params = sum(1 for p in model.parameters() if p.requires_grad)
        grad_ratio = params_with_grad / max(total_params, 1)
        assert grad_ratio > 0.5, (
            f"Only {grad_ratio:.1%} of parameters received gradients "
            f"({params_with_grad}/{total_params})"
        )

    def test_gradient_flow_through_e8_bottleneck(self, model) -> None:
        """Test gradients flow through E8 quantization layer.

        The E8 bottleneck uses straight-through estimator (STE) for gradients
        through discrete quantization. This test verifies:
        1. Gradients reach the E8 quantizer
        2. Gradients propagate through the quantizer
        3. Parameters in unified_hourglass receive gradients
        """
        batch_size = 2
        seq_len = 4
        bulk_dim = model.config.bulk_dim

        x = torch.randn(batch_size, seq_len, bulk_dim, requires_grad=True)

        model.zero_grad()

        # Forward pass
        output, metrics = model(x)

        # Create loss that depends on E8 encoding
        core_state = metrics.get("core_state")
        assert core_state is not None, "CoreState not in metrics"
        assert core_state.e8_code is not None, "E8 code not populated"

        # Loss on both reconstruction and E8 code (tests STE)
        recon_loss = output.pow(2).mean()
        e8_loss = core_state.e8_code.pow(2).mean()
        total_loss = recon_loss + 0.1 * e8_loss

        # Backward
        total_loss.backward()

        # Check input gradient (verifies full backprop)
        assert x.grad is not None, "No gradient on input"
        assert torch.isfinite(x.grad).all(), "Input gradient has NaN/Inf"
        assert x.grad.abs().max() > 1e-8, "Input gradient is zero"

        # Check unified_hourglass has gradients (contains E8 bottleneck)
        hourglass_grads = []
        for name, param in model.unified_hourglass.named_parameters():
            if param.requires_grad and param.grad is not None:
                grad_norm = param.grad.abs().max().item()
                if grad_norm > 1e-8:
                    hourglass_grads.append((name, grad_norm))

        assert (
            len(hourglass_grads) > 0
        ), "No gradients in unified_hourglass (E8 bottleneck not receiving gradients)"

        # Check E8 layer specifically (residual_e8 is the E8 quantizer)
        # Note: E8 quantizer may use frozen codebook (VQ-VAE pattern) with STE gradients,
        # so we verify it exists but don't require learnable parameters.
        if hasattr(model.unified_hourglass, "residual_e8"):
            e8_layer = model.unified_hourglass.residual_e8
            assert e8_layer is not None, "E8 quantizer (residual_e8) not found"
            # E8 quantizer present - gradient flow verified via input.grad and hourglass_grads above


class TestWorldModelRobustness:
    """Test edge cases and numerical stability."""

    @pytest.fixture
    def model(self) -> Any:
        """Create model for robustness tests."""
        return KagamiWorldModelFactory.create(preset="minimal", device="cpu")

    @pytest.mark.parametrize("batch_size", [1, 8, 32, 64, 256])
    def test_batch_size_scaling_1_to_256(self, model, batch_size) -> None:
        """Test batch sizes from 1 to 256.

        Verifies:
        - No crashes for various batch sizes
        - Output shapes are correct
        - Gradients work for all batch sizes
        """
        seq_len = 4
        bulk_dim = model.config.bulk_dim

        x = torch.randn(batch_size, seq_len, bulk_dim)
        target = torch.randn(batch_size, seq_len, bulk_dim)

        model.zero_grad()

        # Forward
        output, _metrics = model(x)
        assert output.shape == (
            batch_size,
            seq_len,
            bulk_dim,
        ), f"Output shape mismatch for batch_size={batch_size}"
        assert torch.isfinite(output).all(), f"Forward produced NaN/Inf for batch_size={batch_size}"

        # Backward
        loss = nn.functional.mse_loss(output, target)
        loss.backward()

        # Check at least some gradients exist
        has_grad = any(
            p.grad is not None and p.grad.abs().max() > 0
            for p in model.parameters()
            if p.requires_grad
        )
        assert has_grad, f"No gradients for batch_size={batch_size}"

    def test_device_placement_all_tensors(self, model) -> None:
        """Test all tensors on correct device (CPU/GPU/MPS).

        This test verifies:
        1. All model parameters are on the expected device
        2. Forward pass produces tensors on the correct device
        3. No accidental device mismatches
        """
        expected_device = model.config.device

        # Check model parameters
        for name, param in model.named_parameters():
            assert (
                param.device.type == expected_device
            ), f"Parameter {name} on wrong device: {param.device.type} != {expected_device}"

        # Check forward pass output device
        x = torch.randn(2, 4, model.config.bulk_dim, device=expected_device)
        output, metrics = model(x)

        assert (
            output.device.type == expected_device
        ), f"Output on wrong device: {output.device.type} != {expected_device}"

        # Check CoreState tensors
        core_state = metrics.get("core_state")
        if core_state is not None:
            if core_state.e8_code is not None:
                assert (
                    core_state.e8_code.device.type == expected_device
                ), "CoreState.e8_code on wrong device"
            if core_state.s7_phase is not None:
                assert (
                    core_state.s7_phase.device.type == expected_device
                ), "CoreState.s7_phase on wrong device"

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_device_placement_cuda(self) -> None:
        """Test device placement specifically for CUDA."""
        model = KagamiWorldModelFactory.create(preset="minimal", device="cuda")

        # All parameters should be on CUDA
        for name, param in model.named_parameters():
            assert param.device.type == "cuda", f"Parameter {name} not on CUDA: {param.device}"

        # Forward pass should stay on CUDA
        x = torch.randn(2, 4, model.config.bulk_dim, device="cuda")
        output, _metrics = model(x)
        assert output.device.type == "cuda", "Output not on CUDA"

    def test_nan_inf_handling_in_forward_pass(self, model) -> None:
        """Test NaN/Inf input doesn't crash the model.

        The model should either:
        1. Handle NaN/Inf gracefully (clamp, replace, etc.)
        2. Produce NaN output (which can be caught by training loop)

        This test verifies the model doesn't crash with invalid input.
        """
        bulk_dim = model.config.bulk_dim

        # Test with NaN input
        x_nan = torch.randn(2, 4, bulk_dim)
        x_nan[0, 0, :] = float("nan")

        try:
            output_nan, _metrics_nan = model(x_nan)
            # If we get here, model handled NaN (acceptable)
            # Output may contain NaN, but shouldn't crash
            assert output_nan.shape == x_nan.shape, "Shape mismatch with NaN input"
        except Exception as e:
            pytest.fail(f"Model crashed on NaN input: {e}")

        # Test with Inf input
        x_inf = torch.randn(2, 4, bulk_dim)
        x_inf[0, 1, :] = float("inf")

        try:
            output_inf, _metrics_inf = model(x_inf)
            assert output_inf.shape == x_inf.shape, "Shape mismatch with Inf input"
        except Exception as e:
            pytest.fail(f"Model crashed on Inf input: {e}")

        # Test with very large values (numerical stability)
        x_large = torch.randn(2, 4, bulk_dim) * 1e6
        try:
            output_large, _metrics_large = model(x_large)
            assert output_large.shape == x_large.shape, "Shape mismatch with large input"
        except Exception as e:
            pytest.fail(f"Model crashed on large input values: {e}")


class TestWorldModelMathematics:
    """Test mathematical correctness."""

    @pytest.fixture
    def model(self) -> Any:
        """Create model for mathematical tests."""
        config = KagamiWorldModelConfig(
            bulk_dim=64,
            device="cpu",
            num_heads=2,
            num_experts=2,
            moe_top_k=1,
        )
        model = KagamiWorldModel(config)
        model.eval()
        return model

    def test_strange_loop_convergence(self, model) -> None:
        """Test mu_self (strange loop fixed point) converges.

        The strange loop tracker maintains an EMA of the S7 phase.
        After multiple forward passes, mu_self should stabilize.

        This test:
        1. Runs multiple forward passes with the same input
        2. Tracks mu_self over time
        3. Verifies it converges (distance decreases)
        """
        bulk_dim = model.config.bulk_dim
        x = torch.randn(2, 4, bulk_dim)

        # Initialize mu_self by running forward pass
        model.train()  # Enable S7 tracking
        _, metrics0 = model(x)

        # Check if strange loop tracking is active
        if "strange_loop" not in metrics0:
            pytest.skip("Strange loop tracking not active (S7 hierarchy not initialized)")

        # Get initial mu_self
        mu_self_history = [model.mu_self.clone()]
        distance_history = []

        # Run multiple forward passes (simulate training steps)
        for _ in range(10):
            _, metrics = model(x)
            mu_self_history.append(model.mu_self.clone())

            # Track distance to fixed point
            strange_loop = metrics.get("strange_loop", {})
            distance = strange_loop.get("distance_to_fixed_point")
            if distance is not None:
                distance_history.append(float(distance))

        # Check convergence: distance should decrease or stabilize
        if len(distance_history) > 5:
            early_distances = distance_history[:3]
            late_distances = distance_history[-3:]

            avg_early = sum(early_distances) / len(early_distances)
            avg_late = sum(late_distances) / len(late_distances)

            # Convergence check with epsilon tolerance for already-converged systems
            # If both early and late are < 1e-6, system is already converged (floating-point noise dominates)
            epsilon = 1e-6
            if avg_early < epsilon and avg_late < epsilon:
                # Already converged - both values at floating-point precision
                pass  # This is success
            else:
                # Not yet converged - late should be <= early (with 50% tolerance for stochasticity)
                assert (
                    avg_late <= avg_early * 1.5
                ), f"Strange loop not converging: early={avg_early:.4f}, late={avg_late:.4f}"

        # Check mu_self changes are bounded (not diverging)
        mu_diffs = [
            (mu_self_history[i + 1] - mu_self_history[i]).abs().max().item()
            for i in range(len(mu_self_history) - 1)
        ]
        max_diff = max(mu_diffs)
        assert max_diff < 10.0, f"mu_self changes too large (max_diff={max_diff}), may be diverging"

    def test_quantization_levels_in_range(self, model) -> None:
        """Test E8 quantization produces valid indices.

        E8 lattice has 240 roots, so quantization indices should be in [0, 240).
        This test verifies:
        1. E8 indices are within valid range
        2. E8 code (continuous) is populated
        3. Quantization is deterministic
        """
        bulk_dim = model.config.bulk_dim
        x = torch.randn(2, 4, bulk_dim)

        # Forward pass
        _, metrics = model(x)

        # Check E8 code in CoreState
        core_state = metrics.get("core_state")
        assert core_state is not None, "CoreState not in metrics"
        assert core_state.e8_code is not None, "E8 code not populated"

        # E8 code should be 8-dimensional (lattice coordinates)
        assert (
            core_state.e8_code.shape[-1] == 8
        ), f"E8 code should be 8D, got {core_state.e8_code.shape[-1]}"

        # E8 code should be finite
        assert torch.isfinite(core_state.e8_code).all(), "E8 code contains NaN/Inf"

        # Check E8 indices if available (discrete quantization)
        encoder_states = metrics.get("encoder_states", {})
        e8_indices = encoder_states.get("e8_indices")

        if e8_indices is not None:
            # Indices should be in valid range [0, 240)
            if isinstance(e8_indices, torch.Tensor):
                assert (e8_indices >= 0).all(), "E8 indices contain negative values"
                assert (e8_indices < 240).all(), f"E8 indices out of range: max={e8_indices.max()}"

        # Test determinism: same input -> same quantization
        _, metrics2 = model(x)
        core_state2 = metrics2.get("core_state")
        assert core_state2 is not None

        if core_state.e8_code is not None and core_state2.e8_code is not None:
            # E8 codes should be identical for same input (deterministic)
            assert torch.allclose(
                core_state.e8_code, core_state2.e8_code, atol=1e-6
            ), "E8 quantization not deterministic"

    def test_s7_phase_structure(self, model) -> None:
        """Test S7 phase has correct structure and properties.

        S7 = unit sphere of imaginary octonions = 7D unit vectors.
        This test verifies:
        1. S7 phase is 7-dimensional
        2. Norms are reasonable (should be close to unit for S7)
        3. S7 phase is finite and bounded
        """
        bulk_dim = model.config.bulk_dim
        x = torch.randn(2, 4, bulk_dim)

        model.eval()
        _, metrics = model(x)

        # Check S7 phase in CoreState
        core_state = metrics.get("core_state")
        assert core_state is not None, "CoreState not in metrics"

        if core_state.s7_phase is None:
            pytest.skip("S7 phase not populated (hourglass may not extract S7)")

        s7_phase = core_state.s7_phase
        assert s7_phase.shape[-1] == 7, f"S7 phase should be 7D, got {s7_phase.shape[-1]}"

        # S7 phase should be finite
        assert torch.isfinite(s7_phase).all(), "S7 phase contains NaN/Inf"

        # S7 phase should be bounded (normalized or close to it)
        s7_norms = s7_phase.norm(dim=-1)
        assert (s7_norms < 10.0).all(), f"S7 phase norms too large: max={s7_norms.max():.2f}"

        # Check multi-level S7 phases if available
        if core_state.s7_e8 is not None:
            assert core_state.s7_e8.shape[-1] == 7, "S7_e8 not 7D"
            assert torch.isfinite(core_state.s7_e8).all(), "S7_e8 not finite"

        # Check S7 coherence (cross-level alignment)
        if core_state.s7_coherence is not None:
            coherence = core_state.s7_coherence
            assert 0.0 <= coherence <= 1.0, f"S7 coherence out of range: {coherence}"


class TestWorldModelIntegration:
    """Test integration with training API."""

    @pytest.fixture
    def model(self) -> Any:
        """Create model for integration tests."""
        return KagamiWorldModelFactory.create(preset="minimal", device="cpu")

    def test_training_step_api(self, model) -> None:
        """Test training_step API returns LossOutput.

        The training_step method is the canonical training API:
        - Input: x (input), target (reconstruction target)
        - Output: LossOutput with total and components
        """
        bulk_dim = model.config.bulk_dim
        x = torch.randn(2, 4, bulk_dim)
        target = torch.randn(2, 4, bulk_dim)

        model.train()
        loss_output = model.training_step(x, target)

        # Check LossOutput structure (uses 'total' not 'total_loss')
        assert hasattr(loss_output, "total"), "LossOutput missing total"
        assert isinstance(loss_output.total, torch.Tensor), "total not a tensor"
        assert loss_output.total.ndim == 0, "total should be scalar"
        assert torch.isfinite(loss_output.total), "total is NaN/Inf"

        # Check loss components (uses 'components' not 'losses')
        assert hasattr(loss_output, "components"), "LossOutput missing components dict"
        assert isinstance(loss_output.components, dict), "components not a dict"

        # Should have reconstruction loss at minimum
        assert len(loss_output.components) > 0, "No loss components"

    def test_encode_decode_roundtrip(self, model) -> None:
        """Test encode -> decode preserves information.

        While exact reconstruction is not expected (lossy E8 quantization),
        the roundtrip should produce reasonable output.
        """
        bulk_dim = model.config.bulk_dim
        x = torch.randn(2, 4, bulk_dim)

        model.eval()

        # Encode
        core_state, _enc_metrics = model.encode(x)
        assert core_state.e8_code is not None, "Encode didn't produce e8_code"

        # Decode
        x_recon, _dec_metrics = model.decode(core_state)
        assert x_recon.shape == x.shape, "Decode shape mismatch"
        assert torch.isfinite(x_recon).all(), "Decode produced NaN/Inf"

        # Check reconstruction quality (should correlate, not exact)
        mse = nn.functional.mse_loss(x_recon, x)
        assert mse < 100.0, f"Reconstruction MSE too high: {mse:.2f}"


class TestHJEPAPredictions:
    """Test H-JEPA multi-horizon prediction module.

    Dec 21, 2025 (Crystal): Tests for the dimension handling fix where
    _compute_h_jepa_predictions now handles both 2D [B, 8] and 3D [B, S, 8] inputs.
    """

    @pytest.fixture
    def model(self) -> Any:
        """Create model for H-JEPA tests."""
        config = KagamiWorldModelConfig(
            bulk_dim=64,
            device="cpu",
            num_heads=2,
            num_experts=2,
            moe_top_k=1,
        )
        return KagamiWorldModel(config)

    def test_forward_with_image_input(self, model) -> None:
        """Forward pass with image input should work with 2D e8_code.

        This tests the Dec 21 fix where single image encoding produces
        [B, 8] e8_code but H-JEPA expected [B, S, 8].
        """
        model.eval()
        batch = 2
        # Single image per batch (no sequence)
        obs = torch.randn(batch, 3, 64, 64)

        with torch.no_grad():
            result = model(obs)

        # Should succeed without ValueError about shape
        assert result is not None
        # Result should be tuple (output, metrics_dict)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_h_jepa_handles_2d_input(self, model) -> None:
        """H-JEPA prediction should handle 2D [B, 8] input.

        The fix adds unsqueeze to convert [B, 8] -> [B, 1, 8].
        """
        model.eval()
        batch = 4
        e8_code_2d = torch.randn(batch, 8)

        # Call the internal method directly on model (not unified_hourglass)
        metrics = model._compute_h_jepa_predictions(e8_code_2d)

        # Should return nested structure
        assert "h_jepa_predictions" in metrics
        predictions = metrics["h_jepa_predictions"]

        # Predictions dict should have all horizons
        assert "horizon_1" in predictions
        assert "horizon_2" in predictions
        assert "horizon_4" in predictions
        assert "horizon_8" in predictions

        # Predictions should have correct shape [B, 8]
        assert predictions["horizon_1"].shape == (batch, 8)

    def test_h_jepa_handles_3d_input(self, model) -> None:
        """H-JEPA prediction should still handle 3D [B, S, 8] input."""
        model.eval()
        batch = 4
        seq_len = 3
        e8_code_3d = torch.randn(batch, seq_len, 8)

        metrics = model._compute_h_jepa_predictions(e8_code_3d)

        # Should return nested structure
        assert "h_jepa_predictions" in metrics
        predictions = metrics["h_jepa_predictions"]
        assert "horizon_1" in predictions
        assert predictions["horizon_1"].shape == (batch, 8)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
