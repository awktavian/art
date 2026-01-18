"""Simplified process_intent implementation using intent_router pattern.

This module provides a cleaner implementation of intent processing that delegates
to the existing modular components instead of having 1106 lines of branching logic.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, cast

from fastapi import HTTPException

logger = logging.getLogger(__name__)


async def _capture_pre_state(intent: dict[str, Any]) -> dict[str, Any] | None:
    """Capture state before execution for learning loop."""
    try:
        from kagami.core.receipts.state_capture import (
            capture_state_for_learning,
            should_capture_state,
        )

        if should_capture_state(intent):
            captured = capture_state_for_learning(intent)
            return cast(dict[str, Any], captured) if isinstance(captured, dict) else None  # type: ignore[redundant-cast]
    except Exception as e:
        logger.debug(f"State capture failed (non-critical): {e}")
    return None


async def _check_safety_gates(intent: dict[str, Any]) -> dict[str, Any] | None:
    """Run safety checks (CBF, Policy). Return error dict[str, Any] if unsafe, None if safe."""
    try:
        from kagami.core.orchestrator.safety_gates import SafetyGates

        gates = SafetyGates()

        # Run CBF check first (fastest)
        cbf_result = await gates.check_cbf_safety(intent)
        if not cbf_result.safe:
            return cbf_result.to_error_response()

        # Run policy check (dangerous patterns)
        policy_result = await gates.check_policy(intent)
        if not policy_result.safe:
            return policy_result.to_error_response()

    except Exception as e:
        # SAFETY: If safety check fails to execute, block operation (fail-closed)
        logger.error(f"Safety gates execution failed: {e} - BLOCKING operation")
        return {
            "status": "blocked",
            "reason": "safety_check_error",
            "detail": f"Safety verification failed: {e}",
            "error": str(e),
        }
    return None


def _check_cache(orchestrator: Any, intent: dict[str, Any]) -> dict[str, Any] | None:
    """Check response cache."""
    if orchestrator._response_cache:
        action = intent.get("action", "")
        if action.startswith(("query.", "get.", "list[Any].", "search.")):
            cached = orchestrator._response_cache.get(intent)
            if cached:
                logger.debug(f"Cache hit for {action}")
                return cast(dict[str, Any], cached)
    return None


async def _execute_strategy(orchestrator: Any, intent: dict[str, Any]) -> dict[str, Any] | None:
    """Execute configured strategy if present."""
    if orchestrator._strategy is None:
        return None

    try:
        if hasattr(orchestrator._strategy, "initialize"):
            if not getattr(orchestrator._strategy, "_initialized", True):
                await orchestrator._strategy.initialize()

        result = await orchestrator._strategy.execute(
            intent=intent,
            apps=orchestrator._apps,
            config={
                "db_session": getattr(orchestrator, "db_session", None),
                "fs": getattr(orchestrator, "fs", None),
            },
        )
        return cast(dict[str, Any], result)
    except Exception as e:
        logger.error(f"❌ Strategy execution failed: {e}")
        raise RuntimeError(
            f"Orchestration strategy failed: {e}\n"
            "K os requires functioning processing_state/RL for all operations.\n"
            "Cannot fall back to default logic - that defeats the purpose."
        ) from e


async def _handle_explicit_routing(
    orchestrator: Any, intent: dict[str, Any]
) -> dict[str, Any] | None:
    """Handle explicit app routing via 'app' field."""
    from kagami.core.orchestrator.utils import _normalize_app_name

    explicit_app = intent.get("app")
    if explicit_app:
        normalized_app = _normalize_app_name(explicit_app)
        if normalized_app:
            try:
                direct_result = await _route_to_app(orchestrator, intent, normalized_app)
                if isinstance(direct_result, dict) and direct_result.get("status") != "error":
                    return direct_result
                logger.debug(
                    "Explicit app routing returned error, falling back to semantic router",
                )
            except Exception as e:
                logger.warning(f"Explicit app routing failed for {normalized_app}: {e}")
    return None


async def _handle_code_generation(
    orchestrator: Any, intent: dict[str, Any]
) -> dict[str, Any] | None:
    """Handle generate_code action."""
    action_lower = (intent.get("action") or "").lower()
    params = intent.get("params", {})

    if action_lower != "generate_code" or not params.get("prompt"):
        return None

    try:
        code_result = await orchestrator._handle_arbitrary_intent(
            intent,
            intent.get("metadata", {}),
            None,
        )
    except HTTPException as exc:
        # Extract detail dict[str, Any], defaulting to empty if not a dict[str, Any]
        detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}  # type: ignore[unreachable]
        err = detail.get("error") or detail.get("result", {}).get("error")
        if err == "verification_failed":
            detail["status"] = "blocked"
        else:
            detail.setdefault("status", "error")
        return detail if detail else {"status": "blocked", "reason": str(exc.detail)}

    if isinstance(code_result, dict):
        err = code_result.get("error") or code_result.get("result", {}).get("error")
        if err == "verification_failed":
            return {
                "status": "blocked",
                "result": code_result.get("result", code_result),
                "intent": code_result.get("intent", intent),
            }
        if code_result.get("status") in {"accepted", "success"}:
            return code_result
        return code_result
    return None


async def _handle_reflex_layer(orchestrator: Any, intent: dict[str, Any]) -> dict[str, Any] | None:
    """Check reflex layer for fast-path responses."""
    action = intent.get("action") or intent.get("intent") or intent.get("command")
    action_lower = (str(action or "")).lower()

    # Reflex layer
    try:
        from kagami.core.swarm.reflex_layer import get_reflex_layer

        reflex = get_reflex_layer()
        ctx = {
            "action": str(action or ""),
            "app": intent.get("app"),
            "agent": (intent.get("metadata") or {}).get("agent_name"),
        }
        resp = reflex.try_reflex(ctx)
        if resp is not None:
            return {"status": "accepted", "response": resp}
    except Exception as e:
        # Intentional: Reflex layer is optional, continue without it
        logger.debug(f"Reflex layer unavailable: {e}")

    # Direct sensorimotor routing
    if action and action_lower in {
        "predict_action",
        "observe_and_act",
        "perceive",
        "sensorimotor.predict",
        "sensorimotor.perceive",
        "sensorimotor.act",
    }:
        return cast(dict[str, Any], await orchestrator._handle_sensorimotor_intent(intent))

    return None


async def _route_semantically(orchestrator: Any, intent: dict[str, Any]) -> dict[str, Any] | None:
    """Route intent using semantic router."""
    try:
        from kagami.core.orchestrator.semantic_router import SemanticIntentRouter

        semantic_router = SemanticIntentRouter()
        route_decision = await semantic_router.route(intent)
        handler_type = route_decision.get("handler_type")

        # Handle blocked intents from CBF safety checks
        if handler_type == "blocked":
            metadata = route_decision.get("metadata", {})
            return {
                "status": "blocked",
                "error": "Safety barrier violation",
                "reason": metadata.get("reason", "safety_barrier_violation"),
                "detail": metadata.get("detail", "Intent blocked by safety checks"),
                "h_x": metadata.get("h_x"),
                "correlation_id": metadata.get("correlation_id"),
            }

        if handler_type == "chat":
            params = intent.get("params", {})
            if params.get("message") or params.get("text"):
                return cast(dict[str, Any], await orchestrator._handle_chat_intent(intent, {}))
            return await _handle_arbitrary_intent(orchestrator, intent)

        elif handler_type == "sensorimotor":
            normalized_action = (intent.get("action") or "").lower()
            allowed_actions = {
                "predict_action",
                "observe_and_act",
                "perceive",
                "sensorimotor.predict",
                "sensorimotor.perceive",
                "sensorimotor.act",
            }
            if normalized_action in allowed_actions:
                try:
                    return cast(
                        dict[str, Any], await orchestrator._handle_sensorimotor_intent(intent)
                    )
                except Exception as e:
                    logger.warning(f"Sensorimotor handling failed: {e}")
                    return {"status": "error", "error": str(e)}
            return await _handle_arbitrary_intent(orchestrator, intent)

        elif handler_type == "symbolic":
            from kagami.core.orchestrator.symbolic_handler import handle_symbolic_intent

            return await handle_symbolic_intent(intent)

        elif handler_type == "visual":
            from kagami.core.orchestrator.visual_handler import handle_visual_intent

            return await handle_visual_intent(intent)

        elif handler_type == "causal":
            from kagami.core.orchestrator.causal_handler import handle_causal_intent

            return await handle_causal_intent(intent)

        elif handler_type == "app":
            app_name = route_decision.get("app_name")
            if app_name:
                return await _route_to_app(orchestrator, intent, app_name)

            # ARCHITECTURE: Fallback to deterministic router when semantic router
            # cannot determine app name. This is intentional and correct:
            # - SemanticRouter: ML-based, handles paraphrasing, cross-lingual
            # - IntentRouter: Rule-based, has app aliases, CBF safety, fast paths
            # Both are complementary, not redundant.
            logger.info(
                "Semantic router returned handler_type='app' but no app_name. "
                "Falling back to deterministic IntentRouter for app inference. "
                f"action={intent.get('action')}"
            )

            try:
                # Track fallback usage for observability
                from kagami_observability.metrics.intelligence import (
                    INTENT_ROUTER_FALLBACK_TOTAL,
                )

                INTENT_ROUTER_FALLBACK_TOTAL.inc()
            except Exception as metrics_err:
                # OPTIONAL: Log metrics failure (non-critical telemetry)
                logger.debug(f"Failed to increment router fallback metric: {metrics_err}")

            from kagami.core.orchestrator.intent_router import IntentRouter

            deterministic_router = IntentRouter()
            if orchestrator._operation_router:
                deterministic_router.set_operation_router(orchestrator._operation_router)
            deterministic_decision = await deterministic_router.route(intent)

            if deterministic_decision.app_name:
                logger.info(
                    f"Deterministic router inferred app_name={deterministic_decision.app_name}"
                )
                return await _route_to_app(orchestrator, intent, deterministic_decision.app_name)
            else:
                logger.warning(
                    f"Both semantic and deterministic routers failed to determine app. "
                    f"action={intent.get('action')}, params={intent.get('params')}"
                )

        return await _handle_arbitrary_intent(orchestrator, intent)

    except Exception as e:
        logger.error(f"Intent routing failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "detail": f"Intent processing failed: {e}",
        }


def _close_learning_loop(
    intent: dict[str, Any], result: dict[str, Any], state_before: dict[str, Any]
) -> None:
    """Capture post-state and emit receipt to close learning loop."""
    try:
        from kagami.core.receipts import emit_receipt
        from kagami.core.receipts.state_capture import extract_state_from_result

        state_after = extract_state_from_result(result, state_before)

        if isinstance(result, dict):
            result.setdefault("context", {})
            result["context"]["state_before"] = state_before
            result["context"]["state_after"] = state_after

        correlation_id = result.get("correlation_id") if isinstance(result, dict) else None
        learning_context = {
            "state_before": state_before,
            "state_after": state_after,
        }

        emit_receipt(
            correlation_id=correlation_id,  # type: ignore[arg-type]
            action=intent.get("action", "unknown"),
            app=intent.get("app", "unknown"),
            args=intent.get("params"),
            event_name="intent.executed",
            event_data={
                "phase": "verify",
                "status": result.get("status") if isinstance(result, dict) else "unknown",
            },
            duration_ms=int(
                (state_after.get("timestamp", 0) - state_before.get("timestamp", 0)) * 1000
            ),
            status=result.get("status", "success") if isinstance(result, dict) else "success",
            context=learning_context,
        )

        logger.debug(
            f"✅ Learning loop closed: {state_before['context_hash']} -> {state_after.get('status')} (receipt emitted)"
        )

        try:
            from kagami_observability.metrics.intelligence import STRANGE_LOOP_CLOSED_TOTAL

            STRANGE_LOOP_CLOSED_TOTAL.inc()
        except Exception as metrics_err:
            # OPTIONAL: Log metrics failure (non-critical telemetry)
            logger.debug(f"Failed to increment strange loop metric: {metrics_err}")

    except Exception as e:
        logger.warning(f"Learning loop closure failed: {e}")


def _emit_execution_receipt(intent: dict[str, Any], result: dict[str, Any]) -> None:
    """Emit receipt for intent execution (Dec 21, 2025 - Flow).

    Ensures ALL intent executions create receipts, not just learning loop closures.
    """
    try:
        from kagami.core.receipts import emit_receipt

        # Prioritize metadata correlation_id (for autonomous goals)
        correlation_id = (
            intent.get("metadata", {}).get("correlation_id")
            or result.get("correlation_id")
            or str(uuid.uuid4())
        )

        emit_receipt(
            correlation_id=correlation_id,
            action=intent.get("action", "unknown"),
            app=intent.get("app", "unknown"),
            args=intent.get("params"),
            event_name="intent.executed",
            event_data={
                "status": result.get("status") if isinstance(result, dict) else "unknown",
                "autonomous": intent.get("metadata", {}).get("autonomous", False),
            },
            status=result.get("status", "success") if isinstance(result, dict) else "success",
            phase="EXECUTE",
            metadata=intent.get("metadata", {}),
        )
        logger.debug(f"Receipt emitted: {correlation_id}")
    except Exception as e:
        logger.debug(f"Receipt emission failed (non-critical): {e}")


async def process_intent_v2(
    orchestrator: Any,
    intent: dict[str, Any],
) -> dict[str, Any]:
    """Process intent using the refactored router + strategy pattern.

    This is a refactored replacement for the complex process_intent logic.
    """
    # 0. Validate intent structure early (and before any heavy imports)
    if not isinstance(intent, dict):
        raise ValueError("Intent must be a dict[str, Any]")

    # 0a. Built-in control fast-paths (no side effects)
    # These should never require heavyweight safety/semantic routing.
    try:
        action_raw = intent.get("action") or intent.get("intent") or intent.get("command")
        action_upper = str(action_raw or "").upper()
        target_lower = str(intent.get("target") or "").lower()
        if action_upper == "EXECUTE" and (
            target_lower in {"noop", "ping", "status"} or "echo" in target_lower
        ):
            correlation_id = intent.get("correlation_id") or str(uuid.uuid4())
            return {
                "status": "accepted",
                "result": {
                    "echo": target_lower,
                    "params": intent.get("params", {}),
                    "message": f"Echo: {target_lower}",
                },
                "correlation_id": correlation_id,
            }
    except Exception:
        # Never let the fast-path crash processing
        pass

    # 0. Capture state before execution
    state_before = await _capture_pre_state(intent)

    # 1. Safety Gates
    safety_error = await _check_safety_gates(intent)
    if safety_error:
        return safety_error

    # 2. Response Cache Check
    cached_result = _check_cache(orchestrator, intent)
    if cached_result:
        return cached_result

    # 4. Strategy Execution
    strategy_result = await _execute_strategy(orchestrator, intent)
    if strategy_result:
        return strategy_result

    # 5. Explicit app routing
    explicit_result = await _handle_explicit_routing(orchestrator, intent)
    if explicit_result:
        _emit_execution_receipt(intent, explicit_result)
        return explicit_result

    # 6. Code generation
    code_result = await _handle_code_generation(orchestrator, intent)
    if code_result:
        _emit_execution_receipt(intent, code_result)
        return code_result

    # 7. Reflex Layer & Heuristics
    reflex_result = await _handle_reflex_layer(orchestrator, intent)
    if reflex_result:
        _emit_execution_receipt(intent, reflex_result)
        return reflex_result

    # 8. Semantic Routing
    result = await _route_semantically(orchestrator, intent)

    # 9. Close Learning Loop (includes receipt emission)
    if state_before is not None and result is not None:
        _close_learning_loop(intent, result, state_before)
    # 9a. Emit receipt for non-learning executions
    elif result is not None:
        _emit_execution_receipt(intent, result)

    if result is None:
        return {
            "status": "error",
            "error": "No result generated",
            "correlation_id": str(uuid.uuid4()),
        }

    if isinstance(result, dict) and "correlation_id" not in result:
        correlation_id = None
        if isinstance(intent, dict):
            correlation_id = intent.get("correlation_id")
        result["correlation_id"] = correlation_id or str(uuid.uuid4())

    if isinstance(result, dict):
        err = result.get("error") or result.get("result", {}).get("error")
        if err == "verification_failed":
            result["status"] = "blocked"

    return result


async def _route_to_app(
    orchestrator: Any,
    intent: dict[str, Any],
    app_name: str,
) -> dict[str, Any]:
    """Route intent to app instance."""
    import uuid

    try:
        app_instance = orchestrator._get_or_create_app(app_name)

        from kagami.core.orchestrator.utils import _IntentEnvelope

        wrapped = _IntentEnvelope(
            action=intent.get("action"),
            app=app_name,
            metadata=intent.get("metadata", {}),
            target=intent.get("params"),
        )

        if hasattr(app_instance, "process_intent"):
            result = await app_instance.process_intent(wrapped)
        elif hasattr(app_instance, "process_intent_v2"):
            result = await app_instance.process_intent_v2(wrapped, {}, {})
        else:
            raise AttributeError(f"App {app_name} has no process_intent method")

        if isinstance(result, dict):
            if "status" not in result or result["status"] == "success":
                result["status"] = "accepted"
            if "correlation_id" not in result:
                result["correlation_id"] = str(uuid.uuid4())

        if isinstance(result, dict):
            return cast(dict[str, Any], result)
        # Normalize non-dict[str, Any] results into a standard envelope
        return {
            "status": "accepted",
            "result": result,
            "app": app_name,
            "correlation_id": str(uuid.uuid4()),
        }

    except Exception as e:
        logger.error(f"App execution failed for {app_name}: {e}")
        return {
            "status": "error",
            "error": str(e),
            "detail": str(e),
            "app": app_name,
            "correlation_id": str(uuid.uuid4()),
        }


async def _handle_arbitrary_intent(
    orchestrator: Any,
    intent: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    original_intent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Handle intents that don't match any known pattern."""
    # Support calling with different signatures for compatibility
    if metadata is None and original_intent is None:
        # Called with just orchestrator and intent
        pass

    action = intent.get("action", "unknown")
    target = str(intent.get("target", "")).lower()

    if action == "EXECUTE" and ("echo" in target or target in ["noop", "ping", "status"]):
        correlation_id = intent.get("correlation_id") or str(uuid.uuid4())
        return {
            "status": "accepted",
            "result": {
                "echo": target,
                "params": intent.get("params", {}),
                "message": f"Echo: {target}",
            },
            "correlation_id": correlation_id,
        }

    logger.warning(f"No handler found for intent: {action}")

    correlation_id = None
    if isinstance(intent, dict):
        correlation_id = intent.get("correlation_id")
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    return {
        "status": "error",
        "error": f"Unknown action: {action}",
        "detail": "No app or handler could process this intent",
        "action": action,
        "correlation_id": correlation_id,
    }
