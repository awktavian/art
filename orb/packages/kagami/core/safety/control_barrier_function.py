"""Backward-compatibility import bridge for Control Barrier Functions.

This module re-exports types and functions for legacy code.
Both import paths are supported and functionally equivalent.

Canonical: from kagami.core.safety import check_cbf_for_operation, SafetyState
Legacy:    from kagami.core.safety.control_barrier_function import SafetyState

HARDENED (Dec 7, 2025): All safety extraction uses trained WildGuard + OptimalCBF.
NO heuristic fallbacks - trained models are MANDATORY.
"""

from __future__ import annotations

# Re-export canonical types (Dec 6, 2025 - consolidation)
from kagami.core.exceptions import SafetyViolationError
from kagami.core.safety.types import (
    CBFResult,
    ContextDict,
    ControlInput,
    SafetyState,
)

__all__ = [
    "CBFResult",
    "ControlBarrierFunction",
    "ControlInput",
    "SafetyState",
    "SafetyViolationError",
    "extract_nominal_control",
    "extract_safety_state",
    "extract_safety_state_async",
    "get_control_barrier_function",
]


# =============================================================================
# SAFETY STATE EXTRACTION (Trained CBF - MANDATORY)
# =============================================================================


def extract_safety_state(context: ContextDict, use_semantic: bool = True) -> SafetyState:
    """Extract safety state using TRAINED CBF only.

    HARDENED (Dec 7, 2025): Uses trained WildGuard + OptimalCBF via cbf_integration.
    NO HEURISTIC FALLBACK - trained CBF is MANDATORY.

    Args:
        context: Operation context dict[str, Any] with operation, action, target, etc.
        use_semantic: Ignored (always uses trained classifier)

    Returns:
        SafetyState with threat, uncertainty, complexity, predictive_risk

    Raises:
        RuntimeError: If trained CBF is unavailable
    """
    # Use trained CBF via cbf_integration (MANDATORY - no fallback)
    import torch

    from kagami.core.safety.cbf_integration import (
        _build_text_for_classification,
        _get_safety_filter,
    )

    safety_filter = _get_safety_filter()
    text_to_classify = (
        context.get("user_input")
        or context.get("content")
        or _build_text_for_classification(context)
    )

    # Run trained classifier
    nominal_control = torch.tensor([[0.5, 0.5]], dtype=torch.float32)
    _safe_control, _penalty, info = safety_filter.filter_text(
        text=text_to_classify,
        nominal_control=nominal_control,
        context=str(context.get("metadata", {}))[:200],
    )

    # Extract safety metrics from trained model
    h_tensor = info.get("h_metric")
    if h_tensor is not None:
        h_x = (
            float(h_tensor.mean().item()) if isinstance(h_tensor, torch.Tensor) else float(h_tensor)
        )
    else:
        # CRITICAL FIX (Dec 27, 2025): Fail closed with h_x = -1.0 (unsafe)
        # If h_metric is missing, assume unsafe rather than safe
        h_x = -1.0

    # Convert h(x) to threat (h=1 is safe, h=0 is unsafe)
    threat = max(0.0, min(1.0, 1.0 - h_x))
    uncertainty = info.get("uncertainty", 0.3)
    complexity = info.get("complexity", 0.3)
    predictive_risk = info.get("predictive_risk", threat * 0.8)

    return SafetyState(
        threat=threat,
        uncertainty=uncertainty,
        complexity=complexity,
        predictive_risk=predictive_risk,
    )


async def extract_safety_state_async(
    context: ContextDict, use_semantic: bool = True
) -> SafetyState:
    """Async wrapper for extract_safety_state."""
    return extract_safety_state(context, use_semantic)


def extract_nominal_control(context: ContextDict) -> ControlInput:
    """Extract desired control from operation intent.

    ARCHITECTURE (December 22, 2025):
    NO keyword heuristics. Control parameters from explicit metadata only.
    """
    metadata = context.get("metadata", {})

    # Use explicit metadata values, not keyword guessing
    aggression = float(metadata.get("aggression", 0.5))
    speed = float(metadata.get("speed", 0.5))

    # Structural flags only
    if context.get("urgent", False):
        speed = max(speed, 0.9)
    elif context.get("careful", False):
        speed = min(speed, 0.3)

    return ControlInput(aggression=aggression, speed=speed)


# =============================================================================
# SIMPLIFIED RE-EXPORTS (canonical imports)
# =============================================================================

# Re-export from optimal_cbf for canonical import paths
# get_cbf_filter removed - use get_safety_filter from kagami.core.safety
from kagami.core.safety.optimal_cbf import (
    OptimalCBF as ControlBarrierFunction,
)
from kagami.core.safety.optimal_cbf import (
    get_optimal_cbf as get_control_barrier_function,
)
