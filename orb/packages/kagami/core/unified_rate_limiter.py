"""Unified rate limiting implementation for K os.

Consolidates multiple rate limiting implementations into a single, consistent interface.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""

    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_minute: int = 60
    window_size_seconds: int = 60
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    burst_size: int = 10
    use_redis: bool = False
    redis_ttl: int = 120
    namespace: str = "rl"


class UnifiedRateLimiter:
    """Unified rate limiter with multiple backend support."""

    MAX_CLIENTS = 100000

    def __init__(self, config: RateLimitConfig) -> None:
        """Initialize the rate limiter.

        Args:
            config: Rate limiting configuration
        """
        self.config = config
        self._lock = asyncio.Lock()
        from collections import OrderedDict

        self.clients: OrderedDict[str, deque[Any]] = OrderedDict()
        self.tokens: OrderedDict[str, float] = OrderedDict()
        self.last_update: OrderedDict[str, float] = OrderedDict()
        self.burst_attempts: OrderedDict[str, int] = OrderedDict()
        self.burst_reset_time: OrderedDict[str, float] = OrderedDict()
        self._redis_client = None

    def _evict_if_needed(self) -> None:
        """Evict oldest clients if max limit exceeded (LRU eviction)."""
        while len(self.clients) > self.MAX_CLIENTS:
            oldest = next(iter(self.clients))
            self.clients.pop(oldest, None)
            self.tokens.pop(oldest, None)
            self.last_update.pop(oldest, None)
            self.burst_attempts.pop(oldest, None)
            self.burst_reset_time.pop(oldest, None)

    def _increment_burst_attempts(self, client_id: str, current_time: float) -> int:
        """Increment burst counter for a client with automatic reset."""
        attempts = self.burst_attempts.get(client_id, 0)
        reset_time = self.burst_reset_time.get(client_id)
        if reset_time and current_time >= reset_time:
            attempts = 0
        attempts += 1
        self.burst_attempts[client_id] = attempts
        # Reset the burst penalty after 60 seconds without spikes
        self.burst_reset_time[client_id] = current_time + 60
        return attempts

    async def _get_redis(self) -> Redis[str] | None:
        """Get Redis client (lazy initialization)."""
        if self._redis_client is None and self.config.use_redis:
            try:
                from kagami.core.caching.redis import RedisClientFactory

                self._redis_client = RedisClientFactory.get_client(
                    purpose="default", async_mode=True, decode_responses=True
                )
            except Exception as e:
                logger.warning(f"Failed to get Redis client: {e}")
                self.config.use_redis = False
        return self._redis_client

    async def is_allowed(self, client_id: str) -> tuple[bool, int, int]:
        """Check if request is allowed for client.

        Args:
            client_id: Unique identifier for the client

        Returns:
            Tuple of (is_allowed, remaining_requests, reset_time_seconds)
        """
        if self.config.use_redis:
            return await self._is_allowed_redis(client_id)
        if self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return await self._is_allowed_sliding_window(client_id)
        elif self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            return await self._is_allowed_token_bucket(client_id)
        elif self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
            return await self._is_allowed_fixed_window(client_id)
        else:
            return await self._is_allowed_leaky_bucket(client_id)

    async def _is_allowed_sliding_window(self, client_id: str) -> tuple[bool, int, int]:
        """Sliding window rate limiting (in-memory)."""
        async with self._lock:
            self._evict_if_needed()
            current_time = time.time()
            if client_id not in self.clients:
                self.clients[client_id] = deque()
            client_requests = self.clients[client_id]
            self.clients.move_to_end(client_id)
            while (
                client_requests
                and client_requests[0] <= current_time - self.config.window_size_seconds
            ):
                client_requests.popleft()
            recent_requests = sum(1 for req_time in client_requests if req_time > current_time - 10)
            if recent_requests > self.config.burst_size * 2:
                attempts = self._increment_burst_attempts(client_id, current_time)
                if attempts > 3:
                    # Exponential backoff: 30s, 60s, 120s, 240s, capped at 300s
                    reset_time = min(300, 30 * 2 ** (attempts - 4))
                    return (False, 0, reset_time)
            if len(client_requests) >= self.config.requests_per_minute:
                oldest_request = client_requests[0]
                reset_time = (
                    int(oldest_request + self.config.window_size_seconds - current_time) + 1
                )
                return (False, 0, max(1, reset_time))
            client_requests.append(current_time)
            remaining = self.config.requests_per_minute - len(client_requests)
            if client_id in self.burst_attempts:
                del self.burst_attempts[client_id]
                self.burst_reset_time.pop(client_id, None)
            return (True, remaining, self.config.window_size_seconds)

    async def _is_allowed_token_bucket(self, client_id: str) -> tuple[bool, int, int]:
        """Token bucket rate limiting (in-memory)."""
        async with self._lock:
            self._evict_if_needed()
            current_time = time.time()
            if client_id not in self.tokens:
                self.tokens[client_id] = float(self.config.burst_size)
                self.last_update[client_id] = current_time
            self.tokens.move_to_end(client_id)
            self.last_update.move_to_end(client_id)
            time_passed = current_time - self.last_update[client_id]
            tokens_to_add = time_passed / 60 * self.config.requests_per_minute
            self.tokens[client_id] = min(
                self.config.burst_size, self.tokens[client_id] + tokens_to_add
            )
            self.last_update[client_id] = current_time
            if self.tokens[client_id] >= 1:
                self.tokens[client_id] -= 1
                remaining = int(self.tokens[client_id])
                return (True, remaining, self.config.window_size_seconds)
            tokens_needed = 1 - self.tokens[client_id]
            reset_time = int(tokens_needed * 60 / self.config.requests_per_minute) + 1
            return (False, 0, reset_time)

    async def _is_allowed_fixed_window(self, client_id: str) -> tuple[bool, int, int]:
        """Fixed window rate limiting (in-memory)."""
        async with self._lock:
            self._evict_if_needed()
            current_time = time.time()
            window_start = (
                int(current_time / self.config.window_size_seconds)
                * self.config.window_size_seconds
            )
            client_requests = self.clients.get(client_id)
            if client_requests is None:
                client_requests = deque()
                self.clients[client_id] = client_requests
            client_requests = deque(t for t in client_requests if t >= window_start)
            self.clients[client_id] = client_requests
            if len(client_requests) >= self.config.requests_per_minute:
                reset_time = int(window_start + self.config.window_size_seconds - current_time) + 1
                return (False, 0, reset_time)
            client_requests.append(current_time)
            remaining = self.config.requests_per_minute - len(client_requests)
            reset_time = int(window_start + self.config.window_size_seconds - current_time)
            return (True, remaining, reset_time)

    async def _is_allowed_leaky_bucket(self, client_id: str) -> tuple[bool, int, int]:
        """Leaky bucket rate limiting (in-memory)."""
        return await self._is_allowed_token_bucket(client_id)

    async def _is_allowed_redis(self, client_id: str) -> tuple[bool, int, int]:
        """Redis-backed rate limiting."""
        try:
            redis = await self._get_redis()
            if not redis:
                return await self._is_allowed_sliding_window(client_id)
            current_time = time.time()
            if self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
                window = current_time // self.config.window_size_seconds
                key = f"{self.config.namespace}:{client_id}:{window}"
                pipe = redis.pipeline()
                pipe.incr(key)
                pipe.expire(key, self.config.redis_ttl)
                results = await pipe.execute()
                count = results[0]
                if count > self.config.requests_per_minute:
                    reset_time = int((window + 1) * self.config.window_size_seconds - current_time)
                    return (False, 0, reset_time)
                remaining = self.config.requests_per_minute - count
                reset_time = int((window + 1) * self.config.window_size_seconds - current_time)
                return (True, remaining, reset_time)
            else:
                key = f"{self.config.namespace}:sw:{client_id}"
                window_start = current_time - self.config.window_size_seconds
                pipe = redis.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {str(current_time): current_time})
                pipe.zcard(key)
                pipe.expire(key, self.config.redis_ttl)
                results = await pipe.execute()
                count = results[2]
                if count > self.config.requests_per_minute:
                    oldest = await redis.zrange(key, 0, 0, withscores=True)
                    if oldest:
                        reset_time = (
                            int(oldest[0][1] + self.config.window_size_seconds - current_time) + 1
                        )
                    else:
                        reset_time = self.config.window_size_seconds
                    return (False, 0, reset_time)
                remaining = self.config.requests_per_minute - count
                return (True, remaining, self.config.window_size_seconds)
        except Exception as e:
            logger.warning(f"Redis rate limiting failed: {e}, falling back to in-memory")
            return await self._is_allowed_sliding_window(client_id)

    async def reset(self, client_id: str) -> None:
        """Reset rate limit for a client.

        Args:
            client_id: Client identifier to reset
        """
        async with self._lock:
            if client_id in self.clients:
                del self.clients[client_id]
            if client_id in self.tokens:
                self.tokens[client_id] = self.config.burst_size
            if client_id in self.burst_attempts:
                del self.burst_attempts[client_id]
        if self.config.use_redis:
            try:
                redis = await self._get_redis()
                if redis:
                    keys = [f"rl:{client_id}:*", f"rl:sw:{client_id}"]
                    for pattern in keys:
                        cursor = 0
                        while True:
                            cursor, matching_keys = await redis.scan(
                                cursor, match=pattern, count=100
                            )
                            if matching_keys:
                                await redis.delete(*matching_keys)
                            if cursor == 0:
                                break
            except Exception as e:
                logger.warning(f"Failed to reset Redis rate limit: {e}")

    def get_status(self) -> dict[str, Any]:
        """Get rate limiter status.

        Returns:
            Status dictionary
        """
        return {
            "strategy": self.config.strategy.value,
            "requests_per_minute": self.config.requests_per_minute,
            "window_size_seconds": self.config.window_size_seconds,
            "burst_size": self.config.burst_size,
            "use_redis": self.config.use_redis,
            "active_clients": len(self.clients),
            "burst_violations": len(self.burst_attempts),
        }


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, key: str, retry_after: float) -> None:
        super().__init__(message)
        self.key = key
        self.retry_after = retry_after


class CacheRateLimiterAdapter:
    """Adapter for cache operations using UnifiedRateLimiter.

    Provides backward compatibility with the old CacheRateLimiter interface.
    """

    def __init__(
        self,
        rate: float | None = None,
        capacity: int | None = None,
        per_key: bool | None = None,
        strategy: str | None = None,
        use_redis: bool = False,
    ) -> None:
        """Initialize cache rate limiter adapter.

        Args:
            rate: Operations per second (default: 100)
            capacity: Burst capacity (default: 200)
            per_key: Enable per-key rate limiting (default: True)
            strategy: "delay" or "block" on limit exceeded
            use_redis: Use Redis backend
        """
        import os

        self.rate = float(rate or os.getenv("KAGAMI_CACHE_RATE_LIMIT", "100"))  # type: ignore[arg-type]
        self.capacity = int(capacity or os.getenv("KAGAMI_CACHE_BURST_CAPACITY", "200"))  # type: ignore[arg-type]

        # Load per_key from env if not specified
        if per_key is None:
            per_key_env = os.getenv("KAGAMI_CACHE_RATE_LIMIT_PER_KEY", "true").lower()
            self.per_key = per_key_env in ("true", "1", "yes")
        else:
            self.per_key = per_key

        # Load strategy from env if not specified
        strategy_val = (
            strategy
            if strategy is not None
            else os.getenv("KAGAMI_CACHE_RATE_LIMIT_STRATEGY", "delay") or "delay"
        ).lower()

        # Validate and fallback for invalid strategy
        if strategy_val not in ("delay", "block"):
            logger.warning(f"Invalid rate limit strategy '{strategy_val}', using 'delay'")
            strategy_val = "delay"

        self.strategy = strategy_val
        self.use_redis = use_redis

        # Convert ops/sec to requests/minute
        requests_per_minute = int(self.rate * 60)

        config = RateLimitConfig(
            requests_per_minute=requests_per_minute,
            burst_size=self.capacity,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            use_redis=use_redis,
            namespace="kagami:cache:rl",
        )
        self._limiter = UnifiedRateLimiter(config)

        # For compatibility with old tests
        self.buckets = self._limiter.clients
        self.global_bucket = None  # Not used in UnifiedRateLimiter

        logger.info(
            f"CacheRateLimiterAdapter initialized: rate={self.rate} ops/s, "
            f"capacity={self.capacity}, per_key={self.per_key}, strategy={self.strategy}, redis={use_redis}"
        )

    async def check_limit(self, key: str, operation: str = "get") -> tuple[bool, float]:
        """Check if operation is within rate limit.

        Args:
            key: Cache key being accessed
            operation: Operation type ("get", "set[Any]", "delete")

        Returns:
            Tuple of (allowed: bool, retry_after: float)
        """
        # Use global limiter if per_key is False
        client_id = key if self.per_key else "global"
        is_allowed, _remaining, reset_time = await self._limiter.is_allowed(client_id)

        if is_allowed:
            return True, 0.0

        # Rate limited
        return False, float(reset_time)

    async def reset(self, key: str | None = None) -> None:
        """Reset rate limiter state.

        Args:
            key: Specific key to reset (None = reset all)
        """
        if key is None:
            # Reset all - need to clear all clients
            self._limiter.clients.clear()
            self._limiter.tokens.clear()
            self._limiter.last_update.clear()
            self._limiter.burst_attempts.clear()
            self._limiter.burst_reset_time.clear()
        else:
            await self._limiter.reset(key)

    def rate_limit(
        self,
        key_fn: Callable[..., str] | None = None,
        operation: str = "get",
        cache_type: str = "unified",
    ) -> Callable[..., Any]:
        """Decorator for rate-limited cache operations.

        Args:
            key_fn: Function to extract cache key from args (default: use arg[1])
            operation: Operation type for metrics ("get", "set[Any]", "delete")
            cache_type: Cache type label for metrics

        Returns:
            Decorated async function
        """
        from functools import wraps

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Extract key for rate limiting
                if key_fn:
                    limit_key = key_fn(*args, **kwargs)
                else:
                    # Default: assume key is second argument (after self)
                    limit_key = args[1] if len(args) > 1 else "default"

                # Check rate limit
                allowed, retry_after = await self.check_limit(limit_key, operation)

                if not allowed:
                    if self.strategy == "block":
                        # Raise exception immediately
                        raise RateLimitError(
                            f"Rate limit exceeded for key: {limit_key}",
                            key=limit_key,
                            retry_after=retry_after,
                        )
                    else:
                        # Delay strategy - wait and retry
                        logger.debug(f"Rate limit hit for {limit_key}, waiting {retry_after:.2f}s")
                        await asyncio.sleep(min(retry_after, 1.0))  # Cap at 1 second

                        # Retry once after delay
                        allowed, retry_after = await self.check_limit(limit_key, operation)
                        if not allowed:
                            # Still rate limited - raise exception
                            raise RateLimitError(
                                f"Rate limit exceeded for key: {limit_key} after retry",
                                key=limit_key,
                                retry_after=retry_after,
                            )

                # Proceed with operation
                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def get_status(self) -> dict[str, Any]:
        """Get rate limiter status.

        Returns:
            Status dictionary
        """

        return {
            "rate": self.rate,
            "capacity": self.capacity,
            "per_key": self.per_key,
            "strategy": self.strategy,
            "use_redis": self.use_redis,
            "active_buckets": len(self._limiter.clients),
            "global_bucket": None,  # Not used in UnifiedRateLimiter
        }


# Global instance for cache operations
_global_cache_limiter: CacheRateLimiterAdapter | None = None


def get_cache_rate_limiter() -> CacheRateLimiterAdapter:
    """Get or create global cache rate limiter instance.

    Returns:
        Global CacheRateLimiterAdapter instance
    """
    global _global_cache_limiter
    if _global_cache_limiter is None:
        _global_cache_limiter = CacheRateLimiterAdapter()
    return _global_cache_limiter
