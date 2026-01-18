from __future__ import annotations

import pytest
from typing import Any

import torch

# =============================================================================
# E8 QUANTIZATION BENCHMARKS
# =============================================================================


class TestE8Benchmarks:
    """Benchmark tests for E8 lattice quantization."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Setup E8 quantizer."""
        from kagami_math.e8 import nearest_e8

        self.nearest_e8 = nearest_e8

    def test_bench_e8_single_vector(self, benchmark) -> None:
        """Benchmark E8 quantization for single vector.

        Baseline: ~0.5ms (p95)
        Regression threshold: +10% (0.55ms)
        """
        x = torch.randn(8)
        result = benchmark(self.nearest_e8, x)
        assert result.shape == (8,)

    def test_bench_e8_batch_32(self, benchmark) -> None:
        """Benchmark E8 quantization for batch of 32 vectors.

        Baseline: ~3ms (p95)
        Regression threshold: +10% (3.3ms)
        """
        x = torch.randn(32, 8)
        result = benchmark(self.nearest_e8, x)
        assert result.shape == (32, 8)

    def test_bench_e8_batch_256(self, benchmark) -> None:
        """Benchmark E8 quantization for batch of 256 vectors.

        Baseline: ~15ms (p95)
        Regression threshold: +10% (16.5ms)
        """
        x = torch.randn(256, 8)
        result = benchmark(self.nearest_e8, x)
        assert result.shape == (256, 8)


# =============================================================================
# FANO ROUTER BENCHMARKS
# =============================================================================


class TestFanoRouterBenchmarks:
    """Benchmark tests for Fano Action Router."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Setup Fano router."""
        from kagami.core.unified_agents.fano_action_router import create_fano_router

        self.router = create_fano_router()

    def test_bench_fano_simple_routing(self, benchmark) -> None:
        """Benchmark simple routing operation.

        Baseline: ~0.5ms (p95)
        Regression threshold: +10% (0.55ms)
        """

        def route() -> Self:
            return self.router.route("ping", {"target": "health"})

        result = benchmark(route)
        assert result is not None

    def test_bench_fano_complex_routing(self, benchmark) -> Any:
        """Benchmark complex routing with all colonies.

        Baseline: ~5ms (p95)
        Regression threshold: +10% (5.5ms)
        """

        def route() -> Self:
            return self.router.route(
                "analyze_architecture",
                {"domain": "security", "modules": ["a", "b", "c"]},
                complexity=0.85,
            )

        result = benchmark(route)
        assert result is not None

    def test_bench_fano_cache_hit(self, benchmark) -> Any:
        """Benchmark routing with cache hit.

        Baseline: ~0.2ms (p95)
        Regression threshold: +10% (0.22ms)
        """
        # Warm up cache
        for _ in range(10):
            self.router.route("cached_action", {})

        def route_cached() -> Self:
            return self.router.route("cached_action", {})

        result = benchmark(route_cached)
        assert result is not None


# =============================================================================
# WORLD MODEL BENCHMARKS
# =============================================================================


class TestWorldModelBenchmarks:
    """Benchmark tests for KagamiWorldModel."""

    @pytest.fixture(autouse=True)
    def setup(self) -> Any:
        """Setup world model."""
        from kagami.core.world_model import create_model

        self.model = create_model(preset="minimal")
        self.model.eval()
        self.bulk_dim = self.model.config.bulk_dim

    def test_bench_world_model_encode(self, benchmark) -> None:
        """Benchmark world model encode operation.

        Baseline: ~50ms (p95)
        Regression threshold: +10% (55ms)
        """
        x = torch.randn(4, 8, self.bulk_dim)

        def encode() -> Self:
            with torch.no_grad():
                return self.model.encode(x)

        result = benchmark(encode)
        assert result is not None

    def test_bench_world_model_forward(self, benchmark) -> Any:
        """Benchmark world model forward pass.

        Baseline: ~100ms (p95)
        Regression threshold: +10% (110ms)
        """
        x = torch.randn(4, 8, self.bulk_dim)

        def forward() -> None:
            with torch.no_grad():
                return self.model(x)

        result = benchmark(forward)
        assert result is not None


# =============================================================================
# SAFETY CACHE BENCHMARKS
# =============================================================================


