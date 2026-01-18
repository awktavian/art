"""Household Sharing API Routes.

Provides household/family sharing functionality including:
- Household creation and management
- Member invitation and management
- Role-based access control within households
- Time-limited guest access

Roles:
- Owner: Full control, billing, delete household
- Admin: Manage members, all device control
- Caregiver: Staff access, time-tracked shifts
- Member: Device control, can't manage members
- Elder: Simplified interface, family monitoring opt-in
- Child: Restricted access, parental controls
- Guest: Limited device control, time-limited access

Created: December 31, 2025 (RALPH Week 3)
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from kagami_api.auth import User, get_current_user
from kagami_api.response_schemas import get_error_responses

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/user/household", tags=["user", "household"])

    # =============================================================================
    # ENUMS
    # =============================================================================

    class HouseholdRole(str, Enum):
        """Roles within a household."""

        OWNER = "owner"  # Full control, billing, can delete household
        ADMIN = "admin"  # Manage members, all device control
        MEMBER = "member"  # Device control, can't manage members
        CHILD = "child"  # Restricted access, parental controls
        ELDER = "elder"  # Simplified interface, family monitoring opt-in
        CAREGIVER = "caregiver"  # Staff access, time-tracked
        GUEST = "guest"  # Limited device control, time-limited

    class InvitationStatus(str, Enum):
        """Status of a household invitation."""

        PENDING = "pending"
        ACCEPTED = "accepted"
        DECLINED = "declined"
        EXPIRED = "expired"
        REVOKED = "revoked"

    class NotificationType(str, Enum):
        """Types of household notifications."""

        INVITATION_SENT = "invitation_sent"
        INVITATION_ACCEPTED = "invitation_accepted"
        INVITATION_DECLINED = "invitation_declined"
        MEMBER_JOINED = "member_joined"
        MEMBER_LEFT = "member_left"
        MEMBER_REMOVED = "member_removed"
        ROLE_CHANGED = "role_changed"

    # Role hierarchy for permission checking
    ROLE_HIERARCHY = {
        HouseholdRole.OWNER: 7,
        HouseholdRole.ADMIN: 6,
        HouseholdRole.CAREGIVER: 5,
        HouseholdRole.MEMBER: 4,
        HouseholdRole.ELDER: 3,
        HouseholdRole.CHILD: 2,
        HouseholdRole.GUEST: 1,
    }

    # =============================================================================
    # SCHEMAS
    # =============================================================================

    class ChildSettings(BaseModel):
        """Settings for child household members."""

        parental_controls: bool = Field(default=True)
        content_filter_level: str = Field(default="moderate")  # strict, moderate, minimal
        screen_time_limit_minutes: int | None = Field(default=None)
        allowed_rooms: list[str] | None = Field(default=None)
        allowed_devices: list[str] | None = Field(default=None)
        bedtime: str | None = Field(default=None)  # HH:MM
        bedtime_warning_minutes: int = Field(default=15)

    class ElderSettings(BaseModel):
        """Settings for elder household members."""

        simplified_interface: bool = Field(default=True)
        larger_buttons: bool = Field(default=True)
        voice_primary: bool = Field(default=True)
        family_can_view_activity: bool = Field(default=True)
        fall_detection_enabled: bool = Field(default=False)
        medication_reminders: list[dict] | None = Field(
            default=None
        )  # [{"time": "08:00", "name": "Morning meds"}, ...]
        check_in_schedule: str | None = Field(default=None)  # daily, twice_daily, weekly

    class CaregiverSettings(BaseModel):
        """Settings for caregiver household members."""

        shift_schedule: list[dict] | None = Field(
            default=None
        )  # [{"start": "08:00", "end": "16:00", "days": [0,1,2,3,4]}, ...]
        care_documentation_access: bool = Field(default=True)
        can_view_health_data: bool = Field(default=True)
        can_administer_medication: bool = Field(default=False)
        private_quarters: list[str] | None = Field(
            default=None
        )  # Rooms that are private to caregiver
        handoff_notes_enabled: bool = Field(default=True)

    class HouseholdCreate(BaseModel):
        """Request to create a new household."""

        name: str = Field(min_length=1, max_length=100, description="Household name")
        address: str | None = Field(None, max_length=500, description="Physical address (optional)")
        timezone: str | None = Field(None, description="Timezone (e.g., America/Los_Angeles)")

    class HouseholdUpdate(BaseModel):
        """Request to update household settings."""

        name: str | None = Field(None, min_length=1, max_length=100, description="Household name")
        address: str | None = Field(None, max_length=500, description="Physical address")
        timezone: str | None = Field(None, description="Timezone")
        guest_access_enabled: bool | None = Field(None, description="Allow guest invitations")
        guest_access_duration_hours: int | None = Field(
            None, ge=1, le=168, description="Default guest access duration (1-168 hours)"
        )
        require_2fa_for_device_control: bool | None = Field(
            None, description="Require 2FA for device control"
        )

    class HouseholdOut(BaseModel):
        """Household information (output)."""

        id: str = Field(description="Household unique identifier")
        name: str = Field(description="Household name")
        owner_id: str = Field(description="Owner's user ID")
        address: str | None = Field(None, description="Physical address")
        timezone: str | None = Field(None, description="Timezone")
        member_count: int = Field(description="Number of members")
        guest_access_enabled: bool = Field(default=True)
        guest_access_duration_hours: int = Field(default=24)
        require_2fa_for_device_control: bool = Field(default=False)
        created_at: datetime = Field(description="Creation timestamp")
        updated_at: datetime | None = Field(None, description="Last update timestamp")

    class HouseholdMemberOut(BaseModel):
        """Household member information."""

        user_id: str = Field(description="Member's user ID")
        email: str = Field(description="Member's email")
        username: str = Field(description="Member's username")
        role: HouseholdRole = Field(description="Role in household")
        joined_at: datetime = Field(description="When they joined")
        expires_at: datetime | None = Field(None, description="When access expires (guests only)")
        last_active: datetime | None = Field(None, description="Last activity timestamp")
        is_online: bool = Field(default=False, description="Currently online")
        child_settings: ChildSettings | None = Field(default=None)
        elder_settings: ElderSettings | None = Field(default=None)
        caregiver_settings: CaregiverSettings | None = Field(default=None)

    class InviteRequest(BaseModel):
        """Request to invite someone to household."""

        email: EmailStr = Field(description="Email to invite")
        role: HouseholdRole = Field(default=HouseholdRole.MEMBER, description="Role to assign")
        message: str | None = Field(None, max_length=500, description="Personal message to include")
        expires_in_hours: int = Field(
            default=72, ge=1, le=168, description="Hours until invitation expires"
        )

    class InvitationOut(BaseModel):
        """Household invitation information."""

        id: str = Field(description="Invitation ID")
        household_id: str = Field(description="Household ID")
        household_name: str = Field(description="Household name")
        email: str = Field(description="Invited email")
        role: HouseholdRole = Field(description="Role being offered")
        status: InvitationStatus = Field(description="Invitation status")
        invited_by: str = Field(description="Who sent the invitation")
        message: str | None = Field(None, description="Personal message")
        created_at: datetime = Field(description="When invitation was sent")
        expires_at: datetime = Field(description="When invitation expires")

    class JoinRequest(BaseModel):
        """Request to join a household with an invitation code."""

        code: str = Field(min_length=6, max_length=64, description="Invitation code")

    class RoleChangeRequest(BaseModel):
        """Request to change a member's role."""

        role: HouseholdRole = Field(description="New role to assign")

    class HouseholdResponse(BaseModel):
        """Response containing household data."""

        household: HouseholdOut
        my_role: HouseholdRole

    class MembersResponse(BaseModel):
        """Response containing household members."""

        members: list[HouseholdMemberOut]
        total: int

    class InvitationsResponse(BaseModel):
        """Response containing household invitations."""

        invitations: list[InvitationOut]
        total: int

    # =============================================================================
    # STORAGE HELPERS (Redis-backed)
    # =============================================================================

    async def _get_redis_client() -> Any:
        """Get async Redis client."""
        try:
            from kagami.core.caching.redis import RedisClientFactory

            return RedisClientFactory.get_client(
                purpose="default", async_mode=True, decode_responses=True
            )
        except Exception:
            return None

    async def _get_household(household_id: str) -> dict[str, Any] | None:
        """Get household by ID."""
        client = await _get_redis_client()
        if not client:
            return None

        key = f"household:{household_id}"
        data = await client.get(key)
        if data:
            return json.loads(data)
        return None

    async def _set_household(household_id: str, household: dict[str, Any]) -> bool:
        """Store household data."""
        client = await _get_redis_client()
        if not client:
            return False

        key = f"household:{household_id}"
        await client.set(key, json.dumps(household, default=str))
        return True

    async def _delete_household(household_id: str) -> bool:
        """Delete household and all related data."""
        client = await _get_redis_client()
        if not client:
            return False

        # Delete household
        await client.delete(f"household:{household_id}")
        # Delete all invitations for this household
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match=f"invitation:*:{household_id}")
            if keys:
                await client.delete(*keys)
            if cursor == 0:
                break

        return True

    async def _get_user_household_id(user_id: str) -> str | None:
        """Get the household ID for a user."""
        client = await _get_redis_client()
        if not client:
            return None

        key = f"user:household:{user_id}"
        return await client.get(key)

    async def _set_user_household(user_id: str, household_id: str | None) -> bool:
        """Set or clear user's household membership."""
        client = await _get_redis_client()
        if not client:
            return False

        key = f"user:household:{user_id}"
        if household_id:
            await client.set(key, household_id)
        else:
            await client.delete(key)
        return True

    async def _get_invitation(invitation_id: str) -> dict[str, Any] | None:
        """Get invitation by ID."""
        client = await _get_redis_client()
        if not client:
            return None

        key = f"invitation:{invitation_id}"
        data = await client.get(key)
        if data:
            return json.loads(data)
        return None

    async def _get_invitation_by_code(code: str) -> dict[str, Any] | None:
        """Get invitation by code."""
        client = await _get_redis_client()
        if not client:
            return None

        key = f"invitation:code:{code}"
        invitation_id = await client.get(key)
        if invitation_id:
            return await _get_invitation(invitation_id)
        return None

    async def _set_invitation(invitation_id: str, invitation: dict[str, Any]) -> bool:
        """Store invitation data."""
        client = await _get_redis_client()
        if not client:
            return False

        key = f"invitation:{invitation_id}"
        await client.set(key, json.dumps(invitation, default=str))

        # Also store by code for lookup
        code = invitation.get("code")
        if code:
            code_key = f"invitation:code:{code}"
            await client.set(code_key, invitation_id)
            # Expire code lookup when invitation expires
            expires_at_str = invitation.get("expires_at")
            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    ttl = int((expires_at - datetime.utcnow()).total_seconds())
                    if ttl > 0:
                        await client.expire(code_key, ttl)
                except Exception:
                    pass

        return True

    async def _get_household_invitations(household_id: str) -> list[dict[str, Any]]:
        """Get all invitations for a household."""
        client = await _get_redis_client()
        if not client:
            return []

        invitations = []
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match="invitation:*")
            for key in keys:
                if key.startswith("invitation:code:"):
                    continue
                data = await client.get(key)
                if data:
                    inv = json.loads(data)
                    if inv.get("household_id") == household_id:
                        invitations.append(inv)
            if cursor == 0:
                break

        return invitations

    async def _get_user_invitations(email: str) -> list[dict[str, Any]]:
        """Get all invitations for an email."""
        client = await _get_redis_client()
        if not client:
            return []

        invitations = []
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match="invitation:*")
            for key in keys:
                if key.startswith("invitation:code:"):
                    continue
                data = await client.get(key)
                if data:
                    inv = json.loads(data)
                    if inv.get("email", "").lower() == email.lower():
                        invitations.append(inv)
            if cursor == 0:
                break

        return invitations

    def _generate_invitation_code() -> str:
        """Generate a secure invitation code."""
        return secrets.token_urlsafe(24)

    async def _send_notification(
        notification_type: NotificationType,
        household_id: str,
        target_user_id: str | None = None,
        target_email: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Send a notification for household events.

        In production, this would integrate with:
        - Push notifications (FCM, APNs)
        - Email service
        - In-app notifications
        """
        logger.info(
            f"Notification: {notification_type.value} for household {household_id}, "
            f"target_user={target_user_id}, target_email={target_email}, data={data}"
        )

        # Store notification in Redis for in-app display
        client = await _get_redis_client()
        if client and target_user_id:
            notification = {
                "id": str(uuid.uuid4()),
                "type": notification_type.value,
                "household_id": household_id,
                "data": data or {},
                "created_at": datetime.utcnow().isoformat(),
                "read": False,
            }
            key = f"notifications:{target_user_id}"
            # Add to list of notifications
            await client.lpush(key, json.dumps(notification, default=str))
            # Keep only last 100 notifications
            await client.ltrim(key, 0, 99)
            # Expire after 30 days
            await client.expire(key, 60 * 60 * 24 * 30)

    def _check_permission(
        user_role: HouseholdRole,
        required_role: HouseholdRole,
    ) -> bool:
        """Check if user has required role level or higher."""
        return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(required_role, 0)

    async def _get_user_role_in_household(
        user_id: str, household: dict[str, Any]
    ) -> HouseholdRole | None:
        """Get user's role in a household."""
        members = household.get("members", [])
        for member in members:
            if member.get("user_id") == user_id:
                return HouseholdRole(member.get("role", "member"))
        return None

    # =============================================================================
    # ROUTES - HOUSEHOLD MANAGEMENT
    # =============================================================================

    @router.post(
        "",
        response_model=HouseholdResponse,
        responses=get_error_responses(400, 401, 409, 422, 500),
        summary="Create household",
        description="""
        Create a new household. The authenticated user becomes the owner.

        A user can only belong to one household at a time. If already in a household,
        they must leave it first before creating a new one.
        """,
    )
    async def create_household(
        request: HouseholdCreate,
        current_user: User = Depends(get_current_user),
    ) -> HouseholdResponse:
        """Create a new household."""
        # Check if user already in a household
        existing_household_id = await _get_user_household_id(current_user.id)
        if existing_household_id:
            raise HTTPException(
                status_code=409,
                detail="Already a member of a household. Leave current household first.",
            )

        household_id = str(uuid.uuid4())
        now = datetime.utcnow()

        household = {
            "id": household_id,
            "name": request.name,
            "owner_id": current_user.id,
            "address": request.address,
            "timezone": request.timezone,
            "guest_access_enabled": True,
            "guest_access_duration_hours": 24,
            "require_2fa_for_device_control": False,
            "created_at": now.isoformat(),
            "updated_at": None,
            "members": [
                {
                    "user_id": current_user.id,
                    "email": current_user.email,
                    "username": current_user.username,
                    "role": HouseholdRole.OWNER.value,
                    "joined_at": now.isoformat(),
                    "expires_at": None,
                    "last_active": now.isoformat(),
                }
            ],
        }

        if not await _set_household(household_id, household):
            raise HTTPException(status_code=500, detail="Failed to create household")

        await _set_user_household(current_user.id, household_id)

        logger.info(f"Household created: {household_id} by user {current_user.id}")

        return HouseholdResponse(
            household=HouseholdOut(
                id=household_id,
                name=request.name,
                owner_id=current_user.id,
                address=request.address,
                timezone=request.timezone,
                member_count=1,
                guest_access_enabled=True,
                guest_access_duration_hours=24,
                require_2fa_for_device_control=False,
                created_at=now,
                updated_at=None,
            ),
            my_role=HouseholdRole.OWNER,
        )

    @router.get(
        "",
        response_model=HouseholdResponse,
        responses=get_error_responses(401, 404, 500),
        summary="Get current household",
        description="Returns the authenticated user's current household.",
    )
    async def get_household(
        current_user: User = Depends(get_current_user),
    ) -> HouseholdResponse:
        """Get the current user's household."""
        household_id = await _get_user_household_id(current_user.id)
        if not household_id:
            raise HTTPException(status_code=404, detail="Not a member of any household")

        household = await _get_household(household_id)
        if not household:
            # Clean up stale reference
            await _set_user_household(current_user.id, None)
            raise HTTPException(status_code=404, detail="Household not found")

        my_role = await _get_user_role_in_household(current_user.id, household)
        if not my_role:
            # Clean up stale reference
            await _set_user_household(current_user.id, None)
            raise HTTPException(status_code=404, detail="Not a member of this household")

        return HouseholdResponse(
            household=HouseholdOut(
                id=household["id"],
                name=household["name"],
                owner_id=household["owner_id"],
                address=household.get("address"),
                timezone=household.get("timezone"),
                member_count=len(household.get("members", [])),
                guest_access_enabled=household.get("guest_access_enabled", True),
                guest_access_duration_hours=household.get("guest_access_duration_hours", 24),
                require_2fa_for_device_control=household.get(
                    "require_2fa_for_device_control", False
                ),
                created_at=datetime.fromisoformat(household["created_at"]),
                updated_at=(
                    datetime.fromisoformat(household["updated_at"])
                    if household.get("updated_at")
                    else None
                ),
            ),
            my_role=my_role,
        )

    @router.put(
        "",
        response_model=HouseholdResponse,
        responses=get_error_responses(401, 403, 404, 422, 500),
        summary="Update household settings",
        description="Update household settings. Requires Admin or Owner role.",
    )
    async def update_household(
        request: HouseholdUpdate,
        current_user: User = Depends(get_current_user),
    ) -> HouseholdResponse:
        """Update household settings."""
        household_id = await _get_user_household_id(current_user.id)
        if not household_id:
            raise HTTPException(status_code=404, detail="Not a member of any household")

        household = await _get_household(household_id)
        if not household:
            raise HTTPException(status_code=404, detail="Household not found")

        my_role = await _get_user_role_in_household(current_user.id, household)
        if not my_role or not _check_permission(my_role, HouseholdRole.ADMIN):
            raise HTTPException(
                status_code=403,
                detail="Admin or Owner role required to update household settings",
            )

        # Apply updates
        if request.name is not None:
            household["name"] = request.name
        if request.address is not None:
            household["address"] = request.address
        if request.timezone is not None:
            household["timezone"] = request.timezone
        if request.guest_access_enabled is not None:
            household["guest_access_enabled"] = request.guest_access_enabled
        if request.guest_access_duration_hours is not None:
            household["guest_access_duration_hours"] = request.guest_access_duration_hours
        if request.require_2fa_for_device_control is not None:
            household["require_2fa_for_device_control"] = request.require_2fa_for_device_control

        household["updated_at"] = datetime.utcnow().isoformat()

        if not await _set_household(household_id, household):
            raise HTTPException(status_code=500, detail="Failed to update household")

        logger.info(f"Household updated: {household_id} by user {current_user.id}")

        return HouseholdResponse(
            household=HouseholdOut(
                id=household["id"],
                name=household["name"],
                owner_id=household["owner_id"],
                address=household.get("address"),
                timezone=household.get("timezone"),
                member_count=len(household.get("members", [])),
                guest_access_enabled=household.get("guest_access_enabled", True),
                guest_access_duration_hours=household.get("guest_access_duration_hours", 24),
                require_2fa_for_device_control=household.get(
                    "require_2fa_for_device_control", False
                ),
                created_at=datetime.fromisoformat(household["created_at"]),
                updated_at=(
                    datetime.fromisoformat(household["updated_at"])
                    if household.get("updated_at")
                    else None
                ),
            ),
            my_role=my_role,
        )

    @router.delete(
        "",
        responses=get_error_responses(401, 403, 404, 500),
        summary="Delete household",
        description="Delete the household. Only the Owner can delete.",
    )
    async def delete_household(
        current_user: User = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Delete the household."""
        household_id = await _get_user_household_id(current_user.id)
        if not household_id:
            raise HTTPException(status_code=404, detail="Not a member of any household")

        household = await _get_household(household_id)
        if not household:
            raise HTTPException(status_code=404, detail="Household not found")

        # Only owner can delete
        if household["owner_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Only the household owner can delete it")

        # Remove all members' household associations in parallel
        members = household.get("members", [])
        if members:
            # Clear associations
            await asyncio.gather(
                *[_set_user_household(member["user_id"], None) for member in members],
                return_exceptions=True,
            )
            # Notify non-owner members
            notifications = [
                _send_notification(
                    NotificationType.MEMBER_REMOVED,
                    household_id,
                    target_user_id=member["user_id"],
                    data={"household_name": household["name"], "reason": "deleted"},
                )
                for member in members
                if member["user_id"] != current_user.id
            ]
            if notifications:
                await asyncio.gather(*notifications, return_exceptions=True)

        # Delete household
        await _delete_household(household_id)

        logger.info(f"Household deleted: {household_id} by owner {current_user.id}")

        return {
            "success": True,
            "message": "Household deleted",
        }

    # =============================================================================
    # ROUTES - MEMBER MANAGEMENT
    # =============================================================================

    @router.get(
        "/members",
        response_model=MembersResponse,
        responses=get_error_responses(401, 404, 500),
        summary="List household members",
        description="Returns all members of the current household.",
    )
    async def list_members(
        current_user: User = Depends(get_current_user),
    ) -> MembersResponse:
        """List all members of the household."""
        household_id = await _get_user_household_id(current_user.id)
        if not household_id:
            raise HTTPException(status_code=404, detail="Not a member of any household")

        household = await _get_household(household_id)
        if not household:
            raise HTTPException(status_code=404, detail="Household not found")

        members = []
        for m in household.get("members", []):
            members.append(
                HouseholdMemberOut(
                    user_id=m["user_id"],
                    email=m["email"],
                    username=m["username"],
                    role=HouseholdRole(m["role"]),
                    joined_at=datetime.fromisoformat(m["joined_at"]),
                    expires_at=(
                        datetime.fromisoformat(m["expires_at"]) if m.get("expires_at") else None
                    ),
                    last_active=(
                        datetime.fromisoformat(m["last_active"]) if m.get("last_active") else None
                    ),
                    is_online=False,  # Would be set from presence service
                )
            )

        return MembersResponse(members=members, total=len(members))

    @router.delete(
        "/members/{user_id}",
        responses=get_error_responses(401, 403, 404, 500),
        summary="Remove member",
        description="""
        Remove a member from the household.

        - Admins can remove Members and Guests
        - Owners can remove anyone except themselves
        - Members can only remove themselves (leave)
        """,
    )
    async def remove_member(
        user_id: str,
        current_user: User = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Remove a member from the household."""
        household_id = await _get_user_household_id(current_user.id)
        if not household_id:
            raise HTTPException(status_code=404, detail="Not a member of any household")

        household = await _get_household(household_id)
        if not household:
            raise HTTPException(status_code=404, detail="Household not found")

        my_role = await _get_user_role_in_household(current_user.id, household)
        target_role = await _get_user_role_in_household(user_id, household)

        if not target_role:
            raise HTTPException(status_code=404, detail="Member not found")

        # Permission checks
        is_self = user_id == current_user.id

        if is_self:
            # Anyone can remove themselves (leave), except the owner
            if my_role == HouseholdRole.OWNER:
                raise HTTPException(
                    status_code=403,
                    detail="Owner cannot leave. Transfer ownership or delete household.",
                )
        else:
            # Removing someone else
            if not my_role or not _check_permission(my_role, HouseholdRole.ADMIN):
                raise HTTPException(
                    status_code=403, detail="Admin or Owner role required to remove members"
                )

            # Can't remove someone with same or higher role (except owner can remove admins)
            if my_role != HouseholdRole.OWNER and ROLE_HIERARCHY.get(
                target_role, 0
            ) >= ROLE_HIERARCHY.get(my_role, 0):
                raise HTTPException(
                    status_code=403, detail="Cannot remove member with equal or higher role"
                )

        # Remove member
        removed_member = None
        household["members"] = [m for m in household.get("members", []) if m["user_id"] != user_id]
        for m in household.get("members", []):
            if m["user_id"] == user_id:
                removed_member = m
                break

        household["updated_at"] = datetime.utcnow().isoformat()

        if not await _set_household(household_id, household):
            raise HTTPException(status_code=500, detail="Failed to update household")

        # Clear user's household reference
        await _set_user_household(user_id, None)

        # Send notifications
        notification_type = (
            NotificationType.MEMBER_LEFT if is_self else NotificationType.MEMBER_REMOVED
        )
        await _send_notification(
            notification_type,
            household_id,
            target_user_id=user_id,
            data={
                "household_name": household["name"],
                "removed_by": current_user.username if not is_self else None,
            },
        )

        # Notify owner if not the one doing the action
        if household["owner_id"] != current_user.id:
            await _send_notification(
                notification_type,
                household_id,
                target_user_id=household["owner_id"],
                data={
                    "member_email": removed_member["email"] if removed_member else user_id,
                    "removed_by": current_user.username,
                },
            )

        logger.info(
            f"Member removed: {user_id} from household {household_id} "
            f"by {current_user.id} (self={is_self})"
        )

        return {
            "success": True,
            "message": "Left household" if is_self else "Member removed",
        }

    @router.put(
        "/members/{user_id}/role",
        responses=get_error_responses(401, 403, 404, 422, 500),
        summary="Change member role",
        description="""
        Change a member's role in the household.

        - Only Owner can promote to Admin
        - Admins can change Member/Guest roles
        - Cannot change your own role
        - Cannot change the Owner's role
        """,
    )
    async def change_member_role(
        user_id: str,
        request: RoleChangeRequest,
        current_user: User = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Change a member's role."""
        household_id = await _get_user_household_id(current_user.id)
        if not household_id:
            raise HTTPException(status_code=404, detail="Not a member of any household")

        household = await _get_household(household_id)
        if not household:
            raise HTTPException(status_code=404, detail="Household not found")

        my_role = await _get_user_role_in_household(current_user.id, household)
        target_role = await _get_user_role_in_household(user_id, household)

        if not target_role:
            raise HTTPException(status_code=404, detail="Member not found")

        # Permission checks
        if user_id == current_user.id:
            raise HTTPException(status_code=403, detail="Cannot change your own role")

        if target_role == HouseholdRole.OWNER:
            raise HTTPException(
                status_code=403,
                detail="Cannot change Owner's role. Use transfer ownership instead.",
            )

        if request.role == HouseholdRole.OWNER:
            raise HTTPException(
                status_code=403,
                detail="Cannot promote to Owner. Use transfer ownership instead.",
            )

        if not my_role or not _check_permission(my_role, HouseholdRole.ADMIN):
            raise HTTPException(status_code=403, detail="Admin or Owner role required")

        # Only owner can promote to admin
        if request.role == HouseholdRole.ADMIN and my_role != HouseholdRole.OWNER:
            raise HTTPException(status_code=403, detail="Only Owner can promote to Admin")

        # Update role
        old_role = None
        for member in household.get("members", []):
            if member["user_id"] == user_id:
                old_role = member["role"]
                member["role"] = request.role.value
                # Clear expiration if promoting from guest
                if old_role == HouseholdRole.GUEST.value and request.role != HouseholdRole.GUEST:
                    member["expires_at"] = None
                break

        household["updated_at"] = datetime.utcnow().isoformat()

        if not await _set_household(household_id, household):
            raise HTTPException(status_code=500, detail="Failed to update household")

        # Notify affected member
        await _send_notification(
            NotificationType.ROLE_CHANGED,
            household_id,
            target_user_id=user_id,
            data={
                "old_role": old_role,
                "new_role": request.role.value,
                "changed_by": current_user.username,
            },
        )

        logger.info(
            f"Role changed: {user_id} from {old_role} to {request.role.value} "
            f"in household {household_id} by {current_user.id}"
        )

        return {
            "success": True,
            "message": f"Role changed to {request.role.value}",
            "old_role": old_role,
            "new_role": request.role.value,
        }

    # =============================================================================
    # ROUTES - INVITATIONS
    # =============================================================================

    @router.post(
        "/invite",
        response_model=InvitationOut,
        responses=get_error_responses(400, 401, 403, 404, 409, 422, 500),
        summary="Send invitation",
        description="""
        Send an invitation to join the household.

        - Admins can invite Members and Guests
        - Owners can invite anyone
        - An invitation code is generated and can be shared
        """,
    )
    async def send_invitation(
        request: InviteRequest,
        current_user: User = Depends(get_current_user),
    ) -> InvitationOut:
        """Send a household invitation."""
        household_id = await _get_user_household_id(current_user.id)
        if not household_id:
            raise HTTPException(status_code=404, detail="Not a member of any household")

        household = await _get_household(household_id)
        if not household:
            raise HTTPException(status_code=404, detail="Household not found")

        my_role = await _get_user_role_in_household(current_user.id, household)

        # Permission checks
        if not my_role or not _check_permission(my_role, HouseholdRole.ADMIN):
            raise HTTPException(
                status_code=403, detail="Admin or Owner role required to invite members"
            )

        # Only owner can invite admins
        if request.role == HouseholdRole.ADMIN and my_role != HouseholdRole.OWNER:
            raise HTTPException(status_code=403, detail="Only Owner can invite Admins")

        # Cannot invite as owner
        if request.role == HouseholdRole.OWNER:
            raise HTTPException(status_code=403, detail="Cannot invite as Owner")

        # Check if guest access is enabled
        if request.role == HouseholdRole.GUEST and not household.get("guest_access_enabled", True):
            raise HTTPException(status_code=403, detail="Guest access is disabled")

        # Check if already a member
        for member in household.get("members", []):
            if member["email"].lower() == request.email.lower():
                raise HTTPException(
                    status_code=409, detail="User is already a member of this household"
                )

        # Check for existing pending invitation
        existing_invitations = await _get_user_invitations(request.email)
        for inv in existing_invitations:
            if (
                inv.get("household_id") == household_id
                and inv.get("status") == InvitationStatus.PENDING.value
            ):
                raise HTTPException(
                    status_code=409, detail="Pending invitation already exists for this email"
                )

        # Create invitation
        invitation_id = str(uuid.uuid4())
        code = _generate_invitation_code()
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=request.expires_in_hours)

        invitation = {
            "id": invitation_id,
            "household_id": household_id,
            "household_name": household["name"],
            "email": request.email,
            "role": request.role.value,
            "status": InvitationStatus.PENDING.value,
            "code": code,
            "invited_by": current_user.username,
            "invited_by_id": current_user.id,
            "message": request.message,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        if not await _set_invitation(invitation_id, invitation):
            raise HTTPException(status_code=500, detail="Failed to create invitation")

        # Send notification (would trigger email in production)
        await _send_notification(
            NotificationType.INVITATION_SENT,
            household_id,
            target_email=request.email,
            data={
                "household_name": household["name"],
                "invited_by": current_user.username,
                "role": request.role.value,
                "code": code,
                "expires_at": expires_at.isoformat(),
            },
        )

        logger.info(
            f"Invitation sent: {invitation_id} to {request.email} "
            f"for household {household_id} by {current_user.id}"
        )

        return InvitationOut(
            id=invitation_id,
            household_id=household_id,
            household_name=household["name"],
            email=request.email,
            role=request.role,
            status=InvitationStatus.PENDING,
            invited_by=current_user.username,
            message=request.message,
            created_at=now,
            expires_at=expires_at,
        )

    @router.get(
        "/invitations",
        response_model=InvitationsResponse,
        responses=get_error_responses(401, 404, 500),
        summary="List pending invitations",
        description="""
        List invitations.

        For household members: Shows all invitations sent from the household.
        For non-members: Shows invitations addressed to the user's email.
        """,
    )
    async def list_invitations(
        current_user: User = Depends(get_current_user),
        status: InvitationStatus | None = Query(None, description="Filter by status"),
    ) -> InvitationsResponse:
        """List invitations."""
        household_id = await _get_user_household_id(current_user.id)

        if household_id:
            # User is in a household - show household's invitations
            invitations_data = await _get_household_invitations(household_id)
        else:
            # User is not in a household - show their invitations
            invitations_data = await _get_user_invitations(current_user.email)

        # Filter by status if provided
        if status:
            invitations_data = [
                inv for inv in invitations_data if inv.get("status") == status.value
            ]

        # Check for expired invitations
        now = datetime.utcnow()
        invitations = []
        for inv in invitations_data:
            expires_at = datetime.fromisoformat(inv["expires_at"])
            if expires_at < now and inv["status"] == InvitationStatus.PENDING.value:
                inv["status"] = InvitationStatus.EXPIRED.value
                await _set_invitation(inv["id"], inv)

            invitations.append(
                InvitationOut(
                    id=inv["id"],
                    household_id=inv["household_id"],
                    household_name=inv["household_name"],
                    email=inv["email"],
                    role=HouseholdRole(inv["role"]),
                    status=InvitationStatus(inv["status"]),
                    invited_by=inv["invited_by"],
                    message=inv.get("message"),
                    created_at=datetime.fromisoformat(inv["created_at"]),
                    expires_at=expires_at,
                )
            )

        return InvitationsResponse(invitations=invitations, total=len(invitations))

    @router.post(
        "/join",
        response_model=HouseholdResponse,
        responses=get_error_responses(400, 401, 404, 409, 410, 500),
        summary="Join household",
        description="Accept an invitation and join a household using the invitation code.",
    )
    async def join_household(
        request: JoinRequest,
        current_user: User = Depends(get_current_user),
    ) -> HouseholdResponse:
        """Join a household using an invitation code."""
        # Check if already in a household
        existing_household_id = await _get_user_household_id(current_user.id)
        if existing_household_id:
            raise HTTPException(
                status_code=409,
                detail="Already a member of a household. Leave current household first.",
            )

        # Find invitation by code
        invitation = await _get_invitation_by_code(request.code)
        if not invitation:
            raise HTTPException(status_code=404, detail="Invalid invitation code")

        # Check invitation status
        if invitation["status"] != InvitationStatus.PENDING.value:
            raise HTTPException(
                status_code=410,
                detail=f"Invitation is {invitation['status']}",
            )

        # Check expiration
        expires_at = datetime.fromisoformat(invitation["expires_at"])
        if expires_at < datetime.utcnow():
            invitation["status"] = InvitationStatus.EXPIRED.value
            await _set_invitation(invitation["id"], invitation)
            raise HTTPException(status_code=410, detail="Invitation has expired")

        # Check email matches (optional - can be removed to allow code-only joins)
        if invitation["email"].lower() != current_user.email.lower():
            raise HTTPException(
                status_code=403,
                detail="Invitation was sent to a different email address",
            )

        # Get household
        household = await _get_household(invitation["household_id"])
        if not household:
            raise HTTPException(status_code=404, detail="Household no longer exists")

        # Add member
        now = datetime.utcnow()
        role = HouseholdRole(invitation["role"])

        # Calculate expiration for guests
        expires_at_member = None
        if role == HouseholdRole.GUEST:
            duration_hours = household.get("guest_access_duration_hours", 24)
            expires_at_member = (now + timedelta(hours=duration_hours)).isoformat()

        household["members"].append(
            {
                "user_id": current_user.id,
                "email": current_user.email,
                "username": current_user.username,
                "role": role.value,
                "joined_at": now.isoformat(),
                "expires_at": expires_at_member,
                "last_active": now.isoformat(),
            }
        )
        household["updated_at"] = now.isoformat()

        if not await _set_household(invitation["household_id"], household):
            raise HTTPException(status_code=500, detail="Failed to join household")

        # Update user's household reference
        await _set_user_household(current_user.id, invitation["household_id"])

        # Update invitation status
        invitation["status"] = InvitationStatus.ACCEPTED.value
        await _set_invitation(invitation["id"], invitation)

        # Send notifications
        await _send_notification(
            NotificationType.INVITATION_ACCEPTED,
            invitation["household_id"],
            target_user_id=invitation["invited_by_id"],
            data={
                "member_email": current_user.email,
                "member_username": current_user.username,
                "role": role.value,
            },
        )

        await _send_notification(
            NotificationType.MEMBER_JOINED,
            invitation["household_id"],
            target_user_id=household["owner_id"],
            data={
                "member_email": current_user.email,
                "member_username": current_user.username,
                "role": role.value,
            },
        )

        logger.info(
            f"User {current_user.id} joined household {invitation['household_id']} as {role.value}"
        )

        return HouseholdResponse(
            household=HouseholdOut(
                id=household["id"],
                name=household["name"],
                owner_id=household["owner_id"],
                address=household.get("address"),
                timezone=household.get("timezone"),
                member_count=len(household.get("members", [])),
                guest_access_enabled=household.get("guest_access_enabled", True),
                guest_access_duration_hours=household.get("guest_access_duration_hours", 24),
                require_2fa_for_device_control=household.get(
                    "require_2fa_for_device_control", False
                ),
                created_at=datetime.fromisoformat(household["created_at"]),
                updated_at=now,
            ),
            my_role=role,
        )

    @router.delete(
        "/invitations/{invitation_id}",
        responses=get_error_responses(401, 403, 404, 500),
        summary="Revoke invitation",
        description="Revoke a pending invitation. Requires Admin or Owner role.",
    )
    async def revoke_invitation(
        invitation_id: str,
        current_user: User = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Revoke a pending invitation."""
        household_id = await _get_user_household_id(current_user.id)
        if not household_id:
            raise HTTPException(status_code=404, detail="Not a member of any household")

        household = await _get_household(household_id)
        if not household:
            raise HTTPException(status_code=404, detail="Household not found")

        my_role = await _get_user_role_in_household(current_user.id, household)
        if not my_role or not _check_permission(my_role, HouseholdRole.ADMIN):
            raise HTTPException(status_code=403, detail="Admin or Owner role required")

        invitation = await _get_invitation(invitation_id)
        if not invitation or invitation.get("household_id") != household_id:
            raise HTTPException(status_code=404, detail="Invitation not found")

        if invitation["status"] != InvitationStatus.PENDING.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot revoke invitation with status: {invitation['status']}",
            )

        invitation["status"] = InvitationStatus.REVOKED.value
        await _set_invitation(invitation_id, invitation)

        logger.info(f"Invitation revoked: {invitation_id} by user {current_user.id}")

        return {
            "success": True,
            "message": "Invitation revoked",
        }

    # =============================================================================
    # ROUTES - OWNERSHIP TRANSFER
    # =============================================================================

    @router.post(
        "/transfer-ownership/{user_id}",
        responses=get_error_responses(401, 403, 404, 500),
        summary="Transfer ownership",
        description="Transfer household ownership to another member. Only Owner can do this.",
    )
    async def transfer_ownership(
        user_id: str,
        current_user: User = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Transfer household ownership."""
        household_id = await _get_user_household_id(current_user.id)
        if not household_id:
            raise HTTPException(status_code=404, detail="Not a member of any household")

        household = await _get_household(household_id)
        if not household:
            raise HTTPException(status_code=404, detail="Household not found")

        # Only owner can transfer
        if household["owner_id"] != current_user.id:
            raise HTTPException(
                status_code=403, detail="Only the household owner can transfer ownership"
            )

        # Check target is a member
        target_role = await _get_user_role_in_household(user_id, household)
        if not target_role:
            raise HTTPException(status_code=404, detail="Target user is not a member")

        if user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot transfer ownership to yourself")

        # Update roles
        for member in household.get("members", []):
            if member["user_id"] == user_id:
                member["role"] = HouseholdRole.OWNER.value
            elif member["user_id"] == current_user.id:
                member["role"] = HouseholdRole.ADMIN.value

        household["owner_id"] = user_id
        household["updated_at"] = datetime.utcnow().isoformat()

        if not await _set_household(household_id, household):
            raise HTTPException(status_code=500, detail="Failed to transfer ownership")

        # Notify new owner
        await _send_notification(
            NotificationType.ROLE_CHANGED,
            household_id,
            target_user_id=user_id,
            data={
                "old_role": target_role.value,
                "new_role": HouseholdRole.OWNER.value,
                "changed_by": current_user.username,
                "is_ownership_transfer": True,
            },
        )

        logger.info(
            f"Ownership transferred: household {household_id} from {current_user.id} to {user_id}"
        )

        return {
            "success": True,
            "message": f"Ownership transferred to user {user_id}",
            "new_owner_id": user_id,
            "your_new_role": HouseholdRole.ADMIN.value,
        }

    # =============================================================================
    # ROUTES - LEAVE HOUSEHOLD (convenience endpoint)
    # =============================================================================

    @router.post(
        "/leave",
        responses=get_error_responses(401, 403, 404, 500),
        summary="Leave household",
        description="Leave the current household. Owners must transfer ownership first.",
    )
    async def leave_household(
        current_user: User = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Leave the current household."""
        # Delegate to remove_member with self
        return await remove_member(current_user.id, current_user)

    return router


__all__ = ["get_router"]
