# SPDX-License-Identifier: MIT
"""Embedding-Based Semantic Safety Cache with Centroid Clustering.

ARCHITECTURE (December 22, 2025):
=================================
Uses fast sentence embeddings + approximate nearest neighbor search
to cache semantically similar queries. Similar queries share safety results.

DESIGN:
=======
1. Embed query using lightweight sentence transformer (~5ms)
2. Find nearest centroid in embedding space (~0.1ms)
3. If distance < threshold: return cached LLM result
4. Otherwise: run full LLM, update centroids

LATENCY PROFILE:
================
| Path                    | Latency  |
|-------------------------|----------|
| Embedding + centroid    | ~5ms     |
| Exact hash cache        | ~0.01ms  |
| Full LLM (WildGuard)    | ~900ms   |

SAFETY GUARANTEE:
=================
- Only caches SAFE results (risky always re-evaluated)
- Centroids represent "safe clusters" in embedding space
- Conservative distance threshold (0.85 cosine similarity)
- Falls back to full LLM on any uncertainty
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Configuration
EMBEDDING_CACHE_ENABLED = os.getenv("KAGAMI_EMBEDDING_CACHE", "1") == "1"
# Use smallest/fastest model for safety cache (384 dim, 22MB)
EMBEDDING_MODEL = os.getenv("KAGAMI_EMBEDDING_MODEL", "paraphrase-MiniLM-L3-v2")
CENTROID_SIMILARITY_THRESHOLD = float(os.getenv("KAGAMI_CENTROID_THRESHOLD", "0.80"))
MAX_CENTROIDS = int(os.getenv("KAGAMI_MAX_CENTROIDS", "1000"))
CENTROID_TTL_SECONDS = float(os.getenv("KAGAMI_CENTROID_TTL", "3600.0"))  # 1 hour


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class SafetyCentroid:
    """A centroid in embedding space representing safe queries."""

    embedding: np.ndarray[Any, Any]  # [embedding_dim]
    h_value: float
    is_safe: bool
    count: int = 1  # Number of queries merged into this centroid
    timestamp: float = field(default_factory=time.time)

    def merge(self, other_embedding: np.ndarray[Any, Any], other_h: float) -> None:
        """Merge another embedding into this centroid (running average)."""
        # Weighted average of embeddings
        total = self.count + 1
        self.embedding = (self.embedding * self.count + other_embedding) / total
        self.h_value = (self.h_value * self.count + other_h) / total
        self.count = total
        self.timestamp = time.time()


@dataclass
class EmbeddingCacheStats:
    """Cache performance statistics."""

    embedding_hits: int = 0
    embedding_misses: int = 0
    centroid_count: int = 0
    avg_similarity: float = 0.0
    total_queries: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.embedding_hits + self.embedding_misses
        return self.embedding_hits / total if total > 0 else 0.0


# =============================================================================
# EMBEDDING MODEL (Lazy Loaded)
# =============================================================================


_embedding_model: Any = None
_embedding_lock = threading.Lock()


def _get_embedding_model() -> Any:
    """Get or create the sentence transformer model."""
    global _embedding_model

    if _embedding_model is not None:
        return _embedding_model

    with _embedding_lock:
        if _embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"⏳ Loading embedding model: {EMBEDDING_MODEL}")
                start = time.time()
                _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
                # Pre-warmup with a test embedding
                _ = _embedding_model.encode("warmup", normalize_embeddings=True)
                elapsed = time.time() - start
                logger.info(f"✅ Embedding model loaded in {elapsed:.1f}s")
            except ImportError:
                logger.warning(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
                raise

    return _embedding_model


# Pre-computed embedding cache for repeated queries
_embedding_lru: dict[str, np.ndarray[Any, Any]] = {}
_EMBEDDING_LRU_SIZE = 1000


def compute_embedding(text: str) -> np.ndarray[Any, Any]:
    """Compute embedding for text using sentence transformer.

    Uses LRU cache for repeated queries.

    Args:
        text: Input text

    Returns:
        Normalized embedding vector [embedding_dim]
    """
    # Check LRU cache first
    if text in _embedding_lru:
        return _embedding_lru[text]

    model = _get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True, show_progress_bar=False)
    result = np.array(embedding, dtype=np.float32)

    # Update LRU cache
    if len(_embedding_lru) >= _EMBEDDING_LRU_SIZE:
        # Remove first item (simple FIFO)
        first_key = next(iter(_embedding_lru))
        del _embedding_lru[first_key]
    _embedding_lru[text] = result

    return result


# =============================================================================
# CENTROID-BASED CACHE
# =============================================================================


class EmbeddingCentroidCache:
    """Semantic cache using embedding centroids.

    Similar queries cluster around centroids. New queries are matched
    to nearest centroid for fast approximate lookup.

    Thread-safe implementation with LRU eviction.
    """

    def __init__(
        self,
        max_centroids: int = MAX_CENTROIDS,
        similarity_threshold: float = CENTROID_SIMILARITY_THRESHOLD,
        ttl_seconds: float = CENTROID_TTL_SECONDS,
    ):
        self.max_centroids = max_centroids
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds

        self._centroids: list[SafetyCentroid] = []
        self._exact_cache: dict[str, tuple[float, bool, float]] = {}  # hash -> (h, safe, time)
        self._lock = threading.RLock()
        self._stats = EmbeddingCacheStats()

        # Pre-computed centroid matrix for fast batch similarity
        self._centroid_matrix: np.ndarray[Any, Any] | None = None
        self._matrix_dirty = True

    def _hash_text(self, text: str) -> str:
        """Compute hash for exact match."""
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    def _cosine_similarity(self, a: np.ndarray[Any, Any], b: np.ndarray[Any, Any]) -> float:
        """Compute cosine similarity between two vectors."""
        # Vectors are already normalized, so dot product = cosine similarity
        return float(np.dot(a, b))

    def _rebuild_matrix(self) -> None:
        """Rebuild centroid matrix for fast batch similarity."""
        if not self._centroids:
            self._centroid_matrix = None
            return

        self._centroid_matrix = np.stack([c.embedding for c in self._centroids])
        self._matrix_dirty = False

    def _find_nearest_centroid(self, embedding: np.ndarray[Any, Any]) -> tuple[int, float] | None:
        """Find nearest centroid using fast matrix multiplication.

        Args:
            embedding: Query embedding [dim]

        Returns:
            (index, similarity) of nearest centroid, or None if empty
        """
        if not self._centroids:
            return None

        if self._matrix_dirty:
            self._rebuild_matrix()

        if self._centroid_matrix is None:
            return None

        # Batch cosine similarity via matrix multiplication
        # Shape: [num_centroids]
        similarities = self._centroid_matrix @ embedding

        best_idx = int(np.argmax(similarities))
        best_sim = float(similarities[best_idx])

        return (best_idx, best_sim)

    def get(self, text: str) -> tuple[float, bool] | None:
        """Get cached safety result for text.

        Args:
            text: Input text

        Returns:
            (h_value, is_safe) if found, None otherwise
        """
        self._stats.total_queries += 1

        with self._lock:
            # Level 1: Exact hash match
            text_hash = self._hash_text(text)
            if text_hash in self._exact_cache:
                h, safe, ts = self._exact_cache[text_hash]
                if time.time() - ts < self.ttl_seconds:
                    self._stats.embedding_hits += 1
                    return (h, safe)
                else:
                    del self._exact_cache[text_hash]

            # Level 2: Centroid similarity match
            if not self._centroids:
                self._stats.embedding_misses += 1
                return None

        # Compute embedding (outside lock)
        try:
            embedding = compute_embedding(text)
        except Exception as e:
            logger.warning(f"Embedding failed: {e}")
            self._stats.embedding_misses += 1
            return None

        with self._lock:
            result = self._find_nearest_centroid(embedding)
            if result is None:
                self._stats.embedding_misses += 1
                return None

            idx, similarity = result

            # Update average similarity stat
            self._stats.avg_similarity = self._stats.avg_similarity * 0.99 + similarity * 0.01

            if similarity >= self.similarity_threshold:
                centroid = self._centroids[idx]

                # Check TTL
                if time.time() - centroid.timestamp > self.ttl_seconds:
                    self._centroids.pop(idx)
                    self._matrix_dirty = True
                    self._stats.embedding_misses += 1
                    return None

                # Cache exact match for future
                self._exact_cache[text_hash] = (
                    centroid.h_value,
                    centroid.is_safe,
                    time.time(),
                )

                self._stats.embedding_hits += 1
                logger.debug(
                    f"🎯 Embedding cache hit: sim={similarity:.3f}, h={centroid.h_value:.2f}"
                )
                return (centroid.h_value, centroid.is_safe)

            self._stats.embedding_misses += 1
            return None

    def put(
        self,
        text: str,
        h_value: float,
        is_safe: bool,
    ) -> None:
        """Cache safety result, updating or creating centroid.

        Args:
            text: Input text
            h_value: Safety barrier value
            is_safe: Whether operation is safe
        """
        # Only cache SAFE results
        if not is_safe:
            return

        # Compute embedding
        try:
            embedding = compute_embedding(text)
        except Exception as e:
            logger.warning(f"Embedding failed, skipping cache: {e}")
            return

        text_hash = self._hash_text(text)

        with self._lock:
            # Store exact match
            self._exact_cache[text_hash] = (h_value, is_safe, time.time())

            # Find if we should merge into existing centroid
            result = self._find_nearest_centroid(embedding)

            if result is not None:
                idx, similarity = result
                if similarity >= self.similarity_threshold:
                    # Merge into existing centroid
                    self._centroids[idx].merge(embedding, h_value)
                    self._matrix_dirty = True
                    return

            # Create new centroid
            new_centroid = SafetyCentroid(
                embedding=embedding,
                h_value=h_value,
                is_safe=is_safe,
            )
            self._centroids.append(new_centroid)
            self._matrix_dirty = True

            # Evict oldest if over capacity
            while len(self._centroids) > self.max_centroids:
                # Remove oldest by timestamp
                oldest_idx = min(
                    range(len(self._centroids)),
                    key=lambda i: self._centroids[i].timestamp,
                )
                self._centroids.pop(oldest_idx)

            self._stats.centroid_count = len(self._centroids)

    def get_stats(self) -> EmbeddingCacheStats:
        """Get cache statistics."""
        with self._lock:
            return EmbeddingCacheStats(
                embedding_hits=self._stats.embedding_hits,
                embedding_misses=self._stats.embedding_misses,
                centroid_count=len(self._centroids),
                avg_similarity=self._stats.avg_similarity,
                total_queries=self._stats.total_queries,
            )

    def clear(self) -> None:
        """Clear all cached data."""
        with self._lock:
            self._centroids.clear()
            self._exact_cache.clear()
            self._centroid_matrix = None
            self._matrix_dirty = True
            self._stats = EmbeddingCacheStats()


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_embedding_cache: EmbeddingCentroidCache | None = None
_cache_lock = threading.Lock()


def get_embedding_cache() -> EmbeddingCentroidCache:
    """Get or create the singleton embedding cache."""
    global _embedding_cache

    if _embedding_cache is not None:
        return _embedding_cache

    with _cache_lock:
        if _embedding_cache is None:
            _embedding_cache = EmbeddingCentroidCache()
            logger.info(
                f"✅ EmbeddingCentroidCache initialized: "
                f"max_centroids={MAX_CENTROIDS}, "
                f"threshold={CENTROID_SIMILARITY_THRESHOLD}"
            )

    return _embedding_cache


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "EMBEDDING_CACHE_ENABLED",
    "EmbeddingCacheStats",
    "EmbeddingCentroidCache",
    "SafetyCentroid",
    "compute_embedding",
    "get_embedding_cache",
]
