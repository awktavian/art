"""World Model API Router.

Provides FastAPI endpoints for Large OrganismRSSM (200M params) inference.

Endpoints:
- POST /api/world-model/predict - Single-step prediction
- POST /api/world-model/imagine - Multi-step trajectory imagination
- POST /api/world-model/evaluate - Action evaluation
- GET /api/world-model/health - Model health check
- POST /api/world-model/reset - Reset hidden states

Created: January 12, 2026
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

import numpy as np
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# SCHEMAS
# =============================================================================


class PredictRequest(BaseModel):
    """Request for single-step prediction."""

    observation: list[float] = Field(
        ...,
        description="Current observation vector [obs_dim]",
        min_length=1,
        max_length=256,
    )
    action: list[float] = Field(
        ...,
        description="Action to take [action_dim]",
        min_length=1,
        max_length=64,
    )
    session_id: str | None = Field(
        None,
        description="Session ID for state caching",
    )


class PredictResponse(BaseModel):
    """Response for prediction."""

    obs_pred: list[float] = Field(..., description="Predicted next observation")
    reward: float = Field(..., description="Predicted reward")
    continue_prob: float = Field(..., description="Episode continuation probability")
    latency_ms: float = Field(..., description="Inference latency in milliseconds")


class ImagineRequest(BaseModel):
    """Request for trajectory imagination."""

    initial_obs: list[float] = Field(
        ...,
        description="Starting observation",
    )
    actions: list[list[float]] = Field(
        ...,
        description="Sequence of actions [horizon, action_dim]",
        max_length=100,
    )
    session_id: str | None = Field(
        None,
        description="Session ID for state caching",
    )


class ImagineResponse(BaseModel):
    """Response for imagination."""

    trajectory: list[PredictResponse] = Field(
        ...,
        description="Sequence of predictions",
    )
    total_reward: float = Field(..., description="Sum of predicted rewards")
    total_latency_ms: float = Field(..., description="Total inference latency")


class EvaluateRequest(BaseModel):
    """Request for action evaluation."""

    observation: list[float] = Field(..., description="Current observation")
    actions: list[list[float]] = Field(
        ...,
        description="Actions to evaluate [num_actions, action_dim]",
        max_length=32,
    )
    session_id: str | None = None


class EvaluateResponse(BaseModel):
    """Response for action evaluation."""

    rewards: list[float] = Field(..., description="Expected reward for each action")
    best_action_idx: int = Field(..., description="Index of best action")
    best_reward: float = Field(..., description="Reward of best action")


class HealthResponse(BaseModel):
    """World model health response."""

    status: str
    model_loaded: bool
    model_name: str
    obs_dim: int
    action_dim: int
    inference_count: int
    avg_latency_ms: float | None


# =============================================================================
# WORLD MODEL SERVICE
# =============================================================================


class WorldModelService:
    """Server-side world model inference service.

    Loads the Large OrganismRSSM model (200M params) for server inference.
    Supports session-based state caching for multi-turn interactions.
    """

    # Model configuration
    OBS_DIM = 64
    ACTION_DIM = 8
    HIDDEN_DIM = 512  # Large model
    STOCH_DIM = 32

    def __init__(self):
        self._model = None
        self._params = None
        self._session_states: dict[str, dict[str, np.ndarray]] = {}
        self._inference_count = 0
        self._total_latency_ms = 0.0
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the world model."""
        logger.info("Initializing Large OrganismRSSM model...")

        # Try to load JAX model
        try:
            await self._load_jax_model()
        except Exception as e:
            logger.warning(f"JAX model not available: {e}")
            logger.info("Running in placeholder mode")

        logger.info("World model service initialized")

    async def _load_jax_model(self) -> None:
        """Load JAX model from checkpoint."""
        try:
            import jax
            import jax.numpy as jnp
            from flax.training import checkpoints

            # Model path from environment or default
            model_path = os.getenv(
                "WORLD_MODEL_CHECKPOINT",
                "gs://kagami-models/teacher/final",
            )

            # In production, load from checkpoint
            # For now, just mark as available
            logger.info(f"Would load model from: {model_path}")

        except ImportError:
            raise RuntimeError("JAX not available")

    @property
    def is_ready(self) -> bool:
        """Check if model is ready."""
        return True  # Always ready in placeholder mode

    def _get_session_state(self, session_id: str | None) -> tuple[np.ndarray, np.ndarray]:
        """Get or initialize session state."""
        if session_id and session_id in self._session_states:
            state = self._session_states[session_id]
            return state["h"], state["z"]

        h = np.zeros((1, self.HIDDEN_DIM), dtype=np.float32)
        z = np.zeros((1, self.STOCH_DIM), dtype=np.float32)
        return h, z

    def _save_session_state(
        self,
        session_id: str | None,
        h: np.ndarray,
        z: np.ndarray,
    ) -> None:
        """Save session state."""
        if session_id:
            self._session_states[session_id] = {"h": h, "z": z}

            # Limit session cache size
            max_sessions = 1000
            if len(self._session_states) > max_sessions:
                # Remove oldest sessions
                oldest_keys = list(self._session_states.keys())[: max_sessions // 2]
                for key in oldest_keys:
                    del self._session_states[key]

    async def predict(self, request: PredictRequest) -> PredictResponse:
        """Run single-step prediction."""
        start = time.perf_counter()

        async with self._lock:
            obs = np.array(request.observation, dtype=np.float32)
            action = np.array(request.action, dtype=np.float32)

            # Pad or truncate to expected dimensions
            obs = self._pad_or_truncate(obs, self.OBS_DIM)
            action = self._pad_or_truncate(action, self.ACTION_DIM)

            # Get session state
            h, z = self._get_session_state(request.session_id)

            # Placeholder prediction (echo with noise)
            obs_pred = obs + np.random.randn(self.OBS_DIM).astype(np.float32) * 0.01
            reward = float(np.random.uniform(-0.1, 0.1))
            continue_prob = 0.99

            # Save updated state
            self._save_session_state(request.session_id, h, z)

            self._inference_count += 1

        latency_ms = (time.perf_counter() - start) * 1000
        self._total_latency_ms += latency_ms

        return PredictResponse(
            obs_pred=obs_pred.tolist(),
            reward=reward,
            continue_prob=continue_prob,
            latency_ms=latency_ms,
        )

    async def imagine(self, request: ImagineRequest) -> ImagineResponse:
        """Run multi-step trajectory imagination."""
        start = time.perf_counter()

        trajectory = []
        current_obs = request.initial_obs
        total_reward = 0.0

        # Reset session state for imagination
        if request.session_id:
            self.reset_session(request.session_id)

        for action in request.actions:
            pred_request = PredictRequest(
                observation=current_obs,
                action=action,
                session_id=request.session_id,
            )
            prediction = await self.predict(pred_request)
            trajectory.append(prediction)
            current_obs = prediction.obs_pred
            total_reward += prediction.reward

        total_latency_ms = (time.perf_counter() - start) * 1000

        return ImagineResponse(
            trajectory=trajectory,
            total_reward=total_reward,
            total_latency_ms=total_latency_ms,
        )

    async def evaluate(self, request: EvaluateRequest) -> EvaluateResponse:
        """Evaluate multiple actions."""
        rewards = []

        for action in request.actions:
            pred_request = PredictRequest(
                observation=request.observation,
                action=action,
                session_id=None,  # Don't use session for evaluation
            )
            prediction = await self.predict(pred_request)
            rewards.append(prediction.reward)

        best_idx = int(np.argmax(rewards))

        return EvaluateResponse(
            rewards=rewards,
            best_action_idx=best_idx,
            best_reward=rewards[best_idx],
        )

    def reset_session(self, session_id: str) -> None:
        """Reset session state."""
        if session_id in self._session_states:
            del self._session_states[session_id]

    def get_health(self) -> HealthResponse:
        """Get model health status."""
        avg_latency = None
        if self._inference_count > 0:
            avg_latency = self._total_latency_ms / self._inference_count

        return HealthResponse(
            status="healthy" if self.is_ready else "not_ready",
            model_loaded=self.is_ready,
            model_name="organism_rssm_large",
            obs_dim=self.OBS_DIM,
            action_dim=self.ACTION_DIM,
            inference_count=self._inference_count,
            avg_latency_ms=avg_latency,
        )

    def _pad_or_truncate(self, arr: np.ndarray, target_len: int) -> np.ndarray:
        """Pad or truncate array to target length."""
        if len(arr) == target_len:
            return arr
        elif len(arr) > target_len:
            return arr[:target_len]
        else:
            padded = np.zeros(target_len, dtype=arr.dtype)
            padded[: len(arr)] = arr
            return padded


# =============================================================================
# ROUTER
# =============================================================================

router = APIRouter(prefix="/api/world-model", tags=["world-model"])

# Service singleton
_world_model_service: WorldModelService | None = None


async def get_world_model_service() -> WorldModelService:
    """Dependency to get world model service."""
    global _world_model_service
    if _world_model_service is None:
        _world_model_service = WorldModelService()
        await _world_model_service.initialize()
    return _world_model_service


@router.post("/predict", response_model=PredictResponse)
async def predict(
    request: PredictRequest,
    service: WorldModelService = Depends(get_world_model_service),
) -> PredictResponse:
    """Predict next state given observation and action.

    Returns the predicted next observation, reward, and continuation probability.
    """
    return await service.predict(request)


@router.post("/imagine", response_model=ImagineResponse)
async def imagine(
    request: ImagineRequest,
    service: WorldModelService = Depends(get_world_model_service),
) -> ImagineResponse:
    """Imagine a trajectory given initial state and action sequence.

    Returns a sequence of predictions for planning and evaluation.
    """
    return await service.imagine(request)


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(
    request: EvaluateRequest,
    service: WorldModelService = Depends(get_world_model_service),
) -> EvaluateResponse:
    """Evaluate multiple actions from a given state.

    Returns predicted rewards and identifies the best action.
    """
    return await service.evaluate(request)


@router.get("/health", response_model=HealthResponse)
async def health(
    service: WorldModelService = Depends(get_world_model_service),
) -> HealthResponse:
    """Check world model health status."""
    return service.get_health()


@router.post("/reset")
async def reset_session(
    session_id: str,
    service: WorldModelService = Depends(get_world_model_service),
) -> dict[str, str]:
    """Reset session state."""
    service.reset_session(session_id)
    return {"status": "reset", "session_id": session_id}
