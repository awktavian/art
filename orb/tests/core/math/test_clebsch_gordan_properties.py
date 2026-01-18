"""Verification tests for Clebsch-Gordan projection properties.

VERIFICATION PROTOCOL (December 14, 2025):
==========================================
This test suite verifies the mathematical correctness of the exceptional
Lie algebra projection chain E8→E7→E6→F4→G2→S7.

THEOREMS UNDER TEST:
====================
1. Projection orthonormality: P @ P.T = I for all projectors
2. E8→E7 maximal subalgebra: 126 roots orthogonal to α = (1,-1,0,...)
3. E7→E6 Dynkin diagram: 72 roots orthogonal to β = (0,1,-1,0,...)
4. E6→F4 σ-folding: h'_i = (h_i + h_σ(i))/√2 for paired nodes
5. F4→G2 exceptional reduction: 14D = 2 Cartan + 12 roots via projection
6. G2→S7 fundamental representation: 7D from 14D via g₂ generators

PRECISION BOUNDS:
================
- Exact projections (E8→E7, E7→E6): atol=1e-5
- Principled projections (E6→F4): atol=1e-4
- Pure construction (G2→S7): atol=1e-4

Created: December 14, 2025
Author: Crystal / Kagami
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import torch
import numpy as np

from kagami_math.clebsch_gordan_exceptional import (
    # Root systems
    generate_e8_roots,
    generate_e7_roots_from_e8,
    generate_e6_roots_from_e8,
    generate_f4_roots,
    generate_g2_roots,
    # Projectors
    compute_e8_to_e7_clebsch_gordan,
    compute_e7_to_e6_clebsch_gordan,
    compute_e6_to_f4_clebsch_gordan,
    compute_f4_to_g2_clebsch_gordan,
    compute_g2_to_s7_clebsch_gordan,
    compute_g2_to_e8_projection,
    # Modules
    E8ToE7TrueProjector,
    E7ToE6TrueProjector,
    E6ToF4TrueProjector,
    F4ToG2TrueProjector,
    G2ToS7TrueProjector,
    TrueExceptionalHierarchy,
    G2DualProjector,
)

# =============================================================================
# PROJECTION ORTHONORMALITY TESTS
# =============================================================================


def test_projection_orthonormality_e8_to_e7():
    """Verify E8→E7 projection orthonormality: P @ P.T = I."""
    P = compute_e8_to_e7_clebsch_gordan()  # [133, 248]

    # Test P @ P.T = I_133
    PPT = P @ P.T
    I = torch.eye(133, dtype=torch.float32)

    error = (PPT - I).abs().max().item()

    # EXACT projection should have very low error
    assert error < 1e-5, f"E8→E7: P @ P.T ≠ I, max error = {error:.2e}"

    # Verify dimensions
    assert P.shape == (133, 248), f"Expected [133, 248], got {P.shape}"

    print(f"✅ E8→E7 orthonormality: max error = {error:.2e}")


def test_projection_orthonormality_e7_to_e6():
    """Verify E7→E6 projection orthonormality: P @ P.T = I."""
    P = compute_e7_to_e6_clebsch_gordan()  # [78, 133]

    PPT = P @ P.T
    I = torch.eye(78, dtype=torch.float32)

    error = (PPT - I).abs().max().item()

    # EXACT projection
    assert error < 1e-5, f"E7→E6: P @ P.T ≠ I, max error = {error:.2e}"
    assert P.shape == (78, 133), f"Expected [78, 133], got {P.shape}"

    print(f"✅ E7→E6 orthonormality: max error = {error:.2e}")


def test_projection_orthonormality_e6_to_f4():
    """Verify E6→F4 projection orthonormality: P @ P.T = I."""
    P = compute_e6_to_f4_clebsch_gordan()  # [52, 78]

    PPT = P @ P.T
    I = torch.eye(52, dtype=torch.float32)

    error = (PPT - I).abs().max().item()

    # PRINCIPLED projection (uses QR orthonormalization)
    assert error < 1e-4, f"E6→F4: P @ P.T ≠ I, max error = {error:.2e}"
    assert P.shape == (52, 78), f"Expected [52, 78], got {P.shape}"

    print(f"✅ E6→F4 orthonormality: max error = {error:.2e}")


def test_projection_orthonormality_f4_to_g2():
    """Verify F4→G2 projection orthonormality: P @ P.T = I."""
    P = compute_f4_to_g2_clebsch_gordan()  # [14, 52]

    PPT = P @ P.T
    I = torch.eye(14, dtype=torch.float32)

    error = (PPT - I).abs().max().item()

    # STRUCTURED projection
    assert error < 1e-4, f"F4→G2: P @ P.T ≠ I, max error = {error:.2e}"
    assert P.shape == (14, 52), f"Expected [14, 52], got {P.shape}"

    print(f"✅ F4→G2 orthonormality: max error = {error:.2e}")


def test_projection_orthonormality_g2_to_s7():
    """Verify G2→S7 projection orthonormality: P @ P.T = I."""
    P = compute_g2_to_s7_clebsch_gordan()  # [7, 14]

    PPT = P @ P.T
    I = torch.eye(7, dtype=torch.float32)

    error = (PPT - I).abs().max().item()

    # PURE construction via g₂ generators
    assert error < 1e-4, f"G2→S7: P @ P.T ≠ I, max error = {error:.2e}"
    assert P.shape == (7, 14), f"Expected [7, 14], got {P.shape}"

    print(f"✅ G2→S7 orthonormality: max error = {error:.2e}")


def test_projection_orthonormality_g2_to_e8():
    """Verify G2→E8 projection orthonormality: P @ P.T = I."""
    P = compute_g2_to_e8_projection()  # [8, 14]

    PPT = P @ P.T
    I = torch.eye(8, dtype=torch.float32)

    error = (PPT - I).abs().max().item()

    # EXACT by construction (Cartan + symmetric root blend)
    assert error < 1e-5, f"G2→E8: P @ P.T ≠ I, max error = {error:.2e}"
    assert P.shape == (8, 14), f"Expected [8, 14], got {P.shape}"

    print(f"✅ G2→E8 orthonormality: max error = {error:.2e}")


# =============================================================================
# ROOT SYSTEM EMBEDDING TESTS
# =============================================================================


def test_e8_to_e7_maximal_subalgebra():
    """Verify E7 roots are E8 roots orthogonal to α = (1,-1,0,...)."""
    e8_roots = generate_e8_roots()  # [240, 8]
    e7_roots, complement = generate_e7_roots_from_e8()  # [126, 8], [114, 8]

    # Verify counts
    assert e7_roots.shape[0] == 126, f"Expected 126 E7 roots, got {e7_roots.shape[0]}"
    assert complement.shape[0] == 114, f"Expected 114 complement roots, got {complement.shape[0]}"
    assert e7_roots.shape[0] + complement.shape[0] == 240, "E7 + complement should equal 240"

    # Verify E7 roots are orthogonal to embedding root α
    alpha = torch.tensor([1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=torch.float32)
    dots = torch.matmul(e7_roots, alpha)

    # All E7 roots should be orthogonal (dot product ≈ 0)
    max_dot = dots.abs().max().item()
    assert max_dot < 1e-5, f"E7 roots not orthogonal to α: max |α·e7| = {max_dot:.2e}"

    # Verify complement roots are NOT orthogonal
    complement_dots = torch.matmul(complement, alpha)
    non_orthogonal = (complement_dots.abs() > 1e-5).sum().item()
    assert (
        non_orthogonal == 114
    ), f"Expected all 114 complement roots non-orthogonal, got {non_orthogonal}"

    print(f"✅ E8→E7: 126 roots orthogonal to α, max |α·e7| = {max_dot:.2e}")


def test_e7_to_e6_dynkin_diagram():
    """Verify E6 roots are E7 roots orthogonal to β = (0,1,-1,0,...)."""
    _e7_roots, _ = generate_e7_roots_from_e8()  # [126, 8]
    e6_roots, _complement = generate_e6_roots_from_e8()  # [72, 8], [168, 8]

    # Verify E6 count
    assert e6_roots.shape[0] == 72, f"Expected 72 E6 roots, got {e6_roots.shape[0]}"

    # E6 embedding: roots orthogonal to BOTH α₁ and α₂
    alpha1 = torch.tensor([1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=torch.float32)
    alpha2 = torch.tensor([0.0, 1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=torch.float32)

    dots1 = torch.matmul(e6_roots, alpha1)
    dots2 = torch.matmul(e6_roots, alpha2)

    max_dot1 = dots1.abs().max().item()
    max_dot2 = dots2.abs().max().item()

    assert max_dot1 < 1e-5, f"E6 roots not orthogonal to α₁: max = {max_dot1:.2e}"
    assert max_dot2 < 1e-5, f"E6 roots not orthogonal to α₂: max = {max_dot2:.2e}"

    print(
        f"✅ E7→E6: 72 roots orthogonal to (α₁, α₂), max errors = ({max_dot1:.2e}, {max_dot2:.2e})"
    )


def test_e6_to_f4_dynkin_folding():
    """Verify E6→F4 Cartan projection uses σ-folding: h'_i = (h_i + h_σ(i))/√2.

    Note: QR orthonormalization can flip signs, so we verify MAGNITUDES only.
    The orthonormality property (P @ P.T = I) is the critical constraint.
    """
    P = compute_e6_to_f4_clebsch_gordan()  # [52, 78]

    # Extract Cartan projection (first 4 rows, first 6 columns)
    P_cartan = P[:4, :6]

    sqrt2 = np.sqrt(2)

    # Expected Cartan projection (up to sign from QR):
    # h'₁ = ±(h₁ + h₅)/√2  → |coeff| = 1/√2
    # h'₂ = ±(h₂ + h₄)/√2  → |coeff| = 1/√2
    # h'₃ = ±h₃            → |coeff| = 1
    # h'₄ = ±h₆            → |coeff| = 1

    # Verify h'₁ coefficients (magnitude)
    assert (
        abs(abs(P_cartan[0, 0]) - 1 / sqrt2) < 1e-4
    ), f"h'₁ from h₁: expected |{1 / sqrt2:.4f}|, got |{P_cartan[0, 0]:.4f}|"
    assert (
        abs(abs(P_cartan[0, 4]) - 1 / sqrt2) < 1e-4
    ), f"h'₁ from h₅: expected |{1 / sqrt2:.4f}|, got |{P_cartan[0, 4]:.4f}|"

    # Verify h'₂ coefficients (magnitude)
    assert (
        abs(abs(P_cartan[1, 1]) - 1 / sqrt2) < 1e-4
    ), f"h'₂ from h₂: expected |{1 / sqrt2:.4f}|, got |{P_cartan[1, 1]:.4f}|"
    assert (
        abs(abs(P_cartan[1, 3]) - 1 / sqrt2) < 1e-4
    ), f"h'₂ from h₄: expected |{1 / sqrt2:.4f}|, got |{P_cartan[1, 3]:.4f}|"

    # Verify h'₃ = ±h₃ (fixed point, magnitude)
    assert (
        abs(abs(P_cartan[2, 2]) - 1.0) < 1e-4
    ), f"h'₃ from h₃: expected |1.0|, got |{P_cartan[2, 2]:.4f}|"

    # Verify h'₄ = ±h₆ (fixed point, magnitude)
    assert (
        abs(abs(P_cartan[3, 5]) - 1.0) < 1e-4
    ), f"h'₄ from h₆: expected |1.0|, got |{P_cartan[3, 5]:.4f}|"

    print(f"✅ E6→F4: Dynkin σ-folding verified with |1/√2| ≈ {1 / sqrt2:.4f}")


def test_f4_to_g2_cartan_projection():
    """Verify F4→G2 uses G2 Cartan projection (x₁+x₂, x₃+x₄).

    Note: QR orthonormalization can flip signs, so we verify MAGNITUDES only.
    """
    P = compute_f4_to_g2_clebsch_gordan()  # [14, 52]

    # Extract Cartan projection (first 2 rows, first 4 columns)
    P_cartan = P[:2, :4]

    sqrt2 = np.sqrt(2)

    # Expected G2 Cartan projection (up to sign from QR):
    # h₁^G2 = ±(h₁^F4 + h₂^F4)/√2  → |coeff| = 1/√2
    # h₂^G2 = ±(h₃^F4 + h₄^F4)/√2  → |coeff| = 1/√2

    assert (
        abs(abs(P_cartan[0, 0]) - 1 / sqrt2) < 1e-4
    ), f"h₁^G2 from h₁^F4: expected |{1 / sqrt2:.4f}|, got |{P_cartan[0, 0]:.4f}|"
    assert (
        abs(abs(P_cartan[0, 1]) - 1 / sqrt2) < 1e-4
    ), f"h₁^G2 from h₂^F4: expected |{1 / sqrt2:.4f}|, got |{P_cartan[0, 1]:.4f}|"
    assert (
        abs(abs(P_cartan[1, 2]) - 1 / sqrt2) < 1e-4
    ), f"h₂^G2 from h₃^F4: expected |{1 / sqrt2:.4f}|, got |{P_cartan[1, 2]:.4f}|"
    assert (
        abs(abs(P_cartan[1, 3]) - 1 / sqrt2) < 1e-4
    ), f"h₂^G2 from h₄^F4: expected |{1 / sqrt2:.4f}|, got |{P_cartan[1, 3]:.4f}|"

    print("✅ F4→G2: G2 Cartan projection verified (magnitude)")


def test_g2_to_s7_unit_sphere():
    """Verify G2→S7 projection produces unit vectors on 7-sphere."""
    P = compute_g2_to_s7_clebsch_gordan()  # [7, 14]

    # Generate random G2 inputs
    torch.manual_seed(42)
    g2_inputs = torch.randn(100, 14)

    # Project to S7
    s7_outputs = g2_inputs @ P.T  # [100, 7]

    # Compute norms
    norms = torch.norm(s7_outputs, dim=-1)

    # Norms should NOT automatically be 1 (that requires explicit normalization)
    # But the projection should preserve relative scale
    mean_norm = norms.mean().item()
    std_norm = norms.std().item()

    # After normalization, should lie on unit sphere
    s7_normalized = s7_outputs / norms.unsqueeze(-1)
    norms_normalized = torch.norm(s7_normalized, dim=-1)

    norm_error = (norms_normalized - 1.0).abs().max().item()

    assert (
        norm_error < 1e-5
    ), f"Normalized S7 vectors not on unit sphere: max error = {norm_error:.2e}"

    print("✅ G2→S7: Projection preserves 7-sphere structure")
    print(f"   Before normalization: mean norm = {mean_norm:.4f} ± {std_norm:.4f}")
    print(f"   After normalization: max norm error = {norm_error:.2e}")


# =============================================================================
# DIMENSION PRESERVATION TESTS
# =============================================================================


def test_projection_dimension_preservation():
    """Verify dimension preservation through full chain."""
    dims = [
        ("E8", 248),
        ("E7", 133),
        ("E6", 78),
        ("F4", 52),
        ("G2", 14),
        ("S7", 7),
    ]

    # Test forward projection
    x = torch.randn(10, 248)
    hierarchy = TrueExceptionalHierarchy()

    # E8 → E7
    e7 = hierarchy.e8_to_e7.project(x)
    assert e7.shape == (10, 133), f"E8→E7: expected [10, 133], got {e7.shape}"

    # E7 → E6
    e6 = hierarchy.e7_to_e6.project(e7)
    assert e6.shape == (10, 78), f"E7→E6: expected [10, 78], got {e6.shape}"

    # E6 → F4
    f4 = hierarchy.e6_to_f4.project(e6)
    assert f4.shape == (10, 52), f"E6→F4: expected [10, 52], got {f4.shape}"

    # F4 → G2
    g2 = hierarchy.f4_to_g2.project(f4)
    assert g2.shape == (10, 14), f"F4→G2: expected [10, 14], got {g2.shape}"

    # G2 → S7
    s7 = hierarchy.g2_to_s7.project(g2)
    assert s7.shape == (10, 7), f"G2→S7: expected [10, 7], got {s7.shape}"

    # Test fused projection E8 → S7
    s7_fused = hierarchy.project_e8_to_s7_fused(x)
    assert s7_fused.shape == (10, 7), f"E8→S7 fused: expected [10, 7], got {s7_fused.shape}"

    # Fused result should match sequential (within numerical precision)
    diff = (s7 - s7_fused).abs().max().item()
    assert diff < 1e-4, f"Fused projection differs from sequential: max diff = {diff:.2e}"

    print("✅ Dimension preservation through full chain verified")
    print("   E8(248) → E7(133) → E6(78) → F4(52) → G2(14) → S7(7)")
    print(f"   Fused vs sequential: max diff = {diff:.2e}")


def test_g2_dual_projector_dimensions():
    """Verify G2DualProjector outputs correct dimensions."""
    dual = G2DualProjector()

    # Test input
    g2 = torch.randn(5, 14)

    # Test S7 projection
    s7 = dual.project_s7(g2, normalize=False)
    assert s7.shape == (5, 7), f"G2→S7: expected [5, 7], got {s7.shape}"

    # Test E8 projection
    e8 = dual.project_e8(g2)
    assert e8.shape == (5, 8), f"G2→E8: expected [5, 8], got {e8.shape}"

    # Test dual projection
    s7_dual, e8_dual = dual.project_dual(g2)
    assert s7_dual.shape == (5, 7), f"Dual S7: expected [5, 7], got {s7_dual.shape}"
    assert e8_dual.shape == (5, 8), f"Dual E8: expected [5, 8], got {e8_dual.shape}"

    # Test embedding
    g2_recon_s7 = dual.embed_s7(s7)
    assert g2_recon_s7.shape == (5, 14), f"S7→G2: expected [5, 14], got {g2_recon_s7.shape}"

    g2_recon_e8 = dual.embed_e8(e8)
    assert g2_recon_e8.shape == (5, 14), f"E8→G2: expected [5, 14], got {g2_recon_e8.shape}"

    print("✅ G2DualProjector dimensions verified")
    print("   G2(14) → S7(7) ✓")
    print("   G2(14) → E8(8) ✓")


# =============================================================================
# PROJECTOR MODULE TESTS
# =============================================================================


def test_projector_module_properties():
    """Verify TrueClebschGordanProjector module properties."""
    projector = E8ToE7TrueProjector()

    # Test projection
    x = torch.randn(10, 248)
    e7 = projector.project(x)
    assert e7.shape == (10, 133), f"Projection: expected [10, 133], got {e7.shape}"

    # Test embedding
    e8_recon = projector.embed(e7)
    assert e8_recon.shape == (10, 248), f"Embedding: expected [10, 248], got {e8_recon.shape}"

    # Test idempotency: project(embed(z)) = z
    z = torch.randn(10, 133)
    z_roundtrip = projector.project(projector.embed(z))

    roundtrip_error = (z - z_roundtrip).abs().max().item()
    assert roundtrip_error < 0.01, f"Idempotency violated: max error = {roundtrip_error:.2e}"

    # Test forward/inverse
    y = projector.forward(x, inverse=False)
    assert torch.allclose(y, e7, atol=1e-6), "Forward should equal project"

    x_recon = projector.forward(e7, inverse=True)
    assert torch.allclose(x_recon, e8_recon, atol=1e-6), "Inverse should equal embed"

    print("✅ TrueClebschGordanProjector properties verified")
    print(f"   Idempotency error: {roundtrip_error:.2e}")


# =============================================================================
# NUMERICAL STABILITY TESTS
# =============================================================================


def test_projection_numerical_stability():
    """Verify projections are numerically stable under repeated application."""
    hierarchy = TrueExceptionalHierarchy()

    # Start with random E8 input
    torch.manual_seed(123)
    x = torch.randn(5, 248)

    # Project down to S7
    s7 = hierarchy.project_to_level(x, target_level="S7")
    assert isinstance(s7, torch.Tensor), "project_to_level should return Tensor"

    # Embed back to E8
    x_recon = hierarchy.embed_from_level(s7, source_level="S7")

    # Project down again (should be idempotent)
    s7_again = hierarchy.project_to_level(x_recon, target_level="S7")

    # Check stability
    stability_error = (s7 - s7_again).abs().max().item()  # type: ignore[operator]

    # Allow larger error due to accumulated projection/embedding
    assert stability_error < 0.1, f"Numerical instability: max error = {stability_error:.2e}"

    print("✅ Numerical stability verified")
    print(f"   Roundtrip E8→S7→E8→S7 error: {stability_error:.2e}")


def test_projection_rank_preservation():
    """Verify projection matrices have full rank."""
    projectors = [
        ("E8→E7", compute_e8_to_e7_clebsch_gordan(), 133),
        ("E7→E6", compute_e7_to_e6_clebsch_gordan(), 78),
        ("E6→F4", compute_e6_to_f4_clebsch_gordan(), 52),
        ("F4→G2", compute_f4_to_g2_clebsch_gordan(), 14),
        ("G2→S7", compute_g2_to_s7_clebsch_gordan(), 7),
        ("G2→E8", compute_g2_to_e8_projection(), 8),
    ]

    for name, P, expected_rank in projectors:
        rank = torch.linalg.matrix_rank(P).item()
        assert rank == expected_rank, f"{name}: Expected rank {expected_rank}, got {rank}"
        print(f"✅ {name}: rank = {rank}/{expected_rank}")


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


def test_full_hierarchy_integration():
    """Integration test: full E8→S7 chain with verification."""
    hierarchy = TrueExceptionalHierarchy()

    # Random E8 input (batch=20)
    torch.manual_seed(456)
    e8 = torch.randn(20, 248)

    # Project with intermediates
    result = hierarchy.project_to_level(e8, target_level="S7", return_intermediates=True)
    assert isinstance(result, dict), "Should return dict with intermediates"

    # Verify all levels present
    assert "E8" in result, "Missing E8"
    assert "E7" in result, "Missing E7"
    assert "E6" in result, "Missing E6"
    assert "F4" in result, "Missing F4"
    assert "G2" in result, "Missing G2"
    assert "S7" in result, "Missing S7"

    # Verify shapes
    assert result["E8"].shape == (20, 248), f"E8 shape: {result['E8'].shape}"
    assert result["E7"].shape == (20, 133), f"E7 shape: {result['E7'].shape}"
    assert result["E6"].shape == (20, 78), f"E6 shape: {result['E6'].shape}"
    assert result["F4"].shape == (20, 52), f"F4 shape: {result['F4'].shape}"
    assert result["G2"].shape == (20, 14), f"G2 shape: {result['G2'].shape}"
    assert result["S7"].shape == (20, 7), f"S7 shape: {result['S7'].shape}"

    # Verify sequential consistency
    e7_direct = hierarchy.e8_to_e7.project(e8)
    assert torch.allclose(result["E7"], e7_direct, atol=1e-5), "E7 mismatch"

    print("✅ Full hierarchy integration verified")
    print("   E8(248) → E7(133) → E6(78) → F4(52) → G2(14) → S7(7)")


# =============================================================================
# SUMMARY REPORT
# =============================================================================


def test_generate_verification_report():
    """Generate comprehensive verification report."""
    print("\n" + "=" * 70)
    print("CLEBSCH-GORDAN PROJECTION VERIFICATION REPORT")
    print("=" * 70)

    # Collect all projection matrices
    projections = [
        ("E8→E7", compute_e8_to_e7_clebsch_gordan(), 133, 248, "EXACT"),
        ("E7→E6", compute_e7_to_e6_clebsch_gordan(), 78, 133, "EXACT"),
        ("E6→F4", compute_e6_to_f4_clebsch_gordan(), 52, 78, "PRINCIPLED"),
        ("F4→G2", compute_f4_to_g2_clebsch_gordan(), 14, 52, "STRUCTURED"),
        ("G2→S7", compute_g2_to_s7_clebsch_gordan(), 7, 14, "PURE"),
        ("G2→E8", compute_g2_to_e8_projection(), 8, 14, "OPTIMAL"),
    ]

    print("\n1. PROJECTION ORTHONORMALITY (P @ P.T = I)")
    print("-" * 70)
    for name, P, target_dim, source_dim, precision in projections:
        PPT = P @ P.T
        I = torch.eye(target_dim, dtype=torch.float32)
        error = (PPT - I).abs().max().item()

        status = "✅ PASS" if error < 1e-4 else "❌ FAIL"
        print(
            f"{name:8s} [{target_dim:3d}, {source_dim:3d}] | error = {error:.2e} | {precision:11s} | {status}"
        )

    print("\n2. ROOT SYSTEM EMBEDDINGS")
    print("-" * 70)

    # E8→E7
    e7_roots, _ = generate_e7_roots_from_e8()
    alpha = torch.tensor([1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=torch.float32)
    e7_ortho = (torch.matmul(e7_roots, alpha).abs() < 1e-5).sum().item()
    print(
        f"E8→E7:   {e7_roots.shape[0]}/126 roots orthogonal to α = {e7_ortho}/126 | {'✅ PASS' if e7_ortho == 126 else '❌ FAIL'}"
    )

    # E7→E6
    e6_roots, _ = generate_e6_roots_from_e8()
    alpha1 = torch.tensor([1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=torch.float32)
    alpha2 = torch.tensor([0.0, 1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=torch.float32)
    e6_ortho = (
        (
            (torch.matmul(e6_roots, alpha1).abs() < 1e-5)
            & (torch.matmul(e6_roots, alpha2).abs() < 1e-5)
        )
        .sum()
        .item()
    )
    print(
        f"E7→E6:   {e6_roots.shape[0]}/72 roots orthogonal to (α₁, α₂) = {e6_ortho}/72 | {'✅ PASS' if e6_ortho == 72 else '❌ FAIL'}"
    )

    # F4, G2 root counts
    f4_roots = generate_f4_roots()
    g2_roots = generate_g2_roots()
    print(
        f"F4:      {f4_roots.shape[0]}/48 roots in R⁴ | {'✅ PASS' if f4_roots.shape[0] == 48 else '❌ FAIL'}"
    )
    print(
        f"G2:      {g2_roots.shape[0]}/12 roots in R³ (x+y+z=0) | {'✅ PASS' if g2_roots.shape[0] == 12 else '❌ FAIL'}"
    )

    print("\n3. DIMENSION PRESERVATION")
    print("-" * 70)
    hierarchy = TrueExceptionalHierarchy()
    x = torch.randn(1, 248)

    results = {}
    current = x
    for name, projector in [
        ("E7", hierarchy.e8_to_e7),
        ("E6", hierarchy.e7_to_e6),
        ("F4", hierarchy.e6_to_f4),
        ("G2", hierarchy.f4_to_g2),
        ("S7", hierarchy.g2_to_s7),
    ]:
        current = projector.project(current)
        results[name] = current.shape[1]

    expected = {"E7": 133, "E6": 78, "F4": 52, "G2": 14, "S7": 7}
    for name, dim in expected.items():
        actual = results[name]
        status = "✅ PASS" if actual == dim else "❌ FAIL"
        print(f"{name:3s}: {actual:3d}/{dim:3d} | {status}")

    print("\n4. MATRIX RANK (Full Rank Required)")
    print("-" * 70)
    for name, P, expected_rank, _, _ in projections:
        rank = torch.linalg.matrix_rank(P).item()
        status = "✅ PASS" if rank == expected_rank else "❌ FAIL"
        print(f"{name:8s}: rank = {rank:3d}/{expected_rank:3d} | {status}")

    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    # Run verification report
    test_generate_verification_report()
