"""Digital sensors - email, calendar, github, linear, slack, figma.

These sensors integrate with digital services via Composio or direct OAuth.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from .base import CachedSense, SenseType

if TYPE_CHECKING:
    from kagami.core.services.composio import ComposioIntegrationService

logger = logging.getLogger(__name__)


class DigitalSensors:
    """Digital sensing capabilities via Composio and direct OAuth."""

    def __init__(
        self,
        cache: dict[SenseType, CachedSense],
        stats: dict[str, Any],
        composio: Any = None,
    ):
        self._cache = cache
        self._stats = stats
        self._composio: ComposioIntegrationService | None = composio

    def set_composio(self, composio: Any) -> None:
        """Set the Composio service."""
        self._composio = composio

    def _get_cached(self, sense_type: SenseType) -> CachedSense | None:
        """Get cached data if valid."""
        cached = self._cache.get(sense_type)
        if cached and cached.is_valid:
            self._stats["cache_hits"] += 1
            return cached
        self._stats["cache_misses"] += 1
        return None

    async def poll_gmail(self) -> dict[str, Any]:
        """Poll Gmail for urgent/unread emails."""
        cached = self._get_cached(SenseType.GMAIL)
        if cached:
            return cached.data

        if not self._composio or not self._composio.initialized:
            return {"urgent_count": 0, "unread_count": 0}

        try:
            urgent_result = await self._composio.execute_action(
                "GMAIL_FETCH_EMAILS", {"query": "is:unread is:important", "max_results": 10}
            )

            urgent_count = 0
            urgent_senders: list[str] = []
            if urgent_result.get("success"):
                emails = urgent_result.get("result", {}).get("data", {}).get("emails", [])
                urgent_count = len(emails)
                urgent_senders = [e.get("from", "")[:30] for e in emails[:3]]

            data = {
                "urgent_count": urgent_count,
                "urgent_senders": urgent_senders,
                "timestamp": datetime.now().isoformat(),
            }

            return data

        except Exception as e:
            logger.debug(f"Gmail poll failed: {e}")
            return {"urgent_count": 0, "error": str(e)}

    async def poll_github(self) -> dict[str, Any]:
        """Poll GitHub for notifications and activity."""
        cached = self._get_cached(SenseType.GITHUB)
        if cached:
            return cached.data

        if not self._composio or not self._composio.initialized:
            return {"notifications": 0}

        try:
            user_result = await self._composio.execute_action(
                "GITHUB_GET_THE_AUTHENTICATED_USER", {}
            )

            user_data = {}
            if user_result.get("success"):
                result_data = user_result.get("result", {}).get("data", {})
                user_data = {
                    "login": result_data.get("login"),
                    "public_repos": result_data.get("public_repos", 0),
                }

            data = {
                "user": user_data,
                "notifications": 0,
                "timestamp": datetime.now().isoformat(),
            }

            return data

        except Exception as e:
            logger.debug(f"GitHub poll failed: {e}")
            return {"notifications": 0, "error": str(e)}

    async def poll_linear(self) -> dict[str, Any]:
        """Poll Linear for active issues."""
        cached = self._get_cached(SenseType.LINEAR)
        if cached:
            return cached.data

        if not self._composio or not self._composio.initialized:
            return {"active_count": 0}

        try:
            teams_result = await self._composio.execute_action("LINEAR_GET_ALL_LINEAR_TEAMS", {})

            teams_data = {}
            if teams_result.get("success"):
                result_data = teams_result.get("result", {}).get("data", {})
                teams = result_data.get("teams", {}).get("nodes", [])
                teams_data = {
                    "team_count": len(teams),
                    "teams": [t.get("name") for t in teams[:5]],
                }

            data = {
                "teams": teams_data,
                "active_count": 0,
                "timestamp": datetime.now().isoformat(),
            }

            return data

        except Exception as e:
            logger.debug(f"Linear poll failed: {e}")
            return {"active_count": 0, "error": str(e)}

    async def poll_slack(self, route_messages_callback: Any = None) -> dict[str, Any]:
        """Poll Slack for new messages.

        Args:
            route_messages_callback: Optional callback to route new messages
        """
        cached = self._get_cached(SenseType.SLACK)
        if cached:
            return cached.data

        if not self._composio or not self._composio.initialized:
            return {"messages": [], "unread": 0}

        try:
            channel_id = "C099P6LUL14"

            result = await self._composio.execute_action(
                "SLACK_FETCH_CONVERSATION_HISTORY",
                {"channel": channel_id, "limit": 10},
            )

            messages = []
            new_human_messages = []

            if result.get("success"):
                result_data = result.get("result", {}).get("data", {})
                raw_messages = result_data.get("messages", [])

                last_ts = "0"
                if self._cache.get(SenseType.SLACK):
                    last_ts = self._cache[SenseType.SLACK].data.get("last_ts", "0")

                for msg in raw_messages:
                    ts = msg.get("ts", "0")
                    bot_id = msg.get("bot_id")
                    text = msg.get("text", "")
                    user = msg.get("user", "")

                    messages.append(
                        {
                            "ts": ts,
                            "text": text[:100],
                            "user": user,
                            "is_bot": bool(bot_id),
                        }
                    )

                    if not bot_id and float(ts) > float(last_ts):
                        new_human_messages.append(
                            {
                                "ts": ts,
                                "text": text,
                                "user": user,
                            }
                        )

                if new_human_messages and route_messages_callback:
                    await route_messages_callback(new_human_messages)

            newest_ts = max((m.get("ts", "0") for m in messages), default="0")

            data = {
                "messages": messages[:5],
                "new_count": len(new_human_messages),
                "last_ts": newest_ts,
                "timestamp": datetime.now().isoformat(),
            }

            return data

        except Exception as e:
            logger.debug(f"Slack poll failed: {e}")
            return {"messages": [], "unread": 0, "error": str(e)}

    async def poll_figma(self) -> dict[str, Any]:
        """Poll Figma for comments and design updates using direct OAuth client."""
        cached = self._get_cached(SenseType.FIGMA)
        if cached:
            return cached.data

        try:
            from kagami.core.integrations.figma_direct import get_figma_client

            client = await get_figma_client()

            design_system_file = "27pdTgOq30LHZuaeVYtkEN"
            comments_response = await client.get_comments(design_system_file)
            comments = comments_response.get("comments", [])

            design_qa_comments = [
                c
                for c in comments
                if "@design-qa" in c.get("message", "").lower() and not c.get("resolved_at")
            ]

            file_response = await client.get_file(design_system_file, depth=1)

            data = {
                "file_name": file_response.get("name", "Unknown"),
                "last_modified": file_response.get("lastModified"),
                "comment_count": len(comments),
                "unresolved_qa": len(design_qa_comments),
                "design_qa_comments": [
                    {
                        "id": c.get("id"),
                        "message": c.get("message", "")[:200],
                        "user": c.get("user", {}).get("handle"),
                        "created_at": c.get("created_at"),
                    }
                    for c in design_qa_comments[:5]
                ],
                "timestamp": datetime.now().isoformat(),
            }

            return data

        except Exception as e:
            logger.debug(f"Figma poll failed: {e}")
            return {"comment_count": 0, "error": str(e)}

    async def poll_calendar(self) -> dict[str, Any]:
        """Poll calendar for upcoming events (Google Calendar via Composio)."""
        cached = self._get_cached(SenseType.CALENDAR)
        if cached:
            return cached.data

        if not self._composio or not self._composio.initialized:
            return {"events": [], "next_event": None}

        try:
            now = datetime.now()
            time_min = now.isoformat() + "Z"
            time_max = (now + timedelta(hours=24)).isoformat() + "Z"

            result = await self._composio.execute_action(
                "GOOGLECALENDAR_FIND_EVENT",
                {
                    "time_min": time_min,
                    "time_max": time_max,
                    "max_results": 10,
                },
            )

            events = []
            next_event = None
            next_meeting_minutes = None

            if result.get("success"):
                raw_events = result.get("result", {}).get("data", {}).get("items", [])
                for event in raw_events:
                    start = event.get("start", {})
                    start_time = start.get("dateTime") or start.get("date")

                    event_data = {
                        "summary": event.get("summary", "Untitled"),
                        "start": start_time,
                        "attendees": len(event.get("attendees", [])),
                        "is_meeting": len(event.get("attendees", [])) > 0,
                    }
                    events.append(event_data)

                    if start_time and not next_event:
                        try:
                            event_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                            if event_dt > now:
                                next_event = event_data
                                next_meeting_minutes = int((event_dt - now).total_seconds() / 60)
                        except Exception:
                            pass

            data = {
                "events": events,
                "event_count": len(events),
                "next_event": next_event,
                "next_meeting_minutes": next_meeting_minutes,
                "has_meeting_soon": next_meeting_minutes is not None and next_meeting_minutes <= 15,
                "timestamp": datetime.now().isoformat(),
            }

            return data

        except Exception as e:
            logger.debug(f"Calendar poll failed: {e}")
            return {"events": [], "next_event": None, "error": str(e)}

    async def poll_social(self, get_cached_sense: Any) -> dict[str, Any]:
        """Poll and aggregate social/communication urgency."""
        cached = self._get_cached(SenseType.SOCIAL)
        if cached:
            return cached.data

        urgency_score = 0.0
        urgent_items: list[dict[str, Any]] = []
        sources: dict[str, Any] = {}

        gmail_data = get_cached_sense(SenseType.GMAIL)
        if gmail_data and gmail_data.is_valid:
            urgent_emails = gmail_data.data.get("urgent_count", 0)
            sources["gmail"] = urgent_emails
            if urgent_emails > 0:
                urgency_score += min(urgent_emails * 0.2, 0.5)
                urgent_items.extend(
                    [
                        {"source": "gmail", "type": "email", "sender": s}
                        for s in gmail_data.data.get("urgent_senders", [])[:3]
                    ]
                )

        linear_data = get_cached_sense(SenseType.LINEAR)
        if linear_data and linear_data.is_valid:
            active_count = linear_data.data.get("active_count", 0)
            sources["linear"] = active_count
            if active_count > 5:
                urgency_score += 0.2

        calendar_data = get_cached_sense(SenseType.CALENDAR)
        if calendar_data and calendar_data.is_valid:
            if calendar_data.data.get("has_meeting_soon"):
                urgency_score += 0.3
                next_evt = calendar_data.data.get("next_event")
                if next_evt:
                    urgent_items.append(
                        {
                            "source": "calendar",
                            "type": "meeting",
                            "summary": next_evt.get("summary"),
                            "minutes": calendar_data.data.get("next_meeting_minutes"),
                        }
                    )

        urgency_score = min(urgency_score, 1.0)

        if urgency_score >= 0.7:
            urgency_level = "high"
        elif urgency_score >= 0.4:
            urgency_level = "medium"
        elif urgency_score >= 0.1:
            urgency_level = "low"
        else:
            urgency_level = "none"

        data = {
            "urgency_score": urgency_score,
            "urgency_level": urgency_level,
            "urgent_items": urgent_items,
            "sources": sources,
            "needs_attention": urgency_score >= 0.4,
            "timestamp": datetime.now().isoformat(),
        }

        return data


__all__ = ["DigitalSensors"]
