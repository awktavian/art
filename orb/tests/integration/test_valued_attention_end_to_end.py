"""End-to-end integration test for valued-attention system."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import numpy as np

from kagami.core.attention import (
    get_preference_memory,
    get_valued_attention_head,
    manifold_to_state_vector,
)
from kagami.core.attention.session_manager import get_session_manager
from kagami.core.attention.value_function import extract_reward_from_receipt


class TestValuedAttentionIntegration:
    """Integration tests for complete valued-attention loop."""

    def test_session_lifecycle(self) -> None:
        """Test session start → operations → session end."""
        session_mgr = get_session_manager()
        pref_memory = get_preference_memory()

        # Start session
        session_mgr.start_session("test_session_001")

        # P_sess should be zero
        assert np.all(pref_memory.P_sess == 0.0)

        # Set P_long to known value
        pref_memory.P_long[0] = 0.5

        # Simulate operations that update P_sess
        head = get_valued_attention_head()

        for _ in range(5):
            T = 3
            E = np.zeros((T, 16), dtype=np.float32)
            E[0, 0] = 1.0  # Tool invocation

            head.last_attention_weights = np.array([0.7, 0.2, 0.1], dtype=np.float32)
            head.last_attribute_embeddings = E
            head.last_state = manifold_to_state_vector()

            from kagami.core.attention.state_vector import H, StateVector

            reward = 1.0
            next_state = StateVector(vector=np.random.rand(H).astype(np.float32))

            head.backward(reward, next_state, session_only=True)

        # P_sess should be non-zero now
        assert np.any(pref_memory.P_sess != 0.0), "P_sess should update during session"

        # P_long should still be 0.5 at index 0 (session_only=True)
        assert pref_memory.P_long[0] == 0.5

        # End session
        session_mgr.end_session()

    def test_P_long_persists_across_sessions(self) -> None:
        """Verify P_long persists when session resets."""
        pref_memory = get_preference_memory()
        session_mgr = get_session_manager()

        # Set P_long to known value
        pref_memory.P_long[5] = 0.75

        # Start session
        session_mgr.start_session("session_A")

        # P_long should still be 0.75
        assert pref_memory.P_long[5] == 0.75

        # P_sess should be reset
        assert np.all(pref_memory.P_sess == 0.0)

    def test_reward_extraction_from_receipt(self) -> None:
        """Test reward signal extraction from receipt."""

        # Receipt with success
        receipt_success = {
            "metrics": {"prediction_error": 0.1},
            "event": {"name": "success", "data": {"safety_margin": 0.9}},
            "duration_ms": 500,
        }

        reward_success = extract_reward_from_receipt(receipt_success)
        assert reward_success > 0.0, "Success receipt should give positive reward"

        # Receipt with failure
        receipt_failure = {
            "metrics": {"prediction_error": 2.0},
            "event": {"name": "error", "data": {"safety_margin": 0.2}},
            "duration_ms": 5000,
        }

        reward_failure = extract_reward_from_receipt(receipt_failure)
        assert reward_failure < 0.0, "Failure receipt should give negative reward"

    def test_safety_mask_enforcement(self) -> None:
        """Verify safety masking prevents unsafe attention."""
        head = get_valued_attention_head()

        T = 5
        logits = np.ones(T, dtype=np.float32)
        tokens = ["safe"] * T

        from kagami.core.attention.state_vector import H, StateVector

        state = StateVector(vector=np.ones(H, dtype=np.float32) * 0.8)

        # Mark token 2 as unsafe
        context = {"unsafe_tokens": [2]}

        result = head.forward(logits, tokens, state, context=context)

        # Token 2 should have near-zero attention
        assert result.attention_weights[2] < 1e-6

        # Other tokens should share remaining attention
        safe_sum = sum(result.attention_weights[i] for i in [0, 1, 3, 4])
        assert safe_sum > 0.99

    def test_complete_learning_cycle(self) -> None:
        """Test complete cycle: forward → outcome → backward → preferences update."""
        head = get_valued_attention_head()
        pref_memory = get_preference_memory()

        # Store initial P
        P_initial = pref_memory.P.copy()

        # Forward
        T = 5
        logits = np.random.randn(T).astype(np.float32)
        tokens = ["tool", "safety", "check", "verify", "done"]

        from kagami.core.attention.state_vector import H, StateVector

        state = StateVector(vector=np.random.rand(H).astype(np.float32))

        head.forward(logits, tokens, state)

        # Backward with positive reward
        reward = 2.0
        next_state = StateVector(vector=np.random.rand(H).astype(np.float32))

        td_error = head.backward(reward, next_state)

        # P should have changed
        P_after = pref_memory.P
        assert not np.allclose(P_after, P_initial), "Preferences should update after learning"

        # TD error should be non-zero (learning happened)
        assert td_error != 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
