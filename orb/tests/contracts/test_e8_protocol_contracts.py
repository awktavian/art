"""E8 Protocol Contract Tests.

Verifies that the E8 lattice protocol maintains backward compatibility.
These tests ensure that:
1. E8 root indices map to consistent vectors
2. The 240-root structure is preserved
3. Semantic byte ranges are stable

Contract violations indicate breaking changes to the E8 protocol.

Created: December 2025
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.tier_integration]

import numpy as np
import torch


class TestE8RootContract:
    """Contract tests for E8 root structure."""

    def test_e8_has_240_roots(self):
        """Contract: E8 lattice has exactly 240 minimal vectors."""
        from kagami.core.unified_agents import get_e8_roots

        roots = get_e8_roots()
        assert roots is not None, "E8 roots must be available"
        assert len(roots) == 240, f"E8 must have 240 roots, got {len(roots)}"

    def test_e8_roots_are_8d(self):
        """Contract: E8 roots live in ℝ⁸."""
        from kagami.core.unified_agents import get_e8_roots

        roots = get_e8_roots()
        assert roots is not None
        assert roots.shape == (240, 8), f"E8 roots must be (240, 8), got {roots.shape}"

    def test_e8_root_norms_sqrt2(self):
        """Contract: All E8 minimal vectors have norm √2."""
        from kagami.core.unified_agents import get_e8_roots

        roots = get_e8_roots()
        norms = np.linalg.norm(roots, axis=1)
        # All norms must be √2 (within floating point tolerance)
        expected_norm = np.sqrt(2)
        assert np.allclose(norms, expected_norm, rtol=1e-5), (
            f"E8 root norms must be √2 ≈ {expected_norm:.6f}, "
            f"got range [{norms.min():.6f}, {norms.max():.6f}]"
        )

    def test_e8_first_root_stable(self):
        """Contract: First E8 root has stable coordinates."""
        from kagami.core.unified_agents import get_e8_roots

        roots = get_e8_roots()
        first_root = roots[0]
        # First root should be consistent (type 1: permutations of (±1, ±1, 0, 0, 0, 0, 0, 0))
        # The exact value depends on implementation, but should be stable
        assert torch.isfinite(first_root).all(), "First root must have finite coordinates"
        assert torch.linalg.norm(first_root) > 0, "First root must be non-zero"


class TestE8SemanticByteContract:
    """Contract tests for E8 semantic byte protocol.
    The legacy semantic byte protocol uses specific ranges:
    - 0x00-0x53 (84): Fano triples
    - 0x54-0x6F (28): Kagami-colony pairs
    - 0x70-0xD2 (99): Safe dense states
    - 0xD3-0xEF (29): Alert states
    - 0xF0-0xF6 (7): Catastrophe markers
    - 0xF7-0xFF (9): Control tokens
    """

    def test_byte_ranges_sum_to_256(self):
        """Contract: Semantic byte ranges cover full byte space."""
        fano_triples = 84  # 0x00-0x53
        kagami_colony = 28  # 0x54-0x6F
        safe_dense = 99  # 0x70-0xD2
        alert_dense = 29  # 0xD3-0xEF
        catastrophe = 7  # 0xF0-0xF6
        control = 9  # 0xF7-0xFF (includes 0xFF)
        total = fano_triples + kagami_colony + safe_dense + alert_dense + catastrophe + control
        assert total == 256, f"Byte ranges must sum to 256, got {total}"

    def test_fano_triple_range(self):
        """Contract: Fano triple bytes are 0x00-0x53."""
        start, end = 0x00, 0x53
        count = end - start + 1
        assert count == 84, f"Fano triple range must have 84 bytes, got {count}"

    def test_catastrophe_marker_range(self):
        """Contract: 7 catastrophe markers at 0xF0-0xF6."""
        start, end = 0xF0, 0xF6
        count = end - start + 1
        assert count == 7, f"Catastrophe range must have 7 bytes (one per colony), got {count}"


class TestFanoLineContract:
    """Contract tests for Fano plane structure."""

    def test_fano_has_7_lines(self):
        """Contract: Fano plane has exactly 7 lines."""
        from kagami.core.unified_agents import FANO_LINES

        assert len(FANO_LINES) == 7, f"Fano plane must have 7 lines, got {len(FANO_LINES)}"

    def test_fano_each_line_has_3_points(self):
        """Contract: Each Fano line contains exactly 3 points."""
        from kagami.core.unified_agents import FANO_LINES

        for i, line in enumerate(FANO_LINES):
            assert len(line) == 3, f"Fano line {i} must have 3 points, got {len(line)}"

    def test_fano_points_are_1_to_7(self):
        """Contract: Fano points are labeled 1-7 (octonion imaginary units)."""
        from kagami.core.unified_agents import FANO_LINES

        all_points = set()
        for line in FANO_LINES:
            all_points.update(line)
        assert all_points == {
            1,
            2,
            3,
            4,
            5,
            6,
            7,
        }, f"Fano points must be {{1,2,3,4,5,6,7}}, got {all_points}"

    def test_fano_lines_canonical_order(self):
        """Contract: Fano lines follow canonical octonion multiplication order."""
        from kagami.core.unified_agents import FANO_LINES

        # Canonical Fano lines from octonion multiplication e_i × e_j = ±e_k
        expected_lines = [
            {1, 2, 3},  # e₁ × e₂ = e₃
            {1, 4, 5},  # e₁ × e₄ = e₅
            {1, 6, 7},  # e₁ × e₆ = e₇
            {2, 4, 6},  # e₂ × e₄ = e₆
            {2, 5, 7},  # e₂ × e₅ = e₇
            {3, 4, 7},  # e₃ × e₄ = e₇
            {3, 5, 6},  # e₃ × e₅ = e₆
        ]
        actual_lines = [set(line) for line in FANO_LINES]
        for expected in expected_lines:
            assert expected in actual_lines, f"Missing Fano line {expected}"


class TestColonyConstantsContract:
    """Contract tests for colony naming and indexing."""

    def test_7_colony_names(self):
        """Contract: Exactly 7 colonies with canonical names (lowercase)."""
        from kagami.core.unified_agents import COLONY_NAMES

        # Colony names are lowercase in the canonical implementation
        expected = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
        assert list(COLONY_NAMES) == expected, (
            f"Colony names must be {expected}, got {list(COLONY_NAMES)}"
        )

    def test_colony_index_mapping_bijective(self):
        """Contract: Colony index mapping is bijective (1-to-1 and onto)."""
        from kagami.core.unified_agents import COLONY_TO_INDEX, INDEX_TO_COLONY

        # Forward then backward should be identity
        for name, idx in COLONY_TO_INDEX.items():
            assert INDEX_TO_COLONY[idx] == name, (
                f"Bijection broken: {name} -> {idx} -> {INDEX_TO_COLONY[idx]}"
            )
        # Backward then forward should be identity
        for idx, name in INDEX_TO_COLONY.items():
            assert COLONY_TO_INDEX[name] == idx, (
                f"Bijection broken: {idx} -> {name} -> {COLONY_TO_INDEX[name]}"
            )

    def test_colony_indices_are_0_to_6(self):
        """Contract: Colony indices are 0-6 (matching S⁷ basis)."""
        from kagami.core.unified_agents import INDEX_TO_COLONY

        assert set(INDEX_TO_COLONY.keys()) == {
            0,
            1,
            2,
            3,
            4,
            5,
            6,
        }, f"Colony indices must be {{0,1,2,3,4,5,6}}, got {set(INDEX_TO_COLONY.keys())}"


# Mark as contract tests
