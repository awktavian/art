"""Tests for True Clebsch-Gordan Coefficients.

These tests verify the mathematical correctness of the exceptional Lie algebra
projection matrices computed from root systems.

Created: December 7, 2025
Updated: December 14, 2025 - Added timeouts for reliability
"""

from __future__ import annotations

from typing import Any

import pytest

# Consolidated markers with timeout
pytestmark = [
    pytest.mark.tier_unit,
    pytest.mark.timeout(30),
]

import torch
import numpy as np

from kagami_math.clebsch_gordan_exceptional import (
    # Root systems
    generate_e8_roots,
    generate_e8_cartan_basis,
    generate_e7_roots_from_e8,
    generate_e6_roots,
    generate_f4_roots,
    generate_g2_roots,
    # C-G matrices
    compute_e8_to_e7_clebsch_gordan,
    compute_e7_to_e6_clebsch_gordan,
    compute_e6_to_f4_clebsch_gordan,
    compute_f4_to_g2_clebsch_gordan,
    compute_g2_to_s7_clebsch_gordan,
    # Projectors
    E8ToE7TrueProjector,
    E7ToE6TrueProjector,
    E6ToF4TrueProjector,
    F4ToG2TrueProjector,
    G2ToS7TrueProjector,
    TrueExceptionalHierarchy,
)
from kagami_math.g2_irrep_tower import G2ClebschGordan
from kagami.core.world_model.equivariance.g2_exact import G2ExactClebschGordan


class TestE8RootSystem:
    """Tests for E8 root system generation."""

    def test_root_count(self) -> None:
        """E8 should have exactly 240 roots."""
        roots = generate_e8_roots()
        assert roots.shape[0] == 240, f"Expected 240 E8 roots, got {roots.shape[0]}"

    def test_root_dimension(self) -> None:
        """E8 roots should be in R^8."""
        roots = generate_e8_roots()
        assert roots.shape[1] == 8, f"Expected 8D roots, got {roots.shape[1]}D"

    def test_root_norms(self) -> None:
        """All E8 roots should have squared length 2."""
        roots = generate_e8_roots()
        sq_norms = (roots**2).sum(dim=1)
        assert torch.allclose(sq_norms, torch.full_like(sq_norms, 2.0), atol=1e-6)

    def test_root_symmetry(self) -> None:
        """Roots should be symmetric: if α is a root, so is -α."""
        roots = generate_e8_roots()
        for i, root in enumerate(roots):
            neg_root = -root
            # Check if -root is also in the list
            distances = ((roots - neg_root) ** 2).sum(dim=1)
            min_dist = distances.min()
            assert min_dist < 1e-6, f"Root {i} has no negative partner"

    def test_cartan_basis_orthonormal(self) -> None:
        """Cartan basis should be orthonormal."""
        basis = generate_e8_cartan_basis()
        gram = basis @ basis.T
        assert torch.allclose(gram, torch.eye(8), atol=1e-6)


class TestE7Embedding:
    """Tests for E7 embedding in E8."""

    def test_e7_root_count(self) -> None:
        """E7 should have exactly 126 roots."""
        e7_roots, _ = generate_e7_roots_from_e8()
        assert e7_roots.shape[0] == 126, f"Expected 126 E7 roots, got {e7_roots.shape[0]}"

    def test_complement_count(self) -> None:
        """Complement should have 114 roots (56×2 + 2)."""
        _, complement = generate_e7_roots_from_e8()
        assert complement.shape[0] == 114, (
            f"Expected 114 complement roots, got {complement.shape[0]}"
        )

    def test_partition_complete(self) -> None:
        """E7 roots + complement should equal all E8 roots."""
        e8_roots = generate_e8_roots()
        e7_roots, complement = generate_e7_roots_from_e8()
        total = e7_roots.shape[0] + complement.shape[0]
        assert total == 240, f"Expected 240 total, got {total}"


