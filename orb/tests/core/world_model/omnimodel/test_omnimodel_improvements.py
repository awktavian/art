"""Test OmniModel improvements: Enhanced video generation, perceptual losses, quality metrics.

This test validates:
1. Enhanced video generator with temporal attention
2. Perceptual loss computation
3. Video quality metrics (FID, LPIPS, temporal consistency)
4. WorldModelRegistry integration
"""

from __future__ import annotations

import pytest

import numpy as np
import torch

pytestmark = pytest.mark.tier_integration


def test_enhanced_video_generator() -> None:
    """Test enhanced video generator with temporal attention."""
    try:
        from kagami.core.world_model.omnimodel.enhanced_video_generator import (
            EnhancedLightweightVideoModel,
        )
    except (ImportError, ModuleNotFoundError):
        pytest.skip("OmniModel video generator module not available")

    # Create model
    device = "cpu"
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"

    model = EnhancedLightweightVideoModel(
        resolution=(256, 256),  # Small for fast test
        device=device,
        embed_dim=512,
        num_attention_heads=8,
        max_context_frames=4,  # Small context for test
    )

    # Test single frame generation (no context)
    frame1 = model.generate_frame(
        prompt="Test scene",
        conditioning=torch.randn(384).to(device),
        previous_frames=None,
    )

    assert frame1.shape == (3, 256, 256), f"Wrong shape: {frame1.shape}"
    assert 0 <= frame1.min() <= 1, "Frame values should be in [0, 1]"
    assert 0 <= frame1.max() <= 1, "Frame values should be in [0, 1]"

    # Test with temporal context
    frame2 = model.generate_frame(
        prompt="Test scene",
        conditioning=torch.randn(384).to(device),
        previous_frames=frame1.unsqueeze(0),  # [1, C, H, W]
    )

    assert frame2.shape == (3, 256, 256)

    # Test with multiple context frames
    prev_frames = torch.stack([frame1, frame2])  # [2, C, H, W]
    frame3 = model.generate_frame(
        prompt="Test scene",
        conditioning=torch.randn(384).to(device),
        previous_frames=prev_frames,
    )

    assert frame3.shape == (3, 256, 256)

    print("✅ Enhanced video generator test passed")


def test_perceptual_losses() -> None:
    """Test perceptual loss computation."""
    try:
        from kagami.core.world_model.omnimodel.perceptual_losses import (
            CombinedVideoLoss,
            PerceptualLoss,
            StyleLoss,
            TemporalConsistencyLoss,
        )
    except (ImportError, ModuleNotFoundError):
        pytest.skip("OmniModel perceptual losses module not available")

    device = "cpu"
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"

    # Create sample images
    B, C, H, W = 2, 3, 128, 128
    pred = torch.randn(B, C, H, W).to(device)
    target = torch.randn(B, C, H, W).to(device)

    # Test perceptual loss
    perceptual_loss = PerceptualLoss(net="alex", device=device)
    loss = perceptual_loss(pred, target)
    assert loss.item() >= 0, "Perceptual loss should be non-negative"

    # Test style loss
    style_loss = StyleLoss(device=device)
    loss = style_loss(pred, target)
    assert loss.item() >= 0, "Style loss should be non-negative"

    # Test temporal consistency loss
    temporal_loss = TemporalConsistencyLoss()
    frames = torch.randn(1, 4, C, H, W).to(device)  # [B, T, C, H, W]
    loss = temporal_loss(frames)
    assert loss.item() >= 0, "Temporal loss should be non-negative"

    # Test combined loss
    combined_loss = CombinedVideoLoss(device=device)
    losses = combined_loss(pred, target)

    assert "l1" in losses
    assert "perceptual" in losses
    assert "style" in losses
    assert "temporal" in losses
    assert "total" in losses
    assert losses["total"].item() >= 0

    print("✅ Perceptual losses test passed")


def test_video_quality_metrics() -> None:
    """Test video quality metrics computation."""
    try:
        from kagami.core.world_model.omnimodel.video_quality_metrics import (
            compute_temporal_consistency,
            evaluate_video_quality,
        )
    except (ImportError, ModuleNotFoundError):
        pytest.skip("OmniModel video quality metrics module not available")

    # Create sample video
    T, C, H, W = 8, 3, 128, 128
    video = torch.randn(T, C, H, W)

    # Normalize to [0, 1]
    video = (video - video.min()) / (video.max() - video.min())

    # Test temporal consistency
    metrics = compute_temporal_consistency(video, use_optical_flow=False)

    assert "mean_frame_diff" in metrics
    assert "consistency_score" in metrics
    assert 0 <= metrics["consistency_score"] <= 1

    # Test comprehensive evaluation
    metrics = evaluate_video_quality(
        generated_frames=video,
        reference_frames=None,  # No reference for this test
        compute_all=False,  # Skip expensive metrics
    )

    assert "mean_frame_diff" in metrics
    assert "consistency_score" in metrics

    print("✅ Video quality metrics test passed")


if __name__ == "__main__":
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Testing OmniModel Improvements")
    print("=" * 60 + "\n")

    try:
        test_world_model_registry()
        test_enhanced_video_generator()
        test_perceptual_losses()
        test_video_quality_metrics()
        test_omnimodel_integration()
        test_backward_compatibility()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()

        raise
