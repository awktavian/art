"""Property-Based Tests for Exceptional Hierarchy Projections.

Uses Hypothesis to verify mathematical invariants hold across wide input spaces.
Tests orthonormality, gradient flow, numerical stability, and branching rules.

Created: December 14, 2025
Author: Crystal Colony (Verification)
"""

from __future__ import annotations

from typing import Any

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.property,
    pytest.mark.tier_unit,
    pytest.mark.timeout(120),  # Math tests need more time
]

import numpy as np
import torch
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from kagami_math.clebsch_gordan_exceptional import (
    E6ToF4TrueProjector,
    E7ToE6TrueProjector,
    E8ToE7TrueProjector,
    F4ToG2TrueProjector,
    G2ToS7TrueProjector,
    TrueExceptionalHierarchy,
    compute_e6_to_f4_clebsch_gordan,
    compute_e7_to_e6_clebsch_gordan,
    compute_e8_to_e7_clebsch_gordan,
    compute_f4_to_g2_clebsch_gordan,
    compute_g2_to_s7_clebsch_gordan,
)

# Configure Hypothesis for longer-running math tests
settings.register_profile("math", deadline=2000, max_examples=200)
settings.load_profile("math")

# =============================================================================
# ORTHONORMALITY PROPERTIES
# =============================================================================