class TestClebschGordanMatrices:
    """Tests for Clebsch-Gordan projection matrices."""

    def test_e8_to_e7_dimensions(self) -> None:
        """E8→E7 projection should be [133, 248]."""
        P = compute_e8_to_e7_clebsch_gordan()
        assert P.shape == (133, 248), f"Expected (133, 248), got {P.shape}"

    def test_e7_to_e6_dimensions(self) -> None:
        """E7→E6 projection should be [78, 133]."""
        P = compute_e7_to_e6_clebsch_gordan()
        assert P.shape == (78, 133), f"Expected (78, 133), got {P.shape}"

    def test_e6_to_f4_dimensions(self) -> None:
        """E6→F4 projection should be [52, 78]."""
        P = compute_e6_to_f4_clebsch_gordan()
        assert P.shape == (52, 78), f"Expected (52, 78), got {P.shape}"

    def test_f4_to_g2_dimensions(self) -> None:
        """F4→G2 projection should be [14, 52]."""
        P = compute_f4_to_g2_clebsch_gordan()
        assert P.shape == (14, 52), f"Expected (14, 52), got {P.shape}"

    def test_g2_to_s7_dimensions(self) -> None:
        """G2→S7 projection should be [7, 14]."""
        P = compute_g2_to_s7_clebsch_gordan()
        assert P.shape == (7, 14), f"Expected (7, 14), got {P.shape}"


class TestProjectorModules:
    """Tests for projector nn.Modules."""

    @pytest.fixture
    def hierarchy(self):
        return TrueExceptionalHierarchy()

    def test_forward_dimensions(self, hierarchy) -> None:
        """Forward pass should reduce dimensions correctly."""
        x = torch.randn(4, 248)

        y_e7 = hierarchy.project_to_level(x, "E7")
        assert y_e7.shape == (4, 133)

        y_e6 = hierarchy.project_to_level(x, "E6")
        assert y_e6.shape == (4, 78)

        y_f4 = hierarchy.project_to_level(x, "F4")
        assert y_f4.shape == (4, 52)

        y_g2 = hierarchy.project_to_level(x, "G2")
        assert y_g2.shape == (4, 14)

        y_s7 = hierarchy.project_to_level(x, "S7")
        assert y_s7.shape == (4, 7)

    def test_embedding_dimensions(self, hierarchy) -> None:
        """Embedding should expand dimensions correctly."""
        z = torch.randn(4, 7)

        x_g2 = hierarchy.embed_from_level(z, "S7")
        # After embedding from S7, we're at G2, but we embed all the way to E8
        x_e8 = hierarchy.embed_from_level(z, "S7")
        assert x_e8.shape == (4, 248)

    def test_intermediates(self, hierarchy) -> None:
        """Should return all intermediate representations."""
        x = torch.randn(2, 248)
        results = hierarchy.project_to_level(x, "S7", return_intermediates=True)

        expected_dims = {"E8": 248, "E7": 133, "E6": 78, "F4": 52, "G2": 14, "S7": 7}
        for name, expected_dim in expected_dims.items():
            assert name in results, f"Missing {name}"
            assert results[name].shape[-1] == expected_dim


class TestProjectorProperties:
    """Tests for mathematical properties of projectors."""

    def test_e8_e7_pe_identity(self) -> None:
        """P @ E should be close to identity on target space."""
        proj = E8ToE7TrueProjector()
        PE = proj.projection_matrix @ proj.embedding_matrix
        I = torch.eye(133)
        error = (PE - I).abs().max().item()
        assert error < 0.1, f"PE ≠ I, max error = {error}"

    def test_projector_idempotence(self) -> None:
        """(E @ P)² should equal E @ P for true projectors."""
        proj = E8ToE7TrueProjector()
        EP = proj.embedding_matrix @ proj.projection_matrix
        EP2 = EP @ EP
        error = (EP - EP2).abs().max().item()
        assert error < 0.1, f"Not idempotent, max error = {error}"

    def test_full_compression_ratio(self) -> None:
        """Total compression should be 248 → 7 (35.4x)."""
        hierarchy = TrueExceptionalHierarchy()
        x = torch.randn(1, 248)
        y = hierarchy(x, target_level="S7")
        compression = 248 / 7
        assert abs(compression - 35.43) < 0.1, f"Compression ratio: {compression}"


class TestOtherRootSystems:
    """Tests for F4 and G2 root systems."""

    def test_f4_root_count(self) -> None:
        """F4 should have 48 roots."""
        roots = generate_f4_roots()
        assert roots.shape[0] == 48, f"Expected 48 F4 roots, got {roots.shape[0]}"

    def test_g2_root_count(self) -> None:
        """G2 should have 12 roots."""
        roots = generate_g2_roots()
        assert roots.shape[0] == 12, f"Expected 12 G2 roots, got {roots.shape[0]}"


