"""G₂ Clebsch-Gordan decomposition with EXACT coefficients.

Implements tensor product decompositions:
    7 ⊗ 7  = 1 ⊕ 7 ⊕ 14 ⊕ 27
    7 ⊗ 14 = 7 ⊕ 27 ⊕ 64
    14 ⊗ 14 = 1 ⊕ 14 ⊕ 27 ⊕ 77 ⊕ 77'

Uses FIXED representation-theoretic projectors (no learned parameters).
"""

from __future__ import annotations

import itertools
import logging

import torch
import torch.nn as nn

from kagami_math.g2_forms import G2ExactClebschGordan, G2PhiPsi

logger = logging.getLogger(__name__)


class G2ClebschGordan(nn.Module):
    """EXACT Clebsch-Gordan coefficients for G₂ tensor products - NO LEARNED PARAMS.

    ENFORCED (December 7, 2025): Uses G2ExactClebschGordan with FIXED coefficients.

    Implements the decomposition:
        7 ⊗ 7 → 1 ⊕ 7 ⊕ 14 ⊕ 27

    Higher tensor products (7⊗14, 14⊗14) use **representation-theoretic** fixed
    projectors derived from the quadratic Casimir (no learned params, no random QR):

        7 ⊗ 14  = 7 ⊕ 27 ⊕ 64
        14 ⊗ 14 = 1 ⊕ 14 ⊕ 27 ⊕ 77 ⊕ 77'
    """

    _exact_cg: G2ExactClebschGordan

    def __init__(self, device: torch.device | None = None):
        super().__init__()

        # Use EXACT C-G implementation - NO LEARNED WEIGHTS
        self._exact_cg = G2ExactClebschGordan(device=device)

        # Expose G2PhiPsi for backward compatibility with code that accesses _g2_struct
        self._g2_struct = G2PhiPsi(device=device)

        # For higher tensor products, build FIXED orthogonal projections
        self._build_higher_projectors(device or torch.device("cpu"))

    def _build_higher_projectors(self, device: torch.device) -> None:
        """Build fixed orthogonal projectors for higher tensor products.

        This uses a representation-theoretic construction (Casimir spectral projectors),
        replacing the old random-QR placeholders:

        1) Build the adjoint (14D) representation from the **exact** g₂ basis in so(7):
           - Compute structure constants from commutators
           - adₐ is the 14×14 matrix of ad(eₐ)
        2) For each tensor product space, build the quadratic Casimir:
              C = Σₐ Rₐᵀ Rₐ  (symmetric, PSD)
           where Rₐ = ρ₁(eₐ) ⊗ I + I ⊗ ρ₂(eₐ)
        3) Eigendecompose C and group eigenvectors by eigenvalue multiplicity.
           Those eigenspaces are the irreducible summands.

        Output projectors are stored as buffers:
          - P_7x14_7, P_7x14_27, P_7x14_64
          - P_14x14_1, P_14x14_14, P_14x14_27, P_14x14_77a, P_14x14_77b

        NOTE: Computation is done on CPU in float64 for stability, then moved to target device.
        """
        target_device = device
        cpu = torch.device("cpu")
        dt = torch.float64

        # ---------------------------------------------------------------------
        # 0) Get exact g₂ basis in the 7D representation (as 7×7 matrices)
        # ---------------------------------------------------------------------
        g2_basis_7 = self._exact_cg.g2_basis.detach().to(device=cpu, dtype=dt)  # type: ignore[operator]  # [14, 7, 7]
        basis_flat = g2_basis_7.reshape(14, 49)  # [14, 49]

        # Ensure orthonormality of basis (under Frobenius inner product)
        gram = basis_flat @ basis_flat.T
        if not torch.allclose(gram, torch.eye(14, dtype=dt), atol=1e-6):
            # Orthonormalize rows via QR on the transpose
            Q, _ = torch.linalg.qr(basis_flat.T)  # [49, 14]
            basis_flat = Q.T.contiguous()  # [14, 49]
            g2_basis_7 = basis_flat.view(14, 7, 7)

        # ---------------------------------------------------------------------
        # 1) Build adjoint representation (14D) from structure constants
        # ---------------------------------------------------------------------
        # Commutators for all pairs: [a,b] = A B - B A
        AB = torch.einsum("aij,bjk->abik", g2_basis_7, g2_basis_7)  # [14,14,7,7]
        BA = torch.einsum("bij,ajk->abik", g2_basis_7, g2_basis_7)  # [14,14,7,7]
        comm_flat = (AB - BA).reshape(14, 14, 49)  # [14,14,49]

        # Structure constants in this orthonormal basis:
        # [e_a, e_b] = Σ_c f[a,b,c] e_c, with f[a,b,c] = ⟨[e_a,e_b], e_c⟩
        f = torch.einsum("abm,cm->abc", comm_flat, basis_flat)  # [14,14,14]
        # ad_a maps basis vector b -> Σ_c f[a,b,c] e_c, so matrix is [c,b] = f[a,b,c]
        g2_basis_14 = f.permute(0, 2, 1).contiguous()  # [14,14,14]

        # ---------------------------------------------------------------------
        # 2) Casimir spectral projectors on tensor product reps
        # ---------------------------------------------------------------------
        def _group_by_tol(evals: torch.Tensor, tol: float) -> list[tuple[int, int, float]]:
            n = int(evals.numel())
            out: list[tuple[int, int, float]] = []
            start = 0
            while start < n:
                end = start + 1
                while end < n and float((evals[end] - evals[start]).abs()) <= tol:
                    end += 1
                out.append((start, end, float(evals[start])))
                start = end
            return out

        def _cluster_groups(
            evals: torch.Tensor,
            expected_sizes: list[int],
        ) -> list[tuple[int, int, float]]:
            """Cluster sorted eigenvalues into groups matching expected multiplicities."""
            n = int(evals.numel())
            expected_sorted = sorted(expected_sizes)

            tol = 1e-10
            groups: list[tuple[int, int, float]] | None = None
            for _ in range(12):
                cand = _group_by_tol(evals, tol)
                sizes_sorted = sorted([e - s for s, e, _ in cand])
                if sizes_sorted == expected_sorted:
                    groups = cand
                    break
                tol *= 10.0

            if groups is not None:
                return groups

            # Fallback: split by largest eigenvalue gaps (robust when small noise prevents grouping)
            diffs = (evals[1:] - evals[:-1]).abs()  # [n-1]
            k = len(expected_sizes)
            if k <= 1:
                return [(0, n, float(evals[0]))]
            # indices of the largest (k-1) gaps
            gap_idx = torch.topk(diffs, k - 1).indices
            gap_idx_sorted = gap_idx.sort().values.tolist()
            split_points = [0] + [int(i) + 1 for i in gap_idx_sorted] + [n]
            cand = []
            for s, e in itertools.pairwise(split_points):
                cand.append((s, e, float(evals[s])))
            sizes_sorted = sorted([e - s for s, e, _ in cand])
            if sizes_sorted != expected_sorted:
                raise RuntimeError(
                    f"Failed to cluster Casimir eigenvalues into expected blocks. "
                    f"expected={expected_sorted}, got={sizes_sorted}"
                )
            return cand

        def _casimir_projectors(
            repA: torch.Tensor,  # [14, dA, dA]
            repB: torch.Tensor,  # [14, dB, dB]
            expected_sizes: list[int],
        ) -> list[torch.Tensor]:
            """Return [P₁, P₂, ...] where each P has shape [dim, dA*dB]."""
            dA = int(repA.shape[-1])
            dB = int(repB.shape[-1])
            n = dA * dB
            I_A = torch.eye(dA, dtype=dt, device=cpu)
            I_B = torch.eye(dB, dtype=dt, device=cpu)

            # Quadratic Casimir (symmetric PSD)
            C = torch.zeros(n, n, dtype=dt, device=cpu)
            for a in range(14):
                R = torch.kron(repA[a], I_B) + torch.kron(I_A, repB[a])  # [n, n]
                C = C + (R.T @ R)

            evals, evecs = torch.linalg.eigh(C)  # evals: [n], evecs: [n,n]
            groups = _cluster_groups(evals, expected_sizes)

            # Build group lookup by size, preserving deterministic order by eigenvalue
            by_size: dict[int, list[tuple[float, int, int]]] = {}
            for s, e, val in groups:
                by_size.setdefault(e - s, []).append((val, s, e))
            for size in by_size:
                by_size[size].sort(key=lambda t: t[0])

            projectors: list[torch.Tensor] = []
            for size in expected_sizes:
                if size not in by_size or not by_size[size]:
                    raise RuntimeError(
                        f"Missing eigen-subspace of size {size} in Casimir decomposition"
                    )
                _val, s, e = by_size[size].pop(0)
                V = evecs[:, s:e].contiguous()  # [n, size]
                P = V.T.contiguous()  # [size, n] with orthonormal rows
                projectors.append(P.to(device=target_device, dtype=torch.float32))
            return projectors

        # 7⊗14 = 98 → 7 ⊕ 27 ⊕ 64
        P_7x14_7, P_7x14_27, P_7x14_64 = _casimir_projectors(
            repA=g2_basis_7, repB=g2_basis_14, expected_sizes=[7, 27, 64]
        )
        self.register_buffer("P_7x14_7", P_7x14_7)
        self.register_buffer("P_7x14_27", P_7x14_27)
        self.register_buffer("P_7x14_64", P_7x14_64)

        # 14⊗14 = 196 → 1 ⊕ 14 ⊕ 27 ⊕ 77 ⊕ 77'
        P_14x14_1, P_14x14_14, P_14x14_27, P_14x14_77a, P_14x14_77b = _casimir_projectors(
            repA=g2_basis_14, repB=g2_basis_14, expected_sizes=[1, 14, 27, 77, 77]
        )
        self.register_buffer("P_14x14_1", P_14x14_1)
        self.register_buffer("P_14x14_14", P_14x14_14)
        self.register_buffer("P_14x14_27", P_14x14_27)
        self.register_buffer("P_14x14_77a", P_14x14_77a)
        self.register_buffer("P_14x14_77b", P_14x14_77b)

        logger.debug("✅ G2ClebschGordan: Casimir projectors built (7⊗14, 14⊗14)")

    def _ensure_device(self, x: torch.Tensor) -> None:
        """Ensure all buffers are on the same device as input."""
        # Check if buffers need device transfer
        P_7x14_7 = self.get_buffer("P_7x14_7")
        if P_7x14_7.device != x.device:
            # Move all projector buffers to target device
            for name in [
                "P_7x14_7",
                "P_7x14_27",
                "P_7x14_64",
                "P_14x14_1",
                "P_14x14_14",
                "P_14x14_27",
                "P_14x14_77a",
                "P_14x14_77b",
            ]:
                buf = self.get_buffer(name)
                self.register_buffer(name, buf.to(x.device))
        # Also ensure _g2_struct is on correct device
        if self._g2_struct.phi.device != x.device:
            self._g2_struct._ensure_device(x)

    def forward(self, x: torch.Tensor, y: torch.Tensor) -> dict[str, torch.Tensor]:
        """Forward pass: decompose 7⊗7 into irreducible components.

        This is the standard nn.Module interface for G₂ Clebsch-Gordan decomposition.

        Args:
            x: First 7D vector [..., 7]
            y: Second 7D vector [..., 7]

        Returns:
            Dict with keys: scalar [1], vector [7], adjoint [14], symmetric [27]
        """
        return self.decompose_7x7(x, y)

    def decompose_7x7(self, x: torch.Tensor, y: torch.Tensor) -> dict[str, torch.Tensor]:
        """EXACT decomposition of 7⊗7 into irreducible components.

        Uses FIXED Clebsch-Gordan coefficients. NO LEARNING.
        """
        return self._exact_cg.decompose_7x7(x, y)

    def decompose_7x14(self, x_7: torch.Tensor, x_14: torch.Tensor) -> dict[str, torch.Tensor]:
        """Decompose 7⊗14 → 7 ⊕ 27 ⊕ 64 using FIXED projectors."""
        self._ensure_device(x_7)
        tensor = torch.einsum("...i,...j->...ij", x_7, x_14)
        tensor_flat = tensor.reshape(*tensor.shape[:-2], 98)

        return {
            "vector": torch.einsum("ij,...j->...i", self.P_7x14_7, tensor_flat),
            "symmetric": torch.einsum("ij,...j->...i", self.P_7x14_27, tensor_flat),
            "mixed_64": torch.einsum("ij,...j->...i", self.P_7x14_64, tensor_flat),
        }

    def decompose_14x14(self, x_14: torch.Tensor, y_14: torch.Tensor) -> dict[str, torch.Tensor]:
        """Decompose 14⊗14 → 1 ⊕ 14 ⊕ 27 ⊕ 77 ⊕ 77' using FIXED projectors."""
        self._ensure_device(x_14)
        tensor = torch.einsum("...i,...j->...ij", x_14, y_14)
        tensor_flat = tensor.reshape(*tensor.shape[:-2], 196)

        return {
            "scalar": torch.einsum("ij,...j->...i", self.P_14x14_1, tensor_flat),
            "adjoint": torch.einsum("ij,...j->...i", self.P_14x14_14, tensor_flat),
            "symmetric": torch.einsum("ij,...j->...i", self.P_14x14_27, tensor_flat),
            "sym3_1": torch.einsum("ij,...j->...i", self.P_14x14_77a, tensor_flat),
            "sym3_2": torch.einsum("ij,...j->...i", self.P_14x14_77b, tensor_flat),
        }


__all__ = [
    "G2ClebschGordan",
]
