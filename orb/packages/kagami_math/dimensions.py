"""Centralized Dimension Configuration for K OS.

This module is the SINGLE SOURCE OF TRUTH for all dimension-related constants.
Import from here instead of hardcoding magic numbers.

MATHEMATICAL CONSTRAINTS (FIXED - Cannot be scaled):
====================================================
- Crystal core: G₂ = 14D (automorphisms of octonions)
- Manifold: H¹⁴ × S⁷ = 21D (14 hyperbolic + 7 intrinsic S⁷)
- S⁷ intrinsic: 7D (imaginary octonions e₁...e₇)
- S⁷ embedding: 8D (ℝ⁸ coordinates for actual computation)
- E₈ lattice: 8D with 240 roots (Viazovska optimal packing)
- Exceptional hierarchy: G₂(14) ⊂ F₄(52) ⊂ E₆(78) ⊂ E₇(133) ⊂ E₈(248)

SCALABLE PARAMETERS:
====================
- Bulk dimension: Input/output width (configurable via KAGAMI_BULK_DIM)

Created: November 30, 2025
Status: Canonical - All dimension constants derive from here
"""

from __future__ import annotations

import logging
import os
from enum import IntEnum
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch

logger = logging.getLogger(__name__)


# =============================================================================
# EXCEPTIONAL LIE ALGEBRA DIMENSIONS (FIXED - DO NOT MODIFY)
# =============================================================================


class ExceptionalLevel(IntEnum):
    """Levels in the exceptional Lie algebra hierarchy."""

    G2 = 0  # Aut(𝕆) - 14D
    MANIFOLD = 1  # H¹⁴ × S⁷ - 21D
    F4 = 2  # Aut(J₃(𝕆)) - 52D
    E6 = 3  # Structure group - 78D
    E7 = 4  # Extended structure - 133D
    E8 = 5  # Complete lattice - 248D


# Exceptional Lie Algebra Dimensions (mathematically fixed)
G2_DIM = 14  # Automorphisms of octonions (12 roots + 2 Cartan)
F4_DIM = 52  # Albert algebra automorphisms (48 roots + 4 Cartan)
E6_DIM = 78  # Structure group (72 roots + 6 Cartan)
E7_DIM = 133  # Freudenthal triple system (126 roots + 7 Cartan)
E8_DIM = 248  # Complete lattice (240 roots + 8 Cartan)

# Manifold Dimensions (mathematically fixed)
HYPERBOLIC_DIM = 14  # H¹⁴ (matches G₂)
S7_INTRINSIC_DIM = 7  # S⁷ intrinsic dimension (imaginary octonions e₁...e₇)
OCTONION_EMBEDDING_DIM = 8  # ℝ⁸ embedding for actual octonion operations
MANIFOLD_DIM = HYPERBOLIC_DIM + S7_INTRINSIC_DIM  # 21D (NOT 22!)

# Core State Dimensions (derived, fixed)
CRYSTAL_DIM = G2_DIM  # 14D (bottleneck)
SHELL_DIM = E8_DIM  # 248D (E₈ Lie algebra)
E8_ROOTS = 240  # E₈ lattice kissing number

# Root counts for each level
ROOT_COUNTS = {
    ExceptionalLevel.G2: 12,
    ExceptionalLevel.F4: 48,
    ExceptionalLevel.E6: 72,
    ExceptionalLevel.E7: 126,
    ExceptionalLevel.E8: 240,
}


# =============================================================================
# E₈ ROOT GENERATION (CANONICAL SOURCE)
# =============================================================================

# Cached E₈ roots tensor (singleton)
_E8_ROOTS_CACHED: torch.Tensor | None = None


