"""Tests for Genesis-only data normalizers.

Legacy dataset normalizers (QM9 / TreeOfLife / multimodal) were removed when the
curriculum became Genesis-only.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import torch

from kagami.core.training.normalizers import (
    GenesisNormalizer,
    get_normalizer,
    NORMALIZERS,
)


class TestGenesisNormalizer:
    """Test Genesis physics normalizer."""

    def test_preserves_dynamics_fields(self) -> None:
        """Test that temporal structure is preserved."""
        normalizer = GenesisNormalizer()

        sample = {
            "state_t": torch.randn(64),
            "state_t_plus_1": torch.randn(64),
            "action_t": torch.randn(8),
        }

        result = normalizer.normalize(sample, "genesis")

        assert "state_t" in result
        assert "state_t_plus_1" in result
        assert "action_t" in result

    def test_preserves_metadata_fields(self) -> None:
        """Test that metadata fields are preserved."""
        normalizer = GenesisNormalizer()

        sample = {
            "state_t": torch.randn(64),
            "state_t_plus_1": torch.randn(64),
            "fingerprint": "sim_001",
            "metadata": {"scene_type": "rigid_body"},
        }

        result = normalizer.normalize(sample, "genesis")

        assert "fingerprint" in result
        assert "metadata" in result
        assert result["fingerprint"] == "sim_001"
        assert result["metadata"]["scene_type"] == "rigid_body"


class TestNormalizerRegistry:
    """Test normalizer registry and lookup."""

    def test_registry_contains_known_sources(self) -> None:
        """Test that registry has all known sources."""
        assert "jepa" in NORMALIZERS
        assert "generation" in NORMALIZERS

    def test_get_normalizer_returns_correct_type(self) -> None:
        """Test that get_normalizer returns correct normalizer type."""
        assert isinstance(get_normalizer("jepa"), GenesisNormalizer)
        assert isinstance(get_normalizer("generation"), GenesisNormalizer)

    def test_get_normalizer_fallback_to_default(self) -> None:
        """Unknown sources should error loudly (no fallback normalizer)."""
        with pytest.raises(KeyError):
            _ = get_normalizer("unknown_source_xyz")

    def test_all_normalizers_have_normalize_method(self) -> None:
        """Test that all normalizers implement normalize method."""
        for _source, normalizer in NORMALIZERS.items():
            assert hasattr(normalizer, "normalize")
            assert callable(normalizer.normalize)


class TestIntegration:
    """Integration tests for normalizers with CurriculumDataset."""

    def test_normalize_preserves_source_metadata(self) -> None:
        """Test that normalization adds source metadata correctly."""
        # This would be done by CurriculumDataset._normalize_sample
        normalizer = get_normalizer("jepa")
        sample = {"state_t": torch.randn(8, 32)}
        result = normalizer.normalize(sample, "jepa")

        # Source metadata is added by _normalize_sample, not the normalizer
        # Just verify the normalizer doesn't interfere
        assert "state_t" in result

    def test_all_data_types_can_be_normalized(self) -> None:
        """Test that all major data types can be normalized."""
        test_samples = {
            "jepa": {"state_t": torch.randn(64), "state_t_plus_1": torch.randn(64)},
            "generation": {"state_t": torch.randn(64), "state_t_plus_1": torch.randn(64)},
        }

        for source, sample in test_samples.items():
            normalizer = get_normalizer(source)
            result = normalizer.normalize(sample, source)
            assert isinstance(result, dict)
            assert len(result) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
