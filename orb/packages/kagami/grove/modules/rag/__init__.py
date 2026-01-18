"""Grove RAG Module — Retrieval-Augmented Generation.

Provides semantic and hybrid search capabilities:
- Semantic search using embeddings
- Hybrid search combining semantic + keyword
- Context retrieval for LLM prompting

Created: December 28, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result."""

    content: str
    score: float
    source: str
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    chunk_id: str = ""

    def __lt__(self, other: SearchResult) -> bool:
        return self.score < other.score


@dataclass
class RAGContext:
    """Context for RAG-enhanced generation."""

    query: str
    results: list[SearchResult]
    total_tokens: int = 0
    context_window: str = ""

    def to_prompt(self) -> str:
        """Format context for LLM prompt."""
        context_parts = []
        for i, result in enumerate(self.results, 1):
            context_parts.append(f"[Source {i}: {result.source}]\n{result.content}\n")

        self.context_window = "\n".join(context_parts)
        return f"""Context information from knowledge base:

{self.context_window}

Based on the above context, answer the following question:
{self.query}
"""


async def search_and_retrieve(
    query: str,
    top_k: int = 5,
    min_score: float = 0.3,
    sources: list[str] | None = None,
) -> RAGContext:
    """Search knowledge base and retrieve relevant context.

    Performs hybrid search (semantic + keyword) and returns
    context suitable for RAG-enhanced generation.

    Args:
        query: Search query
        top_k: Number of results to retrieve
        min_score: Minimum relevance score threshold
        sources: Optional list[Any] of sources to search

    Returns:
        RAGContext with retrieved documents

    Example:
        context = await search_and_retrieve("How does auth work?")
        prompt = context.to_prompt()
        response = await llm.generate(prompt)
    """
    results = await hybrid_search(query, top_k=top_k, min_score=min_score)

    # Filter by sources if specified
    if sources:
        results = [r for r in results if any(s in r.source for s in sources)]

    return RAGContext(
        query=query,
        results=results[:top_k],
    )


async def semantic_search(
    query: str,
    top_k: int = 10,
    min_score: float = 0.3,
) -> list[SearchResult]:
    """Search using semantic embeddings.

    Uses embedding similarity to find relevant documents.

    Args:
        query: Search query
        top_k: Number of results
        min_score: Minimum similarity score

    Returns:
        List of SearchResults sorted by relevance
    """
    try:
        from kagami.core.services.embedding_service import get_embedding_service

        emb_service = get_embedding_service()
        query_embedding = emb_service.embed_text(query)

        # Try to use Weaviate if available
        try:
            from kagami_integrations.elysia.weaviate_e8_adapter import get_weaviate_adapter

            adapter = get_weaviate_adapter()
            await adapter.connect()

            raw_results = await adapter.search(
                query_embedding=query_embedding,
                limit=top_k,
                min_certainty=min_score,
            )

            return [
                SearchResult(
                    content=r.get("content", ""),
                    score=r.get("certainty", 0.0),
                    source=r.get("source", "weaviate"),
                    metadata=r.get("metadata", {}),
                )
                for r in raw_results
            ]
        except Exception as e:
            logger.debug(f"Weaviate not available: {e}")

        # Fallback: use knowledge graph
        try:
            from kagami_knowledge.knowledge_graph import get_knowledge_graph

            kg = get_knowledge_graph()
            result = await kg.query(text_match=query, limit=top_k)

            results = []
            for entity in result.entities[:top_k]:
                results.append(
                    SearchResult(
                        content=entity.name,
                        score=0.5,
                        source=f"kg:{entity.type.value}",
                        metadata={"category": entity.type.value},
                    )
                )

            return sorted(results, reverse=True)[:top_k]
        except Exception as kg_error:
            logger.debug(f"Knowledge graph not available: {kg_error}")
            return []

    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return []


async def hybrid_search(
    query: str,
    top_k: int = 10,
    min_score: float = 0.3,
    semantic_weight: float = 0.7,
) -> list[SearchResult]:
    """Hybrid search combining semantic and keyword matching.

    Combines dense (semantic) and sparse (keyword) retrieval
    for more robust search.

    Args:
        query: Search query
        top_k: Number of results
        min_score: Minimum relevance score
        semantic_weight: Weight for semantic vs keyword (0-1)

    Returns:
        List of SearchResults with combined scores
    """
    # Get semantic results
    semantic_results = await semantic_search(query, top_k=top_k * 2)

    # Keyword search (simple implementation)
    keyword_results = await _keyword_search(query, top_k=top_k * 2)

    # Combine results with weighted scoring
    combined: dict[str, SearchResult] = {}

    for result in semantic_results:
        key = result.content[:100]  # Use first 100 chars as key
        combined[key] = SearchResult(
            content=result.content,
            score=result.score * semantic_weight,
            source=result.source,
            metadata=result.metadata,
        )

    keyword_weight = 1 - semantic_weight
    for result in keyword_results:
        key = result.content[:100]
        if key in combined:
            combined[key].score += result.score * keyword_weight
        else:
            combined[key] = SearchResult(
                content=result.content,
                score=result.score * keyword_weight,
                source=result.source,
                metadata=result.metadata,
            )

    # Sort and filter
    results = sorted(combined.values(), reverse=True)
    results = [r for r in results if r.score >= min_score]

    return results[:top_k]


async def _keyword_search(
    query: str,
    top_k: int = 10,
) -> list[SearchResult]:
    """Simple keyword-based search fallback."""
    try:
        from kagami_knowledge.knowledge_graph import get_knowledge_graph

        kg = get_knowledge_graph()

        # Extract keywords from query
        keywords = query.lower().split()
        keywords = [w for w in keywords if len(w) > 2]

        # Search for each keyword
        results = []
        for keyword in keywords[:3]:  # Limit keywords
            nodes = await kg.query_related(topic=keyword, max_hops=1)
            for node in nodes:
                # Score based on keyword presence
                score = sum(0.3 for kw in keywords if kw in node.content.lower())
                if score > 0:
                    results.append(
                        SearchResult(
                            content=node.content,
                            score=min(1.0, score),
                            source=f"kg:{node.topic}",
                            metadata={"match_type": "keyword"},
                        )
                    )

        return sorted(results, reverse=True)[:top_k]

    except Exception as e:
        logger.debug(f"Keyword search failed: {e}")
        return []


__all__ = [
    "RAGContext",
    "SearchResult",
    "hybrid_search",
    "search_and_retrieve",
    "semantic_search",
]
