"""Colonies API - Unified colony operations.

The colony is Kagami's organizational unit. Each of the 7 colonies
(Spark, Forge, Flow, Nexus, Beacon, Grove, Crystal) has a role
in the Fano plane geometry.

Endpoints:
- /api/colonies/status - System-wide colony status
- /api/colonies/stream (WebSocket) - Real-time activity stream
- /api/colonies/agents/* - Agent management within colonies
- /api/colonies/ui/* - Bidirectional agent-UI communication (AG-UI)

Colony metrics are exposed via /metrics (Prometheus OpenMetrics).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timezone

from fastapi import APIRouter, Depends

from kagami_api.response_schemas import get_error_responses
from kagami_api.schemas.colonies import ColoniesStatusResponse, ColonyStatus
from kagami_api.security import Principal, require_auth

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Sub-routers are imported and included when this is called.
    """
    # Lazy import sub-routers
    from . import agents, stream, ui

    router = APIRouter(tags=["colonies"])

    @router.get(
        "/api/colonies/status",
        response_model=ColoniesStatusResponse,
        responses=get_error_responses(500),
        summary="Get system-wide colony status",
        description=(
            "Get aggregate status across all 7 colonies including active agent counts, "
            "success rates, and overall system health. Returns colony-level metrics "
            "without individual agent details."
        ),
    )
    async def get_colonies_status(
        current_user: Principal = Depends(require_auth),
    ) -> ColoniesStatusResponse:
        """Get system-wide colony status (all 7 colonies).

        Returns aggregate metrics across all colonies including:
        - Active agent counts per colony
        - Success rates
        - Catastrophe types
        - Overall system coherence
        """
        try:
            from kagami.core.unified_agents import get_unified_organism

            organism = get_unified_organism()

            colonies_status: dict[str, ColonyStatus] = {}
            total_agents = 0
            success_rates: list[float] = []

            for name, colony in organism.colonies.items():
                agent_count = len(colony.workers) if hasattr(colony, "workers") else 0
                total_agents += agent_count

                # Get REAL success rate (None if no data)
                raw_success_rate = colony.stats.success_rate if hasattr(colony, "stats") else None

                # Determine colony status - NO FAKE STATS
                if agent_count > 0:
                    colony_status_str = "active"
                elif raw_success_rate is not None and raw_success_rate < 0.5:
                    colony_status_str = "error"
                elif raw_success_rate is None:
                    colony_status_str = "no_data"  # Honest: we have no data yet
                else:
                    colony_status_str = "idle"

                # Get success rate - use display value (0.0 for no data, never fake 0.5)
                success_rate = float(raw_success_rate) if raw_success_rate is not None else 0.0
                if raw_success_rate is not None:
                    success_rates.append(success_rate)

                # Get tasks completed
                tasks_completed = 0
                if hasattr(colony, "workers"):
                    for worker in colony.workers:
                        tasks_completed += int(worker.state.completed_tasks)

                colonies_status[name] = ColonyStatus(
                    name=name,
                    active_agents=agent_count,
                    status=colony_status_str,
                    catastrophe_type=getattr(colony, "catastrophe_type", "unknown"),
                    success_rate=success_rate,
                    tasks_completed=tasks_completed,
                )

            # Determine overall system status
            avg_success = sum(success_rates) / len(success_rates) if success_rates else 1.0
            if avg_success >= 0.8:
                system_status = "operational"
            elif avg_success >= 0.5:
                system_status = "degraded"
            else:
                system_status = "error"

            return ColoniesStatusResponse(
                colonies=colonies_status,
                total_agents=total_agents,
                timestamp=datetime.now(UTC),
                status=system_status,
                avg_success_rate=avg_success,
            )
        except Exception as e:
            logger.error(f"Failed to get colonies status: {e}", exc_info=True)
            # Return degraded status on error instead of raising
            return ColoniesStatusResponse(
                colonies={},
                total_agents=0,
                timestamp=datetime.now(UTC),
                status="error",
                avg_success_rate=0.0,
            )

    # Include sub-routers (support both lazy and eager patterns)
    for module in [stream, agents, ui]:
        if hasattr(module, "get_router"):
            router.include_router(module.get_router())
        else:
            router.include_router(module.router)

    return router


__all__ = ["get_router"]
