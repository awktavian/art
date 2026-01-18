"""Unified Experience Replay Buffer — Single Source of Truth.

CREATED: December 6, 2025

This module consolidates 6 previous replay buffer implementations:
- PrioritizedReplayBuffer (kagami/core/memory/prioritized_replay.py)
- ReceiptBuffer (kagami/core/world_model/receipt_buffer.py)
- PrioritizedReplayEnhanced (kagami/core/optimality/enhanced_online_learning.py)
- CombinedExperienceReplay (kagami/core/research/combined_experience_replay.py)
- HindsightReplayBuffer (kagami/core/learning/hindsight_replay.py)
- DistributedReplayBuffer (kagami/core/memory/distributed_replay.py)

DESIGN PRINCIPLES (per DreamerV3):
==================================
1. **Single Buffer**: All experiences flow through one buffer
2. **Replay Ratio Control**: Configurable gradient steps per env step (1-64)
3. **Prioritized Sampling**: TD-error based with β annealing
4. **Multi-Type Support**: RL experiences, TIC triplets, goals all in one
5. **Geometric Indexing**: Optional E8 bucket lookup for efficient retrieval
6. **Importance Sampling**: Proper IS weights to avoid bias

DREAMERV3 REFERENCE:
====================
From Hafner et al. (2023):
- "Higher replay ratios predictably increase the performance of Dreamer"
- Uses uniform replay by default, but supports prioritization
- Replay ratio of 16-64 common for Atari, 2-8 for continuous control

USAGE:
======
```python
from kagami.core.memory.unified_replay import get_unified_replay, UnifiedExperience

buffer = get_unified_replay()

# Add RL experience
buffer.add(UnifiedExperience(
    state=state_tensor,
    action=action_dict,
    next_state=next_state_tensor,
    reward=1.0,
    done=False,
    priority=abs(td_error),
))

# Add TIC triplet
buffer.add(UnifiedExperience(
    experience_type="tic",
    tic_data=tic_dict,
    plan_state=plan_embedding,
    execute_state=exec_embedding,
    verify_state=verify_embedding,
    actual_success=True,
))

# Sample with replay ratio
for _ in range(config.replay_ratio):
    batch, weights, indices = buffer.sample(batch_size=32)
    # ... train ...
    buffer.update_priorities(indices, new_td_errors)
```
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import torch

logger = logging.getLogger(__name__)


# =============================================================================
# UNIFIED EXPERIENCE TYPE
# =============================================================================


@dataclass
class UnifiedExperience:
    """Unified experience format supporting all experience types.

    This single type replaces:
    - ReplayExperience (prioritized_replay.py)
    - ReceiptTriplet (receipt_buffer.py)
    - EnhancedExperience (enhanced_online_learning.py)
    - GoalConditionedExperience (hindsight_replay.py)
    """

    # Type discriminator
    experience_type: Literal["rl", "tic", "goal", "generic"] = "rl"

    # Common fields
    timestamp: float = field(default_factory=time.time)
    priority: float = 1.0
    times_sampled: int = 0
    task_id: str = "default"

    # RL Experience fields
    state: torch.Tensor | None = None
    action: dict[str, Any] | torch.Tensor | None = None
    next_state: torch.Tensor | None = None
    reward: float = 0.0
    done: bool = False
    td_error: float = 1.0

    # TIC Triplet fields
    tic_data: dict[str, Any] | None = None
    plan_state: torch.Tensor | None = None
    execute_state: torch.Tensor | None = None
    verify_state: torch.Tensor | None = None
    actual_success: bool = False
    actual_postconditions: dict[str, Any] = field(default_factory=dict[str, Any])
    correlation_id: str = ""

    # Goal-Conditioned fields
    goal: Any = None
    achieved_goal: Any = None

    # Context fields (for CentralExperienceStore compatibility)
    context: dict[str, Any] = field(default_factory=dict[str, Any])
    outcome: dict[str, Any] = field(default_factory=dict[str, Any])
    valence: float = 0.0

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    agent_id: str = ""
    surprisal: float = 0.0
    coherence: float = 1.0
    complexity: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "experience_type": self.experience_type,
            "timestamp": self.timestamp,
            "priority": self.priority,
            "task_id": self.task_id,
            "metadata": self.metadata,
        }

        if self.experience_type == "rl":
            result.update(
                {
                    "reward": self.reward,
                    "done": self.done,
                    "td_error": self.td_error,
                }
            )
        elif self.experience_type == "tic":
            result.update(
                {
                    # Normalize optional payloads for stable serialization.
                    "tic_data": self.tic_data or {},
                    "actual_success": self.actual_success,
                    "correlation_id": self.correlation_id,
                }
            )
        elif self.experience_type == "goal":
            result.update(
                {
                    "reward": self.reward,
                    "done": self.done,
                }
            )

        return result


# =============================================================================
# UNIFIED REPLAY BUFFER CONFIG
# =============================================================================


@dataclass
class UnifiedReplayConfig:
    """Configuration for UnifiedReplayBuffer."""

    # Buffer size
    capacity: int = 100_000

    # Prioritized sampling (Schaul et al. 2015)
    alpha: float = 0.6  # Priority exponent (0=uniform, 1=full prioritization)
    beta_start: float = 0.4  # Initial importance sampling exponent
    beta_end: float = 1.0  # Final importance sampling exponent
    beta_frames: int = 100_000  # Frames over which to anneal β
    epsilon: float = 1e-6  # Small constant for non-zero probability

    # DreamerV3-style replay ratio
    replay_ratio: int = 16  # Gradient steps per environment step

    # Sampling
    batch_size: int = 32
    uniform_ratio: float = 0.0  # % from uniform (0 = pure prioritized)

    # E8 geometric indexing
    enable_geometric_indexing: bool = True
    num_e8_buckets: int = 240  # E8 root count

    # Staleness decay
    staleness_decay: float = 0.9999

    # Type-specific capacities (soft limits)
    rl_fraction: float = 0.7  # Target fraction for RL experiences
    tic_fraction: float = 0.2  # Target fraction for TIC triplets
    goal_fraction: float = 0.1  # Target fraction for goal-conditioned


# =============================================================================
# UNIFIED REPLAY BUFFER
# =============================================================================


class UnifiedReplayBuffer:
    """Single replay buffer for all experience types.

    CONSOLIDATES:
    - PrioritizedReplayBuffer: TD-error prioritized sampling
    - ReceiptBuffer: TIC triplet storage with E8 indexing
    - PrioritizedReplayEnhanced: β annealing and staleness decay
    - CombinedExperienceReplay: Mixed uniform/prioritized sampling
    - HindsightReplayBuffer: Goal relabeling (via experience_type="goal")
    - DistributedReplayBuffer: (DB integration delegated to external sync)

    FEATURES:
    - Single source of truth for all experiences
    - DreamerV3-style replay ratio control
    - Proper β annealing for importance sampling
    - Geometric E8 indexing for efficient retrieval
    - Type-aware sampling (can request specific experience types)
    """

    def __init__(
        self,
        config: UnifiedReplayConfig | None = None,
        *,
        capacity: int | None = None,
        alpha: float | None = None,
        **kwargs: Any,
    ) -> None:
        # Handle backward compatibility: accept capacity/alpha as kwargs
        if config is None:
            config_kwargs: dict[str, Any] = {}
            if capacity is not None:
                config_kwargs["capacity"] = capacity
            if alpha is not None:
                config_kwargs["alpha"] = alpha
            config_kwargs.update(kwargs)
            config = (
                UnifiedReplayConfig(**config_kwargs) if config_kwargs else UnifiedReplayConfig()
            )
        self.config = config

        # Main storage (circular buffer)
        self._buffer: deque[UnifiedExperience] = deque(maxlen=self.config.capacity)

        # Priority tree for O(log N) sampling
        self._priorities: np.ndarray[Any, Any] = np.zeros(self.config.capacity, dtype=np.float64)
        self._max_priority = 1.0
        self._position = 0

        # E8 geometric indexing
        if self.config.enable_geometric_indexing:
            self._e8_buckets: dict[int, list[int]] = {
                i: [] for i in range(self.config.num_e8_buckets)
            }
        else:
            self._e8_buckets = {}

        # Type indices for type-aware sampling
        self._type_indices: dict[str, list[int]] = {
            "rl": [],
            "tic": [],
            "goal": [],
            "generic": [],
        }

        # Statistics
        self._total_added = 0
        self._total_sampled = 0
        self._frame = 0

        logger.info(
            f"✅ UnifiedReplayBuffer initialized: "
            f"capacity={self.config.capacity}, "
            f"replay_ratio={self.config.replay_ratio}, "
            f"α={self.config.alpha}, β={self.config.beta_start}→{self.config.beta_end}"
        )

    def __len__(self) -> int:
        return len(self._buffer)

    @property
    def beta(self) -> float:
        """Get current β with annealing."""
        fraction = min(1.0, self._frame / self.config.beta_frames)
        return self.config.beta_start + fraction * (self.config.beta_end - self.config.beta_start)

    # =========================================================================
    # ADDING EXPERIENCES
    # =========================================================================

    def add(
        self,
        experience: UnifiedExperience,
        priority: float | None = None,
    ) -> None:
        """Add experience to buffer.

        Args:
            experience: UnifiedExperience object
            priority: Optional explicit priority (else computed)
        """
        # Compute priority if not provided
        if priority is None:
            priority = self._compute_priority(experience)

        # Apply staleness decay to existing priorities
        self._apply_staleness_decay()

        # Update position for circular buffer
        if len(self._buffer) >= self.config.capacity:
            # Remove from indices
            old_exp = self._buffer[0]
            self._remove_from_indices(0, old_exp)

        # Store experience
        if len(self._buffer) < self.config.capacity:
            self._buffer.append(experience)
            current_idx = len(self._buffer) - 1
        else:
            self._buffer.append(experience)
            current_idx = len(self._buffer) - 1

        # Update priority
        if current_idx < len(self._priorities):
            self._priorities[current_idx] = priority**self.config.alpha
        else:
            # Expand priorities array if needed
            new_priorities: np.ndarray[Any, Any] = np.zeros(self.config.capacity, dtype=np.float64)
            new_priorities[: len(self._priorities)] = self._priorities
            self._priorities = new_priorities
            self._priorities[current_idx] = priority**self.config.alpha

        self._max_priority = max(self._max_priority, priority)

        # Add to type index
        exp_type = experience.experience_type
        if exp_type in self._type_indices:
            self._type_indices[exp_type].append(current_idx)

        # Add to E8 bucket
        if self._e8_buckets:
            # Use explicit None check (tensors don't support `or` for None fallback)
            state = experience.state if experience.state is not None else experience.plan_state
            if state is not None:
                bucket_idx = self._get_e8_bucket(state)
                self._e8_buckets[bucket_idx].append(current_idx)

        self._total_added += 1
        self._frame += 1

    def _compute_priority(self, exp: UnifiedExperience) -> float:
        """Compute multi-criteria priority.

        Priority = α₁|δ| + α₂·surprisal + α₃·(1-coherence) + ε
        """
        td_component = abs(exp.td_error) if exp.td_error else abs(exp.valence) * 100
        surprisal_component = exp.surprisal
        coherence_gap = 1.0 - exp.coherence

        priority = (
            0.6 * td_component
            + 0.2 * surprisal_component
            + 0.2 * coherence_gap
            + self.config.epsilon
        )

        return max(priority, self.config.epsilon)

    def _apply_staleness_decay(self) -> None:
        """Apply decay to existing priorities."""
        if len(self._buffer) > 0:
            valid_len = min(len(self._buffer), self.config.capacity)
            self._priorities[:valid_len] *= self.config.staleness_decay

    def _remove_from_indices(self, idx: int, exp: UnifiedExperience) -> None:
        """Remove experience from type and E8 indices.

        FIXED (Jan 4, 2026): Now properly cleans up E8 buckets.
        Also decrements all indices > idx since deque shifts on popleft.
        """
        exp_type = exp.experience_type
        if exp_type in self._type_indices and idx in self._type_indices[exp_type]:
            self._type_indices[exp_type].remove(idx)

        # E8 bucket cleanup - now properly implemented
        if self._e8_buckets:
            state = exp.state if exp.state is not None else exp.plan_state
            if state is not None:
                bucket_idx = self._get_e8_bucket(state)
                if idx in self._e8_buckets[bucket_idx]:
                    self._e8_buckets[bucket_idx].remove(idx)

        # CRITICAL: Decrement all indices > idx since deque.append + maxlen poplefts
        # When the oldest item (idx 0) is removed, all remaining items shift down by 1
        for type_list in self._type_indices.values():
            for i in range(len(type_list)):
                if type_list[i] > idx:
                    type_list[i] -= 1

        for bucket_list in self._e8_buckets.values():
            for i in range(len(bucket_list)):
                if bucket_list[i] > idx:
                    bucket_list[i] -= 1

    def _get_e8_bucket(self, state: torch.Tensor) -> int:
        """Map state to E8 bucket via hash."""
        if state.dim() > 1:
            state = state.flatten()

        # Simple hash: dot product with E8 roots
        state_sum = state.sum().item()
        bucket = int(abs(state_sum * 240) % self.config.num_e8_buckets)
        return bucket

    # =========================================================================
    # SAMPLING
    # =========================================================================

    def sample(
        self,
        batch_size: int | None = None,
        experience_type: str | None = None,
        device: str = "cpu",
    ) -> tuple[list[UnifiedExperience], torch.Tensor, np.ndarray[Any, Any]]:
        """Sample prioritized batch with importance weights.

        Args:
            batch_size: Number of experiences (default: config.batch_size)
            experience_type: Optional filter for specific type
            device: Device for weight tensor

        Returns:
            (experiences, importance_weights, indices)
        """
        n = batch_size or self.config.batch_size
        n = min(n, len(self._buffer))

        if n == 0:
            return [], torch.ones(0, device=device), np.array([])

        # Get valid indices
        if experience_type and experience_type in self._type_indices:
            valid_indices = self._type_indices[experience_type]
            if not valid_indices:
                # Fall back to all types
                valid_indices = list(range(len(self._buffer)))
        else:
            valid_indices = list(range(len(self._buffer)))

        n = min(n, len(valid_indices))
        if n == 0:
            return [], torch.ones(0, device=device), np.array([])

        # Compute sampling probabilities
        priorities = self._priorities[valid_indices]
        total_priority = priorities.sum()

        if total_priority == 0:
            probabilities = np.ones(len(valid_indices)) / len(valid_indices)
        else:
            probabilities = priorities / total_priority

        # Mixed sampling: prioritized + uniform
        if self.config.uniform_ratio > 0:
            n_uniform = int(n * self.config.uniform_ratio)
            n_prioritized = n - n_uniform

            # Prioritized sample
            if n_prioritized > 0:
                prioritized_idx = np.random.choice(
                    len(valid_indices),
                    size=n_prioritized,
                    replace=False,
                    p=probabilities,
                )
            else:
                prioritized_idx = np.array([])

            # Uniform sample
            if n_uniform > 0:
                uniform_idx = np.random.choice(
                    len(valid_indices),
                    size=n_uniform,
                    replace=False,
                )
            else:
                uniform_idx = np.array([])

            sample_idx = np.concatenate([prioritized_idx, uniform_idx]).astype(int)
        else:
            # Pure prioritized sampling
            sample_idx = np.random.choice(
                len(valid_indices),
                size=n,
                replace=False,
                p=probabilities,
            )

        # Map back to buffer indices
        indices = np.array([valid_indices[i] for i in sample_idx])

        # Compute importance sampling weights
        weights = (len(valid_indices) * probabilities[sample_idx]) ** (-self.beta)
        weights /= weights.max()  # Normalize

        # Gather experiences
        experiences = [self._buffer[i] for i in indices]

        # Update sampling metadata
        _current_time = time.time()
        for idx in indices:
            self._buffer[idx].times_sampled += 1

        self._total_sampled += n

        return (
            experiences,
            torch.tensor(weights, dtype=torch.float32, device=device),
            indices,
        )

    def sample_by_state(
        self,
        query_state: torch.Tensor,
        k: int = 5,
        device: str = "cpu",
    ) -> tuple[list[UnifiedExperience], torch.Tensor, np.ndarray[Any, Any]]:
        """Sample experiences geometrically similar to query state.

        Uses E8 bucket lookup for efficient nearest-neighbor search.
        """
        if not self._e8_buckets or len(self._buffer) == 0:
            return self.sample(k, device=device)

        # Find E8 bucket
        bucket_idx = self._get_e8_bucket(query_state)

        # Get candidates from bucket and neighbors
        candidate_indices = list(self._e8_buckets.get(bucket_idx, []))

        # Add neighbors if not enough
        if len(candidate_indices) < k:
            for offset in [-1, 1, -7, 7]:
                neighbor_idx = (bucket_idx + offset) % self.config.num_e8_buckets
                candidate_indices.extend(self._e8_buckets.get(neighbor_idx, []))

        # Filter to valid indices
        valid_indices = [i for i in candidate_indices if 0 <= i < len(self._buffer)]

        if len(valid_indices) == 0:
            return self.sample(k, device=device)

        # Compute distances and get k-nearest
        distances = []
        for idx in valid_indices:
            exp = self._buffer[idx]
            # Use explicit None check (tensors don't support `or` for None fallback)
            state = exp.state if exp.state is not None else exp.plan_state
            if state is not None:
                dist = (state.flatten() - query_state.flatten()).pow(2).sum().item()
            else:
                dist = float("inf")
            distances.append((idx, dist))

        distances.sort(key=lambda x: x[1])
        selected_indices = np.array([d[0] for d in distances[:k]])

        # Gather and return
        experiences = [self._buffer[i] for i in selected_indices]
        weights = torch.ones(len(experiences), dtype=torch.float32, device=device)

        return experiences, weights, selected_indices

    # =========================================================================
    # PRIORITY UPDATES
    # =========================================================================

    def update_priorities(
        self,
        indices: np.ndarray[Any, Any],
        priorities: np.ndarray[Any, Any] | list[float],
    ) -> None:
        """Update priorities based on TD-errors.

        Call this after learning from batch with new TD-errors.
        """
        priorities = np.array(priorities)

        for idx, priority in zip(indices, priorities, strict=False):
            if 0 <= idx < len(self._buffer):
                priority = max(float(priority), self.config.epsilon)
                self._max_priority = max(self._max_priority, priority)
                self._priorities[idx] = priority**self.config.alpha

                # Also update experience td_error
                self._buffer[idx].td_error = priority

    # =========================================================================
    # REPLAY RATIO SUPPORT
    # =========================================================================

    def sample_for_replay_ratio(
        self,
        batch_size: int | None = None,
        device: str = "cpu",
    ) -> list[tuple[list[UnifiedExperience], torch.Tensor, np.ndarray[Any, Any]]]:
        """Sample batches for DreamerV3-style replay ratio.

        Returns replay_ratio batches for training.

        Usage:
            for batch, weights, indices in buffer.sample_for_replay_ratio():
                loss = train_step(batch, weights)
                buffer.update_priorities(indices, new_td_errors)
        """
        batches = []
        for _ in range(self.config.replay_ratio):
            batch = self.sample(batch_size, device=device)
            batches.append(batch)
        return batches

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get buffer statistics."""
        valid_len = len(self._buffer)

        type_counts = {
            k: len([i for i in v if i < valid_len]) for k, v in self._type_indices.items()
        }

        return {
            "size": valid_len,
            "capacity": self.config.capacity,
            "utilization": valid_len / self.config.capacity,
            "total_added": self._total_added,
            "total_sampled": self._total_sampled,
            "current_beta": self.beta,
            "frame": self._frame,
            "max_priority": self._max_priority,
            "mean_priority": float(self._priorities[:valid_len].mean()) if valid_len > 0 else 0.0,
            "type_counts": type_counts,
            "replay_ratio": self.config.replay_ratio,
            "e8_buckets_used": sum(1 for b in self._e8_buckets.values() if b)
            if self._e8_buckets
            else 0,
        }

    # Back-compat: unified RL loop queries replay stats with a standard name
    def get_replay_stats(self) -> dict[str, Any]:
        """Return normalized replay statistics for compatibility."""
        stats = self.get_stats()
        return {
            "size": stats.get("size", 0),
            "capacity": stats.get("capacity", self.config.capacity),
            "avg_priority": stats.get("mean_priority", 0.0),
            "alpha": self.config.alpha,
            "beta": self.beta,
        }

    def clear(self) -> None:
        """Clear the buffer."""
        self._buffer.clear()
        self._priorities = np.zeros(self.config.capacity, dtype=np.float64)
        self._max_priority = 1.0
        self._position = 0
        self._e8_buckets = {i: [] for i in range(self.config.num_e8_buckets)}
        self._type_indices = {k: [] for k in self._type_indices}


