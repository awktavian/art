"""Identity Embedding Cache for Real-Time Face Recognition.

Fast Redis-backed cache for identity embeddings used in real-time
camera face recognition. Optimized for sub-millisecond lookup.

Key Features:
- Bulk load all embeddings on startup
- Background refresh every hour
- L1 memory cache + L2 Redis
- Cosine similarity matching built-in

Colony: Nexus (e₄) — Integration
Safety: h(x) ≥ 0 — Biometric data handled securely

Usage:
    cache = IdentityCache()
    await cache.initialize()

    # Match a face embedding
    match = await cache.match_face(embedding, threshold=0.6)
    if match:
        print(f"Identified: {match.name} ({match.confidence:.2f})")
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Redis key patterns
REDIS_IDENTITY_PREFIX = "kagami:identity"
REDIS_FACE_KEY = f"{REDIS_IDENTITY_PREFIX}:face"
REDIS_VOICE_KEY = f"{REDIS_IDENTITY_PREFIX}:voice"
REDIS_ALL_IDS_KEY = f"{REDIS_IDENTITY_PREFIX}:all_ids"
REDIS_METADATA_KEY = f"{REDIS_IDENTITY_PREFIX}:metadata"

# Cache configuration
DEFAULT_TTL = 3600  # 1 hour
REFRESH_INTERVAL = 3000  # 50 minutes (refresh before TTL)
FACE_EMBEDDING_DIM = 512
VOICE_EMBEDDING_DIM = 192


@dataclass
class IdentityMatch:
    """Result of identity matching."""

    identity_id: str
    name: str | None
    confidence: float
    embedding_type: str  # face, voice

    def to_dict(self) -> dict:
        return {
            "identity_id": self.identity_id,
            "name": self.name,
            "confidence": self.confidence,
            "embedding_type": self.embedding_type,
        }


@dataclass
class CachedIdentity:
    """Cached identity with embeddings."""

    identity_id: str
    name: str | None
    face_embedding: np.ndarray | None
    voice_embedding: np.ndarray | None
    face_threshold: float = 0.6
    voice_threshold: float = 0.7
    last_updated: float = 0.0


class IdentityCache:
    """Fast identity embedding cache for real-time recognition.

    Two-tier cache:
    - L1: In-memory dict for sub-ms lookups
    - L2: Redis for persistence across restarts
    """

    def __init__(
        self,
        ttl: int = DEFAULT_TTL,
        refresh_interval: int = REFRESH_INTERVAL,
    ):
        """Initialize identity cache.

        Args:
            ttl: Cache TTL in seconds
            refresh_interval: Background refresh interval
        """
        self.ttl = ttl
        self.refresh_interval = refresh_interval

        # L1: In-memory cache
        self._identities: dict[str, CachedIdentity] = {}
        self._face_embeddings: dict[str, np.ndarray] = {}
        self._voice_embeddings: dict[str, np.ndarray] = {}

        # Precomputed normalized embeddings for fast cosine similarity
        self._face_norms: dict[str, np.ndarray] = {}
        self._voice_norms: dict[str, np.ndarray] = {}

        # Redis client
        self._redis: Any = None
        self._initialized = False

        # Background tasks
        self._refresh_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """Initialize cache and load embeddings."""
        if self._initialized:
            return

        try:
            from kagami.core.caching.redis import RedisClientFactory

            self._redis = RedisClientFactory.get_client(
                purpose="default",
                async_mode=True,
                decode_responses=True,
            )

            # Load from Redis first (fast)
            await self._load_from_redis()

            # If empty, load from database
            if not self._identities:
                await self._load_from_database()

            # Start background refresh
            self._refresh_task = asyncio.create_task(self._background_refresh())

            self._initialized = True
            logger.info(f"IdentityCache initialized with {len(self._identities)} identities")

        except Exception as e:
            logger.warning(f"Failed to initialize Redis cache: {e}")
            # Fall back to database-only mode
            await self._load_from_database()
            self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown cache and cancel background tasks."""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

    async def _load_from_redis(self) -> None:
        """Load all embeddings from Redis."""
        if not self._redis:
            return

        try:
            # Get all identity IDs
            identity_ids = await self._redis.smembers(REDIS_ALL_IDS_KEY)

            if not identity_ids:
                return

            # Load all identities in parallel
            if identity_ids:
                await asyncio.gather(
                    *[self._load_identity_from_redis(identity_id) for identity_id in identity_ids],
                    return_exceptions=True,
                )

            logger.info(f"Loaded {len(self._identities)} identities from Redis")

        except Exception as e:
            logger.warning(f"Failed to load from Redis: {e}")

    async def _load_identity_from_redis(self, identity_id: str) -> None:
        """Load single identity from Redis using batched mget."""
        if not self._redis:
            return

        try:
            # Batch get all keys for this identity in single round-trip
            meta_key = f"{REDIS_METADATA_KEY}:{identity_id}"
            face_key = f"{REDIS_FACE_KEY}:{identity_id}"
            voice_key = f"{REDIS_VOICE_KEY}:{identity_id}"

            # Use mget for batch retrieval (single round-trip)
            results = await self._redis.mget(meta_key, face_key, voice_key)
            meta_json, face_json, voice_json = results

            if not meta_json:
                return

            metadata = json.loads(meta_json)

            face_embedding = None
            voice_embedding = None

            if face_json:
                face_embedding = np.array(json.loads(face_json), dtype=np.float32)

            if voice_json:
                voice_embedding = np.array(json.loads(voice_json), dtype=np.float32)

            # Create cached identity
            cached = CachedIdentity(
                identity_id=identity_id,
                name=metadata.get("name"),
                face_embedding=face_embedding,
                voice_embedding=voice_embedding,
                face_threshold=metadata.get("face_threshold", 0.6),
                voice_threshold=metadata.get("voice_threshold", 0.7),
                last_updated=time.time(),
            )

            self._add_to_memory_cache(cached)

        except Exception as e:
            logger.warning(f"Failed to load identity {identity_id} from Redis: {e}")

    async def _load_from_database(self) -> None:
        """Load embeddings from PostgreSQL database."""
        try:
            from kagami.core.database.models import Identity
            from kagami.core.database.session import get_async_session

            async with get_async_session() as session:
                from sqlalchemy import select

                # Get all identities with embeddings
                stmt = select(Identity).where(
                    (Identity.face_embedding.isnot(None)) | (Identity.voice_embedding.isnot(None))
                )

                result = await session.execute(stmt)
                identities = result.scalars().all()

                for identity in identities:
                    face_embedding = None
                    voice_embedding = None

                    if identity.face_embedding:
                        face_embedding = np.array(identity.face_embedding, dtype=np.float32)

                    if identity.voice_embedding:
                        voice_embedding = np.array(identity.voice_embedding, dtype=np.float32)

                    cached = CachedIdentity(
                        identity_id=identity.identity_id,
                        name=identity.name,
                        face_embedding=face_embedding,
                        voice_embedding=voice_embedding,
                        face_threshold=identity.face_threshold or 0.6,
                        voice_threshold=identity.voice_threshold or 0.7,
                        last_updated=time.time(),
                    )

                    self._add_to_memory_cache(cached)

                    # Also save to Redis
                    await self._save_to_redis(cached)

                logger.info(f"Loaded {len(identities)} identities from database")

        except Exception as e:
            logger.warning(f"Failed to load from database: {e}")

    def _add_to_memory_cache(self, identity: CachedIdentity) -> None:
        """Add identity to in-memory cache with precomputed norms."""
        self._identities[identity.identity_id] = identity

        if identity.face_embedding is not None:
            self._face_embeddings[identity.identity_id] = identity.face_embedding
            # Precompute normalized embedding for fast cosine similarity
            norm = np.linalg.norm(identity.face_embedding)
            if norm > 0:
                self._face_norms[identity.identity_id] = identity.face_embedding / norm

        if identity.voice_embedding is not None:
            self._voice_embeddings[identity.identity_id] = identity.voice_embedding
            norm = np.linalg.norm(identity.voice_embedding)
            if norm > 0:
                self._voice_norms[identity.identity_id] = identity.voice_embedding / norm

    async def _save_to_redis(self, identity: CachedIdentity) -> None:
        """Save identity to Redis cache."""
        if not self._redis:
            return

        try:
            # Save metadata
            metadata = {
                "name": identity.name,
                "face_threshold": identity.face_threshold,
                "voice_threshold": identity.voice_threshold,
            }
            meta_key = f"{REDIS_METADATA_KEY}:{identity.identity_id}"
            await self._redis.setex(meta_key, self.ttl, json.dumps(metadata))

            # Save embeddings
            if identity.face_embedding is not None:
                face_key = f"{REDIS_FACE_KEY}:{identity.identity_id}"
                await self._redis.setex(
                    face_key, self.ttl, json.dumps(identity.face_embedding.tolist())
                )

            if identity.voice_embedding is not None:
                voice_key = f"{REDIS_VOICE_KEY}:{identity.identity_id}"
                await self._redis.setex(
                    voice_key, self.ttl, json.dumps(identity.voice_embedding.tolist())
                )

            # Add to ID set
            await self._redis.sadd(REDIS_ALL_IDS_KEY, identity.identity_id)

        except Exception as e:
            logger.warning(f"Failed to save to Redis: {e}")

    async def _background_refresh(self) -> None:
        """Background task to refresh cache."""
        while True:
            try:
                await asyncio.sleep(self.refresh_interval)

                # Reload from database
                await self._load_from_database()

                logger.debug(f"Refreshed identity cache: {len(self._identities)} identities")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache refresh error: {e}")
                await asyncio.sleep(60)  # Wait before retry

    def match_face(
        self,
        embedding: np.ndarray,
        threshold: float | None = None,
    ) -> IdentityMatch | None:
        """Match face embedding against cached identities.

        Fast O(n) scan with precomputed normalized embeddings.

        Args:
            embedding: 512-dim face embedding
            threshold: Optional override for confidence threshold

        Returns:
            IdentityMatch if found, None otherwise
        """
        if not self._face_norms:
            return None

        # Normalize query embedding
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return None
        query_norm = embedding / norm

        best_match: tuple[str, float] | None = None

        for identity_id, cached_norm in self._face_norms.items():
            # Cosine similarity via dot product of normalized vectors
            similarity = float(np.dot(query_norm, cached_norm))

            # Get threshold
            identity = self._identities.get(identity_id)
            identity_threshold = (
                threshold
                if threshold is not None
                else (identity.face_threshold if identity else 0.6)
            )

            if similarity >= identity_threshold:
                if best_match is None or similarity > best_match[1]:
                    best_match = (identity_id, similarity)

        if best_match:
            identity = self._identities.get(best_match[0])
            return IdentityMatch(
                identity_id=best_match[0],
                name=identity.name if identity else None,
                confidence=best_match[1],
                embedding_type="face",
            )

        return None

    def match_voice(
        self,
        embedding: np.ndarray,
        threshold: float | None = None,
    ) -> IdentityMatch | None:
        """Match voice embedding against cached identities.

        Args:
            embedding: 192-dim voice embedding
            threshold: Optional override for confidence threshold

        Returns:
            IdentityMatch if found, None otherwise
        """
        if not self._voice_norms:
            return None

        # Normalize query embedding
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return None
        query_norm = embedding / norm

        best_match: tuple[str, float] | None = None

        for identity_id, cached_norm in self._voice_norms.items():
            similarity = float(np.dot(query_norm, cached_norm))

            identity = self._identities.get(identity_id)
            identity_threshold = (
                threshold
                if threshold is not None
                else (identity.voice_threshold if identity else 0.7)
            )

            if similarity >= identity_threshold:
                if best_match is None or similarity > best_match[1]:
                    best_match = (identity_id, similarity)

        if best_match:
            identity = self._identities.get(best_match[0])
            return IdentityMatch(
                identity_id=best_match[0],
                name=identity.name if identity else None,
                confidence=best_match[1],
                embedding_type="voice",
            )

        return None

    async def add_identity(
        self,
        identity_id: str,
        name: str | None = None,
        face_embedding: np.ndarray | None = None,
        voice_embedding: np.ndarray | None = None,
        face_threshold: float = 0.6,
        voice_threshold: float = 0.7,
    ) -> None:
        """Add or update identity in cache.

        Args:
            identity_id: Unique identity ID
            name: Display name
            face_embedding: 512-dim face embedding
            voice_embedding: 192-dim voice embedding
            face_threshold: Face confidence threshold
            voice_threshold: Voice confidence threshold
        """
        cached = CachedIdentity(
            identity_id=identity_id,
            name=name,
            face_embedding=face_embedding,
            voice_embedding=voice_embedding,
            face_threshold=face_threshold,
            voice_threshold=voice_threshold,
            last_updated=time.time(),
        )

        self._add_to_memory_cache(cached)
        await self._save_to_redis(cached)

        logger.debug(f"Added identity to cache: {identity_id}")

    async def remove_identity(self, identity_id: str) -> None:
        """Remove identity from cache.

        Args:
            identity_id: Identity to remove
        """
        # Remove from memory
        self._identities.pop(identity_id, None)
        self._face_embeddings.pop(identity_id, None)
        self._voice_embeddings.pop(identity_id, None)
        self._face_norms.pop(identity_id, None)
        self._voice_norms.pop(identity_id, None)

        # Remove from Redis
        if self._redis:
            try:
                await self._redis.delete(f"{REDIS_METADATA_KEY}:{identity_id}")
                await self._redis.delete(f"{REDIS_FACE_KEY}:{identity_id}")
                await self._redis.delete(f"{REDIS_VOICE_KEY}:{identity_id}")
                await self._redis.srem(REDIS_ALL_IDS_KEY, identity_id)
            except Exception as e:
                logger.warning(f"Failed to remove from Redis: {e}")

        logger.debug(f"Removed identity from cache: {identity_id}")

    def get_identity(self, identity_id: str) -> CachedIdentity | None:
        """Get cached identity by ID.

        Args:
            identity_id: Identity ID

        Returns:
            CachedIdentity or None
        """
        return self._identities.get(identity_id)

    def get_all_identity_ids(self) -> list[str]:
        """Get all cached identity IDs.

        Returns:
            List of identity IDs
        """
        return list(self._identities.keys())

    @property
    def identity_count(self) -> int:
        """Number of cached identities."""
        return len(self._identities)

    @property
    def face_count(self) -> int:
        """Number of identities with face embeddings."""
        return len(self._face_embeddings)

    @property
    def voice_count(self) -> int:
        """Number of identities with voice embeddings."""
        return len(self._voice_embeddings)


# Singleton instance
_identity_cache: IdentityCache | None = None


async def get_identity_cache() -> IdentityCache:
    """Get singleton identity cache instance.

    Returns:
        Initialized IdentityCache
    """
    global _identity_cache

    if _identity_cache is None:
        _identity_cache = IdentityCache()
        await _identity_cache.initialize()

    return _identity_cache
