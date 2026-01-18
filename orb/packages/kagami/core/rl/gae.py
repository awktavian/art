from __future__ import annotations

"""Generalized Advantage Estimation (GAE).

Implementation of GAE from Schulman et al. 2016.
https://arxiv.org/abs/1506.02438

GAE provides a family of policy gradient estimators with tunable
bias-variance tradeoff via λ parameter.

Key Benefits:
- 20-40% lower variance than simple advantage
- Better credit assignment across time
- Compatible with PPO and other policy gradient methods

Formula:
  GAE(λ) = Σ(γλ)^t δ_t
  where δ_t = r_t + γV(s_{t+1}) - V(s_t)  # TD error
"""
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def compute_gae(
    rewards: list[float],
    values: list[float],
    gamma: float = 0.99,
    lambda_: float = 0.95,
) -> tuple[list[float], list[float]]:
    """Compute GAE advantages and returns.

    Args:
        rewards: Rewards at each timestep
        values: Value estimates V(s_t) at each timestep
        gamma: Discount factor (0.99 typical)
        lambda_: GAE parameter (0.95 typical)
            - λ=0: Pure TD (low variance, high bias)
            - λ=1: Pure Monte Carlo (high variance, low bias)
            - λ=0.95: Sweet spot (empirically validated)

    Returns:
        (advantages, returns)
        advantages: GAE advantages A^GAE_t
        returns: Targets for value function (A_t + V_t)
    """
    # Ensure we have values for t and t+1
    if len(values) < len(rewards) + 1:
        # Extend with last value (bootstrap final state)
        values = [*list(values), values[-1] if values else 0.0]

    advantages: list[float] = []
    gae = 0.0

    # Compute GAE backwards from terminal state
    for t in reversed(range(len(rewards))):
        # TD error: δ_t = r_t + γV(s_{t+1}) - V(s_t)
        delta = rewards[t] + gamma * values[t + 1] - values[t]

        # GAE recursion: A^GAE_t = δ_t + γλ * A^GAE_{t+1}
        gae = delta + gamma * lambda_ * gae

        # Insert at beginning (we're going backwards)
        advantages.insert(0, gae)

    # Returns for value function training: R_t = A_t + V_t
    returns = [adv + val for adv, val in zip(advantages, values[:-1], strict=False)]

    return advantages, returns


def compute_gae_with_dones(
    rewards: list[float],
    values: list[float],
    dones: list[bool],
    gamma: float = 0.99,
    lambda_: float = 0.95,
) -> tuple[list[float], list[float]]:
    """Compute GAE with episode termination handling.

    When episode terminates (done=True), bootstrap value is 0.

    Args:
        rewards: Rewards at each timestep
        values: Value estimates at each timestep
        dones: Episode termination flags
        gamma: Discount factor
        lambda_: GAE parameter

    Returns:
        (advantages, returns)
    """
    # Ensure we have values for t+1
    if len(values) < len(rewards) + 1:
        values = [*list(values), values[-1] if values else 0.0]

    advantages: list[float] = []
    gae = 0.0

    for t in reversed(range(len(rewards))):
        # If episode ends (done=True), bootstrap value is 0 (no future rewards)
        # Otherwise use value estimate of next state
        next_value = 0.0 if dones[t] else values[t + 1]

        # TD error
        delta = rewards[t] + gamma * next_value - values[t]

        # GAE with reset on episode boundary
        gae = delta + gamma * lambda_ * gae * (1 - int(dones[t]))

        advantages.insert(0, gae)

    # Returns
    returns = [adv + val for adv, val in zip(advantages, values[:-1], strict=False)]

    return advantages, returns


def normalize_advantages(advantages: list[float], epsilon: float = 1e-8) -> list[float]:
    """Normalize advantages to have mean=0, std=1.

    This is standard practice in PPO and improves stability.

    Args:
        advantages: Raw advantages
        epsilon: Small constant for numerical stability

    Returns:
        Normalized advantages
    """
    advantages_array = np.array(advantages, dtype=np.float32)

    mean = np.mean(advantages_array)
    std = np.std(advantages_array)

    # Normalize
    normalized = (advantages_array - mean) / (std + epsilon)

    return normalized.tolist()  # type: ignore  # External lib


class GAECalculator:
    """Stateful GAE calculator with running statistics.

    Tracks value function quality for debugging.
    """

    def __init__(self, gamma: float = 0.99, lambda_: float = 0.95) -> None:
        """Initialize GAE calculator.

        Args:
            gamma: Discount factor
            lambda_: GAE parameter (0.95 typical)
        """
        self.gamma = gamma
        self.lambda_ = lambda_

        # Statistics
        self._td_errors: list[float] = []
        self._advantages: list[float] = []

    def compute(
        self,
        rewards: list[float],
        values: list[float],
        dones: list[bool] | None = None,
    ) -> tuple[list[float], list[float]]:
        """Compute GAE advantages and returns.

        Args:
            rewards: Rewards
            values: Value estimates
            dones: Optional episode termination flags

        Returns:
            (advantages, returns)
        """
        if dones is not None and len(dones) > 0:
            advantages, returns = compute_gae_with_dones(
                rewards, values, dones, self.gamma, self.lambda_
            )
        else:
            advantages, returns = compute_gae(rewards, values, self.gamma, self.lambda_)

        # Track statistics
        self._advantages.extend(advantages)
        if len(self._advantages) > 1000:
            self._advantages = self._advantages[-1000:]  # Keep recent

        # Compute TD errors for stats
        for i in range(len(rewards)):
            next_value = values[i + 1] if i + 1 < len(values) else 0.0
            td_error = rewards[i] + self.gamma * next_value - values[i]
            self._td_errors.append(td_error)

        if len(self._td_errors) > 1000:
            self._td_errors = self._td_errors[-1000:]

        return advantages, returns

    def get_stats(self) -> dict[str, Any]:
        """Get GAE statistics for monitoring.

        Returns:
            Statistics dict[str, Any]
        """
        if not self._advantages or not self._td_errors:
            return {
                "mean_advantage": 0.0,
                "std_advantage": 0.0,
                "mean_td_error": 0.0,
                "std_td_error": 0.0,
            }

        return {
            "mean_advantage": float(np.mean(self._advantages)),
            "std_advantage": float(np.std(self._advantages)),
            "mean_td_error": float(np.mean(self._td_errors)),
            "std_td_error": float(np.std(self._td_errors)),
            "gamma": self.gamma,
            "lambda": self.lambda_,
        }


# Global singleton
_gae_calculator: GAECalculator | None = None


def get_gae_calculator() -> GAECalculator:
    """Get or create global GAE calculator."""
    global _gae_calculator
    if _gae_calculator is None:
        _gae_calculator = GAECalculator()
        logger.info("✅ GAE calculator initialized (λ=0.95, γ=0.99)")
    return _gae_calculator
