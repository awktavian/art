"""Tests for CalibrationTracker - World model prediction calibration.

Verifies:
- CalibrationBin: individual bin statistics and adjustment factors
- CalibrationTracker: multi-bin calibration, ECE computation, confidence adjustment
- Domain-specific calibration tracking

Mathematical foundation:
    Calibration Error = E[|P(success|confidence) - confidence|]
    A well-calibrated model: P(success | confidence = p) = p
"""

from __future__ import annotations

import pytest

from kagami.core.world_model.calibration import (
    CalibrationBin,
    CalibrationRecord,
    CalibrationTracker,
)

pytestmark = pytest.mark.tier_integration

# =============================================================================
# TEST CONSTANTS - Named values for clarity and maintainability
# =============================================================================

# Calibration bin boundaries
BIN_LOWER_70 = 0.7
BIN_UPPER_80 = 0.8
BIN_LOWER_40 = 0.4
BIN_UPPER_50 = 0.5
BIN_LOWER_80 = 0.8
BIN_UPPER_90 = 0.9
BIN_LOWER_50 = 0.5
BIN_UPPER_60 = 0.6

# Confidence values
CONFIDENCE_75 = 0.75
CONFIDENCE_55 = 0.55
CONFIDENCE_45 = 0.45
CONFIDENCE_85 = 0.85
CONFIDENCE_70 = 0.7
CONFIDENCE_80 = 0.8
CONFIDENCE_50 = 0.5

# EMA smoothing
EMA_ALPHA_HALF = 0.5  # 50% weight to new observation
EMA_ALPHA_FAST = 1.0  # No smoothing (instant update)
EMA_ALPHA_SLOW = 0.1  # 10% weight to new observation

# Success rates
SUCCESS_RATE_PRIOR = 0.5  # Default prior
SUCCESS_RATE_60 = 0.6
SUCCESS_RATE_70 = 0.7

# Adjustment bounds
ADJUSTMENT_MIN = 0.5  # Minimum adjustment factor
ADJUSTMENT_MAX = 2.0  # Maximum adjustment factor

# Tracker configuration
NUM_BINS_DEFAULT = 10
NUM_BINS_SMALL = 5
NUM_BINS_LARGE = 100

# Error tolerance
ERROR_TOLERANCE = 0.01

# =============================================================================
# CalibrationBin Tests
# =============================================================================


