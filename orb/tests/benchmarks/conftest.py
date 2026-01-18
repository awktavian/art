"""Benchmark fixtures for performance testing.

Created: December 15, 2025
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio


@pytest.fixture
def benchmark_cache_dir(tmp_path: Path) -> Path:
    """Create temporary cache directory for benchmarks."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@pytest_asyncio.fixture
async def mock_redis_client():
    """Mock Redis client for benchmarking.

    Simulates Redis operations with in-memory storage and realistic latencies.
    """
    storage: dict[str, tuple[Any, float]] = {}

    class MockRedis:
        def __init__(self):
            self.storage = storage

        async def get(self, key: str) -> bytes | None:
            """Simulate Redis GET with 0.5ms latency."""
            await asyncio.sleep(0.0005)  # 0.5ms
            if key in self.storage:
                value, expiry = self.storage[key]
                if expiry == 0 or expiry > asyncio.get_event_loop().time():
                    return value
            return None

        async def set(self, key: str, value: bytes, ex: int | None = None) -> bool:
            """Simulate Redis SET with 0.5ms latency."""
            await asyncio.sleep(0.0005)  # 0.5ms
            expiry = 0
            if ex:
                expiry = asyncio.get_event_loop().time() + ex  # type: ignore[assignment]
            self.storage[key] = (value, expiry)
            return True

        async def delete(self, key: str) -> int:
            """Simulate Redis DEL with 0.5ms latency."""
            await asyncio.sleep(0.0005)  # 0.5ms
            if key in self.storage:
                del self.storage[key]
                return 1
            return 0

        async def exists(self, key: str) -> int:
            """Check if key exists."""
            await asyncio.sleep(0.0003)  # 0.3ms
            return 1 if key in self.storage else 0

        async def keys(self, pattern: str = "*") -> list[str]:
            """Get keys matching pattern."""
            await asyncio.sleep(0.001)  # 1ms
            return list(self.storage.keys())

    return MockRedis()


@pytest_asyncio.fixture
async def mock_db_session():
    """Mock database session for benchmarking.

    Simulates database operations with realistic latencies:
    - SELECT: 5-15ms
    - INSERT: 10-20ms
    - UPDATE: 10-20ms
    """
    storage: dict[str, Any] = {}

    class MockSession:
        def __init__(self):
            self.storage = storage

        async def execute(self, stmt: Any) -> None:
            """Simulate query execution."""
            await asyncio.sleep(0.010)  # 10ms average

            class MockResult:
                def scalars(self):
                    class MockScalars:
                        def all(self):
                            return list(storage.values())

                        def first(self):
                            return next(iter(storage.values())) if storage else None

                    return MockScalars()

            return MockResult()

        async def add(self, obj: Any) -> Any:
            """Add object to session."""
            await asyncio.sleep(0.001)  # 1ms

        async def commit(self):
            """Commit transaction."""
            await asyncio.sleep(0.015)  # 15ms

        async def rollback(self):
            """Rollback transaction."""
            await asyncio.sleep(0.005)  # 5ms

        async def flush(self):
            """Flush changes."""
            await asyncio.sleep(0.008)  # 8ms

    return MockSession()


@pytest.fixture
def sample_receipt_data() -> dict[str, Any]:
    """Sample receipt data for benchmarking."""
    return {
        "correlation_id": "bench-test-001",
        "action_type": "PLAN",
        "colony": "beacon",
        "phase": "PLAN",
        "timestamp": 1734278400.0,
        "duration_ms": 150.0,
        "success": True,
        "metadata": {
            "model": "claude-sonnet-4.5",
            "tokens": 1000,
            "cost": 0.015,
        },
    }


@pytest.fixture
def sample_model_config() -> dict[str, Any]:
    """Sample model configuration for benchmarking."""
    return {
        "device": "cpu",
        "dtype": "float32",
        "quantization": None,
        "revision": "main",
    }


@pytest_asyncio.fixture
async def response_cache(mock_redis_client: Any) -> Any:
    """Create ResponseCache instance for benchmarking."""
    from kagami.core.caching.response_cache import CacheConfig, ResponseCache

    config = CacheConfig(
        ttl=300.0,
        max_size=1000,
        enable_redis=True,
    )

    cache = ResponseCache(config=config, namespace="benchmark")
    cache._redis_client = mock_redis_client

    return cache


@pytest_asyncio.fixture
async def model_cache(benchmark_cache_dir: Any) -> Any:
    """Create ModelCache instance for benchmarking."""
    from kagami.core.caching.unified_model_cache import ModelCache

    cache = ModelCache(
        cache_dir=benchmark_cache_dir,
        max_size_gb=1.0,
        max_models=10,
    )

    return cache


@pytest_asyncio.fixture
async def receipt_repository(mock_db_session: Any, mock_redis_client: Any) -> Any:
    """Create ReceiptRepository instance for benchmarking."""
    from kagami.core.storage.receipt_repository import ReceiptRepository

    repo = ReceiptRepository(
        db_session=mock_db_session,
        redis_client=mock_redis_client,
        etcd_client=None,
    )

    return repo


@pytest.fixture
def benchmark_stats():
    """Utility to calculate benchmark statistics."""

    def calculate(times: list[float]) -> dict[str, float]:
        """Calculate statistics from timing data.

        Args:
            times: List of timing measurements in seconds

        Returns:
            Statistics dictionary with mean, median, p95, p99
        """
        import statistics

        sorted_times = sorted(times)
        n = len(sorted_times)

        return {
            "mean": statistics.mean(sorted_times),
            "median": statistics.median(sorted_times),
            "stdev": statistics.stdev(sorted_times) if n > 1 else 0.0,
            "min": min(sorted_times),
            "max": max(sorted_times),
            "p50": sorted_times[int(n * 0.50)],
            "p95": sorted_times[int(n * 0.95)],
            "p99": sorted_times[int(n * 0.99)],
            "count": n,
        }

    return calculate
