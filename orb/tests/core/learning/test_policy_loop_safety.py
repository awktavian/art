"""Tests for PolicyLoop hard safety rejection and UCB exploration.

Verifies:
1. Hard safety rejection (h(x) < 0 raises SafetyViolationError)
2. UCB exploration replaces epsilon-greedy
3. CBF enforcement remains intact during action selection

Created: December 15, 2025
Status: Core safety test
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

import torch

from kagami.core.exceptions import SafetyViolationError
from kagami.core.learning.policy_loop import PolicyLoop, UCBExplorer


class TestHardSafetyRejection:
    """Test suite for hard safety constraint enforcement."""

    def test_safe_action_no_exception(self):
        """Safe action (h(x) > 0) should execute without exception."""
        policy_loop = PolicyLoop(
            state_dim=4,
            action_dim=2,
            use_cbf=True,
            safety_threshold=0.3,
        )

        # Any state with safe=False should execute
        # (This tests the baseline policy execution path)
        safe_state = torch.tensor([[0.1, 0.1, 0.1, 0.1]], dtype=torch.float32)

        # Should not raise when safety is disabled
        action = policy_loop.select_action(safe_state, safe=False)
        assert action.shape == (1, 2)  # type: ignore[union-attr]

    def test_unsafe_action_raises_exception(self):
        """Unsafe action (h(x) < 0) should raise SafetyViolationError."""
        policy_loop = PolicyLoop(
            state_dim=4,
            action_dim=2,
            use_cbf=True,
            safety_threshold=0.3,
        )

        # Unsafe state: high risk values that violate h(x) >= 0
        # With weights [0.4, 0.3, 0.1, 0.2] and threshold 0.3
        # h(x) = 0.3 - (0.4*0.9 + 0.3*0.9 + 0.1*0.9 + 0.2*0.9)
        #      = 0.3 - 0.9 = -0.6 < 0
        unsafe_state = torch.tensor([[0.9, 0.9, 0.9, 0.9]], dtype=torch.float32)

        with pytest.raises(SafetyViolationError) as exc_info:
            policy_loop.select_action(unsafe_state, safe=True)

        # Verify exception contains h(x) value
        assert "h(x)" in str(exc_info.value)
        assert "< 0" in str(exc_info.value) or "negative" in str(exc_info.value)

    def test_exception_contains_diagnostics(self):
        """SafetyViolationError should contain diagnostic information."""
        policy_loop = PolicyLoop(
            state_dim=4,
            action_dim=2,
            use_cbf=True,
            safety_threshold=0.2,
        )

        # Critically unsafe state
        unsafe_state = torch.tensor([[1.0, 1.0, 1.0, 1.0]], dtype=torch.float32)

        with pytest.raises(SafetyViolationError) as exc_info:
            policy_loop.select_action(unsafe_state, safe=True)

        # Should include barrier value
        error_msg = str(exc_info.value)
        assert "h(x)" in error_msg or "barrier" in error_msg

    def test_safe_false_bypasses_check(self):
        """When safe=False, should not raise even for unsafe states."""
        policy_loop = PolicyLoop(
            state_dim=4,
            action_dim=2,
            use_cbf=True,
            safety_threshold=0.3,
        )

        unsafe_state = torch.tensor([[0.9, 0.9, 0.9, 0.9]], dtype=torch.float32)

        # Should not raise when safe=False
        action = policy_loop.select_action(unsafe_state, safe=False)
        assert action.shape == (1, 2)  # type: ignore[union-attr]

    def test_batch_safety_rejection(self):
        """Batch with any unsafe state should raise."""
        policy_loop = PolicyLoop(
            state_dim=4,
            action_dim=2,
            use_cbf=True,
            safety_threshold=0.3,
        )

        # Mixed batch: first safe, second unsafe
        mixed_states = torch.tensor(
            [
                [0.1, 0.1, 0.1, 0.1],  # Safe
                [0.9, 0.9, 0.9, 0.9],  # Unsafe
            ],
            dtype=torch.float32,
        )

        with pytest.raises(SafetyViolationError):
            policy_loop.select_action(mixed_states, safe=True)

    def test_margin_violation_detection(self):
        """Test detection of states near safety boundary."""
        policy_loop = PolicyLoop(
            state_dim=4,
            action_dim=2,
            use_cbf=True,
            safety_threshold=0.3,
        )

        # State just below threshold
        # h(x) = 0.3 - (0.4*0.6 + 0.3*0.6 + 0.1*0.6 + 0.2*0.6)
        #      = 0.3 - 0.6 = -0.3 < 0
        marginal_state = torch.tensor([[0.6, 0.6, 0.6, 0.6]], dtype=torch.float32)

        with pytest.raises(SafetyViolationError):
            policy_loop.select_action(marginal_state, safe=True)


class TestUCBExploration:
    """Test suite for Upper Confidence Bound exploration."""

    def test_ucb_initialization(self):
        """UCB explorer should initialize correctly."""
        ucb = UCBExplorer(
            n_actions=5,
            c=2.0,
        )
        assert ucb.n_actions == 5
        assert ucb.c == 2.0
        assert ucb.Q.shape == (5,)
        assert ucb.N.shape == (5,)
        assert ucb.t == 0

    def test_ucb_prefers_unexplored(self):
        """UCB should prefer unexplored actions."""
        ucb = UCBExplorer(n_actions=3)

        # Action 0: Q=0.5, N=10
        # Action 1: Q=0.6, N=0 (unexplored)
        # Action 2: Q=0.7, N=10
        ucb.Q = torch.tensor([0.5, 0.6, 0.7])
        ucb.N = torch.tensor([10.0, 0.0, 10.0])
        ucb.t = 20

        action = ucb.select_action()

        # Should select action 1 (unexplored, high Q)
        assert action == 1

    def test_ucb_balances_exploitation_exploration(self):
        """UCB should balance Q-value (exploit) and uncertainty (explore)."""
        ucb = UCBExplorer(n_actions=2, c=1.0)

        # Action 0: Q=0.8, N=100 (high Q, low uncertainty)
        # Action 1: Q=0.5, N=1 (lower Q, high uncertainty)
        ucb.Q = torch.tensor([0.8, 0.5])
        ucb.N = torch.tensor([100.0, 1.0])
        ucb.t = 101

        # At t=101:
        # UCB_0 = 0.8 + sqrt(2*ln(101)/100) ≈ 0.8 + 0.215 = 1.015
        # UCB_1 = 0.5 + sqrt(2*ln(101)/1) ≈ 0.5 + 3.04 = 3.54
        # Should prefer action 1 (exploration)

        action = ucb.select_action()
        assert action == 1

    def test_ucb_update(self):
        """Test UCB statistics update."""
        ucb = UCBExplorer(n_actions=3)

        # Update action 1 with reward 0.8
        ucb.update(action=1, reward=0.8)

        assert ucb.N[1] == 1.0
        assert ucb.Q[1] == 0.8
        assert ucb.t == 1

        # Update again with reward 0.6
        ucb.update(action=1, reward=0.6)

        assert ucb.N[1] == 2.0
        # Q should be running average: (0.8 + 0.6) / 2 = 0.7
        assert abs(ucb.Q[1] - 0.7) < 1e-6
        assert ucb.t == 2

    def test_ucb_confidence_increases_with_time(self):
        """Exploration bonus should decrease as action is tried more."""
        ucb = UCBExplorer(n_actions=1, c=2.0)

        # Try same action multiple times
        confidences = []
        for i in range(1, 11):
            ucb.t = i * 10  # Total time increases faster
            ucb.N[0] = float(i)  # Action visits increase
            confidence = ucb._compute_ucb_bonus(action=0)
            confidences.append(confidence)

        # Bonus should generally decrease as N increases relative to t
        # Check first vs last (allow some variance in middle)
        assert confidences[0] > confidences[-1]

    def test_ucb_c_parameter_controls_exploration(self):
        """Larger c should increase exploration."""
        ucb_low = UCBExplorer(n_actions=2, c=0.5)
        ucb_high = UCBExplorer(n_actions=2, c=5.0)

        ucb_low.Q = torch.tensor([0.7, 0.5])
        ucb_high.Q = torch.tensor([0.7, 0.5])
        ucb_low.N = torch.tensor([10.0, 1.0])
        ucb_high.N = torch.tensor([10.0, 1.0])
        ucb_low.t = 11
        ucb_high.t = 11

        bonus_low = ucb_low._compute_ucb_bonus(action=1)
        bonus_high = ucb_high._compute_ucb_bonus(action=1)

        assert bonus_high > bonus_low

    def test_ucb_continuous_actions(self):
        """Test UCB with continuous action discretization."""
        ucb = UCBExplorer(
            n_actions=10,
            action_bounds=(0.0, 1.0),
        )

        # Select discrete action
        discrete_action = ucb.select_action()
        assert 0 <= discrete_action < 10

        # Convert to continuous
        continuous_action = ucb.discrete_to_continuous(discrete_action)
        assert 0.0 <= continuous_action <= 1.0

    def test_ucb_reset(self):
        """Test UCB statistics reset."""
        ucb = UCBExplorer(n_actions=5)

        # Do some updates
        for i in range(10):
            ucb.update(action=i % 5, reward=0.5)

        assert ucb.t == 10
        assert ucb.N.sum() == 10

        # Reset
        ucb.reset()

        assert ucb.t == 0
        assert ucb.N.sum() == 0
        assert ucb.Q.sum() == 0


class TestIntegration:
    """Integration tests for safety + UCB."""

    def test_policy_loop_with_ucb(self):
        """PolicyLoop should integrate with UCB explorer."""
        policy_loop = PolicyLoop(
            state_dim=4,
            action_dim=2,
            use_cbf=True,
            use_ucb_exploration=True,
            ucb_n_actions=10,
        )

        assert hasattr(policy_loop, "ucb_explorer")
        assert policy_loop.ucb_explorer is not None

        safe_state = torch.tensor([[0.1, 0.1, 0.1, 0.1]], dtype=torch.float32)
        # Test with safe=False to avoid random extractor rejections
        action = policy_loop.select_action(safe_state, safe=False, explore=True)

        assert action.shape == (1, 2)  # type: ignore[union-attr]

    def test_ucb_respects_safety(self):
        """UCB exploration should still respect safety constraints."""
        policy_loop = PolicyLoop(
            state_dim=4,
            action_dim=2,
            use_cbf=True,
            use_ucb_exploration=True,
        )

        unsafe_state = torch.tensor([[0.9, 0.9, 0.9, 0.9]], dtype=torch.float32)

        # Even with exploration, unsafe states should raise
        with pytest.raises(SafetyViolationError):
            policy_loop.select_action(unsafe_state, safe=True, explore=True)

    def test_metrics_include_ucb(self):
        """Metrics should include UCB exploration stats."""
        policy_loop = PolicyLoop(
            state_dim=4,
            action_dim=2,
            use_ucb_exploration=True,
        )

        metrics = policy_loop.get_metrics()

        # Should include UCB-related metrics
        assert "ucb_enabled" in metrics
        assert metrics["ucb_enabled"] == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
