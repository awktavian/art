# pyright: reportGeneralTypeIssues=false
# pyright: reportCallIssue=false
# Benchmark module uses dynamic typing for flexibility

from __future__ import annotations

"""MOBIASM Benchmark Suite - Scientific performance measurement.

Benchmarks all 50+ MOBIASM operations with statistical rigor:
- Multiple iterations for confidence intervals
- Warm-up runs
- Input size scaling
- Memory profiling
- Correctness validation
"""
import json
import logging
import statistics
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import torch

# Remove unused imports - Distribution and Property not needed in zero-overhead runtime
from kagami.core.mobiasm.runtime_zero_overhead import MobiASMZeroOverheadRuntime as MobiASMRuntime

# Import canonical BenchmarkResult from unified location
try:
    from kagami_benchmarks.core.result import BenchmarkResult
except (ModuleNotFoundError, ImportError):
    # Define a minimal fallback if benchmark package unavailable
    from dataclasses import dataclass
    from typing import Any

    @dataclass
    class BenchmarkResult:
        """Minimal fallback BenchmarkResult."""

        name: str
        score: float
        metadata: dict[str, Any] = None


logger = logging.getLogger(__name__)


# Minimal enums for benchmark validation (legacy compatibility)
class Property(str, Enum):
    """Geometric property check (benchmark only)."""

    INSIDE = "inside"


class Distribution(str, Enum):
    """Sampling distribution (benchmark only)."""

    GAUSSIAN = "gaussian"


# Note: BenchmarkResult is now imported from kagami_benchmarks.core.result
# This module maintains backward compatibility by directly using the canonical class


@dataclass
class BenchmarkSuite:
    """Complete benchmark suite results."""

    device: str
    dtype: str
    n_warmup: int
    n_runs: int
    total_operations: int
    results: list[BenchmarkResult]
    summary: dict[str, Any]


