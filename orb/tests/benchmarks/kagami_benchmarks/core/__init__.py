# SPDX-License-Identifier: MIT
"""Core benchmarking infrastructure for K OS.

Provides:
- Unified result types with statistical rigor
- Benchmark registry with metadata
- Receipt emission wrapper
- Reproducibility utilities
- Historical result tracking
"""

from kagami_benchmarks.core.receipts import (
    BenchmarkReceiptEmitter,
    with_benchmark_receipts,
)
from kagami_benchmarks.core.registry import BenchmarkRegistry, get_registry
from kagami_benchmarks.core.reproducibility import (
    ReproducibilityContext,
    get_reproducibility_info,
    set_global_seed,
)
from kagami_benchmarks.core.result import (
    BenchmarkResult,
    BenchmarkSuite,
    StatisticalSummary,
)
from kagami_benchmarks.core.statistics import (
    bootstrap_confidence_interval,
    cohens_d,
    compare_distributions,
    compute_percentile,
)

__all__ = [
    # Receipts
    "BenchmarkReceiptEmitter",
    # Registry
    "BenchmarkRegistry",
    # Results
    "BenchmarkResult",
    "BenchmarkSuite",
    "ReproducibilityContext",
    "StatisticalSummary",
    # Statistics
    "bootstrap_confidence_interval",
    "cohens_d",
    "compare_distributions",
    "compute_percentile",
    "get_registry",
    "get_reproducibility_info",
    # Reproducibility
    "set_global_seed",
    "with_benchmark_receipts",
]
