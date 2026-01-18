"""Aperiodic Embeddings — Kagami Embeddings.

Provides embedding utilities for aperiodic/non-regular text processing.
All embeddings flow through the Kagami Embedding Service.

CANONICAL DIMENSION: 512D
========================
All embeddings are 512D to match KagamiWorldModel bulk dimension.

UPDATED (Nov 30, 2025): Removed fallback paths. Uses unified service only.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def get_embedding_model() -> Any:
    """Get the unified embedding service.

    Returns:
        EmbeddingService instance

    Raises:
        RuntimeError: If service unavailable and FULL_OPERATION mode
    """
    from kagami.core.services.embedding_service import get_embedding_service

    return get_embedding_service()


def embed_text(text: str) -> list[float]:
    """Generate embedding for single text.

    Args:
        text: Input text

    Returns:
        Embedding vector as list[Any] of floats
    """
    if not text or not text.strip():
        # Return zero vector of service dimension
        service = get_embedding_model()
        return [0.0] * service.embedding_dim

    service = get_embedding_model()
    embedding = service.embed_text(text)
    return embedding.tolist()  # type: ignore[no-any-return]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts.

    Args:
        texts: List of input texts

    Returns:
        List of embedding vectors
    """
    if not texts:
        return []

    service = get_embedding_model()
    embeddings = service.embed_batch(texts)
    return [e.tolist() for e in embeddings]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First vector
        b: Second vector

    Returns:
        Cosine similarity in [-1, 1]
    """
    if not a or not b:
        return 0.0

    va = np.array(a)
    vb = np.array(b)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(va, vb) / (norm_a * norm_b))


def max_similarity(candidate: str, historical_texts: list[str]) -> float:
    """Compute maximum cosine similarity between candidate and historical texts.

    Args:
        candidate: The candidate text to compare
        historical_texts: List of historical texts to compare against

    Returns:
        Maximum similarity score (0.0 to 1.0)
    """
    if not historical_texts:
        return 0.0

    cand_emb = embed_text(candidate)
    hist_embs = embed_batch(historical_texts)

    max_sim = 0.0
    for h_emb in hist_embs:
        sim = cosine_similarity(cand_emb, h_emb)
        if sim > max_sim:
            max_sim = sim

    return max_sim
