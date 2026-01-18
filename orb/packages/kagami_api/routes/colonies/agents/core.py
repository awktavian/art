"""Colony Agents - Agent state and management.

Fully typed with Pydantic schemas for OpenAPI and SDK generation.

Provides:
- GET /api/colonies/agents/list - List all agents
- GET /api/colonies/agents/status - Agent status overview
- GET /api/colonies/agents/{agent_id}/state - Individual agent state
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from kagami_api.response_schemas import get_error_responses
from kagami_api.schemas.colonies import (
    AgentsListResponse,
    AgentsStatusResponse,
    AgentState,
    AgentStatus,
    AgentSummary,
)

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/colonies/agents", tags=["colonies", "agents"])

    def _map_worker_status(status_value: str) -> AgentStatus:
        """Map unified_agents WorkerStatus → API AgentStatus."""
        v = (status_value or "").strip().lower()
        if v in {"active", "initializing"}:
            return AgentStatus.ACTIVE
        if v == "busy":
            return AgentStatus.BUSY
        if v == "idle":
            return AgentStatus.IDLE
        if v in {"hibernating"}:
            return AgentStatus.PAUSED
        if v in {"dead"}:
            return AgentStatus.ERROR
        raise ValueError(f"Unknown worker status: {status_value!r}")

    @router.get(
        "/list",
        response_model=AgentsListResponse,
        responses=get_error_responses(500),
        summary="List all agents",
        description="List all agents across all colonies with basic status information.",
    )
    async def list_agents(
        page: int = 1,
        per_page: int = 20,
    ) -> AgentsListResponse:
        """List all agents across all colonies with pagination."""
        from kagami.core.unified_agents import get_unified_organism

        organism = get_unified_organism()
        _ = organism.colonies

        all_agents: list[AgentSummary] = []
        by_colony: dict[str, int] = {}
        by_status: dict[str, int] = {}

        for colony_name, colony_obj in organism.colonies.items():
            for worker in colony_obj.workers:
                status = _map_worker_status(worker.state.status.value)
                all_agents.append(
                    AgentSummary(
                        id=worker.worker_id,
                        name=worker.worker_id,
                        colony=colony_name,
                        status=status,
                        current_task=None,
                        uptime_seconds=max(0.0, time.time() - worker.state.created_at),
                        tasks_completed=worker.state.completed_tasks,
                    )
                )

                by_colony[colony_name] = by_colony.get(colony_name, 0) + 1
                by_status[status.value] = by_status.get(status.value, 0) + 1

        # Apply pagination
        total = len(all_agents)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_agents = all_agents[start_idx:end_idx]
        has_more = end_idx < total

        return AgentsListResponse(
            agents=paginated_agents,
            total=total,
            page=page,
            per_page=per_page,
            has_more=has_more,
            by_colony=by_colony,
            by_status=by_status,
        )

    @router.get(
        "/status",
        response_model=AgentsStatusResponse,
        responses=get_error_responses(500),
        summary="Agent status overview",
        description="Get aggregated agent status across all colonies.",
    )
    async def agents_status() -> AgentsStatusResponse:
        """Get agent status overview."""
        from kagami.core.unified_agents import get_unified_organism

        organism = get_unified_organism()
        _ = organism.colonies

        total = 0
        active = 0
        idle = 0
        busy = 0
        error = 0
        total_completed = 0
        colonies: dict[str, dict[str, int]] = {}
        colony_success_rates: list[float] = []

        for colony_name, colony_obj in organism.colonies.items():
            colonies[colony_name] = {"active": 0, "idle": 0, "busy": 0, "error": 0}
            # Some colony stats may be absent or None in lightweight/early boot.
            try:
                sr = getattr(getattr(colony_obj, "stats", None), "success_rate", None)
                if sr is not None:
                    colony_success_rates.append(float(sr))
            except Exception:
                pass

            for worker in colony_obj.workers:
                total += 1
                total_completed += int(worker.state.completed_tasks)
                status = _map_worker_status(worker.state.status.value)
                if status == AgentStatus.ACTIVE:
                    active += 1
                    colonies[colony_name]["active"] += 1
                elif status == AgentStatus.IDLE:
                    idle += 1
                    colonies[colony_name]["idle"] += 1
                elif status == AgentStatus.BUSY:
                    busy += 1
                    colonies[colony_name]["busy"] += 1
                else:
                    error += 1
                    colonies[colony_name]["error"] += 1

        avg_coherence = (
            sum(colony_success_rates) / len(colony_success_rates) if colony_success_rates else 1.0
        )

        return AgentsStatusResponse(
            total_agents=total,
            active_agents=active,
            idle_agents=idle,
            busy_agents=busy,
            error_agents=error,
            colonies=colonies,
            total_tasks_completed=total_completed,
            avg_coherence=float(avg_coherence),
        )

    @router.get(
        "/{agent_id}/state",
        response_model=AgentState,
        responses=get_error_responses(404, 500),
        summary="Get agent state",
        description="Get detailed state snapshot for a specific agent.",
    )
    async def get_agent_state(agent_id: str) -> AgentState:
        """Get current agent state snapshot."""
        try:
            from kagami.core.unified_agents import get_unified_organism

            organism = get_unified_organism()
            _ = organism.colonies

            worker = None
            colony_name = None
            for c_name, colony_obj in organism.colonies.items():
                for w in colony_obj.workers:
                    if w.worker_id == agent_id:
                        worker = w
                        colony_name = c_name
                        break
                if worker is not None:
                    break

            if worker is None or colony_name is None:
                raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

            status = _map_worker_status(worker.state.status.value)
            created_at = datetime.fromtimestamp(worker.state.created_at, tz=UTC)
            last_active = datetime.fromtimestamp(worker.state.last_active, tz=UTC)
            uptime = max(0.0, time.time() - worker.state.created_at)

            return AgentState(
                id=worker.worker_id,
                name=worker.worker_id,
                colony=colony_name,
                status=status,
                current_task=None,
                task_queue_size=0,
                tasks_completed=worker.state.completed_tasks,
                tasks_failed=worker.state.failed_tasks,
                cpu_usage=0.0,
                memory_mb=0.0,
                coherence=float(worker.fitness),
                energy=1.0,
                created_at=created_at,
                last_active=last_active,
                uptime_seconds=uptime,
                internal_state={
                    "worker_id": worker.worker_id,
                    "colony_idx": worker.state.colony_idx,
                    "catastrophe": worker.state.catastrophe_type,
                    "fitness": float(worker.fitness),
                    "current_tasks": int(worker.state.current_tasks),
                },
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get agent state: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    return router
