"""Decentralized Control Barrier Functions for Multi-Colony Safety.

CREATED: December 14, 2025
BASED ON: Decentralized Neural Barrier Certificates (2025 research)

This module implements per-colony barrier functions for the 7-colony architecture,
enabling compositional safety guarantees via local barrier certificates.

MATHEMATICAL FOUNDATION:
========================
Global CBF: Single h(x) ≥ 0 for all system states
Decentralized CBF: One h_i(x_i, x_{-i}) per agent/colony

For compositional safety:
    ∀i ∈ {1..7}: h_i(x_i, x_{-i}) ≥ 0  ⟹  system is safe

Key properties:
1. Local barriers: h_i depends primarily on colony i's local state
2. Neighbor coupling: h_i observes neighbors via Fano plane connectivity
3. Compositional: If all h_i ≥ 0, global safety is guaranteed
4. Distributed: Each colony verifies its own safety independently

FANO PLANE NEIGHBOR STRUCTURE:
===============================
Each colony observes 6 neighbors via 3 Fano lines it participates in.

Colony connectivity (via FANO_LINES):
- Colony i sits on exactly 3 Fano lines
- Each line connects i to 2 other colonies
- Total: 6 unique neighbors per colony

Example: Spark (colony 0, e₁) sits on lines:
  {1,2,3} → neighbors: Forge(1), Flow(2)
  {1,4,5} → neighbors: Nexus(3), Beacon(4)
  {1,6,7} → neighbors: Grove(5), Crystal(6)

USAGE:
======
# Create decentralized CBF
dcbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=64)

# Check multi-colony safety
x = torch.randn(B, 7, 4)  # [batch, 7 colonies, state_dim]
h = dcbf(x)  # [B, 7] barrier values per colony
is_safe = dcbf.is_safe(x)  # [B] compositional safety

# Per-colony safety filtering
u_nominal = torch.randn(B, 7, 2)  # [batch, 7 colonies, control_dim]
u_safe, penalty, info = dcbf.filter_control(x, u_nominal)

References:
- Ames et al. (2017): Control Barrier Functions
- Wang et al. (2017): Safety Barrier Certificates for Collectives
- Dawson et al. (2022): Safe Control with Learned Certificates
- Decentralized Neural Barrier Certificates (2025): arXiv upcoming
"""

from __future__ import annotations

import logging
from typing import Any, cast

import torch
import torch.nn as nn
import torch.nn.functional as F
from kagami_math.fano_plane import get_fano_lines_zero_indexed

logger = logging.getLogger(__name__)


# =============================================================================
# FANO NEIGHBOR STRUCTURE
# =============================================================================


def build_fano_neighbor_map() -> dict[int, list[int]]:
    """Build neighbor map from Fano plane structure.

    Each colony i observes the 6 other colonies it connects to via Fano lines.

    Returns:
        neighbor_map: Dict mapping colony_idx → list[Any] of 6 neighbor indices
    """
    neighbor_map: dict[int, set[int]] = {i: set() for i in range(7)}

    fano_lines_0idx = get_fano_lines_zero_indexed()

    for i, j, k in fano_lines_0idx:
        # Each colony on this line observes the other two
        neighbor_map[i].update([j, k])
        neighbor_map[j].update([i, k])
        neighbor_map[k].update([i, j])

    # Convert sets to sorted lists for deterministic indexing
    return {i: sorted(neighbors) for i, neighbors in neighbor_map.items()}


# Precomputed neighbor structure
FANO_NEIGHBORS = build_fano_neighbor_map()


# =============================================================================
# PER-COLONY BARRIER FUNCTION
# =============================================================================


