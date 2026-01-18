"""Intelligent Notification Curator.

This is NOT a dumb event pump. This is a thoughtful curator that:
1. Decides if something is WORTH Tim's attention
2. Chooses the RIGHT medium (voice, image, ambient, slack)
3. Creates BEAUTIFUL artifacts when it does communicate
4. Respects context (time, focus, importance)

Philosophy: Every notification should be worth looking at.
If Jony Ive would throw up, don't send it.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class NotificationMedium(Enum):
    """How to deliver a notification."""

    SILENT = "silent"  # Log only, don't interrupt
    AMBIENT = "ambient"  # Lights, subtle indicators
    SLACK_QUIET = "slack_quiet"  # Slack, no ping
    SLACK = "slack"  # Slack with notification
    VOICE = "voice"  # Speak through home
    VOICE_URGENT = "voice_urgent"  # Speak + lights flash
    RICH_ARTIFACT = "rich_artifact"  # Generate image/HTML


class ImportanceLevel(Enum):
    """How important is this, really?"""

    NOISE = 0  # Don't even log
    BACKGROUND = 1  # Log for my records
    LOW = 2  # Ambient indicator maybe
    NORMAL = 3  # Batch into digest
    ELEVATED = 4  # Worth a quiet Slack message
    HIGH = 5  # Worth interrupting
    CRITICAL = 6  # Voice + lights + everything


@dataclass
class CuratedEvent:
    """An event that's been evaluated for importance."""

    source: str
    event_type: str
    raw_data: dict
    importance: ImportanceLevel
    medium: NotificationMedium
    summary: str  # One sentence, compelling
    detail: str | None = None  # More context if needed
    artifact_url: str | None = None  # Generated image/HTML
    timestamp: datetime = field(default_factory=datetime.now)


