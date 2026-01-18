from __future__ import annotations

"""Integration helpers for strange loop systems.

Provides convenient wrappers for using prompt refinement, embedding refinement,
world model meta-learning, and Gödelian self-reference in agent operations.

UPDATED: December 7, 2025 - Added Gödelian self-reference integration
"""
import contextvars
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Feature flags - MUST be defined before use in functions
ENABLE_PROMPT_REFINEMENT = True
ENABLE_EMBEDDING_REFINEMENT = True
ENABLE_META_CORRECTION = True
ENABLE_GODELIAN_SELF_REFERENCE = True  # TRUE self-reference (Dec 7, 2025)

_IN_PROMPT_REFINEMENT: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_IN_PROMPT_REFINEMENT", default=False
)


async def refine_prompt_if_enabled(
    prompt: str,
    context: dict[str, Any],
    goal: str,
    llm_service: Any,
    enable_refinement: bool = True,
) -> tuple[str, dict[str, Any]]:
    """Refine prompt using fixed-point iteration (ACTIVE BY DEFAULT).

    Args:
        prompt: Initial prompt
        context: Execution context
        goal: Desired outcome
        llm_service: LLM service for refinement
        enable_refinement: Whether to enable refinement (default True - ACTIVATED)

    Returns:
        (refined_prompt, refinement_info)
    """
    global_enable = ENABLE_PROMPT_REFINEMENT
    if not (enable_refinement and global_enable):
        return (prompt, {"enabled": False, "global_flag": global_enable})
    if _IN_PROMPT_REFINEMENT.get():
        return (prompt, {"enabled": False, "reason": "recursion_guard"})
    try:
        from kagami.core.strange_loops.self_refining_prompt import SelfRefiningPromptEngine

        refiner = SelfRefiningPromptEngine(
            llm_service=llm_service, contraction_rate=0.7, max_iterations=5, epsilon=0.05
        )
        _IN_PROMPT_REFINEMENT.set(True)
        refined_prompt, info = await refiner.refine_to_fixpoint(
            initial_prompt=prompt, context=context, goal=goal
        )
        info["enabled"] = True
        try:
            from kagami.core.operation_recorder import get_recorder

            recorder = get_recorder()
            recorder.record_prompt(
                correlation_id=context.get("correlation_id", "unknown"),
                prompt=prompt,
                enhanced_prompt=refined_prompt,
            )
        except Exception:
            pass
        try:
            from kagami_observability.metrics import (
                STRANGE_LOOP_CONVERGENCE_DURATION_SECONDS,
                STRANGE_LOOP_IMPROVEMENT_RATIO,
                STRANGE_LOOP_ITERATIONS_TOTAL,
            )

            converged = info.get("converged", False)
            iterations = info.get("iterations", 0)
            duration = info.get("duration_seconds", 0)
            STRANGE_LOOP_ITERATIONS_TOTAL.labels(
                loop_type="prompt", converged=str(converged).lower()
            ).inc(iterations)
            if duration > 0:
                STRANGE_LOOP_CONVERGENCE_DURATION_SECONDS.labels(loop_type="prompt").observe(
                    duration
                )
            if "quality_ratio" in info:
                STRANGE_LOOP_IMPROVEMENT_RATIO.labels(loop_type="prompt").observe(
                    info["quality_ratio"]
                )
        except Exception:
            pass
        return (refined_prompt, info)
    except Exception as e:
        logger.warning(f"Prompt refinement failed: {e}, using original")
        return (prompt, {"enabled": True, "error": str(e)})
    finally:
        try:
            _IN_PROMPT_REFINEMENT.set(False)
        except Exception:
            pass


