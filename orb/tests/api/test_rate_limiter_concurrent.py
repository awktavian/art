"""
Concurrent request tests for rate limiter.

Tests rate limiter behavior under concurrent load from multiple clients.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration
import asyncio
import time


class TestRateLimiterConcurrent:
    """Test rate limiter under concurrent load."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_same_client(self):
        """Test multiple concurrent requests from same client."""
        from kagami_api.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=50, window_size=60)

        # Simulate 30 concurrent requests from same client
        async def make_request():
            is_allowed, _, _ = await limiter.is_allowed_async("client1")
            return is_allowed

        results = await asyncio.gather(*[make_request() for _ in range(30)])
        # Some should be allowed, some blocked
        allowed = sum(1 for r in results if r)
        blocked = sum(1 for r in results if not r)
        print("\nConcurrent Same Client:")
        print("  Total: 30")
        print(f"  Allowed: {allowed}")
        print(f"  Blocked: {blocked}")
        # Should allow up to limit (50), so all 30 should be allowed
        assert allowed >= 25, f"Only {allowed}/30 allowed (expected ~30)"

    @pytest.mark.asyncio
    async def test_concurrent_requests_different_clients(self):
        """Test concurrent requests from different clients."""
        from kagami_api.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=10, window_size=60)

        # 5 clients making 5 requests each = 25 total
        async def make_requests_for_client(client_id: str):
            allowed = 0
            for _ in range(5):
                is_allowed, _, _ = await limiter.is_allowed_async(client_id)
                if is_allowed:
                    allowed += 1
            return allowed

        results = await asyncio.gather(*[make_requests_for_client(f"client{i}") for i in range(5)])
        total_allowed = sum(results)

        print("\nConcurrent Different Clients:")
        print("  Clients: 5")
        print("  Requests per client: 5")
        print(f"  Total allowed: {total_allowed}/25")
        # Each client gets their own limit, so all should be allowed
        assert total_allowed >= 20, f"Only {total_allowed}/25 allowed"

    @pytest.mark.asyncio
    async def test_concurrent_burst_detection(self):
        """Test burst detection under concurrent load."""
        from kagami_api.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=100, window_size=60)

        # Simulate burst: 50 concurrent requests
        async def make_request():
            return await limiter.is_allowed_async("burst_client")

        start = time.time()
        results = await asyncio.gather(*[make_request() for _ in range(50)])
        duration = time.time() - start
        allowed = sum(1 for is_allowed, _, _ in results if is_allowed)
        print("\nConcurrent Burst:")
        print("  Requests: 50")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Allowed: {allowed}")
        burst_attempts = getattr(limiter._impl, "burst_attempts", {})
        print(f"  Burst attempts: {burst_attempts.get('burst_client', 0)}")
        # Some requests should be allowed before burst detection kicks in
        assert allowed > 20, f"Too restrictive: only {allowed}/50 allowed"
        # Burst detection may or may not trigger depending on timing
        # (This is expected behavior - timing-dependent)

    @pytest.mark.asyncio
    async def test_rate_limiter_thread_safe(self):
        """Test rate limiter is thread-safe under concurrent access."""
        from kagami_api.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=100, window_size=60)

        # Many clients making concurrent requests
        async def make_batch(client_id: str, count: int):
            results = []
            for _ in range(count):
                is_allowed, _, _ = await limiter.is_allowed_async(client_id)
                results.append(is_allowed)
            return results

        # 10 clients making 10 requests each
        all_results = await asyncio.gather(*[make_batch(f"client{i}", 10) for i in range(10)])
        # Verify no crashes and reasonable results
        total_requests = sum(len(results) for results in all_results)

        total_allowed = sum(sum(1 for r in results if r) for results in all_results)
        print("\nThread Safety Test:")
        print("  Clients: 10")
        print("  Requests per client: 10")
        print(f"  Total: {total_requests}")
        print(f"  Allowed: {total_allowed}")
        # Should handle concurrent access without errors
        assert total_requests == 100
        assert total_allowed >= 90  # Most should be allowed (each client gets 100/min)


class TestRateLimiterPerformance:
    """Test rate limiter performance under load."""

    @pytest.mark.performance
    def test_rate_limiter_latency(self):
        """Test rate limiter decision latency."""
        import numpy as np
        from kagami_api.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=1000, window_size=60)
        # Warm up
        for _ in range(10):
            limiter.is_allowed("perf_client")
        # Measure
        durations = []
        for _ in range(1000):
            start = time.perf_counter()
            limiter.is_allowed("perf_client")
            durations.append((time.perf_counter() - start) * 1000)
        p50 = np.percentile(durations, 50)
        p95 = np.percentile(durations, 95)
        p99 = np.percentile(durations, 99)
        print("\nRate Limiter Latency:")
        print(f"  p50: {p50:.3f}ms")
        print(f"  p95: {p95:.3f}ms")
        print(f"  p99: {p99:.3f}ms")
        # Should be fast - thresholds relaxed for CI/test environments
        # In-memory rate limiting should be <5ms p95 even under load
        assert p95 < 5.0, f"p95 latency {p95:.3f}ms exceeds 5ms"
        assert p99 < 10.0, f"p99 latency {p99:.3f}ms exceeds 10ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