def generate_e8_roots() -> torch.Tensor:
    """Generate the 240 E₈ root vectors (8D, norm √2).

    CANONICAL IMPLEMENTATION - All other modules should import from here.

    E₈ roots come in two types (Conway & Sloane, 1999):
    1. Type 1 (112 roots): All permutations of (±1, ±1, 0, 0, 0, 0, 0, 0)
    2. Type 2 (128 roots): (±½)⁸ with even number of minus signs

    Mathematical Properties:
    - All 240 roots have norm √2
    - Viazovska (2016): This is optimal sphere packing in 8D (Fields Medal)
    - Kissing number 240 (each root touches 240 others)

    Returns:
        [240, 8] tensor of E₈ roots, each with norm √2
    """
    from itertools import combinations

    import torch

    roots = []

    # Type 1: (±1, ±1, 0, 0, 0, 0, 0, 0) — 112 roots
    # Choose 2 positions from 8, each with ±1
    for i, j in combinations(range(8), 2):
        for sign_i in [1, -1]:
            for sign_j in [1, -1]:
                root = [0.0] * 8
                root[i] = float(sign_i)
                root[j] = float(sign_j)
                roots.append(root)

    # Type 2: (±½)⁸ with even minus count — 128 roots
    for bits in range(256):
        signs = [(bits >> i) & 1 for i in range(8)]
        if sum(signs) % 2 == 0:  # Even parity
            root = [0.5 if s == 0 else -0.5 for s in signs]
            roots.append(root)

    tensor = torch.tensor(roots, dtype=torch.float32)

    # Verify count
    assert tensor.shape == (240, 8), f"Expected [240, 8], got {tensor.shape}"
    # Verify norm: all roots should have squared length 2
    sq_lengths = (tensor**2).sum(dim=1)
    assert torch.allclose(
        sq_lengths,
        torch.full_like(sq_lengths, 2.0),
        atol=1e-6,
    ), "E8 roots should have squared length 2"

    return tensor


def get_e8_roots(device: str = "cpu") -> torch.Tensor:
    """Get cached E₈ roots tensor (singleton pattern).

    Args:
        device: Target device ("cpu", "cuda", "mps")

    Returns:
        [240, 8] E₈ roots tensor on specified device
    """

    global _E8_ROOTS_CACHED
    if _E8_ROOTS_CACHED is None:
        _E8_ROOTS_CACHED = generate_e8_roots()
    return _E8_ROOTS_CACHED.to(device)


# Lie algebra dimensions (roots + Cartan rank)
LIE_ALGEBRA_DIMENSIONS = {
    ExceptionalLevel.G2: G2_DIM,
    ExceptionalLevel.MANIFOLD: MANIFOLD_DIM,
    ExceptionalLevel.F4: F4_DIM,
    ExceptionalLevel.E6: E6_DIM,
    ExceptionalLevel.E7: E7_DIM,
    ExceptionalLevel.E8: E8_DIM,
}

# Cartan subalgebra ranks
CARTAN_RANKS = {
    ExceptionalLevel.G2: 2,
    ExceptionalLevel.F4: 4,
    ExceptionalLevel.E6: 6,
    ExceptionalLevel.E7: 7,
    ExceptionalLevel.E8: 8,
}


# =============================================================================
# CONFIGURABLE BULK DIMENSION
# =============================================================================

# Default bulk dimension (can be overridden via environment)
DEFAULT_BULK_DIM = 512

# Environment variable name for bulk dimension
BULK_DIM_ENV_VAR = "KAGAMI_BULK_DIM"


def get_bulk_dim() -> int:
    """Get the configured bulk dimension.

    Priority:
    1. Environment variable KAGAMI_BULK_DIM
    2. Default value (512)

    Returns:
        Configured bulk dimension
    """
    return int(os.getenv(BULK_DIM_ENV_VAR, str(DEFAULT_BULK_DIM)))


def get_embedding_dim() -> int:
    """Get the embedding dimension (alias for bulk_dim).

    This is provided for compatibility with embedding services
    that previously used KAGAMI_EMBED_DIM.

    Returns:
        Configured embedding/bulk dimension
    """
    # Check both env vars for backward compatibility
    embed_dim = os.getenv("KAGAMI_EMBED_DIM")
    if embed_dim:
        logger.warning("KAGAMI_EMBED_DIM is deprecated. Use KAGAMI_BULK_DIM instead.")
        return int(embed_dim)
    return get_bulk_dim()


# =============================================================================
# DIMENSION HIERARCHY GENERATORS
# =============================================================================

# Fixed hierarchy levels (without bulk) in ascending order
EXCEPTIONAL_HIERARCHY_FIXED = (G2_DIM, MANIFOLD_DIM, F4_DIM, E6_DIM, E7_DIM, E8_DIM)


