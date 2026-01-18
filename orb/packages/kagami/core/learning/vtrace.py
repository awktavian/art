from __future__ import annotations

"""V-trace Off-Policy Correction.

Implementation of V-trace from Espeholt et al. 2018 (IMPALA).
https://arxiv.org/abs/1802.01561

V-trace enables stable off-policy learning by correcting for
policy mismatch between behavior policy (old) and target policy (new).

Key Benefits:
- Use much older data from replay buffer (2-3x sample efficiency)
- More stable than importance sampling (clips ratios)
- Works with multi-step returns
- Critical for distributed RL

Algorithm:
  1. Compute importance weights: ρ_t = π(a|s) / μ(a|s)
  2. Clip weights: c̄_t = min(c, ρ_t), ρ̄_t = min(ρ, ρ_t)
  3. Compute V-trace target: v_s = V(s) + Σ γ^t ∏ c̄_i δ_t
  4. Train value function toward v_s
  5. Train policy using ρ̄_t weighted advantages

Typical Values:
  ρ̄ (policy clip) = 1.0 (same as on-policy)
  c̄ (value clip) = 1.0 (allows small off-policy corrections)
"""
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def compute_vtrace(
    rewards: list[float],
    values: list[float],
    old_policy_probs: list[float],
    new_policy_probs: list[float],
    gamma: float = 0.99,
    rho_bar: float = 1.0,
    c_bar: float = 1.0,
) -> tuple[list[float], list[float]]:
    """Compute V-trace corrected values and policy advantages.

    Args:
        rewards: Rewards at each timestep
        values: Value estimates V(s_t)
        old_policy_probs: π_old(a|s) - behavior policy probabilities
        new_policy_probs: π_new(a|s) - target policy probabilities
        gamma: Discount factor
        rho_bar: Clipping threshold for policy gradient (1.0 typical)
        c_bar: Clipping threshold for value function (1.0 typical)

    Returns:
        (vtrace_values, vtrace_advantages)
        vtrace_values: Corrected value targets v_s
        vtrace_advantages: Off-policy corrected advantages
    """
    n = len(rewards)

    # Ensure we have values for t+1
    if len(values) < n + 1:
        values = [*list(values), values[-1] if values else 0.0]

    # Compute importance sampling ratios
    ratios = []
    for old_prob, new_prob in zip(old_policy_probs, new_policy_probs, strict=False):
        # Avoid division by zero
        ratio = new_prob / max(old_prob, 1e-10)
        ratios.append(ratio)

    # Clip ratios
    rho_clipped = [min(rho_bar, r) for r in ratios]  # For policy gradient
    c_clipped = [min(c_bar, r) for r in ratios]  # For value function

    # Compute temporal differences
    deltas = []
    for t in range(n):
        delta = rewards[t] + gamma * values[t + 1] - values[t]
        deltas.append(delta)

    # V-trace value targets (computed backwards)
    vtrace_values = [0.0] * n
    v_s = values[n]  # Bootstrap from final value

    for t in reversed(range(n)):
        # V-trace recursion:
        # v_s = V(s) + δ_t ρ̄_t + γ c̄_t (v_{s+1} - V(s+1))
        v_s = values[t] + deltas[t] * rho_clipped[t] + gamma * c_clipped[t] * (v_s - values[t + 1])
        vtrace_values[t] = v_s

    # Policy gradient advantages:
    # A_t = ρ̄_t (r_t + γ v_{s+1} - V(s_t))
    vtrace_advantages = []
    for t in range(n):
        next_value = vtrace_values[t + 1] if t + 1 < n else values[n]
        advantage = rho_clipped[t] * (rewards[t] + gamma * next_value - values[t])
        vtrace_advantages.append(advantage)

    return vtrace_values, vtrace_advantages


class VTraceCalculator:
    """Stateful V-trace calculator with statistics tracking."""

    def __init__(self, gamma: float = 0.99, rho_bar: float = 1.0, c_bar: float = 1.0) -> None:
        """Initialize V-trace calculator.

        Args:
            gamma: Discount factor
            rho_bar: Policy ratio clipping threshold (1.0 = on-policy)
            c_bar: Value ratio clipping threshold (1.0 allows corrections)
        """
        self.gamma = gamma
        self.rho_bar = rho_bar
        self.c_bar = c_bar

        # Statistics
        self._importance_ratios: list[float] = []
        self._clipped_ratios: list[float] = []

    def compute(
        self,
        rewards: list[float],
        values: list[float],
        old_policy_probs: list[float],
        new_policy_probs: list[float],
    ) -> tuple[list[float], list[float]]:
        """Compute V-trace values and advantages.

        Args:
            rewards: Rewards
            values: Value estimates
            old_policy_probs: Behavior policy probabilities
            new_policy_probs: Target policy probabilities

        Returns:
            (vtrace_values, vtrace_advantages)
        """
        # Track importance ratios for statistics
        for old_prob, new_prob in zip(old_policy_probs, new_policy_probs, strict=False):
            ratio = new_prob / max(old_prob, 1e-10)
            self._importance_ratios.append(ratio)

            clipped = min(self.rho_bar, ratio)
            self._clipped_ratios.append(clipped)

        # Trim history
        if len(self._importance_ratios) > 1000:
            self._importance_ratios = self._importance_ratios[-1000:]
            self._clipped_ratios = self._clipped_ratios[-1000:]

        # Compute V-trace
        vtrace_values, vtrace_advantages = compute_vtrace(
            rewards,
            values,
            old_policy_probs,
            new_policy_probs,
            self.gamma,
            self.rho_bar,
            self.c_bar,
        )

        return vtrace_values, vtrace_advantages

    def get_stats(self) -> dict[str, Any]:
        """Get V-trace statistics.

        Returns:
            Statistics dict[str, Any]
        """
        if not self._importance_ratios:
            return {
                "gamma": self.gamma,
                "rho_bar": self.rho_bar,
                "c_bar": self.c_bar,
            }

        # Clip fraction: how often ratios exceed threshold
        clip_fraction = np.mean([1.0 if r > self.rho_bar else 0.0 for r in self._importance_ratios])

        return {
            "gamma": self.gamma,
            "rho_bar": self.rho_bar,
            "c_bar": self.c_bar,
            "avg_importance_ratio": float(np.mean(self._importance_ratios)),
            "max_importance_ratio": float(np.max(self._importance_ratios)),
            "clip_fraction": float(clip_fraction),
            "samples": len(self._importance_ratios),
        }


# Global singleton
_vtrace_calculator: VTraceCalculator | None = None


def get_vtrace_calculator() -> VTraceCalculator:
    """Get or create global V-trace calculator."""
    global _vtrace_calculator
    if _vtrace_calculator is None:
        _vtrace_calculator = VTraceCalculator(gamma=0.99, rho_bar=1.0, c_bar=1.0)
        logger.info("✅ V-trace calculator initialized (ρ̄=1.0, c̄=1.0)")
    return _vtrace_calculator
