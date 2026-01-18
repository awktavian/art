"""Receipt to Knowledge Graph — Extract knowledge from receipts.

Converts execution receipts into knowledge graph entities and relations,
enabling learning from experience.

Usage:
    from kagami_knowledge.receipt_to_kg import get_receipt_extractor

鏡
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Singleton instance
_receipt_extractor: ReceiptExtractor | None = None


class ReceiptExtractor:
    """Extract knowledge from execution receipts.

    Processes PLAN/EXECUTE/VERIFY receipts to populate the knowledge graph
    with learned patterns, successful strategies, and failure modes.
    """

    def __init__(self) -> None:
        """Initialize receipt extractor."""
        self._initialized = False
        logger.info("ReceiptExtractor initialized")

    async def populate_kg(
        self,
        receipts: list[dict[str, Any]],
    ) -> int:
        """Populate knowledge graph from receipts.

        Args:
            receipts: List of receipt dictionaries

        Returns:
            Number of knowledge nodes added
        """
        from kagami_knowledge.knowledge_graph import (
            Entity,
            EntityType,
            get_knowledge_graph,
        )

        kg = get_knowledge_graph()
        nodes_added = 0

        for receipt in receipts:
            # Extract entities from receipt
            phase = receipt.get("phase", "unknown")
            action = receipt.get("action", "")
            result = receipt.get("result", {})

            # Create entity for the action
            if action:
                entity = Entity(
                    id=f"receipt:{receipt.get('id', 'unknown')}",
                    type=EntityType.ACTION,
                    name=action,
                    properties={
                        "phase": phase,
                        "success": result.get("success", False),
                        "timestamp": receipt.get("timestamp"),
                    },
                    source="receipt_extractor",
                )

                await kg.add_entity(entity)
                nodes_added += 1

        return nodes_added

    async def extract_patterns(
        self,
        receipts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract patterns from a batch of receipts.

        Args:
            receipts: List of receipt dictionaries

        Returns:
            List of extracted patterns
        """
        patterns = []

        # Group receipts by action type
        action_groups: dict[str, list[dict]] = {}
        for receipt in receipts:
            action = receipt.get("action", "unknown")
            if action not in action_groups:
                action_groups[action] = []
            action_groups[action].append(receipt)

        # Find patterns in each group
        for action, group in action_groups.items():
            if len(group) >= 2:
                success_count = sum(1 for r in group if r.get("result", {}).get("success", False))
                patterns.append(
                    {
                        "action": action,
                        "count": len(group),
                        "success_rate": success_count / len(group),
                        "pattern_type": "frequency",
                    }
                )

        return patterns


def get_receipt_extractor() -> ReceiptExtractor:
    """Get the singleton receipt extractor instance.

    Returns:
        ReceiptExtractor: The global receipt extractor instance
    """
    global _receipt_extractor
    if _receipt_extractor is None:
        _receipt_extractor = ReceiptExtractor()
        logger.info("Initialized global ReceiptExtractor instance")
    return _receipt_extractor


__all__ = [
    "ReceiptExtractor",
    "get_receipt_extractor",
]
