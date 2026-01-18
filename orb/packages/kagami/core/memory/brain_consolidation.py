"""Brain-Inspired Consolidation - Sleep Replay & Schema Extraction.

BRAIN SCIENCE BASIS (December 2025):
====================================
Extends existing MemoryConsolidation with brain-inspired mechanisms:

1. SHARP-WAVE RIPPLES (SWR) during NREM
   - Prioritized replay of high-value experiences
   - Compressed "fast-forward" of episodes

2. SCHEMA EXTRACTION
   - Extract generalized patterns from repeated experiences
   - Online clustering with Kuramoto-like schema formation

3. SYNAPTIC HOMEOSTASIS
   - Normalize weights to prevent saturation
   - Enable continuous learning without forgetting

Integrates with existing MemoryConsolidation and UnifiedReplayBuffer.

References:
- Diekelmann & Born (2010): The memory function of sleep
- McClelland et al. (1995): Complementary learning systems
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


@dataclass
class BrainExperience:
    """Experience with brain-inspired priority metadata."""

    state: torch.Tensor  # [8] E8 code
    action: torch.Tensor  # [8] action
    reward: float
    next_state: torch.Tensor
    done: bool = False

    # Priority signals (brain-inspired)
    td_error: float = 0.0  # Prediction error (hippocampal surprise)
    emotional_salience: float = 0.0  # Amygdala valence
    novelty: float = 0.0  # Novelty signal
    replay_count: int = 0  # How many times replayed
    timestamp: float = field(default_factory=time.time)

    # Schema assignment
    schema_id: int = -1
    schema_distance: float = float("inf")

    @property
    def priority(self) -> float:
        """Compute replay priority (higher = more likely to replay)."""
        # TD error most important (prediction learning)
        # Emotional salience next (survival-relevant)
        # Novelty for exploration
        # Decay with replay count (don't over-replay)
        base = abs(self.td_error) * 0.5 + self.emotional_salience * 0.3 + self.novelty * 0.2
        decay = 0.9**self.replay_count
        return base * decay + 0.01  # Minimum priority


class SchemaExtractor(nn.Module):
    """Extract and maintain schemas from experience patterns.

    Schemas are generalized knowledge structures (like concepts).
    Uses online k-means-like clustering.
    """

    def __init__(
        self,
        state_dim: int = 8,
        num_schemas: int = 32,
        learning_rate: float = 0.01,
        assignment_threshold: float = 2.0,
    ):
        super().__init__()
        self.state_dim = state_dim
        self.num_schemas = num_schemas
        self.lr = learning_rate
        self.threshold = assignment_threshold

        # Schema centroids
        self.centroids = nn.Parameter(torch.randn(num_schemas, state_dim) * 0.1)

        # Schema statistics (buffers, not parameters)
        self.register_buffer("counts", torch.zeros(num_schemas))
        self.register_buffer("success_rates", torch.zeros(num_schemas))
        self.register_buffer("last_updated", torch.zeros(num_schemas))

    def assign(self, state: torch.Tensor) -> tuple[int, float]:
        """Assign state to nearest schema.

        Args:
            state: [D] or [B, D] state tensor

        Returns:
            schema_idx: Nearest schema index
            distance: Distance to centroid
        """
        if state.dim() == 1:
            state = state.unsqueeze(0)

        # Compute distances
        distances = torch.cdist(state, self.centroids)  # [B, K]
        min_dist, idx = distances.min(dim=-1)

        return idx[0].item(), min_dist[0].item()  # type: ignore[return-value]

    def update(
        self,
        schema_idx: int,
        state: torch.Tensor,
        reward: float,
    ) -> None:
        """Update schema with new experience."""
        with torch.no_grad():
            # Moving average update of centroid
            self.centroids[schema_idx] = (
                self.centroids[schema_idx] * (1 - self.lr) + state * self.lr
            )

            # Update statistics
            self.counts[schema_idx] += 1  # type: ignore[operator, index]
            old_rate = self.success_rates[schema_idx]  # type: ignore[index]
            n = self.counts[schema_idx]  # type: ignore[index]
            self.success_rates[schema_idx] = old_rate + (reward - old_rate) / n  # type: ignore[operator]
            self.last_updated[schema_idx] = time.time()  # type: ignore[operator]

    def normalize(self) -> None:
        """Synaptic homeostasis: normalize schema centroids."""
        with torch.no_grad():
            norms = self.centroids.norm(dim=-1, keepdim=True)
            self.centroids.div_(norms.clamp(min=0.1))

    def get_active_schemas(self) -> list[int]:
        """Get indices of schemas with experiences."""
        return list((self.counts > 0).nonzero(as_tuple=True)[0].tolist())  # type: ignore[operator, union-attr]

    def get_stats(self) -> dict[str, Any]:
        """Get schema statistics."""
        active = self.get_active_schemas()
        return {
            "num_active": len(active),
            "total_experiences": self.counts.sum().item(),  # type: ignore[operator]
            "avg_success_rate": self.success_rates[active].mean().item() if active else 0.0,  # type: ignore[index]
        }


class BrainReplayBuffer:
    """Prioritized replay buffer with brain-inspired sampling.

    Implements proportional prioritization with:
    - TD error priority (prediction learning)
    - Emotional salience (survival relevance)
    - Novelty bonus (exploration)
    - Replay decay (avoid over-fitting)
    """

    def __init__(
        self,
        capacity: int = 100000,
        alpha: float = 0.6,  # Priority exponent
        beta: float = 0.4,  # Importance sampling
        beta_increment: float = 0.001,
    ):
        self.capacity = capacity
        self.alpha = alpha
        self.beta = beta
        self.beta_increment = beta_increment

        self.buffer: list[BrainExperience] = []
        self.position = 0

    def add(self, exp: BrainExperience) -> None:
        """Add experience to buffer."""
        if len(self.buffer) < self.capacity:
            self.buffer.append(exp)
        else:
            self.buffer[self.position] = exp
        self.position = (self.position + 1) % self.capacity

    def sample(
        self,
        batch_size: int,
    ) -> tuple[list[BrainExperience], torch.Tensor, list[int]]:
        """Sample batch with priority weighting.

        Returns:
            experiences: Sampled experiences
            weights: Importance sampling weights
            indices: Buffer indices for priority update
        """
        if len(self.buffer) < batch_size:
            batch_size = len(self.buffer)

        # Compute priorities
        priorities = torch.tensor(
            [exp.priority for exp in self.buffer],
            dtype=torch.float32,
        )
        probs = priorities**self.alpha
        probs = probs / probs.sum()

        # Sample
        indices = torch.multinomial(probs, batch_size, replacement=False).tolist()
        experiences = [self.buffer[i] for i in indices]

        # Importance sampling weights
        N = len(self.buffer)
        weights = (N * probs[indices]) ** (-self.beta)
        weights = weights / weights.max()

        # Increment beta
        self.beta = min(1.0, self.beta + self.beta_increment)

        # Mark as replayed
        for i in indices:
            self.buffer[i].replay_count += 1

        return experiences, weights, indices

    def update_priorities(
        self,
        indices: list[int],
        td_errors: list[float],
    ) -> None:
        """Update priorities based on TD errors."""
        for idx, td_error in zip(indices, td_errors, strict=True):
            self.buffer[idx].td_error = td_error

    def __len__(self) -> int:
        return len(self.buffer)


class BrainConsolidation(nn.Module):
    """Brain-inspired memory consolidation system.

    Combines:
    1. Prioritized replay buffer (SWR analog)
    2. Schema extraction (semantic memory)
    3. Synaptic homeostasis (weight normalization)
    """

    def __init__(
        self,
        state_dim: int = 8,
        buffer_capacity: int = 100000,
        num_schemas: int = 32,
        consolidation_interval: int = 1000,
    ):
        super().__init__()
        self.state_dim = state_dim
        self.consolidation_interval = consolidation_interval

        # Replay buffer
        self.replay_buffer = BrainReplayBuffer(capacity=buffer_capacity)

        # Schema extractor
        self.schema_extractor = SchemaExtractor(
            state_dim=state_dim,
            num_schemas=num_schemas,
        )

        # Counters
        self.steps = 0
        self.consolidation_count = 0

    def add_experience(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        reward: float,
        next_state: torch.Tensor,
        done: bool = False,
        td_error: float = 0.0,
        emotional_salience: float = 0.0,
        novelty: float = 0.0,
    ) -> None:
        """Add experience with brain-inspired metadata."""
        # Assign to schema
        schema_idx, schema_dist = self.schema_extractor.assign(state)

        exp = BrainExperience(
            state=state.detach(),
            action=action.detach(),
            reward=reward,
            next_state=next_state.detach(),
            done=done,
            td_error=td_error,
            emotional_salience=emotional_salience,
            novelty=novelty,
            schema_id=schema_idx,
            schema_distance=schema_dist,
        )

        self.replay_buffer.add(exp)

        # Update schema
        self.schema_extractor.update(schema_idx, state, reward)

        # Check for consolidation
        self.steps += 1
        if self.steps % self.consolidation_interval == 0:
            self._consolidate()

    def replay(
        self,
        batch_size: int = 64,
    ) -> tuple[list[BrainExperience], torch.Tensor]:
        """Sample experiences for replay learning."""
        if len(self.replay_buffer) < batch_size:
            return [], torch.tensor([])

        experiences, weights, _ = self.replay_buffer.sample(batch_size)
        return experiences, weights

    def _consolidate(self) -> None:
        """Run consolidation cycle (like sleep)."""
        self.consolidation_count += 1

        # 1. Synaptic homeostasis
        self.schema_extractor.normalize()

        # 2. Log stats
        stats = self.schema_extractor.get_stats()
        logger.debug(
            f"Consolidation {self.consolidation_count}: "
            f"{stats['num_active']} schemas, "
            f"{len(self.replay_buffer)} experiences"
        )

    def sleep_consolidate(
        self,
        num_replays: int = 100,
    ) -> dict[str, Any]:
        """Full sleep-like consolidation cycle.

        Should be called during idle periods.

        Returns:
            Consolidation statistics
        """
        replayed = 0

        for _ in range(num_replays):
            experiences, _ = self.replay(batch_size=32)
            if not experiences:
                break
            replayed += len(experiences)

        # Synaptic homeostasis
        self.schema_extractor.normalize()

        return {
            "replayed": replayed,
            "consolidation_count": self.consolidation_count,
            **self.schema_extractor.get_stats(),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get consolidation statistics."""
        return {
            "buffer_size": len(self.replay_buffer),
            "steps": self.steps,
            "consolidation_count": self.consolidation_count,
            **self.schema_extractor.get_stats(),
        }


# Global instance
_brain_consolidation: BrainConsolidation | None = None


def get_brain_consolidation() -> BrainConsolidation:
    """Get or create brain consolidation instance."""
    global _brain_consolidation
    if _brain_consolidation is None:
        _brain_consolidation = BrainConsolidation()
    return _brain_consolidation


__all__ = [
    "BrainConsolidation",
    "BrainExperience",
    "BrainReplayBuffer",
    "SchemaExtractor",
    "get_brain_consolidation",
]
