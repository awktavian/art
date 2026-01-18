"""Knowledge Graph — Re-export from kagami.core.agents.knowledge_graph.

This module provides the canonical import path for knowledge graph functionality.

Usage:
    from kagami_knowledge.knowledge_graph import get_knowledge_graph, KnowledgeGraph

鏡
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

# Re-export everything from the actual implementation
from kagami.core.agents.knowledge_graph import (
    Entity,
    EntityType,
    KnowledgeGraph,
    KnowledgeGraphConfig,
    Relation,
    RelationType,
    StorageScope,
    extract_entities_from_text,
    load_knowledge_graph,
    save_knowledge_graph,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Singleton instance
_knowledge_graph: KnowledgeGraph | None = None


def get_knowledge_graph(agent_id: str = "kagami") -> KnowledgeGraph:
    """Get the singleton knowledge graph instance.

    Args:
        agent_id: Agent ID for the knowledge graph (default: "kagami")

    Returns:
        KnowledgeGraph: The global knowledge graph instance
    """
    global _knowledge_graph
    if _knowledge_graph is None:
        _knowledge_graph = KnowledgeGraph(agent_id=agent_id)
        logger.info("Initialized global KnowledgeGraph instance")
    return _knowledge_graph


__all__ = [
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
]
