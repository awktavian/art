"""Shared Space Booking API Routes.

Supports intentional communities and coliving with:
- Shared space reservations (yoga room, guest suite, workshop)
- Chore rotation tracking
- Community meal RSVPs
- Per-person energy/utility tracking
- Guest night tracking

Created: December 31, 2025 (Diverse Personas)
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from kagami_api.auth import User, get_current_user

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    router = APIRouter(prefix="/api/user/shared-spaces", tags=["user", "shared-spaces"])

    class SpaceType(str, Enum):
        YOGA_ROOM = "yoga_room"
        GUEST_SUITE = "guest_suite"
        WORKSHOP = "workshop"
        COMMON_KITCHEN = "common_kitchen"
        LAUNDRY = "laundry"
        GARDEN = "garden"
        CUSTOM = "custom"

    class ChoreCategory(str, Enum):
        KITCHEN = "kitchen"
        BATHROOM = "bathroom"
        COMMON_AREA = "common_area"
        OUTDOOR = "outdoor"
        SPECIAL = "special"

    class Reservation(BaseModel):
        id: str
        space_id: str
        space_type: SpaceType
        user_id: str
        start_time: datetime
        end_time: datetime
        title: str | None = None
        recurring: bool = False
        recurrence_pattern: str | None = None  # "weekly", "daily", etc.

    class ChoreAssignment(BaseModel):
        id: str
        chore_name: str
        category: ChoreCategory
        assigned_to: str  # user_id
        due_date: datetime
        completed: bool = False
        completed_at: datetime | None = None
        verified_by: str | None = None

    class CommunityMealRSVP(BaseModel):
        meal_date: datetime
        user_id: str
        attending: bool
        guests: int = 0
        dietary_notes: str | None = None

    class UtilityUsage(BaseModel):
        user_id: str
        period_start: datetime
        period_end: datetime
        electricity_kwh: float
        water_gallons: float
        gas_therms: float
        percentage_of_total: float
        estimated_cost: float

    class GuestNights(BaseModel):
        user_id: str
        month: str  # "2025-12"
        nights_used: int
        nights_allowed: int = 3  # configurable per community
        guest_log: list[dict]  # [{"date": "2025-12-15", "guest_name": "...", "nights": 1}, ...]

    # Stub routes
    @router.get("/reservations", summary="Get space reservations")
    async def get_reservations(
        space_type: SpaceType | None = None,
        start_date: datetime | None = None,
        current_user: User = Depends(get_current_user),
    ):
        return {"reservations": [], "space_type": space_type}

    @router.post("/reservations", summary="Create a reservation")
    async def create_reservation(
        space_type: SpaceType,
        start_time: datetime,
        duration_hours: float = 1.0,
        current_user: User = Depends(get_current_user),
    ):
        return {"message": "Reservation created", "user": current_user.id}

    @router.get("/chores", summary="Get chore assignments")
    async def get_chores(current_user: User = Depends(get_current_user)):
        return {"chores": [], "user": current_user.id}

    @router.post("/chores/{chore_id}/complete", summary="Mark chore complete")
    async def complete_chore(chore_id: str, current_user: User = Depends(get_current_user)):
        return {"message": "Chore marked complete", "chore_id": chore_id}

    @router.get("/meals", summary="Get community meal RSVPs")
    async def get_meal_rsvps(current_user: User = Depends(get_current_user)):
        return {"meals": [], "user": current_user.id}

    @router.post("/meals/rsvp", summary="RSVP for community meal")
    async def rsvp_meal(
        meal_date: datetime,
        attending: bool,
        guests: int = 0,
        current_user: User = Depends(get_current_user),
    ):
        return {"message": "RSVP recorded", "attending": attending}

    @router.get("/utility-usage", summary="Get per-user utility usage")
    async def get_utility_usage(
        month: str | None = None,
        current_user: User = Depends(get_current_user),
    ):
        return {"usage": None, "user": current_user.id}

    @router.get("/guest-nights", summary="Get guest night tracking")
    async def get_guest_nights(current_user: User = Depends(get_current_user)):
        return {"nights_used": 0, "nights_allowed": 3, "user": current_user.id}

    return router


__all__ = ["get_router"]
