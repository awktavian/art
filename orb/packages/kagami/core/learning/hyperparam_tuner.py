from __future__ import annotations

"""Adaptive Hyperparameter Tuner for RL Systems.

Automatically tunes RL hyperparameters from outcome feedback:
- PPO clip_epsilon, target_kl, ppo_epochs
- GAE lambda parameter
- Imagination horizon, n_candidates
- Exploration rates

Uses simple Bayesian optimization with median-of-k for robustness.
Persists best configs per task family for future use.

Based on research:
- Hyperparameter tuning best practices (Bergstra & Bengio, 2012)
- PPO hyperparameter sensitivity (Andrychowicz et al., 2021)
- Adaptive RL (Jaderberg et al., 2019)
"""
import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class HyperparamConfig:
    """RL hyperparameter configuration."""

    # PPO
    clip_epsilon: float = 0.2
    target_kl: float = 0.01
    ppo_epochs: int = 4
    minibatch_size: int = 8

    # GAE
    gae_lambda: float = 0.95
    gamma: float = 0.99

    # RL Loop
    imagination_horizon: int = 5
    n_candidates: int = 5
    exploration_rate: float = 0.2
    intrinsic_weight: float = 0.1

    # Meta
    task_family: str = "default"
    performance_score: float = 0.0  # Track best performance


@dataclass
class OutcomeFeedback:
    """Outcome feedback for learning."""

    success: bool
    duration_ms: float
    prediction_error_ms: float
    valence: float
    convergence_steps: int
    timestamp: float


