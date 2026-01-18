"""Cross-Copy Interaction Layer for G₂ rep_multiplier scaling.

Enables interactions between k copies of the fundamental representation
while preserving G₂ equivariance.

For rep_multiplier = k, the input is ℝ^{7k} with G₂ acting diagonally:
    g · (x₁, x₂, ..., xₖ) = (g·x₁, g·x₂, ..., g·xₖ)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import torch
import torch.nn as nn
import torch.nn.functional as F

from kagami_math.g2_forms import G2PhiPsi

from .hardware import SDPAttention

if TYPE_CHECKING:
    G2PhiPsiType = G2PhiPsi
else:
    G2PhiPsiType = G2PhiPsi


class G2CrossCopyInteraction(nn.Module):
    """Enable interactions between k copies of the fundamental representation.

    For rep_multiplier = k, the input is ℝ^{7k} with G₂ acting diagonally.

    This layer computes tensor products BETWEEN copies while preserving
    G₂ equivariance. The key insight is that:

        G₂ acts as: g · (x₁, x₂, ..., xₖ) = (g·x₁, g·x₂, ..., g·xₖ)

    So we can compute x_i × x_j (cross product) between copies, which
    transforms equivariantly: g·(x_i × x_j) = (g·x_i) × (g·x_j)
    """

    def __init__(
        self,
        rep_multiplier: int,
        hidden_dim: int = 64,
        use_attention: bool = True,
    ):
        """Initialize cross-copy interaction.

        Args:
            rep_multiplier: Number of copies (k)
            hidden_dim: Hidden dimension for mixing MLP
            use_attention: Use attention for copy mixing
        """
        super().__init__()

        self.k = rep_multiplier
        self.hidden_dim = hidden_dim
        self.use_attention = use_attention

        # G₂ structures - registered submodule so it moves with .to()
        self._g2_struct = G2PhiPsi(device=torch.device("cpu"))

        # Number of unique pairs: k(k-1)/2
        self.num_pairs = (self.k * (self.k - 1)) // 2

        # Invariant MLP for pair mixing weights
        # Input: k norms + k(k-1)/2 inner products + k(k-1)/2 cross norms
        num_invariants = self.k + 2 * self.num_pairs

        self.pair_mlp = nn.Sequential(
            nn.Linear(num_invariants, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, self.k * self.k),  # k×k mixing matrix
        )

        # Per-copy MLPs for equivariant transformation
        self.copy_mlps = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Linear(7, hidden_dim),
                    nn.LayerNorm(hidden_dim),
                    nn.GELU(),
                    nn.Linear(hidden_dim, 7),
                )
                for _ in range(self.k)
            ]
        )

        # Optional attention mechanism - uses SDPAttention for zero-copy
        if use_attention:
            self.copy_attention = SDPAttention(embed_dim=7, num_heads=1)

        # Output normalization
        self.output_norm = nn.LayerNorm(7 * self.k)

    def _get_g2_struct(self, device: torch.device) -> G2PhiPsiType:
        """Get G₂ structure on correct device.

        Since _g2_struct is a registered submodule, it moves with .to().
        No recreation needed - just return the existing struct.
        """
        # Note: _g2_struct is a submodule, so it auto-moves with model.to(device)
        return self._g2_struct

    def _compute_cross_products(self, copies: list[torch.Tensor]) -> list[torch.Tensor]:
        """Compute all pairwise cross products."""
        g2 = self._get_g2_struct(copies[0].device)
        cross_products = []
        for i in range(self.k):
            for j in range(i + 1, self.k):
                cross = g2.cross(copies[i], copies[j])
                cross_products.append(cross)
        return cross_products

    def _compute_invariants(self, copies: list[torch.Tensor]) -> torch.Tensor:
        """Compute G₂-invariant features from all copies."""
        invariants = []

        # Norms
        for c in copies:
            invariants.append(c.norm(dim=-1, keepdim=True))

        # Pairwise inner products
        for i in range(self.k):
            for j in range(i + 1, self.k):
                inner = torch.sum(copies[i] * copies[j], dim=-1, keepdim=True)
                invariants.append(inner)

        # Cross product norms
        cross_products = self._compute_cross_products(copies)
        for cross in cross_products:
            invariants.append(cross.norm(dim=-1, keepdim=True))

        return torch.cat(invariants, dim=-1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply cross-copy interaction.

        Args:
            x: [..., 7*k] input with k copies concatenated

        Returns:
            [..., 7*k] output with cross-copy mixing
        """
        batch_shape = x.shape[:-1]

        # Split into k copies
        copies = list(x.split(7, dim=-1))  # List of k tensors, each [..., 7]

        # Compute invariants for mixing
        invariants = self._compute_invariants(copies)

        # Get mixing matrix
        mix_flat = self.pair_mlp(invariants)  # [..., k*k]
        mix_matrix = mix_flat.view(*batch_shape, self.k, self.k)
        mix_matrix = F.softmax(mix_matrix, dim=-1)  # Normalize rows

        # Compute cross products for mixing
        cross_products = self._compute_cross_products(copies)

        # Build output copies with mixing
        output_copies = []
        cross_idx = 0

        for i in range(self.k):
            # Start with transformed self
            out_i = self.copy_mlps[i](copies[i])

            # Add weighted contributions from other copies
            for j in range(self.k):
                if i != j:
                    weight = mix_matrix[..., i, j : j + 1]  # [..., 1]

                    if i < j:
                        cross = cross_products[cross_idx]
                        cross_idx += 1
                    else:
                        # Get from symmetric position (j, i), with sign flip
                        sym_idx = sum(range(j, i))  # Index for pair (j, i)
                        cross = -cross_products[sym_idx]  # Antisymmetric

                    out_i = out_i + weight * cross

            # Normalize to preserve norm structure
            out_i_norm = out_i.norm(dim=-1, keepdim=True)
            if (out_i_norm < 1e-8).any():
                raise ValueError(
                    f"Cannot normalize zero vector in G2CrossCopyInteraction forward pass for copy {i}"
                )
            out_i = out_i / out_i_norm * copies[i].norm(dim=-1, keepdim=True)
            output_copies.append(out_i)
            cross_idx = 0  # Reset for next copy

        # Optional attention mixing
        if self.use_attention:
            # Stack copies: [..., k, 7] - stack produces contiguous tensor
            stacked = torch.stack(output_copies, dim=-2)
            # MultiheadAttention expects contiguous input (stack output is already contiguous)
            attended, _ = self.copy_attention(stacked, stacked, stacked)
            # unbind creates views, no copy needed
            output_copies = list(attended.unbind(dim=-2))

        # Concatenate and normalize
        output = torch.cat(output_copies, dim=-1)
        output = self.output_norm(output)

        # Residual connection
        output = x + output * 0.1  # Small residual weight

        return cast(torch.Tensor, output)


__all__ = [
    "G2CrossCopyInteraction",
]