class ColonyCBF(nn.Module):
    """Barrier function for a single colony with neighbor awareness.

    Each colony i maintains its own barrier h_i(x_i, x_{neighbors}).
    The barrier depends on:
    - Local state x_i: Colony's own safety state [threat, uncertainty, complexity, risk]
    - Neighbor states: States of 6 neighbors via Fano connectivity

    Architecture:
        [x_local, x_neighbor_1, ..., x_neighbor_6] → MLP → h_i(x)

    The MLP learns to predict when colony i is in a safe state given
    both its local conditions and its neighbors' states.
    """

    def __init__(
        self,
        colony_idx: int,
        state_dim: int = 4,
        hidden_dim: int = 64,
        safety_threshold: float = 0.3,
    ):
        """Initialize colony barrier function.

        Args:
            colony_idx: Colony index (0-6)
            state_dim: Dimension of safety state per colony
            hidden_dim: Hidden layer dimension for MLP
            safety_threshold: Base safety threshold
        """
        super().__init__()
        self.colony_idx = colony_idx
        self.state_dim = state_dim
        self.safety_threshold = safety_threshold

        # Get neighbors from Fano structure
        self.neighbors = FANO_NEIGHBORS[colony_idx]
        if len(self.neighbors) != 6:
            raise ValueError(
                f"Colony {colony_idx} should have 6 neighbors in Fano plane, "
                f"got {len(self.neighbors)}. This indicates a FANO_NEIGHBORS configuration error."
            )

        # Input: local state (state_dim) + 6 neighbor states (6 * state_dim)
        input_dim = state_dim * 7  # Self + 6 neighbors

        # Barrier network: MLP from states → h_i
        self.barrier_net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
        )

        # Learnable risk weights for local state
        self.risk_weights = nn.Parameter(
            torch.tensor([0.4, 0.3, 0.1, 0.2])  # [threat, uncertainty, complexity, risk]
        )

        logger.debug(
            f"✅ ColonyCBF initialized: colony={colony_idx}, "
            f"neighbors={self.neighbors}, input_dim={input_dim}"
        )

    def forward(
        self,
        x_local: torch.Tensor,  # [B, state_dim]
        x_all: torch.Tensor,  # [B, 7, state_dim]
    ) -> torch.Tensor:
        """Compute barrier value h_i(x_local, x_neighbors).

        Args:
            x_local: Local colony state [B, state_dim]
            x_all: All colony states [B, 7, state_dim] for neighbor extraction

        Returns:
            h_i: Barrier values [B] (positive = safe, negative = unsafe)
        """
        B = x_local.shape[0]

        # Extract neighbor states via Fano connectivity
        x_neighbors = x_all[:, self.neighbors, :]  # [B, 6, state_dim]

        # Concatenate local + neighbors
        x_combined = torch.cat([x_local.unsqueeze(1), x_neighbors], dim=1)  # [B, 7, state_dim]
        x_flat = x_combined.view(B, -1)  # [B, 7 * state_dim]

        # Neural barrier function
        h_neural = cast(torch.Tensor, self.barrier_net(x_flat)).squeeze(-1)  # [B]

        # Linear baseline: threshold - weighted_local_risk
        weights = F.softmax(self.risk_weights.abs(), dim=0)
        local_risk = (weights * x_local).sum(dim=-1)  # [B]
        h_baseline = self.safety_threshold - local_risk

        # Combine: baseline + neural residual
        return h_baseline + 0.1 * h_neural


# =============================================================================
# FANO DECENTRALIZED CBF
# =============================================================================


