"""Comprehensive tests for connection management.

Tests database connection pooling, Redis connection management,
transaction handling, and cleanup guarantees.
"""

import asyncio
import pytest
from typing import Any
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from kagami.core.resources.connection_manager import (
    ConnectionManager,
    DatabaseConnectionManager,
    RedisConnectionManager,
    get_database_connection,
    get_redis_connection,
)
from kagami.core.resources.tracker import get_resource_tracker, reset_tracker


@pytest.fixture(autouse=True)
def reset_resource_tracker():
    """Reset tracker before each test."""
    reset_tracker()
    yield
    reset_tracker()


@pytest.fixture
def mock_connection():
    """Create mock connection."""
    conn = Mock()
    conn.close = AsyncMock()
    return conn


@pytest.fixture
def mock_session():
    """Create mock SQLAlchemy session."""
    session = Mock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_redis():
    """Create mock Redis connection."""
    redis = Mock()
    redis.get = AsyncMock()
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    redis.exists = AsyncMock()
    redis.expire = AsyncMock()
    redis.pipeline = Mock()
    return redis


class TestConnectionManager:
    """Test base ConnectionManager class."""

    @pytest.mark.asyncio
    async def test_basic_lifecycle(self, mock_connection):
        """Test basic open/close lifecycle."""
        async with ConnectionManager(mock_connection) as mgr:
            assert not mgr.closed
            assert mgr.connection is mock_connection

        assert mgr.closed
        mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_resource_tracking(self, mock_connection):
        """Test that connections are tracked."""
        tracker = get_resource_tracker()

        async with ConnectionManager(mock_connection) as mgr:
            # Should be tracked
            resources = tracker.get_resources("connection")
            assert len(resources) == 1
            assert resources[0].metadata["type"] == "ConnectionManager"

        # Should be untracked after exit
        resources = tracker.get_resources("connection")
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_cleanup_on_error(self, mock_connection):
        """Test cleanup happens even on error."""
        tracker = get_resource_tracker()

        try:
            async with ConnectionManager(mock_connection) as mgr:
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should be cleaned up
        resources = tracker.get_resources("connection")
        assert len(resources) == 0
        mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_double_close_is_safe(self, mock_connection):
        """Test that double close doesn't error."""
        mgr = ConnectionManager(mock_connection)
        await mgr.open()
        await mgr.close()
        await mgr.close()  # Should not raise

        # Should only close once
        mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_error_handling(self, mock_connection):
        """Test that close errors are handled properly."""
        mock_connection.close = AsyncMock(side_effect=RuntimeError("Close failed"))

        mgr = ConnectionManager(mock_connection)
        await mgr.open()

        with pytest.raises(RuntimeError, match="Close failed"):
            await mgr.close()

        # Should still be marked as closed
        assert mgr.closed

    @pytest.mark.asyncio
    async def test_sync_close_method(self):
        """Test connection with sync close method."""
        conn = Mock()
        conn.close = Mock()  # Sync close

        async with ConnectionManager(conn) as mgr:
            pass

        conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_aclose_method(self):
        """Test connection with aclose method."""
        conn = Mock(spec=["aclose"])
        conn.aclose = AsyncMock()

        async with ConnectionManager(conn) as mgr:
            pass

        conn.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_without_close(self):
        """Test connection object without close method."""
        conn = Mock(spec=[])  # No close method

        async with ConnectionManager(conn) as mgr:
            pass

        # Should not raise


