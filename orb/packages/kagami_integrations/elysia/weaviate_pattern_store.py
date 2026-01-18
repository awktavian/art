"""Weaviate Pattern Store — Primary Storage for Stigmergy Patterns.

This module provides a Weaviate-backed store for stigmergy patterns,
serving as the canonical storage backend for the hive.

Benefits:
- Vector similarity for pattern matching
- Persistent storage with automatic backup
- Semantic search for related patterns
- E8 quantized embeddings
- No Redis dependency for learning workloads

Redis is still needed for:
- Real-time pub/sub
- Distributed locks
- Rate limiting
- Session state

But for stigmergy/learning/hive memory, Weaviate is canonical.

Created: December 7, 2025
Consolidated: December 7, 2025 - Uses BasePattern from kagami.core.unified_agents.patterns
"""

from __future__ import annotations

import logging
from typing import Any

from kagami.core.unified_agents.patterns.base_pattern import BasePattern

logger = logging.getLogger(__name__)


# Alias for backwards compatibility
WeaviatePattern = BasePattern


class WeaviatePatternStore:
    """Weaviate-backed pattern store for stigmergy.

    Canonical storage for RAG patterns with benefits:
    - Persistent storage in Weaviate Cloud
    - Vector similarity search
    - No Redis dependency for RAG workloads

    Usage:
        store = WeaviatePatternStore(weaviate_adapter)
        await store.connect()

        # Save pattern
        await store.save_pattern(pattern)

        # Load all patterns
        patterns = await store.load_patterns()

        # Search similar patterns
        similar = await store.search_similar("elysia.query", limit=5)
    """

    COLLECTION_NAME = "StigmergyPatterns"

    def __init__(self, weaviate_adapter: Any = None):
        """Initialize pattern store.

        Args:
            weaviate_adapter: WeaviateE8Adapter instance (optional)
        """
        self.weaviate = weaviate_adapter
        self._connected = False
        # Always-available fallback for tests/dev environments without Weaviate.
        self._in_memory_fallback: dict[tuple[str, str], WeaviatePattern] = {}

    async def connect(self) -> bool:
        """Connect and setup collection.

        Returns:
            True if connected successfully

        Notes:
            This method MUST NOT raise when Weaviate is unavailable in dev/test.
            It will transparently fall back to an in-memory store.
        """
        if self._connected:
            return True

        # Attempt Weaviate connection; fall back on any failure.
        if self.weaviate is None:
            try:
                from kagami_integrations.elysia.weaviate_e8_adapter import get_weaviate_adapter

                self.weaviate = get_weaviate_adapter()
            except Exception as e:
                logger.warning(f"Weaviate adapter unavailable, using in-memory fallback: {e}")
                self.weaviate = None

        try:
            if self.weaviate is not None:
                connected = await self.weaviate.connect()
                if connected and getattr(self.weaviate, "client", None) is not None:
                    await self._setup_collection()
                    self._connected = True
                    logger.info("✅ WeaviatePatternStore connected (Weaviate backend)")
                    return True
        except Exception as e:
            logger.warning(f"Weaviate connect failed, using in-memory fallback: {e}")

        # Fallback mode (still considered "connected" for store API)
        self.weaviate = None
        self._connected = True
        logger.info("✅ WeaviatePatternStore connected (in-memory fallback)")
        return True

    async def _setup_collection(self) -> None:
        """Setup patterns collection in Weaviate."""
        if not self.weaviate or not self.weaviate.client:
            return

        try:
            from weaviate.classes.config import Configure, DataType, Property
        except ImportError:
            logger.warning("Weaviate classes not available")
            return

        if self.weaviate.client.collections.exists(self.COLLECTION_NAME):
            return

        # Prefer v4.16+ config API: bring-your-own vectors.
        vector_config = None
        try:
            if hasattr(Configure, "Vectors") and hasattr(Configure.Vectors, "self_provided"):
                vector_config = Configure.Vectors.self_provided()
        except Exception:
            vector_config = None

        # Backwards compatible: Prefer no server-side vectorizers; we provide Kagami-aligned vectors.
        vectorizer_config = None
        for cfg_attr in ("Vectors", "Vectorizer"):
            try:
                cfg = getattr(Configure, cfg_attr, None)
                if cfg is not None and hasattr(cfg, "none"):
                    vectorizer_config = cfg.none()
                    break
            except Exception:
                continue
        if vectorizer_config is None:
            # Fallback (may require server-side modules)
            try:
                vectorizer_config = Configure.Vectorizer.text2vec_weaviate()
            except Exception:
                vectorizer_config = None

        base_kwargs = {
            "name": self.COLLECTION_NAME,
            "properties": [
                Property(name="action", data_type=DataType.TEXT),
                Property(name="domain", data_type=DataType.TEXT),
                Property(name="success_count", data_type=DataType.INT),
                Property(name="failure_count", data_type=DataType.INT),
                Property(name="avg_duration", data_type=DataType.NUMBER),
                Property(name="last_updated", data_type=DataType.NUMBER),
                Property(name="created_at", data_type=DataType.NUMBER),
                Property(name="access_count", data_type=DataType.INT),
                Property(name="heuristic_value", data_type=DataType.NUMBER),
                Property(name="common_params_json", data_type=DataType.TEXT),
                Property(name="error_types_json", data_type=DataType.TEXT),
                # BasePattern always emits this field; keep schema aligned to avoid insert failures.
                Property(name="trigger_config", data_type=DataType.TEXT),
            ],
        }

        attempts: list[dict[str, Any]] = []
        if vector_config is not None:
            attempts.append({"vector_config": vector_config})
        if vectorizer_config is not None:
            attempts.append({"vectorizer_config": vectorizer_config})
        attempts.append({})

        last_exc: Exception | None = None
        for extra in attempts:
            try:
                self.weaviate.client.collections.create(**base_kwargs, **extra)
                last_exc = None
                break
            except TypeError as exc:
                last_exc = exc
                continue
        if last_exc is not None:
            raise last_exc
        logger.info(f"Created collection: {self.COLLECTION_NAME}")

    async def save_pattern(self, pattern: WeaviatePattern) -> bool:
        """Save pattern to Weaviate.

        Args:
            pattern: Pattern to save

        Returns:
            True if saved

        Raises:
            ConnectionError: If not connected to Weaviate
        """
        if not self._connected:
            await self.connect()

        if not self.weaviate or not getattr(self.weaviate, "client", None):
            # In-memory fallback
            self._in_memory_fallback[(pattern.action, pattern.domain)] = pattern
            return True

        from weaviate.classes.query import Filter

        collection = (
            self.weaviate.client.collections.use(self.COLLECTION_NAME)
            if hasattr(self.weaviate.client.collections, "use")
            else self.weaviate.client.collections.get(self.COLLECTION_NAME)
        )

        # Filter properties to schema-supported fields (keeps backwards compat).
        props = pattern.to_dict()
        try:
            schema = collection.config.get()
            allowed = {p.name for p in getattr(schema, "properties", [])}
            props = {k: v for k, v in props.items() if k in allowed}
        except Exception:
            pass

        # Provide a vector for similarity search if possible.
        vec = None
        try:
            if hasattr(self.weaviate, "_try_embed_text"):
                emb = self.weaviate._try_embed_text(f"{pattern.action} {pattern.domain}")
                if emb is not None:
                    vec = emb.flatten().tolist()
        except Exception:
            vec = None

        # Check if exists
        results = collection.query.fetch_objects(
            filters=(
                Filter.by_property("action").equal(pattern.action)
                & Filter.by_property("domain").equal(pattern.domain)
            ),
            limit=1,
        )

        if results.objects:
            # Update existing
            obj_uuid = results.objects[0].uuid
            # Vector update support varies by client; best-effort.
            try:
                from weaviate.classes.data import Vector  # type: ignore[attr-defined]

                if vec is not None:
                    collection.data.update(
                        uuid=obj_uuid, properties=props, vector=Vector(vector=vec)
                    )
                else:
                    collection.data.update(uuid=obj_uuid, properties=props)
            except Exception:
                collection.data.update(uuid=obj_uuid, properties=props)
        else:
            # Create new
            if vec is not None:
                try:
                    from weaviate.classes.data import Vector  # type: ignore[attr-defined]

                    collection.data.insert(props, vector=Vector(vector=vec))
                except Exception:
                    try:
                        collection.data.insert(props, vector=vec)
                    except Exception:
                        collection.data.insert(props)
            else:
                collection.data.insert(props)

        return True

    async def save_patterns_batch(self, patterns: list[WeaviatePattern]) -> int:
        """Save multiple patterns in batch (S⁷ PARALLEL optimization).

        Uses Weaviate's batch API for efficient bulk writes.

        Args:
            patterns: List of patterns to save

        Returns:
            Number of patterns saved

        Raises:
            ConnectionError: If not connected to Weaviate
        """
        if not self._connected:
            await self.connect()

        if not self.weaviate or not getattr(self.weaviate, "client", None):
            # In-memory fallback
            for p in patterns:
                self._in_memory_fallback[(p.action, p.domain)] = p
            return len(patterns)

        # Correctness > raw throughput: batch-save should preserve upsert semantics.
        # We therefore delegate to save_pattern() (which updates or inserts).
        saved = 0
        for pattern in patterns:
            if await self.save_pattern(pattern):
                saved += 1
        logger.info(f"Saved {saved}/{len(patterns)} patterns to Weaviate")
        return saved

    async def load_patterns(self) -> dict[tuple[str, str], WeaviatePattern]:
        """Load all patterns from Weaviate.

        Returns:
            Dict of (action, domain) -> WeaviatePattern

        Raises:
            ConnectionError: If not connected to Weaviate
        """
        if not self._connected:
            await self.connect()

        if not self.weaviate or not getattr(self.weaviate, "client", None):
            # In-memory fallback
            return dict(self._in_memory_fallback)

        collection = (
            self.weaviate.client.collections.use(self.COLLECTION_NAME)
            if hasattr(self.weaviate.client.collections, "use")
            else self.weaviate.client.collections.get(self.COLLECTION_NAME)
        )
        results = collection.query.fetch_objects(limit=10000)

        patterns = {}
        for obj in results.objects:
            pattern = WeaviatePattern.from_dict(obj.properties)
            key = (pattern.action, pattern.domain)
            patterns[key] = pattern

        logger.info(f"Loaded {len(patterns)} patterns from Weaviate")
        return patterns

    async def search_similar(
        self,
        action_prefix: str,
        domain: str | None = None,
        limit: int = 10,
    ) -> list[WeaviatePattern]:
        """Search for similar patterns.

        Args:
            action_prefix: Action prefix to match
            domain: Optional domain filter
            limit: Max results

        Returns:
            List of matching patterns

        Raises:
            ConnectionError: If not connected to Weaviate
        """
        if not self._connected:
            await self.connect()

        if not self.weaviate or not getattr(self.weaviate, "client", None):
            # In-memory fallback: simple prefix filter
            matches: list[WeaviatePattern] = []
            for (action, _domain), pat in self._in_memory_fallback.items():
                if action.startswith(action_prefix) and (domain is None or pat.domain == domain):
                    matches.append(pat)
            return matches[:limit]

        collection = (
            self.weaviate.client.collections.use(self.COLLECTION_NAME)
            if hasattr(self.weaviate.client.collections, "use")
            else self.weaviate.client.collections.get(self.COLLECTION_NAME)
        )

        # Prefer Kagami-native vector search (near_vector). Fall back to near_text.
        results = None
        try:
            emb = None
            if hasattr(self.weaviate, "_try_embed_text"):
                emb = self.weaviate._try_embed_text(action_prefix)
            if emb is not None:
                from weaviate.classes.query import Filter

                filters = None
                if domain:
                    filters = Filter.by_property("domain").equal(domain)
                results = collection.query.near_vector(
                    near_vector=emb.flatten().tolist(),
                    limit=limit,
                    filters=filters,
                )
        except Exception:
            results = None

        if results is None:
            # Fallback: server-side vectorizer (may be unavailable if Vectorizer.none())
            try:
                from weaviate.classes.query import Filter

                filters = None
                if domain:
                    filters = Filter.by_property("domain").equal(domain)
                results = collection.query.near_text(
                    query=action_prefix, limit=limit, filters=filters
                )
            except Exception:
                results = None

        if results is None:
            return []

        matches = []
        for obj in results.objects:
            pattern = WeaviatePattern.from_dict(obj.properties)
            if domain is None or pattern.domain == domain:
                matches.append(pattern)

        return matches[:limit]

    async def delete_pattern(self, action: str, domain: str) -> bool:
        """Delete a pattern.

        Args:
            action: Action name
            domain: Domain name

        Returns:
            True if deleted

        Raises:
            ConnectionError: If not connected to Weaviate
        """
        if not self.weaviate or not getattr(self.weaviate, "client", None):
            self._in_memory_fallback.pop((action, domain), None)
            return True

        from weaviate.classes.query import Filter

        collection = (
            self.weaviate.client.collections.use(self.COLLECTION_NAME)
            if hasattr(self.weaviate.client.collections, "use")
            else self.weaviate.client.collections.get(self.COLLECTION_NAME)
        )
        collection.data.delete_many(
            where=Filter.by_property("action").equal(action)
            & Filter.by_property("domain").equal(domain)
        )
        return True

    async def get_pattern_summary(self) -> dict[str, Any]:
        """Get summary of stored patterns.

        Returns:
            Summary statistics dict
        """
        if not self._connected or not self.weaviate or not getattr(self.weaviate, "client", None):
            # Fallback summary
            pattern_list = list(self._in_memory_fallback.values())
            if not pattern_list:
                return {
                    "total_patterns": 0,
                    "high_success_patterns": 0,
                    "high_failure_patterns": 0,
                    "avg_confidence": 0.0,
                    "storage_backend": "in_memory",
                    "connected": self._connected,
                }
            high_success = sum(
                1
                for p in pattern_list
                if p.bayesian_success_rate > 0.7 and p.bayesian_confidence > 0.5
            )
            high_failure = sum(
                1
                for p in pattern_list
                if p.bayesian_success_rate < 0.3 and p.bayesian_confidence > 0.5
            )
            avg_confidence = sum(p.bayesian_confidence for p in pattern_list) / len(pattern_list)
            return {
                "total_patterns": len(pattern_list),
                "high_success_patterns": high_success,
                "high_failure_patterns": high_failure,
                "avg_confidence": avg_confidence,
                "storage_backend": "in_memory",
                "connected": self._connected,
            }

        try:
            patterns = await self.load_patterns()
            pattern_list = list(patterns.values())

            if not pattern_list:
                return {
                    "total_patterns": 0,
                    "high_success_patterns": 0,
                    "high_failure_patterns": 0,
                    "avg_confidence": 0.0,
                    "storage_backend": "weaviate",
                    "connected": True,
                }

            high_success = sum(
                1
                for p in pattern_list
                if p.bayesian_success_rate > 0.7 and p.bayesian_confidence > 0.5
            )
            high_failure = sum(
                1
                for p in pattern_list
                if p.bayesian_success_rate < 0.3 and p.bayesian_confidence > 0.5
            )
            avg_confidence = sum(p.bayesian_confidence for p in pattern_list) / len(pattern_list)

            return {
                "total_patterns": len(pattern_list),
                "high_success_patterns": high_success,
                "high_failure_patterns": high_failure,
                "avg_confidence": avg_confidence,
                "storage_backend": "weaviate",
                "connected": True,
            }
        except Exception as e:
            logger.warning(f"Failed to get pattern summary: {e}")
            return {
                "total_patterns": 0,
                "error": str(e),
                "storage_backend": "weaviate",
                "connected": self._connected,
            }


# Singleton instance
_pattern_store: WeaviatePatternStore | None = None


def get_weaviate_pattern_store() -> WeaviatePatternStore:
    """Get global pattern store instance."""
    global _pattern_store
    if _pattern_store is None:
        _pattern_store = WeaviatePatternStore()
    return _pattern_store


__all__ = [
    "BasePattern",  # Consolidated pattern class
    "WeaviatePattern",  # Alias for BasePattern (backwards compatibility)
    "WeaviatePatternStore",
    "get_weaviate_pattern_store",
]
