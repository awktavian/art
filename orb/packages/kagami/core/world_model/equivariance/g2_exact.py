from __future__ import annotations

"""Exact G₂ primitives on ℝ⁷ - NO LEARNED PARAMETERS.

ENFORCED (December 7, 2025):
============================
All operations use FIXED mathematical coefficients derived from G₂ structure.
NO nn.Linear layers. NO learned weights. Pure representation theory.

This module provides:
- The standard G₂ 3-form φ and its Hodge dual ψ in the canonical basis
- Exact Im(𝕆) cross product x × y using φ
- Projectors for 2-forms: Λ² = Λ²₇ ⊕ Λ²₁₄ via T(α) = * (φ ∧ α) = (1/2) ψ · α
- EXACT 7⊗7 Clebsch-Gordan decomposition: 7⊗7 = 1 ⊕ 7 ⊕ 14 ⊕ 27
- EXACT g₂ Lie algebra basis (14 generators)

References:
- Bryant, "Some remarks on G₂-structures"
- Karigiannis, "Flows of G₂-structures"
- Baez, "The Octonions"
- Fulton & Harris, "Representation Theory" Ch. 22

DEPENDENCY FIX (December 14, 2025):
====================================
G2PhiPsi has been moved to kagami_math.g2_forms to break circular dependency.
This module now imports from math and re-exports for backward compatibility.
"""
import logging
import math

import torch
import torch.nn as nn

# Import pure mathematical components from math module (dependency fix)
# All exact G₂ operations with no learned parameters have been moved to kagami_math.g2_forms
from kagami_math.g2_forms import (
    G2PhiPsi,
    _phi_psi_standard,
)

logger = logging.getLogger(__name__)


class G2ExactProjectors(nn.Module):
    """Convenience wrapper exposing exact projectors and cross product."""

    def __init__(self) -> None:
        super().__init__()
        self.struct = G2PhiPsi()

    def cross(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        return self.struct.cross(x, y)

    def project_2form(self, alpha: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.struct.project_2form(alpha)


# =============================================================================
# EXACT 7⊗7 CLEBSCH-GORDAN DECOMPOSITION - NO LEARNED PARAMETERS
# =============================================================================


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
    return g2_basis.to(target_device)


def _compute_sym_traceless_basis(device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    """Compute EXACT orthonormal basis for symmetric traceless 7×7 matrices.

    Dimension: 7×8/2 - 1 = 28 - 1 = 27D

    NOTE: QR decomposition done on CPU for MPS compatibility, then moved back.

    Returns:
        [27, 7, 7] orthonormal basis matrices
    """
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
    return result.to(target_device)


class G2ExactClebschGordan(nn.Module):
    """EXACT G₂ Clebsch-Gordan coefficients - NO LEARNED PARAMETERS.

    Computes the tensor product decomposition:
        7 ⊗ 7 = 1 ⊕ 7 ⊕ 14 ⊕ 27

    using FIXED coefficients derived from G₂ structure.
    ALL projections are mathematically exact. NO nn.Linear. NO learned weights.
    """

    phi: torch.Tensor
    psi: torch.Tensor
    g2_basis: torch.Tensor
    sym_basis: torch.Tensor

    def __init__(self, device: torch.device | None = None, dtype: torch.dtype | None = None):
        super().__init__()

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


class G2LieAlgebra(nn.Module):
    """G₂ Lie algebra exponential map - EXACT BASIS, NO LEARNED WEIGHTS.

    14D coefficients → 7×7 rotation matrix in G₂ ⊂ SO(7).
    Uses mathematically exact g₂ basis derived from φ.
    """

    def __init__(self, order: int = 6, device: torch.device | None = None) -> None:
        super().__init__()
        self.order = order

        device = device or torch.device("cpu")
        dtype = torch.float32

        # Build EXACT φ tensor
        phi, _ = _phi_psi_standard(device, dtype)

        # Build EXACT g₂ basis (NO LEARNED PARAMETERS)
        g2_basis = _compute_g2_basis(phi)
        self.register_buffer("g2_basis", g2_basis)  # [14, 7, 7]

    def exp(self, v: torch.Tensor) -> torch.Tensor:
        """Exponential map: 14D g₂ coefficients → 7×7 G₂ rotation matrix.

        Uses EXACT g₂ basis, NOT learned projection.

        Args:
            v: [..., 14] Lie algebra coefficients

        Returns:
            [..., 7, 7] rotation matrices in G₂ ⊂ SO(7)
        """
        # Construct antisymmetric matrix from EXACT basis
        # A = sum_k v_k * B_k where B_k are the 14 g₂ basis matrices
        A = torch.einsum("...k,kij->...ij", v, self.g2_basis)  # [..., 7, 7]

        # Scale for numerical stability
        norm = A.norm(dim=(-2, -1), keepdim=True).clamp(min=1e-8)
        scale = torch.where(norm > 1.0, norm, torch.ones_like(norm))
        A_scaled = A / scale

        # Taylor expansion of matrix exponential
        batch_shape = v.shape[:-1]
        result = torch.eye(7, device=v.device, dtype=v.dtype).expand(*batch_shape, 7, 7).clone()
        A_power = A_scaled.clone()

        factorial = 1.0
        for k in range(1, self.order + 1):
            factorial *= k
            result = result + A_power / factorial
            if k < self.order:
                A_power = torch.matmul(A_power, A_scaled)

        # Re-scale for large norms
        if (scale > 1.0).any():
            n_squares = int(torch.log2(scale.max()).ceil().item())
            for _ in range(n_squares):
                result = torch.matmul(result, result)

        return result


# =============================================================================
# EXACT G₂ EQUIVARIANT LAYER - ONLY INVARIANT MLPs
# =============================================================================


class G2ExactEquivariantLayer(nn.Module):
    """EXACT G₂-equivariant layer.

    The ONLY learned component is an MLP on G₂-INVARIANT scalars.
    This is mathematically equivariant because scalars are invariant!

    For f: V → V to be G₂-equivariant, we have f(g·x) = g·f(x).
    For scalar functions s: V → ℝ, this means s must be invariant: s(g·x) = s(x).

    Architecture:
        1. Compute invariants: ||x||, (x·x scalar), etc.
        2. MLP on invariants → scalar weights
        3. Output: weighted combination of x (equivariant!)
    """

    def __init__(self, hidden_dim: int = 32):
        super().__init__()

        self.cg = G2ExactClebschGordan()

        # MLP on invariants - the ONLY learned part (equivariant because input is invariant)
        self.invariant_mlp = nn.Sequential(
            nn.Linear(4, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 2),  # Output: scale and bias for x
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply G₂-equivariant transformation.

        Args:
            x: [..., 7] input vector

        Returns:
            [..., 7] transformed vector (G₂-equivariant)
        """
        # Compute G₂-invariant features
        x_norm = x.norm(dim=-1, keepdim=True).clamp(min=1e-8)
        x_unit = x / x_norm

        decomp = self.cg.decompose_7x7(x_unit, x_unit)

        invariants = torch.cat(
            [
                x_norm,
                decomp["scalar"].abs(),
                decomp["adjoint"].norm(dim=-1, keepdim=True),
                decomp["symmetric"].norm(dim=-1, keepdim=True),
            ],
            dim=-1,
        )  # [..., 4]

        # MLP on invariants (equivariant!)
        weights = self.invariant_mlp(invariants)  # [..., 2]
        scale = torch.sigmoid(weights[..., 0:1])
        bias_scale = torch.tanh(weights[..., 1:2]) * 0.1

        # Equivariant output: scaled x
        return (scale + bias_scale) * x
