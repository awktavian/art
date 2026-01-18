"""Tests for valued-attention bias computation and safety."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import numpy as np

from kagami.core.attention.preference_memory import M, PreferenceMemory
from kagami.core.attention.state_vector import H, StateVector
from kagami.core.attention.valued_attention import (
    AttentionHyperparams,
    ValuedAttentionHead,
)


class TestBiasComputation:
    """Test bias term computation."""

    def test_B_long_shape(self):
        """Verify B_long has shape (T,)."""
        head = ValuedAttentionHead()

        T = 10  # 10 tokens
        logits = np.random.randn(T).astype(np.float32)
        tokens = [f"token_{i}" for i in range(T)]
        state = StateVector(vector=np.random.rand(H).astype(np.float32))

        result = head.forward(logits, tokens, state)

        assert result.B_long.shape == (T,), f"B_long shape mismatch: {result.B_long.shape}"

    def test_B_state_shape(self):
        """Verify B_state has shape (T,)."""
        head = ValuedAttentionHead()

        T = 10
        logits = np.random.randn(T).astype(np.float32)
        tokens = [f"token_{i}" for i in range(T)]
        state = StateVector(vector=np.random.rand(H).astype(np.float32))

        result = head.forward(logits, tokens, state)

        assert result.B_state.shape == (T,), f"B_state shape mismatch: {result.B_state.shape}"

    def test_B_homeo_scalar(self):
        """Verify B_homeo is scalar."""
        head = ValuedAttentionHead()

        T = 10
        logits = np.random.randn(T).astype(np.float32)
        tokens = [f"token_{i}" for i in range(T)]
        state = StateVector(vector=np.random.rand(H).astype(np.float32))

        result = head.forward(logits, tokens, state)

        assert isinstance(result.B_homeo, (float, np.floating)), "B_homeo should be scalar"

    def test_safety_masking(self):
        """Verify safety masking sets B_long = -inf for unsafe tokens."""
        head = ValuedAttentionHead()

        T = 10
        logits = np.random.randn(T).astype(np.float32)
        tokens = [f"token_{i}" for i in range(T)]
        state = StateVector(vector=np.random.rand(H).astype(np.float32))

        # Mark tokens 2, 5, 7 as unsafe
        context = {"unsafe_tokens": [2, 5, 7]}

        result = head.forward(logits, tokens, state, context=context)

        # Check that B_long is -inf for unsafe tokens
        assert np.isinf(result.B_long[2]) and result.B_long[2] < 0
        assert np.isinf(result.B_long[5]) and result.B_long[5] < 0
        assert np.isinf(result.B_long[7]) and result.B_long[7] < 0

        # Check that attention weights are ~0 for unsafe tokens (softmax of -inf)
        assert result.attention_weights[2] < 1e-6
        assert result.attention_weights[5] < 1e-6
        assert result.attention_weights[7] < 1e-6

        assert result.safety_masked_count == 3

    def test_logits_prime_combination(self):
        """Verify L' = L + B_long + B_state + B_homeo."""
        head = ValuedAttentionHead()

        T = 5
        logits = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
        tokens = [f"token_{i}" for i in range(T)]
        state = StateVector(vector=np.ones(H, dtype=np.float32) * 0.5)

        result = head.forward(logits, tokens, state)

        # Verify combination (element-wise for vectors, broadcast for scalar)
        expected = logits + result.B_long + result.B_state + result.B_homeo

        np.testing.assert_allclose(result.logits_prime, expected, rtol=1e-5)

    def test_entropy_floor_enforcement(self):
        """Verify entropy stays above τ threshold."""
        hyperparams = AttentionHyperparams(tau=0.5)
        head = ValuedAttentionHead(hyperparams=hyperparams)

        # Create logits that would give very low entropy (one dominant token)
        T = 10
        logits = np.array([-10.0] * T, dtype=np.float32)
        logits[0] = 10.0  # One very strong token

        tokens = [f"token_{i}" for i in range(T)]
        state = StateVector(vector=np.ones(H, dtype=np.float32) * 0.5)

        result = head.forward(logits, tokens, state)

        # Entropy should be ≥ τ (temperature scaling applied)
        assert (
            result.entropy >= hyperparams.tau * 0.9
        ), f"Entropy {result.entropy} below floor {hyperparams.tau}"


