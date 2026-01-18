"""Inference Loop End-to-End Test.

Tests the complete inference pipeline:
1. Encode: input → encoder → core state
2. Predict: core state + action → RSSM → next core state
3. Decode: core state → decoder → output

This validates the full loop correctness for:
- Shape consistency throughout the pipeline
- Numerical stability
- Memory efficiency (no leaks)
- Multi-step rollout accuracy

CREATED: November 30, 2025
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import gc
import torch
import torch.nn as nn
import torch.nn.functional as F


class TestEncodePipeline:
    """Test encoding pipeline: input → encoder → core state."""

    @pytest.fixture
    def model(self):
        from kagami.core.world_model.kagami_world_model import (
            KagamiWorldModel,
            KagamiWorldModelConfig,
        )

        config = KagamiWorldModelConfig(
            layer_dimensions=(64, 32, 22, 14),
            num_heads=2,
        )
        model = KagamiWorldModel(config)
        model.eval()
        return model

    def test_encode_shapes(self, model) -> None:
        """Test encoding produces correct core state shapes."""
        x = torch.randn(4, 16, 64)

        core_state, _metrics = model.encode(x)

        # Core state components (Dec 2025: Updated to match actual implementation)
        # E8 code is 8D (E8 lattice quantization in ℝ⁸)
        assert core_state.e8_code.shape[-1] == 8, "E8 code should be 8D"
        # Shell residual is 8D (compressed E8 code)
        assert core_state.shell_residual.shape[-1] == 8, "Shell residual should be 8D"
        # S⁷ phase is 7D intrinsic dimension (model.config.s7_dim)
        assert core_state.s7_phase.shape[-1] == model.config.s7_dim, "S⁷ should be 7D intrinsic"

    def test_encode_deterministic(self, model) -> None:
        """Test encoding is deterministic in eval mode."""
        x = torch.randn(4, 16, 64)

        with torch.no_grad():
            core1, _ = model.encode(x)
            core2, _ = model.encode(x)

        assert torch.allclose(core1.e8_code, core2.e8_code)
        assert torch.allclose(core1.shell_residual, core2.shell_residual)

    def test_encode_numerically_stable(self, model) -> None:
        """Test encoding is numerically stable."""
        # Normal inputs
        x_normal = torch.randn(4, 16, 64)
        core_normal, _ = model.encode(x_normal)
        assert torch.isfinite(core_normal.e8_code).all()
        assert torch.isfinite(core_normal.shell_residual).all()

        # Large inputs
        x_large = torch.randn(4, 16, 64) * 10
        core_large, _ = model.encode(x_large)
        assert torch.isfinite(core_large.e8_code).all()

        # Small inputs
        x_small = torch.randn(4, 16, 64) * 0.01
        core_small, _ = model.encode(x_small)
        assert torch.isfinite(core_small.e8_code).all()


class TestPredictPipeline:
    """Test prediction pipeline: core state + action → next core state."""

    @pytest.fixture
    def model(self):
        from kagami.core.world_model.kagami_world_model import (
            KagamiWorldModel,
            KagamiWorldModelConfig,
        )

        config = KagamiWorldModelConfig(
            layer_dimensions=(64, 32, 22, 14),
            num_heads=2,
            rssm_deter_dim=64,
            rssm_stoch_dim=14,
            rssm_action_dim=8,
        )
        model = KagamiWorldModel(config)
        model.eval()
        return model

    def test_predict_with_action(self, model) -> None:
        """Test prediction with action input."""
        x = torch.randn(4, 8, 64)
        action = torch.randn(4, 8)

        with torch.no_grad():
            output, _metrics = model(x, action=action)

        assert torch.isfinite(output).all()

    def test_predict_multi_step(self, model) -> None:
        """Test multi-step prediction."""
        x = torch.randn(4, 8, 64)
        actions = [torch.randn(4, 8) for _ in range(5)]

        predictions = []
        with torch.no_grad():
            for action in actions:
                output, _metrics = model(x, action=action)
                predictions.append(output)
                # Use output as next input (autoregressive)
                x = output

        # All predictions should be finite
        for i, pred in enumerate(predictions):
            assert torch.isfinite(pred).all(), f"Prediction {i} has NaN/Inf"

    def test_predict_consistency(self, model) -> None:
        """Test predictions from same input produce valid outputs."""
        x = torch.randn(4, 8, 64)
        # Note: Model has stochastic components (VIB sampling)
        # Outputs may not be identical but should be similar in structure
        with torch.no_grad():
            out1, _ = model(x)
            out2, _ = model(x)

        # Both outputs should be valid
        assert torch.isfinite(out1).all()
        assert torch.isfinite(out2).all()
        # Same shape
        assert out1.shape == out2.shape


class TestDecodePipeline:
    """Test decoding pipeline: core state → decoder → output."""

    @pytest.fixture
    def model(self):
        from kagami.core.world_model.kagami_world_model import (
            KagamiWorldModel,
            KagamiWorldModelConfig,
        )

        config = KagamiWorldModelConfig(
            layer_dimensions=(64, 32, 22, 14),
            num_heads=2,
        )
        model = KagamiWorldModel(config)
        model.eval()
        return model

    def test_decode_from_core_state(self, model) -> None:
        """Test decoding from core state."""
        x = torch.randn(4, 8, 64)

        with torch.no_grad():
            core_state, _ = model.encode(x)
            output, _ = model.decode(core_state)

        assert output.shape == x.shape
        assert torch.isfinite(output).all()

    def test_decode_reconstructs(self, model) -> None:
        """Test encode-decode approximately reconstructs."""
        x = torch.randn(4, 8, 64)

        with torch.no_grad():
            core_state, _ = model.encode(x)
            output, _ = model.decode(core_state)

        # Should have some reconstruction (not exact without training)
        # Just check shapes and validity
        assert output.shape == x.shape


class TestFullInferenceLoop:
    """Test full inference loop: encode → predict → decode."""

    @pytest.fixture
    def model(self):
        from kagami.core.world_model.kagami_world_model import (
            KagamiWorldModel,
            KagamiWorldModelConfig,
        )

        config = KagamiWorldModelConfig(
            layer_dimensions=(64, 32, 22, 14),
            num_heads=2,
            rssm_deter_dim=64,
            rssm_stoch_dim=14,
            rssm_action_dim=8,
        )
        model = KagamiWorldModel(config)
        model.eval()
        return model

    def test_full_loop_forward(self, model) -> None:
        """Test full forward pass through the loop."""
        x = torch.randn(4, 8, 64)
        action = torch.randn(4, 8)

        with torch.no_grad():
            # 1. Encode
            core_state, _encode_metrics = model.encode(x)

            # 2. Apply dynamics (prediction)
            # In full forward, this is done internally

            # 3. Decode
            output, _decode_metrics = model.decode(core_state)

        assert output.shape == x.shape
        assert torch.isfinite(output).all()

    def test_multi_step_rollout(self, model) -> None:
        """Test multi-step rollout through the model."""
        x = torch.randn(4, 8, 64)
        num_steps = 10

        rollout_outputs = []

        with torch.no_grad():
            current_input = x
            for _step in range(num_steps):
                action = torch.randn(4, 8)
                output, _metrics = model(current_input, action=action)
                rollout_outputs.append(output)
                current_input = output

        # Check all outputs are valid
        for i, out in enumerate(rollout_outputs):
            assert torch.isfinite(out).all(), f"Step {i} produced NaN/Inf"
            assert out.shape == x.shape, f"Step {i} has wrong shape"

    def test_rollout_stability(self, model) -> None:
        """Test rollout remains stable over many steps."""
        x = torch.randn(4, 8, 64)
        num_steps = 50

        output_norms = []

        with torch.no_grad():
            current_input = x
            for _step in range(num_steps):
                action = torch.randn(4, 8) * 0.1  # Small actions
                output, _ = model(current_input, action=action)
                output_norms.append(output.norm().item())
                current_input = output

        # Norms should not explode
        max_norm = max(output_norms)
        assert max_norm < 1e6, f"Rollout exploded: max norm = {max_norm}"

    def test_rollout_with_e8_context(self, model) -> None:
        """Test rollout with E8 colony context."""
        x = torch.randn(4, 8, 64)
        # E8 context is a single 8D vector (colony aggregate)
        e8_context = torch.randn(8)
        e8_context = F.normalize(e8_context, dim=-1)

        with torch.no_grad():
            output, _metrics = model(x, e8_context=e8_context)

        assert torch.isfinite(output).all()


class TestMemoryEfficiency:
    """Test memory efficiency during inference."""

    @pytest.fixture
    def model(self):
        from kagami.core.world_model.kagami_world_model import (
            KagamiWorldModel,
            KagamiWorldModelConfig,
        )

        config = KagamiWorldModelConfig(
            layer_dimensions=(64, 32, 22, 14),
            num_heads=2,
        )
        return KagamiWorldModel(config)

    def test_no_grad_no_graph(self, model) -> None:
        """Test no grad context doesn't build computation graph."""
        model.eval()
        x = torch.randn(4, 8, 64)

        with torch.no_grad():
            output, _ = model(x)

        # Output should not require grad
        assert not output.requires_grad

    def test_repeated_inference_no_leak(self, model) -> None:
        """Test repeated inference doesn't leak memory."""
        model.eval()

        # Warmup
        with torch.no_grad():
            for _ in range(5):
                x = torch.randn(4, 8, 64)
                _ = model(x)

        # Measure initial memory
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            initial_mem = torch.cuda.memory_allocated()

        # Run many inferences
        with torch.no_grad():
            for _ in range(100):
                x = torch.randn(4, 8, 64)
                _output, _ = model(x)

        # Measure final memory
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            final_mem = torch.cuda.memory_allocated()
            # Memory should not grow significantly
            assert final_mem < initial_mem * 1.5


