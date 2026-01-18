"""Receipt Emitters - Type-specific receipt construction.

This module extracts receipt emission logic by type to reduce cyclomatic complexity.
Each emitter handles a specific concern (success, error, metrics, etc.).

Created: December 14, 2025
Reason: TRAIL-010 - Reduce UnifiedReceiptFacade.emit CC from 63 to <10
"""

from __future__ import annotations

import time
from typing import Any, Protocol


class ReceiptEmitter(Protocol):
    """Protocol for receipt emitters."""

    def emit(self, base_receipt: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Emit receipt with type-specific fields.

        Args:
            base_receipt: Base receipt with core fields
            **kwargs: Type-specific fields

        Returns:
            Receipt dict[str, Any] with added fields
        """
        ...


class CoreEmitter:
    """Emits core receipt structure (intent, event, correlation_id)."""

    def _build_intent(
        self,
        action: str | None,
        app: str | None,
        args: dict[str, Any] | None,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """Build intent structure (CC=3)."""
        intent: dict[str, Any] = {"action": action or ""}

        # Add app if present
        if app:
            intent["app"] = app

        # Merge args
        intent_args: dict[str, Any] = {}
        if isinstance(args, dict):
            intent_args.update(args)
        legacy_args = kwargs.pop("args", None)
        if isinstance(legacy_args, dict):
            intent_args.update(legacy_args)
        if intent_args:
            intent["args"] = intent_args

        return intent

    def _build_event(self, event_name: str, event_data: dict[str, Any] | None) -> dict[str, Any]:
        """Build event structure (CC=1)."""
        event: dict[str, Any] = {"name": event_name}
        if event_data is not None:
            event["data"] = event_data
        return event

    def _add_optional_fields(
        self,
        receipt: dict[str, Any],
        app: str | None,
        action: str | None,
        intent_args: dict[str, Any],
        phase: str | None,
        event_data: dict[str, Any] | None,
        colony: str | None,
    ) -> None:
        """Add optional top-level fields (CC=4)."""
        # Top-level aliases (using dict[str, Any] update to avoid multiple ifs)
        optional: dict[str, Any] = {}
        if app is not None:
            optional["app"] = app
        if action is not None:
            optional["action"] = action
        if intent_args:
            optional["args"] = intent_args
        receipt.update(optional)

        # Phase (prefer explicit phase over event_data.phase)
        if phase:
            receipt["phase"] = phase
        elif isinstance(event_data, dict) and event_data.get("phase") is not None:
            receipt["phase"] = event_data.get("phase")

        # Colony
        if colony:
            receipt["colony"] = colony

    def emit(
        self,
        correlation_id: str,
        event_name: str,
        action: str | None = None,
        app: str | None = None,
        event_data: dict[str, Any] | None = None,
        status: str = "success",
        phase: str | None = None,
        colony: str | None = None,
        args: dict[str, Any] | None = None,
        parent_receipt_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Emit core receipt structure (CC=1).

        Args:
            correlation_id: Unique ID for tracking
            event_name: Event name (e.g., "intent.execute.plan")
            action: Action being performed
            app: Application name
            event_data: Additional event data
            status: Status (success/error/warning)
            phase: Receipt phase (PLAN/EXECUTE/VERIFY)
            colony: Colony name (spark/forge/flow/etc.)
            args: Intent args
            parent_receipt_id: Parent receipt ID for phase/operation DAG
            **kwargs: Legacy kwargs

        Returns:
            Core receipt structure
        """
        # Build structures using helper methods
        intent = self._build_intent(action, app, args, kwargs)
        event = self._build_event(event_name, event_data)

        # Core receipt
        receipt: dict[str, Any] = {
            "correlation_id": correlation_id,
            "intent": intent,
            "event": event,
            "event_name": event_name,
            "event_data": event_data,
            "ts": int(time.time() * 1000),
            "status": status,
        }

        # Add parent receipt ID if provided
        if parent_receipt_id is not None:
            receipt["parent_receipt_id"] = parent_receipt_id

        # Add optional fields
        intent_args = intent.get("args", {})
        self._add_optional_fields(receipt, app, action, intent_args, phase, event_data, colony)

        return receipt


class MetricsEmitter:
    """Emits observability and performance metrics."""

    def emit(self, receipt: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Add metrics fields to receipt.

        Args:
            receipt: Base receipt
            **kwargs: Metrics fields (duration_ms, metrics, prediction, etc.)

        Returns:
            Receipt with metrics fields
        """
        # Duration
        duration_ms = kwargs.pop("duration_ms", None)
        if duration_ms is not None:
            try:
                receipt["duration_ms"] = int(duration_ms)
            except Exception:
                receipt["duration_ms"] = duration_ms

        # Metrics dict[str, Any]
        metrics = kwargs.pop("metrics", None)
        if metrics is not None:
            receipt["metrics"] = metrics

        # Prediction metrics
        prediction = kwargs.pop("prediction", None)
        if prediction is not None:
            receipt["prediction"] = prediction

        prediction_error_ms = kwargs.pop("prediction_error_ms", None)
        if prediction_error_ms is not None:
            receipt["prediction_error_ms"] = prediction_error_ms

        # Valence (emotional state)
        valence = kwargs.pop("valence", None)
        if valence is not None:
            receipt["valence"] = valence

        # Learning metadata
        learning = kwargs.pop("learning", None)
        if learning is not None:
            receipt["learning"] = learning

        return receipt


class SafetyEmitter:
    """Emits safety and guardrails metadata."""

    def emit(self, receipt: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Add safety fields to receipt.

        Args:
            receipt: Base receipt
            **kwargs: Safety fields (guardrails, quality_gates, verifier)

        Returns:
            Receipt with safety fields
        """
        guardrails = kwargs.pop("guardrails", None)
        if guardrails is not None:
            receipt["guardrails"] = guardrails

        quality_gates = kwargs.pop("quality_gates", None)
        if quality_gates is not None:
            receipt["quality_gates"] = quality_gates

        verifier = kwargs.pop("verifier", None)
        if verifier is not None:
            receipt["verifier"] = verifier

        return receipt


class ContextEmitter:
    """Emits context and environment metadata."""

    def emit(self, receipt: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Add context fields to receipt.

        Args:
            receipt: Base receipt
            **kwargs: Context fields (workspace_hash, self_pointer, loop_depth, etc.)

        Returns:
            Receipt with context fields
        """
        workspace_hash = kwargs.pop("workspace_hash", None)
        if workspace_hash is not None:
            receipt["workspace_hash"] = workspace_hash

        self_pointer = kwargs.pop("self_pointer", None)
        if self_pointer is not None:
            receipt["self_pointer"] = self_pointer

        loop_depth = kwargs.pop("loop_depth", None)
        if loop_depth is not None:
            receipt["loop_depth"] = loop_depth

        tool_calls = kwargs.pop("tool_calls", None)
        if tool_calls is not None:
            receipt["tool_calls"] = tool_calls

        content_id = kwargs.pop("content_id", None)
        if content_id is not None:
            receipt["content_id"] = content_id

        operation_type = kwargs.pop("operation_type", None)
        if operation_type is not None:
            receipt["operation_type"] = operation_type

        timestamp = kwargs.pop("timestamp", None)
        if timestamp is not None:
            receipt["timestamp"] = timestamp

        return receipt


class IdentityEmitter:
    """Emits identity and multi-tenancy metadata."""

    def emit(self, receipt: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Add identity fields to receipt.

        Args:
            receipt: Base receipt
            **kwargs: Identity fields (user_id, tenant_id, actor)

        Returns:
            Receipt with identity fields
        """
        actor = kwargs.pop("actor", None)
        if actor is not None and not receipt.get("actor"):
            receipt["actor"] = actor

        user_id = kwargs.pop("user_id", None)
        if user_id is not None:
            receipt["user_id"] = user_id

        tenant_id = kwargs.pop("tenant_id", None)
        if tenant_id is not None:
            receipt["tenant_id"] = tenant_id

        return receipt


class EmitterRegistry:
    """Registry of receipt emitters.

    Manages the emission pipeline: Core → Metrics → Safety → Context → Identity
    """

    def __init__(self) -> None:
        """Initialize emitter registry."""
        self.core_emitter = CoreEmitter()
        self.metrics_emitter = MetricsEmitter()
        self.safety_emitter = SafetyEmitter()
        self.context_emitter = ContextEmitter()
        self.identity_emitter = IdentityEmitter()

    def emit(
        self,
        correlation_id: str,
        event_name: str,
        action: str | None = None,
        app: str | None = None,
        event_data: dict[str, Any] | None = None,
        status: str = "success",
        phase: str | None = None,
        colony: str | None = None,
        args: dict[str, Any] | None = None,
        parent_receipt_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Emit receipt through full pipeline.

        Args:
            correlation_id: Unique ID for tracking
            event_name: Event name
            action: Action being performed
            app: Application name
            event_data: Additional event data
            status: Status (success/error/warning)
            phase: Receipt phase (PLAN/EXECUTE/VERIFY)
            colony: Colony name
            args: Intent args
            parent_receipt_id: Parent receipt ID for phase/operation DAG
            **kwargs: Additional fields

        Returns:
            Fully constructed receipt
        """
        # Handle legacy "data" parameter
        if event_data is None:
            legacy_event_data = kwargs.pop("data", None)
            if isinstance(legacy_event_data, dict):
                event_data = legacy_event_data

        # Core structure (CC=1)
        receipt = self.core_emitter.emit(
            correlation_id=correlation_id,
            event_name=event_name,
            action=action,
            app=app,
            event_data=event_data,
            status=status,
            phase=phase,
            colony=colony,
            args=args,
            parent_receipt_id=parent_receipt_id,
            **kwargs,  # Pass remaining kwargs for legacy args handling
        )

        # Add type-specific fields (CC=1 each)
        receipt = self.metrics_emitter.emit(receipt, **kwargs)
        receipt = self.safety_emitter.emit(receipt, **kwargs)
        receipt = self.context_emitter.emit(receipt, **kwargs)
        receipt = self.identity_emitter.emit(receipt, **kwargs)

        # Any remaining kwargs become intent args (back-compat)
        if kwargs:
            if "args" not in receipt:
                receipt["args"] = {}
            if not isinstance(receipt["args"], dict):
                receipt["args"] = {}
            receipt["args"].update(kwargs)

        return receipt


# Global registry instance
_registry = EmitterRegistry()


def get_emitter_registry() -> EmitterRegistry:
    """Get global emitter registry.

    Returns:
        Global EmitterRegistry instance
    """
    return _registry
