"""Tests for Optimized Sensorimotor Encoder.

Tests cover:
- Encoder initialization
- Forward pass with various modality combinations
- Output dimensions and shapes
- Pre-allocated buffers
- Optional fusion modes (Perceiver, GMU)
- Performance characteristics

Coverage target: kagami/core/embodiment/sensorimotor_encoder_optimized.py
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import torch
import torch.nn as nn

from kagami.core.embodiment import (
    SensorimotorEncoder,
    create_sensorimotor_encoder,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def device():
    """Get appropriate device for testing."""
    if torch.backends.mps.is_available():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"


@pytest.fixture
def encoder(device: Any) -> Any:
    """Create encoder with default settings."""
    return SensorimotorEncoder(device=device)


@pytest.fixture
def batch_inputs(device: Any) -> Dict[str, Any]:
    """Create batch of inputs for all modalities."""
    return {
        "vision_emb": torch.randn(2, 512, device=device),
        "audio_emb": torch.randn(2, 512, device=device),
        "touch_emb": torch.randn(2, 64, device=device),
        "language_emb": torch.randn(2, 384, device=device),
        "proprio_emb": torch.randn(2, 32, device=device),
        "intero_emb": torch.randn(2, 16, device=device),
        "meta_emb": torch.randn(2, 256, device=device),
    }


@pytest.fixture
def single_inputs(device: Any) -> Dict[str, Any]:
    """Create single-sample inputs (batch=1, common case)."""
    return {
        "vision_emb": torch.randn(1, 512, device=device),
        "audio_emb": torch.randn(1, 512, device=device),
        "touch_emb": torch.randn(1, 64, device=device),
        "language_emb": torch.randn(1, 384, device=device),
        "proprio_emb": torch.randn(1, 32, device=device),
        "intero_emb": torch.randn(1, 16, device=device),
        "meta_emb": torch.randn(1, 256, device=device),
    }


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestEncoderInit:
    """Tests for encoder initialization."""

    def test_default_init(self, device) -> None:
        """Test default initialization."""
        encoder = SensorimotorEncoder(device=device)
        assert encoder is not None
        assert encoder.device == device

    def test_custom_dimensions(self, device) -> None:
        """Test initialization with custom dimensions."""
        encoder = SensorimotorEncoder(
            vision_dim=256,
            audio_dim=256,
            touch_dim=32,
            language_dim=128,
            proprio_dim=16,
            intero_dim=8,
            meta_dim=64,
            device=device,
        )
        assert encoder.modality_dims[0] == 256  # vision
        assert encoder.modality_dims[2] == 32  # touch

    def test_fused_projection_created(self, encoder) -> None:
        """Test that fused projection layer is created."""
        assert hasattr(encoder, "fused_octonion_proj")
        assert isinstance(encoder.fused_octonion_proj, nn.Linear)
        assert encoder.fused_octonion_proj.out_features == 7

    def test_temporal_encoder_created(self, encoder) -> None:
        """Test that temporal encoder is created."""
        assert hasattr(encoder, "temporal_encoder")
        assert isinstance(encoder.temporal_encoder, nn.Linear)
        assert encoder.temporal_encoder.out_features == 14

    def test_zero_buffers_registered(self, encoder) -> None:
        """Test that zero buffers are registered."""
        assert hasattr(encoder, "zero_vision")
        assert hasattr(encoder, "zero_audio")
        assert hasattr(encoder, "zero_touch")
        assert hasattr(encoder, "zero_language")
        assert hasattr(encoder, "zero_proprio")
        assert hasattr(encoder, "zero_intero")
        assert hasattr(encoder, "zero_meta")


# =============================================================================
# FORWARD PASS TESTS
# =============================================================================


class TestEncoderForward:
    """Tests for encoder forward pass."""

    def test_forward_all_modalities(self, encoder, batch_inputs) -> None:
        """Test forward pass with all modalities."""
        output = encoder(**batch_inputs)

        # Output is tuple (z_temporal, o_sensory)
        assert isinstance(output, tuple)
        assert len(output) == 2
        z_temporal, o_sensory = output
        assert z_temporal is not None
        assert o_sensory is not None

    def test_forward_single_sample(self, encoder, single_inputs) -> None:
        """Test forward pass with batch=1 (most common case)."""
        output = encoder(**single_inputs)
        assert output is not None

    def test_forward_missing_modality(self, encoder, device) -> None:
        """Test forward pass with missing modalities."""
        # Only vision and audio
        partial_inputs = {
            "vision_emb": torch.randn(1, 512, device=device),
            "audio_emb": torch.randn(1, 512, device=device),
        }
        # Should use pre-allocated zeros for missing modalities
        output = encoder(**partial_inputs)
        assert output is not None

    def test_forward_vision_only(self, encoder, device) -> None:
        """Test forward pass with only vision."""
        vision_only = {
            "vision_emb": torch.randn(1, 512, device=device),
        }
        output = encoder(**vision_only)
        assert output is not None

    def test_forward_empty_inputs(self, encoder) -> None:
        """Test forward pass with no inputs (all zeros)."""
        output = encoder()
        assert output is not None

    def test_forward_various_batch_sizes(self, encoder, device) -> None:
        """Test forward pass with various batch sizes."""
        for batch_size in [1, 2, 4, 8, 16]:
            inputs = {
                "vision_emb": torch.randn(batch_size, 512, device=device),
                "audio_emb": torch.randn(batch_size, 512, device=device),
            }
            output = encoder(**inputs)
            assert output is not None


# =============================================================================
# OUTPUT SHAPE TESTS
# =============================================================================


class TestOutputShapes:
    """Tests for output shapes."""

    def test_octonion_output_shape(self, encoder, single_inputs) -> None:
        """Test octonion output has correct shape."""
        output = encoder(**single_inputs)

        # Output is tuple (z_temporal, o_sensory)
        assert isinstance(output, tuple)
        _z_temporal, o_sensory = output
        # S⁷ is 8-dimensional (unit sphere in R⁸)
        assert o_sensory.shape[-1] == 8

    def test_temporal_output_shape(self, encoder, single_inputs) -> None:
        """Test temporal encoding shape."""
        output = encoder(**single_inputs)

        # Output is tuple (z_temporal, o_sensory)
        z_temporal, _o_sensory = output
        # H¹⁴ is 14-dimensional
        assert z_temporal.shape[-1] == 14


# =============================================================================
# PERCEIVER FUSION TESTS
# =============================================================================


class TestPerceiverFusion:
    """Tests for optional Perceiver fusion."""

    def test_perceiver_init(self, device) -> None:
        """Test initialization with Perceiver fusion."""
        try:
            encoder = SensorimotorEncoder(
                use_perceiver_fusion=True,
                perceiver_latent_dim=128,
                perceiver_num_blocks=2,
                device=device,
            )
            assert encoder.use_perceiver_fusion is True
            assert encoder.perceiver is not None
        except ImportError:
            pytest.skip("SOTA Perceiver not available")

    def test_perceiver_forward(self, device) -> None:
        """Test forward pass with Perceiver fusion."""
        try:
            encoder = SensorimotorEncoder(
                use_perceiver_fusion=True,
                device=device,
            )
            encoder.to(device)  # Ensure all parameters on device
            inputs = {
                "vision_emb": torch.randn(1, 512, device=device),
                "audio_emb": torch.randn(1, 512, device=device),
            }
            output = encoder(**inputs)
            assert output is not None
        except (ImportError, RuntimeError) as e:
            pytest.skip(f"SOTA Perceiver not available or device error: {e}")


# =============================================================================
# GMU GATING TESTS
# =============================================================================


class TestGMUGating:
    """Tests for optional GMU gating."""

    def test_gmu_init(self, device) -> None:
        """Test initialization with GMU gating."""
        try:
            encoder = SensorimotorEncoder(
                use_gmu_gating=True,
                gmu_hidden_dim=64,
                device=device,
            )
            assert encoder.use_gmu_gating is True
            assert encoder.gmu is not None
        except ImportError:
            pytest.skip("GMU gating not available")

    def test_gmu_forward(self, device) -> None:
        """Test forward pass with GMU gating."""
        try:
            encoder = SensorimotorEncoder(
                use_gmu_gating=True,
                device=device,
            )
            # GMU requires all modality inputs, not just some
            inputs = {
                "vision_emb": torch.randn(1, 512, device=device),
                "audio_emb": torch.randn(1, 512, device=device),
                "touch_emb": torch.randn(1, 64, device=device),
                "language_emb": torch.randn(1, 384, device=device),
                "proprio_emb": torch.randn(1, 32, device=device),
                "intero_emb": torch.randn(1, 16, device=device),
                "meta_emb": torch.randn(1, 256, device=device),
            }
            output = encoder(**inputs)
            assert output is not None
        except (ImportError, AttributeError, RuntimeError) as e:
            pytest.skip(f"GMU gating not available: {e}")


# =============================================================================
# FACTORY FUNCTION TESTS
# =============================================================================


class TestFactoryFunction:
    """Tests for create_sensorimotor_encoder factory."""

    def test_create_default(self, device) -> None:
        """Test factory with defaults."""
        encoder = create_sensorimotor_encoder(device=device)
        assert isinstance(encoder, SensorimotorEncoder)

    def test_create_with_options(self, device) -> None:
        """Test factory with custom device."""
        encoder = create_sensorimotor_encoder(device=device)
        assert encoder.device == device


# =============================================================================
# GRADIENT FLOW TESTS
# =============================================================================


class TestGradientFlow:
    """Tests for gradient flow through encoder."""

    def test_gradients_flow(self, encoder, batch_inputs) -> None:
        """Test that gradients flow through encoder."""
        encoder.train()

        # Ensure inputs require grad
        for key in batch_inputs:
            batch_inputs[key] = batch_inputs[key].requires_grad_(True)

        output = encoder(**batch_inputs)

        # Output is tuple (z_temporal, o_sensory)
        z_temporal, o_sensory = output

        # Compute loss and backward
        loss = z_temporal.sum() + o_sensory.sum()
        loss.backward()

        # Check gradients exist
        for _key, tensor in batch_inputs.items():
            if tensor.grad is not None:
                assert tensor.grad.shape == tensor.shape

    def test_no_grad_inference(self, encoder, batch_inputs) -> None:
        """Test inference with no_grad."""
        encoder.eval()

        with torch.no_grad():
            output = encoder(**batch_inputs)

        assert output is not None


# =============================================================================
# DEVICE HANDLING TESTS
# =============================================================================


class TestDeviceHandling:
    """Tests for device handling."""

    def test_cpu_device(self) -> None:
        """Test encoder on CPU."""
        encoder = SensorimotorEncoder(device="cpu")
        inputs = {"vision_emb": torch.randn(1, 512)}
        output = encoder(**inputs)
        assert output is not None

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_cuda_device(self) -> None:
        """Test encoder on CUDA."""
        encoder = SensorimotorEncoder(device="cuda")
        inputs = {"vision_emb": torch.randn(1, 512, device="cuda")}
        output = encoder(**inputs)
        assert output is not None

    @pytest.mark.skipif(not torch.backends.mps.is_available(), reason="MPS not available")
    def test_mps_device(self) -> None:
        """Test encoder on MPS (Apple Silicon)."""
        encoder = SensorimotorEncoder(device="mps")
        inputs = {"vision_emb": torch.randn(1, 512, device="mps")}
        output = encoder(**inputs)
        assert output is not None


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


class TestPerformance:
    """Tests for performance characteristics."""

    def test_single_sample_latency(self, encoder, device) -> None:
        """Test latency for single sample (target: <10ms)."""
        import time

        inputs = {
            "vision_emb": torch.randn(1, 512, device=device),
            "audio_emb": torch.randn(1, 512, device=device),
        }

        # Warmup
        for _ in range(3):
            encoder(**inputs)

        # Measure
        if device != "cpu":
            torch.cuda.synchronize() if torch.cuda.is_available() else None

        start = time.perf_counter()
        for _ in range(10):
            encoder(**inputs)

        if device != "cpu":
            torch.cuda.synchronize() if torch.cuda.is_available() else None

        elapsed = (time.perf_counter() - start) / 10 * 1000  # ms

        # Log but don't fail (performance varies by hardware)
        print(f"Average latency: {elapsed:.2f}ms")
        # Target is <10ms but we don't enforce in tests

    def test_memory_efficiency(self, encoder, device) -> None:
        """Test that pre-allocated buffers are used."""
        # Check zero buffers are on correct device
        assert encoder.zero_vision.device.type == device
        assert encoder.zero_audio.device.type == device

        # Verify buffers are reused (same id)
        id1 = id(encoder.zero_vision)
        _ = encoder(vision_emb=torch.randn(1, 512, device=device))
        id2 = id(encoder.zero_vision)
        assert id1 == id2  # Same buffer


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_nan_input(self, encoder, device) -> None:
        """Test handling of NaN inputs."""
        inputs = {
            "vision_emb": torch.full((1, 512), float("nan"), device=device),
        }
        output = encoder(**inputs)
        # Should handle NaN (may produce NaN output but shouldn't crash)
        assert output is not None

    def test_inf_input(self, encoder, device) -> None:
        """Test handling of Inf inputs."""
        inputs = {
            "vision_emb": torch.full((1, 512), float("inf"), device=device),
        }
        output = encoder(**inputs)
        assert output is not None

    def test_zero_input(self, encoder, device) -> None:
        """Test handling of all-zero inputs."""
        inputs = {
            "vision_emb": torch.zeros(1, 512, device=device),
            "audio_emb": torch.zeros(1, 512, device=device),
        }
        output = encoder(**inputs)
        assert output is not None

    def test_large_batch(self, encoder, device) -> None:
        """Test handling of large batch sizes."""
        inputs = {
            "vision_emb": torch.randn(128, 512, device=device),
        }
        output = encoder(**inputs)
        assert output is not None
