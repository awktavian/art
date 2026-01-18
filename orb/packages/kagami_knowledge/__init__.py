"""kagami_knowledge — Re-export module for knowledge subsystems.

This module provides a clean namespace for knowledge-related functionality
that lives in various places within kagami.core.

Re-exports:
- knowledge_graph: Agent knowledge graph (property graph memory)
- reasoning_engine: Causal reasoning and KG inference
- common_sense: Background knowledge integration
- receipt_to_kg: Receipt extraction to knowledge graph

鏡
"""

from kagami_knowledge.knowledge_graph import (
    Entity,
    EntityType,
    KnowledgeGraph,
    KnowledgeGraphConfig,
    Relation,
    RelationType,
    StorageScope,
    extract_entities_from_text,
    get_knowledge_graph,
    load_knowledge_graph,
    save_knowledge_graph,
)
from kagami_knowledge.reasoning_engine import (
    KGReasoningEngine,
    get_reasoning_engine,
)

__all__ = [
    # Knowledge Graph
    "Entity",
    "EntityType",
    "KnowledgeGraph",
    "KnowledgeGraphConfig",
    "Relation",
    "RelationType",
    "StorageScope",
    "extract_entities_from_text",
    "get_knowledge_graph",
    "load_knowledge_graph",
    "save_knowledge_graph",
    # Reasoning
    "KGReasoningEngine",
    "get_reasoning_engine",
]
