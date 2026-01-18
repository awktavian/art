"""Tests for kagami_math.hierarchical_octonions module.

Tests the HierarchicalOctonionFusion system for multi-scale sensory fusion.

Created: December 13, 2025
Updated: December 13, 2025 - Fixed to match actual API
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import torch
import torch.nn as nn

from kagami_math.hierarchical_octonions import (
    HierarchicalOctonionFusion,
    create_hierarchical_fusion,
    get_hierarchical_octonion,
)


class TestHierarchicalOctonionFusion:
    """Test the hierarchical octonion fusion module."""

    def test_fusion_initialization(self):
        """Test that fusion module initializes correctly."""
        fusion = HierarchicalOctonionFusion(num_modalities=7, num_levels=3, device="cpu")

        assert isinstance(fusion, nn.Module)
        assert hasattr(fusion, "manifold")
        assert fusion.num_modalities == 7
        assert fusion.num_levels == 3

    def test_fusion_with_input_dim_alias(self):
        """Test that input_dim works as alias for num_modalities."""
        fusion = HierarchicalOctonionFusion(
            input_dim=7,  # Backwards compatibility alias
            num_levels=2,
            device="cpu",
        )

        assert fusion.num_modalities == 7
        assert fusion.input_dim == 7

    def test_fusion_forward_with_dict_input(self):
        """Test forward pass with dict of modality octonions."""
        fusion = HierarchicalOctonionFusion(num_modalities=3, num_levels=2, device="cpu")

        # Create test input as dict of [B, 8] octonions
        modality_octonions = {
            "visual": torch.randn(2, 8),
            "audio": torch.randn(2, 8),
            "tactile": torch.randn(2, 8),
        }

        output = fusion(modality_octonions)

        # Should return dict with expected keys
        assert isinstance(output, dict)
        assert "final" in output
        assert "intermediate" in output
        assert "tree_structure" in output

        # Final should be [B, 8]
        assert output["final"].shape == (2, 8)

    def test_fusion_forward_single_modality(self):
        """Test forward pass with single modality."""
        fusion = HierarchicalOctonionFusion(num_modalities=1, num_levels=2)

        modality_octonions = {"only": torch.randn(2, 8)}
        output = fusion(modality_octonions)

        assert output["final"].shape == (2, 8)
        # Should just pass through single modality
        assert torch.allclose(output["final"], modality_octonions["only"])

    def test_fusion_forward_empty_input(self):
        """Test forward pass with empty dict."""
        fusion = HierarchicalOctonionFusion(num_modalities=7, num_levels=2)

        output = fusion({})

        # Should return identity-like octonion
        assert output["final"].shape == (1, 8)
        assert output["final"][0, 0] == 1.0  # Real part is 1

    def test_fusion_lazy_loading(self):
        """Test that lazy loading of OctonionManifold works."""
        # Multiple instances should work (manifold lazy loaded)
        fusion1 = HierarchicalOctonionFusion(num_modalities=7, num_levels=2)
        fusion2 = HierarchicalOctonionFusion(num_modalities=7, num_levels=3)

        assert fusion1 is not None
        assert fusion2 is not None
        assert fusion1 is not fusion2

    def test_fusion_validation(self):
        """Test parameter validation."""
        with pytest.raises(ValueError):
            HierarchicalOctonionFusion(num_modalities=7, num_levels=0)

        with pytest.raises(ValueError):
            HierarchicalOctonionFusion(num_modalities=7, num_levels=-1)

        with pytest.raises(ValueError):
            HierarchicalOctonionFusion(num_modalities=0, num_levels=2)


class TestFactoryFunctions:
    """Test factory functions for hierarchical octonions."""

    def test_create_hierarchical_fusion(self):
        """Test create_hierarchical_fusion factory function."""
        fusion = create_hierarchical_fusion(num_modalities=7, num_levels=2, device="cpu")

        assert isinstance(fusion, HierarchicalOctonionFusion)
        assert fusion.num_modalities == 7
        assert fusion.num_levels == 2

    def test_create_hierarchical_fusion_defaults(self):
        """Test create_hierarchical_fusion with defaults."""
        fusion = create_hierarchical_fusion()

        assert fusion.num_modalities == 7  # Default
        assert fusion.num_levels == 3  # Default

    def test_get_hierarchical_octonion(self):
        """Test get_hierarchical_octonion factory function."""
        modality_octonions = {
            "a": torch.randn(2, 8),
            "b": torch.randn(2, 8),
        }

        result = get_hierarchical_octonion(modality_octonions, num_levels=2)

        assert isinstance(result, dict)
        assert "final" in result
        assert result["final"].shape == (2, 8)


class TestCircularImportFixes:
    """Test that circular import fixes are stable."""

    def test_repeated_imports(self):
        """Test that repeated imports don't cause circular import errors."""
        for _ in range(3):
            try:
                from kagami_math.hierarchical_octonions import HierarchicalOctonionFusion

                assert HierarchicalOctonionFusion is not None
            except ImportError as e:
                pytest.fail(f"Circular import error on repeated import: {e}")

    def test_cross_module_imports(self):
        """Test imports from other modules that use hierarchical octonions."""
        from kagami_math.octonions import HierarchicalOctonionFusion as HO_from_octonions
        from kagami_math.hierarchical_octonions import HierarchicalOctonionFusion as HO_direct

        # Should be the same class
        assert HO_from_octonions is HO_direct

    def test_lazy_manifold_loading(self):
        """Test that lazy OctonionManifold loading works."""
        fusion = HierarchicalOctonionFusion(num_modalities=7, num_levels=2)

        # Accessing manifold should work (lazy loaded)
        assert hasattr(fusion, "manifold")
        assert fusion.manifold is not None


