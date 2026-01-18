"""Tests for the quality feedback module."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.forge.modules.quality_feedback import (
    GenerationFeedback,
    QualityFeedbackModule,
    QualityMetric,
)


@pytest.fixture
def feedback_module():
    """Create a quality feedback module for testing."""
    return QualityFeedbackModule()


@pytest.fixture
def sample_generation_result():
    """Create a sample generation result for testing."""
    return {
        "generation_id": "test-gen-001",
        "visual_design": {
            "mesh_quality": 0.85,
            "texture_quality": 0.75,
            "polygon_count": 25000,
            "topology_score": 0.8,
            "texture_resolution": "2048x2048",
            "material_count": 3,
        },
        "motion": {
            "smoothness_score": 0.9,
            "naturalness_score": 0.7,
            "fps": 60,
            "keyframe_count": 120,
            "physics_accuracy": 0.8,
            "gesture_variety": 0.6,
        },
        "voice": {
            "clarity_score": 0.8,
            "emotional_expression": 0.85,
            "sample_rate": 44100,
            "noise_level": 0.05,
            "emotion_range": 0.9,
            "prosody_score": 0.8,
        },
        "behavior_ai": {
            "coherence_score": 0.9,
            "decision_quality": 0.75,
            "trait_consistency": 0.85,
            "response_variety": 0.95,
            "logic_score": 0.7,
            "context_awareness": 0.8,
        },
        "performance": {
            "generation_time_seconds": 25,
            "peak_memory_mb": 450,
            "gpu_usage": 0.75,
            "module_times": {"visual": 10, "motion": 5, "voice": 8, "behavior": 2},
        },
    }


def test_module_initialization(feedback_module) -> None:
    """Test module initializes correctly."""
    assert feedback_module._initialized is True
    assert feedback_module.feedback_history == []
    assert len(feedback_module.metric_thresholds) > 0


def test_evaluate_generation(feedback_module, sample_generation_result) -> None:
    """Test evaluating a complete generation."""
    feedback = feedback_module.evaluate_generation(sample_generation_result)

    assert isinstance(feedback, GenerationFeedback)
    assert feedback.generation_id == "test-gen-001"
    assert 0 <= feedback.overall_quality <= 1
    assert len(feedback.metrics) > 0
    assert isinstance(feedback.suggestions, list)

    # Check that feedback was stored
    assert len(feedback_module.feedback_history) == 1
    assert feedback_module.feedback_history[0] == feedback


def test_visual_quality_evaluation(feedback_module) -> None:
    """Test visual quality metric evaluation."""
    visual_data = {
        "mesh_quality": 0.9,
        "texture_quality": 0.6,
        "polygon_count": 30000,
        "topology_score": 0.85,
    }

    metrics = feedback_module._evaluate_visual_quality(visual_data)

    assert len(metrics) == 2
    assert any(m.name == "mesh_quality" for m in metrics)
    assert any(m.name == "texture_quality" for m in metrics)
    assert all(m.category == "visual" for m in metrics)


def test_motion_quality_evaluation(feedback_module) -> None:
    """Test motion quality metric evaluation."""
    motion_data = {
        "smoothness_score": 0.8,
        "naturalness_score": 0.7,
        "fps": 30,
        "physics_accuracy": 0.75,
    }

    metrics = feedback_module._evaluate_motion_quality(motion_data)

    assert len(metrics) == 2
    assert any(m.name == "animation_smoothness" for m in metrics)
    assert any(m.name == "motion_naturalness" for m in metrics)
    assert all(m.category == "motion" for m in metrics)


def test_voice_quality_evaluation(feedback_module) -> None:
    """Test voice quality metric evaluation."""
    voice_data = {
        "clarity_score": 0.85,
        "emotional_expression": 0.7,
        "sample_rate": 44100,
        "emotion_range": 0.8,
    }

    metrics = feedback_module._evaluate_voice_quality(voice_data)

    assert len(metrics) == 2
    assert any(m.name == "voice_clarity" for m in metrics)
    assert any(m.name == "voice_expression" for m in metrics)
    assert all(m.category == "voice" for m in metrics)


def test_behavior_quality_evaluation(feedback_module) -> None:
    """Test behavior quality metric evaluation."""
    behavior_data = {
        "coherence_score": 0.9,
        "decision_quality": 0.6,
        "trait_consistency": 0.85,
        "logic_score": 0.7,
    }

    metrics = feedback_module._evaluate_behavior_quality(behavior_data)

    assert len(metrics) == 2
    assert any(m.name == "behavior_coherence" for m in metrics)
    assert any(m.name == "decision_making" for m in metrics)
    assert all(m.category == "behavior" for m in metrics)


def test_performance_evaluation(feedback_module) -> None:
    """Test performance metric evaluation."""
    perf_data = {"generation_time_seconds": 20, "peak_memory_mb": 400, "gpu_usage": 0.6}

    metrics = feedback_module._evaluate_performance(perf_data)

    assert len(metrics) == 2
    assert any(m.name == "generation_speed" for m in metrics)
    assert any(m.name == "resource_efficiency" for m in metrics)
    assert all(m.category == "performance" for m in metrics)


def test_generate_suggestions(feedback_module) -> None:
    """Test suggestion generation based on low metrics."""
    metrics = [
        QualityMetric("mesh_quality", 0.5, "visual"),
        QualityMetric("voice_clarity", 0.6, "voice"),
        QualityMetric("behavior_coherence", 0.9, "behavior"),
    ]

    suggestions = feedback_module._generate_suggestions(metrics)

    assert len(suggestions) >= 2  # Low mesh and voice quality
    assert any("mesh topology" in s for s in suggestions)
    assert any("noise" in s for s in suggestions)


def test_add_user_feedback(feedback_module, sample_generation_result) -> None:
    """Test adding user feedback to generation."""
    # First evaluate a generation
    feedback = feedback_module.evaluate_generation(sample_generation_result)

    # Add user feedback
    success = feedback_module.add_user_feedback(
        "test-gen-001", rating=0.8, comments="Great character, voice could be clearer"
    )

    assert success is True
    assert feedback.user_rating == 0.8
    assert feedback.comments == "Great character, voice could be clearer"

    # Test non-existent generation
    success = feedback_module.add_user_feedback("non-existent", 0.5)
    assert success is False


def test_quality_trends(feedback_module) -> None:
    """Test quality trend analysis."""
    # Generate multiple feedbacks
    for i in range(5):
        result = {
            "generation_id": f"gen-{i}",
            "visual_design": {"mesh_quality": 0.7 + i * 0.05, "texture_quality": 0.8},
            "performance": {
                "generation_time_seconds": 30 - i * 2,
                "peak_memory_mb": 500,
            },
        }
        feedback_module.evaluate_generation(result)

    trends = feedback_module.get_quality_trends(last_n=3)

    assert "overall_average" in trends
    assert "category_averages" in trends
    assert "visual" in trends["category_averages"]
    assert "performance" in trends["category_averages"]
    assert "improvement_areas" in trends


def test_export_feedback_report(feedback_module, sample_generation_result) -> None:
    """Test exporting comprehensive feedback report."""
    # Generate some feedback data
    for i in range(3):
        result = sample_generation_result.copy()
        result["generation_id"] = f"gen-{i}"
        feedback_module.evaluate_generation(result)

    report = feedback_module.export_feedback_report()

    assert report["total_generations"] == 3
    assert "overall_quality" in report
    assert "mean" in report["overall_quality"]
    assert "recent_trends" in report
    assert "common_suggestions" in report
    assert "quality_distribution" in report


def test_quality_distribution(feedback_module) -> None:
    """Test quality score distribution calculation."""
    # Create feedbacks with different quality levels
    quality_scores = [0.3, 0.5, 0.7, 0.9, 0.85]

    for i, score in enumerate(quality_scores):
        feedback = GenerationFeedback(generation_id=f"gen-{i}", overall_quality=score, metrics=[])
        feedback_module.feedback_history.append(feedback)

    distribution = feedback_module._get_quality_distribution()

    assert distribution["poor"] == 1  # 0.3
    assert distribution["fair"] == 1  # 0.5
    assert distribution["good"] == 1  # 0.7
    assert distribution["excellent"] == 2  # 0.9, 0.85


def test_empty_generation_result(feedback_module) -> None:
    """Test handling empty generation result."""
    empty_result = {"generation_id": "empty-gen"}

    feedback = feedback_module.evaluate_generation(empty_result)

    assert feedback.generation_id == "empty-gen"
    assert feedback.overall_quality == 0.0
    assert len(feedback.metrics) == 0
    assert len(feedback.suggestions) == 0
