"""Tests for Unified Perception Module.

Test Coverage:
1. Module initialization
2. Individual modality encoding (vision, audio, text, proprio)
3. Multimodal fusion
4. Zero-padding for missing modalities
5. Singleton access
6. Configuration options
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

import torch

from kagami.core.perception import (
    PerceptionConfig,
    PerceptionModule,
    get_perception_module,
    reset_perception_module,
)


@pytest.fixture
def perception_config() -> PerceptionConfig:
    """Standard perception configuration."""
    return PerceptionConfig(
        state_dim=512,
        vision_dim=512,
        audio_dim=512,
        text_dim=384,
        proprio_dim=256,
        fusion_type="concat",
        hidden_dim=1024,
    )


@pytest.fixture
def perception_module(perception_config: PerceptionConfig) -> PerceptionModule:
    """Perception module instance."""
    return PerceptionModule(perception_config)


class TestPerceptionConfig:
    """Test perception configuration."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = PerceptionConfig()
        assert config.state_dim == 512
        assert config.vision_dim == 512
        assert config.audio_dim == 512
        assert config.text_dim == 384
        assert config.proprio_dim == 256
        assert config.fusion_type == "concat"
        assert config.hidden_dim == 1024

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = PerceptionConfig(
            state_dim=256,
            vision_dim=768,
            fusion_type="concat",
        )
        assert config.state_dim == 256
        assert config.vision_dim == 768


class TestPerceptionModule:
    """Test perception module functionality."""

    def test_initialization(self, perception_module: PerceptionModule) -> None:
        """Test module initializes correctly."""
        assert perception_module.config.state_dim == 512
        assert hasattr(perception_module, "vision")
        assert hasattr(perception_module, "audio")
        assert hasattr(perception_module, "text")
        assert hasattr(perception_module, "proprio")
        assert hasattr(perception_module, "fusion")

    def test_vision_only(self, perception_module: PerceptionModule) -> None:
        """Test perception with only vision input."""
        batch_size = 2
        image = torch.randn(batch_size, 3, 224, 224)

        sensors = {"image": image}
        state = perception_module.perceive(sensors)

        assert state.shape == (batch_size, 512)
        assert not torch.isnan(state).any()
        assert not torch.isinf(state).any()

    def test_audio_only(self, perception_module: PerceptionModule) -> None:
        """Test perception with only audio input."""
        batch_size = 2
        audio = torch.randn(batch_size, 16000)  # 1 second at 16kHz

        sensors = {"audio": audio}
        state = perception_module.perceive(sensors)

        assert state.shape == (batch_size, 512)
        assert not torch.isnan(state).any()

    def test_text_only(self, perception_module: PerceptionModule) -> None:
        """Test perception with only text input."""
        text = ["hello world", "test input"]

        sensors = {"text": text}
        state = perception_module.perceive(sensors)

        assert state.shape == (2, 512)
        assert not torch.isnan(state).any()

    def test_proprio_only(self, perception_module: PerceptionModule) -> None:
        """Test perception with only proprioception input."""
        batch_size = 2
        proprio = torch.randn(batch_size, 256)

        sensors = {"proprio": proprio}
        state = perception_module.perceive(sensors)

        assert state.shape == (batch_size, 512)
        assert not torch.isnan(state).any()

    def test_multimodal_fusion(self, perception_module: PerceptionModule) -> None:
        """Test perception with all modalities."""
        batch_size = 2
        image = torch.randn(batch_size, 3, 224, 224)
        audio = torch.randn(batch_size, 16000)
        text = ["hello", "world"]
        proprio = torch.randn(batch_size, 256)

        sensors = {
            "image": image,
            "audio": audio,
            "text": text,
            "proprio": proprio,
        }
        state = perception_module.perceive(sensors)

        assert state.shape == (batch_size, 512)
        assert not torch.isnan(state).any()
        assert not torch.isinf(state).any()

    def test_partial_modalities(self, perception_module: PerceptionModule) -> None:
        """Test perception with subset of modalities."""
        batch_size = 2
        image = torch.randn(batch_size, 3, 224, 224)
        text = ["test1", "test2"]

        sensors = {"image": image, "text": text}
        state = perception_module.perceive(sensors)

        assert state.shape == (batch_size, 512)
        assert not torch.isnan(state).any()

    def test_empty_sensors(self, perception_module: PerceptionModule) -> None:
        """Test perception with no sensors (should handle gracefully)."""
        sensors = {}
        state = perception_module.perceive(sensors)

        assert state.shape == (1, 512)
        assert not torch.isnan(state).any()

    def test_get_state(self, perception_module: PerceptionModule) -> None:
        """Test get_state method."""
        state = perception_module.get_state()

        assert state.shape == (512,)
        assert torch.allclose(state, torch.zeros(512))


