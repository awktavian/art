from __future__ import annotations

"""
Semantic caching for Forge character generation.

Caches generated characters by semantic similarity for 10x speedup.
"""
import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

try:
    import numpy as np

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    np = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class CachedResult:
    """Cached character generation result."""

    concept: str
    embedding: Any
    result: dict[str, Any]
    timestamp: float
    hit_count: int = 0


class SemanticCache:
    """Semantic similarity cache for character generation."""

    def __init__(self, similarity_threshold: float = 0.92) -> None:
        self.similarity_threshold = similarity_threshold
        self.cache: dict[str, CachedResult] = {}
        self.hits = 0
        self.misses = 0

        # Use unified embedding service (single model load, shared 400MB)
        try:
            from kagami.core.services.embedding_service import get_embedding_service

            self.encoder = get_embedding_service()
            logger.info("Semantic cache using unified embedding service")
        except Exception as e:
            logger.warning(f"Failed to load embedding service: {e}")
            self.encoder: Any | None = None  # type: ignore[assignment, no-redef]

    async def get_or_generate(
        self, prompt: str, generator: Callable, **kwargs: Any
    ) -> tuple[dict[str, Any], bool]:
        """Get from cache or generate fresh."""
        if not self.encoder:
            self.misses += 1
            result = await generator(prompt, **kwargs)
            return result, False

        try:
            # Use unified embedding service API
            query_emb = self.encoder.embed_text(prompt)
        except Exception:
            self.misses += 1
            result = await generator(prompt, **kwargs)
            return result, False

        best_sim = 0.0
        best_key = None

        for key, cached in self.cache.items():
            try:
                if cached.embedding is not None and np:
                    sim = float(
                        np.dot(query_emb, cached.embedding)
                        / (np.linalg.norm(query_emb) * np.linalg.norm(cached.embedding))
                    )
                    if sim > best_sim:
                        best_sim = sim
                        best_key = key
            except Exception:
                continue

        if best_sim >= self.similarity_threshold and best_key:
            self.hits += 1
            cached = self.cache[best_key]
            cached.hit_count += 1
            logger.info(f"Cache HIT: {prompt} → {cached.concept} ({best_sim:.2%})")
            return cached.result, True

        self.misses += 1
        logger.info(f"Cache MISS: {prompt} (best: {best_sim:.2%})")

        result = await generator(prompt, **kwargs)

        key = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        self.cache[key] = CachedResult(
            concept=prompt,
            embedding=query_emb,
            result=result,
            timestamp=time.time(),
        )

        return result, False

    def get_stats(self) -> dict[str, Any]:
        total = self.hits + self.misses
        return {
            "enabled": self.encoder is not None,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / total if total > 0 else 0.0,
            "cache_size": len(self.cache),
        }


_cache: SemanticCache | None = None


def get_semantic_cache() -> SemanticCache:
    global _cache
    if _cache is None:
        _cache = SemanticCache()
    return _cache


__all__ = ["AVAILABLE", "SemanticCache", "get_semantic_cache"]
