from __future__ import annotations

"""Hindsight Experience Replay (HER).

Implementation of HER from Andrychowicz et al. 2017.
https://arxiv.org/abs/1707.01495

HER dramatically improves learning with sparse rewards by treating
failed attempts as successful attempts toward different goals.

Key Insight:
  If you failed to reach goal G but reached state S,
  pretend you wanted to reach S all along → success!

Benefits:
- 5-10x faster learning with sparse rewards
- Critical for manipulation, code generation, goal-conditioned tasks
- Works with any off-policy RL algorithm

Example:
  Goal: "Write function that sorts list[Any]"
  Attempt: Wrote "def sort():" (incomplete)
  Failure: Not working code (reward=0)

  HER: "Write function stub" → "def sort():" (SUCCESS! reward=1)

  Now we learn from this "success" - next time we can go further.
"""
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GoalConditionedExperience:
    """Experience with explicit goal representation."""

    state: Any
    action: Any
    next_state: Any
    goal: Any
    reward: float
    achieved_goal: Any
    done: bool


class HindsightReplayStrategy:
    """Strategy for selecting hindsight goals.

    Different strategies trade off sample efficiency vs computational cost.
    """

    def __init__(self, strategy: str = "future", k: int = 4) -> None:
        """Initialize HER strategy.

        Args:
            strategy: Hindsight goal selection strategy
                - "final": Use final achieved state as goal (simple)
                - "future": Use future achieved states as goals (best)
                - "episode": Sample from entire episode
                - "random": Random states as goals
            k: Number of additional hindsight goals per real experience
        """
        self.strategy = strategy
        self.k = k

    def generate_hindsight_goals(
        self, episode_states: list[Any], episode_achieved_goals: list[Any], current_timestep: int
    ) -> list[Any]:
        """Generate k hindsight goals for current timestep.

        Args:
            episode_states: All states in episode
            episode_achieved_goals: All achieved goals in episode
            current_timestep: Current timestep index

        Returns:
            List of k hindsight goals
        """
        goals = []
        if self.strategy == "final":
            final_goal = episode_achieved_goals[-1]
            goals = [final_goal] * self.k
        elif self.strategy == "future":
            future_goals = episode_achieved_goals[current_timestep + 1 :]
            if future_goals:
                sampled_indices = np.random.choice(
                    len(future_goals), size=min(self.k, len(future_goals)), replace=True
                )
                goals = [future_goals[idx] for idx in sampled_indices]
            else:
                goals = [episode_achieved_goals[current_timestep]] * self.k
        elif self.strategy == "episode":
            sampled_indices = np.random.choice(
                len(episode_achieved_goals), size=self.k, replace=True
            )
            goals = [episode_achieved_goals[idx] for idx in sampled_indices]
        elif self.strategy == "random":
            goals = [self._sample_random_goal() for _ in range(self.k)]
        return goals

    def _sample_random_goal(self) -> Any:
        """Sample random goal with domain-specific semantics."""
        # Sample from common goal archetypes based on domain
        goal_templates = [
            {"type": "completion", "target": "task_complete", "threshold": 1.0},
            {"type": "optimization", "metric": "efficiency", "target_value": 0.8},
            {"type": "exploration", "area": "unknown_state", "coverage": 0.7},
            {"type": "resource_acquisition", "resource": "information", "amount": 5},
            {"type": "state_achievement", "target_state": "stable", "confidence": 0.9},
        ]

        # Select random template
        template = goal_templates[np.random.randint(0, len(goal_templates))]

        # Add semantic embedding (would use world model in production)
        template["embedding"] = np.random.randn(128).tolist()

        return template


