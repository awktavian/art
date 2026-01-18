"""Performance benchmarks for CBF decorators.

Verifies that decorator overhead is <0.1ms as required.

CREATED: December 14, 2025
AUTHOR: Forge (e₂)
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import time

from kagami.core.safety.cbf_decorators import enforce_cbf


class TestCBFDecoratorPerformance:
    """Performance benchmarks for CBF decorators."""

    def test_simple_barrier_overhead(self: Any) -> None:
        """Test that simple barrier overhead is <0.1ms."""

        @enforce_cbf(cbf_func=lambda: 1.0)
        def fast_func():
            return 42

        # Warm up
        for _ in range(100):
            fast_func()

        # Measure
        iterations = 10000
        t0 = time.perf_counter()
        for _ in range(iterations):
            fast_func()
        total_ms = (time.perf_counter() - t0) * 1000

        avg_overhead = total_ms / iterations
        print(f"\nAverage overhead: {avg_overhead:.4f}ms per call")
        assert avg_overhead < 0.1, f"Overhead {avg_overhead:.4f}ms exceeds 0.1ms"

    def test_state_extraction_overhead(self: Any) -> None:
        """Test overhead with state extraction."""

        def extract(x, y) -> dict[str, Any]:
            return {"x": x, "y": y}

        @enforce_cbf(cbf_func=lambda s: 10.0 - s["x"] - s["y"], extract_state=extract)
        def func_with_extraction(x, y):
            return x + y

        # Warm up
        for _ in range(100):
            func_with_extraction(1, 2)

        # Measure
        iterations = 10000
        t0 = time.perf_counter()
        for _ in range(iterations):
            func_with_extraction(1, 2)
        total_ms = (time.perf_counter() - t0) * 1000

        avg_overhead = total_ms / iterations
        print(f"\nAverage overhead with extraction: {avg_overhead:.4f}ms per call")
        assert avg_overhead < 0.15, f"Overhead {avg_overhead:.4f}ms exceeds 0.15ms"

    @pytest.mark.asyncio
    async def test_async_barrier_overhead(self: Any) -> None:
        """Test async barrier overhead."""

        @enforce_cbf(cbf_func=lambda: 1.0)
        async def async_func():
            return 42

        # Warm up
        for _ in range(100):
            await async_func()

        # Measure
        iterations = 1000
        t0 = time.perf_counter()
        for _ in range(iterations):
            await async_func()
        total_ms = (time.perf_counter() - t0) * 1000

        avg_overhead = total_ms / iterations
        print(f"\nAverage async overhead: {avg_overhead:.4f}ms per call")
        assert avg_overhead < 0.2, f"Async overhead {avg_overhead:.4f}ms exceeds 0.2ms"

    def test_baseline_comparison(self: Any) -> None:
        """Compare decorated vs undecorated function."""

        # Undecorated function
        def baseline():
            return 42

        # Decorated function
        @enforce_cbf(cbf_func=lambda: 1.0)
        def decorated():
            return 42

        # Warm up both
        for _ in range(100):
            baseline()
            decorated()

        # Measure baseline
        iterations = 10000
        t0 = time.perf_counter()
        for _ in range(iterations):
            baseline()
        baseline_ms = (time.perf_counter() - t0) * 1000

        # Measure decorated
        t0 = time.perf_counter()
        for _ in range(iterations):
            decorated()
        decorated_ms = (time.perf_counter() - t0) * 1000

        overhead_ms = (decorated_ms - baseline_ms) / iterations
        print(f"\nBaseline: {baseline_ms / iterations:.4f}ms per call")
        print(f"Decorated: {decorated_ms / iterations:.4f}ms per call")
        print(f"Overhead: {overhead_ms:.4f}ms per call")

        assert overhead_ms < 0.1, f"Overhead {overhead_ms:.4f}ms exceeds 0.1ms"
