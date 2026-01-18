"""UnifiedReceiptFacade - Single entry point for receipt operations.

This module provides the canonical interface for emitting receipts,
used throughout the K OS codebase.

Created: December 7, 2025
Reason: Consolidation of receipt emission patterns
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ReceiptResult(dict[str, Any]):
    """A dict[str, Any]-like receipt that is also awaitable.

    Several parts of the codebase historically used `await URF.emit(...)` even though
    receipt emission is synchronous. Returning an awaitable dict[str, Any] preserves that
    contract without requiring invasive callsite refactors.
    """

    def __await__(self) -> None:
        async def _coro() -> Any:
            return self

        return _coro().__await__()  # type: ignore[return-value]


class UnifiedReceiptFacade:
    """Unified interface for receipt operations.

    Provides static methods for:
    - emit(): Emit a receipt with standard fields
    - generate_correlation_id(): Generate unique correlation ID

    Usage:
        from kagami.core.receipts import UnifiedReceiptFacade as URF

        correlation_id = URF.generate_correlation_id()
        URF.emit(
            correlation_id=correlation_id,
            event_name="intent.execute.plan",
            action="search",
            app="elysia",
            event_data={"query": "hello"},
        )
    """

    @staticmethod
    def generate_correlation_id(name: str | None = None, prefix: str | None = None) -> str:
        """Generate unique correlation ID.

        Args:
            name: Optional name to include in ID
            prefix: Optional prefix for ID

        Returns:
            Unique correlation ID string
        """
        from kagami.core.utils.ids import generate_correlation_id as _gen_id

        return _gen_id(name=name, prefix=prefix)

    @staticmethod
    def emit(  # type: ignore[no-untyped-def]
        correlation_id: str,
        event_name: str | None = None,
        action: str | None = None,
        app: str | None = None,
        event_data: dict[str, Any] | None = None,
        status: str = "success",
        phase: str | None = None,
        colony: str | None = None,
        args: dict[str, Any] | None = None,
        parent_receipt_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Emit a receipt with standard fields.

        Args:
            correlation_id: Unique ID for tracking
            event_name: Event name (e.g., "intent.execute.plan"). If None, generated from phase/action.
            action: Action being performed
            app: Application name
            event_data: Additional event data
            status: Status (success/error/warning)
            phase: Receipt phase (PLAN/EXECUTE/VERIFY)
            colony: Colony name (spark/forge/flow/etc.)
            args: Intent args
            parent_receipt_id: Parent receipt ID for phase/operation DAG
            **kwargs: Additional fields

        Raises:
            ValueError: If correlation_id is empty or None
        """
        # Validate correlation_id is present (critical for audit trail integrity)
        if not correlation_id or not isinstance(correlation_id, str) or not correlation_id.strip():
            raise ValueError(
                f"Invalid correlation_id (must be non-empty string): {correlation_id!r}"
            )

        # Generate event_name if not provided (backward compatibility fix)
        if event_name is None:
            if phase:
                event_name = f"intent.execute.{phase.lower()}"
            elif action:
                event_name = f"intent.{action}"
            else:
                event_name = "intent.event"

        from kagami.core.receipts.emitters import get_emitter_registry
        from kagami.core.receipts.ingestor import add_receipt

        # Use emitter registry to construct receipt (CC=3)
        registry = get_emitter_registry()
        receipt = registry.emit(
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
            **kwargs,
        )

        # Persist receipt (CC=1)
        receipt_obj = ReceiptResult(receipt)
        try:
            add_receipt(receipt_obj)
        except Exception as e:
            # Receipt emission should never crash the caller
            logger.debug(f"Receipt emission failed: {e}")
        return receipt_obj


# Convenience function for simpler usage
def emit_receipt(  # type: ignore[no-untyped-def]
    correlation_id: str,
    event_name: str,
    action: str | None = None,
    app: str | None = None,
    event_data: dict[str, Any] | None = None,
    status: str = "success",
    **kwargs,
) -> dict[str, Any]:
    """Convenience function for emitting receipts.

    Delegates to UnifiedReceiptFacade.emit().
    """
    return UnifiedReceiptFacade.emit(
        correlation_id=correlation_id,
        event_name=event_name,
        action=action,
        app=app,
        event_data=event_data,
        status=status,
        **kwargs,
    )


__all__ = [
    "UnifiedReceiptFacade",
    "emit_receipt",
]
