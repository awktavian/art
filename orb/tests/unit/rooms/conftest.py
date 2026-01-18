"""Fixtures for rooms unit tests.

Ensures proper cleanup of Redis connections and async resources.
"""

import atexit
import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio

# Disable world model sync for unit tests to prevent hanging background tasks
os.environ["ENABLE_WORLD_MODEL_SYNC"] = "0"

# Remove the atexit handler that causes hanging in pytest
try:
    from kagami.core.caching.redis.factory import _safe_close_all

    atexit.unregister(_safe_close_all)
except (ImportError, AttributeError, ValueError):
    pass


def pytest_configure(config: Any) -> None:
    """Configure pytest for rooms tests."""
    # Use thread-based timeout to avoid asyncio event loop issues during shutdown
    config.option.timeout_method = "thread"


def pytest_sessionfinish(session: Any, exitstatus: Any) -> None:
    """Force cleanup of asyncio resources at session end.

    The RedisClientFactory atexit handler can cause pytest to hang during
    shutdown. We handle cleanup explicitly here before pytest tries to
    close the event loop.
    """
    import sys

    # Force close all Redis clients without using asyncio.run
    try:
        from kagami.core.caching.redis import RedisClientFactory

        RedisClientFactory._clients.clear()
    except Exception:
        pass

    # Cancel any remaining tasks
    try:
        import asyncio

        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
    except Exception:
        pass


@pytest.fixture(scope="function", autouse=True)
def mock_event_bus(monkeypatch) -> Generator[None, None, None]:
    """Mock the event bus to prevent background task creation.

    The state_service creates fire-and-forget tasks using asyncio.create_task
    to publish events. These keep the event loop alive during test shutdown.
    """

    # Mock get_unified_bus to return a no-op bus
    class MockBus:
        async def publish(self, topic: str, data: dict) -> None:
            pass

    try:
        import kagami.core.events

        monkeypatch.setattr(kagami.core.events, "get_unified_bus", lambda: MockBus())
    except ImportError:
        pass

    yield


@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_async_tasks() -> AsyncGenerator[None, None]:
    """Cancel all pending async tasks after each test.

    The state_service creates fire-and-forget tasks for world model sync
    and event bus publishing. These tasks keep the event loop alive and
    cause tests to hang. We cancel them after each test.
    """
    yield

    # Cancel all pending tasks except the current one
    try:
        current_task = asyncio.current_task()
        tasks = [t for t in asyncio.all_tasks() if not t.done() and t is not current_task]
        for task in tasks:
            task.cancel()
        # Give tasks a moment to cancel
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_redis() -> AsyncGenerator[None, None]:
    """Clean up Redis connections after each test.

    This prevents hanging by ensuring all async Redis clients are properly
    closed after each test completes.
    """
    yield

    # Close all Redis clients
    from kagami.core.caching.redis import RedisClientFactory

    try:
        await RedisClientFactory.aclose_all()
    except Exception:
        # Swallow errors during cleanup (test mode)
        pass


@pytest.fixture(scope="function", autouse=True)
def cleanup_encryption_provider() -> Generator[None, None, None]:
    """Reset encryption provider cache between tests."""
    yield

    # Reset cached encryption provider
    try:
        import kagami.core.rooms.state_service as svc

        svc._ENCRYPTION_PROVIDER = None
    except Exception:
        pass


@pytest.fixture(scope="function", autouse=True)
def cleanup_room_locks() -> Generator[None, None, None]:
    """Clear room locks between tests."""
    yield

    try:
        import kagami.core.rooms.state_service as svc

        svc._LOCAL_ROOM_LOCKS.clear()
    except Exception:
        pass
