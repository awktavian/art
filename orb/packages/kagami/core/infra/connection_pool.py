"""Unified connection pooling for K os.

This module consolidates connection pool patterns from:
- mcp_servers/mcp_utils.py (ConnectionPool)
- Various HTTP client implementations
- Database connection managers

Provides reusable connection pooling for expensive resources.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class PoolConfig:
    """Configuration for connection pools.

    Attributes:
        max_size: Maximum number of connections in pool
        min_size: Minimum number of connections to maintain
        max_lifetime: Maximum lifetime of a connection (seconds)
        health_check_interval: How often to check connection health (seconds)
        acquire_timeout: Max time to wait for a connection (seconds)
        validate_on_acquire: Whether to validate connections before returning them
    """

    max_size: int = 10
    min_size: int = 2
    max_lifetime: float = 3600.0  # 1 hour
    health_check_interval: float = 30.0  # 30 seconds
    acquire_timeout: float = 5.0  # 5 seconds
    validate_on_acquire: bool = True


class ConnectionPool(Generic[T]):
    """Generic connection pool for reusing expensive resources.

    Features:
    - Automatic health checking
    - Connection lifecycle management
    - Configurable pool size
    - Timeout handling
    - Graceful shutdown

    Usage:
        async def create_connection():
            return await connect_to_service()

        async def is_healthy(conn):
            return await conn.ping()

        pool = ConnectionPool(
            factory=create_connection,
            health_check=is_healthy,
            config=PoolConfig(max_size=20)
        )

        async with pool.acquire() as conn:
            result = await conn.query(...)
    """

    def __init__(
        self,
        factory: Callable[[], T] | Callable[[], Any],
        health_check: Callable[[T], bool] | Callable[[T], Any] | None = None,
        config: PoolConfig | None = None,
        cleanup: Callable[[T], None] | Callable[[T], Any] | None = None,
    ) -> None:
        """Initialize connection pool.

        Args:
            factory: Async function to create new connections
            health_check: Optional async function to check connection health
            config: Pool configuration
            cleanup: Optional async function to clean up connections
        """
        self.factory = factory
        self.health_check = health_check
        self.config = config or PoolConfig()
        self.cleanup = cleanup

        self.pool: list[tuple[T, float]] = []  # (connection, created_at)
        self.in_use: dict[int, T] = {}  # connection_id -> connection
        self._lock = asyncio.Lock()
        self._closed = False
        self._last_health_check = 0.0

    async def acquire(self, timeout: float | None = None) -> T:
        """Acquire a connection from the pool.

        Args:
            timeout: Maximum time to wait (uses config default if None)

        Returns:
            Connection instance

        Raises:
            TimeoutError: If timeout exceeded
            RuntimeError: If pool is closed
        """
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        timeout = timeout or self.config.acquire_timeout
        start_time = time.time()

        while time.time() - start_time < timeout:
            async with self._lock:
                # Try to get from pool
                while self.pool:
                    conn, created_at = self.pool.pop(0)

                    # Check if connection is too old
                    if time.time() - created_at > self.config.max_lifetime:
                        await self._close_connection(conn)
                        continue

                    # Validate if required
                    if self.config.validate_on_acquire:
                        if not await self._is_healthy(conn):
                            await self._close_connection(conn)
                            continue

                    # Connection is good
                    self.in_use[id(conn)] = conn
                    return conn

                # Create new if under limit
                if len(self.in_use) < self.config.max_size:
                    conn = await self.factory()  # type: ignore  # Misc
                    self.in_use[id(conn)] = conn
                    return conn

            # Wait a bit before retrying
            await asyncio.sleep(0.1)

        raise TimeoutError(
            f"Could not acquire connection within {timeout}s "
            f"(pool size: {len(self.pool)}, in use: {len(self.in_use)})"
        )

    async def release(self, conn: T) -> None:
        """Return a connection to the pool.

        Args:
            conn: Connection to release
        """
        async with self._lock:
            conn_id = id(conn)
            if conn_id not in self.in_use:
                logger.warning("Attempted to release connection not in use")
                return

            del self.in_use[conn_id]

            # Check if we should keep it
            if len(self.pool) < self.config.max_size and not self._closed:
                # Validate before returning to pool
                if await self._is_healthy(conn):
                    self.pool.append((conn, time.time()))
                else:
                    await self._close_connection(conn)
            else:
                await self._close_connection(conn)

    async def _is_healthy(self, conn: T) -> bool:
        """Check if a connection is healthy.

        Args:
            conn: Connection to check

        Returns:
            True if healthy, False otherwise
        """
        if self.health_check is None:
            return True

        try:
            result = self.health_check(conn)
            if asyncio.iscoroutine(result):
                return await result  # type: ignore  # External lib
            return bool(result)
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False

    async def _close_connection(self, conn: T) -> None:
        """Close a connection gracefully.

        Args:
            conn: Connection to close
        """
        try:
            if self.cleanup:
                result = self.cleanup(conn)
                if asyncio.iscoroutine(result):
                    await result
            elif hasattr(conn, "close"):
                close_method = conn.close
                result = close_method()
                if asyncio.iscoroutine(result):
                    await result
        except Exception as e:
            logger.debug(f"Error closing connection: {e}")

    async def close_all(self) -> None:
        """Close all connections in the pool."""
        async with self._lock:
            self._closed = True

            # Close all connections in parallel
            all_conns = [conn for conn, _ in self.pool] + list(self.in_use.values())
            if all_conns:
                await asyncio.gather(
                    *[self._close_connection(conn) for conn in all_conns], return_exceptions=True
                )
            self.pool.clear()
            self.in_use.clear()

            logger.info("Connection pool closed")

    def stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Dict with pool stats
        """
        return {
            "pooled": len(self.pool),
            "in_use": len(self.in_use),
            "max_size": self.config.max_size,
            "min_size": self.config.min_size,
            "closed": self._closed,
        }

    async def __aenter__(self) -> "ConnectionPool[T]":
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
        """Context manager exit."""
        await self.close_all()


class PooledConnection:
    """Context manager for acquiring pooled connections.

    Usage:
        async with pool.acquire() as conn:
            result = await conn.query(...)
    """

    def __init__(self, pool: ConnectionPool[T], timeout: float | None = None) -> None:
        self.pool = pool
        self.timeout = timeout
        self.conn: T | None = None

    async def __aenter__(self) -> T:
        """Acquire connection."""
        self.conn = await self.pool.acquire(self.timeout)
        return self.conn  # type: ignore[return-value]  # pool.acquire returns T

    async def __aexit__(self, exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
        """Release connection."""
        if self.conn is not None:
            await self.pool.release(self.conn)


# Make acquire return a context manager
ConnectionPool.acquire = lambda self, timeout=None: PooledConnection(self, timeout)  # type: ignore[method-assign,assignment,return-value]