# =============================================================================
# SINGLETON ACCESS
# =============================================================================


_unified_replay: UnifiedReplayBuffer | None = None


def get_unified_replay(
    config: UnifiedReplayConfig | None = None,
    *,
    capacity: int | None = None,
    **kwargs: Any,
) -> UnifiedReplayBuffer:
    """Get singleton UnifiedReplayBuffer instance.

    Args:
        config: Configuration (only used on first call)
        capacity: Convenience arg - creates config with this capacity
        **kwargs: Additional config parameters

    Returns:
        UnifiedReplayBuffer instance
    """
    global _unified_replay
    if _unified_replay is None:
        # Handle convenience capacity argument
        if config is None and (capacity is not None or kwargs):
            config = UnifiedReplayConfig(
                capacity=capacity if capacity is not None else 100_000,
                **kwargs,
            )
        _unified_replay = UnifiedReplayBuffer(config)
    return _unified_replay


def reset_unified_replay() -> None:
    """Reset the singleton."""
    global _unified_replay
    _unified_replay = None


# =============================================================================
# COMPATIBILITY ADAPTERS
# =============================================================================


def create_rl_experience(
    state: torch.Tensor,
    action: dict[str, Any] | torch.Tensor,
    next_state: torch.Tensor,
    reward: float,
    done: bool,
    td_error: float = 1.0,
    **kwargs: Any,
) -> UnifiedExperience:
    """Create RL experience for compatibility with PrioritizedReplayBuffer."""
    return UnifiedExperience(
        experience_type="rl",
        state=state,
        action=action,
        next_state=next_state,
        reward=reward,
        done=done,
        td_error=td_error,
        priority=abs(td_error),
        **kwargs,
    )


