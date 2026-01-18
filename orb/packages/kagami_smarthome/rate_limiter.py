"""Rate Limiter — Prevents API abuse and protects integrations.

Implements per-integration and per-action rate limiting to:
- Prevent accidental command flooding
- Respect external API rate limits
- Protect physical devices from rapid commands

Created: January 2, 2026
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit."""

    calls_per_minute: int = 60
    burst_limit: int = 10  # Max calls in 1 second burst
    cooldown_seconds: float = 1.0  # Minimum time between calls


# Default limits per integration
DEFAULT_LIMITS: dict[str, RateLimitConfig] = {
    # Local integrations - higher limits
    "control4": RateLimitConfig(calls_per_minute=120, burst_limit=20),
    "denon": RateLimitConfig(calls_per_minute=60, burst_limit=10),
    "unifi": RateLimitConfig(calls_per_minute=60, burst_limit=10),
    # Cloud integrations - respect their limits
    "tesla": RateLimitConfig(calls_per_minute=30, burst_limit=5, cooldown_seconds=2.0),
    "eight_sleep": RateLimitConfig(calls_per_minute=20, burst_limit=3, cooldown_seconds=3.0),
    "spotify": RateLimitConfig(calls_per_minute=30, burst_limit=5),
    # Physical devices - protect from rapid commands
    "fireplace": RateLimitConfig(calls_per_minute=4, burst_limit=1, cooldown_seconds=15.0),
    "tv_mount": RateLimitConfig(calls_per_minute=4, burst_limit=1, cooldown_seconds=15.0),
    "locks": RateLimitConfig(calls_per_minute=10, burst_limit=2, cooldown_seconds=5.0),
    # Default for unknown
    "default": RateLimitConfig(calls_per_minute=60, burst_limit=10),
}


@dataclass
class RateLimitState:
    """Tracks rate limit state for a key."""

    call_times: list[float] = field(default_factory=list)
    last_call: float = 0.0
    blocked_count: int = 0


class RateLimiter:
    """Rate limiter with per-key tracking and burst protection.

    Usage:
        limiter = RateLimiter()

        # Check before making a call
        if await limiter.acquire("control4"):
            await make_control4_call()
        else:
            logger.warning("Rate limited!")

        # Or use as context manager (waits if needed)
        async with limiter.limit("tesla"):
            await make_tesla_call()
    """

    def __init__(self, limits: dict[str, RateLimitConfig] | None = None):
        """Initialize rate limiter.

        Args:
            limits: Optional custom limits per key
        """
        self._limits = limits or DEFAULT_LIMITS
        self._states: dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._lock = asyncio.Lock()

    def get_limit(self, key: str) -> RateLimitConfig:
        """Get rate limit config for a key."""
        return self._limits.get(key, self._limits.get("default", RateLimitConfig()))

    async def acquire(self, key: str, wait: bool = True) -> bool:
        """Acquire rate limit permission.

        Args:
            key: Integration/action key
            wait: If True, wait for limit. If False, return immediately.

        Returns:
            True if acquired, False if rate limited and wait=False
        """
        async with self._lock:
            config = self.get_limit(key)
            state = self._states[key]
            now = time.time()

            # Clean old call times (keep last minute)
            state.call_times = [t for t in state.call_times if now - t < 60]

            # Check minute limit
            if len(state.call_times) >= config.calls_per_minute:
                if not wait:
                    state.blocked_count += 1
                    return False
                # Wait until oldest call expires
                wait_time = 60 - (now - state.call_times[0])
                logger.debug(f"Rate limited {key}, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                now = time.time()
                state.call_times = [t for t in state.call_times if now - t < 60]

            # Check burst limit (calls in last second)
            recent_calls = sum(1 for t in state.call_times if now - t < 1)
            if recent_calls >= config.burst_limit:
                if not wait:
                    state.blocked_count += 1
                    return False
                await asyncio.sleep(1.0)
                now = time.time()

            # Check cooldown
            time_since_last = now - state.last_call
            if time_since_last < config.cooldown_seconds:
                if not wait:
                    state.blocked_count += 1
                    return False
                await asyncio.sleep(config.cooldown_seconds - time_since_last)
                now = time.time()

            # Record call
            state.call_times.append(now)
            state.last_call = now
            return True

    def limit(self, key: str) -> RateLimitContext:
        """Context manager for rate limiting.

        Usage:
            async with limiter.limit("control4"):
                await make_call()
        """
        return RateLimitContext(self, key)

    def get_stats(self) -> dict[str, Any]:
        """Get rate limit statistics."""
        stats = {}
        for key, state in self._states.items():
            config = self.get_limit(key)
            now = time.time()
            recent_calls = len([t for t in state.call_times if now - t < 60])
            stats[key] = {
                "calls_last_minute": recent_calls,
                "limit_per_minute": config.calls_per_minute,
                "utilization": recent_calls / config.calls_per_minute
                if config.calls_per_minute > 0
                else 0,
                "blocked_count": state.blocked_count,
                "last_call_ago": now - state.last_call if state.last_call > 0 else None,
            }
        return stats

    def reset(self, key: str | None = None) -> None:
        """Reset rate limit state.

        Args:
            key: Specific key to reset, or None for all
        """
        if key:
            self._states[key] = RateLimitState()
        else:
            self._states.clear()


class RateLimitContext:
    """Async context manager for rate limiting."""

    def __init__(self, limiter: RateLimiter, key: str):
        self._limiter = limiter
        self._key = key

    async def __aenter__(self) -> None:
        await self._limiter.acquire(self._key, wait=True)

    async def __aexit__(self, *args: Any) -> None:
        pass


# Singleton instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get singleton rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


__all__ = [
    "DEFAULT_LIMITS",
    "RateLimitConfig",
    "RateLimiter",
    "get_rate_limiter",
]