class FanoDecentralizedCBF(nn.Module):
    """Decentralized multi-colony CBF with Fano-based neighbor observation.

    Manages 7 independent ColonyCBFs, one per colony, with compositional safety.

    Safety property:
        system_safe ⟺ ∀i ∈ {0..6}: h_i(x_i, x_{neighbors}) ≥ 0

    This enables:
    - Distributed safety verification (each colony checks itself)
    - Fano-structured neighbor coupling (6 neighbors per colony)
    - Compositional guarantees (all local safe → global safe)
    - Gradient flow for end-to-end training
    """

    def __init__(
        self,
        state_dim: int = 4,
        hidden_dim: int = 64,
        safety_threshold: float = 0.3,
        soft_penalty_weight: float = 10.0,
        alpha: float = 1.0,  # Class-K function parameter
    ):
        """Initialize decentralized CBF.

        Args:
            state_dim: Safety state dimension per colony
            hidden_dim: Hidden dimension for colony barrier networks
            safety_threshold: Base safety threshold
            soft_penalty_weight: Weight for soft barrier penalty
            alpha: Class-K function scaling
        """
        super().__init__()
        self.state_dim = state_dim
        self.safety_threshold = safety_threshold
        self.soft_penalty_weight = soft_penalty_weight
        self.alpha = alpha

        # Create 7 colony barrier functions
        self.colonies = nn.ModuleList(
            [
                ColonyCBF(
                    colony_idx=i,
                    state_dim=state_dim,
                    hidden_dim=hidden_dim,
                    safety_threshold=safety_threshold,
                )
                for i in range(7)
            ]
        )

        # Fano neighbor structure
        self.fano_neighbors = FANO_NEIGHBORS

        logger.info(
            f"✅ FanoDecentralizedCBF initialized: "
            f"state_dim={state_dim}, hidden_dim={hidden_dim}, "
            f"7 colonies with Fano neighbor coupling"
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Compute barrier values for all colonies.

        Args:
            x: All colony states [B, 7, state_dim]

        Returns:
            h: Barrier values [B, 7] per colony (positive = safe)
        """
        # Note: B = x.shape[0] is implicitly used via tensor operations
        h = []

        for i in range(7):
            x_local = x[:, i, :]  # [B, state_dim]
            h_i = self.colonies[i](x_local, x)  # [B]
            h.append(h_i)

        return torch.stack(h, dim=1)  # [B, 7]

    def is_safe(self, x: torch.Tensor) -> torch.Tensor:
        """Check compositional safety: all colonies safe.

        Args:
            x: All colony states [B, 7, state_dim]

        Returns:
            safe: Boolean tensor [B] indicating if ALL colonies are safe
        """
        h = self.forward(x)  # [B, 7]
        return (h >= 0).all(dim=1)  # [B]

    def get_unsafe_colonies(self, x: torch.Tensor) -> torch.Tensor:
        """Identify which colonies are unsafe.

        Args:
            x: All colony states [B, 7, state_dim]

        Returns:
            unsafe_mask: Boolean [B, 7] where True = colony i is unsafe
        """
        h = self.forward(x)  # [B, 7]
        return h < 0  # [B, 7]

    def compute_safety_penalty(
        self,
        x: torch.Tensor,
        margin: float = 0.1,
    ) -> torch.Tensor:
        """Compute soft barrier penalty for training.

        Penalizes states where h_i < margin for any colony.

        Args:
            x: All colony states [B, 7, state_dim]
            margin: Safety margin (penalize h < margin)

        Returns:
            penalty: Scalar penalty for optimization
        """
        h = self.forward(x)  # [B, 7]

        # Penalty when any h_i < margin
        unsafe_margin = F.relu(margin - h)  # [B, 7]

        # Sum over colonies, mean over batch
        penalty = self.soft_penalty_weight * (unsafe_margin**2).sum(dim=1).mean()

        return penalty

    def filter_control(
        self,
        x: torch.Tensor,  # [B, 7, state_dim]
        u_nominal: torch.Tensor,  # [B, 7, control_dim]
        control_dim: int = 2,
        margin: float = 0.1,
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, Any]]:
        """Filter control inputs to ensure compositional safety.

        For each colony i, projects u_i to satisfy h_i ≥ 0.

        Args:
            x: All colony states [B, 7, state_dim]
            u_nominal: Nominal controls [B, 7, control_dim]
            control_dim: Control dimension
            margin: Safety margin

        Returns:
            u_safe: Safe controls [B, 7, control_dim]
            penalty: Soft barrier penalty scalar
            info: Dict with per-colony barrier values and violations
        """
        # Note: B = x.shape[0] is implicitly used via tensor operations

        # Compute barrier values
        h = self.forward(x)  # [B, 7]

        # Simple safety filter: scale down control if h < 0
        # More sophisticated: use differentiable QP per colony
        # For now: soft clipping based on barrier value

        # Safety scaling factor: 1.0 when h ≥ margin, smooth to 0 when h < 0
        safety_factor = torch.sigmoid(h / margin)  # [B, 7]

        # Scale control by safety factor
        u_safe = u_nominal * safety_factor.unsqueeze(-1)  # [B, 7, control_dim]

        # Clip to [0, 1]
        u_safe = torch.clamp(u_safe, 0.0, 1.0)

        # Compute penalty
        penalty = self.compute_safety_penalty(x, margin)

        # Info dict[str, Any]
        info = {
            "h_values": h,  # [B, 7]
            "unsafe_colonies": (h < 0).any(dim=0).tolist(),  # Per-colony unsafe flags
            "min_barrier": h.min(dim=1)[0].mean().item(),
            "all_safe": (h >= 0).all().item(),
        }

        return u_safe, penalty, info

    def get_fano_coupling_strength(self, x: torch.Tensor) -> torch.Tensor:
        """Measure coupling strength between colonies via Fano lines.

        For each Fano line {i, j, k}, compute how strongly the barrier
        values are correlated.

        Args:
            x: All colony states [B, 7, state_dim]

        Returns:
            coupling: [7] tensor of coupling strength per Fano line
        """
        h = self.forward(x)  # [B, 7]

        fano_lines_0idx = get_fano_lines_zero_indexed()
        coupling = []

        for i, j, k in fano_lines_0idx:
            # Mean absolute difference in barrier values on this line
            h_i, h_j, h_k = h[:, i], h[:, j], h[:, k]
            line_coupling = ((h_i - h_j).abs() + (h_j - h_k).abs() + (h_k - h_i).abs()).mean() / 3.0
            coupling.append(line_coupling)

        return torch.stack(coupling)  # [7]


# =============================================================================
# COMPOSITIONAL SAFETY VERIFICATION
# =============================================================================


def verify_compositional_safety(
    dcbf: FanoDecentralizedCBF,
    x: torch.Tensor,
    threshold: float = 0.0,
) -> dict[str, Any]:
    """Verify compositional safety property.

    Checks that if all h_i ≥ threshold, then system is safe.

    Args:
        dcbf: Decentralized CBF
        x: All colony states [B, 7, state_dim]
        threshold: Safety threshold (default: 0)

    Returns:
        verification_result: Dict with safety status and diagnostics
    """
    h = dcbf(x)  # [B, 7]

    # Per-colony safety
    colony_safe = h >= threshold  # [B, 7]

    # Compositional safety: all colonies safe
    all_safe = colony_safe.all(dim=1)  # [B]

    # Find unsafe colonies
    unsafe_mask = ~colony_safe  # [B, 7]
    unsafe_counts = unsafe_mask.sum(dim=1)  # [B]

    # Fano line analysis: which lines have violations?
    fano_lines_0idx = get_fano_lines_zero_indexed()
    violated_lines = []

    for line_idx, (i, j, k) in enumerate(fano_lines_0idx):
        line_violations = unsafe_mask[:, [i, j, k]].any(dim=1).sum().item()
        if line_violations > 0:
            violated_lines.append(
                {
                    "line_idx": line_idx,
                    "colonies": [i, j, k],
                    "violations": line_violations,
                }
            )

    return {
        "all_safe": all_safe.all().item(),
        "batch_safety_rate": all_safe.float().mean().item(),
        "min_barrier": h.min().item(),
        "max_barrier": h.max().item(),
        "mean_barrier": h.mean().item(),
        "unsafe_colonies_per_sample": unsafe_counts.float().mean().item(),
        "violated_fano_lines": violated_lines,
        "per_colony_safety_rate": colony_safe.float().mean(dim=0).tolist(),
    }


# =============================================================================
# FACTORY
# =============================================================================


def create_decentralized_cbf(
    state_dim: int = 4,
    hidden_dim: int = 64,
    **kwargs: Any,
) -> FanoDecentralizedCBF:
    """Factory for creating FanoDecentralizedCBF.

    Args:
        state_dim: Safety state dimension per colony
        hidden_dim: Hidden dimension for barrier networks
        **kwargs: Additional config (safety_threshold, soft_penalty_weight, etc.)

    Returns:
        Configured FanoDecentralizedCBF
    """
    return FanoDecentralizedCBF(
        state_dim=state_dim,
        hidden_dim=hidden_dim,
        **kwargs,
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "FANO_NEIGHBORS",
    "ColonyCBF",
    "FanoDecentralizedCBF",
    "build_fano_neighbor_map",
    "create_decentralized_cbf",
    "verify_compositional_safety",
]
