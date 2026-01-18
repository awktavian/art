# SPDX-License-Identifier: MIT
"""Timed Circuit Testing Framework.

Implements hardware-inspired circuit tracing for performance measurement:
- Continuity Testing: Data flow verification
- Signal Injection: Known input → measured output
- Boundary Scan: Module boundary timing
- Time-Domain Reflectometry: Error trace analysis

Created: December 22, 2025
"""

from __future__ import annotations

import functools
import gc
import logging
import statistics
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class PerformanceResult:
    """Result of a timed performance test."""

    name: str
    mean_ms: float
    std_ms: float
    min_ms: float
    max_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    iterations: int
    throughput_ops_per_sec: float
    memory_delta_mb: float = 0.0
    passed: bool = True
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        """Human-readable summary."""
        status = "✅" if self.passed else "❌"
        return (
            f"{status} {self.name}: "
            f"mean={self.mean_ms:.3f}ms, p95={self.p95_ms:.3f}ms, "
            f"throughput={self.throughput_ops_per_sec:.1f} ops/s"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "mean_ms": self.mean_ms,
            "std_ms": self.std_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "iterations": self.iterations,
            "throughput_ops_per_sec": self.throughput_ops_per_sec,
            "memory_delta_mb": self.memory_delta_mb,
            "passed": self.passed,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class TimedCircuitTest:
    """Configuration for a timed circuit test."""

    name: str
    function: Callable[..., Any]
    args: tuple = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    warmup_iterations: int = 5
    test_iterations: int = 100
    timeout_ms: float = 10000.0  # 10 seconds max
    expected_max_ms: float | None = None  # Threshold for pass/fail
    expected_throughput: float | None = None  # Min ops/sec


# =============================================================================
# CIRCUIT TIMER
# =============================================================================


class CircuitTimer:
    """High-precision timer for circuit tracing."""

    def __init__(self, enable_gc_control: bool = True):
        """Initialize circuit timer.

        Args:
            enable_gc_control: Disable GC during measurement for consistent results
        """
        self.enable_gc_control = enable_gc_control
        self._timings: list[float] = []

    def reset(self) -> None:
        """Reset collected timings."""
        self._timings = []

    def time_once(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> tuple[Any, float]:
        """Time a single function call.

        Returns:
            Tuple of (result, elapsed_ms)
        """
        if self.enable_gc_control:
            gc.disable()

        try:
            start = time.perf_counter_ns()
            result = func(*args, **kwargs)
            end = time.perf_counter_ns()
            elapsed_ms = (end - start) / 1_000_000
            self._timings.append(elapsed_ms)
            return result, elapsed_ms
        finally:
            if self.enable_gc_control:
                gc.enable()

    def time_iterations(
        self,
        func: Callable[..., Any],
        iterations: int,
        warmup: int = 5,
        *args: Any,
        **kwargs: Any,
    ) -> list[float]:
        """Time multiple iterations of a function.

        Args:
            func: Function to time
            iterations: Number of timed iterations
            warmup: Number of warmup iterations (not timed)
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            List of elapsed times in milliseconds
        """
        # Warmup (not timed)
        for _ in range(warmup):
            func(*args, **kwargs)

        # Force GC before measurement
        gc.collect()

        timings = []
        if self.enable_gc_control:
            gc.disable()

        try:
            for _ in range(iterations):
                start = time.perf_counter_ns()
                func(*args, **kwargs)
                end = time.perf_counter_ns()
                timings.append((end - start) / 1_000_000)
        finally:
            if self.enable_gc_control:
                gc.enable()

        self._timings.extend(timings)
        return timings

    def compute_statistics(self, timings: list[float]) -> dict[str, float]:
        """Compute statistics from timing data.

        Args:
            timings: List of elapsed times in milliseconds

        Returns:
            Dictionary with mean, std, min, max, p50, p95, p99
        """
        if not timings:
            return {
                "mean_ms": 0.0,
                "std_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            }

        sorted_timings = sorted(timings)
        n = len(sorted_timings)

        return {
            "mean_ms": statistics.mean(timings),
            "std_ms": statistics.stdev(timings) if n > 1 else 0.0,
            "min_ms": sorted_timings[0],
            "max_ms": sorted_timings[-1],
            "p50_ms": sorted_timings[int(n * 0.5)],
            "p95_ms": sorted_timings[int(n * 0.95)] if n >= 20 else sorted_timings[-1],
            "p99_ms": sorted_timings[int(n * 0.99)] if n >= 100 else sorted_timings[-1],
        }


# =============================================================================
# DECORATOR FOR TIMED FUNCTIONS
# =============================================================================


def timed(
    name: str | None = None,
    log_result: bool = True,
    threshold_ms: float | None = None,
) -> Callable[[F], F]:
    """Decorator to time function execution.

    Args:
        name: Name for logging (defaults to function name)
        log_result: Whether to log timing results
        threshold_ms: Log warning if execution exceeds this threshold

    Example:
        @timed("e8_quantize", threshold_ms=10.0)
        def quantize(x):
            return nearest_e8(x)
    """

    def decorator(func: F) -> F:
        func_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter_ns()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
                if log_result:
                    logger.debug(f"⏱️ {func_name}: {elapsed_ms:.3f}ms")
                if threshold_ms and elapsed_ms > threshold_ms:
                    logger.warning(
                        f"⚠️ {func_name} exceeded threshold: {elapsed_ms:.3f}ms > {threshold_ms}ms"
                    )

        return wrapper  # type: ignore

    return decorator


@contextmanager
def profile_function(name: str) -> Any:
    """Context manager for profiling a code block.

    Example:
        with profile_function("encode_batch"):
            result = model.encode(batch)
    """
    start = time.perf_counter_ns()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        logger.info(f"⏱️ {name}: {elapsed_ms:.3f}ms")


# =============================================================================
# TEST RUNNER
# =============================================================================


def run_timed_circuit_test(test: TimedCircuitTest) -> PerformanceResult:
    """Run a single timed circuit test.

    Args:
        test: Test configuration

    Returns:
        PerformanceResult with timing statistics
    """
    timer = CircuitTimer()
    metadata: dict[str, Any] = {}

    try:
        # Measure memory before
        gc.collect()
        import tracemalloc

        tracemalloc.start()
        mem_before = tracemalloc.get_traced_memory()[0]

        # Run timed iterations
        timings = timer.time_iterations(  # type: ignore[misc]
            test.function,
            *test.args,
            iterations=test.test_iterations,
            warmup=test.warmup_iterations,
            **test.kwargs,
        )

        # Measure memory after
        mem_after = tracemalloc.get_traced_memory()[0]
        tracemalloc.stop()
        memory_delta_mb = (mem_after - mem_before) / (1024 * 1024)

        # Compute statistics
        stats = timer.compute_statistics(timings)

        # Compute throughput
        total_time_sec = sum(timings) / 1000
        throughput = len(timings) / total_time_sec if total_time_sec > 0 else 0

        # Check pass/fail
        passed = True
        if test.expected_max_ms and stats["p95_ms"] > test.expected_max_ms:
            passed = False
            metadata["threshold_exceeded"] = True
            metadata["expected_max_ms"] = test.expected_max_ms

        if test.expected_throughput and throughput < test.expected_throughput:
            passed = False
            metadata["throughput_below_expected"] = True
            metadata["expected_throughput"] = test.expected_throughput

        return PerformanceResult(
            name=test.name,
            mean_ms=stats["mean_ms"],
            std_ms=stats["std_ms"],
            min_ms=stats["min_ms"],
            max_ms=stats["max_ms"],
            p50_ms=stats["p50_ms"],
            p95_ms=stats["p95_ms"],
            p99_ms=stats["p99_ms"],
            iterations=test.test_iterations,
            throughput_ops_per_sec=throughput,
            memory_delta_mb=memory_delta_mb,
            passed=passed,
            metadata=metadata,
        )

    except Exception as e:
        logger.error(f"❌ Circuit test {test.name} failed: {e}")
        return PerformanceResult(
            name=test.name,
            mean_ms=0.0,
            std_ms=0.0,
            min_ms=0.0,
            max_ms=0.0,
            p50_ms=0.0,
            p95_ms=0.0,
            p99_ms=0.0,
            iterations=0,
            throughput_ops_per_sec=0.0,
            passed=False,
            error=str(e),
        )


def run_timed_circuit_tests(
    tests: list[TimedCircuitTest],
    parallel: bool = False,
) -> list[PerformanceResult]:
    """Run multiple timed circuit tests.

    Args:
        tests: List of test configurations
        parallel: Run tests in parallel (not recommended for timing accuracy)

    Returns:
        List of PerformanceResult
    """
    results = []

    for test in tests:
        logger.info(f"🔌 Running circuit test: {test.name}")
        result = run_timed_circuit_test(test)
        results.append(result)
        logger.info(result.summary)

    return results
