"""RSSM Core Components and Utilities.

Production components for the Colony RSSM architecture.

Contains:
- SparseFanoAttention: Attention mechanism based on Fano plane
- HofstadterStrangeLoop: Strange loop with μ_self in S7 space
- Utility functions for Fano plane connectivity

CLEANED (December 27, 2025):
============================
Removed legacy classes (BatchedOrganismCore, GodelAgent) that were superseded
by OrganismRSSM in rssm_core.py. Use OrganismRSSM for all RSSM functionality.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from kagami_math.fano_plane import get_fano_lines_zero_indexed

from kagami.core.config.unified_config import HofstadterLoopConfig
from kagami.core.config.unified_config import RSSMConfig as ColonyRSSMConfig

from .rssm_state import ColonyState

logger = logging.getLogger(__name__)


class SparseFanoAttention(nn.Module):
    """Sparse attention mechanism based on the Fano plane structure.

    The Fano plane provides a natural sparsity pattern for 7-colony systems:
    - 7 colonies (points)
    - 7 lines connecting colonies
    - Each line contains exactly 3 colonies
    - Each colony is on exactly 3 lines

    This creates a structured sparse attention pattern that respects
    the mathematical structure of the colony system.
    """

    def __init__(self, config: ColonyRSSMConfig):
        super().__init__()
        self.config = config
        self.num_colonies = config.num_colonies
        self.attention_dim = config.attention_dim
        self.num_heads = config.attention_heads
        self.head_dim = config.head_dim

        # Canonical Fano plane structure (7 colonies, 7 lines, 3 colonies per line)
        # Derived from the G₂ associative 3-form φ (see `kagami_math.fano_plane`).
        self.fano_lines = [list(t) for t in get_fano_lines_zero_indexed()]

        # Linear layers for Q, K, V
        self.query = nn.Linear(config.colony_dim, self.attention_dim, bias=False)
        self.key = nn.Linear(config.colony_dim, self.attention_dim, bias=False)
        self.value = nn.Linear(config.colony_dim, self.attention_dim, bias=False)

        # Output projection
        self.out_proj = nn.Linear(self.attention_dim, config.colony_dim)

        # Dropout
        self.dropout = nn.Dropout(config.attention_dropout)

        # Create sparse attention mask
        self.register_buffer("fano_mask", self._create_fano_mask())

        # PRE-COMPUTED INDEX TENSORS FOR BATCHED SPARSE ATTENTION
        # Eliminates Python for-loops in forward pass (28 ops -> 3 tensor ops)
        self._precompute_fano_indices()

        logger.debug(
            f"SparseFanoAttention initialized: {self.num_heads} heads, dim={self.attention_dim}"
        )

    def _precompute_fano_indices(self) -> None:
        """Pre-compute index tensors for batched Fano plane sparse attention.

        Creates buffers for:
        - line_indices: [7, 3] - colony indices for each of the 7 Fano lines
        - scatter_indices: [21] - flattened colony indices for scatter_add_
        - line_counts: [7] - number of lines each colony participates in (always 3)

        This enables fully vectorized gather/scatter operations instead of Python loops.
        """
        # Fano plane: 7 lines, each with 3 colonies
        # Lines are derived from get_fano_lines_zero_indexed() (G₂ associative 3-form)
        # line_indices[l, p] = colony index of point p on line l
        line_indices = torch.tensor(self.fano_lines, dtype=torch.long)  # [7, 3]
        self.register_buffer("line_indices", line_indices)

        # scatter_indices: flattened [21] for scatter_add_ accumulation
        # Each entry maps (line, point_in_line) -> colony_index
        scatter_indices = line_indices.view(-1)  # [21]
        self.register_buffer("scatter_indices", scatter_indices)

        # Precompute how many lines each colony participates in (for averaging)
        # In Fano plane, each colony is on exactly 3 lines
        line_counts = torch.zeros(self.num_colonies, dtype=torch.float32)
        for line in self.fano_lines:
            for col_idx in line:
                line_counts[col_idx] += 1.0
        self.register_buffer("line_counts", line_counts)  # [7]

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

    def forward(
        self, colony_states: torch.Tensor, mask: torch.Tensor | None = None
    ) -> torch.Tensor:
        """Forward pass through sparse Fano attention.

        OPTIMIZED (Jan 4, 2026): Batched sparse attention with pre-computed indices.
        Replaces Python for-loops with vectorized gather/scatter operations.

        Previous: 7 Python loops + 21 nested accumulations = 28 Python ops per forward
        Current: 3 batched tensor ops (gather, matmul, scatter_add_)

        Mathematical semantics preserved:
        - Each colony attends only to colonies on shared Fano lines
        - 3×3 attention computed within each of 7 lines
        - Results averaged across the 3 lines each colony participates in

        Args:
            colony_states: (batch, num_colonies, colony_dim)
            mask: Optional additional mask (unused in sparse mode)

        Returns:
            Updated colony states: (batch, num_colonies, colony_dim)
        """
        batch_size, num_colonies, _colony_dim = colony_states.shape

        # Compute Q, K, V
        Q = self.query(colony_states)  # (batch, num_colonies, attention_dim)
        K = self.key(colony_states)
        V = self.value(colony_states)

        # Reshape for multi-head attention
        Q = Q.view(batch_size, num_colonies, self.num_heads, self.head_dim).transpose(1, 2)
        K = K.view(batch_size, num_colonies, self.num_heads, self.head_dim).transpose(1, 2)
        V = V.view(batch_size, num_colonies, self.num_heads, self.head_dim).transpose(1, 2)
        # Now: (batch, num_heads, num_colonies, head_dim)

        # BATCHED SPARSE ATTENTION (Jan 4, 2026)
        # All 7 Fano lines processed in parallel using pre-computed index tensors.
        #
        # line_indices: [7, 3] - colony indices for each line
        # scatter_indices: [21] - flattened for accumulation
        # line_counts: [7] - lines per colony (always 3 for Fano plane)

        num_lines = self.line_indices.shape[0]  # 7
        points_per_line = self.line_indices.shape[1]  # 3

        # STEP 1: Gather Q, K, V for all lines in one operation
        # Expand line_indices for batched gather: [7, 3] -> [B, H, 7, 3, D]
        gather_idx = self.line_indices.view(1, 1, num_lines, points_per_line, 1)
        gather_idx = gather_idx.expand(batch_size, self.num_heads, -1, -1, self.head_dim)

        # Gather from Q, K, V: [B, H, 7, D] -> [B, H, 7, 3, D]
        Q_expanded = Q.unsqueeze(2).expand(-1, -1, num_lines, -1, -1)  # [B, H, 7, 7, D]
        K_expanded = K.unsqueeze(2).expand(-1, -1, num_lines, -1, -1)
        V_expanded = V.unsqueeze(2).expand(-1, -1, num_lines, -1, -1)

        Q_lines = torch.gather(Q_expanded, 3, gather_idx)  # [B, H, 7, 3, D]
        K_lines = torch.gather(K_expanded, 3, gather_idx)  # [B, H, 7, 3, D]
        V_lines = torch.gather(V_expanded, 3, gather_idx)  # [B, H, 7, 3, D]

        # STEP 2: Compute 3×3 attention for all 7 lines in parallel
        # scores[b, h, l, i, j] = Q_lines[b,h,l,i] · K_lines[b,h,l,j] / sqrt(d)
        scores = torch.matmul(Q_lines, K_lines.transpose(-2, -1)) / math.sqrt(self.head_dim)
        # [B, H, 7, 3, 3]

        # Softmax within each line
        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)

        # Compute attended values for all lines
        attended_lines = torch.matmul(attn, V_lines)  # [B, H, 7, 3, D]

        # STEP 3: Scatter-add results back to colonies
        # Flatten lines dimension: [B, H, 7, 3, D] -> [B, H, 21, D]
        attended_flat = attended_lines.view(batch_size, self.num_heads, -1, self.head_dim)

        # Prepare scatter indices: [21] -> [B, H, 21, D]
        scatter_idx = self.scatter_indices.view(1, 1, -1, 1)
        scatter_idx = scatter_idx.expand(batch_size, self.num_heads, -1, self.head_dim)

        # Accumulate into output using scatter_add_
        attended = torch.zeros_like(V)  # [B, H, 7, D]
        attended.scatter_add_(2, scatter_idx, attended_flat)

        # Average across lines (each colony is on exactly 3 lines)
        # line_counts: [7] -> [1, 1, 7, 1]
        counts = self.line_counts.view(1, 1, -1, 1)
        attended = attended / counts.clamp(min=1.0)

        # Reshape and project
        attended = attended.transpose(1, 2).reshape(batch_size, num_colonies, self.attention_dim)

        output = self.out_proj(attended)
        return output


def _safe_spectral_norm(module: nn.Module) -> nn.Module:
    """Apply spectral normalization safely to a module.

    Args:
        module: Neural network module

    Returns:
        Module with spectral normalization applied
    """
    try:
        if isinstance(module, nn.Linear | nn.Conv1d | nn.Conv2d | nn.Conv3d):
            return nn.utils.spectral_norm(module)
        else:
            logger.debug(f"Spectral norm not applied to {type(module).__name__}")
            return module
    except Exception as e:
        logger.warning(f"Failed to apply spectral norm to {type(module).__name__}: {e}")
        return module


class HofstadterStrangeLoop(nn.Module):
    """Hofstadter-style strange loop with μ_self in S7 space.

    μ_self lives in S7 (7D) - mathematically meaningful:
    - S7 = unit imaginary octonions = 7 colonies = Fano plane structure
    - Aligns with S7AugmentedHierarchy which extracts S7 at all hierarchy levels
    - The strange loop closure is: s7_{t+1} ≈ s7_t

    Interface:
    - A learnable vector μ_self in S7 (7D)
    - A current-self encoder μ_current = f(internal_z, action)
    - A coherence metric (cosine similarity)
    - An EMA update toward a fixed point with warmup momentum

    Mathematical Foundation:
    - G2 = Aut(𝕆) acts on Im(𝕆) ≅ S7
    - Each colony corresponds to one imaginary octonion axis
    - μ_self represents the system's self-representation in octonion phase space
    """

    def __init__(self, config: HofstadterLoopConfig):
        super().__init__()
        self.config = config

        self.internal_dim = int(getattr(config, "internal_dim", 14))  # G2 dimension
        self.action_dim = int(getattr(config, "action_dim", 8))  # E8 lattice
        self.self_dim = int(getattr(config, "self_dim", 7))  # S7

        # Track steps for warmup momentum schedule.
        self.register_buffer("_step", torch.zeros((), dtype=torch.long))

        # μ_self initialization: scale so E||μ_self|| ≈ init_scale.
        init_scale = float(getattr(config, "init_scale", 0.1))
        denom = math.sqrt(max(1, self.self_dim))
        mu_init = torch.randn(self.self_dim) * (init_scale / denom)
        self.mu_self = nn.Parameter(mu_init)

        # Current-self encoder: (internal_z, action) -> μ_current.
        in_dim = self.internal_dim + (self.action_dim if self.action_dim > 0 else 0)
        hidden = max(32, min(256, 4 * self.self_dim))
        self.self_encoder = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, self.self_dim),
        )

        # Optional action predictor
        self.action_predictor: nn.Module | None = None
        if self.action_dim > 0:
            self.action_predictor = nn.Sequential(
                nn.Linear(self.internal_dim + self.self_dim, hidden),
                nn.GELU(),
                nn.Linear(hidden, self.action_dim),
            )

    def _momentum(self) -> float:
        warmup_steps = int(getattr(self.config, "warmup_steps", 0))
        warmup_m = float(getattr(self.config, "warmup_momentum", 0.7))
        steady_m = float(getattr(self.config, "self_momentum", 0.99))
        step = int(self._step.item())  # type: ignore[operator]
        return warmup_m if step < warmup_steps else steady_m

    def forward(
        self, internal_z: torch.Tensor, action: torch.Tensor | None = None
    ) -> dict[str, Any]:
        if internal_z.dim() != 2 or internal_z.shape[-1] != self.internal_dim:
            raise ValueError(
                f"internal_z must be [B, {self.internal_dim}], got {tuple(internal_z.shape)}"
            )

        B = internal_z.shape[0]
        device = internal_z.device
        dtype = internal_z.dtype

        if self.action_dim > 0:
            if action is None:
                action = torch.zeros(B, self.action_dim, device=device, dtype=dtype)
            elif action.dim() != 2 or action.shape[-1] != self.action_dim:
                raise ValueError(
                    f"action must be [B, {self.action_dim}], got {tuple(action.shape)}"
                )
            enc_in = torch.cat([internal_z, action], dim=-1)
        else:
            enc_in = internal_z

        mu_current = self.self_encoder(enc_in)  # [B, self_dim]
        mu_ref = self.mu_self.unsqueeze(0).expand_as(mu_current)

        coh_t = F.cosine_similarity(mu_current, mu_ref, dim=-1).clamp(-1.0, 1.0)
        coherence = float(coh_t.mean().item())

        # EMA update toward a fixed point (train-mode only).
        if self.training:
            m = self._momentum()
            with torch.no_grad():
                target = mu_current.mean(dim=0)
                self.mu_self.mul_(m).add_((1.0 - m) * target)
                self._step.add_(1)  # type: ignore[operator]

        action_pred = None
        if self.action_predictor is not None:
            action_pred = self.action_predictor(
                torch.cat([internal_z, self.mu_self.unsqueeze(0).expand(B, -1)], dim=-1)
            )

        return {
            "coherence": coherence,
            "mu_self": self.mu_self,
            "encoded_self": mu_current,
            "action_pred": action_pred,
        }


def create_hofstadter_strange_loop(
    config: HofstadterLoopConfig | None = None,
) -> HofstadterStrangeLoop:
    """Create HofstadterStrangeLoop with sensible defaults.

    Args:
        config: Optional configuration. If None, uses default HofstadterLoopConfig
                with S7-aligned dimensions (internal_dim=14, self_dim=7, action_dim=8).

    Returns:
        HofstadterStrangeLoop instance
    """
    if config is None:
        from kagami.core.config.unified_config import HofstadterLoopConfig

        config = HofstadterLoopConfig()

    return HofstadterStrangeLoop(config)


def get_fano_plane_connectivity() -> list[list[int]]:
    """Get the Fano plane connectivity structure.

    Returns:
        List of lines, where each line is a list[Any] of 3 colony indices.
    """
    return [list(t) for t in get_fano_lines_zero_indexed()]


def validate_colony_connectivity(colony_states: list[ColonyState]) -> bool:
    """Validate that colony states follow Fano plane connectivity."""
    if len(colony_states) != 7:
        return False

    # Check that all colonies have valid IDs
    colony_ids = {state.colony_id for state in colony_states}
    expected_ids = set(range(7))

    return colony_ids == expected_ids
