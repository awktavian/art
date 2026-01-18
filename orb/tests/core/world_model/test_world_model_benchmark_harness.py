"""Smoke test for the World Model benchmark harness.

This is NOT a performance test.
It exists to ensure the benchmark can execute end-to-end without crashing
when the KagamiWorldModel service is available.

Why here (tests/core/world_model/) instead of tests/benchmarks/?
- make test ignores tests/benchmarks/ for speed.
- This harness must stay green to prevent benchmark API drift.
"""

from __future__ import annotations

import pytest
import asyncio


def test_world_model_benchmark_harness_smoke_cpu() -> None:
    # Skip if kagami_benchmarks.active_inference is not installed/available
    pytest.importorskip("kagami_benchmarks.active_inference")
    from kagami_benchmarks.active_inference.world_model_benchmark import WorldModelBenchmark

    bench = WorldModelBenchmark(device="cpu", batch_size=2, seq_len=4)

    # If the service can't be constructed in this environment, skip rather than fail.
    # (The harness supports a mock path, but this test is for the real wiring.)
    if bench._get_world_model() is None:
        pytest.skip("World model service unavailable in test environment")

    result = asyncio.run(bench.run(num_samples=1))

    assert result.error is None
    assert 0.0 <= result.score <= 1.0
