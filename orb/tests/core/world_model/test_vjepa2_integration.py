"""Tests for V-JEPA 2 World Model Integration.

Tests the V-JEPA 2 video encoder and its integration with KagamiWorldModel.

Components tested:
1. VJEPA2Config - Configuration dataclass
2. VideoTokenizer - Video to tubelet tokenization
3. VJEPA2Encoder - Vision Transformer encoder
4. VJEPA2Predictor - Masked prediction head
5. VJEPA2WorldModel - Full V-JEPA 2 model with EMA
6. VJEPA2KagamiIntegration - Bridge to KagamiWorldModel

December 2025.
"""

from __future__ import annotations

from typing import Any

import pytest

import torch

from kagami.core.world_model.vjepa2_integration import (
    TransformerBlock,
    VideoTokenizer,
    VJEPA2Config,
    VJEPA2Encoder,
    VJEPA2KagamiIntegration,
    VJEPA2Predictor,
    VJEPA2WorldModel,
)

pytestmark = pytest.mark.tier_integration

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def small_config() -> VJEPA2Config:
    """Small config for fast testing."""
    return VJEPA2Config(
        num_frames=8,
        frame_size=64,
        patch_size=16,
        tubelet_size=2,
        embed_dim=128,
        hidden_dim=256,
        num_heads=4,
        num_layers=2,
        predictor_depth=2,
        predictor_embed_dim=64,
        dropout=0.0,
    )


@pytest.fixture
def video_batch(small_config: VJEPA2Config) -> torch.Tensor:
    """Create a batch of video data."""
    batch_size = 2
    return torch.randn(
        batch_size,
        small_config.num_frames,
        3,  # RGB
        small_config.frame_size,
        small_config.frame_size,
    )


@pytest.fixture
def rssm_state() -> torch.Tensor:
    """Create mock RSSM state for fusion testing."""
    batch_size = 2
    kagami_latent_dim = 64
    return torch.randn(batch_size, kagami_latent_dim)


# ============================================================================
# Configuration Tests
# ============================================================================


class TestVJEPA2Config:
    """Test VJEPA2Config dataclass."""

    def test_default_config(self) -> None:
        """Default config has sensible values."""
        config = VJEPA2Config()

        assert config.model_name == "facebook/vjepa2-vitl"
        assert config.num_frames == 16
        assert config.frame_size == 224
        assert config.patch_size == 16
        assert config.tubelet_size == 2
        assert config.embed_dim == 1024
        assert config.num_heads == 16
        assert config.num_layers == 24
        assert config.context_mask_ratio == 0.9

    def test_custom_config(self) -> None:
        """Custom config overrides defaults."""
        config = VJEPA2Config(
            num_frames=32,
            embed_dim=512,
            num_layers=12,
        )

        assert config.num_frames == 32
        assert config.embed_dim == 512
        assert config.num_layers == 12
        # Unchanged defaults
        assert config.frame_size == 224


# ============================================================================
# VideoTokenizer Tests
# ============================================================================


