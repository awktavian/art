"""Per-user database connection limiter.

Prevents single user from exhausting connection pool.

P0 Mitigation: Database pool exhaustion attack.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class ConnectionLimiter:
    """Limits database connections per user to prevent pool exhaustion.

    P0 Mitigation for: Single user exhausting all 200 connections → API hang

    Usage:
        limiter = ConnectionLimiter(max_per_user=10)

        async with limiter.acquire(user_id="user_123"):
            # Use database connection
            result = await db.query(...)
    """

    def __init__(self, max_per_user: int = 10, max_anonymous: int = 5):
        """Initialize connection limiter.

        Args:
            max_per_user: Maximum connections per authenticated user
            max_anonymous: Maximum connections per anonymous user
        """
        self.max_per_user = max_per_user
        self.max_anonymous = max_anonymous

        self._connections: dict[str, int] = defaultdict(int)
        self._waiters: dict[str, list[asyncio.Future]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def acquire(self, user_id: str | None = None, timeout: float = 10.0) -> ConnectionToken:
        """Acquire connection slot for user.

        Args:
            user_id: User ID (None for anonymous)
            timeout: Max seconds to wait for slot

        Returns:
            Connection token (use as context manager)

        Raises:
            asyncio.TimeoutError: If slot not available within timeout
        """
        user_key = user_id or "anonymous"
        limit = self.max_per_user if user_id else self.max_anonymous

        async with self._lock:
            if self._connections[user_key] < limit:
                self._connections[user_key] += 1
                logger.debug(
                    f"Connection acquired for {user_key}: {self._connections[user_key]}/{limit}"
                )
                return ConnectionToken(self, user_key)

        # Wait for slot to become available
        waiter = asyncio.Future()
        self._waiters[user_key].append(waiter)

        try:
            await asyncio.wait_for(waiter, timeout=timeout)
            return ConnectionToken(self, user_key)
        except TimeoutError:
            self._waiters[user_key].remove(waiter)
            logger.warning(
                f"Connection limit reached for {user_key}: "
                f"{self._connections[user_key]}/{limit} (timeout after {timeout}s)"
            )
            raise

    async def release(self, user_key: str) -> None:
        """Release connection slot."""
        async with self._lock:
            self._connections[user_key] -= 1

            logger.debug(f"Connection released for {user_key}: {self._connections[user_key]}")

            # Wake up next waiter
            if self._waiters[user_key]:
                waiter = self._waiters[user_key].pop(0)
                self._connections[user_key] += 1
                waiter.set_result(None)

    def get_stats(self) -> dict[str, Any]:
        """Get current limiter statistics."""
        return {
            "active_connections": dict(self._connections),
            "waiting_users": {
                user: len(waiters) for user, waiters in self._waiters.items() if waiters
            },
            "limits": {
                "per_user": self.max_per_user,
                "anonymous": self.max_anonymous,
            },
        }


class ConnectionToken:
    """Token representing connection slot ownership.

    Use as context manager:
        async with token:
            # Connection slot held
            pass
        # Slot automatically released
    """

    def __init__(self, limiter: ConnectionLimiter, user_key: str):
        self.limiter = limiter
        self.user_key = user_key
        self._released = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self._released:
            await self.limiter.release(self.user_key)
            self._released = True


# Global limiter instance
_global_limiter: ConnectionLimiter | None = None


def get_connection_limiter() -> ConnectionLimiter:
    """Get global connection limiter instance."""
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = ConnectionLimiter(
            max_per_user=10,  # Prevent single user from using >10 connections
            max_anonymous=5,  # Anonymous users get fewer connections
        )
    return _global_limiter
