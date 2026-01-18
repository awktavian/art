"""Chunking Bridge — Elysia Chunk-on-Demand with HierarchicalMemory.

Integrates Elysia's chunk-on-demand approach with Kagami's
HierarchicalMemory for intelligent document processing.

Elysia's approach: Chunk at query time, not pre-chunk
Kagami's approach: Working → Short-term → Long-term → Semantic

Integration:
1. Initial search uses document-level vectors (Weaviate)
2. If document is relevant + large, chunk dynamically
3. Chunks stored in short-term memory (HierarchicalMemory)
4. Successful chunks promoted to long-term patterns

Created: December 7, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import torch

logger = logging.getLogger(__name__)


@dataclass
class ChunkConfig:
    """Configuration for chunk-on-demand behavior."""

    # Size thresholds (in tokens, estimated)
    token_threshold: int = 4000  # Chunk if document > this
    min_chunk_size: int = 100  # Minimum chunk size
    max_chunk_size: int = 1500  # Maximum chunk size
    overlap_tokens: int = 50  # Overlap between chunks

    # Chunking strategy
    chunk_by_paragraph: bool = True
    chunk_by_heading: bool = True
    chunk_by_sentence: bool = False

    # Memory promotion
    promote_successful_chunks: bool = True
    success_threshold: float = 0.8  # Relevance score for promotion


@dataclass
class ChunkResult:
    """Result of chunking operation."""

    chunks: list[str]
    source_id: str
    method: str  # "paragraph", "heading", "sentence", "hybrid"
    total_tokens: int
    chunk_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkOnDemandBridge:
    """Bridge Elysia chunk-on-demand to HierarchicalMemory.

    Provides intelligent document chunking that:
    1. Only chunks when needed (large documents)
    2. Uses semantic boundaries (paragraphs, headings)
    3. Stores chunks in short-term memory for reuse
    4. Promotes successful chunks to long-term patterns

    Usage:
        bridge = ChunkOnDemandBridge(weaviate_adapter)

        # Retrieve and chunk documents
        chunks = await bridge.retrieve_and_chunk(
            query="What is E8?",
            query_embedding=embedding,
        )
    """

    def __init__(
        self,
        weaviate_adapter: Any = None,
        config: ChunkConfig | None = None,
    ):
        """Initialize chunking bridge.

        Args:
            weaviate_adapter: WeaviateE8Adapter instance
            config: Chunking configuration
        """
        self.weaviate = weaviate_adapter
        self.config = config or ChunkConfig()

        # Lazy-loaded hierarchical memory
        self._hierarchical = None

        # Cache for recently chunked documents
        self._chunk_cache: dict[str, list[str]] = {}
        self._cache_max_size = 100

        logger.info("ChunkOnDemandBridge initialized")

    def _get_hierarchical_memory(self) -> Any:
        """Lazy-load hierarchical memory."""
        if self._hierarchical is None:
            try:
                from kagami.core.memory.hierarchical_memory import (
                    get_hierarchical_memory,
                )

                self._hierarchical = get_hierarchical_memory()  # type: ignore[assignment]
            except ImportError:
                logger.debug("HierarchicalMemory not available")
        return self._hierarchical

    async def retrieve_and_chunk(
        self,
        query: str,
        query_embedding: torch.Tensor | None = None,
        max_documents: int = 20,
        colony_filter: str | None = None,
    ) -> list[str]:
        """Retrieve documents, chunk if needed, consolidate to memory.

        Args:
            query: User query
            query_embedding: Pre-computed embedding (optional)
            max_documents: Maximum documents to retrieve
            colony_filter: Optional colony filter

        Returns:
            List of relevant content chunks
        """
        if self.weaviate is None:
            logger.warning("Weaviate adapter not available")
            return []

        # Step 1: Document-level search
        docs = await self.weaviate.search_similar(
            query=query if query_embedding is None else query_embedding,
            limit=max_documents,
            colony_filter=colony_filter,
        )

        relevant_chunks = []
        memory = self._get_hierarchical_memory()

        for doc in docs:
            content = doc.get("content", "")
            doc_id = doc.get("uuid", str(hash(content[:100])))

            # Estimate token count
            token_count = self._estimate_tokens(content)

            if token_count > self.config.token_threshold:
                # Step 2: Check cache first
                if doc_id in self._chunk_cache:
                    chunks = self._chunk_cache[doc_id]
                    logger.debug(f"Using cached chunks for {doc_id}")
                else:
                    # Chunk dynamically
                    result = self._chunk_document(content, query)
                    chunks = result.chunks

                    # Cache chunks
                    self._cache_chunks(doc_id, chunks)

                # Step 3: Store relevant chunks in working memory (parallel)
                if memory:
                    # Filter chunks by relevance first
                    relevant = [(c, self._compute_relevance(c, query)) for c in chunks]
                    to_store = [(c, r) for c, r in relevant if r > 0.5]
                    if to_store:
                        await asyncio.gather(
                            *[self._store_chunk(memory, c, doc_id, query) for c, _ in to_store],
                            return_exceptions=True,
                        )
                        relevant_chunks.extend([c for c, _ in to_store])
            else:
                # Small document - use as-is
                relevant_chunks.append(content)

                # Store in memory
                if memory:
                    await self._store_chunk(memory, content, doc_id, query)

        logger.info(f"Retrieved {len(docs)} docs, produced {len(relevant_chunks)} chunks")
        return relevant_chunks

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough heuristic).

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        # Simple heuristic: ~1.3 tokens per word
        words = len(text.split())
        return int(words * 1.3)

    def _chunk_document(
        self,
        content: str,
        query: str,
    ) -> ChunkResult:
        """Chunk document using semantic boundaries.

        Args:
            content: Document content
            query: Query for context-aware chunking

        Returns:
            ChunkResult with chunks and metadata
        """
        chunks = []
        method = "hybrid"

        # Try paragraph-based chunking first
        if self.config.chunk_by_paragraph:
            paragraphs = self._split_by_paragraphs(content)

            for para in paragraphs:
                para_tokens = self._estimate_tokens(para)

                if para_tokens < self.config.min_chunk_size:
                    continue  # Skip tiny paragraphs

                if para_tokens > self.config.max_chunk_size:
                    # Split large paragraph by sentences
                    sub_chunks = self._split_by_sentences(para)
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(para)

        # Fallback to sentence-based if no paragraphs
        if not chunks and self.config.chunk_by_sentence:
            chunks = self._split_by_sentences(content)
            method = "sentence"

        # Final fallback: fixed-size chunks
        if not chunks:
            chunks = self._split_by_size(content)
            method = "fixed"

        return ChunkResult(
            chunks=chunks,
            source_id="",  # Set by caller
            method=method,
            total_tokens=self._estimate_tokens(content),
            chunk_count=len(chunks),
            metadata={"query": query[:100]},
        )

    def _split_by_paragraphs(self, text: str) -> list[str]:
        """Split text by paragraph boundaries.

        Args:
            text: Text to split

        Returns:
            List of paragraphs
        """
        # Split on double newlines
        paragraphs = text.split("\n\n")

        # Clean up
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        return paragraphs

    def _split_by_sentences(self, text: str) -> list[str]:
        """Split text by sentences, combining into chunk-sized groups.

        Args:
            text: Text to split

        Returns:
            List of sentence groups
        """
        import re

        # Simple sentence splitting
        sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Combine sentences into chunks
        chunks = []
        current_chunk = []  # type: ignore[var-annotated]
        current_tokens = 0

        for sentence in sentences:
            sent_tokens = self._estimate_tokens(sentence)

            if current_tokens + sent_tokens > self.config.max_chunk_size:
                # Save current chunk
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_tokens = sent_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sent_tokens

        # Don't forget last chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _split_by_size(self, text: str) -> list[str]:
        """Split text by fixed size (fallback).

        Args:
            text: Text to split

        Returns:
            List of fixed-size chunks
        """
        words = text.split()
        chunks = []

        # Estimate words per chunk
        words_per_chunk = int(self.config.max_chunk_size / 1.3)
        overlap_words = int(self.config.overlap_tokens / 1.3)

        i = 0
        while i < len(words):
            chunk_words = words[i : i + words_per_chunk]
            chunks.append(" ".join(chunk_words))
            i += words_per_chunk - overlap_words

        return chunks

    def _compute_relevance(self, chunk: str, query: str) -> float:
        """Compute semantic relevance of chunk to query.

        Simple heuristic based on word overlap.
        Production would use embedding similarity.

        Args:
            chunk: Chunk text
            query: Query text

        Returns:
            Relevance score [0-1]
        """
        # Simple word overlap heuristic
        query_words = set(query.lower().split())
        chunk_words = set(chunk.lower().split())

        if not query_words:
            return 0.0  # Empty query has no relevance

        overlap = len(query_words & chunk_words)
        return min(1.0, overlap / len(query_words))

    async def _store_chunk(
        self,
        memory: Any,
        chunk: str,
        source_id: str,
        query: str,
    ) -> None:
        """Store chunk in hierarchical memory.

        Args:
            memory: HierarchicalMemory instance
            chunk: Chunk content
            source_id: Source document ID
            query: Original query
        """
        try:
            await memory.store(
                {
                    "content": chunk,
                    "source_doc": source_id,
                    "query": query,
                    "timestamp": time.time(),
                    "valence": 0.0,  # Updated after use
                }
            )
        except Exception as e:
            logger.debug(f"Failed to store chunk in memory: {e}")

    def _cache_chunks(self, doc_id: str, chunks: list[str]) -> None:
        """Cache chunks for reuse.

        Args:
            doc_id: Document ID
            chunks: Chunks to cache
        """
        # Evict old entries if needed
        if len(self._chunk_cache) >= self._cache_max_size:
            # Remove oldest (FIFO)
            oldest = next(iter(self._chunk_cache))
            del self._chunk_cache[oldest]

        self._chunk_cache[doc_id] = chunks

    async def promote_successful_chunk(
        self,
        chunk: str,
        source_id: str,
        relevance_score: float,
    ) -> bool:
        """Promote successful chunk to long-term memory.

        Called when a chunk is used successfully in a response.

        Args:
            chunk: Chunk content
            source_id: Source document ID
            relevance_score: How relevant the chunk was

        Returns:
            True if promoted
        """
        if relevance_score < self.config.success_threshold:
            return False

        memory = self._get_hierarchical_memory()
        if memory is None:
            return False

        try:
            # Update valence to promote
            await memory.promote(
                {
                    "content": chunk,
                    "source_doc": source_id,
                    "valence": relevance_score,
                }
            )
            logger.debug(f"Promoted chunk from {source_id}")
            return True
        except Exception as e:
            logger.debug(f"Failed to promote chunk: {e}")
            return False

    def clear_cache(self) -> int:
        """Clear the chunk cache.

        Returns:
            Number of entries cleared
        """
        count = len(self._chunk_cache)
        self._chunk_cache.clear()
        return count


# Factory function
def create_chunking_bridge(
    weaviate_adapter: Any = None,
    config: ChunkConfig | None = None,
) -> ChunkOnDemandBridge:
    """Create a ChunkOnDemandBridge instance.

    Args:
        weaviate_adapter: WeaviateE8Adapter instance
        config: Optional configuration

    Returns:
        ChunkOnDemandBridge instance
    """
    return ChunkOnDemandBridge(weaviate_adapter, config)


__all__ = [
    "ChunkConfig",
    "ChunkOnDemandBridge",
    "ChunkResult",
    "create_chunking_bridge",
]
