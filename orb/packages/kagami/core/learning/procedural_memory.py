from __future__ import annotations

"Procedural Memory: Storage and retrieval of learned workflows WITH cleanup.\n\nThis module manages persistent storage of procedural knowledge (workflows)\nextracted via meta-learning, with Redis caching and CockroachDB persistence.\n"
import json
import logging
from datetime import datetime
from typing import Any

from kagami.core.infra.singleton_cleanup_mixin import SingletonCleanupMixin

logger = logging.getLogger(__name__)


class ProceduralMemory(SingletonCleanupMixin):
    """Storage for learned workflows and patterns WITH automatic cleanup."""

    def __init__(self) -> None:
        """Initialize procedural memory."""
        self._cache: dict[str, dict[str, Any]] = {}
        self._max_cache_size = 200
        self._cleanup_interval = 3600.0
        self._register_cleanup_on_exit()

    async def store_workflow(self, pattern_id: str, workflow: dict[str, Any]) -> bool:
        """Store workflow in procedural memory.

        Args:
            pattern_id: Unique pattern identifier
            workflow: Workflow data to store

        Returns:
            True if stored successfully
        """
        try:
            self._cache[pattern_id] = workflow
            if len(self._cache) > self._max_cache_size:
                oldest = next(iter(self._cache.keys()))
                self._cache.pop(oldest, None)
            try:
                await self._store_redis(pattern_id, workflow)
            except Exception as e:
                logger.debug(f"Redis storage failed for {pattern_id}: {e}")
            try:
                await self._store_db(pattern_id, workflow)
            except Exception as e:
                logger.debug(f"DB storage failed for {pattern_id}: {e}")
            logger.debug(f"Stored workflow {pattern_id} in procedural memory")
            return True
        except Exception as e:
            logger.error(f"Failed to store workflow {pattern_id}: {e}")
            return False

    async def retrieve_workflow(self, pattern_id: str) -> dict[str, Any] | None:
        """Retrieve workflow from procedural memory.

        Args:
            pattern_id: Pattern identifier

        Returns:
            Workflow data or None if not found
        """
        if pattern_id in self._cache:
            logger.debug(f"Cache hit for workflow {pattern_id}")
            return self._cache[pattern_id]
        try:
            workflow = await self._retrieve_redis(pattern_id)
            if workflow:
                self._cache[pattern_id] = workflow
                return workflow
        except Exception as e:
            logger.debug(f"Redis retrieval failed for {pattern_id}: {e}")
        try:
            workflow = await self._retrieve_db(pattern_id)
            if workflow:
                self._cache[pattern_id] = workflow
                return workflow
        except Exception as e:
            logger.debug(f"DB retrieval failed for {pattern_id}: {e}")
        logger.debug(f"Workflow {pattern_id} not found in procedural memory")
        return None

    async def delete_workflow(self, pattern_id: str) -> bool:
        """Delete workflow from procedural memory.

        Args:
            pattern_id: Pattern to delete

        Returns:
            True if deleted
        """
        try:
            self._cache.pop(pattern_id, None)
            try:
                await self._delete_redis(pattern_id)
            except Exception as e:
                logger.debug(f"Redis deletion failed for {pattern_id}: {e}")
            try:
                await self._delete_db(pattern_id)
            except Exception as e:
                logger.debug(f"DB deletion failed for {pattern_id}: {e}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete workflow {pattern_id}: {e}")
            return False

    async def list_workflows(self, limit: int = 100) -> list[dict[str, Any]]:
        """List all stored workflows.

        Args:
            limit: Maximum workflows to return

        Returns:
            List of workflows
        """
        workflows = list(self._cache.values())[:limit]
        return workflows

    async def _store_redis(self, pattern_id: str, workflow: dict[str, Any]) -> None:
        """Store workflow in Redis.

        Args:
            pattern_id: Pattern identifier
            workflow: Workflow data
        """
        try:
            from kagami.core.caching.redis import RedisClientFactory

            redis = RedisClientFactory.get_client("default", async_mode=True)
            if not redis:
                return
            key = f"procedural:workflow:{pattern_id}"
            data = json.dumps(workflow)
            await redis.setex(key, 604800, data)
        except Exception as e:
            logger.debug(f"Redis storage error: {e}")
            raise

    async def _retrieve_redis(self, pattern_id: str) -> dict[str, Any] | None:
        """Retrieve workflow from Redis.

        Args:
            pattern_id: Pattern identifier

        Returns:
            Workflow data or None
        """
        try:
            from kagami.core.caching.redis import RedisClientFactory

            redis = RedisClientFactory.get_client("default", async_mode=True)
            if not redis:
                return None
            key = f"procedural:workflow:{pattern_id}"
            data = await redis.get(key)
            if data:
                return dict(json.loads(data)) if isinstance(json.loads(data), dict) else None
            return None
        except Exception as e:
            logger.debug(f"Redis retrieval error: {e}")
            raise

    async def _delete_redis(self, pattern_id: str) -> None:
        """Delete workflow from Redis.

        Args:
            pattern_id: Pattern identifier
        """
        try:
            from kagami.core.caching.redis import RedisClientFactory

            redis = RedisClientFactory.get_client("default", async_mode=True)
            if not redis:
                return
            key = f"procedural:workflow:{pattern_id}"
            await redis.delete(key)
        except Exception as e:
            logger.debug(f"Redis deletion error: {e}")
            raise

    async def _store_db(self, pattern_id: str, workflow: dict[str, Any]) -> None:
        """Store workflow in CockroachDB.

        Args:
            pattern_id: Pattern identifier
            workflow: Workflow data
        """
        try:
            from sqlalchemy import text

            from kagami.core.database.async_connection import get_async_db_session

            async with get_async_db_session() as db:
                query = text(
                    "\n                    INSERT INTO procedural_workflows (pattern_id, workflow, updated_at)\n                    VALUES (:pattern_id, :workflow, :updated_at)\n                    ON CONFLICT (pattern_id)\n                    DO UPDATE SET workflow = :workflow, updated_at = :updated_at\n                    "
                )
                await db.execute(
                    query,
                    {
                        "pattern_id": pattern_id,
                        "workflow": json.dumps(workflow),
                        "updated_at": datetime.utcnow(),
                    },
                )
                await db.commit()
        except Exception as e:
            logger.debug(f"DB storage error: {e}")
            raise

    async def _retrieve_db(self, pattern_id: str) -> dict[str, Any] | None:
        """Retrieve workflow from CockroachDB.

        Args:
            pattern_id: Pattern identifier

        Returns:
            Workflow data or None
        """
        try:
            from sqlalchemy import text

            from kagami.core.database.async_connection import get_async_db_session

            async with get_async_db_session() as db:
                query = text(
                    "SELECT workflow FROM procedural_workflows WHERE pattern_id = :pattern_id"
                )
                result = await db.execute(query, {"pattern_id": pattern_id})
                row = result.fetchone()
                if row:
                    return (
                        dict(json.loads(row[0])) if isinstance(json.loads(row[0]), dict) else None
                    )
                return None
        except Exception as e:
            logger.debug(f"DB retrieval error: {e}")
            raise

    async def _delete_db(self, pattern_id: str) -> None:
        """Delete workflow from CockroachDB.

        Args:
            pattern_id: Pattern identifier
        """
        try:
            from sqlalchemy import text

            from kagami.core.database.async_connection import get_async_db_session

            async with get_async_db_session() as db:
                query = text("DELETE FROM procedural_workflows WHERE pattern_id = :pattern_id")
                await db.execute(query, {"pattern_id": pattern_id})
                await db.commit()
        except Exception as e:
            logger.debug(f"DB deletion error: {e}")
            raise

    def _cleanup_internal_state(self) -> dict[str, int]:
        """Clean up unused workflows (implements SingletonCleanupMixin)."""
        removed = 0
        if len(self._cache) > self._max_cache_size:
            excess = len(self._cache) - self._max_cache_size
            keys_to_remove = list(self._cache.keys())[:excess]
            for key in keys_to_remove:
                del self._cache[key]
                removed += 1
        return {
            "workflows_removed": removed,
            "workflows_cached": len(self._cache),
            "max_capacity": self._max_cache_size,
        }


_procedural_memory: ProceduralMemory | None = None
