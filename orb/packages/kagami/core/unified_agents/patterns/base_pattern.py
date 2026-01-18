"""Base Pattern — Shared Foundation for Stigmergy and Learning Patterns.

Provides the core pattern class used by:
- StigmergyLearner (kagami/core/unified_agents/memory/stigmergy.py)
- WeaviatePatternStore (kagami_integrations/elysia/weaviate_pattern_store.py)

Consolidates duplicate implementations with Bayesian statistics for:
- Success/failure tracking
- Confidence estimation (Beta distribution)
- Thompson Sampling for exploration
- ACO probability calculation
- Pheromone-style temporal decay

Scientific basis:
- Bayesian inference: Beta-Binomial conjugate prior
- Thompson Sampling: Russo et al. (2018)
- ACO: Dorigo & Di Caro (1999)
- Stigmergy: Theraulaz & Bonabeau (1999)

Created: December 7, 2025
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

# === CONSTANTS ===
# Pheromone evaporation rate (per hour, 0.98 = 2% decay/hour)
DEFAULT_DECAY_RATE = 0.98
# Half-life for recency weighting (7 days in seconds)
DEFAULT_RECENCY_HALF_LIFE = 86400.0 * 7
# UCB exploration constant (controls exploration vs exploitation)
DEFAULT_UCB_C = 1.0
# Beta prior (α=1, β=1 is uniform prior)
BETA_PRIOR_ALPHA = 1.0
BETA_PRIOR_BETA = 1.0

# === ACO HEURISTIC PARAMETERS (Dorigo & Di Caro, 1999) ===
# α: Pheromone weight in probability calculation
DEFAULT_PHEROMONE_WEIGHT = 1.0
# β: Heuristic weight in probability calculation
DEFAULT_HEURISTIC_WEIGHT = 2.0


@dataclass
class BasePattern:
    """Base pattern with Bayesian statistics for stigmergy learning.

    Tracks success/failure rates with proper uncertainty quantification
    using Beta distribution posteriors.

    Properties:
    - bayesian_success_rate: Posterior mean (smoothed estimate)
    - bayesian_confidence: 1 - normalized std (higher = more certain)
    - success_rate: MLE estimate (legacy, for backwards compatibility)

    Methods:
    - sample_thompson(): Draw from Beta posterior for exploration
    - ucb_score(): Upper Confidence Bound for exploration bonus
    - aco_probability(): ACO-style τ^α × η^β probability
    - apply_decay(): Pheromone-style temporal decay

    Usage:
        pattern = BasePattern(action="query.grove", domain="elysia")
        pattern.success_count += 1

        # Bayesian estimate
        prob = pattern.bayesian_success_rate

        # Thompson Sampling
        sample = pattern.sample_thompson()

        # ACO probability
        aco_prob = pattern.aco_probability()
    """

    action: str
    domain: str
    success_count: int = 0
    failure_count: int = 0
    avg_duration: float = 0.0
    last_updated: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    heuristic_value: float = 1.0
    common_params: dict[str, Any] = field(default_factory=dict[str, Any])
    error_types: list[str] = field(default_factory=list[Any])
    # Qualitative stigmergy: configuration that triggers this pattern
    trigger_config: str | None = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate (Maximum Likelihood Estimate).

        Returns:
            MLE success rate [0, 1]
        """
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total

    @property
    def bayesian_success_rate(self) -> float:
        """Calculate Bayesian posterior mean (Beta distribution).

        Uses Beta(α + successes, β + failures) posterior.
        This is a smoothed estimate that handles sparse data better.

        Returns:
            Posterior mean [0, 1]
        """
        alpha = BETA_PRIOR_ALPHA + self.success_count
        beta = BETA_PRIOR_BETA + self.failure_count
        return alpha / (alpha + beta)

    @property
    def bayesian_confidence(self) -> float:
        """Bayesian confidence based on Beta distribution variance.

        Lower variance = higher confidence.
        Returns 1 - normalized_std where std is from Beta distribution.

        Returns:
            Confidence [0, 1] where 1 = very confident
        """
        alpha = BETA_PRIOR_ALPHA + self.success_count
        beta = BETA_PRIOR_BETA + self.failure_count
        # Beta variance: αβ / ((α+β)²(α+β+1))
        variance = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))
        # Standard deviation normalized (max possible std for Beta is 0.5)
        std = math.sqrt(variance)
        return 1.0 - min(1.0, std / 0.5)

    def sample_thompson(self) -> float:
        """Thompson Sampling: Draw from Beta posterior.

        Returns a sample from Beta(α + successes, β + failures).
        Use this for exploration-exploitation balance in action selection.

        Returns:
            Sample from Beta posterior [0, 1]
        """
        alpha = BETA_PRIOR_ALPHA + self.success_count
        beta = BETA_PRIOR_BETA + self.failure_count
        return float(np.random.beta(alpha, beta))

    def ucb_score(self, total_accesses: int, c: float = DEFAULT_UCB_C) -> float:
        """Upper Confidence Bound score for exploration.

        UCB = μ + c * sqrt(ln(N) / n)

        Where:
        - μ = bayesian_success_rate
        - N = total accesses across all patterns
        - n = this pattern's access count
        - c = exploration constant

        Higher UCB = prefer this action (either high success or under-explored).

        Args:
            total_accesses: Total accesses across all patterns
            c: Exploration constant (default 1.0)

        Returns:
            UCB score [0, ∞)
        """
        if self.access_count == 0:
            return float("inf")  # Always explore unseen actions
        if total_accesses <= 0:
            return self.bayesian_success_rate

        exploration_bonus = c * math.sqrt(math.log(total_accesses) / self.access_count)
        return self.bayesian_success_rate + exploration_bonus

    def aco_probability(
        self,
        alpha: float = DEFAULT_PHEROMONE_WEIGHT,
        beta: float = DEFAULT_HEURISTIC_WEIGHT,
    ) -> float:
        """ACO-style probability combining pheromone (τ) and heuristic (η).

        From Dorigo & Di Caro (1999) "Ant Colony Optimization":
        p_ij ∝ τ_ij^α * η_ij^β

        Where:
        - τ = pheromone = bayesian_success_rate (learned from receipts)
        - η = heuristic = domain-specific prior knowledge
        - α = pheromone weight (higher = trust experience more)
        - β = heuristic weight (higher = trust domain knowledge more)

        Args:
            alpha: Pheromone exponent (default 1.0)
            beta: Heuristic exponent (default 2.0)

        Returns:
            Unnormalized probability score (normalize across candidates)
        """
        tau = max(0.01, self.bayesian_success_rate)  # Pheromone (avoid 0)
        eta = max(0.01, self.heuristic_value)  # Heuristic (avoid 0)
        return float((tau**alpha) * (eta**beta))

    def age_hours(self) -> float:
        """Age since last update in hours.

        Returns:
            Hours since last update
        """
        return (time.time() - self.last_updated) / 3600.0

    def apply_decay(self, decay_rate: float = DEFAULT_DECAY_RATE) -> None:
        """Apply pheromone-style temporal decay to counts.

        Decays success and failure counts based on time since last update.
        This implements the "evaporation" property of stigmergic pheromones.

        Args:
            decay_rate: Decay rate per hour (0.98 = 2% decay/hour)
        """
        age_h = self.age_hours()
        if age_h <= 0:
            return

        # Exponential decay: counts *= decay_rate^age_hours
        decay_factor = decay_rate**age_h

        # Apply decay (keep at least 1 if non-zero to preserve direction)
        if self.success_count > 0:
            self.success_count = max(1, int(self.success_count * decay_factor))
        if self.failure_count > 0:
            self.failure_count = max(1, int(self.failure_count * decay_factor))

        # Update timestamp
        self.last_updated = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dict representation
        """
        return {
            "action": self.action,
            "domain": self.domain,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "avg_duration": self.avg_duration,
            "last_updated": self.last_updated,
            "created_at": self.created_at,
            "access_count": self.access_count,
            "heuristic_value": self.heuristic_value,
            "common_params_json": json.dumps(self.common_params),
            "error_types_json": json.dumps(self.error_types),
            "trigger_config": self.trigger_config,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BasePattern:
        """Create from dictionary.

        Args:
            data: Dict representation

        Returns:
            BasePattern instance
        """
        # Handle common_params
        common_params = data.get("common_params", {})
        if isinstance(common_params, str):
            common_params = json.loads(common_params) if common_params else {}
        elif "common_params_json" in data:
            common_params = json.loads(data["common_params_json"] or "{}")

        # Handle error_types
        error_types = data.get("error_types", [])
        if isinstance(error_types, str):
            error_types = json.loads(error_types) if error_types else []
        elif "error_types_json" in data:
            error_types = json.loads(data["error_types_json"] or "[]")

        return cls(
            action=data.get("action", ""),
            domain=data.get("domain", ""),
            success_count=int(data.get("success_count", 0)),
            failure_count=int(data.get("failure_count", 0)),
            avg_duration=float(data.get("avg_duration", 0.0)),
            last_updated=float(data.get("last_updated", time.time())),
            created_at=float(data.get("created_at", time.time())),
            access_count=int(data.get("access_count", 0)),
            heuristic_value=float(data.get("heuristic_value", 1.0)),
            common_params=common_params,
            error_types=error_types,
            trigger_config=data.get("trigger_config"),
        )


__all__ = [
    "BETA_PRIOR_ALPHA",
    "BETA_PRIOR_BETA",
    # Constants
    "DEFAULT_DECAY_RATE",
    "DEFAULT_HEURISTIC_WEIGHT",
    "DEFAULT_PHEROMONE_WEIGHT",
    "DEFAULT_RECENCY_HALF_LIFE",
    "DEFAULT_UCB_C",
    "BasePattern",
]
