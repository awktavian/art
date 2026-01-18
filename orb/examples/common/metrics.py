"""Metrics collection utilities for Kagami examples.

Provides timing, memory tracking, and throughput measurement.
"""

from __future__ import annotations

import gc
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Generator

try:
    import tracemalloc

    TRACEMALLOC_AVAILABLE = True
except ImportError:
    TRACEMALLOC_AVAILABLE = False


@dataclass
class TimingResult:
    """Result of a timing measurement."""

    elapsed_seconds: float
    start_time: float
    end_time: float

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return self.elapsed_seconds * 1000

    def __str__(self) -> str:
        if self.elapsed_seconds < 1:
            return f"{self.elapsed_ms:.1f}ms"
        return f"{self.elapsed_seconds:.2f}s"


class Timer:
    """Context manager for timing code execution.

    Usage:
        with Timer() as t:
            # code to time
        print(f"Elapsed: {t.elapsed}")

        # Or use as decorator
        @Timer.measure
        def my_function():
            pass
    """

    def __init__(self, name: str | None = None):
        self.name = name
        self._start: float | None = None
        self._end: float | None = None

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self._end = time.perf_counter()

    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        if self._start is None:
            return 0.0
        end = self._end if self._end is not None else time.perf_counter()
        return end - self._start

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return self.elapsed * 1000

    @property
    def result(self) -> TimingResult:
        """Get full timing result."""
        return TimingResult(
            elapsed_seconds=self.elapsed,
            start_time=self._start or 0,
            end_time=self._end or time.perf_counter(),
        )

    @staticmethod
    @contextmanager
    def measure(name: str | None = None) -> Generator[Timer, None, None]:
        """Context manager for timing with optional name."""
        timer = Timer(name)
        timer._start = time.perf_counter()
        try:
            yield timer
        finally:
            timer._end = time.perf_counter()


@dataclass
class MemoryResult:
    """Result of memory tracking."""

    peak_mb: float
    current_mb: float
    allocated_mb: float

    def __str__(self) -> str:
        return f"peak={self.peak_mb:.1f}MB, current={self.current_mb:.1f}MB"


class MemoryTracker:
    """Track memory usage during code execution.

    Usage:
        with MemoryTracker() as mem:
            # code that uses memory
        print(f"Peak: {mem.peak_mb:.1f}MB")
    """

    def __init__(self):
        self._started = False
        self._peak_mb = 0.0
        self._current_mb = 0.0
        self._allocated_mb = 0.0

    def __enter__(self) -> MemoryTracker:
        gc.collect()
        if TRACEMALLOC_AVAILABLE:
            tracemalloc.start()
            self._started = True
        return self

    def __exit__(self, *args: Any) -> None:
        if TRACEMALLOC_AVAILABLE and self._started:
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            self._current_mb = current / (1024 * 1024)
            self._peak_mb = peak / (1024 * 1024)
            self._allocated_mb = self._peak_mb

    @property
    def peak_mb(self) -> float:
        """Get peak memory usage in MB."""
        return self._peak_mb

    @property
    def current_mb(self) -> float:
        """Get current memory usage in MB."""
        return self._current_mb

    @property
    def result(self) -> MemoryResult:
        """Get full memory result."""
        return MemoryResult(
            peak_mb=self._peak_mb,
            current_mb=self._current_mb,
            allocated_mb=self._allocated_mb,
        )


@dataclass
class MetricsCollector:
    """Collect and aggregate metrics across an example.

    Usage:
        metrics = MetricsCollector()
        metrics.record("operations", 100)
        metrics.record_timing("phase_1", 1.5)
        print(metrics.summary())
    """

    name: str = "metrics"
    values: dict[str, list[float]] = field(default_factory=dict)
    timings: dict[str, float] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    _start_time: float = field(default_factory=time.perf_counter)

    def record(self, name: str, value: float) -> None:
        """Record a metric value."""
        if name not in self.values:
            self.values[name] = []
        self.values[name].append(value)

    def record_timing(self, name: str, seconds: float) -> None:
        """Record a timing measurement."""
        self.timings[name] = seconds

    def increment(self, name: str, amount: int = 1) -> None:
        """Increment a counter."""
        self.counters[name] = self.counters.get(name, 0) + amount

    @property
    def total_time(self) -> float:
        """Get total elapsed time since creation."""
        return time.perf_counter() - self._start_time

    def average(self, name: str) -> float | None:
        """Get average of recorded values."""
        if name not in self.values or not self.values[name]:
            return None
        return sum(self.values[name]) / len(self.values[name])

    def summary(self) -> dict[str, Any]:
        """Get summary of all metrics."""
        result: dict[str, Any] = {
            "total_time_s": round(self.total_time, 3),
        }

        # Add averages
        for name, values in self.values.items():
            if values:
                result[f"{name}_avg"] = round(sum(values) / len(values), 3)
                result[f"{name}_count"] = len(values)

        # Add timings
        for name, timing in self.timings.items():
            result[f"{name}_s"] = round(timing, 3)

        # Add counters
        for name, count in self.counters.items():
            result[name] = count

        return result

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "name": self.name,
            "total_time_s": self.total_time,
            "values": self.values,
            "timings": self.timings,
            "counters": self.counters,
        }


def measure_throughput(
    operation_count: int,
    elapsed_seconds: float,
    unit: str = "ops",
) -> dict[str, float]:
    """Calculate throughput metrics.

    Args:
        operation_count: Number of operations completed
        elapsed_seconds: Total time in seconds
        unit: Unit name for operations

    Returns:
        Dictionary with throughput metrics
    """
    if elapsed_seconds <= 0:
        return {
            f"{unit}_per_second": 0,
            f"seconds_per_{unit}": 0,
            "total_operations": operation_count,
            "total_time_s": elapsed_seconds,
        }

    return {
        f"{unit}_per_second": round(operation_count / elapsed_seconds, 2),
        f"seconds_per_{unit}": round(elapsed_seconds / operation_count, 4),
        "total_operations": operation_count,
        "total_time_s": round(elapsed_seconds, 3),
    }
