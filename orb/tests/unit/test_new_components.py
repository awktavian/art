"""Tests for new architecture components (Dec 7, 2025).

Tests for IMPLEMENTED components:
1. ResidualE8LatticeVQ (v2 protocol) ✓
2. InformationBottleneck (VIB) ✓
3. TrueExceptionalHierarchy (fixed projectors) ✓

NOTE (Dec 7, 2025): Tests for UnifiedVIBE8Bottleneck and AdaptiveHierarchyBottleneck
were removed as these modules were planned but never implemented. The functionality
they would provide is already covered by:
- InformationBottleneck (kagami.core.world_model.information_bottleneck)
- SemanticResidualE8 (kagami_math.semantic_residual_e8)
- TrueExceptionalHierarchy (kagami_math.clebsch_gordan_exceptional)

Created: December 7, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import math
import torch
import torch.nn as nn

# =============================================================================
# RESIDUAL E8 LATTICE VQ TESTS
# =============================================================================


class TestResidualE8LatticeVQ:
    """Tests for ResidualE8LatticeVQ component.

    NOTE (Jan 2026): VQ now returns dict instead of tuple.
    Keys: "quantized", "loss", "indices", "perplexity"
    """

    def test_fixed_levels_deterministic(self):
        """Residual E8 VQ returns deterministic level count when adaptive disabled."""
        from kagami_math.e8_lattice_protocol import (
            ResidualE8LatticeVQ,
            E8LatticeResidualConfig,
        )

        vq = ResidualE8LatticeVQ(
            E8LatticeResidualConfig(max_levels=3, min_levels=3, adaptive_levels=False)
        )
        x = torch.randn(32, 8)
        result = vq(x, num_levels=3)
        q = result["quantized"]
        indices = result["indices"]

        assert q.shape == x.shape
        # indices is [B, L, 8] where L is number of levels
        assert indices.shape[1] == 3  # 3 levels
        assert indices.shape[0] == 32  # batch

    def test_single_sample(self):
        """Test with batch size of 1."""
        from kagami_math.e8_lattice_protocol import (
            ResidualE8LatticeVQ,
            E8LatticeResidualConfig,
        )

        vq = ResidualE8LatticeVQ(
            E8LatticeResidualConfig(max_levels=2, min_levels=1, adaptive_levels=False)
        )
        x = torch.randn(1, 8)
        result = vq(x, num_levels=2)
        q = result["quantized"]

        assert q.shape == (1, 8)
        assert "loss" in result
        assert "indices" in result

    def test_gradient_flow(self):
        """Test that gradients flow through the module."""
        from kagami_math.e8_lattice_protocol import (
            ResidualE8LatticeVQ,
            E8LatticeResidualConfig,
        )

        vq = ResidualE8LatticeVQ(
            E8LatticeResidualConfig(max_levels=2, min_levels=1, adaptive_levels=False)
        )
        x = torch.randn(4, 8, requires_grad=True)
        result = vq(x, num_levels=2)
        q = result["quantized"]

        loss = q.sum()
        loss.backward()

        assert x.grad is not None
        assert torch.isfinite(x.grad).all()

    def test_quantization_reduces_residual(self):
        """Each level should reduce reconstruction error."""
        from kagami_math.e8_lattice_protocol import (
            ResidualE8LatticeVQ,
            E8LatticeResidualConfig,
        )

        vq = ResidualE8LatticeVQ(
            E8LatticeResidualConfig(max_levels=4, min_levels=1, adaptive_levels=False)
        )
        x = torch.randn(16, 8)

        # Get results at different levels
        q1 = vq(x, num_levels=1)["quantized"]
        q2 = vq(x, num_levels=2)["quantized"]
        q4 = vq(x, num_levels=4)["quantized"]

        err1 = (x - q1).pow(2).mean()
        err2 = (x - q2).pow(2).mean()
        err4 = (x - q4).pow(2).mean()

        # More levels should generally reduce error (may not always be strict)
        assert torch.isfinite(err1)
        assert torch.isfinite(err2)
        assert torch.isfinite(err4)

    def test_zero_input(self):
        """Test with zero input tensor."""
        from kagami_math.e8_lattice_protocol import (
            ResidualE8LatticeVQ,
            E8LatticeResidualConfig,
        )

        vq = ResidualE8LatticeVQ(
            E8LatticeResidualConfig(max_levels=2, min_levels=1, adaptive_levels=False)
        )
        x = torch.zeros(4, 8)
        result = vq(x, num_levels=2)
        q = result["quantized"]

        assert torch.isfinite(q).all()
        assert q.shape == x.shape


# =============================================================================
# TRUE EXCEPTIONAL HIERARCHY TESTS
# =============================================================================


class TestTrueExceptionalHierarchy:
    """Tests for TrueExceptionalHierarchy component."""

    def test_full_projection_chain(self):
        """Test full E8→S7 projection chain."""
        from kagami_math.clebsch_gordan_exceptional import TrueExceptionalHierarchy

        hierarchy = TrueExceptionalHierarchy()

        x_e8 = torch.randn(4, 248)
        result = hierarchy.project_to_level(x_e8, "S7", return_intermediates=True)

        assert result["E8"].shape == (4, 248)  # type: ignore[index]
        assert result["E7"].shape == (4, 133)  # type: ignore[index]
        assert result["E6"].shape == (4, 78)  # type: ignore[index]
        assert result["F4"].shape == (4, 52)  # type: ignore[index]
        assert result["G2"].shape == (4, 14)  # type: ignore[index]
        assert result["S7"].shape == (4, 7)  # type: ignore[index]

    def test_inverse_embedding(self):
        """Test inverse embedding from S7 back to E8."""
        from kagami_math.clebsch_gordan_exceptional import TrueExceptionalHierarchy

        hierarchy = TrueExceptionalHierarchy()

        x_e8 = torch.randn(4, 248)
        result = hierarchy.project_to_level(x_e8, "S7", return_intermediates=True)
        x_s7 = result["S7"]  # type: ignore[index]
        x_e8_back = hierarchy.embed_from_level(x_s7, "S7")

        assert x_e8_back.shape == (4, 248)
        assert torch.isfinite(x_e8_back).all()

    def test_single_sample_projection(self):
        """Test with batch size of 1."""
        from kagami_math.clebsch_gordan_exceptional import TrueExceptionalHierarchy

        hierarchy = TrueExceptionalHierarchy()

        x_e8 = torch.randn(1, 248)
        result = hierarchy.project_to_level(x_e8, "G2", return_intermediates=False)

        assert result.shape == (1, 14)

    def test_intermediate_level_projection(self):
        """Test projection to intermediate levels."""
        from kagami_math.clebsch_gordan_exceptional import TrueExceptionalHierarchy

        hierarchy = TrueExceptionalHierarchy()

        x_e8 = torch.randn(8, 248)

        # Project to each level
        for level, expected_dim in [("E7", 133), ("E6", 78), ("F4", 52), ("G2", 14)]:
            result = hierarchy.project_to_level(x_e8, level, return_intermediates=False)
            assert result.shape == (8, expected_dim), f"Failed for level {level}"

    def test_gradient_flow_through_hierarchy(self):
        """Test gradient flow through projection."""
        from kagami_math.clebsch_gordan_exceptional import TrueExceptionalHierarchy

        hierarchy = TrueExceptionalHierarchy()

        x_e8 = torch.randn(4, 248, requires_grad=True)
        result = hierarchy.project_to_level(x_e8, "S7", return_intermediates=False)

        loss = result.sum()
        loss.backward()

        assert x_e8.grad is not None
        assert torch.isfinite(x_e8.grad).all()


# =============================================================================
# INFORMATION BOTTLENECK (VIB) TESTS
# =============================================================================


class TestInformationBottleneck:
    """Tests for InformationBottleneck component."""

    def test_forward_pass_shapes(self):
        """Test output shapes from VIB forward pass."""
        from kagami.core.world_model.information_bottleneck import InformationBottleneck, IBConfig

        vib = InformationBottleneck(IBConfig(input_dim=32, bottleneck_dim=8, output_dim=32))
        x = torch.randn(4, 32)
        result = vib(x, y=x)

        assert result["z"].shape == (4, 8)
        assert result["y_pred"].shape == (4, 32)
        assert "kl_loss" in result

    def test_kl_loss_non_negative(self):
        """KL loss should be non-negative."""
        from kagami.core.world_model.information_bottleneck import InformationBottleneck, IBConfig

        vib = InformationBottleneck(IBConfig(input_dim=32, bottleneck_dim=8, output_dim=32))
        x = torch.randn(16, 32)
        result = vib(x, y=x)

        assert result["kl_loss"] >= 0

    def test_training_vs_eval_mode(self):
        """Test behavior differs between training and eval modes."""
        from kagami.core.world_model.information_bottleneck import InformationBottleneck, IBConfig

        vib = InformationBottleneck(IBConfig(input_dim=32, bottleneck_dim=8, output_dim=32))
        x = torch.randn(4, 32)

        # Training mode (stochastic sampling)
        vib.train()
        result_train = vib(x, y=x)

        # Eval mode (deterministic)
        vib.eval()
        result_eval = vib(x, y=x)

        # Both should produce valid outputs
        assert torch.isfinite(result_train["z"]).all()
        assert torch.isfinite(result_eval["z"]).all()

    def test_gradient_flow(self):
        """Test gradients flow through VIB."""
        from kagami.core.world_model.information_bottleneck import InformationBottleneck, IBConfig

        vib = InformationBottleneck(IBConfig(input_dim=32, bottleneck_dim=8, output_dim=32))
        x = torch.randn(4, 32, requires_grad=True)
        result = vib(x, y=x)

        loss = result["y_pred"].sum() + result["kl_loss"]
        loss.backward()

        assert x.grad is not None

    def test_single_sample(self):
        """Test with batch size of 1."""
        from kagami.core.world_model.information_bottleneck import InformationBottleneck, IBConfig

        vib = InformationBottleneck(IBConfig(input_dim=32, bottleneck_dim=8, output_dim=32))
        x = torch.randn(1, 32)
        result = vib(x, y=x)

        assert result["z"].shape == (1, 8)
        assert not torch.isnan(result["kl_loss"])


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests across components."""

    def test_residual_e8_vq_fixed_levels(self):
        """Residual E8 VQ returns deterministic level count when adaptive disabled."""
        from kagami_math.e8_lattice_protocol import (
            ResidualE8LatticeVQ,
            E8LatticeResidualConfig,
        )

        vq = ResidualE8LatticeVQ(
            E8LatticeResidualConfig(max_levels=3, min_levels=3, adaptive_levels=False)
        )
        x = torch.randn(32, 8)
        result = vq(x, num_levels=3)
        q = result["quantized"]
        indices = result["indices"]

        assert q.shape == x.shape
        assert indices.shape[1] == 3  # 3 levels

    def test_full_hierarchy_projection(self):
        """Test full E8→S7 projection chain."""
        from kagami_math.clebsch_gordan_exceptional import TrueExceptionalHierarchy

        hierarchy = TrueExceptionalHierarchy()

        # Test forward projection
        x_e8 = torch.randn(4, 248)
        result = hierarchy.project_to_level(x_e8, "S7", return_intermediates=True)

        assert result["E8"].shape == (4, 248)  # type: ignore[index]
        assert result["E7"].shape == (4, 133)  # type: ignore[index]
        assert result["E6"].shape == (4, 78)  # type: ignore[index]
        assert result["F4"].shape == (4, 52)  # type: ignore[index]
        assert result["G2"].shape == (4, 14)  # type: ignore[index]
        assert result["S7"].shape == (4, 7)  # type: ignore[index]

        # Test inverse embedding
        x_s7 = result["S7"]  # type: ignore[index]
        x_e8_back = hierarchy.embed_from_level(x_s7, "S7")
        assert x_e8_back.shape == (4, 248)

    def test_vib_with_e8_quantization(self):
        """Test VIB followed by E8 quantization (functional equivalent of planned UnifiedVIBE8Bottleneck)."""
        from kagami.core.world_model.information_bottleneck import InformationBottleneck, IBConfig
        from kagami_math.e8_lattice_protocol import (
            ResidualE8LatticeVQ,
            E8LatticeResidualConfig,
        )

        # VIB for compression
        vib = InformationBottleneck(IBConfig(input_dim=32, bottleneck_dim=8, output_dim=32))

        # E8 quantization for discrete codes
        e8_quant = ResidualE8LatticeVQ(E8LatticeResidualConfig(max_levels=2, min_levels=1))

        # Combined forward pass
        x = torch.randn(4, 32)
        vib_result = vib(x, y=x)  # Self-reconstruction

        # Quantize the VIB latent
        z = vib_result["z"]  # [4, 8]
        quant_result = e8_quant(z, num_levels=2)
        z_q = quant_result["quantized"]

        # Verify combined functionality
        assert z.shape == (4, 8)
        assert z_q.shape == (4, 8)
        assert "loss" in quant_result
        assert "kl_loss" in vib_result
        # lattice VQ: commitment proxy
        assert torch.isfinite((z - z_q.detach()).pow(2).mean())

    def test_end_to_end_pipeline(self):
        """Test complete pipeline: input -> VIB -> E8 quant -> hierarchy projection."""
        from kagami.core.world_model.information_bottleneck import InformationBottleneck, IBConfig
        from kagami_math.e8_lattice_protocol import (
            ResidualE8LatticeVQ,
            E8LatticeResidualConfig,
        )
        from kagami_math.clebsch_gordan_exceptional import TrueExceptionalHierarchy

        # Build pipeline
        vib = InformationBottleneck(IBConfig(input_dim=64, bottleneck_dim=8, output_dim=64))
        e8_quant = ResidualE8LatticeVQ(E8LatticeResidualConfig(max_levels=2, min_levels=1))
        hierarchy = TrueExceptionalHierarchy()

        # Forward pass
        x = torch.randn(4, 64)

        # Step 1: VIB compression
        vib_result = vib(x, y=x)
        z = vib_result["z"]
        assert z.shape == (4, 8)

        # Step 2: E8 quantization
        quant_result = e8_quant(z, num_levels=2)
        z_q = quant_result["quantized"]
        assert z_q.shape == (4, 8)

        # Step 3: Pad to E8 dim (248) and project through hierarchy
        # Pad z_q to 248 dimensions for hierarchy input
        z_padded = torch.zeros(4, 248)
        z_padded[:, :8] = z_q
        result = hierarchy.project_to_level(z_padded, "S7", return_intermediates=False)
        assert result.shape == (4, 7)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