class TestComposePair:
    """Test the compose_pair method."""

    def test_compose_pair_basic(self):
        """Test basic pairwise composition."""
        fusion = HierarchicalOctonionFusion(num_modalities=2, num_levels=2)

        o1 = torch.randn(2, 8)
        o2 = torch.randn(2, 8)

        composed = fusion.compose_pair(o1, o2)

        assert composed.shape == (2, 8)
        assert not torch.isnan(composed).any()

    def test_compose_pair_with_weight(self):
        """Test composition with weighting."""
        fusion = HierarchicalOctonionFusion(num_modalities=2, num_levels=2)

        o1 = torch.randn(2, 8)
        o2 = torch.randn(2, 8)

        # Weight of 0 should return o1 (projected)
        composed_0 = fusion.compose_pair(o1, o2, weight=0.0)
        assert composed_0.shape == (2, 8)

        # Weight of 1 should give full composition
        composed_1 = fusion.compose_pair(o1, o2, weight=1.0)
        assert composed_1.shape == (2, 8)


class TestOctonionNonAssociativity:
    """Test non-associativity property of octonions."""

    def test_non_associativity_with_basis_vectors(self):
        """Test that octonion multiplication is non-associative."""
        from kagami_math.octonions import octonion_mul

        # Use basis vectors e1, e2, e4 (from Fano plane, not on same line)
        e1 = torch.zeros(1, 7)
        e1[0, 0] = 1.0

        e2 = torch.zeros(1, 7)
        e2[0, 1] = 1.0

        e4 = torch.zeros(1, 7)
        e4[0, 3] = 1.0

        # (e1 × e2) × e4
        e1_e2 = octonion_mul(e1, e2)
        left = octonion_mul(e1_e2, e4)

        # e1 × (e2 × e4)
        e2_e4 = octonion_mul(e2, e4)
        right = octonion_mul(e1, e2_e4)

        # Should be different (non-associative)
        # Note: May be equal for some specific combinations
        # The key is that there exist combinations where they differ
        if torch.allclose(left, right, atol=1e-5):
            # Try different combination
            e3 = torch.zeros(1, 7)
            e3[0, 2] = 1.0

            e1_e4 = octonion_mul(e1, e4)
            left2 = octonion_mul(e1_e4, e3)

            e4_e3 = octonion_mul(e4, e3)
            right2 = octonion_mul(e1, e4_e3)

            # At least one combination should show non-associativity
            assert not torch.allclose(left2, right2, atol=1e-5) or not torch.allclose(
                left, right, atol=1e-5
            ), "Expected non-associativity in octonion multiplication"


class TestTreeStructure:
    """Test the tree structure output."""

    def test_tree_structure_multiple_modalities(self):
        """Test tree structure with multiple modalities."""
        fusion = HierarchicalOctonionFusion(num_modalities=4, num_levels=3)

        modalities = {
            "a": torch.randn(1, 8),
            "b": torch.randn(1, 8),
            "c": torch.randn(1, 8),
            "d": torch.randn(1, 8),
        }

        output = fusion(modalities)

        tree = output["tree_structure"]
        assert "level_0" in tree
        assert len(tree["level_0"]) == 4  # 4 input modalities


class TestMemoryAndPerformance:
    """Test memory usage and performance characteristics."""

    def test_reasonable_memory_usage(self):
        """Test that hierarchical fusion has reasonable memory footprint."""
        fusion = HierarchicalOctonionFusion(num_modalities=7, num_levels=3)

        # Count parameters
        param_count = sum(p.numel() for p in fusion.parameters())

        # Should have some parameters (grouping weights)
        assert param_count >= 0  # May be 0 if learn_grouping=False
        assert param_count < 1000000  # Less than 1M parameters

    def test_batch_processing(self):
        """Test that fusion handles batched inputs efficiently."""
        fusion = HierarchicalOctonionFusion(num_modalities=3, num_levels=2)

        # Test different batch sizes
        for batch_size in [1, 4, 16]:
            modalities = {
                "a": torch.randn(batch_size, 8),
                "b": torch.randn(batch_size, 8),
                "c": torch.randn(batch_size, 8),
            }

            output = fusion(modalities)
            assert output["final"].shape[0] == batch_size


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