class TestSingletonAccess:
    """Test singleton pattern."""

    def test_get_perception_module(self) -> None:
        """Test singleton accessor."""
        reset_perception_module()
        module1 = get_perception_module()
        module2 = get_perception_module()

        assert module1 is module2
        assert isinstance(module1, PerceptionModule)

    def test_get_with_config(self) -> None:
        """Test singleton with custom config."""
        reset_perception_module()
        config = PerceptionConfig(state_dim=256)
        module = get_perception_module(config)

        assert module.config.state_dim == 256

    def test_reset_module(self) -> None:
        """Test reset functionality."""
        reset_perception_module()
        module1 = get_perception_module()
        reset_perception_module()
        module2 = get_perception_module()

        # After reset, should be different instances
        assert module1 is not module2


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_mismatched_batch_sizes(self, perception_module: PerceptionModule) -> None:
        """Test handling of mismatched batch sizes."""
        # Vision batch size 2, text batch size 3
        image = torch.randn(2, 3, 224, 224)
        text = ["a", "b", "c"]

        sensors = {"image": image, "text": text}

        # Should handle by using first modality's batch size
        # or raise clear error
        try:
            state = perception_module.perceive(sensors)
            # If it succeeds, verify output is valid
            assert state.shape[0] in (2, 3)
            assert state.shape[1] == 512
        except (RuntimeError, ValueError) as e:
            # Expected behavior: raise error on mismatch
            assert "batch" in str(e).lower() or "size" in str(e).lower()

    def test_single_item_batch(self, perception_module: PerceptionModule) -> None:
        """Test with batch size of 1."""
        image = torch.randn(1, 3, 224, 224)

        sensors = {"image": image}
        state = perception_module.perceive(sensors)

        assert state.shape == (1, 512)

    def test_large_batch(self, perception_module: PerceptionModule) -> None:
        """Test with large batch size."""
        batch_size = 32
        image = torch.randn(batch_size, 3, 224, 224)

        sensors = {"image": image}
        state = perception_module.perceive(sensors)

        assert state.shape == (batch_size, 512)

    def test_none_values(self, perception_module: PerceptionModule) -> None:
        """Test with explicit None values."""
        sensors = {
            "image": None,
            "audio": None,
            "text": None,
            "proprio": None,
        }
        state = perception_module.perceive(sensors)

        assert state.shape == (1, 512)


class TestIntegration:
    """Integration tests with real components."""

    def test_with_world_model_integration(self, perception_module: PerceptionModule) -> None:
        """Test perception module can be used with world model."""
        # Simulate world model input
        batch_size = 4
        image = torch.randn(batch_size, 3, 224, 224)
        proprio = torch.randn(batch_size, 256)

        sensors = {"image": image, "proprio": proprio}
        state = perception_module.perceive(sensors)

        # Verify output is suitable for world model
        assert state.shape == (batch_size, 512)
        assert state.dtype == torch.float32

    def test_gradient_flow(self, perception_module: PerceptionModule) -> None:
        """Test gradients flow through perception module."""
        batch_size = 2
        image = torch.randn(batch_size, 3, 224, 224, requires_grad=True)

        sensors = {"image": image}
        state = perception_module.perceive(sensors)

        # Compute dummy loss and backprop
        loss = state.sum()
        loss.backward()

        # Verify gradients exist
        assert image.grad is not None
        assert not torch.isnan(image.grad).any()


@pytest.mark.parametrize(
    "batch_size,img_size",
    [
        (1, 64),
        (2, 128),
        (4, 224),
        (8, 256),
    ],
)
def test_various_sizes(
    batch_size: int,
    img_size: int,
    perception_module: PerceptionModule,
) -> None:
    """Test with various batch and image sizes."""
    image = torch.randn(batch_size, 3, img_size, img_size)

    sensors = {"image": image}
    state = perception_module.perceive(sensors)

    assert state.shape == (batch_size, 512)
    assert not torch.isnan(state).any()
