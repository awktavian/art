"""Master Benchmark Harness.

Orchestrates all AI benchmarks for K OS system evaluation.
Provides unified interface for running individual or combined benchmarks.

Benchmark Categories:
- Individual: HumanEval, MMLU, GSM8K, MBPP (traditional benchmarks)
- Agentic: SWE-bench, WebArena (agent capabilities)
- Hive: Collective intelligence (multi-agent emergence)
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkConfig:
    """Configuration for a single benchmark."""

    name: str
    runner: Callable[..., dict[str, Any]]
    category: str
    weight: float = 1.0
    default_samples: int = 10
    enabled: bool = True


@dataclass
class MasterBenchmarkResult:
    """Aggregated results from all benchmarks."""

    individual_score: float
    agentic_score: float
    hive_score: float
    overall_score: float
    benchmark_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    total_duration_s: float = 0.0
    timestamp: float = field(default_factory=time.time)


class MasterBenchmarkHarness:
    """Master harness for orchestrating all K OS benchmarks."""

    def __init__(self) -> None:
        """Initialize master harness with benchmark registry."""
        self._benchmarks: dict[str, BenchmarkConfig] = {}
        self._register_benchmarks()

    def _register_benchmarks(self) -> None:
        """Register all available benchmarks."""
        # Individual benchmarks (traditional LLM evaluation)
        from kagami_benchmarks.ai.gsm8k_runner import run_gsm8k
        from kagami_benchmarks.ai.humaneval_runner import run_humaneval
        from kagami_benchmarks.ai.mbpp_runner import run_mbpp
        from kagami_benchmarks.ai.mmlu_runner import run_mmlu

        self._benchmarks["humaneval"] = BenchmarkConfig(
            name="HumanEval",
            runner=run_humaneval,
            category="individual",
            weight=1.0,
            default_samples=10,
        )

        self._benchmarks["mmlu"] = BenchmarkConfig(
            name="MMLU",
            runner=run_mmlu,
            category="individual",
            weight=1.0,
            default_samples=20,
        )

        self._benchmarks["gsm8k"] = BenchmarkConfig(
            name="GSM8K",
            runner=run_gsm8k,
            category="individual",
            weight=1.0,
            default_samples=20,
        )

        self._benchmarks["mbpp"] = BenchmarkConfig(
            name="MBPP",
            runner=run_mbpp,
            category="individual",
            weight=0.8,
            default_samples=10,
        )

        # Agentic benchmarks (agent capabilities)
        from kagami_benchmarks.ai.swebench_runner import run_verified as run_swebench
        from kagami_benchmarks.ai.webarena_smoke import run_smoke as run_webarena

        self._benchmarks["swebench"] = BenchmarkConfig(
            name="SWE-bench",
            runner=run_swebench,
            category="agentic",
            weight=1.5,
            default_samples=5,
        )

        self._benchmarks["webarena"] = BenchmarkConfig(
            name="WebArena",
            runner=run_webarena,
            category="agentic",
            weight=1.0,
            default_samples=5,
        )

        # Hive benchmarks (collective intelligence)
        from kagami_benchmarks.ai.hive_intelligence_benchmark import run_hive_benchmark

        self._benchmarks["hive"] = BenchmarkConfig(
            name="Hive Intelligence",
            runner=run_hive_benchmark,
            category="hive",
            weight=1.2,
            default_samples=3,
        )

    def get_available_benchmarks(self) -> list[str]:
        """Get list of available benchmark names."""
        return list(self._benchmarks.keys())

    def get_benchmark_info(self) -> dict[str, dict[str, Any]]:
        """Get information about all registered benchmarks."""
        return {
            name: {
                "name": config.name,
                "category": config.category,
                "weight": config.weight,
                "default_samples": config.default_samples,
                "enabled": config.enabled,
            }
            for name, config in self._benchmarks.items()
        }

    async def run_benchmark(  # type: ignore[no-untyped-def]
        self,
        benchmark_name: str,
        num_samples: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Run a single benchmark.

        Args:
            benchmark_name: Name of benchmark to run.
            num_samples: Number of samples (None = use default).
            **kwargs: Additional benchmark-specific arguments.

        Returns:
            Benchmark results dictionary.
        """
        if benchmark_name not in self._benchmarks:
            return {
                "status": "error",
                "error": f"Unknown benchmark: {benchmark_name}",
            }

        config = self._benchmarks[benchmark_name]
        samples = num_samples or config.default_samples

        logger.info(f"Running {config.name} benchmark ({samples} samples)")
        start_time = time.time()

        try:
            result = config.runner(num_samples=samples, **kwargs)
            result["duration_s"] = time.time() - start_time
            result["benchmark"] = benchmark_name
            return result
        except Exception as e:
            logger.error(f"Benchmark {benchmark_name} failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "benchmark": benchmark_name,
                "duration_s": time.time() - start_time,
            }

    def _calculate_category_score(
        self,
        results: dict[str, dict[str, Any]],
        category: str,
    ) -> float:
        """Calculate weighted score for a category.

        Args:
            results: All benchmark results.
            category: Category to calculate score for.

        Returns:
            Weighted average score for category.
        """
        category_benchmarks = [
            (name, config)
            for name, config in self._benchmarks.items()
            if config.category == category and name in results
        ]

        if not category_benchmarks:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0

        for name, config in category_benchmarks:
            result = results.get(name, {})
            score = result.get("score", 0.0)

            if result.get("status") == "completed":
                weighted_sum += score * config.weight
                total_weight += config.weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    async def run_individual_benchmarks(  # type: ignore[no-untyped-def]
        self,
        num_samples: int | None = None,
        **kwargs,
    ) -> dict[str, dict[str, Any]]:
        """Run all individual benchmarks.

        Args:
            num_samples: Number of samples per benchmark.
            **kwargs: Additional arguments.

        Returns:
            Dictionary of benchmark results.
        """
        results = {}
        individual_benchmarks = [
            name
            for name, config in self._benchmarks.items()
            if config.category == "individual" and config.enabled
        ]

        for name in individual_benchmarks:
            results[name] = await self.run_benchmark(name, num_samples, **kwargs)

        return results

    async def run_hive_benchmarks(  # type: ignore[no-untyped-def]
        self,
        num_samples: int | None = None,
        **kwargs,
    ) -> dict[str, dict[str, Any]]:
        """Run all hive benchmarks.

        Args:
            num_samples: Number of samples per benchmark.
            **kwargs: Additional arguments.

        Returns:
            Dictionary of benchmark results.
        """
        results = {}
        hive_benchmarks = [
            name
            for name, config in self._benchmarks.items()
            if config.category == "hive" and config.enabled
        ]

        for name in hive_benchmarks:
            results[name] = await self.run_benchmark(name, num_samples, **kwargs)

        return results

    async def run_full_benchmark(  # type: ignore[no-untyped-def]
        self,
        num_samples: int | None = None,
        categories: list[str] | None = None,
        **kwargs,
    ) -> MasterBenchmarkResult:
        """Run full benchmark suite.

        Args:
            num_samples: Number of samples per benchmark.
            categories: Categories to run (None = all).
            **kwargs: Additional arguments.

        Returns:
            MasterBenchmarkResult with all scores.
        """
        start_time = time.time()
        categories = categories or ["individual", "agentic", "hive"]

        all_results: dict[str, dict[str, Any]] = {}

        # Run benchmarks by category
        for category in categories:
            category_benchmarks = [
                name
                for name, config in self._benchmarks.items()
                if config.category == category and config.enabled
            ]

            for name in category_benchmarks:
                logger.info(f"Running {name}...")
                result = await self.run_benchmark(name, num_samples, **kwargs)
                all_results[name] = result

        # Calculate category scores
        individual_score = self._calculate_category_score(all_results, "individual")
        agentic_score = self._calculate_category_score(all_results, "agentic")
        hive_score = self._calculate_category_score(all_results, "hive")

        # Overall score (weighted combination)
        category_weights = {
            "individual": 0.4,
            "agentic": 0.35,
            "hive": 0.25,
        }

        overall_score = 0.0
        for cat, weight in category_weights.items():
            if cat in categories:
                cat_score = self._calculate_category_score(all_results, cat)
                overall_score += cat_score * weight

        # Normalize if not all categories run
        if len(categories) < 3:
            total_weight = sum(category_weights[c] for c in categories)
            overall_score /= total_weight

        duration = time.time() - start_time

        logger.info(
            f"Full Benchmark Complete: "
            f"overall={overall_score:.3f}, "
            f"individual={individual_score:.3f}, "
            f"agentic={agentic_score:.3f}, "
            f"hive={hive_score:.3f}"
        )

        return MasterBenchmarkResult(
            individual_score=individual_score,
            agentic_score=agentic_score,
            hive_score=hive_score,
            overall_score=overall_score,
            benchmark_results=all_results,
            total_duration_s=duration,
        )