class TestDatabaseConnectionManager:
    """Test DatabaseConnectionManager class."""

    @pytest.mark.asyncio
    async def test_basic_lifecycle(self, mock_session):
        """Test basic database connection lifecycle."""
        async with DatabaseConnectionManager(mock_session) as mgr:
            assert mgr.session is mock_session
            assert not mgr.closed

        assert mgr.closed
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query(self, mock_session):
        """Test executing a query."""
        mock_result = Mock()
        mock_session.execute.return_value = mock_result

        async with DatabaseConnectionManager(mock_session) as mgr:
            result = await mgr.execute("SELECT * FROM users")
            assert result is mock_result

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_commit_on_success(self, mock_session):
        """Test auto-commit on successful execution."""
        async with DatabaseConnectionManager(mock_session, auto_commit=True) as mgr:
            await mgr.execute("INSERT INTO users VALUES (1, 'test')")

        # Should commit on success
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_rollback_on_error(self, mock_session):
        """Test auto-rollback on error."""
        try:
            async with DatabaseConnectionManager(mock_session, auto_commit=True) as mgr:
                await mgr.execute("INSERT INTO users VALUES (1, 'test')")
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should rollback on error
        mock_session.rollback.assert_called()
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_auto_commit(self, mock_session):
        """Test with auto_commit=False."""
        async with DatabaseConnectionManager(mock_session, auto_commit=False) as mgr:
            await mgr.execute("INSERT INTO users VALUES (1, 'test')")

        # Should not auto-commit
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_manual_commit(self, mock_session):
        """Test manual commit."""
        async with DatabaseConnectionManager(mock_session, auto_commit=False) as mgr:
            await mgr.execute("INSERT INTO users VALUES (1, 'test')")
            await mgr.commit()

        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_manual_rollback(self, mock_session):
        """Test manual rollback."""
        async with DatabaseConnectionManager(mock_session, auto_commit=False) as mgr:
            await mgr.execute("INSERT INTO users VALUES (1, 'test')")
            await mgr.rollback()

        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_execution_failure(self, mock_session):
        """Test query execution failure triggers rollback."""
        mock_session.execute.side_effect = RuntimeError("Query failed")

        with pytest.raises(RuntimeError, match="Query failed"):
            async with DatabaseConnectionManager(mock_session) as mgr:
                await mgr.execute("SELECT * FROM users")

        # Should rollback on query error
        mock_session.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_commit_failure(self, mock_session):
        """Test commit failure triggers rollback."""
        mock_session.commit.side_effect = RuntimeError("Commit failed")

        with pytest.raises(RuntimeError, match="Commit failed"):
            async with DatabaseConnectionManager(mock_session, auto_commit=True) as mgr:
                await mgr.execute("INSERT INTO users VALUES (1, 'test')")

        # Should attempt rollback after commit failure
        mock_session.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_flush(self, mock_session):
        """Test flush operation."""
        async with DatabaseConnectionManager(mock_session) as mgr:
            await mgr.flush()

        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh(self, mock_session):
        """Test refresh operation."""
        instance = Mock()

        async with DatabaseConnectionManager(mock_session) as mgr:
            await mgr.refresh(instance)

        mock_session.refresh.assert_called_once_with(instance)

    @pytest.mark.asyncio
    async def test_operation_on_closed_connection(self, mock_session):
        """Test operations on closed connection raise error."""
        mgr = DatabaseConnectionManager(mock_session)
        await mgr.open()
        await mgr.close()

        with pytest.raises(RuntimeError, match="Connection is closed"):
            await mgr.execute("SELECT * FROM users")

    @pytest.mark.asyncio
    async def test_multiple_queries_in_transaction(self, mock_session):
        """Test multiple queries in one transaction."""
        async with DatabaseConnectionManager(mock_session, auto_commit=True) as mgr:
            await mgr.execute("INSERT INTO users VALUES (1, 'test1')")
            await mgr.execute("INSERT INTO users VALUES (2, 'test2')")
            await mgr.execute("INSERT INTO users VALUES (3, 'test3')")

        # Should execute all queries
        assert mock_session.execute.call_count == 3
        # Should commit once
        assert mock_session.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_query_metrics(self, mock_session):
        """Test that query metrics are tracked."""
        async with DatabaseConnectionManager(mock_session) as mgr:
            await mgr.execute("SELECT * FROM users")
            await mgr.execute("SELECT * FROM posts")
            assert mgr._queries_executed == 2

    @pytest.mark.asyncio
    async def test_pending_transaction_rollback_on_close(self, mock_session):
        """Test pending transaction is rolled back on close."""
        mgr = DatabaseConnectionManager(mock_session, auto_commit=False)
        await mgr.open()
        await mgr.execute("INSERT INTO users VALUES (1, 'test')")
        await mgr.close()

        # Should rollback pending transaction
        mock_session.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_from_pool(self, mock_session):
        """Test creating manager from connection pool."""
        # Mock the context manager
        session_cm = AsyncMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock()

        with patch(
            "kagami.core.database.async_connection.get_async_db_session"
        ) as mock_get_session:
            mock_get_session.return_value = session_cm

            mgr = await DatabaseConnectionManager.from_pool()
            assert mgr.session is mock_session
            session_cm.__aenter__.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_connections(self, mock_session):
        """Test multiple concurrent connections."""
        sessions = [Mock() for _ in range(5)]
        for s in sessions:
            s.execute = AsyncMock()
            s.commit = AsyncMock()
            s.rollback = AsyncMock()
            s.close = AsyncMock()

        async def use_connection(session):
            async with DatabaseConnectionManager(session) as mgr:
                await mgr.execute("SELECT * FROM users")

        # Run concurrently
        await asyncio.gather(*[use_connection(s) for s in sessions])

        # All should execute and commit
        for s in sessions:
            s.execute.assert_called_once()
            s.commit.assert_called_once()