class TestLearningRules:
    """Test Hebbian+TD learning convergence."""

    def test_hebbian_td_convergence(self):
        """Verify P converges toward positive-reward attributes over 100 iterations."""

        # Create fresh preference memory
        pref_memory = PreferenceMemory()
        head = ValuedAttentionHead(preference_memory=pref_memory)

        # Simulate 100 iterations with synthetic data
        # Pattern: tokens with e_t[0] = 1.0 (tool invocation) always get positive reward

        np.random.seed(42)

        for iteration in range(100):
            # Create synthetic tokens
            T = 5
            [f"token_{i}" for i in range(T)]

            # Encode: first token always has e_t[0] = 1.0 (tool invocation)
            E = np.zeros((T, M), dtype=np.float32)
            E[0, 0] = 1.0  # First token is tool invocation

            # Random logits
            np.random.randn(T).astype(np.float32)

            # Random state
            state = StateVector(vector=np.random.rand(H).astype(np.float32))

            # Forward (stores attention weights)
            head.last_attention_weights = np.random.rand(T).astype(np.float32)
            head.last_attention_weights /= head.last_attention_weights.sum()  # Normalize
            head.last_attribute_embeddings = E
            head.last_state = state

            # Simulate: tool invocation always succeeds (positive reward)
            reward = 1.0 if iteration % 2 == 0 else 0.5
            next_state = StateVector(vector=np.random.rand(H).astype(np.float32))

            # Backward (updates P)
            head.backward(reward, next_state)

        # After 100 iterations, P[0] (tool invocation) should be positive
        # because tool invocations got positive rewards
        P_final = pref_memory.P

        assert P_final[0] > 0.0, f"P[0] = {P_final[0]} should be positive after positive rewards"

        # Verify norm is bounded (Oja normalization working)
        norm = np.linalg.norm(P_final)
        assert norm < 5.0, f"Preference norm {norm} too large (Oja should bound it)"

    def test_negative_reward_decreases_preference(self):
        """Verify negative rewards decrease preference for associated attributes."""

        pref_memory = PreferenceMemory()
        head = ValuedAttentionHead(preference_memory=pref_memory)

        # Initial P[0] = 0
        assert pref_memory.P[0] == 0.0

        # Create pattern where dimension 0 gets negative rewards
        for _ in range(50):
            T = 3
            E = np.zeros((T, M), dtype=np.float32)
            E[0, 0] = 1.0  # Dimension 0 active

            # Setup
            head.last_attention_weights = np.array([0.8, 0.1, 0.1], dtype=np.float32)
            head.last_attribute_embeddings = E
            head.last_state = StateVector(vector=np.ones(H, dtype=np.float32) * 0.5)

            # Negative reward
            reward = -1.0
            next_state = StateVector(vector=np.ones(H, dtype=np.float32) * 0.5)

            head.backward(reward, next_state)

        # P[0] should be negative
        assert (
            pref_memory.P[0] < 0.0
        ), f"P[0] = {pref_memory.P[0]} should be negative after negative rewards"


class TestSafetyIntegration:
    """Test safety masking and constraints."""

    def test_safety_mask_prevents_attention(self):
        """Verify unsafe tokens get zero attention via -inf masking."""
        head = ValuedAttentionHead()

        T = 5
        logits = np.ones(T, dtype=np.float32)
        tokens = ["safe", "safe", "UNSAFE", "safe", "UNSAFE"]
        state = StateVector(vector=np.ones(H, dtype=np.float32) * 0.8)

        context = {"unsafe_tokens": [2, 4]}

        result = head.forward(logits, tokens, state, context=context)

        # Unsafe tokens should have near-zero attention
        assert result.attention_weights[2] < 1e-6
        assert result.attention_weights[4] < 1e-6

        # Safe tokens should share remaining attention
        safe_attention_sum = (
            result.attention_weights[0] + result.attention_weights[1] + result.attention_weights[3]
        )
        assert safe_attention_sum > 0.99  # ~1.0

    def test_novelty_bonus_requires_safety(self):
        """Verify novelty bonus only applies when safe."""
        head = ValuedAttentionHead()

        T = 3
        logits = np.zeros(T, dtype=np.float32)
        tokens = ["token"] * T

        # Case 1: Unsafe (safety < 0.7)
        state_unsafe = StateVector(
            vector=np.array([0.5, 0.8, 0.8, 0.1, 0.5, 0.9, 0.8, 0.7], dtype=np.float32)
        )
        result_unsafe = head.forward(logits, tokens, state_unsafe, context={"is_novel": True})
        assert not result_unsafe.novelty_bonus_applied

        # Case 2: Safe but not integrated (integration < 0.5)
        state_fragmented = StateVector(
            vector=np.array([0.8, 0.8, 0.3, 0.1, 0.5, 0.9, 0.8, 0.7], dtype=np.float32)
        )
        result_fragmented = head.forward(
            logits, tokens, state_fragmented, context={"is_novel": True}
        )
        assert not result_fragmented.novelty_bonus_applied

        # Case 3: Safe AND integrated
        state_safe = StateVector(
            vector=np.array([0.8, 0.8, 0.7, 0.1, 0.5, 0.9, 0.8, 0.7], dtype=np.float32)
        )
        result_safe = head.forward(logits, tokens, state_safe, context={"is_novel": True})
        assert result_safe.novelty_bonus_applied