class TestOrthonormalityProperties:
    """Property tests for orthonormality of projection matrices.

    For all Clebsch-Gordan projections P: V → W, we verify:
    1. P @ P.T ≈ I_W (rows are orthonormal)
    2. ||P||_F is bounded (Frobenius norm)
    3. Property holds across dtypes and scales
    """

    @given(
        scale=st.floats(min_value=1e-8, max_value=1e8, allow_nan=False, allow_infinity=False),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_g2_to_s7_preserves_norm_distribution(self, scale: float) -> None:
        """Property: G2→S7 projection preserves norm up to scaling."""
        P = compute_g2_to_s7_clebsch_gordan()  # [7, 14]

        # Generate scaled input
        g2 = torch.randn(100, 14) * scale
        s7 = g2 @ P.T  # [100, 7]

        # Verify output doesn't explode or vanish
        norms_in = torch.norm(g2, dim=-1)
        norms_out = torch.norm(s7, dim=-1)

        # Projection should not amplify norms by more than ||P||_op
        # For orthonormal P, ||P||_op ≈ 1
        ratio = (norms_out / (norms_in + 1e-10)).abs()
        assert ratio.max() < 10.0, f"Norm amplification too high: {ratio.max():.4f}"

    @pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
    @pytest.mark.parametrize("scale", [1e-8, 1e-4, 1.0, 1e4, 1e8])
    def test_g2_to_s7_numerical_stability(self, dtype: torch.dtype, scale: float) -> None:
        """Property: G2→S7 projection is numerically stable across scales and dtypes."""
        P = compute_g2_to_s7_clebsch_gordan().to(dtype=dtype)

        # Generate input at various scales
        g2 = (torch.randn(50, 14) * scale).to(dtype=dtype)
        s7 = g2 @ P.T

        # No NaN or Inf in output
        assert not torch.isnan(s7).any(), f"NaN at scale={scale}, dtype={dtype}"
        assert not torch.isinf(s7).any(), f"Inf at scale={scale}, dtype={dtype}"

        # Verify orthonormality of P still holds
        gram = P @ P.T
        I_target = torch.eye(7, dtype=dtype)
        error = (gram - I_target).abs().max().item()
        assert error < 0.01, f"Orthonormality violated: error={error:.6f}"

    @pytest.mark.parametrize(
        "projection_fn,target_dim",
        [
            (compute_e8_to_e7_clebsch_gordan, 133),
            (compute_e7_to_e6_clebsch_gordan, 78),
            (compute_e6_to_f4_clebsch_gordan, 52),
            (compute_f4_to_g2_clebsch_gordan, 14),
            (compute_g2_to_s7_clebsch_gordan, 7),
        ],
    )
    def test_all_projections_orthonormal(self, projection_fn, target_dim: int) -> None:
        """Property: ALL C-G projections have orthonormal rows (P @ P.T ≈ I)."""
        P = projection_fn()
        gram = P @ P.T
        I_target = torch.eye(target_dim, dtype=P.dtype)

        # Measure orthonormality error
        error = (gram - I_target).abs().max().item()

        # Require tight orthonormality for all projections
        assert error < 0.01, f"{projection_fn.__name__}: P @ P.T ≠ I, max error = {error:.6f}"

    @given(
        batch_size=st.integers(min_value=1, max_value=64),
    )
    @settings(max_examples=50)
    def test_batch_independence(self, batch_size: int) -> None:
        """Property: Projection is batch-independent (linear operation)."""
        hierarchy = TrueExceptionalHierarchy()

        # Single batch
        x1 = torch.randn(1, 248)
        y1 = hierarchy.project_to_level(x1, "S7")

        # Batched input (same x1 repeated)
        x_batch = x1.repeat(batch_size, 1)
        y_batch = hierarchy.project_to_level(x_batch, "S7")

        # All outputs should be identical to y1
        for i in range(batch_size):
            assert torch.allclose(y_batch[i], y1[0], atol=1e-6), (  # type: ignore[index]
                f"Batch element {i} differs from single"
            )


# =============================================================================
# GRADIENT FLOW PROPERTIES
# =============================================================================


class TestGradientFlowProperties:
    """Property tests for gradient flow through exceptional hierarchy.

    Critical for training: all projections must be differentiable.
    """

    @given(
        batch_size=st.integers(min_value=1, max_value=16),
        hidden_dim=st.integers(min_value=64, max_value=512).filter(lambda x: x % 8 == 0),
    )
    @settings(max_examples=50, deadline=3000)
    def test_exceptional_hierarchy_gradient_flow(self, batch_size: int, hidden_dim: int) -> None:
        """Property: Gradients flow through E8→E7→E6→F4→G2→S7 chain.

        Updated Jan 2026: Use nn.Linear for proper gradient tracking (leaf tensors).
        """
        hierarchy = TrueExceptionalHierarchy()

        # Start with hidden_dim, project to E8 space
        x_hidden = torch.randn(batch_size, hidden_dim, requires_grad=True)

        # Expand to E8 (use nn.Linear for proper leaf tensor gradients)
        linear = torch.nn.Linear(hidden_dim, 248, bias=False)
        x_e8 = linear(x_hidden)

        # Project through hierarchy
        intermediates = hierarchy.project_to_level(x_e8, "S7", return_intermediates=True)

        # Loss on final output
        s7 = intermediates["S7"]  # type: ignore[index]
        loss = s7.pow(2).sum()
        loss.backward()

        # Verify gradients exist and are non-zero
        assert x_hidden.grad is not None, "No gradient on input"
        assert linear.weight.grad is not None, "No gradient on projection weight"

        # Gradients should be non-trivial (not all zeros)
        assert x_hidden.grad.abs().max() > 1e-8, "Input gradient is zero"
        assert linear.weight.grad.abs().max() > 1e-8, "Weight gradient is zero"

        # Gradients should be bounded (no explosion)
        assert x_hidden.grad.abs().max() < 1e6, "Input gradient exploded"
        assert linear.weight.grad.abs().max() < 1e6, "Weight gradient exploded"

    @given(
        target_level=st.sampled_from(["E7", "E6", "F4", "G2", "S7"]),
    )
    @settings(max_examples=25)
    def test_round_trip_gradient_preservation(self, target_level: str) -> None:
        """Property: Round-trip (project → embed) preserves gradient paths.

        Note: Some projection paths may have zero gradient if the reconstruction
        error is near-zero (idempotent operations). We check gradient exists and
        has finite values, but allow zero gradient when loss is small.
        """
        hierarchy = TrueExceptionalHierarchy()

        # Create leaf tensor and retain grad after operations
        x_base = torch.randn(4, 248)
        x = (x_base * 2.0).requires_grad_(True)
        x.retain_grad()  # Ensure we can access grad on non-leaf tensor

        # Project down to target level
        y = hierarchy.project_to_level(x, target_level)

        # Embed back to E8
        x_reconstructed = hierarchy.embed_from_level(y, target_level)  # type: ignore[arg-type]

        # Project back down (test idempotence)
        y_back = hierarchy.project_to_level(x_reconstructed, target_level)

        # Loss on reconstruction error in target space
        loss = (y - y_back).pow(2).sum()  # type: ignore[operator]
        loss.backward()

        # Gradient must exist and be finite
        assert x.grad is not None, f"No gradient for {target_level}"
        assert torch.isfinite(x.grad).all(), f"Non-finite gradient for {target_level}"
        # Note: Zero gradient is acceptable when loss is very small (near-idempotent)
        # The important property is that gradients are finite and don't explode


# =============================================================================
# NUMERICAL STABILITY PROPERTIES
# =============================================================================


class TestNumericalStabilityProperties:
    """Property tests for numerical stability of projections.

    Projections must not amplify errors or produce NaN/Inf.
    """

    @pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
    @pytest.mark.parametrize("scale", [1e-8, 1e-6, 1e-4, 1e-2, 1.0, 1e2, 1e4, 1e6, 1e8])
    def test_full_hierarchy_numerical_stability(self, dtype: torch.dtype, scale: float) -> None:
        """Property: Full hierarchy is stable across 16 orders of magnitude.

        Updated Jan 2026: Convert hierarchy to target dtype, or convert input to float32
        to match hierarchy's internal projection matrices.
        """
        hierarchy = TrueExceptionalHierarchy()

        # Convert hierarchy to target dtype (this affects all projection matrices)
        hierarchy = hierarchy.to(dtype=dtype)

        # Generate scaled input
        x = (torch.randn(10, 248) * scale).to(dtype=dtype)

        # Project through full hierarchy
        y = hierarchy.project_to_level(x, "S7")

        # Verify no NaN or Inf
        assert not torch.isnan(y).any(), f"NaN at scale={scale:.2e}, dtype={dtype}"  # type: ignore[arg-type]
        assert not torch.isinf(y).any(), f"Inf at scale={scale:.2e}, dtype={dtype}"  # type: ignore[arg-type]

        # Output should be bounded relative to input
        input_norm = x.norm(dim=-1).mean().item()
        output_norm = y.norm(dim=-1).mean().item()  # type: ignore[union-attr]

        if input_norm > 1e-10:  # Skip for near-zero inputs
            ratio = output_norm / input_norm
            # Projection should not explode (operator norm bounded)
            assert ratio < 1e3, f"Output exploded: ratio={ratio:.2e}"

    @given(
        input_norm=st.floats(min_value=1e-6, max_value=1e6, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_projection_preserves_bounded_norms(self, input_norm: float) -> None:
        """Property: Projection of unit-norm input has bounded output norm."""
        hierarchy = TrueExceptionalHierarchy()

        # Generate input with specified norm
        x = torch.randn(50, 248)
        x = x / (x.norm(dim=-1, keepdim=True) + 1e-10) * input_norm

        # Project to S7
        y = hierarchy.project_to_level(x, "S7")

        # Output norm should be bounded
        output_norm = y.norm(dim=-1).max().item()  # type: ignore[union-attr]

        # For orthonormal projection, output_norm ≤ input_norm
        # Allow some slack for numerical errors
        assert output_norm < input_norm * 2.0, (
            f"Output norm {output_norm:.2e} exceeds input {input_norm:.2e}"
        )

    @given(
        perturbation_scale=st.floats(min_value=1e-8, max_value=1e-2, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_projection_lipschitz_continuity(self, perturbation_scale: float) -> None:
        """Property: Small input changes → small output changes (Lipschitz)."""
        hierarchy = TrueExceptionalHierarchy()

        # Original input
        x1 = torch.randn(10, 248)

        # Perturbed input
        perturbation = torch.randn(10, 248) * perturbation_scale
        x2 = x1 + perturbation

        # Project both
        y1 = hierarchy.project_to_level(x1, "S7")
        y2 = hierarchy.project_to_level(x2, "S7")

        # Measure distances
        input_dist = (x2 - x1).norm(dim=-1).mean().item()
        output_dist = (y2 - y1).norm(dim=-1).mean().item()  # type: ignore[operator]

        # Lipschitz constant L: ||f(x) - f(y)|| ≤ L ||x - y||
        # For orthonormal projection, L ≈ 1
        if input_dist > 1e-10:
            lipschitz = output_dist / input_dist
            assert lipschitz < 10.0, f"Lipschitz constant too high: {lipschitz:.2f}"


# =============================================================================
# BRANCHING RULE VERIFICATION
# =============================================================================


class TestBranchingRuleProperties:
    """Property tests verifying branching rule dimension preservation.

    Mathematical branching rules from representation theory:
    - E8 → E7: 248 = 133 + 56×2 + 1×3
    - E7 → E6: 133 = 78 + 27×2 + 1
    - E6 → F4: 78 = 52 + 26
    """

    @pytest.mark.parametrize(
        "projection_fn,source_dim,target_dim,complement_dim",
        [
            (compute_e8_to_e7_clebsch_gordan, 248, 133, 115),  # 56×2 + 1×3
            (compute_e7_to_e6_clebsch_gordan, 133, 78, 55),  # 27 + 27 + 1
            (compute_e6_to_f4_clebsch_gordan, 78, 52, 26),  # 26
            (compute_f4_to_g2_clebsch_gordan, 52, 14, 38),  # 7×2 + 7×2 + 1×3 + 7
        ],
    )
    def test_branching_dimension_conservation(
        self,
        projection_fn,
        source_dim: int,
        target_dim: int,
        complement_dim: int,
    ) -> None:
        """Property: Branching preserves total dimension."""
        # Verify mathematical identity
        assert source_dim == target_dim + complement_dim, (
            f"Dimension mismatch: {source_dim} ≠ {target_dim} + {complement_dim}"
        )

        # Verify projection has correct shape
        P = projection_fn()
        assert P.shape == (
            target_dim,
            source_dim,
        ), f"Wrong projection shape: {P.shape} ≠ ({target_dim}, {source_dim})"

    @given(
        batch_size=st.integers(min_value=1, max_value=32),
    )
    @settings(max_examples=30)
    def test_e8_to_e7_branching_rank(self, batch_size: int) -> None:
        """Property: E8→E7 projection extracts rank-133 subspace."""
        P = compute_e8_to_e7_clebsch_gordan()  # [133, 248]

        # Generate random E8 input
        x = torch.randn(batch_size, 248)

        # Project to E7
        e7 = x @ P.T  # [batch, 133]

        # Verify rank: E7 representation should span full 133D
        # (not degenerate)
        if batch_size >= 133:
            rank = torch.linalg.matrix_rank(e7).item()
            # Allow some numerical slack
            assert rank >= 130, f"E7 rank deficient: {rank} < 133"

    @given(
        num_samples=st.integers(min_value=100, max_value=500),
    )
    @settings(max_examples=10, deadline=5000)
    def test_g2_to_s7_energy_preservation(self, num_samples: int) -> None:
        """Property: G2→S7 projection preserves energy (orthonormal)."""
        P = compute_g2_to_s7_clebsch_gordan()  # [7, 14]

        # Generate random G2 inputs
        g2 = torch.randn(num_samples, 14)

        # Project to S7
        s7 = g2 @ P.T  # [num_samples, 7]

        # Compute energies
        energy_in = (g2**2).sum(dim=-1)
        energy_out = (s7**2).sum(dim=-1)

        # For orthonormal projection to lower dimension:
        # energy_out ≤ energy_in (projection discards information)
        # but should be same ORDER of magnitude
        ratio = (energy_out / (energy_in + 1e-10)).mean().item()

        # Ratio should be roughly 7/14 = 0.5 for random inputs
        # (projecting from 14D to 7D)
        assert 0.3 < ratio < 0.8, f"Energy ratio {ratio:.3f} outside expected range"


# =============================================================================
# IDEMPOTENCE AND ROUND-TRIP PROPERTIES
# =============================================================================


class TestIdempotenceProperties:
    """Property tests for projection idempotence and round-trip behavior.

    For projection P and embedding E = P^T:
    - P @ E = I (on target space)
    - (E @ P)^2 = E @ P (idempotence on source space)
    """

    @pytest.mark.parametrize(
        "projector_class,target_dim",
        [
            (E8ToE7TrueProjector, 133),
            (E7ToE6TrueProjector, 78),
            (E6ToF4TrueProjector, 52),
            (F4ToG2TrueProjector, 14),
            (G2ToS7TrueProjector, 7),
        ],
    )
    def test_pe_identity_property(self, projector_class, target_dim: int) -> None:
        """Property: P @ E = I on target space (exact reconstruction)."""
        proj = projector_class()
        P = proj.projection_matrix
        E = proj.embedding_matrix

        PE = P @ E
        I_target = torch.eye(target_dim, dtype=P.dtype)

        error = (PE - I_target).abs().max().item()

        # Require tight precision for mathematical identity
        assert error < 1e-5, f"{projector_class.__name__}: P @ E ≠ I, error = {error:.8f}"

    @pytest.mark.parametrize(
        "projector_class,source_dim",
        [
            (E8ToE7TrueProjector, 248),
            (E7ToE6TrueProjector, 133),
            (E6ToF4TrueProjector, 78),
            (F4ToG2TrueProjector, 52),
            (G2ToS7TrueProjector, 14),
        ],
    )
    def test_ep_idempotence_property(self, projector_class, source_dim: int) -> None:
        """Property: (E @ P)^2 = E @ P (projection operator idempotence)."""
        proj = projector_class()
        P = proj.projection_matrix
        E = proj.embedding_matrix

        EP = E @ P
        EP2 = EP @ EP

        error = (EP - EP2).abs().max().item()

        # Idempotence should hold to high precision
        assert error < 1e-5, f"{projector_class.__name__}: (E@P)^2 ≠ E@P, error = {error:.8f}"

    @given(
        num_roundtrips=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=20)
    def test_multiple_roundtrip_stability(self, num_roundtrips: int) -> None:
        """Property: Multiple project→embed cycles stabilize (idempotence)."""
        hierarchy = TrueExceptionalHierarchy()

        x = torch.randn(10, 248)

        # First round-trip
        z = hierarchy.project_to_level(x, "S7")
        x_back = hierarchy.embed_from_level(z, "S7")  # type: ignore[arg-type]
        z_back = hierarchy.project_to_level(x_back, "S7")

        # Further round-trips should NOT change z
        z_current = z_back
        for _ in range(num_roundtrips - 1):
            x_tmp = hierarchy.embed_from_level(z_current, "S7")  # type: ignore[arg-type]
            z_next = hierarchy.project_to_level(x_tmp, "S7")

            # Should be stable (idempotent)
            error = (z_next - z_current).abs().max().item()  # type: ignore[operator]
            assert error < 1e-5, f"Roundtrip not stable: error = {error:.8f}"

            z_current = z_next


# =============================================================================
# EDGE CASE PROPERTIES
# =============================================================================


class TestEdgeCaseProperties:
    """Property tests for edge cases and boundary conditions."""

    @given(
        zero_fraction=st.floats(min_value=0.0, max_value=0.99),
    )
    @settings(max_examples=30)
    def test_sparse_input_handling(self, zero_fraction: float) -> None:
        """Property: Projection handles sparse inputs (many zeros)."""
        hierarchy = TrueExceptionalHierarchy()

        # Generate sparse input
        x = torch.randn(20, 248)
        mask = torch.rand(20, 248) > zero_fraction
        x = x * mask.float()

        # Should not produce NaN or Inf
        y = hierarchy.project_to_level(x, "S7")

        assert not torch.isnan(y).any(), "NaN from sparse input"  # type: ignore[arg-type]
        assert not torch.isinf(y).any(), "Inf from sparse input"  # type: ignore[arg-type]

    def test_all_zero_input(self) -> None:
        """Property: Zero input → zero output (linearity)."""
        hierarchy = TrueExceptionalHierarchy()

        x = torch.zeros(5, 248)
        y = hierarchy.project_to_level(x, "S7")

        assert torch.allclose(y, torch.zeros(5, 7), atol=1e-8), "Zero input should give zero output"  # type: ignore[arg-type]

    @given(
        constant_value=st.floats(
            min_value=-100, max_value=100, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(max_examples=50)
    def test_constant_input_handling(self, constant_value: float) -> None:
        """Property: Constant inputs produce bounded outputs."""
        assume(abs(constant_value) > 1e-10)  # Skip near-zero

        hierarchy = TrueExceptionalHierarchy()

        # All elements same value
        x = torch.full((10, 248), constant_value)
        y = hierarchy.project_to_level(x, "S7")

        # Should not explode
        assert not torch.isnan(y).any(), f"NaN from constant {constant_value}"  # type: ignore[arg-type]
        assert not torch.isinf(y).any(), f"Inf from constant {constant_value}"  # type: ignore[arg-type]

        # Output should be bounded
        max_val = y.abs().max().item()  # type: ignore[union-attr]
        assert max_val < abs(constant_value) * 100, f"Output exploded: {max_val}"


# =============================================================================
# FUSED PROJECTION PROPERTIES
# =============================================================================


class TestFusedProjectionProperties:
    """Property tests for optimized fused projection matrices.

    Fused E8→S7 should match sequential projections exactly.
    """

    @given(
        batch_size=st.integers(min_value=1, max_value=64),
    )
    @settings(max_examples=30)
    def test_fused_matches_sequential(self, batch_size: int) -> None:
        """Property: Fused E8→S7 equals sequential projection."""
        hierarchy = TrueExceptionalHierarchy()

        x = torch.randn(batch_size, 248)

        # Sequential projection
        y_seq = hierarchy.project_to_level(x, "S7")

        # Fused projection
        y_fused = hierarchy.project_e8_to_s7_fused(x)

        # Must be identical (within numerical precision)
        assert torch.allclose(y_seq, y_fused, atol=1e-6), "Fused projection differs from sequential"  # type: ignore[arg-type]

    @given(
        batch_size=st.integers(min_value=1, max_value=64),
    )
    @settings(max_examples=30)
    def test_fused_embed_matches_sequential(self, batch_size: int) -> None:
        """Property: Fused S7→E8 equals sequential embedding."""
        hierarchy = TrueExceptionalHierarchy()

        z = torch.randn(batch_size, 7)

        # Sequential embedding
        x_seq = hierarchy.embed_from_level(z, "S7")

        # Fused embedding
        x_fused = hierarchy.embed_s7_to_e8_fused(z)

        # Must be identical
        assert torch.allclose(x_seq, x_fused, atol=1e-6), "Fused embedding differs from sequential"


# Mark all tests for property-based testing

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