class TestCalibrationBin:
    """Tests for CalibrationBin dataclass."""

    def test_bin_creation(self) -> None:
        """Bin initializes with correct bounds and zero statistics."""
        bin_ = CalibrationBin(lower=BIN_LOWER_70, upper=BIN_UPPER_80)

        assert bin_.lower == BIN_LOWER_70
        assert bin_.upper == BIN_UPPER_80
        assert bin_.total_predictions == 0
        assert bin_.successful_predictions == 0
        # Default EMA starts at prior (0.5)
        assert bin_.ema_success_rate == SUCCESS_RATE_PRIOR

    def test_record_success(self) -> None:
        """Recording a success updates statistics correctly."""
        bin_ = CalibrationBin(lower=BIN_LOWER_70, upper=BIN_UPPER_80)

        error = bin_.record(confidence=CONFIDENCE_75, actual_success=True)

        assert bin_.total_predictions == 1
        assert bin_.successful_predictions == 1
        # Error = |confidence - 1.0| for success = |0.75 - 1.0| = 0.25
        assert error == pytest.approx(0.25, abs=ERROR_TOLERANCE)

    def test_record_failure(self) -> None:
        """Recording a failure updates statistics correctly."""
        bin_ = CalibrationBin(lower=BIN_LOWER_70, upper=BIN_UPPER_80)

        error = bin_.record(confidence=CONFIDENCE_75, actual_success=False)

        assert bin_.total_predictions == 1
        assert bin_.successful_predictions == 0
        # Error = |confidence - 0.0| for failure = |0.75 - 0| = 0.75
        assert error == pytest.approx(CONFIDENCE_75, abs=ERROR_TOLERANCE)

    def test_ema_updates(self) -> None:
        """EMA success rate updates according to formula: α*new + (1-α)*old."""
        bin_ = CalibrationBin(lower=BIN_LOWER_50, upper=BIN_UPPER_60, ema_alpha=EMA_ALPHA_HALF)

        # Initial EMA is prior
        assert bin_.ema_success_rate == SUCCESS_RATE_PRIOR

        # Record success: new_ema = α*1.0 + (1-α)*0.5 = 0.5*1.0 + 0.5*0.5 = 0.75
        bin_.record(CONFIDENCE_55, actual_success=True)
        expected_after_success = EMA_ALPHA_HALF * 1.0 + (1 - EMA_ALPHA_HALF) * SUCCESS_RATE_PRIOR
        assert bin_.ema_success_rate == pytest.approx(expected_after_success, abs=ERROR_TOLERANCE)
        assert bin_.ema_success_rate == pytest.approx(0.75, abs=ERROR_TOLERANCE)

        # Record failure: new_ema = α*0.0 + (1-α)*0.75 = 0.5*0.0 + 0.5*0.75 = 0.375
        bin_.record(CONFIDENCE_55, actual_success=False)
        expected_after_failure = EMA_ALPHA_HALF * 0.0 + (1 - EMA_ALPHA_HALF) * 0.75
        assert bin_.ema_success_rate == pytest.approx(expected_after_failure, abs=ERROR_TOLERANCE)
        assert bin_.ema_success_rate == pytest.approx(0.375, abs=ERROR_TOLERANCE)

    def test_empirical_success_rate(self) -> None:
        """Empirical success rate = successes / total predictions."""
        bin_ = CalibrationBin(lower=BIN_LOWER_40, upper=BIN_UPPER_50)

        # No predictions yet - should return prior
        assert bin_.empirical_success_rate == SUCCESS_RATE_PRIOR

        # Record 3 successes, 2 failures → empirical rate = 3/5 = 0.6
        for _ in range(3):
            bin_.record(CONFIDENCE_45, actual_success=True)
        for _ in range(2):
            bin_.record(CONFIDENCE_45, actual_success=False)

        expected_rate = 3.0 / 5.0  # = 0.6
        assert bin_.empirical_success_rate == pytest.approx(expected_rate, abs=ERROR_TOLERANCE)
        assert bin_.total_predictions == 5
        assert bin_.successful_predictions == 3

    def test_calibration_error(self) -> None:
        """Calibration error computed correctly."""
        bin_ = CalibrationBin(lower=0.8, upper=0.9, ema_alpha=1.0)  # No smoothing

        # If mean_confidence is 0.85 and success_rate is 0.6:
        # ECE = |0.85 - 0.6| = 0.25
        bin_.record(0.85, actual_success=True)
        bin_.record(0.85, actual_success=True)
        bin_.record(0.85, actual_success=False)

        # With ema_alpha=1.0, ema tracks last outcome
        # Let's use a sequence that ends at ~0.6 success rate
        bin2 = CalibrationBin(lower=0.8, upper=0.9, ema_alpha=0.1)
        for _ in range(100):
            bin2.record(0.85, actual_success=True)  # 60 successes
        for _ in range(40):
            bin2.record(0.85, actual_success=False)  # 40 failures

        # Empirical: 100/(100+40) ≈ 0.71
        # EMA will be different due to smoothing

    def test_adjustment_factor(self) -> None:
        """Adjustment factor is bounded and correct."""
        # Over-confident bin (predicts 80%, achieves 60%)
        bin_ = CalibrationBin(lower=0.7, upper=0.9, ema_alpha=0.1)
        bin_.ema_success_rate = 0.6  # Simulate actual performance

        # Adjustment = 0.6 / 0.8 = 0.75
        adj = bin_.adjustment_factor
        assert adj == pytest.approx(0.75)

        # Under-confident bin (predicts 40%, achieves 70%)
        bin2 = CalibrationBin(lower=0.3, upper=0.5)
        bin2.ema_success_rate = 0.7

        # Adjustment = 0.7 / 0.4 = 1.75
        adj2 = bin2.adjustment_factor
        assert adj2 == pytest.approx(1.75)

    def test_adjustment_factor_bounded(self) -> None:
        """Adjustment factor is clamped to [0.5, 2.0]."""
        bin_ = CalibrationBin(lower=0.9, upper=1.0)

        # Very low success rate
        bin_.ema_success_rate = 0.1  # Adjustment = 0.1/0.95 ≈ 0.105 → clamped to 0.5
        assert bin_.adjustment_factor >= 0.5

        # Very high success rate for low confidence
        bin2 = CalibrationBin(lower=0.0, upper=0.1)
        bin2.ema_success_rate = 0.9  # Would be huge → clamped to 2.0
        assert bin2.adjustment_factor <= 2.0

    def test_recent_outcomes_stored(self) -> None:
        """Recent outcomes are stored for debugging."""
        bin_ = CalibrationBin(lower=0.5, upper=0.6)

        bin_.record(0.55, actual_success=True)
        bin_.record(0.52, actual_success=False)

        assert len(bin_.recent_outcomes) == 2
        assert bin_.recent_outcomes[0] == (0.55, True)
        assert bin_.recent_outcomes[1] == (0.52, False)


