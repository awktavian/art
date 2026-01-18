# SPDX-License-Identifier: MIT
"""Benchmarking infrastructure for K OS.

Scientific benchmarking system grounded in Active Inference principles.

K OS Intelligence = Individual Capability + Hive Intelligence + Active Inference

Benchmark Categories:
- Individual: HumanEval, MMLU, GSM8K, MBPP (traditional LLM benchmarks)
- Hive: Synergy, collaboration, knowledge sharing (collective intelligence)
- Active Inference: EFE computation, world model accuracy (K OS core)
- System: API latency, WebSocket, boot time (performance SLOs)
- Formal: Z3 proofs, safety verification (mathematical guarantees)
- Scientific: Chaos theory, G2 geometry, CBF (theoretical validation)

Quick Start:
    >>> from kagami.benchmarks import run_full_benchmark
    >>> result = await run_full_benchmark(quick=True)  # Fast mode
    >>> result = await run_full_benchmark(quick=False)  # Full suite

Using Registry (Recommended):
    >>> from kagami_benchmarks.core import get_registry, BenchmarkCategory
    >>> registry = get_registry()
    >>> suite = await registry.run_suite(categories=[BenchmarkCategory.ACTIVE_INFERENCE])

Structure:
    - kagami.benchmarks.core: Registry, statistics, receipts, storage
    - kagami.benchmarks.active_inference: EFE, world model benchmarks
    - kagami.benchmarks.ai: ML/AI benchmarks (HumanEval, MMLU, GSM8K, etc.)
    - kagami.benchmarks.system: System/API performance benchmarks
    - kagami.benchmarks.kernel: Kernel-level benchmarks
    - kagami.benchmarks.formal: Formal verification benchmarks
    - kagami.benchmarks.reasoning: ARC-AGI and reasoning benchmarks
"""

# Re-export AI benchmarks at top level for backward compatibility
from kagami_benchmarks.ai import (
    run_full_benchmark,
    run_gsm8k,
    run_hive_benchmark,
    run_hive_only,
    run_humaneval,
    run_individual_only,
    run_mbpp,
    run_mmlu,
    run_swebench_verified,
    run_webarena_smoke,
)

# New core infrastructure exports
try:
    pass

    _CORE_AVAILABLE = True
except ImportError:
    _CORE_AVAILABLE = False

# Active Inference benchmarks
try:
    pass

    _AI_BENCHMARKS_AVAILABLE = True
except ImportError:
    _AI_BENCHMARKS_AVAILABLE = False

__all__ = [
    # Master harness
    "run_full_benchmark",
    "run_gsm8k",
    # Hive benchmarks
    "run_hive_benchmark",
    "run_hive_only",
    "run_humaneval",
    "run_individual_only",
    "run_mbpp",
    "run_mmlu",
    # Individual benchmarks (legacy)
    "run_swebench_verified",
    "run_webarena_smoke",
]

# Add core exports if available
if _CORE_AVAILABLE:
    __all__.extend(
        [
            "BenchmarkRegistry",
            "BenchmarkResult",
            "BenchmarkSuite",
            "StatisticalSummary",
            "bootstrap_confidence_interval",
            "cohens_d",
            "compare_distributions",
            "get_registry",
            "get_reproducibility_info",
            "set_global_seed",
            "with_benchmark_receipts",
        ]
    )

# Add Active Inference exports if available
if _AI_BENCHMARKS_AVAILABLE:
    __all__.extend(
        [
            "run_efe_benchmark",
            "run_world_model_benchmark",
        ]
    )
