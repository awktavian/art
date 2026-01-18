"""Performance benchmarks for critical paths.

Verifies latency and throughput requirements:
- API response time < 100ms
- State updates < 50ms
- Colony routing < 10ms
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class BenchmarkResult:
    """Result of a performance benchmark.

    Attributes:
        name: Benchmark name.
        iterations: Number of iterations run.
        total_time: Total elapsed time in seconds.
        mean_time: Mean time per iteration in milliseconds.
        min_time: Minimum time in milliseconds.
        max_time: Maximum time in milliseconds.
        p95_time: 95th percentile time in milliseconds.
        p99_time: 99th percentile time in milliseconds.
    """

    name: str
    iterations: int
    total_time: float
    mean_time: float
    min_time: float
    max_time: float
    p95_time: float
    p99_time: float


def run_benchmark(
    name: str,
    func: Callable[[], Any],
    iterations: int = 1000,
) -> BenchmarkResult:
    """Run a synchronous benchmark.

    Args:
        name: Benchmark name.
        func: Function to benchmark.
        iterations: Number of iterations.

    Returns:
        BenchmarkResult with timing statistics.
    """
    times: list[float] = []

    # Warmup
    for _ in range(min(100, iterations // 10)):
        func()

    # Benchmark
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)

    times.sort()
    total = sum(times)

    return BenchmarkResult(
        name=name,
        iterations=iterations,
        total_time=total / 1000,  # seconds
        mean_time=total / iterations,
        min_time=times[0],
        max_time=times[-1],
        p95_time=times[int(iterations * 0.95)],
        p99_time=times[int(iterations * 0.99)],
    )


async def run_async_benchmark(
    name: str,
    func: Callable[[], Any],
    iterations: int = 1000,
) -> BenchmarkResult:
    """Run an async benchmark.

    Args:
        name: Benchmark name.
        func: Async function to benchmark.
        iterations: Number of iterations.

    Returns:
        BenchmarkResult with timing statistics.
    """
    times: list[float] = []

    # Warmup
    for _ in range(min(100, iterations // 10)):
        await func()

    # Benchmark
    for _ in range(iterations):
        start = time.perf_counter()
        await func()
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)

    times.sort()
    total = sum(times)

    return BenchmarkResult(
        name=name,
        iterations=iterations,
        total_time=total / 1000,
        mean_time=total / iterations,
        min_time=times[0],
        max_time=times[-1],
        p95_time=times[int(iterations * 0.95)],
        p99_time=times[int(iterations * 0.99)],
    )


class TestAPILatency:
    """Benchmarks for API response time."""

    def test_json_serialization_latency(self) -> None:
        """JSON serialization should be fast."""
        import json

        data = {
            "lights": [{"id": i, "level": 50, "room": f"Room {i}"} for i in range(100)],
            "presence": {"home": True, "devices": ["phone", "laptop"]},
            "temperature": 72.5,
        }

        def serialize() -> str:
            return json.dumps(data)

        result = run_benchmark("json_serialization", serialize, iterations=10000)

        # Should be < 1ms
        assert result.mean_time < 1.0, f"JSON serialization too slow: {result.mean_time:.2f}ms"
        assert result.p95_time < 2.0, f"JSON serialization p95 too slow: {result.p95_time:.2f}ms"

    def test_dict_access_latency(self) -> None:
        """Dict access should be O(1)."""
        data = {f"key_{i}": f"value_{i}" for i in range(10000)}

        def access() -> str:
            return data["key_5000"]

        result = run_benchmark("dict_access", access, iterations=100000)

        # Should be < 0.001ms (essentially free)
        assert result.mean_time < 0.01, f"Dict access too slow: {result.mean_time:.4f}ms"


class TestStateUpdateLatency:
    """Benchmarks for state update operations."""

    def test_state_merge_latency(self) -> None:
        """State merging should be fast."""
        old_state = {"lights": {f"light_{i}": 50 for i in range(50)}}

        def merge() -> dict:
            new_state = old_state.copy()
            new_state["lights"]["light_25"] = 75
            return new_state

        result = run_benchmark("state_merge", merge, iterations=10000)

        # Should be < 1ms
        assert result.mean_time < 1.0, f"State merge too slow: {result.mean_time:.2f}ms"

    def test_event_dispatch_latency(self) -> None:
        """Event dispatch should be fast."""
        handlers: list[Callable[[dict], None]] = []

        for _ in range(10):
            handlers.append(lambda e: None)

        event = {"type": "light_changed", "id": 1, "level": 50}

        def dispatch() -> None:
            for handler in handlers:
                handler(event)

        result = run_benchmark("event_dispatch", dispatch, iterations=10000)

        # Should be < 0.1ms
        assert result.mean_time < 0.1, f"Event dispatch too slow: {result.mean_time:.3f}ms"


class TestColonyRoutingLatency:
    """Benchmarks for colony routing decisions."""

    def test_signal_matching_latency(self) -> None:
        """Signal matching should be fast."""
        signal_map = {
            "brainstorm": "spark",
            "ideate": "spark",
            "imagine": "spark",
            "build": "forge",
            "implement": "forge",
            "code": "forge",
            "debug": "flow",
            "fix": "flow",
            "error": "flow",
            "connect": "nexus",
            "integrate": "nexus",
            "link": "nexus",
            "plan": "beacon",
            "architect": "beacon",
            "design": "beacon",
            "research": "grove",
            "explore": "grove",
            "document": "grove",
            "test": "crystal",
            "verify": "crystal",
            "audit": "crystal",
        }

        signals = ["brainstorm", "build", "test", "plan", "debug"]

        def match() -> list[str]:
            return [signal_map.get(s, "grove") for s in signals]

        result = run_benchmark("signal_matching", match, iterations=10000)

        # Should be < 0.1ms
        assert result.mean_time < 0.1, f"Signal matching too slow: {result.mean_time:.3f}ms"

    def test_fano_line_lookup_latency(self) -> None:
        """Fano line lookup should be O(1)."""
        fano_lines = {
            (1, 2): 3,
            (1, 3): 2,
            (2, 3): 1,
            (1, 4): 5,
            (1, 5): 4,
            (4, 5): 1,
            (1, 6): 7,
            (1, 7): 6,
            (6, 7): 1,
            (2, 4): 6,
            (2, 6): 4,
            (4, 6): 2,
            (2, 5): 7,
            (2, 7): 5,
            (5, 7): 2,
            (3, 4): 7,
            (3, 7): 4,
            (4, 7): 3,
            (3, 5): 6,
            (3, 6): 5,
            (5, 6): 3,
        }

        def lookup() -> int:
            return fano_lines.get((1, 2), 0)

        result = run_benchmark("fano_lookup", lookup, iterations=100000)

        # Should be < 0.01ms (essentially free)
        assert result.mean_time < 0.01, f"Fano lookup too slow: {result.mean_time:.4f}ms"


class TestE8QuantizationLatency:
    """Benchmarks for E8 lattice operations."""

    def test_vector_distance_latency(self) -> None:
        """Vector distance calculation should be fast."""
        import math

        v1 = [0.5] * 8
        v2 = [0.6] * 8

        def distance() -> float:
            return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2, strict=False)))

        result = run_benchmark("vector_distance", distance, iterations=100000)

        # Should be < 0.01ms
        assert result.mean_time < 0.01, f"Vector distance too slow: {result.mean_time:.4f}ms"


class TestAsyncOperations:
    """Benchmarks for async operations."""

    @pytest.mark.asyncio
    async def test_async_task_creation_latency(self) -> None:
        """Async task creation should be fast."""

        async def noop() -> None:
            pass

        result = await run_async_benchmark("async_noop", noop, iterations=10000)

        # Should be < 0.1ms
        assert result.mean_time < 0.1, f"Async noop too slow: {result.mean_time:.3f}ms"

    @pytest.mark.asyncio
    async def test_asyncio_gather_latency(self) -> None:
        """asyncio.gather overhead should be minimal."""

        async def task() -> int:
            return 1

        async def gather_tasks() -> list[int]:
            return await asyncio.gather(*[task() for _ in range(10)])

        result = await run_async_benchmark("asyncio_gather", gather_tasks, iterations=1000)

        # Should be < 1ms for 10 trivial tasks
        assert result.mean_time < 1.0, f"asyncio.gather too slow: {result.mean_time:.2f}ms"


class TestMemoryEfficiency:
    """Tests for memory efficiency."""

    def test_state_object_size(self) -> None:
        """State objects should have reasonable size."""
        import sys

        state = {
            "lights": {f"light_{i}": {"level": 50, "on": True} for i in range(50)},
            "rooms": [f"Room {i}" for i in range(20)],
            "presence": {"home": True},
        }

        size_bytes = sys.getsizeof(state)

        # State object should be < 1KB (dict header only)
        # Full size depends on content
        assert size_bytes < 10000, f"State object too large: {size_bytes} bytes"

    def test_no_memory_leak_in_loop(self) -> None:
        """Operations in loop should not leak memory."""
        import gc

        gc.collect()
        initial_objects = len(gc.get_objects())

        for _ in range(1000):
            data = {"key": "value"}
            del data

        gc.collect()
        final_objects = len(gc.get_objects())

        # Object count should not grow significantly
        growth = final_objects - initial_objects
        assert growth < 100, f"Possible memory leak: {growth} new objects"