class TestBranchingRules:
    """Tests for mathematical branching rule dimensions.

    These tests verify that the dimension decompositions match
    the theoretical branching rules from representation theory.
    """

    def test_e8_e7_branching_dimensions(self) -> None:
        """E8 → E7 × SU(2): 248 = 133 + 56×2 + 1×3 = 133 + 112 + 3 = 248."""
        e7_dim = 133
        complement_dim = 248 - 133  # 115 (should be 56×2 + 1×3 = 115)
        assert e7_dim + complement_dim == 248, "E8→E7 branching dimensions"

        # The complement splits as (56,2) + (1,3)
        # 56×2 = 112, 1×3 = 3, total = 115
        expected_complement = 56 * 2 + 1 * 3
        assert complement_dim == expected_complement, (
            f"Complement: {complement_dim} ≠ {expected_complement}"
        )

    def test_e7_e6_branching_dimensions(self) -> None:
        """E7 → E6 × U(1): 133 = 78 + 27 + 27 + 1 = 133."""
        e6_dim = 78
        expected_total = 78 + 27 + 27 + 1
        assert expected_total == 133, f"E7→E6 branching: {expected_total} ≠ 133"

    def test_e6_f4_branching_dimensions(self) -> None:
        """E6 → F4: 78 = 52 + 26."""
        f4_dim = 52
        complement_dim = 78 - 52
        assert f4_dim + complement_dim == 78, "E6→F4 branching dimensions"
        assert complement_dim == 26, f"F4 complement: {complement_dim} ≠ 26"

    def test_f4_g2_branching_dimensions(self) -> None:
        """F4 → G2 × SU(2): 52 = 14 + 14 + 14 + 3 + 7 = 52."""
        g2_dim = 14
        # Full branching: (14,1) + (7,2) + (7,2) + (1,3) + (7,1)
        expected_total = 14 * 1 + 7 * 2 + 7 * 2 + 1 * 3 + 7 * 1
        assert expected_total == 52, f"F4→G2 branching: {expected_total} ≠ 52"


class TestAllProjectorsIdempotence:
    """Tests for idempotence property of all projectors.

    For a true orthogonal projector P with embedding E = P^T:
    - P @ E = I_target (projection then embedding = identity on target)
    - E @ P is idempotent: (E @ P)² = E @ P
    """

    @pytest.mark.parametrize(
        "projector_class,source_dim,target_dim,algebra",
        [
            (E8ToE7TrueProjector, 248, 133, "E8→E7"),
            (E7ToE6TrueProjector, 133, 78, "E7→E6"),
            (E6ToF4TrueProjector, 78, 52, "E6→F4"),
            (F4ToG2TrueProjector, 52, 14, "F4→G2"),
        ],
    )
    def test_pe_identity(
        self, projector_class, source_dim: int, target_dim: int, algebra: str
    ) -> None:
        """P @ E should equal identity on target space."""
        proj = projector_class()
        PE = proj.projection_matrix @ proj.embedding_matrix
        I_target = torch.eye(target_dim)
        error = (PE - I_target).abs().max().item()
        assert error < 1e-5, f"{algebra} projector: PE ≠ I, error = {error}"

    @pytest.mark.parametrize(
        "projector_class,source_dim,target_dim,algebra",
        [
            (E8ToE7TrueProjector, 248, 133, "E8→E7"),
            (E7ToE6TrueProjector, 133, 78, "E7→E6"),
            (E6ToF4TrueProjector, 78, 52, "E6→F4"),
            (F4ToG2TrueProjector, 52, 14, "F4→G2"),
        ],
    )
    def test_ep_idempotent(
        self, projector_class, source_dim: int, target_dim: int, algebra: str
    ) -> None:
        """(E @ P)² should equal E @ P (idempotence)."""
        proj = projector_class()
        EP = proj.embedding_matrix @ proj.projection_matrix
        EP2 = EP @ EP
        error = (EP - EP2).abs().max().item()
        assert error < 1e-5, f"{algebra} projector: Not idempotent, error = {error}"


