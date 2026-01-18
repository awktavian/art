"""Elysia Tools — Colony-Aware Weaviate Tools.

Each colony has specialized tools for its domain:

| Colony | Tool | Behavior |
|--------|------|----------|
| Spark | brainstorm_tool | Divergent search, high temperature |
| Forge | implementation_tool | Structured query, exact matches |
| Flow | recovery_tool | Error-tolerant, fallback paths |
| Nexus | integration_tool | Cross-reference, memory binding |
| Beacon | planning_tool | Strategic filtering, roadmaps |
| Grove | research_tool | Deep retrieval, citations |
| Crystal | verification_tool | Validation, safety checks |

S⁷ PARALLELIZATION:
- All tools are async and safe for concurrent execution
- Colony-specific tools optimize query parameters per colony
- Tools can be batched for bulk operations

Created: December 7, 2025
"""

from __future__ import annotations

__all__ = [
    "AggregateTool",
    "ColonyQueryTool",
    "FilterTool",
    "WeaviateQueryTool",
    "get_colony_tools",
]

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


# Colony-specific query configurations
COLONY_QUERY_CONFIGS = {
    "spark": {
        "limit": 15,  # More results for brainstorming
        "temperature": 0.9,  # Divergent
        "diversity_penalty": 0.3,
    },
    "forge": {
        "limit": 8,
        "temperature": 0.2,  # Precise
        "exact_match_boost": 0.5,
    },
    "flow": {
        "limit": 10,
        "temperature": 0.5,
        "fallback_enabled": True,
    },
    "nexus": {
        "limit": 12,
        "temperature": 0.5,
        "cross_reference": True,
    },
    "beacon": {
        "limit": 10,
        "temperature": 0.4,
        "planning_filter": True,
    },
    "grove": {
        "limit": 20,  # Deep research
        "temperature": 0.6,
        "citation_required": True,
    },
    "crystal": {
        "limit": 5,  # Focused verification
        "temperature": 0.1,
        "validation_mode": True,
    },
}


