from __future__ import annotations

"""Embodied Cognition: Spatial awareness and sensorimotor prediction."""
import logging
from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SensoryPrediction:
    """Prediction of sensory consequences."""

    expected_artifact_type: str = ""
    expected_vertices_range: tuple[float, float] = (0, 0)
    expected_file_size_mb: tuple[float, float] = (0, 0)
    expected_duration_seconds: tuple[float, float] = (0, 0)


@dataclass
class SensoryObservation:
    """Actual sensory observation."""

    actual_artifact_type: str = ""
    actual_vertices: int = 0
    actual_file_size_mb: float = 0.0
    actual_duration_seconds: float = 0.0


@dataclass
class EfferenceCopy:
    """Motor command + sensory prediction."""

    motor_command: SensoryPrediction
    sensory_prediction: SensoryPrediction
    actual_sensory: SensoryObservation
    prediction_error: dict[str, float]


class EmbodiedCognitionLayer:
    """Spatial awareness and sensorimotor prediction."""

    def __init__(self) -> None:
        self._spatial_model: dict[str, Any] = {}
        self._efference_copies: deque[Any] = deque(maxlen=100)

    async def predict_sensory_consequence(self, action: dict[str, Any]) -> SensoryPrediction:
        """Before acting, predict what we'll sense."""
        action_type = action.get("action", "")
        app = action.get("app", "")

        # Forge character generation
        if app == "forge" and action_type == "generate":
            return SensoryPrediction(
                expected_artifact_type="3D_mesh",
                expected_vertices_range=(5000, 50000),
                expected_file_size_mb=(1, 10),
                expected_duration_seconds=(5, 30),
            )

        # File upload
        elif app == "files" and action_type == "upload":
            return SensoryPrediction(
                expected_artifact_type="file",
                expected_file_size_mb=(0.1, 100),
                expected_duration_seconds=(0.5, 5),
            )

        # Default
        return SensoryPrediction()

    async def sense_actual_consequence(
        self, action: dict[str, Any], result: dict[str, Any]
    ) -> SensoryObservation:
        """After acting, observe what actually happened."""
        artifact = result.get("artifact", {})

        return SensoryObservation(
            actual_artifact_type=artifact.get("type", ""),
            actual_vertices=artifact.get("vertices", 0),
            actual_file_size_mb=artifact.get("file_size_mb", 0),
            actual_duration_seconds=result.get("duration_ms", 0) / 1000,
        )

    async def update_spatial_model(
        self, prediction: SensoryPrediction, observation: SensoryObservation
    ) -> None:
        """Learn from prediction error to refine spatial understanding."""
        # Compute errors
        vertices_error = abs(
            (observation.actual_vertices or 0) - np.mean(prediction.expected_vertices_range)
        )

        duration_error = abs(
            observation.actual_duration_seconds - np.mean(prediction.expected_duration_seconds)
        )

        error = {
            "vertices_error": vertices_error,
            "duration_error": duration_error,
        }

        # Update internal spatial model
        await self._refine_spatial_predictions(error)  # type: ignore[arg-type]

        # Store efference copy
        self._efference_copies.append(
            EfferenceCopy(
                motor_command=prediction,
                sensory_prediction=prediction,
                actual_sensory=observation,
                prediction_error=error,  # type: ignore[arg-type]
            )
        )

        logger.debug(
            f"Embodied learning: vertices_error={vertices_error:.0f}, "
            f"duration_error={duration_error:.1f}s"
        )

    async def _refine_spatial_predictions(self, error: dict[str, float]) -> None:
        """Refine spatial prediction model."""
        # Would update model parameters - simplified

    def get_spatial_state(self) -> dict[str, Any]:
        """Get current spatial model state."""
        return {
            "model": dict(self._spatial_model),
            "efference_copies": len(self._efference_copies),
            "timestamp": __import__("time").time(),
        }
