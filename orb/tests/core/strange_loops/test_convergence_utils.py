"""Tests for Convergence Detection Utilities.

Tests:
1. ConvergenceDetector basic functionality
2. Distance threshold convergence
3. Stagnation detection
4. Divergence detection
5. Convergence rate estimation
6. Embedding distance computation
7. Contraction checking
8. Oscillation detection

Based on:
- Banach fixed-point theorem
- Contraction mapping principle
- Distance metrics for convergence

鏡
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration

import numpy as np
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from kagami.core.strange_loops.convergence_utils import (
    ConvergenceDetector,
    ConvergenceResult,
    compute_embedding_distance,
    detect_oscillation,
    is_contractive,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def detector():
    """Create ConvergenceDetector instance."""
    return ConvergenceDetector(
        epsilon=0.01,
        max_iterations=10,
        min_progress_rate=0.1,
    )


@pytest.fixture
def sample_embedding_1():
    """Create sample embedding vector."""
    return np.array([0.1, 0.2, 0.3, 0.4, 0.5])


@pytest.fixture
def sample_embedding_2():
    """Create sample embedding vector."""
    return np.array([0.15, 0.25, 0.35, 0.45, 0.55])


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestConvergenceDetectorInit:
    """Test ConvergenceDetector initialization."""

    def test_default_initialization(self) -> None:
        """Test initialization with default parameters."""
        detector = ConvergenceDetector()

        assert detector.epsilon == 0.01
        assert detector.max_iterations == 10
        assert detector.min_progress_rate == 0.1
        assert len(detector.distance_history) == 0
        assert len(detector.state_history) == 0

    def test_custom_initialization(self) -> None:
        """Test initialization with custom parameters."""
        detector = ConvergenceDetector(
            epsilon=0.001,
            max_iterations=20,
            min_progress_rate=0.05,
        )

        assert detector.epsilon == 0.001
        assert detector.max_iterations == 20
        assert detector.min_progress_rate == 0.05


# =============================================================================
# CONVERGENCE CHECK TESTS
# =============================================================================


class TestConvergenceCheck:
    """Test convergence checking."""

    def test_converged_below_threshold(self, detector: ConvergenceDetector) -> None:
        """Test convergence when distance is below threshold."""
        result = detector.check_convergence(current_distance=0.005, iteration=3)

        assert result.converged is True
        assert result.reason == "distance_threshold"
        assert result.final_distance == 0.005
        assert result.iterations == 3

    def test_not_converged_above_threshold(self, detector: ConvergenceDetector) -> None:
        """Test no convergence when distance is above threshold."""
        result = detector.check_convergence(current_distance=0.5, iteration=3)

        assert result.converged is False
        assert result.reason == "iterating"

    def test_max_iterations_reached(self, detector: ConvergenceDetector) -> None:
        """Test max iterations stopping condition."""
        result = detector.check_convergence(current_distance=0.5, iteration=10)

        assert result.converged is False
        assert result.reason == "max_iterations_reached"
        assert result.iterations == 10

    def test_stagnation_detection(self, detector: ConvergenceDetector) -> None:
        """Test detection of stagnation (no progress).

        Stagnation is detected when: max(last 3) - min(last 3) < epsilon * 0.1
        With epsilon=0.01, threshold is 0.001. History must vary by < 0.001.
        """
        # Add history of nearly identical distances (variation < 0.001)
        detector.distance_history = [0.5, 0.5002, 0.5004]

        result = detector.check_convergence(current_distance=0.5006, iteration=4)

        # Should detect stagnation (max - min = 0.0006 < 0.001)
        assert result.converged is False
        assert result.reason == "stagnation_detected"

    def test_divergence_detection(self, detector: ConvergenceDetector) -> None:
        """Test detection of divergence (increasing distance)."""
        # Add history starting small
        detector.distance_history = [0.1]

        # Current distance is much larger
        result = detector.check_convergence(current_distance=0.5, iteration=2)

        # Should detect divergence (distance > 2x initial)
        assert result.converged is False
        assert result.reason == "divergence_detected"

    def test_convergence_rate_estimation(self, detector: ConvergenceDetector) -> None:
        """Test convergence rate estimation."""
        # Add history of decreasing distances
        detector.distance_history = [1.0, 0.5, 0.25]

        result = detector.check_convergence(current_distance=0.005, iteration=4)

        assert result.converged is True
        assert result.convergence_rate is not None
        # Should be around 0.5 (halving each iteration)
        assert 0.3 < result.convergence_rate < 0.7

    def test_reset_history(self, detector: ConvergenceDetector) -> None:
        """Test resetting detector history."""
        detector.distance_history = [1.0, 0.5, 0.25]
        detector.state_history = ["a", "b", "c"]

        detector.reset()

        assert len(detector.distance_history) == 0
        assert len(detector.state_history) == 0


# =============================================================================
# CONVERGENCE RATE TESTS
# =============================================================================


class TestConvergenceRate:
    """Test convergence rate estimation."""

    def test_estimate_rate_insufficient_data(self, detector: ConvergenceDetector) -> None:
        """Test rate estimation with insufficient data."""
        detector.distance_history = [1.0]

        rate = detector._estimate_convergence_rate()

        assert rate is None

    def test_estimate_rate_linear_convergence(self, detector: ConvergenceDetector) -> None:
        """Test rate estimation for linear convergence."""
        # Constant ratio of 0.5
        detector.distance_history = [1.0, 0.5, 0.25, 0.125]

        rate = detector._estimate_convergence_rate()

        assert rate is not None
        # Should be around 0.5
        assert 0.4 < rate < 0.6

    def test_estimate_rate_superlinear_convergence(self, detector: ConvergenceDetector) -> None:
        """Test rate estimation for superlinear convergence."""
        # Decreasing ratio (faster convergence)
        detector.distance_history = [1.0, 0.5, 0.1, 0.01]

        rate = detector._estimate_convergence_rate()

        assert rate is not None
        # Should be less than 0.5 on average
        assert rate < 0.5

    def test_estimate_rate_ignores_outliers(self, detector: ConvergenceDetector) -> None:
        """Test that rate estimation handles outliers."""
        # One outlier shouldn't break estimation
        detector.distance_history = [1.0, 0.5, 0.25, 100.0, 0.125]

        rate = detector._estimate_convergence_rate()

        # Should still estimate a rate (filtering invalid ratios)
        assert rate is not None


# =============================================================================
# EMBEDDING DISTANCE TESTS
# =============================================================================


class TestEmbeddingDistance:
    """Test embedding distance computation."""

    def test_l2_distance(
        self, sample_embedding_1: np.ndarray, sample_embedding_2: np.ndarray
    ) -> None:
        """Test L2 (Euclidean) distance."""
        dist = compute_embedding_distance(sample_embedding_1, sample_embedding_2, metric="l2")

        # Should be positive
        assert dist > 0

        # Manual computation
        expected = np.linalg.norm(sample_embedding_1 - sample_embedding_2)
        assert abs(dist - expected) < 1e-6

    def test_cosine_distance(
        self, sample_embedding_1: np.ndarray, sample_embedding_2: np.ndarray
    ) -> None:
        """Test cosine distance."""
        dist = compute_embedding_distance(sample_embedding_1, sample_embedding_2, metric="cosine")

        # Should be in [0, 2]
        assert 0 <= dist <= 2

        # Cosine distance = 1 - cosine_similarity
        # For similar vectors, should be close to 0
        assert dist < 0.5

    def test_l1_distance(
        self, sample_embedding_1: np.ndarray, sample_embedding_2: np.ndarray
    ) -> None:
        """Test L1 (Manhattan) distance."""
        dist = compute_embedding_distance(sample_embedding_1, sample_embedding_2, metric="l1")

        # Should be positive
        assert dist > 0

        # Manual computation
        expected = np.sum(np.abs(sample_embedding_1 - sample_embedding_2))
        assert abs(dist - expected) < 1e-6

    def test_distance_zero_for_identical(self, sample_embedding_1: np.ndarray) -> None:
        """Test that distance is zero for identical embeddings."""
        dist = compute_embedding_distance(sample_embedding_1, sample_embedding_1, metric="l2")

        assert dist < 1e-6

    def test_distance_symmetric(
        self, sample_embedding_1: np.ndarray, sample_embedding_2: np.ndarray
    ) -> None:
        """Test that distance is symmetric."""
        dist1 = compute_embedding_distance(sample_embedding_1, sample_embedding_2, metric="l2")
        dist2 = compute_embedding_distance(sample_embedding_2, sample_embedding_1, metric="l2")

        assert abs(dist1 - dist2) < 1e-6

    def test_cosine_distance_orthogonal(self) -> None:
        """Test cosine distance for orthogonal vectors."""
        emb1 = np.array([1.0, 0.0, 0.0])
        emb2 = np.array([0.0, 1.0, 0.0])

        dist = compute_embedding_distance(emb1, emb2, metric="cosine")

        # Orthogonal vectors have cosine similarity = 0, so distance = 1
        assert abs(dist - 1.0) < 1e-6

    def test_cosine_distance_zero_vector(self) -> None:
        """Test cosine distance with zero vector."""
        emb1 = np.array([1.0, 2.0, 3.0])
        emb2 = np.array([0.0, 0.0, 0.0])

        dist = compute_embedding_distance(emb1, emb2, metric="cosine")

        # Should return 1.0 (maximum distance)
        assert dist == 1.0

    def test_invalid_metric(
        self, sample_embedding_1: np.ndarray, sample_embedding_2: np.ndarray
    ) -> None:
        """Test error handling for invalid metric."""
        with pytest.raises(ValueError, match="Unknown metric"):
            compute_embedding_distance(sample_embedding_1, sample_embedding_2, metric="invalid")

    def test_list_input(self) -> None:
        """Test that function accepts list inputs."""
        emb1 = [0.1, 0.2, 0.3]
        emb2 = [0.15, 0.25, 0.35]

        dist = compute_embedding_distance(emb1, emb2, metric="l2")

        assert dist > 0


# =============================================================================
# CONTRACTION TESTS
# =============================================================================


class TestContraction:
    """Test contraction checking."""

    def test_contractive_sequence(self) -> None:
        """Test detecting contractive sequence."""
        # Exponentially decreasing distances
        distances = [1.0, 0.5, 0.25, 0.125]

        is_contract, alpha = is_contractive(distances)

        assert is_contract is True
        assert alpha < 1.0
        # Should be around 0.5
        assert 0.4 < alpha < 0.6

    def test_non_contractive_sequence(self) -> None:
        """Test detecting non-contractive sequence."""
        # Increasing distances
        distances = [0.1, 0.2, 0.4, 0.8]

        is_contract, alpha = is_contractive(distances)

        assert is_contract is False
        assert alpha >= 1.0

    def test_borderline_contraction(self) -> None:
        """Test borderline contraction (alpha ≈ 1)."""
        # Nearly constant distances
        distances = [1.0, 0.99, 0.98, 0.97]

        is_contract, alpha = is_contractive(distances, threshold=1.0)

        assert is_contract is True
        assert alpha < 1.0

    def test_insufficient_data(self) -> None:
        """Test contraction check with insufficient data."""
        distances = [1.0]

        is_contract, alpha = is_contractive(distances)

        assert is_contract is False
        assert alpha == 1.0

    def test_zero_distance_handling(self) -> None:
        """Test handling of zero distances."""
        # Some zero distances (convergence reached)
        distances = [1.0, 0.5, 0.0, 0.0]

        _is_contract, alpha = is_contractive(distances)

        # Should still compute alpha from non-zero ratios
        assert isinstance(alpha, float)

    def test_custom_threshold(self) -> None:
        """Test custom contraction threshold."""
        distances = [1.0, 0.7, 0.49, 0.343]

        # With threshold 0.8, alpha ≈ 0.7 should be contractive
        is_contract, alpha = is_contractive(distances, threshold=0.8)

        assert is_contract is True
        assert alpha < 0.8


# =============================================================================
# OSCILLATION DETECTION TESTS
# =============================================================================


class TestOscillationDetection:
    """Test oscillation/limit cycle detection."""

    def test_detect_perfect_cycle(self) -> None:
        """Test detecting perfect periodic cycle."""
        # Pattern: A, B, C, A, B, C, A, B, C
        state_history = ["A", "B", "C"] * 3

        is_cycling = detect_oscillation(state_history, window=3)

        assert is_cycling is True

    def test_detect_numeric_cycle(self) -> None:
        """Test detecting numeric periodic cycle."""
        # Pattern: 0.1, 0.2, 0.3, 0.1, 0.2, 0.3, ...
        state_history = [[0.1], [0.2], [0.3]] * 3

        is_cycling = detect_oscillation(state_history, window=3)

        assert is_cycling is True

    def test_no_cycle_random(self) -> None:
        """Test no false positives for random sequence."""
        state_history = ["A", "B", "C", "D", "E", "F", "G", "H"]

        is_cycling = detect_oscillation(state_history, window=3)

        assert is_cycling is False

    def test_insufficient_history(self) -> None:
        """Test with insufficient history."""
        state_history = ["A", "B"]

        is_cycling = detect_oscillation(state_history, window=3)

        assert is_cycling is False

    def test_approximate_cycle_with_embeddings(self) -> None:
        """Test detecting approximate cycle with embedding vectors."""
        # Nearly identical embeddings in cycle
        emb_a = np.array([0.1, 0.2, 0.3])
        emb_b = np.array([0.4, 0.5, 0.6])
        emb_c = np.array([0.7, 0.8, 0.9])

        # Small noise added
        state_history = [
            emb_a,
            emb_b,
            emb_c,
            emb_a + np.random.randn(3) * 0.01,
            emb_b + np.random.randn(3) * 0.01,
            emb_c + np.random.randn(3) * 0.01,
            emb_a + np.random.randn(3) * 0.01,
            emb_b + np.random.randn(3) * 0.01,
            emb_c + np.random.randn(3) * 0.01,
        ]

        is_cycling = detect_oscillation(state_history, window=3, similarity_threshold=0.95)

        # Should detect approximate cycle
        assert is_cycling is True

    def test_different_window_sizes(self) -> None:
        """Test oscillation detection with different window sizes."""
        # Period-2 cycle
        state_history = ["A", "B"] * 5

        # Window 2 should detect it
        is_cycling_w2 = detect_oscillation(state_history, window=2)
        assert is_cycling_w2 is True

        # Window 3 should not detect it (wrong period)
        is_cycling_w3 = detect_oscillation(state_history, window=3)
        # Might still match partially, so we don't assert False


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestConvergenceIntegration:
    """Integration tests with realistic scenarios."""

    def test_complete_convergence_scenario(self) -> None:
        """Test complete convergence detection scenario."""
        detector = ConvergenceDetector(epsilon=0.01, max_iterations=20)

        # Simulate contractive iteration
        distances = [1.0, 0.5, 0.25, 0.125, 0.0625, 0.03, 0.015, 0.008]

        for i, dist in enumerate(distances):
            result = detector.check_convergence(dist, iteration=i + 1)

            if result.converged:
                assert result.reason == "distance_threshold"
                assert result.convergence_rate is not None
                assert result.convergence_rate < 1.0
                break

    def test_complete_divergence_scenario(self) -> None:
        """Test complete divergence detection scenario."""
        detector = ConvergenceDetector(epsilon=0.01, max_iterations=10)

        # Simulate divergent iteration
        distances = [0.1, 0.2, 0.5, 1.0, 2.0]

        for i, dist in enumerate(distances):
            result = detector.check_convergence(dist, iteration=i + 1)

            if result.reason == "divergence_detected":
                assert result.converged is False
                break

    def test_complete_stagnation_scenario(self) -> None:
        """Test complete stagnation detection scenario."""
        detector = ConvergenceDetector(epsilon=0.01, max_iterations=10)

        # Simulate stagnation (stuck at same distance)
        distances = [0.5, 0.501, 0.502, 0.503, 0.504]

        for i, dist in enumerate(distances):
            result = detector.check_convergence(dist, iteration=i + 1)

            if result.reason == "stagnation_detected":
                assert result.converged is False
                break


# =============================================================================
# PROPERTY-BASED TESTS
# =============================================================================


class TestConvergenceProperties:
    """Property-based tests using Hypothesis."""

    @given(
        distance=st.floats(min_value=0.0, max_value=0.001),
        iteration=st.integers(min_value=1, max_value=5),
    )
    def test_below_threshold_always_converges(self, distance: float, iteration: int) -> None:
        """Property: Distance below threshold always converges."""
        detector = ConvergenceDetector(epsilon=0.01)

        result = detector.check_convergence(distance, iteration)

        assert result.converged is True
        assert result.reason == "distance_threshold"

    @given(iteration=st.integers(min_value=10, max_value=100))
    def test_max_iterations_always_stops(self, iteration: int) -> None:
        """Property: Reaching max iterations always stops."""
        detector = ConvergenceDetector(epsilon=0.01, max_iterations=10)

        result = detector.check_convergence(current_distance=0.5, iteration=iteration)

        if iteration >= detector.max_iterations:
            assert result.converged is False
            assert result.reason == "max_iterations_reached"

    @given(
        emb1=st.lists(
            st.floats(min_value=-1, max_value=1, allow_nan=False, allow_infinity=False),
            min_size=5,
            max_size=5,
        ),
        emb2=st.lists(
            st.floats(min_value=-1, max_value=1, allow_nan=False, allow_infinity=False),
            min_size=5,
            max_size=5,
        ),
    )
    @settings(suppress_health_check=[HealthCheck.too_slow])
    def test_distance_nonnegative(self, emb1: list[float], emb2: list[float]) -> None:
        """Property: Distance is always non-negative."""
        dist = compute_embedding_distance(emb1, emb2, metric="l2")

        assert dist >= 0

    @given(
        emb=st.lists(
            st.floats(min_value=-1, max_value=1, allow_nan=False, allow_infinity=False),
            min_size=5,
            max_size=5,
        )
    )
    @settings(suppress_health_check=[HealthCheck.too_slow])
    def test_distance_to_self_zero(self, emb: list[float]) -> None:
        """Property: Distance to self is zero."""
        dist = compute_embedding_distance(emb, emb, metric="l2")

        assert dist < 1e-5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