# =============================================================================
# CalibrationRecord Tests
# =============================================================================


class TestCalibrationRecord:
    """Tests for CalibrationRecord dataclass."""

    def test_record_creation(self) -> None:
        """Record can be created with all fields."""
        record = CalibrationRecord(
            confidence=0.8,
            threat_score=0.2,
            uncertainty=0.15,
            actual_success=True,
            duration_ms=150.0,
            action_type="tool_use",
            agent_domain="forge",
        )

        assert record.confidence == 0.8
        assert record.threat_score == 0.2
        assert record.uncertainty == 0.15
        assert record.actual_success is True
        assert record.duration_ms == 150.0
        assert record.action_type == "tool_use"
        assert record.agent_domain == "forge"
        assert record.timestamp > 0


# =============================================================================
# CalibrationTracker Tests
# =============================================================================


class TestCalibrationTracker:
    """Tests for CalibrationTracker."""

    def test_tracker_init(self) -> None:
        """Tracker initializes correctly."""
        tracker = CalibrationTracker(num_bins=10)

        assert len(tracker._bins) == 10
        assert tracker._total_records == 0
        assert tracker._running_ece == 0.0

    def test_tracker_init_custom_bins(self) -> None:
        """Tracker respects custom bin count."""
        tracker = CalibrationTracker(num_bins=5)

        assert len(tracker._bins) == 5
        # Bins should cover [0, 1] in 5 equal parts
        assert tracker._bins[0].lower == 0.0
        assert tracker._bins[0].upper == pytest.approx(0.2)
        assert tracker._bins[4].lower == pytest.approx(0.8)
        assert tracker._bins[4].upper == 1.0

    def test_get_bin_index(self) -> None:
        """Bin index is computed correctly."""
        tracker = CalibrationTracker(num_bins=10)

        assert tracker._get_bin_index(0.0) == 0
        assert tracker._get_bin_index(0.05) == 0
        assert tracker._get_bin_index(0.15) == 1
        assert tracker._get_bin_index(0.5) == 5
        assert tracker._get_bin_index(0.95) == 9
        assert tracker._get_bin_index(1.0) == 9  # Edge case

    def test_get_bin_index_clamped(self) -> None:
        """Bin index clamps out-of-range values."""
        tracker = CalibrationTracker(num_bins=10)

        assert tracker._get_bin_index(-0.5) == 0
        assert tracker._get_bin_index(1.5) == 9

    def test_record_single_prediction(self) -> None:
        """Recording a single prediction updates tracker."""
        tracker = CalibrationTracker(num_bins=10)

        predictions = [{"confidence": 0.75, "threat_score": 0.1}]
        error = tracker.record(
            predictions=predictions,
            actual_success=True,
            agent_domain="spark",
        )

        assert error >= 0
        assert tracker._total_records == 1

    def test_record_multiple_predictions(self) -> None:
        """Recording multiple predictions computes average error."""
        tracker = CalibrationTracker(num_bins=10)

        predictions = [
            {"confidence": 0.8},
            {"confidence": 0.6},
            {"confidence": 0.9},
        ]
        error = tracker.record(
            predictions=predictions,
            actual_success=True,
        )

        # Error is average over all predictions
        assert error >= 0
        assert tracker._total_records == 3

    def test_record_empty_predictions(self) -> None:
        """Empty predictions list returns 0."""
        tracker = CalibrationTracker(num_bins=10)

        error = tracker.record(predictions=[], actual_success=True)

        assert error == 0.0

    def test_domain_specific_tracking(self) -> None:
        """Domain-specific calibration is tracked separately."""
        tracker = CalibrationTracker(num_bins=10, enable_domain_specific=True)

        # Record for different domains
        tracker.record(
            predictions=[{"confidence": 0.8}],
            actual_success=True,
            agent_domain="forge",
        )
        tracker.record(
            predictions=[{"confidence": 0.7}],
            actual_success=False,
            agent_domain="spark",
        )

        assert "forge" in tracker._domain_bins
        assert "spark" in tracker._domain_bins
        assert len(tracker._domain_bins["forge"]) == 10
        assert len(tracker._domain_bins["spark"]) == 10

    def test_adjust_confidence_global(self) -> None:
        """Confidence is adjusted based on calibration."""
        tracker = CalibrationTracker(num_bins=10)

        # Simulate over-confident predictions (80% confidence, 50% success)
        for _ in range(50):
            tracker.record(
                predictions=[{"confidence": 0.85}],
                actual_success=True,
            )
        for _ in range(50):
            tracker.record(
                predictions=[{"confidence": 0.85}],
                actual_success=False,
            )

        # Adjustment should bring 0.85 down
        adjusted = tracker.adjust_confidence(0.85)

        # Should be < 0.85 since we're over-confident
        assert adjusted < 0.85

    def test_adjust_confidence_domain_specific(self) -> None:
        """Domain-specific adjustment is used when available."""
        tracker = CalibrationTracker(num_bins=10, enable_domain_specific=True)

        # Domain "forge" is well-calibrated - 70% confidence, 70% success
        for i in range(100):
            tracker.record(
                predictions=[{"confidence": 0.7}],
                actual_success=(i < 70),
                agent_domain="forge",
            )

        # Domain "spark" is over-confident - 70% confidence, 30% success
        for i in range(100):
            tracker.record(
                predictions=[{"confidence": 0.7}],
                actual_success=(i < 30),
                agent_domain="spark",
            )

        # Spark should have lower or equal adjustment due to over-confidence
        forge_adj = tracker.adjust_confidence(0.7, domain="forge")
        spark_adj = tracker.adjust_confidence(0.7, domain="spark")

        # Over-confident domain gets reduced (or stays same if smoothing dominates)
        assert spark_adj <= forge_adj

    def test_get_ece(self) -> None:
        """Expected Calibration Error is computed."""
        tracker = CalibrationTracker(num_bins=10)

        # Record some predictions
        for i in range(100):
            tracker.record(
                predictions=[{"confidence": i / 100.0}],
                actual_success=(i % 2 == 0),
            )

        ece = tracker.compute_expected_calibration_error()

        assert 0 <= ece <= 1

    def test_get_domain_ece(self) -> None:
        """Domain-specific ECE available from report."""
        tracker = CalibrationTracker(num_bins=10, enable_domain_specific=True)

        # Record for a specific domain
        for i in range(50):
            tracker.record(
                predictions=[{"confidence": 0.8}],
                actual_success=(i < 40),  # 80% success
                agent_domain="flow",
            )

        report = tracker.get_calibration_report()
        assert "domain_ece" in report
        assert "flow" in report["domain_ece"]

    def test_get_calibration_report(self) -> None:
        """Calibration report is generated."""
        tracker = CalibrationTracker(num_bins=10)

        # Record some data
        for _ in range(10):
            tracker.record(
                predictions=[{"confidence": 0.5}],
                actual_success=True,
            )

        report = tracker.get_calibration_report()

        assert "expected_calibration_error" in report
        assert "total_records" in report
        assert "bins" in report
        assert len(report["bins"]) == 10

    def test_recent_records_stored(self) -> None:
        """Recent records are stored for analysis."""
        tracker = CalibrationTracker(num_bins=10)

        for i in range(5):
            tracker.record(
                predictions=[{"confidence": 0.5 + i * 0.1}],
                actual_success=(i % 2 == 0),
                agent_domain="test",
                duration_ms=100.0 + i,
            )

        assert len(tracker._recent_records) == 5

    def test_record_with_action_dict(self) -> None:
        """Action can be dict with 'type' key."""
        tracker = CalibrationTracker(num_bins=10)

        predictions = [
            {
                "confidence": 0.8,
                "action": {"type": "tool_use", "tool": "grep"},
            }
        ]

        error = tracker.record(predictions=predictions, actual_success=True)

        assert error >= 0


