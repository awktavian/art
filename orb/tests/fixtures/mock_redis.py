"""Mock Redis client for testing without external Redis dependency.

Provides an in-memory implementation of Redis operations commonly used
in K os, including idempotency key storage, rate limiting, and caching.

Usage:
    @pytest.fixture
    async def test_with_redis(mock_redis) -> None:
        # Use mock_redis instead of real Redis
        await mock_redis.set("key", "value")
        value = await mock_redis.get("key")
        assert value == b"value"
"""

import asyncio
import time
from typing import Any

import pytest
import pytest_asyncio


class MockRedis:
    """Mock Redis client that implements common Redis operations in-memory."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}
        self._expiry: dict[str, float] = {}
        self._lists: dict[str, list[bytes]] = {}
        self._sets: dict[str, set] = {}
        self._hashes: dict[str, dict[bytes, bytes]] = {}
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []

    def _track_call(self, method: str, *args: Any, **kwargs: Any) -> None:
        """Track method calls for debugging."""
        self.call_count += 1
        self.calls.append(
            {"method": method, "args": args, "kwargs": kwargs, "timestamp": time.time()}
        )

    def _is_expired(self, key: str) -> bool:
        """Check if a key has expired."""
        if key in self._expiry:
            if time.time() > self._expiry[key]:
                # Key expired, remove it
                self._store.pop(key, None)
                self._expiry.pop(key, None)
                return True
        return False

    def _ensure_bytes(self, value: str | bytes) -> bytes:
        """Ensure value is bytes."""
        if isinstance(value, str):
            return value.encode("utf-8")
        return value

    async def get(self, key: str) -> bytes | None:
        """Get value for key."""
        self._track_call("get", key)

        if self._is_expired(key):
            return None

        return self._store.get(key)

    async def set(
        self,
        key: str,
        value: str | bytes,
        ex: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool | None:
        """Set key to value with optional expiry and conditions.

        Args:
            key: The key to set
            value: The value to set
            ex: Expiry time in seconds
            nx: Only set if key does NOT exist
            xx: Only set if key DOES exist

        Returns:
            True if set, False if condition not met, None otherwise
        """
        self._track_call("set", key, value, ex=ex, nx=nx, xx=xx)

        # Check expiry for existing key
        if key in self._store:
            self._is_expired(key)

        # NX: Only set if not exists
        if nx and key in self._store:
            return False

        # XX: Only set if exists
        if xx and key not in self._store:
            return False

        # Set the value
        self._store[key] = self._ensure_bytes(value)

        # Set expiry if provided
        if ex is not None:
            self._expiry[key] = time.time() + ex

        return True

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        self._track_call("delete", *keys)

        count = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                self._expiry.pop(key, None)
                count += 1

        return count

    async def exists(self, *keys: str) -> int:
        """Check if keys exist."""
        self._track_call("exists", *keys)

        count = 0
        for key in keys:
            if not self._is_expired(key) and key in self._store:
                count += 1

        return count

    async def keys(self, pattern: str = "*") -> list[bytes]:
        """Get all keys matching pattern."""
        self._track_call("keys", pattern)

        # Remove expired keys first
        for key in list(self._store.keys()):
            self._is_expired(key)

        # Simple pattern matching
        if pattern == "*":
            return [k.encode("utf-8") for k in self._store.keys()]

        # Basic glob pattern support
        import fnmatch

        matching = [k for k in self._store.keys() if fnmatch.fnmatch(k, pattern)]
        return [k.encode("utf-8") for k in matching]

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiry time for key."""
        self._track_call("expire", key, seconds)

        if key not in self._store or self._is_expired(key):
            return False

        self._expiry[key] = time.time() + seconds
        return True

    async def ttl(self, key: str) -> int:
        """Get time to live for key in seconds."""
        self._track_call("ttl", key)

        if key not in self._store or self._is_expired(key):
            return -2  # Key does not exist

        if key not in self._expiry:
            return -1  # Key exists but has no expiry

        remaining = int(self._expiry[key] - time.time())
        return max(0, remaining)

    async def incr(self, key: str) -> int:
        """Increment key by 1."""
        self._track_call("incr", key)

        if key not in self._store or self._is_expired(key):
            self._store[key] = b"1"
            return 1

        try:
            value = int(self._store[key])
            value += 1
            self._store[key] = str(value).encode("utf-8")
            return value
        except (ValueError, TypeError):
            raise ValueError("Value is not an integer") from None

    async def decr(self, key: str) -> int:
        """Decrement key by 1."""
        self._track_call("decr", key)

        if key not in self._store or self._is_expired(key):
            self._store[key] = b"-1"
            return -1

        try:
            value = int(self._store[key])
            value -= 1
            self._store[key] = str(value).encode("utf-8")
            return value
        except (ValueError, TypeError):
            raise ValueError("Value is not an integer") from None

    # List operations
    async def lpush(self, key: str, *values: str | bytes) -> int:
        """Push values to the left of list."""
        self._track_call("lpush", key, *values)

        if key not in self._lists:
            self._lists[key] = []

        for value in reversed(values):
            self._lists[key].insert(0, self._ensure_bytes(value))

        return len(self._lists[key])

    async def rpush(self, key: str, *values: str | bytes) -> int:
        """Push values to the right of list."""
        self._track_call("rpush", key, *values)

        if key not in self._lists:
            self._lists[key] = []

        for value in values:
            self._lists[key].append(self._ensure_bytes(value))

        return len(self._lists[key])

    async def lrange(self, key: str, start: int, stop: int) -> list[bytes]:
        """Get range of elements from list."""
        self._track_call("lrange", key, start, stop)

        if key not in self._lists:
            return []

        # Handle negative indices
        lst = self._lists[key]
        if stop == -1:
            stop = len(lst)
        else:
            stop = stop + 1

        return lst[start:stop]

    # Hash operations
    async def hset(self, name: str, key: str | bytes, value: str | bytes) -> int:
        """Set hash field."""
        self._track_call("hset", name, key, value)

        if name not in self._hashes:
            self._hashes[name] = {}

        key_bytes = self._ensure_bytes(key)
        value_bytes = self._ensure_bytes(value)

        is_new = key_bytes not in self._hashes[name]
        self._hashes[name][key_bytes] = value_bytes

        return 1 if is_new else 0

    async def hget(self, name: str, key: str | bytes) -> bytes | None:
        """Get hash field value."""
        self._track_call("hget", name, key)

        if name not in self._hashes:
            return None

        key_bytes = self._ensure_bytes(key)
        return self._hashes[name].get(key_bytes)

    async def hgetall(self, name: str) -> dict[bytes, bytes]:
        """Get all hash fields and values."""
        self._track_call("hgetall", name)

        if name not in self._hashes:
            return {}

        return self._hashes[name].copy()

    # Sorted set operations (for rate limiting)
    async def zadd(self, key: str, mapping: dict[str, int | float]) -> int:
        """Add members with scores to sorted set."""
        self._track_call("zadd", key, mapping)

        if key not in self._sets:
            self._sets[key] = {}  # type: ignore[assignment]

        added = 0
        for member, score in mapping.items():
            member_bytes = self._ensure_bytes(member)
            if member_bytes not in self._sets[key]:
                added += 1
            self._sets[key][member_bytes] = float(score)  # type: ignore[index]

        return added

    async def zcount(self, key: str, min_score: int | float, max_score: int | float) -> int:
        """Count members in sorted set within score range."""
        self._track_call("zcount", key, min_score, max_score)

        if key not in self._sets:
            return 0

        count = 0
        for score in self._sets[key].values():
            if min_score <= score <= max_score:
                count += 1

        return count

    async def zremrangebyscore(
        self, key: str, min_score: int | float, max_score: int | float
    ) -> int:
        """Remove members in sorted set within score range."""
        self._track_call("zremrangebyscore", key, min_score, max_score)

        if key not in self._sets:
            return 0

        to_remove = []
        for member, score in self._sets[key].items():
            if min_score <= score <= max_score:
                to_remove.append(member)

        for member in to_remove:
            del self._sets[key][member]

        return len(to_remove)

    async def setex(self, key: str, seconds: int, value: str | bytes) -> bool:
        """Set key with expiry in seconds."""
        self._track_call("setex", key, seconds, value)

        self._store[key] = self._ensure_bytes(value)
        self._expiry[key] = time.time() + seconds

        return True

    def reset(self) -> None:
        """Reset all stored data."""
        self._store.clear()
        self._expiry.clear()
        self._lists.clear()
        self._sets.clear()
        self._hashes.clear()
        self.call_count = 0
        self.calls.clear()

    async def ping(self) -> bool:
        """Ping the Redis server."""
        return True

    async def close(self) -> None:
        """Close the connection (no-op for mock)."""

    async def __aenter__(self) -> Any:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


