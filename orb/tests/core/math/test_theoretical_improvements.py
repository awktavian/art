"""Tests for Theoretical Improvements to Exceptional Lie Algebra Hierarchy.

Tests the five key theoretical improvements:
1. Freudenthal Triple System (E₇) for 3-way colony interactions
2. Jordan Algebra Belief Propagation (F₄) for coherent updates
3. G₂ Holonomy Decomposition for associative/coassociative split
4. Weyl Equivariant Convolution for root system symmetry
5. True Octonion Operations for native algebra

Created: December 6, 2025
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import torch
import math

from kagami_math.theoretical_improvements import (
    # Freudenthal Triple System
    FreudenthalTripleSystem,
    FreudenthalTripleLayer,
    # Jordan Algebra
    JordanAlgebra,
    JordanBeliefPropagation,
    # G₂ Holonomy
    G2HolonomyDecomposition,
    # Weyl Equivariance
    WeylEquivariantConv,
    # Octonion Operations
    OctonionLinear,
    OctonionMLP,
    # Unified
    TheoreticalExceptionalHierarchy,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def device() -> Any:
    """Get test device."""
    if torch.backends.mps.is_available():
        return torch.device("mps")
    elif torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


@pytest.fixture
def colony_octonions(device: Any) -> Any:
    """Sample colony octonion states."""
    B = 4
    octonions = torch.randn(B, 7, 8, device=device)
    # Normalize to unit octonions
    norms = octonions.norm(dim=-1, keepdim=True).clamp(min=1e-8)
    return octonions / norms


# =============================================================================
# 1. FREUDENTHAL TRIPLE SYSTEM TESTS
# =============================================================================


class TestFreudenthalTripleSystem:
    """Tests for Freudenthal Triple System."""

    def test_init(self: Any, device: Any) -> None:
        """Test FTS initialization."""
        fts = FreudenthalTripleSystem(dim=56).to(device)
        assert fts.dim == 56
        assert fts.trace_form.shape == (56, 56)
        assert fts.symplectic_form.shape == (56, 56)

    def test_trace_form_symmetric(self: Any, device: Any) -> None:
        """Test that trace form is symmetric."""
        fts = FreudenthalTripleSystem(dim=56).to(device)
        fts._make_symmetric()
        diff = fts.trace_form - fts.trace_form.T
        assert diff.abs().max() < 1e-6

    def test_symplectic_antisymmetric(self: Any, device: Any) -> None:
        """Test that symplectic form is antisymmetric."""
        fts = FreudenthalTripleSystem(dim=56).to(device)
        diff = fts.symplectic_form + fts.symplectic_form.T
        assert diff.abs().max() < 1e-6

    def test_triple_product_shape(self: Any, device: Any) -> None:
        """Test triple product output shape."""
        fts = FreudenthalTripleSystem(dim=56).to(device)
        x = torch.randn(4, 56, device=device)
        y = torch.randn(4, 56, device=device)
        z = torch.randn(4, 56, device=device)

        result = fts.triple_product(x, y, z)
        assert result.shape == (4, 56)

    def test_gradient_flow(self: Any, device: Any) -> None:
        """Test gradient flow through FTS."""
        fts = FreudenthalTripleSystem(dim=56).to(device)
        x = torch.randn(4, 56, device=device, requires_grad=True)
        y = torch.randn(4, 56, device=device)
        z = torch.randn(4, 56, device=device)

        result = fts.triple_product(x, y, z)
        loss = result.sum()
        loss.backward()

        assert x.grad is not None
        assert not torch.isnan(x.grad).any()


class TestFreudenthalTripleLayer:
    """Tests for FTS layer with colony coordination."""

    def test_init(self: Any, device: Any) -> None:
        """Test FTS layer initialization."""
        layer = FreudenthalTripleLayer(
            colony_dim=8,
            hidden_dim=56,
            num_colonies=7,
        ).to(device)
        assert layer.num_triads == 35  # C(7, 3)

    def test_forward_shape(self: Any, colony_octonions: Any) -> None:
        """Test forward pass shape."""
        device = colony_octonions.device
        layer = FreudenthalTripleLayer(
            colony_dim=8,
            hidden_dim=56,
            num_colonies=7,
        ).to(device)

        output = layer(colony_octonions)
        assert output.shape == colony_octonions.shape

    def test_output_normalized(self: Any, colony_octonions: Any) -> None:
        """Test that output is normalized to unit octonions."""
        device = colony_octonions.device
        layer = FreudenthalTripleLayer(
            colony_dim=8,
            hidden_dim=56,
            num_colonies=7,
        ).to(device)

        output = layer(colony_octonions)
        norms = output.norm(dim=-1)
        assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)


# =============================================================================
# 2. JORDAN ALGEBRA TESTS
# =============================================================================


class TestJordanAlgebra:
    """Tests for Jordan Algebra."""

    def test_init(self: Any, device: Any) -> None:
        """Test Jordan algebra initialization."""
        ja = JordanAlgebra(dim=27).to(device)
        assert ja.dim == 27
        assert ja.idempotents.shape == (3, 27)

    def test_jordan_product_commutative(self: Any, device: Any) -> None:
        """Test that Jordan product is commutative: x ∘ y = y ∘ x."""
        ja = JordanAlgebra(dim=27).to(device)
        x = torch.randn(4, 27, device=device)
        y = torch.randn(4, 27, device=device)

        xy = ja.jordan_product(x, y)
        yx = ja.jordan_product(y, x)

        assert torch.allclose(xy, yx, atol=1e-5)

    def test_trace_scalar_output(self: Any, device: Any) -> None:
        """Test that trace produces scalar."""
        ja = JordanAlgebra(dim=27).to(device)
        x = torch.randn(4, 27, device=device)

        trace = ja.trace(x)
        assert trace.shape == (4,)


class TestJordanBeliefPropagation:
    """Tests for Jordan Belief Propagation."""

    def test_init(self: Any, device: Any) -> None:
        """Test JBP initialization."""
        jbp = JordanBeliefPropagation(
            state_dim=27,
            num_agents=7,
            num_iterations=3,
        ).to(device)
        assert jbp.num_agents == 7
        assert jbp.num_iterations == 3

    def test_forward_shape(self: Any, device: Any) -> None:
        """Test forward pass shape."""
        jbp = JordanBeliefPropagation(
            state_dim=27,
            num_agents=7,
            num_iterations=3,
        ).to(device)

        beliefs = torch.randn(4, 7, 27, device=device)
        output = jbp(beliefs)

        assert output.shape == (4, 7, 27)

    def test_trajectory_output(self: Any, device: Any) -> None:
        """Test trajectory output."""
        jbp = JordanBeliefPropagation(
            state_dim=27,
            num_agents=7,
            num_iterations=3,
        ).to(device)

        beliefs = torch.randn(4, 7, 27, device=device)
        output = jbp(beliefs, return_trajectory=True)

        assert "beliefs" in output
        assert "trajectory" in output
        assert len(output["trajectory"]) == 4  # initial + 3 iterations


# =============================================================================
# 3. G₂ HOLONOMY TESTS
# =============================================================================


class TestG2HolonomyDecomposition:
    """Tests for G₂ Holonomy Decomposition."""

    def test_init(self: Any, device: Any) -> None:
        """Test G₂ holonomy initialization."""
        g2h = G2HolonomyDecomposition(dim=7).to(device)
        assert g2h.dim == 7

    def test_forward_shape(self: Any, device: Any) -> None:
        """Test forward pass shape."""
        g2h = G2HolonomyDecomposition(dim=7).to(device)
        x = torch.randn(4, 7, device=device)

        output, assoc, coassoc = g2h(x)

        assert output.shape == (4, 7)
        assert assoc.shape == (4, 7)
        assert coassoc.shape == (4, 7)

    def test_output_normalized(self: Any, device: Any) -> None:
        """Test that output is normalized."""
        g2h = G2HolonomyDecomposition(dim=7).to(device)
        x = torch.randn(4, 7, device=device)

        output, _, _ = g2h(x)
        norms = output.norm(dim=-1)

        assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)

    def test_phi_inner_skew_symmetric(self: Any, device: Any) -> None:
        """Test that φ(x, y, z) = -φ(y, x, z)."""
        g2h = G2HolonomyDecomposition(dim=7).to(device)
        x = torch.randn(4, 7, device=device)
        y = torch.randn(4, 7, device=device)
        z = torch.randn(4, 7, device=device)

        phi_xyz = g2h.compute_phi_inner(x, y, z)
        phi_yxz = g2h.compute_phi_inner(y, x, z)

        assert torch.allclose(phi_xyz, -phi_yxz, atol=1e-5)


# =============================================================================
# 4. WEYL EQUIVARIANT TESTS
# =============================================================================


class TestWeylEquivariantConv:
    """Tests for Weyl Equivariant Convolution."""

    def test_init_e8(self: Any, device: Any) -> None:
        """Test E₈ Weyl conv initialization."""
        weyl = WeylEquivariantConv(
            in_features=8,
            out_features=8,
            root_system="E8",
        ).to(device)
        assert weyl.num_roots == 240
        assert weyl.root_weights.shape == (240, 8)

    def test_init_g2(self: Any, device: Any) -> None:
        """Test G₂ Weyl conv initialization."""
        weyl = WeylEquivariantConv(
            in_features=3,
            out_features=3,
            root_system="G2",
        ).to(device)
        assert weyl.num_roots == 12

    def test_forward_shape(self: Any, device: Any) -> None:
        """Test forward pass shape."""
        weyl = WeylEquivariantConv(
            in_features=8,
            out_features=8,
            root_system="E8",
        ).to(device)

        x = torch.randn(4, 8, device=device)
        output = weyl(x)

        assert output.shape == (4, 8)

    def test_weyl_reflection(self: Any, device: Any) -> None:
        """Test Weyl reflection is involution: s_α(s_α(x)) = x."""
        weyl = WeylEquivariantConv(
            in_features=8,
            out_features=8,
            root_system="E8",
        ).to(device)

        x = torch.randn(8, device=device)
        alpha = weyl.simple_roots[0].to(device)

        # Double reflection should be identity
        sx = weyl.weyl_reflection(x.unsqueeze(0), alpha)
        ssx = weyl.weyl_reflection(sx, alpha)

        assert torch.allclose(ssx.squeeze(0), x, atol=1e-5)


# =============================================================================
# 5. OCTONION OPERATIONS TESTS
# =============================================================================


class TestOctonionLinear:
    """Tests for Octonion Linear layer."""

    def test_init(self: Any, device: Any) -> None:
        """Test octonion linear initialization."""
        layer = OctonionLinear(
            in_features=16,
            out_features=24,
        ).to(device)
        assert layer.in_octonions == 2
        assert layer.out_octonions == 3

    def test_forward_shape(self: Any, device: Any) -> None:
        """Test forward pass shape."""
        layer = OctonionLinear(
            in_features=16,
            out_features=24,
        ).to(device)

        x = torch.randn(4, 16, device=device)
        output = layer(x)

        assert output.shape == (4, 24)

    def test_mult_table_structure(self: Any, device: Any) -> None:
        """Test octonion multiplication table structure."""
        layer = OctonionLinear(16, 16).to(device)

        # e_0 is identity: e_0 * e_i = e_i
        for i in range(8):
            assert layer.mult_table[0, i, i].item() == 1.0  # type: ignore[index]

        # e_i * e_i = -e_0 for i > 0
        for i in range(1, 8):
            assert layer.mult_table[i, i, 0].item() == -1.0  # type: ignore[index]

    def test_alternativity(self: Any, device: Any) -> None:
        """Test alternativity: x(xy) = x²y."""
        layer = OctonionLinear(8, 8).to(device)
        x = torch.randn(8, device=device)

        # This is a property of octonions, should hold
        result = layer.verify_alternativity(x)
        assert result, "Alternativity property failed"


class TestOctonionMLP:
    """Tests for Octonion MLP."""

    def test_forward_shape(self: Any, device: Any) -> None:
        """Test forward pass shape."""
        mlp = OctonionMLP(
            in_features=56,
            hidden_features=64,
            out_features=56,
            num_layers=3,
        ).to(device)

        x = torch.randn(4, 56, device=device)
        output = mlp(x)

        assert output.shape == (4, 56)

    def test_gradient_flow(self: Any, device: Any) -> None:
        """Test gradient flow through MLP."""
        mlp = OctonionMLP(
            in_features=56,
            hidden_features=64,
            out_features=56,
        ).to(device)

        x = torch.randn(4, 56, device=device, requires_grad=True)
        output = mlp(x)
        loss = output.sum()
        loss.backward()

        assert x.grad is not None
        assert not torch.isnan(x.grad).any()


# =============================================================================
# UNIFIED MODULE TESTS
# =============================================================================


class TestTheoreticalExceptionalHierarchy:
    """Tests for unified theoretical hierarchy (all components always enabled)."""

    def test_init_all_components(self: Any, device: Any) -> None:
        """Test initialization with all components enabled."""
        hierarchy = TheoreticalExceptionalHierarchy(
            colony_dim=8,
            num_colonies=7,
        ).to(device)

        # All 5 components must be present
        assert hierarchy.fts is not None
        assert hierarchy.jordan_bp is not None
        assert hierarchy.g2_holonomy is not None
        assert hierarchy.weyl_conv is not None
        assert hierarchy.octonion_mlp is not None
        assert hierarchy.combiner is not None

    def test_forward_shape(self: Any, colony_octonions: Any) -> None:
        """Test forward pass produces all outputs."""
        device = colony_octonions.device
        hierarchy = TheoreticalExceptionalHierarchy().to(device)

        output = hierarchy(colony_octonions)

        # All 6 outputs must be present
        assert "enhanced" in output
        assert output["enhanced"].shape == colony_octonions.shape
        assert "fts" in output
        assert "jordan_bp" in output
        assert "g2_holonomy" in output
        assert "weyl_conv" in output
        assert "octonion_mlp" in output

    def test_output_normalized(self: Any, colony_octonions: Any) -> None:
        """Test that output is normalized."""
        device = colony_octonions.device
        hierarchy = TheoreticalExceptionalHierarchy().to(device)

        output = hierarchy(colony_octonions)
        norms = output["enhanced"].norm(dim=-1)

        assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)

    def test_gradient_flow(self: Any, colony_octonions: Any) -> None:
        """Test gradient flow through entire hierarchy."""
        device = colony_octonions.device
        hierarchy = TheoreticalExceptionalHierarchy(
            colony_dim=8,
            num_colonies=7,
        ).to(device)

        # Make input require grad
        x = colony_octonions.clone().requires_grad_(True)
        output = hierarchy(x)
        loss = output["enhanced"].sum()
        loss.backward()

        assert x.grad is not None
        assert not torch.isnan(x.grad).any()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
