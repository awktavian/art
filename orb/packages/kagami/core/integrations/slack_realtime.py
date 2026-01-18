"""🔌 Kagami Slack Real-time — Full Markov Blanket Handler.

    ╭─ ARCHITECTURE ────────────────────────────────────────────╮
    │ Slack WebSocket → Markov Handler → Organism              │
    │                         ↓                                 │
    │              Plan → Execute → Verify                      │
    │                         ↓                                 │
    │                     Respond                               │
    ╰───────────────────────────────────────────────────────────╯

Single integration point with full preamble + tools.

RATE LIMITING (Jan 5, 2026):
============================
After audit discovered 100% saturation in 3 channels (100/100 messages),
implemented rate limiting: 10 messages per hour per channel (1 per 6 min).

Created: January 4, 2026
Updated: January 5, 2026 — Added rate limiting
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import TYPE_CHECKING, Any

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from kagami.core.integrations.slack_rate_limiter import (
    MessagePriority,
    get_slack_rate_limiter,
)

if TYPE_CHECKING:
    from kagami.core.unified_agents.unified_organism import UnifiedOrganism

logger = logging.getLogger(__name__)

KAGAMI_CHANNEL = "#all-awkronos"
KAGAMI_CHANNEL_ID = "C099P6LUL14"


def _get_bot_token() -> str:
    """Get bot token from env or keychain."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    if token:
        return token

    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", "kagami", "-s", "slack_bot_token", "-w"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    raise ValueError("SLACK_BOT_TOKEN not found")


def _get_app_token() -> str:
    """Get app-level token for Socket Mode."""
    token = os.environ.get("SLACK_APP_TOKEN")
    if token:
        return token

    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", "kagami", "-s", "slack_app_token", "-w"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    raise ValueError("SLACK_APP_TOKEN not found")


