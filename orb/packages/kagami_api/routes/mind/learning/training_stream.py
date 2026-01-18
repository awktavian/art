"""Training Metrics Stream - Learning progress monitoring.

Real-time streaming of training metrics to the Learning gallery.

Endpoints:
- WebSocket /stream - Training progress stream (CBF-validated, authenticated)
- GET /state - Current training state (CBF-validated)
- GET /safety-status - CBF safety metrics
- POST /control - Start/stop/reset training

CBF Safety:
All training state updates are validated against h(x) >= 0.
Unsafe states are blocked with 403 Forbidden responses.

Authentication:
- Query param: ?api_key=sk_... or ?token=...
- First-frame auth: {"type": "auth", "api_key": "...", "token": "..."}
- Auth timeout: 5 seconds

Created: November 30, 2025
Updated: December 15, 2025 - Added CBF safety validation
Updated: December 24, 2025 - Added proper authentication (Socket.IO migration)
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Literal

import numpy as np
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from kagami.core.safety.chaos_safety import ChaosSafetyMonitor, ChaosSafetyResult
from kagami.observability.metrics import chaos as chaos_metrics
from pydantic import BaseModel, Field

from kagami_api.services.training_stream import (
    TrainingStreamBroadcaster,
    TrainingStreamStorage,
    mark_training_active,
    mark_training_complete,
    reset_training_session,
)

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/mind/learning", tags=["mind", "learning"])

    _storage = TrainingStreamStorage()
    _broadcaster = TrainingStreamBroadcaster()
    _safety_monitor = ChaosSafetyMonitor()

    class ControlRequest(BaseModel):
        """Training control request."""

        action: Literal["start", "stop", "reset"] = Field(..., description="Control action")
        run_id: str | None = Field(None, description="Optional run ID for start")

    class SafetyStatusResponse(BaseModel):
        """CBF safety status response."""

        safe: bool = Field(..., description="Whether system is in safe state (h(x) >= 0)")
        cbf_value: float | None = Field(None, description="Current CBF value")
        intervention_needed: bool = Field(
            False, description="Whether safety intervention is needed"
        )
        distance_from_boundary: float | None = Field(
            None, description="Distance from safety boundary"
        )
        total_interventions: int = Field(0, description="Total safety interventions")
        violations_prevented: int = Field(0, description="Total violations prevented")
        timestamp: str = Field(..., description="Timestamp of safety check")

    def _extract_state_vector(state: dict[str, Any]) -> np.ndarray:
        """Extract numerical state vector from training state for CBF evaluation.

        CBF validation requires a numerical state vector. We extract loss values,
        gradient statistics, and system metrics as the state representation.

        Args:
            state: Training state dictionary

        Returns:
            State vector as numpy array
        """
        features = []

        # Extract loss values (primary safety indicators)
        losses = state.get("losses", {})
        for key in ["total", "distill", "contrastive", "vq", "ema", "loop_closure", "recognition"]:
            features.append(losses.get(key, 0.0))

        # Extract gradient statistics (stability indicators)
        gradients = state.get("gradients", {})
        for key in ["p1", "p50", "p99"]:
            features.append(gradients.get(key, 0.0))

        # Extract loop metrics (coherence indicators)
        loop = state.get("loop", {})
        features.append(loop.get("strength", 0.0))
        features.append(loop.get("closure", 0.0))

        # Extract system metrics if available
        system = state.get("system", {})
        features.append(system.get("memory", 0.0))

        return np.array(features, dtype=np.float32)

    def _default_training_cbf(state_vector: np.ndarray) -> float:
        """Default CBF for training state validation.

        Safety constraint: h(x) = -||x||_∞ + threshold

        This ensures no individual metric exceeds threshold (prevents divergence).

        Args:
            state_vector: Extracted state vector

        Returns:
            CBF value (h(x) >= 0 is safe)
        """
        # Threshold for maximum safe metric value
        SAFE_THRESHOLD = 100.0

        # h(x) = threshold - max(|x_i|)
        # Safe if all values are below threshold
        max_value = float(np.max(np.abs(state_vector)))
        h_x = SAFE_THRESHOLD - max_value

        return h_x

    def _validate_training_state(state: dict[str, Any]) -> ChaosSafetyResult:
        """Validate training state against CBF safety constraints.

        Args:
            state: Training state dictionary

        Returns:
            Safety check result
        """
        try:
            # Extract state vector
            state_vector = _extract_state_vector(state)

            # Check safety using monitor
            result = _safety_monitor.check_chaos_safety(
                state_vector,
                cbf_function=_default_training_cbf,
            )

            # Emit metrics
            if not result.safe:
                chaos_metrics.CHAOS_SAFETY_INTERVENTIONS_TOTAL.labels(  # type: ignore[attr-defined]
                    reason="training_state_violation"
                ).inc()
                logger.warning(
                    f"Training state CBF violation: h(x)={result.cbf_value}, "
                    f"state_norm={np.linalg.norm(state_vector):.2f}"
                )

            return result

        except Exception as e:
            logger.error(f"Training state validation failed: {e}")
            # Fail-safe: assume unsafe on error
            return ChaosSafetyResult(
                safe=False,
                intervention_needed=True,
                error=str(e),
            )

    @router.websocket("/stream")
    async def training_stream(websocket: WebSocket) -> None:
        """Stream real-time training metrics with CBF safety validation.

        Authentication:
        - Query param: ?api_key=sk_... or ?token=...
        - First-frame auth: {"type": "auth", "api_key": "...", "token": "..."}

        Protocol:
        1. Client connects with auth (query param or first message)
        2. Server validates authentication (5s timeout)
        3. Server sends initial state with history (CBF-validated)
        4. Server streams metrics as training progresses (each update validated)
        5. Client can request refresh with {"type": "request_state"}
        6. If state violates h(x) >= 0, error message sent instead

        Safety:
        - All state updates validated against CBF before sending
        - Unsafe states result in error message with safety details
        - Metrics emitted for all safety violations
        """
        from kagami_api.security import SecurityFramework
        from kagami_api.security.websocket import (
            WS_AUTH_TIMEOUT_SECONDS,
            WS_CLOSE_UNAUTHORIZED,
            authenticate_ws,
            emit_auth_metrics,
        )

        # Check for auth in query params first
        api_key = websocket.query_params.get("api_key", "")
        token = websocket.query_params.get("token", "")
        auth_info = None

        if api_key and SecurityFramework.validate_api_key(api_key):
            auth_info = {"user_id": "api_key_user", "roles": ["api_user"], "tenant_id": None}
        elif token:
            try:
                principal = SecurityFramework.verify_token(token)
                auth_info = {
                    "user_id": principal.sub,
                    "roles": principal.roles,
                    "tenant_id": principal.tenant_id,
                }
            except Exception:
                logger.debug("Failed to verify token during websocket auth", exc_info=True)

        # Accept connection first (required for first-frame auth)
        await websocket.accept()

        # If no query param auth, try first-frame auth
        if not auth_info:
            try:
                # Wait for auth message with timeout
                auth_msg = await asyncio.wait_for(
                    websocket.receive_json(), timeout=WS_AUTH_TIMEOUT_SECONDS
                )
                auth_info = await authenticate_ws(auth_msg)
            except TimeoutError:
                logger.warning(f"Training stream auth timeout: {websocket.client}")
                emit_auth_metrics(success=False, reason="timeout")
                await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Authentication timeout")
                return
            except Exception as e:
                logger.warning(f"Training stream auth error: {e}")
                emit_auth_metrics(success=False, reason="invalid_message")
                await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Invalid auth message")
                return

        if not auth_info:
            logger.warning(f"Training stream auth failed: {websocket.client}")
            emit_auth_metrics(success=False, reason="invalid_credentials")
            await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Authentication failed")
            return

        emit_auth_metrics(success=True)
        await _broadcaster.add_client(websocket)
        logger.info(
            f"Training stream authenticated: {websocket.client} (user={auth_info.get('user_id')})"
        )

        try:
            state = _storage.get_state()
            history = _storage.get_history()

            # Validate initial state
            safety_result = _validate_training_state(state)

            if not safety_result.safe:
                # Send safety violation error
                await websocket.send_json(
                    {
                        "type": "safety_violation",
                        "timestamp": datetime.utcnow().isoformat(),
                        "error": "Training state violates CBF safety constraint",
                        "cbf_value": safety_result.cbf_value,
                        "safe": False,
                        "intervention_needed": safety_result.intervention_needed,
                    }
                )
                logger.error("Initial training state unsafe, blocking stream")
                return

            # Add safety metadata to initial state
            state["safety_check"] = {
                "safe": True,
                "cbf_value": safety_result.cbf_value,
                "timestamp": datetime.utcnow().isoformat(),
            }

            await _broadcaster.broadcast_initial_state(websocket, state, history)  # type: ignore[arg-type]

            poll_interval = 0.5
            last_step = state.get("step", 0)

            while True:
                try:
                    message = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=poll_interval,
                    )

                    if message.get("type") == "request_state":
                        state = _storage.get_state()

                        # Validate requested state
                        safety_result = _validate_training_state(state)

                        if not safety_result.safe:
                            await websocket.send_json(
                                {
                                    "type": "safety_violation",
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "error": "Training state violates CBF safety constraint",
                                    "cbf_value": safety_result.cbf_value,
                                    "safe": False,
                                }
                            )
                            continue

                        # Add safety metadata
                        state["safety_check"] = {
                            "safe": True,
                            "cbf_value": safety_result.cbf_value,
                            "timestamp": datetime.utcnow().isoformat(),
                        }

                        await websocket.send_json(
                            {
                                "type": "state_snapshot",
                                "timestamp": datetime.utcnow().isoformat(),
                                **state,
                            }
                        )

                except TimeoutError:
                    state = _storage.get_state()
                    current_step = state.get("step", 0)

                    if current_step != last_step or state.get("active"):
                        # Validate state before sending
                        safety_result = _validate_training_state(state)

                        if not safety_result.safe:
                            # Send safety violation instead of update
                            await websocket.send_json(
                                {
                                    "type": "safety_violation",
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "step": current_step,
                                    "error": "Training state violates CBF safety constraint",
                                    "cbf_value": safety_result.cbf_value,
                                    "safe": False,
                                }
                            )
                            # Emit metric
                            chaos_metrics.CHAOS_SAFETY_INTERVENTIONS_TOTAL.labels(  # type: ignore[attr-defined]
                                reason="training_stream_block"
                            ).inc()
                        else:
                            # Add safety metadata
                            state["safety_check"] = {
                                "safe": True,
                                "cbf_value": safety_result.cbf_value,
                                "timestamp": datetime.utcnow().isoformat(),
                            }

                            await websocket.send_json(
                                {
                                    "type": "training_update",
                                    "timestamp": datetime.utcnow().isoformat(),
                                    **state,
                                }
                            )

                        last_step = current_step
                    else:
                        await websocket.send_json(
                            {
                                "type": "heartbeat",
                                "timestamp": datetime.utcnow().isoformat(),
                                "active": state.get("active", False),
                            }
                        )

        except WebSocketDisconnect:
            logger.info(f"Training stream disconnected: {websocket.client}")
        except Exception as e:
            logger.warning(f"Training stream error: {e}")
        finally:
            await _broadcaster.remove_client(websocket)

    @router.get("/state")
    async def get_training_state() -> dict[str, Any]:
        """Get current training state with history and CBF safety validation.

        Returns:
            Training state with safety_check metadata

        Raises:
            HTTPException: 403 if state violates CBF safety constraint
        """
        state = _storage.get_state()
        history = _storage.get_history()

        # Validate state against CBF
        safety_result = _validate_training_state(state)

        if not safety_result.safe:
            # Block unsafe state access with 403
            chaos_metrics.CHAOS_SAFETY_INTERVENTIONS_TOTAL.labels(  # type: ignore[attr-defined]
                reason="training_state_block"
            ).inc()

            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Training state violates CBF safety constraint",
                    "safe": False,
                    "cbf_value": safety_result.cbf_value,
                    "intervention_needed": safety_result.intervention_needed,
                    "distance_from_boundary": safety_result.distance_from_boundary,
                },
            )

        # Add safety metadata to response
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "history": history,
            "safety_check": {
                "safe": True,
                "cbf_value": safety_result.cbf_value,
                "distance_from_boundary": safety_result.distance_from_boundary,
                "timestamp": datetime.utcnow().isoformat(),
            },
            **state,
        }

    @router.post("/control")
    async def control_training(req: ControlRequest) -> dict[str, Any]:
        """Control training session (start/stop/reset)."""
        timestamp = datetime.utcnow().isoformat()

        if req.action == "start":
            run_id = mark_training_active(req.run_id)
            return {"status": "ok", "action": "started", "run_id": run_id, "timestamp": timestamp}
        elif req.action == "stop":
            mark_training_complete()
            return {"status": "ok", "action": "stopped", "timestamp": timestamp}
        elif req.action == "reset":
            reset_training_session()
            return {"status": "ok", "action": "reset", "timestamp": timestamp}

        return {"status": "error", "message": f"Unknown action: {req.action}"}  # type: ignore[unreachable]

    @router.get("/safety-status", response_model=SafetyStatusResponse)
    async def get_safety_status() -> SafetyStatusResponse:
        """Get CBF safety status for current training state.

        This endpoint provides real-time safety monitoring metrics:
        - Current CBF value h(x)
        - Whether intervention is needed
        - Total intervention count
        - Violations prevented

        Returns:
            Safety status with CBF metrics

        Note:
            This endpoint does NOT block on unsafe states (unlike /state).
            It provides observability into safety status regardless of h(x) value.
        """
        state = _storage.get_state()

        # Validate current state
        safety_result = _validate_training_state(state)

        # Get monitor metrics
        _safety_monitor.get_safety_metrics()

        return SafetyStatusResponse(
            safe=safety_result.safe,
            cbf_value=safety_result.cbf_value,
            intervention_needed=safety_result.intervention_needed,
            distance_from_boundary=safety_result.distance_from_boundary,
            total_interventions=_safety_monitor.interventions,
            violations_prevented=_safety_monitor.violations_prevented,
            timestamp=datetime.utcnow().isoformat(),
        )

    return router