# Module-level functions for backwards compatibility
_harness: MasterBenchmarkHarness | None = None


def _get_harness() -> MasterBenchmarkHarness:
    """Get or create harness singleton."""
    global _harness
    if _harness is None:
        _harness = MasterBenchmarkHarness()
    return _harness


def run_full_benchmark(  # type: ignore[no-untyped-def]
    num_samples: int | None = None,
    categories: list[str] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Run full benchmark suite.

    Args:
        num_samples: Number of samples per benchmark.
        categories: Categories to run (None = all).
        **kwargs: Additional arguments.

    Returns:
        Dictionary with benchmark results.
    """
    harness = _get_harness()

    try:
        result = asyncio.run(harness.run_full_benchmark(num_samples, categories, **kwargs))
        return {
            "overall_score": result.overall_score,
            "individual_score": result.individual_score,
            "agentic_score": result.agentic_score,
            "hive_score": result.hive_score,
            "benchmark_results": result.benchmark_results,
            "total_duration_s": result.total_duration_s,
            "status": "completed",
        }
    except Exception as e:
        logger.error(f"Full benchmark failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
        }


def run_individual_only(  # type: ignore[no-untyped-def]
    num_samples: int | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Run individual benchmarks only.

    Args:
        num_samples: Number of samples per benchmark.
        **kwargs: Additional arguments.

    Returns:
        Dictionary with benchmark results.
    """
    return run_full_benchmark(num_samples, categories=["individual"], **kwargs)


def run_hive_only(  # type: ignore[no-untyped-def]
    num_samples: int | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Run hive benchmarks only.

    Args:
        num_samples: Number of samples per benchmark.
        **kwargs: Additional arguments.

    Returns:
        Dictionary with benchmark results.
    """
    return run_full_benchmark(num_samples, categories=["hive"], **kwargs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Run a quick test with minimal samples
    result = run_full_benchmark(num_samples=2, categories=["individual"])
    print("\nBenchmark Result:")
    print(f"  Overall Score: {result.get('overall_score', 0):.3f}")
    print(f"  Individual Score: {result.get('individual_score', 0):.3f}")
    print(f"  Duration: {result.get('total_duration_s', 0):.1f}s")
    print(f"  Status: {result.get('status')}")
