"""Semantic Matcher — Intent Classification via Embeddings.

Uses sentence-transformers for semantic similarity-based classification.
Shares model with EmbeddingService to avoid duplicate loading.

NO FALLBACKS. JUST OPTIMAL SEMANTIC MATCHING.

Created: December 29, 2025
Simplified: December 30, 2025 — Removed fallback complexity
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


# =============================================================================
# TRIP PURPOSE CATEGORIES (Default semantic categories)
# =============================================================================


@dataclass
class CategoryDefinition:
    """Defines a semantic category with exemplar phrases."""

    name: str
    exemplars: list[str]
    embedding: np.ndarray | None = None

    def __post_init__(self):
        if self.embedding is None:
            self.embedding = np.zeros(EMBEDDING_DIM, dtype=np.float32)


# Default categories for trip purpose classification
TRIP_PURPOSE_CATEGORIES = {
    "work": CategoryDefinition(
        name="work",
        exemplars=[
            "going to work",
            "heading to the office",
            "commute to work",
            "team standup",
            "daily standup meeting",
            "sprint planning",
            "code review session",
            "1:1 with manager",
            "all-hands meeting",
            "quarterly review",
        ],
    ),
    "meeting": CategoryDefinition(
        name="meeting",
        exemplars=[
            "client meeting",
            "business meeting",
            "conference call",
            "presentation",
            "pitch meeting",
            "investor meeting",
            "sales call",
            "vendor meeting",
            "interview",
        ],
    ),
    "errand": CategoryDefinition(
        name="errand",
        exemplars=[
            "grocery shopping",
            "going to the store",
            "picking up packages",
            "pharmacy run",
            "bank visit",
            "post office",
            "dry cleaning pickup",
            "car service",
            "shopping trip",
        ],
    ),
    "social": CategoryDefinition(
        name="social",
        exemplars=[
            "dinner with friends",
            "birthday party",
            "meeting friends",
            "date night",
            "happy hour",
            "concert",
            "movie night",
            "game night",
            "brunch",
            "family gathering",
        ],
    ),
    "exercise": CategoryDefinition(
        name="exercise",
        exemplars=[
            "going to the gym",
            "workout",
            "running",
            "yoga class",
            "tennis match",
            "swimming",
            "hiking",
            "cycling",
            "fitness class",
        ],
    ),
    "medical": CategoryDefinition(
        name="medical",
        exemplars=[
            "doctor appointment",
            "dentist appointment",
            "medical checkup",
            "therapy session",
            "hospital visit",
            "physical therapy",
            "specialist appointment",
        ],
    ),
    "travel": CategoryDefinition(
        name="travel",
        exemplars=[
            "airport trip",
            "catching a flight",
            "train station",
            "road trip",
            "vacation start",
            "business trip",
            "travel day",
        ],
    ),
}


# =============================================================================
# SEMANTIC MATCHER
# =============================================================================


class SemanticMatcher:
    """Semantic similarity-based intent classifier.

    Uses sentence-transformers (shared with EmbeddingService).
    No fallbacks — just optimal semantic matching.

    Usage:
        matcher = get_semantic_matcher()
        result = matcher.classify("team standup at 9am")
        # Returns: {"category": "work", "confidence": 0.87, ...}
    """

    def __init__(self):
        """Initialize semantic matcher."""
        # Model is shared with EmbeddingService
        self._model = None
        self._init_lock = threading.Lock()
        self._initialized = False

        # Use Kagami's caching
        self._cache = None
        self._storage_router = None

        # Category definitions
        self._categories: dict[str, CategoryDefinition] = {}
        for name, cat in TRIP_PURPOSE_CATEGORIES.items():
            self._categories[name] = CategoryDefinition(
                name=cat.name,
                exemplars=cat.exemplars.copy(),
            )

        # Statistics
        self._stats = {
            "classifications": 0,
            "cache_hits": 0,
        }

        logger.info("SemanticMatcher initialized")

    def _ensure_model(self) -> None:
        """Initialize model from EmbeddingService (shared)."""
        if self._initialized:
            return

        with self._init_lock:
            if self._initialized:
                return

            start = time.perf_counter()

            # Get model from EmbeddingService (shared, no duplicate loading)
            from kagami.core.services.embedding_service import get_embedding_service

            service = get_embedding_service()
            service._ensure_initialized()
            self._model = service._sentence_transformer

            if self._model is None:
                raise RuntimeError("EmbeddingService model not initialized")

            # Use Kagami's caching
            try:
                from kagami.core.caching import MemoryCache

                self._cache = MemoryCache(
                    name="semantic_matcher",
                    max_size=1000,
                    default_ttl=3600.0,
                )
            except ImportError:
                pass

            # Use StorageRouter for Weaviate
            try:
                from kagami.core.services.storage_routing import get_storage_router

                self._storage_router = get_storage_router()
            except ImportError:
                pass

            # Compute category embeddings
            self._compute_category_embeddings()

            elapsed = time.perf_counter() - start
            logger.info(f"✅ SemanticMatcher ready ({elapsed:.2f}s) — using shared model")
            self._initialized = True

    def _compute_category_embeddings(self) -> None:
        """Compute centroid embeddings for all categories."""
        if self._model is None:
            return

        for _name, cat in self._categories.items():
            if cat.exemplars:
                embeddings = self._model.encode(
                    cat.exemplars,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                )
                centroid = embeddings.mean(axis=0)
                norm = np.linalg.norm(centroid)
                if norm > 0:
                    centroid = centroid / norm
                cat.embedding = centroid.astype(np.float32)

        logger.debug(f"Computed embeddings for {len(self._categories)} categories")

    def _embed(self, text: str) -> np.ndarray:
        """Embed a single text."""
        self._ensure_model()

        # Check cache
        cache_key = f"sem:{text}"
        if self._cache:
            cached = self._cache.get_sync(cache_key)
            if cached is not None:
                self._stats["cache_hits"] += 1
                return cached

        # Compute embedding
        embedding = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(np.float32)

        # Cache result
        if self._cache:
            self._cache.set_sync(cache_key, embedding)

        return embedding

    def _embed_batch(self, texts: list[str]) -> np.ndarray:
        """Embed multiple texts."""
        self._ensure_model()

        return self._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(np.float32)

    def similarity(self, text: str, category: str) -> float:
        """Compute similarity between text and category."""
        if category not in self._categories:
            return 0.0

        cat = self._categories[category]
        if cat.embedding is None or np.allclose(cat.embedding, 0):
            return 0.0

        text_emb = self._embed(text)
        return float(np.dot(text_emb, cat.embedding))

    def classify(
        self,
        text: str,
        threshold: float = 0.5,
    ) -> dict[str, Any]:
        """Classify text into best matching category.

        Args:
            text: Text to classify
            threshold: Minimum similarity threshold

        Returns:
            Dict with category, confidence, all_scores
        """
        self._stats["classifications"] += 1

        text_emb = self._embed(text)

        # Compute similarity to all categories
        scores: dict[str, float] = {}
        for name, cat in self._categories.items():
            if cat.embedding is not None and not np.allclose(cat.embedding, 0):
                scores[name] = float(np.dot(text_emb, cat.embedding))
            else:
                scores[name] = 0.0

        if not scores:
            return {
                "category": None,
                "confidence": 0.0,
                "all_scores": {},
            }

        best_category = max(scores.keys(), key=lambda k: scores[k])
        best_score = scores[best_category]

        if best_score < threshold:
            return {
                "category": None,
                "confidence": best_score,
                "all_scores": scores,
                "below_threshold": True,
            }

        return {
            "category": best_category,
            "confidence": best_score,
            "all_scores": scores,
        }

    def classify_batch(
        self,
        texts: list[str],
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Classify multiple texts."""
        if not texts:
            return []

        embeddings = self._embed_batch(texts)
        results = []

        for text_emb in embeddings:
            scores: dict[str, float] = {}
            for name, cat in self._categories.items():
                if cat.embedding is not None and not np.allclose(cat.embedding, 0):
                    scores[name] = float(np.dot(text_emb, cat.embedding))
                else:
                    scores[name] = 0.0

            best_category = max(scores.keys(), key=lambda k: scores[k]) if scores else None
            best_score = scores.get(best_category, 0.0) if best_category else 0.0

            if best_score < threshold:
                results.append(
                    {
                        "category": None,
                        "confidence": best_score,
                        "all_scores": scores,
                        "below_threshold": True,
                    }
                )
            else:
                results.append(
                    {
                        "category": best_category,
                        "confidence": best_score,
                        "all_scores": scores,
                    }
                )

        return results

    def add_category(self, name: str, exemplars: list[str]) -> None:
        """Add or update a category."""
        self._categories[name] = CategoryDefinition(
            name=name,
            exemplars=exemplars,
        )

        # Recompute embedding if model is loaded
        if self._model is not None:
            embeddings = self._model.encode(
                exemplars,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            centroid = embeddings.mean(axis=0)
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid = centroid / norm
            self._categories[name].embedding = centroid.astype(np.float32)

        logger.info(f"Added category: {name} ({len(exemplars)} exemplars)")

    def has_category(self, name: str) -> bool:
        """Check if a category exists.

        Args:
            name: Category name to check

        Returns:
            True if category exists, False otherwise
        """
        return name in self._categories

    def add_exemplar(self, category: str, exemplar: str) -> None:
        """Add an exemplar to existing category."""
        if category not in self._categories:
            self._categories[category] = CategoryDefinition(
                name=category,
                exemplars=[exemplar],
            )
        else:
            self._categories[category].exemplars.append(exemplar)

        # Recompute embedding if model is loaded
        if self._model is not None:
            cat = self._categories[category]
            embeddings = self._model.encode(
                cat.exemplars,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            centroid = embeddings.mean(axis=0)
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid = centroid / norm
            cat.embedding = centroid.astype(np.float32)

    def get_categories(self) -> list[str]:
        """Get all category names."""
        return list(self._categories.keys())

    def get_stats(self) -> dict[str, Any]:
        """Get matcher statistics."""
        return {
            **self._stats,
            "initialized": self._initialized,
            "categories": len(self._categories),
            "model": DEFAULT_MODEL,
            "cache": self._cache is not None,
            "storage_router": self._storage_router is not None,
        }

    # =========================================================================
    # WEAVIATE INTEGRATION (Via StorageRouter)
    # =========================================================================

    async def init_weaviate(self) -> bool:
        """Initialize Weaviate via StorageRouter."""
        self._ensure_model()
        return self._storage_router is not None

    async def persist_categories(self) -> None:
        """Persist categories to Weaviate via StorageRouter."""
        if not self._storage_router:
            return

        for name, cat in self._categories.items():
            for exemplar in cat.exemplars:
                embedding = self._embed(exemplar)
                try:
                    await self._storage_router.store_vector(
                        vector=embedding,
                        data={
                            "content": exemplar,
                            "category": name,
                            "kind": "semantic_category",
                        },
                        namespace="semantic_categories",
                    )
                except Exception as e:
                    logger.debug(f"Persist failed: {e}")

    async def load_from_weaviate(self) -> int:
        """Load categories from Weaviate via StorageRouter."""
        if not self._storage_router:
            return 0

        try:
            results = await self._storage_router.search_semantic(
                query="",
                limit=1000,
                kind_filter="semantic_category",
            )

            for obj in results:
                cat_name = obj.get("category")
                exemplar = obj.get("content")

                if cat_name and exemplar:
                    self.add_exemplar(cat_name, exemplar)

            logger.info(f"Loaded {len(results)} exemplars from Weaviate")
            return len(results)

        except Exception as e:
            logger.warning(f"Load from Weaviate failed: {e}")
            return 0


# =============================================================================
# SINGLETON
# =============================================================================

_matcher: SemanticMatcher | None = None
_matcher_lock = threading.Lock()


def get_semantic_matcher() -> SemanticMatcher:
    """Get global SemanticMatcher instance."""
    global _matcher

    if _matcher is None:
        with _matcher_lock:
            if _matcher is None:
                _matcher = SemanticMatcher()

    return _matcher


def reset_semantic_matcher() -> None:
    """Reset global instance (for testing)."""
    global _matcher
    _matcher = None
