from __future__ import annotations

from typing import Any

"""Valued-Attention Head - Attention that learns preferences.

Implements attention with preference memory:
    L' = L + B_long + B_state + B_homeo
    α' = softmax(L')

Where:
- L = QK^T / √d_k (standard attention logits)
- B_long = β·⟨P, e_t⟩ (long-term preferences)
- B_state = γ·s^T W_v e_t (state-coupled preferences)
- B_homeo = -λ·||s - s*||² (homeostatic pressure)

Learning:
- After outcome, compute TD error δ_t
- Update P via Hebbian+TD: P ← (1-η_d)P + η_p·δ·(Σ a_t e_t)
- Normalize via Oja rule to prevent blow-up
"""
import logging
from dataclasses import dataclass

import numpy as np

from kagami.core.attention.attribute_encoder import (
    AttributeEncoder,
    get_attribute_encoder,
)
from kagami.core.attention.preference_memory import (
    M,
    PreferenceMemory,
    get_preference_memory,
)
from kagami.core.attention.state_vector import TARGET_STATE, H, StateVector
from kagami.core.attention.value_function import (
    CriticNetwork,
    get_value_function,
)

logger = logging.getLogger(__name__)


@dataclass
class AttentionHyperparams:
    """Hyperparameters for valued-attention."""

    # Bias strengths
    beta: float = 0.1  # Long-term preference bias
    gamma: float = 0.05  # State-coupled bias
    delta: float = 0.05  # Semantic identity bias
    lambda_: float = 0.01  # Homeostatic pressure (lambda is reserved keyword)

    # Exploration
    xi: float = 0.1  # Novelty bonus coefficient
    tau: float = 0.5  # Entropy floor (temperature clamp)

    # Safety
    h_threshold: float = 0.0  # CBF safety threshold


@dataclass
class AttentionResult:
    """Result from valued-attention forward pass."""

    logits_prime: np.ndarray[Any, Any]  # Modified logits L'
    attention_weights: np.ndarray[Any, Any]  # α' = softmax(L')
    output: np.ndarray[Any, Any]  # α' @ V

    # Bias components (for interpretability)
    B_long: np.ndarray[Any, Any]
    B_state: np.ndarray[Any, Any]
    B_semantic: np.ndarray[Any, Any] | None
    B_homeo: float

    # Metadata
    entropy: float
    safety_masked_count: int
    novelty_bonus_applied: bool


