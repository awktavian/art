"""World Model → Routing Hints Integration.

NEXUS BRIDGE (December 19, 2025):
===================================
Connects RSSM world model predictions to FanoActionRouter routing decisions.

COHERENCY REFACTOR (December 27, 2025):
=======================================
Updated to use OctonionState for unified state representation across the pipeline.
Now includes s7_phase in wm_colony_hint for direct routing integration.

INTEGRATION GAP CLOSURE:
========================
FanoActionRouter checks for `wm_colony_hint` in context but no code
populates this hint. This module closes the gap by:

1. Extracting colony activation scores from RSSM hidden state
2. Computing confidence using S7 phase coherence
3. Formatting hint dict[str, Any] for router consumption
4. Including OctonionState for unified downstream processing

MATHEMATICAL FOUNDATION:
========================
The RSSM maintains colony-specific hidden states h_t ∈ R^{7 × deter_dim}.
Each colony's activation is computed from its deterministic state via:

    activation_i = softmax(h_i @ W_colony)[i]

where W_colony projects hidden state to colony preference logits.

S7 phase coherence provides confidence:
    confidence = 1 - std(s7_phase) / mean(s7_phase)

High coherence = reliable prediction, low coherence = uncertain.

Created: December 19, 2025
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import torch
else:
    torch = None  # type: ignore

logger = logging.getLogger(__name__)


def _lazy_import_torch() -> Any:
    """Lazy import torch to avoid blocking module import."""
    import torch

    return torch


def extract_colony_hint_from_rssm(
    rssm_states: list[Any],  # list[ColonyState] from rssm_components
    confidence_threshold: float = 0.6,
) -> dict[str, Any] | None:
    """Extract colony routing hint from RSSM states.

    Analyzes RSSM deterministic state (h_t) to predict which colony
    is most suited for the current task context.

    Args:
        rssm_states: list[ColonyState] (7 colonies)
        confidence_threshold: Minimum confidence to return hint (default 0.6)

    Returns:
        Colony hint dict[str, Any] with keys:
        - colony_idx: int (0-6)
        - colony_name: str
        - confidence: float (0-1)
        - source: str ("rssm_state")
        OR None if confidence below threshold or state unavailable

    Example:
        >>> from kagami.core.world_model.colony_rssm import get_organism_rssm
        >>> rssm = get_organism_rssm()
        >>> states = rssm.get_current_states()  # list[ColonyState]
        >>> hint = extract_colony_hint_from_rssm(states)
        >>> if hint:
        ...     print(f"Predicted colony: {hint['colony_name']} ({hint['confidence']:.2f})")
    """
    if rssm_states is None or not isinstance(rssm_states, list):
        return None

    torch = _lazy_import_torch()

    try:
        # Extract hidden states from each colony
        colony_hidden_states = []
        for colony_state in rssm_states:
            h = getattr(colony_state, "hidden", None)
            if h is not None and isinstance(h, torch.Tensor):
                colony_hidden_states.append(h)

        if len(colony_hidden_states) != 7:
            logger.debug(f"Invalid colony count: expected 7, got {len(colony_hidden_states)}")
            return None

        # Stack colony hidden states [7, B, deter_dim]
        h_stacked = torch.stack(colony_hidden_states, dim=0)  # [7, B, deter_dim]

        # Extract batch 0 if batched
        if h_stacked.shape[1] > 1:
            h_stacked = h_stacked[:, 0, :]  # [7, deter_dim]
        else:
            h_stacked = h_stacked.squeeze(1)  # [7, deter_dim]

        # Compute colony activation scores (L2 norm = energy proxy)
        colony_energies = torch.norm(h_stacked, dim=-1)  # [7]

        # Normalize to probabilities
        colony_activations = torch.softmax(colony_energies, dim=0)  # [7]

        # Find best colony
        best_colony_idx = int(torch.argmax(colony_activations).item())
        colony_confidence = float(colony_activations[best_colony_idx].item())

        # Compute S7 phase coherence for confidence adjustment
        # Extract s7_phase from metadata (organism-level)
        s7_phase = None
        if len(rssm_states) > 0:
            # Check both direct attribute and metadata
            s7_phase = getattr(rssm_states[0], "s7_phase", None)
            if s7_phase is None:
                s7_phase = rssm_states[0].metadata.get("s7_phase")

        if s7_phase is not None and isinstance(s7_phase, torch.Tensor):
            # S7 coherence: how aligned is the phase?
            s7_norm = torch.norm(s7_phase, dim=-1)  # [B, 7] or [7]
            if s7_norm.numel() > 1:  # Need at least 2 elements for std
                std = float(torch.std(s7_norm).item())
                mean = float(torch.mean(s7_norm).item())
                # Handle edge cases
                if mean > 1e-6 and not torch.isnan(s7_norm).any():
                    coherence = 1.0 - std / (mean + 1e-6)
                    # Clamp coherence to [0, 1]
                    coherence = max(0.0, min(1.0, coherence))
                    # Blend colony activation confidence with phase coherence
                    colony_confidence = 0.7 * colony_confidence + 0.3 * coherence

        # Check confidence threshold
        if colony_confidence < confidence_threshold:
            logger.debug(
                f"RSSM colony hint below threshold: "
                f"colony={best_colony_idx}, confidence={colony_confidence:.3f} < {confidence_threshold}"
            )
            return None

        # Map colony index to name
        from kagami_math.catastrophe_constants import COLONY_NAMES

        colony_name = COLONY_NAMES[best_colony_idx]

        logger.debug(
            f"RSSM colony hint extracted: {colony_name} (confidence={colony_confidence:.3f})"
        )

        # COHERENCY (Dec 27, 2025): Create OctonionState for unified representation
        from kagami.core.unified_agents.octonion_state import OctonionState

        # Build e8_code from colony activations
        # e₀ = confidence (real part), e₁..e₇ = colony activations
        e8_code = torch.zeros(8)
        e8_code[0] = colony_confidence  # Real part = confidence
        e8_code[1:] = colony_activations  # Imaginary part = colony activations

        octonion = OctonionState(
            e8_code=e8_code,
            confidence=colony_confidence,
            metadata={"source": "rssm_state"},
        )

        return {
            "colony_idx": best_colony_idx,
            "colony_name": colony_name,
            "confidence": colony_confidence,
            "source": "rssm_state",
            # COHERENCY (Dec 27, 2025): Include S7 phase and OctonionState
            "s7_phase": colony_activations,  # [7] - colony routing weights
            "octonion_state": octonion,  # Unified representation
        }

    except Exception as e:
        logger.debug(f"Failed to extract colony hint from RSSM state: {e}")
        return None


def extract_colony_hint_from_world_model(
    world_model_service: Any,  # WorldModelService
    observation: dict[str, Any],
    action: dict[str, Any] | None = None,
    confidence_threshold: float = 0.6,
) -> dict[str, Any] | None:
    """Extract colony routing hint from world model prediction.

    Queries world model for next-state prediction and extracts colony preference.

    Args:
        world_model_service: WorldModelService instance
        observation: Current observation dict[str, Any]
        action: Optional action dict[str, Any] (uses "route_intent" if None)
        confidence_threshold: Minimum confidence for hint

    Returns:
        Colony hint dict[str, Any] or None

    Example:
        >>> from kagami.core.world_model.service import get_world_model_service
        >>> service = get_world_model_service()
        >>> obs = {"intent": "build.feature", "params": {}}
        >>> hint = extract_colony_hint_from_world_model(service, obs)
    """
    if world_model_service is None or not world_model_service.is_available:
        return None

    try:
        # Use action routing type if not specified
        if action is None:
            action = {"type": "route_intent"}

        # Query world model for prediction
        prediction = world_model_service.predict(
            observation=observation,
            action=action,
            horizon=1,
        )

        if prediction is None:
            return None

        # Extract colony hint from prediction
        # Check for explicit colony recommendation
        if hasattr(prediction, "recommended_colony"):
            colony_idx = int(prediction.recommended_colony)
            confidence = float(getattr(prediction, "confidence", 0.5))

            if confidence < confidence_threshold:
                return None

            from kagami_math.catastrophe_constants import COLONY_NAMES

            return {
                "colony_idx": colony_idx,
                "colony_name": COLONY_NAMES[colony_idx],
                "confidence": confidence,
                "source": "world_model_prediction",
            }

        # Extract from latent state (RSSM-based)
        if hasattr(prediction, "state") and prediction.state is not None:
            state_tensor = prediction.state
            torch = _lazy_import_torch()

            if isinstance(state_tensor, torch.Tensor) and state_tensor.numel() >= 7:
                # Use first 7 dims as colony activation probabilities
                colony_activations = state_tensor.flatten()[:7]
                best_colony_idx = int(torch.argmax(colony_activations).item())

                s7_softmax = torch.softmax(colony_activations, dim=0)
                confidence = float(s7_softmax[best_colony_idx].item())

                if confidence < confidence_threshold:
                    return None

                from kagami_math.catastrophe_constants import COLONY_NAMES

                from kagami.core.unified_agents.octonion_state import OctonionState

                # COHERENCY (Dec 27, 2025): Create OctonionState
                e8_code = torch.zeros(8)
                e8_code[0] = confidence
                e8_code[1:] = s7_softmax

                octonion = OctonionState(
                    e8_code=e8_code,
                    confidence=confidence,
                    metadata={"source": "world_model_state"},
                )

                return {
                    "colony_idx": best_colony_idx,
                    "colony_name": COLONY_NAMES[best_colony_idx],
                    "confidence": confidence,
                    "source": "world_model_state",
                    "s7_phase": s7_softmax,  # [7] - colony routing weights
                    "octonion_state": octonion,  # Unified representation
                }

        return None

    except Exception as e:
        logger.debug(f"Failed to extract colony hint from world model: {e}")
        return None


def enrich_routing_context_with_world_model(
    context: dict[str, Any],
    world_model_service: Any,
    observation: dict[str, Any] | None = None,
    rssm_state: Any = None,
) -> dict[str, Any]:
    """Enrich routing context with world model predictions.

    NEXUS BRIDGE: Primary entry point for world model → routing integration.

    This function is called by ColonyCoordinator before routing to inject
    world model predictions into the routing context. FanoActionRouter
    will check for `wm_colony_hint` and use it if confident.

    Args:
        context: Existing routing context dict[str, Any] (will be modified)
        world_model_service: WorldModelService instance
        observation: Current observation (optional)
        rssm_state: Current RSSM state (optional)

    Returns:
        Updated context dict[str, Any] with `wm_colony_hint` if prediction available

    Example:
        >>> from kagami.core.world_model.service import get_world_model_service
        >>> from kagami.core.world_model.colony_rssm import get_organism_rssm
        >>>
        >>> service = get_world_model_service()
        >>> rssm = get_organism_rssm()
        >>> state = rssm.get_state()
        >>>
        >>> context = {}
        >>> context = enrich_routing_context_with_world_model(
        ...     context, service, rssm_state=state
        ... )
        >>> if "wm_colony_hint" in context:
        ...     print(f"World model suggests: {context['wm_colony_hint']['colony_name']}")
    """
    # Try RSSM state first (fastest, most direct)
    if rssm_state is not None:
        hint = extract_colony_hint_from_rssm(rssm_state)
        if hint is not None:
            context["wm_colony_hint"] = hint
            logger.debug(f"Added RSSM colony hint to context: {hint['colony_name']}")
            return context

    # Fallback to world model prediction (slower, requires forward pass)
    if observation is not None and world_model_service is not None:
        hint = extract_colony_hint_from_world_model(world_model_service, observation)
        if hint is not None:
            context["wm_colony_hint"] = hint
            logger.debug(f"Added WM colony hint to context: {hint['colony_name']}")
            return context

    # No hint available
    logger.debug("No world model colony hint available for routing")
    return context


__all__ = [
    "enrich_routing_context_with_world_model",
    "extract_colony_hint_from_rssm",
    "extract_colony_hint_from_world_model",
]
