"""Embedding-Based Semantic Matcher - NO KEYWORDS.

This module provides embedding-based semantic matching for routing decisions.
ALL routing must use semantic embeddings, NOT keyword matching.

NO keyword checks allowed. NO string pattern matching. NO heuristics.
ONLY embedding-based semantic similarity.

Created: January 5, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SemanticMatch:
    """Result of semantic matching."""

    label: str
    confidence: float
    embedding: np.ndarray


class SemanticMatcher:
    """Embedding-based semantic matcher with NO keyword fallbacks.

    All matching is done via semantic embeddings using sentence-transformers
    or similar embedding models. NO string comparisons allowed.
    """

    def __init__(self) -> None:
        """Initialize semantic matcher."""
        self._encoder: Any = None
        self._label_embeddings: dict[str, np.ndarray] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize embedding model."""
        if self._initialized:
            return

        try:
            # Use lightweight sentence-transformers model
            from sentence_transformers import SentenceTransformer

            # all-MiniLM-L6-v2: 384-dim, fast, good for semantic similarity
            self._encoder = SentenceTransformer("all-MiniLM-L6-v2")

            # Pre-compute embeddings for common labels
            await self._precompute_label_embeddings()

            self._initialized = True
            logger.info("✅ Semantic matcher initialized (all-MiniLM-L6-v2)")

        except Exception as e:
            logger.error(f"❌ Failed to initialize semantic matcher: {e}")
            raise RuntimeError(f"Semantic matcher initialization failed: {e}") from e

    async def _precompute_label_embeddings(self) -> None:
        """Pre-compute embeddings for common labels."""
        # Colony semantic descriptions
        colony_descriptions = {
            "spark": "creative ideation brainstorming innovation imagination",
            "forge": "building implementation construction coding development",
            "flow": "debugging recovery maintenance healing error handling",
            "nexus": "integration connection bridging coordination linking",
            "beacon": "planning architecture strategy organization design",
            "grove": "research exploration investigation learning discovery",
            "crystal": "testing verification validation quality assurance safety",
        }

        # Task type semantic descriptions
        task_descriptions = {
            "create": "generate new ideas creative brainstorming ideation",
            "build": "implement construct develop code write software",
            "fix": "repair debug resolve errors maintain troubleshoot",
            "integrate": "connect merge combine link coordinate systems",
            "plan": "strategize organize design architecture blueprint",
            "research": "explore investigate study analyze learn discover",
            "verify": "test validate check quality assurance audit safety",
        }

        # Service semantic descriptions
        service_descriptions = {
            "github": "git version control repository code commits branches pull requests",
            "linear": "project management issues tasks sprints cycles milestones",
            "notion": "knowledge base documentation notes wiki information",
            "slack": "messaging communication alerts notifications team chat",
            "twitter": "social media trends posts tweets public discourse",
            "gmail": "email messages correspondence communication inbox",
            "calendar": "scheduling events meetings appointments time management",
        }

        # Compute all embeddings
        all_labels = {}
        all_labels.update(colony_descriptions)
        all_labels.update(task_descriptions)
        all_labels.update(service_descriptions)

        for label, description in all_labels.items():
            self._label_embeddings[label] = self._encoder.encode(
                description, convert_to_numpy=True, show_progress_bar=False
            )

        logger.debug(f"📊 Pre-computed {len(all_labels)} label embeddings")

    def encode(self, text: str) -> np.ndarray:
        """Encode text to embedding vector.

        Args:
            text: Text to encode

        Returns:
            Embedding vector

        Raises:
            RuntimeError: If matcher not initialized
        """
        if not self._initialized:
            raise RuntimeError("Semantic matcher not initialized - call initialize() first")

        return self._encoder.encode(text, convert_to_numpy=True, show_progress_bar=False)

    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score [0, 1]
        """
        # Cosine similarity
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        # Normalize to [0, 1] range (cosine is [-1, 1])
        return float((similarity + 1) / 2)

    async def match_colony(
        self, action: str, context: dict[str, Any] | None = None
    ) -> SemanticMatch:
        """Match action to colony using semantic similarity.

        Args:
            action: Action to match
            context: Optional routing context

        Returns:
            SemanticMatch with best colony

        Raises:
            RuntimeError: If matcher not initialized
        """
        if not self._initialized:
            raise RuntimeError("Semantic matcher not initialized")

        # Encode action
        action_embedding = self.encode(action)

        # Compute similarities to all colonies
        similarities = {}
        for colony_name in ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]:
            colony_embedding = self._label_embeddings[colony_name]
            similarity = self.compute_similarity(action_embedding, colony_embedding)
            similarities[colony_name] = similarity

        # Get best match
        best_colony = max(similarities, key=similarities.get)  # type: ignore[arg-type]
        best_confidence = similarities[best_colony]

        logger.debug(
            f"🎯 Semantic colony match: '{action}' → {best_colony} "
            f"(confidence={best_confidence:.2f})"
        )

        return SemanticMatch(
            label=best_colony,
            confidence=best_confidence,
            embedding=action_embedding,
        )

    async def match_task_type(self, action: str) -> SemanticMatch:
        """Match action to task type using semantic similarity.

        Args:
            action: Action to match

        Returns:
            SemanticMatch with best task type

        Raises:
            RuntimeError: If matcher not initialized
        """
        if not self._initialized:
            raise RuntimeError("Semantic matcher not initialized")

        # Encode action
        action_embedding = self.encode(action)

        # Compute similarities to all task types
        similarities = {}
        for task_type in ["create", "build", "fix", "integrate", "plan", "research", "verify"]:
            task_embedding = self._label_embeddings[task_type]
            similarity = self.compute_similarity(action_embedding, task_embedding)
            similarities[task_type] = similarity

        # Get best match
        best_type = max(similarities, key=similarities.get)  # type: ignore[arg-type]
        best_confidence = similarities[best_type]

        logger.debug(
            f"🎯 Semantic task type: '{action}' → {best_type} (confidence={best_confidence:.2f})"
        )

        return SemanticMatch(
            label=best_type,
            confidence=best_confidence,
            embedding=action_embedding,
        )

    async def match_service(self, action: str) -> SemanticMatch | None:
        """Match action to service using semantic similarity.

        Args:
            action: Action to match

        Returns:
            SemanticMatch with best service, or None if confidence < 0.6

        Raises:
            RuntimeError: If matcher not initialized
        """
        if not self._initialized:
            raise RuntimeError("Semantic matcher not initialized")

        # Encode action
        action_embedding = self.encode(action)

        # Compute similarities to all services
        similarities = {}
        for service in ["github", "linear", "notion", "slack", "twitter", "gmail", "calendar"]:
            service_embedding = self._label_embeddings[service]
            similarity = self.compute_similarity(action_embedding, service_embedding)
            similarities[service] = similarity

        # Get best match
        best_service = max(similarities, key=similarities.get)  # type: ignore[arg-type]
        best_confidence = similarities[best_service]

        # Only return if confidence is high enough
        if best_confidence < 0.6:
            logger.debug(f"🔍 No strong service match for '{action}' (best={best_confidence:.2f})")
            return None

        logger.debug(
            f"🎯 Semantic service match: '{action}' → {best_service} "
            f"(confidence={best_confidence:.2f})"
        )

        return SemanticMatch(
            label=best_service,
            confidence=best_confidence,
            embedding=action_embedding,
        )

    async def compute_action_embedding(self, action: str, params: dict[str, Any]) -> np.ndarray:
        """Compute embedding for action with parameters.

        Args:
            action: Action name
            params: Action parameters

        Returns:
            Combined embedding vector

        Raises:
            RuntimeError: If matcher not initialized
        """
        if not self._initialized:
            raise RuntimeError("Semantic matcher not initialized")

        # Combine action and parameters into text
        param_text = " ".join(
            f"{k} {v}" for k, v in params.items() if isinstance(v, (str, int, float))
        )
        combined_text = f"{action} {param_text}"

        return self.encode(combined_text)


# =============================================================================
# FACTORY (via centralized registry)
# =============================================================================

from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
get_semantic_matcher = _singleton_registry.register_async("semantic_matcher", SemanticMatcher)


__all__ = [
    "SemanticMatch",
    "SemanticMatcher",
    "get_semantic_matcher",
]