@lru_cache(maxsize=32)
def get_layer_dimensions(bulk_dim: int | None = None, mode: str = "algebraic") -> tuple[int, ...]:
    """Get the complete layer dimension hierarchy.

    OPTIMAL (Dec 6, 2025): Uses ALGEBRAIC dimensions as waypoints.

    The exceptional Lie algebra hierarchy has deep mathematical meaning:
    - G₂ (14D): Automorphisms of octonions (Fano plane structure)
    - F₄ (52D): Automorphisms of Albert algebra (octonionic matrices)
    - E₆ (78D): Structure group of octonionic projective plane
    - E₇ (133D): Freudenthal triple system
    - E₈ (248D): Complete lattice (optimal sphere packing, Viazovska)
    - H¹⁴×S⁷ (21D): Manifold dimension (hyperbolic + sphere)

    Using these dimensions ensures:
    1. Natural projection onto Lie algebra subspaces
    2. Exact Fano plane colony coordination
    3. Equivariant operations leverage group structure
    4. E8 root lattice alignment at bottleneck

    Args:
        bulk_dim: Bulk dimension. If None, uses KAGAMI_BULK_DIM env var or default.
        mode: "algebraic" (default, recommended), "geometric", or "hybrid"

    Returns:
        Tuple of dimensions in encoder order (bulk first, crystal last)
        Algebraic example: (512, 248, 133, 78, 52, 21, 14)
    """
    import math

    if bulk_dim is None:
        bulk_dim = get_bulk_dim()

    # Target bottleneck is always G2_DIM = 14
    target_dim = G2_DIM

    # Algebraic waypoints in descending order (exceptional Lie algebra dimensions)
    # E8 → E7 → E6 → F4 → Manifold → G2
    ALGEBRAIC_WAYPOINTS = [E8_DIM, E7_DIM, E6_DIM, F4_DIM, MANIFOLD_DIM, G2_DIM]

    if mode == "algebraic":
        # ALGEBRAIC COMPRESSION (OPTIMAL)
        # Uses exceptional Lie algebra dimensions directly
        # This preserves the mathematical structure for equivariant operations
        #
        # Only adds geometric intermediates when ratio > 3x to avoid
        # gradient flow issues, while preserving algebraic meaning

        dims = [bulk_dim]
        current = bulk_dim

        # Add algebraic waypoints that fit between bulk and target
        for waypoint in ALGEBRAIC_WAYPOINTS:
            if waypoint < current:
                gap_ratio = current / waypoint
                # Only add intermediate if gap is VERY large (>3x)
                # This preserves algebraic structure while avoiding huge jumps
                if gap_ratio > 3.0:
                    mid = int(math.sqrt(current * waypoint))
                    dims.append(mid)
                dims.append(waypoint)
                current = waypoint

        # Ensure we end at G2
        if dims[-1] != G2_DIM:
            dims.append(G2_DIM)

        return tuple(dims)

    elif mode == "geometric":
        # GEOMETRIC COMPRESSION (smooth but loses algebra)
        # Use constant compression ratio for smooth gradient flow

        if bulk_dim <= 128:
            n_steps = 3
        elif bulk_dim <= 256:
            n_steps = 4
        elif bulk_dim <= 512:
            n_steps = 6
        elif bulk_dim <= 1024:
            n_steps = 7
        else:
            n_steps = 8

        ratio = (bulk_dim / target_dim) ** (1.0 / n_steps)

        dims = [bulk_dim]
        current = bulk_dim
        for _ in range(n_steps - 1):
            current = max(target_dim, int(current / ratio))
            if current > target_dim:
                dims.append(current)
        dims.append(target_dim)

        return tuple(dims)

    elif mode == "hybrid":
        # HYBRID: Algebraic waypoints with geometric smoothing
        # Adds intermediate steps when ratio > 2.0x

        dims = [bulk_dim]
        current = bulk_dim

        for waypoint in ALGEBRAIC_WAYPOINTS:
            if waypoint < current:
                gap_ratio = current / waypoint
                # Add intermediate geometric step if gap is too large
                if gap_ratio > 2.0:
                    mid = int(math.sqrt(current * waypoint))
                    if mid > waypoint + 10 and mid < current - 10:
                        dims.append(mid)
                dims.append(waypoint)
                current = waypoint

        return tuple(dims)

    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'algebraic', 'geometric', or 'hybrid'")


