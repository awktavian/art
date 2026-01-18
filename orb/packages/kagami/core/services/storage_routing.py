"""Unified Storage Architecture — Optimal Routing to Data Stores.

STORAGE SYSTEMS (Dec 7, 2025):
===============================

┌─────────────────────────────────────────────────────────────────────────────┐
│                        UNIFIED STORAGE ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │   Weaviate   │     │    Redis     │     │ CockroachDB  │                │
│  │ (Vectors/RAG)│     │ (Cache/Pub)  │     │  (Relational)│                │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘                │
│         │                    │                    │                         │
│         └────────────────────┼────────────────────┘                         │
│                              │                                              │
│                     ┌────────┴────────┐                                     │
│                     │      etcd       │                                     │
│                     │ (Coordination)  │                                     │
│                     └─────────────────┘                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

ROUTING DECISION TREE:
======================

    Data Type?
        │
        ├─ Vector/Embedding ───────────► WEAVIATE
        │   - RAG results
        │   - Semantic search
        │   - E8 quantized embeddings
        │   - Stigmergy patterns
        │   - Few-shot examples
        │
        ├─ Ephemeral/Cache ────────────► REDIS
        │   - Session state
        │   - Rate limiting
        │   - L2 cache
        │   - Pub/sub events
        │   - Short-term receipts
        │
        ├─ Relational/Transactional ───► COCKROACHDB
        │   - Users/auth
        │   - Billing/tenants
        │   - Audit logs (permanent)
        │   - Safety snapshots
        │   - Learning signals (EFE/rewards)
        │
        └─ Coordination/Consensus ─────► ETCD
            - Leader election
            - Federated aggregation
            - Service discovery
            - Cross-instance sync
            - Distributed locks

SIMPLIFICATION ACHIEVED:
========================

1. Weaviate replaces Redis for:
   - Pattern storage (WeaviatePatternStore)
   - Stigmergy learning data
   - Few-shot example retrieval

2. Single vector store:
   - Weaviate is THE vector database
   - RediSearch deprecated for RAG workloads

3. etcd + Weaviate integration:
   - Cross-instance receipts synced to Weaviate for semantic search
   - Federated learning patterns persisted to Weaviate

4. Clear separation:
   - Redis = ephemeral/real-time
   - Weaviate = semantic/persistent
   - CockroachDB = relational/transactional
   - etcd = coordination/consensus

Created: December 7, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class StorageBackend(Enum):
    """Available storage backends."""

    WEAVIATE = "weaviate"  # Vector/semantic storage
    REDIS = "redis"  # Cache/ephemeral storage
    COCKROACHDB = "cockroachdb"  # Relational/transactional
    ETCD = "etcd"  # Coordination/consensus
    MEMORY = "memory"  # In-process (L1 cache)


class DataCategory(Enum):
    """Categories of data for routing decisions."""

    VECTOR = "vector"  # Embeddings, semantic search
    CACHE = "cache"  # Ephemeral, TTL-based
    RELATIONAL = "relational"  # Structured, transactional
    COORDINATION = "coordination"  # Distributed consensus
    PATTERN = "pattern"  # Stigmergy/learning patterns
    RECEIPT = "receipt"  # Audit/feedback data


# Storage routing rules
STORAGE_ROUTING = {
    # Vector/semantic data → Weaviate
    DataCategory.VECTOR: StorageBackend.WEAVIATE,
    DataCategory.PATTERN: StorageBackend.WEAVIATE,
    # Ephemeral data → Redis
    DataCategory.CACHE: StorageBackend.REDIS,
    # Relational data → CockroachDB
    DataCategory.RELATIONAL: StorageBackend.COCKROACHDB,
    # Coordination → etcd
    DataCategory.COORDINATION: StorageBackend.ETCD,
    # Receipts → Weaviate (semantic) + CockroachDB (audit)
    DataCategory.RECEIPT: StorageBackend.WEAVIATE,  # Primary for search
}


@dataclass
class StorageConfig:
    """Configuration for unified storage."""

    # Weaviate
    weaviate_enabled: bool = True
    weaviate_url: str = ""
    weaviate_api_key: str = ""

    # Redis
    redis_enabled: bool = True
    redis_url: str = "redis://localhost:6379"

    # CockroachDB
    cockroach_enabled: bool = True
    cockroach_url: str = "postgresql://root@localhost:26257/kagami"

    # etcd
    etcd_enabled: bool = True
    etcd_endpoints: list[str] | None = None


class UnifiedStorageRouter:
    """Routes data to optimal storage backend.

    Provides a single entry point for all storage operations,
    routing to the appropriate backend based on data category.

    Usage:
        router = UnifiedStorageRouter()

        # Store vector data → routes to Weaviate
        await router.store(DataCategory.VECTOR, key, embedding)

        # Store cache data → routes to Redis
        await router.store(DataCategory.CACHE, key, data, ttl=300)

        # Store relational → routes to CockroachDB
        await router.store(DataCategory.RELATIONAL, "users", user_data)
    """

    def __init__(self, config: StorageConfig | None = None):
        """Initialize storage router.

        Args:
            config: Storage configuration
        """
        self.config = config or StorageConfig()

        # Lazy-loaded backends
        self._weaviate = None
        self._redis = None
        self._cockroach = None
        self._etcd = None

        logger.info("🗄️ UnifiedStorageRouter initialized")

    def get_backend(self, category: DataCategory) -> StorageBackend:
        """Get optimal backend for data category.

        Args:
            category: Data category

        Returns:
            Optimal storage backend
        """
        return STORAGE_ROUTING.get(category, StorageBackend.REDIS)

    def _get_weaviate(self) -> Any:
        """Lazy-load Weaviate adapter."""
        if self._weaviate is None:
            try:
                from kagami_integrations.elysia.weaviate_e8_adapter import get_weaviate_adapter

                self._weaviate = get_weaviate_adapter()
            except ImportError:
                logger.warning("Weaviate adapter not available")
        return self._weaviate

    def _get_redis(self) -> Any:
        """Lazy-load Redis client."""
        if self._redis is None:
            try:
                from kagami.core.caching.redis.factory import RedisClientFactory

                self._redis = RedisClientFactory.get_client()
            except ImportError:
                logger.warning("Redis client not available")
        return self._redis

    def _get_cockroach(self) -> Any:
        """Lazy-load CockroachDB client."""
        if self._cockroach is None:
            try:
                from kagami.core.database.cockroach import CockroachDB

                self._cockroach = CockroachDB()  # type: ignore[assignment]
            except ImportError:
                logger.warning("CockroachDB client not available")
        return self._cockroach

    def _get_etcd(self) -> Any:
        """Lazy-load etcd client."""
        if self._etcd is None:
            try:
                from kagami.core.consensus.etcd_client import get_etcd_client

                self._etcd = get_etcd_client()
            except ImportError:
                logger.warning("etcd client not available")
        return self._etcd

    def _coerce_embedding_to_torch(self, embedding: Any) -> Any | None:
        """Best-effort conversion of embeddings to a torch tensor.

        WeaviateE8Adapter supports both:
        - torch tensors (preferred: near_vector search, E8 quantization)
        - raw strings (fallback: near_text search via Weaviate vectorizer)
        """
        if embedding is None:
            return None
        try:
            import numpy as np
            import torch

            if isinstance(embedding, torch.Tensor):
                return embedding
            if isinstance(embedding, np.ndarray):
                return torch.from_numpy(embedding).float()
            if isinstance(embedding, (list, tuple)):
                return torch.tensor(list(embedding), dtype=torch.float32)
        except Exception:
            return None
        return None

    def _embed_text(self, text: str) -> Any | None:
        """Compute a Kagami-native embedding for text (best-effort).

        This keeps Weaviate usage optimal even when its server-side vectorizers are disabled
        (we often configure collections with `Vectorizer.none()` and supply vectors ourselves).
        """
        try:
            from kagami.core.services.embedding_service import get_embedding_service

            # Prefer bulk semantic space for retrieval; service may fall back to hash embeddings
            # in test/lightweight environments.
            svc = get_embedding_service()

            # OPTIMIZATION (Dec 16, 2025): Use return_tensor=True to avoid GPU→CPU conversion
            # Weaviate adapter is device-agnostic and works with GPU tensors
            vec = svc.embed_text(text, dimension=svc.embedding_dim, return_tensor=True)
            return vec  # Already a torch tensor, no conversion needed
        except Exception:
            return None

    async def store_vector(
        self,
        content: str,
        embedding: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Store vector/semantic data in Weaviate.

        Args:
            content: Text content
            embedding: Optional pre-computed embedding
            metadata: Additional metadata

        Returns:
            UUID of stored object
        """
        weaviate = self._get_weaviate()
        if weaviate is None:
            logger.warning("Weaviate not available for vector storage")
            return None

        await weaviate.connect()
        emb = self._coerce_embedding_to_torch(embedding)
        if emb is None:
            emb = self._embed_text(content)
        return await weaviate.store(content, emb, metadata)  # type: ignore[no-any-return]

    async def search_semantic(
        self,
        query: str,
        limit: int = 10,
        colony_filter: str | None = None,
        kind_filter: str | None = None,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search in Weaviate.

        Args:
            query: Search query
            limit: Max results
            colony_filter: Optional colony filter

        Returns:
            List of matching results
        """
        weaviate = self._get_weaviate()
        if weaviate is None:
            return []

        await weaviate.connect()
        # Prefer vector search via Kagami embeddings; fall back to near_text if unavailable.
        emb = self._embed_text(query)
        if emb is not None:
            try:
                return await weaviate.search_similar(  # type: ignore[no-any-return]
                    emb,
                    limit=limit,
                    colony_filter=colony_filter,
                    kind_filter=kind_filter,
                    tenant_id=tenant_id,
                )
            except Exception:
                pass
        return await weaviate.search_similar(  # type: ignore[no-any-return]
            query,
            limit=limit,
            colony_filter=colony_filter,
            kind_filter=kind_filter,
            tenant_id=tenant_id,
        )

    async def store_pattern(
        self,
        action: str,
        domain: str,
        success: bool,
        duration: float = 0.0,
    ) -> bool:
        """Store stigmergy pattern in Weaviate.

        Args:
            action: Action name
            domain: Domain name
            success: Whether action succeeded
            duration: Action duration

        Returns:
            True if stored
        """
        try:
            from kagami_integrations.elysia.weaviate_pattern_store import (
                WeaviatePattern,
                get_weaviate_pattern_store,
            )

            store = get_weaviate_pattern_store()

            # Load existing or create new
            patterns = await store.load_patterns()
            key = (action, domain)

            if key in patterns:
                pattern = patterns[key]
                if success:
                    pattern.success_count += 1
                else:
                    pattern.failure_count += 1
                pattern.avg_duration = (pattern.avg_duration * pattern.access_count + duration) / (
                    pattern.access_count + 1
                )
                pattern.access_count += 1
            else:
                pattern = WeaviatePattern(
                    action=action,
                    domain=domain,
                    success_count=1 if success else 0,
                    failure_count=0 if success else 1,
                    avg_duration=duration,
                    access_count=1,
                )

            return await store.save_pattern(pattern)

        except Exception as e:
            logger.warning(f"Failed to store pattern: {e}")
            return False

    async def cache_set(
        self,
        key: str,
        value: Any,
        ttl: int = 300,
    ) -> bool:
        """Set cache value in Redis.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds

        Returns:
            True if cached
        """
        redis = self._get_redis()
        if redis is None:
            return False

        try:
            import json

            await redis.set(key, json.dumps(value), ex=ttl)
            return True
        except Exception as e:
            logger.warning(f"Cache set[Any] failed: {e}")
            return False

    async def cache_get(self, key: str) -> Any | None:
        """Get cache value from Redis.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        redis = self._get_redis()
        if redis is None:
            return None

        try:
            import json

            value = await redis.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.debug(f"Cache get failed: {e}")
            return None

    async def store_receipt_to_weaviate(
        self,
        receipt: dict[str, Any],
    ) -> str | None:
        """Store receipt in Weaviate for semantic search.

        This enables cross-instance learning via semantic similarity.

        Args:
            receipt: Receipt data

        Returns:
            UUID of stored receipt
        """
        weaviate = self._get_weaviate()
        if weaviate is None:
            return None

        await weaviate.connect()

        # Extract searchable content
        content_parts = [
            f"action:{receipt.get('event_name', 'unknown')}",
            f"phase:{receipt.get('phase', 'unknown')}",
            f"status:{receipt.get('status', 'unknown')}",
            f"colony:{receipt.get('colony', 'unknown')}",
        ]

        if receipt.get("error"):
            content_parts.append(f"error:{receipt['error']}")

        content = " ".join(content_parts)

        metadata = {
            "kind": "receipt",
            "colony": receipt.get("colony", "nexus"),
            "source_id": receipt.get("correlation_id", ""),
            "from_instance": receipt.get("from_instance", "local"),
        }

        return await weaviate.store(content, None, metadata)  # type: ignore[no-any-return]

    def get_status(self) -> dict[str, Any]:
        """Get status of all storage backends.

        Returns:
            Status dict[str, Any]
        """
        return {
            "weaviate": {
                "enabled": self.config.weaviate_enabled,
                "connected": self._weaviate is not None,
            },
            "redis": {
                "enabled": self.config.redis_enabled,
                "connected": self._redis is not None,
            },
            "cockroachdb": {
                "enabled": self.config.cockroach_enabled,
                "connected": self._cockroach is not None,
            },
            "etcd": {
                "enabled": self.config.etcd_enabled,
                "connected": self._etcd is not None,
            },
            "routing": {cat.value: backend.value for cat, backend in STORAGE_ROUTING.items()},
        }


# Singleton
_storage_router: UnifiedStorageRouter | None = None


def get_storage_router() -> UnifiedStorageRouter:
    """Get global storage router instance."""
    global _storage_router
    if _storage_router is None:
        _storage_router = UnifiedStorageRouter()
    return _storage_router


__all__ = [
    "STORAGE_ROUTING",
    "DataCategory",
    "StorageBackend",
    "StorageConfig",
    "UnifiedStorageRouter",
    "get_storage_router",
]
