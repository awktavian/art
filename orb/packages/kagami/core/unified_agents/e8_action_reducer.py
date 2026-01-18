"""E₈ Action Reducer - Combine Colony Outputs via Optimal Quantization.

This module combines outputs from multiple colonies into a single
action using the E₈ lattice for mathematically optimal quantization.

MATHEMATICAL FOUNDATION:
=======================
Viazovska (2016): E₈ is the optimal sphere packing in ℝ⁸.
- 240 roots = discrete action categories (shell quantization)
- Full E8 lattice = optimal nearest-point quantization
- Straight-through estimator for gradient flow

UPDATED (December 13, 2025):
===========================
Now uses canonical E8 lattice quantizer (nearest_e8) from:
  kagami_math.e8_lattice_quantizer

The reducer takes N colony outputs (each 8D), combines them with
learned weights, and quantizes using the full E8 lattice.

References:
- Viazovska (2016): Sphere Packing in Dimension 8 (Fields Medal)
- Conway & Sloane (1999): Sphere Packings, Lattices and Groups

Created: December 2, 2025
Updated: December 13, 2025 - Use canonical E8 lattice quantizer
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import torch

if TYPE_CHECKING:
    from kagami.core.unified_agents.octonion_state import OctonionState
import torch.nn as nn
import torch.nn.functional as F
from kagami_math.dimensions import get_e8_roots
from kagami_math.e8_lattice_quantizer import nearest_e8

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class E8Action:
    """Quantized action in E₈ space."""

    code: torch.Tensor  # [8] E₈ code (continuous)
    index: int  # Index into 240 roots (0-239)
    root: torch.Tensor  # [8] Nearest E₈ root
    distance: float  # Distance to nearest root
    confidence: float  # 1 - normalized distance
    colony_weights: list[float]  # Contribution from each colony
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    @property
    def is_crystalline(self) -> bool:
        """True if very close to E₈ root (low distortion)."""
        return self.distance < 0.1


# =============================================================================
# E₈ ACTION REDUCER
# =============================================================================


class E8ActionReducer(nn.Module):
    """Combine N colony outputs to single E₈-quantized action.

    Architecture:
    1. Receive colony outputs (each 8D, on S⁷)
    2. Weight by confidence/relevance
    3. Combine via attention or simple weighted sum
    4. Quantize to nearest E₈ root (240 options)
    5. Return with straight-through gradient

    The reduction is Viazovska-optimal: E₈ provides minimal
    distortion for 8D sphere quantization.
    """

    def __init__(
        self,
        num_colonies: int = 7,
        hidden_dim: int = 32,
        use_attention: bool = True,
        device: str = "cpu",
    ):
        """Initialize E₈ action reducer.

        Args:
            num_colonies: Number of colonies (default 7)
            hidden_dim: Hidden dimension for attention
            use_attention: Use attention for weighting (vs learned fixed)
            device: Torch device
        """
        super().__init__()

        self.num_colonies = num_colonies
        self.hidden_dim = hidden_dim
        self.use_attention = use_attention

        # Register E₈ roots as buffer
        self.register_buffer("e8_roots", get_e8_roots(device))

        # Enhanced Cross-Colony Communication (Forge Colony Mission Optimization)
        if use_attention:
            # Attention-based weighting
            self.query = nn.Linear(8, hidden_dim)
            self.key = nn.Linear(8, hidden_dim)
            self.value = nn.Linear(8, 8)

            # FORGE OPTIMIZATION: Cross-colony communication matrix
            # Learns dependencies between colonies (e.g., Forge → Crystal for validation)
            self.colony_communication_matrix = nn.Parameter(
                torch.eye(num_colonies) + 0.1 * torch.randn(num_colonies, num_colonies)
            )

            # FORGE OPTIMIZATION: Multi-head attention for richer communication
            self.num_heads = min(4, hidden_dim // 8)
            if self.num_heads > 1:
                self.multi_head_attn = nn.MultiheadAttention(
                    embed_dim=8,
                    num_heads=self.num_heads,
                    batch_first=True,
                    dropout=0.1,
                )

            # FORGE OPTIMIZATION: Colony role specialization weights
            # Biases attention based on colony specialized roles
            self.role_specialization = nn.Parameter(torch.ones(num_colonies))
        else:
            # Learned fixed weights
            self.colony_weights = nn.Parameter(torch.ones(num_colonies) / num_colonies)

        # Post-combination projection (optional refinement)
        self.refine = nn.Sequential(
            nn.Linear(8, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 8),
        )

        # Residual gate
        self.gate = nn.Parameter(torch.tensor(0.1))

        logger.info(
            f"✅ E8ActionReducer: {num_colonies} colonies → 240 E₈ roots, attention={use_attention}"
        )

    def forward(
        self,
        colony_outputs: torch.Tensor,
        colony_confidences: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Reduce colony outputs to E₈ action.

        Args:
            colony_outputs: [B, N, 8] colony outputs (N colonies, 8D each)
            colony_confidences: [B, N] optional confidence weights

        Returns:
            Tuple of:
            - e8_code: [B, 8] quantized E₈ code
            - e8_index: [B] index into 240 roots
            - weights: [B, N] colony contribution weights
        """
        B, _N, D = colony_outputs.shape
        assert D == 8, f"Expected 8D outputs, got {D}"

        # Normalize inputs to S⁷
        colony_outputs = F.normalize(colony_outputs, dim=-1)

        # Compute weights
        if self.use_attention:
            weights = self._attention_weights(colony_outputs)
        else:
            weights = F.softmax(self.colony_weights, dim=0)
            weights = weights.unsqueeze(0).expand(B, -1)

        # Apply confidence modulation
        if colony_confidences is not None:
            weights = weights * colony_confidences
            weights = weights / weights.sum(dim=-1, keepdim=True).clamp(min=1e-8)

        # Apply value transformation if using attention
        if self.use_attention:
            values = self.value(colony_outputs)  # [B, N, 8]
        else:
            values = colony_outputs

        # Weighted combination: [B, 8]
        combined = torch.einsum("bn,bnd->bd", weights, values)

        # Optional refinement with residual
        refined = combined + torch.sigmoid(self.gate) * self.refine(combined)

        # Normalize to S⁷
        refined = F.normalize(refined, dim=-1)

        # Quantize to E₈
        e8_code, e8_index = self._quantize_e8(refined)

        return e8_code, e8_index, weights

    def _attention_weights(self, outputs: torch.Tensor) -> torch.Tensor:
        """Compute enhanced attention-based colony weights with cross-colony communication.

        FORGE OPTIMIZATION: Enhanced attention mechanism that models colony
        interdependencies and role specialization for optimal routing.

        Args:
            outputs: [B, N, 8] colony outputs

        Returns:
            [B, N] attention weights
        """
        _B, _N, _D = outputs.shape

        # Base attention mechanism
        query = self.query(outputs.mean(dim=1))  # [B, H]
        keys = self.key(outputs)  # [B, N, H]

        # Base attention scores
        scores = torch.einsum("bh,bnh->bn", query, keys)
        scores = scores / (self.hidden_dim**0.5)

        # FORGE OPTIMIZATION: Apply cross-colony communication matrix
        # This models dependencies between colonies (e.g., Forge needs Crystal for validation)
        if hasattr(self, "colony_communication_matrix"):
            comm_matrix = F.softmax(self.colony_communication_matrix, dim=-1)
            # Apply communication: each colony's attention is influenced by others
            scores = torch.einsum("bn,nm->bm", scores, comm_matrix)

        # FORGE OPTIMIZATION: Apply role specialization bias
        # This biases attention based on colony specialized capabilities
        if hasattr(self, "role_specialization"):
            # Normalize specialization weights
            role_weights = F.softmax(self.role_specialization, dim=0)
            # Apply bias (broadcast to batch dimension)
            scores = scores + role_weights.unsqueeze(0)

        # FORGE OPTIMIZATION: Multi-head attention for richer representation
        # Allows different attention "perspectives" to capture complex dependencies
        if hasattr(self, "multi_head_attn") and hasattr(self, "num_heads") and self.num_heads > 1:
            try:
                # Apply multi-head self-attention to outputs
                _attended_outputs, attn_weights = self.multi_head_attn(outputs, outputs, outputs)
                # Combine multi-head attention with base scores
                multi_head_scores = attn_weights.mean(dim=1)  # Average across heads [B, N]
                scores = 0.7 * scores + 0.3 * multi_head_scores
            except Exception:
                # Fallback to base scores if multi-head fails
                pass

        return F.softmax(scores, dim=-1)

    def _quantize_e8(
        self,
        x: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Quantize to nearest E₈ lattice point using canonical algorithm.

        UPDATED (Dec 13, 2025): Uses canonical nearest_e8() from e8_lattice_quantizer.
        This implements the true E8 lattice: E8 = D8 ∪ (D8 + 1/2)

        The 240 root indices are computed for backwards compatibility with
        discrete action spaces, but the quantized vectors use full lattice precision.

        Args:
            x: [B, 8] input vectors

        Returns:
            Tuple of:
            - quantized: [B, 8] quantized vectors (true E8 lattice points)
            - indices: [B] indices into 240 roots (nearest root for categorization)
        """
        # Use canonical E8 lattice quantizer (true nearest-point algorithm)
        hard_quantized = nearest_e8(x)

        # Compute root indices for discrete action categorization
        # This finds the nearest of the 240 roots (norm √2 shell)
        sq_distances = ((x.unsqueeze(1) - self.e8_roots.unsqueeze(0)) ** 2).sum(dim=-1)  # type: ignore[operator]
        indices = sq_distances.argmin(dim=-1)  # [B]

        if self.training:
            # Straight-through estimator: use hard quantized in forward,
            # but allow gradients to flow through x in backward
            quantized = x + (hard_quantized - x).detach()
        else:
            quantized = hard_quantized

        return quantized, indices

    def to_octonion_state(
        self,
        e8_code: torch.Tensor,
        weights: torch.Tensor,
    ) -> OctonionState:
        """Convert E8 reduction output to OctonionState.

        COHERENCY (Dec 27, 2025): Unified state representation for downstream.

        Args:
            e8_code: [B, 8] or [8] quantized E8 code
            weights: [B, N] or [N] colony contribution weights

        Returns:
            OctonionState with full context
        """
        from kagami.core.unified_agents.octonion_state import OctonionState

        # Handle batch vs single
        if e8_code.dim() == 1:
            e8_code = e8_code.unsqueeze(0)
        if weights.dim() == 1:
            weights = weights.unsqueeze(0)

        # Compute confidence from weight entropy
        # High entropy (spread weights) = low confidence
        # Low entropy (concentrated weights) = high confidence
        entropy = -(weights * (weights + 1e-8).log()).sum(dim=-1)
        max_entropy = torch.log(torch.tensor(weights.size(-1), dtype=weights.dtype))
        confidence = 1.0 - (entropy / max_entropy)

        # Return OctonionState for first batch element
        return OctonionState(
            e8_code=e8_code[0],
            confidence=float(confidence[0].item()),
            metadata={"weights": weights[0].tolist(), "source": "e8_reducer"},
        )

    def reduce(
        self,
        colony_outputs: list[torch.Tensor],
        colony_confidences: list[float] | None = None,
    ) -> E8Action:
        """High-level reduce interface.

        Args:
            colony_outputs: List of [8] tensors from each colony
            colony_confidences: Optional list[Any] of confidence values

        Returns:
            E8Action with quantized result
        """
        # Stack outputs - use same device as e8_roots buffer
        device = self.e8_roots.device
        stacked = torch.stack([o.to(device) for o in colony_outputs], dim=0).unsqueeze(  # type: ignore[arg-type]
            0
        )  # [1, N, 8]

        # Stack confidences on same device
        if colony_confidences is not None:
            conf_tensor = torch.tensor(colony_confidences, device=device).unsqueeze(  # type: ignore[arg-type]
                0
            )  # [1, N]  # type: ignore[arg-type]
        else:
            conf_tensor = None

        # Forward
        with torch.no_grad():
            e8_code, e8_index, weights = self.forward(stacked, conf_tensor)

        # Get nearest root and distance
        root = self.e8_roots[e8_index[0]]  # type: ignore[index]
        distance = (e8_code[0] - root).norm().item()

        return E8Action(
            code=e8_code[0],
            index=e8_index[0].item(),  # type: ignore[arg-type]
            root=root,
            distance=distance,
            confidence=max(0, 1 - distance / 2),  # Normalize by max E₈ distance
            colony_weights=weights[0].tolist(),
        )

    def get_root_semantics(self, index: int) -> dict[str, Any]:
        """Return minimal metadata for a root index.

        The v2 protocol no longer couples a fixed semantic category map to root ordering.
        """
        return {"index": int(index)}


# =============================================================================
# FACTORY
# =============================================================================


def create_e8_reducer(
    num_colonies: int = 7,
    hidden_dim: int = 32,
    use_attention: bool = True,
    device: str = "cpu",
) -> E8ActionReducer:
    """Create an E₈ action reducer.

    Args:
        num_colonies: Number of input colonies
        hidden_dim: Hidden dimension for attention
        use_attention: Use attention weighting
        device: Torch device

    Returns:
        Configured E8ActionReducer
    """
    reducer = E8ActionReducer(
        num_colonies=num_colonies,
        hidden_dim=hidden_dim,
        use_attention=use_attention,
        device=device,
    )
    return reducer.to(device)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "E8Action",
    "E8ActionReducer",
    "create_e8_reducer",
    "get_e8_roots",
]
