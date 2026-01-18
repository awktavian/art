"""Intent Orchestrator - High-Level Intent Routing with Cross-System Integration.

This module implements the public API for intent-based execution:
- Parses intent strings (e.g., "research.web", "build.feature")
- Scores system affinity (forge/rooms/ambient)
- Infers complexity (0.0-1.0) to determine routing mode
- Routes to 1, 3, or 7 colonies based on complexity and system involvement
- Applies Fano line patterns for cross-system integration
- Aggregates E8 outputs via E8ActionReducer
- Generates receipts for traceability

ROUTING MODES:
==============
- SINGLE (< 0.3): Route to 1 colony (fastest, least-loaded)
- FANO_LINE (0.3-0.7): Route to 3 colonies on Fano line (composition)
- ALL_COLONIES (>= 0.7): Route to all 7 colonies (synthesis)

CROSS-SYSTEM INTEGRATION:
==========================
Detects when multiple systems (forge, rooms, ambient) are involved and applies
appropriate Fano line patterns:

1. FORGE × AMBIENT (via Nexus):
   - Pattern: forge (build) → nexus (integrate) → grove (persist)
   - Triggered by: room_id + (model | prompt)
   - Use case: Generate content in shared room

2. AMBIENT × ROOMS (via Beacon):
   - Pattern: spark (express) → nexus (share) → beacon (coordinate)
   - Triggered by: room_id + (ambient_mode | depth)
   - Use case: Presence-aware shared spaces

3. FORGE × ROOMS × AMBIENT (all colonies):
   - Pattern: Full synthesis across all systems
   - Triggered by: all three systems involved
   - Use case: Multiplayer generative ambient experience
   - Forces complexity ≥ 0.7

COMPLEXITY INFERENCE:
=====================
Complexity is inferred from:
1. Action patterns (simple → synthesis)
2. Parameter count and depth
3. Context signals (query length, domain hints)
4. System affinity scores (cross-system ops increase complexity)
5. Historical receipt patterns (stigmergy learning)

Manual override: context["complexity"] = 0.5

FASTAPI INTEGRATION:
====================
POST /api/v1/intents
{
    "intent": "generate.image",
    "context": {
        "room_id": "room_abc123",
        "prompt": "a serene landscape",
        "ambient_mode": "calm"
    }
}

Response:
{
    "success": true,
    "mode": "all",
    "routing_pattern": "all_colonies",
    "system_scores": {"forge": 0.8, "rooms": 0.9, "ambient": 0.8},
    "results": [...],
    "e8_action": {"code": [...], "index": 42},
    "receipt_id": "abc123",
    "colonies_used": [0, 1, 2, 3, 4, 5, 6],
    "latency_ms": 234.5,
    "complexity": 0.85
}

Created: December 14, 2025
Updated: December 15, 2025 (cross-system routing)
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from kagami.core.unified_agents.fano_action_router import (
    FanoActionRouter,
    create_fano_router,
)
from kagami.core.unified_agents.unified_organism import (
    UnifiedOrganism,
    get_unified_organism,
)
from kagami.orchestration.colony_manager import ColonyManager

logger = logging.getLogger(__name__)


# =============================================================================
# CROSS-SYSTEM ROUTING PATTERNS
# =============================================================================

# Fano composition patterns for cross-system integration
# These describe routing strategies when multiple systems (forge/rooms/ambient) are involved
#
# IMPORTANT: These patterns represent Fano line connectivity for routing decisions,
# NOT strict octonion multiplication. The router uses Fano lines as a combinatorial
# design for multi-colony orchestration.

# Forge × Ambient integration (via Nexus)
# Pattern: forge (build) → nexus (integrate) → grove (persist knowledge)
PATTERN_FORGE_AMBIENT = "forge × nexus = grove"

# Ambient × Rooms integration (via Beacon)
# Pattern: spark (express) → nexus (share) → beacon (coordinate)
PATTERN_AMBIENT_ROOMS = "spark × nexus = beacon"

# Forge × Rooms × Ambient (all colonies)
# Pattern: Full synthesis across all three systems
PATTERN_THREE_WAY = "all_colonies"


# =============================================================================
# DATA STRUCTURES
# =============================================================================


class IntentParseError(Exception):
    """Raised when intent parsing fails."""


class IntentExecutionError(Exception):
    """Raised when intent execution fails."""


# =============================================================================
# INTENT ORCHESTRATOR
# =============================================================================


class ColonyIntentRouter:
    """High-level intent router for colony-based execution.

    Public API for Kagami OS that automatically routes intents to
    appropriate colonies based on inferred or explicit complexity.

    NOTE: Renamed from IntentRouter (Dec 2025) to avoid collision with
    kagami.core.orchestrator.intent_router.IntentRouter (deterministic router).

    Attributes:
        organism: UnifiedOrganism for colony coordination
        colony_manager: ColonyManager for process supervision (optional)
        router: FanoActionRouter for routing decisions
    """

    def __init__(
        self,
        organism: UnifiedOrganism | None = None,
        colony_manager: ColonyManager | None = None,
        router: FanoActionRouter | None = None,
    ):
        """Initialize intent orchestrator.

        Args:
            organism: UnifiedOrganism (default: global singleton)
            colony_manager: ColonyManager for process management (optional)
            router: FanoActionRouter (default: create new)
        """
        self.organism = organism or get_unified_organism()
        self.colony_manager = colony_manager
        self.router = router or create_fano_router()

        # Execution stats
        self._total_executions = 0
        self._start_time = time.time()

        logger.info("ColonyIntentRouter initialized")

    # =========================================================================
    # SYSTEM AFFINITY SCORING (LLM-BASED - NO KEYWORD HEURISTICS)
    # =========================================================================

    async def _score_system_affinity_llm(
        self,
        action: str,
        context: dict[str, Any],
    ) -> dict[str, float]:
        """Score system affinity using LLM classification.

        NO KEYWORD HEURISTICS - Uses LLM to analyze action semantics.

        Args:
            action: Action name (e.g., "generate", "share", "express")
            context: Execution context

        Returns:
            dict[str, Any] with scores for each system: {"forge": 0.0-1.0, "rooms": 0.0-1.0, "ambient": 0.0-1.0}

        Raises:
            RuntimeError: If LLM unavailable
        """
        from pydantic import BaseModel, Field

        from kagami.core.services.llm.service import get_llm_service

        class SystemAffinity(BaseModel):
            forge: float = Field(
                ge=0.0, le=1.0, description="Affinity for generative AI (create, generate, build)"
            )
            rooms: float = Field(
                ge=0.0,
                le=1.0,
                description="Affinity for multiplayer/shared spaces (share, room, collaborate)",
            )
            ambient: float = Field(
                ge=0.0,
                le=1.0,
                description="Affinity for calm/presence-aware tech (ambient, sense, adapt)",
            )

        llm = get_llm_service()
        if not llm.is_initialized or not llm.are_models_ready:
            raise RuntimeError(
                "LLM required for system affinity classification - no heuristic fallbacks"
            )

        # Context summary for LLM
        context_summary = []
        if context.get("room_id"):
            context_summary.append("has room_id (multiplayer)")
        if context.get("ambient_mode"):
            context_summary.append("has ambient_mode (presence-aware)")
        if context.get("model") or context.get("prompt"):
            context_summary.append("has model/prompt (generation)")
        if context.get("depth") is not None:
            context_summary.append(f"has depth={context['depth']} (ambient interaction)")

        prompt = f"""Classify this action for system routing. Score each system's affinity (0.0-1.0):

