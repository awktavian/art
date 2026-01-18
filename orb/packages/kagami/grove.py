"""Grove Capability Layer — Knowledge Infrastructure (CONSOLIDATED).

Grove (e₆, Elliptic catastrophe, D₄⁻) is The Seeker.
This module provides research, RAG, and document processing tools.

MODULES (consolidated from kagami/grove/):
==========================================
- RAG: Retrieval-Augmented Generation
- Documents: Document parsing and extraction
- Synthesis: Knowledge synthesis and summarization

USAGE:
======
from kagami.grove import (
    search_and_retrieve,
    parse_document,
    synthesize_knowledge,
)

Created: December 28, 2025
Consolidated: December 31, 2025
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# RAG MODULE
# =============================================================================


@dataclass
class SearchResult:
    """A single search result."""

    content: str
    score: float
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
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
    """Search knowledge base and retrieve relevant context."""
    results = await hybrid_search(query, top_k=top_k, min_score=min_score)

    if sources:
        results = [r for r in results if any(s in r.source for s in sources)]

    return RAGContext(query=query, results=results[:top_k])


async def semantic_search(
    query: str,
    top_k: int = 10,
    min_score: float = 0.3,
) -> list[SearchResult]:
    """Search using semantic embeddings.

    RELIABILITY FIX (Jan 2026): Explicit error handling instead of silent fallbacks.
    Logs actual errors instead of silently demoting to fallback systems.
    """
    # Try primary search backend (Weaviate)
    weaviate_available = False
    try:
        from kagami.core.services.embedding_service import get_embedding_service

        emb_service = get_embedding_service()
        query_embedding = emb_service.embed_text(query)

        try:
            from kagami_integrations.elysia.weaviate_e8_adapter import get_weaviate_adapter

            adapter = get_weaviate_adapter()
            await adapter.connect()
            weaviate_available = True

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
        except ImportError:
            logger.debug("Weaviate adapter not installed, using knowledge graph fallback")
        except ConnectionError as e:
            logger.warning(f"Weaviate connection failed: {e}")
        except Exception as e:
            logger.warning(f"Weaviate search error: {e}")

    except ImportError:
        logger.debug("Embedding service not installed")
    except Exception as e:
        logger.warning(f"Embedding service error: {e}")

    # Fallback to knowledge graph only if Weaviate not available
    if not weaviate_available:
        try:
            from kagami_knowledge.knowledge_graph import get_knowledge_graph

            kg = get_knowledge_graph()
            result = await kg.query(text_match=query, limit=top_k)

            results = []
            for entity in result.entities[:top_k]:
                results.append(
                    SearchResult(
                        content=entity.name,
                        score=0.5,  # Base score for KG results
                        source=f"kg:{entity.type.value}",
                        metadata={"category": entity.type.value, "fallback": True},
                    )
                )

            if results:
                logger.info(f"Using knowledge graph fallback: {len(results)} results")
            return sorted(results, reverse=True)[:top_k]
        except ImportError:
            logger.debug("Knowledge graph not installed")
        except Exception as kg_error:
            logger.warning(f"Knowledge graph search error: {kg_error}")

    return []


async def hybrid_search(
    query: str,
    top_k: int = 10,
    min_score: float = 0.3,
    semantic_weight: float = 0.7,
) -> list[SearchResult]:
    """Hybrid search combining semantic and keyword matching."""
    semantic_results = await semantic_search(query, top_k=top_k * 2)
    keyword_results = await _keyword_search(query, top_k=top_k * 2)

    combined: dict[str, SearchResult] = {}

    for result in semantic_results:
        key = result.content[:100]
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

    results = sorted(combined.values(), reverse=True)
    results = [r for r in results if r.score >= min_score]

    return results[:top_k]


async def _keyword_search(query: str, top_k: int = 10) -> list[SearchResult]:
    """Simple keyword-based search fallback using knowledge graph."""
    try:
        from kagami_knowledge.knowledge_graph import get_knowledge_graph

        kg = get_knowledge_graph()
        keywords = [w for w in query.lower().split() if len(w) > 2]

        results = []
        for keyword in keywords[:3]:
            result = await kg.query(text_match=keyword, limit=top_k)
            for entity in result.entities:
                score = sum(0.3 for kw in keywords if kw in entity.name.lower())
                if score > 0:
                    results.append(
                        SearchResult(
                            content=entity.name,
                            score=min(1.0, score),
                            source=f"kg:{entity.type.value}",
                            metadata={"match_type": "keyword"},
                        )
                    )

        return sorted(results, reverse=True)[:top_k]

    except Exception as e:
        logger.debug(f"Keyword search failed: {e}")
        return []


# =============================================================================
# DOCUMENTS MODULE
# =============================================================================


@dataclass
class Chunk:
    """A document chunk for processing."""

    content: str
    start_line: int
    end_line: int
    chunk_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Document:
    """A parsed document."""

    path: str
    content: str
    chunks: list[Chunk] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    concepts: list[str] = field(default_factory=list)
    file_type: str = ""
    total_lines: int = 0
    total_tokens: int = 0

    def __post_init__(self) -> None:
        self.total_lines = len(self.content.split("\n"))
        self.total_tokens = len(self.content) // 4


def parse_document(
    path: str | Path,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> Document:
    """Parse a document into chunks."""
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    content = path.read_text(encoding="utf-8", errors="ignore")
    file_type = path.suffix.lower()

    if file_type == ".md":
        chunks = _parse_markdown(content, chunk_size, chunk_overlap)
    elif file_type == ".py":
        chunks = _parse_python(content, chunk_size, chunk_overlap)
    else:
        chunks = _parse_text(content, chunk_size, chunk_overlap)

    concepts = extract_concepts(content)
    metadata = _extract_metadata(content, file_type)

    return Document(
        path=str(path),
        content=content,
        chunks=chunks,
        metadata=metadata,
        concepts=concepts,
        file_type=file_type,
    )


def extract_concepts(content: str, max_concepts: int = 20) -> list[str]:
    """Extract key concepts from content."""
    concepts: dict[str, int] = {}

    title_words = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", content)
    for word in title_words:
        if len(word) > 3:
            concepts[word] = concepts.get(word, 0) + 1

    code_identifiers = re.findall(r"\b([A-Z][a-z]+[A-Z][a-z]*|[a-z]+_[a-z_]+)\b", content)
    for identifier in code_identifiers:
        if len(identifier) > 3:
            concepts[identifier] = concepts.get(identifier, 0) + 1

    words = re.findall(r"\b([a-z]{4,})\b", content.lower())
    stopwords = {"this", "that", "with", "from", "have", "been", "were", "they"}
    for word in words:
        if word not in stopwords:
            concepts[word] = concepts.get(word, 0) + 1

    sorted_concepts = sorted(concepts.items(), key=lambda x: x[1], reverse=True)
    return [c[0] for c in sorted_concepts[:max_concepts]]


def _parse_markdown(content: str, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    """Parse Markdown into chunks by headings."""
    chunks: list[Chunk] = []
    lines = content.split("\n")
    current_chunk_lines: list[str] = []
    current_start = 0
    current_type = "text"

    for i, line in enumerate(lines):
        if line.startswith("#"):
            if current_chunk_lines:
                chunks.append(
                    Chunk(
                        content="\n".join(current_chunk_lines),
                        start_line=current_start,
                        end_line=i - 1,
                        chunk_type=current_type,
                    )
                )
            current_chunk_lines = [line]
            current_start = i
            current_type = "heading"
        elif line.startswith("```"):
            current_type = "code" if current_type != "code" else "text"
            current_chunk_lines.append(line)
        else:
            current_chunk_lines.append(line)
            if len("\n".join(current_chunk_lines)) > chunk_size * 4:
                chunks.append(
                    Chunk(
                        content="\n".join(current_chunk_lines),
                        start_line=current_start,
                        end_line=i,
                        chunk_type=current_type,
                    )
                )
                overlap_lines = current_chunk_lines[-chunk_overlap:] if chunk_overlap else []
                current_chunk_lines = overlap_lines
                current_start = i - len(overlap_lines) + 1

    if current_chunk_lines:
        chunks.append(
            Chunk(
                content="\n".join(current_chunk_lines),
                start_line=current_start,
                end_line=len(lines) - 1,
                chunk_type=current_type,
            )
        )

    return chunks


def _parse_python(content: str, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    """Parse Python into chunks by functions/classes."""
    chunks: list[Chunk] = []
    lines = content.split("\n")

    try:
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                start = node.lineno - 1
                end = getattr(node, "end_lineno", start + 1)
                chunk_content = "\n".join(lines[start:end])
                chunks.append(
                    Chunk(
                        content=chunk_content,
                        start_line=start,
                        end_line=end,
                        chunk_type="code",
                        metadata={"name": node.name},
                    )
                )

    except SyntaxError:
        return _parse_text(content, chunk_size, chunk_overlap)

    return chunks if chunks else _parse_text(content, chunk_size, chunk_overlap)


def _parse_text(content: str, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    """Parse plain text into chunks by paragraphs."""
    chunks: list[Chunk] = []
    paragraphs = content.split("\n\n")
    current_chunk_content = ""
    current_start = 0
    line_counter = 0

    for para in paragraphs:
        para_lines = para.count("\n") + 1

        if len(current_chunk_content) + len(para) > chunk_size * 4:
            if current_chunk_content:
                chunks.append(
                    Chunk(
                        content=current_chunk_content,
                        start_line=current_start,
                        end_line=line_counter - 1,
                        chunk_type="text",
                    )
                )
            current_chunk_content = para
            current_start = line_counter
        else:
            current_chunk_content += "\n\n" + para if current_chunk_content else para

        line_counter += para_lines + 1

    if current_chunk_content:
        chunks.append(
            Chunk(
                content=current_chunk_content,
                start_line=current_start,
                end_line=line_counter,
                chunk_type="text",
            )
        )

    return chunks


def _extract_metadata(content: str, file_type: str) -> dict[str, Any]:
    """Extract metadata from document."""
    metadata: dict[str, Any] = {
        "file_type": file_type,
        "char_count": len(content),
        "word_count": len(content.split()),
    }

    if file_type == ".md":
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if title_match:
            metadata["title"] = title_match.group(1)

    if file_type == ".py":
        docstring_match = re.search(r'^"""(.+?)"""', content, re.DOTALL)
        if docstring_match:
            metadata["description"] = docstring_match.group(1)[:200]

    return metadata


# =============================================================================
# SYNTHESIS MODULE
# =============================================================================


@dataclass
class Entity:
    """An extracted entity."""

    name: str
    entity_type: str
    mentions: int = 1
    context: str = ""


@dataclass
class Relationship:
    """A relationship between entities."""

    source: str
    target: str
    relationship_type: str
    confidence: float = 0.5


@dataclass
class KnowledgeSynthesis:
    """Synthesized knowledge from multiple sources."""

    summary: str
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.0
    grove_voice: str = ""

    def __post_init__(self) -> None:
        if not self.grove_voice:
            self.grove_voice = (
                f"I've traced through {len(self.sources)} sources and found "
                f"{len(self.entities)} key concepts connected by "
                f"{len(self.relationships)} relationships..."
            )


def synthesize_knowledge(
    documents: list[Any],
    question: str | None = None,
) -> KnowledgeSynthesis:
    """Synthesize knowledge from multiple documents."""
    all_content = "\n\n".join(doc.content for doc in documents)
    sources = [doc.path for doc in documents]

    entities = extract_entities_from_content(all_content)
    relationships = _extract_relationships(all_content, entities)
    key_points = _extract_key_points(all_content, question)
    summary = _generate_summary(all_content, question, key_points)
    confidence = min(1.0, 0.3 + 0.1 * len(entities) + 0.2 * len(key_points))

    return KnowledgeSynthesis(
        summary=summary,
        entities=entities,
        relationships=relationships,
        key_points=key_points,
        sources=sources,
        confidence=confidence,
    )


def summarize_documents(documents: list[Any], max_length: int = 500) -> str:
    """Generate a concise summary of multiple documents."""
    synthesis = synthesize_knowledge(documents)
    return synthesis.summary[: max_length * 5]


def extract_entities_from_content(content: str, max_entities: int = 30) -> list[Entity]:
    """Extract entities from content."""
    entities: dict[str, Entity] = {}

    camel_case = re.findall(r"\b([A-Z][a-z]+[A-Z][a-z]*)\b", content)
    for term in camel_case:
        if term not in entities:
            entities[term] = Entity(name=term, entity_type="concept")
        else:
            entities[term].mentions += 1

    tech_patterns = [
        (r"\b(Python|JavaScript|TypeScript|Rust|Go)\b", "technology"),
        (r"\b(React|Vue|Angular|FastAPI|Django)\b", "framework"),
        (r"\b(PostgreSQL|MongoDB|Redis|Weaviate)\b", "database"),
        (r"\b(AWS|GCP|Azure|Docker|Kubernetes)\b", "infrastructure"),
    ]

    for pattern, entity_type in tech_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            if match not in entities:
                entities[match] = Entity(name=match, entity_type=entity_type)
            else:
                entities[match].mentions += 1

    proper_nouns = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", content)
    for noun in proper_nouns:
        if noun not in entities and len(noun) > 5:
            entities[noun] = Entity(name=noun, entity_type="concept")
        elif noun in entities:
            entities[noun].mentions += 1

    sorted_entities = sorted(entities.values(), key=lambda e: e.mentions, reverse=True)
    return sorted_entities[:max_entities]


# Alias for backward compatibility
extract_entities = extract_entities_from_content


def _extract_relationships(content: str, entities: list[Entity]) -> list[Relationship]:
    """Extract relationships between entities."""
    relationships: list[Relationship] = []
    entity_names = {e.name.lower() for e in entities}

    patterns = [
        (r"(\w+)\s+(?:uses|using|with)\s+(\w+)", "uses"),
        (r"(\w+)\s+(?:extends|inherits from)\s+(\w+)", "extends"),
        (r"(\w+)\s+(?:depends on|requires)\s+(\w+)", "depends_on"),
        (r"(\w+)\s+(?:and|or|with)\s+(\w+)", "related_to"),
    ]

    for pattern, rel_type in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for source, target in matches:
            if source.lower() in entity_names and target.lower() in entity_names:
                relationships.append(
                    Relationship(
                        source=source,
                        target=target,
                        relationship_type=rel_type,
                        confidence=0.6,
                    )
                )

    return relationships[:20]


def _extract_key_points(content: str, question: str | None) -> list[str]:
    """Extract key points from content."""
    key_points: list[str] = []

    bullets = re.findall(r"^[-*]\s+(.+)$", content, re.MULTILINE)
    key_points.extend(bullets[:5])

    numbered = re.findall(r"^\d+[.)]\s+(.+)$", content, re.MULTILINE)
    key_points.extend(numbered[:5])

    if question:
        keywords = [w.lower() for w in question.split() if len(w) > 3]
        sentences = re.split(r"[.!?]", content)
        for sentence in sentences:
            if any(kw in sentence.lower() for kw in keywords):
                clean = sentence.strip()
                if 20 < len(clean) < 200 and clean not in key_points:
                    key_points.append(clean)
                    if len(key_points) >= 10:
                        break

    return key_points[:10]


def _generate_summary(content: str, question: str | None, key_points: list[str]) -> str:
    """Generate summary from content and key points."""
    if key_points:
        summary_parts = ["Key findings:"]
        for i, point in enumerate(key_points[:5], 1):
            summary_parts.append(f"{i}. {point}")

        if question:
            summary_parts.insert(0, f"Regarding: {question}\n")

        return "\n".join(summary_parts)

    paragraphs = content.split("\n\n")
    for para in paragraphs:
        clean = para.strip()
        if len(clean) > 100 and not clean.startswith("#"):
            return clean[:500] + "..."

    return "No summary available."


__all__ = [
    "Chunk",
    "Document",
    "Entity",
    "KnowledgeSynthesis",
    "RAGContext",
    "Relationship",
    "SearchResult",
    "extract_concepts",
    "extract_entities",
    "hybrid_search",
    "parse_document",
    "search_and_retrieve",
    "semantic_search",
    "summarize_documents",
    "synthesize_knowledge",
]
