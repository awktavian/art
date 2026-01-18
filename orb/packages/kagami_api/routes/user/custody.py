"""Custody and Co-Parenting API Routes.

Supports divorced/separated co-parents with shared custody arrangements:
- Custody schedule integration
- Parent-specific home settings
- Asynchronous parent communication via logs
- Child-centric profiles that persist across parent switches

Created: December 31, 2025 (Diverse Personas)
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from kagami_api.auth import User, get_current_user

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    router = APIRouter(prefix="/api/user/custody", tags=["user", "custody"])

    class CustodyScheduleType(str, Enum):
        WEEK_ON_WEEK_OFF = "week_on_week_off"  # Alternating weeks
        EVERY_OTHER_WEEKEND = "every_other_weekend"
        CUSTOM = "custom"

    class CustodySchedule(BaseModel):
        """Custody schedule configuration."""

        type: CustodyScheduleType = Field(description="Type of custody arrangement")
        parent_a_id: str = Field(description="First parent's user ID")
        parent_b_id: str = Field(description="Second parent's user ID")
        children: list[str] = Field(description="Child member IDs")
        handoff_day: int = Field(
            default=6, ge=0, le=6, description="Day of week for handoff (0=Mon)"
        )
        handoff_time: str = Field(default="18:00", description="Handoff time")
        # For custom schedules
        custom_pattern: list[dict] | None = Field(default=None)

    class ParentModeSettings(BaseModel):
        """Per-parent household settings that activate during their custody time."""

        parent_id: str
        thermostat_temp: int | None = Field(default=None)
        bedtime_rules: dict | None = Field(default=None)  # {"child_id": "21:00", ...}
        allowed_content_rating: str | None = Field(default=None)
        spotify_playlist: str | None = Field(default=None)
        morning_routine: str | None = Field(default=None)

    class CustodyLogEntry(BaseModel):
        """Asynchronous communication between parents."""

        id: str
        from_parent_id: str
        message: str
        category: str = Field(default="general")  # general, medical, school, behavior
        attachments: list[str] | None = Field(default=None)
        created_at: datetime
        read_at: datetime | None = Field(default=None)

    class CustodyArrangement(BaseModel):
        """Full custody arrangement for a household."""

        id: str
        household_id: str
        schedule: CustodySchedule
        parent_a_settings: ParentModeSettings
        parent_b_settings: ParentModeSettings
        current_parent_id: str = Field(description="Which parent is currently 'active'")
        next_handoff: datetime
        logs: list[CustodyLogEntry] = Field(default_factory=list)

    # Routes would go here for:
    # GET /custody - Get custody arrangement
    # POST /custody - Create custody arrangement
    # PUT /custody/schedule - Update schedule
    # POST /custody/log - Add log entry
    # GET /custody/log - Get log entries
    # POST /custody/handoff - Manual handoff trigger

    @router.get("", summary="Get custody arrangement")
    async def get_custody(current_user: User = Depends(get_current_user)):
        return {"message": "Custody support coming soon", "user": current_user.id}

    @router.get("/current-parent", summary="Get which parent is currently 'active'")
    async def get_current_parent(current_user: User = Depends(get_current_user)):
        return {"current_parent_id": current_user.id, "until": None}

    return router


__all__ = ["get_router"]
