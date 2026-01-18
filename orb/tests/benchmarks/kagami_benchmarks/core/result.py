# SPDX-License-Identifier: MIT
"""Unified benchmark result types with statistical rigor.

Canonical result types for all K OS benchmarks.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class BenchmarkStatus(str, Enum):
    """Benchmark execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StatisticalSummary:
    """Statistical summary of benchmark measurements.

    Provides rigorous statistical analysis including:
    - Central tendency (mean, median)
    - Dispersion (std, IQR)
    - Percentiles (p50, p95, p99)
    - Confidence intervals via bootstrap
    """

    n_samples: int
    mean: float
    median: float
    std: float
    min_val: float
    max_val: float
    p50: float
    p95: float
    p99: float
    iqr: float  # Interquartile range
    ci_lower: float  # 95% CI lower bound
    ci_upper: float  # 95% CI upper bound
    ci_method: str = "bootstrap"  # Method used for CI

    @classmethod
    def from_samples(
        cls,
        samples: list[float],
        ci_confidence: float = 0.95,
        n_bootstrap: int = 1000,
    ) -> StatisticalSummary:
        """Compute statistical summary from samples.

        Args:
            samples: Raw measurement samples.
            ci_confidence: Confidence level for CI.
            n_bootstrap: Number of bootstrap iterations.

        Returns:
            StatisticalSummary with computed statistics.
        """
        import statistics

        from kagami_benchmarks.core.statistics import (
            bootstrap_confidence_interval,
            compute_percentile,
        )

        if not samples:
            return cls(
                n_samples=0,
                mean=0.0,
                median=0.0,
                std=0.0,
                min_val=0.0,
                max_val=0.0,
                p50=0.0,
                p95=0.0,
                p99=0.0,
                iqr=0.0,
                ci_lower=0.0,
                ci_upper=0.0,
            )

        n = len(samples)
        mean = statistics.mean(samples)
        median = statistics.median(samples)
        std = statistics.stdev(samples) if n > 1 else 0.0

        # Percentiles
        sorted_samples = sorted(samples)
        p25 = compute_percentile(sorted_samples, 25)
        p50 = compute_percentile(sorted_samples, 50)
        p75 = compute_percentile(sorted_samples, 75)
        p95 = compute_percentile(sorted_samples, 95)
        p99 = compute_percentile(sorted_samples, 99)

        # Confidence interval via bootstrap
        ci_lower, ci_upper = bootstrap_confidence_interval(
            samples,
            confidence=ci_confidence,
            n_iterations=n_bootstrap,
        )

        return cls(
            n_samples=n,
            mean=mean,
            median=median,
            std=std,
            min_val=min(samples),
            max_val=max(samples),
            p50=p50,
            p95=p95,
            p99=p99,
            iqr=p75 - p25,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
        )

    def meets_slo(self, p95_target: float, p99_target: float) -> bool:
        """Check if result meets SLO targets."""
        return self.p95 <= p95_target and self.p99 <= p99_target

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class BenchmarkResult:
    """Canonical result of a benchmark execution.

    Used across all benchmark modules. Includes:
    - Identification (task_id, benchmark_name)
    - Outcome (passed, score, status)
    - Timing (duration_ms, latency_stats)
    - Provenance (correlation_id, reproducibility_info)
    - Details (error, metadata)

    Supports both AI benchmarks (task_id, dataset, subject) and
    performance benchmarks (operation, input_dims, timing stats).
    """

    # Identification
    task_id: str
    benchmark_name: str
    category: str

    # Outcome
    passed: bool
    score: float = 0.0
    status: BenchmarkStatus = BenchmarkStatus.COMPLETED

    # Timing
    duration_ms: float = 0.0
    latency_stats: StatisticalSummary | None = None

    # Provenance
    correlation_id: str = ""
    timestamp: float = field(default_factory=time.time)
    reproducibility_info: dict[str, Any] = field(default_factory=dict)

    # Details
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Legacy compatibility fields (from benchmarks/shared.py)
    dataset: str = ""
    """Dataset name (e.g., 'mmlu', 'arc', 'humaneval'). Alias for benchmark_name."""

    subject: str = ""
    """Subject or category within the dataset. Alias for category."""

    schema_name: str | None = None
    """For schema benchmarks: name of the schema."""

    strategy: Any | None = None
    """Generation strategy used."""

    success: bool | None = None
    """Alternative success indicator. Alias for passed."""

    json_valid: bool | None = None
    """For JSON benchmarks: whether JSON is valid."""

    schema_valid: bool | None = None
    """For schema benchmarks: whether result validates against schema."""

    generation_time: float | None = None
    """Alternative time measurement (seconds). Computed from duration_ms."""

    details: dict[str, Any] | None = None
    """Additional benchmark-specific details. Alias for metadata."""

    # MOBIASM-specific fields (from core/mobiasm/benchmark.py)
    operation: str = ""
    """Operation name (for MOBIASM benchmarks). Alias for task_id."""

    input_dims: tuple[int, ...] = field(default_factory=tuple)
    """Input dimensions for reporting (MOBIASM)."""

    n_runs: int = 0
    """Number of measurement runs (MOBIASM)."""

    mean_us: float = 0.0
    """Mean latency in microseconds (MOBIASM)."""

    median_us: float = 0.0
    """Median latency in microseconds (MOBIASM)."""

    std_us: float = 0.0
    """Standard deviation in microseconds (MOBIASM)."""

    min_us: float = 0.0
    """Minimum latency in microseconds (MOBIASM)."""

    max_us: float = 0.0
    """Maximum latency in microseconds (MOBIASM)."""

    p95_us: float = 0.0
    """95th percentile in microseconds (MOBIASM)."""

    p99_us: float = 0.0
    """99th percentile in microseconds (MOBIASM)."""

    throughput_ops_per_sec: float = 0.0
    """Throughput in ops/sec (MOBIASM)."""

    memory_mb: float = 0.0
    """Memory usage in MB (MOBIASM)."""

    correctness_passed: bool = True
    """Correctness check result (MOBIASM)."""

    correctness_details: str = "OK"
    """Correctness check details (MOBIASM)."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        d = asdict(self)
        d["status"] = self.status.value
        if self.latency_stats:
            d["latency_stats"] = self.latency_stats.to_dict()
        return d

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkResult:
        """Create from dictionary."""
        data = data.copy()
        if "status" in data:
            data["status"] = BenchmarkStatus(data["status"])
        if data.get("latency_stats"):
            data["latency_stats"] = StatisticalSummary(**data["latency_stats"])
        return cls(**data)


@dataclass
class BenchmarkSuite:
    """Collection of benchmark results with aggregate statistics.

    Represents a complete benchmark run with:
    - Individual results
    - Aggregate scores by category
    - Overall metrics
    - Reproducibility information
    """

    name: str
    description: str
    results: list[BenchmarkResult] = field(default_factory=list)

    # Aggregate scores
    overall_score: float = 0.0
    category_scores: dict[str, float] = field(default_factory=dict)

    # Metadata
    correlation_id: str = ""
    timestamp: float = field(default_factory=time.time)
    duration_s: float = 0.0
    reproducibility_info: dict[str, Any] = field(default_factory=dict)

    # Status
    total_passed: int = 0
    total_failed: int = 0
    total_skipped: int = 0

    def add_result(self, result: BenchmarkResult) -> None:
        """Add a benchmark result to the suite."""
        self.results.append(result)

        # Update counters
        if result.status == BenchmarkStatus.COMPLETED:
            if result.passed:
                self.total_passed += 1
            else:
                self.total_failed += 1
        elif result.status == BenchmarkStatus.SKIPPED:
            self.total_skipped += 1

    def compute_aggregate_scores(
        self,
        category_weights: dict[str, float] | None = None,
    ) -> None:
        """Compute aggregate scores from results.

        Args:
            category_weights: Optional weights for each category.
        """
        if not self.results:
            return

        # Group by category
        categories: dict[str, list[BenchmarkResult]] = {}
        for result in self.results:
            if result.category not in categories:
                categories[result.category] = []
            categories[result.category].append(result)

        # Compute category scores
        self.category_scores = {}
        for cat, cat_results in categories.items():
            completed = [r for r in cat_results if r.status == BenchmarkStatus.COMPLETED]
            if completed:
                self.category_scores[cat] = sum(r.score for r in completed) / len(completed)
            else:
                self.category_scores[cat] = 0.0

        # Compute overall score
        if category_weights:
            total_weight = 0.0
            weighted_sum = 0.0
            for cat, score in self.category_scores.items():
                weight = category_weights.get(cat, 1.0)
                weighted_sum += score * weight
                total_weight += weight
            self.overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        else:
            # Simple average
            if self.category_scores:
                self.overall_score = sum(self.category_scores.values()) / len(self.category_scores)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "results": [r.to_dict() for r in self.results],
            "overall_score": self.overall_score,
            "category_scores": self.category_scores,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "duration_s": self.duration_s,
            "reproducibility_info": self.reproducibility_info,
            "total_passed": self.total_passed,
            "total_failed": self.total_failed,
            "total_skipped": self.total_skipped,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Benchmark Suite: {self.name}",
            f"  {self.description}",
            "",
            f"Overall Score: {self.overall_score:.3f}",
            f"Results: {self.total_passed} passed, {self.total_failed} failed, {self.total_skipped} skipped",
            f"Duration: {self.duration_s:.2f}s",
            "",
            "Category Scores:",
        ]

        for cat, score in sorted(self.category_scores.items()):
            lines.append(f"  {cat}: {score:.3f}")

        return "\n".join(lines)
