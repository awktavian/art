"""Unified Display Service for Kagami.

HIGH-LEVEL DISPLAY PRIMITIVES that route through:
  HAL → EventBus → AGUI → All Connected Clients

This is THE ONLY way to display content to users. No more:
  - open /tmp/file.png
  - subprocess.call(['open', path])
  - print() for user-facing content

Instead:
  from kagami_hal.display_service import display
  await display.show_qr(url, label="Scan me")
  await display.show_image(path, title="Screenshot")
  await display.show_notification("Task complete", level="success")
  await display.show_modal(title, content, actions=[...])

Created: Jan 1, 2026
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from kagami.core.events import get_unified_bus

logger = logging.getLogger(__name__)


# =============================================================================
# Display Event Types (extend AGUI)
# =============================================================================


class DisplayEventType(str, Enum):
    """Display-specific event types for AGUI."""

    # Image display
    SHOW_IMAGE = "hal.display.show_image"
    SHOW_QR = "hal.display.show_qr"

    # Notifications
    SHOW_NOTIFICATION = "hal.display.notification"
    SHOW_TOAST = "hal.display.toast"

    # Modals/Dialogs
    SHOW_MODAL = "hal.display.modal"
    CLOSE_MODAL = "hal.display.modal_close"
    MODAL_ACTION = "hal.display.modal_action"

    # Progress
    SHOW_PROGRESS = "hal.display.progress"
    UPDATE_PROGRESS = "hal.display.progress_update"
    HIDE_PROGRESS = "hal.display.progress_hide"

    # Rich content
    SHOW_CARD = "hal.display.card"
    SHOW_LIST = "hal.display.list"
    SHOW_TABLE = "hal.display.table"


class NotificationLevel(str, Enum):
    """Notification severity levels."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class DisplayEvent:
    """Display event payload."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: DisplayEventType = DisplayEventType.SHOW_NOTIFICATION
    data: dict[str, Any] = field(default_factory=dict)

    # Targeting
    target_clients: list[str] | None = None  # None = all clients
    target_rooms: list[str] | None = None  # For spatial display (Vision Pro, etc.)

    # Behavior
    auto_dismiss_ms: int | None = None
    priority: int = 0  # Higher = more important

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "data": self.data,
            "target_clients": self.target_clients,
            "target_rooms": self.target_rooms,
            "auto_dismiss_ms": self.auto_dismiss_ms,
            "priority": self.priority,
        }


# =============================================================================
# Display Service
# =============================================================================


class DisplayService:
    """Unified display service for all Kagami output.

    ALL visual output should go through this service:
    - QR codes → show_qr()
    - Images → show_image()
    - Notifications → show_notification()
    - Modals → show_modal()
    - Progress → show_progress()

    The service broadcasts to:
    - All connected AGUI clients (WebSocket, SSE)
    - Desktop app (Tauri)
    - Mobile apps (iOS, Android)
    - Spatial apps (Vision Pro)
    - Voice announcements (when appropriate)
    """

    def __init__(self):
        self._bus = get_unified_bus()
        self._active_modals: dict[str, DisplayEvent] = {}
        self._active_progress: dict[str, DisplayEvent] = {}
        self._modal_callbacks: dict[str, Callable] = {}

    async def _emit(self, event: DisplayEvent) -> str:
        """Emit display event to all listeners."""
        await self._bus.publish(event.type.value, event.to_dict())
        logger.debug(f"Display event: {event.type.value} ({event.id})")
        return event.id

    # =========================================================================
    # QR Codes
    # =========================================================================

    async def show_qr(
        self,
        data: str,
        label: str | None = None,
        sublabel: str | None = None,
        *,
        size: int = 256,
        auto_dismiss_ms: int | None = None,
        target_clients: list[str] | None = None,
    ) -> str:
        """Display a QR code to all connected clients.

        Args:
            data: The data to encode (URL, text, etc.)
            label: Primary label below QR
            sublabel: Secondary label (e.g., URL preview)
            size: QR code size in pixels
            auto_dismiss_ms: Auto-dismiss after N ms (None = manual dismiss)
            target_clients: Specific clients to target (None = all)

        Returns:
            Event ID for tracking/dismissal

        Example:
            >>> await display.show_qr(
            ...     "https://example.com/auth",
            ...     label="🔐 Scan to authenticate",
            ...     sublabel="example.com"
            ... )
        """
        import qrcode

        # Generate QR code
        qr = qrcode.QRCode(
            version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2
        )
        qr.add_data(data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        event = DisplayEvent(
            type=DisplayEventType.SHOW_QR,
            data={
                "qr_data": data,
                "qr_image": f"data:image/png;base64,{qr_base64}",
                "label": label,
                "sublabel": sublabel or data[:50],
                "size": size,
            },
            auto_dismiss_ms=auto_dismiss_ms,
            target_clients=target_clients,
        )

        return await self._emit(event)

    # =========================================================================
    # Images
    # =========================================================================

    async def show_image(
        self,
        image: str | Path | bytes,
        title: str | None = None,
        caption: str | None = None,
        *,
        auto_dismiss_ms: int | None = None,
        target_clients: list[str] | None = None,
    ) -> str:
        """Display an image to all connected clients.

        Args:
            image: Path to image, URL, or raw bytes
            title: Image title
            caption: Image caption/description
            auto_dismiss_ms: Auto-dismiss after N ms
            target_clients: Specific clients to target

        Returns:
            Event ID

        Example:
            >>> await display.show_image(
            ...     "/tmp/screenshot.png",
            ...     title="Desktop Screenshot",
            ...     caption="Captured at 12:34 PM"
            ... )
        """
        # Convert to base64 if needed
        if isinstance(image, bytes):
            image_b64 = base64.b64encode(image).decode("utf-8")
            mime_type = "image/png"
        elif isinstance(image, (str, Path)):
            path = Path(image)
            if path.exists():
                image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
                suffix = path.suffix.lower()
                mime_type = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                    ".svg": "image/svg+xml",
                }.get(suffix, "image/png")
            elif str(image).startswith(("http://", "https://", "data:")):
                # URL or data URI - pass through
                image_b64 = None
                mime_type = None
            else:
                raise FileNotFoundError(f"Image not found: {image}")
        else:
            raise TypeError(f"Invalid image type: {type(image)}")

        event = DisplayEvent(
            type=DisplayEventType.SHOW_IMAGE,
            data={
                "image": f"data:{mime_type};base64,{image_b64}" if image_b64 else str(image),
                "title": title,
                "caption": caption,
            },
            auto_dismiss_ms=auto_dismiss_ms,
            target_clients=target_clients,
        )

        return await self._emit(event)

    # =========================================================================
    # Notifications
    # =========================================================================

    async def show_notification(
        self,
        message: str,
        title: str | None = None,
        level: NotificationLevel | str = NotificationLevel.INFO,
        *,
        auto_dismiss_ms: int = 5000,
        target_clients: list[str] | None = None,
        announce: bool = False,
        announce_rooms: list[str] | None = None,
    ) -> str:
        """Show a notification to all connected clients.

        Args:
            message: Notification message
            title: Optional title
            level: info, success, warning, error
            auto_dismiss_ms: Auto-dismiss after N ms
            target_clients: Specific clients to target
            announce: Also announce via audio
            announce_rooms: Rooms for audio announcement

        Returns:
            Event ID

        Example:
            >>> await display.show_notification(
            ...     "Lights set to 50%",
            ...     title="Smart Home",
            ...     level="success"
            ... )
        """
        if isinstance(level, str):
            level = NotificationLevel(level)

        event = DisplayEvent(
            type=DisplayEventType.SHOW_NOTIFICATION,
            data={
                "message": message,
                "title": title,
                "level": level.value,
            },
            auto_dismiss_ms=auto_dismiss_ms,
            target_clients=target_clients,
        )

        event_id = await self._emit(event)

        # Optional audio announcement
        if announce:
            try:
                from kagami_smarthome import get_smart_home

                controller = await get_smart_home()
                await controller.announce(message, rooms=announce_rooms)
            except Exception as e:
                logger.debug(f"Audio announcement failed: {e}")

        return event_id

    async def show_toast(
        self,
        message: str,
        *,
        auto_dismiss_ms: int = 3000,
        target_clients: list[str] | None = None,
    ) -> str:
        """Show a brief toast notification.

        Simpler than show_notification - just a message.

        Example:
            >>> await display.show_toast("Saved!")
        """
        event = DisplayEvent(
            type=DisplayEventType.SHOW_TOAST,
            data={"message": message},
            auto_dismiss_ms=auto_dismiss_ms,
            target_clients=target_clients,
        )
        return await self._emit(event)

    # =========================================================================
    # Modals
    # =========================================================================

    async def show_modal(
        self,
        title: str,
        content: str | dict[str, Any],
        actions: list[dict[str, str]] | None = None,
        *,
        modal_id: str | None = None,
        closable: bool = True,
        target_clients: list[str] | None = None,
        callback: Callable[[str], Any] | None = None,
    ) -> str:
        """Show a modal dialog to all connected clients.

        Args:
            title: Modal title
            content: Modal content (text or structured UI)
            actions: Action buttons, e.g. [{"id": "confirm", "label": "OK"}]
            modal_id: Custom ID (auto-generated if None)
            closable: Whether user can dismiss
            target_clients: Specific clients to target
            callback: Called when user takes action

        Returns:
            Modal ID

        Example:
            >>> await display.show_modal(
            ...     "Confirm Action",
            ...     "Are you sure you want to continue?",
            ...     actions=[
            ...         {"id": "yes", "label": "Yes", "variant": "primary"},
            ...         {"id": "no", "label": "No", "variant": "secondary"},
            ...     ]
            ... )
        """
        event = DisplayEvent(
            id=modal_id or str(uuid.uuid4()),
            type=DisplayEventType.SHOW_MODAL,
            data={
                "title": title,
                "content": content,
                "actions": actions or [{"id": "close", "label": "Close"}],
                "closable": closable,
            },
            target_clients=target_clients,
        )

        self._active_modals[event.id] = event
        if callback:
            self._modal_callbacks[event.id] = callback

        return await self._emit(event)

    async def close_modal(self, modal_id: str) -> None:
        """Close a modal by ID."""
        if modal_id in self._active_modals:
            del self._active_modals[modal_id]
        if modal_id in self._modal_callbacks:
            del self._modal_callbacks[modal_id]

        event = DisplayEvent(
            type=DisplayEventType.CLOSE_MODAL,
            data={"modal_id": modal_id},
        )
        await self._emit(event)

    async def handle_modal_action(self, modal_id: str, action_id: str) -> None:
        """Handle a modal action (called by AGUI when user clicks)."""
        callback = self._modal_callbacks.get(modal_id)
        if callback:
            try:
                result = callback(action_id)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Modal callback error: {e}")

        # Auto-close modal after action
        await self.close_modal(modal_id)

    # =========================================================================
    # Progress
    # =========================================================================

    async def show_progress(
        self,
        title: str,
        message: str | None = None,
        *,
        progress_id: str | None = None,
        value: float = 0.0,
        indeterminate: bool = False,
        target_clients: list[str] | None = None,
    ) -> str:
        """Show a progress indicator.

        Args:
            title: Progress title
            message: Status message
            progress_id: Custom ID (for updates)
            value: Progress value 0.0-1.0
            indeterminate: Show indeterminate spinner
            target_clients: Specific clients to target

        Returns:
            Progress ID

        Example:
            >>> progress_id = await display.show_progress(
            ...     "Rendering Symphony",
            ...     "Synthesizing instruments..."
            ... )
            >>> await display.update_progress(progress_id, 0.5, "Mixing channels...")
            >>> await display.hide_progress(progress_id)
        """
        event = DisplayEvent(
            id=progress_id or str(uuid.uuid4()),
            type=DisplayEventType.SHOW_PROGRESS,
            data={
                "title": title,
                "message": message,
                "value": value,
                "indeterminate": indeterminate,
            },
            target_clients=target_clients,
        )

        self._active_progress[event.id] = event
        return await self._emit(event)

    async def update_progress(
        self,
        progress_id: str,
        value: float,
        message: str | None = None,
    ) -> None:
        """Update an existing progress indicator."""
        event = DisplayEvent(
            type=DisplayEventType.UPDATE_PROGRESS,
            data={
                "progress_id": progress_id,
                "value": value,
                "message": message,
            },
        )
        await self._emit(event)

    async def hide_progress(self, progress_id: str) -> None:
        """Hide a progress indicator."""
        if progress_id in self._active_progress:
            del self._active_progress[progress_id]

        event = DisplayEvent(
            type=DisplayEventType.HIDE_PROGRESS,
            data={"progress_id": progress_id},
        )
        await self._emit(event)

    # =========================================================================
    # Rich Content
    # =========================================================================

    async def show_card(
        self,
        title: str,
        content: str | dict[str, Any],
        *,
        image: str | None = None,
        actions: list[dict[str, str]] | None = None,
        auto_dismiss_ms: int | None = None,
        target_clients: list[str] | None = None,
    ) -> str:
        """Show a rich card with optional image and actions.

        Example:
            >>> await display.show_card(
            ...     "Now Playing",
            ...     "Bach - Toccata and Fugue",
            ...     image="/path/to/album_art.jpg",
            ...     actions=[{"id": "pause", "label": "⏸ Pause"}]
            ... )
        """
        event = DisplayEvent(
            type=DisplayEventType.SHOW_CARD,
            data={
                "title": title,
                "content": content,
                "image": image,
                "actions": actions,
            },
            auto_dismiss_ms=auto_dismiss_ms,
            target_clients=target_clients,
        )
        return await self._emit(event)


# =============================================================================
# Global Singleton
# =============================================================================

_display_service: DisplayService | None = None


def get_display_service() -> DisplayService:
    """Get the global display service instance."""
    global _display_service
    if _display_service is None:
        _display_service = DisplayService()
    return _display_service


# Convenience alias
display = get_display_service()


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "DisplayEvent",
    "DisplayEventType",
    "DisplayService",
    "NotificationLevel",
    "display",
    "get_display_service",
]
