from __future__ import annotations

from typing import Any
import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.integration,
    pytest.mark.tier_integration,
]

"""Smoke tests for integration test infrastructure.

Quick validation that all services are accessible and functioning.
Run these first to verify docker-compose.test.yml setup.

Author: Forge (e₂) — Infrastructure Verification
"""


class TestInfrastructureHealth:
    """Verify all services are accessible and responsive."""

    @pytest.mark.asyncio
    async def test_cockroachdb_connection(self, db_session: Any) -> None:
        """Test CockroachDB is accessible and can execute queries."""

        from sqlalchemy import text

        result = await db_session.execute(text("SELECT 1 as test"))
        row = result.first()
        assert row is not None
        assert row.test == 1

    @pytest.mark.asyncio
    async def test_redis_connection(self, redis_client: Any) -> None:
        """Test Redis is accessible and can store/retrieve data."""
        # Set a test value
        await redis_client.set("smoke_test", "success")

        # Retrieve it
        value = await redis_client.get("smoke_test")
        assert value == "success"

        # Verify delete works
        await redis_client.delete("smoke_test")
        value = await redis_client.get("smoke_test")
        assert value is None

    @pytest.mark.asyncio
    async def test_etcd_connection(self, etcd_client: Any) -> None:
        """Test etcd is accessible and can store/retrieve data."""
        # Put a test value
        await etcd_client.put(b"/smoke/test", b"success")

        # Get it back
        value = await etcd_client.get(b"/smoke/test")
        assert value == b"success"

        # Verify delete works
        await etcd_client.delete(b"/smoke/test")
        value = await etcd_client.get(b"/smoke/test")
        assert value is None

    @pytest.mark.asyncio
    async def test_weaviate_connection(self, weaviate_client: Any) -> None:
        """Test Weaviate is accessible and ready."""
        # Verify client is ready
        assert weaviate_client.is_ready(), "Weaviate should be ready"

        # Verify we can list collections (even if empty)
        collections = weaviate_client.collections.list_all()
        assert isinstance(collections, dict)


class TestServicePerformance:
    """Quick performance checks for service responsiveness."""

    @pytest.mark.asyncio
    async def test_redis_latency(self, redis_client: Any) -> None:
        """Verify Redis has acceptable latency (<10ms per operation)."""
        import time

        iterations = 100
        start = time.perf_counter()

        for i in range(iterations):
            await redis_client.set(f"perf_test_{i}", f"value_{i}")

        duration = time.perf_counter() - start
        avg_latency_ms = (duration / iterations) * 1000

        assert avg_latency_ms < 10.0, f"Redis latency too high: {avg_latency_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_database_latency(self, db_session: Any) -> None:
        """Verify database has acceptable latency (<50ms per query)."""
        import time
        from sqlalchemy import text

        iterations = 100
        start = time.perf_counter()

        for _ in range(iterations):
            await db_session.execute(text("SELECT 1"))

        duration = time.perf_counter() - start
        avg_latency_ms = (duration / iterations) * 1000

        assert avg_latency_ms < 50.0, f"Database latency too high: {avg_latency_ms:.2f}ms"


class TestServiceIsolation:
    """Verify services are properly isolated between tests."""

    @pytest.mark.asyncio
    async def test_redis_isolation_part1(self, redis_client: Any) -> None:
        """First test: set a value that should not leak."""
        await redis_client.set("isolation_test", "part1")
        value = await redis_client.get("isolation_test")
        assert value == "part1"

    @pytest.mark.asyncio
    async def test_redis_isolation_part2(self, redis_client: Any) -> None:
        """Second test: verify previous test's data is cleaned up."""
        # Fixture should have flushed the database
        value = await redis_client.get("isolation_test")
        assert value is None, "Redis data leaked between tests"

    @pytest.mark.asyncio
    async def test_etcd_isolation_part1(self, etcd_client: Any) -> None:
        """First test: set a value that should not leak."""
        await etcd_client.put(b"/isolation/test", b"part1")
        value = await etcd_client.get(b"/isolation/test")
        assert value == b"part1"

    @pytest.mark.asyncio
    async def test_etcd_isolation_part2(self, etcd_client: Any) -> None:
        """Second test: verify previous test's data is cleaned up."""
        # Fixture should have cleaned up test keys
        value = await etcd_client.get(b"/isolation/test")
        assert value is None, "etcd data leaked between tests"
