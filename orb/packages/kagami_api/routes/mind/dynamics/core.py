"""Dynamics Management Routes - Consolidated chaos and criticality control.

Endpoints for monitoring and controlling organism dynamics:
- Chaos safety monitoring (CBF-based)
- Self-organized criticality (Lyapunov exponents)

Both systems work together to keep the organism at the "edge of chaos"
where computation is most effective.

Chaos Endpoints:
- GET /chaos/status - Chaos safety monitor status
- POST /chaos/check - Check if state is safe
- POST /chaos/stabilize - Stabilize chaotic state using OGY control
- GET /chaos/metrics - Chaos management metrics

Criticality Endpoints:
- GET /criticality/status - Current criticality status
- POST /criticality/adjust - Adjust criticality parameters
- GET /criticality/metrics - Criticality metrics
- GET /criticality/history - Measurement history
"""

import logging
from collections.abc import Callable
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from kagami.core.safety import enforce_tier1
from kagami.core.safety.chaos_safety import ChaosSafetyMonitor
from pydantic import BaseModel, Field

from kagami_api.security import require_auth

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/mind/dynamics", tags=["mind", "dynamics"])

    # =============================================================================
    # CHAOS MODELS
    # =============================================================================

    class ChaosStateRequest(BaseModel):
        """Request to check chaos state."""

        state: list[float] = Field(..., description="Current chaotic state vector")
        cbf_function: str | None = Field(
            None, description="CBF function identifier (unit_ball, norm, none)"
        )

    class StabilizeRequest(BaseModel):
        """Request to stabilize chaos."""

        state: list[float] = Field(..., description="Current chaotic state")
        target_state: list[float] | None = Field(None, description="Target safe state")
        gain: float = Field(0.1, ge=0.0, le=1.0, description="Control gain (0-1)")

    # =============================================================================
    # CRITICALITY MODELS
    # =============================================================================

    class AdjustCriticalityRequest(BaseModel):
        """Request to adjust criticality parameters."""

        target_lyapunov: float | None = Field(
            None, description="Target Lyapunov exponent (0 = edge of chaos)"
        )
        adjustment_rate: float | None = Field(
            None, ge=0.0, le=1.0, description="Adjustment rate (0-1)"
        )

    # =============================================================================
    # CHAOS ENDPOINTS
    # =============================================================================

    @router.get("/chaos/status")
    async def get_chaos_status() -> dict[str, Any]:
        """Get chaos safety monitor status.

        Returns:
            Status including safety metrics, intervention count, and violations prevented.
        """
        try:
            monitor = ChaosSafetyMonitor()
            metrics = monitor.get_safety_metrics().to_dict()

            return {
                "status": "operational",
                "metrics": metrics,
                "interventions": monitor.interventions,
                "violations_prevented": monitor.violations_prevented,
            }
        except Exception as e:
            logger.error(f"Failed to get chaos status: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    @router.post("/chaos/check", dependencies=[Depends(require_auth)])
    @enforce_tier1("memory")
    async def check_chaos_safety(req: ChaosStateRequest) -> dict[str, Any]:
        """Check if chaotic state is safe via CBF.

        Args:
            req: State vector and optional CBF function identifier.

        Returns:
            Safety assessment including CBF value and intervention needs.
        """
        try:
            monitor = ChaosSafetyMonitor()
            state = np.array(req.state)

            cbf_fn: Callable[[np.ndarray], float] | None = None
            if req.cbf_function:
                func_name = req.cbf_function.strip().lower()
                if func_name in {"unit_ball", "norm", "simple_norm"}:

                    def cbf_fn(state_vec: np.ndarray) -> float:
                        return 1.0 - float(np.linalg.norm(state_vec))

                elif func_name != "none":
                    raise HTTPException(
                        status_code=400, detail=f"Unknown cbf_function '{req.cbf_function}'"
                    )

            result = monitor.check_chaos_safety(state, cbf_fn).to_dict()

            response: dict[str, Any] = {
                "safe": result["safe"],
                "cbf_value": result.get("cbf_value"),
                "intervention_needed": result.get("intervention_needed", False),
                "distance_from_boundary": result.get("distance_from_boundary"),
            }
            if result.get("error"):
                response["error"] = result["error"]
            return response
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Chaos safety check failed: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    @router.post("/chaos/stabilize", dependencies=[Depends(require_auth)])
    @enforce_tier1("process")
    async def stabilize_chaos(req: StabilizeRequest) -> dict[str, Any]:
        """Stabilize chaotic state using OGY control.

        Args:
            req: Current state, optional target, and control gain.

        Returns:
            Original and stabilized state vectors.
        """
        try:
            monitor = ChaosSafetyMonitor()
            state = np.array(req.state)
            target = np.array(req.target_state) if req.target_state else None

            stabilized = monitor.stabilize_chaos(state, target_state=target, gain=req.gain)

            return {
                "success": True,
                "original_state": state.tolist(),
                "stabilized_state": stabilized.tolist(),
                "gain": req.gain,
            }
        except Exception as e:
            logger.error(f"Chaos stabilization failed: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    @router.get("/chaos/metrics")
    async def get_chaos_metrics() -> dict[str, Any]:
        """Get chaos management metrics including CBF blocks."""
        try:
            from kagami.observability.metrics.safety import CBF_BLOCKS_TOTAL

            blocks = 0
            try:
                blocks = (
                    int(CBF_BLOCKS_TOTAL._value.get()) if hasattr(CBF_BLOCKS_TOTAL, "_value") else 0
                )
            except Exception:
                logger.debug("Failed to get CBF blocks total value", exc_info=True)

            return {
                "cbf_blocks_total": blocks,
                "status": "operational",
            }
        except Exception as e:
            logger.error(f"Failed to get chaos metrics: {e}")
            return {"cbf_blocks_total": 0, "status": "error", "error": str(e)}

    # =============================================================================
    # CRITICALITY ENDPOINTS
    # =============================================================================

    @router.get("/criticality/status")
    async def get_criticality_status() -> dict[str, Any]:
        """Get current criticality status.

        Returns:
            Status including Lyapunov exponent, regime classification,
            and edge-of-chaos indicator.
        """
        try:
            from kagami.core.unified_agents import get_criticality_manager

            manager = get_criticality_manager()
            metrics = manager.get_criticality_metrics()

            return {
                "status": "operational",
                "current_lyapunov": metrics.get("current_lyapunov", 0.0),
                "average_lyapunov": metrics.get("average_lyapunov", 0.0),
                "regime": metrics.get("regime", "unknown"),
                "at_edge_of_chaos": metrics.get("at_edge_of_chaos", False),
                "target_lyapunov": manager.target_lyapunov,
            }
        except Exception as e:
            logger.error(f"Failed to get criticality status: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    @router.post("/criticality/adjust", dependencies=[Depends(require_auth)])
    @enforce_tier1("process")
    async def adjust_criticality(req: AdjustCriticalityRequest) -> dict[str, Any]:
        """Adjust criticality parameters.

        Args:
            req: New target Lyapunov and/or adjustment rate.

        Returns:
            Updated parameters and adjustment result.
        """
        try:
            from kagami.core.unified_agents import get_criticality_manager, get_unified_organism

            manager = get_criticality_manager()
            organism = get_unified_organism()

            if req.target_lyapunov is not None:
                manager.target_lyapunov = req.target_lyapunov
            if req.adjustment_rate is not None:
                manager.adjustment_rate = req.adjustment_rate

            result = await manager.measure_and_adjust(organism)

            return {
                "success": True,
                "target_lyapunov": manager.target_lyapunov,
                "adjustment_rate": manager.adjustment_rate,
                "adjustment": result,
            }
        except Exception as e:
            logger.error(f"Failed to adjust criticality: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    @router.get("/criticality/metrics")
    async def get_criticality_metrics() -> dict[str, Any]:
        """Get criticality metrics.

        Returns:
            Current and average Lyapunov, regime, and measurement count.
        """
        try:
            from kagami.core.unified_agents import get_criticality_manager

            manager = get_criticality_manager()
            metrics = manager.get_criticality_metrics()

            return {
                "current_lyapunov": round(metrics.get("current_lyapunov", 0.0), 6),
                "average_lyapunov": round(metrics.get("average_lyapunov", 0.0), 6),
                "regime": metrics.get("regime", "unknown"),
                "measurement_count": metrics.get("measurement_count", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get criticality metrics: {e}")
            return {
                "current_lyapunov": 0.0,
                "average_lyapunov": 0.0,
                "regime": "error",
                "error": str(e),
            }

    @router.get("/criticality/history")
    async def get_criticality_history() -> dict[str, Any]:
        """Get criticality measurement history.

        Returns:
            Historical data for Lyapunov, success rate, agent count, response time.
        """
        try:
            from kagami.core.unified_agents import get_criticality_manager

            manager = get_criticality_manager()

            return {
                "lyapunov_history": list(manager.lyapunov_history),
                "success_history": list(manager.success_history),
                "agent_count_history": list(manager.agent_count_history),
                "response_time_history": list(manager.response_time_history),
            }
        except Exception as e:
            logger.error(f"Failed to get criticality history: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    return router