class TestSafetyCacheBenchmarks:
    """Benchmark tests for safety classification cache."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Setup safety cache."""
        from kagami.core.safety.safety_cache import SafetyClassificationCache

        self.cache = SafetyClassificationCache(max_size=1000)
        # Populate cache
        for i in range(100):
            self.cache.put(f"test query {i}", h_value=1.0, is_safe=True)

    def test_bench_cache_lookup(self, benchmark) -> None:
        """Benchmark cache lookup operation.

        Baseline: ~0.1ms (p95)
        Regression threshold: +10% (0.11ms)
        """

        def lookup() -> Self:
            return self.cache.get("test query 50")

        result = benchmark(lookup)
        assert result is not None

    def test_bench_cache_insert(self, benchmark) -> Any:
        """Benchmark cache insert operation.

        Baseline: ~0.2ms (p95)
        Regression threshold: +10% (0.22ms)
        """
        import random

        def insert() -> None:
            key = f"query_{random.randint(0, 1000000)}"
            self.cache.put(key, h_value=1.0, is_safe=True)

        benchmark(insert)


# =============================================================================
# ROUTING + E8 COMPOSITE BENCHMARKS
# =============================================================================


class TestCompositeBenchmarks:
    """Benchmark tests for composite operations."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Setup dependencies."""
        from kagami_math.e8 import nearest_e8
        from kagami.core.unified_agents.fano_action_router import create_fano_router

        self.nearest_e8 = nearest_e8
        self.router = create_fano_router()

    def test_bench_route_and_quantize(self, benchmark) -> None:
        """Benchmark routing decision followed by E8 quantization.

        This simulates a common pattern in the system.

        Baseline: ~1ms (p95)
        Regression threshold: +10% (1.1ms)
        """

        def composite_op() -> Any:
            # Route to determine action
            route_result = self.router.route("process_state", {"dim": 8})
            # Quantize result state
            state = torch.randn(8)
            quantized = self.nearest_e8(state)
            return route_result, quantized

        result = benchmark(composite_op)
        assert result is not None


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================


def pytest_benchmark_update_json(config, benchmarks, output_json) -> Any:
    """Hook to add regression checking after benchmarks run.

    This compares current run against baseline and fails if regression > 10%.
    """
    import json
    from pathlib import Path

    # Load baseline if it exists
    baseline_file = Path(__file__).parent / ".benchmarks" / "baseline.json"
    if not baseline_file.exists():
        print(f"\n⚠️  No baseline found at {baseline_file}")
        print("Run: pytest --benchmark-save=baseline to create baseline")
        return

    with open(baseline_file) as f:
        baseline_data = json.load(f)

    baseline_benchmarks = {b["fullname"]: b for b in baseline_data["benchmarks"]}

    # Check for regressions
    regressions = []
    for bench in benchmarks:
        fullname = bench["fullname"]
        if fullname not in baseline_benchmarks:
            continue

        baseline = baseline_benchmarks[fullname]
        current_mean = bench["stats"]["mean"]
        baseline_mean = baseline["stats"]["mean"]

        # Calculate regression percentage
        regression_pct = ((current_mean - baseline_mean) / baseline_mean) * 100

        if regression_pct > 10.0:
            regressions.append(
                {
                    "name": fullname,
                    "baseline_mean": baseline_mean,
                    "current_mean": current_mean,
                    "regression_pct": regression_pct,
                }
            )

    # Report regressions
    if regressions:
        print("\n" + "=" * 80)
        print("❌ PERFORMANCE REGRESSIONS DETECTED")
        print("=" * 80)
        for r in regressions:
            print(f"\n{r['name']}:")
            print(f"  Baseline: {r['baseline_mean'] * 1000:.3f}ms")
            print(f"  Current:  {r['current_mean'] * 1000:.3f}ms")
            print(f"  Regression: {r['regression_pct']:.1f}% (threshold: 10%)")
        print("\n" + "=" * 80)

        # Fail the test run
        raise pytest.UsageError(
            f"Performance regression detected in {len(regressions)} benchmark(s). "
            f"See details above."
        )
    else:
        print("\n✅ No performance regressions detected (threshold: 10%)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])
