"""Login attempt tracking for account lockout protection.

This module implements login attempt tracking to prevent brute force attacks
by locking accounts after a certain number of failed attempts.
"""

import logging
import time
from threading import Lock
from typing import TYPE_CHECKING

from kagami.core.boot_mode import is_test_mode
from kagami.core.config import get_int_config
from redis.exceptions import RedisError

if TYPE_CHECKING:
    from redis.asyncio import Redis as AsyncRedis

logger = logging.getLogger(__name__)

# Import metrics for observability

try:
    from kagami.observability.metrics import AUTH_LOCKOUTS
except ImportError:
    # Graceful degradation if metrics not available
    AUTH_LOCKOUTS: object | None = None  # type: ignore  # Redef

# Default configuration constants (can be overridden by environment variables)
DEFAULT_MAX_LOGIN_ATTEMPTS = 5  # Maximum failed login attempts before lockout
DEFAULT_LOCKOUT_DURATION_MINUTES = 15  # Account lockout duration
DEFAULT_MEMORY_QUEUE_SIZE = 100  # Maximum queue size for in-memory fallback
DEFAULT_CLEANUP_INTERVAL_SECONDS = 3600  # Memory cleanup interval (1 hour)


class LoginTracker:
    """Tracks login attempts and enforces account lockout policy."""

    def __init__(self) -> None:
        """Initialize login tracker with Redis backend."""
        self.redis_client: AsyncRedis[str] | None = None

        # Load configuration from environment variables with defaults
        self.max_attempts: int = get_int_config("LOGIN_MAX_ATTEMPTS", DEFAULT_MAX_LOGIN_ATTEMPTS)
        self.lockout_minutes: int = get_int_config(
            "LOGIN_LOCKOUT_DURATION_MINUTES", DEFAULT_LOCKOUT_DURATION_MINUTES
        )
        self.memory_queue_size: int = get_int_config(
            "LOGIN_MEMORY_QUEUE_SIZE", DEFAULT_MEMORY_QUEUE_SIZE
        )
        self._cleanup_interval: int = get_int_config(
            "LOGIN_CLEANUP_INTERVAL_SECONDS", DEFAULT_CLEANUP_INTERVAL_SECONDS
        )

        # Log configuration on initialization
        logger.info(
            f"LoginTracker initialized with: max_attempts={self.max_attempts}, "
            f"lockout_minutes={self.lockout_minutes}, "
            f"memory_queue_size={self.memory_queue_size}, "
            f"cleanup_interval={self._cleanup_interval}s"
        )

        # Redis key prefixes
        self.attempts_prefix = "kagami:login:attempts:"
        self.lockout_prefix = "kagami:login:lockout:"

        # In-memory fallback for when Redis is unavailable
        # Use deque with configurable maxlen to prevent unbounded growth
        from collections import deque

        self._memory_attempts: dict[str, deque[float]] = {}
        self._memory_lockouts: dict[str, float] = {}
        self._use_redis = True
        self._last_cleanup = time.time()

        # Thread safety for in-memory operations when multiple workers
        self._memory_lock = Lock()
        self._cleanup_lock = Lock()

    async def initialize(self) -> None:
        """Initialize Redis connection.

        In Full Operation mode (production), Redis MUST be available.
        Fails fast rather than degrading to in-memory.
        """
        import os

        # Check if Full Operation mode is enabled
        env = (os.getenv("ENVIRONMENT") or "development").lower()
        full_operation = (
            os.getenv("KAGAMI_FULL_OPERATION") or ("1" if env == "production" else "0")
        ).lower() in ("1", "true", "yes", "on")

        try:
            from kagami.core.caching.redis import RedisClientFactory

            redis = RedisClientFactory.get_client(
                purpose="sessions", async_mode=True, decode_responses=True
            )
            await redis.ping()
            self.redis_client = redis
            self._use_redis = True
            logger.info("Login tracker connected to Redis")

        except (RedisError, Exception) as e:
            if full_operation and not is_test_mode():
                # K2 Full Operation Mode: fail-closed in production
                logger.error(
                    f"FULL OPERATION MODE: Redis required for login tracking but unavailable: {e}"
                )
                logger.error("Recovery: Ensure Redis is running - docker-compose up redis")
                # Emit metric for monitoring
                try:
                    from kagami.observability.metrics import REDIS_FALLBACK_TOTAL

                    REDIS_FALLBACK_TOTAL.labels(service="login_tracker").inc()
                except Exception:
                    pass
                raise RuntimeError(
                    f"Full Operation requires Redis for login tracking. Error: {e}"
                ) from None
            else:
                # Development/test: allow in-memory fallback
                logger.warning(f"Redis unavailable for login tracking, using memory: {e}")
                self._use_redis = False
                # Emit metric even in dev (for visibility)
                try:
                    from kagami.observability.metrics import REDIS_FALLBACK_TOTAL

                    REDIS_FALLBACK_TOTAL.labels(service="login_tracker").inc()
                except Exception:
                    pass

    async def record_failed_attempt(self, username: str) -> tuple[int, bool]:
        """Record a failed login attempt.

        Args:
            username: Username that failed login

        Returns:
            Tuple of (remaining_attempts, is_locked)
        """
        if self._use_redis and self.redis_client:
            return await self._record_failed_redis(username)
        else:
            return self._record_failed_memory(username)

    async def _record_failed_redis(self, username: str) -> tuple[int, bool]:
        """Record failed attempt in Redis."""
        redis = self.redis_client
        if redis is None:
            return 0, False
        try:
            # Check if already locked
            lockout_key = f"{self.lockout_prefix}{username}"
            if await redis.exists(lockout_key):
                return 0, True

            # Increment attempts
            attempts_key = f"{self.attempts_prefix}{username}"
            current_attempts = await redis.incr(attempts_key)

            # Set expiration on first attempt
            if current_attempts == 1:
                await redis.expire(attempts_key, self.lockout_minutes * 60)

            # Check if should lock
            if current_attempts >= self.max_attempts:
                # Lock the account
                await redis.setex(lockout_key, self.lockout_minutes * 60, str(int(time.time())))
                await redis.delete(attempts_key)
                logger.warning(
                    f"Account locked due to {current_attempts} failed attempts: {username}"
                )
                # Emit metric (best-effort, don't fail if metric broken)
                try:
                    if AUTH_LOCKOUTS:
                        AUTH_LOCKOUTS.labels(reason="max_attempts_exceeded").inc()
                except Exception as metric_err:
                    logger.debug(f"Failed to emit lockout metric: {metric_err}")
                return 0, True

            remaining = self.max_attempts - current_attempts
            return remaining, False

        except Exception as e:
            logger.error(f"Error recording failed attempt in Redis: {e}")
            # Fall back to memory
            self._use_redis = False
            return self._record_failed_memory(username)

    def _record_failed_memory(self, username: str) -> tuple[int, bool]:
        """Record failed attempt in memory (fallback) with cleanup and thread safety."""
        current_time = time.time()

        # Periodic cleanup with lock
        if current_time - self._last_cleanup > self._cleanup_interval:
            # Try to acquire cleanup lock without blocking
            if self._cleanup_lock.acquire(blocking=False):
                try:
                    self._cleanup_memory()
                finally:
                    self._cleanup_lock.release()

        # Thread-safe memory operations
        with self._memory_lock:
            # Check if locked
            if username in self._memory_lockouts:
                lockout_time = self._memory_lockouts[username]
                if current_time - lockout_time < self.lockout_minutes * 60:
                    return 0, True
                else:
                    # Lockout expired
                    del self._memory_lockouts[username]

            # Initialize deque if needed with configurable max length
            if username not in self._memory_attempts:
                from collections import deque

                self._memory_attempts[username] = deque(maxlen=self.memory_queue_size)

            # Clean old attempts
            attempts = self._memory_attempts[username]
            window_start = current_time - (self.lockout_minutes * 60)

            # Remove old attempts
            while attempts and attempts[0] < window_start:
                attempts.popleft()

            # Add new attempt
            self._memory_attempts[username].append(current_time)
            current_attempts = len(self._memory_attempts[username])

            # Check if should lock
            if current_attempts >= self.max_attempts:
                self._memory_lockouts[username] = current_time
                del self._memory_attempts[username]
                logger.warning(
                    f"Account locked due to {current_attempts} failed attempts: {username}"
                )
                # Emit metric
                if AUTH_LOCKOUTS:
                    AUTH_LOCKOUTS.labels(reason="max_attempts_exceeded").inc()
                return 0, True

            remaining = self.max_attempts - current_attempts
            return remaining, False

    def _cleanup_memory(self) -> None:
        """Clean up old entries from memory to prevent unbounded growth.

        Note: This method assumes it's called with _cleanup_lock already acquired.
        """
        current_time = time.time()
        self._last_cleanup = current_time

        # Thread-safe cleanup with memory lock
        with self._memory_lock:
            # Clean up old attempts
            window_start = current_time - (self.lockout_minutes * 60)
            usernames_to_remove = []

            for username, attempts in self._memory_attempts.items():
                # Remove old attempts
                while attempts and attempts[0] < window_start:
                    attempts.popleft()

                # Remove empty entries
                if not attempts:
                    usernames_to_remove.append(username)

            for username in usernames_to_remove:
                del self._memory_attempts[username]

            # Clean up expired lockouts
            lockouts_to_remove = []
            for username, lockout_time in self._memory_lockouts.items():
                if current_time - lockout_time > self.lockout_minutes * 60:
                    lockouts_to_remove.append(username)

            for username in lockouts_to_remove:
                del self._memory_lockouts[username]

        if usernames_to_remove or lockouts_to_remove:
            logger.info(
                f"Cleaned up {len(usernames_to_remove)} attempt entries and {len(lockouts_to_remove)} lockout entries"
            )

    async def is_locked(self, username: str) -> tuple[bool, int | None]:
        """Check if an account is locked.

        Args:
            username: Username to check

        Returns:
            Tuple of (is_locked, seconds_until_unlock)
        """
        if self._use_redis and self.redis_client:
            return await self._is_locked_redis(username)
        else:
            return self._is_locked_memory(username)

    async def _is_locked_redis(self, username: str) -> tuple[bool, int | None]:
        """Check lock status in Redis."""
        redis = self.redis_client
        if redis is None:
            return False, None
        try:
            lockout_key = f"{self.lockout_prefix}{username}"
            ttl = await redis.ttl(lockout_key)

            if ttl > 0:
                return True, ttl
            return False, None

        except Exception as e:
            logger.error(f"Error checking lock status in Redis: {e}")
            return self._is_locked_memory(username)

    def _is_locked_memory(self, username: str) -> tuple[bool, int | None]:
        """Check lock status in memory with thread safety."""
        with self._memory_lock:
            if username not in self._memory_lockouts:
                return False, None

            current_time = time.time()
            lockout_time = self._memory_lockouts[username]
            elapsed = current_time - lockout_time

            if elapsed < self.lockout_minutes * 60:
                remaining = int(self.lockout_minutes * 60 - elapsed)
                return True, remaining
            else:
                # Lockout expired
                del self._memory_lockouts[username]
                return False, None

    async def clear_attempts(self, username: str) -> None:
        """Clear login attempts after successful login.

        Args:
            username: Username to clear attempts for
        """
        redis = self.redis_client
        if self._use_redis and redis is not None:
            try:
                attempts_key = f"{self.attempts_prefix}{username}"
                await redis.delete(attempts_key)
            except Exception as e:
                logger.error(f"Error clearing attempts in Redis: {e}")
        else:
            # Clear from memory with thread safety
            with self._memory_lock:
                if username in self._memory_attempts:
                    del self._memory_attempts[username]

    async def unlock_account(self, username: str) -> bool:
        """Manually unlock an account (admin action).

        Args:
            username: Username to unlock

        Returns:
            True if account was locked and is now unlocked
        """
        redis = self.redis_client
        if self._use_redis and redis is not None:
            try:
                lockout_key = f"{self.lockout_prefix}{username}"
                attempts_key = f"{self.attempts_prefix}{username}"

                # Check if was locked
                was_locked = await redis.exists(lockout_key)

                # Clear both keys
                await redis.delete(lockout_key, attempts_key)

                if was_locked:
                    logger.info(f"Account manually unlocked: {username}")

                return bool(was_locked)

            except Exception as e:
                logger.error(f"Error unlocking account in Redis: {e}")
                return False
        else:
            # Unlock in memory with thread safety
            with self._memory_lock:
                was_locked = username in self._memory_lockouts
                if was_locked:
                    del self._memory_lockouts[username]
                    logger.info(f"Account manually unlocked: {username}")
                if username in self._memory_attempts:
                    del self._memory_attempts[username]
                return was_locked

    async def get_status(self, username: str) -> dict:
        """Get current status for a username.

        Args:
            username: Username to check

        Returns:
            Dictionary with status information
        """
        is_locked, unlock_seconds = await self.is_locked(username)

        if is_locked:
            return {
                "username": username,
                "is_locked": True,
                "unlock_in_seconds": unlock_seconds,
                "unlock_in_minutes": ((unlock_seconds + 59) // 60 if unlock_seconds else None),
                "attempts": 0,
                "remaining_attempts": 0,
            }

        # Get current attempts
        redis = self.redis_client
        if self._use_redis and redis is not None:
            try:
                attempts_key = f"{self.attempts_prefix}{username}"
                attempts = await redis.get(attempts_key)
                current_attempts = int(attempts) if attempts else 0
            except Exception:
                with self._memory_lock:
                    current_attempts = len(self._memory_attempts.get(username, []))
        else:
            with self._memory_lock:
                current_attempts = len(self._memory_attempts.get(username, []))

        return {
            "username": username,
            "is_locked": False,
            "unlock_in_seconds": None,
            "unlock_in_minutes": None,
            "attempts": current_attempts,
            "remaining_attempts": max(0, self.max_attempts - current_attempts),
        }


# Global instance
_login_tracker: LoginTracker | None = None


async def get_login_tracker() -> LoginTracker:
    """Get the global login tracker instance."""
    global _login_tracker

    if _login_tracker is None:
        _login_tracker = LoginTracker()
        await _login_tracker.initialize()

    return _login_tracker
