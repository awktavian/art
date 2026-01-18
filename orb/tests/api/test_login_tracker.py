"""Comprehensive tests for login attempt tracking and account lockout functionality.

Tests both Redis-backed and in-memory modes to ensure consistent behavior.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration
import asyncio
import time
from collections import deque
from unittest.mock import AsyncMock, patch
import pytest_asyncio
import redis.asyncio as redis
from redis.exceptions import RedisError
from kagami_api.security.login_tracker import LoginTracker, get_login_tracker


class TestLoginTrackerRedisMode:
    """Test LoginTracker with Redis backend."""

    @pytest_asyncio.fixture
    async def redis_client(self):
        """Create a mock Redis client."""
        client = AsyncMock(spec=redis.Redis)
        client.ping = AsyncMock(return_value=True)
        client.exists = AsyncMock(return_value=False)
        client.incr = AsyncMock(return_value=1)
        client.expire = AsyncMock(return_value=True)
        client.setex = AsyncMock(return_value=True)
        client.delete = AsyncMock(return_value=1)
        client.ttl = AsyncMock(return_value=-2)
        client.get = AsyncMock(return_value=None)
        return client

    @pytest_asyncio.fixture
    async def tracker_with_redis(self, redis_client: Any) -> Any:
        """Create LoginTracker with mocked Redis."""
        with (
            patch(
                "kagami.core.caching.redis.RedisClientFactory.get_client",
                return_value=redis_client,
            ),
            patch("kagami.core.boot_mode.is_test_mode", return_value=True),
        ):
            tracker = LoginTracker()
            await tracker.initialize()
            tracker.redis_client = redis_client
            return tracker

    @pytest.mark.asyncio
    async def test_initialization_with_redis(self, redis_client: Any) -> Any:
        """Test successful Redis initialization."""
        with (
            patch(
                "kagami.core.caching.redis.RedisClientFactory.get_client",
                return_value=redis_client,
            ),
            patch("kagami.core.boot_mode.is_test_mode", return_value=True),
        ):
            tracker = LoginTracker()
            await tracker.initialize()
            assert tracker._use_redis is True
            assert tracker.redis_client is not None
            redis_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_redis_failure(self) -> None:
        """Test fallback to memory when Redis unavailable."""
        # Mock the RedisClientFactory to raise exception
        with patch(
            "kagami.core.caching.redis.RedisClientFactory.get_client",
            side_effect=RedisError("Connection failed"),
        ):
            tracker = LoginTracker()
            await tracker.initialize()
            assert tracker._use_redis is False
            assert len(tracker._memory_attempts) == 0
            assert len(tracker._memory_lockouts) == 0

    @pytest.mark.asyncio
    async def test_record_failed_attempt_first(self, tracker_with_redis: Any) -> None:
        """Test recording first failed attempt."""
        tracker_with_redis.redis_client.incr.return_value = 1
        remaining, is_locked = await tracker_with_redis.record_failed_attempt("testuser")
        assert remaining == 4  # MAX_LOGIN_ATTEMPTS (5) - 1
        assert is_locked is False
        tracker_with_redis.redis_client.incr.assert_called_once()
        tracker_with_redis.redis_client.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_failed_attempt_multiple(self, tracker_with_redis: Any) -> None:
        """Test recording multiple failed attempts."""
        tracker_with_redis.redis_client.incr.side_effect = [1, 2, 3, 4]
        for i in range(4):
            remaining, is_locked = await tracker_with_redis.record_failed_attempt("testuser")
            assert remaining == 4 - i
            assert is_locked is False

    @pytest.mark.asyncio
    async def test_lockout_after_max_attempts(self, tracker_with_redis: Any) -> None:
        """Test account lockout after max attempts."""
        tracker_with_redis.redis_client.incr.return_value = 5
        tracker_with_redis.max_attempts = 5
        remaining, is_locked = await tracker_with_redis.record_failed_attempt("testuser")
        assert remaining == 0
        assert is_locked is True
        tracker_with_redis.redis_client.setex.assert_called_once()
        tracker_with_redis.redis_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_already_locked(self, tracker_with_redis: Any) -> None:
        """Test behavior when account is already locked."""
        tracker_with_redis.redis_client.exists.return_value = True
        remaining, is_locked = await tracker_with_redis.record_failed_attempt("testuser")
        assert remaining == 0
        assert is_locked is True
        tracker_with_redis.redis_client.incr.assert_not_called()

    @pytest.mark.asyncio
    async def test_is_locked_true(self, tracker_with_redis: Any) -> None:
        """Test checking if account is locked."""
        tracker_with_redis.redis_client.ttl.return_value = 300  # 5 minutes remaining
        is_locked, seconds_remaining = await tracker_with_redis.is_locked("testuser")
        assert is_locked is True
        assert seconds_remaining == 300

    @pytest.mark.asyncio
    async def test_is_locked_false(self, tracker_with_redis: Any) -> None:
        """Test checking unlocked account."""
        tracker_with_redis.redis_client.ttl.return_value = -2  # Key doesn't exist
        is_locked, seconds_remaining = await tracker_with_redis.is_locked("testuser")
        assert is_locked is False
        assert seconds_remaining is None

    @pytest.mark.asyncio
    async def test_clear_attempts(self, tracker_with_redis: Any) -> None:
        """Test clearing attempts after successful login."""
        await tracker_with_redis.clear_attempts("testuser")
        tracker_with_redis.redis_client.delete.assert_called_once_with(
            f"{tracker_with_redis.attempts_prefix}testuser"
        )

    @pytest.mark.asyncio
    async def test_unlock_account(self, tracker_with_redis: Any) -> None:
        """Test manual account unlock."""
        tracker_with_redis.redis_client.exists.return_value = True
        tracker_with_redis.redis_client.delete.return_value = 2
        was_locked = await tracker_with_redis.unlock_account("testuser")
        assert was_locked is True
        assert tracker_with_redis.redis_client.delete.call_count == 1

    @pytest.mark.asyncio
    async def test_get_status_locked(self, tracker_with_redis: Any) -> None:
        """Test getting status for locked account."""
        tracker_with_redis.redis_client.ttl.return_value = 600  # 10 minutes
        status = await tracker_with_redis.get_status("testuser")
        assert status["is_locked"] is True
        assert status["unlock_in_seconds"] == 600
        assert status["unlock_in_minutes"] == 10
        assert status["attempts"] == 0
        assert status["remaining_attempts"] == 0

    @pytest.mark.asyncio
    async def test_get_status_unlocked(self, tracker_with_redis: Any) -> None:
        """Test getting status for unlocked account with attempts."""
        tracker_with_redis.redis_client.ttl.return_value = -2
        tracker_with_redis.redis_client.get.return_value = "3"
        status = await tracker_with_redis.get_status("testuser")
        assert status["is_locked"] is False
        assert status["unlock_in_seconds"] is None
        assert status["attempts"] == 3
        assert status["remaining_attempts"] == 2


class TestLoginTrackerMemoryMode:
    """Test LoginTracker with in-memory fallback."""

    @pytest_asyncio.fixture
    async def tracker_memory(self):
        """Create LoginTracker in memory mode."""
        tracker = LoginTracker()
        await tracker.initialize()
        tracker._use_redis = False
        return tracker

    def test_record_failed_attempt_memory_first(self, tracker_memory: Any) -> None:
        """Test recording first failed attempt in memory."""
        remaining, is_locked = tracker_memory._record_failed_memory("testuser")
        assert remaining == 4
        assert is_locked is False
        assert "testuser" in tracker_memory._memory_attempts
        assert len(tracker_memory._memory_attempts["testuser"]) == 1

    def test_record_failed_attempt_memory_multiple(self, tracker_memory: Any) -> None:
        """Test recording multiple failed attempts in memory."""
        for i in range(4):
            remaining, is_locked = tracker_memory._record_failed_memory("testuser")
            assert remaining == 4 - i
            assert is_locked is False
            assert len(tracker_memory._memory_attempts["testuser"]) == i + 1

    def test_lockout_after_max_attempts_memory(self, tracker_memory: Any) -> None:
        """Test account lockout after max attempts in memory."""
        tracker_memory.max_attempts = 5
        for _ in range(4):
            tracker_memory._record_failed_memory("testuser")
        remaining, is_locked = tracker_memory._record_failed_memory("testuser")
        assert remaining == 0
        assert is_locked is True
        assert "testuser" in tracker_memory._memory_lockouts
        assert "testuser" not in tracker_memory._memory_attempts

    def test_check_already_locked_memory(self, tracker_memory: Any) -> None:
        """Test behavior when account is already locked in memory."""
        current_time = time.time()
        tracker_memory._memory_lockouts["testuser"] = current_time
        remaining, is_locked = tracker_memory._record_failed_memory("testuser")
        assert remaining == 0
        assert is_locked is True

    def test_lockout_expiration_memory(self, tracker_memory: Any) -> None:
        """Test lockout expiration in memory."""
        # Set lockout in the past
        tracker_memory._memory_lockouts["testuser"] = time.time() - (
            tracker_memory.lockout_minutes * 60 + 1
        )
        remaining, is_locked = tracker_memory._record_failed_memory("testuser")
        assert remaining == 4
        assert is_locked is False
        assert "testuser" not in tracker_memory._memory_lockouts

    def test_is_locked_memory(self, tracker_memory: Any) -> None:
        """Test checking if account is locked in memory."""
        current_time = time.time()
        tracker_memory._memory_lockouts["testuser"] = current_time
        is_locked, seconds_remaining = tracker_memory._is_locked_memory("testuser")
        assert is_locked is True
        assert seconds_remaining is not None
        assert seconds_remaining > 0

    def test_is_locked_expired_memory(self, tracker_memory: Any) -> None:
        """Test checking expired lockout in memory."""
        tracker_memory._memory_lockouts["testuser"] = time.time() - (
            tracker_memory.lockout_minutes * 60 + 1
        )
        is_locked, seconds_remaining = tracker_memory._is_locked_memory("testuser")
        assert is_locked is False
        assert seconds_remaining is None
        assert "testuser" not in tracker_memory._memory_lockouts

    def test_cleanup_memory(self, tracker_memory: Any) -> None:
        """Test memory cleanup of old entries."""
        current_time = time.time()
        old_time = current_time - (tracker_memory.lockout_minutes * 60 + 1)
        # Add old attempts
        from collections import deque

        tracker_memory._memory_attempts["olduser"] = deque([old_time])
        tracker_memory._memory_attempts["currentuser"] = deque([current_time])
        # Add old lockout
        tracker_memory._memory_lockouts["oldlocked"] = old_time
        tracker_memory._memory_lockouts["currentlocked"] = current_time
        tracker_memory._cleanup_memory()
        assert "olduser" not in tracker_memory._memory_attempts
        assert "currentuser" in tracker_memory._memory_attempts
        assert "oldlocked" not in tracker_memory._memory_lockouts
        assert "currentlocked" in tracker_memory._memory_lockouts

    def test_sliding_window_memory(self, tracker_memory: Any) -> None:
        """Test sliding window behavior in memory mode."""
        current_time = time.time()
        # Add attempts at different times
        from collections import deque

        tracker_memory._memory_attempts["testuser"] = deque()
        # Add old attempt (outside window)
        old_attempt = current_time - (tracker_memory.lockout_minutes * 60 + 1)
        tracker_memory._memory_attempts["testuser"].append(old_attempt)
        # Add recent attempts
        for i in range(3):
            tracker_memory._memory_attempts["testuser"].append(current_time - i)
        # Record new attempt - old one should be removed
        remaining, is_locked = tracker_memory._record_failed_memory("testuser")
        # Should have 4 attempts (3 recent + 1 new), old one removed
        assert len(tracker_memory._memory_attempts["testuser"]) == 4
        assert remaining == 1
        assert is_locked is False

    @pytest.mark.asyncio
    async def test_unlock_account_memory(self, tracker_memory: Any) -> None:
        """Test manual unlock in memory mode."""
        tracker_memory._memory_lockouts["testuser"] = time.time()
        tracker_memory._memory_attempts["testuser2"] = deque([time.time()])
        was_locked = await tracker_memory.unlock_account("testuser")
        assert was_locked is True
        assert "testuser" not in tracker_memory._memory_lockouts
        was_locked2 = await tracker_memory.unlock_account("testuser2")
        assert was_locked2 is False
        assert "testuser2" not in tracker_memory._memory_attempts


class TestLoginTrackerIntegration:
    """Integration tests for LoginTracker."""

    @pytest.mark.asyncio
    async def test_fallback_to_memory_on_redis_error(self) -> None:
        """Test automatic fallback to memory when Redis fails."""
        tracker = LoginTracker()
        # Mock Redis to fail after initialization
        with patch("kagami.core.caching.redis.RedisClientFactory.get_client") as mock_factory:
            mock_client = AsyncMock(spec=redis.Redis)
            mock_client.ping = AsyncMock(return_value=True)
            mock_client.exists = AsyncMock(side_effect=RedisError("Connection lost"))
            mock_factory.return_value = mock_client
            await tracker.initialize()
            assert tracker._use_redis is True
            # This should trigger fallback to memory
            remaining, is_locked = await tracker.record_failed_attempt("testuser")
            assert tracker._use_redis is False
            assert remaining == 4
            assert is_locked is False

    @pytest.mark.asyncio
    async def test_get_login_tracker_singleton(self) -> None:
        """Test that get_login_tracker returns singleton."""
        tracker1 = await get_login_tracker()
        tracker2 = await get_login_tracker()
        assert tracker1 is tracker2

    @pytest.mark.asyncio
    async def test_concurrent_attempts(self) -> None:
        """Test handling concurrent login attempts."""
        tracker_memory = LoginTracker()
        tracker_memory._use_redis = False
        tasks = []
        # Simulate concurrent failed attempts
        for _ in range(10):
            tasks.append(asyncio.create_task(tracker_memory.record_failed_attempt("testuser")))
        results = await asyncio.gather(*tasks)
        # At least one should result in lockout
        locked_count = sum(1 for _, is_locked in results if is_locked)
        assert locked_count >= 1
        # Check final state
        is_locked, _ = await tracker_memory.is_locked("testuser")
        assert is_locked is True

    def test_max_deque_size_memory(self) -> None:
        """Test that deque has max size to prevent unbounded growth."""
        tracker_memory = LoginTracker()
        tracker_memory._use_redis = False
        # First access creates deque
        tracker_memory._record_failed_memory("testuser")
        # Check deque has maxlen set
        attempts_deque = tracker_memory._memory_attempts["testuser"]
        assert attempts_deque.maxlen == 100

    @pytest.mark.asyncio
    async def test_configuration_from_environment(self) -> None:
        """Test configuration from environment variables."""
        with patch("kagami_api.security.login_tracker.get_int_config") as mock_config:
            mock_config.side_effect = lambda key, default: {
                "LOGIN_MAX_ATTEMPTS": 3,
                "LOGIN_LOCKOUT_DURATION_MINUTES": 30,
            }.get(key, default)
            tracker = LoginTracker()
            assert tracker.max_attempts == 3
            assert tracker.lockout_minutes == 30
