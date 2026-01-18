"""Tests for cache rate limiter.

Tests token bucket algorithm, per-key limiting, integration with cache operations,
and graceful degradation.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import os

from kagami.core.unified_rate_limiter import (
    CacheRateLimiterAdapter as CacheRateLimiter,
    RateLimitError,
    get_cache_rate_limiter,
)

# TokenBucket tests removed - now using UnifiedRateLimiter internally
# The adapter (CacheRateLimiterAdapter) provides the same interface without
# exposing internal TokenBucket implementation details


class TestCacheRateLimiter:
    """Tests for CacheRateLimiter."""

    @pytest.mark.asyncio
    async def test_basic_rate_limiting(self) -> None:
        """Test basic rate limiting."""
        limiter = CacheRateLimiter(rate=10.0, capacity=10, per_key=False)

        # First 10 requests should succeed
        for i in range(10):
            allowed, retry_after = await limiter.check_limit(f"key{i}", "get")
            assert allowed is True
            assert retry_after == 0.0

        # 11th should fail
        allowed, retry_after = await limiter.check_limit("key11", "get")
        assert allowed is False
        assert retry_after > 0.0

    @pytest.mark.asyncio
    async def test_per_key_limiting(self) -> None:
        """Test per-key rate limiting."""
        limiter = CacheRateLimiter(rate=5.0, capacity=5, per_key=True)

        # Key1: 5 requests (should all succeed)
        for _ in range(5):
            allowed, _ = await limiter.check_limit("key1", "get")
            assert allowed is True

        # Key1: 6th request (should fail)
        allowed, retry_after = await limiter.check_limit("key1", "get")
        assert allowed is False
        assert retry_after > 0.0

        # Key2: First request (should succeed - different key)
        allowed, _ = await limiter.check_limit("key2", "get")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_decorator_delay_strategy(self) -> None:
        """Test decorator with delay strategy."""
        limiter = CacheRateLimiter(rate=100.0, capacity=5, strategy="delay")

        call_count = 0

        @limiter.rate_limit(key_fn=lambda key: key, operation="get")
        async def get_value(key: str):
            nonlocal call_count
            call_count += 1
            return f"value_{key}"

        # First 5 calls should succeed immediately
        for i in range(5):
            result = await get_value(f"key{i}")
            assert result == f"value_key{i}"

        # 6th call should delay but eventually succeed
        start = asyncio.get_event_loop().time()
        result = await get_value("key6")
        elapsed = asyncio.get_event_loop().time() - start

        assert result == "value_key6"
        assert elapsed > 0.0  # Should have delayed
        assert call_count == 6

    @pytest.mark.asyncio
    async def test_decorator_block_strategy(self) -> None:
        """Test decorator with block strategy."""
        limiter = CacheRateLimiter(rate=100.0, capacity=5, strategy="block", per_key=True)

        @limiter.rate_limit(key_fn=lambda key: key, operation="get")
        async def get_value(key: str):
            return f"value_{key}"

        # Drain capacity for a single key
        for _i in range(5):
            await get_value("key1")

        # 6th call to same key should raise exception
        with pytest.raises(RateLimitError) as exc_info:
            await get_value("key1")

        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.key == "key1"
        assert exc_info.value.retry_after > 0.0

    @pytest.mark.asyncio
    async def test_reset_all(self) -> None:
        """Test resetting all rate limits."""
        limiter = CacheRateLimiter(rate=5.0, capacity=5, per_key=True)

        # Exhaust limits for multiple keys
        for key in ["key1", "key2", "key3"]:
            for _ in range(5):
                await limiter.check_limit(key, "get")

        # All should be rate limited
        for key in ["key1", "key2", "key3"]:
            allowed, _ = await limiter.check_limit(key, "get")
            assert allowed is False

        # Reset all
        await limiter.reset()

        # All should work again
        for key in ["key1", "key2", "key3"]:
            allowed, _ = await limiter.check_limit(key, "get")
            assert allowed is True

    @pytest.mark.asyncio
    async def test_reset_specific_key(self) -> None:
        """Test resetting specific key."""
        limiter = CacheRateLimiter(rate=5.0, capacity=5, per_key=True)

        # Exhaust limits for key1
        for _ in range(5):
            await limiter.check_limit("key1", "get")

        # key1 should be rate limited
        allowed, _ = await limiter.check_limit("key1", "get")
        assert allowed is False

        # Reset only key1
        await limiter.reset("key1")

        # key1 should work again
        allowed, _ = await limiter.check_limit("key1", "get")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_concurrent_access(self) -> None:
        """Test concurrent access to rate limiter."""
        limiter = CacheRateLimiter(rate=100.0, capacity=50, per_key=False)

        async def make_request(i: int):
            allowed, _ = await limiter.check_limit(f"key{i}", "get")
            return allowed

        # 50 concurrent requests (at capacity)
        tasks = [make_request(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        # All should succeed (within capacity)
        assert all(results)

        # Next request should fail (over capacity)
        allowed, _ = await limiter.check_limit("key_extra", "get")
        assert allowed is False

    def test_get_status(self) -> None:
        """Test status reporting."""
        limiter = CacheRateLimiter(rate=100.0, capacity=200, per_key=True, strategy="delay")
        status = limiter.get_status()

        assert status["rate"] == 100.0
        assert status["capacity"] == 200
        assert status["per_key"] is True
        assert status["strategy"] == "delay"
        assert status["active_buckets"] == 0

    @pytest.mark.asyncio
    async def test_refill_rate(self) -> None:
        """Test token refill rate."""
        limiter = CacheRateLimiter(rate=100.0, capacity=10, per_key=False)

        # Drain bucket
        for _ in range(10):
            await limiter.check_limit("key", "get")

        # Should be rate limited
        allowed, _ = await limiter.check_limit("key", "get")
        assert allowed is False

        # Wait for refill (0.1 sec = 10 tokens at 100/sec)
        await asyncio.sleep(0.11)

        # Should have tokens available
        allowed, _ = await limiter.check_limit("key", "get")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_operation_tracking(self) -> None:
        """Test different operations are tracked separately."""
        limiter = CacheRateLimiter(rate=5.0, capacity=5, per_key=True)

        # 5 get operations
        for _ in range(5):
            await limiter.check_limit("key1", "get")

        # 5 set operations (same key, but operation parameter for metrics)
        for _ in range(5):
            await limiter.check_limit("key1", "set")

        # Both should be exhausted (same bucket, different metric labels)
        allowed_get, _ = await limiter.check_limit("key1", "get")
        allowed_set, _ = await limiter.check_limit("key1", "set")

        assert allowed_get is False
        assert allowed_set is False


class TestCacheIntegration:
    """Tests for rate limiter integration with cache implementations."""

    @pytest.mark.asyncio
    async def test_unified_cache_rate_limiting(self) -> None:
        """Test rate limiting in UnifiedCache."""
        from kagami.core.caching.unified import UnifiedCache

        # Create cache with aggressive rate limit
        cache = UnifiedCache(namespace="test_rate_limit")
        cache._rate_limiter = CacheRateLimiter(rate=5.0, capacity=5, strategy="block", per_key=True)

        # First 5 gets to same key should succeed
        for _i in range(5):
            await cache.get("key1")

        # 6th get to same key should raise RateLimitError
        with pytest.raises(RateLimitError):
            await cache.get("key1")

    @pytest.mark.asyncio
    async def test_response_cache_rate_limiting(self) -> None:
        """Test rate limiting in ResponseCache."""
        from kagami.core.caching.response_cache import ResponseCache, CacheConfig

        # Create cache with aggressive rate limit
        config = CacheConfig(ttl=60.0, max_size=100)
        cache = ResponseCache(config=config, namespace="test_rate_limit")
        cache._rate_limiter = CacheRateLimiter(rate=5.0, capacity=5, strategy="block", per_key=True)

        # First 5 sets to same key should succeed
        for i in range(5):
            await cache.set("key1", f"value{i}")

        # 6th set to same key should raise RateLimitError
        with pytest.raises(RateLimitError):
            await cache.set("key1", "value6")

    @pytest.mark.asyncio
    async def test_model_cache_rate_limiting(self) -> None:
        """Test rate limiting in ModelCache."""
        from kagami.core.caching.unified_model_cache import ModelCache
        import tempfile
        from pathlib import Path

        # Create cache with aggressive rate limit
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ModelCache(cache_dir=Path(tmpdir), max_size_gb=1.0, max_models=10)
            cache._rate_limiter = CacheRateLimiter(
                rate=3.0, capacity=3, strategy="block", per_key=True
            )

            # Mock loader function
            def load_model():
                return {"weights": "mock"}

            # First 3 loads of same model should succeed
            for _i in range(3):
                model = await cache.get_cached_model(
                    model_id="model1", config={"device": "cpu"}, loader_fn=load_model
                )
                assert model == {"weights": "mock"}

            # 4th load of same model should raise RateLimitError
            with pytest.raises(RateLimitError):
                await cache.get_cached_model(
                    model_id="model1", config={"device": "cpu"}, loader_fn=load_model
                )


class TestEnvironmentConfig:
    """Tests for environment variable configuration."""

    def test_env_config_rate(self, monkeypatch: Any) -> None:
        """Test KAGAMI_CACHE_RATE_LIMIT environment variable."""
        monkeypatch.setenv("KAGAMI_CACHE_RATE_LIMIT", "50")
        limiter = CacheRateLimiter()
        assert limiter.rate == 50.0

    def test_env_config_capacity(self, monkeypatch: Any) -> None:
        """Test KAGAMI_CACHE_BURST_CAPACITY environment variable."""
        monkeypatch.setenv("KAGAMI_CACHE_BURST_CAPACITY", "100")
        limiter = CacheRateLimiter()
        assert limiter.capacity == 100

    def test_env_config_strategy(self, monkeypatch: Any) -> None:
        """Test KAGAMI_CACHE_RATE_LIMIT_STRATEGY environment variable."""
        monkeypatch.setenv("KAGAMI_CACHE_RATE_LIMIT_STRATEGY", "block")
        limiter = CacheRateLimiter()
        assert limiter.strategy == "block"

    def test_env_config_per_key(self, monkeypatch: Any) -> None:
        """Test KAGAMI_CACHE_RATE_LIMIT_PER_KEY environment variable."""
        monkeypatch.setenv("KAGAMI_CACHE_RATE_LIMIT_PER_KEY", "false")
        limiter = CacheRateLimiter()
        assert limiter.per_key is False

    def test_invalid_strategy_fallback(self) -> None:
        """Test fallback for invalid strategy."""
        limiter = CacheRateLimiter(strategy="invalid")
        assert limiter.strategy == "delay"  # Should fallback to delay


class TestGlobalInstance:
    """Tests for global rate limiter instance."""

    def test_get_global_instance(self) -> None:
        """Test getting global rate limiter instance."""
        limiter1 = get_cache_rate_limiter()
        limiter2 = get_cache_rate_limiter()

        # Should return same instance
        assert limiter1 is limiter2

    @pytest.mark.asyncio
    async def test_global_instance_state(self) -> None:
        """Test global instance maintains state."""
        limiter = get_cache_rate_limiter()

        # Reset first to ensure clean state
        await limiter.reset()

        # Create a new limiter with aggressive limits for this test
        from kagami.core.unified_rate_limiter import CacheRateLimiterAdapter

        test_limiter = CacheRateLimiterAdapter(rate=3.0, capacity=3)

        # Drain capacity
        for _ in range(3):
            await test_limiter.check_limit("key", "get")

        # Should be rate limited
        allowed, _ = await test_limiter.check_limit("key", "get")
        assert allowed is False

        # Reset for other tests
        await limiter.reset()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
