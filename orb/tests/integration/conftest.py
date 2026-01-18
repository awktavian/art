"""Integration test fixtures for real service connections.

This conftest provides fixtures for integration tests that need real
CockroachDB, Redis, Weaviate, and etcd services.

To run integration tests:
    1. Start services: make test-infra-up
    2. Run tests: make test-integration
    3. Stop services: make test-infra-down
"""

import asyncio
import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio

# Mark all tests in this directory as integration tests
pytestmark = pytest.mark.integration


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "mock_services: mark test to run with mocked services (no real service check)"
    )


# ==============================================================================
# Service Availability Checks
# ==============================================================================


def _check_service_port(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a service port is open and accepting connections."""
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


@pytest.fixture(scope="session")
def _services_available():
    """Check which services are available (internal helper).

    Returns tuple (missing_services_list, all_available_bool).
    """
    required_services = {
        "CockroachDB": ("localhost", 26257),
        "Redis": ("localhost", 6379),
        "Weaviate": ("localhost", 8085),  # Production port
        "etcd": ("localhost", 2379),
    }

    missing_services = []
    for name, (host, port) in required_services.items():
        if not _check_service_port(host, port):
            missing_services.append(f"{name} ({host}:{port})")

    if not missing_services:
        # Set environment flag indicating services are available
        os.environ["KAGAMI_USE_REAL_SERVICES"] = "1"
        os.environ["KAGAMI_TEST_DISABLE_REDIS"] = "0"
        os.environ["KAGAMI_DISABLE_ETCD"] = "0"

    return missing_services, len(missing_services) == 0


@pytest.fixture(autouse=True)
def check_services_available(request, _services_available):
    """Verify required services are available before running tests.

    Tests marked with @pytest.mark.mock_services will skip this check,
    allowing mocked integration tests to run without real services.
    """
    # Skip service check for tests marked with mock_services
    if request.node.get_closest_marker("mock_services"):
        return

    # Skip service check for test classes marked with mock_services
    if hasattr(request, "cls") and request.cls is not None:
        for marker in getattr(request.cls, "pytestmark", []):
            if marker.name == "mock_services":
                return

    missing_services, all_available = _services_available

    if not all_available:
        pytest.skip(
            f"Integration test services not available: {', '.join(missing_services)}. "
            "Run 'make test-infra-up' to start services."
        )


# ==============================================================================
# Database Fixtures
# ==============================================================================


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator:
    """Provide a database session connected to test CockroachDB instance.

    Creates tables and cleans up after each test.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    from kagami.core.database.models import Base

    # Use test database URL
    db_url = "postgresql+asyncpg://root@localhost:26257/kagami_test?sslmode=disable"

    engine = create_async_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Provide session
    async with async_session_factory() as session:
        yield session

    # Cleanup: Drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# ==============================================================================
# Redis Fixtures
# ==============================================================================


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator:
    """Provide a Redis client connected to test Redis instance.

    Flushes the test database before and after each test.
    """
    import redis.asyncio as aioredis

    client = aioredis.from_url(
        "redis://localhost:6379/15",  # Use database 15 for testing
        encoding="utf-8",
        decode_responses=True,
    )

    # Flush test database before test
    await client.flushdb()

    yield client

    # Flush test database after test
    await client.flushdb()
    await client.aclose()


# ==============================================================================
# etcd Fixtures
# ==============================================================================


@pytest_asyncio.fixture
async def etcd_client() -> AsyncGenerator:
    """Provide an etcd client connected to test etcd instance.

    Cleans up test keys before and after each test.
    """
    try:
        from kagami.core.consensus.etcd_client import get_etcd_client
    except ImportError:
        pytest.skip("etcd client not available")

    client = get_etcd_client()

    # Initialize connection
    try:
        await client.initialize()
    except Exception as e:
        pytest.skip(f"Could not connect to etcd: {e}")

    # Clean up test keys before test
    test_prefix = b"/kagami/test/"
    await client.delete_prefix(test_prefix)

    yield client

    # Clean up test keys after test
    await client.delete_prefix(test_prefix)


# ==============================================================================
# Weaviate Fixtures
# ==============================================================================


@pytest_asyncio.fixture
async def weaviate_client() -> AsyncGenerator:
    """Provide a Weaviate client connected to test Weaviate instance.

    Creates test schema and cleans up after each test.
    """
    try:
        import weaviate
        import weaviate.classes as wvc
    except ImportError:
        pytest.skip("weaviate-client not available")

    # Connect to test Weaviate instance
    client = weaviate.connect_to_local(
        host="localhost",
        port=8081,
        grpc_port=50051,
    )

    try:
        # Verify connection
        if not client.is_ready():
            pytest.skip("Weaviate not ready")

        yield client

    finally:
        # Cleanup: Delete all test collections
        try:
            for collection in client.collections.list_all():
                if collection.startswith("Test"):
                    client.collections.delete(collection)
        except Exception:
            pass

        client.close()


# ==============================================================================
# Storage Repository Fixtures
# ==============================================================================


@pytest_asyncio.fixture
async def receipt_repository(db_session, redis_client, etcd_client):
    """Provide a ReceiptRepository with all storage layers connected."""
    from kagami.core.storage.receipt_repository import ReceiptRepository

    repo = ReceiptRepository(
        db_session=db_session,
        redis_client=redis_client,
        etcd_client=etcd_client,
    )

    return repo


@pytest_asyncio.fixture
async def user_repository(db_session, redis_client):
    """Provide a UserRepository with database and cache."""
    from kagami.core.storage.user_repository import UserRepository

    repo = UserRepository(
        db_session=db_session,
        redis_client=redis_client,
    )

    return repo


# ==============================================================================
# Service Integration Fixtures
# ==============================================================================


@pytest_asyncio.fixture
async def integration_services(db_session, redis_client, etcd_client, weaviate_client):
    """Provide all integrated services as a bundle.

    Use this when you need full system integration with all services.
    """
    return {
        "db": db_session,
        "redis": redis_client,
        "etcd": etcd_client,
        "weaviate": weaviate_client,
    }


# ==============================================================================
# Cleanup Fixtures
# ==============================================================================


@pytest.fixture(autouse=True)
def reset_environment_after_test(monkeypatch: Any) -> None:
    """Reset critical environment variables after each test.

    Ensures test isolation even when tests modify environment.
    """
    # Store original values
    original_env = {
        "KAGAMI_USE_REAL_SERVICES": os.environ.get("KAGAMI_USE_REAL_SERVICES"),
        "KAGAMI_TEST_MODE": os.environ.get("KAGAMI_TEST_MODE"),
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "REDIS_URL": os.environ.get("REDIS_URL"),
    }

    yield

    # Restore original values
    for key, value in original_env.items():
        if value is not None:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)
