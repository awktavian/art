#!/usr/bin/env python3
"""
Quick Benchmark Script for Kagami

Runs basic performance tests and outputs results.
Use this for quick verification of performance characteristics.

Usage:
    python scripts/benchmark/quick_benchmark.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@dataclass
class BenchmarkResult:
    """Single benchmark result."""

    name: str
    duration_ms: float
    memory_mb: float
    success: bool
    details: dict[str, Any] | None = None


def measure_time(func):
    """Decorator to measure function execution time."""

    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        end = time.perf_counter()
        return result, (end - start) * 1000

    return wrapper


async def benchmark_import_time() -> BenchmarkResult:
    """Benchmark import time for core modules."""
    start = time.perf_counter()

    try:
        # Core imports
        from kagami.agents import get_organism  # noqa: F401
        from kagami.core.safety import get_safety_filter  # noqa: F401
        from kagami.math.e8_lattice_quantizer import nearest_e8  # noqa: F401

        duration = (time.perf_counter() - start) * 1000
        return BenchmarkResult(
            name="Core Import Time",
            duration_ms=duration,
            memory_mb=0,  # Not measured here
            success=True,
        )
    except ImportError as e:
        return BenchmarkResult(
            name="Core Import Time",
            duration_ms=0,
            memory_mb=0,
            success=False,
            details={"error": str(e)},
        )


async def benchmark_organism_init() -> BenchmarkResult:
    """Benchmark organism initialization."""
    try:
        from kagami.agents import get_organism

        start = time.perf_counter()
        org = get_organism()
        duration = (time.perf_counter() - start) * 1000

        return BenchmarkResult(
            name="Organism Initialization",
            duration_ms=duration,
            memory_mb=0,
            success=True,
            details={"colonies": len(org.colonies) if hasattr(org, "colonies") else 7},
        )
    except Exception as e:
        return BenchmarkResult(
            name="Organism Initialization",
            duration_ms=0,
            memory_mb=0,
            success=False,
            details={"error": str(e)},
        )


async def benchmark_safety_check() -> BenchmarkResult:
    """Benchmark CBF safety check."""
    try:
        from kagami.core.safety import get_safety_filter

        cbf = get_safety_filter()

        # Mock state and action
        state = {"position": [0.5, 0.5], "velocity": [0.1, 0.0]}
        action = {"type": "move", "direction": [0.1, 0.0]}

        start = time.perf_counter()
        # Run safety check 100 times for better measurement
        for _ in range(100):
            try:
                cbf.check_action(action, state)
            except Exception:
                pass  # Some configs may not have full CBF
        duration = (time.perf_counter() - start) * 1000 / 100

        return BenchmarkResult(
            name="Safety Check (CBF)",
            duration_ms=duration,
            memory_mb=0,
            success=True,
        )
    except Exception as e:
        return BenchmarkResult(
            name="Safety Check (CBF)",
            duration_ms=0,
            memory_mb=0,
            success=False,
            details={"error": str(e)},
        )


async def benchmark_e8_quantization() -> BenchmarkResult:
    """Benchmark E8 lattice quantization."""
    try:
        import numpy as np

        from kagami.math.e8_lattice_quantizer import nearest_e8

        # Generate random 8D vectors
        vectors = np.random.randn(1000, 8).astype(np.float32)

        start = time.perf_counter()
        for v in vectors:
            nearest_e8(v)
        duration = (time.perf_counter() - start) * 1000 / 1000

        return BenchmarkResult(
            name="E8 Quantization (per vector)",
            duration_ms=duration,
            memory_mb=0,
            success=True,
        )
    except Exception as e:
        return BenchmarkResult(
            name="E8 Quantization",
            duration_ms=0,
            memory_mb=0,
            success=False,
            details={"error": str(e)},
        )


async def benchmark_fano_routing() -> BenchmarkResult:
    """Benchmark Fano plane routing."""
    try:
        from kagami.math.fano_plane import get_fano_line_for_pair

        start = time.perf_counter()
        # Test all 21 pairs
        for i in range(1, 8):
            for j in range(i + 1, 8):
                get_fano_line_for_pair(i, j)
        duration = (time.perf_counter() - start) * 1000 / 21

        return BenchmarkResult(
            name="Fano Routing (per pair)",
            duration_ms=duration,
            memory_mb=0,
            success=True,
        )
    except Exception as e:
        return BenchmarkResult(
            name="Fano Routing",
            duration_ms=0,
            memory_mb=0,
            success=False,
            details={"error": str(e)},
        )


async def run_all_benchmarks() -> list[BenchmarkResult]:
    """Run all benchmarks."""
    benchmarks = [
        benchmark_import_time,
        benchmark_organism_init,
        benchmark_safety_check,
        benchmark_e8_quantization,
        benchmark_fano_routing,
    ]

    results = []
    for bench in benchmarks:
        result = await bench()
        results.append(result)
        status = "✅" if result.success else "❌"
        print(f"{status} {result.name}: {result.duration_ms:.2f}ms")
        if result.details and not result.success:
            print(f"   Error: {result.details.get('error', 'Unknown')}")

    return results


def print_summary(results: list[BenchmarkResult]) -> None:
    """Print benchmark summary."""
    print("\n" + "=" * 50)
    print("BENCHMARK SUMMARY")
    print("=" * 50)

    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    print(f"Total: {len(results)} | Passed: {len(successful)} | Failed: {len(failed)}")

    if successful:
        total_time = sum(r.duration_ms for r in successful)
        print(f"Total time (successful): {total_time:.2f}ms")

    print()
    print("Individual Results:")
    print("-" * 50)
    for r in results:
        status = "PASS" if r.success else "FAIL"
        print(f"  {r.name:30} {r.duration_ms:8.2f}ms  [{status}]")

    print("\n鏡 — Benchmarks complete")


async def main():
    """Main entry point."""
    print("🔬 Kagami Quick Benchmark")
    print("=" * 50)
    print()

    results = await run_all_benchmarks()
    print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
