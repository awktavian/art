from __future__ import annotations

from typing import Any

"""Preference Memory - Stable attentional preferences over time.

Maintains two timescales:
- P_long: Trait-level preferences (persistent across sessions)
- P_sess: Session-level preferences (ephemeral, cleared on reset)

P = P_long + P_sess

Dimensions (m=16):
0. tool_invocation_frequency
1. safety_check_priority
2. causal_reasoning_depth
3. plan_phase_thoroughness
4. verify_phase_strictness
5. novel_concept_tolerance
6. tim_value_alignment
7. code_over_docs_bias
8. refactor_boldness
9. test_coverage_preference
10. collaboration_seeking
11. hive_consultation_rate
12. autonomous_initiative
13. error_correction_speed
14. convergence_patience
15. exploration_vs_exploitation
"""
import json
import logging

import numpy as np

logger = logging.getLogger(__name__)

# Preference dimension labels for interpretability
PREFERENCE_DIMENSIONS = [
    "tool_invocation_frequency",
    "safety_check_priority",
    "causal_reasoning_depth",
    "plan_phase_thoroughness",
    "verify_phase_strictness",
    "novel_concept_tolerance",
    "tim_value_alignment",
    "code_over_docs_bias",
    "refactor_boldness",
    "test_coverage_preference",
    "collaboration_seeking",
    "hive_consultation_rate",
    "autonomous_initiative",
    "error_correction_speed",
    "convergence_patience",
    "exploration_vs_exploitation",
]

M = len(PREFERENCE_DIMENSIONS)  # 16 dimensions


