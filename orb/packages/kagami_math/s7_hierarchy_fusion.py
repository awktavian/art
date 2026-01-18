"""S7 Hierarchy Fusion - Unified S7 Phase Extraction and Fusion.

COHERENCY REFACTOR (December 27, 2025):
=======================================
This module consolidates duplicate S7 hierarchy logic from:
- OrganismRSSM._fuse_s7_hierarchy()
- KagamiWorldModel._extract_s7_at_all_levels()

Both components now use this single source of truth for S7 phase operations.

MATHEMATICAL FOUNDATION:
========================
S⁷ = Unit sphere in Im(𝕆) = {x ∈ Im(𝕆) : ||x|| = 1}

The exceptional Lie hierarchy provides multiple projections to S⁷:
    E8(248) → S⁷ (richest, noisiest)
    E7(133) → S⁷ (gravity-like)
    E6(78)  → S⁷ (electroweak-like)
    F4(52)  → S⁷ (strong-like)
    G₂(14)  → S⁷ (canonical)

Fusion combines these views with learned weights to produce a robust S⁷ phase.

Created: December 27, 2025
Author: Forge (coherency refactor)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class S7HierarchyPhases:
    """Container for S7 phases at all hierarchy levels.

    Attributes:
        s7_e8: S7 from E8(248) projection [B, 7] or None
        s7_e7: S7 from E7(133) projection [B, 7] or None
        s7_e6: S7 from E6(78) projection [B, 7] or None
        s7_f4: S7 from F4(52) projection [B, 7] or None
        s7_g2: S7 from G2(14) projection (canonical) [B, 7] or None
        fused: Fused S7 phase [B, 7]
        coherence: Cross-level coherence score [B] or scalar
    """

    s7_e8: torch.Tensor | None = None
    s7_e7: torch.Tensor | None = None
    s7_e6: torch.Tensor | None = None
    s7_f4: torch.Tensor | None = None
    s7_g2: torch.Tensor | None = None
    fused: torch.Tensor | None = None
    coherence: torch.Tensor | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "s7_e8": self.s7_e8.tolist() if self.s7_e8 is not None else None,
            "s7_e7": self.s7_e7.tolist() if self.s7_e7 is not None else None,
            "s7_e6": self.s7_e6.tolist() if self.s7_e6 is not None else None,
            "s7_f4": self.s7_f4.tolist() if self.s7_f4 is not None else None,
            "s7_g2": self.s7_g2.tolist() if self.s7_g2 is not None else None,
            "fused": self.fused.tolist() if self.fused is not None else None,
            "coherence": float(self.coherence.mean()) if self.coherence is not None else None,
        }


class S7HierarchyFusion(nn.Module):
    """Unified S7 hierarchy fusion module.

    SINGLE SOURCE OF TRUTH for S7 phase fusion across the codebase.

    Replaces:
    - OrganismRSSM._fuse_s7_hierarchy()
    - Implicit fusion in KagamiWorldModel._extract_s7_at_all_levels()

    Architecture:
    - Learnable weights for 4 hierarchy levels (E8, E7, E6, F4)
    - Optional projection for richer fusion (concat → project)
    - Residual connection with primary S7 phase
    - Coherence computation across levels
    """

    def __init__(
        self,
        s7_dim: int = 7,
        use_projection: bool = True,
        init_weights: tuple[float, ...] = (0.4, 0.3, 0.2, 0.1),
        alpha_init: float = 0.7,
    ):
        """Initialize S7 hierarchy fusion.

        Args:
            s7_dim: Dimension of S7 phase (default 7)
            use_projection: Whether to use MLP projection for richer fusion
            init_weights: Initial weights for (E8, E7, E6, F4) levels
            alpha_init: Initial blend factor for hierarchy vs primary
        """
        super().__init__()
        self.s7_dim = s7_dim
        self.use_projection = use_projection

        # Learnable weights for hierarchy levels (softmax-normalized)
        self.hierarchy_weights = nn.Parameter(torch.tensor(init_weights))

        # Learnable alpha for hierarchy vs primary blend
        # sigmoid(alpha_init_logit) ≈ alpha_init
        alpha_init_logit = torch.log(torch.tensor(alpha_init / (1 - alpha_init)))
        self.alpha_logit = nn.Parameter(alpha_init_logit)

        # Optional projection for richer fusion
        if use_projection:
            self.projection = nn.Sequential(
                nn.Linear(s7_dim * 4, s7_dim * 2),
                nn.GELU(),
                nn.Linear(s7_dim * 2, s7_dim),
                nn.Tanh(),  # Bounded output for phase
            )
        else:
            self.projection = None  # type: ignore[assignment]

    def forward(
        self,
        s7_primary: torch.Tensor,
        s7_e8: torch.Tensor | None = None,
        s7_e7: torch.Tensor | None = None,
        s7_e6: torch.Tensor | None = None,
        s7_f4: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        """Fuse multi-level S7 phases.

        Args:
            s7_primary: Primary S7 phase [B, 7] (always required, typically from G2)
            s7_e8: S7 from E8(248) projection [B, 7] (optional)
            s7_e7: S7 from E7(133) projection [B, 7] (optional)
            s7_e6: S7 from E6(78) projection [B, 7] (optional)
            s7_f4: S7 from F4(52) projection [B, 7] (optional)

        Returns:
            fused: Fused S7 phase [B, 7]
            info: Dict with fusion metadata (weights, coherence, etc.)
        """
        B = s7_primary.size(0)
        device = s7_primary.device
        dtype = s7_primary.dtype

        # If no hierarchy phases provided, return primary directly
        hierarchy_phases = [s7_e8, s7_e7, s7_e6, s7_f4]
        if all(p is None for p in hierarchy_phases):
            return s7_primary, {"fusion_mode": "primary_only", "coherence": 1.0}

        # Build hierarchy tensor, replacing None with zeros
        phases = []
        for phase in hierarchy_phases:
            if phase is not None:
                # Handle sequence dimension if present [B, T, 7] → [B, 7]
                if phase.dim() == 3:
                    phase = phase[:, -1, :]  # Take last timestep
                phases.append(phase.to(device=device, dtype=dtype))
            else:
                phases.append(torch.zeros(B, self.s7_dim, device=device, dtype=dtype))

        # Stack: [B, 4, 7]
        hierarchy = torch.stack(phases, dim=1)

        # Compute normalized weights
        weights = F.softmax(self.hierarchy_weights, dim=0)  # [4]

        # Weighted sum: [B, 7]
        weighted_sum = (hierarchy * weights.view(1, 4, 1)).sum(dim=1)

        # Optional projection for richer fusion
        if self.projection is not None:
            # Concatenate all levels: [B, 28]
            concat = hierarchy.view(B, -1)
            projected = self.projection(concat)  # [B, 7]

            # Blend weighted sum with projection (50/50)
            fused_hierarchy = 0.5 * weighted_sum + 0.5 * projected
        else:
            fused_hierarchy = weighted_sum  # type: ignore[unreachable]

        # Compute alpha (blend factor for hierarchy vs primary)
        alpha = torch.sigmoid(self.alpha_logit)

        # Final fusion: blend hierarchy with primary
        fused = alpha * fused_hierarchy + (1 - alpha) * s7_primary

        # Normalize to S7 sphere
        fused = F.normalize(fused, dim=-1, eps=1e-8)

        # Compute coherence (how well do levels agree?)
        # Lower variance across levels = higher coherence
        if any(p is not None for p in hierarchy_phases):
            # Only compute variance across non-None levels
            valid_phases = [p for p in hierarchy_phases if p is not None]
            if len(valid_phases) > 1:
                stacked = torch.stack(
                    [p if p.dim() == 2 else p[:, -1, :] for p in valid_phases], dim=1
                )  # [B, N, 7]
                variance = stacked.var(dim=1).mean(dim=-1)  # [B]
                coherence = 1.0 / (1.0 + variance)  # Higher coherence when lower variance
            else:
                coherence = torch.ones(B, device=device)
        else:
            coherence = torch.ones(B, device=device)

        info = {
            "fusion_mode": "hierarchy",
            "alpha": float(alpha.item()),
            "weights": weights.tolist(),
            "coherence": float(coherence.mean().item()),
            "num_hierarchy_levels": sum(1 for p in hierarchy_phases if p is not None),
        }

        return fused, info

    def extract_phases(
        self,
        s7_primary: torch.Tensor,
        s7_e8: torch.Tensor | None = None,
        s7_e7: torch.Tensor | None = None,
        s7_e6: torch.Tensor | None = None,
        s7_f4: torch.Tensor | None = None,
        s7_g2: torch.Tensor | None = None,
    ) -> S7HierarchyPhases:
        """Extract and package all S7 phases with fusion.

        Convenience method that returns S7HierarchyPhases dataclass.

        Args:
            s7_primary: Primary S7 phase (used for fusion)
            s7_e8, s7_e7, s7_e6, s7_f4: Hierarchy level phases
            s7_g2: G2-level S7 (often same as s7_primary)

        Returns:
            S7HierarchyPhases with all phases and fused result
        """
        fused, info = self.forward(s7_primary, s7_e8, s7_e7, s7_e6, s7_f4)

        return S7HierarchyPhases(
            s7_e8=s7_e8,
            s7_e7=s7_e7,
            s7_e6=s7_e6,
            s7_f4=s7_f4,
            s7_g2=s7_g2 if s7_g2 is not None else s7_primary,
            fused=fused,
            coherence=torch.tensor(info["coherence"]),
        )


# =============================================================================
# SINGLETON
# =============================================================================

_FUSION_MODULE: S7HierarchyFusion | None = None


def get_s7_hierarchy_fusion(device: str = "cpu") -> S7HierarchyFusion:
    """Get or create global S7HierarchyFusion instance.

    Args:
        device: Device to place module on

    Returns:
        S7HierarchyFusion module
    """
    global _FUSION_MODULE
    if _FUSION_MODULE is None:
        _FUSION_MODULE = S7HierarchyFusion()
        _FUSION_MODULE = _FUSION_MODULE.to(device)
        logger.info(f"S7HierarchyFusion initialized on {device}")
    return _FUSION_MODULE


def reset_s7_hierarchy_fusion() -> None:
    """Reset global S7HierarchyFusion instance."""
    global _FUSION_MODULE
    _FUSION_MODULE = None


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "S7HierarchyFusion",
    "S7HierarchyPhases",
    "get_s7_hierarchy_fusion",
    "reset_s7_hierarchy_fusion",
]
