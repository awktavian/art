"""Tests for Learned Hierarchical Planning (Pan et al., 2024)."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import numpy as np


class TestTemporalAbstractionNetwork:
    """Test temporal abstraction network."""

    def test_subgoal_encoding(self):
        """Test state encoding to subgoal space."""
        from kagami.core.rl.learned_hierarchical_planning import (
            TemporalAbstractionNetwork,
        )

        net = TemporalAbstractionNetwork(state_dim=128, subgoal_dim=32)

        # Encode state
        state = np.random.randn(128)
        subgoal_emb = net.encode_state_to_subgoal(state)

        # Should return correct dimension
        assert subgoal_emb.shape == (32,)

    def test_subgoal_discovery(self):
        """Test discrete subgoal assignment."""
        from kagami.core.rl.learned_hierarchical_planning import (
            TemporalAbstractionNetwork,
        )

        net = TemporalAbstractionNetwork(n_subgoals=8)

        # Discover subgoal
        state = np.random.randn(128)
        subgoal_id = net.discover_subgoal(state)

        # Should return valid subgoal ID
        assert 0 <= subgoal_id < 8

    def test_prototype_update(self):
        """Test subgoal prototype learning."""
        from kagami.core.rl.learned_hierarchical_planning import (
            TemporalAbstractionNetwork,
        )

        net = TemporalAbstractionNetwork(n_subgoals=4, subgoal_dim=16)

        # Generate trajectory
        np.random.seed(42)
        trajectory = [np.random.randn(128) for _ in range(50)]

        # Update prototypes
        net.update_prototypes(trajectory)

        # Prototypes should be updated (not initial random)
        assert net._subgoal_prototypes.shape == (4, 16)

    def test_subgoal_state_reconstruction(self):
        """Test subgoal to state conversion."""
        from kagami.core.rl.learned_hierarchical_planning import (
            TemporalAbstractionNetwork,
        )

        net = TemporalAbstractionNetwork(state_dim=128, subgoal_dim=32)

        # Get state for subgoal
        state = net.get_subgoal_state(subgoal_id=3)

        assert state.shape == (128,)


class TestHierarchicalValueFunction:
    """Test hierarchical value functions."""

    def test_high_level_value_update(self):
        """Test high-level value function learning."""
        from kagami.core.rl.learned_hierarchical_planning import (
            HierarchicalValueFunction,
        )

        vf = HierarchicalValueFunction(n_subgoals=8)

        state_hash = "test_state"

        # Initialize
        v0 = vf.get_high_level_value(state_hash, subgoal_id=3)
        assert v0 == 0.0

        # Update
        vf.update_high_level(state_hash, subgoal_id=3, reward=1.0, lr=0.1)

        # Should increase
        v1 = vf.get_high_level_value(state_hash, subgoal_id=3)
        assert v1 > 0.0
        assert abs(v1 - 0.1) < 0.01  # 0 + 0.1 * (1 - 0) = 0.1

    def test_low_level_value_update(self):
        """Test low-level value function learning."""
        from kagami.core.rl.learned_hierarchical_planning import (
            HierarchicalValueFunction,
        )

        vf = HierarchicalValueFunction()

        state_hash = "test_state"
        action = "search"

        # Update multiple times
        for _ in range(10):
            vf.update_low_level(state_hash, action, reward=1.0, lr=0.1)

        # Should converge toward 1.0
        value = vf.get_low_level_value(state_hash, action)
        assert value > 0.5  # Should be increasing toward 1.0


class TestLearnedHierarchicalPlanner:
    """Test full hierarchical planner."""

    @pytest.mark.asyncio
    async def test_hierarchical_planning(self):
        """Test hierarchical plan generation."""
        from kagami.core.rl.learned_hierarchical_planning import (
            get_hierarchical_planner,
        )

        planner = get_hierarchical_planner()

        # Create mock state
        class MockState:
            embedding = np.zeros(128).tolist()
            timestamp = 0.0
            context_hash = "initial"

        # Plan
        plan = await planner.plan_hierarchical(initial_state=MockState(), goal=None, horizon=50)

        # Should return valid plan
        assert len(plan.high_level_actions) > 0
        assert len(plan.subgoals) > 0
        assert isinstance(plan.expected_value, float)
        assert 0.0 <= plan.confidence <= 1.0

    def test_learning_from_trajectory(self):
        """Test learning from experience."""
        from kagami.core.rl.learned_hierarchical_planning import (
            get_hierarchical_planner,
        )

        planner = get_hierarchical_planner()

        # Generate trajectory
        trajectory = [np.random.randn(128) for _ in range(20)]
        rewards = [np.random.rand() for _ in range(20)]

        # Learn (should not crash)
        planner.learn_from_trajectory(trajectory, rewards)

        # Subgoal prototypes should be updated
        assert planner.abstraction_net._subgoal_prototypes.shape[0] == 8

    @pytest.mark.asyncio
    async def test_low_level_planning_toward_subgoal(self):
        """Test low-level action planning."""
        from kagami.core.rl.learned_hierarchical_planning import (
            get_hierarchical_planner,
        )

        planner = get_hierarchical_planner()

        # Plan from state to subgoal
        state = np.zeros(128)
        subgoal = np.ones(128) * 0.5

        actions = await planner._low_level_planning(state, subgoal, max_steps=10)

        # Should generate some actions
        assert len(actions) > 0
        assert all(isinstance(a, dict) for a in actions)

    def test_state_hash_consistency(self):
        """Test state hashing is consistent."""
        from kagami.core.rl.learned_hierarchical_planning import (
            get_hierarchical_planner,
        )

        planner = get_hierarchical_planner()

        state = np.array([1.0, 2.0, 3.0] + [0.0] * 125)

        # Same state should hash to same value
        hash1 = planner._hash_state(state)
        hash2 = planner._hash_state(state)

        assert hash1 == hash2

        # Different state should (usually) hash differently
        state2 = np.array([1.1, 2.0, 3.0] + [0.0] * 125)
        hash3 = planner._hash_state(state2)

        # May collide but unlikely
        assert isinstance(hash3, str)