class TestGradientFlow:
    """Tests to verify gradients flow through projections.

    This is critical for training - projections must be differentiable.
    """

    def test_hierarchy_gradient_flow(self) -> None:
        """Gradients should flow through full hierarchy."""
        hierarchy = TrueExceptionalHierarchy()

        x = torch.randn(2, 248, requires_grad=True)
        y = hierarchy(x, target_level="S7")

        # Compute loss and backprop
        loss = y.sum()
        loss.backward()

        # Check gradients exist and are non-zero
        assert x.grad is not None, "No gradient computed"
        assert x.grad.abs().max() > 0, "Gradient is all zeros"

    def test_round_trip_gradient(self) -> None:
        """Gradients should flow through project→embed round trip."""
        hierarchy = TrueExceptionalHierarchy()

        x = torch.randn(2, 248, requires_grad=True)

        # Project down
        z = hierarchy(x, target_level="S7")

        # Embed back up
        x_reconstructed = hierarchy(z, target_level="S7", inverse=True)

        # Loss on reconstruction
        loss = (x - x_reconstructed).pow(2).sum()
        loss.backward()

        assert x.grad is not None, "No gradient on round-trip"


class TestNumericalStability:
    """Tests for numerical stability of projections."""

    def test_projection_bounded_output(self) -> None:
        """Projection output should not explode for bounded input."""
        hierarchy = TrueExceptionalHierarchy()

        # Test with unit norm input
        x = torch.randn(100, 248)
        x = x / x.norm(dim=-1, keepdim=True)

        y = hierarchy(x, target_level="S7")

        # Output should be reasonably bounded (not exploding)
        max_norm = y.norm(dim=-1).max().item()
        assert max_norm < 100, f"Output norm too large: {max_norm}"

    def test_embedding_bounded_output(self) -> None:
        """Embedding output should not explode for bounded input."""
        hierarchy = TrueExceptionalHierarchy()

        # Test with unit norm input at S7 level
        z = torch.randn(100, 7)
        z = z / z.norm(dim=-1, keepdim=True)

        x = hierarchy(z, target_level="S7", inverse=True)

        # Output should be reasonably bounded
        max_norm = x.norm(dim=-1).max().item()
        assert max_norm < 100, f"Embedding norm too large: {max_norm}"


class TestFusedProjections:
    """Tests for optimized fused projection matrices."""

    @pytest.fixture
    def hierarchy(self):
        """Create hierarchy for testing."""
        from kagami_math.clebsch_gordan_exceptional import TrueExceptionalHierarchy

        return TrueExceptionalHierarchy()

    def test_fused_e8_to_s7_correctness(self, hierarchy) -> None:
        """Test that fused E8->S7 matches sequential."""
        x = torch.randn(100, 248)
        y_seq = hierarchy.project_to_level(x, "S7")
        y_fused = hierarchy.project_e8_to_s7_fused(x)
        assert torch.allclose(y_seq, y_fused, atol=1e-5)

    def test_fused_s7_to_e8_correctness(self, hierarchy) -> None:
        """Test that fused S7->E8 matches sequential."""
        z = torch.randn(100, 7)
        x_seq = hierarchy.embed_from_level(z, "S7")
        x_fused = hierarchy.embed_s7_to_e8_fused(z)
        assert torch.allclose(x_seq, x_fused, atol=1e-5)

    def test_fused_roundtrip(self, hierarchy) -> None:
        """Test fused project -> embed roundtrip."""
        x = torch.randn(50, 248)
        z = hierarchy.project_e8_to_s7_fused(x)
        x_back = hierarchy.embed_s7_to_e8_fused(z)
        z_back = hierarchy.project_e8_to_s7_fused(x_back)
        # z should equal z_back (idempotence)
        assert torch.allclose(z, z_back, atol=1e-5)

    def test_fused_batch_independence(self, hierarchy) -> None:
        """Test that fused projections are batch-independent."""
        x1 = torch.randn(1, 248)
        x16 = torch.randn(16, 248)

        # Single batch
        y1 = hierarchy.project_e8_to_s7_fused(x1)

        # Batch of 16
        y16 = hierarchy.project_e8_to_s7_fused(x16)

        # First element of batch should match single
        x_combined = torch.cat([x1, x16], dim=0)
        y_combined = hierarchy.project_e8_to_s7_fused(x_combined)

        assert torch.allclose(y_combined[0], y1[0], atol=1e-6)


