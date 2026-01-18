"""Fano Plane - The multiplication structure of octonions.

NOTE (Dec 13, 2025):
This file was moved from `kagami.core.world_model.quantum.fano_plane` to
`kagami.math.fano_plane` to break cross-layer cycles:
- math/events/unified_agents/active_inference frequently depend on Fano lines
- they must not depend on the world-model package to access pure math constants

The Fano plane is a finite projective plane with 7 points and 7 lines.
It encodes the multiplication table of the 7 imaginary octonion units.

MATHEMATICAL FOUNDATION (Dec 14, 2025 - CORRECTED):
====================================================
The Fano lines encode the multiplication table of octonion imaginary units.
This implementation uses the CAYLEY-DICKSON construction with quaternion split:
    First quaternion:  [e₀, e₁, e₂, e₃]
    Second quaternion: [e₄, e₅, e₆, e₇]

The Cayley-Dickson formula (a,b) × (c,d) = (ac - d̄b, da + bc̄) uniquely
determines the multiplication table. This gives a specific sign convention.

For each line {i,j,k}, the multiplication rules are:
    e_i × e_j = +e_k  (positive for cyclic order on line)
    e_j × e_k = +e_i  (cyclic continuation)
    e_k × e_i = +e_j  (cyclic continuation)
    Reverse order gives negative sign (anti-commutativity)

Note: There exist 480 equivalent octonion algebras (G₂ automorphisms) differing
by relabeling. Our choice is fixed by the Cayley-Dickson split. The G₂ 3-form
φ = e^{123} + e^{145} + e^{167} + e^{246} - e^{257} - e^{347} - e^{356}
defines a DIFFERENT labeling. Both are mathematically valid.

References:
- Baez (2002), "The Octonions", Bull. AMS 39(2) - Table 2
- Conway & Smith (2003), "On Quaternions and Octonions"
- Dray & Manogue (2015), "The Geometry of the Octonions"
"""

# 7 Fano lines from CAYLEY-DICKSON construction with split [e₀-e₃|e₄-e₇]
# Each tuple (i, j, k) represents imaginary units where e_i × e_j = +e_k
# The ordering is chosen so that the CYCLIC product is POSITIVE
# Index 1-7 corresponds to octonion imaginaries e₁...e₇
#
# These lines are EXTRACTED from the Cayley-Dickson multiplication formula,
# ensuring perfect consistency with OctonionManifold.multiply()

FANO_LINES = [
    (1, 2, 3),  # e₁ × e₂ = +e₃  (from +e^{123})
    (1, 4, 5),  # e₁ × e₄ = +e₅  (from +e^{145})
    (1, 7, 6),  # e₁ × e₇ = +e₆  (Cayley-Dickson with split [e0-e3|e4-e7])
    (2, 4, 6),  # e₂ × e₄ = +e₆  (from +e^{246})
    (2, 5, 7),  # e₂ × e₅ = +e₇  (Cayley-Dickson with split [e0-e3|e4-e7])
    (3, 4, 7),  # e₃ × e₄ = +e₇  (Cayley-Dickson with split [e0-e3|e4-e7])
    (3, 6, 5),  # e₃ × e₆ = +e₅  (Cayley-Dickson with split [e0-e3|e4-e7])
]

# Signs for multiplication table
# Dictionary: (i, j) -> (result_index, sign)
# Positive sign for cyclic order on line, negative for anticyclic
FANO_SIGNS: dict[tuple[int, int], tuple[int, int]] = {}

# Build complete multiplication table from Fano lines
for _line_idx, (i, j, k) in enumerate(FANO_LINES):
    # Forward cyclic: e_i × e_j = +e_k
    FANO_SIGNS[(i, j)] = (k, 1)
    FANO_SIGNS[(j, k)] = (i, 1)
    FANO_SIGNS[(k, i)] = (j, 1)

    # Reverse anticyclic: e_j × e_i = -e_k
    FANO_SIGNS[(j, i)] = (k, -1)
    FANO_SIGNS[(k, j)] = (i, -1)
    FANO_SIGNS[(i, k)] = (j, -1)


def get_fano_lines_zero_indexed() -> list[tuple[int, int, int]]:
    """Get Fano lines with 0-based indexing for tensor operations.

    The canonical FANO_LINES uses 1-based indexing (e₁...e₇) matching
    mathematical convention. This helper converts to 0-based indexing
    for use in tensor operations where indices start at 0.
    """
    # Explicit cast to tuple[int, int, int] for type safety
    return [(line[0] - 1, line[1] - 1, line[2] - 1) for line in FANO_LINES]


def get_fano_line_for_pair(i: int, j: int) -> tuple[int, int, int] | None:
    """Find the Fano line containing both indices i and j (1-indexed)."""

    if i == j or not (1 <= i <= 7 and 1 <= j <= 7):
        return None

    for line in FANO_LINES:
        line_set = set(line)
        if i in line_set and j in line_set:
            return line

    return None  # Should never happen for valid Fano plane


def verify_fano_plane() -> bool:
    """Verify that FANO_LINES forms a valid Fano plane."""

    # Check 7 lines with 3 points each
    assert len(FANO_LINES) == 7, f"Expected 7 lines, got {len(FANO_LINES)}"
    for line in FANO_LINES:
        assert len(line) == 3, f"Line {line} should have 3 elements"
        assert len(set(line)) == 3, f"Line {line} has duplicates"

    # Check each pair appears exactly once
    pair_count: dict[tuple[int, int], int] = {}
    for line in FANO_LINES:
        for idx_a in range(3):
            for idx_b in range(idx_a + 1, 3):
                # Explicit 2-tuple construction for type safety
                a, b = line[idx_a], line[idx_b]
                pair = (min(a, b), max(a, b))
                pair_count[pair] = pair_count.get(pair, 0) + 1

    # Should have exactly 21 pairs (C(7,2) = 21)
    assert len(pair_count) == 21, f"Expected 21 pairs, got {len(pair_count)}"
    for pair, count in pair_count.items():
        assert count == 1, f"Pair {pair} appears {count} times"

    return True


# Verify on import
_valid = verify_fano_plane()


__all__ = [
    "FANO_LINES",
    "FANO_SIGNS",
    "get_fano_line_for_pair",
    "get_fano_lines_zero_indexed",
    "verify_fano_plane",
]
