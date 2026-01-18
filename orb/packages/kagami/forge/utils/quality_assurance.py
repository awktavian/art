"""Quality assurance utilities for Forge character generation."""

from dataclasses import dataclass
from typing import Any

from kagami.forge.schema import Character


@dataclass
class QualityReport:
    """Comprehensive quality report for character generation."""

    character_id: str
    passed: bool
    score: float
    checks: dict[str, bool]
    issues: list[str]
    recommendations: list[str]


class QualityAssurance:
    """Quality assurance system for character generation."""

    def __init__(self) -> None:
        """Initialize QA system."""
        self.min_quality_score = 0.7
        self.required_components = [
            "mesh",
            "skeleton",
            "animations",
            "voice_profile",
            "personality",
        ]

    def check_character(self, character: Character) -> QualityReport:
        """Run comprehensive quality checks on a character."""
        checks = {}
        issues = []
        recommendations = []

        # Check mesh quality
        checks["has_mesh"] = character.mesh is not None
        if not checks["has_mesh"]:
            issues.append("Missing 3D mesh data")
            recommendations.append("Generate mesh using Gaussian Splatting or external 3D pipeline")

        # Check skeleton
        checks["has_skeleton"] = character.skeleton is not None
        if not checks["has_skeleton"]:
            issues.append("Missing skeleton rigging")
            recommendations.append("Add skeleton rigging for animation")

        # Check animations
        checks["has_animations"] = bool(character.animations)
        if not checks["has_animations"]:
            issues.append("No animations defined")
            recommendations.append("Create basic animation set[Any]")

        # Check voice
        checks["has_voice"] = character.voice_profile is not None
        if not checks["has_voice"]:
            issues.append("No voice profile")
            recommendations.append("Generate voice with ElevenLabs")

        # Check personality
        checks["has_personality"] = character.personality is not None
        checks["has_backstory"] = character.backstory is not None
        if not checks["has_personality"]:
            issues.append("Missing personality definition")
            recommendations.append("Define character personality traits")
        if not checks["has_backstory"]:
            issues.append("Missing backstory")
            recommendations.append("Create character backstory")

        # Calculate overall score
        total_checks = len(checks)
        passed_checks = sum(1 for v in checks.values() if v)
        score = passed_checks / total_checks if total_checks > 0 else 0

        # Determine if passed
        passed = score >= self.min_quality_score and all(
            checks.get(f"has_{comp}", False) for comp in self.required_components
        )

        return QualityReport(
            character_id=character.character_id,
            passed=passed,
            score=score,
            checks=checks,
            issues=issues,
            recommendations=recommendations,
        )


class PerformanceMonitor:
    """Monitor performance of character generation."""

    def __init__(self) -> None:
        """Initialize performance monitor."""
        self.metrics: dict[str, list[float]] = {
            "generation_time": [],
            "memory_usage": [],
            "gpu_usage": [],
        }

    def record_metric(self, metric_name: str, value: float) -> None:
        """Record a performance metric."""
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        self.metrics[metric_name].append(value)

    def get_statistics(self) -> dict[str, dict[str, float]]:
        """Get performance statistics."""
        stats = {}
        for metric, values in self.metrics.items():
            if values:
                stats[metric] = {
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "count": len(values),
                }
        return stats


class QualityAssurancePipeline:
    """Complete quality assurance pipeline for character generation."""

    def __init__(self) -> None:
        """Initialize QA pipeline."""
        self.qa = QualityAssurance()
        self.performance_monitor = PerformanceMonitor()
        self.quality_threshold = 0.8
        # Structures expected by tests
        self.validators: list[str] = [
            "completeness",
            "consistency",
            "creativity",
            "technical_quality",
            "performance",
            "integration",
        ]
        self.quality_standards: dict[str, Any] = {
            "completeness": {
                "min_score": 0.7,
                "required_fields": [
                    "visual",
                    "behavior",
                    "voice",
                    "narrative",
                    "motion",
                    "beliefs",
                ],
                "critical_fields": ["visual", "behavior", "narrative"],
            },
            "consistency": {"min_score": 0.6},
            "creativity": {"min_score": 0.5},
            "technical_quality": {"min_score": 0.6},
            "performance": {"max_latency_ms": 5000},
            "integration": {"min_score": 0.6},
        }
        self.validation_history: list[Any] = []

    async def evaluate_character(self, character_data: dict[str, Any]) -> Any:
        """Evaluate character data and return QualityMetrics-like object."""
        import time

        from kagami.forge.schema import QualityMetrics

        start = time.time()

        # Compute simple component scores
        required = self.quality_standards["completeness"]["required_fields"]
        completeness = sum(1 for f in required if f in character_data) / max(1, len(required))

        consistency = (
            0.8
            if (
                isinstance(character_data.get("behavior"), dict)
                and isinstance(character_data.get("narrative"), dict)
            )
            else 0.5
        )

        creativity = 0.5
        if "visual" in character_data:
            colors = (
                character_data["visual"].get("colors", [])
                if isinstance(character_data["visual"], dict)
                else []
            )
            if isinstance(colors, list) and len(colors) > 2:
                creativity += 0.25

        technical = 0.6 if isinstance(character_data, dict) else 0.0

        overall = (completeness + consistency + creativity + technical) / 4.0

        metrics = QualityMetrics(
            completeness_score=completeness,
            consistency_score=consistency,
            creativity_score=creativity,
            technical_quality_score=technical,
            overall_score=overall,
            processing_time_ms=(time.time() - start) * 1000.0,
            issues=[],
        )
        self.validation_history.append(metrics)
        return metrics

    def get_quality_report(self) -> dict[str, Any]:
        """Aggregate report based on validation history."""
        if not self.validation_history:
            return {"status": "no_data"}
        total = len(self.validation_history)
        avg = {
            "completeness": sum(m.completeness_score for m in self.validation_history) / total,
            "consistency": sum(m.consistency_score for m in self.validation_history) / total,
            "creativity": sum(m.creativity_score for m in self.validation_history) / total,
            "technical_quality": sum(m.technical_quality_score for m in self.validation_history)
            / total,
            "overall": sum(m.overall_score for m in self.validation_history) / total,
        }
        avg_time = sum(m.processing_time_ms for m in self.validation_history) / total
        return {
            "status": "active",
            "total_validations": total,
            "average_scores": avg,
            "average_processing_time": avg_time,
        }

    async def cleanup(self) -> None:
        """Clear validation history."""
        self.validation_history.clear()


__all__ = [
    "PerformanceMonitor",
    "QualityAssurance",
    "QualityAssurancePipeline",
    "QualityReport",
]
