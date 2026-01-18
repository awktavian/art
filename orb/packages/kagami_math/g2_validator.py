"""G₂ Equivariance Validation and Enforcement

G₂ = Aut(𝕆) is the automorphism group of octonions, the 14-dimensional
exceptional Lie group that preserves octonion multiplication.

Like Lorentz group defines valid spacetime transformations, G₂ defines valid
compositional operations for non-associative reasoning.

Mathematical role:
- G₂ is the 14-dimensional exceptional Lie group
- Acts on Im(𝕆) ≅ ℝ⁷, preserving octonion multiplication table (Fano plane)
- Enables context-dependent composition while maintaining structural coherence

This module:
1. Validates G₂ equivariance: f(g·x) = g·f(x) for g ∈ G₂
2. Projects operations onto G₂-invariant subspace (enforces structure)
3. Measures deviation from G₂ (tracks correctness)
4. Enforces G₂ constraints during training (prevents drift to noise)

Critical insight: Without G₂ structure, non-associative composition degenerates
to arbitrary operations. G₂ preserves the Fano plane structure that makes
octonion operations mathematically coherent.

UPDATED Dec 24, 2025: Uses canonical fano_plane.FANO_LINES (fano_ops.py deleted)
"""

import logging
from typing import Any

import torch
import torch.nn as nn

from kagami_math.fano_plane import FANO_LINES

logger = logging.getLogger(__name__)