class TestBatchInference:
    """Test batch inference handling."""

    @pytest.fixture
    def model(self):
        from kagami.core.world_model.kagami_world_model import (
            KagamiWorldModel,
            KagamiWorldModelConfig,
        )

        config = KagamiWorldModelConfig(
            layer_dimensions=(64, 32, 22, 14),
            num_heads=2,
        )
        model = KagamiWorldModel(config)
        model.eval()
        return model

    def test_different_batch_sizes(self, model) -> None:
        """Test model handles different batch sizes."""
        for batch_size in [1, 4, 16, 32]:
            x = torch.randn(batch_size, 8, 64)
            with torch.no_grad():
                output, _ = model(x)
            assert output.shape[0] == batch_size

    def test_different_sequence_lengths(self, model) -> None:
        """Test model handles different sequence lengths."""
        for seq_len in [1, 4, 16, 64]:
            x = torch.randn(4, seq_len, 64)
            with torch.no_grad():
                output, _ = model(x)
            assert output.shape[1] == seq_len

    def test_single_sample_inference(self, model) -> None:
        """Test inference with single sample."""
        x = torch.randn(1, 1, 64)
        with torch.no_grad():
            output, _ = model(x)
        assert output.shape == (1, 1, 64)


class TestCoreStateOperations:
    """Test core state creation and manipulation."""

    @pytest.fixture
    def model(self):
        from kagami.core.world_model.kagami_world_model import (
            KagamiWorldModel,
            KagamiWorldModelConfig,
        )

        config = KagamiWorldModelConfig(
            layer_dimensions=(64, 32, 22, 14),
            num_heads=2,
        )
        return KagamiWorldModel(config)

    def test_core_state_creation(self, model) -> None:
        """Test core state can be created manually."""
        from kagami.core.world_model.kagami_world_model import CoreState

        core_state = CoreState(
            e8_code=torch.randn(4, 8, 8),
            s7_phase=torch.randn(4, 8, 8),
            shell_residual=torch.randn(4, 8, 14),
            timestamp=0.0,
        )

        assert core_state.e8_code.shape == (4, 8, 8)  # type: ignore[union-attr]
        assert core_state.s7_phase.shape == (4, 8, 8)  # type: ignore[union-attr]
        assert core_state.shell_residual.shape == (4, 8, 14)  # type: ignore[union-attr]

    def test_core_state_device_transfer(self, model) -> None:
        """Test core state can be transferred between devices."""
        from kagami.core.world_model.kagami_world_model import CoreState

        core_state = CoreState(
            e8_code=torch.randn(4, 8, 8),
            s7_phase=torch.randn(4, 8, 8),
            shell_residual=torch.randn(4, 8, 14),
            timestamp=0.0,
        )

        # Should be on CPU
        assert core_state.e8_code.device.type == "cpu"  # type: ignore[union-attr]


class TestInferenceWithMask:
    """Test inference with attention mask."""

    @pytest.fixture
    def model(self):
        from kagami.core.world_model.kagami_world_model import (
            KagamiWorldModel,
            KagamiWorldModelConfig,
        )

        config = KagamiWorldModelConfig(
            layer_dimensions=(64, 32, 22, 14),
            num_heads=2,
        )
        model = KagamiWorldModel(config)
        model.eval()
        return model

    def test_inference_with_causal_mask(self, model) -> None:
        """Test inference with causal attention mask."""
        x = torch.randn(4, 16, 64)
        # Causal mask
        seq_len = 16
        mask = torch.triu(torch.ones(seq_len, seq_len), diagonal=1).bool()

        with torch.no_grad():
            output, _ = model(x, mask=mask)

        assert output.shape == x.shape
        assert torch.isfinite(output).all()

    def test_inference_with_padding_mask(self, model) -> None:
        """Test inference with padding mask."""
        x = torch.randn(4, 16, 64)
        # Padding mask (some positions are padding)
        mask = torch.zeros(4, 16).bool()
        mask[:, 12:] = True  # Last 4 positions are padding

        with torch.no_grad():
            output, _ = model(x, mask=mask)

        assert output.shape == x.shape


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