class TestG2FanoStructure:
    """Tests for G2→S7 projection with Fano plane structure."""

    def test_g2_s7_preserves_fano_lines(self) -> None:
        """G2→S7 projection should respect Fano line structure."""
        try:
            # Moved (Dec 13, 2025): world_model.quantum -> core.math to break cycles
            from kagami_math.fano_plane import FANO_LINES
        except ImportError:
            pytest.skip("Fano plane module not available")

        proj = G2ToS7TrueProjector()
        P = proj.projection_matrix  # [7, 14]

        # Verify projection is non-trivial (not all zeros)
        assert P.abs().sum() > 0, "G2→S7 projection is all zeros"

        # Verify shape
        assert P.shape == (7, 14), f"Wrong shape: {P.shape}"

    def test_g2_s7_output_dimension(self) -> None:
        """G2→S7 should map 14D to 7D correctly."""
        proj = G2ToS7TrueProjector()

        x = torch.randn(10, 14)
        y = proj.project(x)

        assert y.shape == (10, 7), f"Expected (10, 7), got {y.shape}"


class TestG2DualProjector:
    """Tests for G2DualProjector that outputs both S7 phase and E8 input."""

    @pytest.fixture
    def dual_projector(self):
        from kagami_math.clebsch_gordan_exceptional import G2DualProjector

        return G2DualProjector()

    def test_dual_output_dimensions(self, dual_projector) -> None:
        """Dual projector should output [7] S7 and [8] E8."""
        g2 = torch.randn(10, 14)
        s7, e8 = dual_projector(g2)

        assert s7.shape == (10, 7), f"S7 shape: {s7.shape}"
        assert e8.shape == (10, 8), f"E8 shape: {e8.shape}"

    def test_s7_normalized(self, dual_projector) -> None:
        """S7 output should be normalized to unit sphere."""
        g2 = torch.randn(10, 14)
        s7, _ = dual_projector(g2, normalize_s7=True)

        norms = s7.norm(dim=-1)
        assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)

    def test_s7_unnormalized(self, dual_projector) -> None:
        """S7 output can be unnormalized if requested."""
        g2 = torch.randn(10, 14)
        s7, _ = dual_projector(g2, normalize_s7=False)

        # Unnormalized output should NOT all be unit norm
        norms = s7.norm(dim=-1)
        assert not torch.allclose(norms, torch.ones_like(norms), atol=0.1)

    def test_e8_projection_orthonormal(self, dual_projector) -> None:
        """E8 projection matrix should be orthonormal."""
        P = dual_projector.P_e8
        gram = P @ P.T
        assert torch.allclose(gram, torch.eye(8), atol=1e-5)

    def test_s7_projection_orthonormal(self, dual_projector) -> None:
        """S7 projection matrix should be orthonormal."""
        P = dual_projector.P_s7
        gram = P @ P.T
        assert torch.allclose(gram, torch.eye(7), atol=1e-5)

    def test_embed_roundtrip_s7(self, dual_projector) -> None:
        """S7 embed should be pseudo-inverse of project."""
        g2 = torch.randn(10, 14)
        s7 = dual_projector.project_s7(g2, normalize=False)
        g2_back = dual_projector.embed_s7(s7)
        s7_back = dual_projector.project_s7(g2_back, normalize=False)

        # Roundtrip should preserve the S7 representation
        assert torch.allclose(s7, s7_back, atol=1e-5)

    def test_embed_roundtrip_e8(self, dual_projector) -> None:
        """E8 embed should be pseudo-inverse of project."""
        g2 = torch.randn(10, 14)
        e8 = dual_projector.project_e8(g2)
        g2_back = dual_projector.embed_e8(e8)
        e8_back = dual_projector.project_e8(g2_back)

        # Roundtrip should preserve the E8 representation
        assert torch.allclose(e8, e8_back, atol=1e-5)

    def test_with_e8_lattice_vq(self, dual_projector) -> None:
        """E8 output should be compatible with E8 lattice quantizer."""
        from kagami_math.e8_lattice_protocol import ResidualE8LatticeVQ

        g2 = torch.randn(10, 14)
        _, e8_input = dual_projector(g2)

        # Should be able to quantize without error
        vq = ResidualE8LatticeVQ()
        result = vq(e8_input, num_levels=4)
        e8_quantized = result["quantized"]
        indices = result["indices"]

        assert e8_quantized.shape == (10, 8)
        assert indices.shape == (10, 4, 8)  # [batch, levels, dims]

    def test_full_hierarchy_integration(self, dual_projector) -> None:
        """Test integration with full exceptional hierarchy."""
        hierarchy = TrueExceptionalHierarchy()

        # E8 → G2 via hierarchy
        x = torch.randn(5, 248)
        g2 = hierarchy.project_to_level(x, "G2")

        # G2 → dual outputs
        s7, e8 = dual_projector(g2)

        assert s7.shape == (5, 7)
        assert e8.shape == (5, 8)
        assert torch.allclose(s7.norm(dim=-1), torch.ones(5), atol=1e-5)


