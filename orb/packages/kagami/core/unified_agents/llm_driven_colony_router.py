"""LLM-Driven Colony Router - NO THRESHOLD HEURISTICS.

This module implements fully LLM-driven colony routing with:
1. LLM-based complexity assessment
2. LLM-based colony selection
3. LLM-based mode determination (single/fano/all)
4. NO hardcoded thresholds (simple_threshold, complex_threshold)
5. Exponential backoff retry for resilience

All routing decisions are made by the LLM, ensuring the organism
is fully self-directed and learns from execution outcomes.

Created: January 5, 2026
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from .router_core import COLONY_NAMES, ActionMode, ColonyAction, RoutingResult

logger = logging.getLogger(__name__)


@dataclass
class LLMRoutingDecision:
    """LLM routing decision."""

    mode: ActionMode
    colonies: list[int]  # Colony indices (0-6)
    complexity: float
    confidence: float
    reasoning: str


class LLMDrivenColonyRouter:
    """Fully LLM-driven colony router with NO threshold heuristics.

    Key principles:
    1. ALL routing decisions made by LLM
    2. NO hardcoded thresholds (simple_threshold, complex_threshold)
    3. NO keyword matching fallbacks
    4. Resilience through exponential backoff retry
    5. Learning from execution outcomes
    """

    def __init__(self) -> None:
        """Initialize LLM-driven colony router."""
        self._llm_service: Any = None
        self._performance_history: dict[tuple[str, int], list[float]] = {}

    async def initialize(self) -> None:
        """Initialize LLM service for routing decisions."""
        from kagami.core.services.llm import get_llm_service

        self._llm_service = get_llm_service()
        await self._llm_service.initialize()

    async def route(
        self,
        action: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> RoutingResult:
        """Route action to colonies using LLM decision.

        Args:
            action: Action to route
            params: Action parameters
            context: Optional routing context

        Returns:
            RoutingResult with LLM-selected colonies

        Raises:
            RuntimeError: If routing fails after retries
        """
        if not self._llm_service:
            raise RuntimeError("Router not initialized - call initialize() first")

        context = context or {}

        # Get LLM routing decision
        decision = await self._get_llm_routing_decision(action, params, context)

        # Build colony actions
        actions = []
        for colony_idx in decision.colonies:
            actions.append(
                ColonyAction(
                    colony_idx=colony_idx,
                    colony_name=COLONY_NAMES[colony_idx],
                    action=action,
                    params=params,
                    priority=1.0,
                )
            )

        return RoutingResult(
            actions=actions,
            mode=decision.mode,
            complexity=decision.complexity,
            metadata={
                "action": action,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
                "llm_driven": True,
            },
        )

    async def _get_llm_routing_decision(
        self,
        action: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> LLMRoutingDecision:
        """Get routing decision from LLM.

        Args:
            action: Action to route
            params: Action parameters
            context: Routing context

        Returns:
            LLMRoutingDecision

        Raises:
            RuntimeError: If decision fails after retries
        """
        # Build performance context
        perf_context = self._build_performance_context(action)

        # Build colony descriptions
        colony_desc = self._build_colony_descriptions()

        prompt = f"""Route this action to the optimal colony or colonies.

Action: {action}
Parameters: {params}
Context: {context}

Available Colonies:
{colony_desc}

Performance History:
{perf_context}

Routing Modes:
- SINGLE: Route to 1 colony (simple, focused tasks)
- FANO: Route to 3 colonies on a Fano line (moderate complexity, composition)
- ALL: Route to all 7 colonies (high complexity, synthesis)

Analyze:
1. Task complexity (0.0-1.0)
2. Which colonies are best suited
3. Whether this needs single/fano/all colonies
4. Your confidence in this routing (0.0-1.0)

Respond in this EXACT format:
MODE: [SINGLE|FANO|ALL]
COLONIES: [comma-separated indices 0-6]
COMPLEXITY: [0.0-1.0]
CONFIDENCE: [0.0-1.0]
REASONING: [brief explanation]

