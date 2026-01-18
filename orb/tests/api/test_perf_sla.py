"""Performance SLA Tests

Tests performance SLAs for REST endpoints.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration
import os
import statistics
import time
from httpx import ASGITransport, AsyncClient
from kagami_api import create_app


def _percentile(values: list[float], p: float) -> float:
    """Calculate percentile from a list of values."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = round((p / 100.0) * (len(s) - 1))
    return s[min(max(k, 0), len(s) - 1)]


@pytest.mark.asyncio
@pytest.mark.performance
async def test_rest_perf_sla_health(monkeypatch: pytest.MonkeyPatch) -> None:
    """Perf regression guard for a lightweight REST endpoint."""
    monkeypatch.setenv("LIGHTWEIGHT_STARTUP", "1")

    # Disable global rate limiting for perf test
    async def mock_allowed(*args: Any) -> bool:
        return True, 999, 0

    from kagami_api import rate_limiter

    monkeypatch.setattr(rate_limiter.api_rate_limiter, "is_allowed_async", mock_allowed)
    app = create_app()
    transport = ASGITransport(app=app)
    p95_target = float(os.getenv("KAGAMI_SLA_P95_MS", "50"))
    p99_target = float(os.getenv("KAGAMI_SLA_P99_MS", "100"))
    loosen = float(os.getenv("KAGAMI_SLA_MARGIN", "1.0"))
    latencies_ms: list[float] = []
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Use correct vitals endpoint
        for _ in range(5):
            await client.get("/api/vitals/probes/live", timeout=2.0)
        for _ in range(120):
            t0 = time.perf_counter()
            r = await client.get("/api/vitals/probes/live", timeout=2.0)
            assert r.status_code == 200
            latencies_ms.append((time.perf_counter() - t0) * 1000.0)
    p95 = _percentile(latencies_ms, 95)
    p99 = _percentile(latencies_ms, 99)
    mean_lat = statistics.mean(latencies_ms)
    print(f"REST /api/vitals/probes/live: mean={mean_lat:.1f}ms p95={p95:.1f}ms p99={p99:.1f}ms")
    assert p95 <= p95_target * loosen, f"p95 {p95:.1f}ms > {p95_target * loosen}ms"
    assert p99 <= p99_target * loosen, f"p99 {p99:.1f}ms > {p99_target * loosen}ms"


@pytest.mark.asyncio
@pytest.mark.performance
async def test_rest_perf_sla_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Perf regression guard for metrics endpoint."""
    monkeypatch.setenv("LIGHTWEIGHT_STARTUP", "1")
    app = create_app()
    transport = ASGITransport(app=app)
    latencies_ms: list[float] = []
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(5):
            await client.get("/metrics", timeout=2.0)
        for _ in range(50):
            t0 = time.perf_counter()
            r = await client.get("/metrics", timeout=2.0)
            assert r.status_code == 200
            latencies_ms.append((time.perf_counter() - t0) * 1000.0)
    p95 = _percentile(latencies_ms, 95)
    mean_lat = statistics.mean(latencies_ms)
    print(f"REST /metrics: mean={mean_lat:.1f}ms p95={p95:.1f}ms")
    # Metrics endpoint is heavier, allow more time
    assert p95 <= 200, f"p95 {p95:.1f}ms > 200ms"
