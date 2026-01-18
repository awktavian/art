"""User Preferences API Routes.

Provides comprehensive user preference management including:
- Display settings (theme, language, units)
- Notification settings (push, email, voice)
- Smart home defaults (default rooms, scenes)
- Privacy settings
- Accessibility settings

Created: December 31, 2025 (RALPH Week 2)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from kagami_api.auth import User, get_current_user
from kagami_api.response_schemas import get_error_responses

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/user/preferences", tags=["user", "preferences"])

    # =============================================================================
    # ENUMS
    # =============================================================================

    class Theme(str, Enum):
        """UI theme options."""

        DARK = "dark"
        LIGHT = "light"
        AUTO = "auto"  # Follow system setting

    class TemperatureUnit(str, Enum):
        """Temperature display units."""

        FAHRENHEIT = "fahrenheit"
        CELSIUS = "celsius"

    class TimeFormat(str, Enum):
        """Time display format."""

        TWELVE_HOUR = "12h"
        TWENTY_FOUR_HOUR = "24h"

    class VoiceSpeed(str, Enum):
        """Voice response speed."""

        SLOW = "slow"
        NORMAL = "normal"
        FAST = "fast"

    class NotificationLevel(str, Enum):
        """Notification verbosity level."""

        MINIMAL = "minimal"  # Critical only
        NORMAL = "normal"  # Important updates
        VERBOSE = "verbose"  # All notifications

    class NotificationModality(str, Enum):
        """How this user prefers to receive notifications."""

        AUDIO = "audio"  # Voice announcements
        VISUAL = "visual"  # Screen flashes, LED indicators
        HAPTIC = "haptic"  # Vibration, bed shakers
        TEXT = "text"  # On-screen text only

    class ScheduleType(str, Enum):
        """Quiet hours schedule type for diverse personas."""

        FIXED = "fixed"  # Same time every day
        WEEKDAY_WEEKEND = "weekday_weekend"  # Different weekday/weekend schedules
        ROTATING = "rotating"  # Rotating shift pattern (e.g., nurses, factory workers)
        CUSTOM = "custom"  # Per-day schedule for maximum flexibility

    # =============================================================================
    # SCHEMAS
    # =============================================================================

    class QuietHoursSchedule(BaseModel):
        """Flexible quiet hours schedule supporting diverse lifestyles.

        Supports multiple schedule types:
        - FIXED: Same time every day (default, traditional approach)
        - WEEKDAY_WEEKEND: Different times for work days vs weekends
        - ROTATING: For shift workers with rotating patterns
        - CUSTOM: Per-day schedules for maximum flexibility
        """

        type: ScheduleType = Field(
            default=ScheduleType.FIXED,
            description="Schedule type determining which fields are used",
        )

        # Fixed schedule (default)
        fixed_start: str | None = Field(
            default="22:00", description="Fixed quiet hours start time (HH:MM)"
        )
        fixed_end: str | None = Field(
            default="07:00", description="Fixed quiet hours end time (HH:MM)"
        )

        # Weekday/weekend split (for typical office workers)
        weekday_start: str | None = Field(
            default=None, description="Weekday quiet hours start (HH:MM)"
        )
        weekday_end: str | None = Field(default=None, description="Weekday quiet hours end (HH:MM)")
        weekend_start: str | None = Field(
            default=None, description="Weekend quiet hours start (HH:MM)"
        )
        weekend_end: str | None = Field(default=None, description="Weekend quiet hours end (HH:MM)")

        # Rotating pattern (for shift workers like nurses, factory workers)
        # Example: [{"days": [0,1,2], "start": "08:00", "end": "16:00"}, ...]
        rotation_pattern: list[dict] | None = Field(
            default=None,
            description="Rotating shift pattern: list of {days: [0-6], start: HH:MM, end: HH:MM}",
        )

        # Custom per-day schedule (maximum flexibility)
        # Keys are day of week (0=Monday, 6=Sunday), values are (start, end) tuples
        per_day: dict[int, tuple[str, str]] | None = Field(
            default=None,
            description="Per-day schedule: {day_of_week: (start, end)}",
        )

    class DisplayPreferences(BaseModel):
        """Display and UI preferences."""

        theme: Theme = Field(default=Theme.AUTO, description="UI color theme")
        language: str = Field(
            default="en", min_length=2, max_length=10, description="Language code"
        )
        temperature_unit: TemperatureUnit = Field(
            default=TemperatureUnit.FAHRENHEIT, description="Temperature display unit"
        )
        time_format: TimeFormat = Field(
            default=TimeFormat.TWELVE_HOUR, description="Time display format"
        )
        compact_mode: bool = Field(default=False, description="Use compact UI layout")

        # Multi-language support for immigrant households
        primary_language: str = Field(
            default="en",
            description="Primary language code (en, ar, vi, zh, es, ko, tl, etc.)",
        )
        secondary_language: str | None = Field(
            default=None,
            description="Secondary language for bilingual households",
        )

        # Language-specific settings
        rtl_support: bool = Field(
            default=False,
            description="Enable right-to-left text (Arabic, Hebrew)",
        )

        # Calendar systems
        calendar_system: str = Field(
            default="gregorian",
            description="Calendar system (gregorian, hijri, hebrew, lunar)",
        )
        show_secondary_calendar: bool = Field(
            default=False,
            description="Show secondary calendar dates",
        )
        secondary_calendar_system: str | None = Field(
            default=None,
            description="Secondary calendar system",
        )

    class NotificationPreferences(BaseModel):
        """Notification delivery preferences."""

        push_enabled: bool = Field(default=True, description="Enable push notifications")
        email_enabled: bool = Field(default=True, description="Enable email notifications")
        voice_enabled: bool = Field(default=True, description="Enable voice announcements")
        level: NotificationLevel = Field(
            default=NotificationLevel.NORMAL, description="Notification verbosity"
        )

        # Quiet hours - new flexible schedule system
        quiet_hours_enabled: bool = Field(default=False, description="Enable quiet hours")
        quiet_hours_schedule: QuietHoursSchedule = Field(
            default_factory=QuietHoursSchedule,
            description="Flexible quiet hours schedule (supports fixed, weekday/weekend, rotating, and custom)",
        )

        # Category toggles
        security_alerts: bool = Field(default=True, description="Receive security alerts")
        weather_alerts: bool = Field(default=True, description="Receive weather alerts")
        device_alerts: bool = Field(default=True, description="Receive device status alerts")
        reminder_alerts: bool = Field(default=True, description="Receive reminder notifications")

    class VoicePreferences(BaseModel):
        """Voice assistant preferences."""

        enabled: bool = Field(default=True, description="Enable voice control")
        wake_word: str = Field(default="kagami", description="Wake word (kagami, hey kagami, etc.)")
        response_speed: VoiceSpeed = Field(
            default=VoiceSpeed.NORMAL, description="Voice response speed"
        )
        default_colony: str = Field(
            default="kagami",
            description="Default voice personality (spark, forge, flow, nexus, beacon, grove, crystal, kagami)",
        )
        confirm_actions: bool = Field(
            default=True, description="Require voice confirmation for actions"
        )
        feedback_sounds: bool = Field(
            default=True, description="Play sounds for wake word detection"
        )

        # Multi-language voice support
        voice_language: str = Field(
            default="en-US",
            description="Voice language/accent (en-US, ar-SA, vi-VN, zh-CN, etc.)",
        )
        translate_responses: bool = Field(
            default=False,
            description="Translate Kagami's responses to user's language",
        )

    class SmartHomePreferences(BaseModel):
        """Smart home default preferences."""

        default_room: str | None = Field(None, description="Default room for voice commands")
        default_scene: str | None = Field(
            None, description="Default scene for 'set the scene' command"
        )
        auto_lights_off: bool = Field(default=True, description="Auto-off lights when leaving room")
        auto_lights_off_delay_minutes: int = Field(
            default=5, ge=1, le=60, description="Delay before auto-off (minutes)"
        )
        presence_based_climate: bool = Field(
            default=True, description="Adjust climate based on presence"
        )
        goodnight_auto_arm: bool = Field(default=True, description="Auto-lock doors on goodnight")

    class PrivacyPreferences(BaseModel):
        """Privacy and data preferences."""

        analytics_enabled: bool = Field(default=True, description="Share anonymous usage analytics")
        crash_reports_enabled: bool = Field(default=True, description="Send crash reports")
        voice_history_enabled: bool = Field(
            default=False, description="Store voice command history"
        )
        location_history_enabled: bool = Field(default=False, description="Store location history")
        data_retention_days: int = Field(
            default=90, ge=7, le=365, description="Data retention period (days)"
        )

    class AccessibilityPreferences(BaseModel):
        """Accessibility settings."""

        reduce_motion: bool = Field(default=False, description="Reduce UI animations")
        high_contrast: bool = Field(default=False, description="Use high contrast mode")
        larger_text: bool = Field(default=False, description="Use larger text size")
        screen_reader_optimized: bool = Field(
            default=False, description="Optimize for screen readers"
        )
        voice_feedback: bool = Field(default=True, description="Provide voice feedback for actions")
        haptic_feedback: bool = Field(default=True, description="Enable haptic feedback")

        # Notification modality (critical for deaf/blind users)
        primary_modality: NotificationModality = Field(
            default=NotificationModality.AUDIO,
            description="Primary notification method (audio for hearing, visual for deaf, haptic for deaf-blind)",
        )
        secondary_modality: NotificationModality | None = Field(
            default=None,
            description="Backup notification method",
        )

        # Deaf accessibility
        deaf_mode: bool = Field(
            default=False, description="Enable deaf accessibility (visual alerts, no audio)"
        )
        visual_doorbell: bool = Field(default=False, description="Flash lights for doorbell")
        visual_alarms: bool = Field(default=False, description="Flash lights for smoke/CO alarms")
        bed_shaker_enabled: bool = Field(
            default=False, description="Use bed shaker for critical alerts"
        )

        # Blind accessibility
        blind_mode: bool = Field(
            default=False, description="Enable blind accessibility (audio-only, no visual)"
        )
        audio_descriptions: bool = Field(
            default=True, description="Describe visual elements audibly"
        )
        screen_reader_announcements: bool = Field(default=True, description="Push to screen reader")

        # Neurodivergent accommodations
        sensory_load_limit: int | None = Field(
            default=None,
            ge=1,
            le=10,
            description="Max sensory stimulation level 1-10 (for autism/SPD)",
        )
        no_sudden_changes: bool = Field(
            default=False, description="Avoid sudden lighting/sound changes"
        )
        routine_warnings: bool = Field(default=False, description="Warn before routine changes")

    class UserPreferences(BaseModel):
        """Complete user preferences."""

        display: DisplayPreferences = Field(
            default_factory=DisplayPreferences, description="Display settings"
        )
        notifications: NotificationPreferences = Field(
            default_factory=NotificationPreferences, description="Notification settings"
        )
        voice: VoicePreferences = Field(
            default_factory=VoicePreferences, description="Voice assistant settings"
        )
        smart_home: SmartHomePreferences = Field(
            default_factory=SmartHomePreferences, description="Smart home defaults"
        )
        privacy: PrivacyPreferences = Field(
            default_factory=PrivacyPreferences, description="Privacy settings"
        )
        accessibility: AccessibilityPreferences = Field(
            default_factory=AccessibilityPreferences, description="Accessibility settings"
        )

        # Metadata
        version: int = Field(default=1, description="Preferences schema version")
        updated_at: datetime | None = Field(default=None, description="Last update timestamp")

    class PreferencesResponse(BaseModel):
        """Response containing user preferences."""

        preferences: UserPreferences
        user_id: str

    class PreferencesUpdateRequest(BaseModel):
        """Request to update user preferences.

        All fields are optional - only provided fields will be updated.
        """

        display: DisplayPreferences | None = None
        notifications: NotificationPreferences | None = None
        voice: VoicePreferences | None = None
        smart_home: SmartHomePreferences | None = None
        privacy: PrivacyPreferences | None = None
        accessibility: AccessibilityPreferences | None = None

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

    async def _get_preferences(user_id: str) -> UserPreferences:
        """Get user preferences from Redis."""
        client = await _get_redis_client()
        if client:
            key = f"preferences:{user_id}"
            data = await client.get(key)
            if data:
                try:
                    return UserPreferences(**json.loads(data))
                except Exception as e:
                    logger.warning(f"Failed to parse preferences for {user_id}: {e}")

        # Return defaults
        return UserPreferences()

    async def _set_preferences(user_id: str, preferences: UserPreferences) -> bool:
        """Store user preferences in Redis."""
        client = await _get_redis_client()
        if not client:
            logger.warning("Redis not available for preferences storage")
            return False

        key = f"preferences:{user_id}"
        preferences.updated_at = datetime.utcnow()

        try:
            await client.set(key, preferences.model_dump_json())
            # Expire after 1 year
            await client.expire(key, 60 * 60 * 24 * 365)
            return True
        except Exception as e:
            logger.error(f"Failed to store preferences for {user_id}: {e}")
            return False

    # =============================================================================
    # ROUTES
    # =============================================================================

    @router.get(
        "",
        response_model=PreferencesResponse,
        responses=get_error_responses(401, 500),
        summary="Get user preferences",
        description="Returns the current user's preferences.",
    )
    async def get_preferences(
        current_user: User = Depends(get_current_user),
    ) -> PreferencesResponse:
        """Get the authenticated user's preferences."""
        preferences = await _get_preferences(current_user.id)

        return PreferencesResponse(
            preferences=preferences,
            user_id=current_user.id,
        )

    @router.put(
        "",
        response_model=PreferencesResponse,
        responses=get_error_responses(400, 401, 422, 500),
        summary="Update user preferences",
        description="""
        Update user preferences. Only provided fields will be updated.

        Example - update just theme:
        ```json
        {
          "display": {
            "theme": "dark"
          }
        }
        ```
        """,
    )
    async def update_preferences(
        updates: PreferencesUpdateRequest,
        current_user: User = Depends(get_current_user),
    ) -> PreferencesResponse:
        """Update the authenticated user's preferences."""
        # Get current preferences
        preferences = await _get_preferences(current_user.id)

        # Apply updates (merge, don't replace)
        if updates.display:
            preferences.display = updates.display
        if updates.notifications:
            preferences.notifications = updates.notifications
        if updates.voice:
            preferences.voice = updates.voice
        if updates.smart_home:
            preferences.smart_home = updates.smart_home
        if updates.privacy:
            preferences.privacy = updates.privacy
        if updates.accessibility:
            preferences.accessibility = updates.accessibility

        # Save
        if not await _set_preferences(current_user.id, preferences):
            raise HTTPException(
                status_code=500,
                detail="Failed to save preferences. Please try again.",
            )

        logger.info(f"Preferences updated for user {current_user.id}")

        return PreferencesResponse(
            preferences=preferences,
            user_id=current_user.id,
        )

    @router.patch(
        "",
        response_model=PreferencesResponse,
        responses=get_error_responses(400, 401, 422, 500),
        summary="Patch user preferences",
        description="Partially update user preferences. Same as PUT but semantically a patch.",
    )
    async def patch_preferences(
        updates: PreferencesUpdateRequest,
        current_user: User = Depends(get_current_user),
    ) -> PreferencesResponse:
        """Patch the authenticated user's preferences (alias for PUT)."""
        return await update_preferences(updates, current_user)

    @router.delete(
        "",
        responses=get_error_responses(401, 500),
        summary="Reset preferences to defaults",
        description="Resets all user preferences to their default values.",
    )
    async def reset_preferences(
        current_user: User = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Reset preferences to defaults."""
        default_preferences = UserPreferences()
        await _set_preferences(current_user.id, default_preferences)

        return {
            "success": True,
            "message": "Preferences reset to defaults",
            "user_id": current_user.id,
        }

    # =============================================================================
    # INDIVIDUAL SECTION ROUTES (for mobile apps with limited bandwidth)
    # =============================================================================

    @router.get(
        "/display",
        response_model=DisplayPreferences,
        responses=get_error_responses(401, 500),
        summary="Get display preferences",
    )
    async def get_display_preferences(
        current_user: User = Depends(get_current_user),
    ) -> DisplayPreferences:
        """Get just display preferences."""
        preferences = await _get_preferences(current_user.id)
        return preferences.display

    @router.put(
        "/display",
        response_model=DisplayPreferences,
        responses=get_error_responses(401, 422, 500),
        summary="Update display preferences",
    )
    async def update_display_preferences(
        display: DisplayPreferences,
        current_user: User = Depends(get_current_user),
    ) -> DisplayPreferences:
        """Update display preferences."""
        preferences = await _get_preferences(current_user.id)
        preferences.display = display
        await _set_preferences(current_user.id, preferences)
        return preferences.display

    @router.get(
        "/notifications",
        response_model=NotificationPreferences,
        responses=get_error_responses(401, 500),
        summary="Get notification preferences",
    )
    async def get_notification_preferences(
        current_user: User = Depends(get_current_user),
    ) -> NotificationPreferences:
        """Get notification preferences."""
        preferences = await _get_preferences(current_user.id)
        return preferences.notifications

    @router.put(
        "/notifications",
        response_model=NotificationPreferences,
        responses=get_error_responses(401, 422, 500),
        summary="Update notification preferences",
    )
    async def update_notification_preferences(
        notifications: NotificationPreferences,
        current_user: User = Depends(get_current_user),
    ) -> NotificationPreferences:
        """Update notification preferences."""
        preferences = await _get_preferences(current_user.id)
        preferences.notifications = notifications
        await _set_preferences(current_user.id, preferences)
        return preferences.notifications

    @router.get(
        "/voice",
        response_model=VoicePreferences,
        responses=get_error_responses(401, 500),
        summary="Get voice preferences",
    )
    async def get_voice_preferences(
        current_user: User = Depends(get_current_user),
    ) -> VoicePreferences:
        """Get voice assistant preferences."""
        preferences = await _get_preferences(current_user.id)
        return preferences.voice

    @router.put(
        "/voice",
        response_model=VoicePreferences,
        responses=get_error_responses(401, 422, 500),
        summary="Update voice preferences",
    )
    async def update_voice_preferences(
        voice: VoicePreferences,
        current_user: User = Depends(get_current_user),
    ) -> VoicePreferences:
        """Update voice assistant preferences."""
        preferences = await _get_preferences(current_user.id)
        preferences.voice = voice
        await _set_preferences(current_user.id, preferences)
        return preferences.voice

    @router.get(
        "/smart-home",
        response_model=SmartHomePreferences,
        responses=get_error_responses(401, 500),
        summary="Get smart home preferences",
    )
    async def get_smart_home_preferences(
        current_user: User = Depends(get_current_user),
    ) -> SmartHomePreferences:
        """Get smart home default preferences."""
        preferences = await _get_preferences(current_user.id)
        return preferences.smart_home

    @router.put(
        "/smart-home",
        response_model=SmartHomePreferences,
        responses=get_error_responses(401, 422, 500),
        summary="Update smart home preferences",
    )
    async def update_smart_home_preferences(
        smart_home: SmartHomePreferences,
        current_user: User = Depends(get_current_user),
    ) -> SmartHomePreferences:
        """Update smart home default preferences."""
        preferences = await _get_preferences(current_user.id)
        preferences.smart_home = smart_home
        await _set_preferences(current_user.id, preferences)
        return preferences.smart_home

    @router.get(
        "/privacy",
        response_model=PrivacyPreferences,
        responses=get_error_responses(401, 500),
        summary="Get privacy preferences",
    )
    async def get_privacy_preferences(
        current_user: User = Depends(get_current_user),
    ) -> PrivacyPreferences:
        """Get privacy preferences."""
        preferences = await _get_preferences(current_user.id)
        return preferences.privacy

    @router.put(
        "/privacy",
        response_model=PrivacyPreferences,
        responses=get_error_responses(401, 422, 500),
        summary="Update privacy preferences",
    )
    async def update_privacy_preferences(
        privacy: PrivacyPreferences,
        current_user: User = Depends(get_current_user),
    ) -> PrivacyPreferences:
        """Update privacy preferences."""
        preferences = await _get_preferences(current_user.id)
        preferences.privacy = privacy
        await _set_preferences(current_user.id, preferences)
        return preferences.privacy

    @router.get(
        "/accessibility",
        response_model=AccessibilityPreferences,
        responses=get_error_responses(401, 500),
        summary="Get accessibility preferences",
    )
    async def get_accessibility_preferences(
        current_user: User = Depends(get_current_user),
    ) -> AccessibilityPreferences:
        """Get accessibility preferences."""
        preferences = await _get_preferences(current_user.id)
        return preferences.accessibility

    @router.put(
        "/accessibility",
        response_model=AccessibilityPreferences,
        responses=get_error_responses(401, 422, 500),
        summary="Update accessibility preferences",
    )
    async def update_accessibility_preferences(
        accessibility: AccessibilityPreferences,
        current_user: User = Depends(get_current_user),
    ) -> AccessibilityPreferences:
        """Update accessibility preferences."""
        preferences = await _get_preferences(current_user.id)
        preferences.accessibility = accessibility
        await _set_preferences(current_user.id, preferences)
        return preferences.accessibility

    return router


__all__ = ["get_router"]
