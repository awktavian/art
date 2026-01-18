"""Grove Documents Module — Document Parsing and Processing.

Provides document handling capabilities:
- Multi-format parsing (Markdown, Python, text)
- Chunking strategies
- Concept extraction
- Metadata extraction

Created: December 28, 2025
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A document chunk for processing."""

    content: str
    start_line: int
    end_line: int
    chunk_type: str  # "text", "code", "heading", "list[Any]"
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class Document:
    """A parsed document."""

    path: str
    content: str
    chunks: list[Chunk] = field(default_factory=list[Any])
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    concepts: list[str] = field(default_factory=list[Any])
    file_type: str = ""
    total_lines: int = 0
    total_tokens: int = 0

    def __post_init__(self) -> None:
        self.total_lines = len(self.content.split("\n"))
        # Rough token estimate (4 chars per token)
        self.total_tokens = len(self.content) // 4


def parse_document(
    path: str | Path,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> Document:
    """Parse a document into chunks.

    Supports multiple formats:
    - Markdown (.md): Splits by headings
    - Python (.py): Splits by functions/classes
    - Text (.txt): Splits by paragraphs

    Args:
        path: Path to document
        chunk_size: Maximum chunk size in tokens
        chunk_overlap: Overlap between chunks

    Returns:
        Parsed Document with chunks

    Example:
        doc = parse_document("README.md")
        for chunk in doc.chunks:
            print(f"Chunk: {chunk.content[:50]}...")
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    content = path.read_text(encoding="utf-8", errors="ignore")
    file_type = path.suffix.lower()

    # Parse based on file type
    if file_type == ".md":
        chunks = _parse_markdown(content, chunk_size, chunk_overlap)
    elif file_type == ".py":
        chunks = _parse_python(content, chunk_size, chunk_overlap)
    else:
        chunks = _parse_text(content, chunk_size, chunk_overlap)

    # Extract concepts
    concepts = extract_concepts(content)

    # Extract metadata
    metadata = _extract_metadata(content, file_type)

    return Document(
        path=str(path),
        content=content,
        chunks=chunks,
        metadata=metadata,
        concepts=concepts,
        file_type=file_type,
    )


def extract_concepts(
    content: str,
    max_concepts: int = 20,
) -> list[str]:
    """Extract key concepts from content.

    Uses simple heuristics to identify important terms:
    - Title case words (likely proper nouns)
    - Repeated technical terms
    - Code identifiers

    Args:
        content: Document content
        max_concepts: Maximum concepts to extract

    Returns:
        List of concept strings
    """
    concepts: dict[str, int] = {}

    # Extract capitalized phrases (proper nouns, titles)
    title_words = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", content)
    for word in title_words:
        if len(word) > 3:
            concepts[word] = concepts.get(word, 0) + 1

    # Extract code identifiers (CamelCase, snake_case)
    code_identifiers = re.findall(r"\b([A-Z][a-z]+[A-Z][a-z]*|[a-z]+_[a-z_]+)\b", content)
    for identifier in code_identifiers:
        if len(identifier) > 3:
            concepts[identifier] = concepts.get(identifier, 0) + 1

    # Extract technical terms (repeated words)
    words = re.findall(r"\b([a-z]{4,})\b", content.lower())
    for word in words:
        if word not in {"this", "that", "with", "from", "have", "been", "were", "they"}:
            concepts[word] = concepts.get(word, 0) + 1

    # Sort by frequency and return top concepts
    sorted_concepts = sorted(concepts.items(), key=lambda x: x[1], reverse=True)
    return [c[0] for c in sorted_concepts[:max_concepts]]


def _parse_markdown(
    content: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    """Parse Markdown into chunks by headings."""
    chunks: list[Chunk] = []
    lines = content.split("\n")

    current_chunk_lines: list[str] = []
    current_start = 0
    current_type = "text"

    for i, line in enumerate(lines):
        # Check for heading
        if line.startswith("#"):
            # Save previous chunk if exists
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
            # Code block toggle
            current_type = "code" if current_type != "code" else "text"
            current_chunk_lines.append(line)
        else:
            current_chunk_lines.append(line)

            # Check chunk size
            if len("\n".join(current_chunk_lines)) > chunk_size * 4:
                chunks.append(
                    Chunk(
                        content="\n".join(current_chunk_lines),
                        start_line=current_start,
                        end_line=i,
                        chunk_type=current_type,
                    )
                )
                # Overlap
                overlap_lines = current_chunk_lines[-chunk_overlap:] if chunk_overlap else []
                current_chunk_lines = overlap_lines
                current_start = i - len(overlap_lines) + 1

    # Add final chunk
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


def _parse_python(
    content: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    """Parse Python into chunks by functions/classes."""
    import ast

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
        # Fall back to text parsing
        return _parse_text(content, chunk_size, chunk_overlap)

    return chunks if chunks else _parse_text(content, chunk_size, chunk_overlap)


def _parse_text(
    content: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
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

        line_counter += para_lines + 1  # +1 for the blank line

    # Add final chunk
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

    # Extract title from Markdown
    if file_type == ".md":
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if title_match:
            metadata["title"] = title_match.group(1)

    # Extract docstring from Python
    if file_type == ".py":
        docstring_match = re.search(r'^"""(.+?)"""', content, re.DOTALL)
        if docstring_match:
            metadata["description"] = docstring_match.group(1)[:200]

    return metadata


__all__ = [
    "Chunk",
    "Document",
    "extract_concepts",
    "parse_document",
]
