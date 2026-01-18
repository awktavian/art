"""Reconstruction and prediction loss functions.

This module provides core loss functions for reconstruction and prediction,
including DreamerV3-style symlog losses.

Mathematical Foundation:
========================
- Symlog prediction loss: L = (symlog(pred) - symlog(target))²
- Benefits: multi-scale targets, bounded gradients, small-target attention

Created: December 15, 2025 (refactored from unified_loss.py)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch
import torch.nn as nn
import torch.nn.functional as F

from kagami.core.world_model.dreamer_transforms import symlog

if TYPE_CHECKING:
    from kagami.core.world_model.losses.composed import LossConfig


def symlog_squared_loss(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Symlog-squared loss from DreamerV3.

    L = (symlog(pred) - symlog(target))²

    Benefits over MSE:
    - Handles multi-scale targets without normalization
    - Gradient magnitude bounded for large targets
    - Small targets get appropriate attention

    Args:
        pred: Model predictions
        target: Ground truth targets

    Returns:
        Scalar loss tensor
    """
    return (symlog(pred) - symlog(target)).pow(2).mean()


def free_bits_kl(kl: torch.Tensor, free_nats: float = 1.0) -> torch.Tensor:
    """Apply free bits constraint to KL divergence.

    DreamerV3: Clips KL below threshold to prevent posterior collapse
    while allowing the model to focus on prediction loss when KL is
    already minimized.

    Args:
        kl: Per-dimension KL divergence
        free_nats: Minimum bits (in nats) to allow. DreamerV3 uses 1.0.

    Returns:
        Clipped KL divergence
    """
    return torch.maximum(kl, torch.full_like(kl, free_nats))


