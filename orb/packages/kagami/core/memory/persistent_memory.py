"""Persistent Memory System - Lifetime Memory Across Restarts.

This module implements long-term episodic memory that survives
organism restarts, enabling true continuity of experience.

Created: November 1, 2025 (Master Plan Phase 2, Week 6)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


class PersistentMemory:
    """Long-term memory system with semantic and temporal retrieval.

    Uses dual storage:
    1. Vector store (Weaviate) for semantic search
    2. SQL database for structured temporal queries

    This enables the organism to remember everything it's ever done
    and learn from accumulated experience.
    """

    def __init__(self, agent_id: str | None = None) -> None:
        """Initialize persistent memory.

        Args:
            agent_id: Optional agent ID (None for organism-level memory)
        """
        self.agent_id = agent_id or "organism"
        self._vector_store = None  # Lazy-loaded
        self._sql_db = None  # Lazy-loaded

        logger.info(f"💾 Persistent memory initialized for {self.agent_id}")

    async def remember(self, event: dict[str, Any]) -> None:
        """Store event in long-term memory.

        Args:
            event: Event to remember (must have id, timestamp, description, data)
        """
        try:
            event_id = event.get("id", f"mem_{int(time.time() * 1000)}")
            timestamp = event.get("timestamp", datetime.now())
            description = event.get("description", "")
            data = event.get("data", {})

            # Create embedding for semantic search (reuse provided embedding if present).
            embedding = event.get("embedding")
            if embedding is None:
                embedding = await self._create_embedding(description)

            # Store in vector store (Weaviate)
            await self._store_in_vector_db(
                event_id=event_id,
                embedding=embedding,
                metadata={
                    "timestamp": (
                        timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)
                    ),
                    "description": description,
                    "agent_id": self.agent_id,
                    "type": event.get("type", "general"),
                },
                data=data,
            )

            # Store in SQL for structured queries
            await self._store_in_sql_db(
                event_id=event_id,
                timestamp=timestamp,
                event_type=event.get("type", "general"),
                description=description,
                data=data,
                embedding=embedding.tolist() if hasattr(embedding, "tolist") else embedding,
            )

            logger.debug(f"💾 Remembered: {description[:50]}...")

        except Exception as e:
            logger.error(f"Failed to remember event: {e}", exc_info=True)

    async def store_event(
        self,
        event_type: str,
        description: str,
        data: dict[str, Any] | None = None,
        embedding: Any | None = None,
        timestamp: Any | None = None,
        event_id: str | None = None,
    ) -> None:
        """Compatibility wrapper used by kernel syscalls."""
        await self.remember(
            {
                "id": event_id or f"mem_{int(time.time() * 1000)}",
                "timestamp": timestamp or datetime.now(),
                "type": event_type,
                "description": description,
                "data": data or {},
                "embedding": embedding,
            }
        )

    async def recall(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Retrieve memories by semantic similarity.

        Args:
            query: Query text
            k: Number of memories to retrieve

        Returns:
            List of similar memories
        """
        try:
            # Search vector store (Weaviate). We keep the signature stable but do not
            # require callers to provide embeddings.
            results = await self._search_vector_db(query, k=k)

            logger.debug(f"💾 Recalled {len(results)} memories for: {query[:50]}...")

            return results

        except Exception as e:
            logger.error(f"Failed to recall memories: {e}", exc_info=True)
            return []

    async def recall_temporal(
        self, start: datetime, end: datetime, event_type: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Retrieve memories in time range.

        Args:
            start: Start time
            end: End time
            event_type: Optional filter by type
            limit: Max results

        Returns:
            List of memories in time range
        """
        try:
            results = await self._query_sql_temporal(start, end, event_type, limit)

            logger.debug(
                f"💾 Recalled {len(results)} memories between "
                f"{start.strftime('%Y-%m-%d')} and {end.strftime('%Y-%m-%d')}"
            )

            return results

        except Exception as e:
            logger.error(f"Failed to recall temporal memories: {e}", exc_info=True)
            return []

    async def recall_recent(self, hours: int = 24, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent memories.

        Args:
            hours: How many hours back
            limit: Max results

        Returns:
            Recent memories
        """
        end = datetime.now()
        start = end - timedelta(hours=hours)

        return await self.recall_temporal(start, end, limit=limit)

    async def _create_embedding(self, text: str) -> Any:
        """Create semantic embedding of text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector

        Raises:
            Exception: If embedding service is unavailable (no fallback since Dec 30, 2025)
        """
        # Use shared Kagami EmbeddingService (guaranteed available as of Dec 30, 2025)
        from kagami.core.services.embedding_service import get_embedding_service

        service = get_embedding_service()
        return await service.embed_text_async(text)

    async def _store_in_vector_db(
        self, event_id: str, embedding: Any, metadata: dict[str, Any], data: dict[str, Any]
    ) -> None:
        """Store in Weaviate vector store (via UnifiedStorageRouter).

        Args:
            event_id: Unique event ID
            embedding: Embedding vector
            metadata: Event metadata
            data: Event data
        """
        try:
            from kagami.core.services.storage_routing import get_storage_router

            router = get_storage_router()

            # Build compact searchable text (description + type)
            description = str(metadata.get("description") or "")
            event_type = str(metadata.get("type") or "general")
            content = f"[{event_type}] {description}".strip()

            payload_json = json.dumps({"metadata": metadata, "data": data}, default=str)

            await router.store_vector(
                content=content,
                embedding=embedding,
                metadata={
                    "kind": "persistent_memory",
                    "agent": self.agent_id,
                    "category": event_type,
                    "source_id": event_id,
                    "created_at": metadata.get("timestamp"),
                    "metadata_json": payload_json,
                },
            )

        except Exception as e:
            logger.debug(f"Failed to store in vector DB: {e}")

    async def _search_vector_db(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Search Weaviate for similar memories.

        Args:
            query: Query text
            k: Number of results

        Returns:
            Similar memories
        """
        try:
            from kagami.core.services.storage_routing import get_storage_router

            router = get_storage_router()
            hits = await router.search_semantic(
                query=query, limit=k, kind_filter="persistent_memory"
            )

            out: list[dict[str, Any]] = []
            for h in hits:
                # WeaviateE8Adapter returns both flattened keys and full properties.
                props = h.get("properties") or {}
                meta_raw = h.get("metadata_json") or props.get("metadata_json") or ""
                payload: dict[str, Any] = {}
                if meta_raw and isinstance(meta_raw, str):
                    try:
                        payload = json.loads(meta_raw)
                    except Exception:
                        payload = {}

                distance = h.get("score")
                similarity = None
                if isinstance(distance, (int, float)):
                    similarity = 1.0 - float(distance)

                out.append(
                    {
                        "event_id": h.get("source_id") or h.get("uuid"),
                        "similarity": similarity,
                        "distance": distance,
                        "description": h.get("content", ""),
                        "metadata": payload.get("metadata") or {},
                        "data": payload.get("data") or {},
                    }
                )

            return out

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def _store_in_sql_db(
        self,
        event_id: str,
        timestamp: datetime,
        event_type: str,
        description: str,
        data: dict[str, Any],
        embedding: list[float],
    ) -> None:
        """Store in SQL database for structured queries.

        Args:
            event_id: Unique event ID
            timestamp: Event timestamp
            event_type: Type of event
            description: Event description
            data: Event data
            embedding: Embedding vector
        """
        try:
            from kagami.core.database.connection import get_session_factory

            # Episode table exists in models.py (episodes table with embedding support)
            # Uses best-effort SQL storage with JSONB for flexible schema

            db = get_session_factory()()

            # Try to insert into episodes table if it exists
            try:
                db.execute(
                    text(
                        """
                    INSERT INTO episodes (id, agent_id, timestamp, type, description, data, embedding)
                    VALUES (:id, :agent_id, :timestamp, :type, :description, :data, :embedding)
                    ON CONFLICT (id) DO UPDATE SET
                        data = :data,
                        embedding = :embedding
                    """
                    ),
                    {
                        "id": event_id,
                        "agent_id": self.agent_id,
                        "timestamp": timestamp,
                        "type": event_type,
                        "description": description,
                        "data": json.dumps(data),
                        "embedding": json.dumps(embedding),
                    },
                )
                db.commit()
            except Exception:
                # Table might not exist yet - that's ok
                db.rollback()
            finally:
                db.close()

        except Exception as e:
            logger.debug(f"Failed to store in SQL: {e}")

    async def _query_sql_temporal(
        self, start: datetime, end: datetime, event_type: str | None, limit: int
    ) -> list[dict[str, Any]]:
        """Query SQL for temporal range.

        Args:
            start: Start time
            end: End time
            event_type: Optional type filter
            limit: Max results

        Returns:
            Matching events
        """
        try:
            from kagami.core.database.connection import get_session_factory

            db = get_session_factory()()

            try:
                query = "SELECT * FROM episodes WHERE agent_id = :agent_id AND timestamp BETWEEN :start AND :end"
                params: dict[str, Any] = {
                    "agent_id": self.agent_id,
                    "start": start,
                    "end": end,
                }

                if event_type:
                    query += " AND type = :type"
                    params["type"] = event_type

                query += " ORDER BY timestamp DESC LIMIT :limit"
                params["limit"] = limit

                rows = db.execute(text(query), params).fetchall()

                results = []
                for row in rows:
                    results.append(
                        {
                            "event_id": row.id,
                            "timestamp": row.timestamp,
                            "type": row.type,
                            "description": row.description,
                            "data": json.loads(row.data) if isinstance(row.data, str) else row.data,
                        }
                    )

                return results

            finally:
                db.close()

        except Exception as e:
            logger.debug(f"SQL temporal query failed: {e}")
            return []

    def get_statistics(self) -> dict[str, Any]:
        """Get memory statistics.

        Returns:
            Statistics about stored memories
        """
        try:
            return {
                "agent_id": self.agent_id,
                "storage_backend": "weaviate+sql",
            }

        except Exception as e:
            logger.debug(f"Could not get memory statistics: {e}")
            return {"status": "error", "error": str(e)}


_PERSISTENT_MEMORIES: dict[str, PersistentMemory] = {}


def get_persistent_memory(agent_id: str | None = None) -> PersistentMemory:
    """Get or create a PersistentMemory instance (per agent_id)."""
    key = agent_id or "organism"
    if key not in _PERSISTENT_MEMORIES:
        _PERSISTENT_MEMORIES[key] = PersistentMemory(agent_id=key)
    return _PERSISTENT_MEMORIES[key]


def reset_persistent_memory(agent_id: str | None = None) -> None:
    """Reset cached persistent memory instances (tests/dev)."""
    if agent_id is None:
        _PERSISTENT_MEMORIES.clear()
    else:
        _PERSISTENT_MEMORIES.pop(agent_id, None)


async def store_event(
    agent_id: str,
    event_type: str,
    description: str,
    data: dict[str, Any] | None = None,
    embedding: Any | None = None,
    timestamp: Any | None = None,
    event_id: str | None = None,
) -> None:
    """Compatibility helper: store an event in persistent memory."""
    mem = get_persistent_memory(agent_id=agent_id)
    await mem.store_event(
        event_type=event_type,
        description=description,
        data=data,
        embedding=embedding,
        timestamp=timestamp,
        event_id=event_id,
    )


__all__ = ["PersistentMemory", "get_persistent_memory", "reset_persistent_memory", "store_event"]