class SlackRealtime:
    """Event-driven Slack with full Markov blanket handler.

    Architecture:
    ```
    Slack → Sense → Plan → Execute → Verify → Respond
                         (full preamble + tools)
    ```
    """

    def __init__(self, organism: UnifiedOrganism | None = None):
        """Initialize Slack with Markov blanket handler.

        Args:
            organism: UnifiedOrganism to wire events to.
        """
        self._bot_token = _get_bot_token()
        self._app_token = _get_app_token()
        self._app = AsyncApp(token=self._bot_token)
        self._handler: AsyncSocketModeHandler | None = None
        self._organism = organism
        self._bot_id: str | None = None
        self._e8_bus: Any | None = None
        self._running = False

        # Register event handlers
        self._setup_handlers()

    def wire_organism(self, organism: UnifiedOrganism) -> None:
        """Wire to unified organism for intent execution."""
        self._organism = organism
        logger.info("🔗 Slack wired to UnifiedOrganism")

    def wire_e8_bus(self, bus: Any) -> None:
        """Wire to E8 bus for event distribution."""
        self._e8_bus = bus
        logger.info("🔗 Slack wired to E8 Bus")

    def _setup_handlers(self) -> None:
        """Set up Slack event handlers — routes to organism."""

        @self._app.event("message")
        async def handle_message(event: dict, say, client) -> None:
            """Handle incoming messages — route to organism."""
            # Skip bot messages and subtypes (joins, leaves, etc.)
            if event.get("bot_id") or event.get("subtype"):
                return

            user = event.get("user", "unknown")
            text = event.get("text", "")
            channel = event.get("channel", "")
            ts = event.get("ts", "")
            thread_ts = event.get("thread_ts")

            logger.info(f"⚡ {user}: {text[:50]}")

            # Publish to E8 bus
            if self._e8_bus:
                await self._e8_bus.publish(
                    topic="slack.message",
                    data={
                        "user": user,
                        "text": text,
                        "channel": channel,
                        "ts": ts,
                        "thread_ts": thread_ts,
                    },
                )

            # Route to organism intent execution
            if self._organism:
                try:
                    response = await self._process_with_organism(
                        text=text,
                        user=user,
                        channel=channel,
                        say=say,
                        thread_ts=thread_ts or ts,
                    )
                    if response:
                        await say(text=response, thread_ts=thread_ts or ts)
                except Exception as e:
                    logger.error(f"Organism processing error: {e}")
                    await say(text="hmm, something went wrong", thread_ts=thread_ts or ts)

        @self._app.event("app_mention")
        async def handle_mention(event: dict, say) -> None:
            """Handle @kagami mentions — priority routing."""
            text = event.get("text", "")
            user = event.get("user", "unknown")
            channel = event.get("channel", "")
            ts = event.get("ts", "")
            thread_ts = event.get("thread_ts")

            logger.info(f"📢 Mention from {user}: {text[:50]}")

            # Publish to E8 bus
            if self._e8_bus:
                await self._e8_bus.publish(
                    topic="slack.mention",
                    data={"user": user, "text": text, "channel": channel, "ts": ts},
                )

            # Route to organism with priority
            if self._organism:
                try:
                    response = await self._process_with_organism(
                        text=text,
                        user=user,
                        channel=channel,
                        say=say,
                        thread_ts=thread_ts or ts,
                        priority=True,
                    )
                    if response:
                        await say(text=response, thread_ts=thread_ts or ts)
                except Exception as e:
                    logger.error(f"Mention processing error: {e}")
                    await say(text="error processing mention", thread_ts=thread_ts or ts)

    async def _process_with_organism(
        self,
        text: str,
        user: str,
        channel: str,
        say: Any,
        thread_ts: str,
        priority: bool = False,
    ) -> str | None:
        """Process message through FULL Markov blanket cycle.

        Complete cycle: sense → plan → execute → verify → act

        With full Kagami preamble and tool access.

        Returns:
            Response text or None if no response needed.
        """
        if not self._organism:
            return None

        try:
            # Lazy load Markov handler
            if not hasattr(self, "_markov_handler"):
                from kagami.core.integrations.slack_markov_handler import SlackMarkovHandler

                self._markov_handler = SlackMarkovHandler(self._organism)

            # Process through FULL Markov blanket
            event_data = {
                "user": user,
                "channel": channel,
                "text": text,
                "thread_ts": thread_ts,
            }

            # This does: sense → plan → execute tools → verify → respond
            response_text = await self._markov_handler.process_message(
                text=text,
                user=user,
                channel=channel,
                event=event_data,
            )

            return response_text

        except Exception as e:
            logger.error(f"Markov processing error: {e}")
            return f"error: {e}"

    async def start(self) -> None:
        """Start the Socket Mode connection."""
        if self._running:
            return

        logger.info("🔌 Connecting to Slack Socket Mode...")
        self._handler = AsyncSocketModeHandler(self._app, self._app_token)
        self._running = True

        # Start in background (non-blocking) — CRITICAL: start_async() blocks forever
        # We need to run it as a background task
        import asyncio

        asyncio.create_task(self._handler.start_async())

        # Give it a moment to connect
        await asyncio.sleep(0.5)
        logger.info("⚡ Slack real-time active (event-driven, no polling)")

    async def stop(self) -> None:
        """Stop the Socket Mode connection."""
        if not self._running:
            return

        self._running = False
        if self._handler:
            await self._handler.close_async()
            self._handler = None
        logger.info("🔌 Slack disconnected")

    async def send(
        self,
        text: str,
        channel: str | None = None,
        blocks: list | None = None,
        priority: MessagePriority | str = MessagePriority.NORMAL,
    ) -> bool:
        """Send a message to Slack with rate limiting.

        Args:
            text: Message text
            channel: Channel name or ID
            blocks: Optional Block Kit blocks
            priority: Message priority (CRITICAL, HIGH, NORMAL, LOW)

        Returns:
            True if sent, False if rate limited or failed
        """
        target_channel = channel or KAGAMI_CHANNEL_ID

        # Check rate limit
        rate_limiter = get_slack_rate_limiter()
        if not await rate_limiter.can_send(target_channel, priority):
            # Queue for later if priority allows
            if isinstance(priority, str):
                priority = MessagePriority[priority.upper()]

            if priority.value <= MessagePriority.NORMAL.value:
                await rate_limiter.queue_message(
                    target_channel, {"text": text, "blocks": blocks}, priority
                )
                logger.info(f"Rate limited: queued message to {target_channel}")
                return False

        # Send message
        try:
            kwargs: dict[str, Any] = {
                "channel": target_channel,
                "text": text,
            }
            if blocks:
                kwargs["blocks"] = blocks
            await self._app.client.chat_postMessage(**kwargs)

            # Record send for rate limiting
            await rate_limiter.record_send(target_channel, priority)
            return True
        except Exception as e:
            logger.error(f"Send failed: {e}")
            return False

    @property
    def is_running(self) -> bool:
        """Check if Socket Mode is active."""
        return self._running


# Singleton
_realtime_instance: SlackRealtime | None = None


async def get_slack_realtime(organism: UnifiedOrganism | None = None) -> SlackRealtime:
    """Get or create the Slack real-time singleton.

    Args:
        organism: Optional organism to wire on first call.
    """
    global _realtime_instance
    if _realtime_instance is None:
        _realtime_instance = SlackRealtime(organism)
    elif organism and not _realtime_instance._organism:
        _realtime_instance.wire_organism(organism)
    return _realtime_instance


async def start_slack_integration(
    organism: UnifiedOrganism, e8_bus: Any | None = None
) -> SlackRealtime:
    """Start Slack integration wired to organism and E8 bus.

    This is the main entry point for wiring Slack into the organism loop.

    Args:
        organism: UnifiedOrganism instance.
        e8_bus: Optional E8 bus for event distribution.

    Returns:
        Started SlackRealtime instance.
    """
    realtime = await get_slack_realtime(organism)
    if e8_bus:
        realtime.wire_e8_bus(e8_bus)
    await realtime.start()
    return realtime