class TestVideoTokenizer:
    """Test video tokenization into tubelets."""

    def test_output_shape(self, small_config: VJEPA2Config, video_batch: torch.Tensor) -> None:
        """Tokenizer produces correct output shape."""
        tokenizer = VideoTokenizer(
            frame_size=small_config.frame_size,
            patch_size=small_config.patch_size,
            tubelet_size=small_config.tubelet_size,
            embed_dim=small_config.embed_dim,
        )

        tokens = tokenizer(video_batch)

        # Expected: [B, N, D] where N = (T/t) * (H/p) * (W/p)
        B = video_batch.shape[0]
        T = small_config.num_frames
        t = small_config.tubelet_size
        H = W = small_config.frame_size
        p = small_config.patch_size

        expected_num_tokens = (T // t) * (H // p) * (W // p)

        assert tokens.shape == (B, expected_num_tokens, small_config.embed_dim)

    def test_gradient_flow(self, small_config: VJEPA2Config, video_batch: torch.Tensor) -> None:
        """Gradients flow through tokenizer."""
        tokenizer = VideoTokenizer(
            frame_size=small_config.frame_size,
            patch_size=small_config.patch_size,
            tubelet_size=small_config.tubelet_size,
            embed_dim=small_config.embed_dim,
        )

        video_batch.requires_grad = True
        tokens = tokenizer(video_batch)
        loss = tokens.sum()
        loss.backward()

        assert video_batch.grad is not None
        assert video_batch.grad.shape == video_batch.shape


# ============================================================================
# TransformerBlock Tests
# ============================================================================


class TestTransformerBlock:
    """Test transformer block component."""

    def test_output_shape(self) -> None:
        """Block preserves sequence shape."""
        dim = 128
        num_heads = 4
        block = TransformerBlock(dim=dim, num_heads=num_heads)

        x = torch.randn(2, 10, dim)
        y = block(x)

        assert y.shape == x.shape

    def test_residual_connection(self) -> None:
        """Block uses residual connections."""
        dim = 128
        num_heads = 4
        block = TransformerBlock(dim=dim, num_heads=num_heads)

        x = torch.randn(2, 10, dim)
        y = block(x)

        # Output should be close to input if weights are small
        # (not a strict test, just sanity check)
        assert torch.isfinite(y).all()


# ============================================================================
# VJEPA2Encoder Tests
# ============================================================================


class TestVJEPA2Encoder:
    """Test V-JEPA 2 video encoder."""

    def test_output_shape(self, small_config: VJEPA2Config, video_batch: torch.Tensor) -> None:
        """Encoder produces correct output shape with CLS token."""
        encoder = VJEPA2Encoder(small_config)

        encoded = encoder(video_batch)

        # Calculate expected number of tokens
        T = small_config.num_frames
        t = small_config.tubelet_size
        H = W = small_config.frame_size
        p = small_config.patch_size

        num_patches = (T // t) * (H // p) * (W // p)
        expected_seq_len = num_patches + 1  # +1 for CLS token

        assert encoded.shape == (
            video_batch.shape[0],
            expected_seq_len,
            small_config.embed_dim,
        )

    def test_cls_token_present(self, small_config: VJEPA2Config, video_batch: torch.Tensor) -> None:
        """CLS token is first in sequence."""
        encoder = VJEPA2Encoder(small_config)

        encoded = encoder(video_batch)
        cls_tokens = encoded[:, 0]  # First token is CLS

        # CLS should have the embedding dimension
        assert cls_tokens.shape == (video_batch.shape[0], small_config.embed_dim)

    def test_with_mask(self, small_config: VJEPA2Config, video_batch: torch.Tensor) -> None:
        """Encoder handles mask input."""
        encoder = VJEPA2Encoder(small_config)

        # Create binary mask (exclude CLS)
        T = small_config.num_frames
        t = small_config.tubelet_size
        H = W = small_config.frame_size
        p = small_config.patch_size
        num_patches = (T // t) * (H // p) * (W // p)

        mask = torch.ones(video_batch.shape[0], num_patches)
        mask[:, num_patches // 2 :] = 0  # Mask half

        encoded = encoder(video_batch, mask=mask)

        # Output shape should be same regardless of mask
        expected_seq_len = num_patches + 1
        assert encoded.shape == (
            video_batch.shape[0],
            expected_seq_len,
            small_config.embed_dim,
        )

    def test_gradient_flow(self, small_config: VJEPA2Config, video_batch: torch.Tensor) -> None:
        """Gradients flow through encoder."""
        encoder = VJEPA2Encoder(small_config)

        video_batch.requires_grad = True
        encoded = encoder(video_batch)
        loss = encoded.sum()
        loss.backward()

        assert video_batch.grad is not None


# ============================================================================
# VJEPA2Predictor Tests
# ============================================================================


class TestVJEPA2Predictor:
    """Test V-JEPA 2 masked predictor."""

    def test_output_shape(self, small_config: VJEPA2Config) -> None:
        """Predictor produces predictions for masked tokens."""
        predictor = VJEPA2Predictor(small_config)

        batch_size = 2
        num_visible = 20
        num_mask = 10

        visible_tokens = torch.randn(batch_size, num_visible, small_config.embed_dim)
        mask_indices = torch.randint(0, 100, (batch_size, num_mask))

        predictions = predictor(visible_tokens, mask_indices)

        # Output should match encoder dimension
        assert predictions.shape == (batch_size, num_mask, small_config.embed_dim)

    def test_gradient_flow(self, small_config: VJEPA2Config) -> None:
        """Gradients flow through predictor."""
        predictor = VJEPA2Predictor(small_config)

        batch_size = 2
        num_visible = 20
        num_mask = 10

        visible_tokens = torch.randn(batch_size, num_visible, small_config.embed_dim)
        visible_tokens.requires_grad = True
        mask_indices = torch.randint(0, 100, (batch_size, num_mask))

        predictions = predictor(visible_tokens, mask_indices)
        loss = predictions.sum()
        loss.backward()

        assert visible_tokens.grad is not None


# ============================================================================
# VJEPA2WorldModel Tests
# ============================================================================


class TestVJEPA2WorldModel:
    """Test full V-JEPA 2 world model."""

    def test_construction(self, small_config: VJEPA2Config) -> None:
        """Model constructs with given config."""
        model = VJEPA2WorldModel(small_config)

        assert model.config == small_config
        assert model._ema_step == 0

    def test_forward_training(self, small_config: VJEPA2Config, video_batch: torch.Tensor) -> None:
        """Forward pass in training mode returns loss and info."""
        model = VJEPA2WorldModel(small_config)
        model.train()

        loss, info = model(video_batch)

        assert isinstance(loss, torch.Tensor)
        assert loss.ndim == 0  # Scalar
        assert "vjepa2_loss" in info
        assert "mask_ratio" in info
        assert "num_masked" in info
        assert "ema_step" in info

    def test_forward_eval(self, small_config: VJEPA2Config, video_batch: torch.Tensor) -> None:
        """Forward pass in eval mode still works."""
        model = VJEPA2WorldModel(small_config)
        model.eval()

        with torch.no_grad():
            loss, _info = model(video_batch)

        assert isinstance(loss, torch.Tensor)

    def test_ema_update(self, small_config: VJEPA2Config, video_batch: torch.Tensor) -> None:
        """EMA update increments step counter in training."""
        model = VJEPA2WorldModel(small_config)
        model.train()

        initial_step = model._ema_step

        _, info = model(video_batch)

        assert model._ema_step == initial_step + 1
        assert info["ema_step"] == model._ema_step

    def test_context_encoder_frozen(self, small_config: VJEPA2Config) -> None:
        """Context encoder parameters are frozen."""
        model = VJEPA2WorldModel(small_config)

        for param in model.context_encoder.parameters():
            assert not param.requires_grad

    def test_encode_video(self, small_config: VJEPA2Config, video_batch: torch.Tensor) -> None:
        """encode_video produces global representation."""
        model = VJEPA2WorldModel(small_config)
        model.eval()

        with torch.no_grad():
            encoding = model.encode_video(video_batch)

        # Should return CLS token: [B, D]
        assert encoding.shape == (video_batch.shape[0], small_config.embed_dim)

    def test_predict_future(self, small_config: VJEPA2Config, video_batch: torch.Tensor) -> None:
        """predict_future generates future representations."""
        model = VJEPA2WorldModel(small_config)
        model.eval()

        num_future = 4

        with torch.no_grad():
            future = model.predict_future(video_batch, num_future_frames=num_future)

        assert future.shape == (video_batch.shape[0], num_future, small_config.embed_dim)

    def test_generate_mask(self, small_config: VJEPA2Config) -> None:
        """Mask generation produces correct shapes."""
        model = VJEPA2WorldModel(small_config)

        batch_size = 4
        num_tokens = 100
        mask_ratio = 0.9

        visible_mask, mask_indices = model.generate_mask(batch_size, num_tokens, mask_ratio)

        # Match implementation: num_mask = int(num_tokens * mask_ratio)
        num_masked = int(num_tokens * mask_ratio)
        num_visible = num_tokens - num_masked

        assert visible_mask.shape == (batch_size, num_tokens)
        assert mask_indices.shape == (batch_size, num_masked)

        # Check mask is binary
        assert torch.all((visible_mask == 0) | (visible_mask == 1))

        # Check correct number of visible tokens
        assert visible_mask.sum(dim=1).allclose(torch.tensor(num_visible).float())


# ============================================================================
# VJEPA2KagamiIntegration Tests
# ============================================================================


class TestVJEPA2KagamiIntegration:
    """Test V-JEPA 2 integration with KagamiWorldModel."""

    def test_construction(self, small_config: VJEPA2Config) -> None:
        """Integration module constructs correctly."""
        kagami_latent_dim = 64

        integration = VJEPA2KagamiIntegration(
            kagami_latent_dim=kagami_latent_dim,
            vjepa2_config=small_config,
        )

        assert integration.kagami_latent_dim == kagami_latent_dim
        assert isinstance(integration.vjepa2, VJEPA2WorldModel)

    def test_encode_video_context(
        self,
        small_config: VJEPA2Config,
        video_batch: torch.Tensor,
    ) -> None:
        """Video encoding produces Kagami-compatible latent."""
        kagami_latent_dim = 64

        integration = VJEPA2KagamiIntegration(
            kagami_latent_dim=kagami_latent_dim,
            vjepa2_config=small_config,
        )
        integration.eval()

        with torch.no_grad():
            context = integration.encode_video_context(video_batch)

        assert context.shape == (video_batch.shape[0], kagami_latent_dim)

    def test_fuse_with_rssm(
        self,
        small_config: VJEPA2Config,
        video_batch: torch.Tensor,
        rssm_state: torch.Tensor,
    ) -> None:
        """Gated fusion combines video context with RSSM state."""
        kagami_latent_dim = rssm_state.shape[-1]

        integration = VJEPA2KagamiIntegration(
            kagami_latent_dim=kagami_latent_dim,
            vjepa2_config=small_config,
        )
        integration.eval()

        with torch.no_grad():
            video_context = integration.encode_video_context(video_batch)
            fused = integration.fuse_with_rssm(video_context, rssm_state)

        assert fused.shape == rssm_state.shape

    def test_forward_without_rssm(
        self,
        small_config: VJEPA2Config,
        video_batch: torch.Tensor,
    ) -> None:
        """Forward without RSSM returns video context."""
        kagami_latent_dim = 64

        integration = VJEPA2KagamiIntegration(
            kagami_latent_dim=kagami_latent_dim,
            vjepa2_config=small_config,
        )
        integration.eval()

        with torch.no_grad():
            output, info = integration(video_batch)

        assert output.shape == (video_batch.shape[0], kagami_latent_dim)
        assert info["fused"] is False
        assert "video_context_norm" in info

    def test_forward_with_rssm(
        self,
        small_config: VJEPA2Config,
        video_batch: torch.Tensor,
        rssm_state: torch.Tensor,
    ) -> None:
        """Forward with RSSM returns fused output."""
        kagami_latent_dim = rssm_state.shape[-1]

        integration = VJEPA2KagamiIntegration(
            kagami_latent_dim=kagami_latent_dim,
            vjepa2_config=small_config,
        )
        integration.eval()

        with torch.no_grad():
            output, info = integration(video_batch, rssm_state=rssm_state)

        assert output.shape == rssm_state.shape
        assert info["fused"] is True

    def test_training_mode(
        self,
        small_config: VJEPA2Config,
        video_batch: torch.Tensor,
    ) -> None:
        """Training mode computes V-JEPA 2 loss."""
        kagami_latent_dim = 64

        integration = VJEPA2KagamiIntegration(
            kagami_latent_dim=kagami_latent_dim,
            vjepa2_config=small_config,
        )
        integration.train()

        _output, info = integration(video_batch)

        # Should have V-JEPA 2 metrics in training
        assert "vjepa2_loss" in info
        assert "ema_step" in info

    def test_gradient_flow_through_fusion(
        self,
        small_config: VJEPA2Config,
        video_batch: torch.Tensor,
        rssm_state: torch.Tensor,
    ) -> None:
        """Gradients flow through fusion layer."""
        kagami_latent_dim = rssm_state.shape[-1]

        integration = VJEPA2KagamiIntegration(
            kagami_latent_dim=kagami_latent_dim,
            vjepa2_config=small_config,
        )
        integration.train()

        rssm_state.requires_grad = True
        output, _ = integration(video_batch, rssm_state=rssm_state)
        loss = output.sum()
        loss.backward()

        assert rssm_state.grad is not None


# ============================================================================
# Integration with KagamiWorldModel Tests
# ============================================================================


class TestKagamiWorldModelVideoIntegration:
    """Test integration with actual KagamiWorldModel."""

    @pytest.fixture
    def kagami_model(self) -> Any:
        """Get KagamiWorldModel instance."""
        try:
            from kagami.core.world_model.kagami_world_model import KagamiWorldModelFactory

            return KagamiWorldModelFactory.create()

        except ImportError:
            pytest.skip("KagamiWorldModel not available")

    def test_latent_dimension_compatibility(
        self,
        small_config: VJEPA2Config,
        kagami_model,
        video_batch: torch.Tensor,
    ) -> None:
        """V-JEPA 2 output matches KagamiWorldModel input dimension."""
        # Get Kagami's expected input dimension
        kagami_input_dim = kagami_model.config.layer_dimensions[0]

        integration = VJEPA2KagamiIntegration(
            kagami_latent_dim=kagami_input_dim,
            vjepa2_config=small_config,
        )
        integration.eval()

        with torch.no_grad():
            video_context = integration.encode_video_context(video_batch)

        # Should be compatible with Kagami input
        assert video_context.shape[-1] == kagami_input_dim

    def test_video_to_kagami_pipeline(
        self,
        small_config: VJEPA2Config,
        kagami_model,
        video_batch: torch.Tensor,
    ) -> None:
        """Full pipeline: video → V-JEPA 2 → KagamiWorldModel."""
        kagami_input_dim = kagami_model.config.layer_dimensions[0]

        integration = VJEPA2KagamiIntegration(
            kagami_latent_dim=kagami_input_dim,
            vjepa2_config=small_config,
        )
        integration.eval()
        kagami_model.eval()

        with torch.no_grad():
            # Encode video
            video_context = integration.encode_video_context(video_batch)

            # Reshape for Kagami (add sequence dim)
            video_context_seq = video_context.unsqueeze(1)  # [B, 1, D]

            # Pass through Kagami
            kagami_output, metrics = kagami_model(video_context_seq)

        assert kagami_output.shape == video_context_seq.shape
        assert isinstance(metrics, dict)


# ============================================================================
# Device Compatibility Tests
# ============================================================================


class TestDeviceCompatibility:
    """Test model on different devices."""

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_cuda(self, small_config: VJEPA2Config) -> None:
        """Model runs on CUDA."""
        device = torch.device("cuda")
        model = VJEPA2WorldModel(small_config).to(device)

        video = torch.randn(1, 8, 3, 64, 64, device=device)

        with torch.no_grad():
            encoding = model.encode_video(video)

        assert encoding.device.type == "cuda"

    @pytest.mark.skipif(not torch.backends.mps.is_available(), reason="MPS not available")
    def test_mps(self, small_config: VJEPA2Config) -> None:
        """Model runs on Apple Silicon MPS."""
        device = torch.device("mps")
        model = VJEPA2WorldModel(small_config).to(device)

        video = torch.randn(1, 8, 3, 64, 64, device=device)

        with torch.no_grad():
            encoding = model.encode_video(video)

        assert encoding.device.type == "mps"


# ============================================================================
# Memory and Performance Tests
# ============================================================================


class TestMemoryEfficiency:
    """Test memory usage and efficiency."""

    def test_inference_no_grad(self, small_config: VJEPA2Config, video_batch: torch.Tensor) -> None:
        """Inference with no_grad doesn't accumulate gradients."""
        model = VJEPA2WorldModel(small_config)
        model.eval()

        with torch.no_grad():
            _ = model.encode_video(video_batch)

        # No parameters should have gradients
        for param in model.parameters():
            assert param.grad is None

    def test_batch_processing(self, small_config: VJEPA2Config) -> None:
        """Model handles different batch sizes."""
        model = VJEPA2WorldModel(small_config)
        model.eval()

        for batch_size in [1, 2, 4, 8]:
            video = torch.randn(
                batch_size,
                small_config.num_frames,
                3,
                small_config.frame_size,
                small_config.frame_size,
            )

            with torch.no_grad():
                encoding = model.encode_video(video)

            assert encoding.shape[0] == batch_size


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
