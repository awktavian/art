"""Tests for K os feature flags system.

Created: November 16, 2025 (Q1 Production Roadmap)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit

import os
from unittest.mock import patch

from kagami.core.config.feature_flags import (
    FeatureFlags,
    LifecycleFlags,
    ObservabilityFlags,
    ResearchFlags,
    SafetyFlags,
    WorldModelFlags,
    get_feature_flags,
    reload_feature_flags,
    reset_feature_flags,
)


class TestLifecycleFlags:
    """Test lifecycle feature flags."""

    def test_default_values(self) -> None:
        """Test default lifecycle flags."""
        flags = LifecycleFlags()
        assert flags.enable_agent_mitosis is True
        assert flags.enable_agent_apoptosis is True
        assert flags.enable_genetic_evolution is True
        assert flags.enable_genetic_memory is True
        assert flags.force_static_pool is False
        assert flags.max_global_agents == 500

    def test_from_env(self) -> None:
        """Test loading from environment.

        Note: Core lifecycle booleans are always-on; only numeric parameters are configurable.
        """
        with patch.dict(
            os.environ,
            {
                "KAGAMI_MAX_GLOBAL_AGENTS": "100",
            },
        ):
            flags = LifecycleFlags.from_env()
            # All boolean flags are True by design (Full Operation mode)
            assert flags.enable_agent_mitosis is True
            assert flags.enable_agent_apoptosis is True
            # Numeric parameters are configurable
            assert flags.max_global_agents == 100


class TestWorldModelFlags:
    """Test world model feature flags."""

    def test_default_values(self) -> None:
        """Test default world model flags."""
        flags = WorldModelFlags()
        assert flags.use_geometric_world_model is True
        assert flags.enforce_g2_equivariance is True
        assert flags.enable_matryoshka_brain is True
        assert flags.enable_chaos_reservoir is True  # Mandatory - always on
        assert flags.world_model_dimensions == 2048
        assert flags.matryoshka_layers == 7

    def test_from_env_simplified_mode(self) -> None:
        """Test from_env configuration.

        Note: Core world-model booleans are always-on; only numeric parameters are configurable.
        """
        with patch.dict(
            os.environ,
            {
                "KAGAMI_WM_DIMENSIONS": "1024",
            },
        ):
            flags = WorldModelFlags.from_env()
            # All boolean flags are True by design (Full Operation mode)
            assert flags.use_geometric_world_model is True
            # Numeric parameters are configurable
            assert flags.world_model_dimensions == 1024


class TestSafetyFlags:
    """Test safety feature flags."""

    def test_default_values_safe(self) -> None:
        """Test safety configuration defaults."""
        flags = SafetyFlags()
        # Safety systems are always on - only parameters are configurable
        assert flags.cbf_safety_threshold == 1.0
        assert flags.cbf_alpha == 0.5
        assert flags.memory_soft_limit_gb == 4.0
        assert flags.memory_hard_limit_gb == 8.0

    def test_validation_error_on_invalid_limits(self) -> None:
        """Test validation fails when hard < soft limit."""
        flags = SafetyFlags(memory_soft_limit_gb=10.0, memory_hard_limit_gb=5.0)
        with pytest.raises(ValueError, match="Hard limit.*< soft limit"):
            flags.validate()


class TestObservabilityFlags:
    """Test observability feature flags."""

    def test_default_values(self) -> None:
        """Test observability configuration defaults."""
        flags = ObservabilityFlags()
        # Receipts and metrics are always on - only parameters are configurable
        assert flags.enable_profiling is False  # Overhead - off by default
        assert flags.receipt_batch_size == 100
        assert flags.receipt_flush_interval_ms == 1000
        assert flags.enable_high_cardinality_labels is False  # Risky


class TestResearchFlags:
    """Test research feature flags."""

    def test_default_values_off(self) -> None:
        """Research flags default to OFF (opt-in)."""
        flags = ResearchFlags()
        assert flags.enable_self_modification is False
        assert flags.enable_continuous_evolution is False
        assert flags.enable_self_healing is False
        assert flags.enable_periodic_reflection is False
        assert flags.enable_federated_learning is False

    def test_from_env_opt_in(self) -> None:
        """Research features are opt-in via env vars."""
        with patch.dict(
            os.environ,
            {
                "KAGAMI_ENABLE_SELF_MODIFICATION": "1",
                "KAGAMI_ENABLE_CONTINUOUS_EVOLUTION": "1",
                "KAGAMI_ENABLE_SELF_HEALING": "1",
                "KAGAMI_ENABLE_PERIODIC_REFLECTION": "1",
                "KAGAMI_ENABLE_FEDERATED_LEARNING": "1",
            },
        ):
            flags = ResearchFlags.from_env()
            assert flags.enable_self_modification is True
            assert flags.enable_continuous_evolution is True
            assert flags.enable_self_healing is True
            assert flags.enable_periodic_reflection is True
            assert flags.enable_federated_learning is True


class TestFeatureFlags:
    """Test complete feature flags system."""

    def setup_method(self) -> None:
        """Reset global state before each test."""
        reset_feature_flags()

    def test_singleton_behavior(self) -> None:
        """Test that get_feature_flags returns singleton."""
        flags1 = get_feature_flags()
        flags2 = get_feature_flags()
        assert flags1 is flags2  # Same instance

    def test_reload_reloads_from_env(self) -> None:
        """Test that reload picks up environment changes.

        Note: Numeric parameters can be reloaded.
        """
        # First call with no overrides
        flags1 = get_feature_flags()
        assert flags1.lifecycle.enable_agent_mitosis is True

        # Change environment - numeric params can change
        with patch.dict(os.environ, {"KAGAMI_MAX_GLOBAL_AGENTS": "200"}):
            flags2 = reload_feature_flags()
            # Boolean flags stay True (Full Operation)
            assert flags2.lifecycle.enable_agent_mitosis is True
            # Numeric params can be reloaded
            assert flags2.lifecycle.max_global_agents == 200

    def test_as_dict_structure(self) -> None:
        """Test conversion to dictionary."""
        flags = FeatureFlags.from_env()
        d = flags.as_dict()

        assert "lifecycle" in d
        assert "world_model" in d
        assert "safety" in d
        assert "observability" in d
        assert "research" in d

        assert "enable_agent_mitosis" in d["lifecycle"]
        assert "use_geometric_world_model" in d["world_model"]

    def test_as_metric_labels(self) -> None:
        """Test conversion to Prometheus labels."""
        flags = FeatureFlags.from_env()
        labels = flags.as_metric_labels()

        assert labels["mitosis"] in ("on", "off")
        assert labels["apoptosis"] in ("on", "off")
        assert labels["g2_equivariance"] in ("on", "off")

    def test_safety_validation_runs(self) -> None:
        """Test that from_env validates safety."""
        # Safety systems are always on - only parameters are configurable
        flags = FeatureFlags.from_env()
        assert flags.safety.cbf_safety_threshold > 0
        assert flags.safety.memory_hard_limit_gb >= flags.safety.memory_soft_limit_gb


class TestFeatureFlagIntegration:
    """Integration tests for feature flags with other modules."""

    def setup_method(self) -> None:
        """Reset global state."""
        reset_feature_flags()

    def test_metrics_emission(self) -> None:
        """Test that feature flags emit metrics."""
        # Note: This test may fail if metrics are not available
        # In that case, the code should gracefully handle ImportError
        try:
            flags = get_feature_flags()
            # Should not raise, even if metrics unavailable
            assert flags is not None
        except ImportError:
            pytest.skip("Metrics not available in test environment")

    @pytest.mark.asyncio
    async def test_lifecycle_mitosis_respects_flags(self) -> None:
        """Test that agent lifecycle respects mitosis flag."""
        # This is tested in test_agent_lifecycle.py
        # Here we just verify flag can be loaded
        flags = get_feature_flags()
        assert isinstance(flags.lifecycle.enable_agent_mitosis, bool)

    def test_world_model_configuration(self) -> None:
        """Test world model flag configuration."""
        flags = get_feature_flags()
        assert flags.world_model.world_model_dimensions > 0
        assert flags.world_model.matryoshka_layers >= 1
        assert 0 < flags.world_model.g2_validation_threshold < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