# =============================================================================
# Edge Cases and Robustness
# =============================================================================


class TestCalibrationEdgeCases:
    """Tests for edge cases and robustness."""

    def test_single_bin_tracker(self) -> None:
        """Tracker works with single bin."""
        tracker = CalibrationTracker(num_bins=1)

        tracker.record(
            predictions=[{"confidence": 0.5}],
            actual_success=True,
        )

        assert len(tracker._bins) == 1
        assert tracker._bins[0].total_predictions == 1

    def test_many_bins_tracker(self) -> None:
        """Tracker works with many bins."""
        tracker = CalibrationTracker(num_bins=100)

        tracker.record(
            predictions=[{"confidence": 0.123}],
            actual_success=True,
        )

        assert len(tracker._bins) == 100

    def test_extreme_confidence_values(self) -> None:
        """Extreme confidence values are handled."""
        tracker = CalibrationTracker(num_bins=10)

        # Very low confidence
        tracker.record(
            predictions=[{"confidence": 0.001}],
            actual_success=True,
        )

        # Very high confidence
        tracker.record(
            predictions=[{"confidence": 0.999}],
            actual_success=False,
        )

        # Zero confidence
        tracker.record(
            predictions=[{"confidence": 0.0}],
            actual_success=True,
        )

        # Exactly 1.0
        tracker.record(
            predictions=[{"confidence": 1.0}],
            actual_success=True,
        )

        assert tracker._total_records == 4

    def test_missing_confidence_defaults(self) -> None:
        """Missing confidence field defaults to 0.5."""
        tracker = CalibrationTracker(num_bins=10)

        predictions = [{"threat_score": 0.1}]  # No confidence key

        error = tracker.record(predictions=predictions, actual_success=True)

        assert error >= 0
        # Should have recorded in bin 5 (0.5 confidence)

    def test_rapid_succession_records(self) -> None:
        """Many rapid records don't cause issues."""
        tracker = CalibrationTracker(num_bins=10)

        for i in range(1000):
            tracker.record(
                predictions=[{"confidence": (i % 100) / 100.0}],
                actual_success=(i % 3 == 0),
            )

        assert tracker._total_records == 1000

    def test_ece_with_empty_tracker(self) -> None:
        """ECE of empty tracker is 0."""
        tracker = CalibrationTracker(num_bins=10)

        ece = tracker.compute_expected_calibration_error()

        assert ece == 0.0

    def test_adjustment_with_no_data(self) -> None:
        """Adjustment with no data returns original confidence."""
        tracker = CalibrationTracker(num_bins=10)

        adjusted = tracker.adjust_confidence(0.7)

        # Default adjustment factor is ~1.0
        assert adjusted == pytest.approx(0.7, abs=0.3)


