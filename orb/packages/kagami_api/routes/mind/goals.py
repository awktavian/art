"""Goals API - Autonomous goal pursuit control.

Manages the autonomous goal orchestrator:
- Status of goal pursuit
- Pause/resume control

Endpoints at /api/mind/goals:
- GET /status - Orchestrator and goal status
- POST /pause - Pause autonomous pursuit
- POST /resume - Resume autonomous pursuit
"""

import logging
from typing import Any, Protocol

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from kagami_api.response_schemas import get_error_responses
from kagami_api.security import require_auth

logger = logging.getLogger(__name__)


class GoalManagerProtocol(Protocol):
    """Protocol for goal manager."""

    active_goals: list[Any]


class MotivationSystemProtocol(Protocol):
    """Protocol for motivation system."""

    def get_drive_weights(self) -> dict[str, float]: ...


class AutonomousOrchestratorProtocol(Protocol):
    """Protocol for autonomous orchestrator."""

    _enabled: bool
    _background_task: Any | None
    _goal_manager: GoalManagerProtocol | None
    _motivation_system: MotivationSystemProtocol | None

    async def pause(self) -> None: ...

    async def resume(self) -> None: ...


class ContinuousMindProtocol(Protocol):
    """Protocol for continuous mind."""

    _thoughts_count: int


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/mind/goals", tags=["mind", "goals"])

    class GoalStatus(BaseModel):
        """Status of autonomous goal system."""

        enabled: bool = Field(description="Whether autonomous pursuit is enabled")
        running: bool = Field(description="Whether autonomous loop is running")
        active_goals: int = Field(default=0, description="Number of active goals")
        thoughts_generated: int = Field(default=0, description="Thoughts generated")
        drive_weights: dict[str, float] = Field(default_factory=dict)
        errors: list[str] = Field(default_factory=list)

    @router.get(
        "/status",
        response_model=GoalStatus,
        responses=get_error_responses(401, 403, 429, 500),
    )
    async def get_status(request: Request, _user=Depends(require_auth)) -> GoalStatus:  # type: ignore[no-untyped-def]
        """Get current status of autonomous goal system."""
        status = GoalStatus(enabled=True, running=False)

        try:
            app_state = request.app.state

            orch: AutonomousOrchestratorProtocol | None = getattr(
                app_state, "autonomous_orchestrator", None
            )
            if orch is not None:
                try:
                    status.enabled = orch._enabled
                    status.running = (
                        orch._background_task is not None and not orch._background_task.done()
                    )
                except AttributeError as e:
                    logger.warning("Orchestrator missing expected attributes: %s", e)
                    status.errors.append(f"Orchestrator attribute error: {e}")

                if orch._goal_manager:
                    try:
                        status.active_goals = len(orch._goal_manager.active_goals)
                    except (AttributeError, TypeError) as e:
                        logger.warning("Failed to get active goals: %s", e)
                        status.errors.append(f"Goal manager error: {e}")

                if orch._motivation_system:
                    try:
                        status.drive_weights = orch._motivation_system.get_drive_weights()
                    except (AttributeError, TypeError) as e:
                        logger.warning("Failed to get drive weights: %s", e)
                        status.errors.append(f"Motivation system error: {e}")

            mind: ContinuousMindProtocol | None = getattr(app_state, "continuous_mind", None)
            if mind is not None:
                try:
                    status.thoughts_generated = mind._thoughts_count
                except AttributeError as e:
                    logger.warning("Continuous mind missing thoughts_count: %s", e)
                    status.errors.append(f"Mind attribute error: {e}")

        except Exception as e:
            logger.error("Unexpected error getting goal status: %s", e, exc_info=True)
            status.errors.append(str(e))

        return status

    @router.post(
        "/pause",
        responses=get_error_responses(401, 403, 429, 500),
    )
    async def pause(request: Request, _user=Depends(require_auth)) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        """Pause autonomous goal pursuit."""
        try:
            orch: AutonomousOrchestratorProtocol | None = getattr(
                request.app.state, "autonomous_orchestrator", None
            )
            if orch is not None:
                await orch.pause()
                return {"status": "paused"}
            return {"status": "not_running"}
        except Exception as e:
            logger.error("Failed to pause autonomous orchestrator: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post(
        "/resume",
        responses=get_error_responses(401, 403, 429, 500),
    )
    async def resume(request: Request, _user=Depends(require_auth)) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        """Resume autonomous goal pursuit."""
        try:
            orch: AutonomousOrchestratorProtocol | None = getattr(
                request.app.state, "autonomous_orchestrator", None
            )
            if orch is not None:
                await orch.resume()
                return {"status": "resumed"}
            return {"status": "not_running"}
        except Exception as e:
            logger.error("Failed to resume autonomous orchestrator: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

    return router
