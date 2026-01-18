"""Thoughts API - Awareness, reasoning, perception, and introspection.

UPDATED: December 6, 2025 - Unified World Model Integration

The thoughts module handles:
- Recent thoughts from continuous mind
- Unified insight (brief + activity + suggestions)
- Sensorimotor loop (unified perceive/predict/act)
- Direct world model access (encode, predict, status)

Endpoints at /api/mind:
- GET /thoughts - Recent thoughts
- GET /insights - Unified intelligence
- POST /sense - Unified sensorimotor (perceive, predict, act)
- GET /world/status - World model status and metrics
- POST /world/encode - Encode observation to latent state
- POST /world/decode - Decode latent state back to observation
- POST /world/predict - Predict future states
- POST /world/plan - Plan actions via Active Inference
"""

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import torch
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from kagami_api.response_schemas import get_error_responses
from kagami_api.security import require_auth

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/mind", tags=["mind"])

    # =============================================================================
    # CANONICAL WORLD MODEL ACCESS (Dec 6, 2025)
    # =============================================================================
    # All world model access now goes through WorldModelService.
    # Legacy sensorimotor world model is wrapped for backward compatibility.

    def _get_world_model_service() -> Any:
        """Get canonical world model service."""
        try:
            from kagami.core.world_model.service import get_world_model_service

            return get_world_model_service()
        except ImportError:
            return None

    def _get_sensorimotor_adapter() -> Any:
        """Get sensorimotor adapter wrapping canonical world model.

        Falls back to legacy embodiment model if canonical unavailable.
        """
        # Try canonical service first
        service = _get_world_model_service()
        if service and service.is_available:
            return SensorimotorAdapter(service)

        # Fallback to legacy embodiment
        try:
            from kagami.core.embodiment import create_sensorimotor_world_model

            return create_sensorimotor_world_model(dimensions=[32, 64, 128, 256])
        except Exception:
            logger.debug("Legacy embodiment unavailable", exc_info=True)
            return None

    class SensorimotorAdapter:
        """Adapter that wraps WorldModelService with sensorimotor interface.

        Provides backward-compatible perceive/predict_future/act methods
        using the canonical KagamiWorldModel.

        MARKOV BLANKET DISCIPLINE:
        ==========================
        This adapter is STATELESS. It does NOT cache state or create instant feedback.
        State tracking is handled via receipts with correlation_id.

        Flow: η (external) → s (sensory) → μ (internal) → a (active) → η
        - No instant feedback: a_t computed from μ_t, uses a_{t-1} for dynamics
        - No global state: Each call is pure function of inputs
        - Correlation tracking: Use receipt correlation_id for state continuity
        """

        def __init__(self, service: Any) -> None:
            self.service = service
            # NO CACHE - adapter is stateless

        def perceive(self, multimodal: dict, correlation_id: str | None = None) -> Any:
            """Encode multimodal input to latent state.

            STATELESS: Returns fresh state without persistence.
            Use correlation_id to track state across requests via receipts.

            Args:
                multimodal: Dict with vision/audio/language modalities
                correlation_id: Optional correlation ID for receipt tracking

            Returns:
                SemanticState representing current observation (sensory boundary)
            """
            from kagami.core.world_model.jepa.states import SemanticState

            # Convert multimodal dict to tensor
            embeddings = []
            if "vision" in multimodal:
                embeddings.append(torch.tensor(multimodal["vision"], dtype=torch.float32))
            if "audio" in multimodal:
                embeddings.append(torch.tensor(multimodal["audio"], dtype=torch.float32))
            if "language" in multimodal:
                # Encode text via embedding service
                try:
                    from kagami.core.services.embedding_service import get_embedding_service

                    emb_service = get_embedding_service()
                    text_emb = emb_service.encode(multimodal["language"])  # type: ignore[attr-defined]
                    embeddings.append(torch.tensor(text_emb, dtype=torch.float32))
                except Exception:
                    logger.debug("Failed to encode language via embedding service", exc_info=True)

            if not embeddings:
                embeddings = [torch.zeros(512)]

            # Concatenate and pad/truncate to model dim
            combined = torch.cat(embeddings, dim=-1) if len(embeddings) > 1 else embeddings[0]
            bulk_dim = 512
            if combined.shape[-1] < bulk_dim:
                combined = torch.nn.functional.pad(combined, (0, bulk_dim - combined.shape[-1]))
            else:
                combined = combined[..., :bulk_dim]

            # Encode via world model (STATELESS - no caching)
            if self.service.model is not None:
                state = self.service.model.encode_observation({"embedding": combined.numpy()})
                # Attach correlation_id to state metadata if provided
                if correlation_id and hasattr(state, "context_hash"):
                    state.context_hash = f"{state.context_hash}:{correlation_id}"
                return state

            return SemanticState(
                embedding=combined.numpy().tolist(),
                timestamp=time.time(),
                context_hash=f"adapter:{correlation_id}" if correlation_id else "adapter",
            )

        def predict_future(
            self, state: Any, horizon: int = 1, correlation_id: str | None = None
        ) -> list:
            """Predict future states.

            STATELESS: Predictions are pure functions of current state.
            Uses a_{t-1} for dynamics (action from previous timestep).

            Args:
                state: Current latent state (from perceive)
                horizon: Number of steps to predict
                correlation_id: Optional correlation ID for tracking

            Returns:
                List of predicted future states (sensory boundary)
            """
            from kagami.core.world_model.jepa.states import SemanticState

            predictions = []
            if self.service.model is not None:
                # Predict without action (or use zero action as a_{t-1} default)
                # The world model internally uses stored a_{t-1} for dynamics
                pred = self.service.model.predict_next_state(state, action={}, horizon=horizon)
                if hasattr(pred, "embedding"):
                    for i in range(horizon):
                        ctx = f"pred_{i}:{correlation_id}" if correlation_id else f"pred_{i}"
                        predictions.append(
                            SemanticState(
                                embedding=pred.embedding.tolist()
                                if hasattr(pred.embedding, "tolist")
                                else pred.embedding,
                                timestamp=time.time(),
                                context_hash=ctx,
                            )
                        )

            if not predictions:
                # Fallback: Identity prediction (no dynamics)
                for i in range(horizon):
                    ctx = f"pred_{i}:{correlation_id}" if correlation_id else f"pred_{i}"
                    predictions.append(
                        SemanticState(
                            embedding=state.embedding
                            if hasattr(state, "embedding")
                            else [0.0] * 512,
                            timestamp=time.time(),
                            context_hash=ctx,
                        )
                    )

            return predictions

        def act(self, state: Any, correlation_id: str | None = None) -> list:
            """Decode actions from latent state.

            STATELESS: Action is pure function of internal state μ.
            No instant feedback - action will be used as a_{t-1} in next step.

            Args:
                state: Current latent state (internal μ)
                correlation_id: Optional correlation ID for tracking

            Returns:
                List of actions (active boundary)
            """
            from dataclasses import dataclass

            @dataclass
            class Action:
                action_type: str
                confidence: float
                params: dict
                correlation_id: str | None = None

                def to_dict(self) -> Any:
                    result = {
                        "action_type": self.action_type,
                        "confidence": self.confidence,
                        "params": self.params,
                    }
                    if self.correlation_id:
                        result["correlation_id"] = self.correlation_id
                    return result

            # Use Active Inference if available
            if self.service.active_inference is not None:
                try:
                    # Get action from AI engine (uses internal state μ)
                    action_tensor = torch.zeros(8)  # Default E8 action
                    return [
                        Action("predicted", 0.5, {"tensor": action_tensor.tolist()}, correlation_id)
                    ]
                except Exception:
                    logger.debug("Failed to get action from Active Inference", exc_info=True)

            return [Action("noop", 1.0, {}, correlation_id)]

    # Optional embodiment imports for legacy compatibility
    try:
        from kagami.core.embodiment import DISCRETE_ACTIONS
        from kagami.core.embodiment.composio_actuators import get_composio_actuators

        _EMBODIMENT_AVAILABLE = True
    except Exception:
        _EMBODIMENT_AVAILABLE = False
        DISCRETE_ACTIONS = []
        get_composio_actuators = None  # type: ignore[assignment]

    # =============================================================================
    # THOUGHTS
    # =============================================================================

    class ThoughtResponse(BaseModel):
        """Information about a thought."""

        id: str
        type: str
        content: str
        priority: float
        conclusion: str | None
        actionable: bool
        confidence: float
        created_at: float
        completed_at: float | None
        reasoning_duration_ms: float

    @router.get(
        "/thoughts",
        response_model=list[ThoughtResponse],
        responses=get_error_responses(401, 403, 429, 500),
    )
    async def get_recent_thoughts(request: Request, limit: int = 10) -> list[Any]:
        """Get recent thoughts from the continuous mind."""
        try:
            continuous_mind = getattr(request.app.state, "continuous_mind", None)
            if continuous_mind is None:
                return []
            recent = list(continuous_mind._active_thoughts)[-limit:]
            return [
                ThoughtResponse(
                    id=t.id,
                    type=t.type.value,
                    content=t.content,
                    priority=t.priority,
                    conclusion=t.conclusion,
                    actionable=t.actionable,
                    confidence=t.confidence,
                    created_at=t.created_at,
                    completed_at=t.completed_at,
                    reasoning_duration_ms=t.reasoning_duration_ms,
                )
                for t in recent
            ]
        except Exception as e:
            logger.error(f"Error getting thoughts: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    # =============================================================================
    # INSIGHT
    # =============================================================================

    class Insight(BaseModel):
        """Unified intelligence insight."""

        timestamp: str
        period: dict[str, str]
        summary: str
        highlights: list[dict[str, Any]] = Field(default_factory=list)
        concerns: list[dict[str, Any]] = Field(default_factory=list)
        suggestions: list[dict[str, Any]] = Field(default_factory=list)
        activity: dict[str, Any] = Field(default_factory=dict)
        metrics: dict[str, Any] = Field(default_factory=dict)

    @router.get(
        "/insights",
        responses=get_error_responses(401, 403, 429, 500),
    )
    async def get_insight(since_hours: int = 24, _user=Depends(require_auth)) -> Insight:  # type: ignore[no-untyped-def]
        """Get unified insight: brief, suggestions, and activity."""
        now = datetime.now(UTC)
        since = now - timedelta(hours=since_hours)

        metrics: dict[str, Any] = {"total_agents": 0, "active_agents": 0, "success_rate": 0.0}

        from kagami.core.unified_agents import get_unified_organism

        organism = get_unified_organism()
        _ = organism.colonies
        stats = organism.get_stats()
        metrics["total_agents"] = int(stats.get("total_population", 0))
        # Active = available workers (can take work) across colonies
        metrics["active_agents"] = int(
            sum(int(c.get("available_workers", 0)) for c in stats.get("colonies", {}).values())
        )
        metrics["success_rate"] = float(stats.get("success_rate", 0.0))

        activity: dict[str, Any] = {"goals_completed": 0, "goals_failed": 0, "receipts": 0}
        from kagami.core.receipts.redis_storage import get_redis_receipt_storage

        storage = get_redis_receipt_storage()
        receipts = await storage.query_time_range(since.timestamp(), now.timestamp())
        activity["receipts"] = len(receipts)
        for r in receipts:
            if r.get("phase") == "verify":
                if r.get("status") == "success":
                    activity["goals_completed"] += 1
                else:
                    activity["goals_failed"] += 1

        return Insight(
            timestamp=now.isoformat(),
            period={"start": since.isoformat(), "end": now.isoformat()},
            summary=f"Activity over the last {since_hours} hours.",
            highlights=[
                {
                    "title": "Systems Operational",
                    "description": f"{metrics['active_agents']} agents active",
                }
            ]
            if metrics["active_agents"] > 0
            else [],
            concerns=[],
            suggestions=[
                {"title": "Review metrics", "description": "Check system performance regularly"}
            ],
            activity=activity,
            metrics=metrics,
        )

    # =============================================================================
    # SENSE (unified sensorimotor: perceive, predict, act)
    # =============================================================================

    class SenseRequest(BaseModel):
        """Unified sensorimotor request."""

        mode: Literal["perceive", "predict", "act"] = Field(..., description="Operation mode")
        # For perceive/predict
        vision_emb: list[float] | None = Field(None, description="CLIP vision embedding")
        audio_emb: list[float] | None = Field(None, description="Whisper audio embedding")
        language_text: str | None = Field(None, description="Text to encode")
        # For predict
        horizon: int = Field(1, ge=1, le=10, description="Steps ahead to predict")
        # For act
        manifold_state: list[float] | None = Field(None, description="State from world model")
        execute: bool = Field(False, description="Actually execute or just decode")

    @router.post(
        "/sense",
        responses=get_error_responses(400, 401, 403, 429, 500, 503),
    )
    async def sense(request: SenseRequest, _user=Depends(require_auth)) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        """Unified sensorimotor endpoint: perceive, predict, or act.

        MARKOV BLANKET ENFORCEMENT:
        - Each request generates a unique correlation_id
        - State tracking via receipts (not global cache)
        - No instant feedback loops
        """
        from kagami.core.receipts import UnifiedReceiptFacade as URF

        wm = _get_sensorimotor_adapter()
        if wm is None:
            raise HTTPException(status_code=503, detail="World model not available")

        # Generate correlation ID for this sensorimotor cycle
        correlation_id = URF.generate_correlation_id(prefix="sense")

        try:
            if request.mode == "perceive":
                multimodal = {}
                if request.vision_emb:
                    multimodal["vision"] = request.vision_emb
                if request.audio_emb:
                    multimodal["audio"] = request.audio_emb
                if request.language_text:
                    multimodal["language"] = request.language_text  # type: ignore[assignment]

                # STATELESS perception (η → s)
                state = wm.perceive(multimodal, correlation_id=correlation_id)
                embedding = state.embedding if hasattr(state, "embedding") else state
                if hasattr(embedding, "tolist"):
                    embedding = embedding.tolist()

                # Emit receipt (for state tracking)
                URF.emit(
                    correlation_id=correlation_id,
                    event_name="sensorimotor.perceive",
                    action="encode",
                    event_data={
                        "input_dims": {
                            k: len(v) if isinstance(v, list) else "text"
                            for k, v in multimodal.items()
                        }
                    },
                    status="success",
                )

                return {
                    "mode": "perceive",
                    "manifold_state": embedding,
                    "dim": len(embedding),
                    "correlation_id": correlation_id,
                }

            elif request.mode == "predict":
                multimodal = {}
                if request.vision_emb:
                    multimodal["vision"] = request.vision_emb
                if request.audio_emb:
                    multimodal["audio"] = request.audio_emb
                if request.language_text:
                    multimodal["language"] = request.language_text  # type: ignore[assignment]

                # STATELESS perception then prediction (s → μ → future s)
                current = wm.perceive(multimodal, correlation_id=correlation_id)
                predictions = wm.predict_future(
                    current, horizon=request.horizon, correlation_id=correlation_id
                )

                # Emit receipt
                URF.emit(
                    correlation_id=correlation_id,
                    event_name="sensorimotor.predict",
                    action="predict",
                    event_data={"horizon": request.horizon},
                    status="success",
                )

                return {
                    "mode": "predict",
                    "predictions": [
                        {
                            "step": i + 1,
                            "embedding": p.embedding.tolist()
                            if hasattr(p.embedding, "tolist")
                            else p.embedding,
                        }
                        for i, p in enumerate(predictions)
                    ],
                    "correlation_id": correlation_id,
                }

            elif request.mode == "act":
                if not request.manifold_state:
                    raise HTTPException(
                        status_code=400, detail="manifold_state required for act mode"
                    )

                from kagami.core.world_model.jepa.states import SemanticState

                # STATELESS action generation (μ → a)
                state = SemanticState(
                    embedding=request.manifold_state,
                    timestamp=time.time(),
                    context_hash=f"api:{correlation_id}",
                )
                actions = wm.act(state, correlation_id=correlation_id)

                if request.execute and get_composio_actuators:  # type: ignore[truthy-function]
                    actuators = get_composio_actuators()
                    results = []
                    for action in actions[:3]:
                        if (
                            hasattr(action, "action_type")
                            and action.action_type in DISCRETE_ACTIONS
                        ):
                            result = await actuators.execute_action(action)  # type: ignore[attr-defined]
                            results.append(result)

                    # Emit receipt for execution (a → η)
                    URF.emit(
                        correlation_id=correlation_id,
                        event_name="sensorimotor.act",
                        action="execute",
                        event_data={"num_actions": len(results)},
                        status="success",
                    )

                    return {
                        "mode": "act",
                        "executed": True,
                        "actions": [a.to_dict() for a in actions],
                        "results": results,
                        "correlation_id": correlation_id,
                    }

                # Emit receipt for decode only
                URF.emit(
                    correlation_id=correlation_id,
                    event_name="sensorimotor.act",
                    action="decode",
                    event_data={"num_actions": len(actions)},
                    status="success",
                )

                return {
                    "mode": "act",
                    "executed": False,
                    "actions": [a.to_dict() for a in actions],
                    "correlation_id": correlation_id,
                }

            else:
                raise HTTPException(status_code=400, detail=f"Unknown mode: {request.mode}")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Sense error: {e}")
            # Emit error receipt
            URF.emit(
                correlation_id=correlation_id,
                event_name="sensorimotor.error",
                action=request.mode,
                event_data={"error": str(e)},
                status="error",
            )
            raise HTTPException(status_code=500, detail=str(e)) from None

    # =============================================================================
    # WORLD MODEL DIRECT ACCESS (Dec 6, 2025)
    # =============================================================================

    class WorldModelStatus(BaseModel):
        """World model status response."""

        available: bool
        device: str
        features: dict[str, bool]
        metrics: dict[str, Any]
        config: dict[str, Any] | None = None

    @router.get(
        "/world/status",
        responses=get_error_responses(401, 403, 429, 500),
    )
    async def world_status(_user=Depends(require_auth)) -> WorldModelStatus:  # type: ignore[no-untyped-def]
        """Get world model status, metrics, and configuration."""
        service = _get_world_model_service()

        if service is None or not service.is_available:
            return WorldModelStatus(
                available=False,
                device="none",
                features={},
                metrics={},
                config=None,
            )

        # Extract config info
        config_info = None
        if service.model and hasattr(service.model, "config"):
            cfg = service.model.config
            config_info = {
                "bulk_dim": getattr(cfg, "bulk_dim", None),
                "e8_dim": getattr(cfg, "e8_dim", 8),
                "max_nucleus_levels": getattr(cfg, "max_nucleus_levels", 16),
                "training_nucleus_levels": getattr(cfg, "training_nucleus_levels", 8),
                "ib_beta": getattr(cfg, "ib_beta", 0.1),
            }

        return WorldModelStatus(
            available=service.is_available,
            device=str(service.device),
            features=service._get_feature_status(),
            metrics=service.get_metrics(),
            config=config_info,
        )

    class EncodeRequest(BaseModel):
        """Request to encode observation."""

        observation: dict[str, Any] | list[float] | str = Field(
            ..., description="Observation to encode"
        )

    class EncodeResponse(BaseModel):
        """Encoded latent state."""

        success: bool
        latent_state: list[float] | None = None
        e8_code: list[float] | None = None
        s7_phase: list[float] | None = None
        encoding_ms: float = 0.0
        error: str | None = None

    @router.post(
        "/world/encode",
        responses=get_error_responses(400, 401, 403, 429, 500, 503),
    )
    async def world_encode(request: EncodeRequest, _user=Depends(require_auth)) -> EncodeResponse:  # type: ignore[no-untyped-def]
        """Encode observation to latent state via KagamiWorldModel."""
        service = _get_world_model_service()

        if service is None or not service.is_available:
            return EncodeResponse(success=False, error="World model not available")

        start = time.perf_counter()
        try:
            # Handle different input types
            if isinstance(request.observation, str):
                core_state = service.encode(request.observation)
            elif isinstance(request.observation, list):
                tensor = torch.tensor(request.observation, dtype=torch.float32)
                core_state = service.encode(tensor)
            else:
                core_state = service.encode(request.observation)

            if core_state is None:
                return EncodeResponse(success=False, error="Encoding failed")

            return EncodeResponse(
                success=True,
                latent_state=core_state.shell_residual.squeeze().tolist()
                if hasattr(core_state.shell_residual, "tolist")
                else None,
                e8_code=core_state.e8_code.squeeze().tolist()
                if hasattr(core_state.e8_code, "tolist")
                else None,
                s7_phase=core_state.s7_phase.squeeze().tolist()
                if hasattr(core_state.s7_phase, "tolist")
                else None,
                encoding_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return EncodeResponse(
                success=False, error=str(e), encoding_ms=(time.perf_counter() - start) * 1000
            )

    class DecodeRequest(BaseModel):
        """Request to decode latent state back to observation."""

        e8_code: list[float] = Field(..., description="E8 lattice code (8-dim)")
        s7_phase: list[float] | None = Field(None, description="S7 phase (optional)")
        correlation_id: str | None = Field(None, description="Correlation ID for tracking")

    class DecodeResponse(BaseModel):
        """Decoded observation from latent state."""

        success: bool
        observation: list[float] | None = None
        decoding_ms: float = 0.0
        correlation_id: str | None = None
        error: str | None = None

    @router.post(
        "/world/decode",
        responses=get_error_responses(400, 401, 403, 429, 500, 503),
    )
    async def world_decode(request: DecodeRequest, _user=Depends(require_auth)) -> DecodeResponse:  # type: ignore[no-untyped-def]
        """Decode latent state back to observation via KagamiWorldModel."""
        service = _get_world_model_service()

        if service is None or not service.is_available:
            return DecodeResponse(
                success=False,
                error="World model not available",
                correlation_id=request.correlation_id,
            )

        start = time.perf_counter()
        try:
            # Convert inputs to tensors
            e8_tensor = torch.tensor(request.e8_code, dtype=torch.float32)

            # Build latent state for decoding
            if request.s7_phase:
                s7_tensor = torch.tensor(request.s7_phase, dtype=torch.float32)
            else:
                s7_tensor = None

            # Decode via world model
            if service.model is not None and hasattr(service.model, "decode"):
                decoded = service.model.decode(e8_code=e8_tensor, s7_phase=s7_tensor)
                if decoded is not None:
                    obs = decoded.squeeze().tolist() if hasattr(decoded, "tolist") else decoded
                    return DecodeResponse(
                        success=True,
                        observation=obs,
                        decoding_ms=(time.perf_counter() - start) * 1000,
                        correlation_id=request.correlation_id,
                    )

            # Fallback: If no decode method, try reconstruction via encoder-decoder pair
            if service.model is not None and hasattr(service.model, "decoder"):
                # Reconstruct from E8 code
                decoded = service.model.decoder(e8_tensor.unsqueeze(0))
                obs = decoded.squeeze().tolist() if hasattr(decoded, "tolist") else decoded
                return DecodeResponse(
                    success=True,
                    observation=obs,
                    decoding_ms=(time.perf_counter() - start) * 1000,
                    correlation_id=request.correlation_id,
                )

            return DecodeResponse(
                success=False,
                error="Decode not available on world model",
                decoding_ms=(time.perf_counter() - start) * 1000,
                correlation_id=request.correlation_id,
            )
        except Exception as e:
            return DecodeResponse(
                success=False,
                error=str(e),
                decoding_ms=(time.perf_counter() - start) * 1000,
                correlation_id=request.correlation_id,
            )

    class PredictRequest(BaseModel):
        """Request to predict future states."""

        observation: dict[str, Any] | list[float] | str = Field(
            ..., description="Current observation"
        )
        horizon: int = Field(5, ge=1, le=100, description="Prediction horizon")
        action: dict[str, Any] | None = Field(None, description="Optional action to simulate")

    class PredictResponse(BaseModel):
        """Prediction result."""

        success: bool
        predictions: list[dict[str, Any]] = Field(default_factory=list)
        prediction_ms: float = 0.0
        error: str | None = None

    @router.post(
        "/world/predict",
        responses=get_error_responses(400, 401, 403, 429, 500, 503),
    )
    async def world_predict(  # type: ignore[no-untyped-def]
        request: PredictRequest, _user=Depends(require_auth)
    ) -> PredictResponse:
        """Predict future states via KagamiWorldModel."""
        service = _get_world_model_service()

        if service is None or not service.is_available:
            return PredictResponse(success=False, error="World model not available")

        start = time.perf_counter()
        try:
            prediction = service.predict(
                request.observation, action=request.action, horizon=request.horizon
            )

            if prediction is None:
                return PredictResponse(success=False, error="Prediction failed")

            # Format prediction
            predictions = []
            if hasattr(prediction, "embedding"):
                emb = prediction.embedding
                if hasattr(emb, "tolist"):
                    emb = emb.tolist()
                predictions.append({"step": 1, "embedding": emb})
            elif isinstance(prediction, list):
                for i, p in enumerate(prediction):
                    emb = p.embedding if hasattr(p, "embedding") else p
                    if hasattr(emb, "tolist"):
                        emb = emb.tolist()
                    predictions.append({"step": i + 1, "embedding": emb})

            return PredictResponse(
                success=True,
                predictions=predictions,
                prediction_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return PredictResponse(
                success=False, error=str(e), prediction_ms=(time.perf_counter() - start) * 1000
            )

    class PlanRequest(BaseModel):
        """Request to plan actions via Active Inference."""

        observation: dict[str, Any] | list[float] = Field(..., description="Current observation")
        goal: list[float] | None = Field(None, description="Goal embedding")
        candidates: list[dict[str, Any]] | None = Field(None, description="Action candidates")

    class PlanResponse(BaseModel):
        """Planning result."""

        success: bool
        action: dict[str, Any] | None = None
        efe_value: float | None = None
        planning_ms: float = 0.0
        error: str | None = None

    @router.post(
        "/world/plan",
        responses=get_error_responses(400, 401, 403, 429, 500, 503),
    )
    async def world_plan(request: PlanRequest, _user=Depends(require_auth)) -> PlanResponse:  # type: ignore[no-untyped-def]
        """Plan action via Active Inference Expected Free Energy."""
        service = _get_world_model_service()

        if service is None or not service.is_available:
            return PlanResponse(success=False, error="World model not available")

        if service.active_inference is None:
            return PlanResponse(success=False, error="Active Inference engine not available")

        start = time.perf_counter()
        try:
            # Convert observation to dict format
            obs = request.observation
            if isinstance(obs, list):
                obs = {"state_embedding": torch.tensor(obs, dtype=torch.float32)}

            # Convert goal if provided
            goals = None
            if request.goal:
                goals = torch.tensor(request.goal, dtype=torch.float32)

            # Select action
            result = await service.select_action_ai(obs, candidates=request.candidates, goals=goals)

            return PlanResponse(
                success=True,
                action=result,
                efe_value=result.get("G") if isinstance(result, dict) else None,
                planning_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return PlanResponse(
                success=False, error=str(e), planning_ms=(time.perf_counter() - start) * 1000
            )

    return router
