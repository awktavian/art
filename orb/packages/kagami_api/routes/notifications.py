"""Push Notification API Routes.

Provides REST endpoints for push notification management:
- Device token registration (APNs/FCM)
- Notification sending (admin)
- Preference management
- Delivery tracking

Created: December 31, 2025 (RALPH Week 3)
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from kagami_api.auth import User, require_admin, require_auth

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/notifications",
    tags=["Push Notifications"],
    dependencies=[Depends(require_auth)],
)


# =============================================================================
# ENUMS
# =============================================================================


class DevicePlatform(str, Enum):
    """Device platform for push notifications."""

    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class NotificationType(str, Enum):
    """Notification type categories."""

    SMART_HOME_ALERT = "smart_home_alert"
    ROUTINE_REMINDER = "routine_reminder"
    SECURITY_ALERT = "security_alert"
    SYSTEM_UPDATE = "system_update"


class NotificationPriority(str, Enum):
    """Notification priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


# =============================================================================
# SCHEMAS
# =============================================================================


class DeviceRegistration(BaseModel):
    """Request to register a device for push notifications."""

    device_token: str = Field(..., min_length=10, description="APNs or FCM device token")
    platform: DevicePlatform = Field(..., description="Device platform (ios, android, web)")
    device_id: str = Field(..., description="Unique device identifier")
    device_name: str | None = Field(None, description="Human-readable device name")
    app_version: str | None = Field(None, description="App version")


class DeviceRegistrationResponse(BaseModel):
    """Response from device registration."""

    success: bool
    device_id: str
    platform: str
    registered_at: str


class NotificationPreferences(BaseModel):
    """User notification preferences."""

    smart_home_alerts: bool = Field(True, description="Receive smart home alerts")
    routine_reminders: bool = Field(True, description="Receive routine reminders")
    security_alerts: bool = Field(True, description="Receive security alerts")
    system_updates: bool = Field(True, description="Receive system updates")
    quiet_hours_enabled: bool = Field(False, description="Enable quiet hours")
    quiet_hours_start: str | None = Field(None, description="Quiet hours start (HH:MM)")
    quiet_hours_end: str | None = Field(None, description="Quiet hours end (HH:MM)")


class SendNotificationRequest(BaseModel):
    """Request to send a push notification (admin only)."""

    title: str = Field(..., min_length=1, max_length=100, description="Notification title")
    body: str = Field(..., min_length=1, max_length=500, description="Notification body")
    notification_type: NotificationType = Field(..., description="Notification type")
    priority: NotificationPriority = Field(
        NotificationPriority.NORMAL, description="Notification priority"
    )
    user_ids: list[str] | None = Field(None, description="Target user IDs (None = all users)")
    data: dict[str, Any] | None = Field(None, description="Custom data payload")
    action_url: str | None = Field(None, description="Deep link URL for notification action")
    category: str | None = Field(None, description="Notification category for actions")


class SendNotificationResponse(BaseModel):
    """Response from sending notification."""

    success: bool
    notification_id: str
    recipients: int
    delivered: int
    failed: int


class NotificationDeliveryStatus(BaseModel):
    """Delivery status for a notification."""

    notification_id: str
    status: str
    delivered_at: str | None
    read_at: str | None
    platform: str
    device_id: str


# =============================================================================
# SERVICE DEPENDENCY
# =============================================================================


async def get_push_service() -> Any:
    """Get the push notification service."""
    try:
        from kagami.core.services.push_notifications import get_push_notification_service

        return await get_push_notification_service()
    except ImportError as e:
        logger.warning(f"Push notification service not available: {e}")
        raise HTTPException(
            status_code=503, detail="Push notification service not available"
        ) from e


# =============================================================================
# DEVICE REGISTRATION ROUTES
# =============================================================================


