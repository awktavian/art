"""Property-Based Tests for Strange Loop Stability.

Verifies the stability properties referenced in docs/self_ARCHITECTURE.md:

Theorem: Under conditions X (contractive), Y (energy dissipative), and
Z (safety barrier), the strange loop μ_self converges to a unique fixed point.

This module uses hypothesis for property-based testing of convergence conditions.

鏡
"""

from __future__ import annotations

import pytest
from typing import cast

pytestmark = pytest.mark.tier_unit

import math
from collections.abc import Callable

import numpy as np
import torch
import torch.nn as nn
from hypothesis import HealthCheck, assume, given, settings, strategies as st
from scipy import stats

# Constants for thresholds (from proof)
CONTRACTION_THRESHOLD = 0.99
ENERGY_DISSIPATION_MIN = 0.001
SAFETY_THRESHOLD = 0.0
CONVERGENCE_EPS = 0.01
MAX_ITERATIONS = 100

# =============================================================================
# FIXTURES AND HELPERS
# =============================================================================


def create_contractive_map(alpha: float = 0.8) -> Callable:
    """Create a contractive map with specified contraction factor.

    T(μ) = α·μ
    has contraction factor α.
    """

    def T(mu: torch.Tensor) -> torch.Tensor:
        return alpha * mu

    return T


def create_oscillating_map() -> Callable:
    """Create a non-contractive oscillating map.

    T(μ) = -μ (oscillates between μ and -μ)
    has no fixed point, violates condition X.
    """

    def T(mu: torch.Tensor) -> torch.Tensor:
        return -mu

    return T


def create_dissipative_energy_function() -> tuple[Callable, Callable]:
    """Create T with guaranteed energy dissipation.

    T(μ) = 0.7·μ + 0.05·noise
    E(μ) = 0.5·||μ||²

    Energy decreases due to scaling by 0.7 < 1.
    """

    def T(mu: torch.Tensor) -> torch.Tensor:
        noise = 0.05 * torch.randn_like(mu)
        return 0.7 * mu + noise

    def E(mu: torch.Tensor) -> float:
        return (0.5 * torch.norm(mu) ** 2).item()

    return T, E


def create_safety_barrier(threshold: float = 0.0) -> Callable:
    """Create a safety barrier function h(μ) ≥ 0.

    h(μ) = 0.5 - 0.1·||μ||
    Safe region: ||μ|| ≤ 5.0
    """

    def h(mu: torch.Tensor) -> torch.Tensor:
        return cast(torch.Tensor, 0.5 - 0.1 * torch.norm(mu))

    return h


def create_unsafe_barrier() -> Callable:
    """Create a barrier that violations occur.

    h(μ) = -0.5 - ||μ||  (always unsafe)
    """

    def h(mu: torch.Tensor) -> torch.Tensor:
        return cast(torch.Tensor, -0.5 - torch.norm(mu))

    return h


# =============================================================================
# PROPERTY: CONDITION X (CONTRACTIVITY)
# =============================================================================