def get_matryoshka_dimensions(bulk_dim: int | None = None) -> tuple[int, ...]:
    """Get Matryoshka-compatible dimensions in ascending order.

    Args:
        bulk_dim: Bulk dimension. If None, uses KAGAMI_BULK_DIM env var or default.

    Returns:
        Tuple of dimensions in ascending order (crystal first, bulk last)
        Example: (14, 21, 52, 78, 133, 248, 512)
    """
    if bulk_dim is None:
        bulk_dim = get_bulk_dim()

    # Always include full exceptional hierarchy plus bulk
    return (G2_DIM, MANIFOLD_DIM, F4_DIM, E6_DIM, E7_DIM, E8_DIM, bulk_dim)


def get_exceptional_dimensions_without_bulk() -> tuple[int, ...]:
    """Get exceptional dimensions without bulk (for internal math operations).

    Returns:
        (14, 21, 52, 78, 133, 248) - fixed by Lie algebra theory
    """
    return EXCEPTIONAL_HIERARCHY_FIXED


def get_exceptional_dimensions(
    include_bulk: bool = True, bulk_dim: int | None = None
) -> tuple[int, ...]:
    """Get exceptional dimensions with optional bulk.

    Args:
        include_bulk: Whether to include bulk dimension
        bulk_dim: Custom bulk dimension (uses KAGAMI_BULK_DIM if None)

    Returns:
        Tuple of exceptional dimensions
    """
    if not include_bulk:
        return EXCEPTIONAL_HIERARCHY_FIXED

    if bulk_dim is None:
        bulk_dim = get_bulk_dim()

    return (*EXCEPTIONAL_HIERARCHY_FIXED, bulk_dim)


# =============================================================================
# VALIDATION
# =============================================================================


def validate_bulk_dim(bulk_dim: int) -> None:
    """Validate that bulk dimension is acceptable.

    Args:
        bulk_dim: Dimension to validate

    Raises:
        ValueError: If bulk_dim is invalid
    """
    if bulk_dim < 64:
        raise ValueError(f"bulk_dim must be >= 64, got {bulk_dim}")
    if bulk_dim > 4096:
        logger.warning(f"bulk_dim={bulk_dim} is very large, may cause memory issues")


def is_exceptional_dimension(dim: int) -> bool:
    """Check if a dimension is in the exceptional hierarchy.

    Args:
        dim: Dimension to check

    Returns:
        True if dim is G₂, F₄, E₆, E₇, E₈, or manifold dimension
    """
    return dim in EXCEPTIONAL_HIERARCHY_FIXED


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "BULK_DIM_ENV_VAR",
    "CARTAN_RANKS",
    "CRYSTAL_DIM",
    # Configurable Dimension
    "DEFAULT_BULK_DIM",
    "E6_DIM",
    "E7_DIM",
    "E8_DIM",
    "E8_ROOTS",
    # Dimension Generators
    "EXCEPTIONAL_HIERARCHY_FIXED",
    "F4_DIM",
    # Fixed Mathematical Constants
    "G2_DIM",
    "HYPERBOLIC_DIM",
    "LIE_ALGEBRA_DIMENSIONS",
    "MANIFOLD_DIM",
    "OCTONION_EMBEDDING_DIM",
    # Root/Cartan Info
    "ROOT_COUNTS",
    "S7_INTRINSIC_DIM",
    "SHELL_DIM",
    # Exceptional Level Enum
    "ExceptionalLevel",
    # E₈ Root Generation (CANONICAL)
    "generate_e8_roots",
    "get_bulk_dim",
    "get_e8_roots",
    "get_embedding_dim",
    "get_exceptional_dimensions",
    "get_exceptional_dimensions_without_bulk",
    "get_layer_dimensions",
    "get_matryoshka_dimensions",
    "is_exceptional_dimension",
    # Validation
    "validate_bulk_dim",
]


# =============================================================================
# INITIALIZATION LOG
# =============================================================================

# Log the configured bulk dimension on import (only once)
_bulk_dim = get_bulk_dim()
if _bulk_dim != DEFAULT_BULK_DIM and not hasattr(logger, "_bulk_dim_logged"):
    logger.info(f"📐 Bulk dimension configured: {_bulk_dim}D (via {BULK_DIM_ENV_VAR})")
    logger._bulk_dim_logged = True  # type: ignore[attr-defined]