@router.post("/register", response_model=DeviceRegistrationResponse)
async def register_device(
    registration: DeviceRegistration,
    user: User = Depends(require_auth),
) -> DeviceRegistrationResponse:
    """Register a device for push notifications.

    This endpoint should be called when:
    - App launches for the first time
    - Device token is refreshed
    - User logs in on a new device

    The device token will be associated with the authenticated user.
    """
    service = await get_push_service()

    try:
        await service.register_device(
            user_id=user.id,
            device_token=registration.device_token,
            platform=registration.platform.value,
            device_id=registration.device_id,
            device_name=registration.device_name,
            app_version=registration.app_version,
        )

        logger.info(
            f"Device registered: {registration.device_id} for user {user.id} "
            f"({registration.platform.value})"
        )

        return DeviceRegistrationResponse(
            success=True,
            device_id=registration.device_id,
            platform=registration.platform.value,
            registered_at=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Device registration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {e}") from e


@router.delete("/unregister")
async def unregister_device(
    device_id: str = Query(..., description="Device ID to unregister"),
    user: User = Depends(require_auth),
) -> dict[str, Any]:
    """Unregister a device from push notifications.

    This should be called when:
    - User logs out
    - User disables notifications
    - App is uninstalled (if detectable)
    """
    service = await get_push_service()

    try:
        result = await service.unregister_device(
            user_id=user.id,
            device_id=device_id,
        )

        logger.info(f"Device unregistered: {device_id} for user {user.id}")

        return {
            "success": result,
            "device_id": device_id,
            "unregistered_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Device unregistration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Unregistration failed: {e}") from e


@router.get("/devices")
async def list_devices(
    user: User = Depends(require_auth),
) -> dict[str, Any]:
    """List all registered devices for the current user."""
    service = await get_push_service()

    try:
        devices = await service.get_user_devices(user.id)

        return {
            "user_id": user.id,
            "device_count": len(devices),
            "devices": devices,
        }

    except Exception as e:
        logger.error(f"Failed to list devices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list devices: {e}") from e


# =============================================================================
# NOTIFICATION PREFERENCES ROUTES
# =============================================================================


@router.get("/preferences", response_model=NotificationPreferences)
async def get_preferences(
    user: User = Depends(require_auth),
) -> NotificationPreferences:
    """Get notification preferences for the current user."""
    service = await get_push_service()

    try:
        prefs = await service.get_user_preferences(user.id)

        return NotificationPreferences(
            smart_home_alerts=prefs.get("smart_home_alerts", True),
            routine_reminders=prefs.get("routine_reminders", True),
            security_alerts=prefs.get("security_alerts", True),
            system_updates=prefs.get("system_updates", True),
            quiet_hours_enabled=prefs.get("quiet_hours_enabled", False),
            quiet_hours_start=prefs.get("quiet_hours_start"),
            quiet_hours_end=prefs.get("quiet_hours_end"),
        )

    except Exception as e:
        logger.error(f"Failed to get preferences: {e}")
        # Return defaults on error
        return NotificationPreferences()


@router.put("/preferences", response_model=NotificationPreferences)
async def update_preferences(
    preferences: NotificationPreferences,
    user: User = Depends(require_auth),
) -> NotificationPreferences:
    """Update notification preferences for the current user."""
    service = await get_push_service()

    try:
        await service.update_user_preferences(
            user_id=user.id,
            preferences=preferences.model_dump(),
        )

        logger.info(f"Preferences updated for user {user.id}")

        return preferences

    except Exception as e:
        logger.error(f"Failed to update preferences: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update preferences: {e}") from e


# =============================================================================
# NOTIFICATION SENDING ROUTES (ADMIN)
# =============================================================================


@router.post("/send", response_model=SendNotificationResponse)
async def send_notification(
    request: SendNotificationRequest,
    user: User = Depends(require_admin),
) -> SendNotificationResponse:
    """Send a push notification to users (admin only).

    This endpoint allows admins to send targeted or broadcast notifications.
    The notification will be delivered to all registered devices of the target users.
    """
    service = await get_push_service()

    try:
        result = await service.send_notification(
            title=request.title,
            body=request.body,
            notification_type=request.notification_type.value,
            priority=request.priority.value,
            user_ids=request.user_ids,
            data=request.data,
            action_url=request.action_url,
            category=request.category,
        )

        logger.info(
            f"Notification sent by {user.username}: {request.title} "
            f"(type={request.notification_type.value}, recipients={result.get('recipients', 0)})"
        )

        return SendNotificationResponse(
            success=True,
            notification_id=result.get("notification_id", ""),
            recipients=result.get("recipients", 0),
            delivered=result.get("delivered", 0),
            failed=result.get("failed", 0),
        )

    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send notification: {e}") from e


@router.post("/send-to-device")
async def send_to_device(
    device_id: str = Query(..., description="Target device ID"),
    title: str = Query(..., description="Notification title"),
    body: str = Query(..., description="Notification body"),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Send a push notification to a specific device (admin only).

    Useful for testing and targeted debugging.
    """
    service = await get_push_service()

    try:
        result = await service.send_to_device(
            device_id=device_id,
            title=title,
            body=body,
        )

        return {
            "success": result.get("success", False),
            "device_id": device_id,
            "sent_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to send to device: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send: {e}") from e


# =============================================================================
# DELIVERY TRACKING ROUTES
# =============================================================================


@router.get("/history")
async def get_notification_history(
    limit: int = Query(50, ge=1, le=200, description="Number of notifications to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    user: User = Depends(require_auth),
) -> dict[str, Any]:
    """Get notification history for the current user."""
    service = await get_push_service()

    try:
        history = await service.get_notification_history(
            user_id=user.id,
            limit=limit,
            offset=offset,
        )

        return {
            "user_id": user.id,
            "count": len(history),
            "offset": offset,
            "notifications": history,
        }

    except Exception as e:
        logger.error(f"Failed to get notification history: {e}")
        return {"user_id": user.id, "count": 0, "offset": offset, "notifications": []}


@router.post("/mark-read/{notification_id}")
async def mark_notification_read(
    notification_id: str,
    user: User = Depends(require_auth),
) -> dict[str, Any]:
    """Mark a notification as read."""
    service = await get_push_service()

    try:
        await service.mark_notification_read(
            user_id=user.id,
            notification_id=notification_id,
        )

        return {
            "success": True,
            "notification_id": notification_id,
            "read_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to mark notification read: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mark read: {e}") from e


@router.get("/unread-count")
async def get_unread_count(
    user: User = Depends(require_auth),
) -> dict[str, Any]:
    """Get count of unread notifications."""
    service = await get_push_service()

    try:
        count = await service.get_unread_count(user.id)

        return {
            "user_id": user.id,
            "unread_count": count,
        }

    except Exception as e:
        logger.error(f"Failed to get unread count: {e}")
        return {"user_id": user.id, "unread_count": 0}


# =============================================================================
# SERVICE STATUS ROUTES
# =============================================================================


@router.get("/status")
async def get_service_status(
    user: User = Depends(require_auth),
) -> dict[str, Any]:
    """Get push notification service status."""
    try:
        service = await get_push_service()
        stats = await service.get_stats()

        return {
            "available": True,
            "apns_connected": stats.get("apns_connected", False),
            "fcm_connected": stats.get("fcm_connected", False),
            "total_devices": stats.get("total_devices", 0),
            "notifications_sent_24h": stats.get("notifications_sent_24h", 0),
            "delivery_rate": stats.get("delivery_rate", 0.0),
        }

    except HTTPException:
        return {
            "available": False,
            "apns_connected": False,
            "fcm_connected": False,
            "total_devices": 0,
            "notifications_sent_24h": 0,
            "delivery_rate": 0.0,
        }
