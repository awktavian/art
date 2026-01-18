"""Knowledge graph repository with Weaviate integration.

Created: December 15, 2025
"""

from __future__ import annotations

import logging
from typing import Any

from kagami.core.storage.routing import get_storage_router

logger = logging.getLogger(__name__)


class KnowledgeRepository:
    """Repository for knowledge graph storage in Weaviate.

    Storage architecture:
    - Primary: Weaviate (vector/semantic storage)
    - L2 Cache: Redis (fast lookups)

    Cache strategy: READ_THROUGH
    - High read volume for RAG
    - Semantic similarity search
    - Vector embeddings
    """

    def __init__(
        self,
        redis_client: Any | None = None,
    ):
        """Initialize knowledge repository.

        Args:
            redis_client: Optional Redis client for L2 cache
        """
        self._router = get_storage_router()
        self._redis = redis_client
        logger.info("KnowledgeRepository initialized")

    async def store_knowledge(
        self,
        content: str,
        embedding: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Store knowledge in Weaviate.

        Args:
            content: Text content
            embedding: Optional pre-computed embedding
            metadata: Additional metadata

        Returns:
            UUID of stored object
        """
        try:
            return await self._router.store_vector(
                content=content,
                embedding=embedding,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Knowledge storage failed: {e}")
            return None

    async def search_knowledge(
        self,
        query: str,
        limit: int = 10,
        colony_filter: str | None = None,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search for knowledge.

        Args:
            query: Search query
            limit: Max results
            colony_filter: Optional colony filter
            tenant_id: Optional tenant filter

        Returns:
            List of matching knowledge items
        """
        try:
            return await self._router.search_semantic(
                query=query,
                limit=limit,
                colony_filter=colony_filter,
                kind_filter="knowledge",
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.error(f"Knowledge search failed: {e}")
            return []

    async def store_pattern(
        self,
        action: str,
        domain: str,
        success: bool,
        duration: float = 0.0,
    ) -> bool:
        """Store stigmergy pattern.

        Args:
            action: Action name
            domain: Domain name
            success: Whether action succeeded
            duration: Action duration

        Returns:
            True if stored
        """
        try:
            return await self._router.store_pattern(
                action=action,
                domain=domain,
                success=success,
                duration=duration,
            )
        except Exception as e:
            logger.error(f"Pattern storage failed: {e}")
            return False

    async def get_pattern_statistics(
        self,
        action: str,
        domain: str,
    ) -> dict[str, Any] | None:
        """Get statistics for a pattern.

        Args:
            action: Action name
            domain: Domain name

        Returns:
            Pattern statistics or None
        """
        # Load patterns from Weaviate
        try:
            from kagami_integrations.elysia.weaviate_pattern_store import (
                get_weaviate_pattern_store,
            )

            store = get_weaviate_pattern_store()
            patterns = await store.load_patterns()
            key = (action, domain)

            if key in patterns:
                pattern = patterns[key]
                return {
                    "action": pattern.action,
                    "domain": pattern.domain,
                    "success_count": pattern.success_count,
                    "failure_count": pattern.failure_count,
                    "success_rate": pattern.success_count
                    / (pattern.success_count + pattern.failure_count),
                    "avg_duration": pattern.avg_duration,
                    "access_count": pattern.access_count,
                }

            return None

        except Exception as e:
            logger.error(f"Pattern statistics failed: {e}")
            return None


__all__ = ["KnowledgeRepository"]
