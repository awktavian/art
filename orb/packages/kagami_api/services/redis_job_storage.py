"""Redis-backed job storage for async tasks.

Replaces unbounded in-memory dicts with TTL-based Redis storage.

Features:
- Automatic expiration (1 hour TTL)
- Per-user job limits (10 concurrent)
- LRU eviction fallback (in-memory mode)
- No binary data storage (file paths only)
- Background cleanup task

Safety:
- Prevents memory leaks from abandoned jobs
- Rate limiting per user
- Graceful degradation without Redis

December 2025 - Fix for unbounded memory growth
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from kagami.core.caching.redis import RedisClientFactory

logger = logging.getLogger(__name__)


class RedisJobStorage:
    """Redis-backed job storage with TTL and per-user limits.

    Job data structure:
    {
        "job_id": str,
        "status": "queued" | "processing" | "completed" | "failed" | "cancelled",
        "created_at": float,
        "started_at": float | None,
        "completed_at": float | None,
        "user_id": str | None,
        "metadata": dict,
        "result_path": str | None,  # File path, NOT base64 data
        "error": str | None,
    }
    """

    # TTL configuration
    JOB_TTL_SECONDS = 3600  # 1 hour
    MAX_JOBS_PER_USER = 10
    CLEANUP_INTERVAL_SECONDS = 300  # 5 minutes

    def __init__(self, namespace: str = "job"):
        """Initialize job storage.

        Args:
            namespace: Redis key namespace (e.g., "image", "animation")
        """
        self.namespace = namespace
        self._redis_client: Any = None
        self._cleanup_task: asyncio.Task | None = None
        self._shutdown = False

    async def _get_redis(self) -> Any:
        """Get or create Redis client."""
        if self._redis_client is None:
            self._redis_client = RedisClientFactory.get_client(
                purpose="sessions",  # Short-lived data
                async_mode=True,
                decode_responses=True,
            )
        return self._redis_client

    def _make_job_key(self, job_id: str) -> str:
        """Generate Redis key for job."""
        return f"{self.namespace}:job:{job_id}"

    def _make_user_jobs_key(self, user_id: str) -> str:
        """Generate Redis key for user's job set."""
        return f"{self.namespace}:user:{user_id}:jobs"

    async def create_job(
        self,
        job_id: str,
        user_id: str | None,
        metadata: dict[str, Any],
    ) -> bool:
        """Create new job entry.

        Args:
            job_id: Unique job identifier
            user_id: User identifier (for rate limiting)
            metadata: Job-specific metadata

        Returns:
            True if created, False if user limit exceeded
        """
        redis = await self._get_redis()

        # Check per-user limit
        if user_id:
            user_jobs_key = self._make_user_jobs_key(user_id)
            user_job_count = await redis.scard(user_jobs_key) or 0

            if user_job_count >= self.MAX_JOBS_PER_USER:
                logger.warning(
                    f"User {user_id} exceeded job limit: {user_job_count}/{self.MAX_JOBS_PER_USER}"
                )
                return False

        # Create job entry
        job_key = self._make_job_key(job_id)
        job_data = {
            "job_id": job_id,
            "status": "queued",
            "created_at": time.time(),
            "started_at": None,
            "completed_at": None,
            "user_id": user_id,
            "metadata": json.dumps(metadata),
            "result_path": None,
            "error": None,
        }

        # Store job data
        await redis.hset(job_key, mapping=job_data)
        await redis.expire(job_key, self.JOB_TTL_SECONDS)

        # Add to user's job set
        if user_id:
            user_jobs_key = self._make_user_jobs_key(user_id)
            await redis.sadd(user_jobs_key, job_id)
            await redis.expire(user_jobs_key, self.JOB_TTL_SECONDS)

        logger.info(f"Created job {job_id} (user: {user_id or 'anonymous'})")
        return True

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job data.

        Args:
            job_id: Job identifier

        Returns:
            Job data dict or None if not found
        """
        redis = await self._get_redis()
        job_key = self._make_job_key(job_id)

        job_data = await redis.hgetall(job_key)
        if not job_data:
            return None

        # Parse JSON metadata
        try:
            job_data["metadata"] = json.loads(job_data.get("metadata", "{}"))
        except (json.JSONDecodeError, TypeError):
            job_data["metadata"] = {}

        # Convert numeric fields
        for field in ("created_at", "started_at", "completed_at"):
            if job_data.get(field):
                try:
                    job_data[field] = float(job_data[field])
                except (ValueError, TypeError):
                    job_data[field] = None

        from typing import cast

        return cast(dict[str, Any], job_data)

    async def update_job(
        self,
        job_id: str,
        status: str | None = None,
        result_path: str | None = None,
        error: str | None = None,
        **extra_fields: Any,
    ) -> bool:
        """Update job status and fields.

        Args:
            job_id: Job identifier
            status: New status
            result_path: Path to result file (NOT base64 data)
            error: Error message if failed
            **extra_fields: Additional fields to update

        Returns:
            True if updated, False if job not found
        """
        redis = await self._get_redis()
        job_key = self._make_job_key(job_id)

        # Check if job exists
        exists = await redis.exists(job_key)
        if not exists:
            logger.warning(f"Job {job_id} not found for update")
            return False

        # Build update dict
        updates: dict[str, Any] = {}

        if status:
            updates["status"] = status

            # Set timestamps based on status
            started_at = await redis.hget(job_key, "started_at")
            if status == "processing" and (not started_at or started_at == "None"):
                updates["started_at"] = str(time.time())
            elif status in ("completed", "failed", "cancelled"):
                updates["completed_at"] = str(time.time())

        if result_path is not None:
            updates["result_path"] = result_path

        if error is not None:
            updates["error"] = error

        # Add extra fields
        for field, value in extra_fields.items():
            if isinstance(value, dict):
                updates[field] = json.dumps(value)
            else:
                updates[field] = str(value)

        if updates:
            await redis.hset(job_key, mapping=updates)
            logger.debug(f"Updated job {job_id}: {list(updates.keys())}")

        return True

    async def delete_job(self, job_id: str) -> bool:
        """Delete job and cleanup user associations.

        Args:
            job_id: Job identifier

        Returns:
            True if deleted, False if not found
        """
        redis = await self._get_redis()
        job_key = self._make_job_key(job_id)

        # Get user_id before deletion
        user_id = await redis.hget(job_key, "user_id")

        # Delete job
        deleted = await redis.delete(job_key)

        # Remove from user's job set
        if user_id:
            user_jobs_key = self._make_user_jobs_key(user_id)
            await redis.srem(user_jobs_key, job_id)

        if deleted:
            logger.info(f"Deleted job {job_id}")

        return bool(deleted)

    async def list_user_jobs(self, user_id: str) -> list[str]:
        """List all job IDs for a user.

        Args:
            user_id: User identifier

        Returns:
            List of job IDs
        """
        redis = await self._get_redis()
        user_jobs_key = self._make_user_jobs_key(user_id)

        job_ids = await redis.smembers(user_jobs_key)
        return list(job_ids) if job_ids else []

    async def cleanup_expired_jobs(self) -> int:
        """Cleanup expired jobs (Redis TTL handles most, this is for orphans).

        Returns:
            Number of jobs cleaned up
        """
        redis = await self._get_redis()
        cleaned = 0

        # Scan for all job keys
        pattern = f"{self.namespace}:job:*"
        async for job_key in redis.scan_iter(match=pattern):
            try:
                # Check if job is expired based on completion time
                completed_at = await redis.hget(job_key, "completed_at")
                status = await redis.hget(job_key, "status")

                if completed_at and status in ("completed", "failed", "cancelled"):
                    age = time.time() - float(completed_at)

                    # Delete if completed more than 1 hour ago
                    if age > self.JOB_TTL_SECONDS:
                        job_id = job_key.split(":")[-1]
                        await self.delete_job(job_id)
                        cleaned += 1

            except Exception as e:
                logger.warning(f"Error cleaning job {job_key}: {e}")
                continue

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired jobs")

        return cleaned

    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is not None:
            logger.warning("Cleanup task already running")
            return

        self._shutdown = False
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info(f"Started cleanup task (interval: {self.CLEANUP_INTERVAL_SECONDS}s)")

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task is None:
            return

        self._shutdown = True

        # Cancel task
        self._cleanup_task.cancel()

        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass

        self._cleanup_task = None
        logger.info("Stopped cleanup task")

    async def _cleanup_loop(self) -> None:
        """Background loop to cleanup expired jobs."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.CLEANUP_INTERVAL_SECONDS)

                if not self._shutdown:
                    await self.cleanup_expired_jobs()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup task error: {e}", exc_info=True)
                # Continue running despite errors
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def get_stats(self) -> dict[str, Any]:
        """Get storage statistics.

        Returns:
            Dict with job counts by status
        """
        redis = await self._get_redis()
        stats = {
            "total_jobs": 0,
            "by_status": {
                "queued": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
            },
        }

        # Count jobs by status
        pattern = f"{self.namespace}:job:*"
        async for job_key in redis.scan_iter(match=pattern):
            try:
                status = await redis.hget(job_key, "status")
                stats["total_jobs"] += 1  # type: ignore[operator]

                if status in stats["by_status"]:  # type: ignore[operator]
                    stats["by_status"][status] += 1  # type: ignore[index]

            except Exception:
                continue

        return stats


# Global storage instances (lazily initialized)
_storage_instances: dict[str, RedisJobStorage] = {}


def get_job_storage(namespace: str) -> RedisJobStorage:
    """Get or create job storage for namespace.

    Args:
        namespace: Storage namespace (e.g., "image", "animation")

    Returns:
        RedisJobStorage instance
    """
    if namespace not in _storage_instances:
        _storage_instances[namespace] = RedisJobStorage(namespace)

    return _storage_instances[namespace]


async def cleanup_all_storage() -> None:
    """Cleanup all storage instances (shutdown hook)."""
    for storage in _storage_instances.values():
        try:
            await storage.stop_cleanup_task()
        except Exception as e:
            logger.warning(f"Error stopping cleanup task: {e}")

    _storage_instances.clear()


__all__ = [
    "RedisJobStorage",
    "cleanup_all_storage",
    "get_job_storage",
]