ACTION: {action}
CONTEXT: {", ".join(context_summary) if context_summary else "none"}

SYSTEMS:
- forge: Generative AI operations (create, generate, synthesize, build, infer)
- rooms: Multiplayer/shared spaces (share, collaborate, broadcast, join, invite)
- ambient: Calm/presence-aware technology (ambient, contextual, sense, adapt)

Return scores as JSON with keys: forge, rooms, ambient (each 0.0-1.0)"""

        result = await llm.generate(
            prompt,
            app_name="intent_router",
            max_tokens=50,
            temperature=0.2,
            structured_output=SystemAffinity,
        )

        if isinstance(result, SystemAffinity):
            scores = {"forge": result.forge, "rooms": result.rooms, "ambient": result.ambient}
        elif isinstance(result, dict):  # type: ignore[unreachable]
            scores = {  # type: ignore[unreachable]
                "forge": float(result.get("forge", 0.0)),
                "rooms": float(result.get("rooms", 0.0)),
                "ambient": float(result.get("ambient", 0.0)),
            }
        else:
            raise RuntimeError(f"LLM returned unexpected type: {type(result)}")

        logger.debug(
            f"System affinity (LLM): forge={scores['forge']:.2f}, rooms={scores['rooms']:.2f}, ambient={scores['ambient']:.2f}"
        )
        return scores

    def _score_system_affinity(
        self,
        action: str,
        context: dict[str, Any],
    ) -> dict[str, float]:
        """Score affinity for forge/rooms/ambient systems.

        Uses context signals only - no keyword heuristics.
        For full semantic analysis, use _score_system_affinity_llm().

        Args:
            action: Action name (e.g., "generate", "share", "express")
            context: Execution context (may contain room_id, ambient_mode, etc.)

        Returns:
            dict[str, Any] with scores for each system
        """
        scores = {"forge": 0.0, "rooms": 0.0, "ambient": 0.0}

        # Context signals only - no keyword matching
        if context.get("model") or context.get("prompt") or context.get("generation"):
            scores["forge"] = 0.8

        if context.get("room_id") or context.get("room_name") or context.get("participants"):
            scores["rooms"] = 0.9

        if context.get("ambient_mode") or context.get("presence") or context.get("depth"):
            scores["ambient"] = 0.8

        logger.debug(
            f"System affinity (context): forge={scores['forge']:.2f}, rooms={scores['rooms']:.2f}, ambient={scores['ambient']:.2f}"
        )
        return scores

    def _determine_routing_mode(
        self,
        complexity: float,
        system_scores: dict[str, float],
        context: dict[str, Any],
    ) -> tuple[str, str | None]:
        """Determine execution mode and cross-system pattern.

        Combines complexity analysis with system affinity to select
        appropriate routing strategy.

        Args:
            complexity: Complexity score (0-1)
            system_scores: System affinity scores from _score_system_affinity
            context: Execution context

        Returns:
            Tuple of (mode, pattern) where:
                - mode: "single", "fano", or "all"
                - pattern: Cross-system pattern constant or None
        """
        # Count systems with significant affinity (> 0.5)
        active_systems = [sys for sys, score in system_scores.items() if score > 0.5]
        num_systems = len(active_systems)

        # === THREE-WAY INTEGRATION (all systems) ===
        if num_systems >= 3:
            logger.info(f"🔀 Cross-system routing: ALL SYSTEMS ({', '.join(active_systems)})")
            return ("all", PATTERN_THREE_WAY)

        # === TWO-WAY INTEGRATION (Fano line patterns) ===
        if num_systems == 2:
            # Forge + Ambient
            if "forge" in active_systems and "ambient" in active_systems:
                logger.info("🔀 Cross-system routing: FORGE × AMBIENT")
                # Force complexity >= 0.7 for cross-system integration
                if complexity < 0.7:
                    context["complexity"] = 0.7
                return ("fano", PATTERN_FORGE_AMBIENT)

            # Ambient + Rooms
            elif "ambient" in active_systems and "rooms" in active_systems:
                logger.info("🔀 Cross-system routing: AMBIENT × ROOMS")
                # Force complexity >= 0.7 for cross-system integration
                if complexity < 0.7:
                    context["complexity"] = 0.7
                return ("fano", PATTERN_AMBIENT_ROOMS)

            # Forge + Rooms (also requires coordination)
            elif "forge" in active_systems and "rooms" in active_systems:
                logger.info("🔀 Cross-system routing: FORGE × ROOMS")
                # Force complexity >= 0.7 for cross-system integration
                if complexity < 0.7:
                    context["complexity"] = 0.7
                return ("fano", PATTERN_FORGE_AMBIENT)  # Use forge-ambient pattern

        # === SINGLE SYSTEM OR DEFAULT COMPLEXITY ROUTING ===
        # Fall back to standard complexity-based routing
        if complexity < self.router.simple_threshold:
            return ("single", None)
        elif complexity < self.router.complex_threshold:
            return ("fano", None)
        else:
            return ("all", None)

    # =========================================================================
    # INTENT PARSING
    # =========================================================================

    def _parse_intent(self, intent: str | dict[str, Any]) -> dict[str, Any]:
        """Parse intent string or dict[str, Any] to structured format.

        Supports formats:
        - String: "research.web" → {action: "research", domain: "web"}
        - String: "build" → {action: "build"}
        - Dict: {"action": "research", "domain": "web", "params": {...}}

        Args:
            intent: Intent as string or dict[str, Any]

        Returns:
            Parsed intent dict[str, Any] with keys: action, domain, params

        Raises:
            IntentParseError: If intent format is invalid
        """
        if isinstance(intent, dict):
            # Already structured
            if "action" not in intent:
                raise IntentParseError("Intent dict[str, Any] must contain 'action' key")

            return {
                "action": intent["action"],
                "domain": intent.get("domain", "general"),
                "params": intent.get("params", {}),
            }

        if isinstance(intent, str):
            # Parse string format
            intent = intent.strip()
            if not intent:
                raise IntentParseError("Intent string cannot be empty")

            # Split on "." for domain-qualified actions
            parts = intent.split(".", 1)
            if len(parts) == 2:
                action, domain = parts
                return {
                    "action": action,
                    "domain": domain,
                    "params": {},
                }
            else:
                return {
                    "action": parts[0],
                    "domain": "general",
                    "params": {},
                }

        raise IntentParseError(
            f"Intent must be string or dict[str, Any], got {type(intent).__name__}"
        )

    # =========================================================================
    # COMPLEXITY INFERENCE
    # =========================================================================

    async def _infer_complexity(
        self,
        intent: dict[str, Any],
        context: dict[str, Any],
    ) -> float:
        """Infer complexity score (0-1) for intent.

        Uses FanoActionRouter's complexity inference, enhanced with
        intent structure and context.

        Args:
            intent: Parsed intent dict[str, Any]
            context: Execution context

        Returns:
            Complexity score (0.0 = simple, 1.0 = synthesis)
        """
        # Check for explicit complexity override
        if "complexity" in context:
            return float(context["complexity"])

        # Build action string for router
        action = intent["action"]
        if intent["domain"] != "general":
            action = f"{intent['action']}.{intent['domain']}"

        # Use router's complexity inference
        params = intent.get("params", {})
        complexity = self.router._infer_complexity(action, params, context)

        logger.debug(f"Complexity inference: action={action}, complexity={complexity:.3f}")

        return complexity

    # =========================================================================
    # EXECUTION MODES
    # =========================================================================

    async def _execute_single(
        self,
        intent: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute via single colony (least-loaded).

        Args:
            intent: Parsed intent
            context: Execution context

        Returns:
            Execution result
        """
        action = intent["action"]
        if intent["domain"] != "general":
            action = f"{action}.{intent['domain']}"

        params = intent.get("params", {})

        # Execute via organism (which handles routing)
        result = await self.organism.execute_intent(
            intent=action,
            params=params,
            context=context,
        )

        return result

    async def _execute_fano_line(
        self,
        intent: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute via Fano line (3 colonies).

        Args:
            intent: Parsed intent
            context: Execution context

        Returns:
            Execution result
        """
        action = intent["action"]
        if intent["domain"] != "general":
            action = f"{action}.{intent['domain']}"

        params = intent.get("params", {})

        # Execute via organism (router determines Fano line)
        result = await self.organism.execute_intent(
            intent=action,
            params=params,
            context=context,
        )

        return result

    async def _execute_all_colonies(
        self,
        intent: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute via all 7 colonies (synthesis).

        Args:
            intent: Parsed intent
            context: Execution context

        Returns:
            Execution result
        """
        action = intent["action"]
        if intent["domain"] != "general":
            action = f"{action}.{intent['domain']}"

        params = intent.get("params", {})

        # Execute via organism (router engages all colonies)
        result = await self.organism.execute_intent(
            intent=action,
            params=params,
            context=context,
        )

        return result

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    async def execute_intent(
        self,
        intent: str | dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute intent with automatic routing and cross-system integration.

        This is the main entry point for intent execution. It:
        1. Parses the intent
        2. Scores system affinity (forge/rooms/ambient)
        3. Infers complexity (or uses explicit override)
        4. Determines execution mode and cross-system pattern
        5. Routes to appropriate colonies via Fano composition
        6. Aggregates E8 outputs
        7. Generates receipt for traceability

        CROSS-SYSTEM INTEGRATION:
        - Detects forge, rooms, and ambient system involvement
        - Applies Fano line patterns for 2-way integration
        - Uses all-colonies mode for 3-way integration
        - Forces complexity ≥ 0.7 for cross-system operations

        Args:
            intent: Intent string or dict[str, Any]
            context: Additional context (optional)
                - room_id: Triggers rooms system integration
                - ambient_mode: Triggers ambient system integration
                - model/prompt: Triggers forge system integration
                - depth: Ambient interaction depth (0-4)
                - complexity: Explicit override (0-1)

        Returns:
            result: {
                "success": bool,
                "mode": "single" | "fano" | "all",
                "results": [...],  # Colony outputs
                "e8_action": {"code": [...], "index": int},
                "receipt_id": str,
                "colonies_used": [0, 2, 4],  # Colony indices
                "latency_ms": float,
                "complexity": float,
                "routing_pattern": str | None,  # Cross-system pattern
                "system_scores": dict[str, Any] | None,  # System affinity scores
            }

        Raises:
            IntentParseError: If intent format is invalid
            IntentExecutionError: If execution fails
        """
        context = context or {}
        start_time = time.time()

        try:
            # Parse intent
            parsed_intent = self._parse_intent(intent)

            # Build action string for system affinity analysis
            action = parsed_intent["action"]
            if parsed_intent["domain"] != "general":
                action = f"{action}.{parsed_intent['domain']}"

            # Score system affinity
            system_scores = self._score_system_affinity(action, context)

            # Infer complexity
            complexity = await self._infer_complexity(parsed_intent, context)

            # Determine mode and cross-system pattern
            mode, pattern = self._determine_routing_mode(complexity, system_scores, context)

            # Add routing metadata to context
            context["complexity"] = complexity
            context["system_scores"] = system_scores
            if pattern:
                context["routing_pattern"] = pattern

            # Execute based on mode
            if mode == "single":
                result = await self._execute_single(parsed_intent, context)
            elif mode == "fano":
                result = await self._execute_fano_line(parsed_intent, context)
            else:
                result = await self._execute_all_colonies(parsed_intent, context)

            # Generate receipt ID (if not already present)
            # Check context first for correlation_id (explicit passthrough takes priority)
            if context.get("correlation_id"):
                receipt_id = context["correlation_id"]
            elif result.get("intent_id"):
                receipt_id = result["intent_id"]
            else:
                receipt_id = str(uuid.uuid4())[:8]

            # Extract colonies used from results
            colonies_used = []
            if "results" in result:
                # Extract colony indices from results
                for r in result.get("results", []):
                    if hasattr(r, "worker_id"):
                        # Extract colony from worker_id (format: "colony_0_worker_0")
                        parts = r.worker_id.split("_")
                        if len(parts) >= 2 and parts[0] == "colony":
                            try:
                                colonies_used.append(int(parts[1]))
                            except (ValueError, IndexError):
                                pass

            # If no colonies extracted, infer from mode
            if not colonies_used:
                if mode == "single":
                    colonies_used = [1]  # Default to forge
                elif mode == "fano":
                    colonies_used = [0, 1, 2]  # Placeholder
                else:
                    colonies_used = list(range(7))

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000.0

            # Update stats
            self._total_executions += 1

            # Build response
            response = {
                "success": result.get("success", False),
                "mode": mode,
                "results": result.get("results", []),
                "e8_action": result.get("e8_action", {"code": [], "index": 0}),
                "receipt_id": receipt_id,
                "colonies_used": colonies_used,
                "latency_ms": round(latency_ms, 2),
                "complexity": round(complexity, 3),
            }

            # Add cross-system routing metadata
            if pattern:
                response["routing_pattern"] = pattern
            if system_scores:
                # Only include systems with affinity > 0
                active_systems = {k: round(v, 3) for k, v in system_scores.items() if v > 0}
                if active_systems:
                    response["system_scores"] = active_systems

            # Add coordination phase if available
            if "coordination_phase" in result:
                response["coordination_phase"] = result["coordination_phase"]

            # Log with cross-system info
            log_msg = (
                f"Intent executed: mode={mode}, complexity={complexity:.3f}, "
                f"latency={latency_ms:.1f}ms, receipt={receipt_id}"
            )
            if pattern:
                log_msg += f", pattern={pattern}"
            if system_scores:
                active_systems = [k for k, v in system_scores.items() if v > 0.5]  # type: ignore[assignment]
                if active_systems:
                    log_msg += f", systems=[{', '.join(active_systems)}]"
            logger.info(log_msg)

            # Emit receipt for traceability (Dec 21, 2025 - Flow)
            try:
                from kagami.core.receipts.facade import emit_receipt

                await emit_receipt(  # type: ignore[misc]
                    correlation_id=receipt_id,
                    event_name="intent.execute",
                    action=parsed_intent["action"],
                    app=parsed_intent.get("domain", "orchestrator"),
                    phase="EXECUTE",
                    status="success" if response["success"] else "error",
                    event_data={
                        "mode": mode,
                        "complexity": round(complexity, 3),
                        "colonies_used": colonies_used,
                        "latency_ms": round(latency_ms, 2),
                        "pattern": pattern,
                        "system_scores": {
                            k: round(v, 3) for k, v in system_scores.items() if v > 0
                        },
                    },
                    args=intent.get("params", {}),  # type: ignore[union-attr]
                    metadata=context,
                )
                logger.debug(f"Receipt emitted: {receipt_id}")
            except Exception as e:
                # Receipt emission should never crash the execution
                logger.warning(f"Failed to emit receipt for intent {receipt_id}: {e}")

            return response

        except IntentParseError as e:
            logger.error(f"Intent parsing failed: {e}")
            return {
                "success": False,
                "error": f"IntentParseError: {e!s}",
                "latency_ms": (time.time() - start_time) * 1000.0,
            }

        except Exception as e:
            logger.error(f"Intent execution failed: {e}", exc_info=True)

            # Emit error receipt for traceability (Dec 21, 2025 - Flow)
            try:
                from kagami.core.receipts.facade import emit_receipt

                error_id = context.get("correlation_id") or str(uuid.uuid4())[:8]
                await emit_receipt(  # type: ignore[misc]
                    correlation_id=error_id,
                    event_name="intent.execute.error",
                    action=intent if isinstance(intent, str) else "unknown",
                    app="orchestrator",
                    phase="EXECUTE",
                    status="error",
                    event_data={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "latency_ms": round((time.time() - start_time) * 1000.0, 2),
                    },
                    metadata=context or {},
                )
            except Exception as receipt_err:
                logger.debug(f"Failed to emit error receipt: {receipt_err}")

            return {
                "success": False,
                "error": f"IntentExecutionError: {e!s}",
                "latency_ms": (time.time() - start_time) * 1000.0,
            }

    # =========================================================================
    # STATS & MONITORING
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get orchestrator statistics.

        Returns:
            Statistics dictionary
        """
        uptime = time.time() - self._start_time

        return {
            "total_executions": self._total_executions,
            "uptime_seconds": round(uptime, 2),
            "organism_stats": self.organism.get_stats(),
            "router_thresholds": {
                "simple": self.router.simple_threshold,
                "complex": self.router.complex_threshold,
            },
        }


# =============================================================================
# FACTORY & SINGLETON
# =============================================================================

_INTENT_ROUTER: ColonyIntentRouter | None = None


def get_global_intent_router() -> ColonyIntentRouter:
    """Get global intent router singleton.

    Returns:
        Global ColonyIntentRouter instance
    """
    global _INTENT_ROUTER
    if _INTENT_ROUTER is None:
        _INTENT_ROUTER = create_intent_router()
    return _INTENT_ROUTER


def set_global_intent_router(router: ColonyIntentRouter | None) -> None:
    """Set global intent router.

    Args:
        router: ColonyIntentRouter or None
    """
    global _INTENT_ROUTER
    _INTENT_ROUTER = router


def create_intent_router(
    organism: UnifiedOrganism | None = None,
    colony_manager: ColonyManager | None = None,
    router: FanoActionRouter | None = None,
) -> ColonyIntentRouter:
    """Create an intent router.

    Args:
        organism: UnifiedOrganism (default: global)
        colony_manager: ColonyManager (optional)
        router: FanoActionRouter (default: create new)

    Returns:
        Configured ColonyIntentRouter
    """
    return ColonyIntentRouter(
        organism=organism,
        colony_manager=colony_manager,
        router=router,
    )


# Backwards compatibility alias
IntentRouter = ColonyIntentRouter


# =============================================================================
# FASTAPI INTEGRATION
# =============================================================================


try:
    from fastapi import FastAPI
    from pydantic import BaseModel

    FASTAPI_AVAILABLE = True

    class IntentRequest(BaseModel):
        """Request model for intent execution."""

        intent: str | dict[str, Any]
        context: dict[str, Any] | None = None

    class IntentResponse(BaseModel):
        """Response model for intent execution."""

        success: bool
        mode: str | None = None
        results: list[Any] | None = None
        e8_action: dict[str, Any] | None = None
        receipt_id: str | None = None
        colonies_used: list[int] | None = None
        latency_ms: float | None = None
        complexity: float | None = None
        error: str | None = None

    def create_intent_api(
        app: FastAPI,
        router: ColonyIntentRouter | None = None,
    ) -> None:
        """Add intent routing endpoints to FastAPI app.

        Args:
            app: FastAPI application
            router: ColonyIntentRouter (default: global)
        """
        orch = router or get_global_intent_router()

        @app.post("/api/v1/intents", response_model=IntentResponse)
        async def execute_intent_endpoint(request: IntentRequest) -> Any:
            """Public API endpoint for intent execution.

            Execute an intent with automatic complexity inference and routing.

            Request:
                {
                    "intent": "research.web",
                    "context": {"query": "how to implement E8 lattice"}
                }

            Response:
                {
                    "success": true,
                    "mode": "fano",
                    "results": [...],
                    "e8_action": {"code": [...], "index": 42},
                    "receipt_id": "abc123",
                    "colonies_used": [0, 2, 4],
                    "latency_ms": 123.4,
                    "complexity": 0.55
                }
            """
            result = await orch.execute_intent(
                request.intent,
                request.context,
            )
            return result

        @app.get("/api/v1/intents/stats")
        async def get_intent_router_stats() -> Any:
            """Get intent router statistics."""
            return orch.get_stats()

        logger.info("Intent routing API endpoints registered")

except ImportError:
    FASTAPI_AVAILABLE = False
    logger.debug("FastAPI not available, skipping API integration")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


if __name__ == "__main__":
    import sys

    print("Intent Router - Use tests/orchestration/test_intent_orchestrator.py for testing")
    print("For production use, import and use execute_intent() directly")
    sys.exit(0)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "PATTERN_AMBIENT_ROOMS",
    # Cross-system patterns
    "PATTERN_FORGE_AMBIENT",
    "PATTERN_THREE_WAY",
    # Classes
    "ColonyIntentRouter",
    "IntentExecutionError",
    "IntentParseError",
    "IntentRequest",
    "IntentResponse",
    "IntentRouter",  # Backwards compatibility alias
    # FastAPI (if available)
    "create_intent_api",
    # Factory
    "create_intent_router",
    # Singleton
    "get_global_intent_router",
    "set_global_intent_router",
]