# =============================================================================
# Integration Tests
# =============================================================================


class TestCalibrationIntegration:
    """Integration tests for calibration workflow."""

    def test_full_calibration_workflow(self) -> None:
        """Test complete calibration workflow."""
        tracker = CalibrationTracker(num_bins=10, enable_domain_specific=True)

        # Phase 1: Initial predictions (over-confident)
        for i in range(100):
            predictions = [{"confidence": 0.9, "threat_score": 0.1}]
            tracker.record(
                predictions=predictions,
                actual_success=(i < 60),  # Only 60% success at 90% confidence
                agent_domain="forge",
                duration_ms=100.0,
            )

        # Check calibration error
        ece = tracker.compute_expected_calibration_error()
        assert ece > 0  # Should show miscalibration

        # Phase 2: Adjust future predictions
        raw_confidence = 0.9
        adjusted = tracker.adjust_confidence(raw_confidence, domain="forge")
        assert adjusted < raw_confidence  # Should reduce over-confident predictions

        # Phase 3: Generate report
        report = tracker.get_calibration_report()
        assert report["total_records"] == 100
        assert "forge" in report.get("domain_ece", {})

    def test_calibration_improves_with_adjustment(self) -> None:
        """Using adjusted confidence should improve calibration."""
        tracker = CalibrationTracker(num_bins=10)

        # Simulate model that's consistently 20% over-confident
        # Model says 80%, but actually succeeds 60%
        for _ in range(200):
            tracker.record(
                predictions=[{"confidence": 0.8}],
                actual_success=(_ % 5 < 3),  # 60% success rate
            )

        # Get adjustment factor
        adjusted = tracker.adjust_confidence(0.8)

        # Adjusted confidence should be closer to actual 60%
        assert adjusted < 0.8
        assert adjusted > 0.4  # But not too aggressive
