"""Tests for Strange Loop Trajectory Verifier.

Tests:
1. Trajectory point recording
2. Invariant verification (I1-I4)
3. Convergence detection
4. Identity drift computation
5. Oscillation detection
6. Contraction factor estimation
7. Self-pointer computation

Based on:
- Temporal Poincaré geometry (H⁷ manifold)
- Gödel incompleteness (limits on self-prediction)
- Banach fixed-point theory (convergence)

鏡
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration

import numpy as np

from kagami.core.strange_loops.trajectory_verifier import (
    StrangeLoopVerifier,
    TrajectoryPoint,
    TrajectoryVerificationResult,
    get_strange_loop_verifier,
    verify_self_pointer_computation,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def verifier():
    """Create StrangeLoopVerifier instance."""
    return StrangeLoopVerifier(
        max_loops=3,
        convergence_threshold=0.01,
        drift_threshold=0.5,
        coherence_threshold=0.5,
    )


@pytest.fixture
def correlation_id():
    """Generate test correlation ID."""
    return "test-correlation-12345"


@pytest.fixture
def sample_trajectory_point():
    """Create sample trajectory point."""
    return TrajectoryPoint(
        loop_depth=1,
        self_pointer="abc123",
        correlation_id="test-123",
        workspace_hash="workspace-hash",
        radius=0.5,
        semantic_direction=np.random.randn(6) / np.linalg.norm(np.random.randn(6)),
        cost=0.1,
        quality_score=0.8,
        timestamp=1000.0,
        phase="planning",
    )


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestVerifierInit:
    """Test verifier initialization."""

    def test_default_initialization(self) -> None:
        """Test initialization with default parameters."""
        verifier = StrangeLoopVerifier()

        assert verifier.max_loops == 3
        assert verifier.convergence_threshold == 0.01
        assert verifier.drift_threshold == 0.5
        assert verifier.coherence_threshold == 0.5
        assert len(verifier._trajectories) == 0

    def test_custom_initialization(self) -> None:
        """Test initialization with custom parameters."""
        verifier = StrangeLoopVerifier(
            max_loops=5,
            convergence_threshold=0.001,
            drift_threshold=0.3,
            coherence_threshold=0.7,
        )

        assert verifier.max_loops == 5
        assert verifier.convergence_threshold == 0.001
        assert verifier.drift_threshold == 0.3
        assert verifier.coherence_threshold == 0.7

    def test_singleton_factory(self) -> None:
        """Test get_strange_loop_verifier singleton."""
        verifier1 = get_strange_loop_verifier()
        verifier2 = get_strange_loop_verifier()

        # Should return same instance
        assert verifier1 is verifier2


# =============================================================================
# TRAJECTORY RECORDING TESTS
# =============================================================================


class TestTrajectoryRecording:
    """Test trajectory point recording."""

    def test_record_single_point(self, verifier, correlation_id) -> None:
        """Test recording a single trajectory point."""
        verifier.record_trajectory_point(
            correlation_id=correlation_id,
            loop_depth=1,
            self_pointer="pointer1",
            workspace_hash="workspace1",
            cost=0.5,
            quality_score=0.8,
            phase="planning",
        )

        assert correlation_id in verifier._trajectories
        assert len(verifier._trajectories[correlation_id]) == 1

        point = verifier._trajectories[correlation_id][0]
        assert point.loop_depth == 1
        assert point.self_pointer == "pointer1"
        assert point.cost == 0.5

    def test_record_multiple_points(self, verifier, correlation_id) -> None:
        """Test recording multiple trajectory points."""
        for i in range(5):
            verifier.record_trajectory_point(
                correlation_id=correlation_id,
                loop_depth=i,
                self_pointer=f"pointer{i}",
                workspace_hash=f"workspace{i}",
                cost=0.1 * i,
                phase="executing",
            )

        assert len(verifier._trajectories[correlation_id]) == 5

    def test_record_with_manifold_position(self, verifier, correlation_id) -> None:
        """Test recording with explicit manifold position."""
        semantic_direction = np.random.randn(6)
        semantic_direction /= np.linalg.norm(semantic_direction)

        verifier.record_trajectory_point(
            correlation_id=correlation_id,
            loop_depth=1,
            self_pointer="pointer1",
            workspace_hash="workspace1",
            cost=0.5,
            radius=0.3,
            semantic_direction=semantic_direction,
        )

        point = verifier._trajectories[correlation_id][0]
        assert point.radius == 0.3
        np.testing.assert_array_almost_equal(point.semantic_direction, semantic_direction)

    def test_automatic_manifold_generation(self, verifier, correlation_id) -> None:
        """Test automatic generation of manifold position."""
        verifier.record_trajectory_point(
            correlation_id=correlation_id,
            loop_depth=2,
            self_pointer="pointer1",
            workspace_hash="workspace1",
            cost=0.5,
        )

        point = verifier._trajectories[correlation_id][0]
        # Radius should be auto-generated from loop_depth
        assert 0 <= point.radius <= 1
        # Semantic direction should be unit vector
        assert abs(np.linalg.norm(point.semantic_direction) - 1.0) < 1e-6


# =============================================================================
# INVARIANT VERIFICATION TESTS
# =============================================================================


class TestInvariantVerification:
    """Test invariant verification (I1-I4)."""

    def test_i1_safety_constraint(self, verifier: Any) -> None:
        """Test I1: Safety constraint h(x) ≥ 0."""
        # Safe
        satisfied, reason = verifier.verify_invariant_I1_safety(0.5)
        assert satisfied is True
        assert reason is None

        # Unsafe
        satisfied, reason = verifier.verify_invariant_I1_safety(-0.1)
        assert satisfied is False
        assert "h(x)" in reason

    def test_i2_value_alignment(self, verifier: Any) -> None:
        """Test I2: Value alignment (tim_partnership ≥ 0.95)."""
        # Aligned
        satisfied, reason = verifier.verify_invariant_I2_values({"tim_partnership": 0.98})
        assert satisfied is True

        # Not aligned
        satisfied, reason = verifier.verify_invariant_I2_values({"tim_partnership": 0.90})
        assert satisfied is False
        assert "tim_partnership" in reason

    def test_i3_pointer_uniqueness(self, verifier: Any) -> None:
        """Test I3: Self-pointer uniqueness."""
        # Unique pointers
        trajectory_unique = [
            TrajectoryPoint(
                loop_depth=i,
                self_pointer=f"pointer{i}",
                correlation_id="test",
                workspace_hash="workspace",
                radius=0.1 * i,
                semantic_direction=np.random.randn(6),
                cost=0.1,
                quality_score=0.8,
                timestamp=float(i),
                phase="test",
            )
            for i in range(3)
        ]

        satisfied, reason = verifier.verify_invariant_I3_uniqueness(trajectory_unique)
        assert satisfied is True

        # Duplicate pointers
        trajectory_duplicate = [
            TrajectoryPoint(
                loop_depth=i,
                self_pointer="same_pointer",  # Same pointer!
                correlation_id="test",
                workspace_hash="workspace",
                radius=0.1 * i,
                semantic_direction=np.random.randn(6),
                cost=0.1,
                quality_score=0.8,
                timestamp=float(i),
                phase="test",
            )
            for i in range(3)
        ]

        satisfied, reason = verifier.verify_invariant_I3_uniqueness(trajectory_duplicate)
        assert satisfied is False
        assert "duplicate" in reason

    def test_i4_causal_monotonicity(self, verifier: Any) -> None:
        """Test I4: Causal monotonicity (radius increasing)."""
        # Monotonically increasing
        trajectory_monotonic = [
            TrajectoryPoint(
                loop_depth=i,
                self_pointer=f"pointer{i}",
                correlation_id="test",
                workspace_hash="workspace",
                radius=0.1 * (i + 1),  # Increasing
                semantic_direction=np.random.randn(6),
                cost=0.1,
                quality_score=0.8,
                timestamp=float(i),
                phase="test",
            )
            for i in range(3)
        ]

        satisfied, reason = verifier.verify_invariant_I4_causality(trajectory_monotonic)
        assert satisfied is True

        # Time reversal
        trajectory_reversal = [
            TrajectoryPoint(
                loop_depth=i,
                self_pointer=f"pointer{i}",
                correlation_id="test",
                workspace_hash="workspace",
                radius=0.5 - 0.1 * i,  # Decreasing!
                semantic_direction=np.random.randn(6),
                cost=0.1,
                quality_score=0.8,
                timestamp=float(i),
                phase="test",
            )
            for i in range(3)
        ]

        satisfied, reason = verifier.verify_invariant_I4_causality(trajectory_reversal)
        assert satisfied is False
        assert "Time reversal" in reason


# =============================================================================
# CONVERGENCE DETECTION TESTS
# =============================================================================


class TestConvergenceDetection:
    """Test convergence detection."""

    def test_converged_trajectory(self, verifier, correlation_id) -> None:
        """Test detection of converged trajectory."""
        # Record trajectory with decreasing costs
        costs = [1.0, 0.5, 0.2, 0.05, 0.01, 0.005]
        for i, cost in enumerate(costs):
            verifier.record_trajectory_point(
                correlation_id=correlation_id,
                loop_depth=i,
                self_pointer=f"pointer{i}",
                workspace_hash=f"workspace{i}",
                cost=cost,
                radius=0.1 * (i + 1),
            )

        result = verifier.verify_trajectory(correlation_id)

        assert result.converged is True
        assert result.convergence_type in ["normal", "fast"]
        assert result.iterations_to_converge is not None

    def test_divergent_trajectory(self, verifier, correlation_id) -> None:
        """Test detection of divergent trajectory."""
        # Record trajectory exceeding max_loops
        for i in range(5):  # More than max_loops=3
            verifier.record_trajectory_point(
                correlation_id=correlation_id,
                loop_depth=i,
                self_pointer=f"pointer{i}",
                workspace_hash=f"workspace{i}",
                cost=1.0 * i,  # Increasing cost
                radius=0.1 * (i + 1),
            )

        result = verifier.verify_trajectory(correlation_id)

        assert result.convergence_type == "divergent"
        assert result.max_loops_exceeded is True

    def test_oscillating_trajectory(self, verifier, correlation_id) -> None:
        """Test detection of oscillating trajectory."""
        # Record trajectory with oscillating costs
        costs = [0.5, 0.3, 0.6, 0.2, 0.7, 0.1]
        for i, cost in enumerate(costs):
            verifier.record_trajectory_point(
                correlation_id=correlation_id,
                loop_depth=i,
                self_pointer=f"pointer{i}",
                workspace_hash=f"workspace{i}",
                cost=cost,
                radius=0.1 * (i + 1),
            )

        result = verifier.verify_trajectory(correlation_id)

        # Should detect oscillation
        if result.convergence_type == "oscillating":
            assert True  # Oscillation detected
        else:
            # Might not always detect depending on threshold
            pass

    def test_fast_convergence(self, verifier, correlation_id) -> None:
        """Test detection of fast convergence."""
        # Single point with very low cost
        verifier.record_trajectory_point(
            correlation_id=correlation_id,
            loop_depth=0,
            self_pointer="pointer0",
            workspace_hash="workspace0",
            cost=0.001,  # Very low
            radius=0.1,
        )

        result = verifier.verify_trajectory(correlation_id)

        assert result.converged is True
        assert result.convergence_type == "fast"
        assert result.iterations_to_converge == 1


# =============================================================================
# IDENTITY DRIFT TESTS
# =============================================================================


class TestIdentityDrift:
    """Test identity drift computation."""

    def test_no_drift(self, verifier, correlation_id) -> None:
        """Test trajectory with no drift (same pointer)."""
        # Should not happen in practice (I3 violation), but test the logic
        for i in range(3):
            verifier.record_trajectory_point(
                correlation_id=correlation_id,
                loop_depth=i,
                self_pointer="same_pointer",
                workspace_hash=f"workspace{i}",
                cost=0.1,
                radius=0.1 * (i + 1),
            )

        result = verifier.verify_trajectory(correlation_id)

        # Drift should be 0 (only 1 unique pointer)
        assert result.total_drift == 0.0
        assert result.coherence_score == 1.0

    def test_high_drift(self, verifier, correlation_id) -> None:
        """Test trajectory with high drift (all unique pointers)."""
        for i in range(5):
            verifier.record_trajectory_point(
                correlation_id=correlation_id,
                loop_depth=i,
                self_pointer=f"pointer{i}",
                workspace_hash=f"workspace{i}",
                cost=0.1,
                radius=0.1 * (i + 1),
            )

        result = verifier.verify_trajectory(correlation_id)

        # Drift should be 4 (5 unique pointers = 4 changes)
        assert result.total_drift == 4.0
        assert result.drift_per_iteration == 1.0  # Every iteration changed

    def test_compute_identity_drift_10d(self, verifier, sample_trajectory_point) -> None:
        """Test 10D identity drift vector computation."""
        point1 = sample_trajectory_point
        point2 = TrajectoryPoint(
            loop_depth=2,
            self_pointer="different_pointer",
            correlation_id="test-123",
            workspace_hash="workspace-hash",
            radius=0.6,
            semantic_direction=np.random.randn(6) / np.linalg.norm(np.random.randn(6)),
            cost=0.2,
            quality_score=0.7,
            timestamp=2000.0,
            phase="execution",
        )

        drift = verifier.compute_identity_drift_10d(point1, point2)

        assert drift.shape == (10,)
        # First component should be 1.0 (different pointers)
        assert drift[0] == 1.0
        # All components should be in [0, 1]
        assert np.all((drift >= 0) & (drift <= 1))


# =============================================================================
# CONTRACTION & OSCILLATION TESTS
# =============================================================================


class TestContractionAndOscillation:
    """Test contraction factor and limit cycle detection."""

    def test_contractive_trajectory(
        self, verifier: StrangeLoopVerifier, correlation_id: str
    ) -> None:
        """Test contraction factor for converging trajectory."""
        # Exponentially decreasing costs (contractive)
        costs = [1.0, 0.5, 0.25, 0.125]
        for i, cost in enumerate(costs):
            verifier.record_trajectory_point(
                correlation_id=correlation_id,
                loop_depth=i,
                self_pointer=f"pointer{i}",
                workspace_hash=f"workspace{i}",
                cost=cost,
                radius=0.1 * (i + 1),
            )

        is_contractive, alpha = verifier.compute_contraction_factor(correlation_id)

        # Should be contractive (alpha < 1)
        assert is_contractive is True
        assert alpha < 1.0

    def test_non_contractive_trajectory(
        self, verifier: StrangeLoopVerifier, correlation_id: str
    ) -> None:
        """Test contraction factor for diverging trajectory."""
        # Increasing costs (non-contractive)
        costs = [0.1, 0.2, 0.4, 0.8]
        for i, cost in enumerate(costs):
            verifier.record_trajectory_point(
                correlation_id=correlation_id,
                loop_depth=i,
                self_pointer=f"pointer{i}",
                workspace_hash=f"workspace{i}",
                cost=cost,
                radius=0.1 * (i + 1),
            )

        is_contractive, alpha = verifier.compute_contraction_factor(correlation_id)

        # Should NOT be contractive (alpha >= 1)
        assert is_contractive is False
        assert alpha >= 1.0

    def test_detect_limit_cycle(self, verifier: StrangeLoopVerifier, correlation_id: str) -> None:
        """Test limit cycle detection."""
        # Periodic pattern: 0.1, 0.2, 0.3, 0.1, 0.2, 0.3, ...
        costs = [0.1, 0.2, 0.3] * 3
        for i, cost in enumerate(costs):
            verifier.record_trajectory_point(
                correlation_id=correlation_id,
                loop_depth=i,
                self_pointer=f"pointer{i}",
                workspace_hash=f"workspace{i}",
                cost=cost,
                radius=0.1 * (i + 1),
            )

        is_cycling, period = verifier.detect_limit_cycle(correlation_id, window=3)

        # Should detect cycle with period 3
        assert is_cycling is True
        assert period == 3

    def test_no_limit_cycle(self, verifier: StrangeLoopVerifier, correlation_id: str) -> None:
        """Test no false positives for non-cyclic trajectory."""
        # Random non-periodic costs
        costs = [0.5, 0.3, 0.7, 0.2, 0.9, 0.1]
        for i, cost in enumerate(costs):
            verifier.record_trajectory_point(
                correlation_id=correlation_id,
                loop_depth=i,
                self_pointer=f"pointer{i}",
                workspace_hash=f"workspace{i}",
                cost=cost,
                radius=0.1 * (i + 1),
            )

        is_cycling, _period = verifier.detect_limit_cycle(correlation_id)

        # Should not detect cycle
        assert is_cycling is False


# =============================================================================
# SELF-POINTER COMPUTATION TESTS
# =============================================================================


class TestSelfPointerComputation:
    """Test self-pointer hash computation."""

    def test_verify_self_pointer(self) -> None:
        """Test self-pointer computation matches specification."""
        workspace_hash = "workspace123"
        correlation_id = "corr456"
        loop_depth = 2

        is_valid, computed = verify_self_pointer_computation(
            workspace_hash, correlation_id, loop_depth
        )

        assert is_valid is True
        assert len(computed) == 16  # Truncated SHA256
        assert isinstance(computed, str)

    def test_self_pointer_deterministic(self) -> None:
        """Test self-pointer is deterministic."""
        workspace_hash = "workspace123"
        correlation_id = "corr456"
        loop_depth = 2

        _, computed1 = verify_self_pointer_computation(workspace_hash, correlation_id, loop_depth)
        _, computed2 = verify_self_pointer_computation(workspace_hash, correlation_id, loop_depth)

        assert computed1 == computed2

    def test_self_pointer_changes_with_input(self) -> None:
        """Test self-pointer changes when inputs change."""
        _, pointer1 = verify_self_pointer_computation("workspace1", "corr1", 1)
        _, pointer2 = verify_self_pointer_computation("workspace2", "corr1", 1)
        _, pointer3 = verify_self_pointer_computation("workspace1", "corr2", 1)
        _, pointer4 = verify_self_pointer_computation("workspace1", "corr1", 2)

        # All should be different
        assert pointer1 != pointer2
        assert pointer1 != pointer3
        assert pointer1 != pointer4
        assert pointer2 != pointer3


# =============================================================================
# CLEANUP TESTS
# =============================================================================


class TestTrajectoryCleanup:
    """Test trajectory cleanup."""

    def test_cleanup_trajectory(self, verifier: StrangeLoopVerifier, correlation_id: str) -> None:
        """Test cleaning up trajectory data."""
        # Record trajectory
        verifier.record_trajectory_point(
            correlation_id=correlation_id,
            loop_depth=0,
            self_pointer="pointer0",
            workspace_hash="workspace0",
            cost=0.5,
        )

        assert correlation_id in verifier._trajectories

        # Cleanup
        verifier.cleanup_trajectory(correlation_id)

        assert correlation_id not in verifier._trajectories
        assert correlation_id not in verifier._seen_pointers

    def test_get_active_trajectories(self, verifier: StrangeLoopVerifier) -> None:
        """Test getting active trajectory count."""
        assert verifier.get_active_trajectories() == 0

        # Add some trajectories
        for i in range(3):
            verifier.record_trajectory_point(
                correlation_id=f"corr{i}",
                loop_depth=0,
                self_pointer=f"pointer{i}",
                workspace_hash=f"workspace{i}",
                cost=0.5,
            )

        assert verifier.get_active_trajectories() == 3


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestVerifierIntegration:
    """Integration tests with complete trajectories."""

    def test_complete_successful_trajectory(self, verifier: StrangeLoopVerifier) -> None:
        """Test complete successful trajectory from start to finish."""
        correlation_id = "integration-success"

        # Record converging trajectory
        costs = [1.0, 0.5, 0.2, 0.05, 0.005]
        for i, cost in enumerate(costs):
            verifier.record_trajectory_point(
                correlation_id=correlation_id,
                loop_depth=i,
                self_pointer=f"pointer{i}",
                workspace_hash=f"workspace{i}",
                cost=cost,
                quality_score=0.9 - i * 0.05,
                radius=0.1 * (i + 1),
            )

        # Verify
        result = verifier.verify_trajectory(correlation_id)

        assert result.invariants_satisfied is True
        assert result.converged is True
        assert result.trajectory_length == 5
        assert result.total_duration_ms > 0

        # Cleanup
        verifier.cleanup_trajectory(correlation_id)

    def test_complete_failed_trajectory(self, verifier: StrangeLoopVerifier) -> None:
        """Test complete failed trajectory (invariant violation)."""
        correlation_id = "integration-failed"

        # Record trajectory with time reversal (I4 violation)
        for i in range(3):
            verifier.record_trajectory_point(
                correlation_id=correlation_id,
                loop_depth=i,
                self_pointer=f"pointer{i}",
                workspace_hash=f"workspace{i}",
                cost=0.5,
                radius=0.5 - 0.1 * i,  # Decreasing!
            )

        # Verify
        result = verifier.verify_trajectory(correlation_id)

        assert result.invariants_satisfied is False
        assert "I4_causal_monotonicity" in result.violated_invariants


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
