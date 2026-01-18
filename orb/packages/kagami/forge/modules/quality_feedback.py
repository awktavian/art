"""Quality Feedback Module for Forge Character Generation.

This module tracks generation quality metrics and provides feedback
for continuous improvement of the character generation pipeline.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class QualityMetric:
    """Individual quality metric measurement."""

    name: str
    value: float  # 0.0 to 1.0
    category: str  # visual, behavior, performance, etc.
    timestamp: datetime = field(default_factory=datetime.now)
    details: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class GenerationFeedback:
    """Feedback for a single generation."""

    generation_id: str
    overall_quality: float  # 0.0 to 1.0
    metrics: list[QualityMetric]
    user_rating: float | None = None  # User-provided rating
    comments: str | None = None
    suggestions: list[str] = field(default_factory=list[Any])
    timestamp: datetime = field(default_factory=datetime.now)


class QualityFeedbackModule:
    """Tracks and analyzes quality metrics for character generation."""

    def __init__(self) -> None:
        """Initialize the quality feedback module."""
        self.feedback_history: list[GenerationFeedback] = []
        self.metric_thresholds = {
            "mesh_quality": 0.7,
            "texture_quality": 0.7,
            "animation_quality": 0.6,
            "voice_quality": 0.7,
            "behavior_coherence": 0.8,
            "performance": 0.8,  # Speed/efficiency
        }
        self._initialized = True

    def evaluate_generation(self, generation_result: dict[str, Any]) -> GenerationFeedback:
        """Evaluate the quality of a character generation.

        Args:
            generation_result: Complete generation result including all modules.

        Returns:
            Quality feedback with metrics and suggestions.
        """
        generation_id = generation_result.get("generation_id", "unknown")
        metrics = []

        # Visual quality metrics
        if "visual_design" in generation_result:
            visual_metrics = self._evaluate_visual_quality(generation_result["visual_design"])
            metrics.extend(visual_metrics)

        # Animation quality metrics
        if "motion" in generation_result:
            motion_metrics = self._evaluate_motion_quality(generation_result["motion"])
            metrics.extend(motion_metrics)

        # Voice quality metrics
        if "voice" in generation_result:
            voice_metrics = self._evaluate_voice_quality(generation_result["voice"])
            metrics.extend(voice_metrics)

        # Behavior quality metrics
        if "behavior_ai" in generation_result:
            behavior_metrics = self._evaluate_behavior_quality(generation_result["behavior_ai"])
            metrics.extend(behavior_metrics)

        # Performance metrics
        if "performance" in generation_result:
            perf_metrics = self._evaluate_performance(generation_result["performance"])
            metrics.extend(perf_metrics)

        # Calculate overall quality
        if metrics:
            overall_quality = float(np.mean([m.value for m in metrics]))
        else:
            overall_quality = 0.0

        # Generate suggestions
        suggestions = self._generate_suggestions(metrics)

        # Create feedback
        feedback = GenerationFeedback(
            generation_id=generation_id,
            overall_quality=overall_quality,
            metrics=metrics,
            suggestions=suggestions,
        )

        # Store feedback
        self.feedback_history.append(feedback)

        return feedback

    def _evaluate_visual_quality(self, visual_data: dict[str, Any]) -> list[QualityMetric]:
        """Evaluate visual design quality."""
        metrics = []

        # Mesh quality
        mesh_score = visual_data.get("mesh_quality", 0.5)
        metrics.append(
            QualityMetric(
                name="mesh_quality",
                value=mesh_score,
                category="visual",
                details={
                    "polygon_count": visual_data.get("polygon_count", 0),
                    "topology_score": visual_data.get("topology_score", 0.5),
                },
            )
        )

        # Texture quality
        texture_score = visual_data.get("texture_quality", 0.5)
        metrics.append(
            QualityMetric(
                name="texture_quality",
                value=texture_score,
                category="visual",
                details={
                    "resolution": visual_data.get("texture_resolution", "1024x1024"),
                    "material_count": visual_data.get("material_count", 1),
                },
            )
        )

        return metrics

    def _evaluate_motion_quality(self, motion_data: dict[str, Any]) -> list[QualityMetric]:
        """Evaluate animation and motion quality."""
        metrics = []

        # Animation smoothness
        smoothness = motion_data.get("smoothness_score", 0.5)
        metrics.append(
            QualityMetric(
                name="animation_smoothness",
                value=smoothness,
                category="motion",
                details={
                    "fps": motion_data.get("fps", 30),
                    "keyframe_count": motion_data.get("keyframe_count", 0),
                },
            )
        )

        # Motion naturalness
        naturalness = motion_data.get("naturalness_score", 0.5)
        metrics.append(
            QualityMetric(
                name="motion_naturalness",
                value=naturalness,
                category="motion",
                details={
                    "physics_accuracy": motion_data.get("physics_accuracy", 0.5),
                    "gesture_variety": motion_data.get("gesture_variety", 0.5),
                },
            )
        )

        return metrics

    def _evaluate_voice_quality(self, voice_data: dict[str, Any]) -> list[QualityMetric]:
        """Evaluate voice synthesis quality."""
        metrics = []

        # Voice clarity
        clarity = voice_data.get("clarity_score", 0.5)
        metrics.append(
            QualityMetric(
                name="voice_clarity",
                value=clarity,
                category="voice",
                details={
                    "sample_rate": voice_data.get("sample_rate", 22050),
                    "noise_level": voice_data.get("noise_level", 0.1),
                },
            )
        )

        # Emotional expression
        expression = voice_data.get("emotional_expression", 0.5)
        metrics.append(
            QualityMetric(
                name="voice_expression",
                value=expression,
                category="voice",
                details={
                    "emotion_range": voice_data.get("emotion_range", 0.5),
                    "prosody_score": voice_data.get("prosody_score", 0.5),
                },
            )
        )

        return metrics

    def _evaluate_behavior_quality(self, behavior_data: dict[str, Any]) -> list[QualityMetric]:
        """Evaluate behavior and personality quality."""
        metrics = []

        # Personality coherence
        coherence = behavior_data.get("coherence_score", 0.5)
        metrics.append(
            QualityMetric(
                name="behavior_coherence",
                value=coherence,
                category="behavior",
                details={
                    "trait_consistency": behavior_data.get("trait_consistency", 0.5),
                    "response_variety": behavior_data.get("response_variety", 0.5),
                },
            )
        )

        # Decision making quality
        decision_quality = behavior_data.get("decision_quality", 0.5)
        metrics.append(
            QualityMetric(
                name="decision_making",
                value=decision_quality,
                category="behavior",
                details={
                    "logic_score": behavior_data.get("logic_score", 0.5),
                    "context_awareness": behavior_data.get("context_awareness", 0.5),
                },
            )
        )

        return metrics

    def _evaluate_performance(self, perf_data: dict[str, Any]) -> list[QualityMetric]:
        """Evaluate performance metrics."""
        metrics = []

        # Generation speed
        gen_time = perf_data.get("generation_time_seconds", 60)
        speed_score = min(1.0, 30.0 / gen_time)  # Target: 30 seconds
        metrics.append(
            QualityMetric(
                name="generation_speed",
                value=speed_score,
                category="performance",
                details={
                    "total_time": gen_time,
                    "module_times": perf_data.get("module_times", {}),
                },
            )
        )

        # Resource efficiency
        memory_mb = perf_data.get("peak_memory_mb", 1000)
        efficiency_score = min(1.0, 500.0 / memory_mb)  # Target: 500MB
        metrics.append(
            QualityMetric(
                name="resource_efficiency",
                value=efficiency_score,
                category="performance",
                details={
                    "peak_memory_mb": memory_mb,
                    "gpu_usage": perf_data.get("gpu_usage", 0.5),
                },
            )
        )

        return metrics

    def _generate_suggestions(self, metrics: list[QualityMetric]) -> list[str]:
        """Generate improvement suggestions based on metrics."""
        suggestions = []

        for metric in metrics:
            threshold = self.metric_thresholds.get(metric.name, 0.7)

            if metric.value < threshold:
                # Generate specific suggestions based on metric
                if metric.name == "mesh_quality":
                    suggestions.append(
                        f"Improve mesh topology (current: {metric.value:.2f}, target: {threshold})"
                    )
                elif metric.name == "texture_quality":
                    suggestions.append(
                        f"Enhance texture resolution or detail (current: {metric.value:.2f})"
                    )
                elif metric.name == "animation_smoothness":
                    suggestions.append("Increase keyframe density for smoother animation")
                elif metric.name == "voice_clarity":
                    suggestions.append("Reduce background noise in voice synthesis")
                elif metric.name == "behavior_coherence":
                    suggestions.append("Improve personality trait consistency")
                elif metric.name == "generation_speed":
                    suggestions.append("Optimize pipeline for faster generation")

        return suggestions

    def add_user_feedback(
        self, generation_id: str, rating: float, comments: str | None = None
    ) -> bool:
        """Add user feedback for a generation.

        Args:
            generation_id: ID of the generation.
            rating: User rating (0.0 to 1.0).
            comments: Optional user comments.

        Returns:
            True if feedback was added, False if generation not found.
        """
        for feedback in self.feedback_history:
            if feedback.generation_id == generation_id:
                feedback.user_rating = rating
                feedback.comments = comments
                return True

        return False

    def get_quality_trends(self, last_n: int = 10) -> dict[str, Any]:
        """Get quality trends over recent generations.

        Args:
            last_n: Number of recent generations to analyze.

        Returns:
            Dictionary with trend analysis.
        """
        if not self.feedback_history:
            return {"error": "No feedback history available"}

        recent = self.feedback_history[-last_n:]

        # Calculate averages by category
        category_scores: dict[str, list[float]] = {}
        metric_scores: dict[str, list[float]] = {}

        for feedback in recent:
            for metric in feedback.metrics:
                # By category
                if metric.category not in category_scores:
                    category_scores[metric.category] = []
                category_scores[metric.category].append(metric.value)

                # By metric name
                if metric.name not in metric_scores:
                    metric_scores[metric.name] = []
                metric_scores[metric.name].append(metric.value)

        # Calculate trends
        trends = {
            "overall_average": np.mean([f.overall_quality for f in recent]),
            "category_averages": {cat: np.mean(scores) for cat, scores in category_scores.items()},
            "metric_averages": {name: np.mean(scores) for name, scores in metric_scores.items()},
            "user_satisfaction": self._calculate_user_satisfaction(recent),
            "improvement_areas": self._identify_improvement_areas(metric_scores),
        }

        return trends

    def _calculate_user_satisfaction(self, feedback_list: list[GenerationFeedback]) -> float | None:
        """Calculate average user satisfaction from ratings."""
        ratings = [f.user_rating for f in feedback_list if f.user_rating is not None]
        return float(np.mean(ratings)) if ratings else None

    def _identify_improvement_areas(self, metric_scores: dict[str, list[float]]) -> list[str]:
        """Identify areas needing improvement based on scores."""
        areas = []

        for metric_name, scores in metric_scores.items():
            avg_score = np.mean(scores)
            threshold = self.metric_thresholds.get(metric_name, 0.7)

            if avg_score < threshold:
                areas.append(f"{metric_name} (avg: {avg_score:.2f}, target: {threshold})")

        return areas

    def export_feedback_report(self) -> dict[str, Any]:
        """Export comprehensive feedback report.

        Returns:
            Dictionary with full feedback analysis.
        """
        if not self.feedback_history:
            return {"error": "No feedback data available"}

        return {
            "total_generations": len(self.feedback_history),
            "overall_quality": {
                "mean": np.mean([f.overall_quality for f in self.feedback_history]),
                "std": np.std([f.overall_quality for f in self.feedback_history]),
                "min": min(f.overall_quality for f in self.feedback_history),
                "max": max(f.overall_quality for f in self.feedback_history),
            },
            "recent_trends": self.get_quality_trends(),
            "common_suggestions": self._get_common_suggestions(),
            "quality_distribution": self._get_quality_distribution(),
        }

    def _get_common_suggestions(self) -> list[tuple[str, int]]:
        """Get most common improvement suggestions."""
        suggestion_counts: dict[str, int] = {}

        for feedback in self.feedback_history:
            for suggestion in feedback.suggestions:
                # Normalize suggestion for counting
                key = suggestion.split("(")[0].strip()
                suggestion_counts[key] = suggestion_counts.get(key, 0) + 1

        # Sort by frequency
        return sorted(suggestion_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    def _get_quality_distribution(self) -> dict[str, int]:
        """Get distribution of quality scores."""
        bins = {"poor": 0, "fair": 0, "good": 0, "excellent": 0}

        for feedback in self.feedback_history:
            if feedback.overall_quality < 0.4:
                bins["poor"] += 1
            elif feedback.overall_quality < 0.6:
                bins["fair"] += 1
            elif feedback.overall_quality < 0.8:
                bins["good"] += 1
            else:
                bins["excellent"] += 1

        return bins
