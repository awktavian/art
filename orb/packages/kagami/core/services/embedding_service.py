"""Kagami Embedding Service — Semantic Embeddings via Sentence-Transformers.

ALL-IN on sentence-transformers/all-MiniLM-L6-v2:
- Fast (384D, ~20ms per embed)
- Semantic (trained on 1B+ sentence pairs)
- CPU-friendly (no GPU required)
- Well-tested (industry standard)

NO FALLBACKS. NO WORLD MODEL DEPENDENCY. JUST OPTIMAL EMBEDDINGS.

Created: November 30, 2025
Simplified: December 30, 2025 — Removed World Model complexity
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# The optimal model - fast, semantic, well-tested
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


@dataclass
class EmbeddingServiceConfig:
    """Configuration for Embedding Service."""

    model_name: str = MODEL_NAME
    embedding_dim: int = EMBEDDING_DIM
    cache_size: int = 10000
    cache_ttl_seconds: int = 3600


# =============================================================================
# EMBEDDING SERVICE
# =============================================================================

# Use centralized caching
from kagami.core.caching import MemoryCache


class EmbeddingService:
    """Semantic Embedding Service via sentence-transformers.

    Uses all-MiniLM-L6-v2 — the optimal choice for:
    - Fast inference (~20ms per text)
    - High-quality semantic embeddings
    - CPU-friendly (works everywhere)

    Usage:
        service = get_embedding_service()
        vec = service.embed_text("Hello world")  # Returns 384D numpy array
        batch = service.embed_batch(["Hello", "World"])  # Returns [2, 384]
    """

    def __init__(self, config: EmbeddingServiceConfig | None = None) -> None:
        self.config = config or EmbeddingServiceConfig()
        self.embedding_dim = self.config.embedding_dim

        # State
        self._initialized = False
        self._sentence_transformer: Any = None
        self._init_lock = threading.Lock()

        # Cache
        self._cache = MemoryCache(
            name="embedding_cache",
            max_size=self.config.cache_size,
            default_ttl=float(self.config.cache_ttl_seconds),
        )

        # Metrics
        self._embed_count = 0
        self._cache_hits = 0
        self._embed_latency_sum = 0.0

        logger.info(f"EmbeddingService created: {self.config.model_name}")

    @property
    def model_name(self) -> str:
        """Return model name."""
        return self.config.model_name

    @property
    def is_semantic(self) -> bool:
        """Check if semantic embeddings are available (always True)."""
        return True

    def _ensure_initialized(self) -> None:
        """Lazy initialization of sentence-transformers model."""
        if self._initialized:
            return

        with self._init_lock:
            if self._initialized:
                return

            start = time.perf_counter()

            try:
                from sentence_transformers import SentenceTransformer

                self._sentence_transformer = SentenceTransformer(self.config.model_name)

                elapsed = time.perf_counter() - start
                logger.info(f"✅ EmbeddingService ready: {self.config.model_name} ({elapsed:.2f}s)")
                self._initialized = True

            except ImportError as err:
                raise ImportError(
                    "sentence-transformers not installed. Run: pip install sentence-transformers"
                ) from err

    def _cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return f"emb:{hash(text)}"

    # =========================================================================
    # CORE EMBEDDING OPERATIONS
    # =========================================================================

    def embed_text(self, text: str) -> np.ndarray:
        """Embed text to semantic vector.

        Args:
            text: Text to embed

        Returns:
            384D normalized embedding vector
        """
        self._ensure_initialized()
        start = time.perf_counter()

        # Check cache
        cache_key = self._cache_key(text)
        cached = self._cache.get_sync(cache_key)
        if cached is not None:
            self._cache_hits += 1
            return cached

        # Compute embedding
        embedding = self._sentence_transformer.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(np.float32)

        # Cache result
        self._cache.set_sync(cache_key, embedding)

        # Metrics
        self._embed_count += 1
        self._embed_latency_sum += time.perf_counter() - start

        return embedding

    async def embed_text_async(self, text: str) -> np.ndarray:
        """Async text embedding."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.embed_text, text)

    def embed_batch(self, texts: Sequence[str]) -> np.ndarray:
        """Embed batch of texts.

        Args:
            texts: List of texts

        Returns:
            Embeddings [N, 384]
        """
        if not texts:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)

        self._ensure_initialized()

        # Check cache for each
        results = []
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            cache_key = self._cache_key(text)
            cached = self._cache.get_sync(cache_key)
            if cached is not None:
                results.append((i, cached))
                self._cache_hits += 1
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        # Embed uncached texts
        if uncached_texts:
            embeddings = self._sentence_transformer.encode(
                uncached_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
            ).astype(np.float32)

            for idx, emb in zip(uncached_indices, embeddings, strict=True):
                results.append((idx, emb))
                cache_key = self._cache_key(texts[idx])
                self._cache.set_sync(cache_key, emb)
                self._embed_count += 1

        # Sort by original index
        results.sort(key=lambda x: x[0])
        return np.vstack([r[1] for r in results])

    async def embed_batch_async(self, texts: Sequence[str]) -> np.ndarray:
        """Async batch embedding."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.embed_batch, texts)

    # =========================================================================
    # SIMILARITY OPERATIONS
    # =========================================================================

    def similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts."""
        emb1 = self.embed_text(text1)
        emb2 = self.embed_text(text2)
        return float(np.dot(emb1, emb2))

    def similarity_to_vector(self, text: str, vector: np.ndarray) -> float:
        """Compute similarity between text and pre-computed vector."""
        emb = self.embed_text(text)
        # Normalize vector if needed
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return float(np.dot(emb, vector))

    # =========================================================================
    # STATS & HEALTH
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        avg_latency = self._embed_latency_sum / self._embed_count if self._embed_count > 0 else 0
        return {
            "model": self.config.model_name,
            "embedding_dim": self.embedding_dim,
            "initialized": self._initialized,
            "embed_count": self._embed_count,
            "cache_hits": self._cache_hits,
            "cache_hit_rate": (
                self._cache_hits / (self._embed_count + self._cache_hits)
                if (self._embed_count + self._cache_hits) > 0
                else 0
            ),
            "avg_latency_ms": avg_latency * 1000,
        }

    def health_check(self) -> dict[str, Any]:
        """Health check for service."""
        try:
            self._ensure_initialized()
            # Quick test embed
            test = self.embed_text("health check")
            return {
                "status": "healthy",
                "model": self.config.model_name,
                "embedding_dim": len(test),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# =============================================================================
# SINGLETON
# =============================================================================

_embedding_service: EmbeddingService | None = None
_service_lock = threading.Lock()


def get_embedding_service() -> EmbeddingService:
    """Get global EmbeddingService instance."""
    global _embedding_service

    if _embedding_service is None:
        with _service_lock:
            if _embedding_service is None:
                _embedding_service = EmbeddingService()

    return _embedding_service


def reset_embedding_service() -> None:
    """Reset global instance (for testing)."""
    global _embedding_service
    _embedding_service = None
