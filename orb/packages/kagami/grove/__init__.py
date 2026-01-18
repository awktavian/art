"""Grove Capability Layer — Knowledge Infrastructure.

Grove (e₆, Elliptic catastrophe, D₄⁻) is The Seeker.
This package provides research, RAG, and document processing tools.

MODULES:
========
- rag: Retrieval-Augmented Generation
- documents: Document parsing and extraction
- synthesis: Knowledge synthesis and summarization

USAGE:
======
from kagami.grove import (
    search_and_retrieve,
    parse_document,
    synthesize_knowledge,
)

# RAG search
results = await search_and_retrieve(
    query="How does authentication work?",
    top_k=5,
)

# Parse document
doc = parse_document("README.md")

# Synthesize
summary = synthesize_knowledge(documents=[doc], question="What is this project?")

Created: December 28, 2025
"""

from kagami.grove.modules.documents import (
    Chunk,
    Document,
    extract_concepts,
    parse_document,
)
from kagami.grove.modules.rag import (
    SearchResult,
    hybrid_search,
    search_and_retrieve,
    semantic_search,
)
from kagami.grove.modules.synthesis import (
    KnowledgeSynthesis,
    extract_entities,
    summarize_documents,
    synthesize_knowledge,
)

__all__ = [
    "Chunk",
    "Document",
    "KnowledgeSynthesis",
    "SearchResult",
    "extract_concepts",
    "extract_entities",
    "hybrid_search",
    # Documents
    "parse_document",
    # RAG
    "search_and_retrieve",
    "semantic_search",
    "summarize_documents",
    # Synthesis
    "synthesize_knowledge",
]
