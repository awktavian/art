"""G₂ Irreducible Representation Tower.

Builds towers of G₂ irreps via tensor products and mixes them with
learnable coefficients. This is the core scaling mechanism.

Architecture:
    Level 0: 7D (standard)
    Level 1: 7⊗7 → 1 + 7 + 14 + 27 = 49D
    Level 2: + 7⊗14 → + 7 + 27 + 64 = 147D
    Level 3: + 14⊗14 → + 1 + 14 + 27 + 77 + 77 = 343D
"""

from __future__ import annotations

import logging
import math
from typing import cast

import torch
import torch.nn as nn
import torch.nn.functional as F

from .clebsch_gordan import G2ClebschGordan
from .hardware import G2HardwareConfig, SDPAttention
from .irrep_levels import IrrepLevel

logger = logging.getLogger(__name__)


class G2IrrepTower(nn.Module):
    """Build towers of G₂ irreducible representations.

    This is the core scaling mechanism: instead of k copies of 7D,
    we build multiple irreps via tensor products and mix them.

    Architecture:
    ============
    Input: x ∈ ℝ^7 (standard rep)

    Level 0: 7D (standard)
    Level 1: 7⊗7 → 1 + 7 + 14 + 27 = 49D
    Level 2: + 7⊗14 → + 7 + 27 + 64 = 147D
    Level 3: + 14⊗14 → + 1 + 14 + 27 + 77 + 77 = 343D

    Output: Learnable weighted sum of all irreps → target_dim
    """

    def __init__(
        self,
        config: G2HardwareConfig | None = None,
        target_dim: int = 128,
        num_layers: int = 2,
    ):
        """Initialize G₂ Irrep Tower.

        Args:
            config: Hardware configuration (auto-detects if None)
            target_dim: Output dimension
            num_layers: Number of tower layers
        """
        super().__init__()

        self.config = config or G2HardwareConfig()
        self.target_dim = target_dim
        self.num_layers = num_layers
        self.irrep_level = self.config.irrep_level

        # Clebsch-Gordan decomposition
        self.cg = G2ClebschGordan(self.config.get_device())

        # Reference vectors for invariant extraction
        self.ref_vectors = nn.ParameterList(
            [nn.Parameter(torch.randn(7) / math.sqrt(7)) for _ in range(3)]
        )

        # Build layers
        self._build_tower()

        # Output projection
        total_irrep_dim = self._compute_total_dim()
        self.output_proj = nn.Sequential(
            nn.Linear(total_irrep_dim, target_dim * 2),
            nn.LayerNorm(target_dim * 2),
            nn.GELU(),
            nn.Linear(target_dim * 2, target_dim),
        )

        # Learnable mixing weights per irrep
        self.irrep_weights = nn.Parameter(torch.ones(self._num_irreps()))

        logger.debug(f"G2IrrepTower: {total_irrep_dim}→{target_dim}, layers={num_layers}")

    def _compute_total_dim(self) -> int:
        """Compute total dimension of all irreps."""
        if self.irrep_level == IrrepLevel.MINIMAL:
            return 1 + 7  # 8
        elif self.irrep_level == IrrepLevel.STANDARD:
            return 1 + 7 + 14 + 27  # 49
        elif self.irrep_level == IrrepLevel.EXTENDED:
            return 1 + 7 + 14 + 27 + 64 + 77  # 190
        else:  # MAXIMAL
            return 1 + 7 + 14 + 27 + 64 + 77 + 77 + 189  # 456

    def _num_irreps(self) -> int:
        """Number of distinct irreps."""
        return {
            IrrepLevel.MINIMAL: 2,
            IrrepLevel.STANDARD: 4,
            IrrepLevel.EXTENDED: 6,
            IrrepLevel.MAXIMAL: 8,
        }[self.irrep_level]

    def _build_tower(self) -> None:
        """Build the irrep tower layers."""
        # Invariant MLP for scalar coefficients
        # Maps G₂-invariants to mixing weights
        num_invariants = 6  # ||x||, ⟨x,ref₁⟩, ⟨x,ref₂⟩, ⟨x,ref₃⟩, ||x×ref₁||, φ(x,ref₁,ref₂)

        self.invariant_mlp = nn.Sequential(
            nn.Linear(num_invariants, 64),
            nn.LayerNorm(64),
            nn.GELU(),
            nn.Linear(64, 32),
            nn.LayerNorm(32),
            nn.GELU(),
            nn.Linear(32, self._num_irreps()),  # Weights per irrep
        )

        # Normalizations for each irrep dimension
        # GRADIENT FIX (Dec 4, 2025): LayerNorm(1) always outputs 0 for 1D inputs
        # Use learned scale for scalar (1D), LayerNorm for higher dims
        irrep_dims = self._get_irrep_dims()
        self.irrep_norms = nn.ModuleDict()
        for name, dim in irrep_dims.items():
            if dim == 1:
                # Scalar irrep: use learned affine transform instead of broken LayerNorm(1)
                self.irrep_norms[name] = nn.Linear(1, 1, bias=True)
            else:
                self.irrep_norms[name] = nn.LayerNorm(dim)

        # Cross-attention between irreps (optional, for EXTENDED+)
        # Uses SDPAttention for zero-copy operation (48 fewer contiguous calls)
        self.irrep_attention: SDPAttention | None
        if self.irrep_level >= IrrepLevel.EXTENDED:
            self.irrep_attention = SDPAttention(embed_dim=64, num_heads=4)
        else:
            self.irrep_attention = None

        # Higher irrep projection for MAXIMAL (189D from lower irreps)
        self._higher_proj: nn.Linear | None
        if self.irrep_level >= IrrepLevel.MAXIMAL:
            # Input: all lower irreps (1+7+14+27+64+77+77 = 267D)
            lower_dim = 1 + 7 + 14 + 27 + 64 + 77 + 77
            self._higher_proj = nn.Linear(lower_dim, 189, bias=False)
            # MPS-safe orthogonal init: do QR on CPU first
            cpu_weight = self._higher_proj.weight.cpu()
            nn.init.orthogonal_(cpu_weight)
            self._higher_proj.weight.data = cpu_weight.to(self._higher_proj.weight.device)
        else:
            self._higher_proj = None

    def _get_irrep_dims(self) -> dict[str, int]:
        """Get dimensions for each irrep at current level."""
        dims = {"scalar": 1, "vector": 7}

        if self.irrep_level >= IrrepLevel.STANDARD:
            dims["adjoint"] = 14
            dims["symmetric"] = 27

        if self.irrep_level >= IrrepLevel.EXTENDED:
            dims["mixed_64"] = 64
            dims["sym3_1"] = 77

        if self.irrep_level >= IrrepLevel.MAXIMAL:
            dims["sym3_2"] = 77
            dims["higher_189"] = 189

        return dims

    def _compute_invariants(self, x: torch.Tensor) -> torch.Tensor:
        """Compute G₂-invariant features from input.

        These invariants determine the mixing weights for irreps.
        """
        # Use ref_vectors directly (already on correct device via forward device check)
        refs = [F.normalize(ref, dim=0) for ref in self.ref_vectors]

        # CG struct is now a registered submodule, no device check needed

        # Norm
        norm_x = x.norm(dim=-1, keepdim=True)

        # Inner products
        inner_1 = torch.sum(x * refs[0], dim=-1, keepdim=True)
        inner_2 = torch.sum(x * refs[1], dim=-1, keepdim=True)
        inner_3 = torch.sum(x * refs[2], dim=-1, keepdim=True)

        # Cross product norm
        cross = self.cg._g2_struct.cross(x, refs[0].expand_as(x))
        cross_norm = cross.norm(dim=-1, keepdim=True)

        # Triple product φ(x, ref₁, ref₂)
        phi = self.cg._g2_struct.phi  # [7, 7, 7]
        triple = torch.einsum(
            "ijk,...i,...j,...k->...", phi, x, refs[0].expand_as(x), refs[1].expand_as(x)
        ).unsqueeze(-1)

        invariants = torch.cat([norm_x, inner_1, inner_2, inner_3, cross_norm, triple], dim=-1)

        return invariants

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Build irrep tower from input.

        GRADIENT FLOW FIXED (Dec 2, 2025):
        - All computed values are now used in forward pass
        - invariant_mlp output modulates irreps via learned mixing
        - irrep_attention applied for EXTENDED+ levels
        - All irrep_norms applied to their respective components

        Args:
            x: [..., 7] input in standard representation

        Returns:
            [..., target_dim] output with all irreps mixed
        """
        # Ensure module is on correct device (move once, not every forward)
        if self.ref_vectors[0].device != x.device:
            self.to(x.device)

        batch_shape = x.shape[:-1]

        # Compute invariants for mixing weights
        invariants = self._compute_invariants(x)
        mixing_raw = self.invariant_mlp(invariants)
        mixing = F.softmax(mixing_raw + self.irrep_weights, dim=-1)

        # Get reference vectors (use ALL of them)
        refs = [F.normalize(ref, dim=0) for ref in self.ref_vectors]

        # Level 0: Standard (7D) - apply normalization
        x_normed = self.irrep_norms["vector"](x)
        irreps = [x_normed]

        # Level 1: 7⊗7 decomposition (use ref[0] and ref[2] for diversity)
        decomp_77 = self.cg.decompose_7x7(x, refs[0].expand_as(x))
        decomp_77_alt = self.cg.decompose_7x7(x, refs[2].expand_as(x))  # Use ref[2]

        if self.irrep_level >= IrrepLevel.MINIMAL:
            # Normalize scalar and combine with alternative
            scalar_combined = (
                self.irrep_norms["scalar"](decomp_77["scalar"])
                + self.irrep_norms["scalar"](decomp_77_alt["scalar"])
            ) * 0.5
            irreps.append(scalar_combined)

        if self.irrep_level >= IrrepLevel.STANDARD:
            irreps.append(self.irrep_norms["adjoint"](decomp_77["adjoint"]))
            irreps.append(self.irrep_norms["symmetric"](decomp_77["symmetric"]))

        # Level 2: 7⊗14 decomposition - USE ALL OUTPUTS for gradient flow
        if self.irrep_level >= IrrepLevel.EXTENDED:
            decomp_714 = self.cg.decompose_7x14(x, decomp_77["adjoint"])

            # Use all outputs from 7x14: vector(7), symmetric(27), mixed_64(64)
            # The vector and symmetric from 7x14 provide additional expressiveness
            vec_714 = decomp_714["vector"]  # 7D - uses _proj_7x14_7
            sym_714 = decomp_714["symmetric"]  # 27D - uses _proj_7x14_27

            # Enhance vector irrep with 7x14 contribution
            irreps[0] = irreps[0] + 0.1 * vec_714

            # Add mixed_64 as new irrep
            irreps.append(self.irrep_norms["mixed_64"](decomp_714["mixed_64"]))

            # 14⊗14 for higher irreps - USE ALL OUTPUTS
            decomp_1414 = self.cg.decompose_14x14(
                decomp_77["adjoint"], self.cg.decompose_7x7(x, refs[1].expand_as(x))["adjoint"]
            )

            # Use all 14x14 outputs via residual connections
            scalar_1414 = decomp_1414["scalar"]  # 1D - uses _proj_14x14_1
            adj_1414 = decomp_1414["adjoint"]  # 14D - uses _proj_14x14_14
            sym_1414 = decomp_1414["symmetric"]  # 27D - uses _proj_14x14_27

            # Enhance scalar (irreps[1]) with 14x14 contribution
            irreps[1] = irreps[1] + 0.1 * scalar_1414

            # Find and update adjoint in irreps list (index 2 in STANDARD+)
            if len(irreps) > 2:
                irreps[2] = irreps[2] + 0.1 * self.irrep_norms["adjoint"](adj_1414)

            # Find and update symmetric in irreps list (index 3 in STANDARD+)
            # Also include contribution from 7x14 symmetric
            if len(irreps) > 3:
                irreps[3] = irreps[3] + 0.1 * (
                    self.irrep_norms["symmetric"](sym_1414) + self.irrep_norms["symmetric"](sym_714)
                )

            irreps.append(self.irrep_norms["sym3_1"](decomp_1414["sym3_1"]))

        # Level 3: Additional 77' and 189D for MAXIMAL
        if self.irrep_level >= IrrepLevel.MAXIMAL:
            irreps.append(self.irrep_norms["sym3_2"](decomp_1414["sym3_2"]))

            if self._higher_proj is not None:
                lower_cat = torch.cat(irreps, dim=-1)
                higher = self._higher_proj(lower_cat)
                irreps.append(self.irrep_norms["higher_189"](higher))

        # Concatenate all irreps
        all_irreps = torch.cat(irreps, dim=-1)

        # Apply irrep attention for EXTENDED+ (gradient flow fix)
        if self.irrep_level >= IrrepLevel.EXTENDED and self.irrep_attention is not None:
            # Reshape for attention: [B, num_irreps, embed_dim]
            B = x.shape[0] if x.dim() > 1 else 1
            total_dim = all_irreps.shape[-1]

            # Pad to multiple of 64 for attention
            pad_size = (64 - total_dim % 64) % 64
            if pad_size > 0:
                # F.pad output is already contiguous
                all_irreps_padded = F.pad(all_irreps, (0, pad_size))
            else:
                # Ensure contiguous before reshape to avoid extra copy
                all_irreps_padded = all_irreps.contiguous()

            num_chunks = all_irreps_padded.shape[-1] // 64
            # reshape on contiguous tensor doesn't copy
            irrep_chunks = all_irreps_padded.view(B, num_chunks, 64)

            # Self-attention over irrep chunks
            attn_out, _ = self.irrep_attention(irrep_chunks, irrep_chunks, irrep_chunks)
            attn_out = attn_out.reshape(B, -1)[:, :total_dim]  # Remove padding

            # Residual connection
            all_irreps = all_irreps + 0.1 * attn_out

        # Apply learned mixing weights to modulate output
        # Expand mixing to match all_irreps dimensions
        irrep_dims = [ir.shape[-1] for ir in irreps]

        # Create per-dimension weights from per-irrep weights
        weights_expanded = []
        for i, dim in enumerate(irrep_dims):
            if i < mixing.shape[-1]:
                weights_expanded.append(mixing[..., i : i + 1].expand(*batch_shape, dim))
            else:
                weights_expanded.append(torch.ones(*batch_shape, dim, device=x.device))
        mixing_full = torch.cat(weights_expanded, dim=-1)

        # Modulate irreps with mixing weights
        all_irreps = all_irreps * (1.0 + 0.1 * mixing_full)

        # Output projection
        output = self.output_proj(all_irreps)

        return cast(torch.Tensor, output)


__all__ = [
    "G2IrrepTower",
]
