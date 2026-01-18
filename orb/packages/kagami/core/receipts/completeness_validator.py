"""Receipt Completeness Validator.

Validates that operations emit complete PLAN→EXECUTE→VERIFY cycles.
Emits warnings and metrics for incomplete receipts.

Created: November 10, 2025
Purpose: Fix 47.2% incomplete receipt rate identified in organism analysis
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, cast

logger = logging.getLogger(__name__)


@dataclass
class ReceiptCycleStatus:
    """Status of a receipt cycle for a given correlation_id."""

    correlation_id: str
    has_plan: bool = False
    has_execute: bool = False
    has_verify: bool = False
    first_seen: float = 0.0
    last_seen: float = 0.0
    app: str | None = None
    action: str | None = None

    @property
    def is_complete(self) -> bool:
        """Check if cycle is complete (P→E→V)."""
        return self.has_plan and self.has_execute and self.has_verify

    @property
    def missing_phases(self) -> list[str]:
        """Get list[Any] of missing phases."""
        missing = []
        if not self.has_plan:
            missing.append("plan")
        if not self.has_execute:
            missing.append("execute")
        if not self.has_verify:
            missing.append("verify")
        return missing

    @property
    def completeness_percent(self) -> float:
        """Get completeness as percentage (0.0 - 1.0)."""
        count = sum([self.has_plan, self.has_execute, self.has_verify])
        return count / 3.0


class ReceiptCompletenessValidator:
    """Tracks receipt cycles and validates completeness.

    Usage:
        validator = get_completeness_validator()
        validator.track_receipt(receipt)

        # Later, check status:
        stats = validator.get_statistics()
        incomplete = validator.get_incomplete_operations()
    """

    # Correlation ID prefixes that are expected to have incomplete cycles
    # These are single-phase operations that don't follow P→E→V pattern
    SINGLE_PHASE_PREFIXES = frozenset(
        {
            "cbf_check",  # CBF safety checks - only emit VERIFY
            "phase_transition",  # Phase transitions - only emit EXECUTE
        }
    )

    def __init__(self, retention_seconds: int = 3600):
        """Initialize validator.

        Args:
            retention_seconds: How long to keep cycle status in memory
        """
        self._cycles: dict[str, ReceiptCycleStatus] = {}
        self._retention_seconds = retention_seconds
        self._last_cleanup = time.time()
        self._total_tracked = 0
        self._warnings_emitted = 0

    def _is_single_phase_operation(self, correlation_id: str) -> bool:
        """Check if correlation_id belongs to a single-phase operation.

        Single-phase operations don't follow the P→E→V pattern and should
        not trigger incomplete cycle warnings.

        Args:
            correlation_id: Correlation ID to check

        Returns:
            True if this is a known single-phase operation
        """
        for prefix in self.SINGLE_PHASE_PREFIXES:
            if correlation_id.startswith(prefix):
                return True
        return False

    def track_receipt(self, receipt: dict[str, Any]) -> None:
        """Track a receipt and update cycle status.

        Args:
            receipt: Receipt dict[str, Any] with correlation_id and phase
        """
        correlation_id = receipt.get("correlation_id")
        if not correlation_id:
            return

        phase = str(receipt.get("phase", "")).lower()
        if not phase or phase not in ("plan", "execute", "verify"):
            return

        # Skip single-phase operations from completeness tracking
        if self._is_single_phase_operation(correlation_id):
            return

        # Best-effort extraction for labeling/diagnostics.
        intent = receipt.get("intent") if isinstance(receipt.get("intent"), dict) else {}
        receipt_app = receipt.get("app") or (
            intent.get("app") if isinstance(intent, dict) else None
        )
        receipt_action = receipt.get("action") or (
            intent.get("action") if isinstance(intent, dict) else None
        )

        # Get or create cycle status
        if correlation_id not in self._cycles:
            self._cycles[correlation_id] = ReceiptCycleStatus(
                correlation_id=correlation_id,
                first_seen=time.time(),
                app=str(receipt_app).strip() if receipt_app is not None else None,
                action=str(receipt_action).strip() if receipt_action is not None else None,
            )
            self._total_tracked += 1

        status = self._cycles[correlation_id]
        status.last_seen = time.time()

        # Backfill app/action if first receipt lacked these fields.
        if status.app is None and receipt_app is not None:
            status.app = str(receipt_app).strip()
        if status.action is None and receipt_action is not None:
            status.action = str(receipt_action).strip()

        # Update phase flags
        if phase == "plan":
            status.has_plan = True
        elif phase == "execute":
            status.has_execute = True
        elif phase == "verify":
            status.has_verify = True

        # Emit metrics
        try:
            from kagami_observability.metrics import Counter

            # Track receipt phases
            receipts_by_phase = Counter(
                "kagami_receipts_by_phase_total",
                "Receipt count by phase",
                ["phase", "app"],
            )
            receipts_by_phase.labels(phase=phase, app=status.app or "unknown").inc()

            # Track completeness when VERIFY received
            if phase == "verify":
                if status.is_complete:
                    complete_cycles = Counter(
                        "kagami_complete_receipt_cycles_total",
                        "Complete P→E→V cycles",
                        ["app"],
                    )
                    complete_cycles.labels(app=status.app or "unknown").inc()
                else:
                    # Emit warning for incomplete cycle
                    self._emit_incompleteness_warning(status)

                    incomplete_cycles = Counter(
                        "kagami_incomplete_receipt_cycles_total",
                        "Incomplete receipt cycles",
                        ["app", "missing_phases"],
                    )
                    missing_str = ",".join(status.missing_phases)
                    incomplete_cycles.labels(
                        app=status.app or "unknown", missing_phases=missing_str
                    ).inc()

        except Exception as e:
            logger.debug(f"Failed to emit completeness metrics: {e}")

        # Periodic cleanup
        if time.time() - self._last_cleanup > 300:  # Every 5 minutes
            self._cleanup_old_cycles()

    # Actions that are exempt from P→E→V completeness checks
    # These are one-shot events that don't follow the standard cycle
    EXEMPT_ACTIONS = frozenset(
        {
            "startup.loaders",
            "boot.verified",
            "shutdown",
            "health_check",
            "metric_emission",
            "background_task",
        }
    )

    def _emit_incompleteness_warning(self, status: ReceiptCycleStatus) -> None:
        """Emit warning for incomplete receipt cycle.

        Args:
            status: Cycle status with missing phases
        """
        # Skip warning for exempt actions (startup, shutdown, etc.)
        if status.action and status.action in self.EXEMPT_ACTIONS:
            logger.debug(f"Skipping completeness check for exempt action: {status.action}")
            return

        missing = ", ".join(status.missing_phases)
        logger.warning(
            f"Incomplete receipt cycle [{status.correlation_id[:16]}]: "
            f"missing {missing} | app={status.app} action={status.action}"
        )
        self._warnings_emitted += 1

        # Emit error metric for incomplete cycles
        try:
            from kagami_observability.metrics.receipts import RECEIPT_WRITE_ERRORS_TOTAL

            RECEIPT_WRITE_ERRORS_TOTAL.labels(error_type="incomplete_cycle").inc()
        except Exception:
            pass

        # Emit detailed warning every 10th incomplete cycle
        if self._warnings_emitted % 10 == 0:
            stats = self.get_statistics()
            logger.warning(
                f"Receipt completeness alert: "
                f"{stats['incomplete_count']}/{stats['total_tracked']} cycles incomplete "
                f"({stats['completeness_rate']:.1%})"
            )

    def _cleanup_old_cycles(self) -> None:
        """Remove old cycle statuses from memory."""
        now = time.time()
        cutoff = now - self._retention_seconds

        old_cycles = [cid for cid, status in self._cycles.items() if status.last_seen < cutoff]

        for cid in old_cycles:
            del self._cycles[cid]

        self._last_cleanup = now

        if old_cycles:
            logger.debug(f"Cleaned up {len(old_cycles)} old receipt cycles")

    def get_statistics(self) -> dict[str, Any]:
        """Get completeness statistics.

        Returns:
            Statistics dict[str, Any] with counts and rates
        """
        complete_count = sum(1 for s in self._cycles.values() if s.is_complete)
        incomplete_count = len(self._cycles) - complete_count

        # Count by missing phase
        missing_plan = sum(1 for s in self._cycles.values() if not s.has_plan)
        missing_execute = sum(1 for s in self._cycles.values() if not s.has_execute)
        missing_verify = sum(1 for s in self._cycles.values() if not s.has_verify)

        return {
            "total_tracked": self._total_tracked,
            "current_cycles": len(self._cycles),
            "complete_count": complete_count,
            "incomplete_count": incomplete_count,
            "completeness_rate": complete_count / max(len(self._cycles), 1),
            "missing_phases": {
                "plan": missing_plan,
                "execute": missing_execute,
                "verify": missing_verify,
            },
            "warnings_emitted": self._warnings_emitted,
        }

    def get_incomplete_operations(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get list[Any] of incomplete operations.

        Args:
            limit: Maximum number to return

        Returns:
            List of incomplete operation summaries
        """
        incomplete = [
            {
                "correlation_id": s.correlation_id,
                "app": s.app,
                "action": s.action,
                "missing_phases": s.missing_phases,
                "completeness": s.completeness_percent,
                "age_seconds": time.time() - s.first_seen,
            }
            for s in self._cycles.values()
            if not s.is_complete
        ]

        # Sort by age (oldest first)
        incomplete.sort(key=lambda x: cast(float, x["age_seconds"]), reverse=True)

        return incomplete[:limit]

    def check_operation_complete(self, correlation_id: str) -> bool:
        """Check if a specific operation has complete receipt cycle.

        Args:
            correlation_id: Correlation ID to check

        Returns:
            True if complete, False if incomplete or not found
        """
        if correlation_id not in self._cycles:
            return False

        return self._cycles[correlation_id].is_complete


# Global singleton
_validator: ReceiptCompletenessValidator | None = None


def get_completeness_validator() -> ReceiptCompletenessValidator:
    """Get singleton completeness validator.

    Returns:
        ReceiptCompletenessValidator instance
    """
    global _validator
    if _validator is None:
        _validator = ReceiptCompletenessValidator()
    return _validator


def track_receipt_for_completeness(receipt: dict[str, Any]) -> None:
    """Track a receipt for completeness validation.

    This should be called for every emitted receipt.

    Args:
        receipt: Receipt dict[str, Any] with correlation_id and phase
    """
    try:
        validator = get_completeness_validator()
        validator.track_receipt(receipt)
    except Exception as e:
        logger.debug(f"Receipt completeness tracking failed: {e}")


__all__ = [
    "ReceiptCompletenessValidator",
    "ReceiptCycleStatus",
    "get_completeness_validator",
    "track_receipt_for_completeness",
]