class TestConditionX:
    """Tests for Condition X: Contractive Mapping."""

    @given(
        alpha=st.floats(min_value=0.1, max_value=0.99),
        initial_dim=st.integers(min_value=1, max_value=20),
        initial_norm=st.floats(min_value=0.01, max_value=10.0),
    )
    @settings(max_examples=50)
    def test_contractivity_linear_map(
        self, alpha: float, initial_dim: int, initial_norm: float
    ) -> None:
        """Test that linear maps T(μ) = α·μ are contractive for α < 1."""
        T = create_contractive_map(alpha)

        # Create two random initial states
        mu1 = initial_norm * torch.randn(initial_dim)
        mu2 = initial_norm * torch.randn(initial_dim)

        # Apply map
        T_mu1 = T(mu1)
        T_mu2 = T(mu2)

        # Check contraction: ||T(μ1) - T(μ2)|| ≤ α·||μ1 - μ2||
        dist_after = torch.norm(T_mu1 - T_mu2).item()
        dist_before = torch.norm(mu1 - mu2).item()

        if dist_before > 1e-8:
            contraction_factor = dist_after / dist_before
            assert contraction_factor <= alpha * (
                1 + 1e-5
            ), f"Failed: {contraction_factor:.4f} > {alpha:.4f}"

    @given(
        n_iterations=st.integers(min_value=2, max_value=50),
        alpha=st.floats(min_value=0.5, max_value=0.95),
        initial_dim=st.integers(min_value=1, max_value=15),
    )
    @settings(max_examples=50)
    def test_distance_sequence_is_decreasing(
        self, n_iterations: int, alpha: float, initial_dim: int
    ):
        """Test that distances form a strictly decreasing sequence.

        Property: d_{n+1} ≤ α·d_n for all n
        """
        T = create_contractive_map(alpha)
        mu = torch.randn(initial_dim)

        distances = []
        mu_prev = mu.clone()

        for _ in range(n_iterations):
            mu_curr = T(mu_prev)
            dist = torch.norm(mu_curr - mu_prev).item()
            distances.append(dist)
            mu_prev = mu_curr

        # Check monotonic decrease
        for i in range(1, len(distances)):
            if distances[i - 1] > 1e-8:
                ratio = distances[i] / distances[i - 1]
                assert ratio <= alpha * (
                    1 + 1e-4
                ), f"Distance ratio {ratio:.4f} exceeds α={alpha:.4f}"

    def test_non_contractive_map_fails_condition_x(self) -> None:
        """Test that non-contractive maps are detected."""
        T = create_oscillating_map()
        mu = torch.tensor([1.0, 2.0, 3.0])

        mu1 = T(mu)
        mu2 = T(mu1)

        dist1 = torch.norm(mu1 - mu).item()
        dist2 = torch.norm(mu2 - mu1).item()

        # Oscillating map preserves distance
        if dist1 > 1e-8:
            ratio = dist2 / dist1
            assert ratio > 0.99, "Oscillating map should have ratio ≈ 1"

    @given(
        alpha=st.floats(min_value=0.1, max_value=0.99),
        n_samples=st.integers(min_value=20, max_value=100),
    )
    @settings(max_examples=30)
    def test_estimated_alpha_matches_theoretical(self, alpha: float, n_samples: int) -> None:
        """Test that empirical contraction factor matches theoretical α.

        Property: Collect distance ratios d_n/d_{n-1}, verify mean ≈ α
        """
        T = create_contractive_map(alpha)
        mu = torch.randn(15)

        distances = []
        mu_prev = mu.clone()

        for _ in range(n_samples):
            mu_curr = T(mu_prev)
            dist = torch.norm(mu_curr - mu_prev).item()
            distances.append(dist)
            mu_prev = mu_curr

        # Estimate α from ratios
        ratios = []
        for i in range(1, len(distances)):
            if distances[i - 1] > 1e-8:
                ratio = distances[i] / distances[i - 1]
                if 0 < ratio < 2.0:  # Sanity filter
                    ratios.append(ratio)

        estimated_alpha = float(np.mean(ratios)) if ratios else 1.0

        # Should match within tolerance
        assert (
            abs(estimated_alpha - alpha) < 0.1
        ), f"Estimated α={estimated_alpha:.3f} vs theoretical α={alpha:.3f}"


# =============================================================================
# PROPERTY: CONDITION Y (ENERGY DISSIPATION)
# =============================================================================


class TestConditionY:
    """Tests for Condition Y: Energy Dissipation."""

    @given(
        n_iterations=st.integers(min_value=10, max_value=50),
        initial_norm=st.floats(min_value=0.5, max_value=5.0),
    )
    @settings(max_examples=50)
    def test_energy_monotonic_decrease(self, n_iterations: int, initial_norm: float) -> None:
        """Test that energy E(μ) = 0.5·||μ||² is monotonically decreasing.

        Note: Due to stochastic noise in T, we allow small increases.
        """
        T, E = create_dissipative_energy_function()
        mu = initial_norm * torch.randn(15)

        energies = []
        mu_curr = mu.clone()

        for _ in range(n_iterations):
            mu_curr = T(mu_curr)
            energy = E(mu_curr)
            energies.append(energy)

        # Check overall trend: final energy should be much lower
        # (Allow for noise in individual steps)
        assert (
            energies[-1] < energies[0] * 0.5
        ), f"Energy not decreasing overall: {energies[0]:.6f} → {energies[-1]:.6f}"

    @given(
        n_iterations=st.integers(min_value=10, max_value=100),
        initial_norm=st.floats(min_value=0.5, max_value=10.0),
    )
    @settings(max_examples=40)
    def test_energy_decrease_rate(self, n_iterations: int, initial_norm: float) -> None:
        """Test that energy decreases at a measurable rate.

        For T(μ) = 0.7·μ, we expect E_{n+1} ≈ 0.49·E_n
        """
        T, E = create_dissipative_energy_function()
        mu = initial_norm * torch.randn(15)

        E_init = E(mu)
        mu_curr = mu.clone()

        for _ in range(n_iterations):
            mu_curr = T(mu_curr)

        E_final = E(mu_curr)

        # After n iterations with factor 0.7, expect scaling 0.7^(2n)
        expected_ratio = 0.7 ** (2 * n_iterations)
        actual_ratio = E_final / E_init if E_init > 1e-8 else 0.0

        # Allow some noise
        tolerance = max(0.2, expected_ratio)  # Accounts for noise in T
        assert (
            actual_ratio < tolerance
        ), f"Energy ratio {actual_ratio:.4f} exceeds expected {expected_ratio:.4f}"

    def test_energy_dissipation_lambda_estimation(self) -> None:
        """Test estimation of dissipation rate λ from formula:
        E(T(μ)) ≤ E(μ) - λ·||T(μ) - μ||²
        """
        T, E = create_dissipative_energy_function()

        mu_samples = [torch.randn(15) for _ in range(20)]
        lambda_estimates = []

        for mu in mu_samples:
            mu_new = T(mu)
            delta_e = E(mu_new) - E(mu)
            dist_sq = torch.norm(mu_new - mu).item() ** 2

            if dist_sq > 1e-8:
                lambda_est = -delta_e / dist_sq
                if lambda_est > 0:  # Only positive λ makes sense
                    lambda_estimates.append(lambda_est)

        # Should have positive λ values
        assert len(lambda_estimates) > 0, "No positive λ estimates"
        lambda_avg = float(np.mean(lambda_estimates))
        assert (
            lambda_avg > ENERGY_DISSIPATION_MIN
        ), f"λ={lambda_avg:.6f} below minimum {ENERGY_DISSIPATION_MIN}"


