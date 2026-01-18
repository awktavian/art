"""Unit tests for unified configuration system.

Tests the Pydantic V2-based unified config that consolidates:
    1. kagami/core/config/e2e_model_config.py
    2. kagami/core/world_model/model_config.py
    3. kagami/core/world_model/rssm_config.py
    4. kagami/core/training/training_config.py
    5. kagami/core/safety/cbf_config.py (DELETED Dec 2025 - replaced by SafetyConfig)

Test coverage:
    - Pydantic V2 validation
    - Cross-field validation
    - Dimension synchronization
    - Profile presets
    - Environment variable overrides
    - Backward compatibility
    - Serialization (save/load)
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import json
import os
import tempfile
from pathlib import Path

import torch

from kagami.core.config.unified_config import (
    AdaptiveConfig,
    CBFDynamicsConfig,
    ClassKConfig,
    ClassKType,
    E8BottleneckConfig,
    HofstadterLoopConfig,
    KagamiConfig,
    RSSMConfig,
    SafetyConfig,
    TrainingConfig,
    WorldModelConfig,
    apply_env_overrides,
    get_kagami_config,
)

# =============================================================================
# E8 BOTTLENECK CONFIG TESTS
# =============================================================================


class TestE8BottleneckConfig:
    """Test E8 bottleneck configuration."""

    def test_default_config(self) -> None:
        """Test default E8 bottleneck configuration."""
        config = E8BottleneckConfig()
        assert config.training_levels == 4
        assert config.inference_levels == 8
        assert config.adaptive_levels is True
        assert config.temp_start == 1.0
        assert config.temp_end == 0.01
        assert config.commitment_weight == 0.25

    def test_validation_inference_ge_training(self) -> None:
        """Test that inference_levels >= training_levels."""
        # Valid: inference >= training
        config = E8BottleneckConfig(training_levels=4, inference_levels=8)
        assert config.inference_levels >= config.training_levels

        # Invalid: inference < training
        with pytest.raises(ValueError, match="inference_levels.*must be.*training_levels"):
            E8BottleneckConfig(training_levels=8, inference_levels=4)

    def test_validation_temp_end_lt_temp_start(self) -> None:
        """Test that temp_end < temp_start."""
        # Valid
        config = E8BottleneckConfig(temp_start=1.0, temp_end=0.01)
        assert config.temp_end < config.temp_start

        # Invalid: temp_end >= temp_start
        with pytest.raises(ValueError, match="temp_end.*must be.*temp_start"):
            E8BottleneckConfig(temp_start=1.0, temp_end=2.0)

    def test_validation_levels_range(self) -> None:
        """Test levels must be in [1, 16]."""
        # Valid
        E8BottleneckConfig(training_levels=1, inference_levels=16)

        # Invalid: too small
        with pytest.raises(ValueError):
            E8BottleneckConfig(training_levels=0)

        # Invalid: too large
        with pytest.raises(ValueError):
            E8BottleneckConfig(training_levels=17)


# =============================================================================
# RSSM CONFIG TESTS
# =============================================================================


class TestRSSMConfig:
    """Test RSSM configuration."""

    def test_default_config(self) -> None:
        """Test default RSSM configuration."""
        config = RSSMConfig()
        assert config.state_dim == 256
        assert config.num_colonies == 7
        assert config.action_dim == 8  # E8
        assert config.obs_dim == 15  # E8(8) + S7(7)
        assert config.stochastic_dim == 14  # H14
        assert config.latent_classes == 240  # E8 roots

    def test_validation_num_colonies_fixed(self) -> None:
        """Test that num_colonies must be 7."""
        # Valid
        config = RSSMConfig(num_colonies=7)
        assert config.num_colonies == 7

        # Invalid: not 7
        with pytest.raises(ValueError):
            RSSMConfig(num_colonies=5)

    def test_validation_divisible_by_8(self) -> None:
        """Test that state_dim and colony_dim are divisible by 8."""
        # Valid
        RSSMConfig(state_dim=256, colony_dim=128)

        # Invalid: not divisible by 8
        with pytest.raises(ValueError, match="divisible by 8"):
            RSSMConfig(state_dim=100)

    def test_validation_max_std_gt_min_std(self) -> None:
        """Test that max_std > min_std."""
        # Valid
        config = RSSMConfig(min_std=0.1, max_std=1.0)
        assert config.max_std > config.min_std

        # Invalid: max <= min
        with pytest.raises(ValueError, match="max_std.*must be.*min_std"):
            RSSMConfig(min_std=1.0, max_std=0.5)

    def test_validation_burn_in_lt_sequence_length(self) -> None:
        """Test that burn_in_steps < sequence_length."""
        # Valid
        config = RSSMConfig(sequence_length=50, burn_in_steps=5)
        assert config.burn_in_steps < config.sequence_length

        # Invalid: burn_in >= sequence
        with pytest.raises(ValueError, match="burn_in_steps.*must be.*sequence_length"):
            RSSMConfig(sequence_length=10, burn_in_steps=15)

    def test_hofstadter_loop_config(self) -> None:
        """Test nested Hofstadter loop configuration."""
        config = RSSMConfig()
        assert config.hofstadter_config.self_dim == 7  # S7
        assert config.hofstadter_config.internal_dim == 14  # G2
        assert config.hofstadter_config.action_dim == 8  # E8


# =============================================================================
# WORLD MODEL CONFIG TESTS
# =============================================================================


class TestWorldModelConfig:
    """Test world model configuration."""

    def test_default_config(self) -> None:
        """Test default world model configuration."""
        config = WorldModelConfig()
        assert config.bulk_dim >= 32
        assert config.bulk_dim % 8 == 0
        assert len(config.layer_dimensions) > 0
        assert config.layer_dimensions[0] == config.bulk_dim

    def test_validation_bulk_dim_multiple_of_8(self) -> None:
        """Test that bulk_dim must be multiple of 8."""
        # Valid
        WorldModelConfig(bulk_dim=512)

        # Invalid: not multiple of 8
        with pytest.raises(ValueError, match="bulk_dim must be multiple of 8"):
            WorldModelConfig(bulk_dim=100)

    def test_dimension_derivation(self) -> None:
        """Test automatic dimension derivation."""
        config = WorldModelConfig(bulk_dim=512)
        # Should auto-derive layer_dimensions and matryoshka_dims
        assert len(config.layer_dimensions) > 0
        assert len(config.matryoshka_dims) > 0
        assert config.layer_dimensions[0] == 512

    def test_device_validation(self) -> None:
        """Test device normalization and validation."""
        # Valid devices
        config_cpu = WorldModelConfig(device="cpu")
        assert config_cpu.device == "cpu"

        config_cuda = WorldModelConfig(device="cuda")
        # Should be cuda if available, cpu otherwise
        assert config_cuda.device in {"cpu", "cuda"}

        # Invalid device falls back to CPU
        config_bad = WorldModelConfig(device="invalid")
        assert config_bad.device == "cpu"

    def test_dtype_validation(self) -> None:
        """Test dtype validation."""
        # Valid
        WorldModelConfig(dtype="float32")
        WorldModelConfig(dtype="float16")
        WorldModelConfig(dtype="bfloat16")

        # Invalid
        with pytest.raises(ValueError, match="dtype must be in"):
            WorldModelConfig(dtype="invalid")

    def test_nested_configs(self) -> None:
        """Test nested configuration objects."""
        config = WorldModelConfig()
        assert isinstance(config.rssm, RSSMConfig)
        assert isinstance(config.e8_bottleneck, E8BottleneckConfig)


# =============================================================================
# TRAINING CONFIG TESTS
# =============================================================================


class TestTrainingConfig:
    """Test training configuration."""

    def test_default_config(self) -> None:
        """Test default training configuration."""
        config = TrainingConfig()
        assert config.model_preset == "balanced"
        assert config.batch_size > 0
        assert config.learning_rate > 0
        assert config.gradient_accumulation_steps >= 1

    def test_validation_model_preset(self) -> None:
        """Test model preset validation."""
        # Valid presets
        for preset in ["minimal", "balanced", "large", "maximal"]:
            config = TrainingConfig(model_preset=preset)
            assert config.model_preset == preset

        # Invalid preset
        with pytest.raises(ValueError, match="model_preset must be in"):
            TrainingConfig(model_preset="invalid")

    def test_validation_positive_values(self) -> None:
        """Test that numeric values must be positive."""
        # Valid
        TrainingConfig(batch_size=32, learning_rate=1e-3, warmup_steps=10)

        # Invalid: zero or negative
        with pytest.raises(ValueError):
            TrainingConfig(batch_size=0)

        with pytest.raises(ValueError):
            TrainingConfig(learning_rate=-0.001)

    def test_device_auto_detection(self) -> None:
        """Test automatic device detection."""
        config = TrainingConfig(device="auto")
        # Should select best available device
        assert config.device in {"cpu", "cuda", "mps"}


# =============================================================================
# SAFETY (CBF) CONFIG TESTS
# =============================================================================


class TestSafetyConfig:
    """Test CBF safety configuration."""

    def test_default_config(self) -> None:
        """Test default safety configuration."""
        config = SafetyConfig()
        assert config.safety_threshold == 0.5  # CRITICAL FIX value
        assert len(config.u_min) == 2
        assert len(config.u_max) == 2
        assert len(config.risk_weights) == 4

    def test_validation_safety_threshold(self) -> None:
        """Test safety_threshold must be in (0, 1)."""
        # Valid
        SafetyConfig(safety_threshold=0.5)

        # Invalid: out of range
        with pytest.raises(ValueError):
            SafetyConfig(safety_threshold=0.0)

        with pytest.raises(ValueError):
            SafetyConfig(safety_threshold=1.5)

    def test_validation_control_bounds(self) -> None:
        """Test control bounds validation."""
        # Valid
        SafetyConfig(u_min=[0.0, 0.0], u_max=[1.0, 1.0])

        # Invalid: wrong size
        with pytest.raises(ValueError, match="2 elements"):
            SafetyConfig(u_min=[0.0, 0.0, 0.0])

        # Invalid: u_min >= u_max
        with pytest.raises(ValueError, match="u_min.*must be.*u_max"):
            SafetyConfig(u_min=[0.5, 0.5], u_max=[0.3, 0.3])

    def test_validation_risk_weights(self) -> None:
        """Test risk weights validation."""
        # Valid
        SafetyConfig(risk_weights=[0.4, 0.3, 0.1, 0.2])

        # Invalid: wrong size
        with pytest.raises(ValueError, match="4 elements"):
            SafetyConfig(risk_weights=[0.5, 0.5])

        # Invalid: negative weights
        with pytest.raises(ValueError, match="non-negative"):
            SafetyConfig(risk_weights=[0.4, -0.3, 0.1, 0.2])

    def test_nested_configs(self) -> None:
        """Test nested CBF configuration objects."""
        config = SafetyConfig()
        assert isinstance(config.dynamics, CBFDynamicsConfig)
        assert isinstance(config.class_k, ClassKConfig)
        assert isinstance(config.adaptive, AdaptiveConfig)


# =============================================================================
# ROOT KAGAMI CONFIG TESTS
# =============================================================================


class TestKagamiConfig:
    """Test root KagamiConfig."""

    def test_default_config(self) -> None:
        """Test default Kagami configuration."""
        config = KagamiConfig()
        assert isinstance(config.world_model, WorldModelConfig)
        assert isinstance(config.training, TrainingConfig)
        assert isinstance(config.safety, SafetyConfig)
        assert config.profile_name == "base"

    def test_dimension_synchronization(self) -> None:
        """Test automatic dimension synchronization across configs."""
        config = KagamiConfig()
        bulk_dim = config.world_model.bulk_dim

        # RSSM dimensions should sync with bulk_dim
        assert config.world_model.rssm.state_dim == bulk_dim
        assert config.world_model.rssm.latent_dim == bulk_dim

    def test_serialization_to_dict(self) -> None:
        """Test config serialization to dictionary."""
        config = KagamiConfig()
        data = config.to_dict()

        assert isinstance(data, dict)
        assert "world_model" in data
        assert "training" in data
        assert "safety" in data
        assert "profile_name" in data

    def test_deserialization_from_dict(self) -> None:
        """Test config deserialization from dictionary."""
        config = KagamiConfig()
        data = config.to_dict()

        # Round-trip should work
        config2 = KagamiConfig.from_dict(data)
        assert config2.world_model.bulk_dim == config.world_model.bulk_dim
        assert config2.training.batch_size == config.training.batch_size

    def test_save_and_load(self) -> None:
        """Test saving and loading configuration to/from file."""
        config = KagamiConfig()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_config.json"

            # Save
            config.save(path)
            assert path.exists()

            # Load
            config2 = KagamiConfig.load(path)
            assert config2.world_model.bulk_dim == config.world_model.bulk_dim
            assert config2.training.learning_rate == config.training.learning_rate


# =============================================================================
# FACTORY FUNCTION TESTS
# =============================================================================


class TestGetKagamiConfig:
    """Test get_kagami_config factory function."""

    def test_default_config(self) -> None:
        """Test getting default configuration."""
        config = get_kagami_config()
        assert config.profile_name == "base"
        assert config.world_model.bulk_dim >= 32

    def test_profile_presets(self) -> None:
        """Test named profile presets."""
        # Minimal
        config_min = get_kagami_config(profile="minimal")
        assert config_min.world_model.bulk_dim == 32
        assert config_min.training.batch_size == 8

        # Balanced
        config_bal = get_kagami_config(profile="balanced")
        assert config_bal.world_model.bulk_dim == 128
        assert config_bal.training.batch_size == 32

        # Large
        config_large = get_kagami_config(profile="large")
        assert config_large.world_model.bulk_dim == 512
        assert config_large.training.batch_size == 16

        # Maximal
        config_max = get_kagami_config(profile="maximal")
        assert config_max.world_model.bulk_dim == 2048
        assert config_max.training.batch_size == 4

    def test_bulk_dim_override(self) -> None:
        """Test bulk_dim override."""
        config = get_kagami_config(bulk_dim=1024)
        assert config.world_model.bulk_dim == 1024
        assert len(config.world_model.layer_dimensions) > 0
        assert config.world_model.layer_dimensions[0] == 1024

    def test_nested_overrides(self) -> None:
        """Test nested configuration overrides."""
        config = get_kagami_config(
            world_model={"bulk_dim": 512, "device": "cpu"},
            training={"batch_size": 64, "learning_rate": 5e-4},
            safety={"safety_threshold": 0.6},
        )

        assert config.world_model.bulk_dim == 512
        assert config.world_model.device == "cpu"
        assert config.training.batch_size == 64
        assert config.training.learning_rate == 5e-4
        assert config.safety.safety_threshold == 0.6

    def test_invalid_profile(self) -> None:
        """Test invalid profile raises error."""
        with pytest.raises(ValueError, match="Unknown profile"):
            get_kagami_config(profile="invalid")


# =============================================================================
# ENVIRONMENT VARIABLE TESTS
# =============================================================================


class TestEnvironmentOverrides:
    """Test environment variable overrides."""

    def test_bulk_dim_override(self, monkeypatch) -> None:
        """Test KAGAMI_BULK_DIM environment variable."""
        monkeypatch.setenv("KAGAMI_BULK_DIM", "1024")
        config = get_kagami_config()
        config = apply_env_overrides(config)
        assert config.world_model.bulk_dim == 1024

    def test_device_override(self, monkeypatch) -> None:
        """Test KAGAMI_DEVICE environment variable."""
        monkeypatch.setenv("KAGAMI_DEVICE", "cpu")
        config = get_kagami_config()
        config = apply_env_overrides(config)
        assert config.world_model.device == "cpu"
        assert config.training.device == "cpu"

    def test_batch_size_override(self, monkeypatch) -> None:
        """Test KAGAMI_BATCH_SIZE environment variable."""
        monkeypatch.setenv("KAGAMI_BATCH_SIZE", "128")
        config = get_kagami_config()
        config = apply_env_overrides(config)
        assert config.training.batch_size == 128

    def test_learning_rate_override(self, monkeypatch) -> None:
        """Test KAGAMI_LEARNING_RATE environment variable."""
        monkeypatch.setenv("KAGAMI_LEARNING_RATE", "5e-4")
        config = get_kagami_config()
        config = apply_env_overrides(config)
        assert config.training.learning_rate == 5e-4

    def test_cbf_threshold_override(self, monkeypatch) -> None:
        """Test KAGAMI_CBF_SAFETY_THRESHOLD environment variable."""
        monkeypatch.setenv("KAGAMI_CBF_SAFETY_THRESHOLD", "0.6")
        config = get_kagami_config()
        config = apply_env_overrides(config)
        assert config.safety.safety_threshold == 0.6

    def test_invalid_env_values_ignored(self, monkeypatch) -> None:
        """Test invalid environment values are ignored."""
        config = get_kagami_config()
        original_bulk_dim = config.world_model.bulk_dim

        # Set invalid value
        monkeypatch.setenv("KAGAMI_BULK_DIM", "not_a_number")
        config = apply_env_overrides(config)

        # Should keep original value
        assert config.world_model.bulk_dim == original_bulk_dim


# =============================================================================
# BACKWARD COMPATIBILITY TESTS
# =============================================================================


class TestBackwardCompatibility:
    """Test backward compatibility with old config imports."""

    @pytest.fixture(autouse=True)
    def clear_deprecated_module_cache(self):
        """Clear sys.modules cache for deprecated modules before each test.

        This ensures deprecation warnings are emitted even if the module
        was already imported by another test in the session.
        """
        import sys

        # List of deprecated modules to clear from cache
        deprecated_modules = [
            "kagami.core.world_model.model_config",
            "kagami.core.world_model.rssm_config",
            "kagami.core.training.training_config",
        ]

        # Clear before test
        for module in deprecated_modules:
            if module in sys.modules:
                del sys.modules[module]

        yield

        # Clear after test (for isolation)
        for module in deprecated_modules:
            if module in sys.modules:
                del sys.modules[module]

    def test_e2e_model_config_removed(self) -> None:
        """Test that e2e_model_config has been removed and replaced by unified_config."""
        # e2e_model_config.py has been deleted (Dec 16, 2025)
        # All functionality moved to unified_config.get_kagami_config()
        with pytest.raises(ModuleNotFoundError):
            from kagami.core.config.e2e_model_config import get_e2e_config


# Tests for deprecated configs removed (Dec 21, 2025)
# Rationale: These tests verify deprecated code marked for Q2 2026 deletion.
# The unified_config system is SSOT and has comprehensive tests above.

# =============================================================================
# CROSS-FIELD VALIDATION TESTS
# =============================================================================


class TestCrossFieldValidation:
    """Test cross-field validation logic."""

    def test_e8_bottleneck_temp_ordering(self) -> None:
        """Test E8 bottleneck temperature ordering."""
        # Valid: temp_end < temp_start
        E8BottleneckConfig(temp_start=1.0, temp_end=0.01)

        # Invalid: temp_end >= temp_start
        with pytest.raises(ValueError):
            E8BottleneckConfig(temp_start=0.5, temp_end=1.0)

    def test_rssm_std_ordering(self) -> None:
        """Test RSSM std ordering."""
        # Valid: max_std > min_std
        RSSMConfig(min_std=0.1, max_std=1.0)

        # Invalid: max_std <= min_std
        with pytest.raises(ValueError):
            RSSMConfig(min_std=1.0, max_std=0.5)

    def test_cbf_control_bounds_ordering(self) -> None:
        """Test CBF control bounds ordering."""
        # Valid: u_min < u_max
        SafetyConfig(u_min=[0.0, 0.0], u_max=[1.0, 1.0])

        # Invalid: u_min >= u_max
        with pytest.raises(ValueError):
            SafetyConfig(u_min=[0.5, 0.5], u_max=[0.3, 0.3])

    def test_adaptive_config_alpha_ordering(self) -> None:
        """Test adaptive config alpha ordering."""
        # Valid: alpha_max > alpha_min
        AdaptiveConfig(alpha_min=0.1, alpha_max=10.0)

        # Invalid: alpha_max <= alpha_min
        with pytest.raises(ValueError):
            AdaptiveConfig(alpha_min=10.0, alpha_max=0.1)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestConfigIntegration:
    """Integration tests for full config workflows."""

    def test_full_config_workflow(self) -> None:
        """Test complete config creation, modification, and usage."""
        # Create config with profile
        config = get_kagami_config(profile="large")

        # Override specific values
        config.world_model.device = "cpu"
        config.training.batch_size = 64
        config.safety.safety_threshold = 0.6

        # Validate dimensions are synchronized
        assert config.world_model.rssm.state_dim == config.world_model.bulk_dim

        # Save and load
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            config.save(path)
            config2 = KagamiConfig.load(path)

            assert config2.world_model.device == "cpu"
            assert config2.training.batch_size == 64
            assert config2.safety.safety_threshold == 0.6

    # test_config_migration_from_old deleted (Dec 21, 2025)
    # Rationale: No "old config" exists to migrate from. This simulated migration
    # that never existed. Unified config is the only config system.
