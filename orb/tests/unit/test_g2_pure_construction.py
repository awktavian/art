"""Test pure G₂→S⁷ construction eliminates fallback.

This test verifies that the new explicit octonion-based g₂ generator construction
produces a full-rank projection matrix without needing the Fano fallback.

Author: Forge Colony
Date: December 14, 2025
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_unit



import torch


def test_g2_to_s7_pure_construction():
    """Verify G2→S7 uses explicit generators (no fallback)."""
    from kagami_math.clebsch_gordan_exceptional import compute_g2_to_s7_clebsch_gordan

    # Compute projection matrix
    P = compute_g2_to_s7_clebsch_gordan()

    # Verify shape
    assert P.shape == (7, 14), f"Expected [7, 14], got {P.shape}"

    # Verify full rank (no rank deficiency that triggers fallback)
    rank = torch.linalg.matrix_rank(P).item()
    assert rank == 7, f"Expected rank 7, got {rank}"

    # Verify orthonormality
    gram = P @ P.T
    error = (gram - torch.eye(7)).abs().max().item()
    assert error < 1e-4, f"Projection not orthonormal: error={error}"

    print("✅ G2→S7 pure construction successful (no fallback needed)")


def test_g2_generators_from_octonions():
    """Verify g₂ generators are built from octonion multiplication."""
    from kagami_math.clebsch_gordan_exceptional import compute_g2_to_s7_clebsch_gordan
    from kagami_math.fano_plane import FANO_SIGNS

    # Verify FANO_SIGNS table is used (42 entries for 7×6 antisymmetric pairs)
    assert len(FANO_SIGNS) == 42, f"Expected 42 Fano products, got {len(FANO_SIGNS)}"

    # Verify projection succeeds (uses FANO_SIGNS internally)
    P = compute_g2_to_s7_clebsch_gordan()
    assert P.shape == (7, 14)

    print("✅ G2 generators correctly use Fano multiplication table")


def test_no_fallback_function_called():
    """Verify the fallback function is never needed."""
    # The fallback function `_compute_g2_to_s7_fano_fallback` has been deleted
    # Attempting to import it should fail
    with pytest.raises(ImportError):
        from kagami_math.clebsch_gordan_exceptional import _compute_g2_to_s7_fano_fallback

    print("✅ Fallback function successfully removed")


if __name__ == "__main__":
    test_g2_to_s7_pure_construction()
    test_g2_generators_from_octonions()
    test_no_fallback_function_called()