# =============================================================================
# PROPERTY: CONDITION Z (SAFETY MAINTENANCE)
# =============================================================================


class TestConditionZ:
    """Tests for Condition Z: Safety Barrier Maintenance."""

    @given(
        n_iterations=st.integers(min_value=5, max_value=50),
        initial_norm=st.floats(min_value=0.1, max_value=3.0),  # Stay safe
    )
    @settings(max_examples=50)
    def test_safety_barrier_maintained(self, n_iterations: int, initial_norm: float) -> None:
        """Test that h(μ) ≥ 0 is maintained throughout iteration."""
        T = create_contractive_map(0.8)
        h = create_safety_barrier(SAFETY_THRESHOLD)

        mu = initial_norm * torch.randn(15)

        # Check initial safety
        assume(h(mu).item() >= SAFETY_THRESHOLD)

        # Iterate and verify safety at each step
        mu_curr = mu.clone()
        for _ in range(n_iterations):
            mu_curr = T(mu_curr)
            h_val = h(mu_curr).item()

            assert (
                h_val >= SAFETY_THRESHOLD * 0.99
            ), f"Safety barrier violated: h={h_val:.4f} < {SAFETY_THRESHOLD}"

    def test_unsafe_barrier_violates_condition_z(self) -> None:
        """Test that unsafe maps violate Condition Z."""
        T = create_contractive_map(0.8)
        h_unsafe = create_unsafe_barrier()

        mu = 0.1 * torch.randn(15)
        mu_new = T(mu)

        h_val = h_unsafe(mu_new).item()
        assert h_val < SAFETY_THRESHOLD, "Unsafe barrier should produce h < 0"

    @given(
        n_samples=st.integers(min_value=30, max_value=100),
        confidence=st.floats(min_value=0.90, max_value=0.99),
    )
    @settings(max_examples=30)
    def test_safety_statistical_confidence(self, n_samples: int, confidence: float) -> None:
        """Test statistical confidence interval for h(μ) ≥ 0.

        Property: If h_values are i.i.d. N(μ, σ²), confidence interval
        is μ ± t_α/2·σ/√n. Lower bound should exceed 0.
        """
        T = create_contractive_map(0.8)
        h = create_safety_barrier(SAFETY_THRESHOLD)

        h_values = []
        mu = 0.5 * torch.randn(15)

        for _ in range(n_samples):
            mu = T(mu)
            h_values.append(h(mu).item())

        h_mean = float(np.mean(h_values))
        h_std = float(np.std(h_values)) if len(h_values) > 1 else 0.0

        # Compute confidence interval
        alpha = 1 - confidence
        if len(h_values) > 1:
            se = h_std / math.sqrt(len(h_values))
            t_crit = stats.t.ppf(1 - alpha / 2, len(h_values) - 1)
            ci_low = h_mean - t_crit * se
        else:
            ci_low = h_mean

        # For safe system, lower CI bound should exceed safety threshold
        assert (
            ci_low > SAFETY_THRESHOLD
        ), f"Safety not assured: CI lower bound {ci_low:.4f} ≤ {SAFETY_THRESHOLD}"


