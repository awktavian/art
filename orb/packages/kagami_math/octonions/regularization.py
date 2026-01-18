"""Octonion-Specific Regularization

Enforce geometric and algebraic constraints:
1. Unit norm: ||o|| = 1 (stay on S⁷)
2. Sparsity: Encourage sparse imaginary units
3. G₂ structure: Penalize deviations from G₂-invariant subspaces
4. Non-associativity: Preserve (discourage associative collapse)
"""

import logging
from typing import cast

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class OctonionRegularization(nn.Module):
    """Regularization losses for octonion networks.

    Components:
    - Unit norm penalty: ||o|| - 1
    - Sparsity: L1 on imaginary components
    - G₂ structure: Distance to nearest G₂ orbit
    - Diversity: Encourage different heads to use different units
    """

    def __init__(
        self,
        unit_norm_weight: float = 1.0,
        sparsity_weight: float = 0.1,
        g2_weight: float = 0.1,
        diversity_weight: float = 0.1,
    ) -> None:
        super().__init__()
        self.unit_norm_weight = unit_norm_weight
        self.sparsity_weight = sparsity_weight
        self.g2_weight = g2_weight
        self.diversity_weight = diversity_weight
        logger.info("✅ Octonion regularization: unit_norm + sparsity + G₂ + diversity")

    def unit_norm_loss(self, o: torch.Tensor) -> torch.Tensor:
        """Penalize deviation from S⁷.

        Args:
            o: [B, N, 8] or [B, 8] octonions

        Returns:
            loss: Mean squared deviation from unit norm
        """
        norms = o.norm(dim=-1)
        return cast(torch.Tensor, ((norms - 1.0) ** 2).mean())

    def sparsity_loss(self, o: torch.Tensor) -> torch.Tensor:
        """Encourage sparse imaginary components.

        Args:
            o: [B, N, 8] or [B, 8]

        Returns:
            loss: L1 on imaginary parts
        """
        imag = o[..., 1:]
        return imag.abs().mean()

    def g2_structure_loss(self, o: torch.Tensor) -> torch.Tensor:
        """Penalize deviations from G₂-invariant structure.

        G₂ acts on imaginary octonions (7D).
        Simplified proxy: Encourage alignment with Fano lines.

        Args:
            o: [B, N, 8]

        Returns:
            loss: Distance to nearest Fano line
        """
        imag = o[..., 1:]
        from kagami_math.fano_plane import FANO_LINES

        distances = []
        for line in FANO_LINES:
            line_indices = [i - 1 for i in line]
            mask = torch.ones(7, device=imag.device)
            mask[line_indices] = 0
            orthogonal = imag * mask.view(1, 1, 7)
            distance = orthogonal.norm(dim=-1).mean()
            distances.append(distance)
        # Use torch.stack to maintain gradient flow
        min_distance = torch.stack(distances).min()
        return min_distance

    def diversity_loss(self, o_heads: torch.Tensor) -> torch.Tensor:
        """Encourage different heads to use different imaginary units.

        Args:
            o_heads: [B, N, num_heads, 8]

        Returns:
            loss: Negative entropy of unit usage
        """
        if o_heads.dim() < 4:
            return torch.tensor(0.0, device=o_heads.device)
        imag_heads = o_heads[..., 1:]
        mean_activation = imag_heads.abs().mean(dim=[0, 1])
        probs = F.softmax(mean_activation, dim=-1)
        entropy = -(probs * torch.log(probs + 1e-08)).sum(dim=-1).mean()
        return -entropy

    def forward(
        self, o: torch.Tensor, o_heads: torch.Tensor | None = None
    ) -> dict[str, torch.Tensor]:
        """Compute all regularization losses.

        Args:
            o: [B, N, 8] or [B, 8] octonions
            o_heads: [B, N, num_heads, 8] optional multi-head octonions

        Returns:
            Dict of individual losses and total
        """
        losses = {}
        losses["unit_norm"] = self.unit_norm_loss(o) * self.unit_norm_weight
        losses["sparsity"] = self.sparsity_loss(o) * self.sparsity_weight
        losses["g2_structure"] = self.g2_structure_loss(o) * self.g2_weight
        if o_heads is not None:
            losses["diversity"] = self.diversity_loss(o_heads) * self.diversity_weight
        else:
            # Explicit tensor creation for type safety
            losses["diversity"] = torch.zeros(1, device=o.device, dtype=o.dtype).squeeze()
        # Type-safe sum: convert to list and use torch.stack
        total: torch.Tensor = torch.stack(list(losses.values())).sum()
        losses["total"] = total
        return losses
