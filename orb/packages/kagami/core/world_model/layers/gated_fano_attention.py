"""Gated Fano Sparse Attention.

Implementation of the NeurIPS 2025 best paper gating mechanism applied to
KagamiOS's Fano plane structured sparse attention.

**Mathematical Foundation:**

The gated attention mechanism introduces learned input-dependent gates:
    Y' = Y ⊙ σ(XWθ)

Where:
- Y: SDPA output (attention result)
- X: Input tokens
- Wθ: Learnable linear projection per attention head
- σ: Sigmoid activation (creates sparse gating via saturation)
- ⊙: Element-wise multiplication (Hadamard product)

**Integration with Fano Plane:**

KagamiOS uses the Fano plane for structured sparse attention:
- 7 colonies (points) corresponding to imaginary octonions e₁-e₇
- 7 lines, each containing exactly 3 colonies
- Each colony attends to 6 others via 3 Fano lines
- Enforces mathematical structure: G₂ = Aut(𝕆) acts on Im(𝕆) ≅ S⁷

The gating mechanism is applied AFTER Fano-structured attention to:
1. Preserve the algebraic connectivity (Fano topology is fixed)
2. Add input-dependent dynamic sparsity on top of structural sparsity
3. Enable the network to "reject" uninformative attention outputs

**Benefits:**
- Improved training stability (non-linear attention mapping)
- Ultra-long context support (1M+ tokens demonstrated)
- 80% gating sparsity → better accuracy than dense attention
- Maintains Fano plane's mathematical coherence

**Reference:**
NeurIPS 2025 Best Paper: "Gated Attention for Long-Context Transformers"

**Author:** Forge (e₂) — The Builder
**Date:** December 14, 2025
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Literal, cast

import torch
import torch.nn as nn
import torch.nn.functional as F
from kagami_math.fano_plane import get_fano_lines_zero_indexed

# MIGRATION (Dec 15, 2025): Use unified_config for RSSMConfig
# rssm_config.py removed Dec 21, 2025 - all config now in unified_config
from kagami.core.config.unified_config import RSSMConfig as ColonyRSSMConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class GatedFanoAttention(nn.Module):
    """Gated sparse attention mechanism based on the Fano plane structure.

    Extends the standard Fano sparse attention with learned input-dependent
    gating as described in the NeurIPS 2025 best paper.

    **Architecture:**
    1. Standard multi-head attention with Fano plane sparsity mask
    2. Per-head sigmoid gates: g = σ(XWθ) where X is input
    3. Gated output: Y' = Y ⊙ g

    **Fano Plane Sparsity:**
    - 7 colonies (points)
    - 7 lines connecting colonies
    - Each line contains exactly 3 colonies
    - Each colony is on exactly 3 lines
    - Self-attention always enabled

    **Gating Modes:**
    - "enabled": Apply gates to all attention outputs (default)
    - "disabled": Disable gating (reduces to standard Fano sparse attention)

    Args:
        config: ColonyRSSMConfig with attention parameters
        gating_mode: How to apply gates ("enabled", "disabled")
        gate_bias: Whether to use bias in gate projection (default: False)
    """

    def __init__(
        self,
        config: ColonyRSSMConfig,
        gating_mode: Literal["enabled", "disabled"] = "enabled",
        gate_bias: bool = False,
    ):
        super().__init__()
        self.config = config
        self.num_colonies = config.num_colonies
        self.attention_dim = config.attention_dim
        self.num_heads = config.attention_heads
        self.head_dim = config.head_dim
        self.gating_mode = gating_mode

        if self.num_colonies != 7:
            raise ValueError(f"Fano plane requires exactly 7 colonies, got {self.num_colonies}")

        # Canonical Fano plane structure (7 colonies, 7 lines, 3 colonies per line)
        # Derived from the G₂ associative 3-form φ (see `kagami_math.fano_plane`).
        self.fano_lines = [list(t) for t in get_fano_lines_zero_indexed()]

        # Linear layers for Q, K, V
        self.query = nn.Linear(config.colony_dim, self.attention_dim, bias=False)
        self.key = nn.Linear(config.colony_dim, self.attention_dim, bias=False)
        self.value = nn.Linear(config.colony_dim, self.attention_dim, bias=False)

        # Gate projections (per-head gating)
        # Input: colony_dim → Output: head_dim per head
        # Single batched Linear computes all heads at once (avoids Python for-loop)
        if self.gating_mode != "disabled":
            self.gate_proj = nn.Linear(
                config.colony_dim, self.num_heads * self.head_dim, bias=gate_bias
            )

        # Output projection
        self.out_proj = nn.Linear(self.attention_dim, config.colony_dim)

        # Dropout
        self.dropout = nn.Dropout(config.attention_dropout)

        # Create sparse attention mask
        fano_mask: torch.Tensor = self._create_fano_mask()
        self.register_buffer("fano_mask", fano_mask)

        logger.debug(
            f"GatedFanoAttention initialized: {self.num_heads} heads, "
            f"dim={self.attention_dim}, gating_mode={self.gating_mode}"
        )

    def _create_fano_mask(self) -> torch.Tensor:
        """Create sparse attention mask based on Fano plane structure."""
        mask = torch.zeros(self.num_colonies, self.num_colonies)

        # Allow self-attention
        for i in range(self.num_colonies):
            mask[i, i] = 1.0

        # Allow attention along Fano lines
        for line in self.fano_lines:
            for i in line:
                for j in line:
                    mask[i, j] = 1.0

        return mask

    def _compute_gates(
        self,
        colony_states: torch.Tensor,
        batch_size: int,
        num_colonies: int,
    ) -> torch.Tensor:
        """Compute input-dependent sigmoid gates per head.

        Args:
            colony_states: (batch, num_colonies, colony_dim)
            batch_size: Batch dimension
            num_colonies: Number of colonies (should be 7)

        Returns:
            gates: (batch, num_heads, num_colonies, head_dim)
        """
        # Single batched projection for all heads at once
        # (batch, num_colonies, colony_dim) -> (batch, num_colonies, num_heads * head_dim)
        gate_logits = self.gate_proj(colony_states)

        # Reshape to separate heads: (batch, num_colonies, num_heads, head_dim)
        gate_logits = gate_logits.view(batch_size, num_colonies, self.num_heads, self.head_dim)

        # Transpose to match expected output: (batch, num_heads, num_colonies, head_dim)
        gate_logits = gate_logits.transpose(1, 2)

        # Apply sigmoid to get gates in [0, 1]
        gates = torch.sigmoid(gate_logits)

        return gates

    def forward(
        self,
        colony_states: torch.Tensor,
        mask: torch.Tensor | None = None,
        return_gate_stats: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, dict[str, float]]:
        """Forward pass through gated sparse Fano attention.

        Args:
            colony_states: (batch, num_colonies, colony_dim)
            mask: Optional additional mask
            return_gate_stats: If True, return (output, gate_stats)

        Returns:
            Updated colony states: (batch, num_colonies, colony_dim)
            Or tuple[Any, ...] of (states, gate_stats) if return_gate_stats=True
        """
        batch_size, num_colonies, _colony_dim = colony_states.shape

        if num_colonies != self.num_colonies:
            raise ValueError(f"Expected {self.num_colonies} colonies, got {num_colonies}")

        # Compute Q, K, V
        Q = self.query(colony_states)  # (batch, num_colonies, attention_dim)
        K = self.key(colony_states)
        V = self.value(colony_states)

        # Reshape for multi-head attention
        Q = Q.view(batch_size, num_colonies, self.num_heads, self.head_dim).transpose(1, 2)
        K = K.view(batch_size, num_colonies, self.num_heads, self.head_dim).transpose(1, 2)
        V = V.view(batch_size, num_colonies, self.num_heads, self.head_dim).transpose(1, 2)
        # Now: (batch, num_heads, num_colonies, head_dim)

        # Compute attention scores
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.head_dim)
        # (batch, num_heads, num_colonies, num_colonies)

        # Apply Fano plane sparsity mask
        fano_mask: torch.Tensor = (
            cast(torch.Tensor, self.fano_mask).unsqueeze(0).unsqueeze(0)
        )  # (1, 1, num_colonies, num_colonies)
        scores = scores.masked_fill(fano_mask == 0, float("-inf"))

        # Apply additional mask if provided
        if mask is not None:
            scores = scores.masked_fill(mask == 0, float("-inf"))

        # Softmax
        attention_weights = F.softmax(scores, dim=-1)
        attention_weights = self.dropout(attention_weights)

        # Apply attention to values
        attended = torch.matmul(attention_weights, V)
        # (batch, num_heads, num_colonies, head_dim)

        # Apply gating if enabled
        gate_stats = {}
        if self.gating_mode != "disabled":
            gates = self._compute_gates(colony_states, batch_size, num_colonies)
            # gates: (batch, num_heads, num_colonies, head_dim)

            # Apply gates to all attention outputs
            # attended: (batch, num_heads, num_colonies, head_dim)
            # gates: (batch, num_heads, num_colonies, head_dim)
            attended = attended * gates

            # Compute gate statistics for diagnostics
            if return_gate_stats:
                with torch.no_grad():
                    gate_mean = gates.mean().item()
                    gate_std = gates.std().item()
                    # Sparsity: fraction of gates < 0.1
                    sparsity = (gates < 0.1).float().mean().item()

                    gate_stats = {
                        "gate_mean": gate_mean,
                        "gate_std": gate_std,
                        "gate_sparsity": sparsity,
                        "gate_min": gates.min().item(),
                        "gate_max": gates.max().item(),
                    }

        # Reshape and project
        attended = (
            attended.transpose(1, 2).contiguous().view(batch_size, num_colonies, self.attention_dim)
        )

        output = self.out_proj(attended)

        if return_gate_stats:
            return output, gate_stats
        return output

    def get_gate_weights(self) -> list[torch.Tensor] | None:
        """Get the gate projection weights for analysis.

        Returns:
            List of gate weight matrices (one per head), or None if gating disabled.
            Each tensor has shape (head_dim, colony_dim).
        """
        if self.gating_mode == "disabled":
            return None

        gate_proj = getattr(self, "gate_proj", None)
        if gate_proj is None:
            return None

        # gate_proj.weight shape: (num_heads * head_dim, colony_dim)
        # Split into per-head weights: list of (head_dim, colony_dim) tensors
        weight = gate_proj.weight.detach()
        return list(weight.view(self.num_heads, self.head_dim, -1))

    def set_gating_mode(self, mode: Literal["enabled", "disabled"]) -> None:
        """Change the gating mode at runtime (for ablation studies).

        Args:
            mode: New gating mode

        Raises:
            ValueError: If trying to enable gating when no gate weights exist
        """
        # Check if trying to enable gating when gate_proj doesn't exist
        if mode == "enabled" and not hasattr(self, "gate_proj"):
            raise ValueError(
                "Cannot enable gating on a model initialized with gating_mode='disabled'. "
                "Gate projection weights do not exist."
            )

        self.gating_mode = mode
        logger.info(f"Gating mode changed to: {mode}")


# NOTE: replace_fano_attention_with_gated() was removed in the Dec 2025 cleanup.

__all__ = [
    "GatedFanoAttention",
]
