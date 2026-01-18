"""Root systems and coefficient generation for Clebsch-Gordan projections.

This module contains the explicit root system constructions for exceptional
Lie algebras E8, E7, E6, F4, and G2, which are used to compute the
Clebsch-Gordan projection matrices.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import combinations, product
from typing import cast

import numpy as np
import torch

logger = logging.getLogger(__name__)


# =============================================================================
# E8 ROOT SYSTEM - EXPLICIT CONSTRUCTION
# =============================================================================

# Module-level cache for E8 roots (240 roots × 8D = 7.68KB per device)
_E8_ROOTS_CACHE: dict[str, torch.Tensor] = {}


def generate_e8_roots(device: str = "cpu") -> torch.Tensor:
    """Generate all 240 roots of the E8 root system (cached per device).

    E8 roots in R^8 consist of two types:
    1. 112 roots: All permutations of (±1, ±1, 0, 0, 0, 0, 0, 0)
    2. 128 roots: All (±½, ±½, ±½, ±½, ±½, ±½, ±½, ±½) with EVEN number of minus signs

    All roots have squared length 2.

    OPTIMIZATION: Results are cached per device to avoid regeneration.
    Memory cost: ~7.68KB per device (240 × 8 × 4 bytes).

    Args:
        device: Device to place roots on ("cpu", "cuda", "cuda:0", etc.)

    Returns:
        Tensor of shape [240, 8] containing all E8 roots
    """
    if device not in _E8_ROOTS_CACHE:
        # Use kagami_math's own E8 root generation (standalone, no circular deps)
        from kagami_math.dimensions import generate_e8_roots as _generate_e8_roots

        _E8_ROOTS_CACHE[device] = _generate_e8_roots().to(device)
        logger.debug(
            "✅ Generated E8 roots for device '%s' (%d roots, cached)",
            device,
            _E8_ROOTS_CACHE[device].shape[0],
        )
    return _E8_ROOTS_CACHE[device]


def generate_e8_cartan_basis() -> torch.Tensor:
    """Generate orthonormal basis for E8 Cartan subalgebra (8D).

    The Cartan subalgebra is the maximal abelian subalgebra.
    We use the standard orthonormal basis in R^8.

    Returns:
        Tensor of shape [8, 8] - orthonormal basis vectors
    """
    return torch.eye(8, dtype=torch.float32)


# =============================================================================
# E7 EMBEDDING IN E8
# =============================================================================


def get_e7_embedding_root() -> torch.Tensor:
    """Get the E8 root that defines the E7 embedding.

    E7 ⊂ E8 is constructed as the subalgebra preserving a chosen root.
    We use the standard choice: α = (1, -1, 0, 0, 0, 0, 0, 0)

    E7 roots are then all E8 roots orthogonal to α.

    Returns:
        Tensor of shape [8] - the embedding root
    """
    return torch.tensor([1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=torch.float32)


def generate_e7_roots_from_e8() -> tuple[torch.Tensor, torch.Tensor]:
    """Generate E7 roots as E8 roots orthogonal to embedding root.

    Returns:
        Tuple of (e7_roots [126, 8], complement_roots [114, 8])

    The 126 E7 roots + 7 Cartan = 133D representation.
    The 114 complement roots correspond to (56,2) and (1,3) components.
    """
    e8_roots = generate_e8_roots()
    alpha = get_e7_embedding_root()

    # E7 roots are orthogonal to alpha
    dots = torch.matmul(e8_roots, alpha)

    e7_mask = torch.abs(dots) < 1e-6
    e7_roots = e8_roots[e7_mask]
    complement_roots = e8_roots[~e7_mask]

    # Verify: E7 should have 126 roots
    if e7_roots.shape[0] != 126:
        raise RuntimeError(f"Expected 126 E7 roots, got {e7_roots.shape[0]}")

    logger.debug(f"✅ E7 embedding: {e7_roots.shape[0]} roots (orthogonal to α)")
    return e7_roots, complement_roots


def compute_e8_to_e7_projection_basis() -> torch.Tensor:
    """Compute the 7D subspace basis for E7 embedding.

    E7 sits in the orthogonal complement of the embedding root α.
    This is a 7D subspace of R^8.

    Returns:
        Tensor of shape [7, 8] - orthonormal basis for E7 Cartan
    """
    alpha = get_e7_embedding_root()
    alpha_norm = torch.norm(alpha)
    if alpha_norm < 1e-8:
        raise ValueError(
            "Cannot normalize zero embedding root in compute_e8_to_e7_projection_basis"
        )
    alpha = alpha / alpha_norm

    # Find orthonormal basis for orthogonal complement
    # Start with standard basis and Gram-Schmidt orthogonalize
    basis = torch.eye(8, dtype=torch.float32)

    # Project out alpha component from all basis vectors, then use QR for orthonormalization
    # This is more efficient than Gram-Schmidt: O(n²m) via LAPACK vs O(n³)
    V = basis - torch.outer(basis @ alpha, alpha)  # [8, 8] - remove alpha component from each row

    # Use QR decomposition to get orthonormal basis
    Q, _R = torch.linalg.qr(V.T)  # Q is [8, k] with orthonormal columns

    # Filter columns with non-zero norm (should get 7 for the orthogonal complement)
    norms = torch.norm(Q, dim=0)
    valid_mask = norms > 1e-6
    Q_valid = Q[:, valid_mask]

    if Q_valid.shape[1] < 7:
        raise ValueError(
            f"Expected 7 basis vectors in orthogonal complement, got {Q_valid.shape[1]}"
        )

    result = Q_valid[:, :7].T  # Take first 7, transpose to [7, 8]

    # Verify orthonormality
    gram = result @ result.T
    if not torch.allclose(gram, torch.eye(7), atol=1e-5):
        raise RuntimeError("Basis not orthonormal")

    return cast(torch.Tensor, result)


# =============================================================================
# E8 ADJOINT REPRESENTATION STRUCTURE
# =============================================================================


@dataclass
class E8AdjointBasis:
    """Structure of E8 adjoint representation (248D).

    The basis is organized as:
    - 8 Cartan generators (diagonal)
    - 240 root space generators (one for each root)

    Under E8 → E7 × SU(2) branching:
    - (133, 1): E7 adjoint as SU(2) singlet
        - 7 E7 Cartan
        - 126 E7 root generators
    - (56, 2): E7 fundamental ⊗ SU(2) doublet = 112D
        - 56 pairs corresponding to non-E7 roots
    - (1, 3): SU(2) triplet = 3D
        - 1 "extra" Cartan direction + 2 root generators
    """

    cartan_dim: int = 8
    root_dim: int = 240
    total_dim: int = 248

    # E7 component dimensions
    e7_cartan_dim: int = 7
    e7_root_dim: int = 126
    e7_total_dim: int = 133

    # SU(2) component dimensions
    su2_fund_dim: int = 56  # E7 fundamental representation
    su2_doublet_dim: int = 112  # 56 × 2
    su2_triplet_dim: int = 3


# =============================================================================
# E7 ROOT SYSTEM - EXPLICIT CONSTRUCTION
# =============================================================================


def generate_e7_roots() -> torch.Tensor:
    """Generate all 126 roots of the E7 root system.

    E7 roots in R^8 with constraint sum(x_i) = 0:
    1. 112 roots: All permutations of (1, -1, 0, 0, 0, 0, 0, 0) with sum=0
    2. 14 roots: (±½)^8 with even minus signs AND sum=0

    Actually, the standard E7 embedding uses 7D Cartan space.
    We embed in R^8 with the constraint x_1 + x_8 = 0.

    Returns:
        Tensor of shape [126, 8] containing all E7 roots
    """

    # E7 is a subalgebra of E8. We get E7 roots by selecting E8 roots
    # orthogonal to a specific E8 root (the embedding root).
    # This is already computed in generate_e7_roots_from_e8()
    e7_roots, _ = generate_e7_roots_from_e8()

    return e7_roots


# =============================================================================
# E6, F4, G2 ROOT SYSTEMS - TRUE CONSTRUCTION FROM E8
# =============================================================================


def generate_e6_roots_from_e8() -> tuple[torch.Tensor, torch.Tensor]:
    """Generate E6 roots by embedding in E8.

    E6 ⊂ E7 ⊂ E8. We construct E6 as roots orthogonal to TWO E8 roots.

    E8 → E6 × SU(3): The E6 roots are those E8 roots orthogonal to
    both α₁ = (1, -1, 0, 0, 0, 0, 0, 0) and α₂ = (0, 1, -1, 0, 0, 0, 0, 0)

    Returns:
        Tuple of (e6_roots [72, 8], complement_roots)
    """
    e8_roots = generate_e8_roots()

    # E6 embedding: roots orthogonal to both α₁ and α₂
    alpha1 = torch.tensor([1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=torch.float32)
    alpha2 = torch.tensor([0.0, 1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=torch.float32)

    dots1 = torch.matmul(e8_roots, alpha1)
    dots2 = torch.matmul(e8_roots, alpha2)

    e6_mask = (torch.abs(dots1) < 1e-6) & (torch.abs(dots2) < 1e-6)
    e6_roots = e8_roots[e6_mask]
    complement_roots = e8_roots[~e6_mask]

    # Verify: E6 should have 72 roots
    if e6_roots.shape[0] != 72:
        logger.warning(f"E6 roots: expected 72, got {e6_roots.shape[0]}")
    else:
        logger.debug(f"✅ E6 embedding: {e6_roots.shape[0]} roots")

    return e6_roots, complement_roots


def generate_e6_roots() -> torch.Tensor:
    """Generate E6 root system (72 roots).

    Uses the E8 embedding for consistency with the hierarchy.

    Returns:
        Tensor of shape [72, 8] - E6 roots in E8 coordinates
    """
    e6_roots, _ = generate_e6_roots_from_e8()
    return e6_roots


def generate_f4_roots() -> torch.Tensor:
    """Generate F4 root system (48 roots in R^4).

    F4 roots consist of:
    - 24 long roots: permutations of (±1, ±1, 0, 0)
    - 8 short roots: (±1, 0, 0, 0) permutations
    - 16 short roots: (±½, ±½, ±½, ±½)

    All roots normalized to have squared length 2 (for long) or 1 (for short).

    Returns:
        Tensor of shape [48, 4]
    """
    roots = []

    # Long roots: (±1, ±1, 0, 0) permutations - 24 roots
    for i, j in combinations(range(4), 2):
        for si in [-1, 1]:
            for sj in [-1, 1]:
                root = [0.0] * 4
                root[i] = si
                root[j] = sj
                roots.append(root)

    # Short roots type 1: (±1, 0, 0, 0) permutations - 8 roots
    for i in range(4):
        for s in [-1, 1]:
            root = [0.0] * 4
            root[i] = s
            roots.append(root)

    # Short roots type 2: (±½, ±½, ±½, ±½) - 16 roots
    for signs in product([-1, 1], repeat=4):
        root = [0.5 * s for s in signs]
        roots.append(root)

    f4_roots = torch.tensor(roots, dtype=torch.float32)

    # Verify: should have 48 roots
    if f4_roots.shape[0] != 48:
        raise RuntimeError(f"Expected 48 F4 roots, got {f4_roots.shape[0]}")

    logger.debug(f"✅ F4 roots: {f4_roots.shape[0]} roots in R^4")
    return f4_roots


def generate_g2_roots() -> torch.Tensor:
    """Generate G2 root system (12 roots in R^2).

    G2 is the smallest exceptional Lie algebra.
    Its roots form a hexagonal pattern with two lengths.

    Standard embedding in R^3 with x+y+z=0:
    Short roots: ±(1,-1,0), ±(1,0,-1), ±(0,1,-1) - 6 roots
    Long roots: ±(2,-1,-1), ±(-1,2,-1), ±(-1,-1,2) - 6 roots

    Returns:
        Tensor of shape [12, 3] - G2 roots in R^3 (constrained to x+y+z=0 plane).

    Note:
        G2 has rank 2, so roots are intrinsically 2D. Representing them in R^3
        with the linear constraint x+y+z=0 is a standard embedding of the
        2D root space as a plane in R^3.
    """
    # G2 in R^3 with constraint x+y+z=0
    roots = []

    # Short roots (norm² = 2)
    short = [
        [1.0, -1.0, 0.0],
        [-1.0, 1.0, 0.0],
        [1.0, 0.0, -1.0],
        [-1.0, 0.0, 1.0],
        [0.0, 1.0, -1.0],
        [0.0, -1.0, 1.0],
    ]
    roots.extend(short)

    # Long roots (norm² = 6)
    long = [
        [2.0, -1.0, -1.0],
        [-2.0, 1.0, 1.0],
        [-1.0, 2.0, -1.0],
        [1.0, -2.0, 1.0],
        [-1.0, -1.0, 2.0],
        [1.0, 1.0, -2.0],
    ]
    roots.extend(long)

    result = torch.tensor(roots, dtype=torch.float32)

    # Verify: should have 12 roots
    if result.shape[0] != 12:
        raise RuntimeError(f"Expected 12 G2 roots, got {result.shape[0]}")

    # Verify constraint: x+y+z=0
    sums = result.sum(dim=1)
    if not torch.allclose(sums, torch.zeros(12), atol=1e-6):
        raise RuntimeError("G2 roots should satisfy x+y+z=0")

    return result


# =============================================================================
# G2 FUNDAMENTAL REPRESENTATION WEIGHTS (7D)
# =============================================================================


def generate_g2_fundamental_weights() -> torch.Tensor:
    """Generate the 7 weights of the G2 7D fundamental representation.

    MATHEMATICAL FOUNDATION:
    ========================
    The 7D fundamental irrep of G2 has the weight diagram:
    - One zero weight (multiplicity 1)
    - Six non-zero weights forming a hexagon in the 2D weight space (rank 2)

    This function returns those weights in a 2D Cartan basis (rank-2),
    using a standard hexagon parameterization (up to an overall scale
    and basis choice, which are convention-dependent).

    Returns:
        Tensor of shape [7, 2] - weight vectors (rows) in a 2D Cartan basis
    """
    # Hexagon in 2D (angles 0, 60, 120, 180, 240, 300 degrees) + center.
    # Using radius=1.0 in an orthonormal 2D basis.
    r = 1.0
    s3 = float(np.sqrt(3.0))
    hexagon = [
        (r, 0.0),
        (0.5 * r, 0.5 * s3 * r),
        (-0.5 * r, 0.5 * s3 * r),
        (-r, 0.0),
        (-0.5 * r, -0.5 * s3 * r),
        (0.5 * r, -0.5 * s3 * r),
    ]
    weights = torch.tensor([(0.0, 0.0), *hexagon], dtype=torch.float32)
    return weights


__all__ = [
    "E8AdjointBasis",
    "compute_e8_to_e7_projection_basis",
    "generate_e6_roots",
    "generate_e6_roots_from_e8",
    "generate_e7_roots",
    "generate_e7_roots_from_e8",
    "generate_e8_cartan_basis",
    "generate_e8_roots",
    "generate_f4_roots",
    "generate_g2_fundamental_weights",
    "generate_g2_roots",
    "get_e7_embedding_root",
]