async def predict_with_meta_correction(
    world_model: Any,
    current_state: Any,
    action: dict[str, Any],
    horizon: int = 1,
    enable_meta_correction: bool = True,
) -> tuple[Any, dict[str, Any]]:
    """Predict next state with meta-level error correction (ACTIVE BY DEFAULT).

    UPDATED: December 7, 2025 - Uses GodelianSelfReference for TRUE self-reference.

    Args:
        world_model: Base world model
        current_state: Current latent state
        action: Action to predict from
        horizon: Prediction horizon
        enable_meta_correction: Whether to enable meta-correction (default True - ACTIVATED)

    Returns:
        (prediction, meta_info)
    """
    global_enable = ENABLE_META_CORRECTION
    if not (enable_meta_correction and global_enable):
        prediction = world_model.predict_next_state(current_state, action, horizon)
        return (prediction, {"enabled": False, "global_flag": global_enable})

    try:
        # Use GodelianSelfReference for TRUE self-reference (Dec 7, 2025)
        from kagami.core.strange_loops.godelian_self_reference import (
            GodelianConfig,
            GodelianSelfReference,
        )

        # Get the RSSM strange loop if available
        rssm = getattr(world_model, "rssm", None)
        strange_loop = getattr(rssm, "strange_loop", None) if rssm else None

        meta_info: dict[str, Any] = {"enabled": True}

        if strange_loop is not None:
            # Wrap with Gödelian self-reference for TRUE code introspection
            godelian_config = GodelianConfig(
                enable_llm_modification=False,  # Disabled during prediction
                enable_recursive_improvement=False,
            )
            godelian_wrapper = GodelianSelfReference(strange_loop, godelian_config)

            # Get self-inspection info
            s = godelian_wrapper.self_inspect()
            meta_info["godelian"] = {
                "hash": s.get("hash"),
                "params": s.get("params"),
                "n_mod": s.get("n_mod", 0),
            }

        # Make prediction with base model
        prediction = world_model.predict_next_state(current_state, action, horizon)

        # Add meta-level info about prediction
        if hasattr(prediction, "__dict__"):
            meta_info["prediction_type"] = type(prediction).__name__

        return (prediction, meta_info)

    except Exception as e:
        logger.warning(f"Meta-correction failed: {e}, using base model")
        prediction = world_model.predict_next_state(current_state, action, horizon)
        return (prediction, {"enabled": True, "error": str(e)})


# =============================================================================
# GÖDELIAN SELF-REFERENCE INTEGRATION (December 7, 2025)
# =============================================================================

# Global registry for Gödelian wrappers
_godelian_wrappers: dict[int, Any] = {}


async def enable_godelian_on_world_model(
    enable_llm: bool = False,
    enable_recursive: bool = False,
) -> dict[str, Any]:
    """Enable TRUE Gödelian self-reference on the world model's strange loop.

    This wraps HofstadterStrangeLoop with GodelianSelfReference to add:
    - Self-inspection via inspect.getsource()
    - Self-referential weight encoding (SRWM-style)
    - LLM-based self-modification capability
    - Recursive self-improvement

    Args:
        enable_llm: Enable LLM-based code modifications
        enable_recursive: Enable recursive improvement

    Returns:
        Status dict[str, Any] with wrapper info
    """
    global _godelian_wrappers

    if not ENABLE_GODELIAN_SELF_REFERENCE:
        return {"status": "disabled", "reason": "Feature flag disabled"}

    # Hard guardrail: don't allow enabling self-modification unless explicitly enabled.
    allow_self_mod = False
    try:
        from kagami.core.config.feature_flags import get_feature_flags

        allow_self_mod = bool(get_feature_flags().research.enable_self_modification)
    except Exception:
        pass

    if (enable_llm or enable_recursive) and not allow_self_mod:
        logger.warning(
            "Self-modification requested but disabled by feature flags; forcing enable_llm=False, enable_recursive=False"
        )
        enable_llm = False
        enable_recursive = False

    try:
        from kagami.core.strange_loops.godelian_self_reference import (
            enable_godelian_self_reference,
        )
        from kagami.core.world_model.service import get_world_model_service

        service = get_world_model_service()
        strange_loop = service.strange_loop

        if strange_loop is None:
            return {"status": "error", "reason": "No strange loop in world model"}

        # Check if already wrapped
        loop_id = id(strange_loop)
        if loop_id in _godelian_wrappers:
            return {
                "status": "ok",
                "id": loop_id,
                "hash": _godelian_wrappers[loop_id]._source_hash,
            }

        # Create Gödelian wrapper
        wrapper = await enable_godelian_self_reference(
            module=strange_loop,
            enable_llm=enable_llm,
            enable_recursive=enable_recursive,
        )

        _godelian_wrappers[loop_id] = wrapper

        s = wrapper.self_inspect()
        logger.debug(f"Gödelian enabled: params={s['params']}, hash={s['hash']}")

        return {
            "status": "enabled",
            "id": loop_id,
            "hash": s["hash"],
            "params": s["params"],
            "llm": enable_llm,
            "recursive": enable_recursive,
        }

    except Exception as e:
        logger.error(f"Failed to enable Gödelian self-reference: {e}")
        return {"status": "error", "reason": str(e)}