class TestRedisConnectionManager:
    """Test RedisConnectionManager class."""

    @pytest.mark.asyncio
    async def test_basic_lifecycle(self, mock_redis):
        """Test basic Redis connection lifecycle."""
        async with RedisConnectionManager(mock_redis) as mgr:
            assert mgr.redis is mock_redis
            assert not mgr.closed

        assert mgr.closed

    @pytest.mark.asyncio
    async def test_get_operation(self, mock_redis):
        """Test Redis GET operation."""
        mock_redis.get.return_value = b"value"

        async with RedisConnectionManager(mock_redis) as mgr:
            result = await mgr.get("key")
            assert result == b"value"

        mock_redis.get.assert_called_once_with("key")

    @pytest.mark.asyncio
    async def test_set_operation(self, mock_redis):
        """Test Redis SET operation."""
        mock_redis.set.return_value = True

        async with RedisConnectionManager(mock_redis) as mgr:
            result = await mgr.set("key", "value")
            assert result is True

        mock_redis.set.assert_called_once_with("key", "value", ex=None, px=None)

    @pytest.mark.asyncio
    async def test_set_with_expiration(self, mock_redis):
        """Test Redis SET with expiration."""
        async with RedisConnectionManager(mock_redis) as mgr:
            await mgr.set("key", "value", ex=300)

        mock_redis.set.assert_called_once_with("key", "value", ex=300, px=None)

    @pytest.mark.asyncio
    async def test_delete_operation(self, mock_redis):
        """Test Redis DELETE operation."""
        mock_redis.delete.return_value = 2

        async with RedisConnectionManager(mock_redis) as mgr:
            result = await mgr.delete("key1", "key2")
            assert result == 2

        mock_redis.delete.assert_called_once_with("key1", "key2")

    @pytest.mark.asyncio
    async def test_exists_operation(self, mock_redis):
        """Test Redis EXISTS operation."""
        mock_redis.exists.return_value = 1

        async with RedisConnectionManager(mock_redis) as mgr:
            result = await mgr.exists("key")
            assert result == 1

        mock_redis.exists.assert_called_once_with("key")

    @pytest.mark.asyncio
    async def test_expire_operation(self, mock_redis):
        """Test Redis EXPIRE operation."""
        mock_redis.expire.return_value = True

        async with RedisConnectionManager(mock_redis) as mgr:
            result = await mgr.expire("key", 300)
            assert result is True

        mock_redis.expire.assert_called_once_with("key", 300)

    @pytest.mark.asyncio
    async def test_pipeline_operations(self, mock_redis):
        """Test Redis pipeline operations."""
        mock_pipeline = Mock()
        mock_pipeline.set = Mock()
        mock_pipeline.get = Mock()
        mock_pipeline.execute = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipeline

        async with RedisConnectionManager(mock_redis) as mgr:
            pipe = mgr.pipeline()
            pipe.set("key1", "value1")
            pipe.set("key2", "value2")
            await pipe.execute()

        mock_redis.pipeline.assert_called_once()
        mock_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_cleanup(self, mock_redis):
        """Test pipelines are cleaned up."""
        mock_pipeline = Mock()
        mock_pipeline.reset = Mock()
        mock_redis.pipeline.return_value = mock_pipeline

        async with RedisConnectionManager(mock_redis) as mgr:
            pipe = mgr.pipeline()

        # Pipeline should be reset on cleanup
        mock_pipeline.reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_operations_on_closed_connection(self, mock_redis):
        """Test operations on closed connection raise error."""
        mgr = RedisConnectionManager(mock_redis)
        await mgr.open()
        await mgr.close()

        with pytest.raises(RuntimeError, match="Connection is closed"):
            await mgr.get("key")

    @pytest.mark.asyncio
    async def test_query_metrics(self, mock_redis):
        """Test that query metrics are tracked."""
        async with RedisConnectionManager(mock_redis) as mgr:
            await mgr.get("key1")
            await mgr.set("key2", "value")
            await mgr.delete("key3")
            assert mgr._queries_executed == 3

    @pytest.mark.asyncio
    async def test_concurrent_redis_operations(self, mock_redis):
        """Test concurrent Redis operations."""
        redis_clients = [Mock() for _ in range(5)]
        for r in redis_clients:
            r.get = AsyncMock(return_value=b"value")
            r.set = AsyncMock(return_value=True)

        async def use_redis(redis):
            async with RedisConnectionManager(redis) as mgr:
                await mgr.set("key", "value")
                await mgr.get("key")

        # Run concurrently
        await asyncio.gather(*[use_redis(r) for r in redis_clients])

        # All should execute
        for r in redis_clients:
            r.set.assert_called_once()
            r.get.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="TODO: Implement get_redis_client in factory.py - see backlog")
    async def test_from_pool(self, mock_redis):
        """Test creating manager from Redis pool.

        FUTURE: Implement get_redis_client convenience function in factory.py
        Currently only RedisClientFactory.get_client exists (tracked in backlog)
        """
        pass


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_get_database_connection(self):
        """Test get_database_connection function."""
        mock_mgr = Mock()

        with patch.object(
            DatabaseConnectionManager, "from_pool", return_value=mock_mgr
        ) as mock_from_pool:
            result = await get_database_connection(auto_commit=True)
            assert result is mock_mgr
            mock_from_pool.assert_called_once_with(auto_commit=True)

    @pytest.mark.asyncio
    async def test_get_redis_connection(self):
        """Test get_redis_connection function."""
        mock_mgr = Mock()

        with patch.object(
            RedisConnectionManager, "from_pool", return_value=mock_mgr
        ) as mock_from_pool:
            result = await get_redis_connection()
            assert result is mock_mgr
            mock_from_pool.assert_called_once()


