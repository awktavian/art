"""Unit tests for Training Validation Report Generator.

Tests the TrainingValidationReport dataclass and factory function for
comprehensive post-training validation reporting.

December 14, 2025
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from kagami.core.validation import (
    TrainingValidationReport,
    create_validation_report_from_training,
)


class TestTrainingValidationReport:
    """Test suite for TrainingValidationReport."""

    def test_report_instantiation(self) -> None:
        """Test basic report creation."""
        report = TrainingValidationReport(
            model_size="base",
            total_steps=1000,
            final_loss=0.05,
            converged=True,
            plateau_detected=False,
            prediction_mse=0.03,
            reconstruction_r2=0.90,
            temporal_coherence=0.85,
            compression_ratio=4.0,
            integration_score=0.75,
            integration_interpretation="High integration",
            cbf_violations=5,
            gradient_explosions=0,
            recovery_attempts=0,
        )

        assert report.model_size == "base"
        assert report.total_steps == 1000
        assert report.final_loss == 0.05

    def test_quality_gates_pass(self) -> None:
        """Test quality gates with passing metrics."""
        report = TrainingValidationReport(
            model_size="base",
            total_steps=1000,
            final_loss=0.02,
            converged=True,
            plateau_detected=False,
            prediction_mse=0.03,  # < 0.05
            reconstruction_r2=0.90,  # > 0.85
            temporal_coherence=0.85,
            compression_ratio=4.0,
            integration_score=0.75,  # > 0.7
            integration_interpretation="High integration",
            cbf_violations=10,  # < 100
            gradient_explosions=0,
            recovery_attempts=0,
        )

        assert report.passes_quality_gates() is True

    def test_quality_gates_fail_prediction_mse(self) -> None:
        """Test quality gates failing on high prediction MSE."""
        report = TrainingValidationReport(
            model_size="base",
            total_steps=1000,
            final_loss=0.08,
            converged=True,
            plateau_detected=False,
            prediction_mse=0.08,  # > 0.05 FAIL
            reconstruction_r2=0.90,
            temporal_coherence=0.85,
            compression_ratio=4.0,
            integration_score=0.75,
            integration_interpretation="High integration",
            cbf_violations=10,
            gradient_explosions=0,
            recovery_attempts=0,
        )

        assert report.passes_quality_gates() is False

    def test_quality_gates_fail_reconstruction(self) -> None:
        """Test quality gates failing on low reconstruction R²."""
        report = TrainingValidationReport(
            model_size="base",
            total_steps=1000,
            final_loss=0.05,
            converged=True,
            plateau_detected=False,
            prediction_mse=0.03,
            reconstruction_r2=0.70,  # < 0.85 FAIL
            temporal_coherence=0.85,
            compression_ratio=4.0,
            integration_score=0.75,
            integration_interpretation="High integration",
            cbf_violations=10,
            gradient_explosions=0,
            recovery_attempts=0,
        )

        assert report.passes_quality_gates() is False

    def test_quality_gates_fail_integration(self) -> None:
        """Test quality gates failing on low integration score."""
        report = TrainingValidationReport(
            model_size="base",
            total_steps=1000,
            final_loss=0.05,
            converged=True,
            plateau_detected=False,
            prediction_mse=0.03,
            reconstruction_r2=0.90,
            temporal_coherence=0.85,
            compression_ratio=4.0,
            integration_score=0.50,  # < 0.7 FAIL
            integration_interpretation="Moderate integration",
            cbf_violations=10,
            gradient_explosions=0,
            recovery_attempts=0,
        )

        assert report.passes_quality_gates() is False

    def test_quality_gates_fail_cbf_violations(self) -> None:
        """Test quality gates failing on excessive CBF violations."""
        report = TrainingValidationReport(
            model_size="base",
            total_steps=1000,
            final_loss=0.05,
            converged=True,
            plateau_detected=False,
            prediction_mse=0.03,
            reconstruction_r2=0.90,
            temporal_coherence=0.85,
            compression_ratio=4.0,
            integration_score=0.75,
            integration_interpretation="High integration",
            cbf_violations=150,  # > 100 FAIL
            gradient_explosions=0,
            recovery_attempts=0,
        )

        assert report.passes_quality_gates() is False

    def test_quality_gates_fail_convergence(self) -> None:
        """Test quality gates failing when training didn't converge."""
        report = TrainingValidationReport(
            model_size="base",
            total_steps=1000,
            final_loss=0.12,
            converged=False,  # FAIL
            plateau_detected=True,
            prediction_mse=0.03,
            reconstruction_r2=0.90,
            temporal_coherence=0.85,
            compression_ratio=4.0,
            integration_score=0.75,
            integration_interpretation="High integration",
            cbf_violations=10,
            gradient_explosions=0,
            recovery_attempts=0,
        )

        assert report.passes_quality_gates() is False

    def test_markdown_generation(self) -> None:
        """Test markdown report generation."""
        report = TrainingValidationReport(
            model_size="base",
            total_steps=1000,
            final_loss=0.05,
            converged=True,
            plateau_detected=False,
            prediction_mse=0.03,
            reconstruction_r2=0.90,
            temporal_coherence=0.85,
            compression_ratio=4.0,
            integration_score=0.75,
            integration_interpretation="High integration",
            cbf_violations=10,
            gradient_explosions=2,
            recovery_attempts=1,
        )

        markdown = report.generate_markdown()

        # Check key sections present
        assert "# Training Validation Report: base" in markdown
        assert "Training Summary" in markdown
        assert "Benchmark Results" in markdown
        assert "Integration Metrics" in markdown
        assert "Safety Audit" in markdown
        assert "Conclusion" in markdown
        assert "Recommendations" in markdown

        # Check verdict
        assert "✅" in markdown  # Should pass
        assert "PASS" in markdown

    def test_markdown_generation_failing(self) -> None:
        """Test markdown report generation for failing case."""
        report = TrainingValidationReport(
            model_size="large",
            total_steps=500,
            final_loss=0.15,
            converged=False,
            plateau_detected=True,
            prediction_mse=0.08,
            reconstruction_r2=0.70,
            temporal_coherence=0.60,
            compression_ratio=3.5,
            integration_score=0.50,
            integration_interpretation="Moderate integration",
            cbf_violations=200,
            gradient_explosions=50,
            recovery_attempts=10,
        )

        markdown = report.generate_markdown()

        # Check verdict
        assert "❌" in markdown
        assert "FAIL" in markdown

        # Check recommendations present
        assert "Recommendations" in markdown

    def test_json_export(self) -> None:
        """Test JSON serialization."""
        report = TrainingValidationReport(
            model_size="base",
            total_steps=1000,
            final_loss=0.05,
            converged=True,
            plateau_detected=False,
            prediction_mse=0.03,
            reconstruction_r2=0.90,
            temporal_coherence=0.85,
            compression_ratio=4.0,
            integration_score=0.75,
            integration_interpretation="High integration",
            cbf_violations=10,
            gradient_explosions=2,
            recovery_attempts=1,
        )

        data = report.to_json()

        assert isinstance(data, dict)
        assert data["model_size"] == "base"
        assert data["total_steps"] == 1000
        assert "benchmark_metrics" in data
        assert "integration_metrics" in data
        assert "safety_audit" in data
        assert "quality_gates" in data
        assert data["quality_gates"]["passed"] is True

    def test_save_markdown(self) -> None:
        """Test saving report to markdown file."""
        report = TrainingValidationReport(
            model_size="base",
            total_steps=1000,
            final_loss=0.05,
            converged=True,
            plateau_detected=False,
            prediction_mse=0.03,
            reconstruction_r2=0.90,
            temporal_coherence=0.85,
            compression_ratio=4.0,
            integration_score=0.75,
            integration_interpretation="High integration",
            cbf_violations=10,
            gradient_explosions=2,
            recovery_attempts=1,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            report.save(output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert "Training Validation Report" in content

    def test_save_json(self) -> None:
        """Test saving report to JSON file."""
        report = TrainingValidationReport(
            model_size="base",
            total_steps=1000,
            final_loss=0.05,
            converged=True,
            plateau_detected=False,
            prediction_mse=0.03,
            reconstruction_r2=0.90,
            temporal_coherence=0.85,
            compression_ratio=4.0,
            integration_score=0.75,
            integration_interpretation="High integration",
            cbf_violations=10,
            gradient_explosions=2,
            recovery_attempts=1,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            report.save_json(output_path)

            assert output_path.exists()
            with open(output_path) as f:
                data = json.load(f)
            assert data["model_size"] == "base"


class TestFactoryFunction:
    """Test suite for create_validation_report_from_training factory."""

    @dataclass
    class MockBenchmarkResult:
        """Mock benchmark result."""

        dynamics_prediction_mse: float = 0.03
        prediction_r2: float = 0.90
        temporal_coherence: float = 0.85
        compression_ratio: float = 4.0

    @dataclass
    class MockIntegrationMetrics:
        """Mock integration metrics."""

        system_integration_score: float = 0.75
        interpretation: str = "High integration"

    @dataclass
    class MockTrainingMonitor:
        """Mock training monitor."""

        divergence_events: int = 5
        loss_history: list = None  # type: ignore[assignment]
        recovery_attempts: int = 1
        steps_since_improvement: int = 10
        plateau_patience: int = 100

        def __post_init__(self):
            if self.loss_history is None:
                self.loss_history = [0.1, 0.09, 0.08, 0.07, 0.06]

    def test_factory_basic(self) -> None:
        """Test basic factory function usage."""
        report = create_validation_report_from_training(
            model_size="base",
            total_steps=1000,
            final_loss=0.05,
            benchmark_result=self.MockBenchmarkResult(),
            integration_metrics=self.MockIntegrationMetrics(),
            training_monitor=self.MockTrainingMonitor(),
        )

        assert isinstance(report, TrainingValidationReport)
        assert report.model_size == "base"
        assert report.total_steps == 1000
        assert report.prediction_mse == 0.03
        assert report.integration_score == 0.75

    def test_factory_extracts_monitor_fields(self) -> None:
        """Test factory correctly extracts training monitor fields."""
        monitor = self.MockTrainingMonitor()
        monitor.recovery_attempts = 2
        monitor.divergence_events = 15

        report = create_validation_report_from_training(
            model_size="base",
            total_steps=1000,
            final_loss=0.05,
            benchmark_result=self.MockBenchmarkResult(),
            integration_metrics=self.MockIntegrationMetrics(),
            training_monitor=monitor,
        )

        assert report.recovery_attempts == 2
        assert report.cbf_violations == 15

    def test_factory_convergence_logic(self) -> None:
        """Test factory convergence determination logic."""
        # Converged case (recovery_attempts < 3)
        monitor1 = self.MockTrainingMonitor()
        monitor1.recovery_attempts = 1

        report1 = create_validation_report_from_training(
            model_size="base",
            total_steps=1000,
            final_loss=0.05,
            benchmark_result=self.MockBenchmarkResult(),
            integration_metrics=self.MockIntegrationMetrics(),
            training_monitor=monitor1,
        )

        assert report1.converged is True

        # Failed to converge (recovery_attempts >= 3)
        monitor2 = self.MockTrainingMonitor()
        monitor2.recovery_attempts = 5

        report2 = create_validation_report_from_training(
            model_size="base",
            total_steps=1000,
            final_loss=0.15,
            benchmark_result=self.MockBenchmarkResult(),
            integration_metrics=self.MockIntegrationMetrics(),
            training_monitor=monitor2,
        )

        assert report2.converged is False

    def test_factory_plateau_detection(self) -> None:
        """Test factory plateau detection logic."""
        # No plateau
        monitor1 = self.MockTrainingMonitor()
        monitor1.steps_since_improvement = 10
        monitor1.plateau_patience = 100

        report1 = create_validation_report_from_training(
            model_size="base",
            total_steps=1000,
            final_loss=0.05,
            benchmark_result=self.MockBenchmarkResult(),
            integration_metrics=self.MockIntegrationMetrics(),
            training_monitor=monitor1,
        )

        assert report1.plateau_detected is False

        # Plateau detected
        monitor2 = self.MockTrainingMonitor()
        monitor2.steps_since_improvement = 150
        monitor2.plateau_patience = 100

        report2 = create_validation_report_from_training(
            model_size="base",
            total_steps=1000,
            final_loss=0.10,
            benchmark_result=self.MockBenchmarkResult(),
            integration_metrics=self.MockIntegrationMetrics(),
            training_monitor=monitor2,
        )

        assert report2.plateau_detected is True

    def test_factory_gradient_explosion_counting(self) -> None:
        """Test factory counts gradient explosions from loss history."""
        monitor = self.MockTrainingMonitor()
        # Create loss history with 2 explosions (10x jumps)
        monitor.loss_history = [0.1, 0.09, 0.95, 0.08, 0.9, 0.07]

        report = create_validation_report_from_training(
            model_size="base",
            total_steps=1000,
            final_loss=0.07,
            benchmark_result=self.MockBenchmarkResult(),
            integration_metrics=self.MockIntegrationMetrics(),
            training_monitor=monitor,
        )

        assert report.gradient_explosions == 2
