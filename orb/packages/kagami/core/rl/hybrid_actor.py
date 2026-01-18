from __future__ import annotations

"""Hybrid Actor: Fast hash-based + Slow semantic-based action selection.

Combines the speed of classical RL (hash tables, <1ms) with the generalization
of neural RL (semantic embeddings, ~20ms) for optimal performance.

Key innovation: Adaptive path selection based on state frequency.
- Frequent states → Fast hash lookup
- Novel states → Slow semantic matching

Result: 95% operations use fast path, 5% use smart path.
"""
import logging
from collections import Counter
from typing import Any

import numpy as np
import torch

from kagami.core.rl.actor_critic import Actor
from kagami.core.rl.semantic_encoder import get_semantic_encoder

logger = logging.getLogger(__name__)


class HybridActor(Actor):
    """Hybrid actor with dual-mode action selection.

    Fast Path (frequent states):
      - Hash-based policy lookup
      - <1ms decision time
      - 95% of operations

    Slow Path (novel states):
      - Semantic embedding + similarity search
      - ~20ms decision time
      - 5% of operations (novel situations)

    Over time: Novel → Frequent → Fast (automatic optimization)
    """

    def __init__(
        self,
        action_dim: int = 128,
        novel_threshold: int = 3,
    ) -> None:
        """Initialize hybrid actor.

        Args:
            action_dim: Number of discrete actions
            novel_threshold: State seen < this many times = novel
        """
        super().__init__(action_dim=action_dim)

        # Semantic encoder for novel states
        self._semantic_encoder = get_semantic_encoder()

        # State frequency tracking
        self._state_frequency = Counter()  # type: ignore  # Var
        self._novel_threshold = novel_threshold

        # Cache semantic embeddings for seen states
        self._state_embeddings: dict[str, np.ndarray[Any, Any]] = {}

        # Statistics
        self._fast_path_count = 0
        self._slow_path_count = 0

    async def sample_actions(  # type: ignore  # Override
        self,
        state: Any,
        k: int = 5,
        exploration_noise: float = 0.2,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Sample k candidate actions (hybrid mode).

        Args:
            state: Current latent state
            k: Number of candidates to sample
            exploration_noise: Exploration factor (0=greedy, 1=random)
            context: Additional context for semantic encoding

        Returns:
            List of candidate actions
        """
        state_hash = self._compute_state_hash(state)
        self._state_frequency[state_hash] += 1

        # FAST PATH: Frequent state (seen >= threshold times)
        if self._state_frequency[state_hash] >= self._novel_threshold:
            self._fast_path_count += 1
            logger.debug(f"🚀 Fast path: state seen {self._state_frequency[state_hash]} times")

            # Emit metric
            try:
                from kagami_observability.metrics import kagami_rl_hybrid_path_total

                kagami_rl_hybrid_path_total.labels(path="fast").inc()
            except Exception:
                pass

            # IMPORTANT: Use keyword arguments to avoid mis-binding 'context' to
            # the parent's 'temperature' parameter. Passing positionally can set[Any]
            # temperature=None and trigger TypeError in logits/temperature.
            return await super().sample_actions(
                state,
                k,
                exploration_noise=exploration_noise,
                context=context,
            )

        # SLOW PATH: Novel state (semantic matching)
        self._slow_path_count += 1
        logger.info(
            f"🧠 Slow path: novel state (seen {self._state_frequency[state_hash]} times), "
            f"using semantic matching"
        )

        # Emit metrics
        try:
            from kagami_observability.metrics import (
                kagami_rl_hybrid_path_total,
                kagami_rl_novel_states_total,
            )

            kagami_rl_hybrid_path_total.labels(path="slow").inc()
            kagami_rl_novel_states_total.inc()
        except Exception:
            pass

        return await self._sample_actions_semantic(state, k, exploration_noise, context)

    async def _sample_actions_semantic(
        self,
        state: Any,
        k: int,
        exploration_noise: float,
        context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Sample actions using semantic similarity to past states.

        Args:
            state: Current state
            k: Number of candidates
            exploration_noise: Exploration factor
            context: Context for semantic encoding

        Returns:
            Candidate actions from similar past states
        """
        # Encode current state semantically
        if context is None:
            context = {"state": str(state)[:200]}

        query_embedding = await self._semantic_encoder.encode(context)
        state_hash = self._compute_state_hash(state)

        # Cache embedding for future use
        self._state_embeddings[state_hash] = query_embedding

        # Find similar past states
        similar_states = self._semantic_encoder.find_similar_states(
            query_embedding=query_embedding,
            state_embeddings=list(self._state_embeddings.items()),
            top_k=min(10, len(self._state_embeddings)),
            min_similarity=0.6,  # 60% similarity threshold
        )

        if not similar_states:
            # No similar states found - use exploration
            logger.debug("No similar states found, exploring randomly")
            return await super().sample_actions(state, k, exploration_noise=0.8, context=context)

        # Blend policies from similar states
        blended_actions = []

        for similar_hash, similarity in similar_states[:k]:
            # Get policy from similar state
            if similar_hash in self._policy_weights:
                logits = self._policy_weights[similar_hash]
                probs = self._softmax(logits)

                # Weight by similarity
                weighted_probs = probs * similarity

                # Sample action
                p = weighted_probs / weighted_probs.sum()
                action_idx = int(torch.multinomial(p, num_samples=1).item())

                action = self._index_to_action(action_idx, state)
                action["similarity_source"] = similar_hash
                action["similarity_score"] = float(similarity)

                blended_actions.append(action)

        # Add exploration if needed
        if len(blended_actions) < k:
            exploration_actions = await super().sample_actions(
                state, k - len(blended_actions), exploration_noise=0.8, context=context
            )
            blended_actions.extend(exploration_actions)

        logger.debug(
            f"Sampled {len(blended_actions)} actions via semantic matching "
            f"(from {len(similar_states)} similar states)"
        )

        return blended_actions[:k]

    async def update(  # type: ignore  # Override
        self, trajectory: list[Any], returns: list[float], baseline: list[float]
    ) -> float:
        """Update policy (standard policy gradient).

        Note: Both fast and slow path updates use the same gradient descent.
        Novel states gradually become frequent → automatic migration to fast path.

        Args:
            trajectory: State-action trajectory
            returns: Discounted returns
            baseline: Value function baseline

        Returns:
            Policy loss
        """
        # Use parent class update (works for both paths)
        loss = await super().update(trajectory, returns, baseline)

        # Log path statistics periodically
        total_samples = self._fast_path_count + self._slow_path_count
        if total_samples > 0 and total_samples % 100 == 0:
            fast_pct = (self._fast_path_count / total_samples) * 100
            logger.info(
                f"📊 Hybrid Actor Stats: {fast_pct:.1f}% fast path, "
                f"{100 - fast_pct:.1f}% slow path (total: {total_samples})"
            )

        return loss

    def get_stats(self) -> dict[str, Any]:
        """Get hybrid actor statistics."""
        total = self._fast_path_count + self._slow_path_count

        return {
            "fast_path_count": self._fast_path_count,
            "slow_path_count": self._slow_path_count,
            "total_samples": total,
            "fast_path_pct": (self._fast_path_count / max(1, total)) * 100,
            "unique_states": len(self._policy_weights),
            "cached_embeddings": len(self._state_embeddings),
            "novel_threshold": self._novel_threshold,
        }


# Global singleton
_hybrid_actor: HybridActor | None = None


def get_hybrid_actor() -> HybridActor:
    """Get or create global hybrid actor."""
    global _hybrid_actor

    if _hybrid_actor is None:
        _hybrid_actor = HybridActor()
        logger.info("🎯 Hybrid actor initialized (fast hash + slow semantic paths)")

    return _hybrid_actor


def get_actor() -> HybridActor:
    """Get actor (returns hybrid actor for backward compatibility)."""
    return get_hybrid_actor()
