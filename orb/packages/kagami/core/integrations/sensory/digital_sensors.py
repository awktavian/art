"""Digital Sensor Manager - calendar write operations and digital service management.

This module provides the DigitalSensorManager class for managing calendar events
and other digital services via Composio.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.services.composio import ComposioIntegrationService

logger = logging.getLogger(__name__)


class DigitalSensorManager:
    """Manager for digital services with calendar write operations.

    This class provides methods for creating, updating, and deleting calendar events
    via the Composio integration.
    """

    def __init__(self, composio: Any = None):
        """Initialize the digital sensor manager.

        Args:
            composio: Optional Composio service instance
        """
        self._composio: ComposioIntegrationService | None = composio

    def set_composio(self, composio: Any) -> None:
        """Set the Composio service.

        Args:
            composio: Composio service instance
        """
        self._composio = composio

    async def create_calendar_event(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        description: str | None = None,
        location: str | None = None,
        attendees: list[str] | None = None,
        timezone: str | None = None,
        visibility: str | None = None,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Create a new calendar event.

        Args:
            summary: Event title/summary
            start_time: Start time in ISO format
            end_time: End time in ISO format
            description: Optional event description
            location: Optional event location
            attendees: Optional list of attendee email addresses
            timezone: Optional timezone (e.g., "America/Los_Angeles")
            visibility: Optional visibility ("default", "public", "private")
            calendar_id: Calendar ID (default: "primary")

        Returns:
            dict with success status, event_id, and html_link on success,
            or error message on failure
        """
        if not self._composio:
            return {"success": False, "error": "Composio not available"}

        try:
            # Build start/end time objects
            start = {"dateTime": start_time}
            end = {"dateTime": end_time}

            if timezone:
                start["timeZone"] = timezone
                end["timeZone"] = timezone

            params: dict[str, Any] = {
                "summary": summary,
                "start": start,
                "end": end,
                "calendar_id": calendar_id,
            }

            if description:
                params["description"] = description

            if location:
                params["location"] = location

            if attendees:
                params["attendees"] = [{"email": email} for email in attendees]

            if visibility:
                params["visibility"] = visibility

            result = await self._composio.execute_action("GOOGLECALENDAR_CREATE_EVENT", params)

            if result.get("success"):
                event_data = result.get("result", {})
                return {
                    "success": True,
                    "event_id": event_data.get("id"),
                    "html_link": event_data.get("htmlLink"),
                    "event": event_data,
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to create event"),
                }

        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}")
            return {"success": False, "error": str(e)}

    async def update_calendar_event(
        self,
        event_id: str,
        summary: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        description: str | None = None,
        location: str | None = None,
        attendees: list[str] | None = None,
        timezone: str | None = None,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Update an existing calendar event.

        Args:
            event_id: ID of the event to update
            summary: Optional new event title
            start_time: Optional new start time in ISO format
            end_time: Optional new end time in ISO format
            description: Optional new event description
            location: Optional new event location
            attendees: Optional new list of attendee email addresses
            timezone: Optional timezone for start/end times
            calendar_id: Calendar ID (default: "primary")

        Returns:
            dict with success status and updated event data
        """
        if not self._composio:
            return {"success": False, "error": "Composio not available"}

        try:
            params: dict[str, Any] = {
                "event_id": event_id,
                "calendar_id": calendar_id,
            }

            if summary:
                params["summary"] = summary

            if start_time:
                start = {"dateTime": start_time}
                if timezone:
                    start["timeZone"] = timezone
                params["start"] = start

            if end_time:
                end = {"dateTime": end_time}
                if timezone:
                    end["timeZone"] = timezone
                params["end"] = end

            if description:
                params["description"] = description

            if location:
                params["location"] = location

            if attendees:
                params["attendees"] = [{"email": email} for email in attendees]

            result = await self._composio.execute_action("GOOGLECALENDAR_PATCH_EVENT", params)

            if result.get("success"):
                return {
                    "success": True,
                    "event_id": event_id,
                    "event": result.get("result", {}),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to update event"),
                }

        except Exception as e:
            logger.error(f"Failed to update calendar event: {e}")
            return {"success": False, "error": str(e)}

    async def delete_calendar_event(
        self,
        event_id: str,
        send_updates: str | None = None,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Delete a calendar event.

        Args:
            event_id: ID of the event to delete
            send_updates: Notification setting ("all", "externalOnly", "none")
            calendar_id: Calendar ID (default: "primary")

        Returns:
            dict with success status
        """
        if not self._composio:
            return {"success": False, "error": "Composio not available"}

        try:
            params: dict[str, Any] = {
                "event_id": event_id,
                "calendar_id": calendar_id,
            }

            if send_updates:
                params["send_updates"] = send_updates

            result = await self._composio.execute_action("GOOGLECALENDAR_DELETE_EVENT", params)

            if result.get("success"):
                return {
                    "success": True,
                    "event_id": event_id,
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to delete event"),
                }

        except Exception as e:
            logger.error(f"Failed to delete calendar event: {e}")
            return {"success": False, "error": str(e)}

    async def quick_add_calendar_event(
        self,
        text: str,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Quick add a calendar event using natural language.

        Args:
            text: Natural language event description (e.g., "Meeting with Tim tomorrow at 3pm")
            calendar_id: Calendar ID (default: "primary")

        Returns:
            dict with success status and event details
        """
        if not self._composio:
            return {"success": False, "error": "Composio not available"}

        try:
            params = {
                "text": text,
                "calendar_id": calendar_id,
            }

            result = await self._composio.execute_action("GOOGLECALENDAR_QUICK_ADD_EVENT", params)

            if result.get("success"):
                event_data = result.get("result", {})
                return {
                    "success": True,
                    "event_id": event_data.get("id"),
                    "event": event_data,
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to quick add event"),
                }

        except Exception as e:
            logger.error(f"Failed to quick add calendar event: {e}")
            return {"success": False, "error": str(e)}

    async def get_calendar_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Get details of a specific calendar event.

        Args:
            event_id: ID of the event to retrieve
            calendar_id: Calendar ID (default: "primary")

        Returns:
            dict with success status and event details
        """
        if not self._composio:
            return {"success": False, "error": "Composio not available"}

        try:
            params = {
                "event_id": event_id,
                "calendar_id": calendar_id,
            }

            result = await self._composio.execute_action("GOOGLECALENDAR_GET_EVENT", params)

            if result.get("success"):
                return {
                    "success": True,
                    "event": result.get("result", {}),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to get event"),
                }

        except Exception as e:
            logger.error(f"Failed to get calendar event: {e}")
            return {"success": False, "error": str(e)}

    async def find_free_slots(
        self,
        time_min: str,
        time_max: str,
        calendar_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Find free/busy time slots in calendar(s).

        Args:
            time_min: Start of time range (ISO format)
            time_max: End of time range (ISO format)
            calendar_ids: Optional list of calendar IDs (default: ["primary"])

        Returns:
            dict with success status and free/busy information
        """
        if not self._composio:
            return {"success": False, "error": "Composio not available"}

        try:
            if calendar_ids is None:
                calendar_ids = ["primary"]

            params = {
                "time_min": time_min,
                "time_max": time_max,
                "items": [{"id": cal_id} for cal_id in calendar_ids],
            }

            result = await self._composio.execute_action("GOOGLECALENDAR_FREE_BUSY_QUERY", params)

            if result.get("success"):
                return {
                    "success": True,
                    "free_busy": result.get("result", {}),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to query free/busy"),
                }

        except Exception as e:
            logger.error(f"Failed to find free slots: {e}")
            return {"success": False, "error": str(e)}


__all__ = ["DigitalSensorManager"]