class ValuedAttentionHead:
    """Attention head with preference memory and homeostatic regulation.

    Modifies standard attention to:
    1. Prefer patterns that led to success (B_long)
    2. Adapt to current internal state (B_state)
    3. Maintain homeostatic balance (B_homeo)
    4. Enforce safety constraints (masking)
    5. Maintain entropy floor (prevent collapse)
    """

    def __init__(
        self,
        preference_memory: PreferenceMemory | None = None,
        value_function: CriticNetwork | None = None,
        attribute_encoder: AttributeEncoder | None = None,
        hyperparams: AttentionHyperparams | None = None,
    ) -> None:
        """Initialize valued-attention head.

        Args:
            preference_memory: Preference memory (P_long, P_sess)
            value_function: Critic network V(s)
            attribute_encoder: Token → attribute embedding
            hyperparams: Tunable parameters
        """
        self.pref_memory = preference_memory or get_preference_memory()
        self.value_fn = value_function or get_value_function()
        self.attr_encoder = attribute_encoder or get_attribute_encoder()
        self.hyperparams = hyperparams or AttentionHyperparams()

        # State coupling matrix W_v: (h, m) - learns how state modulates preferences
        # Initialize randomly
        self.W_v = np.random.randn(H, M).astype(np.float32) * 0.01

        # Semantic coupling matrix W_sem: (d_sem, m) - learns how identity modulates preferences
        # We don't know d_sem a priori (usually 32 or 384), so we initialize lazily or generic
        self.W_sem: np.ndarray[Any, Any] | None = None

        # Tracking
        self.last_attention_weights: np.ndarray[Any, Any] | None = None
        self.last_attribute_embeddings: np.ndarray[Any, Any] | None = None
        self.last_state: StateVector | None = None

    def forward(
        self,
        logits: np.ndarray[Any, Any],
        tokens: list[str],
        state: StateVector,
        context: dict[str, Any] | None = None,
    ) -> AttentionResult:
        """Forward pass with preference biases.

        Args:
            logits: Standard attention logits L = QK^T / √d_k (T,)
            tokens: Token strings for attribute encoding (T,)
            state: Current proprioceptive state s ∈ R^h
            context: Optional context (phase, safety info, etc.)

        Returns:
            AttentionResult with modified logits and metadata
        """
        T = len(logits)

        # Encode tokens to attribute space: e_t ∈ R^m for each token
        E = self.attr_encoder.encode_sequence(tokens, context)  # (T, m)

        # Get combined preferences: P = P_long + P_sess ∈ R^m
        P = self.pref_memory.P

        # Compute bias terms

        # B_long = β·⟨P, e_t⟩ for each token t
        # Shape: (m,) @ (T, m)^T = (T,)
        B_long = self.hyperparams.beta * (E @ P)  # (T,)

        # B_state = γ·s^T W_v e_t for each token t
        # Shape: (h,) @ (h, m) @ (T, m)^T = (T,)
        s_vec = state.vector  # (h,)
        B_state_matrix = s_vec @ self.W_v  # (m,) - state-modulated preference
        B_state = self.hyperparams.gamma * (E @ B_state_matrix)  # (T,)

        # B_semantic = δ·sem^T W_sem e_t (semantic identity bias)
        B_semantic = None
        if state.semantic_pointer is not None:
            sem_vec = state.semantic_pointer  # (d_sem,)

            # Lazy init W_sem
            if self.W_sem is None or self.W_sem.shape[0] != sem_vec.shape[0]:
                d_sem = sem_vec.shape[0]
                self.W_sem = np.random.randn(d_sem, M).astype(np.float32) * 0.01

            B_sem_matrix = sem_vec @ self.W_sem  # (m,)
            B_semantic = self.hyperparams.delta * (E @ B_sem_matrix)  # (T,)

        # B_homeo = -λ·||s - s*||² (scalar, same for all tokens)
        dist_sq = np.sum((state.vector - TARGET_STATE) ** 2)
        B_homeo = -self.hyperparams.lambda_ * dist_sq

        # Novelty bonus (state-dependent)
        novelty_bonus_applied = False
        if state.safety > 0.7 and state.integration > 0.5:
            # Safe to explore - add novelty bonus
            for i, _token in enumerate(tokens):
                if context and context.get("is_novel", False):
                    B_state[i] += self.hyperparams.xi
                    novelty_bonus_applied = True

        # Safety masking: B_long[t] = -∞ for unsafe tokens
        safety_masked_count = 0
        if context and "unsafe_tokens" in context:
            unsafe_indices = context["unsafe_tokens"]
            for idx in unsafe_indices:
                if 0 <= idx < T:
                    B_long[idx] = -np.inf
                    safety_masked_count += 1

        # Combine: L' = L + B_long + B_state + B_homeo + (B_semantic or 0)
        L_prime = logits + B_long + B_state + B_homeo
        if B_semantic is not None:
            L_prime += B_semantic

        # Softmax with temperature clamping (entropy floor)
        alpha_prime = self._softmax_with_entropy_floor(L_prime)

        # Compute entropy
        entropy = self._compute_entropy(alpha_prime)

        # Store for backward pass
        self.last_attention_weights = alpha_prime
        self.last_attribute_embeddings = E
        self.last_state = state

        # Output (simplified - assumes values V provided externally)
        # In practice, this would be α' @ V where V are value vectors
        # For now, just return the weights
        output = alpha_prime  # Placeholder

        return AttentionResult(
            logits_prime=L_prime,
            attention_weights=alpha_prime,
            output=output,
            B_long=B_long,
            B_state=B_state,
            B_semantic=B_semantic,
            B_homeo=B_homeo,  # type: ignore[arg-type]
            entropy=entropy,
            safety_masked_count=safety_masked_count,
            novelty_bonus_applied=novelty_bonus_applied,
        )

    def backward(
        self,
        reward: float,
        next_state: StateVector,
        done: bool = False,
        session_only: bool = False,
    ) -> float:
        """Backward pass: update preferences via Hebbian+TD learning.

        Args:
            reward: Immediate reward r_t
            next_state: Next state s_{t+1}
            done: If True, terminal state (no future value)
            session_only: If True, only update P_sess (not P_long)

        Returns:
            TD error δ_t
        """
        if self.last_attention_weights is None:
            logger.warning("No forward pass stored, cannot update preferences")
            return 0.0

        # Compute TD error: δ = r + γ·V(s') - V(s)
        td_error = self.value_fn.compute_td_error(
            s_t=self.last_state.vector,  # type: ignore  # Union member
            reward=reward,
            s_next=next_state.vector,
            done=done,
        )

        # Train value function
        target = reward + (
            0.0 if done else self.value_fn.gamma_td * self.value_fn.forward(next_state.vector)
        )
        loss = self.value_fn.train_step(self.last_state.vector, target)  # type: ignore  # Union member

        # Attribution: a_t = attention weights (stop gradient)
        # In practice, could use attention rollout or integrated gradients
        a_t = self.last_attention_weights.copy()  # (T,)

        # Hebbian+TD update: P ← (1-η_d)P + η_p·δ·(Σ a_t e_t)
        self.pref_memory.update(
            td_error=td_error,
            attribution_weights=a_t,
            attribute_embeddings=self.last_attribute_embeddings,  # type: ignore[arg-type]
            session_only=session_only,
        )

        # Emit metrics
        try:
            from kagami_observability.metrics import (
                VALUED_ATTENTION_TD_ERROR,
                VALUED_ATTENTION_VALUE_LOSS,
            )

            VALUED_ATTENTION_TD_ERROR.observe(abs(td_error))  # Dynamic attr
            VALUED_ATTENTION_VALUE_LOSS.observe(loss)  # Dynamic attr
        except Exception:
            pass

        logger.debug(f"Valued-attention: δ={td_error:.3f}, loss={loss:.3f}, r={reward:.3f}")

        return td_error

    def _softmax_with_entropy_floor(self, logits: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        """Softmax with temperature adjustment to maintain entropy floor.

        If entropy would drop below τ, increase temperature.

        Args:
            logits: Input logits (T,)

        Returns:
            Attention weights (T,) with entropy ≥ τ
        """
        # Standard softmax
        exp_logits = np.exp(logits - np.max(logits))  # Numerical stability
        alpha = exp_logits / np.sum(exp_logits)

        # Check entropy
        entropy = self._compute_entropy(alpha)

        # If below floor, increase temperature to reach target entropy
        if entropy < self.hyperparams.tau:
            # Binary search for temperature that achieves target entropy
            temp_low, temp_high = 1.0, 100.0
            target_entropy = self.hyperparams.tau

            for _ in range(10):  # Max 10 iterations
                temp = (temp_low + temp_high) / 2.0
                exp_logits_temp = np.exp(logits / temp - np.max(logits / temp))
                alpha_temp = exp_logits_temp / np.sum(exp_logits_temp)
                ent_temp = self._compute_entropy(alpha_temp)

                if abs(ent_temp - target_entropy) < 0.01:  # Close enough
                    alpha = alpha_temp
                    break
                elif ent_temp < target_entropy:
                    temp_low = temp  # Need higher temperature
                else:
                    temp_high = temp  # Need lower temperature
            else:
                # If binary search didn't converge, use high temp as fallback
                alpha = alpha_temp

        return alpha

    def _compute_entropy(self, alpha: np.ndarray[Any, Any]) -> float:
        """Compute entropy H(α) = -Σ α_i log α_i.

        Args:
            alpha: Attention weights (T,)

        Returns:
            Entropy in nats
        """
        # Avoid log(0)
        alpha_safe = np.clip(alpha, 1e-10, 1.0)
        entropy = -np.sum(alpha * np.log(alpha_safe))
        return float(entropy)

    def reset_session(self) -> None:
        """Clear session-level preferences."""
        self.pref_memory.reset_session()
        logger.info("Valued-attention: session reset")

    def get_top_preferences(self, k: int = 5) -> list[tuple[str, float]]:
        """Get top-k learned preferences (interpretability).

        Returns:
            List of (attribute_name, value) sorted by magnitude
        """
        return self.pref_memory.get_top_preferences(k=k)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for persistence."""
        return {
            "W_v": self.W_v.tolist(),
            "W_sem": self.W_sem.tolist() if self.W_sem is not None else None,
            "hyperparams": {
                "beta": self.hyperparams.beta,
                "gamma": self.hyperparams.gamma,
                "delta": self.hyperparams.delta,
                "lambda": self.hyperparams.lambda_,
                "xi": self.hyperparams.xi,
                "tau": self.hyperparams.tau,
                "h_threshold": self.hyperparams.h_threshold,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValuedAttentionHead:
        """Deserialize from dictionary."""
        hp_data = data.get("hyperparams", {})
        hyperparams = AttentionHyperparams(
            beta=hp_data.get("beta", 0.1),
            gamma=hp_data.get("gamma", 0.05),
            delta=hp_data.get("delta", 0.05),
            lambda_=hp_data.get("lambda", 0.01),
            xi=hp_data.get("xi", 0.1),
            tau=hp_data.get("tau", 0.5),
            h_threshold=hp_data.get("h_threshold", 0.0),
        )

        head = cls(hyperparams=hyperparams)
        head.W_v = np.array(data["W_v"], dtype=np.float32)
        if data.get("W_sem") is not None:
            head.W_sem = np.array(data["W_sem"], dtype=np.float32)

        return head


# Singleton instance
_valued_attention_head: ValuedAttentionHead | None = None


def get_valued_attention_head() -> ValuedAttentionHead:
    """Get singleton valued-attention head."""
    global _valued_attention_head
    if _valued_attention_head is None:
        _valued_attention_head = ValuedAttentionHead()

        # Try to load from Redis
        try:
            import json

            from kagami.core.caching.redis import RedisClientFactory

            redis_client = RedisClientFactory.get_client(
                purpose="default", async_mode=False, decode_responses=True
            )
            data = redis_client.get("kagami:valued_attention_head")
            if data:
                _valued_attention_head = ValuedAttentionHead.from_dict(json.loads(data))
                logger.info("Loaded valued-attention head from Redis")
        except Exception as e:
            logger.warning(f"Could not load valued-attention head from Redis: {e}")

    return _valued_attention_head


def save_valued_attention_head() -> None:
    """Save valued-attention head to Redis."""
    global _valued_attention_head
    if _valued_attention_head is None:
        return

    try:
        import json

        from kagami.core.caching.redis import RedisClientFactory

        redis_client = RedisClientFactory.get_client(
            purpose="default", async_mode=False, decode_responses=True
        )
        data = json.dumps(_valued_attention_head.to_dict())
        redis_client.set("kagami:valued_attention_head", data, ex=86400 * 30)  # 30 days
        logger.info("Saved valued-attention head to Redis")
    except Exception as e:
        logger.warning(f"Could not save valued-attention head to Redis: {e}")