class GeometricLossComputer(nn.Module):
    """Computes losses that exploit geometric structure.

    This module understands the E8, Fano, and H¹⁴ × S⁷ structure
    and creates loss terms that encourage geometric coherence.
    """

    def __init__(self, config: LossConfig) -> None:
        super().__init__()
        self.config = config

        # Fano lines for synergy computation (0-indexed)
        from kagami_math.fano_plane import get_fano_lines_zero_indexed

        fano_lines = get_fano_lines_zero_indexed()
        self.register_buffer("fano_lines", torch.tensor(fano_lines, dtype=torch.long))

        # E8 root categories for semantic-aware commitment
        # First 84 roots are Fano-aligned (most important)
        # Roots 84-111 are Kagami-colony (observer interactions)
        # Roots 112-239 are dense Type 2
        self.register_buffer("e8_importance", self._build_e8_importance_weights())

    def _build_e8_importance_weights(self) -> torch.Tensor:
        """Build importance weights for E8 roots based on semantic structure."""
        weights = torch.ones(240)
        # Fano triples (most important for colony coordination)
        weights[:84] = 1.5
        # Kagami-colony pairs (observer interactions)
        weights[84:112] = 1.2
        # Safe dense (Type 2 balanced)
        weights[112:211] = 1.0
        # Alert dense (Type 2 extreme - higher weight to avoid)
        weights[211:240] = 0.8
        return weights

    def e8_commitment_loss(
        self,
        s7_phase: torch.Tensor,
        e8_quantized: torch.Tensor,
        e8_indices: torch.Tensor,
    ) -> torch.Tensor:
        """Geometry-aware E8 commitment loss.

        Unlike simple MSE, this weights commitment by:
        1. Root importance (Fano > Kagami > Dense)
        2. Distance to nearest root (penalize amorphous states)

        Args:
            s7_phase: Continuous S⁷ representation [B, S, 8]
            e8_quantized: Quantized E8 vectors [B, S, 8]
            e8_indices: E8 root indices [B, S]

        Returns:
            Weighted commitment loss
        """
        # Dec 2025: e8_quantized is 8D octonion, s7_phase is 7D S⁷
        # Project E8 octonion to S⁷ (drop real part, normalize imaginary)
        s7_flat = s7_phase.reshape(-1, 7)

        # E8 octonions [B, S, 8] -> imaginary part [B, S, 7]
        if e8_quantized.shape[-1] == 8:
            e8_imag = e8_quantized[..., 1:]  # Drop real part (e₀)
        else:
            e8_imag = e8_quantized
        e8_flat = e8_imag.reshape(-1, 7)
        indices_flat = e8_indices.reshape(-1)

        # Per-sample commitment error
        commitment_error = (s7_flat - e8_flat.detach()).pow(2).sum(dim=-1)

        # Weight by root importance
        importance = self.e8_importance[indices_flat.clamp(0, 239)]  # type: ignore[index]
        weighted_commitment = (commitment_error * importance).mean()

        return weighted_commitment * self.config.e8_commitment_weight

    def fano_synergy_loss(
        self,
        colony_activations: torch.Tensor,
        use_parallel: bool = True,
        use_vitals_weighting: bool = True,
    ) -> torch.Tensor:
        """Loss encouraging Fano-aligned colony interactions.

        CONSOLIDATED (Dec 1, 2025):
        - Uses ParallelFanoProducts for efficient batched computation when available
        - Optionally weights by live FanoVitals for adaptive training
        - This is the SINGLE source for Fano synergy loss

        Colonies on the same Fano line should have coherent activations.
        e_i × e_j = ±e_k for Fano lines (i, j, k).

        Args:
            colony_activations: [B, 7, 8] or dict[str, Any] of domain → [B, 8]
            use_parallel: Use ParallelFanoProducts (faster, recommended)
            use_vitals_weighting: Weight lines by FanoVitals synergy (adaptive)

        Returns:
            Fano coherence loss
        """
        if isinstance(colony_activations, dict):
            # Convert dict[str, Any] to tensor
            B = next(iter(colony_activations.values())).shape[0]
            device = next(iter(colony_activations.values())).device
            colonies = torch.zeros(B, 7, 8, device=device)
            domain_order = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
            for i, domain in enumerate(domain_order):
                if domain in colony_activations:
                    colonies[:, i] = colony_activations[domain]
        else:
            colonies = colony_activations

        if colonies.dim() == 2:
            return torch.tensor(0.0, device=colonies.device)

        # Validate colonies shape: must be [B, 7, 8] for 7 Fano colonies in E8 space
        if colonies.shape[1] != 7:
            # Wrong shape - likely sequence length mistaken for colonies dimension
            return torch.tensor(0.0, device=colonies.device)

        device = colonies.device

        # Parallel path removed (Dec 2025): legacy root-shell quantizer deleted.
        _ = use_parallel

        # Get vitals-based weights if enabled
        line_weights = torch.ones(7, device=device)
        if use_vitals_weighting:
            try:
                # Dynamic import to avoid world_model.losses ↔ unified_agents cycles.
                import importlib

                agents_mod = importlib.import_module("kagami.core.unified_agents")
                get_fano_vitals = getattr(agents_mod, "get_fano_vitals", None)
                if get_fano_vitals is None:
                    raise ImportError("get_fano_vitals not available")
                vitals = get_fano_vitals()
                # FIX (Dec 5, 2025): Use correct attribute access
                if hasattr(vitals, "line_synergies"):
                    synergies = vitals.line_synergies
                    for i in range(min(7, len(synergies))):
                        # Inverse synergy: low synergy = high weight (needs more training)
                        line_weights[i] = 1.0 - synergies[i] + 0.1
                elif hasattr(vitals, "synergy"):
                    # Single synergy score - use for all lines
                    line_weights[:] = 1.0 - vitals.synergy + 0.1
            except (ImportError, AttributeError):
                pass  # Use uniform weights

        fano_loss = torch.tensor(0.0, device=device)

        # For each Fano line, check that product is aligned
        for line_idx in range(7):
            i, j, k = self.fano_lines[line_idx]  # type: ignore[index]

            c_i = colonies[:, i]  # [B, 8]
            c_j = colonies[:, j]  # [B, 8]
            c_k = colonies[:, k]  # [B, 8]

            # Hadamard proxy for octonion product (same proxy used elsewhere in KagamiWorldModel)
            # We want (c_i ⊙ c_j) to be directionally aligned with c_k on each Fano line.
            product = c_i * c_j  # [B, 8]
            cos_sim = F.cosine_similarity(product, c_k, dim=-1).abs()  # [B] in [0, 1]

            # Penalize misalignment, weighted by inverse synergy
            line_loss = (1.0 - cos_sim).mean()
            fano_loss = fano_loss + line_weights[line_idx] * line_loss

        return fano_loss / 7.0 * self.config.fano_synergy_weight

    def manifold_curvature_loss(
        self,
        z_hyp: torch.Tensor,
        s7_phase: torch.Tensor,
    ) -> torch.Tensor:
        """Regularize curvature on H¹⁴ × S⁷ manifold.

        In hyperbolic space H¹⁴:
        - Points near origin have low uncertainty
        - Points near boundary have high uncertainty

        On S⁷:
        - Unit norm is enforced (already done via normalization)
        - Geodesic smoothness encouraged

        Args:
            z_hyp: Hyperbolic coordinates [B, S, 14]
            s7_phase: S⁷ phase [B, S, 8]

        Returns:
            Curvature regularization loss
        """
        # Hyperbolic: penalize extreme radii (too certain or too uncertain)
        hyp_radius = z_hyp.norm(dim=-1)  # [B, S]
        # Poincaré ball: valid radius < 1, prefer 0.3-0.7 range
        hyp_penalty = F.relu(hyp_radius - 0.9) + F.relu(0.1 - hyp_radius)

        # S⁷: penalize deviation from unit sphere (should already be normalized)
        s7_radius = s7_phase.norm(dim=-1)  # [B, S]
        s7_penalty = (s7_radius - 1.0).pow(2)

        # Geodesic smoothness: consecutive states should be close on manifold
        if z_hyp.shape[1] > 1:
            hyp_smoothness = (z_hyp[:, 1:] - z_hyp[:, :-1]).pow(2).sum(dim=-1).mean()
            s7_smoothness = (s7_phase[:, 1:] - s7_phase[:, :-1]).pow(2).sum(dim=-1).mean()
        else:
            hyp_smoothness = torch.tensor(0.0, device=z_hyp.device)
            s7_smoothness = torch.tensor(0.0, device=s7_phase.device)

        total = (
            hyp_penalty.mean() * 0.5
            + s7_penalty.mean() * 0.5
            + hyp_smoothness * 0.1
            + s7_smoothness * 0.1
        )

        return total * self.config.manifold_curvature_weight


__all__ = [
    "GeometricLossComputer",
    "free_bits_kl",
    "symlog_squared_loss",
]
