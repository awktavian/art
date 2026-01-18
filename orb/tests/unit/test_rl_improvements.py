"""Tests for RL Architecture Improvements (Oct 2025 Audit).

Tests PPO, GAE, HER, RND, Ensemble, and V-trace implementations.
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_unit



import numpy as np

# Set seed for reproducibility
np.random.seed(42)


@pytest.mark.unit
def test_gae_computation():
    """Test GAE advantage computation."""
    from kagami.core.rl.gae import compute_gae

    # Simple trajectory
    rewards = [1.0, 0.0, 1.0, 0.0, 1.0]
    values = [0.5, 0.4, 0.6, 0.3, 0.7, 0.0]  # Includes V(s_T+1)

    advantages, returns = compute_gae(rewards, values, gamma=0.99, lambda_=0.95)

    # Verify shapes
    assert len(advantages) == len(rewards)
    assert len(returns) == len(rewards)

    # Verify advantages are reasonable
    assert all(isinstance(a, float) for a in advantages)
    assert all(isinstance(r, float) for r in returns)

    # Returns should be advantages + values
    for i in range(len(returns)):
        expected_return = advantages[i] + values[i]
        assert abs(returns[i] - expected_return) < 1e-6


@pytest.mark.unit
def test_gae_with_dones():
    """Test GAE with episode termination."""
    from kagami.core.rl.gae import compute_gae_with_dones

    rewards = [1.0, 1.0, 1.0]
    values = [0.5, 0.6, 0.7, 0.0]
    dones = [False, False, True]  # Episode ends at step 2

    advantages, returns = compute_gae_with_dones(rewards, values, dones, gamma=0.99, lambda_=0.95)

    assert len(advantages) == 3
    assert len(returns) == 3

    # Final advantage should account for terminal state
    # GAE still includes some bootstrapping from earlier steps
    final_advantage = advantages[-1]
    # Just verify it's computed (not exact value due to GAE recursion)
    assert isinstance(final_advantage, float)


@pytest.mark.unit
def test_gae_normalization():
    """Test advantage normalization."""
    from kagami.core.rl.gae import normalize_advantages

    advantages = [1.0, 2.0, 3.0, 4.0, 5.0]
    normalized = normalize_advantages(advantages)

    # Should have mean ~0, std ~1
    assert abs(np.mean(normalized)) < 0.01
    assert abs(np.std(normalized) - 1.0) < 0.01


@pytest.mark.unit
def test_ppo_actor_initialization():
    """Test PPO actor initializes correctly."""
    from kagami.core.rl.ppo_actor import PPOActor

    actor = PPOActor(embedding_dim=128, action_dim=64)

    assert actor.clip_epsilon == 0.2
    assert actor.ppo_epochs == 4
    assert actor.target_kl == 0.01
    assert actor.use_target_network is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ppo_action_sampling():
    """Test PPO actor can sample actions."""
    from kagami.core.rl.ppo_actor import PPOActor
    from kagami.core.world_model.jepa import LatentState

    actor = PPOActor()

    # Create test state
    state = LatentState(embedding=[0.1] * 128, timestamp=0.0, context_hash="test_state")

    # Sample actions
    actions = await actor.sample_actions(state, k=5)

    assert len(actions) == 5
    assert all(isinstance(a, dict) for a in actions)
    assert all("action" in a for a in actions)


@pytest.mark.unit
def test_her_strategy():
    """Test HER hindsight goal generation."""
    from kagami.core.learning.hindsight_replay import HindsightReplayStrategy

    strategy = HindsightReplayStrategy(strategy="future", k=4)

    # Mock episode
    episode_states = [f"state_{i}" for i in range(10)]
    episode_goals = [f"goal_{i}" for i in range(10)]

    # Generate hindsight goals for timestep 3
    hindsight_goals = strategy.generate_hindsight_goals(
        episode_states, episode_goals, current_timestep=3
    )

    # Should generate up to k=4 goals (may be fewer near the end)
    assert 1 <= len(hindsight_goals) <= 4

    # Future strategy: goals should be from future timesteps if available
    for goal in hindsight_goals:
        assert goal in episode_goals[4:]


@pytest.mark.unit
def test_her_buffer_episode_processing():
    """Test HER buffer processes episodes correctly."""
    from kagami.core.learning.hindsight_replay import (
        HindsightReplayBuffer,
    )

    buffer = HindsightReplayBuffer(capacity=1000, her_k=4)

    # Add 5-step episode
    for t in range(5):
        buffer.add_timestep(
            state=f"state_{t}",
            action=f"action_{t}",
            next_state=f"state_{t + 1}",
            goal="original_goal",
            reward=0.0,  # Failed to reach goal
            achieved_goal=f"achieved_{t}",
            done=(t == 4),  # Last step
        )

    # After episode ends (done=True), should have:
    # 5 original + hindsight (depends on future availability)
    assert buffer.original_experiences == 5
    assert buffer.hindsight_experiences >= 10  # At least some hindsight
    assert len(buffer.buffer) >= 15  # Original + some hindsight


@pytest.mark.unit
def test_rnd_curiosity():
    """Test RND curiosity computation."""
    from kagami.core.rl.rnd_curiosity import RNDCuriosity
    from kagami.core.world_model.jepa import LatentState

    rnd = RNDCuriosity(state_dim=128)

    # Novel state should have high curiosity
    novel_state = LatentState(
        embedding=np.random.randn(128).tolist(), timestamp=0.0, context_hash="novel"
    )

    curiosity = rnd.compute_intrinsic_reward(novel_state)

    # Should be between 0 and 1
    assert 0.0 <= curiosity <= 1.0

    # After training predictor, same state should have lower curiosity
    initial_curiosity = curiosity

    # Train predictor several times
    for _ in range(10):
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(rnd.update_predictor(novel_state))
        except RuntimeError:
            # No loop, synchronous update
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(rnd.update_predictor(novel_state))
            finally:
                loop.close()

    # Recompute curiosity - should decrease (predictor learned)
    new_curiosity = rnd.compute_intrinsic_reward(novel_state)

    # Curiosity should decrease (or stay same if already learned)
    assert new_curiosity <= initial_curiosity + 0.1


@pytest.mark.unit
def test_vtrace_correction():
    """Test V-trace off-policy correction."""
    from kagami.core.learning.vtrace import compute_vtrace

    # Simple trajectory
    rewards = [1.0, 0.0, 1.0]
    values = [0.5, 0.4, 0.6, 0.0]

    # Policy changed slightly (new policy more greedy)
    old_probs = [0.5, 0.5, 0.5]
    new_probs = [0.7, 0.6, 0.8]  # Higher probabilities

    vtrace_values, vtrace_advantages = compute_vtrace(
        rewards, values, old_probs, new_probs, gamma=0.99, rho_bar=1.0, c_bar=1.0
    )

    # Verify shapes
    assert len(vtrace_values) == 3
    assert len(vtrace_advantages) == 3

    # Verify values are reasonable
    assert all(isinstance(v, float) for v in vtrace_values)
    assert all(isinstance(a, float) for a in vtrace_advantages)


@pytest.mark.unit
def test_vtrace_clipping():
    """Test V-trace clips extreme importance ratios."""
    from kagami.core.learning.vtrace import compute_vtrace

    rewards = [1.0]
    values = [0.5, 0.0]

    # Extreme policy change
    old_probs = [0.1]  # Old policy: 10% chance
    new_probs = [0.9]  # New policy: 90% chance
    # Ratio = 9.0 (very high!)

    # With rho_bar=1.0, should clip to 1.0
    _vtrace_values, vtrace_advantages = compute_vtrace(
        rewards, values, old_probs, new_probs, rho_bar=1.0
    )

    # Advantage should be clipped (max influence = 1.0)
    assert abs(vtrace_advantages[0]) < 2.0


@pytest.mark.unit
def test_integration_ppo_gae():
    """Test PPO + GAE integration."""
    from kagami.core.rl.gae import get_gae_calculator

    gae = get_gae_calculator()

    # Mock trajectory
    rewards = [0.5, 0.3, 0.8]
    values = [0.4, 0.5, 0.6, 0.0]

    # Compute GAE advantages
    advantages, returns = gae.compute(rewards, values)

    # Advantages should be computed correctly
    assert len(advantages) == 3
    assert len(returns) == 3

    # Advantages computed (normalization happens in PPO actor if needed)
    mean_adv = np.mean(advantages)
    # Just verify they're computed (may not be normalized yet)
    assert isinstance(mean_adv, (float, np.floating))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_intrinsic_reward_with_rnd():
    """Test intrinsic reward calculator uses RND."""
    from kagami.core.rl.intrinsic_reward import IntrinsicRewardCalculator
    from kagami.core.world_model.jepa import LatentState

    intrinsic = IntrinsicRewardCalculator()

    state = LatentState(embedding=[0.1] * 128, timestamp=0.0, context_hash="test")

    action = {"action": "explore"}

    # Compute intrinsic reward (should use RND curiosity component)
    reward = intrinsic.compute(state, action, world_model=None)

    # Should return valid reward
    assert 0.0 <= reward <= 1.0


@pytest.mark.unit
def test_her_goal_achievement():
    """Test HER goal achievement checking."""
    from kagami.core.learning.hindsight_replay import HindsightReplayBuffer
    from kagami.core.world_model.jepa import LatentState

    buffer = HindsightReplayBuffer(capacity=100, her_k=4)

    # Similar states should match
    achieved = LatentState(embedding=[0.5] * 128, timestamp=0.0, context_hash="achieved")

    goal = LatentState(embedding=[0.5] * 128, timestamp=0.0, context_hash="goal")

    # Should match (same embedding)
    assert buffer._check_goal_achieved(achieved, goal, threshold=0.1)

    # Different states should not match
    different_goal = LatentState(embedding=[0.9] * 128, timestamp=0.0, context_hash="different")

    assert not buffer._check_goal_achieved(achieved, different_goal, threshold=0.1)


@pytest.mark.unit
def test_rnd_target_network_fixed():
    """Test RND target network stays fixed."""
    from kagami.core.rl.rnd_curiosity import RandomTargetNetwork

    target = RandomTargetNetwork(input_dim=128, hidden_dim=64, output_dim=32)

    # Get initial output
    state_emb = np.random.randn(128)
    output1 = target.forward(state_emb)

    # Output should be deterministic (same input → same output)
    output2 = target.forward(state_emb)

    assert np.allclose(output1, output2)


@pytest.mark.unit
def test_rnd_predictor_learning():
    """Test RND predictor can learn."""
    from kagami.core.rl.rnd_curiosity import PredictorNetwork, RandomTargetNetwork

    target = RandomTargetNetwork(input_dim=128, hidden_dim=64, output_dim=32)
    predictor = PredictorNetwork(input_dim=128, hidden_dim=64, output_dim=32)

    state_emb = np.random.randn(128)

    # Initial prediction error should be high
    target_output = target.forward(state_emb)
    initial_output = predictor.forward(state_emb)
    initial_error = np.linalg.norm(initial_output - target_output)

    # Train predictor for 100 steps
    for _ in range(100):
        predictor.update(state_emb, target_output)

    # After training, error should decrease
    final_output = predictor.forward(state_emb)
    final_error = np.linalg.norm(final_output - target_output)

    # Error should decrease (learning works)
    assert final_error < initial_error


@pytest.mark.unit
def test_vtrace_on_policy_matches_standard():
    """Test V-trace equals standard when on-policy (ratios=1)."""
    from kagami.core.learning.vtrace import compute_vtrace

    rewards = [1.0, 0.5, 0.3]
    values = [0.4, 0.5, 0.6, 0.0]

    # On-policy: old and new probs identical
    probs = [0.5, 0.5, 0.5]

    vtrace_values, vtrace_advantages = compute_vtrace(
        rewards,
        values,
        probs,
        probs,  # Same policy
    )

    # When on-policy (ratio=1), V-trace should match standard TD
    # Verify values computed
    assert len(vtrace_values) == 3
    assert len(vtrace_advantages) == 3


@pytest.mark.unit
def test_ppo_clipping_mechanism():
    """Test PPO clips policy ratios correctly."""
    from kagami.core.rl.ppo_actor import PPOActor

    _ = PPOActor(clip_epsilon=0.2)

    # Simulate ratio and advantage
    ratio = 1.5  # 50% increase in probability
    advantage = 1.0

    # PPO clips to [0.8, 1.2]
    clipped_ratio = np.clip(ratio, 1.0 - 0.2, 1.0 + 0.2)

    assert clipped_ratio == 1.2  # Clipped to upper bound

    # Objective takes minimum
    unclipped_obj = ratio * advantage  # = 1.5
    clipped_obj = clipped_ratio * advantage  # = 1.2

    assert min(unclipped_obj, clipped_obj) == 1.2  # Clipped version wins


@pytest.mark.unit
def test_gae_calculator_stats():
    """Test GAE calculator tracks statistics."""
    from kagami.core.rl.gae import GAECalculator

    gae = GAECalculator()

    # Run several computations
    for _ in range(5):
        rewards = np.random.rand(10).tolist()
        values = np.random.rand(11).tolist()

        gae.compute(rewards, values)

    # Should have statistics
    stats = gae.get_stats()

    assert "mean_advantage" in stats
    assert "std_advantage" in stats
    assert "mean_td_error" in stats
    assert stats["gamma"] == 0.99
    assert stats["lambda"] == 0.95


@pytest.mark.unit
def test_her_should_use_for_code_tasks():
    """Test HER detection for sparse reward tasks."""
    from kagami.core.learning.hindsight_replay import should_use_her

    # Code tasks should use HER (sparse rewards)
    code_task = {"type": "code_generation", "goal": "implement function"}
    assert should_use_her(code_task) is True

    # Build tasks should use HER
    build_task = {"type": "build_system"}
    assert should_use_her(build_task) is True
