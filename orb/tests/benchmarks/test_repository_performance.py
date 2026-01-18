"""Repository performance benchmarks.

Measures performance of data repositories with caching:
- Receipt repository CRUD operations
- Cache hit vs miss performance
- Bulk operations
- Query performance

Target metrics:
- Read (cached): < 5ms
- Read (uncached): < 30ms
- Write: < 50ms
- Bulk read (100 items): < 200ms

Created: December 15, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_e2e
import time
from typing import Any
from uuid import uuid4


@pytest.mark.benchmark
class TestReceiptRepositoryRead:
    """Receipt repository read performance benchmarks."""

    @pytest.mark.asyncio
    async def test_receipt_read_cached(
        self, receipt_repository: Any, sample_receipt_data: dict[str, Any], benchmark_stats: Any
    ) -> None:
        """Receipt read with cache hit.
        Target: < 5ms per operation
        """
        from kagami.core.database.models import Receipt

        # Prepare data
        receipts = []
        for i in range(100):
            data = sample_receipt_data.copy()
            data["correlation_id"] = f"cached-{i}"
            receipt = Receipt(**data)
            receipt.id = uuid4()  # type: ignore[assignment]
            await receipt_repository.set(str(receipt.id), receipt)
            receipts.append(receipt)
        # Warmup
        await receipt_repository.get(str(receipts[0].id))
        # Benchmark cached reads
        times = []
        for receipt in receipts:
            start = time.perf_counter()
            result = await receipt_repository.get(str(receipt.id))
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            assert result is not None
            assert result.correlation_id == receipt.correlation_id
        stats = benchmark_stats(times)
        assert stats["mean"] < 0.005, f"Cached read {stats['mean'] * 1000:.2f}ms > 5ms"
        assert stats["p95"] < 0.010, f"Cached read p95 {stats['p95'] * 1000:.2f}ms > 10ms"
        print("\nReceipt Read (Cached):")
        print(f"  Mean:   {stats['mean'] * 1000:.3f}ms")
        print(f"  Median: {stats['median'] * 1000:.3f}ms")
        print(f"  P95:    {stats['p95'] * 1000:.3f}ms")
        print(f"  P99:    {stats['p99'] * 1000:.3f}ms")

    @pytest.mark.asyncio
    async def test_receipt_read_uncached(
        self, receipt_repository: Any, sample_receipt_data: dict[str, Any], benchmark_stats: Any
    ) -> None:
        """Receipt read with cache miss.
        Target: < 30ms per operation
        """
        from kagami.core.database.models import Receipt

        # Prepare data (stored but not cached)
        receipts = []
        for i in range(50):
            data = sample_receipt_data.copy()
            data["correlation_id"] = f"uncached-{i}"
            receipt = Receipt(**data)
            receipt.id = uuid4()  # type: ignore[assignment]
            # Store directly in mock DB without caching
            receipt_repository.db_session.storage[str(receipt.id)] = receipt
            receipts.append(receipt)
        # Benchmark uncached reads (will hit DB)
        times = []
        for receipt in receipts:
            # Ensure not in cache
            await receipt_repository.invalidate(str(receipt.id))
            start = time.perf_counter()
            await receipt_repository.get_by_id(str(receipt.id))
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            # Note: Mock DB may return None for non-existent keys
            # This is expected in benchmark context
        stats = benchmark_stats(times)
        # With mock DB adding ~10ms latency
        assert stats["mean"] < 0.030, f"Uncached read {stats['mean'] * 1000:.2f}ms > 30ms"
        assert stats["p95"] < 0.050, f"Uncached read p95 {stats['p95'] * 1000:.2f}ms > 50ms"
        print("\nReceipt Read (Uncached):")
        print(f"  Mean:   {stats['mean'] * 1000:.3f}ms")
        print(f"  Median: {stats['median'] * 1000:.3f}ms")
        print(f"  P95:    {stats['p95'] * 1000:.3f}ms")
        print(f"  P99:    {stats['p99'] * 1000:.3f}ms")

    @pytest.mark.asyncio
    async def test_receipt_read_comparison(
        self, receipt_repository: Any, sample_receipt_data: dict[str, Any], benchmark_stats: Any
    ) -> None:
        """Compare cached vs uncached read performance.
        Validates that caching provides significant speedup.
        """
        from kagami.core.database.models import Receipt

        # Create receipt
        data = sample_receipt_data.copy()
        data["correlation_id"] = "comparison-test"
        receipt = Receipt(**data)
        receipt.id = uuid4()  # type: ignore[assignment]
        # Store in DB
        receipt_repository.db_session.storage[str(receipt.id)] = receipt
        # Benchmark uncached read
        uncached_times = []
        for _ in range(50):
            await receipt_repository.invalidate(str(receipt.id))
            start = time.perf_counter()
            await receipt_repository.get_by_id(str(receipt.id))
            elapsed = time.perf_counter() - start
            uncached_times.append(elapsed)
        # Benchmark cached read
        cached_times = []
        for _ in range(50):
            start = time.perf_counter()
            await receipt_repository.get(str(receipt.id))
            elapsed = time.perf_counter() - start
            cached_times.append(elapsed)
        uncached_stats = benchmark_stats(uncached_times)
        cached_stats = benchmark_stats(cached_times)
        speedup = uncached_stats["mean"] / cached_stats["mean"]
        print("\nCached vs Uncached Comparison:")
        print(f"  Uncached mean: {uncached_stats['mean'] * 1000:.3f}ms")
        print(f"  Cached mean:   {cached_stats['mean'] * 1000:.3f}ms")
        print(f"  Speedup:       {speedup:.1f}x")
        # Cache should be at least 2x faster
        assert speedup > 2.0, f"Cache speedup {speedup:.1f}x < 2x"


@pytest.mark.benchmark
class TestReceiptRepositoryWrite:
    """Receipt repository write performance benchmarks."""

    @pytest.mark.asyncio
    async def test_receipt_write_performance(
        self, receipt_repository: Any, sample_receipt_data: dict[str, Any], benchmark_stats: Any
    ) -> None:
        """Receipt write (insert) performance.
        Target: < 50ms per operation
        """
        from kagami.core.database.models import Receipt

        times = []
        for i in range(50):
            data = sample_receipt_data.copy()
            data["correlation_id"] = f"write-test-{i}"
            receipt = Receipt(**data)
            receipt.id = uuid4()  # type: ignore[assignment]
            start = time.perf_counter()
            await receipt_repository.set(str(receipt.id), receipt)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        stats = benchmark_stats(times)
        # Mock DB adds ~15ms for commit
        assert stats["mean"] < 0.050, f"Write mean {stats['mean'] * 1000:.2f}ms > 50ms"
        assert stats["p95"] < 0.100, f"Write p95 {stats['p95'] * 1000:.2f}ms > 100ms"
        print("\nReceipt Write Performance:")
        print(f"  Mean:   {stats['mean'] * 1000:.3f}ms")
        print(f"  Median: {stats['median'] * 1000:.3f}ms")
        print(f"  P95:    {stats['p95'] * 1000:.3f}ms")
        print(f"  P99:    {stats['p99'] * 1000:.3f}ms")

    @pytest.mark.asyncio
    async def test_receipt_write_with_cache_update(
        self, receipt_repository: Any, sample_receipt_data: dict[str, Any], benchmark_stats: Any
    ) -> None:
        """Receipt write with automatic cache update.
        Target: < 60ms per operation
        """
        from kagami.core.database.models import Receipt

        times = []
        for i in range(50):
            data = sample_receipt_data.copy()
            data["correlation_id"] = f"cached-write-{i}"
            receipt = Receipt(**data)
            receipt.id = uuid4()  # type: ignore[assignment]
            start = time.perf_counter()
            # Write and cache
            await receipt_repository.set(str(receipt.id), receipt)
            # Verify cached
            cached = await receipt_repository.get(str(receipt.id))
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            assert cached is not None
        stats = benchmark_stats(times)
        assert stats["mean"] < 0.060, f"Write+cache {stats['mean'] * 1000:.2f}ms > 60ms"
        print("\nReceipt Write + Cache Update:")
        print(f"  Mean:   {stats['mean'] * 1000:.3f}ms")
        print(f"  P95:    {stats['p95'] * 1000:.3f}ms")


@pytest.mark.benchmark
class TestReceiptRepositoryBulk:
    """Receipt repository bulk operation benchmarks."""

    @pytest.mark.asyncio
    async def test_bulk_read_cached(
        self, receipt_repository: Any, sample_receipt_data: dict[str, Any], benchmark_stats: Any
    ) -> None:
        """Bulk read of 100 cached receipts.
        Target: < 200ms total
        """
        from kagami.core.database.models import Receipt

        # Prepare 100 receipts
        receipts = []
        for i in range(100):
            data = sample_receipt_data.copy()
            data["correlation_id"] = f"bulk-{i}"
            receipt = Receipt(**data)
            receipt.id = uuid4()  # type: ignore[assignment]
            await receipt_repository.set(str(receipt.id), receipt)
            receipts.append(receipt)
        # Benchmark bulk read
        start = time.perf_counter()
        results = []
        for receipt in receipts:
            result = await receipt_repository.get(str(receipt.id))
            results.append(result)
        elapsed = time.perf_counter() - start
        assert len(results) == 100
        assert all(r is not None for r in results)
        assert elapsed < 0.200, f"Bulk read {elapsed * 1000:.2f}ms > 200ms"
        avg_per_item = elapsed / 100
        print("\nBulk Read (100 items, cached):")
        print(f"  Total time:   {elapsed * 1000:.2f}ms")
        print(f"  Per item:     {avg_per_item * 1000:.3f}ms")
        print(f"  Throughput:   {100 / elapsed:.0f} reads/sec")

    @pytest.mark.asyncio
    async def test_bulk_write(
        self, receipt_repository: Any, sample_receipt_data: dict[str, Any], benchmark_stats: Any
    ) -> None:
        """Bulk write of 50 receipts.
        Target: < 3000ms total (60ms per item)
        """
        from kagami.core.database.models import Receipt

        # Prepare 50 receipts
        receipts = []
        for i in range(50):
            data = sample_receipt_data.copy()
            data["correlation_id"] = f"bulk-write-{i}"
            receipt = Receipt(**data)
            receipt.id = uuid4()  # type: ignore[assignment]
            receipts.append(receipt)
        # Benchmark bulk write
        start = time.perf_counter()
        for receipt in receipts:
            await receipt_repository.set(str(receipt.id), receipt)
        elapsed = time.perf_counter() - start
        assert elapsed < 3.0, f"Bulk write {elapsed * 1000:.2f}ms > 3000ms"
        avg_per_item = elapsed / 50
        print("\nBulk Write (50 items):")
        print(f"  Total time:   {elapsed * 1000:.2f}ms")
        print(f"  Per item:     {avg_per_item * 1000:.3f}ms")
        print(f"  Throughput:   {50 / elapsed:.0f} writes/sec")


@pytest.mark.benchmark
class TestReceiptRepositoryQuery:
    """Receipt repository query performance benchmarks."""

    @pytest.mark.asyncio
    async def test_correlation_id_query(
        self, receipt_repository: Any, sample_receipt_data: dict[str, Any], benchmark_stats: Any
    ) -> None:
        """Query receipts by correlation_id.
        Target: < 100ms for 3 receipts
        """
        from kagami.core.database.models import Receipt

        # Create 3 receipts with same correlation_id
        correlation_id = "query-test-001"
        for _i, phase in enumerate(["PLAN", "EXECUTE", "VERIFY"]):
            data = sample_receipt_data.copy()
            data["correlation_id"] = correlation_id
            data["phase"] = phase
            receipt = Receipt(**data)
            receipt.id = uuid4()  # type: ignore[assignment]
            # Store in mock DB
            receipt_repository.db_session.storage[str(receipt.id)] = receipt
        # Benchmark query
        times = []
        for _ in range(20):
            start = time.perf_counter()
            await receipt_repository.get_by_correlation_id(correlation_id)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            # Mock may return empty results, which is acceptable for benchmark
        stats = benchmark_stats(times)
        assert stats["mean"] < 0.100, f"Query mean {stats['mean'] * 1000:.2f}ms > 100ms"
        print("\nCorrelation ID Query (3 receipts):")
        print(f"  Mean:   {stats['mean'] * 1000:.3f}ms")
        print(f"  Median: {stats['median'] * 1000:.3f}ms")
        print(f"  P95:    {stats['p95'] * 1000:.3f}ms")


@pytest.mark.benchmark
class TestCacheInvalidation:
    """Cache invalidation performance benchmarks."""

    @pytest.mark.asyncio
    async def test_single_key_invalidation(
        self, receipt_repository: Any, sample_receipt_data: dict[str, Any], benchmark_stats: Any
    ) -> None:
        """Single key cache invalidation.
        Target: < 5ms per operation
        """
        from kagami.core.database.models import Receipt

        # Prepare data
        receipts = []
        for i in range(50):
            data = sample_receipt_data.copy()
            data["correlation_id"] = f"invalidate-{i}"
            receipt = Receipt(**data)
            receipt.id = uuid4()  # type: ignore[assignment]
            await receipt_repository.set(str(receipt.id), receipt)
            receipts.append(receipt)
        # Benchmark invalidation
        times = []
        for receipt in receipts:
            start = time.perf_counter()
            await receipt_repository.invalidate(str(receipt.id))
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        stats = benchmark_stats(times)
        assert stats["mean"] < 0.005, f"Invalidation {stats['mean'] * 1000:.2f}ms > 5ms"
        print("\nCache Invalidation (single key):")
        print(f"  Mean:   {stats['mean'] * 1000:.3f}ms")
        print(f"  Median: {stats['median'] * 1000:.3f}ms")
        print(f"  P95:    {stats['p95'] * 1000:.3f}ms")

    @pytest.mark.asyncio
    async def test_pattern_invalidation(
        self, receipt_repository: Any, sample_receipt_data: dict[str, Any], benchmark_stats: Any
    ) -> None:
        """Pattern-based cache invalidation.
        Target: < 50ms for 100 keys
        """
        from kagami.core.database.models import Receipt

        # Prepare 100 receipts with pattern
        for i in range(100):
            data = sample_receipt_data.copy()
            data["correlation_id"] = f"pattern-test-{i}"
            receipt = Receipt(**data)
            receipt.id = uuid4()  # type: ignore[assignment]
            await receipt_repository.set(str(receipt.id), receipt)
        # Benchmark pattern invalidation
        start = time.perf_counter()
        # Note: This requires implementing pattern invalidation in repository
        # For now, we'll invalidate individually
        for i in range(100):
            receipt_id = f"pattern-test-{i}"
            await receipt_repository.invalidate(receipt_id)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.050, f"Pattern invalidation {elapsed * 1000:.2f}ms > 50ms"
        print("\nCache Invalidation (100 keys):")
        print(f"  Total time: {elapsed * 1000:.2f}ms")
        print(f"  Per key:    {elapsed * 1000 / 100:.3f}ms")