Example:
MODE: SINGLE
COLONIES: 1
COMPLEXITY: 0.3
CONFIDENCE: 0.9
REASONING: Simple build task, Forge colony is best suited."""

        # Retry with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self._llm_service.generate(
                    prompt=prompt,
                    max_tokens=200,
                    temperature=0.2,
                )

                # Parse response
                decision = self._parse_routing_response(response)

                logger.info(
                    f"🎯 LLM routing: {action} → {decision.mode.value} "
                    f"(colonies={decision.colonies}, complexity={decision.complexity:.2f})"
                )

                return decision

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Routing decision attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(2**attempt)
                    continue
                raise RuntimeError(f"Routing decision failed after {max_retries} attempts") from e

        raise RuntimeError("Routing decision failed")

    def _build_performance_context(self, action: str) -> str:
        """Build performance context for LLM.

        Args:
            action: Action being routed

        Returns:
            Performance context string
        """
        if not self._performance_history:
            return "No performance history available."

        # Find relevant performance data
        relevant = []
        for (past_action, colony_idx), scores in self._performance_history.items():
            if past_action.lower() in action.lower() or action.lower() in past_action.lower():
                avg_score = sum(scores) / len(scores) if scores else 0.0
                relevant.append(
                    f"- {COLONY_NAMES[colony_idx]}: avg_score={avg_score:.2f} "
                    f"(from {len(scores)} executions of '{past_action}')"
                )

        if not relevant:
            return "No directly relevant performance history."

        return "\n".join(relevant)

    def _build_colony_descriptions(self) -> str:
        """Build colony descriptions for LLM.

        Returns:
            Colony descriptions string
        """
        descriptions = [
            "0. Spark (Fold A₂): Ideation, creativity, brainstorming, ignition",
            "1. Forge (Cusp A₃): Building, implementation, construction, coding",
            "2. Flow (Swallowtail A₄): Debugging, recovery, maintenance, healing",
            "3. Nexus (Butterfly A₅): Integration, connection, bridging, coordination",
            "4. Beacon (Hyperbolic D₄⁺): Planning, architecture, strategy, organization",
            "5. Grove (Elliptic D₄⁻): Research, exploration, investigation, learning",
            "6. Crystal (Parabolic D₅): Testing, verification, validation, safety",
        ]
        return "\n".join(descriptions)

    def _parse_routing_response(self, response: str) -> LLMRoutingDecision:
        """Parse LLM routing response.

        Args:
            response: LLM response text

        Returns:
            LLMRoutingDecision

        Raises:
            ValueError: If response format is invalid
        """
        lines = response.strip().split("\n")
        parsed = {}

        for line in lines:
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip().upper()
            value = value.strip()

            if key == "MODE":
                parsed["mode"] = value.upper()
            elif key == "COLONIES":
                # Parse comma-separated indices
                parsed["colonies"] = [int(x.strip()) for x in value.split(",")]
            elif key == "COMPLEXITY":
                parsed["complexity"] = float(value)
            elif key == "CONFIDENCE":
                parsed["confidence"] = float(value)
            elif key == "REASONING":
                parsed["reasoning"] = value

        # Validate required fields
        required = ["mode", "colonies", "complexity", "confidence"]
        missing = [f for f in required if f not in parsed]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Convert mode string to enum
        mode_map = {
            "SINGLE": ActionMode.SINGLE,
            "FANO": ActionMode.FANO_LINE,
            "ALL": ActionMode.ALL_COLONIES,
        }
        mode = mode_map.get(parsed["mode"])
        if mode is None:
            raise ValueError(f"Invalid mode: {parsed['mode']}")

        # Validate colony indices
        for idx in parsed["colonies"]:
            if not 0 <= idx <= 6:
                raise ValueError(f"Invalid colony index: {idx}")

        return LLMRoutingDecision(
            mode=mode,
            colonies=parsed["colonies"],
            complexity=parsed["complexity"],
            confidence=parsed["confidence"],
            reasoning=parsed.get("reasoning", "No reasoning provided"),
        )

    async def record_outcome(
        self,
        action: str,
        colony_idx: int,
        success: bool,
        quality_score: float | None = None,
    ) -> None:
        """Record routing outcome for learning.

        Args:
            action: Action that was executed
            colony_idx: Colony that executed it
            success: Whether execution succeeded
            quality_score: Optional quality score (0-1)
        """
        key = (action, colony_idx)

        if key not in self._performance_history:
            self._performance_history[key] = []

        score = quality_score if quality_score is not None else (1.0 if success else 0.0)
        self._performance_history[key].append(score)

        # Keep last 100 scores per (action, colony) pair
        if len(self._performance_history[key]) > 100:
            self._performance_history[key] = self._performance_history[key][-100:]

        logger.debug(
            f"📊 Recorded outcome: {COLONY_NAMES[colony_idx]} for '{action}' "
            f"(success={success}, score={score:.2f})"
        )


# =============================================================================
# FACTORY (via centralized registry)
# =============================================================================

from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
get_llm_driven_colony_router = _singleton_registry.register_async(
    "llm_driven_colony_router", LLMDrivenColonyRouter
)


__all__ = [
    "LLMDrivenColonyRouter",
    "LLMRoutingDecision",
    "get_llm_driven_colony_router",
]
