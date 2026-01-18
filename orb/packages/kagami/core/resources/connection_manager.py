"""Connection management for databases and Redis.

Provides managed connections with automatic cleanup and pooling.
"""

import asyncio
import logging
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from kagami.core.resources.tracker import track_resource

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Base connection manager with automatic cleanup.

    Features:
    - Automatic resource cleanup
    - Resource leak tracking
    - Error handling with proper cleanup
    - Transaction management
    - Metrics collection

    Attributes:
        connection: Underlying connection object
        closed: Whether connection is closed
    """

    def __init__(self, connection: Any) -> None:
        """Initialize connection manager.

        Args:
            connection: Connection object to manage
        """
        self.connection = connection
        self._resource_id: str | None = None
        self._closed = False
        self._queries_executed = 0
        self._bytes_transferred = 0

    async def __aenter__(self) -> "ConnectionManager":
        """Async context manager entry."""
        await self.open()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        """Async context manager exit with cleanup."""
        await self.close()
        return False

    async def open(self) -> None:
        """Open/initialize the connection."""
        if self._closed:
            raise RuntimeError("Connection is closed")

        # Track resource
        self._resource_id = track_resource(
            resource_type="connection",
            resource_id=str(id(self.connection)),
            metadata={"type": self.__class__.__name__},
        )

        logger.debug(f"Connection opened: {self.__class__.__name__}")

    async def close(self) -> None:
        """Close the connection with cleanup."""
        if self._closed:
            return

        cleanup_error = None
        try:
            # Close underlying connection
            if self.connection:
                try:
                    # Try async close first
                    if hasattr(self.connection, "close"):
                        close_result = self.connection.close()
                        if asyncio.iscoroutine(close_result):
                            await close_result
                    elif hasattr(self.connection, "aclose"):
                        await self.connection.aclose()
                except Exception as e:
                    cleanup_error = e
                    logger.error(f"Failed to close connection: {e}")

            # Log metrics
            if self._queries_executed > 0:
                logger.debug(
                    f"Connection closed: queries={self._queries_executed}, "
                    f"bytes={self._bytes_transferred}"
                )

        finally:
            self._closed = True

            # Untrack resource
            if self._resource_id:
                from kagami.core.resources.tracker import get_resource_tracker

                tracker = get_resource_tracker()
                tracker.untrack(self._resource_id)
                self._resource_id = None

            if cleanup_error:
                raise cleanup_error

    @property
    def closed(self) -> bool:
        """Check if connection is closed."""
        return self._closed


class DatabaseConnectionManager(ConnectionManager):
    """Managed database connection with automatic cleanup.

    Features:
    - Transaction management with auto-rollback on error
    - Connection pooling integration
    - Query metrics
    - Automatic cleanup

    Usage:
        # With session from get_async_db_session
        from kagami.core.database.async_connection import get_async_db_session

        async with get_async_db_session() as session:
            async with DatabaseConnectionManager(session) as mgr:
                result = await mgr.execute(query)
                await mgr.commit()

        # Direct usage
        async with DatabaseConnectionManager.from_pool() as mgr:
            result = await mgr.execute(query)
            # Auto-commit on success, auto-rollback on error
    """

    def __init__(self, session: AsyncSession, auto_commit: bool = True) -> None:
        """Initialize database connection manager.

        Args:
            session: SQLAlchemy async session
            auto_commit: Whether to auto-commit on success
        """
        super().__init__(session)
        self.session = session
        self.auto_commit = auto_commit
        self._in_transaction = False

    @classmethod
    async def from_pool(cls, auto_commit: bool = True) -> "DatabaseConnectionManager":
        """Create manager from connection pool.

        Args:
            auto_commit: Whether to auto-commit on success

        Returns:
            Database connection manager
        """
        from kagami.core.database.async_connection import get_async_db_session

        # Get session from pool
        session_cm = get_async_db_session()
        session = await session_cm.__aenter__()

        # Create manager
        manager = cls(session, auto_commit=auto_commit)
        manager._session_context = session_cm
        return manager

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        """Exit with transaction management."""
        try:
            if exc_type is not None:
                # Error occurred - rollback
                await self.rollback()
            elif self.auto_commit and self._in_transaction:
                # Success - commit
                await self.commit()
        finally:
            await self.close()

        return False

    async def execute(self, query: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute a query.

        Args:
            query: SQL query or statement
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Query result
        """
        if self._closed:
            raise RuntimeError("Connection is closed")

        self._queries_executed += 1
        self._in_transaction = True

        try:
            result = await self.session.execute(query, *args, **kwargs)
            return result
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            await self.rollback()
            raise

    async def commit(self) -> None:
        """Commit current transaction."""
        if self._closed:
            raise RuntimeError("Connection is closed")

        try:
            await self.session.commit()
            self._in_transaction = False
            logger.debug("Transaction committed")
        except Exception as e:
            logger.error(f"Commit failed: {e}")
            await self.rollback()
            raise

    async def rollback(self) -> None:
        """Rollback current transaction."""
        if self._closed:
            return

        try:
            await self.session.rollback()
            self._in_transaction = False
            logger.debug("Transaction rolled back")
        except Exception as e:
            logger.error(f"Rollback failed: {e}")

    async def flush(self) -> None:
        """Flush pending changes."""
        if self._closed:
            raise RuntimeError("Connection is closed")

        await self.session.flush()

    async def refresh(self, instance: Any) -> None:
        """Refresh instance from database.

        Args:
            instance: SQLAlchemy model instance
        """
        if self._closed:
            raise RuntimeError("Connection is closed")

        await self.session.refresh(instance)

    async def close(self) -> None:
        """Close connection and cleanup."""
        # Rollback any pending transaction
        if self._in_transaction:
            await self.rollback()

        # Close session context if we own it
        if hasattr(self, "_session_context"):
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Failed to close session context: {e}")

        await super().close()