# Pytest fixtures


@pytest.fixture
def mock_redis() -> MockRedis:
    """Provide a mock Redis client."""
    return MockRedis()


@pytest_asyncio.fixture
async def mock_redis_client(mock_redis: MockRedis, monkeypatch: Any) -> Any:
    """Provide a mock Redis client and patch get_redis_client.

    This fixture automatically patches the Redis client getter
    so tests using get_redis_client() will get the mock.
    """
    # Patch the Redis client getter
    # NOTE: Production get_redis_client is SYNC, not async
    try:
        from kagami.core import redis_client

        def mock_get_redis_client():
            return mock_redis

        monkeypatch.setattr(redis_client, "get_redis_client", mock_get_redis_client)
    except ImportError:
        pass  # Module doesn't exist, that's OK

    yield mock_redis

    # Cleanup
    mock_redis.reset()


@pytest_asyncio.fixture(autouse=False)
async def auto_mock_redis(mock_redis_client):
    """Auto-mock Redis for all tests in a module.

    Use by adding to pytest_plugins or conftest.py:
        pytest_plugins = ["tests.fixtures.mock_redis"]

    Or use explicitly:
        def test_something(auto_mock_redis) -> None:
            # Redis is mocked automatically
    """
    yield mock_redis_client


# Tests for the mock itself


