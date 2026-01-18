from __future__ import annotations

"""Scientific Layer: Study & Systematize system performance."""
import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FailurePattern:
    """Identified failure pattern from analysis."""

    route: str
    error_type: str
    occurrences: int
    duration_days: float
    average_duration_ms: float
    root_cause_hypothesis: str
    confidence: float


@dataclass
class Experiment:
    """Proposed experiment to test improvement hypothesis."""

    name: str
    hypothesis: str
    treatment: dict[str, Any]
    duration_seconds: int
    success_criteria: dict[str, float]


@dataclass
class ExperimentResult:
    """Result of running an experiment."""

    experiment_name: str
    improvement: float
    confidence: float
    recommendation: str  # "adopt"|"reject"|"needs_more_data"
    metrics: dict[str, Any]


@dataclass
class AnalysisReport:
    """Analysis of system performance."""

    timestamp: datetime
    window_hours: int
    failure_patterns: list[FailurePattern]
    experiments: list[Experiment]
    recommendations: list[str]
    performance_trends: dict[str, float]


class ScientificLayer:
    """Analyzes system performance and proposes improvements.

    This layer observes the Technological Layer's execution,
    identifies patterns, and designs experiments for optimization.
    """

    def __init__(self) -> None:
        self._receipt_cache: list[dict[str, Any]] = []
        self._experiment_history: list[ExperimentResult] = []
        self._pattern_memory: dict[str, FailurePattern] = {}

    async def analyze_receipts_window(self, hours: int = 24) -> AnalysisReport:
        """Analyze recent receipts for patterns."""
        logger.info(f"Scientific Layer: Analyzing {hours}h window")

        # Fetch recent receipts
        receipts = await self._fetch_receipts(hours)

        if not receipts:
            return AnalysisReport(
                timestamp=datetime.utcnow(),
                window_hours=hours,
                failure_patterns=[],
                experiments=[],
                recommendations=["Insufficient data for analysis"],
                performance_trends={},
            )

        # Identify failure patterns
        failures = [r for r in receipts if r.get("status") == "error"]
        failure_patterns = self._cluster_failures(failures)

        # Analyze performance trends
        trends = self._analyze_trends(receipts)

        # Propose experiments
        experiments = []
        if trends.get("error_rate", 0) > 0.05:  # 5% error rate
            experiments.append(self._design_robustness_experiment(failure_patterns))
        if trends.get("latency_increase", 0) > 1.2:  # 20% slower
            experiments.append(self._design_optimization_experiment(receipts))

        # Generate recommendations
        recommendations = self._generate_recommendations(failure_patterns, trends)

        return AnalysisReport(
            timestamp=datetime.utcnow(),
            window_hours=hours,
            failure_patterns=failure_patterns,
            experiments=experiments,
            recommendations=recommendations,
            performance_trends=trends,
        )

    async def run_experiment(self, experiment: Experiment) -> ExperimentResult:
        """Execute A/B test or controlled change."""
        logger.info(f"Running experiment: {experiment.name}")

        # Baseline metrics
        control_metrics = await self._baseline_metrics()

        # Apply treatment
        await self._apply_treatment(experiment.treatment)

        # Observe for duration
        await asyncio.sleep(experiment.duration_seconds)

        # Collect treatment metrics
        treatment_metrics = await self._collect_metrics()

        # Revert treatment
        await self._revert_treatment(experiment.treatment)

        # Compute improvement
        improvement = self._compute_improvement(control_metrics, treatment_metrics)
        confidence = self._statistical_significance(control_metrics, treatment_metrics)

        # Decide recommendation
        recommendation = "adopt" if improvement > 0.1 and confidence > 0.95 else "reject"

        result = ExperimentResult(
            experiment_name=experiment.name,
            improvement=improvement,
            confidence=confidence,
            recommendation=recommendation,
            metrics={
                "control": control_metrics,
                "treatment": treatment_metrics,
            },
        )

        self._experiment_history.append(result)

        return result

    async def _fetch_receipts(self, hours: int) -> list[dict[str, Any]]:
        """Fetch receipts from the last N hours."""
        # Try to fetch from receipt store
        try:
            from kagami.core.receipts.service import get_unified_receipt_storage

            receipts_store = get_unified_receipt_storage()
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            # search() doesn't support 'since' yet, using raw list[Any]
            # In production, search() should be enhanced to support time filters
            all_receipts = receipts_store.search(limit=10000)
            receipts = [
                r for r in all_receipts if r.get("ts") and datetime.fromisoformat(r["ts"]) >= cutoff
            ]
            return receipts
        except Exception as e:
            logger.debug(f"Could not fetch receipts: {e}")
            return []

    def _cluster_failures(self, failures: list[dict[str, Any]]) -> list[FailurePattern]:
        """Cluster failures by route and error type."""
        clusters: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list[Any])

        for failure in failures:
            route = failure.get("operation", "unknown")
            error = failure.get("error", "unknown")
            key = (route, error)
            clusters[key].append(failure)

        patterns = []
        for (route, error_type), cluster in clusters.items():
            if len(cluster) >= 3:  # Minimum 3 occurrences
                durations = [c.get("duration_ms", 0) for c in cluster if "duration_ms" in c]
                avg_duration = float(np.mean(durations)) if durations else 0.0

                # Estimate duration in days
                timestamps = [
                    datetime.fromisoformat(c["timestamp"]) for c in cluster if "timestamp" in c
                ]
                if len(timestamps) >= 2:
                    duration_days = (max(timestamps) - min(timestamps)).total_seconds() / 86400
                else:
                    duration_days = 0.0

                # Generate hypothesis
                hypothesis = self._generate_root_cause_hypothesis(route, error_type, cluster)

                pattern = FailurePattern(
                    route=route,
                    error_type=error_type,
                    occurrences=len(cluster),
                    duration_days=duration_days,
                    average_duration_ms=avg_duration,
                    root_cause_hypothesis=hypothesis,
                    confidence=min(1.0, len(cluster) / 10),
                )
                patterns.append(pattern)

        return patterns

    def _generate_root_cause_hypothesis(
        self, route: str, error_type: str, cluster: list[dict[str, Any]]
    ) -> str:
        """Generate hypothesis for root cause."""
        # Simple heuristics for common patterns
        if error_type == "timeout":
            return "Slow downstream dependency or database query"
        elif error_type == "validation_error":
            return "Input schema mismatch or missing field"
        elif error_type == "unknown_app":
            return "Routing configuration issue"
        elif "database" in error_type.lower():
            return "Database connection or query issue"
        else:
            return f"Repeated {error_type} on {route}"

    def _analyze_trends(self, receipts: list[dict[str, Any]]) -> dict[str, float]:
        """Analyze performance trends."""
        trends = {}

        # Error rate trend
        error_count = sum(1 for r in receipts if r.get("status") == "error")
        trends["error_rate"] = error_count / max(1, len(receipts))

        # Latency trend
        durations = [
            r.get("duration_ms", 0)
            for r in receipts
            if "duration_ms" in r and r.get("duration_ms", 0) > 0
        ]
        if durations:
            trends["avg_latency_ms"] = float(np.mean(durations))
            trends["p99_latency_ms"] = float(np.percentile(durations, 99))

            # Compare to baseline (first half vs second half)
            mid = len(durations) // 2
            first_half = durations[:mid]
            second_half = durations[mid:]
            if first_half and second_half:
                trends["latency_increase"] = np.mean(second_half) / max(1, np.mean(first_half))
        else:
            trends["latency_increase"] = 1.0

        return trends

    def _design_robustness_experiment(self, patterns: list[FailurePattern]) -> Experiment:
        """Design experiment to improve robustness."""
        # Find most common failure
        if patterns:
            primary_pattern = max(patterns, key=lambda p: p.occurrences)
            hypothesis = f"Adding retry logic will reduce {primary_pattern.error_type} failures"
        else:
            hypothesis = "Increasing timeout will reduce failures"

        return Experiment(
            name="robustness_improvement",
            hypothesis=hypothesis,
            treatment={"retry_enabled": True, "max_retries": 3},
            duration_seconds=300,  # 5 minutes
            success_criteria={"error_rate": 0.03},  # Under 3%
        )

    def _design_optimization_experiment(self, receipts: list[dict[str, Any]]) -> Experiment:
        """Design experiment to optimize latency."""
        return Experiment(
            name="latency_optimization",
            hypothesis="Enabling caching will reduce latency",
            treatment={"cache_enabled": True, "cache_ttl_seconds": 60},
            duration_seconds=300,
            success_criteria={"avg_latency_ms": 50},  # Under 50ms
        )

    def _generate_recommendations(
        self,
        patterns: list[FailurePattern],
        trends: dict[str, float],
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # High error rate
        if trends.get("error_rate", 0) > 0.05:
            recommendations.append(
                f"Error rate is {trends['error_rate']:.1%}. "
                "Consider implementing retry logic or improving input validation."
            )

        # High latency
        if trends.get("p99_latency_ms", 0) > 100:
            recommendations.append(
                f"P99 latency is {trends['p99_latency_ms']:.0f}ms. "
                "Consider adding caching or optimizing database queries."
            )

        # Repeated patterns
        for pattern in patterns[:3]:  # Top 3
            if pattern.occurrences > 10:
                recommendations.append(
                    f"Pattern: {pattern.route} failing with {pattern.error_type} "
                    f"({pattern.occurrences} times). Hypothesis: {pattern.root_cause_hypothesis}"
                )

        if not recommendations:
            recommendations.append("System performing within normal parameters.")

        return recommendations

    async def _baseline_metrics(self) -> dict[str, float]:
        """Collect baseline metrics from Prometheus."""
        try:
            from kagami.core.receipts.service import get_unified_receipt_storage

            receipts_store = get_unified_receipt_storage()
            # Get last 100 receipts for baseline
            recent = receipts_store.search(limit=100)
            if not recent:
                return {}

            durations = [r.get("duration_ms", 0) for r in recent if "duration_ms" in r]
            errors = sum(1 for r in recent if r.get("status") == "error")

            return {
                "avg_latency_ms": float(np.mean(durations)) if durations else 0.0,
                "error_rate": errors / max(1, len(recent)),
                "throughput": float(len(recent)),
            }
        except Exception as e:
            logger.debug(f"Could not collect baseline: {e}")
            return {}

    async def _apply_treatment(self, treatment: dict[str, Any]) -> None:
        """Apply experimental treatment."""
        logger.info(f"Applying treatment: {treatment}")
        # In real implementation, this would modify system config

    async def _revert_treatment(self, treatment: dict[str, Any]) -> None:
        """Revert experimental treatment."""
        logger.info(f"Reverting treatment: {treatment}")

    async def _collect_metrics(self) -> dict[str, float]:
        """Collect current metrics from Prometheus."""
        # Reuse baseline collection logic for consistency
        return await self._baseline_metrics()

    def _compute_improvement(self, control: dict[str, float], treatment: dict[str, float]) -> float:
        """Compute percentage improvement."""
        if not control or not treatment:
            return 0.0

        # Weighted improvement across metrics
        improvements = []
        if "avg_latency_ms" in control and "avg_latency_ms" in treatment:
            latency_improvement = (
                control["avg_latency_ms"] - treatment["avg_latency_ms"]
            ) / control["avg_latency_ms"]
            improvements.append(latency_improvement)

        if "error_rate" in control and "error_rate" in treatment:
            error_improvement = (control["error_rate"] - treatment["error_rate"]) / max(
                0.001, control["error_rate"]
            )
            improvements.append(error_improvement)

        return float(np.mean(improvements)) if improvements else 0.0

    def _statistical_significance(
        self, control: dict[str, float], treatment: dict[str, float]
    ) -> float:
        """Compute statistical confidence using improvement magnitude."""
        if not control or not treatment:
            return 0.0

        # Compute confidence based on effect size
        improvements = []
        for key in ["avg_latency_ms", "error_rate"]:
            if key in control and key in treatment:
                if control[key] > 0:
                    effect = abs(control[key] - treatment[key]) / control[key]
                    improvements.append(effect)

        if not improvements:
            return 0.0

        # Higher effect sizes = higher confidence (sigmoid-like mapping)
        avg_effect = float(np.mean(improvements))
        confidence = 1.0 / (1.0 + np.exp(-10 * (avg_effect - 0.1)))
        return float(min(0.99, max(0.01, confidence)))