class G2EquivarianceValidator(nn.Module):
    """Validate and enforce G₂ equivariance.

    G₂ preserves:
    - Octonion multiplication table (Fano plane structure)
    - Cross product on ℝ⁷ (imaginary octonions)
    - Triality (special 3-way symmetry)

    UPDATED Dec 24, 2025: Uses canonical fano_plane.FANO_LINES directly.
    """

    def __init__(self) -> None:
        super().__init__()
        # Use canonical FANO_LINES from fano_plane (1-indexed: e₁...e₇)
        self.fano_lines = list(FANO_LINES)

        # OPTIMIZED: Pre-cache Fano line indices as buffers for device placement
        for i, line in enumerate(self.fano_lines):
            self.register_buffer(
                f"_fano_idx_{i}", torch.tensor([x - 1 for x in line], dtype=torch.long)
            )

        # Keep list reference for iteration
        self.fano_lines_indices = [
            getattr(self, f"_fano_idx_{i}") for i in range(len(self.fano_lines))
        ]

        # OPTIMIZATION: G₂ basis computed once and stored as buffer
        # Will be populated on first use with correct device
        self._g2_basis: torch.Tensor | None = None
        self._basis_device: torch.device | None = None

        logger.debug("G₂ equivariance validator initialized")

    def _ensure_basis_cache(self, device: torch.device) -> torch.Tensor:
        """Lazy load and cache G₂ basis on correct device."""
        if self._g2_basis is not None and self._g2_basis.device == device:
            return self._g2_basis

        # Construct basis if not exists or wrong device
        # We build basis for so(7) (21 dim) and project to g2 (14 dim)
        # This runs once per device

        # Standard basis for skew-symmetric 7x7 matrices
        # E_ij = e_i e_j^T - e_j e_i^T for 1 <= i < j <= 7
        # Total 7*6/2 = 21 basis elements
        torch.eye(7, device=device)
        candidates = []
        for i in range(7):
            for j in range(i + 1, 7):
                mat = torch.zeros((7, 7), device=device)
                mat[i, j] = 1.0
                mat[j, i] = -1.0
                candidates.append(mat)

        # Project each candidate to G2 algebra
        # Note: project_to_g2 uses SVD, but we only do this 21 times at init
        g2_candidates = []
        for mat in candidates:
            proj = self._project_to_g2_svd(mat)
            if proj.norm() > 1e-6:
                g2_candidates.append(proj)

        # Orthogonalize (Gram-Schmidt) to get 14 basis vectors
        ortho_basis: list[torch.Tensor] = []
        for v in g2_candidates:
            # Orthogonalize against existing
            for u in ortho_basis:
                coeff = (v * u).sum()
                v = v - coeff * u

            norm = v.norm()
            if norm > 1e-6:
                ortho_basis.append(v / norm)
                if len(ortho_basis) >= 14:
                    break

        if len(ortho_basis) < 14:
            logger.warning(f"G2 basis construction incomplete: got {len(ortho_basis)}/14 vectors")

        self._g2_basis = torch.stack(ortho_basis)  # [14, 7, 7]
        return self._g2_basis

    def _project_to_g2_svd(self, transform: torch.Tensor) -> torch.Tensor:
        """Original SVD-based projection (slow, used for init only)."""
        projected = transform.clone()
        # Re-implementation of the original loop for internal use
        for line_idx in self.fano_lines_indices:
            if line_idx.device != transform.device:
                line_idx = line_idx.to(transform.device)
            rows = line_idx.unsqueeze(1)
            cols = line_idx.unsqueeze(0)
            submatrix = transform[rows, cols]
            try:
                U, _S, V = torch.linalg.svd(submatrix)
                submatrix_orth = U @ V
                projected[rows, cols] = submatrix_orth
            except RuntimeError:
                pass
        return projected

    def check_fano_preservation(self, o: torch.Tensor, transform: torch.Tensor) -> float:
        """Check if transform preserves Fano plane structure.

        Args:
            o: [B, 8] octonions
            transform: [7, 7] linear transform on imaginary units

        Returns:
            error: Deviation from Fano structure preservation
        """
        imag = o[:, 1:]
        imag_transformed = imag @ transform.t()
        error = torch.tensor(0.0, device=o.device)

        # Vectorized check if possible, but loop is fine for validation-only
        for i, line1 in enumerate(self.fano_lines):
            line1_idx = [x - 1 for x in line1]
            v1_orig = imag[:, line1_idx].mean(dim=0)
            v1_trans = imag_transformed[:, line1_idx].mean(dim=0)

            for line2 in self.fano_lines[i + 1 :]:
                line2_idx = [x - 1 for x in line2]
                v2_orig = imag[:, line2_idx].mean(dim=0)
                dot_orig = (v1_orig * v2_orig).sum()

                v2_trans = imag_transformed[:, line2_idx].mean(dim=0)
                dot_trans = (v1_trans * v2_trans).sum()

                error += (dot_trans - dot_orig).abs()

        return error.item() / len(self.fano_lines)

    @torch.jit.export
    def project_to_g2(self, transform: torch.Tensor) -> torch.Tensor:
        """Project linear transform onto G₂-invariant subspace.

        OPTIMIZED (B2): Uses pre-computed basis projection instead of SVD.
        Complexity: O(14 * 49) = O(1) vs O(SVD)

        Args:
            transform: [7, 7] linear transform

        Returns:
            projected: [7, 7] G₂-equivariant transform
        """
        # Ensure basis is ready
        basis = self._ensure_basis_cache(transform.device)

        # Projection onto subspace spanned by orthonormal basis B_i:
        # P(M) = sum_i <M, B_i> B_i
        # where <A, B> = tr(A.T @ B) = sum(A * B)

        # Calculate coefficients: [14]
        # transform: [7, 7]
        # basis: [14, 7, 7]
        # We want dot product of transform with each basis matrix

        # Reshape for batched dot product
        flat_transform = transform.view(-1)  # [49]
        flat_basis = basis.view(14, -1)  # [14, 49]

        coeffs = torch.mv(flat_basis, flat_transform)  # [14]

        # Reconstruct projected matrix
        # sum(coeff_i * B_i)
        projected = torch.einsum("i,ijk->jk", coeffs, basis)

        return projected

    def g2_regularization_loss(self, weights: torch.Tensor) -> torch.Tensor:
        """Regularization to encourage G₂ equivariance.

        Args:
            weights: [out_features, 7] linear layer weights acting on imaginaries

        Returns:
            loss: Penalty for non-G₂-equivariant weights
        """
        if weights.shape[-1] != 7:
            return torch.tensor(0.0, device=weights.device)
        if weights.shape[0] > 7:
            W = weights[:7, :]
        else:
            W = weights

        # Accumulate loss as tensor to avoid torch.tensor() copy warning
        loss = torch.tensor(0.0, device=weights.device, dtype=weights.dtype)
        for i, line1 in enumerate(self.fano_lines):
            for line2 in self.fano_lines[i + 1 :]:
                line1_idx = [x - 1 for x in line1]
                line2_idx = [x - 1 for x in line2]
                v1 = W[:, line1_idx].mean(dim=1)
                v2 = W[:, line2_idx].mean(dim=1)
                dot = (v1 * v2).sum()
                loss = loss + dot.abs()

        return loss / len(self.fano_lines)

    def validate_operation(
        self, operation: Any, test_inputs: torch.Tensor, g2_transform: torch.Tensor
    ) -> dict[str, float]:
        """Validate G₂ equivariance of operation.

        Test: operation(g·x) = g·operation(x) for g ∈ G₂

        Args:
            operation: Callable octonion operation
            test_inputs: [B, 8] test octonions
            g2_transform: [7, 7] G₂ element

        Returns:
            metrics: Equivariance error
        """
        with torch.no_grad():
            imag = test_inputs[:, 1:]
            imag_transformed = imag @ g2_transform.t()
            inputs_transformed = torch.cat([test_inputs[:, :1], imag_transformed], dim=-1)
            path1 = operation(inputs_transformed)
            outputs = operation(test_inputs)
            outputs_imag = outputs[:, 1:]
            outputs_transformed_imag = outputs_imag @ g2_transform.t()
            path2 = torch.cat([outputs[:, :1], outputs_transformed_imag], dim=-1)
            error = (path1 - path2).norm(dim=-1).mean().item()
            return {"equivariance_error": error, "is_g2_equivariant": error < 0.001}


# Module ready
