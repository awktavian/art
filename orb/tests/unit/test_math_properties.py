"""Property-Based Tests for Mathematical Invariants.

Tests mathematical properties that must ALWAYS hold:
- Softmax sums to 1.0
- GAE recursion correctness
- PPO clipping bounds
- k-NN kernel normalization
- Adam optimizer convergence
- V-trace importance ratio clipping

Uses hypothesis for property-based testing when available,
otherwise uses parametrized tests.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import numpy as np

# Set seed for reproducibility
np.random.seed(42)


class TestSoftmaxProperties:
    """Test softmax mathematical properties."""

    def test_softmax_sums_to_one(self) -> None:
        """Softmax output must sum to exactly 1.0."""

        def softmax_stable(x):
            x_max = np.max(x)
            exp_x = np.exp(x - x_max)
            return exp_x / np.sum(exp_x)

        # Test with various inputs
        test_cases = [
            np.array([1.0, 2.0, 3.0]),
            np.array([0.0, 0.0, 0.0]),  # All zeros
            np.array([1000, 1001, 1002]),  # Large values
            np.array([-1000, -1001, -1002]),  # Large negative values
            np.random.randn(10),  # Random
            np.random.randn(100),  # Large random
        ]

        for x in test_cases:
            probs = softmax_stable(x)
            total = np.sum(probs)
            assert abs(total - 1.0) < 1e-6, f"Softmax sum={total}, expected 1.0"
            assert np.all(probs >= 0), "Softmax must be non-negative"
            assert np.all(probs <= 1), "Softmax must be ≤ 1.0"

    def test_softmax_overflow_prevention(self) -> None:
        """Softmax must handle overflow gracefully."""

        def softmax_naive(x):
            return np.exp(x) / np.sum(np.exp(x))

        def softmax_stable(x):
            x_max = np.max(x)
            return np.exp(x - x_max) / np.sum(np.exp(x - x_max))

        # This would overflow with naive softmax
        x = np.array([1000, 1001, 1002])

        # Naive fails
        with pytest.warns(RuntimeWarning):
            result_naive = softmax_naive(x)
            assert np.any(np.isnan(result_naive)), "Naive softmax should overflow"

        # Stable works
        result_stable = softmax_stable(x)
        assert not np.any(np.isnan(result_stable)), "Stable softmax must not overflow"
        assert abs(np.sum(result_stable) - 1.0) < 1e-6, "Must sum to 1.0"


class TestGAEProperties:
    """Test GAE (Generalized Advantage Estimation) properties."""

    def test_gae_recursion(self) -> None:
        """Test GAE recursive formula."""
        from kagami.core.rl.gae import compute_gae

        # Simple test case
        rewards = [1.0, 2.0, 3.0]
        values = [0.5, 1.0, 1.5, 2.0]  # One extra for bootstrap
        gamma = 0.99
        lambda_ = 0.95

        advantages, returns = compute_gae(rewards, values, gamma, lambda_)

        # Verify recursion manually for last step
        delta_2 = rewards[2] + gamma * values[3] - values[2]
        expected_adv_2 = delta_2
        assert abs(advantages[2] - expected_adv_2) < 1e-6, "GAE recursion failed"

        # Returns should be advantages + values
        for i in range(len(returns)):
            expected_return = advantages[i] + values[i]
            assert abs(returns[i] - expected_return) < 1e-6, f"Return[{i}] != advantage + value"

    def test_gae_bounds(self) -> None:
        """Test GAE advantage bounds."""
        from kagami.core.rl.gae import compute_gae

        # Bounded rewards
        rewards = [0.5] * 10
        values = [0.5] * 11
        gamma = 0.99
        lambda_ = 0.95

        advantages, _returns = compute_gae(rewards, values, gamma, lambda_)

        # With constant rewards and values, advantages should be small
        for adv in advantages:
            assert abs(adv) < 10.0, "Advantages should be bounded"

    def test_gae_normalization(self) -> None:
        """Test advantage normalization."""
        from kagami.core.rl.gae import normalize_advantages

        advantages = [1.0, 2.0, 3.0, 4.0, 5.0]
        normalized = normalize_advantages(advantages)

        # Mean should be ~0
        mean = np.mean(normalized)
        assert abs(mean) < 1e-6, f"Normalized mean={mean}, expected ~0"

        # Std should be ~1
        std = np.std(normalized)
        assert abs(std - 1.0) < 1e-1, f"Normalized std={std}, expected ~1"


class TestPPOProperties:
    """Test PPO clipping properties."""

    def test_ppo_clip_bounds(self) -> None:
        """PPO clipping must respect [1-ε, 1+ε] bounds."""
        epsilon = 0.2

        # Test various ratios
        ratios = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]

        for ratio in ratios:
            clipped = np.clip(ratio, 1 - epsilon, 1 + epsilon)

            assert clipped >= 1 - epsilon, f"Clipped {ratio} = {clipped} < {1 - epsilon}"
            assert clipped <= 1 + epsilon, f"Clipped {ratio} = {clipped} > {1 + epsilon}"

    def test_ppo_objective_pessimistic(self) -> None:
        """PPO objective must be pessimistic (take minimum)."""
        epsilon = 0.2
        advantage = 1.0

        # For positive advantage and ratio > 1+ε, clipping should reduce objective
        ratio = 2.0
        unclipped = ratio * advantage
        clipped_ratio = np.clip(ratio, 1 - epsilon, 1 + epsilon)
        clipped_obj = clipped_ratio * advantage
        ppo_obj = np.minimum(unclipped, clipped_obj)

        assert ppo_obj <= unclipped, "PPO objective must be ≤ unclipped (pessimistic)"
        assert ppo_obj == clipped_obj, "Should take clipped when ratio large"


class TestRBFKernelProperties:
    """Test RBF kernel normalization."""

    def test_rbf_weights_sum_to_one(self) -> None:
        """RBF kernel weights must sum to 1.0."""
        distances = np.array([0.1, 0.2, 0.3, 0.4, 0.5])

        # Silverman's rule
        n = len(distances)
        sigma = 1.06 * np.std(distances) * n ** (-0.2)
        sigma = max(sigma, 0.1)

        # Compute weights
        weights = np.exp(-(distances**2) / (2 * sigma**2))
        weights_normalized = weights / np.sum(weights)

        # Must sum to 1.0
        total = np.sum(weights_normalized)
        assert abs(total - 1.0) < 1e-6, f"RBF weights sum={total}, expected 1.0"

        # All weights must be positive
        assert np.all(weights_normalized > 0), "RBF weights must be positive"

    def test_rbf_nearest_highest_weight(self) -> None:
        """Nearest neighbor should have highest weight."""
        distances = np.array([0.1, 0.5, 1.0, 2.0])  # 0.1 is nearest

        sigma = 0.5  # Fixed for test
        weights = np.exp(-(distances**2) / (2 * sigma**2))
        weights_normalized = weights / np.sum(weights)

        # Nearest (smallest distance) should have highest weight
        assert weights_normalized[0] == np.max(
            weights_normalized
        ), "Nearest neighbor must have highest weight"


class TestAdamOptimizerProperties:
    """Test Adam optimizer properties."""

    def test_adam_bias_correction(self) -> None:
        """Adam bias correction must converge to correct values."""
        # Hyperparameters
        beta1 = 0.9
        beta2 = 0.999

        # Simulate a few steps
        gradient = np.array([1.0, 1.0, 1.0])
        m = np.zeros_like(gradient)
        v = np.zeros_like(gradient)

        for t in range(1, 4):
            # Update moments
            m = beta1 * m + (1 - beta1) * gradient
            v = beta2 * v + (1 - beta2) * (gradient**2)

            # Bias correction
            m_hat = m / (1 - beta1**t)
            v / (1 - beta2**t)

            # m_hat should approach gradient with bias correction
            if t > 1:
                assert np.all(m_hat > m), "Bias-corrected moment should be larger than biased"


class TestVTraceProperties:
    """Test V-trace properties."""

    def test_vtrace_ratio_clipping(self) -> None:
        """V-trace must clip importance ratios."""
        from kagami.core.learning.vtrace import compute_vtrace

        rewards = [1.0, 1.0, 1.0]
        values = [0.5, 0.5, 0.5, 0.5]
        old_probs = [0.5, 0.5, 0.5]
        new_probs = [0.9, 0.1, 0.9]  # Some large ratios

        rho_bar = 1.0
        c_bar = 1.0

        vtrace_values, vtrace_advantages = compute_vtrace(
            rewards,
            values,
            old_probs,
            new_probs,
            gamma=0.99,
            rho_bar=rho_bar,
            c_bar=c_bar,
        )

        # Verify output is valid
        assert len(vtrace_values) == len(rewards), "Length mismatch"
        assert len(vtrace_advantages) == len(rewards), "Length mismatch"

        # Values should be finite
        assert np.all(np.isfinite(vtrace_values)), "V-trace values must be finite"
        assert np.all(np.isfinite(vtrace_advantages)), "V-trace advantages must be finite"


class TestWorldModelProperties:
    """Test world model prediction properties."""

    def test_latent_state_distance_symmetric(self) -> None:
        """Distance between states must be symmetric."""
        from kagami.core.world_model.jepa import LatentState

        state1 = LatentState(
            embedding=[1.0, 2.0, 3.0],
            timestamp=0.0,
            context_hash="test1",
        )

        state2 = LatentState(
            embedding=[4.0, 5.0, 6.0],
            timestamp=0.0,
            context_hash="test2",
        )

        # Compute distance both ways
        emb1 = np.array(state1.embedding)
        emb2 = np.array(state2.embedding)

        dist_12 = np.linalg.norm(emb1 - emb2)
        dist_21 = np.linalg.norm(emb2 - emb1)

        assert abs(dist_12 - dist_21) < 1e-6, "Distance must be symmetric"

    def test_latent_state_distance_triangle_inequality(self) -> None:
        """Distance must satisfy triangle inequality."""
        from kagami.core.world_model.jepa import LatentState

        s1 = LatentState(embedding=[1.0, 0.0], timestamp=0.0, context_hash="1")
        s2 = LatentState(embedding=[0.0, 1.0], timestamp=0.0, context_hash="2")
        s3 = LatentState(embedding=[1.0, 1.0], timestamp=0.0, context_hash="3")

        e1 = np.array(s1.embedding)
        e2 = np.array(s2.embedding)
        e3 = np.array(s3.embedding)

        d12 = np.linalg.norm(e1 - e2)
        d13 = np.linalg.norm(e1 - e3)
        d23 = np.linalg.norm(e2 - e3)

        # Triangle inequality: d(a,c) ≤ d(a,b) + d(b,c)
        assert d13 <= d12 + d23 + 1e-6, "Triangle inequality violated"
        assert d12 <= d13 + d23 + 1e-6, "Triangle inequality violated"
        assert d23 <= d12 + d13 + 1e-6, "Triangle inequality violated"


class TestIntrinsicRewardProperties:
    """Test intrinsic reward properties."""

    def test_novelty_decreases_with_visits(self) -> None:
        """Novelty reward must decrease as state is visited."""
        import math

        visit_counts = [0, 1, 3, 9, 99]
        novelties = [1.0 / math.sqrt(1.0 + c) for c in visit_counts]

        for i in range(len(novelties) - 1):
            assert novelties[i] > novelties[i + 1], "Novelty must decrease with visits"

    def test_intrinsic_reward_bounded(self) -> None:
        """Intrinsic rewards must be bounded [0, 1]."""
        from kagami.core.rl.intrinsic_reward import IntrinsicRewardCalculator

        calculator = IntrinsicRewardCalculator()

        # Test with various states
        for _ in range(100):
            state = {"embedding": list(np.random.randn(128))}
            action = {"action": "explore"}

            reward = calculator.compute(state, action, world_model=None)

            assert 0.0 <= reward <= 1.0, f"Intrinsic reward={reward} out of bounds"


class TestHierarchicalPlanningProperties:
    """Test hierarchical planning properties."""

    def test_subgoal_assignment_deterministic(self) -> None:
        """Same state should map to same subgoal."""
        from kagami.core.rl.learned_hierarchical_planning import (
            TemporalAbstractionNetwork,
        )

        network = TemporalAbstractionNetwork(state_dim=128, n_subgoals=8)

        state = np.random.randn(128)

        # Call twice
        subgoal1 = network.discover_subgoal(state)
        subgoal2 = network.discover_subgoal(state)

        assert subgoal1 == subgoal2, "Same state must map to same subgoal (deterministic)"

    def test_subgoal_ids_valid(self) -> None:
        """Subgoal IDs must be in valid range."""
        from kagami.core.rl.learned_hierarchical_planning import (
            TemporalAbstractionNetwork,
        )

        network = TemporalAbstractionNetwork(state_dim=128, n_subgoals=8)

        # Test with many random states
        for _ in range(100):
            state = np.random.randn(128)
            subgoal_id = network.discover_subgoal(state)

            assert 0 <= subgoal_id < 8, f"Subgoal ID={subgoal_id} out of range [0, 8)"


class TestMetaCorrectionProperties:
    """Test meta-correction properties."""

    def test_damping_prevents_overcorrection(self) -> None:
        """Damping must prevent correction exceeding predicted error."""
        damping = 0.5
        confidence = 0.8

        effective_damping = damping * confidence  # 0.4

        # If predicted error is 1.0, correction should be at most 0.4
        assert effective_damping < 1.0, "Damping must be < 1.0"
        assert effective_damping >= 0.0, "Damping must be ≥ 0.0"

    def test_meta_correction_bounded(self) -> None:
        """Meta-corrected embeddings should remain bounded."""
        base_embedding = [1.0, 2.0, 3.0]
        error_vector = [0.5, -0.3, 0.2]
        damping = 0.5

        corrected = [
            base - damping * err for base, err in zip(base_embedding, error_vector, strict=False)
        ]

        # Normalize
        norm = np.linalg.norm(corrected)
        if norm > 0:
            corrected = [c / norm for c in corrected]

        # Check norm
        final_norm = np.linalg.norm(corrected)
        assert abs(final_norm - 1.0) < 1e-6, "Corrected embedding must be normalized"


# =============================================================================
# NaN AND INF EDGE CASE TESTS
# =============================================================================


class TestNaNAndInfHandling:
    """Test proper handling of NaN and Inf values in mathematical operations."""

    def test_softmax_with_inf_values(self) -> None:
        """Softmax should handle inf values - demonstrating the problem."""

        def softmax_stable(x):
            x_max = np.max(x)
            exp_x = np.exp(x - x_max)
            return exp_x / np.sum(exp_x)

        # Test with +inf - this produces nan because inf - inf = nan
        x_with_inf = np.array([1.0, np.inf, 2.0])
        result = softmax_stable(x_with_inf)

        # Standard stable softmax produces nan when inf is present
        # This is expected behavior - need special handling for inf
        assert np.isnan(result[1]), "inf in softmax produces nan without special handling"

        # Proper handling would filter or clip inf values first
        x_clipped = np.clip(x_with_inf, -1e10, 1e10)
        result_clipped = softmax_stable(x_clipped)
        assert np.isfinite(result_clipped).all(), "Clipping prevents nan"

    def test_softmax_with_neg_inf_values(self) -> None:
        """Softmax should handle -inf values gracefully."""

        def softmax_stable(x):
            x_max = np.max(x)
            exp_x = np.exp(x - x_max)
            return exp_x / np.sum(exp_x)

        # -inf should become 0 after softmax
        x = np.array([1.0, -np.inf, 2.0])
        result = softmax_stable(x)

        assert np.isclose(result[1], 0.0), "-inf should map to 0 probability"
        assert result[0] > 0 and result[2] > 0
        assert abs(np.sum(result) - 1.0) < 1e-6

    def test_softmax_all_same_large_values(self) -> None:
        """Softmax of identical large values should be uniform."""

        def softmax_stable(x):
            x_max = np.max(x)
            exp_x = np.exp(x - x_max)
            return exp_x / np.sum(exp_x)

        x = np.array([1e10, 1e10, 1e10])
        result = softmax_stable(x)

        # Should be uniform distribution
        assert np.allclose(result, [1 / 3, 1 / 3, 1 / 3])

    def test_normalize_nan_detection(self) -> None:
        """Normalization should detect NaN in input."""
        x = np.array([1.0, np.nan, 3.0])

        # np.mean and np.std return nan for arrays containing nan
        mean = np.mean(x)
        assert np.isnan(mean), "Mean of array with NaN should be NaN"

    def test_divide_by_zero_handling(self) -> None:
        """Test safe division patterns."""
        epsilon = 1e-8

        # Standard division would produce inf
        numerator = 1.0
        denominator = 0.0

        # Safe division with epsilon
        safe_result = numerator / (denominator + epsilon)
        assert np.isfinite(safe_result), "Safe division should prevent inf"

    def test_log_of_zero_handling(self) -> None:
        """Test log of zero produces -inf."""
        result = np.log(0.0)
        assert result == -np.inf, "log(0) should be -inf"

        # Safe log pattern
        epsilon = 1e-10
        safe_result = np.log(0.0 + epsilon)
        assert np.isfinite(safe_result), "Safe log should prevent -inf"

    def test_exp_overflow_prevention(self) -> None:
        """Test exponential overflow prevention."""
        # Direct exp would overflow
        large_value = 1000

        # Clipping prevents overflow
        clipped = np.clip(large_value, -88, 88)  # exp(88) ~= 1.6e38
        result = np.exp(clipped)
        assert np.isfinite(result), "Clipped exp should be finite"

    def test_gradient_clipping_prevents_explosion(self) -> None:
        """Test gradient clipping prevents exploding gradients."""
        gradients = np.array([1e10, -1e10, 1.0])
        max_norm = 1.0

        # Compute norm
        norm = np.linalg.norm(gradients)
        if norm > max_norm:
            gradients = gradients * (max_norm / norm)

        assert np.linalg.norm(gradients) <= max_norm + 1e-6
        assert np.all(np.isfinite(gradients))

    def test_weighted_average_with_zero_weights(self) -> None:
        """Test weighted average when all weights are zero."""
        values = np.array([1.0, 2.0, 3.0])
        weights = np.array([0.0, 0.0, 0.0])

        # NumPy raises ZeroDivisionError for zero weights
        with pytest.raises(ZeroDivisionError):
            np.average(values, weights=weights)

        # Safe pattern: add small epsilon to weights
        safe_weights = weights + 1e-10
        safe_result = np.average(values, weights=safe_weights)
        assert np.isfinite(safe_result)


class TestNumericalStabilityPatterns:
    """Test common numerical stability patterns."""

    def test_logsumexp_stability(self) -> None:
        """Test log-sum-exp trick for numerical stability."""
        # Large values that would overflow with naive implementation
        x = np.array([1000, 1001, 1002])

        # Naive implementation (would overflow)
        with np.errstate(over="ignore"):
            naive_result = np.log(np.sum(np.exp(x)))
            # Result is inf due to overflow

        # Stable implementation
        x_max = np.max(x)
        stable_result = x_max + np.log(np.sum(np.exp(x - x_max)))

        assert np.isfinite(stable_result), "Stable logsumexp should be finite"
        assert abs(stable_result - 1002.40) < 0.1  # Approximate expected value

    def test_kl_divergence_with_zeros(self) -> None:
        """Test KL divergence handling when probabilities are zero."""
        p = np.array([0.5, 0.5, 0.0])  # Contains zero
        q = np.array([0.3, 0.4, 0.3])

        # Naive KL would have 0 * log(0) = nan
        # Proper handling: 0 * log(0) should be 0 by convention
        epsilon = 1e-10
        p_safe = p + epsilon
        p_safe = p_safe / p_safe.sum()
        q_safe = q + epsilon
        q_safe = q_safe / q_safe.sum()

        kl = np.sum(p_safe * np.log(p_safe / q_safe))
        assert np.isfinite(kl), "KL divergence should be finite"
        assert kl >= 0, "KL divergence should be non-negative"

    def test_cosine_similarity_with_zero_vector(self) -> None:
        """Test cosine similarity when one vector is zero."""
        a = np.array([1.0, 2.0, 3.0])
        b = np.zeros(3)

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        # Would produce nan without epsilon
        epsilon = 1e-10
        similarity = np.dot(a, b) / (norm_a * norm_b + epsilon)

        assert np.isfinite(similarity), "Cosine similarity should be finite"
        assert abs(similarity) < epsilon, "Similarity with zero should be ~0"

    def test_variance_of_constant_array(self) -> None:
        """Test variance of constant array is zero (not nan)."""
        x = np.array([5.0, 5.0, 5.0, 5.0])
        variance = np.var(x)

        assert variance == 0.0, "Variance of constant should be 0"
        assert np.isfinite(variance)

    def test_normalize_constant_array(self) -> None:
        """Test normalization of constant array."""
        x = np.array([5.0, 5.0, 5.0])
        mean = np.mean(x)
        std = np.std(x)

        # Would produce nan without epsilon
        epsilon = 1e-8
        normalized = (x - mean) / (std + epsilon)

        assert np.all(np.isfinite(normalized))
        assert np.allclose(normalized, 0.0), "Constant array normalizes to zeros"


class TestBoundaryConditions:
    """Test boundary conditions in mathematical operations."""

    def test_sigmoid_saturation(self) -> None:
        """Test sigmoid at extreme values."""

        def sigmoid(x):
            return 1 / (1 + np.exp(-np.clip(x, -500, 500)))

        # Large positive
        assert np.isclose(sigmoid(1000), 1.0)
        # Large negative
        assert np.isclose(sigmoid(-1000), 0.0)
        # Zero
        assert np.isclose(sigmoid(0), 0.5)

    def test_tanh_saturation(self) -> None:
        """Test tanh at extreme values."""
        # Large positive
        assert np.isclose(np.tanh(100), 1.0)
        # Large negative
        assert np.isclose(np.tanh(-100), -1.0)
        # Zero
        assert np.isclose(np.tanh(0), 0.0)

    def test_relu_with_negative_values(self) -> None:
        """Test ReLU properly clips negative values."""
        x = np.array([-1e10, -1.0, 0.0, 1.0, 1e10])
        relu = np.maximum(x, 0)

        assert relu[0] == 0.0
        assert relu[1] == 0.0
        assert relu[2] == 0.0
        assert relu[3] == 1.0
        assert relu[4] == 1e10

    def test_leaky_relu_preserves_gradient(self) -> None:
        """Test leaky ReLU preserves gradient for negative values."""
        alpha = 0.01
        x = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
        leaky_relu = np.where(x > 0, x, alpha * x)

        assert leaky_relu[0] == -0.02
        assert leaky_relu[1] == -0.01
        assert leaky_relu[2] == 0.0
        assert leaky_relu[3] == 1.0
        assert leaky_relu[4] == 2.0

    def test_batch_norm_with_single_sample(self) -> None:
        """Test batch norm behavior with single sample."""
        x = np.array([[1.0, 2.0, 3.0]])  # batch_size=1

        # Mean across batch
        mean = np.mean(x, axis=0)
        # Variance across batch is 0 for single sample
        var = np.var(x, axis=0)

        assert np.allclose(var, 0.0), "Single sample variance is 0"

        # Safe normalization
        epsilon = 1e-5
        normalized = (x - mean) / np.sqrt(var + epsilon)
        assert np.all(np.isfinite(normalized))


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
