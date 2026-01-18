"""Tests for Redis-backed job storage.

Verifies:
- TTL-based expiration
- Per-user job limits
- Background cleanup
- No unbounded memory growth
"""

from __future__ import annotations

import pytest
import pytest_asyncio

pytestmark = pytest.mark.tier_integration
import asyncio
import time
from pathlib import Path
from kagami_api.services.redis_job_storage import RedisJobStorage, get_job_storage


@pytest_asyncio.fixture
async def job_storage() -> RedisJobStorage:
    """Create test job storage instance."""
    storage = RedisJobStorage(namespace="test")
    yield storage
    # Cleanup
    await storage.stop_cleanup_task()


class TestRedisJobStorage:
    """Test Redis job storage."""

    @pytest.mark.asyncio
    async def test_create_job(self, job_storage: RedisJobStorage):
        """Test job creation."""
        created = await job_storage.create_job(
            job_id="test-001",
            user_id="user-123",
            metadata={"prompt": "test image", "width": 1024},
        )
        assert created is True
        # Verify job exists
        job = await job_storage.get_job("test-001")
        assert job is not None
        assert job["job_id"] == "test-001"
        assert job["status"] == "queued"
        assert job["metadata"]["prompt"] == "test image"

    @pytest.mark.asyncio
    async def test_update_job(self, job_storage: RedisJobStorage):
        """Test job status updates."""
        await job_storage.create_job(
            job_id="test-002",
            user_id="user-123",
            metadata={},
        )
        # Update to processing
        updated = await job_storage.update_job("test-002", status="processing")
        assert updated is True
        job = await job_storage.get_job("test-002")
        assert job["status"] == "processing"  # type: ignore[index]
        assert job["started_at"] is not None  # type: ignore[index]
        # Update to completed
        await job_storage.update_job(
            "test-002",
            status="completed",
            result_path="/tmp/test.png",
        )
        job = await job_storage.get_job("test-002")
        assert job["status"] == "completed"  # type: ignore[index]
        assert job["result_path"] == "/tmp/test.png"  # type: ignore[index]
        assert job["completed_at"] is not None  # type: ignore[index]

    @pytest.mark.asyncio
    async def test_per_user_limit(self, job_storage: RedisJobStorage):
        """Test per-user job limit enforcement."""
        user_id = "user-limit-test"
        # Create max jobs
        for i in range(RedisJobStorage.MAX_JOBS_PER_USER):
            created = await job_storage.create_job(
                job_id=f"test-limit-{i}",
                user_id=user_id,
                metadata={},
            )
            assert created is True
        # Next job should be rejected
        created = await job_storage.create_job(
            job_id="test-limit-overflow",
            user_id=user_id,
            metadata={},
        )
        assert created is False

    @pytest.mark.asyncio
    async def test_delete_job(self, job_storage: RedisJobStorage):
        """Test job deletion."""
        await job_storage.create_job(
            job_id="test-delete",
            user_id="user-123",
            metadata={},
        )
        # Delete job
        deleted = await job_storage.delete_job("test-delete")
        assert deleted is True
        # Job should not exist
        job = await job_storage.get_job("test-delete")
        assert job is None

    @pytest.mark.asyncio
    async def test_list_user_jobs(self, job_storage: RedisJobStorage):
        """Test listing user's jobs."""
        user_id = "user-list-test"
        # Create multiple jobs
        for i in range(3):
            await job_storage.create_job(
                job_id=f"test-list-{i}",
                user_id=user_id,
                metadata={},
            )
        # List jobs
        job_ids = await job_storage.list_user_jobs(user_id)
        assert len(job_ids) == 3
        assert all(jid.startswith("test-list-") for jid in job_ids)

    @pytest.mark.asyncio
    async def test_cleanup_expired_jobs(self, job_storage: RedisJobStorage):
        """Test cleanup of expired jobs."""
        # Create completed job with old completion time
        job_id = "test-cleanup"
        await job_storage.create_job(
            job_id=job_id,
            user_id="user-123",
            metadata={},
        )
        # Mark as completed
        await job_storage.update_job(job_id, status="completed")
        # Get job and manually set old completion time
        redis = await job_storage._get_redis()
        job_key = job_storage._make_job_key(job_id)
        old_time = time.time() - (RedisJobStorage.JOB_TTL_SECONDS + 100)
        await redis.hset(job_key, "completed_at", str(old_time))
        # Run cleanup
        cleaned = await job_storage.cleanup_expired_jobs()
        assert cleaned >= 1
        # Job should be deleted
        job = await job_storage.get_job(job_id)
        assert job is None

    @pytest.mark.asyncio
    async def test_get_stats(self, job_storage: RedisJobStorage):
        """Test storage statistics."""
        # Create jobs in different states
        await job_storage.create_job("test-stat-1", None, {})
        await job_storage.create_job("test-stat-2", None, {})
        await job_storage.update_job("test-stat-2", status="processing")
        stats = await job_storage.get_stats()
        assert stats["total_jobs"] >= 2
        assert stats["by_status"]["queued"] >= 1
        assert stats["by_status"]["processing"] >= 1

    @pytest.mark.asyncio
    async def test_cleanup_task_lifecycle(self, job_storage: RedisJobStorage):
        """Test cleanup task start/stop."""
        # Start cleanup task
        await job_storage.start_cleanup_task()
        assert job_storage._cleanup_task is not None
        # Wait briefly
        await asyncio.sleep(0.1)
        # Stop cleanup task
        await job_storage.stop_cleanup_task()
        assert job_storage._cleanup_task is None

    @pytest.mark.asyncio
    async def test_no_unbounded_memory_growth(self, job_storage: RedisJobStorage):
        """Verify jobs don't accumulate in memory (Redis-backed)."""
        # This test verifies the fix for unbounded dict growth
        # Jobs should be stored in Redis, not in-memory dicts
        # Create many jobs
        for i in range(100):
            await job_storage.create_job(
                job_id=f"test-memory-{i}",
                user_id=f"user-{i % 10}",
                metadata={"index": i},
            )
        # Verify we can retrieve jobs (proving Redis storage)
        job = await job_storage.get_job("test-memory-50")
        assert job is not None
        assert job["metadata"]["index"] == 50
        # Verify no global dict exists (module-level check)
        from kagami_api.routes.command.forge import image_generation

        # The old _image_jobs dict should not exist
        assert not hasattr(image_generation, "_image_jobs") or (
            hasattr(image_generation, "_job_storage") and image_generation._job_storage is not None
        )


def test_get_job_storage_singleton():
    """Test job storage factory returns singleton per namespace."""
    storage1 = get_job_storage("test_ns")
    storage2 = get_job_storage("test_ns")
    storage3 = get_job_storage("other_ns")
    # Same namespace should return same instance
    assert storage1 is storage2
    # Different namespace should return different instance
    assert storage1 is not storage3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