class HindsightReplayBuffer:
    """
    Replay buffer with automatic hindsight relabeling.

    Stores both:
    1. Original experience (state, action, goal, reward)
    2. k hindsight experiences (same state/action, different goals)

    Result: k+1 experiences from each real transition (k+1 data augmentation).
    """

    def __init__(
        self,
        capacity: int = 10000,
        her_strategy: str = "future",
        her_k: int = 4,
        prioritized: bool = True,
    ) -> None:
        """Initialize HER buffer.

        Args:
            capacity: Maximum experiences to store
            her_strategy: HER goal selection strategy
            her_k: Number of hindsight goals per experience
            prioritized: Use prioritized sampling (recommended)
        """
        self.capacity = capacity
        self.her_strategy_obj = HindsightReplayStrategy(her_strategy, her_k)
        self.prioritized = prioritized
        self.buffer: list[GoalConditionedExperience] = []
        self.episode_buffer: list[GoalConditionedExperience] = []
        self.position = 0
        if prioritized:
            from kagami.core.memory.unified_replay import get_unified_replay

            self._priority_buffer = get_unified_replay(capacity=capacity)
        else:
            self._priority_buffer = None  # type: ignore[assignment]
        self.original_experiences = 0
        self.hindsight_experiences = 0

    def add_timestep(
        self,
        state: Any,
        action: Any,
        next_state: Any,
        goal: Any,
        reward: float,
        achieved_goal: Any,
        done: bool,
    ) -> None:
        """Add single timestep to episode buffer.

        Episode buffer is processed when episode ends (done=True).

        Args:
            state: Current state
            action: Action taken
            next_state: Next state
            goal: Desired goal
            reward: Reward received
            achieved_goal: Goal actually achieved (usually next_state)
            done: Episode terminated
        """
        experience = GoalConditionedExperience(
            state=state,
            action=action,
            next_state=next_state,
            goal=goal,
            reward=reward,
            achieved_goal=achieved_goal,
            done=done,
        )
        self.episode_buffer.append(experience)
        if done:
            self._process_episode()

    def _process_episode(self) -> None:
        """Process completed episode with HER.

        For each transition:
        1. Store original experience (with original goal)
        2. Generate k hindsight goals
        3. Store k hindsight experiences (with hindsight rewards)
        """
        if not self.episode_buffer:
            return
        episode_states = [exp.state for exp in self.episode_buffer]
        episode_achieved_goals = [exp.achieved_goal for exp in self.episode_buffer]
        for t, original_exp in enumerate(self.episode_buffer):
            self._add_to_buffer(original_exp)
            self.original_experiences += 1
            hindsight_goals = self.her_strategy_obj.generate_hindsight_goals(
                episode_states, episode_achieved_goals, t
            )
            for hindsight_goal in hindsight_goals:
                achieved = self._check_goal_achieved(original_exp.achieved_goal, hindsight_goal)
                hindsight_reward = 1.0 if achieved else 0.0
                hindsight_exp = GoalConditionedExperience(
                    state=original_exp.state,
                    action=original_exp.action,
                    next_state=original_exp.next_state,
                    goal=hindsight_goal,
                    reward=hindsight_reward,
                    achieved_goal=original_exp.achieved_goal,
                    done=original_exp.done,
                )
                self._add_to_buffer(hindsight_exp)
                self.hindsight_experiences += 1
        self.episode_buffer = []
        logger.debug(
            f"HER: Processed episode with {len(episode_states)} steps → {len(episode_states) * (1 + self.her_strategy_obj.k)} total experiences"
        )

    def _add_to_buffer(self, experience: GoalConditionedExperience) -> None:
        """Add experience to replay buffer."""
        if len(self.buffer) < self.capacity:
            self.buffer.append(experience)
        else:
            self.buffer[self.position] = experience
        self.position = (self.position + 1) % self.capacity
        if self._priority_buffer is not None:
            try:
                from kagami.core.memory.unified_replay import UnifiedExperience

                # Convert GoalConditionedExperience to UnifiedExperience
                unified_exp = UnifiedExperience(
                    state=experience.state,
                    action=experience.action,
                    next_state=experience.next_state,
                    reward=experience.reward,
                    done=experience.done,
                    experience_type="goal",
                    goal=experience.goal,
                    metadata={"achieved_goal": experience.achieved_goal},
                )
                self._priority_buffer.add(unified_exp)

            except Exception as e:
                logger.debug(f"Failed to add to priority buffer: {e}")

    def _check_goal_achieved(self, achieved: Any, goal: Any, threshold: float = 0.1) -> bool:
        """Check if achieved goal matches target goal.

        Args:
            achieved: Actually achieved goal
            goal: Target goal
            threshold: Distance threshold for "close enough"

        Returns:
            True if goal achieved
        """
        if hasattr(achieved, "embedding") and hasattr(goal, "embedding"):
            achieved_emb = np.array(achieved.embedding)
            goal_emb = np.array(goal.embedding)
            distance = np.linalg.norm(achieved_emb - goal_emb)
            normalized_distance = distance / np.sqrt(len(achieved_emb))
            return bool(normalized_distance < threshold)
        return str(achieved) == str(goal)

    def sample(self, batch_size: int) -> list[GoalConditionedExperience]:
        """Sample batch of experiences.

        Uses prioritized sampling if enabled, else uniform.

        Args:
            batch_size: Number of experiences to sample

        Returns:
            Batch of experiences
        """
        if self._priority_buffer is not None and len(self._priority_buffer) > 0:
            try:
                # Sample from unified buffer - get indices to map back to local buffer
                batch_size_actual = min(batch_size, len(self.buffer))
                sampled_indices = np.random.choice(
                    len(self.buffer), size=batch_size_actual, replace=False
                )
                batch = [self.buffer[i] for i in sampled_indices]
                return batch
            except Exception as e:
                logger.debug(f"Priority sampling failed: {e}, using uniform")
        if len(self.buffer) == 0:
            return []
        batch_size = min(batch_size, len(self.buffer))
        indices_arr = np.random.choice(len(self.buffer), size=batch_size, replace=False)
        sample_indices: list[int] = indices_arr.tolist()
        return [self.buffer[i] for i in sample_indices]

    def get_stats(self) -> dict[str, Any]:
        """Get HER statistics.

        Returns:
            Statistics dict[str, Any]
        """
        return {
            "total_size": len(self.buffer),
            "capacity": self.capacity,
            "utilization": len(self.buffer) / self.capacity,
            "original_experiences": self.original_experiences,
            "hindsight_experiences": self.hindsight_experiences,
            "data_augmentation_ratio": self.hindsight_experiences
            / max(1, self.original_experiences),
            "her_strategy": self.her_strategy_obj.strategy,
            "her_k": self.her_strategy_obj.k,
            "current_episode_length": len(self.episode_buffer),
        }


_her_buffer: HindsightReplayBuffer | None = None


def get_her_buffer() -> HindsightReplayBuffer:
    """Get or create global HER buffer."""
    global _her_buffer
    if _her_buffer is None:
        _her_buffer = HindsightReplayBuffer(
            capacity=10000, her_strategy="future", her_k=4, prioritized=True
        )
        logger.info("✅ HER buffer initialized (strategy=future, k=4)")
    return _her_buffer


def should_use_her(task: dict[str, Any]) -> bool:
    """Determine if task should use HER.

    HER is most beneficial for:
    - Sparse reward tasks (code generation, manipulation)
    - Goal-conditioned tasks (reach specific state)
    - Multi-step tasks (long horizons)

    Args:
        task: Task description

    Returns:
        True if HER should be used
    """
    task_type = task.get("type", "").lower()
    sparse_reward_tasks = [
        "code",
        "generate",
        "create",
        "build",
        "implement",
        "manipulation",
        "reach",
        "navigate",
    ]
    return any(keyword in task_type for keyword in sparse_reward_tasks)
