"""Unified Safety Messages — Consistent, Helpful Safety Communication.

All safety rejections should feel helpful, not blocking. This module provides
a unified voice for safety-related communications across Kagami.

Design Principles:
==================
1. Explain WHY, not just WHAT
2. Offer alternatives when possible
3. Use first-person voice ("I cannot...")
4. Be reassuring, not alarming
5. Include the safety score for transparency

Architecture:
```
SafetyViolation → SafetyMessageFormatter → User-Facing Message
                         │
                    ┌────┴────┐
                    │ Context │
                    └─────────┘
                    • h(x) value
                    • Violation type
                    • Suggested alternative
```

Colony: Crystal (e7) — Verification
Created: December 31, 2025
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SafetyViolationType(Enum):
    """Types of safety violations."""

    # Physical safety
    LOCK_WHILE_AWAY = "lock_while_away"
    UNLOCK_UNVERIFIED = "unlock_unverified"
    FIREPLACE_EXTENDED = "fireplace_extended"
    FIREPLACE_UNOCCUPIED = "fireplace_unoccupied"
    TV_MOUNT_OBSTRUCTION = "tv_mount_obstruction"

    # Temporal safety
    ANNOUNCEMENT_SLEEP_HOURS = "announcement_sleep_hours"
    LOUD_AUDIO_LATE = "loud_audio_late"

    # State safety
    CONFLICTING_ACTIONS = "conflicting_actions"
    SYSTEM_OVERLOAD = "system_overload"

    # Privacy safety
    CAMERA_RECORDING_DENIED = "camera_recording_denied"
    LOCATION_SHARING_DENIED = "location_sharing_denied"

    # General
    UNKNOWN = "unknown"


@dataclass
class SafetyContext:
    """Context for safety message formatting."""

    violation_type: SafetyViolationType
    h_x: float  # Current barrier value
    requested_action: str
    current_state: dict[str, Any] = field(default_factory=dict)
    suggested_alternative: str | None = None
    can_override: bool = False
    override_confirmation: str | None = None


@dataclass
class SafetyMessage:
    """Formatted safety message for user display."""

    title: str
    body: str
    h_x: float
    severity: str  # "info", "warning", "critical"
    suggested_action: str | None = None
    can_override: bool = False
    override_prompt: str | None = None


# =============================================================================
# MESSAGE TEMPLATES
# =============================================================================

_TEMPLATES: dict[SafetyViolationType, dict[str, str]] = {
    SafetyViolationType.LOCK_WHILE_AWAY: {
        "title": "Door Already Secured",
        "body": "I cannot unlock the {door} while you're away from home. This is a safety measure to protect your home.",
        "suggestion": "I can unlock it when you arrive, or you can confirm your identity to override.",
        "severity": "warning",
    },
    SafetyViolationType.UNLOCK_UNVERIFIED: {
        "title": "Identity Verification Required",
        "body": "I need to verify your identity before unlocking the {door}. This protects against unauthorized access.",
        "suggestion": "Please confirm via the app or use your fingerprint.",
        "severity": "warning",
    },
    SafetyViolationType.FIREPLACE_EXTENDED: {
        "title": "Fireplace Safety Limit",
        "body": "The fireplace has been on for {duration} minutes. For safety, I'm turning it off to prevent overheating.",
        "suggestion": "You can restart it after a 30-minute cooldown period.",
        "severity": "info",
    },
    SafetyViolationType.FIREPLACE_UNOCCUPIED: {
        "title": "Room Unoccupied",
        "body": "I cannot turn on the fireplace because no one appears to be in the living room. Unattended fires are a safety concern.",
        "suggestion": "I'll turn it on automatically when you enter the room.",
        "severity": "warning",
    },
    SafetyViolationType.TV_MOUNT_OBSTRUCTION: {
        "title": "TV Movement Blocked",
        "body": "I detected something that might obstruct the TV mount's movement. Moving it now could cause damage.",
        "suggestion": "Please clear the area below the TV and try again.",
        "severity": "warning",
    },
    SafetyViolationType.ANNOUNCEMENT_SLEEP_HOURS: {
        "title": "Sleep Hours Active",
        "body": "I'm not making announcements right now because it's {time} and sleep mode is active.",
        "suggestion": "I'll deliver this message when you wake up, or I can send it to your phone silently.",
        "severity": "info",
    },
    SafetyViolationType.LOUD_AUDIO_LATE: {
        "title": "Late Night Audio Limit",
        "body": "I've limited the volume to {max_volume}% because it's after {time}. This helps maintain peace with neighbors.",
        "suggestion": "You can use headphones for full volume, or I can adjust the limit in settings.",
        "severity": "info",
    },
    SafetyViolationType.CONFLICTING_ACTIONS: {
        "title": "Action Conflict Detected",
        "body": "This action conflicts with {conflicting_action} which is currently active. Running both could cause unexpected behavior.",
        "suggestion": "I can queue this action to run after the current one completes.",
        "severity": "warning",
    },
    SafetyViolationType.SYSTEM_OVERLOAD: {
        "title": "System Busy",
        "body": "I'm processing multiple requests right now and need a moment to catch up. This prevents errors.",
        "suggestion": "Your request is queued and will complete shortly.",
        "severity": "info",
    },
    SafetyViolationType.CAMERA_RECORDING_DENIED: {
        "title": "Privacy Protection",
        "body": "Camera recording in {room} is disabled by your privacy settings.",
        "suggestion": "You can adjust privacy settings in the app if needed.",
        "severity": "info",
    },
    SafetyViolationType.LOCATION_SHARING_DENIED: {
        "title": "Location Privacy",
        "body": "Location sharing is turned off. I can't determine your position for this feature.",
        "suggestion": "Enable location sharing in settings to use presence-aware features.",
        "severity": "info",
    },
    SafetyViolationType.UNKNOWN: {
        "title": "Safety Check",
        "body": "I've paused this action for a safety review. This is a precautionary measure.",
        "suggestion": "Please try again in a moment, or contact support if this persists.",
        "severity": "warning",
    },
}


# =============================================================================
# FORMATTER
# =============================================================================


class SafetyMessageFormatter:
    """Formats safety violations into user-friendly messages.

    Usage:
        formatter = SafetyMessageFormatter()
        context = SafetyContext(
            violation_type=SafetyViolationType.FIREPLACE_EXTENDED,
            h_x=0.15,
            requested_action="keep fireplace on",
            current_state={"duration": 180},
        )
        message = formatter.format(context)
        print(message.body)
        # "The fireplace has been on for 180 minutes..."
    """

    def format_message(self, context: SafetyContext) -> SafetyMessage:
        """Format a safety context into a user-facing message.

        Args:
            context: Safety violation context

        Returns:
            Formatted SafetyMessage ready for display
        """
        template = _TEMPLATES.get(
            context.violation_type,
            _TEMPLATES[SafetyViolationType.UNKNOWN],
        )

        # Format body with context variables
        body = template["body"]
        for key, value in context.current_state.items():
            body = body.replace(f"{{{key}}}", str(value))

        # Format suggestion
        suggestion = template.get("suggestion", context.suggested_alternative)
        if suggestion:
            for key, value in context.current_state.items():
                suggestion = suggestion.replace(f"{{{key}}}", str(value))

        # Determine override prompt
        override_prompt = None
        if context.can_override:
            override_prompt = (
                context.override_confirmation or "Confirm to override this safety check"
            )

        return SafetyMessage(
            title=template["title"],
            body=body,
            h_x=context.h_x,
            severity=template["severity"],
            suggested_action=suggestion,
            can_override=context.can_override,
            override_prompt=override_prompt,
        )

    def format_quick(
        self,
        violation_type: SafetyViolationType,
        h_x: float,
        **kwargs: Any,
    ) -> SafetyMessage:
        """Quick format without creating explicit context.

        Args:
            violation_type: Type of safety violation
            h_x: Current barrier value
            **kwargs: State variables for template substitution

        Returns:
            Formatted SafetyMessage
        """
        context = SafetyContext(
            violation_type=violation_type,
            h_x=h_x,
            requested_action=kwargs.pop("action", "action"),
            current_state=kwargs,
        )
        return self.format_message(context)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_default_formatter = SafetyMessageFormatter()


def format_safety_message(context: SafetyContext) -> SafetyMessage:
    """Format a safety context using the default formatter."""
    return _default_formatter.format_message(context)


def format_safety_quick(
    violation_type: SafetyViolationType,
    h_x: float,
    **kwargs: Any,
) -> SafetyMessage:
    """Quick format using the default formatter."""
    return _default_formatter.format_quick(violation_type, h_x, **kwargs)


def get_safety_explanation(h_x: float) -> str:
    """Get a human-readable explanation of the safety score.

    Args:
        h_x: Barrier function value

    Returns:
        Human-readable explanation
    """
    if h_x >= 0.7:
        return f"Safety score: {h_x:.0%} — All systems operating normally."
    elif h_x >= 0.3:
        return f"Safety score: {h_x:.0%} — Some caution applied, monitoring closely."
    elif h_x >= 0.0:
        return f"Safety score: {h_x:.0%} — Operating near safety boundary, extra care taken."
    else:
        return f"Safety score: {h_x:.0%} — Action blocked to prevent unsafe state."


__all__ = [
    "SafetyContext",
    "SafetyMessage",
    "SafetyMessageFormatter",
    "SafetyViolationType",
    "format_safety_message",
    "format_safety_quick",
    "get_safety_explanation",
]
