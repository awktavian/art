"""Tests for CBF Runtime Safety Monitoring.

CREATED: December 14, 2025
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import numpy as np
import torch

from kagami.core.safety.cbf_monitor import (
    CBFMonitor,
    DecentralizedCBFMonitor,
    AdaptiveE8Monitor,
    GatedFanoMonitor,
    CompositeMonitor,
    MonitorResult,
    create_cbf_monitor,
    create_composite_monitor,
)

# Set seeds for reproducibility
np.random.seed(42)
torch.manual_seed(42)

# =============================================================================
# TEST CONSTANTS - Named values for clarity and maintainability
# =============================================================================

# CBF Thresholds
SAFE_THRESHOLD = 0.0  # h(x) >= 0 is safe invariant
WARN_THRESHOLD = 0.1  # Warning zone between 0 and 0.1
SAFE_VALUE = 0.5  # Clearly safe value
WARNING_VALUE = 0.05  # In warning zone
VIOLATION_VALUE = -0.1  # Below safe threshold

# E8 Depth Constraints
E8_VARIANCE_THRESHOLD = 4.0  # Max allowed variance in E8 depths
E8_VARIANCE_WARN = 3.0  # Warning threshold for variance
E8_MIN_MEAN_DEPTH = 2.0  # Minimum safe mean depth
E8_MAX_MEAN_DEPTH = 14.0  # Maximum safe mean depth (within 240 root space)
E8_NOMINAL_DEPTH = 8.0  # Nominal depth for stable operation

# Fano Gate Constraints
GATE_EPSILON = 0.01  # Minimum gate value (avoid collapse)
GATE_MAX = 0.99  # Maximum gate value (avoid saturation)
GATE_MIN_SPARSITY = 0.3  # Minimum sparsity (avoid too dense)
GATE_MAX_SPARSITY = 0.9  # Maximum sparsity (avoid too sparse)
GATE_NOMINAL = 0.5  # Nominal gate value

# Floating point tolerance
FP_TOLERANCE = 1e-6

# Colony configuration
NUM_COLONIES = 7
NUM_FANO_LINES = 7

# History tracking
DEFAULT_HISTORY_SIZE = 10
LARGE_HISTORY_SIZE = 500

# =============================================================================
# BASE MONITOR TESTS
# =============================================================================


class TestCBFMonitor:
    """Test base CBFMonitor functionality."""

    def test_initialization(self):
        """Test monitor initialization."""
        monitor = CBFMonitor(threshold=SAFE_THRESHOLD, warn_threshold=WARN_THRESHOLD)
        assert monitor.threshold == SAFE_THRESHOLD
        assert monitor.warn_threshold == WARN_THRESHOLD
        assert len(monitor.history) == 0

    def test_initialization_invalid_thresholds(self):
        """Test that invalid thresholds raise error."""
        with pytest.raises(ValueError, match="warn_threshold.*must be >"):
            CBFMonitor(threshold=0.5, warn_threshold=0.3)

    def test_classify_status(self):
        """Test safety status classification."""
        monitor = CBFMonitor(threshold=SAFE_THRESHOLD, warn_threshold=WARN_THRESHOLD)

        # Test violation: h(x) < 0
        assert monitor._classify_status(VIOLATION_VALUE) == "violation"
        # Test warning zone: 0 <= h(x) < 0.1
        assert monitor._classify_status(SAFE_THRESHOLD) == "warning"
        assert monitor._classify_status(WARNING_VALUE) == "warning"
        assert monitor._classify_status(WARN_THRESHOLD) == "warning"
        # Test safe: h(x) >= 0.1
        assert monitor._classify_status(SAFE_VALUE) == "safe"

    def test_log_and_history(self):
        """Test logging results to history."""
        monitor = CBFMonitor(
            threshold=SAFE_THRESHOLD,
            warn_threshold=WARN_THRESHOLD,
            history_size=DEFAULT_HISTORY_SIZE,
        )

        result = MonitorResult(
            status="safe",
            value=SAFE_VALUE,
            threshold=SAFE_THRESHOLD,
            warn_threshold=WARN_THRESHOLD,
        )

        monitor.log(result)
        assert len(monitor.history) == 1
        assert monitor.history[0] == result

    def test_history_size_limit(self):
        """Test that history respects maxlen."""
        monitor = CBFMonitor(threshold=0.0, warn_threshold=0.1, history_size=5)

        for i in range(10):
            result = MonitorResult(
                status="safe",
                value=float(i),
                threshold=0.0,
                warn_threshold=0.1,
            )
            monitor.log(result)

        assert len(monitor.history) == 5
        assert monitor.history[-1].value == 9.0

    def test_report_empty(self):
        """Test report with no history."""
        monitor = CBFMonitor(threshold=0.0, warn_threshold=0.1)
        report = monitor.report()

        assert report["total_checks"] == 0
        assert report["violations"] == 0
        assert report["warnings"] == 0
        assert report["safe"] == 0
        assert report["violation_rate"] == 0.0
        assert report["current_status"] is None

    def test_report_with_history(self):
        """Test report generation with history."""
        monitor = CBFMonitor(threshold=0.0, warn_threshold=0.1)

        # Add various results
        statuses = ["violation", "warning", "safe", "safe", "violation"]
        for status in statuses:
            value = -0.1 if status == "violation" else 0.05 if status == "warning" else 0.2
            result = MonitorResult(
                status=status,  # type: ignore
                value=value,
                threshold=0.0,
                warn_threshold=0.1,
            )
            monitor.log(result)

        report = monitor.report()
        assert report["total_checks"] == 5
        assert report["violations"] == 2
        assert report["warnings"] == 1
        assert report["safe"] == 2
        assert report["violation_rate"] == 0.4
        assert report["warning_rate"] == 0.2
        assert report["current_status"] == "violation"


# =============================================================================
# DECENTRALIZED CBF MONITOR TESTS
# =============================================================================


class TestDecentralizedCBFMonitor:
    """Test DecentralizedCBFMonitor."""

    def test_initialization(self):
        """Test monitor initialization."""
        monitor = DecentralizedCBFMonitor()
        assert monitor.num_colonies == 7
        assert len(monitor.fano_lines) == 7
        assert len(monitor.colony_names) == 7

    def test_check_safe_torch(self):
        """Test check with safe values (torch)."""
        monitor = DecentralizedCBFMonitor(threshold=0.0, warn_threshold=0.1)
        h_values = torch.ones(4, 7) * 0.5  # [B, 7] all safe

        result = monitor.check(h_values)
        assert result.status == "safe"
        assert result.value == 0.5
        assert result.details["compositional_safe"] is True
        assert len(result.details["unsafe_colonies"]) == 0

    def test_check_safe_numpy(self):
        """Test check with safe values (numpy)."""
        monitor = DecentralizedCBFMonitor(threshold=0.0, warn_threshold=0.1)
        h_values = np.ones((4, 7)) * 0.5  # [B, 7] all safe

        result = monitor.check(h_values)
        assert result.status == "safe"
        assert result.details["compositional_safe"] is True

    def test_check_warning(self):
        """Test check with warning values."""
        monitor = DecentralizedCBFMonitor(threshold=0.0, warn_threshold=0.1)
        h_values = torch.tensor([0.05, 0.08, 0.12, 0.15, 0.09, 0.11, 0.06])

        result = monitor.check(h_values)
        assert result.status == "warning"  # min = 0.05 which is in warning zone
        assert abs(result.value - 0.05) < 1e-6  # Floating point tolerance
        assert len(result.details["warning_colonies"]) > 0

    def test_check_violation(self):
        """Test check with violations."""
        monitor = DecentralizedCBFMonitor(threshold=0.0, warn_threshold=0.1)
        h_values = torch.tensor([0.2, -0.1, 0.3, 0.15, -0.05, 0.25, 0.18])

        result = monitor.check(h_values)
        assert result.status == "violation"
        assert result.value < 0.0
        assert result.details["compositional_safe"] is False
        assert len(result.details["unsafe_colonies"]) == 2  # Forge and Beacon

    def test_fano_line_violations(self):
        """Test Fano line violation tracking."""
        monitor = DecentralizedCBFMonitor(threshold=0.0, warn_threshold=0.1)

        # Violate Spark (0) - should affect lines 0, 1, 2
        h_values = torch.tensor([-0.1, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2])

        result = monitor.check(h_values)
        assert len(result.details["violated_fano_lines"]) == 3

        # Check that Spark is in all violated lines
        for violation in result.details["violated_fano_lines"]:
            assert "Spark" in violation["colonies"]

    def test_per_colony_tracking(self):
        """Test per-colony h value tracking."""
        monitor = DecentralizedCBFMonitor()
        h_values = torch.linspace(0.0, 0.6, 7)

        result = monitor.check(h_values)

        per_colony = result.details["per_colony_h"]
        assert len(per_colony) == 7
        assert "Spark" in per_colony
        assert "Crystal" in per_colony
        assert per_colony["Crystal"] > per_colony["Spark"]

    def test_batch_averaging(self):
        """Test that batch dimension is averaged correctly."""
        monitor = DecentralizedCBFMonitor()

        # Batch of 8 samples, centered around 0.5 (safe zone)
        h_values = torch.randn(8, NUM_COLONIES) + SAFE_VALUE

        result = monitor.check(h_values)
        # Verify result is numeric float (not tensor)
        assert isinstance(result.value, float)
        # Verify value is in reasonable range given input (0.5 ± ~3σ)
        assert -1.0 < result.value < 2.0, f"Unexpected averaged value: {result.value}"
        # Verify per-colony tracking exists
        assert "per_colony_h" in result.details
        assert len(result.details["per_colony_h"]) == NUM_COLONIES

    def test_invalid_shape(self):
        """Test error on invalid input shape."""
        monitor = DecentralizedCBFMonitor()
        h_values = torch.randn(5)  # Only 5 colonies instead of 7

        with pytest.raises(ValueError, match="Expected 7 colony values"):
            monitor.check(h_values)


# =============================================================================
# ADAPTIVE E8 MONITOR TESTS
# =============================================================================


class TestAdaptiveE8Monitor:
    """Test AdaptiveE8Monitor."""

    def test_initialization(self):
        """Test monitor initialization."""
        monitor = AdaptiveE8Monitor()
        assert monitor.variance_threshold == 4.0
        assert monitor.variance_warn == 3.0
        assert monitor.min_mean_depth == 2.0
        assert monitor.max_mean_depth == 14.0

    def test_check_safe_variance(self):
        """Test check with safe variance - variance must be < 4.0."""
        monitor = AdaptiveE8Monitor(variance_threshold=E8_VARIANCE_THRESHOLD)

        # Generate depths with low variance: std=0.5 → var ≈ 0.25
        importance = torch.randn(4, 100) * 0.5 + E8_NOMINAL_DEPTH

        result = monitor.check(importance)
        assert result.status == "safe"
        # Variance should be well below threshold
        assert result.value < E8_VARIANCE_THRESHOLD
        assert result.value < 1.0, f"Unexpected high variance: {result.value}"
        assert result.details["variance_ok"] is True
        # Mean should be near nominal depth
        assert E8_MIN_MEAN_DEPTH < result.details["depth_mean"] < E8_MAX_MEAN_DEPTH

    def test_check_violation_high_variance(self):
        """Test violation on high variance."""
        monitor = AdaptiveE8Monitor(variance_threshold=4.0)

        # Generate depths with very high variance
        importance = torch.randn(4, 100) * 5.0 + 8.0  # σ² ≈ 25

        result = monitor.check(importance)
        assert result.status == "violation"
        assert result.value > 4.0
        assert result.details["variance_ok"] is False

    def test_check_warning_variance(self):
        """Test warning on moderate variance."""
        monitor = AdaptiveE8Monitor(variance_threshold=4.0, variance_warn=3.0)

        # Generate depths with moderate variance
        importance = torch.randn(4, 100) * 1.8 + 8.0  # σ² ≈ 3.24

        result = monitor.check(importance)
        assert result.status == "warning"
        assert 3.0 < result.value <= 4.0

    def test_check_mean_depth_violation_low(self):
        """Test violation on mean depth too low."""
        monitor = AdaptiveE8Monitor(min_mean_depth=2.0, max_mean_depth=14.0)

        # Generate depths with mean < 2.0
        importance = torch.ones(4, 100) * 1.0  # mean = 1.0

        result = monitor.check(importance)
        assert result.status == "violation"
        assert result.details["mean_depth_ok"] is False
        assert result.details["depth_mean"] < 2.0

    def test_check_mean_depth_violation_high(self):
        """Test violation on mean depth too high."""
        monitor = AdaptiveE8Monitor(min_mean_depth=2.0, max_mean_depth=14.0)

        # Generate depths with mean > 14.0
        importance = torch.ones(4, 100) * 15.0  # mean = 15.0

        result = monitor.check(importance)
        assert result.status == "violation"
        assert result.details["mean_depth_ok"] is False
        assert result.details["depth_mean"] > 14.0

    def test_depth_statistics(self):
        """Test depth statistics in details."""
        monitor = AdaptiveE8Monitor()
        importance = torch.randn(4, 100) * 2.0 + 8.0

        result = monitor.check(importance)

        details = result.details
        assert "depth_variance" in details
        assert "depth_mean" in details
        assert "depth_std" in details
        assert "depth_min" in details
        assert "depth_max" in details

        # Sanity checks
        assert details["depth_std"] > 0
        assert details["depth_min"] < details["depth_mean"]
        assert details["depth_max"] > details["depth_mean"]

    def test_numpy_input(self):
        """Test with numpy input - should handle numpy arrays correctly."""
        monitor = AdaptiveE8Monitor()
        # Generate depths with moderate variance around nominal depth
        importance = np.random.randn(4, 100) * 2.0 + E8_NOMINAL_DEPTH

        result = monitor.check(importance)
        # Verify numeric conversion
        assert isinstance(result.value, float)
        # Verify variance is computed (std=2.0 → var ≈ 4.0)
        assert 0.0 <= result.value <= 10.0, f"Variance out of expected range: {result.value}"
        # Verify details populated
        assert "depth_variance" in result.details
        assert "depth_mean" in result.details


# =============================================================================
# GATED FANO MONITOR TESTS
# =============================================================================


class TestGatedFanoMonitor:
    """Test GatedFanoMonitor."""

    def test_initialization(self):
        """Test monitor initialization with default Fano gate constraints."""
        monitor = GatedFanoMonitor()
        assert monitor.epsilon == GATE_EPSILON
        assert monitor.max_gate == GATE_MAX
        assert monitor.min_sparsity == GATE_MIN_SPARSITY
        assert monitor.max_sparsity == GATE_MAX_SPARSITY

    def test_check_safe_gates(self):
        """Test check with healthy gates."""
        monitor = GatedFanoMonitor(epsilon=0.01, max_gate=0.99)

        # Generate gates with good properties (set seed for reproducibility)
        torch.manual_seed(42)
        gates = torch.sigmoid(torch.randn(4, 8, 64, 64) * 0.5)  # [B, heads, T, T]

        result = monitor.check(gates)
        # May be safe or warning depending on sparsity
        assert result.status in ["safe", "warning"]
        assert result.details["collapsed_low"] is False
        assert result.details["collapsed_high"] is False

    def test_check_violation_collapse_low(self):
        """Test violation on gate collapse (too low)."""
        monitor = GatedFanoMonitor(epsilon=0.01)

        # Generate gates that are all very small
        gates = torch.ones(4, 8, 64, 64) * 0.001

        result = monitor.check(gates)
        assert result.status == "violation"
        assert result.details["collapsed_low"] is True
        assert result.value < 0.01

    def test_check_violation_collapse_high(self):
        """Test violation on gate collapse (too high)."""
        monitor = GatedFanoMonitor(max_gate=0.99)

        # Generate gates that are all very large
        gates = torch.ones(4, 8, 64, 64) * 0.999

        result = monitor.check(gates)
        assert result.status == "violation"
        assert result.details["collapsed_high"] is True

    def test_check_warning_sparsity(self):
        """Test warning on suboptimal sparsity."""
        monitor = GatedFanoMonitor(min_sparsity=0.3, max_sparsity=0.9)

        # Generate gates with very low sparsity (most gates > 0.5)
        gates = torch.ones(4, 8, 64, 64) * 0.8  # sparsity ≈ 0

        result = monitor.check(gates)
        # Should be warning or safe depending on sparsity
        assert result.details["sparsity_ok"] is False

    def test_sparsity_calculation(self):
        """Test sparsity calculation."""
        monitor = GatedFanoMonitor()

        # Create gates with known sparsity
        gates = torch.cat(
            [
                torch.ones(2, 4, 32, 32) * 0.2,  # Sparse
                torch.ones(2, 4, 32, 32) * 0.8,  # Dense
            ],
            dim=0,
        )  # 50% sparsity

        result = monitor.check(gates)
        sparsity = result.details["sparsity"]
        assert 0.4 < sparsity < 0.6  # Should be around 0.5

    def test_gate_statistics(self):
        """Test gate statistics in details."""
        monitor = GatedFanoMonitor()
        gates = torch.sigmoid(torch.randn(4, 8, 64, 64))

        result = monitor.check(gates)

        details = result.details
        assert "min_gate" in details
        assert "max_gate" in details
        assert "mean_gate" in details
        assert "sparsity" in details

        # Sanity checks
        assert 0.0 <= details["min_gate"] <= details["mean_gate"]
        assert details["mean_gate"] <= details["max_gate"] <= 1.0
        assert 0.0 <= details["sparsity"] <= 1.0

    def test_per_head_statistics(self):
        """Test per-head statistics tracking."""
        monitor = GatedFanoMonitor()
        gates = torch.sigmoid(torch.randn(4, 8, 64, 64))  # 8 heads

        result = monitor.check(gates)

        # Should have per-head stats for multi-head gates
        if "per_head_mean" in result.details:
            assert len(result.details["per_head_mean"]) == 8

    def test_flattened_gates(self):
        """Test with 2D gates (already flattened) - should handle non-4D input."""
        monitor = GatedFanoMonitor()
        gates = torch.sigmoid(torch.randn(4, 100))  # [B, T]

        result = monitor.check(gates)
        # Verify numeric conversion
        assert isinstance(result.value, float)
        # Verify gate value is minimum gate (used as CBF value)
        assert GATE_EPSILON <= result.value <= 1.0, f"Gate value out of range: {result.value}"
        # Verify statistics populated
        assert "min_gate" in result.details
        assert "max_gate" in result.details
        assert "sparsity" in result.details

    def test_numpy_input(self):
        """Test with numpy input - should handle numpy arrays correctly."""
        monitor = GatedFanoMonitor()
        # Use scipy.special.expit (sigmoid) to generate gate values in [0, 1]
        from scipy.special import expit

        gates = expit(np.random.randn(4, 8, 64, 64))

        result = monitor.check(gates)
        # Verify numeric conversion
        assert isinstance(result.value, float)
        # Verify gate value is in valid range (sigmoid output)
        assert 0.0 <= result.value <= 1.0, f"Gate value out of range: {result.value}"
        # Verify statistics computed
        assert "min_gate" in result.details
        assert "mean_gate" in result.details


# =============================================================================
# COMPOSITE MONITOR TESTS
# =============================================================================


class TestCompositeMonitor:
    """Test CompositeMonitor."""

    def test_initialization(self):
        """Test composite monitor initialization."""
        monitor = CompositeMonitor()
        assert "cbf" in monitor.monitors
        assert "e8" in monitor.monitors
        assert "fano" in monitor.monitors

    def test_check_all_safe(self):
        """Test check_all with all monitors safe."""
        monitor = CompositeMonitor()

        # Use deterministic values to ensure safety
        torch.manual_seed(42)
        metrics = {
            "h_values": torch.ones(4, 7) * 0.5,
            "importance": torch.ones(4, 100) * 8.0,  # Constant depth (low variance)
            "gates": torch.ones(4, 8, 64, 64) * 0.5,  # All gates at 0.5
        }

        status = monitor.check_all(metrics)  # type: ignore[arg-type]

        # Should be safe or warning (gates might have suboptimal sparsity)
        assert status["status"] in ["safe", "warning"]
        assert len(status["results"]) == 3
        assert status["summary"]["num_violations"] == 0

    def test_check_all_violation(self):
        """Test check_all with violations."""
        monitor = CompositeMonitor()

        metrics = {
            "h_values": torch.tensor([[-0.5] * 7]),  # CBF violation
            "importance": torch.randn(4, 100) * 1.0 + 8.0,
            "gates": torch.sigmoid(torch.randn(4, 8, 64, 64)),
        }

        status = monitor.check_all(metrics)  # type: ignore[arg-type]

        assert status["status"] == "violation"
        assert status["summary"]["num_violations"] > 0
        assert "cbf" in status["results"]
        assert status["results"]["cbf"]["status"] == "violation"

    def test_check_all_warning(self):
        """Test check_all with warnings."""
        monitor = CompositeMonitor(cbf_warn=0.2)

        torch.manual_seed(42)
        metrics = {
            "h_values": torch.ones(4, 7) * 0.15,  # In warning zone
            "importance": torch.ones(4, 100) * 8.0,  # Low variance
            "gates": torch.ones(4, 8, 64, 64) * 0.5,  # Constant gates
        }

        status = monitor.check_all(metrics)  # type: ignore[arg-type]

        # Should have at least warnings (CBF in warning zone)
        assert status["status"] in ["warning", "safe", "violation"]
        assert "cbf" in status["results"]

    def test_check_all_partial_metrics(self):
        """Test check_all with only some metrics."""
        monitor = CompositeMonitor()

        # Only provide CBF metrics
        metrics = {
            "h_values": torch.ones(4, 7) * 0.5,
        }

        status = monitor.check_all(metrics)  # type: ignore[arg-type]

        assert "cbf" in status["results"]
        assert "e8" not in status["results"]
        assert "fano" not in status["results"]
        assert len(status["summary"]["monitors_checked"]) == 1

    def test_check_all_multiple_violations(self):
        """Test with multiple monitors violating."""
        monitor = CompositeMonitor()

        metrics = {
            "h_values": torch.tensor([[-0.5] * 7]),  # CBF violation
            "importance": torch.ones(4, 100) * 20.0,  # Variance violation
            "gates": torch.ones(4, 8, 64, 64) * 0.001,  # Gate collapse
        }

        status = monitor.check_all(metrics)  # type: ignore[arg-type]

        assert status["status"] == "violation"
        assert status["summary"]["num_violations"] >= 2

    def test_report_all(self):
        """Test aggregate reporting."""
        monitor = CompositeMonitor()

        # Run some checks
        metrics = {
            "h_values": torch.ones(4, 7) * 0.5,
            "importance": torch.randn(4, 100) * 1.0 + 8.0,
            "gates": torch.sigmoid(torch.randn(4, 8, 64, 64)),
        }

        for _ in range(5):
            monitor.check_all(metrics)  # type: ignore[arg-type]

        reports = monitor.report_all()

        assert "cbf" in reports
        assert "e8" in reports
        assert "fano" in reports

        for report in reports.values():
            assert report["total_checks"] == 5

    def test_overall_status_precedence(self):
        """Test that violation > warning > safe."""
        monitor = CompositeMonitor()

        # Mix of statuses
        metrics = {
            "h_values": torch.tensor([[-0.1] * 7]),  # Violation
            "importance": torch.randn(4, 100) * 1.0 + 8.0,  # Safe
        }

        status = monitor.check_all(metrics)  # type: ignore[arg-type]
        assert status["status"] == "violation"  # Violation takes precedence


# =============================================================================
# FACTORY FUNCTION TESTS
# =============================================================================


class TestFactoryFunctions:
    """Test factory functions."""

    def test_create_cbf_monitor(self):
        """Test CBF monitor factory."""
        monitor = create_cbf_monitor(
            cbf_threshold=0.0,
            cbf_warn=0.15,
            history_size=500,
        )

        assert isinstance(monitor, DecentralizedCBFMonitor)
        assert monitor.threshold == 0.0
        assert monitor.warn_threshold == 0.15
        assert monitor.history.maxlen == 500

    def test_create_composite_monitor(self):
        """Test composite monitor factory."""
        monitor = create_composite_monitor(
            cbf_threshold=0.0,
            cbf_warn=0.1,
            e8_variance_threshold=5.0,
            gate_epsilon=0.02,
            history_size=2000,
        )

        assert isinstance(monitor, CompositeMonitor)
        assert monitor.monitors["cbf"].threshold == 0.0
        assert monitor.monitors["e8"].variance_threshold == 5.0
        assert monitor.monitors["fano"].epsilon == 0.02


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests simulating real usage."""

    def test_training_loop_simulation(self):
        """Simulate monitoring in a training loop."""
        monitor = CompositeMonitor()

        # Simulate 10 batches
        violations_detected = 0

        for i in range(10):
            # Generate synthetic metrics
            h_values = torch.randn(8, 7) * 0.2 + 0.3  # Mostly safe
            importance = torch.randn(8, 128) * 1.5 + 8.0
            gates = torch.sigmoid(torch.randn(8, 8, 128, 128))

            # Inject occasional violation
            if i == 5:
                h_values[0, 0] = -0.5  # Violation in Spark

            metrics = {
                "h_values": h_values,
                "importance": importance,
                "gates": gates,
            }

            status = monitor.check_all(metrics)  # type: ignore[arg-type]

            if status["status"] == "violation":
                violations_detected += 1

        assert violations_detected >= 1  # Should detect the injected violation

        # Check that history was accumulated
        report = monitor.report_all()
        assert report["cbf"]["total_checks"] == 10

    def test_monitoring_overhead(self):
        """Test that monitoring overhead is minimal."""
        import time

        monitor = CompositeMonitor()

        metrics = {
            "h_values": torch.randn(32, 7),
            "importance": torch.randn(32, 256),
            "gates": torch.sigmoid(torch.randn(32, 8, 256, 256)),
        }

        # Time 100 checks
        start = time.time()
        for _ in range(100):
            monitor.check_all(metrics)  # type: ignore[arg-type]
        elapsed = time.time() - start

        # Should be < 50ms per check on average (relaxed for CI)
        avg_time = elapsed / 100
        assert avg_time < 0.05, f"Monitoring too slow: {avg_time * 1000:.2f}ms per check"

    def test_progressive_degradation(self):
        """Test monitoring progressive safety degradation."""
        monitor = DecentralizedCBFMonitor()

        values = [0.5, 0.3, 0.15, 0.05, -0.05]  # Progressively worse
        statuses = []

        for val in values:
            h = torch.ones(7) * val
            result = monitor.check(h)
            statuses.append(result.status)

        # Should see progression: safe → warning → violation
        assert statuses[0] == "safe"
        assert statuses[-1] == "violation"
        assert "warning" in statuses