class TestSessionManagement:
    """Test session lifecycle."""

    def test_session_reset_clears_P_sess(self):
        """Verify session reset clears P_sess but preserves P_long."""
        pref_memory = PreferenceMemory()

        # Set both to non-zero
        pref_memory.P_long = np.ones(M, dtype=np.float32) * 0.5  # type: ignore[assignment]
        pref_memory.P_sess = np.ones(M, dtype=np.float32) * 0.3  # type: ignore[assignment]

        # Reset session
        pref_memory.reset_session()

        # P_long preserved
        assert np.all(pref_memory.P_long > 0.4)

        # P_sess cleared
        assert np.all(pref_memory.P_sess == 0.0)

    def test_persistence_roundtrip(self):
        """Verify preference memory serialization roundtrip."""
        pref_memory = PreferenceMemory()

        # Set to known values
        pref_memory.P_long = np.random.randn(M).astype(np.float32)  # type: ignore[assignment]
        pref_memory.P_sess = np.random.randn(M).astype(np.float32)  # type: ignore[assignment]
        pref_memory.update_count_long = 42
        pref_memory.update_count_sess = 13

        # Serialize
        data = pref_memory.to_dict()

        # Deserialize
        restored = PreferenceMemory.from_dict(data)

        # Verify match
        np.testing.assert_allclose(restored.P_long, pref_memory.P_long)
        np.testing.assert_allclose(restored.P_sess, pref_memory.P_sess)
        assert restored.update_count_long == 42
        assert restored.update_count_sess == 13


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_forward_backward_cycle(self):
        """Test complete forward → backward cycle."""
        head = ValuedAttentionHead()

        T = 5
        logits = np.random.randn(T).astype(np.float32)
        tokens = ["tool", "call", "safety", "check", "done"]
        state = StateVector(vector=np.random.rand(H).astype(np.float32))

        # Forward
        result = head.forward(logits, tokens, state)

        assert result.logits_prime.shape == (T,)
        assert result.attention_weights.shape == (T,)
        assert np.abs(result.attention_weights.sum() - 1.0) < 1e-5  # Normalized

        # Backward
        reward = 1.0
        next_state = StateVector(vector=np.random.rand(H).astype(np.float32))

        td_error = head.backward(reward, next_state)

        assert isinstance(td_error, float)

        # Verify preferences updated
        P_after = head.pref_memory.P
        assert np.any(P_after != 0.0), "Preferences should be non-zero after update"

    def test_entropy_maintained(self):
        """Verify entropy stays above floor across multiple steps."""
        hyperparams = AttentionHyperparams(tau=0.5)
        head = ValuedAttentionHead(hyperparams=hyperparams)

        for _ in range(20):
            T = 10
            logits = np.random.randn(T).astype(np.float32) * 10  # Large variance
            tokens = [f"token_{i}" for i in range(T)]
            state = StateVector(vector=np.random.rand(H).astype(np.float32))

            result = head.forward(logits, tokens, state)

            # Entropy should stay above floor
            assert (
                result.entropy >= hyperparams.tau * 0.8
            ), f"Entropy {result.entropy} below floor {hyperparams.tau}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
