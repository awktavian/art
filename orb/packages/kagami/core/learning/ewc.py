from __future__ import annotations

from typing import Any

"""Elastic Weight Consolidation (EWC) helper.

Prevents catastrophic forgetting by penalizing changes to important weights.
This is a lightweight, optional module: if unavailable, training proceeds
without EWC. When present, it adds a small regularization term.
"""
import logging

import numpy as np

logger = logging.getLogger(__name__)


class EWC:
    """Minimal EWC penalty manager.

    Tracks approximate importance via a simple moving average heuristic.
    This is not a full Fisher computation, but provides stabilizing regularization.
    """

    def __init__(self, lambda_ewc: float = 0.05) -> None:
        self.lambda_ewc = float(lambda_ewc)
        # State-hash keyed importance estimates (proxy for Fisher)
        self._importance: dict[str, float] = {}
        # Snapshot of optimal logits per state (target to preserve)
        self._optimal_logits: dict[str, np.ndarray[Any, Any]] = {}

    def consolidate_state(self, state_hash: str, logits: np.ndarray[Any, Any]) -> None:
        """Record current weights as optimal for this state.

        Called periodically (e.g., after good performance episodes).
        """
        try:
            self._optimal_logits[state_hash] = logits.copy()
            # Increase importance for consolidated states
            self._importance[state_hash] = self._importance.get(state_hash, 0.0) * 0.9 + 0.1
        except Exception:
            logger.error("Failed to consolidate EWC state for %s", state_hash, exc_info=True)

    def compute_penalty_for_state(
        self, state_hash: str, logits: np.ndarray[Any, Any]
    ) -> np.ndarray[Any, Any]:
        """Compute EWC penalty gradient term for this state.

        Penalty ≈ λ * I(s) * (logits - optimal_logits)
        Returns a vector shaped like logits to subtract from gradient.
        """
        try:
            if state_hash not in self._optimal_logits:
                return np.zeros_like(logits)
            importance = self._importance.get(state_hash, 0.0)
            delta = logits - self._optimal_logits[state_hash]
            return self.lambda_ewc * importance * delta  # External lib
        except Exception:
            logger.error("Failed to compute EWC penalty for %s", state_hash, exc_info=True)
            return np.zeros_like(logits)


# Global singleton
_ewc: EWC | None = None


def get_ewc() -> EWC:
    """Get or create global EWC manager."""
    global _ewc
    if _ewc is None:
        _ewc = EWC()
    return _ewc
