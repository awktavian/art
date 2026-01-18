"""Async LLM Routing Helper.

This module provides async helpers to pre-compute LLM routing decisions
that can be passed to the synchronous FanoActionRouter.route() method.

Created: January 5, 2026
"""

from __future__ import annotations

import logging
from typing import Any

from .router_core import ActionMode

logger = logging.getLogger(__name__)


async def get_llm_routing_decision(
    action: str,
    params: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get LLM routing decision asynchronously.

    This should be called BEFORE FanoActionRouter.route() to pre-compute
    the routing decision using the LLM.

    Args:
        action: Action to route
        params: Action parameters
        context: Optional routing context

    Returns:
        Dict with routing decision that can be passed to route() via context
    """
    try:
        from kagami.core.unified_agents.llm_driven_colony_router import get_llm_driven_colony_router

        llm_router = await get_llm_driven_colony_router()
        llm_result = await llm_router.route(action, params, context or {})

        return {
            "mode": llm_result.mode,
            "complexity": llm_result.complexity,
            "confidence": llm_result.metadata.get("confidence", 0.0),
            "reasoning": llm_result.metadata.get("reasoning", ""),
            "llm_driven": True,
        }

    except Exception as e:
        logger.warning(f"LLM routing decision failed: {e}, will use complexity-based fallback")
        return {
            "mode": ActionMode.SINGLE,
            "complexity": 0.5,
            "confidence": 0.0,
            "reasoning": f"LLM unavailable: {e}",
            "llm_driven": False,
        }


async def route_with_llm(
    router: Any,
    action: str,
    params: dict[str, Any],
    complexity: float | None = None,
    context: dict[str, Any] | None = None,
) -> Any:
    """Route action with LLM decision pre-computed.

    This is a convenience wrapper that:
    1. Gets LLM routing decision asynchronously
    2. Passes it to router.route() synchronously

    Args:
        router: FanoActionRouter instance
        action: Action to route
        params: Action parameters
        complexity: Optional explicit complexity
        context: Optional routing context

    Returns:
        RoutingResult from router.route()
    """
    context = context or {}

    # Get LLM decision
    llm_decision = await get_llm_routing_decision(action, params, context)

    # Add to context
    context["llm_routing_decision"] = llm_decision

    # Call synchronous route() with LLM decision in context
    return router.route(action, params, complexity, context)


__all__ = [
    "get_llm_routing_decision",
    "route_with_llm",
]
