"""KG Reasoning Engine — Re-export from kagami.core.world_model.

This module provides the canonical import path for knowledge graph reasoning.

Usage:
    from kagami_knowledge.reasoning_engine import get_reasoning_engine

鏡
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Singleton instance
_reasoning_engine: KGReasoningEngine | None = None


@dataclass
class ActionRecommendation:
    """Recommendation from the reasoning engine."""

    action: str
    confidence: float
    rationale: str
    success_rate: float = 0.0
    required_tools: list[str] = field(default_factory=list)
    potential_pitfalls: list[str] = field(default_factory=list)


class KGReasoningEngine:
    """Knowledge Graph Reasoning Engine.

    Provides multi-hop reasoning over the knowledge graph,
    integrating with the causal reasoning engine for counterfactual queries.
    """

    def __init__(self) -> None:
        """Initialize the reasoning engine."""
        self._initialized = False
        logger.info("KGReasoningEngine initialized")

    async def infer_action(
        self,
        intent: str,
        context: dict[str, Any],
    ) -> list[ActionRecommendation]:
        """Infer action recommendations from intent and context.

        Args:
            intent: User intent string
            context: Execution context

        Returns:
            List of action recommendations
        """
        # Import here to avoid circular dependency
        from kagami_knowledge.knowledge_graph import get_knowledge_graph

        kg = get_knowledge_graph()

        # Query knowledge graph for related entities
        query_result = await kg.query(
            entity_types=["action", "intent"],
            text_match=intent,
            limit=5,
        )

        recommendations = []
        for entity in query_result.entities:
            recommendations.append(
                ActionRecommendation(
                    action=entity.name,
                    confidence=0.7,  # Base confidence
                    rationale=f"Related to {entity.type.value}: {entity.name}",
                    success_rate=entity.properties.get("success_rate", 0.5),
                    required_tools=entity.properties.get("tools", []),
                    potential_pitfalls=entity.properties.get("pitfalls", []),
                )
            )

        return recommendations

    async def query_related(
        self,
        topic: str,
        max_hops: int = 2,
    ) -> list[Any]:
        """Query for related knowledge nodes.

        Args:
            topic: Topic to search for
            max_hops: Maximum hops in graph traversal

        Returns:
            List of related nodes
        """
        from kagami_knowledge.knowledge_graph import get_knowledge_graph

        kg = get_knowledge_graph()

        # Simple implementation - get entities matching topic
        result = await kg.query(
            text_match=topic,
            limit=max_hops * 5,
        )

        return result.entities


def get_reasoning_engine() -> KGReasoningEngine:
    """Get the singleton reasoning engine instance.

    Returns:
        KGReasoningEngine: The global reasoning engine instance
    """
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = KGReasoningEngine()
        logger.info("Initialized global KGReasoningEngine instance")
    return _reasoning_engine


__all__ = [
    "ActionRecommendation",
    "KGReasoningEngine",
    "get_reasoning_engine",
]
