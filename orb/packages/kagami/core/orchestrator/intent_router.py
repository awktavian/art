"""Intent Router - Deterministic rule-based intent routing.

This is the DETERMINISTIC router, complementing SemanticIntentRouter.
Extracted from orchestrator.py to improve maintainability.

ARCHITECTURE (Dec 15, 2025):
  KagamiOS uses TWO routers:
  1. SemanticIntentRouter (ML-based, semantic similarity)
  2. IntentRouter (this file - rule-based, deterministic)

  They are COMPLEMENTARY, not redundant. See ROUTER_ARCHITECTURE.md.

UNIQUE CAPABILITIES:
  - CBF safety checks BEFORE routing (fail-closed security)
  - Fast path optimization for read-only operations
  - App name normalization and alias handling
  - Deterministic action->app inference via app_registry
  - Returns structured RouteDecision dataclass

USED AS FALLBACK:
  When SemanticRouter returns handler_type="app" but app_name=None,
  process_intent_v2.py falls back to this router for deterministic inference.

Safety Integration (Dec 14, 2025):
- CBF safety checks before routing
- Prevents unsafe intent routing
- Correlation tracking for verification
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, cast

logger = logging.getLogger(__name__)


@dataclass
class RouteDecision:
    """Routing decision for an intent."""

    app_name: str | None
    handler_type: str  # "app", "chat", "sensorimotor", "arbitrary", "fast_path", "blocked"
    metadata: dict[str, Any]
    use_fast_path: bool = False


class IntentRouter:
    """Routes intents to appropriate handlers based on action patterns."""

    _operation_router: Any
    _agent_routing_graph: Any

    def __init__(self) -> None:
        """Initialize intent router."""
        self._operation_router = None
        self._agent_routing_graph = None

    def _normalize_app_name(self, name: str | None) -> str | None:
        """Normalize app name (handle aliases).

        Delegates to centralized utils._normalize_app_name.

        Args:
            name: App name to normalize

        Returns:
            Normalized app name
        """
        from kagami.core.orchestrator.utils import _normalize_app_name

        return _normalize_app_name(name)

    def _infer_app_from_action(self, action: str | None) -> str | None:
        """Infer app from action using registry configuration.

        Args:
            action: Action string

        Returns:
            App name or None
        """
        from kagami.core.unified_agents.app_registry import infer_app_from_action

        return cast(str | None, infer_app_from_action(action))  # type: ignore[redundant-cast]

    async def route(self, intent: dict[str, Any]) -> RouteDecision:
        """Route intent to appropriate handler.

        Args:
            intent: Intent dict[str, Any] with action, app, params, metadata

        Returns:
            RouteDecision with app name and handler type
        """
        # Generate correlation ID for traceability
        correlation_id = str(uuid.uuid4())

        action = intent.get("action") or intent.get("intent") or intent.get("command")
        action_str = str(action or "").strip()

        # CBF SAFETY CHECK - Block unsafe routing before processing
        try:
            from kagami.core.safety.cbf_integration import check_cbf_for_operation

            safety_result = await check_cbf_for_operation(
                operation="intent.route",
                action=action_str,
                target=intent.get("app"),
                params=intent.get("params", {}),
                metadata=intent.get("metadata", {}),
                source="intent_router",
                user_input=intent.get("query") or intent.get("message"),
            )

            if not safety_result.safe:
                logger.warning(
                    f"Intent routing blocked by CBF: action={action_str}, "
                    f"h(x)={safety_result.h_x:.3f}, reason={safety_result.reason}, "
                    f"correlation_id={correlation_id}"
                )
                return RouteDecision(
                    app_name=None,
                    handler_type="blocked",
                    metadata={
                        "blocked": True,
                        "h_x": safety_result.h_x,
                        "reason": safety_result.reason or "safety_barrier_violation",
                        "detail": safety_result.detail or "Intent routing blocked by safety checks",
                        "correlation_id": correlation_id,
                    },
                )

            logger.debug(
                f"Intent routing safety check passed: action={action_str}, "
                f"h(x)={safety_result.h_x:.3f}, correlation_id={correlation_id}"
            )

        except Exception as e:
            # Fail-safe: block on CBF check failure
            logger.error(f"CBF check failed in intent router: {e}, correlation_id={correlation_id}")
            return RouteDecision(
                app_name=None,
                handler_type="blocked",
                metadata={
                    "blocked": True,
                    "reason": "safety_check_failed",
                    "detail": f"Safety check error: {e!s}",
                    "correlation_id": correlation_id,
                },
            )

        # Check for chat intent
        if action == "chat.send" or intent.get("intent") == "chat.send":
            metadata = intent.get("metadata", {}).copy()
            metadata["correlation_id"] = correlation_id
            return RouteDecision(app_name=None, handler_type="chat", metadata=metadata)

        # Check for sensorimotor intent
        if action and (
            action_str.startswith("sensorimotor.")
            or action in ["perceive", "predict_action", "act", "observe_and_act"]
        ):
            metadata = intent.get("metadata", {}).copy()
            metadata["correlation_id"] = correlation_id
            return RouteDecision(app_name=None, handler_type="sensorimotor", metadata=metadata)

        app_name = None

        # Infer app name from intent
        if not app_name:
            app_name = self._normalize_app_name(intent.get("app")) or self._infer_app_from_action(
                action_str
            )

        # Check for fast path (operation router) - optional optimization
        use_fast_path = False
        if self._operation_router:
            try:
                from kagami.core.execution.operation_router import ExecutionPath

                path = self._operation_router.classify_operation(intent, threat_score=0.2)
                is_read_only = action_str and action_str.startswith(
                    ("get.", "list[Any].", "query.", "search.")
                )
                if path == ExecutionPath.FAST and is_read_only:
                    use_fast_path = True
            except Exception as e:
                logger.debug(f"Fast path classification unavailable: {e}")

        # Determine handler type
        if not app_name:
            handler_type = "arbitrary"
        elif use_fast_path:
            handler_type = "fast_path"
        else:
            handler_type = "app"

        # Add correlation_id to metadata for traceability
        metadata = intent.get("metadata", {}).copy()
        metadata["correlation_id"] = correlation_id

        return RouteDecision(
            app_name=app_name,
            handler_type=handler_type,
            metadata=metadata,
            use_fast_path=use_fast_path,
        )

    def set_operation_router(self, router: Any) -> None:
        """Set operation router for fast path classification.

        Args:
            router: OperationRouter instance
        """
        self._operation_router = router


def get_intent_router() -> IntentRouter:
    """Get singleton intent router."""
    global _intent_router
    if _intent_router is None:
        _intent_router = IntentRouter()
    return _intent_router


_intent_router: IntentRouter | None = None

__all__ = ["IntentRouter", "RouteDecision", "get_intent_router"]
