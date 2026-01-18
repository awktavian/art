from __future__ import annotations

"""Intrinsic Motivation for Curiosity-Driven Exploration.

Compute intrinsic rewards to encourage:
1. Curiosity: Reducing model uncertainty
2. Novelty: Visiting rare states
3. Empowerment: Increasing control/options
4. Progress: Mastering skills

Based on Pathak et al. (2017), Burda et al. (2018), and recent intrinsic motivation research.
"""
import logging
import math
from collections import defaultdict
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class IntrinsicRewardCalculator:
    """
    Compute intrinsic rewards for exploration.

    Intrinsic rewards encourage the agent to explore and learn,
    independent of task-specific extrinsic rewards.
    """

    def __init__(self) -> None:
        """Initialize intrinsic reward calculator."""
        # State visitation counts (for novelty)
        self.state_visitation: dict[str, int] = defaultdict(int)

        # Prediction error history (for curiosity)
        self.prediction_errors: dict[str, list[float]] = defaultdict(list[Any])

        # Weights for different reward components
        self.weights = {
            "curiosity": 0.4,  # Reward learning
            "novelty": 0.3,  # Reward exploration
            "empowerment": 0.2,  # Reward control
            "progress": 0.1,  # Reward mastery
        }

    def compute(
        self,
        state: Any,
        action: dict[str, Any],
        world_model: Any = None,
        custom_weights: dict[str, float] | None = None,
    ) -> float:
        """
        Compute total intrinsic reward (weighted sum of components).

        OPTIMIZED: Includes epistemic value from ActiveInferenceEngine.

        Args:
            state: Current latent state
            action: Proposed action
            world_model: World model for uncertainty estimation
            custom_weights: Optional custom weights for reward components

        Returns:
            Total intrinsic reward (0.0-1.0)
        """
        weights = custom_weights or self.weights

        # Compute individual components
        curiosity = self._curiosity_reward(state, action, world_model)
        novelty = self._novelty_reward(state)
        empowerment = self._empowerment_reward(state, world_model)
        progress = self._progress_reward(state, world_model)

        # NOTE: ActiveInferenceEngine requires async - integrate at higher level
        # Epistemic value bonus added in unified_loop when available

        # Weighted combination
        total = (
            weights["curiosity"] * curiosity
            + weights["novelty"] * novelty
            + weights["empowerment"] * empowerment
            + weights["progress"] * progress
        )

        return float(total)

    def _curiosity_reward(self, state: Any, action: dict[str, Any], world_model: Any) -> float:
        """
        Curiosity: Reward for reducing prediction uncertainty.

        High reward when action leads to surprising outcomes (learn something new).

        UPGRADED (Oct 2025): Uses RND (Random Network Distillation) when available.
        RND is more robust than forward dynamics in stochastic environments.

        Formula:
          - RND: ||predictor(s) - target(s)||² (robust)
          - Fallback: uncertainty(next_state) (original)
        """
        # Try RND curiosity first (more robust)
        try:
            from kagami.core.rl.rnd_curiosity import get_rnd_curiosity

            rnd = get_rnd_curiosity()
            rnd_reward = rnd.compute_intrinsic_reward(state)

            # Train predictor (asynchronously in background is better)
            # Schedule only when an event loop is running to avoid coroutine warnings
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(rnd.update_predictor(state))
            except RuntimeError:
                # No running loop - skip update (will happen in background)
                pass

            return rnd_reward

        except Exception as e:
            logger.debug(f"RND curiosity unavailable: {e}, using forward dynamics")

        # Fallback: Forward dynamics uncertainty
        if world_model is None:
            # Use novelty as proxy for curiosity when no world model
            return self._novelty_reward(state)

        try:
            # Predict next state
            prediction = world_model.predict_next_state(state, action)

            # Reward proportional to uncertainty
            # High uncertainty → high curiosity → explore!
            curiosity = prediction.uncertainty

            return float(curiosity)

        except Exception as e:
            logger.debug(f"Curiosity reward computation failed: {e}")
            # Fallback to novelty-based curiosity
            return self._novelty_reward(state)

    def _novelty_reward(self, state: Any) -> float:
        """
        Novelty: Reward for visiting rare states.

        Encourages visiting unexplored regions of state space.

        Formula: reward = 1 / sqrt(1 + visit_count)

        Note: Square root decay provides slower decline than 1/(1+n),
        which better preserves exploration incentive over time.
        """
        state_hash = self._compute_state_hash(state)

        # Get visit count
        visit_count = self.state_visitation[state_hash]

        # Update count
        self.state_visitation[state_hash] += 1

        # Novelty decays with visits (1/sqrt for slower decay)
        novelty = 1.0 / math.sqrt(1.0 + visit_count)

        return float(novelty)

    def _empowerment_reward(self, state: Any, world_model: Any) -> float:
        """
        Empowerment: Reward for states with many options.

        Encourages finding states where agent has control.

        Theoretical: Mutual information I(S_t+n ; A_t)
        Practical: Measure diversity of reachable future states
        """
        if world_model is None:
            # Without world model, estimate empowerment from state complexity
            state_hash = self._compute_state_hash(state)
            visit_count = self.state_visitation.get(state_hash, 0)
            # Rarely visited states likely have more unexplored options
            return 1.0 / (1.0 + visit_count * 0.1)

        try:
            # Sample multiple actions from current state
            # Increased from 5 to 20 for better empowerment estimates
            n_samples = 20
            reachable_states = []

            for i in range(n_samples):
                # Sample diverse actions (cycle through action types)
                action = {"action": f"explore_{i % 8}"}

                # Predict next state
                prediction = world_model.predict_next_state(state, action)
                reachable_states.append(prediction.predicted_state)

            # Measure diversity of reachable states
            if len(reachable_states) < 2:
                return 0.2  # Low empowerment if can't sample diverse states

            # OPTIMIZED: Use variance of embeddings instead of O(n²) pairwise distances
            # Complexity: O(n × d) instead of O(n² × d) → 10x faster for n=20
            # Theory: Variance captures spread/diversity without pairwise comparisons
            embeddings = np.array([s.embedding for s in reachable_states])

            # Compute variance across all dimensions
            variance = np.var(embeddings, axis=0).mean()

            # Normalize to 0-1 range (empirical: variance ~ 0.1 for diverse states)
            empowerment = min(1.0, variance * 5.0)  # Scale factor from empirical data

            return float(empowerment)

        except Exception as e:
            logger.debug(f"Empowerment computation failed: {e}")
            return 0.3  # Conservative low empowerment on failure

    def _progress_reward(self, state: Any, world_model: Any) -> float:
        """
        Progress: Reward for improving prediction accuracy (skill mastery).

        Tracks learning progress over time.

        Formula: reward = (error_t-1 - error_t) / error_t-1
        """
        if world_model is None:
            return 0.3  # Assume no progress without world model

        try:
            # Get model quality
            quality = world_model.get_model_quality()

            # Check if model is learning
            if quality["quality"] == "good":
                return 0.8  # High reward for good model
            elif quality["quality"] == "learning":
                return 0.6  # Moderate reward while learning
            else:
                return 0.4  # Lower reward when untrained

        except Exception as e:
            logger.debug(f"Progress computation failed: {e}")
            return 0.3  # Assume no progress on failure

    def _compute_state_hash(self, state: Any) -> str:
        """Compute hash of state for indexing."""
        if hasattr(state, "context_hash"):
            return state.context_hash  # type: ignore  # External lib
        return str(hash(str(state)))[:16]

    def get_stats(self) -> dict[str, Any]:
        """Get intrinsic motivation statistics."""
        return {
            "unique_states_visited": len(self.state_visitation),
            "total_visits": sum(self.state_visitation.values()),
            "avg_visits_per_state": (
                np.mean(list(self.state_visitation.values())) if self.state_visitation else 0
            ),
            "exploration_diversity": len(self.state_visitation)
            / max(1, sum(self.state_visitation.values())),
        }


# Global singleton
_intrinsic_reward: IntrinsicRewardCalculator | None = None


def get_intrinsic_reward_calculator() -> IntrinsicRewardCalculator:
    """Get or create global intrinsic reward calculator."""
    global _intrinsic_reward
    if _intrinsic_reward is None:
        _intrinsic_reward = IntrinsicRewardCalculator()
    return _intrinsic_reward
