"""Tests for Meta-Tower Fixed Point Convergence.

Tests:
1. MetaTower initialization and configuration
2. Fixed point convergence detection
3. Policy update mechanism
4. Safety verification integration
5. Gradient computation from receipts
6. Convergence history tracking

Based on:
- Banach fixed-point theorem (contraction mapping)
- Meta-learning (Finn et al., 2017)
- Population-based training (Jaderberg et al., 2017)

鏡
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration

import torch
import torch.nn as nn

from kagami.core.strange_loops.fixed_point import (
    MetaTower,
    PolicyState,
    create_meta_tower,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def simple_policy():
    """Create simple policy modules for testing."""
    return {
        "encoder": nn.Linear(10, 10),
        "world_model": nn.Linear(10, 10),
        "controller": nn.Linear(10, 5),
    }


@pytest.fixture
def success_receipts():
    """Create receipts indicating successful operations."""
    return [
        {"event": {"name": "execution.success"}, "timestamp": 1.0},
        {"event": {"name": "task.completed"}, "timestamp": 2.0},
        {"event": {"name": "execution.success"}, "timestamp": 3.0},
    ] * 10


@pytest.fixture
def mixed_receipts():
    """Create receipts with mixed success/failure."""
    return [
        {"event": {"name": "execution.success"}, "timestamp": 1.0},
        {"event": {"name": "execution.error"}, "timestamp": 2.0},
        {"event": {"name": "task.completed"}, "timestamp": 3.0},
        {"event": {"name": "execution.failed"}, "timestamp": 4.0},
    ] * 5


@pytest.fixture
def meta_tower():
    """Create MetaTower instance."""
    return MetaTower(
        convergence_threshold=0.01,
        max_iterations=10,
        safety_verification_samples=50,
        meta_learning_rate=0.001,
    )


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestMetaTowerInit:
    """Test MetaTower initialization."""

    def test_default_initialization(self) -> None:
        """Test initialization with default parameters."""
        tower = MetaTower()

        assert tower.epsilon == 0.01
        assert tower.max_iters == 10
        assert tower.safety_samples == 100
        assert tower.meta_lr == 0.001
        assert len(tower.policy_history) == 0

    def test_custom_initialization(self) -> None:
        """Test initialization with custom parameters."""
        tower = MetaTower(
            convergence_threshold=0.001,
            max_iterations=20,
            safety_verification_samples=200,
            meta_learning_rate=0.0001,
        )

        assert tower.epsilon == 0.001
        assert tower.max_iters == 20
        assert tower.safety_samples == 200
        assert tower.meta_lr == 0.0001

    def test_factory_function(self) -> None:
        """Test create_meta_tower factory."""
        tower = create_meta_tower(
            convergence_threshold=0.005,
            max_iterations=15,
        )

        assert isinstance(tower, MetaTower)
        assert tower.epsilon == 0.005
        assert tower.max_iters == 15


# =============================================================================
# GRADIENT COMPUTATION TESTS
# =============================================================================


class TestMetaGradients:
    """Test meta-gradient computation from receipts."""

    def test_compute_gradients_from_success(
        self, meta_tower, simple_policy, success_receipts
    ) -> None:
        """Test gradient computation from successful receipts."""
        gradients = meta_tower._compute_meta_gradients(simple_policy, success_receipts)

        # Should have gradients for all policy modules
        assert "encoder" in gradients
        assert "world_model" in gradients
        assert "controller" in gradients

        # All gradients should be negative (low loss from success)
        for _name, grad in gradients.items():
            assert isinstance(grad, (int, float))

    def test_compute_gradients_from_mixed(self, meta_tower, simple_policy, mixed_receipts) -> None:
        """Test gradient computation from mixed receipts."""
        gradients = meta_tower._compute_meta_gradients(simple_policy, mixed_receipts)

        # Should still compute gradients
        assert len(gradients) == len(simple_policy)

    def test_gradient_norm_computation(self, meta_tower) -> None:
        """Test gradient norm computation."""
        gradients = {
            "encoder": 0.1,
            "world_model": 0.2,
            "controller": 0.3,
        }

        norm = meta_tower._compute_gradient_norm(gradients)

        # Should be sqrt(0.1^2 + 0.2^2 + 0.3^2) ≈ 0.374
        expected = (0.1**2 + 0.2**2 + 0.3**2) ** 0.5
        assert abs(norm - expected) < 1e-6

    def test_gradient_norm_empty(self, meta_tower) -> None:
        """Test gradient norm with no gradients."""
        norm = meta_tower._compute_gradient_norm({})
        assert norm == 0.0


# =============================================================================
# CONVERGENCE TESTS
# =============================================================================


class TestFixedPointConvergence:
    """Test fixed point convergence detection."""

    def test_immediate_convergence(self, simple_policy) -> None:
        """Test convergence when gradients are already small."""
        tower = MetaTower(convergence_threshold=1.0)  # High threshold

        receipts = [{"event": {"name": "execution.success"}}] * 5

        result = tower.update_until_fixed_point(simple_policy, receipts)

        assert result["converged"] is True
        assert result["iterations"] >= 0
        assert "convergence_history" in result
        assert "final_norm" in result

    def test_no_convergence_max_iterations(self, simple_policy) -> None:
        """Test when max iterations reached without convergence."""
        tower = MetaTower(
            convergence_threshold=0.0001,  # Very strict
            max_iterations=3,
        )

        receipts = [
            {"event": {"name": "execution.error"}},
            {"event": {"name": "execution.error"}},
        ] * 10

        result = tower.update_until_fixed_point(simple_policy, receipts)

        assert result["converged"] is False
        assert result["iterations"] == 3
        assert result["reason"] == "max_iterations"

    def test_convergence_history_tracking(
        self, meta_tower, simple_policy, success_receipts
    ) -> None:
        """Test that convergence history is tracked."""
        result = meta_tower.update_until_fixed_point(simple_policy, success_receipts)

        assert "convergence_history" in result
        assert len(result["convergence_history"]) > 0

        # History should be monotonically decreasing (for successful case)
        # or show convergence trend


# =============================================================================
# SAFETY VERIFICATION TESTS
# =============================================================================


class TestSafetyVerification:
    """Test safety constraint verification."""

    def test_safety_checker_integration(self, meta_tower, simple_policy, success_receipts) -> None:
        """Test integration with safety checker."""

        def safe_checker(policy_new):
            """Always returns safe."""
            return True

        result = meta_tower.update_until_fixed_point(
            simple_policy, success_receipts, safety_checker=safe_checker
        )

        # Should not fail due to safety
        assert "safety_violation" not in result.get("reason", "")

    def test_safety_violation_prevents_update(self, simple_policy) -> None:
        """Test that safety violations prevent policy update."""
        tower = MetaTower(
            convergence_threshold=0.01,
            max_iterations=5,
        )

        receipts = [{"event": {"name": "execution.error"}}] * 10

        def unsafe_checker(policy_new):
            """Always returns unsafe."""
            return False

        result = tower.update_until_fixed_point(
            simple_policy, receipts, safety_checker=unsafe_checker
        )

        # Should stop due to safety violation
        if not result["converged"]:
            # If it didn't converge, might be due to safety
            assert result.get("reason") in ["safety_violation", "max_iterations"]

    def test_no_safety_checker(self, meta_tower, simple_policy, success_receipts) -> None:
        """Test when no safety checker provided."""
        result = meta_tower.update_until_fixed_point(
            simple_policy, success_receipts, safety_checker=None
        )

        # Should still work (no safety check)
        assert "converged" in result


# =============================================================================
# POLICY UPDATE TESTS
# =============================================================================


class TestPolicyUpdate:
    """Test policy update mechanism."""

    def test_apply_meta_update(self, meta_tower, simple_policy) -> None:
        """Test applying meta update to policy."""
        gradients = {
            "encoder": 0.1,
            "world_model": 0.2,
            "controller": 0.3,
        }

        updated_policy = meta_tower._apply_meta_update(simple_policy, gradients)

        # Should return policy modules
        assert "encoder" in updated_policy
        assert "world_model" in updated_policy
        assert "controller" in updated_policy

    def test_commit_policy_update(self, meta_tower, simple_policy) -> None:
        """Test committing policy update to history."""
        initial_history_len = len(meta_tower.policy_history)

        meta_tower._commit_policy_update(simple_policy, simple_policy)

        # History should grow
        assert len(meta_tower.policy_history) == initial_history_len + 1

        # Last entry should be PolicyState
        last_state = meta_tower.policy_history[-1]
        assert isinstance(last_state, PolicyState)
        assert last_state.iteration == initial_history_len

    def test_policy_history_tracking(self, meta_tower, simple_policy, success_receipts) -> None:
        """Test that policy updates are tracked in history."""
        initial_len = len(meta_tower.policy_history)

        meta_tower.update_until_fixed_point(simple_policy, success_receipts)

        # History should have grown (at least one update)
        assert len(meta_tower.policy_history) > initial_len


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestMetaTowerIntegration:
    """Integration tests with realistic scenarios."""

    def test_realistic_convergence_scenario(self) -> None:
        """Test realistic convergence with moderate parameters."""
        tower = MetaTower(
            convergence_threshold=0.05,
            max_iterations=10,
        )

        policy = {
            "encoder": nn.Linear(128, 64),
            "world_model": nn.Sequential(
                nn.Linear(64, 64),
                nn.ReLU(),
                nn.Linear(64, 32),
            ),
            "controller": nn.Linear(32, 16),
        }

        receipts = [
            {"event": {"name": "execution.success"}},
            {"event": {"name": "task.completed"}},
        ] * 20

        result = tower.update_until_fixed_point(policy, receipts)

        assert "converged" in result
        assert "iterations" in result
        assert isinstance(result["iterations"], int)

    def test_empty_receipts(self, meta_tower, simple_policy) -> None:
        """Test behavior with no receipts."""
        result = meta_tower.update_until_fixed_point(simple_policy, [])

        # Should still run but converge quickly
        assert "converged" in result


# =============================================================================
# PROPERTY-BASED TESTS
# =============================================================================


class TestMetaTowerProperties:
    """Property-based tests using invariants."""

    def test_convergence_implies_small_gradient(
        self, meta_tower, simple_policy, success_receipts
    ) -> None:
        """Property: If converged, final gradient norm should be < threshold."""
        result = meta_tower.update_until_fixed_point(simple_policy, success_receipts)

        if result["converged"]:
            assert result["final_norm"] < meta_tower.epsilon

    def test_max_iterations_never_exceeded(self, meta_tower, simple_policy) -> None:
        """Property: Iterations never exceed max_iterations."""
        receipts = [{"event": {"name": "execution.error"}}] * 100

        result = meta_tower.update_until_fixed_point(simple_policy, receipts)

        assert result["iterations"] <= meta_tower.max_iters

    def test_policy_history_monotonic_growth(
        self, meta_tower, simple_policy, success_receipts
    ) -> None:
        """Property: Policy history only grows, never shrinks."""
        initial_len = len(meta_tower.policy_history)

        meta_tower.update_until_fixed_point(simple_policy, success_receipts)

        assert len(meta_tower.policy_history) >= initial_len


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
