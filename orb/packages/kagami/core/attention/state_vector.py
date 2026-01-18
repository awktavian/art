from __future__ import annotations

from typing import Any

"State Vector - Proprioceptive state for valued-attention.\n\nMaps manifold position + system metrics to a compact state vector s ∈ R^h\nthat captures current internal condition.\n\nDimensions (h=8):\n0. safety - from manifold (CBF h(x))\n1. novelty - from manifold (LZC)\n2. integration - from manifold (IC)\n3. prediction_error - from world model\n4. memory_pressure - from system (psutil)\n5. convergence_rate - from delta_j\n6. recent_success_rate - from receipts\n7. attention_entropy - from current attention\n"
import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)
H = 8


@dataclass
class StateVector:
    """Proprioceptive state vector for valued-attention.

    Represents current internal condition across 8 dimensions.
    Used to modulate attention preferences based on context.
    """

    vector: np.ndarray[Any, Any]
    _semantic_pointer: np.ndarray[Any, Any] | None = None

    @property
    def safety(self) -> float:
        return float(self.vector[0])

    @property
    def novelty(self) -> float:
        return float(self.vector[1])

    @property
    def integration(self) -> float:
        return float(self.vector[2])

    @property
    def prediction_error(self) -> float:
        return float(self.vector[3])

    @property
    def memory_pressure(self) -> float:
        return float(self.vector[4])

    @property
    def convergence_rate(self) -> float:
        return float(self.vector[5])

    @property
    def recent_success_rate(self) -> float:
        return float(self.vector[6])

    @property
    def attention_entropy(self) -> float:
        return float(self.vector[7])

    @property
    def semantic_pointer(self) -> np.ndarray[Any, Any] | None:
        """Optional semantic identity pointer (32D or similar)."""
        return self._semantic_pointer

    def distance_to_target(self, target: np.ndarray[Any, Any]) -> float:
        """Compute L2 distance to target state."""
        return float(np.linalg.norm(self.vector - target))

    def to_dict(self) -> dict[str, Any]:
        """Serialize for logging/debugging."""
        d = {
            "safety": self.safety,
            "novelty": self.novelty,
            "integration": self.integration,
            "prediction_error": self.prediction_error,
            "memory_pressure": self.memory_pressure,
            "convergence_rate": self.convergence_rate,
            "recent_success_rate": self.recent_success_rate,
            "attention_entropy": self.attention_entropy,
        }
        if self.semantic_pointer is not None:
            d["has_semantic_pointer"] = True
        return d


TARGET_STATE = np.array([0.8, 0.6, 0.6, 0.1, 0.5, 0.9, 0.8, 0.7], dtype=np.float32)


def manifold_to_state_vector(
    manifold_position: object | None = None,
    agent_context: object | None = None,
    world_model: object | None = None,
    semantic_pointer: list[float] | np.ndarray[Any, Any] | None = None,
) -> StateVector:
    """Convert manifold position + context to state vector.

    Args:
        manifold_position: Current position on manifold (safety, novelty, integration, time)
        agent_context: AgentOperationContext with convergence tracking
        world_model: WorldModel with prediction error history
        semantic_pointer: Optional semantic identity vector

    Returns:
        StateVector s ∈ R^8
    """
    s = np.zeros(H, dtype=np.float32)
    if manifold_position is not None:
        try:
            s[0] = float(getattr(manifold_position, "safety", 0.5))
            s[1] = float(getattr(manifold_position, "novelty", 0.5))
            s[2] = float(getattr(manifold_position, "integration", 0.5))
        except Exception:
            s[0] = 0.5
            s[1] = 0.5
            s[2] = 0.5
    else:
        try:
            from kagami.core.matryoshka_fiber_bundle import get_matryoshka_bundle

            mk = get_matryoshka_bundle()
            if mk.position_history:
                recent_positions = [
                    p
                    for positions in mk.position_history.values()
                    for p in positions[-1:]  # type: ignore[operator]
                ]
                if recent_positions:
                    nav = recent_positions[-1].navigation_7d
                    s[0] = abs(nav[0])
                    s[1] = float(np.mean(np.abs(nav[1:3])))
                    s[2] = float(np.mean(np.abs(nav[3:5])))
                else:
                    s[0] = 0.5
                    s[1] = 0.5
                    s[2] = 0.5
            else:
                s[0] = 0.5
                s[1] = 0.5
                s[2] = 0.5
        except Exception:
            s[0] = 0.5
            s[1] = 0.5
            s[2] = 0.5
    if world_model is not None:
        try:
            history = getattr(world_model, "prediction_errors", [])
            if history:
                s[3] = float(np.mean(history[-10:]))
            else:
                s[3] = 0.5
        except Exception:
            s[3] = 0.5
    else:
        s[3] = 0.5
    try:
        import psutil

        s[4] = psutil.virtual_memory().percent / 100.0
    except Exception:
        s[4] = 0.5
    if agent_context is not None:
        try:
            delta_j_history = getattr(agent_context, "delta_j_history", [])
            if len(delta_j_history) >= 2:
                last_delta = delta_j_history[-1]
                s[5] = 1.0 / (1.0 + last_delta)
            else:
                s[5] = 0.5
        except Exception:
            s[5] = 0.5
    else:
        s[5] = 0.5
    try:
        from kagami.core.receipts.service import get_unified_receipt_storage

        storage = get_unified_receipt_storage()
        # Use search instead of _iter_receipts
        receipts = storage.search(limit=20)
        if receipts:
            successes = sum(
                1
                for r in receipts
                if "success" in str(r.get("event", {}).get("name", "")).lower()
                or r.get("event", {}).get("data", {}).get("status") == "success"
            )
            s[6] = successes / len(receipts)
        else:
            s[6] = 0.5
    except Exception:
        s[6] = 0.5
    s[7] = 0.7

    sv = StateVector(vector=s)
    if semantic_pointer is not None:
        if isinstance(semantic_pointer, list):
            sv._semantic_pointer = np.array(semantic_pointer, dtype=np.float32)
        else:
            sv._semantic_pointer = semantic_pointer.astype(np.float32)

    return sv
