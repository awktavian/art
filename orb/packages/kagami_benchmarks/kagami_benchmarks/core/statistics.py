# SPDX-License-Identifier: MIT
"""Statistical utilities for rigorous benchmark analysis.

Provides:
- Bootstrap confidence intervals
- Effect size calculations (Cohen's d)
- Distribution comparison tests
- Percentile computation
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from typing import Literal


def compute_percentile(sorted_samples: list[float], percentile: float) -> float:
    """Compute percentile from sorted samples.

    Uses linear interpolation method.

    Args:
        sorted_samples: Pre-sorted list of samples.
        percentile: Percentile to compute (0-100).

    Returns:
        The percentile value.
    """
    if not sorted_samples:
        return 0.0

    n = len(sorted_samples)
    if n == 1:
        return sorted_samples[0]

    # Compute index with linear interpolation
    idx = (percentile / 100.0) * (n - 1)
    lower_idx = int(idx)
    upper_idx = min(lower_idx + 1, n - 1)

    # Interpolate
    fraction = idx - lower_idx
    return sorted_samples[lower_idx] * (1 - fraction) + sorted_samples[upper_idx] * fraction


def bootstrap_confidence_interval(
    samples: list[float],
    confidence: float = 0.95,
    n_iterations: int = 1000,
    statistic: Literal["mean", "median"] = "mean",
    seed: int | None = None,
) -> tuple[float, float]:
    """Compute bootstrap confidence interval for a statistic.

    Bootstrap resampling provides non-parametric confidence intervals
    that don't assume normal distribution.

    Args:
        samples: Original samples.
        confidence: Confidence level (0.0-1.0).
        n_iterations: Number of bootstrap iterations.
        statistic: Statistic to compute CI for.
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (lower_bound, upper_bound).
    """
    if not samples:
        return (0.0, 0.0)

    if len(samples) == 1:
        return (samples[0], samples[0])

    # Set seed for reproducibility
    rng = random.Random(seed)

    # Select statistic function
    stat_fn = statistics.mean if statistic == "mean" else statistics.median

    # Generate bootstrap distribution
    bootstrap_stats = []
    n = len(samples)

    for _ in range(n_iterations):
        # Resample with replacement
        bootstrap_sample = [rng.choice(samples) for _ in range(n)]
        bootstrap_stats.append(stat_fn(bootstrap_sample))

    # Compute percentile CI
    bootstrap_stats.sort()
    alpha = 1 - confidence
    lower_idx = int((alpha / 2) * n_iterations)
    upper_idx = int((1 - alpha / 2) * n_iterations) - 1

    return (bootstrap_stats[lower_idx], bootstrap_stats[upper_idx])


def cohens_d(
    group1: list[float],
    group2: list[float],
    pooled: bool = True,
) -> float:
    """Compute Cohen's d effect size between two groups.

    Cohen's d measures the standardized difference between means:
    - Small effect: d ~ 0.2
    - Medium effect: d ~ 0.5
    - Large effect: d ~ 0.8

    Args:
        group1: First group of samples.
        group2: Second group of samples.
        pooled: Use pooled standard deviation.

    Returns:
        Cohen's d effect size.
    """
    if not group1 or not group2:
        return 0.0

    mean1 = statistics.mean(group1)
    mean2 = statistics.mean(group2)

    if pooled:
        # Pooled standard deviation
        n1 = len(group1)
        n2 = len(group2)

        if n1 < 2 or n2 < 2:
            return 0.0

        var1 = statistics.variance(group1)
        var2 = statistics.variance(group2)

        # Pooled variance
        pooled_var = ((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)
        pooled_std = pooled_var**0.5

        if pooled_std == 0:
            return 0.0

        return float((mean1 - mean2) / pooled_std)
    else:
        # Use first group's std
        if len(group1) < 2:
            return 0.0
        std1 = statistics.stdev(group1)
        if std1 == 0:
            return 0.0
        return (mean1 - mean2) / std1


@dataclass
class DistributionComparison:
    """Result of comparing two distributions."""

    effect_size: float  # Cohen's d
    effect_magnitude: str  # "negligible", "small", "medium", "large"
    mean_diff: float  # Difference in means
    relative_change: float  # Percentage change
    ci_lower: float  # CI for difference
    ci_upper: float  # CI for difference
    significant: bool  # CIs don't overlap zero

    @property
    def summary(self) -> str:
        """Human-readable summary."""
        direction = "increase" if self.mean_diff > 0 else "decrease"
        return (
            f"{self.effect_magnitude.title()} effect ({direction}): "
            f"{abs(self.relative_change):.1f}% "
            f"(95% CI: [{self.ci_lower:.2f}, {self.ci_upper:.2f}])"
        )


def compare_distributions(
    baseline: list[float],
    treatment: list[float],
    confidence: float = 0.95,
    n_bootstrap: int = 1000,
) -> DistributionComparison:
    """Compare two distributions with statistical rigor.

    Useful for A/B testing benchmark results.

    Args:
        baseline: Baseline measurements.
        treatment: Treatment measurements.
        confidence: Confidence level.
        n_bootstrap: Bootstrap iterations.

    Returns:
        DistributionComparison with effect size and significance.
    """
    if not baseline or not treatment:
        return DistributionComparison(
            effect_size=0.0,
            effect_magnitude="negligible",
            mean_diff=0.0,
            relative_change=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            significant=False,
        )

    # Effect size
    d = cohens_d(treatment, baseline)

    # Classify effect magnitude
    abs_d = abs(d)
    if abs_d < 0.2:
        magnitude = "negligible"
    elif abs_d < 0.5:
        magnitude = "small"
    elif abs_d < 0.8:
        magnitude = "medium"
    else:
        magnitude = "large"

    # Mean difference
    mean_baseline = statistics.mean(baseline)
    mean_treatment = statistics.mean(treatment)
    mean_diff = mean_treatment - mean_baseline

    # Relative change
    if mean_baseline != 0:
        relative_change = (mean_diff / mean_baseline) * 100
    else:
        relative_change = 0.0 if mean_diff == 0 else float("inf")

    # Bootstrap CI for the difference
    rng = random.Random(42)  # Fixed seed for reproducibility

    diff_bootstrap = []
    n_base = len(baseline)
    n_treat = len(treatment)

    for _ in range(n_bootstrap):
        boot_base = [rng.choice(baseline) for _ in range(n_base)]
        boot_treat = [rng.choice(treatment) for _ in range(n_treat)]
        diff_bootstrap.append(statistics.mean(boot_treat) - statistics.mean(boot_base))

    diff_bootstrap.sort()
    alpha = 1 - confidence
    lower_idx = int((alpha / 2) * n_bootstrap)
    upper_idx = int((1 - alpha / 2) * n_bootstrap) - 1

    ci_lower = diff_bootstrap[lower_idx]
    ci_upper = diff_bootstrap[upper_idx]

    # Significant if CI doesn't include zero
    significant = ci_lower > 0 or ci_upper < 0

    return DistributionComparison(
        effect_size=d,
        effect_magnitude=magnitude,
        mean_diff=mean_diff,
        relative_change=relative_change,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        significant=significant,
    )
