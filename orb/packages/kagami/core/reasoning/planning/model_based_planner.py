from __future__ import annotations

"Model-Based Rollout Planning.\n\nUses world model to plan actions before execution (look-ahead).\nSimulates possible outcomes to choose best action sequence.\n\nKey benefits:\n- Better long-term decisions (look ahead 5-10 steps)\n- Avoid costly mistakes (simulate first)\n- Sample-efficient (learn in imagination)\n- Optimal action sequences\n\nAlgorithm:\n    1. Generate candidate action sequences (100-1000 candidates)\n    2. Simulate each sequence with world model\n    3. Score final states (proximity to goal)\n    4. Return best action sequence\n    5. Execute first action, replan\n\nPlanning Methods:\n    - Random Shooting: Sample random action sequences\n    - Cross-Entropy Method (CEM): Iterative refinement\n    - Model Predictive Control (MPC): Receding horizon\n\nReference: Model-Based RL (Sutton & Barto, 2018)\n"
import logging
from collections.abc import Callable
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class ModelBasedPlanner:
    """Plan action sequences using world model rollouts.

    Usage:
        planner = ModelBasedPlanner(world_model, horizon=5)

        # Plan to reach goal
        actions = await planner.plan(current_state, goal_state)

        # Execute first action
        result = await execute(actions[0])

        # Replan with new state
        actions = await planner.plan(new_state, goal_state)
    """

    def __init__(
        self, world_model: Any, horizon: int = 5, n_candidates: int = 100, method: str = "cem"
    ) -> None:
        """Initialize model-based planner.

        Args:
            world_model: World model for simulation
            horizon: Planning horizon (steps to look ahead)
            n_candidates: Number of candidate action sequences
            method: Planning method ('random', 'cem', or 'mpc')
        """
        self._world_model = world_model
        self._horizon = horizon
        self._n_candidates = n_candidates
        self._method = method
        self._cem_iterations = 10
        self._cem_elite_frac = 0.1
        self._plans_generated = 0
        self._avg_plan_quality = 0.0
        logger.info(
            f"Model-based planner initialized: horizon={horizon}, n_candidates={n_candidates}, method={method}"
        )

    async def plan(
        self,
        current_state: dict[str, Any],
        goal_state: dict[str, Any],
        reward_fn: Callable | None = None,
    ) -> list[dict[str, Any]]:
        """Plan action sequence to reach goal.

        Args:
            current_state: Current state dict[str, Any]
            goal_state: Desired goal state dict[str, Any]
            reward_fn: Optional custom reward function

        Returns:
            List of actions to execute
        """
        current_vec = await self._encode_state(current_state)
        goal_vec = await self._encode_state(goal_state)
        if self._method == "random":
            actions = await self._random_shooting(current_vec, goal_vec, reward_fn)
        elif self._method == "cem":
            actions = await self._cross_entropy_method(current_vec, goal_vec, reward_fn)
        elif self._method == "mpc":
            actions = await self._model_predictive_control(current_vec, goal_vec, reward_fn)
        else:
            raise ValueError(f"Unknown planning method: {self._method}")
        self._plans_generated += 1
        return actions

    async def _random_shooting(
        self,
        current_state: np.ndarray[Any, Any],
        goal_state: np.ndarray[Any, Any],
        reward_fn: Callable | None,
    ) -> list[dict[str, Any]]:
        """Random shooting: Sample random action sequences.

        Args:
            current_state: Current state vector
            goal_state: Goal state vector
            reward_fn: Reward function

        Returns:
            Best action sequence
        """
        best_actions = None
        best_score = -np.inf
        for _ in range(self._n_candidates):
            actions = self._sample_action_sequence(self._horizon)
            final_state, total_reward = await self._simulate_rollout(
                current_state, actions, reward_fn
            )
            goal_proximity = -np.linalg.norm(final_state - goal_state)
            score = goal_proximity + total_reward
            if score > best_score:
                best_score = score  # type: ignore[assignment]
                best_actions = actions
        return best_actions or []

    async def _cross_entropy_method(
        self,
        current_state: np.ndarray[Any, Any],
        goal_state: np.ndarray[Any, Any],
        reward_fn: Callable | None,
    ) -> list[dict[str, Any]]:
        """Cross-Entropy Method: Iterative refinement of action distribution.

        More sample-efficient than random shooting.

        Args:
            current_state: Current state vector
            goal_state: Goal state vector
            reward_fn: Reward function

        Returns:
            Best action sequence
        """
        action_dim = self._infer_action_dim()
        action_mean = np.zeros((self._horizon, action_dim))
        action_std = np.ones((self._horizon, action_dim))
        for _iteration in range(self._cem_iterations):
            candidates = []
            scores = []
            for _ in range(self._n_candidates):
                actions_vec = np.random.normal(action_mean, action_std)
                actions = self._decode_actions(actions_vec)
                final_state, total_reward = await self._simulate_rollout(
                    current_state, actions, reward_fn
                )
                score = -np.linalg.norm(final_state - goal_state) + total_reward
                candidates.append(actions_vec)
                scores.append(score)
            scores = np.array(scores)  # type: ignore[assignment]
            n_elites = max(1, int(self._n_candidates * self._cem_elite_frac))
            elite_idx = np.argsort(scores)[-n_elites:]
            elite_actions = np.array([candidates[i] for i in elite_idx])
            action_mean = elite_actions.mean(axis=0)
            action_std = elite_actions.std(axis=0) + 0.01
        best_actions = self._decode_actions(action_mean)
        return best_actions

    async def _model_predictive_control(
        self,
        current_state: np.ndarray[Any, Any],
        goal_state: np.ndarray[Any, Any],
        reward_fn: Callable | None,
    ) -> list[dict[str, Any]]:
        """Model Predictive Control: Receding horizon planning.

        Args:
            current_state: Current state vector
            goal_state: Goal state vector
            reward_fn: Reward function

        Returns:
            Action sequence (only first action executed, then replan)
        """
        actions = await self._cross_entropy_method(current_state, goal_state, reward_fn)
        return actions[:1]

    async def _simulate_rollout(
        self,
        initial_state: np.ndarray[Any, Any],
        actions: list[dict[str, Any]],
        reward_fn: Callable | None,
    ) -> tuple[np.ndarray[Any, Any], float]:
        """Simulate action sequence with world model.

        Args:
            initial_state: Initial state vector
            actions: Action sequence to simulate
            reward_fn: Optional reward function

        Returns:
            (final_state, total_reward) tuple[Any, ...]
        """
        current_state = initial_state
        total_reward = 0.0
        for action in actions:
            next_state = self._world_model.predict(current_state, action)
            if reward_fn:
                reward = reward_fn(current_state, action, next_state)
            else:
                reward = 0.0
            total_reward += reward
            current_state = next_state
        return (current_state, total_reward)

    def _sample_action_sequence(self, length: int) -> list[dict[str, Any]]:
        """Sample random action sequence.

        Args:
            length: Sequence length

        Returns:
            List of action dicts
        """
        return [self._sample_action() for _ in range(length)]

    def _sample_action(self) -> dict[str, Any]:
        """Sample single random action.

        Returns:
            Action dict[str, Any]
        """
        actions = ["search", "generate", "analyze", "optimize"]
        return {"type": np.random.choice(actions)}

    def _infer_action_dim(self) -> int:
        """Infer action space dimension."""
        return 64

    def _decode_actions(self, action_vectors: np.ndarray[Any, Any]) -> list[dict[str, Any]]:
        """Decode action vectors to action dicts.

        Args:
            action_vectors: Action vectors [horizon, action_dim]

        Returns:
            List of action dicts
        """
        actions = []
        for vec in action_vectors:
            action = {"embedding": vec.tolist()}
            actions.append(action)
        return actions

    async def _encode_state(self, state: dict[str, Any]) -> np.ndarray[Any, Any]:
        """Encode state dict[str, Any] to vector.

        Args:
            state: State dict[str, Any]

        Returns:
            State vector
        """
        from kagami.core.services.embedding_service import get_embedding_service

        emb_svc = get_embedding_service()
        text = " ".join((f"{k}:{v}" for k, v in state.items()))
        return np.array(emb_svc.embed_text(text))

    def get_stats(self) -> dict[str, Any]:
        """Get planner statistics.

        Returns:
            Stats dict[str, Any]
        """
        return {
            "plans_generated": self._plans_generated,
            "horizon": self._horizon,
            "n_candidates": self._n_candidates,
            "method": self._method,
            "avg_plan_quality": self._avg_plan_quality,
        }


_planner: ModelBasedPlanner | None = None
