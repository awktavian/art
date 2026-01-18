"""Colony Coordinator - Multi-Colony Execution and Routing.

Handles intent execution across multiple colonies using Fano-based routing
and E8-based output fusion.

RESPONSIBILITIES:
=================
1. Execute intents via single colony (SINGLE mode)
2. Execute intents via Fano line (3 colonies, FANO_LINE mode)
3. Execute intents via all colonies (7 colonies, ALL_COLONIES mode)
4. Fuse colony outputs via E8ActionReducer
5. Encode/decode E8 messages for inter-colony communication

ARCHITECTURE:
=============
┌─────────────────────────────────────────────────────────┐
│              ColonyCoordinator                          │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────┐ │
│  │ Route Intent │ → │ Execute Mode │ → │ Fuse E8  │ │
│  └──────────────┘    └──────────────┘    └──────────┘ │
│        │                    │                   │      │
│        ▼                    ▼                   ▼      │
│   FanoRouter         MinimalColonies      E8Reducer   │
└─────────────────────────────────────────────────────────┘

Created: December 14, 2025
Extracted from: unified_organism.py (refactor)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any

# CONCURRENCY FIX (Dec 25, 2025): Bounded concurrency for colony execution
# Prevents resource exhaustion when executing multiple colonies in parallel
_MAX_CONCURRENT_COLONIES = int(os.getenv("MAX_CONCURRENT_COLONIES", "7"))
_colony_semaphore: asyncio.Semaphore | None = None


def _get_colony_semaphore() -> asyncio.Semaphore:
    """Get or create the colony execution semaphore."""
    global _colony_semaphore
    if _colony_semaphore is None:
        _colony_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_COLONIES)
    return _colony_semaphore


if TYPE_CHECKING:
    import torch
    import torch.nn.functional as F

    from kagami.core.unified_agents.fano_action_router import (
        ActionMode,
        RoutingResult,
    )
else:
    torch = None  # type: ignore
    F = None  # type: ignore
    ActionMode = None  # type: ignore
    RoutingResult = None  # type: ignore

logger = logging.getLogger(__name__)


def _lazy_import_torch() -> Any:
    """Lazy import torch to avoid blocking module import.

    OPTIMIZATION (Dec 16, 2025): torch import adds 200-1000ms delay.
    Only import when actually needed for coordinator operations.

    Returns:
        torch module
    """
    import torch

    return torch


def _lazy_import_torch_nn_functional() -> Any:
    """Lazy import torch.nn.functional for softmax operations.

    Returns:
        torch.nn.functional module
    """
    import torch.nn.functional as F

    return F


def _lazy_import_fano_types() -> Any:
    """Lazy import ActionMode and RoutingResult to avoid transitive torch dependency.

    Returns:
        tuple[Any, ...] of (ActionMode, RoutingResult)
    """
    from kagami.core.unified_agents.fano_action_router import ActionMode, RoutingResult

    return ActionMode, RoutingResult


# =============================================================================
# COLONY COORDINATOR
# =============================================================================


class ColonyCoordinator:
    """Coordinates multi-colony execution and E8 fusion.

    Handles three execution modes:
    - SINGLE: One colony executes
    - FANO_LINE: Three colonies (Fano line composition)
    - ALL_COLONIES: All seven colonies
    """

    def __init__(
        self,
        router: Any,  # FanoActionRouter - deferred
        reducer: Any,  # E8ActionReducer - deferred
        e8_roots: Any,  # torch.Tensor - deferred to avoid eager import
        get_colony_fn: callable,  # type: ignore[valid-type]
    ):
        """Initialize colony coordinator.

        Args:
            router: FanoActionRouter for intent routing
            reducer: E8ActionReducer for output fusion
            e8_roots: E8 roots tensor [240, 8]
            get_colony_fn: Function to get colony by index
        """
        self._router = router
        self._reducer = reducer
        self._e8_roots = e8_roots
        self._get_colony = get_colony_fn

    def _extract_octonion_output(
        self,
        result: Any,
        colony_idx: int,
        weight: float = 1.0,
    ) -> Any:  # torch.Tensor - deferred
        """Extract octonion (E8) output from TaskResult.

        REFACTORED Dec 27, 2025: Renamed from _extract_s7_output for clarity.
        This function extracts 8D octonion embeddings (E8 space), not 7D S⁷.

        Architecture: Each colony produces an 8D octonion vector that gets
        fused by E8ActionReducer. The naming aligns with the mathematical
        structure: E8 = ℝ ⊕ Im(𝕆) = e₀ ⊕ (e₁..e₇).

        Args:
            result: TaskResult from colony execution
            colony_idx: Colony index (0-6)
            weight: Weight to apply to output

        Returns:
            8D tensor (octonion) normalized to unit sphere
        """
        torch = _lazy_import_torch()

        # Import OctonionState for unified handling
        from kagami.core.unified_agents.octonion_state import octonion_state_from_agent_result

        # Try to extract kernel output from result
        if hasattr(result, "result") and isinstance(result.result, dict):
            # Check for e8_code (preferred) or s7_output (legacy)
            e8_code = result.result.get("e8_code")
            if e8_code is not None:
                if isinstance(e8_code, torch.Tensor) and e8_code.shape[-1] == 8:
                    return e8_code.squeeze() * weight
                if isinstance(e8_code, list) and len(e8_code) == 8:
                    return torch.tensor(e8_code, dtype=torch.float32) * weight

            # Check for kernel_output with e8_code or s7_output
            kernel_output = result.result.get("kernel_output", {})
            if kernel_output:
                e8_out = kernel_output.get("e8_code") or kernel_output.get("s7_output")
                if e8_out is not None:
                    if isinstance(e8_out, torch.Tensor):
                        out = e8_out.squeeze()
                        # Pad 7D to 8D if needed (legacy s7_output format)
                        if out.shape[-1] == 7:
                            out = torch.cat([torch.zeros(1, device=out.device), out])
                        return out * weight
                    return torch.tensor(e8_out, dtype=torch.float32).squeeze() * weight

            # Check for direct s7_output (legacy format)
            s7_out = result.result.get("s7_output")
            if s7_out is not None:
                if isinstance(s7_out, torch.Tensor):
                    out = s7_out.squeeze()
                    if out.shape[-1] == 7:
                        out = torch.cat([torch.zeros(1, device=out.device), out])
                    return out * weight

        # Use OctonionState for consistent fallback generation
        octonion = octonion_state_from_agent_result(result, colony_idx)
        return octonion.e8_code * weight

    # =========================================================================
    # INTENT EXECUTION
    # =========================================================================

    async def execute_intent(
        self,
        intent: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute intent across appropriate colonies.

        Args:
            intent: Intent name (e.g., "research.web")
            params: Intent parameters
            context: Execution context

        Returns:
            Execution result with colony outputs and E8 action
        """
        ActionMode, _ = _lazy_import_fano_types()
        context = context or {}

        # NEXUS BRIDGE (Dec 19, 2025): Enrich context with world model predictions
        # This populates `wm_colony_hint` that FanoActionRouter checks at line 746
        context = await self._enrich_context_with_world_model(intent, params, context)

        # Route intent
        routing = self._router.route(intent, params, context=context)

        # Execute based on mode
        if routing.mode == ActionMode.SINGLE:
            result = await self._execute_single(routing, params, context)
        elif routing.mode == ActionMode.FANO_LINE:
            result = await self._execute_fano_line(routing, params, context)
        else:
            result = await self._execute_all_colonies(routing, params, context)

        # Fuse outputs via E8
        e8_result = await self._fuse_e8(result["colony_outputs"])

        torch = _lazy_import_torch()
        return {
            "mode": routing.mode.value,
            "complexity": routing.complexity,
            "results": result["results"],
            "e8_action": {
                "index": e8_result["index"],
                "code": e8_result["code"].tolist()
                if isinstance(e8_result["code"], torch.Tensor)
                else e8_result["code"],
                "weights": e8_result["weights"],
            },
            "routing": routing,
            # COHERENCY (Dec 27, 2025): Unified state representation
            "octonion_state": e8_result.get("octonion_state"),
        }

    async def _execute_single(
        self,
        routing: Any,  # RoutingResult - deferred
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute via single colony."""
        torch = _lazy_import_torch()
        F = _lazy_import_torch_nn_functional()

        action = routing.actions[0]
        colony = self._get_colony(action.colony_idx)  # type: ignore[misc]

        result = await colony.execute(action.action, params, context)

        # Create 8D output from single colony using semantic embedding
        output = torch.zeros(7, 8)
        output[action.colony_idx] = self._extract_octonion_output(result, action.colony_idx)
        output = F.normalize(output, dim=-1)

        return {
            "results": [result],
            "colony_outputs": output.unsqueeze(0),  # [1, 7, 8]
        }

    async def _execute_fano_line(
        self,
        routing: Any,  # RoutingResult - deferred
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute via Fano line (3 colonies)."""
        torch = _lazy_import_torch()
        F = _lazy_import_torch_nn_functional()
        semaphore = _get_colony_semaphore()

        # CONCURRENCY FIX (Dec 25, 2025): Execute with bounded concurrency
        async def execute_with_semaphore(action: Any) -> None:
            async with semaphore:
                colony = self._get_colony(action.colony_idx)  # type: ignore[misc]
                return await colony.execute(action.action, params, context)  # type: ignore[no-any-return]

        tasks = [execute_with_semaphore(action) for action in routing.actions]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error(f"Colony {routing.actions[i].colony_idx} execution failed: {result}")
                # Create a failure result placeholder
                results[i] = type("FailedResult", (), {"success": False, "result": {}})()
        results = list(results)

        # Create 8D outputs using semantic embeddings from results
        output = torch.zeros(7, 8)
        for i, action in enumerate(routing.actions):
            output[action.colony_idx] = self._extract_octonion_output(
                results[i], action.colony_idx, action.weight
            )
        output = F.normalize(output, dim=-1)

        return {
            "results": results,
            "colony_outputs": output.unsqueeze(0),  # [1, 7, 8]
        }

    async def _execute_all_colonies(
        self,
        routing: Any,  # RoutingResult - deferred
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute via all 7 colonies."""
        torch = _lazy_import_torch()
        F = _lazy_import_torch_nn_functional()
        semaphore = _get_colony_semaphore()

        # CONCURRENCY FIX (Dec 25, 2025): Execute with bounded concurrency
        async def execute_with_semaphore(action: Any) -> None:
            async with semaphore:
                colony = self._get_colony(action.colony_idx)  # type: ignore[misc]
                return await colony.execute(action.action, params, context)  # type: ignore[no-any-return]

        tasks = [execute_with_semaphore(action) for action in routing.actions]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error(f"Colony {routing.actions[i].colony_idx} execution failed: {result}")
                # Create a failure result placeholder
                results[i] = type("FailedResult", (), {"success": False, "result": {}})()
        results = list(results)

        # Create 8D outputs using semantic embeddings from results
        output = torch.zeros(7, 8)
        for i, action in enumerate(routing.actions):
            output[action.colony_idx] = self._extract_octonion_output(
                results[i], action.colony_idx, action.weight
            )
        output = F.normalize(output, dim=-1)

        return {
            "results": results,
            "colony_outputs": output.unsqueeze(0),  # [1, 7, 8]
        }

    async def _fuse_e8(
        self,
        colony_outputs: Any,  # torch.Tensor - deferred
    ) -> dict[str, Any]:
        """Fuse colony outputs via E8ActionReducer.

        COHERENCY (Dec 27, 2025): Returns OctonionState for unified representation.
        """
        torch = _lazy_import_torch()
        with torch.no_grad():
            e8_code, e8_index, weights = self._reducer(colony_outputs)

        # COHERENCY: Convert to OctonionState
        octonion_state = self._reducer.to_octonion_state(e8_code, weights)

        return {
            "code": e8_code[0],
            "index": int(e8_index[0].item()),
            "weights": weights[0].tolist(),
            "octonion_state": octonion_state,  # Unified state (Dec 27, 2025)
        }

    async def _enrich_context_with_world_model(
        self,
        intent: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Enrich routing context with world model predictions.

        NEXUS BRIDGE (Dec 19, 2025): Closes integration gap between RSSM
        and FanoActionRouter. Populates `wm_colony_hint` for routing.

        Args:
            intent: Intent being executed
            params: Intent parameters
            context: Existing context dict[str, Any]

        Returns:
            Updated context with world model hints
        """
        try:
            # Lazy import to avoid circular dependencies
            from kagami.core.world_model.colony_rssm import get_organism_rssm
            from kagami.core.world_model.routing_hints import (
                enrich_routing_context_with_world_model,
            )
            from kagami.core.world_model.service import get_world_model_service

            # Get world model service
            wm_service = get_world_model_service()
            if not wm_service.is_available:
                logger.debug("World model unavailable for routing hints")
                return context

            # Get current RSSM states (list[ColonyState])
            rssm = get_organism_rssm()
            rssm_states = None
            if rssm is not None:
                try:
                    # Get current colony states from RSSM
                    if hasattr(rssm, "get_current_states"):
                        rssm_states = rssm.get_current_states()
                    elif hasattr(rssm, "_current_states"):
                        rssm_states = rssm._current_states
                except Exception as e:
                    logger.debug(f"Failed to get RSSM states: {e}")

            # Construct observation from intent + params
            observation = {
                "intent": intent,
                "params": params,
                "context": context,
            }

            # Enrich context with world model predictions
            context = enrich_routing_context_with_world_model(
                context=context,
                world_model_service=wm_service,
                observation=observation,
                rssm_state=rssm_states,  # list[ColonyState]
            )

            return context

        except Exception as e:
            logger.debug(f"World model context enrichment failed: {e}")
            return context

    # =========================================================================
    # E8 COMMUNICATION
    # =========================================================================

    def encode_e8_message(
        self,
        source_colony: int,
        target_colony: int,
        data: Any,  # torch.Tensor - deferred
    ) -> dict[str, Any]:
        """Encode a message using E8 protocol.

        Args:
            source_colony: Source colony index (0-6)
            target_colony: Target colony index (0-6)
            data: 8D data tensor

        Returns:
            E8 encoded message
        """
        torch = _lazy_import_torch()
        F = _lazy_import_torch_nn_functional()

        # Normalize to S⁷
        normalized = F.normalize(data.unsqueeze(0), dim=-1)

        # Quantize to E8
        with torch.no_grad():
            # NOTE (MPS): `torch.cdist` backward is not implemented on MPS (and we don't
            # need true cdist semantics here). Squared distances are enough for argmin.
            x = normalized.to(torch.float32)  # [1, 8]
            r = self._e8_roots.to(torch.float32)  # [240, 8]
            x2 = (x * x).sum(dim=-1, keepdim=True)  # [1, 1]
            r2 = (r * r).sum(dim=-1).unsqueeze(0)  # [1, 240]
            d2 = (x2 + r2 - 2.0 * (x @ r.transpose(0, 1))).clamp_min(0.0)  # [1, 240]
            e8_index = d2.argmin(dim=-1)  # [1]

        return {
            "source": source_colony,
            "target": target_colony,
            "e8_index": int(e8_index[0].item()),
            "e8_root": self._e8_roots[e8_index[0]].tolist(),
        }

    def decode_e8_message(
        self,
        e8_index: int,
    ) -> Any:  # torch.Tensor - deferred
        """Decode E8 message to data tensor.

        Args:
            e8_index: E8 root index (0-239)

        Returns:
            8D data tensor
        """
        return self._e8_roots[e8_index]


# =============================================================================
# FACTORY
# =============================================================================


def create_colony_coordinator(
    router: Any,  # FanoActionRouter - deferred
    reducer: Any,  # E8ActionReducer - deferred
    e8_roots: Any,  # torch.Tensor - deferred
    get_colony_fn: callable,  # type: ignore[valid-type]
) -> ColonyCoordinator:
    """Create a colony coordinator.

    Args:
        router: FanoActionRouter instance
        reducer: E8ActionReducer instance
        e8_roots: E8 roots tensor [240, 8]
        get_colony_fn: Function to get colony by index

    Returns:
        Configured ColonyCoordinator
    """
    return ColonyCoordinator(
        router=router,
        reducer=reducer,
        e8_roots=e8_roots,
        get_colony_fn=get_colony_fn,
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ColonyCoordinator",
    "create_colony_coordinator",
]
