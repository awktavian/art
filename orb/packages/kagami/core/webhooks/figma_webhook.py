"""Figma webhook handler for real-time design events.

Handles incoming webhook events from Figma for:
- FILE_UPDATE: Design file was modified
- FILE_COMMENT: Comment added to file
- FILE_VERSION_UPDATE: New version created

Events are published to the UnifiedE8Bus for colony routing and
processed by auto-triggers for cross-domain actions.

Webhook Registration:
    await client.create_webhook(
        team_id="1526902801777552354",
        event_type="FILE_UPDATE",
        callback_url="https://api.awkronos.com/webhooks/figma"
    )

Created: January 5, 2026
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FigmaWebhookEvent:
    """Parsed Figma webhook event.

    Attributes:
        event_type: Type of event (FILE_UPDATE, FILE_COMMENT, etc.).
        file_key: Figma file key.
        file_name: Figma file name.
        timestamp: Event timestamp.
        triggered_by: User who triggered the event.
        passcode: Webhook passcode for verification.
        payload: Raw event payload.
    """

    event_type: str
    file_key: str
    file_name: str
    timestamp: str
    triggered_by: dict[str, Any]
    passcode: str
    payload: dict[str, Any]

    @classmethod
    def from_webhook(cls, data: dict[str, Any]) -> FigmaWebhookEvent:
        """Parse webhook payload into event object.

        Args:
            data: Raw webhook payload from Figma.

        Returns:
            Parsed FigmaWebhookEvent.
        """
        return cls(
            event_type=data.get("event_type", "UNKNOWN"),
            file_key=data.get("file_key", ""),
            file_name=data.get("file_name", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            triggered_by=data.get("triggered_by", {}),
            passcode=data.get("passcode", ""),
            payload=data,
        )

    def to_bus_event(self) -> dict[str, Any]:
        """Convert to event bus format.

        Returns:
            Event data for UnifiedE8Bus.
        """
        return {
            "source": "figma",
            "event_type": self.event_type,
            "file_key": self.file_key,
            "file_name": self.file_name,
            "timestamp": self.timestamp,
            "user": self.triggered_by.get("handle"),
            "payload": self.payload,
        }


class FigmaWebhookHandler:
    """Handler for Figma webhook events.

    This class processes incoming Figma webhooks, validates them,
    and routes them to appropriate handlers.

    Attributes:
        webhook_secret: Secret for webhook signature verification.
        registered_webhooks: Dict of registered webhook IDs.

    Example:
        handler = FigmaWebhookHandler(webhook_secret="my_secret")
        await handler.process_event(request_body, signature)
    """

    def __init__(
        self,
        webhook_secret: str | None = None,
    ) -> None:
        """Initialize the webhook handler.

        Args:
            webhook_secret: Secret for HMAC signature verification.
                If None, signature verification is skipped.
        """
        self.webhook_secret = webhook_secret
        self.registered_webhooks: dict[str, str] = {}
        self._event_handlers: dict[str, list] = {
            "FILE_UPDATE": [],
            "FILE_COMMENT": [],
            "FILE_VERSION_UPDATE": [],
            "FILE_DELETE": [],
            "LIBRARY_PUBLISH": [],
        }

    def register_handler(
        self,
        event_type: str,
        handler,
    ) -> None:
        """Register a handler for an event type.

        Args:
            event_type: Figma event type (FILE_UPDATE, etc.).
            handler: Async function to handle the event.
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def verify_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Verify webhook signature using HMAC-SHA256.

        Args:
            payload: Raw request body.
            signature: Signature from X-Figma-Signature header.

        Returns:
            True if signature is valid, False otherwise.
        """
        if not self.webhook_secret:
            # Skip verification if no secret configured
            logger.warning("Webhook signature verification skipped (no secret)")
            return True

        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def process_event(
        self,
        payload: dict[str, Any],
        signature: str | None = None,
        raw_body: bytes | None = None,
    ) -> dict[str, Any]:
        """Process incoming webhook event.

        Args:
            payload: Parsed JSON payload.
            signature: X-Figma-Signature header value.
            raw_body: Raw request body for signature verification.

        Returns:
            Processing result with status and any errors.
        """
        # Verify signature if provided
        if signature and raw_body:
            if not self.verify_signature(raw_body, signature):
                logger.warning("Invalid webhook signature")
                return {"status": "error", "message": "Invalid signature"}

        try:
            # Parse event
            event = FigmaWebhookEvent.from_webhook(payload)

            logger.info(f"Processing Figma webhook: {event.event_type} for file {event.file_name}")

            # Publish to event bus
            await self._publish_to_bus(event)

            # Run registered handlers
            await self._run_handlers(event)

            return {
                "status": "ok",
                "event_type": event.event_type,
                "file_key": event.file_key,
            }

        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _publish_to_bus(self, event: FigmaWebhookEvent) -> None:
        """Publish event to UnifiedE8Bus.

        Args:
            event: Parsed webhook event.
        """
        try:
            from kagami.core.events import get_unified_bus

            bus = get_unified_bus()
            await bus.publish(
                f"figma.{event.event_type.lower()}",
                event.to_bus_event(),
            )
        except Exception as e:
            logger.debug(f"Failed to publish to event bus: {e}")

    async def _run_handlers(self, event: FigmaWebhookEvent) -> None:
        """Run registered handlers for event type.

        Args:
            event: Parsed webhook event.
        """
        handlers = self._event_handlers.get(event.event_type, [])

        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Handler error for {event.event_type}: {e}")


# Global webhook handler instance
_handler: FigmaWebhookHandler | None = None


def get_figma_webhook_handler() -> FigmaWebhookHandler:
    """Get or create the global Figma webhook handler."""
    global _handler
    if _handler is None:
        _handler = FigmaWebhookHandler()
    return _handler


async def handle_figma_webhook(
    payload: dict[str, Any],
    signature: str | None = None,
    raw_body: bytes | None = None,
) -> dict[str, Any]:
    """Handle incoming Figma webhook (convenience function).

    This is the main entry point for the FastAPI webhook route.

    Args:
        payload: Parsed JSON payload from request.
        signature: X-Figma-Signature header.
        raw_body: Raw request body for signature verification.

    Returns:
        Processing result.
    """
    handler = get_figma_webhook_handler()
    return await handler.process_event(payload, signature, raw_body)


async def register_figma_webhook(
    team_id: str,
    event_type: str,
    callback_url: str,
    passcode: str = "",
) -> dict[str, Any]:
    """Register a webhook with Figma.

    Args:
        team_id: Figma team ID.
        event_type: Event type to subscribe to.
        callback_url: URL to receive webhook events.
        passcode: Optional passcode for verification.

    Returns:
        Webhook registration response from Figma.
    """
    try:
        from kagami.core.integrations.figma_direct import get_figma_client

        client = await get_figma_client()
        result = await client.create_webhook(
            team_id=team_id,
            event_type=event_type,
            callback_url=callback_url,
            passcode=passcode,
        )

        if result.get("id"):
            handler = get_figma_webhook_handler()
            handler.registered_webhooks[event_type] = result["id"]
            logger.info(f"Registered Figma webhook: {event_type} → {callback_url}")

        return result

    except Exception as e:
        logger.error(f"Failed to register webhook: {e}")
        return {"error": str(e)}