class NotificationCurator:
    """Curates notifications with taste and intelligence.

    This is the gatekeeper. It decides:
    - Is this worth Tim's attention AT ALL?
    - If yes, what's the RIGHT way to tell him?
    - How do I make this communication BEAUTIFUL?

    Example:
        >>> curator = NotificationCurator()
        >>> await curator.initialize()
        >>>
        >>> # Don't spam about every email
        >>> event = await curator.evaluate({
        ...     "source": "gmail",
        ...     "type": "new_email",
        ...     "count": 5,
        ...     "subjects": ["Re: meeting", "Newsletter", ...]
        ... })
        >>>
        >>> if event.importance >= ImportanceLevel.ELEVATED:
        ...     await curator.deliver(event)
    """

    def __init__(self) -> None:
        """Initialize curator with taste."""
        self._composio = None
        self._slack = None
        self._last_digest: datetime | None = None
        self._pending_events: list[dict] = []
        self._state_cache: dict[str, Any] = {}

    async def initialize(self) -> None:
        """Set up connections."""
        from kagami.core.services.composio import get_composio_service

        self._composio = get_composio_service()
        await self._composio.initialize()

        # Wire Slack for curated notifications
        try:
            from kagami.core.integrations.slack_realtime import get_slack_realtime

            self._slack = await get_slack_realtime()
            logger.info("✅ Curator wired to Slack")
        except Exception as e:
            logger.warning(f"Slack not available for curator: {e}")

    async def evaluate(self, raw_event: dict) -> CuratedEvent:
        """Evaluate an event and decide its fate.

        This is where taste lives. We ask:
        - Is this actually important?
        - Has Tim already seen this?
        - Is this part of a pattern (batch it)?
        - What's the RIGHT medium?
        """
        source = raw_event.get("source", "unknown")
        event_type = raw_event.get("type", "unknown")

        # Route to specific evaluators
        if source == "gmail":
            return await self._evaluate_email(raw_event)
        elif source == "github":
            return await self._evaluate_github(raw_event)
        elif source == "calendar":
            return await self._evaluate_calendar(raw_event)
        elif source == "figma":
            return await self._evaluate_figma(raw_event)
        else:
            # Default: probably not important
            return CuratedEvent(
                source=source,
                event_type=event_type,
                raw_data=raw_event,
                importance=ImportanceLevel.BACKGROUND,
                medium=NotificationMedium.SILENT,
                summary=f"Event from {source}",
            )

    async def _evaluate_email(self, event: dict) -> CuratedEvent:
        """Evaluate email importance with actual intelligence.

        Not every email matters. We look for:
        - Is it from someone important?
        - Does the subject suggest urgency?
        - Is it a reply to something Tim sent?
        - Is it actionable?
        """
        emails = event.get("emails", [])

        # Filter to actually interesting emails
        interesting = []
        for email in emails:
            sender = email.get("from", "").lower()
            subject = email.get("subject", "").lower()

            # VIP senders always matter
            vips = ["@apple.com", "@anthropic.com", "@figma.com", "important"]
            if any(vip in sender for vip in vips):
                interesting.append(email)
                continue

            # Urgent keywords
            urgent_words = ["urgent", "asap", "important", "action required", "deadline"]
            if any(word in subject for word in urgent_words):
                interesting.append(email)
                continue

            # Skip obvious noise
            noise_words = ["newsletter", "unsubscribe", "promotion", "sale"]
            if any(word in subject for word in noise_words):
                continue

            # Everything else goes to batch
            interesting.append(email)

        if not interesting:
            return CuratedEvent(
                source="gmail",
                event_type="new_emails",
                raw_data=event,
                importance=ImportanceLevel.NOISE,
                medium=NotificationMedium.SILENT,
                summary="Only noise in inbox",
            )

        # One important email? Tell Tim specifically
        if len(interesting) == 1:
            email = interesting[0]
            return CuratedEvent(
                source="gmail",
                event_type="important_email",
                raw_data=event,
                importance=ImportanceLevel.ELEVATED,
                medium=NotificationMedium.SLACK_QUIET,
                summary=f"From {email.get('from', 'someone')}: {email.get('subject', 'No subject')}",
            )

        # Multiple? Batch into a beautiful summary
        return CuratedEvent(
            source="gmail",
            event_type="email_digest",
            raw_data=event,
            importance=ImportanceLevel.NORMAL,
            medium=NotificationMedium.SLACK_QUIET,
            summary=f"{len(interesting)} emails worth reading",
            detail="\n".join(f"• {e.get('subject', '?')}" for e in interesting[:5]),
        )

    async def _evaluate_github(self, event: dict) -> CuratedEvent:
        """Evaluate GitHub events.

        CI failure on main = CRITICAL
        CI pass = SILENT (expected behavior)
        PR merged = maybe worth noting
        """
        event_type = event.get("type", "")

        if event_type == "ci_failure":
            branch = event.get("branch", "unknown")
            if branch == "main":
                return CuratedEvent(
                    source="github",
                    event_type="ci_failure",
                    raw_data=event,
                    importance=ImportanceLevel.CRITICAL,
                    medium=NotificationMedium.VOICE,
                    summary=f"CI broken on main: {event.get('workflow', 'build')}",
                )
            else:
                # Branch failure - less urgent
                return CuratedEvent(
                    source="github",
                    event_type="ci_failure",
                    raw_data=event,
                    importance=ImportanceLevel.ELEVATED,
                    medium=NotificationMedium.SLACK_QUIET,
                    summary=f"CI failed on {branch}",
                )

        elif event_type == "ci_pass":
            # Expected. Don't celebrate normal.
            return CuratedEvent(
                source="github",
                event_type="ci_pass",
                raw_data=event,
                importance=ImportanceLevel.BACKGROUND,
                medium=NotificationMedium.SILENT,
                summary="CI passed (as expected)",
            )

        elif event_type == "pr_merged":
            return CuratedEvent(
                source="github",
                event_type="pr_merged",
                raw_data=event,
                importance=ImportanceLevel.LOW,
                medium=NotificationMedium.AMBIENT,
                summary=f"Merged: {event.get('title', 'PR')}",
            )

        return CuratedEvent(
            source="github",
            event_type=event_type,
            raw_data=event,
            importance=ImportanceLevel.BACKGROUND,
            medium=NotificationMedium.SILENT,
            summary=f"GitHub: {event_type}",
        )

    async def _evaluate_calendar(self, event: dict) -> CuratedEvent:
        """Evaluate calendar events.

        Meeting in 5 min = HIGH (voice reminder)
        Meeting in 15 min = NORMAL (slack)
        All-day event = BACKGROUND
        """
        minutes_until = event.get("minutes_until", 60)
        summary = event.get("summary", "Event")

        if minutes_until <= 5:
            return CuratedEvent(
                source="calendar",
                event_type="imminent",
                raw_data=event,
                importance=ImportanceLevel.HIGH,
                medium=NotificationMedium.VOICE,
                summary=f"{summary} starts in {minutes_until} minutes",
            )
        elif minutes_until <= 15:
            return CuratedEvent(
                source="calendar",
                event_type="soon",
                raw_data=event,
                importance=ImportanceLevel.NORMAL,
                medium=NotificationMedium.SLACK_QUIET,
                summary=f"{summary} in {minutes_until} min",
            )
        else:
            return CuratedEvent(
                source="calendar",
                event_type="upcoming",
                raw_data=event,
                importance=ImportanceLevel.BACKGROUND,
                medium=NotificationMedium.SILENT,
                summary=f"{summary} later",
            )

    async def _evaluate_figma(self, event: dict) -> CuratedEvent:
        """Evaluate Figma events.

        Comment mentioning Tim = ELEVATED
        Design QA request = HIGH
        General activity = SILENT
        """
        comment = event.get("message", "")

        if "@tim" in comment.lower() or "@design-qa" in comment.lower():
            return CuratedEvent(
                source="figma",
                event_type="mention",
                raw_data=event,
                importance=ImportanceLevel.ELEVATED,
                medium=NotificationMedium.SLACK,
                summary=f"Figma: {comment[:50]}...",
            )

        return CuratedEvent(
            source="figma",
            event_type="activity",
            raw_data=event,
            importance=ImportanceLevel.BACKGROUND,
            medium=NotificationMedium.SILENT,
            summary="Figma activity",
        )

    async def deliver(self, event: CuratedEvent) -> bool:
        """Deliver a curated event through its chosen medium.

        This is where we make it BEAUTIFUL.
        """
        if event.medium == NotificationMedium.SILENT:
            logger.debug(f"[SILENT] {event.summary}")
            return True

        if event.medium == NotificationMedium.AMBIENT:
            return await self._deliver_ambient(event)

        if event.medium in (NotificationMedium.SLACK, NotificationMedium.SLACK_QUIET):
            return await self._deliver_slack(event)

        if event.medium in (NotificationMedium.VOICE, NotificationMedium.VOICE_URGENT):
            return await self._deliver_voice(event)

        return False

    async def _deliver_ambient(self, event: CuratedEvent) -> bool:
        """Deliver through ambient indicators (lights)."""
        try:
            import sys

            sys.path.insert(0, "packages")
            from kagami_smarthome import get_smart_home

            controller = await get_smart_home()
            # Subtle pulse in office
            await controller.set_lights(70, rooms=["Office"])
            await asyncio.sleep(0.5)
            await controller.set_lights(60, rooms=["Office"])
            return True
        except Exception as e:
            logger.warning(f"Ambient delivery failed: {e}")
            return False

    async def _deliver_slack(self, event: CuratedEvent) -> bool:
        """Deliver to Slack with beautiful formatting."""
        # Build rich Slack blocks
        blocks = self._build_slack_blocks(event)

        try:
            result = await self._composio.execute_action(
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL",
                {
                    "channel": "#all-awkronos",
                    "text": event.summary,  # Fallback
                    "blocks": blocks,
                },
            )
            return result.get("success", False)
        except Exception as e:
            logger.error(f"Slack delivery failed: {e}")
            return False

    def _build_slack_blocks(self, event: CuratedEvent) -> list[dict]:
        """Build beautiful Slack blocks for an event."""
        # Icon based on source
        icons = {
            "gmail": "📧",
            "github": "🔧",
            "calendar": "📅",
            "figma": "🎨",
        }
        icon = icons.get(event.source, "💫")

        # Importance indicator
        importance_bar = {
            ImportanceLevel.CRITICAL: "🔴",
            ImportanceLevel.HIGH: "🟠",
            ImportanceLevel.ELEVATED: "🟡",
            ImportanceLevel.NORMAL: "🟢",
        }.get(event.importance, "")

        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"{importance_bar} {icon} *{event.summary}*"},
            }
        ]

        if event.detail:
            blocks.append(
                {"type": "context", "elements": [{"type": "mrkdwn", "text": event.detail}]}
            )

        return blocks

    async def _deliver_voice(self, event: CuratedEvent) -> bool:
        """Speak through the home."""
        try:
            import sys

            sys.path.insert(0, "packages")
            from kagami_smarthome import get_smart_home

            controller = await get_smart_home()

            # If urgent, flash lights first
            if event.medium == NotificationMedium.VOICE_URGENT:
                await controller.set_lights(100, rooms=["Living Room"])
                await asyncio.sleep(0.3)
                await controller.set_lights(50, rooms=["Living Room"])

            await controller.announce(event.summary, rooms=["Living Room", "Office"])
            return True
        except Exception as e:
            logger.error(f"Voice delivery failed: {e}")
            return False


# Singleton
_curator: NotificationCurator | None = None


async def get_curator() -> NotificationCurator:
    """Get or create the notification curator."""
    global _curator
    if _curator is None:
        _curator = NotificationCurator()
        await _curator.initialize()
    return _curator
