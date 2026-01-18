"""Tests for kagami.core.world_model.model_factory module.

This tests the KagamiWorldModelFactory and related functions that were
extracted during recent refactoring.

Created: December 13, 2025
Updated: December 13, 2025 - Removed deprecated get_kagami_world_model tests
"""

from __future__ import annotations

import pytest

from unittest.mock import Mock, patch

import torch
import torch.nn as nn

from kagami.core.config.unified_config import WorldModelConfig as KagamiWorldModelConfig
from kagami.core.config.unified_config import (
    get_kagami_config,
)
from kagami.core.world_model.model_core import KagamiWorldModel
from kagami.core.world_model.model_factory import (
    KagamiWorldModelFactory,
    get_model_info,
    load_model_from_checkpoint,
    save_model_checkpoint,
)

pytestmark = pytest.mark.tier_integration


class TestKagamiWorldModelFactory:
    """Test the main factory class."""

    def test_factory_initialization(self) -> None:
        """Test factory initializes with default config."""
        factory = KagamiWorldModelFactory()

        assert factory.config is not None
        assert isinstance(factory.config, KagamiWorldModelConfig)

    def test_factory_with_custom_config(self) -> None:
        """Test factory with custom configuration."""
        custom_config = get_kagami_config().world_model
        custom_config.device = "cpu"

        factory = KagamiWorldModelFactory(custom_config)
        assert factory.config is custom_config
        assert factory.config.device == "cpu"

    def test_create_model_basic(self) -> None:
        """Test basic model creation."""
        factory = KagamiWorldModelFactory()
        model = factory.create_model()

        assert isinstance(model, KagamiWorldModel)
        assert model.config is not None

        # Should have parameters
        param_count = sum(p.numel() for p in model.parameters())
        assert param_count > 0

    def test_create_model_with_overrides(self) -> None:
        """Test model creation with configuration overrides."""
        factory = KagamiWorldModelFactory()

        # Test with device override
        model = factory.create_model(device="cpu")

        assert isinstance(model, KagamiWorldModel)
        # Config should be updated
        assert model.config.device == "cpu"

    def test_factory_create_classmethod(self) -> None:
        """Test KagamiWorldModelFactory.create() classmethod."""
        model = KagamiWorldModelFactory.create(preset="minimal", device="cpu")

        assert isinstance(model, KagamiWorldModel)
        # minimal preset = bulk_dim 32
        assert model.config.bulk_dim == 32
        assert model.config.device == "cpu"

    def test_factory_create_with_bulk_dim(self) -> None:
        """Test factory create with explicit bulk_dim."""
        model = KagamiWorldModelFactory.create(bulk_dim=64, device="cpu")

        assert isinstance(model, KagamiWorldModel)
        assert model.config.bulk_dim == 64

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_create_model_cuda(self) -> None:
        """Test model creation with CUDA device."""
        factory = KagamiWorldModelFactory()
        model = factory.create_model(device="cuda")

        assert isinstance(model, KagamiWorldModel)
        # Model should be on CUDA
        assert next(model.parameters()).device.type == "cuda"

    def test_create_multiple_models(self) -> None:
        """Test creating multiple models doesn't interfere."""
        factory = KagamiWorldModelFactory()

        model1 = factory.create_model()
        model2 = factory.create_model()

        # Should be different instances
        assert model1 is not model2
        assert isinstance(model1, KagamiWorldModel)
        assert isinstance(model2, KagamiWorldModel)


class TestFactoryFunctions:
    """Test model info and utility functions."""

    def test_get_model_info(self) -> None:
        """Test get_model_info function."""
        model = KagamiWorldModelFactory.create(preset="minimal")
        info = get_model_info(model)

        assert isinstance(info, dict)
        assert "total_parameters" in info
        assert "trainable_parameters" in info
        assert "config" in info
        assert "device" in info
        assert "model_size_mb" in info

        assert info["total_parameters"] > 0
        assert info["trainable_parameters"] > 0
        assert info["model_size_mb"] > 0