class RedisConnectionManager(ConnectionManager):
    """Managed Redis connection with automatic cleanup.

    Features:
    - Pipeline support
    - Transaction (MULTI/EXEC) support
    - Automatic cleanup
    - Connection metrics

    Usage:
        async with RedisConnectionManager.from_pool() as mgr:
            await mgr.set("key", "value")
            value = await mgr.get("key")

        # With pipeline
        async with RedisConnectionManager.from_pool() as mgr:
            async with mgr.pipeline() as pipe:
                pipe.set("key1", "value1")
                pipe.set("key2", "value2")
                await pipe.execute()
    """

    def __init__(self, connection: Any) -> None:
        """Initialize Redis connection manager.

        Args:
            connection: Redis connection
        """
        super().__init__(connection)
        self.redis = connection
        self._pipelines: list[Any] = []

    @classmethod
    async def from_pool(cls) -> "RedisConnectionManager":
        """Create manager from Redis pool.

        Returns:
            Redis connection manager
        """
        from kagami.core.caching.redis.factory import get_redis_client

        redis = await get_redis_client()
        return cls(redis)

    async def get(self, key: str) -> Any:
        """Get value from Redis.

        Args:
            key: Redis key

        Returns:
            Value or None
        """
        if self._closed:
            raise RuntimeError("Connection is closed")

        self._queries_executed += 1
        return await self.redis.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None, px: int | None = None) -> bool:
        """Set value in Redis.

        Args:
            key: Redis key
            value: Value to set[Any]
            ex: Expiration in seconds
            px: Expiration in milliseconds

        Returns:
            True if successful
        """
        if self._closed:
            raise RuntimeError("Connection is closed")

        self._queries_executed += 1
        return await self.redis.set(key, value, ex=ex, px=px)

    async def delete(self, *keys: str) -> int:
        """Delete keys from Redis.

        Args:
            *keys: Keys to delete

        Returns:
            Number of keys deleted
        """
        if self._closed:
            raise RuntimeError("Connection is closed")

        self._queries_executed += 1
        return await self.redis.delete(*keys)

    async def exists(self, *keys: str) -> int:
        """Check if keys exist.

        Args:
            *keys: Keys to check

        Returns:
            Number of existing keys
        """
        if self._closed:
            raise RuntimeError("Connection is closed")

        self._queries_executed += 1
        return await self.redis.exists(*keys)

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key.

        Args:
            key: Redis key
            seconds: Expiration in seconds

        Returns:
            True if expiration was set[Any]
        """
        if self._closed:
            raise RuntimeError("Connection is closed")

        self._queries_executed += 1
        return await self.redis.expire(key, seconds)

    def pipeline(self) -> Any:
        """Create a pipeline for batching commands.

        Returns:
            Redis pipeline context manager
        """
        if self._closed:
            raise RuntimeError("Connection is closed")

        pipe = self.redis.pipeline()
        self._pipelines.append(pipe)
        return pipe

    async def close(self) -> None:
        """Close connection and cleanup pipelines."""
        # Close any open pipelines
        for pipe in self._pipelines:
            try:
                if hasattr(pipe, "reset"):
                    pipe.reset()
            except Exception as e:
                logger.error(f"Failed to close pipeline: {e}")

        self._pipelines.clear()

        # Note: Redis client typically uses connection pooling
        # so we don't actually close the connection here
        # The pool will manage connection lifecycle

        await super().close()


# Convenience functions


async def get_database_connection(
    auto_commit: bool = True,
) -> DatabaseConnectionManager:
    """Get managed database connection from pool.

    Args:
        auto_commit: Whether to auto-commit on success

    Returns:
        Database connection manager
    """
    return await DatabaseConnectionManager.from_pool(auto_commit=auto_commit)


async def get_redis_connection() -> RedisConnectionManager:
    """Get managed Redis connection from pool.

    Returns:
        Redis connection manager
    """
    return await RedisConnectionManager.from_pool()
