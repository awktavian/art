"""Grove Synthesis Module — Knowledge Synthesis and Summarization.

Provides synthesis capabilities:
- Multi-document summarization
- Entity extraction
- Relationship mapping
- Question answering synthesis

Created: December 28, 2025
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """An extracted entity."""

    name: str
    entity_type: str  # "person", "concept", "technology", "organization"
    mentions: int = 1
    context: str = ""


@dataclass
class Relationship:
    """A relationship between entities."""

    source: str
    target: str
    relationship_type: str  # "uses", "extends", "depends_on", "related_to"
    confidence: float = 0.5


@dataclass
class KnowledgeSynthesis:
    """Synthesized knowledge from multiple sources."""

    summary: str
    entities: list[Entity] = field(default_factory=list[Any])
    relationships: list[Relationship] = field(default_factory=list[Any])
    key_points: list[str] = field(default_factory=list[Any])
    sources: list[str] = field(default_factory=list[Any])
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
    documents: list[Any],  # List of Document objects
    question: str | None = None,
) -> KnowledgeSynthesis:
    """Synthesize knowledge from multiple documents.

    Extracts entities, relationships, and key points,
    then generates a coherent summary.

    Args:
        documents: List of Document objects to synthesize
        question: Optional question to focus synthesis

    Returns:
        KnowledgeSynthesis with summary and extracted knowledge

    Example:
        docs = [parse_document(f) for f in files]
        synthesis = synthesize_knowledge(docs, "What is the architecture?")
    """
    # Combine content from all documents
    all_content = "\n\n".join(doc.content for doc in documents)
    sources = [doc.path for doc in documents]

    # Extract entities
    entities = extract_entities(all_content)

    # Extract relationships (simple heuristic)
    relationships = _extract_relationships(all_content, entities)

    # Extract key points
    key_points = _extract_key_points(all_content, question)

    # Generate summary
    summary = _generate_summary(all_content, question, key_points)

    # Calculate confidence based on evidence
    confidence = min(1.0, 0.3 + 0.1 * len(entities) + 0.2 * len(key_points))

    return KnowledgeSynthesis(
        summary=summary,
        entities=entities,
        relationships=relationships,
        key_points=key_points,
        sources=sources,
        confidence=confidence,
    )


def summarize_documents(
    documents: list[Any],
    max_length: int = 500,
) -> str:
    """Generate a concise summary of multiple documents.

    Args:
        documents: List of Document objects
        max_length: Maximum summary length in words

    Returns:
        Summary string
    """
    synthesis = synthesize_knowledge(documents)
    return synthesis.summary[: max_length * 5]  # Rough word to char conversion


def extract_entities(
    content: str,
    max_entities: int = 30,
) -> list[Entity]:
    """Extract entities from content.

    Identifies:
    - Technical concepts (CamelCase)
    - Technologies (known patterns)
    - Proper nouns (Title Case)
    - Code identifiers

    Args:
        content: Document content
        max_entities: Maximum entities to extract

    Returns:
        List of Entity objects
    """
    entities: dict[str, Entity] = {}

    # Technical terms (CamelCase)
    camel_case = re.findall(r"\b([A-Z][a-z]+[A-Z][a-z]*)\b", content)
    for term in camel_case:
        if term not in entities:
            entities[term] = Entity(name=term, entity_type="concept")
        else:
            entities[term].mentions += 1

    # Technology patterns
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

    # Proper nouns (consecutive capitalized words)
    proper_nouns = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", content)
    for noun in proper_nouns:
        if noun not in entities and len(noun) > 5:
            entities[noun] = Entity(name=noun, entity_type="concept")
        elif noun in entities:
            entities[noun].mentions += 1

    # Sort by mentions and return top entities
    sorted_entities = sorted(
        entities.values(),
        key=lambda e: e.mentions,
        reverse=True,
    )
    return sorted_entities[:max_entities]


def _extract_relationships(
    content: str,
    entities: list[Entity],
) -> list[Relationship]:
    """Extract relationships between entities."""
    relationships: list[Relationship] = []
    entity_names = {e.name.lower() for e in entities}

    # Relationship patterns
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

    return relationships[:20]  # Limit relationships


def _extract_key_points(
    content: str,
    question: str | None,
) -> list[str]:
    """Extract key points from content."""
    key_points: list[str] = []

    # Extract bullet points
    bullets = re.findall(r"^[-*]\s+(.+)$", content, re.MULTILINE)
    key_points.extend(bullets[:5])

    # Extract numbered points
    numbered = re.findall(r"^\d+[.)]\s+(.+)$", content, re.MULTILINE)
    key_points.extend(numbered[:5])

    # Extract sentences containing question keywords
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


def _generate_summary(
    content: str,
    question: str | None,
    key_points: list[str],
) -> str:
    """Generate summary from content and key points."""
    # Simple extractive summary
    if key_points:
        summary_parts = [
            "Key findings:",
        ]
        for i, point in enumerate(key_points[:5], 1):
            summary_parts.append(f"{i}. {point}")

        if question:
            summary_parts.insert(0, f"Regarding: {question}\n")

        return "\n".join(summary_parts)

    # Fallback: extract first meaningful paragraph
    paragraphs = content.split("\n\n")
    for para in paragraphs:
        clean = para.strip()
        if len(clean) > 100 and not clean.startswith("#"):
            return clean[:500] + "..."

    return "No summary available."


__all__ = [
    "Entity",
    "KnowledgeSynthesis",
    "Relationship",
    "extract_entities",
    "summarize_documents",
    "synthesize_knowledge",
]