class TestConnectionTimeout:
    """Test connection timeout handling."""

    @pytest.mark.asyncio
    async def test_connection_timeout(self):
        """Test connection operation timeout."""
        # Create a connection that hangs
        conn = Mock()

        async def hang():
            await asyncio.sleep(10)

        conn.close = hang

        mgr = ConnectionManager(conn)
        await mgr.open()

        # Close should timeout eventually (but we won't wait that long)
        # This is more of a smoke test
        task = asyncio.create_task(mgr.close())
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestResourceCleanupGuarantees:
    """Test that cleanup is guaranteed even in edge cases."""

    @pytest.mark.asyncio
    async def test_cleanup_on_keyboard_interrupt(self, mock_connection):
        """Test cleanup happens on KeyboardInterrupt."""
        tracker = get_resource_tracker()

        try:
            async with ConnectionManager(mock_connection) as mgr:
                raise KeyboardInterrupt()
        except KeyboardInterrupt:
            pass

        # Should still cleanup
        resources = tracker.get_resources("connection")
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_cleanup_on_system_exit(self, mock_connection):
        """Test cleanup happens on SystemExit."""
        tracker = get_resource_tracker()

        try:
            async with ConnectionManager(mock_connection) as mgr:
                raise SystemExit(1)
        except SystemExit:
            pass

        # Should still cleanup
        resources = tracker.get_resources("connection")
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_cleanup_with_multiple_errors(self, mock_session):
        """Test cleanup works even with multiple errors."""
        mock_session.execute.side_effect = RuntimeError("Execute failed")
        mock_session.rollback.side_effect = RuntimeError("Rollback failed")

        # Should not hang or leak resources
        with pytest.raises(RuntimeError):
            async with DatabaseConnectionManager(mock_session) as mgr:
                await mgr.execute("SELECT * FROM users")

        # Verify cleanup attempt was made
        mock_session.rollback.assert_called()