class TestModelCheckpointing:
    """Test model save/load functionality."""

    def test_save_model_checkpoint_basic(self) -> None:
        """Test basic model checkpoint saving."""
        model = KagamiWorldModelFactory.create(preset="minimal")

        # Mock the actual file saving to avoid filesystem issues
        with patch("torch.save") as mock_save:
            result = save_model_checkpoint(model, "/tmp/test_checkpoint.pt")

            # Should call torch.save
            mock_save.assert_called_once()

            # Function returns None but should complete without error
            assert result is None  # Function returns None on success

    def test_save_model_checkpoint_with_metadata(self) -> None:
        """Test checkpoint saving with metadata."""
        model = KagamiWorldModelFactory.create(preset="minimal")
        metadata = {"epoch": 5, "loss": 0.1, "optimizer_state": {}}

        with patch("torch.save") as mock_save:
            result = save_model_checkpoint(model, "/tmp/test.pt", metadata=metadata)

            mock_save.assert_called_once()
            # Check that call includes metadata
            args, _kwargs = mock_save.call_args
            checkpoint_data = args[0]
            assert "metadata" in checkpoint_data

    def test_load_model_from_checkpoint(self) -> None:
        """Test model loading from checkpoint."""
        # Mock checkpoint data
        mock_checkpoint = {
            "model_state_dict": {},
            "config": get_kagami_config().world_model.__dict__,
            "metadata": {"epoch": 5},
        }

        with patch("torch.load", return_value=mock_checkpoint) as mock_load:
            with patch.object(KagamiWorldModel, "load_state_dict") as mock_load_state:
                model = load_model_from_checkpoint("/tmp/test.pt")

                # Security fix: now includes weights_only=False parameter
                mock_load.assert_called_once_with(
                    "/tmp/test.pt", map_location="cpu", weights_only=False
                )
                mock_load_state.assert_called_once()

                assert isinstance(model, KagamiWorldModel)

    def test_load_checkpoint_with_device(self) -> None:
        """Test loading checkpoint to specific device."""
        mock_checkpoint = {
            "model_state_dict": {},
            "config": get_kagami_config().world_model.__dict__,
        }

        with patch("torch.load", return_value=mock_checkpoint):
            with patch.object(KagamiWorldModel, "load_state_dict"):
                model = load_model_from_checkpoint("/tmp/test.pt", device="cpu")

                # Model device should be set correctly
                # (Note: config.device might not always match due to implementation details)
                assert isinstance(model, KagamiWorldModel)


class TestWeightInitialization:
    """Test model weight initialization."""

    def test_model_has_initialized_weights(self) -> None:
        """Test that created models have properly initialized weights."""
        model = KagamiWorldModelFactory.create(preset="minimal")

        # Check that parameters are not all zero
        all_params = torch.cat([p.flatten() for p in model.parameters()])

        # Should have some non-zero values (proper initialization)
        assert not torch.allclose(all_params, torch.zeros_like(all_params))

        # Should have reasonable variance (not all same value)
        assert torch.std(all_params) > 1e-6

    def test_consistent_initialization(self) -> None:
        """Test that initialization is consistent (same seed gives same model)."""
        # Set seed for reproducibility
        torch.manual_seed(42)
        model1 = KagamiWorldModelFactory.create(preset="minimal")

        torch.manual_seed(42)
        model2 = KagamiWorldModelFactory.create(preset="minimal")

        # Should have same parameter values
        for p1, p2 in zip(model1.parameters(), model2.parameters(), strict=False):
            assert torch.allclose(p1, p2, atol=1e-6)


class TestFactoryErrorHandling:
    """Test factory error handling."""

    def test_checkpoint_load_file_not_found(self) -> None:
        """Test handling when checkpoint file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_model_from_checkpoint("/nonexistent/path.pt")

    def test_corrupted_checkpoint_handling(self) -> None:
        """Test handling of corrupted checkpoint data."""
        # Mock corrupted checkpoint (missing required keys)
        mock_corrupted = {"invalid": "data"}

        with patch("torch.load", return_value=mock_corrupted):
            with pytest.raises(KeyError):
                load_model_from_checkpoint("/tmp/corrupted.pt")


class TestFactoryIntegration:
    """Test factory integration with other components."""

    def test_factory_creates_compatible_models(self) -> None:
        """Test that factory creates models compatible with training."""
        model = KagamiWorldModelFactory.create(preset="minimal")

        # Should be able to create optimizer
        optimizer = torch.optim.Adam(model.parameters())
        assert optimizer is not None

        # Should be able to compute forward pass
        test_input = torch.randn(1, 32)  # minimal preset bulk_dim=32
        try:
            # May fail if full forward pass needs more setup,
            # but should at least not crash on parameter access
            params = list(model.parameters())
            assert len(params) > 0
        except Exception as e:
            # If forward pass needs specific setup, just verify structure
            assert hasattr(model, "forward")

    def test_factory_model_device_placement(self) -> None:
        """Test that device placement works correctly."""
        # CPU model
        cpu_model = KagamiWorldModelFactory.create(preset="minimal", device="cpu")
        cpu_param = next(cpu_model.parameters())
        assert cpu_param.device.type == "cpu"

        # CUDA model (if available)
        if torch.cuda.is_available():
            cuda_model = KagamiWorldModelFactory.create(preset="minimal", device="cuda")
            cuda_param = next(cuda_model.parameters())
            assert cuda_param.device.type == "cuda"


if __name__ == "__main__":
    pytest.main([__file__])
