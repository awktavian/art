"""Consent Manager for Ambient Intelligence.

Implements granular, context-aware consent management:
- Per-sensor consent toggles
- Context-aware permissions (home vs work vs public)
- Temporal consent (time-limited permissions)
- Visual indicators of active sensing
- Pause/resume ambient with clear feedback

Design Principles:
1. Opt-in by default: Nothing captures without consent
2. Granular control: Per-sensor, per-context permissions
3. Clear feedback: User always knows what's active
4. Easy reversal: One-tap pause, easy to disable

Created: December 7, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from kagami.core.ambient.privacy import DataCategory, DataSensitivity

logger = logging.getLogger(__name__)


class ConsentLevel(Enum):
    """Consent levels for data capture."""

    DENIED = "denied"  # Explicitly denied
    NOT_ASKED = "not_asked"  # Never asked
    GRANTED = "granted"  # Explicitly granted
    GRANTED_ONCE = "granted_once"  # One-time permission
    GRANTED_SESSION = "granted_session"  # Until app restart
    GRANTED_TIMED = "granted_timed"  # Until expiry time


class ConsentContext(Enum):
    """Contexts that affect consent."""

    HOME = "home"
    WORK = "work"
    PUBLIC = "public"
    PRIVATE = "private"  # E.g., bathroom
    SHARED = "shared"  # Multi-user space
    TRAVEL = "travel"
    UNKNOWN = "unknown"


@dataclass
class ConsentRecord:
    """Record of a consent decision."""

    id: str
    category: DataCategory
    level: ConsentLevel
    context: ConsentContext | None
    granted_at: float
    expires_at: float | None = None
    granted_by: str = "user"  # "user", "default", "admin"
    reason: str = ""

    @property
    def is_valid(self) -> bool:
        """Check if consent is still valid."""
        # DENIED is a valid explicit decision and must override older grants.
        if self.level == ConsentLevel.NOT_ASKED:
            return False
        if self.expires_at and time.time() > self.expires_at:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "category": self.category.value,
            "level": self.level.value,
            "context": self.context.value if self.context else None,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
            "granted_by": self.granted_by,
            "reason": self.reason,
            "is_valid": self.is_valid,
        }


@dataclass
class ConsentConfig:
    """Consent manager configuration."""

    # Default consent levels by sensitivity
    default_public: ConsentLevel = ConsentLevel.GRANTED  # Public data auto-allowed
    default_internal: ConsentLevel = ConsentLevel.NOT_ASKED
    default_confidential: ConsentLevel = ConsentLevel.NOT_ASKED
    default_restricted: ConsentLevel = ConsentLevel.DENIED  # Restricted always needs explicit

    # Context-aware defaults
    more_permissive_at_home: bool = True
    stricter_in_public: bool = True

    # Expiry
    session_expiry_hours: float = 24.0
    timed_default_hours: float = 1.0

    # UI
    show_active_indicator: bool = True
    require_confirmation_for_restricted: bool = True


class ConsentManager:
    """Manages user consent for ambient data capture.

    Responsibilities:
    - Track consent per category and context
    - Provide quick pause/resume functionality
    - Show active sensors to user
    - Time-limited and context-aware consent
    """

    def __init__(self, config: ConsentConfig | None = None):
        """Initialize consent manager.

        Args:
            config: Consent configuration
        """
        self.config = config or ConsentConfig()

        # Consent records by category
        self._consents: dict[DataCategory, list[ConsentRecord]] = {}

        # Current context
        self._current_context: ConsentContext = ConsentContext.UNKNOWN

        # Pause state
        self._paused = False
        self._pause_until: float | None = None
        self._pause_reason: str = ""

        # Callbacks for consent changes
        self._on_consent_change: list[Callable[[DataCategory, ConsentLevel], None]] = []
        self._on_pause_change: list[Callable[[bool], None]] = []

        # Statistics
        self._stats = {
            "consent_checks": 0,
            "grants": 0,
            "denials": 0,
            "pauses": 0,
        }

        logger.info("✅ Consent manager initialized")

    # =========================================================================
    # Consent Management
    # =========================================================================

    def get_consent(
        self,
        category: DataCategory,
        context: ConsentContext | None = None,
    ) -> ConsentLevel:
        """Get current consent level for a category.

        Args:
            category: Data category
            context: Optional context override

        Returns:
            Current consent level
        """
        self._stats["consent_checks"] += 1

        # Check if paused
        if self.is_paused:
            return ConsentLevel.DENIED

        context = context or self._current_context

        # Find applicable consent record
        records = self._consents.get(category, [])

        # Find most specific valid consent.
        # Priority: context-specific > general > default
        # IMPORTANT: most recent record wins (revocations must override grants).
        for record in reversed(records):
            if not record.is_valid:
                continue

            # Context-specific match
            if record.context == context:
                return record.level

            # General (no context) match
            if record.context is None:
                return record.level

        # No consent found - return default based on sensitivity
        return self._get_default_consent(category, context)

    def _get_default_consent(self, category: DataCategory, context: ConsentContext) -> ConsentLevel:
        """Get default consent based on sensitivity and context."""
        from kagami.core.ambient.privacy import CATEGORY_SENSITIVITY

        sensitivity = CATEGORY_SENSITIVITY.get(category, DataSensitivity.CONFIDENTIAL)

        # Base default by sensitivity
        if sensitivity == DataSensitivity.PUBLIC:
            default = self.config.default_public
        elif sensitivity == DataSensitivity.INTERNAL:
            default = self.config.default_internal
        elif sensitivity == DataSensitivity.CONFIDENTIAL:
            default = self.config.default_confidential
        else:  # RESTRICTED
            default = self.config.default_restricted

        # Context modifiers
        if self.config.more_permissive_at_home and context == ConsentContext.HOME:
            if default == ConsentLevel.NOT_ASKED:
                default = ConsentLevel.GRANTED_SESSION

        if self.config.stricter_in_public and context == ConsentContext.PUBLIC:
            if default in (ConsentLevel.GRANTED, ConsentLevel.GRANTED_SESSION):
                default = ConsentLevel.NOT_ASKED

        return default

    def grant_consent(
        self,
        category: DataCategory,
        level: ConsentLevel = ConsentLevel.GRANTED,
        context: ConsentContext | None = None,
        duration_hours: float | None = None,
        reason: str = "",
    ) -> ConsentRecord:
        """Grant consent for a category.

        Args:
            category: Data category
            level: Consent level
            context: Optional context restriction
            duration_hours: Optional time limit
            reason: Why consent was granted

        Returns:
            Consent record
        """
        expires_at = None
        if duration_hours:
            expires_at = time.time() + (duration_hours * 3600)
            level = ConsentLevel.GRANTED_TIMED
        elif level == ConsentLevel.GRANTED_SESSION:
            expires_at = time.time() + (self.config.session_expiry_hours * 3600)

        record = ConsentRecord(
            id=str(uuid.uuid4())[:8],
            category=category,
            level=level,
            context=context,
            granted_at=time.time(),
            expires_at=expires_at,
            reason=reason,
        )

        if category not in self._consents:
            self._consents[category] = []
        self._consents[category].append(record)

        self._stats["grants"] += 1

        # Notify callbacks
        for callback in self._on_consent_change:
            try:
                callback(category, level)
            except Exception as e:
                logger.error(f"Consent callback error: {e}")

        logger.info(f"✅ Consent granted: {category.value} ({level.value})")
        return record

    def revoke_consent(
        self,
        category: DataCategory,
        context: ConsentContext | None = None,
    ) -> bool:
        """Revoke consent for a category.

        Args:
            category: Data category
            context: Optional context (None = all contexts)

        Returns:
            True if any consent was revoked
        """
        if category not in self._consents:
            return False

        # Create denial record
        record = ConsentRecord(
            id=str(uuid.uuid4())[:8],
            category=category,
            level=ConsentLevel.DENIED,
            context=context,
            granted_at=time.time(),
            reason="User revoked",
        )

        self._consents[category].append(record)
        self._stats["denials"] += 1

        # Notify callbacks
        for callback in self._on_consent_change:
            try:
                callback(category, ConsentLevel.DENIED)
            except Exception as e:
                logger.error(f"Consent callback error: {e}")

        logger.info(f"❌ Consent revoked: {category.value}")
        return True

    def has_consent(
        self,
        category: DataCategory,
        context: ConsentContext | None = None,
    ) -> bool:
        """Check if consent is granted.

        Args:
            category: Data category
            context: Optional context

        Returns:
            True if consent granted
        """
        level = self.get_consent(category, context)
        return level in (
            ConsentLevel.GRANTED,
            ConsentLevel.GRANTED_ONCE,
            ConsentLevel.GRANTED_SESSION,
            ConsentLevel.GRANTED_TIMED,
        )

    # =========================================================================
    # Context Management
    # =========================================================================

    def set_context(self, context: ConsentContext) -> None:
        """Set current context.

        Args:
            context: New context
        """
        if context != self._current_context:
            old = self._current_context
            self._current_context = context
            logger.info(f"📍 Context changed: {old.value} → {context.value}")

    def get_context(self) -> ConsentContext:
        """Get current context."""
        return self._current_context

    # =========================================================================
    # Pause/Resume
    # =========================================================================

    async def pause_ambient(
        self,
        duration_minutes: float = 30,
        reason: str = "User requested",
    ) -> None:
        """Pause all ambient sensing.

        Args:
            duration_minutes: How long to pause (0 = indefinite)
            reason: Why pausing
        """
        self._paused = True
        self._pause_reason = reason

        if duration_minutes > 0:
            self._pause_until = time.time() + (duration_minutes * 60)

            # Schedule auto-resume
            asyncio.create_task(self._auto_resume(duration_minutes * 60))
        else:
            self._pause_until = None

        self._stats["pauses"] += 1

        # Notify callbacks
        for callback in self._on_pause_change:
            try:
                callback(True)
            except Exception as e:
                logger.error(f"Pause callback error: {e}")

        logger.info(f"⏸️ Ambient paused for {duration_minutes}min: {reason}")

    async def _auto_resume(self, delay: float) -> None:
        """Auto-resume after delay."""
        await asyncio.sleep(delay)
        if self._paused and self._pause_until and time.time() >= self._pause_until:
            await self.resume_ambient()

    async def resume_ambient(self) -> None:
        """Resume ambient sensing."""
        self._paused = False
        self._pause_until = None
        self._pause_reason = ""

        # Notify callbacks
        for callback in self._on_pause_change:
            try:
                callback(False)
            except Exception as e:
                logger.error(f"Resume callback error: {e}")

        logger.info("▶️ Ambient resumed")

    @property
    def is_paused(self) -> bool:
        """Check if ambient is paused."""
        if not self._paused:
            return False

        # Check if pause expired
        if self._pause_until and time.time() > self._pause_until:
            self._paused = False
            return False

        return True

    def get_pause_status(self) -> dict[str, Any]:
        """Get current pause status."""
        return {
            "paused": self.is_paused,
            "reason": self._pause_reason if self._paused else None,
            "resume_at": self._pause_until,
            "remaining_seconds": (
                max(0, self._pause_until - time.time()) if self._pause_until else None
            ),
        }

    # =========================================================================
    # Active Sensors Indicator
    # =========================================================================

    def get_active_sensors(self) -> list[dict[str, Any]]:
        """Get list[Any] of sensors with active consent.

        Returns:
            List of active sensor info
        """
        active = []

        for category in DataCategory:
            if self.has_consent(category):
                active.append(
                    {
                        "category": category.value,
                        "consent_level": self.get_consent(category).value,
                        "context": self._current_context.value,
                    }
                )

        return active

    def get_sensor_indicator(self) -> dict[str, Any]:
        """Get visual indicator data for active sensors.

        Returns:
            Indicator data for UI
        """
        active = self.get_active_sensors()

        # Determine overall status
        if self.is_paused:
            status = "paused"
            color = "gray"
        elif any(s["category"] in ("audio", "video", "biometric") for s in active):
            status = "recording"
            color = "red"
        elif active:
            status = "sensing"
            color = "blue"
        else:
            status = "idle"
            color = "green"

        return {
            "status": status,
            "color": color,
            "active_count": len(active),
            "active_categories": [s["category"] for s in active],
            "paused": self.is_paused,
        }

    # =========================================================================
    # Preferences UI Data
    # =========================================================================

    def get_preferences(self) -> dict[str, Any]:
        """Get preferences for settings UI.

        Returns:
            Preferences data structure
        """
        from kagami.core.ambient.privacy import CATEGORY_SENSITIVITY

        categories = []
        for category in DataCategory:
            sensitivity = CATEGORY_SENSITIVITY.get(category, DataSensitivity.INTERNAL)
            consent = self.get_consent(category)

            categories.append(
                {
                    "category": category.value,
                    "sensitivity": sensitivity.value,
                    "consent": consent.value,
                    "has_consent": self.has_consent(category),
                    "description": self._get_category_description(category),
                }
            )

        return {
            "categories": categories,
            "current_context": self._current_context.value,
            "paused": self.is_paused,
            "pause_status": self.get_pause_status(),
            "indicator": self.get_sensor_indicator(),
        }

    def _get_category_description(self, category: DataCategory) -> str:
        """Get human-readable description of a category."""
        descriptions = {
            DataCategory.PRESENCE: "Detect if you're nearby",
            DataCategory.LOCATION: "Track your location (GPS, room)",
            DataCategory.ACTIVITY: "Detect activity (walking, sitting)",
            DataCategory.AUDIO: "Listen to voice commands and ambient sound",
            DataCategory.VIDEO: "Use camera for vision",
            DataCategory.BIOMETRIC: "Track health metrics (heart rate, etc)",
            DataCategory.DEVICE: "Monitor device state (battery, screen)",
            DataCategory.CONTEXT: "Infer context (home, work, etc)",
            DataCategory.INTERACTION: "Remember your preferences",
        }
        return descriptions.get(category, "Unknown data type")

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_consent_change(self, callback: Callable[[DataCategory, ConsentLevel], None]) -> None:
        """Register callback for consent changes.

        Args:
            callback: Function(category, level) called on change
        """
        self._on_consent_change.append(callback)

    def on_pause_change(self, callback: Callable[[bool], None]) -> None:
        """Register callback for pause state changes.

        Args:
            callback: Function(is_paused) called on change
        """
        self._on_pause_change.append(callback)

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get consent statistics."""
        return {
            **self._stats,
            "current_context": self._current_context.value,
            "paused": self.is_paused,
            "active_sensors": len(self.get_active_sensors()),
            "total_consents": sum(len(records) for records in self._consents.values()),
        }


# =============================================================================
# Global Instance
# =============================================================================

_CONSENT_MANAGER: ConsentManager | None = None


def get_consent_manager() -> ConsentManager:
    """Get global consent manager instance."""
    global _CONSENT_MANAGER
    if _CONSENT_MANAGER is None:
        _CONSENT_MANAGER = ConsentManager()
    return _CONSENT_MANAGER