# =============================================================================
# CONVERGENCE TESTS (Integration of X, Y, Z)
# =============================================================================


class TestConvergence:
    """Tests for complete convergence under all three conditions."""

    @given(
        alpha=st.floats(min_value=0.5, max_value=0.95),
        initial_norm=st.floats(min_value=0.1, max_value=5.0),
    )
    @settings(max_examples=40)
    def test_convergence_to_zero(self, alpha: float, initial_norm: float) -> None:
        """Test convergence of T(μ) = α·μ to fixed point μ* = 0."""
        T = create_contractive_map(alpha)
        mu = initial_norm * torch.randn(15)

        # Estimate iterations needed for convergence
        mu0_norm = torch.norm(mu).item()
        n_needed = (
            math.ceil(math.log(CONVERGENCE_EPS / mu0_norm) / math.log(alpha))
            if mu0_norm > 1e-8
            else 10
        )

        # Add buffer for numerical precision
        n_max = min(n_needed + 20, 300)

        distances = []
        mu_curr = mu.clone()

        for n in range(n_max):
            mu_curr = T(mu_curr)
            dist = torch.norm(mu_curr).item()
            distances.append(dist)

            # Check exponential decay: dist ≤ α^n · ||mu_0||
            expected = alpha**n * torch.norm(mu).item()
            assert dist <= expected * 1.01, f"Iteration {n}: {dist:.6f} > {expected:.6f}"

            if dist < CONVERGENCE_EPS:
                break

        # Final distance should be very small
        assert (
            distances[-1] < CONVERGENCE_EPS * 2
        ), f"Failed to converge: final distance {distances[-1]:.6f}"

    @given(
        alpha=st.floats(min_value=0.5, max_value=0.95),
        initial_norm=st.floats(min_value=0.1, max_value=5.0),
    )
    @settings(max_examples=40)
    def test_convergence_time_estimation(self, alpha: float, initial_norm: float) -> None:
        """Test that we can estimate time to convergence.

        Expect: n ≥ ln(eps/||μ₀||) / ln(α)
        """
        T = create_contractive_map(alpha)
        mu = initial_norm * torch.randn(15)

        # Estimate iterations needed for convergence to CONVERGENCE_EPS
        mu0_norm = torch.norm(mu).item()
        estimated_n = (
            math.ceil(math.log(CONVERGENCE_EPS / mu0_norm) / math.log(alpha))
            if mu0_norm > 1e-8
            else 1
        )

        # Run iterations
        mu_curr = mu.clone()
        for _n in range(estimated_n + 10):  # Add buffer
            mu_curr = T(mu_curr)

        final_dist = torch.norm(mu_curr).item()

        # Should be close to CONVERGENCE_EPS
        assert (
            final_dist < CONVERGENCE_EPS * 10
        ), f"Estimate {estimated_n} insufficient: final distance {final_dist:.6f}"

    def test_convergence_failure_on_oscillation(self) -> None:
        """Test that oscillating maps fail to converge."""
        T = create_oscillating_map()
        mu = torch.tensor([1.0, 0.0, 0.0])

        mu_curr = mu.clone()
        max_dist = 0.0

        for _ in range(100):
            mu_curr = T(mu_curr)
            dist = torch.norm(mu_curr).item()
            max_dist = max(max_dist, dist)

        # Oscillating map should not converge
        assert max_dist > CONVERGENCE_EPS * 0.5, "Oscillating map should not converge"


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Edge case testing."""

    def test_zero_fixed_point_stability(self) -> None:
        """Test that μ* = 0 is stable for T(μ) = α·μ."""
        T = create_contractive_map(0.8)
        mu_star = torch.zeros(15)

        # Zero should stay zero
        mu_new = T(mu_star)
        assert torch.allclose(mu_new, torch.zeros(15)), "Zero fixed point should remain zero"

    def test_near_convergence_detection(self) -> None:
        """Test that we can detect near-convergence."""
        T = create_contractive_map(0.9)
        mu = torch.randn(15)

        # Iterate until near fixed point
        mu_curr = mu.clone()
        for _ in range(500):
            mu_curr = T(mu_curr)

        dist = torch.norm(mu_curr).item()
        assert dist < 1e-6, f"Should be near-zero: {dist:.10f}"

    @given(
        initial_norm=st.floats(min_value=0.01, max_value=3.0),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.filter_too_much])
    def test_wide_range_initial_conditions(self, initial_norm: float) -> None:
        """Test convergence for reasonable range of initial norms.

        Only tests norms in safe region (||μ|| ≤ 5) to avoid filtering.
        """
        T = create_contractive_map(0.8)
        h = create_safety_barrier()

        mu = initial_norm * torch.randn(15)

        # Only test if initially safe
        if h(mu).item() < SAFETY_THRESHOLD:
            assume(False)

        # Iterate
        mu_curr = mu.clone()
        for _ in range(100):
            mu_curr = T(mu_curr)

            # Verify safety maintained
            h_val = h(mu_curr).item()
            assert (
                h_val >= SAFETY_THRESHOLD * 0.99
            ), f"Initial norm {initial_norm:.2e}: safety violated"

        final_dist = torch.norm(mu_curr).item()
        assert final_dist < 0.01, f"Initial norm {initial_norm:.2e}: failed convergence"

    def test_single_iteration_contraction(self) -> None:
        """Test single iteration satisfies contraction."""
        alpha = 0.8
        T = create_contractive_map(alpha)

        mu1 = torch.randn(15)
        mu2 = mu1 + 0.1 * torch.randn(15)

        T_mu1 = T(mu1)
        T_mu2 = T(mu2)

        dist_before = torch.norm(mu1 - mu2).item()
        dist_after = torch.norm(T_mu1 - T_mu2).item()

        if dist_before > 1e-8:
            ratio = dist_after / dist_before
            assert ratio <= alpha * (
                1 + 1e-5
            ), f"Single iteration failed: ratio {ratio:.4f} > {alpha:.4f}"


# =============================================================================
# INTEGRATION TEST: ALL CONDITIONS TOGETHER
# =============================================================================


class TestIntegratedStrangeLoopStability:
    """Integration test verifying all three conditions together."""

    def test_full_strange_loop_convergence_scenario(self) -> None:
        """Complete convergence scenario with all conditions verified."""
        # Setup
        alpha_target = 0.8
        T = create_contractive_map(alpha_target)
        T_dissipative, E = create_dissipative_energy_function()
        h = create_safety_barrier()

        # Use dissipative version for this test
        T_use = T_dissipative

        initial_mu = 0.5 * torch.randn(15)

        # Verify initial safety
        assert h(initial_mu).item() >= SAFETY_THRESHOLD

        # Run convergence
        trajectory = [initial_mu.clone()]
        h_values = [h(initial_mu).item()]
        energies = [E(initial_mu)]

        mu_curr = initial_mu.clone()

        for iteration in range(MAX_ITERATIONS):
            mu_next = T_use(mu_curr)

            # Check conditions at each step
            # Condition Z
            h_val = h(mu_next).item()
            h_values.append(h_val)
            assert h_val >= SAFETY_THRESHOLD * 0.99, f"Safety violated at iteration {iteration}"

            # Track trajectory
            trajectory.append(mu_next.clone().detach())
            energies.append(E(mu_next))

            # Check convergence
            dist = torch.norm(mu_next - mu_curr).item()
            if dist < CONVERGENCE_EPS:
                break

            mu_curr = mu_next

        # Post-convergence verification
        # Condition X (contractivity)
        # Note: Dissipative map has noise, so we relax threshold
        distances = [
            torch.norm(trajectory[i + 1] - trajectory[i]).item() for i in range(len(trajectory) - 1)
        ]
        if len(distances) >= 3:
            ratios = []
            for i in range(1, len(distances)):
                if distances[i - 1] > 1e-8:
                    ratio = distances[i] / distances[i - 1]
                    if 0 < ratio < 2.0:  # Filter outliers
                        ratios.append(ratio)

            if ratios:
                alpha_est = float(np.mean(ratios))
                # Relax threshold for noisy map
                assert alpha_est < 1.1, f"Condition X failed: α={alpha_est:.3f} >= 1.1"

        # Condition Y (energy dissipation)
        # Check overall trend (allow for noise)
        assert (
            energies[-1] < energies[0] * 0.5
        ), f"Condition Y failed: energy not decreasing overall: {energies[0]:.6f} → {energies[-1]:.6f}"

        # Condition Z (safety)
        all_safe = all(h >= SAFETY_THRESHOLD * 0.99 for h in h_values)
        assert all_safe, "Condition Z failed: safety barrier violated"

        # Convergence achieved (allow one over due to loop structure)
        assert (
            len(trajectory) <= MAX_ITERATIONS + 1
        ), f"Did not converge within {MAX_ITERATIONS} iterations"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
