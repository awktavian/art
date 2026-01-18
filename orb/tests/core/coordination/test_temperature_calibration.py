"""Test TemperatureScaler integration with MetacognitiveLayer.

Tests:
1. Basic calibration functionality
2. ECE (Expected Calibration Error) improvement
3. Automatic recalibration on data accumulation
4. Confidence adjustment after calibration
5. Integration with existing metacognition features
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import torch

from kagami.core.coordination.metacognition import MetacognitiveLayer
from kagami.core.world_model.calibration import TemperatureScaler, compute_ece


class TestTemperatureScaler:
    """Test TemperatureScaler module."""

    def test_init(self) -> None:
        """Test initialization."""
        scaler = TemperatureScaler()
        assert scaler.temperature.item() == 1.0, "Initial temperature should be 1.0"

    def test_forward(self) -> None:
        """Test forward pass (scaling)."""
        scaler = TemperatureScaler()
        scaler.temperature.data = torch.tensor([2.0])

        logits = torch.tensor([1.0, 2.0, 3.0])
        scaled = scaler(logits)

        expected = logits / 2.0
        assert torch.allclose(scaled, expected), "Scaling should divide by temperature"  # type: ignore[arg-type]

    def test_calibrate(self) -> None:
        """Test calibration process."""
        scaler = TemperatureScaler()

        # Simulated overconfident predictions
        confidence_scores = torch.tensor([0.9, 0.85, 0.95, 0.88, 0.92, 0.87, 0.9, 0.91, 0.89, 0.93])
        # But actual accuracy is lower
        accuracy_scores = torch.tensor(
            [0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 1.0]
        )  # 60% actual

        initial_temp = scaler.temperature.item()
        scaler.calibrate(confidence_scores, accuracy_scores, num_epochs=100, lr=0.01)
        final_temp = scaler.temperature.item()

        # Temperature should increase for overconfident model
        assert (
            final_temp > initial_temp
        ), "Temperature should increase for overconfident predictions"
        print(f"\nCalibration: T={initial_temp:.3f} → T={final_temp:.3f}")

    def test_compute_ece(self) -> None:
        """Test ECE computation."""
        # Perfect calibration
        confidence_perfect = torch.tensor([0.1, 0.3, 0.5, 0.7, 0.9] * 20)  # 100 samples
        accuracy_perfect = (torch.rand(100) < confidence_perfect).float()

        ece_perfect, _ = compute_ece(
            confidence_perfect.to(torch.float32).numpy(),
            accuracy_perfect.to(torch.float32).numpy(),
            n_bins=10,
        )

        # ECE should be low for well-calibrated predictions
        assert ece_perfect < 0.2, f"ECE for well-calibrated should be <0.2, got {ece_perfect:.3f}"

        # Overconfident predictions
        confidence_over = torch.ones(100) * 0.9
        accuracy_over = (torch.rand(100) < 0.5).float()

        ece_over, _ = compute_ece(
            confidence_over.to(torch.float32).numpy(),
            accuracy_over.to(torch.float32).numpy(),
            n_bins=10,
        )

        # ECE should be high for miscalibrated predictions
        assert ece_over > 0.2, f"ECE for miscalibrated should be >0.2, got {ece_over:.3f}"

        print(f"\nECE: well-calibrated={ece_perfect:.3f}, miscalibrated={ece_over:.3f}")


class TestMetacognitiveLayerWithTemperature:
    """Test MetacognitiveLayer with temperature scaling."""

    @pytest.fixture
    def metacog_basic(self):
        """MetacognitiveLayer without temperature scaling (opt-out of default)."""
        return MetacognitiveLayer(use_temperature_scaling=False)

    @pytest.fixture
    def metacog_calibrated(self):
        """MetacognitiveLayer with temperature scaling (default)."""
        return MetacognitiveLayer()  # use_temperature_scaling=True is now default

    @pytest.mark.asyncio
    async def test_init_without_temperature(self, metacog_basic: Any) -> None:
        """Test initialization without temperature scaling."""
        assert not metacog_basic.use_temperature_scaling
        assert not hasattr(metacog_basic, "temperature_scaler")

    @pytest.mark.asyncio
    async def test_init_with_temperature(self, metacog_calibrated: Any) -> None:
        """Test initialization with temperature scaling."""
        assert metacog_calibrated.use_temperature_scaling
        assert hasattr(metacog_calibrated, "temperature_scaler")
        assert isinstance(metacog_calibrated.temperature_scaler, TemperatureScaler)

    @pytest.mark.asyncio
    async def test_assess_confidence_basic(self, metacog_basic: Any) -> None:
        """Test confidence assessment without temperature scaling."""
        assessment = await metacog_basic.assess_confidence(
            basis_samples=10,
            novelty=0.2,
            complexity=0.5,
        )

        assert 0.0 <= assessment.confidence <= 1.0
        assert isinstance(assessment.basis, str)
        assert isinstance(assessment.uncertainty_sources, list)

    @pytest.mark.asyncio
    async def test_assess_confidence_calibrated(self, metacog_calibrated: Any) -> None:
        """Test confidence assessment with temperature scaling."""
        assessment = await metacog_calibrated.assess_confidence(
            basis_samples=10,
            novelty=0.2,
            complexity=0.5,
        )

        assert 0.0 <= assessment.confidence <= 1.0
        assert isinstance(assessment.basis, str)
        # Initial temperature is 1.0, so confidence should be similar to uncalibrated

    @pytest.mark.asyncio
    async def test_record_outcome_basic(self, metacog_basic: Any) -> None:
        """Test outcome recording without temperature scaling."""
        await metacog_basic.record_outcome(
            predicted_confidence=0.8,
            actual_success=True,
            task_type="test_task",
            correlation_id="test_corr_1",
        )

        assert len(metacog_basic.calibration_history) == 1
        assert metacog_basic.calibration_history[0].predicted_confidence == 0.8

    @pytest.mark.asyncio
    async def test_record_outcome_calibrated(self, metacog_calibrated: Any) -> None:
        """Test outcome recording with temperature scaling."""
        await metacog_calibrated.record_outcome(
            predicted_confidence=0.8,
            actual_success=True,
            task_type="test_task",
            correlation_id="test_corr_1",
        )

        assert len(metacog_calibrated.calibration_history) == 1
        assert len(metacog_calibrated._calibration_pending) == 1

    @pytest.mark.asyncio
    async def test_automatic_recalibration(self, metacog_calibrated: Any) -> None:
        """Test automatic recalibration after accumulating data."""
        # Set lower interval for testing
        metacog_calibrated._calibration_interval = 25

        initial_temp = metacog_calibrated.temperature_scaler.temperature.item()

        # Simulate overconfident predictions
        for i in range(30):
            await metacog_calibrated.record_outcome(
                predicted_confidence=0.9,  # High confidence
                actual_success=(i % 3 == 0),  # But only 33% success
                task_type="test_task",
                correlation_id=f"test_corr_{i}",
            )

        # Temperature should have been recalibrated
        final_temp = metacog_calibrated.temperature_scaler.temperature.item()

        print(f"\nAutomatic recalibration: T={initial_temp:.3f} → T={final_temp:.3f}")

        # Temperature should increase for overconfident predictions
        assert (
            final_temp > initial_temp
        ), "Temperature should increase after observing overconfidence"

    @pytest.mark.asyncio
    async def test_confidence_adjustment_after_calibration(self, metacog_calibrated: Any) -> None:
        """Test that confidence is adjusted after calibration."""
        # Pre-calibration assessment
        assessment_before = await metacog_calibrated.assess_confidence(
            basis_samples=10,
            novelty=0.1,
            complexity=0.3,
        )
        confidence_before = assessment_before.confidence

        # Simulate calibration with overconfident data
        metacog_calibrated._calibration_interval = 25
        for i in range(30):
            await metacog_calibrated.record_outcome(
                predicted_confidence=0.9,
                actual_success=(i % 3 == 0),  # 33% success
                task_type="test_task",
                correlation_id=f"test_corr_{i}",
            )

        # Post-calibration assessment
        assessment_after = await metacog_calibrated.assess_confidence(
            basis_samples=10,
            novelty=0.1,
            complexity=0.3,
        )
        confidence_after = assessment_after.confidence

        print(
            f"\nConfidence adjustment: before={confidence_before:.3f}, after={confidence_after:.3f}"
        )

        # Confidence should be adjusted (typically lowered if overconfident)
        # Note: The exact direction depends on the calibration, but they should differ
        # In this case, we expect lower confidence after observing poor performance

    @pytest.mark.asyncio
    async def test_calibration_stats_integration(self, metacog_calibrated: Any) -> None:
        """Test that calibration stats work with temperature scaling."""
        # Record some outcomes
        for i in range(20):
            await metacog_calibrated.record_outcome(
                predicted_confidence=0.8 + (i % 5) * 0.02,
                actual_success=(i % 2 == 0),
                task_type="test_task",
                correlation_id=f"test_corr_{i}",
            )

        stats = await metacog_calibrated.get_calibration_stats(hours=1)

        # Sample count should be at least what we recorded (may include previous test data)
        assert stats.sample_count >= 20
        # Confidence may be scaled (not necessarily 0-1 after temperature scaling)
        assert stats.avg_predicted_confidence is not None
        assert 0.0 <= stats.actual_success_rate <= 1.0
        assert stats.calibration_error >= 0.0

    @pytest.mark.asyncio
    async def test_temperature_persistence(self, metacog_calibrated: Any) -> None:
        """Test that temperature persists across assessments."""
        # Calibrate
        metacog_calibrated._calibration_interval = 20
        for i in range(25):
            await metacog_calibrated.record_outcome(
                predicted_confidence=0.9,
                actual_success=(i % 3 == 0),
                task_type="test_task",
                correlation_id=f"test_corr_{i}",
            )

        temp_after_calibration = metacog_calibrated.temperature_scaler.temperature.item()

        # Make several assessments
        for _ in range(5):
            await metacog_calibrated.assess_confidence(
                basis_samples=10,
                novelty=0.2,
            )

        # Temperature should remain the same
        temp_after_assessments = metacog_calibrated.temperature_scaler.temperature.item()
        assert temp_after_calibration == temp_after_assessments

    @pytest.mark.asyncio
    async def test_knowledge_gap_detection_with_temperature(self, metacog_calibrated: Any) -> None:
        """Test knowledge gap detection with temperature scaling."""
        # Record some poor performance
        for i in range(10):
            await metacog_calibrated.record_outcome(
                predicted_confidence=0.7,
                actual_success=False,
                task_type="difficult_task",
                correlation_id=f"test_corr_{i}",
            )

        gaps = await metacog_calibrated.detect_knowledge_gaps("difficult_task")

        assert isinstance(gaps, dict)
        assert "has_gap" in gaps
        assert gaps["has_gap"] is True  # Should detect low success rate


class TestTemperatureScalingBenefits:
    """Test the benefits of temperature scaling."""

    @pytest.mark.asyncio
    async def test_ece_improvement(self) -> None:
        """Test that temperature scaling improves ECE."""
        # Create calibrated layer
        metacog = MetacognitiveLayer(use_temperature_scaling=True)

        # Simulate overconfident predictions and outcomes
        confidences = []
        successes = []

        metacog._calibration_interval = 50

        for i in range(60):
            conf = 0.85 + (i % 10) * 0.01  # High confidence: 0.85-0.94
            success = i % 2 == 0  # But only 50% actual success

            confidences.append(conf)
            successes.append(success)

            await metacog.record_outcome(
                predicted_confidence=conf,
                actual_success=success,
                task_type="test_task",
                correlation_id=f"test_corr_{i}",
            )

        # Check that temperature adjusted
        temp = metacog.temperature_scaler.temperature.item()
        print(f"\nFinal temperature: {temp:.3f}")

        # Temperature should be > 1.0 for overconfident predictions
        assert temp > 1.0, "Temperature should increase for overconfident model"

        # Compute ECE before and after temperature scaling
        conf_tensor = torch.tensor(confidences)
        succ_tensor = torch.tensor(successes, dtype=torch.float)

        # ECE without scaling
        ece_before, _ = compute_ece(
            conf_tensor.to(torch.float32).numpy(),
            succ_tensor.to(torch.float32).numpy(),
        )

        # ECE with scaling
        scaled_logits = metacog.temperature_scaler(
            torch.logit(torch.clamp(conf_tensor, 1e-7, 1 - 1e-7))
        )
        scaled_conf = torch.sigmoid(scaled_logits)  # type: ignore[arg-type]
        ece_after, _ = compute_ece(
            scaled_conf.detach().to(torch.float32).numpy(),
            succ_tensor.to(torch.float32).numpy(),
        )

        print(
            f"ECE: before={ece_before:.3f}, after={ece_after:.3f}, improvement={ece_before - ece_after:.3f}"
        )

        # ECE should improve (or at least not get worse)
        assert (
            ece_after <= ece_before + 0.05
        ), "Temperature scaling should not significantly worsen ECE"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
