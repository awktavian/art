"""Slack Rate Limiter — Prevent channel saturation.

Implements token bucket algorithm with per-channel limits to prevent
the organism from over-posting and saturating Slack channels.

Architecture:
    - 10 messages per hour per channel (default)
    - 1 message per 6 minutes minimum spacing
    - Message priority queue (critical > high > normal > low)
    - Automatic batching of low-priority messages

Usage:
    >>> limiter = SlackRateLimiter()
    >>> if await limiter.can_send("#all-awkronos", priority="high"):
    ...     await send_message(...)
    ...     await limiter.record_send("#all-awkronos")

Created: 2026-01-05 (in response to 100% channel saturation audit finding)
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """Message priority levels."""

    CRITICAL = 4  # h(x) < 0, emergencies
    HIGH = 3  # Important updates, alerts
    NORMAL = 2  # Regular notifications
    LOW = 1  # Batch-able, informational


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a channel."""

    messages_per_hour: int = 10  # Default: 10 msg/hour
    burst_size: int = 3  # Allow 3 messages in quick succession
    min_spacing_seconds: float = 360.0  # 6 minutes between messages


class SlackRateLimiter:
    """Token bucket rate limiter with per-channel tracking.

    Prevents channel saturation by enforcing:
    - Maximum messages per hour (default: 10)
    - Minimum spacing between messages (default: 6 minutes)
    - Priority-based queuing (critical messages bypass limits)

    Thread-safe for async use.
    """

    def __init__(self, default_config: RateLimitConfig | None = None):
        """Initialize rate limiter.

        Args:
            default_config: Default configuration for all channels
        """
        self._default_config = default_config or RateLimitConfig()

        # Per-channel state
        self._tokens: dict[str, float] = defaultdict(lambda: self._default_config.burst_size)
        self._last_send: dict[str, float] = {}
        self._send_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Priority queue for pending messages
        self._pending: dict[str, list[tuple[MessagePriority, dict]]] = defaultdict(list)

        # Statistics
        self._allowed_count = 0
        self._denied_count = 0
        self._batched_count = 0

        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def can_send(
        self, channel: str, priority: MessagePriority | str = MessagePriority.NORMAL
    ) -> bool:
        """Check if message can be sent to channel.

        Args:
            channel: Channel name or ID
            priority: Message priority (CRITICAL bypasses limits)

        Returns:
            True if message can be sent now
        """
        if isinstance(priority, str):
            priority = MessagePriority[priority.upper()]

        # CRITICAL messages always allowed (h(x) < 0 emergencies)
        if priority == MessagePriority.CRITICAL:
            return True

        async with self._lock:
            now = time.time()

            # Check minimum spacing
            last_send = self._last_send.get(channel, 0)
            time_since_last = now - last_send
            if time_since_last < self._default_config.min_spacing_seconds:
                # HIGH priority can override spacing if urgent
                if priority == MessagePriority.HIGH and time_since_last > 60.0:
                    return True
                self._denied_count += 1
                logger.debug(
                    f"Rate limit: {channel} denied (last send {time_since_last:.1f}s ago, "
                    f"min spacing {self._default_config.min_spacing_seconds}s)"
                )
                return False

            # Refill tokens based on time elapsed
            tokens = self._tokens[channel]
            refill_rate = self._default_config.messages_per_hour / 3600.0  # tokens per second
            tokens_to_add = time_since_last * refill_rate
            self._tokens[channel] = min(tokens + tokens_to_add, self._default_config.burst_size)

            # Check if we have tokens
            if self._tokens[channel] >= 1.0:
                return True

            self._denied_count += 1
            logger.debug(
                f"Rate limit: {channel} denied (tokens: {self._tokens[channel]:.2f}, need 1.0)"
            )
            return False

    async def record_send(
        self, channel: str, priority: MessagePriority | str = MessagePriority.NORMAL
    ) -> None:
        """Record that a message was sent.

        Args:
            channel: Channel name or ID
            priority: Message priority
        """
        if isinstance(priority, str):
            priority = MessagePriority[priority.upper()]

        async with self._lock:
            now = time.time()

            # Update state
            self._last_send[channel] = now
            self._send_history[channel].append((now, priority.value))

            # Consume token (CRITICAL doesn't consume tokens)
            if priority != MessagePriority.CRITICAL:
                self._tokens[channel] = max(0, self._tokens[channel] - 1.0)

            self._allowed_count += 1
            logger.debug(
                f"Rate limit: {channel} sent (tokens remaining: {self._tokens[channel]:.2f})"
            )

    async def queue_message(
        self,
        channel: str,
        message_data: dict[str, Any],
        priority: MessagePriority | str = MessagePriority.NORMAL,
    ) -> None:
        """Queue message for later sending (if rate limited).

        Args:
            channel: Channel name or ID
            message_data: Message payload
            priority: Message priority
        """
        if isinstance(priority, str):
            priority = MessagePriority[priority.upper()]

        async with self._lock:
            self._pending[channel].append((priority, message_data))
            self._batched_count += 1
            logger.info(
                f"Rate limit: {channel} queued (priority={priority.name}, "
                f"queue size={len(self._pending[channel])})"
            )

    async def get_pending_messages(
        self, channel: str, max_count: int = 10
    ) -> list[tuple[MessagePriority, dict]]:
        """Get pending messages for a channel, sorted by priority.

        Args:
            channel: Channel name or ID
            max_count: Maximum messages to return

        Returns:
            List of (priority, message_data) tuples
        """
        async with self._lock:
            pending = self._pending.get(channel, [])
            # Sort by priority (high to low)
            pending.sort(key=lambda x: x[0].value, reverse=True)
            result = pending[:max_count]
            # Remove returned messages from queue
            self._pending[channel] = pending[max_count:]
            return result

    async def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics.

        Returns:
            Statistics dictionary with counts and state
        """
        async with self._lock:
            total_pending = sum(len(q) for q in self._pending.values())
            return {
                "allowed_count": self._allowed_count,
                "denied_count": self._denied_count,
                "batched_count": self._batched_count,
                "total_pending": total_pending,
                "channels_tracked": len(self._last_send),
                "tokens_by_channel": dict(self._tokens),
                "pending_by_channel": {k: len(v) for k, v in self._pending.items()},
            }

    async def reset_channel(self, channel: str) -> None:
        """Reset rate limit state for a channel.

        Args:
            channel: Channel name or ID
        """
        async with self._lock:
            self._tokens[channel] = self._default_config.burst_size
            self._last_send.pop(channel, None)
            self._send_history[channel].clear()
            self._pending.pop(channel, None)
            logger.info(f"Rate limit: {channel} reset")

    def get_next_available_time(self, channel: str) -> float:
        """Get timestamp when next message can be sent.

        Args:
            channel: Channel name or ID

        Returns:
            Unix timestamp when channel will be available
        """
        last_send = self._last_send.get(channel, 0)
        min_spacing = self._default_config.min_spacing_seconds
        return last_send + min_spacing


# Singleton instance
_rate_limiter: SlackRateLimiter | None = None


def get_slack_rate_limiter() -> SlackRateLimiter:
    """Get the global Slack rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = SlackRateLimiter()
    return _rate_limiter
