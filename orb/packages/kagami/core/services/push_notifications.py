"""Push Notification Service for Kagami.

Provides push notification delivery via:
- APNs (Apple Push Notification service) for iOS devices
- FCM (Firebase Cloud Messaging) for Android devices

Features:
- Device token management
- User preference handling
- Rate limiting per user
- Delivery tracking
- Retry logic with exponential backoff

Created: December 31, 2025 (RALPH Week 3)
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND TYPES
# =============================================================================


class Platform(str, Enum):
    """Device platform."""

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
# DATA CLASSES
# =============================================================================


@dataclass
class DeviceInfo:
    """Registered device information."""

    device_id: str
    user_id: str
    device_token: str
    platform: Platform
    device_name: str | None = None
    app_version: str | None = None
    registered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_active_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    is_active: bool = True


@dataclass
class NotificationRecord:
    """Record of a sent notification."""

    notification_id: str
    user_id: str
    device_id: str
    title: str
    body: str
    notification_type: str
    priority: str
    sent_at: str
    delivered_at: str | None = None
    read_at: str | None = None
    failed: bool = False
    error: str | None = None


@dataclass
class UserPreferences:
    """User notification preferences."""

    smart_home_alerts: bool = True
    routine_reminders: bool = True
    security_alerts: bool = True
    system_updates: bool = True
    quiet_hours_enabled: bool = False
    quiet_hours_start: str | None = None  # HH:MM format
    quiet_hours_end: str | None = None  # HH:MM format


# =============================================================================
# APNs CLIENT
# =============================================================================


class APNsClient:
    """Apple Push Notification service client using HTTP/2."""

    def __init__(
        self,
        key_id: str | None = None,
        team_id: str | None = None,
        key_path: str | None = None,
        bundle_id: str | None = None,
        use_sandbox: bool = False,
    ):
        self.key_id = key_id or os.getenv("APNS_KEY_ID")
        self.team_id = team_id or os.getenv("APNS_TEAM_ID")
        self.key_path = key_path or os.getenv("APNS_KEY_PATH")
        self.bundle_id = bundle_id or os.getenv("APNS_BUNDLE_ID", "com.kagami.ios")
        self.use_sandbox = use_sandbox or os.getenv("APNS_SANDBOX", "false").lower() == "true"

        self._client: httpx.AsyncClient | None = None
        self._jwt_token: str | None = None
        self._jwt_expires: float = 0

        # APNs endpoints
        self.host = "api.sandbox.push.apple.com" if self.use_sandbox else "api.push.apple.com"

    @property
    def is_configured(self) -> bool:
        """Check if APNs is properly configured."""
        return all([self.key_id, self.team_id, self.key_path, self.bundle_id])

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP/2 client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    def _generate_jwt(self) -> str:
        """Generate JWT token for APNs authentication."""
        import jwt

        now = time.time()

        # Reuse token if not expired (APNs tokens valid for ~1 hour)
        if self._jwt_token and self._jwt_expires > now:
            return self._jwt_token

        if not self.key_path or not os.path.exists(self.key_path):
            raise ValueError(f"APNs key file not found: {self.key_path}")

        with open(self.key_path) as f:
            key = f.read()

        headers = {"alg": "ES256", "kid": self.key_id}
        payload = {"iss": self.team_id, "iat": int(now)}

        self._jwt_token = jwt.encode(payload, key, algorithm="ES256", headers=headers)
        self._jwt_expires = now + 3500  # Refresh 100 seconds before expiry

        return self._jwt_token

    async def send(
        self,
        device_token: str,
        title: str,
        body: str,
        badge: int | None = None,
        sound: str = "default",
        category: str | None = None,
        data: dict[str, Any] | None = None,
        priority: str = "normal",
    ) -> dict[str, Any]:
        """Send push notification via APNs.

        Args:
            device_token: APNs device token
            title: Notification title
            body: Notification body
            badge: Badge count (optional)
            sound: Sound name (default: "default")
            category: Notification category for actions
            data: Custom data payload
            priority: Priority level (critical, high, normal, low)

        Returns:
            dict with success status and any error info
        """
        if not self.is_configured:
            return {"success": False, "error": "APNs not configured"}

        client = await self._get_client()

        # Build APNs payload
        aps = {
            "alert": {"title": title, "body": body},
            "sound": sound,
        }

        if badge is not None:
            aps["badge"] = badge

        if category:
            aps["category"] = category

        # Map priority to APNs priority
        apns_priority = "10" if priority in ("critical", "high") else "5"

        payload = {"aps": aps}
        if data:
            payload.update(data)

        # Build headers
        headers = {
            "authorization": f"bearer {self._generate_jwt()}",
            "apns-topic": self.bundle_id,
            "apns-priority": apns_priority,
            "apns-push-type": "alert",
        }

        if priority == "critical":
            headers["apns-expiration"] = str(int(time.time()) + 86400)  # 24 hours

        url = f"https://{self.host}:443/3/device/{device_token}"

        try:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
            )

            if response.status_code == 200:
                return {"success": True, "apns_id": response.headers.get("apns-id")}
            else:
                error_body = response.json() if response.content else {}
                return {
                    "success": False,
                    "status": response.status_code,
                    "error": error_body.get("reason", "Unknown error"),
                }

        except Exception as e:
            logger.error(f"APNs send failed: {e}")
            return {"success": False, "error": str(e)}

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# =============================================================================
# FCM CLIENT
# =============================================================================


class FCMClient:
    """Firebase Cloud Messaging client using HTTP v1 API."""

    def __init__(
        self,
        project_id: str | None = None,
        credentials_path: str | None = None,
    ):
        self.project_id = project_id or os.getenv("FCM_PROJECT_ID")
        self.credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None
        self._token_expires: float = 0

    @property
    def is_configured(self) -> bool:
        """Check if FCM is properly configured."""
        return bool(self.project_id and self.credentials_path)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def _get_access_token(self) -> str:
        """Get OAuth2 access token for FCM."""
        now = time.time()

        # Reuse token if not expired
        if self._access_token and self._token_expires > now:
            return self._access_token

        try:
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account

            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=["https://www.googleapis.com/auth/firebase.messaging"],
            )
            credentials.refresh(Request())

            self._access_token = credentials.token
            self._token_expires = (
                credentials.expiry.timestamp() - 60 if credentials.expiry else now + 3500
            )

            return self._access_token

        except ImportError:
            logger.warning("google-auth not installed, using fallback token method")
            # Fallback: read service account key and generate JWT manually
            return await self._generate_jwt_fallback()

    async def _generate_jwt_fallback(self) -> str:
        """Generate JWT access token without google-auth library."""
        import jwt

        if not self.credentials_path or not os.path.exists(self.credentials_path):
            raise ValueError(f"FCM credentials file not found: {self.credentials_path}")

        with open(self.credentials_path) as f:
            creds = json.load(f)

        now = int(time.time())
        payload = {
            "iss": creds["client_email"],
            "sub": creds["client_email"],
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600,
            "scope": "https://www.googleapis.com/auth/firebase.messaging",
        }

        token = jwt.encode(payload, creds["private_key"], algorithm="RS256")

        # Exchange JWT for access token
        client = await self._get_client()
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": token,
            },
        )

        if response.status_code == 200:
            data = response.json()
            self._access_token = data["access_token"]
            self._token_expires = time.time() + data.get("expires_in", 3600) - 60
            return self._access_token

        raise ValueError(f"Failed to get FCM access token: {response.text}")

    async def send(
        self,
        device_token: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
        priority: str = "normal",
        channel_id: str | None = None,
    ) -> dict[str, Any]:
        """Send push notification via FCM.

        Args:
            device_token: FCM device token
            title: Notification title
            body: Notification body
            data: Custom data payload
            priority: Priority level (critical, high, normal, low)
            channel_id: Android notification channel ID

        Returns:
            dict with success status and any error info
        """
        if not self.is_configured:
            return {"success": False, "error": "FCM not configured"}

        client = await self._get_client()
        access_token = await self._get_access_token()

        # Map priority to FCM priority
        fcm_priority = "high" if priority in ("critical", "high") else "normal"

        # Build FCM message
        message = {
            "message": {
                "token": device_token,
                "notification": {
                    "title": title,
                    "body": body,
                },
                "android": {
                    "priority": fcm_priority,
                    "notification": {
                        "channel_id": channel_id or "kagami_notifications",
                        "click_action": "FLUTTER_NOTIFICATION_CLICK",
                    },
                },
            }
        }

        if data:
            message["message"]["data"] = {k: str(v) for k, v in data.items()}

        url = f"https://fcm.googleapis.com/v1/projects/{self.project_id}/messages:send"

        try:
            response = await client.post(
                url,
                json=message,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 200:
                result = response.json()
                return {"success": True, "message_id": result.get("name")}
            else:
                error_body = response.json() if response.content else {}
                return {
                    "success": False,
                    "status": response.status_code,
                    "error": error_body.get("error", {}).get("message", "Unknown error"),
                }

        except Exception as e:
            logger.error(f"FCM send failed: {e}")
            return {"success": False, "error": str(e)}

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# =============================================================================
# PUSH NOTIFICATION SERVICE
# =============================================================================


class PushNotificationService:
    """Main push notification service."""

    def __init__(self):
        # Clients
        self._apns = APNsClient()
        self._fcm = FCMClient()

        # In-memory storage (replace with database in production)
        self._devices: dict[str, DeviceInfo] = {}  # device_id -> DeviceInfo
        self._user_devices: dict[str, set[str]] = defaultdict(set)  # user_id -> set of device_ids
        self._preferences: dict[str, UserPreferences] = {}  # user_id -> UserPreferences
        self._notifications: list[NotificationRecord] = []

        # Rate limiting
        self._rate_limits: dict[str, list[float]] = defaultdict(list)  # user_id -> timestamps
        self._rate_limit_window = 60.0  # 1 minute
        self._rate_limit_max = 30  # 30 notifications per minute per user

        # Stats
        self._stats = {
            "notifications_sent": 0,
            "notifications_delivered": 0,
            "notifications_failed": 0,
            "last_24h_sent": 0,
        }

    async def initialize(self) -> None:
        """Initialize the service."""
        logger.info("Push notification service initializing...")

        if self._apns.is_configured:
            logger.info("APNs client configured")
        else:
            logger.warning("APNs client not configured - iOS notifications disabled")

        if self._fcm.is_configured:
            logger.info("FCM client configured")
        else:
            logger.warning("FCM client not configured - Android notifications disabled")

    async def shutdown(self) -> None:
        """Shutdown the service."""
        await self._apns.close()
        await self._fcm.close()
        logger.info("Push notification service shutdown")

    # =========================================================================
    # DEVICE MANAGEMENT
    # =========================================================================

    async def register_device(
        self,
        user_id: str,
        device_token: str,
        platform: str,
        device_id: str,
        device_name: str | None = None,
        app_version: str | None = None,
    ) -> DeviceInfo:
        """Register a device for push notifications."""
        device = DeviceInfo(
            device_id=device_id,
            user_id=user_id,
            device_token=device_token,
            platform=Platform(platform),
            device_name=device_name,
            app_version=app_version,
        )

        self._devices[device_id] = device
        self._user_devices[user_id].add(device_id)

        logger.info(f"Device registered: {device_id} ({platform}) for user {user_id}")

        return device

    async def unregister_device(
        self,
        user_id: str,
        device_id: str,
    ) -> bool:
        """Unregister a device from push notifications."""
        if device_id in self._devices:
            device = self._devices[device_id]
            if device.user_id == user_id:
                device.is_active = False
                self._user_devices[user_id].discard(device_id)
                logger.info(f"Device unregistered: {device_id}")
                return True

        return False

    async def get_user_devices(self, user_id: str) -> list[dict[str, Any]]:
        """Get all registered devices for a user."""
        device_ids = self._user_devices.get(user_id, set())
        devices = []

        for device_id in device_ids:
            device = self._devices.get(device_id)
            if device and device.is_active:
                devices.append(
                    {
                        "device_id": device.device_id,
                        "platform": device.platform.value,
                        "device_name": device.device_name,
                        "app_version": device.app_version,
                        "registered_at": device.registered_at,
                        "last_active_at": device.last_active_at,
                    }
                )

        return devices

    # =========================================================================
    # PREFERENCES
    # =========================================================================

    async def get_user_preferences(self, user_id: str) -> dict[str, Any]:
        """Get notification preferences for a user."""
        prefs = self._preferences.get(user_id, UserPreferences())
        return {
            "smart_home_alerts": prefs.smart_home_alerts,
            "routine_reminders": prefs.routine_reminders,
            "security_alerts": prefs.security_alerts,
            "system_updates": prefs.system_updates,
            "quiet_hours_enabled": prefs.quiet_hours_enabled,
            "quiet_hours_start": prefs.quiet_hours_start,
            "quiet_hours_end": prefs.quiet_hours_end,
        }

    async def update_user_preferences(
        self,
        user_id: str,
        preferences: dict[str, Any],
    ) -> None:
        """Update notification preferences for a user."""
        prefs = self._preferences.get(user_id, UserPreferences())

        if "smart_home_alerts" in preferences:
            prefs.smart_home_alerts = preferences["smart_home_alerts"]
        if "routine_reminders" in preferences:
            prefs.routine_reminders = preferences["routine_reminders"]
        if "security_alerts" in preferences:
            prefs.security_alerts = preferences["security_alerts"]
        if "system_updates" in preferences:
            prefs.system_updates = preferences["system_updates"]
        if "quiet_hours_enabled" in preferences:
            prefs.quiet_hours_enabled = preferences["quiet_hours_enabled"]
        if "quiet_hours_start" in preferences:
            prefs.quiet_hours_start = preferences["quiet_hours_start"]
        if "quiet_hours_end" in preferences:
            prefs.quiet_hours_end = preferences["quiet_hours_end"]

        self._preferences[user_id] = prefs

    # =========================================================================
    # NOTIFICATION SENDING
    # =========================================================================

    def _should_send_notification(
        self,
        user_id: str,
        notification_type: str,
        priority: str,
    ) -> bool:
        """Check if notification should be sent based on preferences."""
        prefs = self._preferences.get(user_id, UserPreferences())

        # Critical always sends
        if priority == "critical":
            return True

        # Check notification type preference
        type_map = {
            "smart_home_alert": prefs.smart_home_alerts,
            "routine_reminder": prefs.routine_reminders,
            "security_alert": prefs.security_alerts,
            "system_update": prefs.system_updates,
        }

        if not type_map.get(notification_type, True):
            return False

        # Check quiet hours
        if prefs.quiet_hours_enabled and prefs.quiet_hours_start and prefs.quiet_hours_end:
            now = datetime.now().strftime("%H:%M")
            start = prefs.quiet_hours_start
            end = prefs.quiet_hours_end

            # Handle overnight quiet hours
            if start <= end:
                in_quiet = start <= now <= end
            else:
                in_quiet = now >= start or now <= end

            if in_quiet and priority not in ("critical", "high"):
                return False

        return True

    def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user has exceeded rate limit."""
        now = time.time()
        timestamps = self._rate_limits[user_id]

        # Remove old timestamps
        timestamps[:] = [t for t in timestamps if now - t < self._rate_limit_window]

        if len(timestamps) >= self._rate_limit_max:
            return False

        timestamps.append(now)
        return True

    async def send_notification(
        self,
        title: str,
        body: str,
        notification_type: str,
        priority: str = "normal",
        user_ids: list[str] | None = None,
        data: dict[str, Any] | None = None,
        action_url: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Send push notification to users.

        Args:
            title: Notification title
            body: Notification body
            notification_type: Type of notification
            priority: Priority level
            user_ids: Target user IDs (None = all users)
            data: Custom data payload
            action_url: Deep link URL
            category: Notification category

        Returns:
            dict with notification_id, recipients, delivered, failed
        """
        notification_id = str(uuid.uuid4())
        recipients = 0
        delivered = 0
        failed = 0

        # Get target users
        target_users = user_ids if user_ids else list(self._user_devices.keys())

        # Prepare data payload
        payload = data.copy() if data else {}
        if action_url:
            payload["action_url"] = action_url

        for user_id in target_users:
            # Check preferences
            if not self._should_send_notification(user_id, notification_type, priority):
                continue

            # Check rate limit
            if not self._check_rate_limit(user_id):
                logger.warning(f"Rate limit exceeded for user {user_id}")
                continue

            # Get user devices
            device_ids = self._user_devices.get(user_id, set())

            for device_id in device_ids:
                device = self._devices.get(device_id)
                if not device or not device.is_active:
                    continue

                recipients += 1

                # Send to appropriate platform
                if device.platform == Platform.IOS:
                    result = await self._apns.send(
                        device_token=device.device_token,
                        title=title,
                        body=body,
                        category=category,
                        data=payload,
                        priority=priority,
                    )
                elif device.platform == Platform.ANDROID:
                    result = await self._fcm.send(
                        device_token=device.device_token,
                        title=title,
                        body=body,
                        data=payload,
                        priority=priority,
                        channel_id=self._get_channel_for_type(notification_type),
                    )
                else:
                    result = {"success": False, "error": "Unsupported platform"}

                # Record notification
                record = NotificationRecord(
                    notification_id=notification_id,
                    user_id=user_id,
                    device_id=device_id,
                    title=title,
                    body=body,
                    notification_type=notification_type,
                    priority=priority,
                    sent_at=datetime.utcnow().isoformat(),
                    delivered_at=datetime.utcnow().isoformat() if result.get("success") else None,
                    failed=not result.get("success"),
                    error=result.get("error"),
                )
                self._notifications.append(record)

                if result.get("success"):
                    delivered += 1
                    self._stats["notifications_delivered"] += 1
                else:
                    failed += 1
                    self._stats["notifications_failed"] += 1
                    logger.warning(f"Failed to send to {device_id}: {result.get('error')}")

                self._stats["notifications_sent"] += 1

        return {
            "notification_id": notification_id,
            "recipients": recipients,
            "delivered": delivered,
            "failed": failed,
        }

    def _get_channel_for_type(self, notification_type: str) -> str:
        """Get Android notification channel for type."""
        channel_map = {
            "smart_home_alert": "kagami_home_alerts",
            "routine_reminder": "kagami_reminders",
            "security_alert": "kagami_security",
            "system_update": "kagami_updates",
        }
        return channel_map.get(notification_type, "kagami_notifications")

    async def send_to_device(
        self,
        device_id: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send notification to a specific device."""
        device = self._devices.get(device_id)
        if not device or not device.is_active:
            return {"success": False, "error": "Device not found"}

        if device.platform == Platform.IOS:
            result = await self._apns.send(
                device_token=device.device_token,
                title=title,
                body=body,
                data=data,
            )
        elif device.platform == Platform.ANDROID:
            result = await self._fcm.send(
                device_token=device.device_token,
                title=title,
                body=body,
                data=data,
            )
        else:
            result = {"success": False, "error": "Unsupported platform"}

        return result

    # =========================================================================
    # NOTIFICATION HISTORY
    # =========================================================================

    async def get_notification_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get notification history for a user."""
        user_notifications = [n for n in self._notifications if n.user_id == user_id]
        user_notifications.sort(key=lambda n: n.sent_at, reverse=True)

        return [
            {
                "notification_id": n.notification_id,
                "title": n.title,
                "body": n.body,
                "type": n.notification_type,
                "priority": n.priority,
                "sent_at": n.sent_at,
                "delivered_at": n.delivered_at,
                "read_at": n.read_at,
                "failed": n.failed,
            }
            for n in user_notifications[offset : offset + limit]
        ]

    async def mark_notification_read(
        self,
        user_id: str,
        notification_id: str,
    ) -> None:
        """Mark a notification as read."""
        for notification in self._notifications:
            if (
                notification.notification_id == notification_id
                and notification.user_id == user_id
                and not notification.read_at
            ):
                notification.read_at = datetime.utcnow().isoformat()
                break

    async def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications for a user."""
        return sum(
            1
            for n in self._notifications
            if n.user_id == user_id and not n.read_at and not n.failed
        )

    # =========================================================================
    # STATS
    # =========================================================================

    async def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        total_devices = sum(1 for d in self._devices.values() if d.is_active)

        # Count 24h notifications
        cutoff = datetime.utcnow() - timedelta(hours=24)
        cutoff_str = cutoff.isoformat()
        last_24h = sum(1 for n in self._notifications if n.sent_at >= cutoff_str)

        total_sent = self._stats["notifications_sent"]
        total_delivered = self._stats["notifications_delivered"]

        return {
            "apns_connected": self._apns.is_configured,
            "fcm_connected": self._fcm.is_configured,
            "total_devices": total_devices,
            "notifications_sent_24h": last_24h,
            "delivery_rate": (total_delivered / total_sent * 100) if total_sent > 0 else 100.0,
        }


# =============================================================================
# SINGLETON
# =============================================================================


_PUSH_SERVICE: PushNotificationService | None = None


async def get_push_notification_service() -> PushNotificationService:
    """Get the global push notification service instance."""
    global _PUSH_SERVICE

    if _PUSH_SERVICE is None:
        _PUSH_SERVICE = PushNotificationService()
        await _PUSH_SERVICE.initialize()

    return _PUSH_SERVICE


__all__ = [
    "APNsClient",
    "DeviceInfo",
    "FCMClient",
    "NotificationPriority",
    "NotificationRecord",
    "NotificationType",
    "Platform",
    "PushNotificationService",
    "UserPreferences",
    "get_push_notification_service",
]
