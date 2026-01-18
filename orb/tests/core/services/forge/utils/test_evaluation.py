"""Test evaluation utilities for comprehensive quality assessment."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kagami.forge.schema import QualityMetrics
from kagami.forge.utils.evaluation import (
    EvaluationResult,
    PerformanceEvaluation,
    QualityEvaluator,
)
from kagami.forge.utils.quality_assurance import (
    QualityAssurancePipeline,
)


class TestQualityEvaluator:
    """Test the QualityEvaluator class"""

    @pytest.fixture
    def evaluator(self):
        """Create a QualityEvaluator instance"""
        return QualityEvaluator()

    @pytest.fixture
    def sample_character_data(self):
        """Create sample character data for testing"""
        return {
            "visual": {
                "appearance": "tall and lean",
                "style": "modern casual",
                "colors": ["blue", "gray"],
            },
            "behavior": {
                "personality": "introverted",
                "traits": ["analytical", "creative"],
                "social_style": "reserved",
            },
            "voice": {"tone": "calm", "pace": "measured", "accent": "neutral"},
            "narrative": {
                "backstory": "A skilled analyst who values precision",
                "motivation": "To solve complex problems",
                "goals": ["career advancement", "work-life balance"],
            },
            "motion": {
                "gait": "confident stride",
                "gestures": "minimal but purposeful",
                "posture": "upright",
            },
            "beliefs": {
                "values": ["honesty", "competence"],
                "worldview": "logical and systematic",
                "ethics": "utilitarian",
            },
        }

    def test_evaluator_initialization(self, evaluator: QualityEvaluator) -> None:
        """Test evaluator initialization"""
        assert evaluator is not None
        assert hasattr(evaluator, "evaluation_criteria")
        assert hasattr(evaluator, "baseline_metrics")
        assert hasattr(evaluator, "evaluation_history")
        assert len(evaluator.evaluation_history) == 0

    def test_evaluation_criteria_structure(self, evaluator: QualityEvaluator) -> None:
        """Test evaluation criteria structure"""
        criteria = evaluator.evaluation_criteria
        assert "character_quality" in criteria
        assert "system_performance" in criteria
        assert "integration_quality" in criteria

        # Check character quality criteria
        char_quality = criteria["character_quality"]
        assert "min_score" in char_quality
        assert "max_score" in char_quality
        assert "criteria" in char_quality

        # Check criteria weights
        weights = char_quality["criteria"]
        assert "completeness" in weights
        assert "consistency" in weights
        assert "creativity" in weights
        assert "technical_quality" in weights
        assert "usability" in weights

        # Weights should sum to approximately 1.0
        total_weight = sum(weights.values())
        assert abs(total_weight - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_evaluate_character_basic(
        self, evaluator: QualityEvaluator, sample_character_data: dict[str, Any]
    ) -> None:
        """Test basic character evaluation"""
        result = await evaluator.evaluate_character(sample_character_data)

        assert isinstance(result, EvaluationResult)
        assert result.score >= 0.0  # type: ignore[operator]
        assert result.score <= 1.0  # type: ignore[operator]
        assert result.max_score == 1.0
        assert isinstance(result.passed, bool)
        assert isinstance(result.details, str)
        assert isinstance(result.metrics, dict)
        assert isinstance(result.issues, list)
        assert result.processing_time_ms > 0  # type: ignore[operator]

    @pytest.mark.asyncio
    async def test_evaluate_character_metrics(
        self, evaluator: QualityEvaluator, sample_character_data: dict[str, Any]
    ) -> None:
        """Test character evaluation metrics"""
        result = await evaluator.evaluate_character(sample_character_data)

        metrics = result.metrics
        assert "completeness" in metrics
        assert "consistency" in metrics
        assert "creativity" in metrics
        assert "technical_quality" in metrics
        assert "usability" in metrics

        # All metrics should be between 0 and 1
        for metric_name, metric_value in metrics.items():
            if metric_name != "processing_time":
                assert (
                    0.0 <= metric_value <= 1.0
                ), f"Metric {metric_name} out of range: {metric_value}"

    @pytest.mark.asyncio
    async def test_evaluate_empty_character(self, evaluator: QualityEvaluator) -> None:
        """Test evaluation of empty character data"""
        result = await evaluator.evaluate_character({})

        assert isinstance(result, EvaluationResult)
        assert result.score == 0.0
        assert not result.passed
        assert len(result.issues) > 0  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_evaluate_incomplete_character(self, evaluator: QualityEvaluator) -> None:
        """Test evaluation of incomplete character data"""
        incomplete_data = {
            "visual": {"appearance": "basic"},
            "behavior": {"personality": "simple"},
        }

        result = await evaluator.evaluate_character(incomplete_data)

        assert isinstance(result, EvaluationResult)
        assert result.score < 0.7  # type: ignore[operator]  # Should be below threshold
        assert not result.passed
        assert "completeness" in result.issues[0].lower() or "missing" in result.issues[0].lower()  # type: ignore[index]

    def test_completeness_evaluation(
        self, evaluator: QualityEvaluator, sample_character_data: dict[str, Any]
    ) -> None:
        """Test completeness evaluation"""
        score = evaluator._evaluate_completeness(sample_character_data)
        assert 0.0 <= score <= 1.0

        # Test with missing fields
        incomplete_data = {"visual": {"appearance": "test"}}
        score_incomplete = evaluator._evaluate_completeness(incomplete_data)
        assert score_incomplete < score

    def test_consistency_evaluation(
        self, evaluator: QualityEvaluator, sample_character_data: dict[str, Any]
    ) -> None:
        """Test consistency evaluation"""
        score = evaluator._evaluate_consistency(sample_character_data)
        assert 0.0 <= score <= 1.0

        # Test with inconsistent data
        inconsistent_data = {
            "visual": "string_instead_of_dict",
            "behavior": {"personality": "test"},
        }
        score_inconsistent = evaluator._evaluate_consistency(inconsistent_data)
        assert score_inconsistent <= score

    def test_creativity_evaluation(
        self, evaluator: QualityEvaluator, sample_character_data: dict[str, Any]
    ) -> None:
        """Test creativity evaluation"""
        score = evaluator._evaluate_creativity(sample_character_data)
        assert 0.0 <= score <= 1.0

        # Test with minimal data
        minimal_data = {"visual": {"appearance": "basic"}}
        score_minimal = evaluator._evaluate_creativity(minimal_data)
        assert score_minimal <= score

    def test_technical_quality_evaluation(
        self, evaluator: QualityEvaluator, sample_character_data: dict[str, Any]
    ) -> None:
        """Test technical quality evaluation"""
        score = evaluator._evaluate_technical_quality(sample_character_data)
        assert 0.0 <= score <= 1.0

        # Test with invalid data
        invalid_data = "not_a_dict"
        score_invalid = evaluator._evaluate_technical_quality(invalid_data)
        assert score_invalid == 0.0

    def test_usability_evaluation(
        self, evaluator: QualityEvaluator, sample_character_data: dict[str, Any]
    ) -> None:
        """Test usability evaluation"""
        score = evaluator._evaluate_usability(sample_character_data)
        assert 0.0 <= score <= 1.0

        # Test with user-unfriendly data
        unfriendly_data = {"x1": {"y1": "z1"}, "x2": {"y2": "z2"}}
        score_unfriendly = evaluator._evaluate_usability(unfriendly_data)
        assert score_unfriendly <= score

    @pytest.mark.asyncio
    async def test_performance_evaluation(self, evaluator: QualityEvaluator) -> None:
        """Test performance evaluation"""

        async def dummy_operation():
            await asyncio.sleep(0.01)  # 10ms operation

        result = await evaluator.evaluate_performance(dummy_operation, iterations=3)

        assert isinstance(result, PerformanceEvaluation)
        assert result.latency_ms > 0
        assert result.throughput_ops_per_sec > 0
        assert result.memory_usage_mb >= 0
        assert result.cpu_usage_percent >= 0
        assert 0.0 <= result.success_rate <= 1.0
        assert result.error_count >= 0

    @pytest.mark.asyncio
    async def test_performance_evaluation_with_errors(self, evaluator: QualityEvaluator) -> None:
        """Test performance evaluation with errors"""

        async def failing_operation():
            raise ValueError("Test error")

        result = await evaluator.evaluate_performance(failing_operation, iterations=3)

        assert isinstance(result, PerformanceEvaluation)
        assert result.error_count == 3
        assert result.success_rate == 0.0

    @pytest.mark.asyncio
    async def test_baseline_comparison(
        self, evaluator: QualityEvaluator, sample_character_data: dict[str, Any]
    ) -> None:
        """Test baseline comparison"""
        result = await evaluator.evaluate_character(sample_character_data)
        comparison = evaluator.compare_with_baseline(result)

        assert isinstance(comparison, dict)
        assert "score_improvement" in comparison
        assert "processing_time_improvement" in comparison
        assert "better_than_baseline" in comparison
        assert "baseline_metrics" in comparison
        assert "current_metrics" in comparison

    @pytest.mark.asyncio
    async def test_evaluation_history(
        self, evaluator: QualityEvaluator, sample_character_data: dict[str, Any]
    ) -> None:
        """Test evaluation history tracking"""
        initial_count = len(evaluator.evaluation_history)

        await evaluator.evaluate_character(sample_character_data)
        assert len(evaluator.evaluation_history) == initial_count + 1

        await evaluator.evaluate_character(sample_character_data)
        assert len(evaluator.evaluation_history) == initial_count + 2

    def test_evaluation_statistics(self, evaluator: QualityEvaluator) -> None:
        """Test evaluation statistics"""
        stats = evaluator.get_evaluation_statistics()
        assert "status" in stats
        assert stats["status"] == "no_data"

        # Add some mock history
        evaluator.evaluation_history = [
            EvaluationResult(0.8, 1.0, True, "test", {}, [], 100.0),
            EvaluationResult(0.7, 1.0, True, "test", {}, [], 150.0),
            EvaluationResult(0.9, 1.0, True, "test", {}, [], 120.0),
        ]

        stats = evaluator.get_evaluation_statistics()
        assert "total_evaluations" in stats
        assert "average_score" in stats
        assert "success_rate" in stats
        assert stats["total_evaluations"] == 3
        assert stats["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_cleanup(self, evaluator: QualityEvaluator) -> None:
        """Test cleanup functionality"""
        # Add some history
        evaluator.evaluation_history = [EvaluationResult(0.8, 1.0, True, "test", {}, [], 100.0)]

        await evaluator.cleanup()
        assert len(evaluator.evaluation_history) == 0

    def test_performance_evaluation_targets(self) -> None:
        """Test performance evaluation targets"""
        targets = {
            "latency_ms": 100,
            "throughput_ops_per_sec": 50,
            "memory_usage_mb": 256,
            "cpu_usage_percent": 70,
            "success_rate": 0.95,
        }

        # Test meeting targets
        good_performance = PerformanceEvaluation(
            latency_ms=80,
            throughput_ops_per_sec=60,
            memory_usage_mb=200,
            cpu_usage_percent=60,
            success_rate=0.98,
            error_count=1,
        )

        assert good_performance.meets_targets(targets)

        # Test not meeting targets
        poor_performance = PerformanceEvaluation(
            latency_ms=150,
            throughput_ops_per_sec=30,
            memory_usage_mb=300,
            cpu_usage_percent=90,
            success_rate=0.85,
            error_count=5,
        )

        assert not poor_performance.meets_targets(targets)

    def test_result_to_dict(self) -> None:
        """Test EvaluationResult to_dict method"""
        result = EvaluationResult(
            score=0.85,
            max_score=1.0,
            passed=True,
            details="Test evaluation",
            metrics={"completeness": 0.8, "consistency": 0.9},
            issues=["minor issue"],
            processing_time_ms=150.5,
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["score"] == 0.85
        assert result_dict["max_score"] == 1.0
        assert result_dict["passed"] is True
        assert result_dict["details"] == "Test evaluation"
        assert result_dict["metrics"] == {"completeness": 0.8, "consistency": 0.9}
        assert result_dict["issues"] == ["minor issue"]
        assert result_dict["processing_time_ms"] == 150.5


class TestQualityAssurancePipeline:
    """Test the QualityAssurancePipeline class"""

    @pytest.fixture
    def pipeline(self):
        """Create a QualityAssurancePipeline instance"""
        return QualityAssurancePipeline()

    @pytest.fixture
    def sample_character_data(self):
        """Create sample character data for testing"""
        return {
            "visual": {"appearance": "professional", "style": "business casual"},
            "behavior": {
                "personality": "confident",
                "traits": ["leadership", "analytical"],
            },
            "voice": {"tone": "authoritative", "pace": "steady"},
            "narrative": {
                "backstory": "Experienced manager",
                "motivation": "Team success",
            },
            "motion": {"gait": "purposeful", "gestures": "expressive"},
            "beliefs": {
                "values": ["integrity", "excellence"],
                "worldview": "pragmatic",
            },
        }

    def test_pipeline_initialization(self, pipeline: QualityAssurancePipeline) -> None:
        """Test pipeline initialization"""
        assert pipeline is not None
        assert hasattr(pipeline, "validators")
        assert hasattr(pipeline, "quality_standards")
        assert hasattr(pipeline, "validation_history")
        assert len(pipeline.validation_history) == 0

    def test_quality_standards_structure(self, pipeline: QualityAssurancePipeline) -> None:
        """Test quality standards structure"""
        standards = pipeline.quality_standards
        assert "completeness" in standards
        assert "consistency" in standards
        assert "creativity" in standards
        assert "technical_quality" in standards
        assert "performance" in standards
        assert "integration" in standards

        # Check completeness standards
        completeness = standards["completeness"]
        assert "min_score" in completeness
        assert "required_fields" in completeness
        assert "critical_fields" in completeness

    @pytest.mark.asyncio
    async def test_evaluate_character_pipeline(
        self, pipeline: QualityAssurancePipeline, sample_character_data: dict[str, Any]
    ) -> None:
        """Test character evaluation through pipeline"""
        metrics = await pipeline.evaluate_character(sample_character_data)

        assert isinstance(metrics, QualityMetrics)
        assert 0.0 <= metrics.completeness_score <= 1.0
        assert 0.0 <= metrics.consistency_score <= 1.0
        assert 0.0 <= metrics.creativity_score <= 1.0
        assert 0.0 <= metrics.technical_quality_score <= 1.0
        assert 0.0 <= metrics.overall_score <= 1.0
        assert metrics.processing_time_ms > 0
        assert isinstance(metrics.issues, list)

    @pytest.mark.asyncio
    async def test_validation_history_tracking(
        self, pipeline: QualityAssurancePipeline, sample_character_data: dict[str, Any]
    ) -> None:
        """Test validation history tracking"""
        initial_count = len(pipeline.validation_history)

        await pipeline.evaluate_character(sample_character_data)
        assert len(pipeline.validation_history) == initial_count + 1

        await pipeline.evaluate_character(sample_character_data)
        assert len(pipeline.validation_history) == initial_count + 2

    def test_quality_report_generation(self, pipeline: QualityAssurancePipeline) -> None:
        """Test quality report generation"""
        report = pipeline.get_quality_report()
        assert "status" in report
        assert report["status"] == "no_data"

        # Add mock history
        pipeline.validation_history = [
            QualityMetrics(0.8, 0.7, 0.9, 0.8, 0.8, 100.0, []),
            QualityMetrics(0.7, 0.8, 0.8, 0.9, 0.8, 120.0, []),
            QualityMetrics(0.9, 0.9, 0.7, 0.8, 0.85, 110.0, []),
        ]

        report = pipeline.get_quality_report()
        assert report["status"] == "active"
        assert "total_validations" in report
        assert "average_scores" in report
        assert "average_processing_time" in report
        assert report["total_validations"] == 3

    @pytest.mark.asyncio
    async def test_cleanup_pipeline(self, pipeline: QualityAssurancePipeline) -> None:
        """Test pipeline cleanup"""
        # Add some history
        pipeline.validation_history = [QualityMetrics(0.8, 0.7, 0.9, 0.8, 0.8, 100.0, [])]

        await pipeline.cleanup()
        assert len(pipeline.validation_history) == 0


# Integration test
class TestEvaluationIntegration:
    """Integration tests for evaluation components"""

    @pytest.mark.asyncio
    async def test_full_evaluation_workflow(self) -> None:
        """Test complete evaluation workflow"""
        evaluator = QualityEvaluator()
        pipeline = QualityAssurancePipeline()

        # Create test character data with sufficient completeness
        character_data = {
            "visual": {
                "appearance": "tall and elegant",
                "age": 25,
                "hair": "dark brown",
                "eyes": "bright green",
                "build": "athletic",
                "style": "professional",
            },
            "behavior": {
                "personality": "friendly",
                "traits": ["empathetic", "reliable", "patient"],
                "mannerisms": "calm and composed",
                "social_style": "approachable",
                "communication": "clear and warm",
            },
            "voice": {
                "tone": "warm",
                "pace": "moderate",
                "pitch": "medium",
                "accent": "neutral",
                "speech_patterns": "articulate",
            },
            "narrative": {
                "backstory": "Helper with extensive experience",
                "motivation": "Assist others",
                "goals": "make people feel comfortable",
                "conflicts": "perfectionist tendencies",
                "relationships": "maintains close friendships",
            },
            "motion": {
                "gait": "relaxed",
                "gestures": "welcoming",
                "posture": "upright and confident",
                "movements": "fluid and graceful",
                "energy_level": "moderate",
            },
            "beliefs": {
                "values": ["kindness", "honesty", "growth"],
                "worldview": "optimistic",
                "philosophy": "everyone deserves respect",
                "motivations": "help others succeed",
                "principles": "treat others as you want to be treated",
            },
        }

        # Run both evaluations
        eval_result = await evaluator.evaluate_character(character_data)
        qa_metrics = await pipeline.evaluate_character(character_data)

        # Both should succeed
        assert eval_result.passed
        assert qa_metrics.overall_score > 0.0

        # Results should be consistent
        assert eval_result.score > 0.0  # type: ignore[operator]
        assert qa_metrics.completeness_score > 0.0

        # Cleanup
        await evaluator.cleanup()
        await pipeline.cleanup()
