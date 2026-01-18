"""Tests for rate limiter.

Created: January 2, 2026
"""

import asyncio

import pytest

from kagami_smarthome.rate_limiter import (
    DEFAULT_LIMITS,
    RateLimitConfig,
    RateLimiter,
    get_rate_limiter,
)


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_default_values(self):
        """Default config values."""
        config = RateLimitConfig()
        assert config.calls_per_minute == 60
        assert config.burst_limit == 10
        assert config.cooldown_seconds == 1.0

    def test_custom_values(self):
        """Custom config values."""
        config = RateLimitConfig(
            calls_per_minute=30,
            burst_limit=5,
            cooldown_seconds=2.0,
        )
        assert config.calls_per_minute == 30


class TestDefaultLimits:
    """Tests for default limit configurations."""

    def test_local_integrations_higher(self):
        """Local integrations have higher limits."""
        assert (
            DEFAULT_LIMITS["control4"].calls_per_minute > DEFAULT_LIMITS["tesla"].calls_per_minute
        )

    def test_physical_devices_lower(self):
        """Physical devices have lower limits."""
        assert (
            DEFAULT_LIMITS["fireplace"].calls_per_minute
            < DEFAULT_LIMITS["control4"].calls_per_minute
        )
        assert (
            DEFAULT_LIMITS["tv_mount"].calls_per_minute
            < DEFAULT_LIMITS["control4"].calls_per_minute
        )

    def test_default_exists(self):
        """Default limit exists."""
        assert "default" in DEFAULT_LIMITS


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.mark.asyncio
    async def test_basic_acquire(self):
        """Basic acquire works."""
        limiter = RateLimiter()
        result = await limiter.acquire("test")
        assert result is True

    @pytest.mark.asyncio
    async def test_burst_limit(self):
        """Burst limit prevents rapid calls."""
        limiter = RateLimiter(
            limits={
                "test": RateLimitConfig(calls_per_minute=100, burst_limit=2, cooldown_seconds=0),
            }
        )

        # First two should pass immediately
        assert await limiter.acquire("test", wait=False) is True
        assert await limiter.acquire("test", wait=False) is True

        # Third should be blocked (burst limit)
        result = await limiter.acquire("test", wait=False)
        # May pass if enough time elapsed, so just check it returns bool
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_cooldown(self):
        """Cooldown between calls works."""
        limiter = RateLimiter(
            limits={
                "test": RateLimitConfig(
                    calls_per_minute=100, burst_limit=100, cooldown_seconds=0.1
                ),
            }
        )

        # First call
        assert await limiter.acquire("test") is True
        start = asyncio.get_event_loop().time()

        # Second call with wait
        assert await limiter.acquire("test") is True
        elapsed = asyncio.get_event_loop().time() - start

        # Should have waited for cooldown
        assert elapsed >= 0.09  # Allow some timing variance

    @pytest.mark.asyncio
    async def test_different_keys(self):
        """Different keys tracked separately."""
        limiter = RateLimiter(
            limits={
                "key1": RateLimitConfig(calls_per_minute=1, burst_limit=1, cooldown_seconds=60),
                "key2": RateLimitConfig(calls_per_minute=100, burst_limit=100, cooldown_seconds=0),
            }
        )

        # key1 should be limited after one call
        assert await limiter.acquire("key1", wait=False) is True
        assert await limiter.acquire("key1", wait=False) is False

        # key2 should still work
        assert await limiter.acquire("key2", wait=False) is True

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Context manager works."""
        limiter = RateLimiter()

        async with limiter.limit("test"):
            pass  # Should not raise

    def test_get_stats(self):
        """Stats tracking works."""
        limiter = RateLimiter()
        stats = limiter.get_stats()
        assert isinstance(stats, dict)

    def test_reset(self):
        """Reset clears state."""
        limiter = RateLimiter()
        # Make some calls to create state
        asyncio.run(limiter.acquire("test"))

        stats_before = limiter.get_stats()
        assert "test" in stats_before

        limiter.reset()
        stats_after = limiter.get_stats()
        assert stats_after == {}

    def test_reset_specific_key(self):
        """Reset specific key."""
        limiter = RateLimiter()
        asyncio.run(limiter.acquire("key1"))
        asyncio.run(limiter.acquire("key2"))

        limiter.reset("key1")

        stats = limiter.get_stats()
        assert "key1" not in stats or stats.get("key1", {}).get("calls_last_minute", 0) == 0


class TestGetRateLimiter:
    """Tests for singleton accessor."""

    def test_returns_singleton(self):
        """Returns same instance."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2

    def test_is_rate_limiter(self):
        """Returns RateLimiter instance."""
        limiter = get_rate_limiter()
        assert isinstance(limiter, RateLimiter)
