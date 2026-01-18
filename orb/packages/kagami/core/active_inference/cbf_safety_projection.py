"""CBF Safety Projection - Policy Selection Safety via Barrier Functions.

CREATED: January 4, 2026
PURPOSE: Project EFE G-values through a safety barrier to penalize unsafe policies.

This module provides a simpler CBF interface for EFE policy selection:
- barrier_function(states) -> h_values
- forward(G, states) -> G_safe, aux_loss, info

Unlike the full EFECBFOptimizer (which includes QP solvers for hard constraints),
CBFSafetyProjection focuses on differentiable soft safety filtering with
regularization to prevent trivial solutions.

REGULARIZATION (December 2, 2025):
=================================
The barrier function h(x) can collapse to trivial solutions:
1. h(x) = constant (no variance) - doesn't discriminate states
2. h(x) > 0 always - never blocks anything

We prevent this via:
- Spread loss: encourages h(x) to have variance across states
- Center loss: encourages h(x) mean to be near target (not all positive)

References:
- Ames et al. (2019): Control Barrier Functions
- DecisionNCBF (2024): Neural CBF with spread regularization
"""

from __future__ import annotations

import logging
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class CBFSafetyProjection(nn.Module):
    """Project policy G-values through safety barrier for safe policy selection.

    This is a lightweight CBF module for Active Inference policy selection.
    It computes h(x) for states and penalizes policies with h(x) < 0.

    KEY FEATURES:
    =============
    1. Differentiable soft constraint (training-friendly)
    2. Regularization to prevent trivial solutions
    3. Simple API: barrier_function() + forward()

    USAGE:
    ======
    ```python
    cbf = CBFSafetyProjection(state_dim=270, hidden_dim=64)

    # Compute barrier values
    h_values = cbf.barrier_function(states)  # [batch, state_dim] -> [batch]

    # Project G through safety
    G_safe, aux_loss, info = cbf(G, states)  # Penalize unsafe policies
    ```

    REGULARIZATION:
    ==============
    - spread_loss: Encourages variance in h(x) (prevents constant output)
    - center_loss: Encourages h_mean near target_mean (prevents all-positive)
    """

    def __init__(
        self,
        state_dim: int = 270,
        hidden_dim: int = 64,
        min_spread: float = 0.5,
        target_mean: float = 0.3,
        penalty_weight: float = 10.0,
    ) -> None:
        """Initialize CBF safety projection.

        Args:
            state_dim: Dimension of input state (h + z concatenated)
            hidden_dim: Hidden layer dimension
            min_spread: Minimum desired std of h(x) (spread_loss threshold)
            target_mean: Target mean for h(x) (center_loss target)
            penalty_weight: Weight for CBF penalty in G_safe
        """
        super().__init__()
        self.state_dim = state_dim
        self.min_spread = min_spread
        self.target_mean = target_mean
        self.penalty_weight = penalty_weight

        # Barrier network: state -> h(x)
        # Architecture: linear baseline + neural residual (from optimal_cbf.py)
        self.encoder = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
        )

        # Output layer with initialization for sufficient variance
        self.h_output = nn.Linear(hidden_dim // 2, 1)
        # Initialize with larger gain to ensure h(x) has variance > 0.001
        # At init: h(x) = W @ encoded + b, where encoded has variance ~1
        # We want h(x) std > 0.032 (so var > 0.001)
        nn.init.xavier_uniform_(self.h_output.weight, gain=0.5)
        nn.init.zeros_(self.h_output.bias)

        # Learnable baseline for h(x)
        self.h_baseline = nn.Parameter(torch.tensor(0.3))

        logger.debug(
            f"CBFSafetyProjection: state_dim={state_dim}, "
            f"min_spread={min_spread}, target_mean={target_mean}"
        )

    def barrier_function(self, states: torch.Tensor) -> torch.Tensor:
        """Compute barrier function h(x) for states.

        Args:
            states: [batch, state_dim] or [batch, num_policies, state_dim]

        Returns:
            h_values: [batch] or [batch, num_policies] barrier values
                      h(x) >= 0 means safe, h(x) < 0 means unsafe
        """
        original_shape = states.shape
        has_policy_dim = len(original_shape) == 3

        # Flatten for processing
        if has_policy_dim:
            B, P, D = states.shape
            states_flat = states.reshape(B * P, D)
        else:
            states_flat = states

        # Encode state
        encoded = self.encoder(states_flat)  # [N, hidden//2]

        # Compute h(x)
        h_raw = self.h_output(encoded).squeeze(-1)  # [N]

        # Add baseline (learnable shift)
        h = h_raw + self.h_baseline

        # Reshape back
        if has_policy_dim:
            h = h.reshape(original_shape[0], original_shape[1])

        return h

    def forward(
        self,
        G: torch.Tensor,
        states: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, Any]]:
        """Project G-values through safety barrier.

        Args:
            G: [batch, num_policies] EFE values (lower is better)
            states: [batch, num_policies, state_dim] state trajectories

        Returns:
            G_safe: [batch, num_policies] safety-penalized G values
            aux_loss: Scalar auxiliary loss (spread + center regularization)
            info: Dict with metrics (spread_loss, center_loss, h_mean, etc.)
        """
        _B, _P = G.shape

        # Compute barrier values
        h_values = self.barrier_function(states)  # [B, P]

        # CBF penalty: ReLU(-h) = max(0, -h)
        # Positive when h < 0 (unsafe), zero when h >= 0 (safe)
        violation = F.relu(-h_values)  # [B, P]

        # Penalize unsafe policies
        cbf_penalty = self.penalty_weight * violation
        G_safe = G + cbf_penalty

        # === Regularization ===
        # Flatten for computing stats
        h_flat = h_values.reshape(-1)

        # Spread loss: encourage variance > min_spread^2
        h_std = h_flat.std()
        spread_loss = F.relu(self.min_spread - h_std)

        # Center loss: encourage mean near target
        h_mean = h_flat.mean()
        center_loss = (h_mean - self.target_mean).abs()

        # Combined auxiliary loss
        aux_loss = spread_loss + center_loss

        # Build info dict
        info = {
            "h_values": h_values,
            "h_mean": h_mean,
            "h_std": h_std,
            "spread_loss": spread_loss,
            "center_loss": center_loss,
            "cbf_penalty": cbf_penalty.mean(),
            "num_violations": (h_values < 0).sum(),
        }

        return G_safe, aux_loss, info


__all__ = ["CBFSafetyProjection"]
