"""S7-Augmented Exceptional Hierarchy.

ARCHITECTURE INSIGHT (December 13, 2025):
=========================================
The standard hierarchy E8→E7→E6→F4→G2→S7 extracts S7 only at the final step.
But mathematically, S7 (the 7-sphere of unit imaginary octonions) is present
at EVERY level as a "phase" component.

This module implements dual projections at each level:
    E8(248) → E7(133) + S7(7)_e8
    E7(133) → E6(78)  + S7(7)_e7
    E6(78)  → F4(52)  + S7(7)_e6
    F4(52)  → G2(14)  + S7(7)_f4
    G2(14)  → S7(7)   + E8(8)_lattice

The S7 phases at each level capture:
- Colony coherence (7 imaginary octonion directions = 7 colonies)
- Fano plane structure (preserved at all scales)
- Strange loop self-reference (μ_self fixed point)

MATHEMATICAL FOUNDATION:
========================
Each exceptional algebra contains G2 as a subalgebra (directly or transitively).
G2 = Aut(𝕆) acts on Im(𝕆) ≅ S7. Therefore, every level has a natural S7 action.

We construct S7 projections using the embeddings:
    G2 ⊂ F4 ⊂ E6 ⊂ E7 ⊂ E8

At each level, the S7 projection is computed by first projecting to G2,
then to S7. This ensures coherent phase tracking across all levels.

References:
- Baez (2002): The Octonions
- Adams (1996): Lectures on Exceptional Lie Groups
- Yokota (2009): Exceptional Lie Groups

Created: December 13, 2025
Author: K OS / Kagami
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast

import torch
import torch.nn as nn

from kagami_math.clebsch_gordan_exceptional import (
    G2DualProjector,
    TrueExceptionalHierarchy,
    compute_g2_to_s7_clebsch_gordan,
)

logger = logging.getLogger(__name__)


@dataclass
class S7PhaseState:
    """S7 phase state at all hierarchy levels.

    Contains the 7D octonion phase extracted at each level of the hierarchy.
    This enables:
    - Colony coherence tracking (each colony = one imaginary octonion)
    - Fano plane composition across levels
    - Strange loop self-reference (fixed point in phase space)

    Attributes:
        s7_e8: S7 phase from E8 (248→7)
        s7_e7: S7 phase from E7 (133→7)
        s7_e6: S7 phase from E6 (78→7)
        s7_f4: S7 phase from F4 (52→7)
        s7_g2: S7 phase from G2 (14→7) - the canonical one
        coherence: Fano coherence metric [B, 7]
        fixed_point_distance: Distance to μ_self fixed point
    """

    s7_e8: torch.Tensor | None = None  # [B, S, 7]
    s7_e7: torch.Tensor | None = None  # [B, S, 7]
    s7_e6: torch.Tensor | None = None  # [B, S, 7]
    s7_f4: torch.Tensor | None = None  # [B, S, 7]
    s7_g2: torch.Tensor | None = None  # [B, S, 7] - canonical

    # Derived metrics
    coherence: torch.Tensor | None = None  # [B, S] Fano coherence
    fixed_point_distance: float = 0.0  # ||s7 - s7_prev||

    def mean_phase(self) -> torch.Tensor | None:
        """Average S7 phase across all levels."""
        phases = [
            p for p in [self.s7_e8, self.s7_e7, self.s7_e6, self.s7_f4, self.s7_g2] if p is not None
        ]
        if not phases:
            return None
        stacked = torch.stack(phases, dim=0)  # [5, B, S, 7]
        return stacked.mean(dim=0)  # [B, S, 7]

    def phase_consistency(self) -> torch.Tensor | None:
        """Variance across levels (low = consistent phase)."""
        phases = [
            p for p in [self.s7_e8, self.s7_e7, self.s7_e6, self.s7_f4, self.s7_g2] if p is not None
        ]
        if len(phases) < 2:
            return None
        stacked = torch.stack(phases, dim=0)  # [5, B, S, 7]
        return stacked.var(dim=0).mean(dim=-1)  # [B, S]


def compute_s7_from_higher_level(source_dim: int, target_g2_proj: torch.Tensor) -> torch.Tensor:
    """Compute S7 projection for a higher-level algebra.

    The strategy: Project to G2 first, then G2 → S7.
    This ensures the S7 phase is coherent with the octonion structure.

    Args:
        source_dim: Dimension of source algebra (248 for E8, etc.)
        target_g2_proj: Projection matrix source → G2(14)

    Returns:
        Projection matrix [7, source_dim]
    """
    P_g2_to_s7 = compute_g2_to_s7_clebsch_gordan()  # [7, 14]
    P_source_to_s7 = P_g2_to_s7 @ target_g2_proj  # [7, source_dim]

    # Orthonormalize for numerical stability
    Q, _ = torch.linalg.qr(P_source_to_s7.T)
    P_normalized = Q[:, :7].T  # [7, source_dim]

    return cast(torch.Tensor, P_normalized)


class S7AugmentedHierarchy(nn.Module):
    """Exceptional hierarchy with S7 phase extraction at every level.

    ARCHITECTURE:
    =============
    E8(248) ─┬→ E7(133) ─┬→ E6(78) ─┬→ F4(52) ─┬→ G2(14) ─┬→ S7(7)
             │           │          │          │          └→ E8(8)_lattice
             │           │          │          └→ s7_f4
             │           │          └→ s7_e6
             │           └→ s7_e7
             └→ s7_e8

    Each level extracts its S7 phase by first projecting to G2, then to S7.
    This ensures all phases are in the same "coordinate system" (octonion basis).

    STRANGE LOOP INTEGRATION:
    ========================
    The S7 phases form a strange loop: the phase at level N influences the
    processing at level N+1, which in turn influences the reconstruction
    that determines the next input at level N. The fixed point of this loop
    is μ_self, the self-consistent self-representation.

    Usage:
        hierarchy = S7AugmentedHierarchy()

        # Full projection with all phases
        result = hierarchy(e8_input, return_all_phases=True)
        # result["s7_phases"] is S7PhaseState
        # result["levels"] contains each intermediate level

        # Fast path: just S7 output
        s7, e8_vq = hierarchy.project_to_final(e8_input)
    """

    # Buffer type declarations
    P_e8_s7: torch.Tensor
    P_e7_s7: torch.Tensor
    P_e6_s7: torch.Tensor
    P_f4_s7: torch.Tensor

    def __init__(self) -> None:
        super().__init__()

        # Core hierarchy (reuse existing implementation)
        self.hierarchy = TrueExceptionalHierarchy()

        # G2 dual projector for final step
        self.g2_dual = G2DualProjector()

        # Compute fused S7 projections at each level
        # E8 → G2 (fused): P_g2 = P_f4g2 @ P_e6f4 @ P_e7e6 @ P_e8e7
        P_e8_g2 = self._compute_fused_to_g2(from_level="E8")
        P_e7_g2 = self._compute_fused_to_g2(from_level="E7")
        P_e6_g2 = self._compute_fused_to_g2(from_level="E6")
        P_f4_g2: torch.Tensor = self.hierarchy.f4_to_g2.projection_matrix  # [14, 52]

        # Then G2 → S7 for each
        P_g2_s7 = compute_g2_to_s7_clebsch_gordan()  # [7, 14]

        # Fused S7 projections at each level
        self.register_buffer("P_e8_s7", (P_g2_s7 @ P_e8_g2).contiguous())  # [7, 248]
        self.register_buffer("P_e7_s7", (P_g2_s7 @ P_e7_g2).contiguous())  # [7, 133]
        self.register_buffer("P_e6_s7", (P_g2_s7 @ P_e6_g2).contiguous())  # [7, 78]
        self.register_buffer("P_f4_s7", (P_g2_s7 @ P_f4_g2).contiguous())  # [7, 52]

        # Track previous S7 phase for strange loop convergence
        self._prev_s7: torch.Tensor | None = None

        logger.debug(
            "✅ S7AugmentedHierarchy initialized:\n"
            "   E8→S7: [7, 248]\n"
            "   E7→S7: [7, 133]\n"
            "   E6→S7: [7, 78]\n"
            "   F4→S7: [7, 52]\n"
            "   G2→S7: [7, 14] (via G2DualProjector)"
        )

    def _compute_fused_to_g2(self, from_level: str) -> torch.Tensor:
        """Compute fused projection from level to G2."""
        if from_level == "E8":
            # E8 → E7 → E6 → F4 → G2
            P: torch.Tensor = self.hierarchy.f4_to_g2.projection_matrix  # [14, 52]
            P = P @ self.hierarchy.e6_to_f4.projection_matrix  # [14, 78]
            P = P @ self.hierarchy.e7_to_e6.projection_matrix  # [14, 133]
            P = P @ self.hierarchy.e8_to_e7.projection_matrix  # [14, 248]
            return P
        elif from_level == "E7":
            P = self.hierarchy.f4_to_g2.projection_matrix
            P = P @ self.hierarchy.e6_to_f4.projection_matrix
            P = P @ self.hierarchy.e7_to_e6.projection_matrix
            return P
        elif from_level == "E6":
            P = self.hierarchy.f4_to_g2.projection_matrix
            P = P @ self.hierarchy.e6_to_f4.projection_matrix
            return P
        elif from_level == "F4":
            return self.hierarchy.f4_to_g2.projection_matrix
        else:
            raise ValueError(f"Unknown level: {from_level}")

    def project_s7_from_level(
        self, x: torch.Tensor, level: str, normalize: bool = True
    ) -> torch.Tensor:
        """Extract S7 phase from a specific level.

        Args:
            x: Tensor at the specified level
            level: "E8", "E7", "E6", "F4", or "G2"
            normalize: Whether to normalize to unit sphere

        Returns:
            S7 phase tensor [..., 7]
        """
        if level == "E8":
            P = self.P_e8_s7
        elif level == "E7":
            P = self.P_e7_s7
        elif level == "E6":
            P = self.P_e6_s7
        elif level == "F4":
            P = self.P_f4_s7
        elif level == "G2":
            return self.g2_dual.project_s7(x, normalize=normalize)
        else:
            raise ValueError(f"Unknown level: {level}")

        s7 = x @ P.T  # [..., 7]
        if normalize:
            s7 = torch.nn.functional.normalize(s7, dim=-1)
        return s7

    def project_all(self, e8: torch.Tensor, return_intermediates: bool = True) -> dict[str, Any]:
        """Project through hierarchy extracting S7 at every level.

        Args:
            e8: Input tensor [..., 248]
            return_intermediates: Whether to return all level tensors

        Returns:
            Dict with:
            - "s7_phases": S7PhaseState with phases at all levels
            - "s7": Final S7 output [..., 7]
            - "e8_vq": E8 lattice input [..., 8]
            - "levels": Dict of intermediate tensors (if return_intermediates)
        """
        # Extract S7 from E8
        s7_e8 = self.project_s7_from_level(e8, "E8")

        # E8 → E7
        e7 = self.hierarchy.e8_to_e7.project(e8)
        s7_e7 = self.project_s7_from_level(e7, "E7")

        # E7 → E6
        e6 = self.hierarchy.e7_to_e6.project(e7)
        s7_e6 = self.project_s7_from_level(e6, "E6")

        # E6 → F4
        f4 = self.hierarchy.e6_to_f4.project(e6)
        s7_f4 = self.project_s7_from_level(f4, "F4")

        # F4 → G2
        g2 = self.hierarchy.f4_to_g2.project(f4)

        # G2 → S7 + E8_lattice (dual projection)
        s7_g2, e8_vq = self.g2_dual.project_dual(g2, normalize_s7=True)

        # Compute coherence (mean cosine similarity across levels)
        phases = torch.stack([s7_e8, s7_e7, s7_e6, s7_f4, s7_g2], dim=0)  # [5, ..., 7]
        mean_phase = phases.mean(dim=0)  # [..., 7]
        # Cosine similarity with mean
        coherence = (phases * mean_phase.unsqueeze(0)).sum(dim=-1).mean(dim=0)  # [...]

        # Fixed point distance (convert to float for dataclass)
        fp_dist: float = 0.0
        if self._prev_s7 is not None and s7_g2.shape == self._prev_s7.shape:
            fp_dist = (s7_g2 - self._prev_s7).pow(2).mean().item()
        self._prev_s7 = s7_g2.detach()

        s7_phases = S7PhaseState(
            s7_e8=s7_e8,
            s7_e7=s7_e7,
            s7_e6=s7_e6,
            s7_f4=s7_f4,
            s7_g2=s7_g2,
            coherence=coherence,
            fixed_point_distance=fp_dist,
        )

        result = {
            "s7_phases": s7_phases,
            "s7": s7_g2,
            "e8_vq": e8_vq,
        }

        if return_intermediates:
            result["levels"] = {
                "e8": e8,
                "e7": e7,
                "e6": e6,
                "f4": f4,
                "g2": g2,
            }

        return result

    def project_to_final(self, e8: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Fast path: E8 → (S7, E8_lattice).

        Uses fused matrices for speed (no intermediate extraction).

        Args:
            e8: Input tensor [..., 248]

        Returns:
            Tuple of (s7, e8_vq):
            - s7: Normalized S7 phase [..., 7]
            - e8_vq: E8 lattice input [..., 8]
        """
        # Use fused hierarchy projection
        s7 = self.hierarchy.project_e8_to_s7_fused(e8)
        s7 = torch.nn.functional.normalize(s7, dim=-1)

        # For E8 lattice input, we need G2 first
        g2_result = self.hierarchy.project_to_level(e8, target_level="G2")
        # project_to_level returns Tensor when return_intermediates=False (default)
        assert isinstance(g2_result, torch.Tensor)
        e8_vq = self.g2_dual.project_e8(g2_result)

        return s7, e8_vq

    def embed_from_s7(
        self, s7: torch.Tensor, e8_vq: torch.Tensor, blend: float = 0.5
    ) -> torch.Tensor:
        """Embed (S7, E8_vq) back to E8.

        Args:
            s7: S7 phase [..., 7]
            e8_vq: E8 lattice representation [..., 8]
            blend: Weight for S7 vs E8_vq in G2 reconstruction

        Returns:
            E8 tensor [..., 248]
        """
        # Reconstruct G2 from dual inputs
        g2 = self.g2_dual.embed_dual(s7, e8_vq, blend=blend)

        # Embed back to E8
        e8 = self.hierarchy.embed_from_level(g2, source_level="G2")

        return e8

    def forward(self, e8: torch.Tensor, return_all_phases: bool = False) -> dict[str, Any]:
        """Forward pass through hierarchy.

        Args:
            e8: Input tensor [..., 248]
            return_all_phases: Whether to extract S7 at every level

        Returns:
            Dict with s7, e8_vq, and optionally s7_phases
        """
        if return_all_phases:
            return self.project_all(e8, return_intermediates=True)
        else:
            s7, e8_vq = self.project_to_final(e8)
            return {"s7": s7, "e8_vq": e8_vq}