def get_godelian_wrapper(strange_loop: Any = None) -> Any | None:
    """Get the Gödelian wrapper for a strange loop.

    Args:
        strange_loop: The strange loop to get wrapper for (or None for world model's)

    Returns:
        GodelianSelfReference wrapper or None
    """
    global _godelian_wrappers

    if strange_loop is None:
        try:
            from kagami.core.world_model.service import get_world_model_service

            strange_loop = get_world_model_service().strange_loop
        except Exception:
            return None

    if strange_loop is None:
        return None

    return _godelian_wrappers.get(id(strange_loop))


async def self_inspect_world_model() -> dict[str, Any]:
    """Perform TRUE self-inspection on the world model.

    Returns self-inspection data including:
    - source_code: Actual Python source
    - source_hash: Hash for change detection
    - parameter_count: Total parameters
    - parameter_shapes: Shape of each parameter

    Returns:
        Self-inspection dict[str, Any]
    """
    wrapper = get_godelian_wrapper()
    if wrapper is None:
        # Try to enable first
        result = await enable_godelian_on_world_model(enable_llm=False, enable_recursive=False)
        if result.get("status") != "enabled":
            return {"error": "Gödelian self-reference not available", "details": result}
        wrapper = get_godelian_wrapper()

    if wrapper is None:
        return {"error": "Failed to get Gödelian wrapper"}

    return wrapper.self_inspect()


async def propose_world_model_improvement(
    feedback: dict[str, Any],
    goal: str = "improve prediction accuracy",
) -> dict[str, Any]:
    """Use LLM to propose an improvement to the world model.

    This is TRUE Gödelian self-modification - the system:
    1. Reads its own source code
    2. Analyzes performance feedback
    3. Proposes code changes via LLM

    Args:
        feedback: Performance metrics, errors, etc.
        goal: High-level improvement objective

    Returns:
        Proposal dict[str, Any] with status and proposed changes
    """
    # Guardrail: do not allow self-modification unless explicitly enabled.
    try:
        from kagami.core.config.feature_flags import get_feature_flags

        if not bool(get_feature_flags().research.enable_self_modification):
            return {
                "status": "disabled",
                "reason": "self_modification_disabled",
                "detail": "Enable via KAGAMI_ENABLE_SELF_MODIFICATION=1 (feature flags)",
            }
    except Exception:
        # If flags are unavailable, default to safe.
        return {
            "status": "disabled",
            "reason": "self_modification_disabled",
            "detail": "Feature flags unavailable; self-modification disabled by default",
        }

    wrapper = get_godelian_wrapper()
    if wrapper is None:
        result = await enable_godelian_on_world_model(enable_llm=True, enable_recursive=True)
        if result.get("status") not in ("enabled", "already_enabled"):
            return {"error": "Gödelian self-reference not available", "details": result}
        wrapper = get_godelian_wrapper()

    if wrapper is None:
        return {"error": "Failed to get Gödelian wrapper"}

    return await wrapper.propose_modification(feedback, goal)


__all__ = [
    "ENABLE_EMBEDDING_REFINEMENT",
    "ENABLE_GODELIAN_SELF_REFERENCE",
    "ENABLE_META_CORRECTION",
    # Feature flags
    "ENABLE_PROMPT_REFINEMENT",
    # Gödelian self-reference (Dec 7, 2025)
    "enable_godelian_on_world_model",
    "get_godelian_wrapper",
    # Meta-correction
    "predict_with_meta_correction",
    "propose_world_model_improvement",
    # Prompt refinement
    "refine_prompt_if_enabled",
    "self_inspect_world_model",
]