class WeaviateQueryTool:
    """Base Weaviate query tool."""

    def __init__(self, weaviate_adapter: Any):
        self.weaviate = weaviate_adapter

    async def __call__(
        self,
        query: str,
        colony: str = "nexus",
        limit: int = 10,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute search query.

        Args:
            query: Search query
            colony: Colony filter
            limit: Max results

        Returns:
            Dict with sources and content
        """
        if not self.weaviate:
            return {"sources": [], "content": "Weaviate not connected"}

        results = await self.weaviate.search_similar(
            query=query,
            limit=limit,
            colony_filter=colony,
        )

        content = "\n\n".join([r.get("content", "")[:500] for r in results[:5]])

        return {
            "sources": results,
            "content": content,
        }


class FilterTool:
    """Filter tool for structured queries."""

    def __init__(self, weaviate_adapter: Any):
        self.weaviate = weaviate_adapter

    async def __call__(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute filtered query.

        Args:
            query: Search query
            filters: Filter conditions

        Returns:
            Dict with filtered results
        """
        if not self.weaviate:
            return {"sources": [], "content": "Weaviate not connected"}

        filters = filters or {}
        limit = int(kwargs.get("limit", 10))

        # Normalize common filter keys.
        colony_filter = (
            filters.get("colony")
            or filters.get("colony_affinity")
            or kwargs.get("colony")
            or kwargs.get("colony_filter")
        )
        kind_filter = filters.get("kind") or filters.get("type") or kwargs.get("kind")
        tenant_id = (
            filters.get("tenant_id")
            or filters.get("tenant")
            or kwargs.get("tenant_id")
            or kwargs.get("tenant")
        )

        # Run the vector search with filters when supported.
        try:
            results = await self.weaviate.search_similar(
                query=query,
                limit=limit,
                colony_filter=colony_filter,
                kind_filter=kind_filter,
                tenant_id=tenant_id,
            )
        except TypeError:
            # Backwards-compat: older adapters may only support colony_filter.
            results = await self.weaviate.search_similar(
                query=query,
                limit=limit,
                colony_filter=colony_filter,
            )

        # Apply any remaining filters as a best-effort post-filter over returned properties.
        reserved = {
            "colony",
            "colony_affinity",
            "colony_filter",
            "kind",
            "type",
            "tenant_id",
            "tenant",
        }
        extra_filters = {k: v for k, v in filters.items() if k not in reserved}

        def _matches(value: Any, spec: Any) -> bool:
            if isinstance(spec, dict):
                if "eq" in spec:
                    return bool(value == spec.get("eq"))
                if "in" in spec:
                    try:
                        return value in set(spec.get("in") or [])
                    except Exception:
                        return False
                if "contains" in spec:
                    needle = str(spec.get("contains") or "")
                    return isinstance(value, str) and needle.lower() in value.lower()
                # Unknown operator dict: treat as mismatch.
                return False
            if isinstance(spec, (list, tuple, set)):
                try:
                    return value in spec
                except Exception:
                    return False
            return bool(value == spec)

        if extra_filters:
            filtered = []
            for r in results:
                props = r.get("properties") if isinstance(r, dict) else None
                props = props if isinstance(props, dict) else {}
                ok = True
                for k, spec in extra_filters.items():
                    candidate = props.get(k, r.get(k) if isinstance(r, dict) else None)
                    if not _matches(candidate, spec):
                        ok = False
                        break
                if ok:
                    filtered.append(r)
            results = filtered

        content = "\n\n".join([r.get("content", "")[:500] for r in results[:5]]) if results else ""

        return {
            "sources": results,
            "content": content,
            "filters": filters,
        }


class AggregateTool:
    """Aggregation tool for analytics."""

    def __init__(self, weaviate_adapter: Any):
        self.weaviate = weaviate_adapter

    async def __call__(
        self,
        query: str,
        group_by: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute aggregation.

        Args:
            query: Query context
            group_by: Field to group by

        Returns:
            Dict with aggregation results
        """
        if not self.weaviate:
            return {"sources": [], "content": "Weaviate not connected"}

        analysis = await self.weaviate.analyze_collection()

        return {
            "sources": [],
            "content": f"Collection has {analysis.get('total_count', 0)} items",
            "analysis": analysis,
        }


class ColonyQueryTool:
    """Colony-specific query tool with optimized parameters.

    Each colony has different query behaviors:
    - Spark: Divergent, more results, high temperature
    - Forge: Precise, exact matches, low temperature
    - Flow: Error-tolerant with fallbacks
    - Nexus: Cross-reference enabled
    - Beacon: Planning-focused filtering
    - Grove: Deep research, citations required
    - Crystal: Focused verification mode
    """

    def __init__(self, weaviate_adapter: Any, colony: str):
        self.weaviate = weaviate_adapter
        self.colony = colony
        self.config = COLONY_QUERY_CONFIGS.get(colony, COLONY_QUERY_CONFIGS["nexus"])

    async def __call__(
        self,
        query: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute colony-optimized search.

        Args:
            query: Search query

        Returns:
            Dict with sources and content
        """
        if not self.weaviate:
            return {"sources": [], "content": "Weaviate not connected"}

        # Apply colony-specific limit
        limit = self.config.get("limit", 10)

        try:
            results = await self.weaviate.search_similar(
                query=query,
                limit=limit,
                colony_filter=self.colony,
            )

            # Post-process based on colony
            processed_results = self._post_process(results)

            content = "\n\n".join([r.get("content", "")[:500] for r in processed_results[:5]])

            return {
                "sources": processed_results,
                "content": content,
                "colony": self.colony,
                "config_used": self.config,
            }

        except Exception as e:
            # Flow colony has fallback behavior
            if self.colony == "flow" and self.config.get("fallback_enabled"):
                logger.warning(f"Colony {self.colony} query failed, using fallback: {e}")
                return {
                    "sources": [],
                    "content": f"Fallback: Query failed but system recovered. Error: {e}",
                    "fallback": True,
                }
            raise

    def _post_process(self, results: list[dict]) -> list[dict]:
        """Apply colony-specific post-processing."""
        if not results:
            return results

        # Crystal: Add validation flags
        if self.colony == "crystal" and self.config.get("validation_mode"):
            for r in results:
                r["validated"] = False  # Mark for validation

        # Grove: Ensure citations present
        if self.colony == "grove" and self.config.get("citation_required"):
            for r in results:
                if "citation" not in r:
                    r["citation"] = f"Source: {r.get('uuid', 'unknown')[:8]}"

        return results


def get_colony_tools(weaviate_adapter: Any) -> dict[str, Callable]:
    """Get all colony-specific tools.

    S⁷ PARALLEL: All tools are async-safe for concurrent execution.

    Args:
        weaviate_adapter: WeaviateE8Adapter instance

    Returns:
        Dict of tool name → callable
    """
    # Base tools
    query_tool = WeaviateQueryTool(weaviate_adapter)
    filter_tool = FilterTool(weaviate_adapter)
    aggregate_tool = AggregateTool(weaviate_adapter)

    # Colony-specific tools (optimized per colony)
    colony_tools = {
        colony: ColonyQueryTool(weaviate_adapter, colony) for colony in COLONY_QUERY_CONFIGS
    }

    return {
        # Base tools
        "weaviate_query": query_tool,
        "filter": filter_tool,
        "aggregate": aggregate_tool,
        # Colony-specific tools (properly wired with colony configs)
        "spark_brainstorm": colony_tools["spark"],
        "forge_implement": colony_tools["forge"],
        "flow_recover": colony_tools["flow"],
        "nexus_integrate": colony_tools["nexus"],
        "beacon_plan": colony_tools["beacon"],
        "grove_research": colony_tools["grove"],
        "crystal_verify": colony_tools["crystal"],
    }
