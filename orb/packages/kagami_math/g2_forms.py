"""G₂ Differential Forms - Pure Mathematical Module.

This module provides the fundamental G₂ 3-form φ and 4-form ψ in the canonical basis,
extracted from world_model to establish proper dependency hierarchy.

MATHEMATICAL FOUNDATIONS:
========================
G₂ is the 14-dimensional exceptional Lie group, the automorphism group of the octonions.
Its defining structure is encoded in two differential forms on ℝ⁷:

- φ: The associative 3-form (Λ³₁)
- ψ: The coassociative 4-form (Λ⁴₁), the Hodge dual ψ = *φ

These forms satisfy:
- dφ = 0 (φ is closed)
- d*φ = 0 (φ is co-closed)
- φ ∧ *φ = 7 vol (normalization condition)

The 3-form φ encodes the octonion multiplication table:
    (x × y)ₖ = φᵢⱼₖ xᵢ yⱼ

CANONICAL EXPRESSION:
====================
φ = e¹²³ + e¹⁴⁵ + e¹⁶⁷ + e²⁴⁶ - e²⁵⁷ - e³⁴⁷ - e³⁵⁶

where eⁱʲᵏ denotes the basis 3-form dxⁱ ∧ dxʲ ∧ dxᵏ.

OCTONION CONVENTION NOTE (December 2025):
=========================================
This module uses the G₂ 3-form convention for octonion multiplication, which is the
CANONICAL convention from differential geometry (Bryant 1987, Karigiannis 2009).

Note: fano_plane.py uses the Cayley-Dickson convention, which gives a DIFFERENT
but EQUIVALENT octonion algebra (related by a G₂ automorphism). Both are valid.

For Lie algebra computations (E₈→E₇→E₆→F₄→G₂ cascade), this module's convention
is used to maintain consistency with the root system constructions.

REFERENCES:
===========
- Bryant, "Some remarks on G₂-structures" (2005)
- Karigiannis, "Flows of G₂-structures" (2009)
- Baez, "The Octonions" (2002)

Created: December 14, 2025 (extracted from g2_exact.py)
Purpose: Break circular dependency (math should not depend on world_model)
"""

from __future__ import annotations

from typing import cast

import torch
import torch.nn as nn