def create_tic_triplet(
    tic_data: dict[str, Any],
    plan_state: torch.Tensor,
    execute_state: torch.Tensor,
    verify_state: torch.Tensor,
    actual_success: bool,
    correlation_id: str = "",
    **kwargs: Any,
) -> UnifiedExperience:
    """Create TIC triplet for compatibility with ReceiptBuffer."""
    return UnifiedExperience(
        experience_type="tic",
        tic_data=tic_data,
        plan_state=plan_state,
        execute_state=execute_state,
        verify_state=verify_state,
        actual_success=actual_success,
        correlation_id=correlation_id,
        priority=1.0 if actual_success else 2.0,  # Failures are more informative
        **kwargs,
    )


def create_goal_experience(
    state: torch.Tensor,
    action: Any,
    next_state: torch.Tensor,
    goal: Any,
    achieved_goal: Any,
    reward: float,
    done: bool,
    **kwargs: Any,
) -> UnifiedExperience:
    """Create goal-conditioned experience for compatibility with HindsightReplayBuffer."""
    return UnifiedExperience(
        experience_type="goal",
        state=state,
        action=action,
        next_state=next_state,
        goal=goal,
        achieved_goal=achieved_goal,
        reward=reward,
        done=done,
        priority=abs(reward) + 0.1,
        **kwargs,
    )


__all__ = [
    "UnifiedExperience",
    "UnifiedReplayBuffer",
    "UnifiedReplayConfig",
    "create_goal_experience",
    "create_rl_experience",
    "create_tic_triplet",
    "get_unified_replay",
    "reset_unified_replay",
]
