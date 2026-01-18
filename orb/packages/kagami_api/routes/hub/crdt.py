"""Hub CRDT State Synchronization API — Cross-hub distributed state.

This module provides API endpoints for synchronizing CRDT state between
the Python API server and Rust Kagami Hubs.

Endpoints:
    POST /api/v1/hub/crdt-state     - Receive CRDT state from hub
    GET  /api/v1/hub/crdt-state     - Get current CRDT state
    POST /api/v1/hub/crdt-delta     - Get delta since vector clock
    GET  /api/v1/hub/crdt-status    - Get sync status

Architecture:
```
    Rust Hub                         Python API
    ─────────                        ──────────
    CRDTState  ──POST /crdt-state──►  CrossHubCRDTManager
    (sync.rs)  ◄──GET /crdt-state───  (cross_hub_crdt.py)
```

Colony: Nexus (e₄) — Bridge between hubs
h(x) ≥ 0. Always.

Created: January 4, 2026
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hub-crdt"])


# =============================================================================
# Request/Response Models
# =============================================================================


class VectorClockModel(BaseModel):
    """Vector clock for causality tracking."""

    clocks: dict[str, int] = Field(default_factory=dict)


class LWWRegisterModel(BaseModel):
    """Last-Writer-Wins register."""

    value: Any
    timestamp: float
    writer: str


class ORSetModel(BaseModel):
    """Observed-Remove Set."""

    elements: list[dict[str, str]] = Field(default_factory=list)
    tombstones: list[str] = Field(default_factory=list)


class GCounterModel(BaseModel):
    """Grow-only counter."""

    counts: dict[str, int] = Field(default_factory=dict)


class CRDTStateModel(BaseModel):
    """Full CRDT state from hub."""

    clock: VectorClockModel
    presence: LWWRegisterModel | None = None
    home_state: LWWRegisterModel | None = None
    tesla_state: LWWRegisterModel | None = None
    weather_state: LWWRegisterModel | None = None
    active_rooms: ORSetModel | None = None
    sync_count: GCounterModel | None = None
    source_hub: str
    timestamp: float


class DeltaRequestModel(BaseModel):
    """Request for state delta since a vector clock."""

    since_clock: VectorClockModel


class SyncStatusModel(BaseModel):
    """Synchronization status."""

    node_id: str
    sync_count: int
    last_sync_time: float | None
    known_hubs: list[str]
    vector_clock: dict[str, int]
    active_rooms: list[str]
    total_syncs: int


# =============================================================================
# API Endpoints
# =============================================================================


@router.post("/crdt-state", status_code=status.HTTP_202_ACCEPTED)
async def receive_crdt_state(state: CRDTStateModel) -> dict[str, Any]:
    """Receive CRDT state from a hub.

    Merges the incoming state with local state using CRDT semantics.
    All merges are commutative, associative, and idempotent.

    Args:
        state: CRDT state from hub.

    Returns:
        Acknowledgment with merge status.
    """
    try:
        from kagami.core.coordination.cross_hub_crdt import (
            get_cross_hub_crdt_manager,
        )

        manager = await get_cross_hub_crdt_manager()
        await manager.merge_hub_state_dict(state.model_dump())

        logger.info(f"Merged CRDT state from hub {state.source_hub}")

        return {
            "status": "accepted",
            "source_hub": state.source_hub,
            "merged": True,
            "local_clock": manager.get_state().clock.clocks,
        }

    except Exception as e:
        logger.error(f"Failed to merge CRDT state: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to merge state: {str(e)}",
        ) from e


@router.get("/crdt-state", response_model=CRDTStateModel)
async def get_crdt_state() -> CRDTStateModel:
    """Get current CRDT state.

    Returns the local CRDT state for synchronization.
    Hubs can call this to pull state from the API server.

    Returns:
        Current CRDT state.
    """
    try:
        from kagami.core.coordination.cross_hub_crdt import (
            get_cross_hub_crdt_manager,
        )

        manager = await get_cross_hub_crdt_manager()
        state = manager.get_state()

        return CRDTStateModel(**state.to_dict())

    except Exception as e:
        logger.error(f"Failed to get CRDT state: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get state: {str(e)}",
        ) from e


@router.post("/crdt-delta")
async def get_crdt_delta(request: DeltaRequestModel) -> dict[str, Any]:
    """Get state delta since a vector clock.

    Calculates and returns only the state changes since the given
    vector clock. If no changes needed, returns null delta.

    Args:
        request: Delta request with since_clock.

    Returns:
        Delta state or null indicator.
    """
    try:
        from kagami.core.coordination.cross_hub_crdt import (
            VectorClock,
            get_cross_hub_crdt_manager,
        )

        manager = await get_cross_hub_crdt_manager()

        # Convert request to VectorClock
        since_clock = VectorClock(clocks=dict(request.since_clock.clocks))

        delta = manager.calculate_delta(since_clock)

        if delta is None:
            return {
                "has_delta": False,
                "delta": None,
            }

        return {
            "has_delta": True,
            "delta": delta.to_dict(),
        }

    except Exception as e:
        logger.error(f"Failed to calculate CRDT delta: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate delta: {str(e)}",
        ) from e


@router.get("/crdt-status", response_model=SyncStatusModel)
async def get_crdt_status() -> SyncStatusModel:
    """Get CRDT synchronization status.

    Returns status information about the CRDT manager including
    sync count, known hubs, and active rooms.

    Returns:
        Sync status.
    """
    try:
        from kagami.core.coordination.cross_hub_crdt import (
            get_cross_hub_crdt_manager,
        )

        manager = await get_cross_hub_crdt_manager()
        status_dict = manager.get_sync_status()

        return SyncStatusModel(**status_dict)

    except Exception as e:
        logger.error(f"Failed to get CRDT status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}",
        ) from e


# =============================================================================
# 鏡
# State flows. Hubs sync. The mesh converges.
# h(x) ≥ 0. Always.
# =============================================================================