def _phi_psi_standard(
    device: torch.device, dtype: torch.dtype
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return (φ, ψ) tensors in the canonical basis.

    φ indices: [i,j,k] fully antisymmetric
    ψ indices: [i,j,k,l] fully antisymmetric, ψ = *φ

    Returns:
        (phi, psi): The G₂ 3-form and 4-form tensors
    """
    phi = torch.zeros(7, 7, 7, device=device, dtype=dtype)
    # φ = e^{123} + e^{145} + e^{167} + e^{246} - e^{257} - e^{347} - e^{356}
    triples = [
        (0, 1, 2, +1),
        (0, 3, 4, +1),
        (0, 5, 6, +1),
        (1, 3, 5, +1),
        (1, 4, 6, -1),
        (2, 3, 6, -1),
        (2, 4, 5, -1),
    ]
    for i, j, k, s in triples:
        phi[i, j, k] = s
        phi[j, k, i] = s
        phi[k, i, j] = s
        phi[i, k, j] = -s
        phi[j, i, k] = -s
        phi[k, j, i] = -s

    # ψ = *φ = e^{4567} + e^{2367} + e^{2345} + e^{1357} - e^{1346} - e^{1256} - e^{1247}
    psi = torch.zeros(7, 7, 7, 7, device=device, dtype=dtype)
    quads = [
        (3, 4, 5, 6, +1),
        (1, 2, 5, 6, +1),
        (1, 2, 3, 4, +1),
        (0, 2, 5, 6, +1),
        (0, 2, 3, 5, -1),
        (0, 1, 4, 5, -1),
        (0, 1, 3, 6, -1),
    ]
    for a, b, c, d, s in quads:
        # Set all permutations with sign
        idxs = [a, b, c, d]
        from itertools import permutations

        for perm in set(permutations(idxs, 4)):
            # Sign of permutation
            sign = _perm_sign(perm, idxs)
            psi[perm[0], perm[1], perm[2], perm[3]] = s * sign

    return phi, psi


def _perm_sign(p: tuple[int, ...], base: list[int]) -> int:
    """Compute sign of permutation mapping base ordering to p.

    The sign is determined by counting inversions after mapping values
    to their positions in the base sequence. This is necessary when
    base is not [0, 1, 2, ...].

    Args:
        p: Permutation tuple (contains same values as base, reordered)
        base: Base ordering (defines the identity permutation)

    Returns:
        +1 for even permutation, -1 for odd permutation
    """
    # Map values to their positions in base
    # e.g., base=[3,4,5,6], p=(4,3,6,5) → positions=[1,0,3,2]
    value_to_pos = {v: i for i, v in enumerate(base)}
    positions = [value_to_pos[v] for v in p]

    # Count inversions in the position sequence
    sign = 1
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            if positions[i] > positions[j]:
                sign *= -1
    return sign


class G2PhiPsi(nn.Module):
    """G₂ 3-form φ and 4-form ψ with geometric operations.

    This module stores the canonical G₂ forms and provides:
    - Im(𝕆) cross product: x × y via φ
    - T operator on 2-forms: T(α) = *(φ ∧ α) = (1/2) ψ · α
    - Projection of 2-forms: Λ² = Λ²₇ ⊕ Λ²₁₄

    All operations use FIXED mathematical coefficients. NO learned parameters.
    """

    def __init__(
        self, device: torch.device | None = None, dtype: torch.dtype | None = None
    ) -> None:
        """Initialize G₂ forms.

        Args:
            device: Target device (defaults to CPU, moves with .to())
            dtype: Data type (defaults to default dtype)
        """
        super().__init__()
        dt = dtype or torch.get_default_dtype()
        # Build on CPU (register_buffer moves with .to())
        phi, psi = _phi_psi_standard(torch.device("cpu"), dt)
        self.register_buffer("phi", phi)
        self.register_buffer("psi", psi)

    def _ensure_device(self, x: torch.Tensor) -> None:
        """Ensure buffers are on the same device as input.

        Args:
            x: Input tensor
        """
        # Fast path: same device (no-op)
        if self.phi.device == x.device:
            return
        # Slow path: move once (subsequent calls hit fast path)
        self.to(x.device)

    def cross(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        """Im(𝕆) cross product x×y via φ.

        Mathematical formula:
            (x × y)ₖ = φᵢⱼₖ xᵢ yⱼ

        Args:
            x, y: [..., 7] vectors in Im(𝕆)

        Returns:
            [..., 7] cross product
        """
        self._ensure_device(x)
        return torch.einsum("ijk,...i,...j->...k", self.phi, x, y)

    def T_on_2form(self, alpha: torch.Tensor) -> torch.Tensor:
        """Apply T: Λ²→Λ², T(α) = * (φ ∧ α) = 0.5 ψ · α.

        The T operator is a key component of G₂ geometry:
        - Eigenvalue +1: Λ²₇ (associative 2-forms)
        - Eigenvalue -1/2: Λ²₁₄ (coassociative 2-forms)

        Args:
            alpha: [..., 7, 7] skew-symmetric 2-form

        Returns:
            [..., 7, 7] skew-symmetric T(α)
        """
        self._ensure_device(alpha)
        # (T α)_{ij} = 0.5 α_{mn} ψ_{mnij}
        Tij = 0.5 * torch.einsum("mnij,...mn->...ij", self.psi, alpha)
        # Enforce skew-symmetry numerically
        return 0.5 * (Tij - Tij.transpose(-1, -2))

    def project_2form(self, alpha: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Project 2-form α into Λ²₇ and Λ²₁₄.

        Decomposition: Λ² = Λ²₇ ⊕ Λ²₁₄

        Formulas using eigenvalues of T on Λ² components:
            P₇  = (1/3)(I + T)    (eigenvalue +1)
            P₁₄ = (2/3)(I - T)    (eigenvalue -1/2)

        Args:
            alpha: [..., 7, 7] skew-symmetric 2-form

        Returns:
            (P₇α, P₁₄α): Projections into 7D and 14D components
        """
        Tα = self.T_on_2form(alpha)
        P7 = (alpha + Tα) / 3.0
        P14 = (2.0 * (alpha - Tα)) / 3.0
        return P7, P14


def _compute_g2_basis(phi: torch.Tensor) -> torch.Tensor:
    """Compute EXACT orthonormal basis for g₂ ⊂ so(7).

    g₂ is 14-dimensional. It's the subspace of so(7) that preserves φ.
    The orthogonal complement (7D) is spanned by A_v where (A_v)_{ij} = φ_{ijk} v_k.

    NOTE: QR decomposition done on CPU for MPS compatibility, then moved back.

    Args:
        phi: [7, 7, 7] the G₂ 3-form

    Returns:
        [14, 7, 7] orthonormal basis matrices for g₂
    """
    import logging

    logger = logging.getLogger(__name__)
    target_device, dtype = phi.device, phi.dtype

    # Move to CPU for QR (not supported on MPS)
    phi_cpu = phi.cpu()

    # Build all 21 so(7) basis matrices E_{ij} = e_i e_j^T - e_j e_i^T
    so7_basis_list: list[torch.Tensor] = []
    for i in range(7):
        for j in range(i + 1, 7):
            E = torch.zeros(7, 7, dtype=dtype)
            E[i, j] = 1.0
            E[j, i] = -1.0
            so7_basis_list.append(E)
    so7_basis = torch.stack(so7_basis_list)  # [21, 7, 7]

    # Build the 7D complement: span of A_v where A_v = φ[:, :, k]
    complement_basis_list: list[torch.Tensor] = []
    for k in range(7):
        A_v = phi_cpu[:, :, k].clone()
        complement_basis_list.append(A_v)
    complement_basis = torch.stack(complement_basis_list)  # [7, 7, 7]

    # Orthogonalize: flatten and project (on CPU)
    so7_flat = so7_basis.view(21, 49)
    comp_flat = complement_basis.view(7, 49)

    # Gram-Schmidt on complement to get orthonormal basis
    Q_comp, _ = torch.linalg.qr(comp_flat.T)  # [49, 7]

    # Project so7 onto orthogonal complement of complement span
    proj = so7_flat @ Q_comp @ Q_comp.T
    g2_flat = so7_flat - proj  # [21, 49]

    # Extract non-zero basis vectors
    norms = g2_flat.norm(dim=1)
    nonzero_mask = norms > 1e-6
    g2_flat_nonzero = g2_flat[nonzero_mask]

    # Orthonormalize to get exactly 14 basis vectors.
    #
    # IMPORTANT (Dec 2025): g2_flat_nonzero has rank 14 but typically has >14 rows.
    # A plain QR on (49×k) without pivoting is NOT rank-robust: the first 14 columns of Q
    # are not guaranteed to lie in the column space when rank-deficient. Use SVD to get
    # a stable orthonormal basis for the **row space** (≡ Λ²₁₄ ⊂ so(7)).
    if g2_flat_nonzero.shape[0] >= 14:
        _u, s, vh = torch.linalg.svd(g2_flat_nonzero, full_matrices=False)  # vh: [k, 49]
        rank = int((s > 1e-10).sum().item())
        if rank < 14:
            logger.warning(f"g₂ basis rank too small: got rank={rank} (<14); padding zeros")
        g2_basis_flat = vh[: min(14, vh.shape[0])].contiguous()  # [<=14, 49]
        g2_basis = g2_basis_flat.view(-1, 7, 7)
        if g2_basis.shape[0] < 14:
            pad = torch.zeros(14 - g2_basis.shape[0], 7, 7, dtype=dtype)
            g2_basis = torch.cat([g2_basis, pad], dim=0)
        # Enforce so(7) antisymmetry numerically, then re-orthonormalize.
        g2_basis = 0.5 * (g2_basis - g2_basis.transpose(-1, -2))
        Q_g2, _ = torch.linalg.qr(g2_basis.view(14, 49).T)  # [49, 14]
        g2_basis = Q_g2.T.view(14, 7, 7)
    else:
        # Fallback: pad with zeros (should not happen for correct φ)
        logger.warning(f"g₂ basis incomplete: got {g2_flat_nonzero.shape[0]} vectors")
        g2_basis = torch.zeros(14, 7, 7, dtype=dtype)

    # Move back to target device
    return cast(torch.Tensor, g2_basis.to(target_device))


def _compute_sym_traceless_basis(device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    """Compute EXACT orthonormal basis for symmetric traceless 7×7 matrices.

    Dimension: 7×8/2 - 1 = 28 - 1 = 27D

    NOTE: QR decomposition done on CPU for MPS compatibility, then moved back.

    Returns:
        [27, 7, 7] orthonormal basis matrices
    """
    import math

    target_device = device
    basis = []

    # Off-diagonal symmetric: (e_ij + e_ji)/√2 for i < j (21 matrices)
    for i in range(7):
        for j in range(i + 1, 7):
            E = torch.zeros(7, 7, dtype=dtype)  # CPU
            E[i, j] = 1.0 / math.sqrt(2)
            E[j, i] = 1.0 / math.sqrt(2)
            basis.append(E)

    # Diagonal traceless: (e_ii - e_{i+1,i+1})/√2 for i = 0..5 (6 matrices)
    for i in range(6):
        E = torch.zeros(7, 7, dtype=dtype)  # CPU
        E[i, i] = 1.0 / math.sqrt(2)
        E[i + 1, i + 1] = -1.0 / math.sqrt(2)
        basis.append(E)

    basis_tensor = torch.stack(basis)  # [27, 7, 7] on CPU

    # Orthonormalize (on CPU)
    basis_flat = basis_tensor.view(27, 49)
    Q, _ = torch.linalg.qr(basis_flat.T)
    result = Q.T.view(27, 7, 7)

    # Move to target device
    return cast(torch.Tensor, result.to(target_device))


class G2ExactClebschGordan(nn.Module):
    """EXACT G₂ Clebsch-Gordan coefficients - NO LEARNED PARAMETERS.

    Computes the tensor product decomposition:
        7 ⊗ 7 = 1 ⊕ 7 ⊕ 14 ⊕ 27

    using FIXED coefficients derived from G₂ structure.
    ALL projections are mathematically exact. NO nn.Linear. NO learned weights.
    """

    def __init__(self, device: torch.device | None = None, dtype: torch.dtype | None = None):
        super().__init__()

        import logging

        logger = logging.getLogger(__name__)

        # Store target device for lazy buffer movement
        self._target_device = device
        dtype = dtype or torch.float32

        # Always build on CPU (QR not supported on MPS)
        # Using register_buffer ensures automatic device movement with .to()
        phi, psi = _phi_psi_standard(torch.device("cpu"), dtype)
        self.register_buffer("phi", phi)  # [7, 7, 7]
        self.register_buffer("psi", psi)  # [7, 7, 7, 7]

        # Build FIXED g₂ basis (14 antisymmetric matrices) - already on CPU
        g2_basis = _compute_g2_basis(phi)
        self.register_buffer("g2_basis", g2_basis)  # [14, 7, 7]

        # Build FIXED symmetric traceless basis (27 matrices) - already on CPU
        sym_basis = _compute_sym_traceless_basis(torch.device("cpu"), dtype)
        self.register_buffer("sym_basis", sym_basis)  # [27, 7, 7]

        logger.debug("G2ExactClebschGordan: FIXED C-G coefficients initialized")

    def _ensure_device(self, x: torch.Tensor) -> None:
        """Ensure buffers are on the same device as input."""
        if self.phi.device != x.device:
            # Move entire module to preserve buffer registration
            self.to(x.device)

    def cross(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        """EXACT cross product: (x × y)_k = φ_{ijk} x_i y_j"""
        self._ensure_device(x)
        return torch.einsum("ijk,...i,...j->...k", self.phi, x, y)

    def decompose_7x7(self, x: torch.Tensor, y: torch.Tensor) -> dict[str, torch.Tensor]:
        """EXACT decomposition of 7⊗7 into irreducible components.

        Args:
            x: [..., 7] first vector
            y: [..., 7] second vector

        Returns:
            Dictionary with scalar (1D), vector (7D), adjoint (14D), symmetric (27D)
        """
        import math

        self._ensure_device(x)

        # === SCALAR (1D): Inner product / √7 ===
        scalar = torch.sum(x * y, dim=-1, keepdim=True) / math.sqrt(7)

        # === VECTOR (7D): Cross product via φ ===
        vector = self.cross(x, y)

        # === TENSOR PRODUCT [7, 7] ===
        tensor = torch.einsum("...i,...j->...ij", x, y)

        # === ADJOINT (14D): Project antisymmetric part to g₂ ===
        antisym = 0.5 * (tensor - tensor.transpose(-1, -2))
        adjoint = torch.einsum("kij,...ij->...k", self.g2_basis, antisym)

        # === SYMMETRIC TRACELESS (27D) ===
        sym = 0.5 * (tensor + tensor.transpose(-1, -2))
        trace = torch.diagonal(sym, dim1=-2, dim2=-1).sum(dim=-1, keepdim=True)
        eye = torch.eye(7, device=x.device, dtype=x.dtype)
        sym_traceless = sym - (trace / 7.0).unsqueeze(-1) * eye
        symmetric = torch.einsum("kij,...ij->...k", self.sym_basis, sym_traceless)

        return {
            "scalar": scalar,  # [..., 1]
            "vector": vector,  # [..., 7]
            "adjoint": adjoint,  # [..., 14]
            "symmetric": symmetric,  # [..., 27]
        }

    def total_irrep_dim(self) -> int:
        """Total dimension of all irreps: 1 + 7 + 14 + 27 = 49"""
        return 49


__all__ = [
    "G2ExactClebschGordan",
    "G2PhiPsi",
    "_compute_g2_basis",
    "_compute_sym_traceless_basis",
    "_perm_sign",
    "_phi_psi_standard",
]