@pytest.mark.asyncio
async def test_mock_redis_set_get(mock_redis) -> None:
    """Test basic set/get operations."""
    await mock_redis.set("key", "value")
    result = await mock_redis.get("key")
    assert result == b"value"


@pytest.mark.asyncio
async def test_mock_redis_set_nx(mock_redis) -> None:
    """Test SET with NX flag."""
    # First set should succeed
    result = await mock_redis.set("key", "value1", nx=True)
    assert result is True

    # Second set should fail (key exists)
    result = await mock_redis.set("key", "value2", nx=True)
    assert result is False

    # Value should still be the first one
    value = await mock_redis.get("key")
    assert value == b"value1"


@pytest.mark.asyncio
async def test_mock_redis_expiry(mock_redis) -> None:
    """Test key expiry."""
    # Set with 1 second expiry
    await mock_redis.set("key", "value", ex=1)

    # Should exist immediately
    assert await mock_redis.exists("key") == 1

    # Wait for expiry
    await asyncio.sleep(1.1)

    # Should be gone
    assert await mock_redis.exists("key") == 0
    assert await mock_redis.get("key") is None


@pytest.mark.asyncio
async def test_mock_redis_delete(mock_redis) -> None:
    """Test delete operation."""
    await mock_redis.set("key1", "value1")
    await mock_redis.set("key2", "value2")

    # Delete one key
    count = await mock_redis.delete("key1")
    assert count == 1

    # key1 should be gone, key2 should remain
    assert await mock_redis.get("key1") is None
    assert await mock_redis.get("key2") == b"value2"


# ============================================================================
# Fixtures
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