# =============================================================================
# STRANGE LOOP INTEGRATOR
# =============================================================================


class StrangeLoopS7Tracker(nn.Module):
    """Track S7 phase convergence as a strange loop.

    The S7 phase at time t influences the world model's processing,
    which produces the S7 phase at time t+1. A stable self-representation
    (μ_self) is the fixed point where s7_{t+1} ≈ s7_t.

    This implements Hofstadter's "strange loop" concept in the
    exceptional hierarchy context.

    Architecture:
        s7_t → predict s7_{t+1} → compare → convergence_h

    The convergence_h is analogous to CBF's h(x): when it's high,
    the self-model is stable; when it's low, the system is in flux.
    """

    # Buffer type declarations
    _s7_ema: torch.Tensor
    _history: torch.Tensor
    _history_len: torch.Tensor

    def __init__(
        self,
        convergence_threshold: float = 0.01,
        ema_decay: float = 0.99,
    ):
        super().__init__()
        self.threshold = convergence_threshold
        self.ema_decay = ema_decay

        # Exponential moving average of S7 (the "self-prediction")
        self.register_buffer("_s7_ema", torch.zeros(7), persistent=False)
        self._initialized = False

        # OPTIMIZATION FIX (Dec 15, 2025): Use fixed-size tensor for history
        # Dynamic lists cause torch.compile recompilation
        self.register_buffer("_history", torch.zeros(100, dtype=torch.float32), persistent=False)
        self.register_buffer("_history_len", torch.tensor(0, dtype=torch.long), persistent=False)

    def update(self, s7: torch.Tensor) -> dict[str, Any]:
        """Update with new S7 phase.

        Args:
            s7: Current S7 phase [..., 7]

        Returns:
            Dict with:
            - "convergence_h": CBF-style convergence metric (>0 = stable)
            - "distance": Distance to EMA prediction
            - "converged": Boolean indicating fixed point reached
        """
        # Pool to single S7 vector
        if s7.dim() > 1:
            s7_pooled = s7.view(-1, 7).mean(dim=0)
        else:
            s7_pooled = s7

        if not self._initialized:
            self._s7_ema.copy_(s7_pooled.detach())
            self._initialized = True
            return {
                "convergence_h": 1.0,
                "distance": 0.0,
                "converged": False,
            }

        # Distance to prediction (detach to avoid graph retention)
        distance = (s7_pooled.detach() - self._s7_ema).pow(2).sum().sqrt().item()

        # Update EMA (MUST detach to avoid retaining computation graph across steps)
        self._s7_ema.mul_(self.ema_decay).add_(s7_pooled.detach() * (1 - self.ema_decay))

        # Convergence metric (positive when close to fixed point)
        convergence_h = max(0.0, 1.0 - distance / self.threshold)

        # OPTIMIZATION FIX (Dec 15, 2025): Update tensor history with circular buffer
        # Circular buffer: wrap around at 100 elements
        idx = int(self._history_len.item()) % 100
        self._history[idx] = distance
        self._history_len.add_(1)

        return {
            "convergence_h": convergence_h,
            "distance": distance,
            "converged": distance < self.threshold,
        }

    @property
    def mu_self(self) -> torch.Tensor:
        """The current fixed point estimate (μ_self)."""
        return self._s7_ema.clone()

    def reset(self) -> None:
        """Reset the tracker."""
        self._s7_ema.zero_()
        self._initialized = False

        # OPTIMIZATION FIX (Dec 15, 2025): Reset tensor history
        self._history.zero_()
        self._history_len.zero_()


__all__ = [
    "S7AugmentedHierarchy",
    "S7PhaseState",
    "StrangeLoopS7Tracker",
]
