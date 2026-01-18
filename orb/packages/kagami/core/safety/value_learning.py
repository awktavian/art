from __future__ import annotations

"""Feedback request logic for value learning.

Simplified from full inverse RL - provides logic to determine
when human feedback should be requested.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ValueLearningSystem:
    """Determines when to request human feedback on decisions.

    HARDENED (Dec 22, 2025): Confidence derived from real feedback history.
    Core insight: Request feedback on low-confidence, novel, or high-stakes decisions.
    """

    def __init__(self) -> None:
        # Track feedback confidence over time
        self._feedback_count = 0
        # HARDENED: Initialize confidence from historical feedback data
        self._confidence = self._compute_initial_confidence()

    def _compute_initial_confidence(self) -> float:
        """Compute initial confidence from historical feedback data.

        HARDENED (Dec 22, 2025): Uses real receipt approval data.
        """
        try:
            from kagami.core.receipts.store import ReceiptStore  # type: ignore[attr-defined]

            store = ReceiptStore()
            recent_receipts = store.get_recent(limit=500)

            # Count approved/rejected receipts
            approved = sum(1 for r in recent_receipts if r.get("user_approved", r.get("approved")))
            total = len([r for r in recent_receipts if "user_approved" in r or "approved" in r])

            if total >= 10:
                # Enough data - use approval rate as confidence
                self._feedback_count = total
                return min(0.95, max(0.1, approved / total))
            else:
                # Insufficient data - use conservative default
                return 0.3
        except Exception:
            # If receipts unavailable, use conservative default
            return 0.3

    def should_request_feedback(self, action: dict[str, Any]) -> bool:
        """Decide if we should ask for human feedback on this action.

        ARCHITECTURE (December 22, 2025):
        NO keyword heuristics. Feedback decisions use structural metadata only.

        Request feedback when:
        - Low confidence in values (confidence < 0.5)
        - Explicit novelty flag in metadata
        - High stakes (risk > 0.7)

        This helps build value alignment through actual human feedback.
        """
        # Low confidence → request feedback
        if self._confidence < 0.5:
            return True

        # Novel action marked in metadata → request feedback
        # NO keyword guessing - use explicit metadata flag
        metadata = action.get("metadata", {})
        if metadata.get("novel") or metadata.get("requires_feedback"):
            return True

        # High stakes action → request feedback
        risk = action.get("risk", 0.0)
        if risk > 0.7:
            return True

        return False

    def record_feedback(self, approved: bool) -> None:
        """Record human feedback to update confidence.

        Args:
            approved: Whether human approved the action
        """
        self._feedback_count += 1

        # Increase confidence with more feedback
        import numpy as np

        self._confidence = min(0.95, 0.3 + 0.05 * np.log(self._feedback_count + 1))

        logger.debug(
            f"Recorded feedback (approved={approved}), new confidence={self._confidence:.2f}"
        )

    def get_confidence(self) -> float:
        """Get current value alignment confidence."""
        return self._confidence


# Global singleton
_value_learning: ValueLearningSystem | None = None


def get_value_learning() -> ValueLearningSystem:
    """Get or create global value learning system."""
    global _value_learning

    if _value_learning is None:
        _value_learning = ValueLearningSystem()

    return _value_learning