class AdaptiveHyperparamTuner:
    """Bayesian-style hyperparameter tuner with outcome feedback.

    Learns optimal hyperparameters per task family by:
    1. Tracking outcomes for each config
    2. Sampling promising regions (exploit)
    3. Exploring new regions (explore)
    4. Updating best config based on median-of-k (robust to outliers)
    """

    def __init__(self, persistence_path: str = "state/rl_hyperparams.json") -> None:
        """Initialize adaptive tuner.

        Args:
            persistence_path: Path to save/load tuned configs
        """
        self.persistence_path = Path(persistence_path)

        # Best configs per task family
        self._best_configs: dict[str, HyperparamConfig] = {}

        # Outcome history: config_hash → [outcomes]
        self._outcome_history: dict[str, list[OutcomeFeedback]] = defaultdict(list[Any])

        # Exploration: configs to try
        self._exploration_queue: list[HyperparamConfig] = []

        # Tuning stats
        self._configs_tried = 0
        self._best_performances: dict[str, float] = {}

        # Load persisted configs
        self._load_configs()

    def get_config(self, task_family: str = "default") -> HyperparamConfig:
        """Get best known config for task family.

        Args:
            task_family: Task category (e.g., "planning", "code", "spatial")

        Returns:
            Best hyperparameter config
        """
        if task_family in self._best_configs:
            return self._best_configs[task_family]

        # Use default config
        config = HyperparamConfig(task_family=task_family)
        self._best_configs[task_family] = config
        return config

    async def record_outcome(
        self,
        config: HyperparamConfig,
        outcome: OutcomeFeedback,
    ) -> None:
        """Record outcome for a config.

        Args:
            config: Config used
            outcome: Outcome observed
        """
        config_hash = self._hash_config(config)

        # Store outcome
        self._outcome_history[config_hash].append(outcome)

        # Trim history (keep last 100 per config)
        if len(self._outcome_history[config_hash]) > 100:
            self._outcome_history[config_hash] = self._outcome_history[config_hash][-100:]

        # Update best config if this performed better
        await self._update_best_config(config, outcome.timestamp)

        logger.debug(
            f"Recorded outcome for {config.task_family}: "
            f"success={outcome.success}, performance={self._compute_performance(config_hash):.3f}"
        )

    async def _update_best_config(self, config: HyperparamConfig, timestamp: float) -> None:
        """Update best config if performance improved.

        Args:
            config: Config to evaluate
            timestamp: When evaluated
        """
        config_hash = self._hash_config(config)
        outcomes = self._outcome_history[config_hash]

        if len(outcomes) < 3:
            return  # Need at least 3 samples for robust estimate

        # Compute performance (median-of-k for robustness)
        performance = self._compute_performance(config_hash)

        # Update if better than current best
        task_family = config.task_family
        current_best = self._best_performances.get(task_family, 0.0)

        if performance > current_best:
            config.performance_score = performance
            self._best_configs[task_family] = config
            self._best_performances[task_family] = performance

            logger.info(
                f"🎯 New best config for {task_family}: "
                f"performance={performance:.3f} (previous={current_best:.3f})"
            )

            # Persist
            await self._save_configs()

    def _compute_performance(self, config_hash: str) -> float:
        """Compute performance score for config.

        Uses median-of-k for robustness to outliers.

        Args:
            config_hash: Config identifier

        Returns:
            Performance score (0.0-1.0)
        """
        outcomes = self._outcome_history[config_hash]

        if not outcomes:
            return 0.0

        # Components (normalize to 0-1)
        success_rate = np.mean([1.0 if o.success else 0.0 for o in outcomes])

        # Speed (lower duration = better)
        durations = [o.duration_ms for o in outcomes]
        median_duration = np.median(durations)
        speed_score = 1.0 / (1.0 + median_duration / 1000.0)  # Normalize

        # Accuracy (lower prediction error = better)
        errors = [o.prediction_error_ms for o in outcomes]
        median_error = np.median(errors)
        accuracy_score = 1.0 / (1.0 + median_error / 100.0)

        # Efficiency (fewer convergence steps = better)
        steps = [o.convergence_steps for o in outcomes]
        median_steps = np.median(steps)
        efficiency_score = 1.0 / (1.0 + median_steps / 5.0)

        # Weighted combination
        performance = (
            0.4 * success_rate + 0.25 * speed_score + 0.2 * accuracy_score + 0.15 * efficiency_score
        )

        return float(performance)

    def suggest_next_config(self, task_family: str = "default") -> HyperparamConfig:
        """Suggest next config to try (exploit + explore).

        Args:
            task_family: Task category

        Returns:
            Config to try next
        """
        # 80% exploit: Use best config with small perturbation
        if np.random.random() < 0.8 and task_family in self._best_configs:
            best = self._best_configs[task_family]
            return self._perturb_config(best, sigma=0.1)

        # 20% explore: Sample from reasonable ranges
        return self._sample_random_config(task_family)

    def _perturb_config(self, config: HyperparamConfig, sigma: float = 0.1) -> HyperparamConfig:
        """Perturb config for local exploration.

        Args:
            config: Base config
            sigma: Perturbation magnitude

        Returns:
            Perturbed config
        """
        return HyperparamConfig(
            clip_epsilon=np.clip(config.clip_epsilon + np.random.normal(0, sigma * 0.2), 0.1, 0.3),
            target_kl=np.clip(config.target_kl + np.random.normal(0, sigma * 0.01), 0.005, 0.05),
            ppo_epochs=int(np.clip(config.ppo_epochs + np.random.randint(-1, 2), 2, 10)),
            minibatch_size=int(
                np.clip(config.minibatch_size * (1 + np.random.normal(0, sigma)), 4, 32)
            ),
            gae_lambda=np.clip(config.gae_lambda + np.random.normal(0, sigma * 0.05), 0.9, 0.99),
            gamma=config.gamma,  # Keep gamma fixed (sensitive)
            imagination_horizon=int(
                np.clip(config.imagination_horizon + np.random.randint(-1, 2), 1, 15)
            ),
            n_candidates=int(np.clip(config.n_candidates + np.random.randint(-1, 2), 3, 10)),
            exploration_rate=np.clip(
                config.exploration_rate + np.random.normal(0, sigma * 0.1), 0.05, 0.5
            ),
            intrinsic_weight=np.clip(
                config.intrinsic_weight + np.random.normal(0, sigma * 0.05), 0.0, 0.3
            ),
            task_family=config.task_family,
        )

    def _sample_random_config(self, task_family: str) -> HyperparamConfig:
        """Sample random config from reasonable ranges.

        Args:
            task_family: Task category

        Returns:
            Random config
        """
        return HyperparamConfig(
            clip_epsilon=np.random.uniform(0.1, 0.3),
            target_kl=np.random.uniform(0.005, 0.05),
            ppo_epochs=np.random.randint(2, 11),
            minibatch_size=int(2 ** np.random.randint(2, 6)),  # 4, 8, 16, 32
            gae_lambda=np.random.uniform(0.9, 0.99),
            gamma=0.99,  # Standard
            imagination_horizon=np.random.randint(1, 16),
            n_candidates=np.random.randint(3, 11),
            exploration_rate=np.random.uniform(0.05, 0.5),
            intrinsic_weight=np.random.uniform(0.0, 0.3),
            task_family=task_family,
        )

    def _hash_config(self, config: HyperparamConfig) -> str:
        """Hash config for indexing.

        Args:
            config: Config to hash

        Returns:
            Config hash
        """
        # Round to 3 decimals for reasonable bucketing
        key_values = (
            round(config.clip_epsilon, 3),
            round(config.target_kl, 4),
            config.ppo_epochs,
            config.minibatch_size,
            round(config.gae_lambda, 3),
            config.imagination_horizon,
            config.n_candidates,
            round(config.exploration_rate, 3),
        )
        return str(hash(key_values))

    def get_stats(self) -> dict[str, Any]:
        """Get tuning statistics.

        Returns:
            Statistics dict[str, Any]
        """
        return {
            "configs_tried": self._configs_tried,
            "task_families": list(self._best_configs.keys()),
            "best_performances": self._best_performances,
            "total_outcomes": sum(len(outcomes) for outcomes in self._outcome_history.values()),
        }

    def _load_configs(self) -> None:
        """Load persisted configs from disk."""
        if not self.persistence_path.exists():
            logger.debug("No persisted hyperparameter configs found")
            return

        try:
            with open(self.persistence_path) as f:
                data = json.load(f)

            for task_family, config_dict in data.items():
                config = HyperparamConfig(**config_dict)
                self._best_configs[task_family] = config
                self._best_performances[task_family] = config.performance_score

            logger.info(f"✅ Loaded {len(self._best_configs)} tuned hyperparameter configs")

        except Exception as e:
            logger.warning(f"Failed to load hyperparameter configs: {e}")

    async def _save_configs(self) -> None:
        """Persist best configs to disk."""
        try:
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                task_family: asdict(config) for task_family, config in self._best_configs.items()
            }

            with open(self.persistence_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"💾 Saved {len(self._best_configs)} hyperparameter configs")

        except Exception as e:
            logger.warning(f"Failed to save hyperparameter configs: {e}")


# Global singleton
_hyperparam_tuner: AdaptiveHyperparamTuner | None = None


def get_hyperparam_tuner() -> AdaptiveHyperparamTuner:
    """Get or create global hyperparameter tuner."""
    global _hyperparam_tuner
    if _hyperparam_tuner is None:
        _hyperparam_tuner = AdaptiveHyperparamTuner()
        logger.info("🎛️ Adaptive hyperparameter tuner initialized")
    return _hyperparam_tuner