class PreferenceMemory:
    """Stores and updates attentional preferences via Hebbian+TD learning.

    Two timescales:
    - P_long: Slow, trait-level (η_p = 0.0001, persists across sessions)
    - P_sess: Fast, session-level (η_p = 0.01, cleared on reset)

    Updates:
        P ← (1-η_d)P + η_p·δ_t·(Σ_t a_t e_t)

    Normalization (Oja rule):
        P ← P - η_o·(P^T P - c)·P
    """

    def __init__(
        self,
        m: int = M,
        eta_p_slow: float = 0.0001,
        eta_p_fast: float = 0.01,
        eta_decay: float = 0.001,
        eta_oja: float = 0.001,
        target_norm: float = 1.0,
    ) -> None:
        """Initialize preference memory.

        Args:
            m: Dimension of preference space (default 16)
            eta_p_slow: Learning rate for P_long (trait-level)
            eta_p_fast: Learning rate for P_sess (session-level)
            eta_decay: Weight decay rate
            eta_oja: Oja normalization rate
            target_norm: Target norm for Oja (default 1.0)
        """
        self.m = m
        self.eta_p_slow = eta_p_slow
        self.eta_p_fast = eta_p_fast
        self.eta_decay = eta_decay
        self.eta_oja = eta_oja
        self.target_norm = target_norm

        # Preference vectors
        self.P_long = np.zeros(m, dtype=np.float32)  # Trait
        self.P_sess = np.zeros(m, dtype=np.float32)  # Session

        # Tracking
        self.update_count_long = 0
        self.update_count_sess = 0

    @property
    def P(self) -> np.ndarray[Any, Any]:
        """Combined preference vector: P = P_long + P_sess."""
        return self.P_long + self.P_sess

    def update(
        self,
        td_error: float,
        attribution_weights: np.ndarray[Any, Any],
        attribute_embeddings: np.ndarray[Any, Any],
        session_only: bool = False,
    ) -> None:
        """Update preferences via Hebbian+TD learning.

        Args:
            td_error: TD error δ_t = r_t + γ·V(s') - V(s)
            attribution_weights: a_t ∝ attention weights (T,)
            attribute_embeddings: e_t for each token (T, m)
            session_only: If True, only update P_sess
        """
        # Compute credit-assigned gradient: Σ_t a_t e_t
        # Shape: (T,) @ (T, m) -> (m,)
        gradient = attribution_weights @ attribute_embeddings

        # Update P_sess (fast, session-level)
        self.P_sess = (1 - self.eta_decay) * self.P_sess + self.eta_p_fast * td_error * gradient
        self.update_count_sess += 1

        # Update P_long (slow, trait-level) unless session_only
        if not session_only:
            self.P_long = (1 - self.eta_decay) * self.P_long + self.eta_p_slow * td_error * gradient
            self.update_count_long += 1

        # Oja normalization (prevent blow-up)
        self._oja_normalize(self.P_sess)
        if not session_only:
            self._oja_normalize(self.P_long)

    def _oja_normalize(self, P: np.ndarray[Any, Any]) -> None:
        """Apply Oja normalization rule in-place.

        P ← P - η_o·(P^T P - c)·P

        This keeps ||P|| ≈ √c without explicit normalization.
        """
        norm_sq = np.dot(P, P)
        P -= self.eta_oja * (norm_sq - self.target_norm) * P

    def reset_session(self) -> None:
        """Clear session-level preferences (called on context reset)."""
        self.P_sess = np.zeros(self.m, dtype=np.float32)
        self.update_count_sess = 0
        logger.info("Preference memory: session reset")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for persistence."""
        return {
            "P_long": self.P_long.tolist(),
            "P_sess": self.P_sess.tolist(),
            "update_count_long": self.update_count_long,
            "update_count_sess": self.update_count_sess,
            "hyperparams": {
                "eta_p_slow": self.eta_p_slow,
                "eta_p_fast": self.eta_p_fast,
                "eta_decay": self.eta_decay,
                "eta_oja": self.eta_oja,
                "target_norm": self.target_norm,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PreferenceMemory:
        """Deserialize from dictionary."""
        hyperparams = data.get("hyperparams", {})
        memory = cls(
            m=len(data["P_long"]),
            eta_p_slow=hyperparams.get("eta_p_slow", 0.0001),
            eta_p_fast=hyperparams.get("eta_p_fast", 0.01),
            eta_decay=hyperparams.get("eta_decay", 0.001),
            eta_oja=hyperparams.get("eta_oja", 0.001),
            target_norm=hyperparams.get("target_norm", 1.0),
        )
        memory.P_long = np.array(data["P_long"], dtype=np.float32)  # type: ignore[assignment]

        memory.P_sess = np.array(data["P_sess"], dtype=np.float32)  # type: ignore[assignment]
        memory.update_count_long = data.get("update_count_long", 0)
        memory.update_count_sess = data.get("update_count_sess", 0)
        return memory

    def get_top_preferences(self, k: int = 5) -> list[tuple[str, float]]:
        """Get top-k preferred dimensions (for interpretability).

        Returns:
            List of (dimension_name, value) sorted by magnitude
        """
        P_combined = self.P
        indices = np.argsort(np.abs(P_combined))[::-1][:k]
        return [(PREFERENCE_DIMENSIONS[i], float(P_combined[i])) for i in indices]


# Singleton instance
_preference_memory: PreferenceMemory | None = None


def get_preference_memory() -> PreferenceMemory:
    """Get singleton preference memory instance."""
    global _preference_memory
    if _preference_memory is None:
        _preference_memory = PreferenceMemory()

        # Try to load from Redis
        try:
            from kagami.core.caching.redis import RedisClientFactory

            redis_client = RedisClientFactory.get_client(
                purpose="default", async_mode=False, decode_responses=True
            )
            data = redis_client.get("kagami:preference_memory")
            if data:
                _preference_memory = PreferenceMemory.from_dict(json.loads(data))
                logger.info("Loaded preference memory from Redis")
        except Exception as e:
            logger.warning(f"Could not load preference memory from Redis: {e}")

    return _preference_memory


def save_preference_memory() -> None:
    """Save preference memory to Redis."""
    global _preference_memory
    if _preference_memory is None:
        return

    try:
        from kagami.core.caching.redis import RedisClientFactory

        redis_client = RedisClientFactory.get_client(
            purpose="default", async_mode=False, decode_responses=True
        )
        data = json.dumps(_preference_memory.to_dict())
        redis_client.set("kagami:preference_memory", data, ex=86400 * 30)  # 30 days
        logger.info("Saved preference memory to Redis")
    except Exception as e:
        logger.warning(f"Could not save preference memory to Redis: {e}")
