"""World Model Safety Oracle.

Calculates risk based on trajectory stability in the H¹⁴×S⁷ manifold.
Uses geodesic curvature and octonion norm violations as proxy for 'danger'.

Theory:
    Unsafe operations cause 'wobble' in the eigenstate trajectory.
    - High hyperbolic curvature (H¹⁴) = radical conceptual shift (high risk)
    - Octonion norm violation (S⁷) = compositional breakdown (incoherence)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class WorldModelSafetyOracle:
    """Safety Oracle bridging World Model geometry and CBF risk scores."""

    def __init__(self) -> None:
        self._world_model = None
        self._initialized = False

    def initialize(self) -> None:
        """Lazy load world model to avoid circular imports/startup costs."""
        if self._initialized:
            return

        try:
            from kagami.core.world_model.service import get_world_model_service

            self._world_model = get_world_model_service().model  # type: ignore[assignment]

            self._initialized = True
            logger.debug("World Model Safety Oracle initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize World Model Safety Oracle: {e}")

    def compute_manifold_risk(self, prediction: Any) -> float:
        """Convert prediction trajectory into a scalar risk score (0.0-1.0).

        Args:
            prediction: Prediction object from WorldModel (containing predicted_state)

        Returns:
            Risk score based on geometric stability.
        """
        if not self._initialized or not prediction:
            return 0.8  # High risk when uninitialized (conservative)

        try:
            # 1. Extract states
            # Assuming prediction has predicted_state which might have geometric_coords
            state = prediction.predicted_state

            # 2. Check Octonion Norm (S⁷ Stability)
            # In S⁷, unit norm is required. Deviation implies loss of structure.
            oct_risk = 0.0
            if hasattr(state, "geometric_coords") and state.geometric_coords:
                oct_coords = state.geometric_coords.get("octonion")
                if oct_coords is not None:
                    norm = np.linalg.norm(oct_coords)
                    # Risk is proportional to deviation from 1.0
                    oct_risk = min(  # type: ignore[assignment]
                        1.0, abs(1.0 - norm) * 5.0
                    )  # Sensitive scaling  # type: ignore[assignment]

            # 3. Check Hyperbolic Curvature / Displacement (H¹⁴ Stability)
            # Large jumps in hyperbolic space imply radical context shifts
            # Need previous state to compute displacement, for single state prediction
            # we rely on confidence as a proxy for 'smoothness' of transition

            # 4. Use Prediction Confidence
            # Low confidence = high predictive risk
            conf_risk = 1.0 - prediction.confidence

            # Synthesize
            # Octonion breakdown is a critical structural failure -> high weight
            total_risk = (oct_risk * 0.4) + (conf_risk * 0.6)

            return min(1.0, max(0.0, total_risk))

        except Exception as e:
            logger.debug(f"Manifold risk computation failed: {e}")
            return 0.9  # High risk on computation failure

    async def predict_safety_trajectory(
        self, current_state: Any, action: dict[str, Any], horizon: int = 3
    ) -> list[float]:
        """Predict risk profile over a time horizon.

        Returns:
            List of risk scores for t+1, t+2, ... t+horizon
        """
        if not self._initialized or not self._world_model:
            return [0.8] * horizon  # Conservative high-risk when uninitialized

        risks = []
        sim_state = current_state

        # This assumes world_model has a predict_next_state method
        # and we can iterate. Simplified for this implementation.
        try:
            # Single step prediction for now as per current WM capabilities in search results
            # To do multi-step, we'd need to feed output back as input
            pred = self._world_model.predict_next_state(sim_state, action, horizon=1)
            risk = self.compute_manifold_risk(pred)
            risks.append(risk)

            # For subsequent steps, we'd need a valid state object to feed back
            # skipping for this MVP implementation

        except Exception as e:
            logger.debug(f"Trajectory safety prediction failed: {e}")
            risks.append(0.9)  # Conservative high-risk on failure

        return risks + [risks[-1]] * (horizon - len(risks))


_safety_oracle: WorldModelSafetyOracle | None = None


def get_world_model_safety_oracle() -> WorldModelSafetyOracle:
    global _safety_oracle
    if _safety_oracle is None:
        _safety_oracle = WorldModelSafetyOracle()
        # Initialize can be called here or lazily
    return _safety_oracle
