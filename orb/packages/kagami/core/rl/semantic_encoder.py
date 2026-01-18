"""Semantic State Encoder — Uses Kagami Embedding Service.

Converts context dicts into semantic embeddings using the unified
Kagami Embedding Service. No fallbacks — all embedding goes through
the single source.

CANONICAL: kagami.core.services.embedding_service.get_embedding_service()
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Canonical dimension (matches world model bulk)
KAGAMI_EMBED_DIM = 512


class SemanticEncoder:
    """Encode states using Kagami Embedding Service.

    This is a thin wrapper that adds context-to-text conversion
    and similarity utilities on top of the embedding service.

    Key innovation: States with similar semantics get similar embeddings,
    enabling generalization across contexts.
    """

    def __init__(self, embedding_dim: int = KAGAMI_EMBED_DIM) -> None:
        """Initialize with Kagami Embedding Service.

        Args:
            embedding_dim: Dimension of embeddings (default: 512)
        """
        self.embedding_dim = embedding_dim

        # Get shared embedding service (THE source)
        from kagami.core.services.embedding_service import get_embedding_service

        self._embedding_service = get_embedding_service()
        logger.info("✅ SemanticEncoder: Using Kagami Embedding Service")

    async def encode(self, context: dict[str, Any]) -> np.ndarray[Any, Any]:
        """Encode context into semantic embedding.

        Args:
            context: Context dict[str, Any] with action, goal, status, etc.

        Returns:
            512D numpy array (Kagami standard)
        """
        context_text = self._context_to_text(context)
        return await self._embedding_service.embed_text_async(
            context_text, dimension=self.embedding_dim
        )

    def encode_sync(self, context: dict[str, Any]) -> np.ndarray[Any, Any]:
        """Synchronous version of encode.

        Args:
            context: Context dict[str, Any]

        Returns:
            512D numpy array
        """
        context_text = self._context_to_text(context)
        return self._embedding_service.embed_text(context_text, dimension=self.embedding_dim)  # type: ignore[return-value]

    def _context_to_text(self, context: dict[str, Any]) -> str:
        """Convert context dict[str, Any] to natural language text.

        Args:
            context: Context dict[str, Any]

        Returns:
            Natural language description
        """
        parts = []

        # Action
        if "action" in context:
            parts.append(f"Action: {context['action']}")

        # Tool
        if "tool" in context:
            parts.append(f"Using: {context['tool']}")

        # Goal
        if "goal" in context:
            parts.append(f"Goal: {context['goal']}")

        # Status
        if "status" in context:
            parts.append(f"Status: {context['status']}")

        # Recent operations
        if "recent_operations" in context:
            recent = context["recent_operations"]
            if recent:
                parts.append(f"Recent: {', '.join(str(op) for op in recent[:3])}")

        # Error message
        if "error" in context:
            parts.append(f"Error: {context['error']}")

        if not parts:
            parts.append("Unknown operation")

        return " | ".join(parts)

    def compute_similarity(
        self, embedding1: np.ndarray[Any, Any], embedding2: np.ndarray[Any, Any]
    ) -> float:
        """Compute cosine similarity between embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Similarity score (0.0-1.0)
        """
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        return float((similarity + 1.0) / 2.0)

    def find_similar_states(
        self,
        query_embedding: np.ndarray[Any, Any],
        state_embeddings: list[tuple[str, np.ndarray[Any, Any]]],
        top_k: int = 5,
        min_similarity: float = 0.7,
    ) -> list[tuple[str, float]]:
        """Find most similar states to query.

        Args:
            query_embedding: Query state embedding
            state_embeddings: List of (state_hash, embedding) tuples
            top_k: Number of results
            min_similarity: Minimum threshold

        Returns:
            List of (state_hash, similarity) sorted by similarity
        """
        similarities = []

        for state_hash, embedding in state_embeddings:
            similarity = self.compute_similarity(query_embedding, embedding)
            if similarity >= min_similarity:
                similarities.append((state_hash, similarity))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]


# Global singleton
_semantic_encoder: SemanticEncoder | None = None


def get_semantic_encoder() -> SemanticEncoder:
    """Get or create global semantic encoder."""
    global _semantic_encoder

    if _semantic_encoder is None:
        _semantic_encoder = SemanticEncoder()
        logger.info("🧠 Semantic encoder initialized (Kagami Embedding Service)")

    return _semantic_encoder


# Direct access functions (preferred)
async def encode_context(context: dict[str, Any]) -> np.ndarray[Any, Any]:
    """Encode context to semantic embedding.

    Args:
        context: Context dict[str, Any]

    Returns:
        512D numpy array
    """
    return await get_semantic_encoder().encode(context)


def encode_context_sync(context: dict[str, Any]) -> np.ndarray[Any, Any]:
    """Encode context to semantic embedding (sync).

    Args:
        context: Context dict[str, Any]

    Returns:
        512D numpy array
    """
    return get_semantic_encoder().encode_sync(context)


__all__ = [
    "KAGAMI_EMBED_DIM",
    "SemanticEncoder",
    "encode_context",
    "encode_context_sync",
    "get_semantic_encoder",
]
