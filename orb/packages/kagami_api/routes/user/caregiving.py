"""Caregiving Coordination API Routes.

Supports households with live-in caregivers or family caregiving:
- Shift handoff notes and documentation
- Care log entries (meals, medications, incidents)
- Family dashboard for remote monitoring
- Wellness checks and activity summaries

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
    router = APIRouter(prefix="/api/user/caregiving", tags=["user", "caregiving"])

    class CareLogCategory(str, Enum):
        MEDICATION = "medication"
        MEAL = "meal"
        ACTIVITY = "activity"
        INCIDENT = "incident"
        MOOD = "mood"
        SLEEP = "sleep"
        VITAL_SIGNS = "vital_signs"
        NOTE = "note"

    class AlertSeverity(str, Enum):
        INFO = "info"
        WARNING = "warning"
        URGENT = "urgent"
        EMERGENCY = "emergency"

    class CareLogEntry(BaseModel):
        id: str
        care_recipient_id: str  # The person being cared for
        caregiver_id: str  # Who logged this
        category: CareLogCategory
        summary: str
        details: str | None = None
        occurred_at: datetime
        logged_at: datetime
        attachments: list[str] | None = None

    class MedicationLog(BaseModel):
        id: str
        care_recipient_id: str
        caregiver_id: str
        medication_name: str
        dosage: str
        scheduled_time: datetime
        administered_at: datetime | None = None
        skipped: bool = False
        skip_reason: str | None = None
        notes: str | None = None

    class MedicationLogEntry(BaseModel):  # noqa: F841
        id: str
        care_recipient_id: str
        caregiver_id: str
        medication_name: str
        dosage: str
        scheduled_time: datetime
        administered_at: datetime | None = None
        skipped: bool = False
        skip_reason: str | None = None
        notes: str | None = None

    class ShiftHandoff(BaseModel):
        id: str
        care_recipient_id: str
        outgoing_caregiver_id: str
        incoming_caregiver_id: str | None = None
        handoff_time: datetime
        summary: str
        key_observations: list[str]
        pending_tasks: list[str]
        medication_status: str
        mood_assessment: str | None = None
        concerns: list[str] | None = None

    class WellnessCheck(BaseModel):
        id: str
        care_recipient_id: str
        check_time: datetime
        initiated_by: str  # "system", "family", "caregiver"
        response_received: bool
        response_time: datetime | None = None
        response_method: str | None = None  # "voice", "button", "motion"
        escalated: bool = False

    class FamilyDashboardSummary(BaseModel):
        care_recipient_id: str
        recipient_name: str
        last_activity: datetime | None = None
        today_summary: str
        medications_on_schedule: bool
        meals_logged: int
        incidents_today: int
        current_caregiver: str | None = None
        next_handoff: datetime | None = None
        alerts: list[dict] = []

    # Stub routes
    @router.get("/care-logs", summary="Get care log entries")
    async def get_care_logs(
        care_recipient_id: str | None = None,
        category: CareLogCategory | None = None,
        since: datetime | None = None,
        current_user: User = Depends(get_current_user),
    ):
        return {"logs": [], "user": current_user.id}

    @router.post("/care-logs", summary="Add care log entry")
    async def add_care_log(
        care_recipient_id: str,
        category: CareLogCategory,
        summary: str,
        details: str | None = None,
        current_user: User = Depends(get_current_user),
    ):
        return {"message": "Care log added", "category": category}

    @router.get("/medications", summary="Get medication schedule and logs")
    async def get_medications(
        care_recipient_id: str,
        current_user: User = Depends(get_current_user),
    ):
        return {"medications": [], "care_recipient_id": care_recipient_id}

    @router.post("/medications/log", summary="Log medication administration")
    async def log_medication(
        care_recipient_id: str,
        medication_name: str,
        administered: bool = True,
        notes: str | None = None,
        current_user: User = Depends(get_current_user),
    ):
        return {"message": "Medication logged", "administered": administered}

    @router.get("/handoffs", summary="Get shift handoff notes")
    async def get_handoffs(
        care_recipient_id: str,
        current_user: User = Depends(get_current_user),
    ):
        return {"handoffs": [], "care_recipient_id": care_recipient_id}

    @router.post("/handoffs", summary="Create shift handoff note")
    async def create_handoff(
        care_recipient_id: str,
        summary: str,
        key_observations: list[str],
        pending_tasks: list[str],
        current_user: User = Depends(get_current_user),
    ):
        return {"message": "Handoff created", "care_recipient_id": care_recipient_id}

    @router.get("/wellness-checks", summary="Get wellness check history")
    async def get_wellness_checks(
        care_recipient_id: str,
        current_user: User = Depends(get_current_user),
    ):
        return {"checks": [], "care_recipient_id": care_recipient_id}

    @router.post("/wellness-checks/initiate", summary="Initiate wellness check")
    async def initiate_wellness_check(
        care_recipient_id: str,
        current_user: User = Depends(get_current_user),
    ):
        return {"message": "Wellness check initiated", "care_recipient_id": care_recipient_id}

    @router.get("/family-dashboard", summary="Get family dashboard summary")
    async def get_family_dashboard(
        care_recipient_id: str,
        current_user: User = Depends(get_current_user),
    ):
        return FamilyDashboardSummary(
            care_recipient_id=care_recipient_id,
            recipient_name="Care Recipient",
            today_summary="No activity logged today",
            medications_on_schedule=True,
            meals_logged=0,
            incidents_today=0,
        )

    return router


__all__ = ["get_router"]