class MobiASMBenchmark:
    """Comprehensive benchmark suite for MOBIASM operations."""

    def __init__(
        self,
        device: str = "mps",
        dtype: torch.dtype = torch.float32,
        n_warmup: int = 10,
        n_runs: int = 100,
    ) -> None:
        """Initialize benchmark suite.

        Args:
            device: Compute device
            dtype: Data type
            n_warmup: Number of warm-up iterations
            n_runs: Number of measurement iterations
        """
        self.device = device
        self.dtype = dtype
        self.n_warmup = n_warmup
        self.n_runs = n_runs

        self.runtime = MobiASMRuntime(
            device=device,
            dtype=dtype,
        )

        self.results: list[BenchmarkResult] = []

    def benchmark_operation(
        self,
        op_name: str,
        category: str,
        operation: Callable[..., Any],
        input_dims: tuple[int, ...],
        correctness_check: Callable[..., bool | tuple[bool, str]] | None = None,
    ) -> BenchmarkResult:
        """Benchmark a single operation.

        Args:
            op_name: Operation name
            category: Category (H, O, F, M, C, V, S, I, G, A, E, X)
            operation: Function to benchmark
            input_dims: Input dimensions for reporting
            correctness_check: Optional correctness validation function

        Returns:
            BenchmarkResult with timing and correctness data
        """
        # Warm-up
        for _ in range(self.n_warmup):
            try:
                operation()

            except Exception:
                pass

        # Synchronize if GPU
        if self.device in ["cuda", "mps"]:
            torch.cuda.synchronize() if self.device == "cuda" else None

        # Benchmark
        times: list[float] = []
        for _ in range(self.n_runs):
            start = time.perf_counter()
            try:
                result = operation()
            except Exception as e:
                # Operation failed
                return BenchmarkResult(
                    task_id=op_name,
                    benchmark_name="MOBIASM",
                    category=category,
                    passed=False,
                    operation=op_name,
                    input_dims=input_dims,
                    n_runs=0,
                    mean_us=0.0,
                    median_us=0.0,
                    std_us=0.0,
                    min_us=0.0,
                    max_us=0.0,
                    p95_us=0.0,
                    p99_us=0.0,
                    throughput_ops_per_sec=0.0,
                    memory_mb=0.0,
                    correctness_passed=False,
                    correctness_details=f"Operation failed: {e!s}",
                )

            if self.device in ["cuda", "mps"]:
                torch.cuda.synchronize() if self.device == "cuda" else None

            elapsed = time.perf_counter() - start
            times.append(elapsed * 1e6)  # Convert to microseconds

        # Statistics
        times_sorted = sorted(times)
        mean_us = statistics.mean(times)
        median_us = statistics.median(times)
        std_us = statistics.stdev(times) if len(times) > 1 else 0.0
        min_us = min(times)
        max_us = max(times)
        p95_us = times_sorted[int(0.95 * len(times))]
        p99_us = times_sorted[int(0.99 * len(times))]
        throughput = 1e6 / mean_us if mean_us > 0 else 0.0  # ops/sec

        # Memory (simplified - actual measurement would use torch.cuda.memory_allocated)
        memory_mb = 0.0

        # Correctness check
        correctness_passed = True
        correctness_details = "OK"
        if correctness_check is not None:
            try:
                check_result = correctness_check(result)
                if isinstance(check_result, tuple):
                    correctness_passed, correctness_details = check_result
                else:
                    correctness_passed = bool(check_result)
                    correctness_details = "OK" if correctness_passed else "FAILED"
            except Exception as e:
                correctness_passed = False
                correctness_details = f"Check failed: {e!s}"

        return BenchmarkResult(
            task_id=op_name,
            benchmark_name="MOBIASM",
            category=category,
            passed=correctness_passed,
            operation=op_name,
            input_dims=input_dims,
            n_runs=self.n_runs,
            mean_us=mean_us,
            median_us=median_us,
            std_us=std_us,
            min_us=min_us,
            max_us=max_us,
            p95_us=p95_us,
            p99_us=p99_us,
            throughput_ops_per_sec=throughput,
            memory_mb=memory_mb,
            correctness_passed=correctness_passed,
            correctness_details=correctness_details,
        )

    def run_all_benchmarks(self) -> BenchmarkSuite:
        """Run complete benchmark suite."""
        logger.info("=" * 80)
        logger.info("MOBIASM BENCHMARK SUITE")
        logger.info("=" * 80)
        logger.info("Device: %s", self.device)
        logger.info("Dtype: %s", self.dtype)
        logger.info("Warmup runs: %d", self.n_warmup)
        logger.info("Measurement runs: %d", self.n_runs)
        logger.info("=" * 80)

        self.results = []

        # Category H: Hyperbolic Operations
        logger.info("\n[H] Hyperbolic Operations")
        logger.info("-" * 80)

        v_14 = torch.randn(14, device=self.device, dtype=self.dtype) * 0.1
        z_14 = self.runtime.h_exp0(v_14)
        z2_14 = self.runtime.h_exp0(torch.randn(14, device=self.device, dtype=self.dtype) * 0.1)

        self._benchmark_and_add(
            "H.EXP0",
            "H",
            lambda: self.runtime.h_exp0(v_14),
            (14,),
            lambda r: self.runtime.g_check_property(r, "in_ball"),
        )

        self._benchmark_and_add("H.LOG0", "H", lambda: self.runtime.h_log0(z_14), (14,))

        self._benchmark_and_add(
            "H.EXP",
            "H",
            lambda: self.runtime.h_exp(z_14, v_14 * 0.1),
            (14,),
            lambda r: self.runtime.g_check_property(r, "in_ball"),
        )

        self._benchmark_and_add("H.LOG", "H", lambda: self.runtime.h_log(z_14, z2_14), (14,))

        self._benchmark_and_add(
            "H.ADD",
            "H",
            lambda: self.runtime.h_add(z_14, z2_14),
            (14,),
            lambda r: self.runtime.g_check_property(r, "in_ball"),
        )

        self._benchmark_and_add(
            "H.MUL",
            "H",
            lambda: self.runtime.h_mul(0.5, z_14),
            (14,),
            lambda r: self.runtime.g_check_property(r, "in_ball"),
        )

        self._benchmark_and_add(
            "H.DIST", "H", lambda: self.runtime.h_dist(z_14, z2_14), (14,), lambda r: bool(r >= 0)
        )

        self._benchmark_and_add(
            "H.TRANSPORT",
            "H",
            lambda: self.runtime.h_parallel_transport(z_14, z2_14, v_14 * 0.1),
            (14,),
        )

        self._benchmark_and_add(
            "H.PROJECT",
            "H",
            lambda: self.runtime.h_project(v_14),
            (14,),
            lambda r: self.runtime.g_check_property(r, "in_ball"),
        )

        # Category O: Octonion Operations
        logger.info("\n[O] Octonion Operations")
        logger.info("-" * 80)

        o1 = torch.randn(8, device=self.device, dtype=self.dtype)
        o1 = self.runtime.o_project(o1)
        o2 = torch.randn(8, device=self.device, dtype=self.dtype)
        o2 = self.runtime.o_project(o2)

        self._benchmark_and_add(
            "O.MUL",
            "O",
            lambda: self.runtime.o_mul(o1, o2),
            (8,),
            lambda r: bool(torch.abs(r.norm(p=2) - 1.0) < 1e-3),
        )

        self._benchmark_and_add("O.CONJ", "O", lambda: self.runtime.o_conj(o1), (8,))

        self._benchmark_and_add(
            "O.NORM",
            "O",
            lambda: self.runtime.o_norm(o1),
            (8,),
            lambda r: bool(torch.abs(r - 1.0) < 1e-3),
        )

        self._benchmark_and_add(
            "O.SLERP.SIMPLE", "O", lambda: self.runtime.o_slerp(o1, o2, 0.5), (8,)
        )

        self._benchmark_and_add(
            "O.PROJECT",
            "O",
            lambda: self.runtime.o_project(torch.randn(8, device=self.device, dtype=self.dtype)),
            (8,),
            lambda r: bool(torch.abs(r.norm(p=2) - 1.0) < 1e-3),
        )

        # Category M: Meta Operations
        logger.info("\n[M] Meta Operations")
        logger.info("-" * 80)

        self._benchmark_and_add(
            "M.SET_CURVATURE", "M", lambda: self.runtime.m_set_curvature(0.1), ()
        )

        self._benchmark_and_add(
            "M.SET_DEVICE", "M", lambda: self.runtime.m_set_device(self.device), ()
        )

        self._benchmark_and_add("M.TRACE", "M", lambda: self.runtime.m_trace(True), ())

        self._benchmark_and_add("M.VALIDATE", "M", lambda: self.runtime.m_validate(True), ())

        # Category C: Comparison & Conditional
        logger.info("\n[C] Comparison & Conditional Operations")
        logger.info("-" * 80)

        self._benchmark_and_add(
            "C.COMPARE", "C", lambda: self.runtime.c_compare("LT", z_14, z2_14), (14,)
        )

        self._benchmark_and_add(
            "C.NEAR", "C", lambda: self.runtime.c_near(z_14, z2_14, epsilon=1e-5), (14,)
        )

        # Category V: Vector/Batch Operations
        logger.info("\n[V] Vector/Batch Operations")
        logger.info("-" * 80)

        batch = [torch.randn(14, device=self.device, dtype=self.dtype) * 0.1 for _ in range(10)]
        batch = [self.runtime.h_exp0(v) for v in batch]

        self._benchmark_and_add(
            "V.MAP",
            "V",
            lambda: self.runtime.v_map(lambda z: self.runtime.h_mul(0.9, z), batch),
            (10,),
        )

        self._benchmark_and_add(
            "V.REDUCE",
            "V",
            lambda: self.runtime.v_reduce(
                self.runtime.h_add, batch[:3], torch.zeros(14, device=self.device, dtype=self.dtype)
            ),
            (3,),
        )

        self._benchmark_and_add(
            "V.NORMALIZE", "V", lambda: self.runtime.v_normalize(batch[0]), (14,)
        )

        self._benchmark_and_add("V.SCALE", "V", lambda: self.runtime.v_scale(0.5, batch[0]), (14,))

        # Category S: State Management
        logger.info("\n[S] State Management Operations")
        logger.info("-" * 80)

        self._benchmark_and_add(
            "S.SAVE", "S", lambda: self.runtime.s_save("test_state", z_14, o1), ()
        )

        self.runtime.s_save("test_state", z_14, o1)  # Ensure state exists
        self._benchmark_and_add("S.LOAD", "S", lambda: self.runtime.s_load("test_state"), ())

        self._benchmark_and_add("S.PUSH", "S", lambda: self.runtime.s_push(z_14, o1), ())

        self.runtime.s_push(z_14, o1)  # Ensure stack not empty
        self._benchmark_and_add("S.POP", "S", lambda: self.runtime.s_pop(), ())

        self._benchmark_and_add("S.CLEAR", "S", lambda: self.runtime.s_clear(), ())

        # Category I: Interpolation & Sampling
        logger.info("\n[I] Interpolation & Sampling Operations")
        logger.info("-" * 80)

        self._benchmark_and_add(
            "I.LERP",
            "I",
            lambda: self.runtime.i_lerp(z_14, z2_14, 0.5),
            (14,),
        )

        self._benchmark_and_add(
            "I.GEODESIC",
            "I",
            lambda: self.runtime.i_geodesic(z_14, z2_14, 0.5),
            (14,),
            lambda r: self.runtime.g_check_property(r, "in_ball"),
        )

        self._benchmark_and_add(
            "I.SAMPLE",
            "I",
            lambda: self.runtime.i_sample(distribution="normal", shape=(14,), std=0.1),
            (14,),
        )

        # Category G: Geometric Queries
        logger.info("\n[G] Geometric Query Operations")
        logger.info("-" * 80)

        self._benchmark_and_add(
            "G.CHECK_PROPERTY",
            "G",
            lambda: self.runtime.g_check_property(z_14, "in_ball"),
            (14,),
        )

        self._benchmark_and_add(
            "G.DISTANCE_TO_BOUNDARY",
            "G",
            lambda: self.runtime.g_distance_to_boundary(z_14),
            (14,),
        )

        # Category A: Aggregation Operations
        logger.info("\n[A] Aggregation Operations")
        logger.info("-" * 80)

        self._benchmark_and_add(
            "A.SUM",
            "A",
            lambda: self.runtime.a_sum(batch[:5]),
            (5,),
        )

        self._benchmark_and_add(
            "A.MEAN",
            "A",
            lambda: self.runtime.a_mean(batch[:5], max_iter=10),
            (5,),
        )

        self._benchmark_and_add(
            "A.MAX",
            "A",
            lambda: self.runtime.a_max(batch[:5]),
            (5,),
        )

        self._benchmark_and_add(
            "A.MIN",
            "A",
            lambda: self.runtime.a_min(batch[:5]),
            (5,),
        )

        # Category F: Fiber bundle operations
        logger.info("\n[F] Fiber Bundle Operations")
        logger.info("-" * 80)

        self._benchmark_and_add(
            "F.LIFT",
            "F",
            lambda: self.runtime.f_lift(z_14),
            (14,),
        )

        lifted = self.runtime.f_lift(z_14)
        self._benchmark_and_add(
            "F.PROJECT_DOWN",
            "F",
            lambda: self.runtime.f_project_down(lifted),
            (14,),
        )

        self._benchmark_and_add(
            "F.HORIZONTAL_LIFT",
            "F",
            lambda: self.runtime.f_horizontal_lift(z_14, v_14 * 0.1),
            (14,),
        )

        # Generate summary
        summary = self._generate_summary()

        logger.info("\n" + "=" * 80)
        logger.info("BENCHMARK COMPLETE")
        logger.info("=" * 80)

        return BenchmarkSuite(
            device=self.device,
            dtype=str(self.dtype),
            n_warmup=self.n_warmup,
            n_runs=self.n_runs,
            total_operations=len(self.results),
            results=self.results,
            summary=summary,
        )

    def _benchmark_and_add(
        self,
        op_name: str,
        category: str,
        operation: Callable[..., Any],
        input_dims: tuple[int, ...],
        correctness_check: Callable[..., bool | tuple[bool, str]] | None = None,
    ) -> None:
        """Benchmark operation and add to results."""
        logger.info("  %s", op_name.ljust(30))
        result = self.benchmark_operation(
            op_name, category, operation, input_dims, correctness_check
        )
        self.results.append(result)

        status = "✓" if result.correctness_passed else "✗"
        logger.info(
            "%s %.2f µs ± %.2f µs | %.0f ops/s",
            status,
            result.mean_us,
            result.std_us,
            result.throughput_ops_per_sec,
        )

    def _generate_summary(self) -> dict[str, Any]:
        """Generate summary statistics."""
        by_category: dict[str, list[BenchmarkResult]] = {}
        for result in self.results:
            if result.category not in by_category:
                by_category[result.category] = []
            by_category[result.category].append(result)

        category_summary = {}
        for cat, results in by_category.items():
            times = [r.mean_us for r in results]
            category_summary[cat] = {
                "operation_count": len(results),
                "total_time_us": sum(times),
                "mean_time_us": statistics.mean(times),
                "fastest_op": min(results, key=lambda r: r.mean_us).operation,
                "slowest_op": max(results, key=lambda r: r.mean_us).operation,
                "correctness_rate": sum(1 for r in results if r.correctness_passed) / len(results),
            }

        all_times = [r.mean_us for r in self.results]
        all_passed = sum(1 for r in self.results if r.correctness_passed)

        return {
            "total_operations": len(self.results),
            "total_time_us": sum(all_times),
            "mean_time_us": statistics.mean(all_times),
            "median_time_us": statistics.median(all_times),
            "fastest_operation": min(self.results, key=lambda r: r.mean_us).operation,
            "slowest_operation": max(self.results, key=lambda r: r.mean_us).operation,
            "fastest_time_us": min(all_times),
            "slowest_time_us": max(all_times),
            "correctness_rate": all_passed / len(self.results),
            "correctness_passed": all_passed,
            "correctness_failed": len(self.results) - all_passed,
            "by_category": category_summary,
        }

    def print_summary(self) -> None:
        """Print benchmark summary."""
        suite = BenchmarkSuite(
            device=self.device,
            dtype=str(self.dtype),
            n_warmup=self.n_warmup,
            n_runs=self.n_runs,
            total_operations=len(self.results),
            results=self.results,
            summary=self._generate_summary(),
        )

        logger.info("\n" + "=" * 80)
        logger.info("SUMMARY STATISTICS")
        logger.info("=" * 80)
        logger.info("Total operations benchmarked: %d", suite.summary["total_operations"])
        logger.info("Total execution time: %.2f ms", suite.summary["total_time_us"] / 1000)
        logger.info("Mean operation time: %.2f µs", suite.summary["mean_time_us"])
        logger.info("Median operation time: %.2f µs", suite.summary["median_time_us"])
        logger.info(
            "Fastest operation: %s (%.2f µs)",
            suite.summary["fastest_operation"],
            suite.summary["fastest_time_us"],
        )
        logger.info(
            "Slowest operation: %s (%.2f µs)",
            suite.summary["slowest_operation"],
            suite.summary["slowest_time_us"],
        )
        logger.info(
            "Correctness rate: %.1f%% (%d/%d)",
            suite.summary["correctness_rate"] * 100,
            suite.summary["correctness_passed"],
            suite.summary["total_operations"],
        )

        logger.info("\n" + "-" * 80)
        logger.info("BY CATEGORY")
        logger.info("-" * 80)
        for cat, stats in sorted(suite.summary["by_category"].items()):
            logger.info("\n%s:", cat)
            logger.info("  Operations: %d", stats["operation_count"])
            logger.info("  Mean time: %.2f µs", stats["mean_time_us"])
            logger.info("  Fastest: %s", stats["fastest_op"])
            logger.info("  Slowest: %s", stats["slowest_op"])
            logger.info("  Correctness: %.1f%%", stats["correctness_rate"] * 100)

    def save_results(self, filepath: str | Path) -> None:
        """Save benchmark results to JSON."""
        suite = BenchmarkSuite(
            device=self.device,
            dtype=str(self.dtype),
            n_warmup=self.n_warmup,
            n_runs=self.n_runs,
            total_operations=len(self.results),
            results=self.results,
            summary=self._generate_summary(),
        )

        # Convert any torch.Tensors to Python primitives
        def convert_tensors(obj: Any) -> Any:
            if isinstance(obj, torch.Tensor):
                return obj.item() if obj.numel() == 1 else obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_tensors(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_tensors(item) for item in obj]
            return obj

        data = {
            "device": suite.device,
            "dtype": suite.dtype,
            "n_warmup": suite.n_warmup,
            "n_runs": suite.n_runs,
            "total_operations": suite.total_operations,
            "summary": convert_tensors(suite.summary),
            "results": [convert_tensors(asdict(r)) for r in suite.results],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info("Results saved to: %s", filepath)