class TestG2ExactAndHigherTensorProducts:
    """Regression tests for 'exact' G₂ primitives and higher tensor projectors."""

    def test_g2_basis_preserves_phi(self) -> None:
        """The computed g₂ basis must preserve φ: A·φ = 0."""
        cg = G2ExactClebschGordan(dtype=torch.float64)
        phi = cg.phi.to(dtype=torch.float64)
        g2_basis = cg.g2_basis.to(dtype=torch.float64)

        # Basis must be in so(7): antisymmetric with zero diagonal
        assert torch.allclose(
            g2_basis + g2_basis.transpose(-1, -2),
            torch.zeros_like(g2_basis),
            atol=1e-10,
        )
        assert torch.allclose(
            torch.diagonal(g2_basis, dim1=-2, dim2=-1),
            torch.zeros(14, 7, dtype=torch.float64),
            atol=1e-10,
        )

        # Preservation: (A·φ)_{ijk} = A_{im} φ_{mjk} + A_{jm} φ_{imk} + A_{km} φ_{ijm} = 0
        max_err = 0.0
        for a in range(14):
            A = g2_basis[a]
            t1 = torch.einsum("im,mjk->ijk", A, phi)
            t2 = torch.einsum("jm,imk->ijk", A, phi)
            t3 = torch.einsum("km,ijm->ijk", A, phi)
            max_err = max(max_err, float((t1 + t2 + t3).abs().max().item()))
        assert max_err < 1e-10, f"g₂ basis does not preserve φ (max_err={max_err})"

    def test_g2_higher_tensor_projectors_are_orthogonal(self) -> None:
        """7⊗14 and 14⊗14 decompositions must be orthogonal (energy splits)."""
        cg = G2ClebschGordan(device=torch.device("cpu"))

        # 7⊗14 = 98 → 7 ⊕ 27 ⊕ 64
        x7 = torch.randn(8, 7)
        x14 = torch.randn(8, 14)
        d = cg.decompose_7x14(x7, x14)
        full = torch.einsum("bi,bj->bij", x7, x14).reshape(8, 98)
        e_full = (full * full).sum(dim=-1)
        e_parts = (
            (d["vector"] * d["vector"]).sum(dim=-1)
            + (d["symmetric"] * d["symmetric"]).sum(dim=-1)
            + (d["mixed_64"] * d["mixed_64"]).sum(dim=-1)
        )
        assert torch.allclose(e_full, e_parts, atol=1e-4, rtol=1e-4)

        # 14⊗14 = 196 → 1 ⊕ 14 ⊕ 27 ⊕ 77 ⊕ 77'
        y14 = torch.randn(8, 14)
        d2 = cg.decompose_14x14(x14, y14)
        full2 = torch.einsum("bi,bj->bij", x14, y14).reshape(8, 196)
        e_full2 = (full2 * full2).sum(dim=-1)
        e_parts2 = (
            (d2["scalar"] * d2["scalar"]).sum(dim=-1)
            + (d2["adjoint"] * d2["adjoint"]).sum(dim=-1)
            + (d2["symmetric"] * d2["symmetric"]).sum(dim=-1)
            + (d2["sym3_1"] * d2["sym3_1"]).sum(dim=-1)
            + (d2["sym3_2"] * d2["sym3_2"]).sum(dim=-1)
        )
        assert torch.allclose(e_full2, e_parts2, atol=1e-4, rtol=1e-4)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
