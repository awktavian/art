"""Cloud Pub/Sub Backend for UnifiedE8Bus.

Provides durable, scalable event streaming via Google Cloud Pub/Sub.
Integrates with the existing UnifiedE8Bus architecture for cross-service
and cross-instance messaging.

ARCHITECTURE:
=============
    ┌─────────────────────────────────────────────────────────────────┐
    │                     UnifiedE8Bus                                 │
    │                                                                  │
    │   Local (Redis)        │        Cloud (Pub/Sub)                 │
    │   ─────────────        │        ────────────────                 │
    │   - Low latency        │        - Durable                       │
    │   - Ephemeral          │        - Cross-region                  │
    │   - Same instance      │        - At-least-once                 │
    │                        │        - Dead letter queue             │
    └─────────────────────────────────────────────────────────────────┘

TOPIC NAMING:
=============
Topics follow the pattern: kagami-{environment}-{topic_name}
- kagami-prod-colony-events
- kagami-prod-training-metrics
- kagami-prod-alerts

E8 INTEGRATION:
===============
Messages include E8 routing metadata in attributes:
- e8_index: E8 lattice index (0-239)
- colony: Target colony name
- fano_line: Fano line for routing

USAGE:
======
    from kagami.core.events.pubsub_backend import get_pubsub_backend

    backend = get_pubsub_backend()
    await backend.initialize()

    # Publish
    await backend.publish(
        topic="colony-events",
        message={"type": "state_update", "colony": "forge"},
        attributes={"e8_index": "42", "priority": "high"},
    )

    # Subscribe
    async def handler(message: PubSubMessage):
        print(f"Received: {message.data}")
        await message.ack()

    await backend.subscribe("colony-events", handler)

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# Lazy imports for optional GCP dependencies
_pubsub_available = False
_pubsub_v1 = None


def _lazy_import_pubsub() -> tuple[Any, Any]:
    """Lazy import google.cloud.pubsub_v1."""
    global _pubsub_available, _pubsub_v1
    if _pubsub_v1 is not None:
        return _pubsub_v1
    try:
        from google.cloud import pubsub_v1

        _pubsub_v1 = pubsub_v1
        _pubsub_available = True
        return pubsub_v1
    except ImportError as e:
        _pubsub_available = False
        raise ImportError(
            "google-cloud-pubsub not installed. Install with: pip install google-cloud-pubsub"
        ) from e


@dataclass
class PubSubConfig:
    """Configuration for Cloud Pub/Sub backend.

    Attributes:
        project_id: GCP project ID.
        environment: Environment name (dev/staging/prod).
        topic_prefix: Prefix for all topic names.
        subscription_prefix: Prefix for subscription names.
        default_ack_deadline_seconds: Default ack deadline.
        enable_message_ordering: Enable ordered delivery.
        dead_letter_topic: Topic for failed messages.
        max_delivery_attempts: Max retries before dead letter.
    """

    project_id: str | None = None
    environment: str = "dev"
    topic_prefix: str = "kagami"
    subscription_prefix: str = "kagami-sub"
    default_ack_deadline_seconds: int = 60
    enable_message_ordering: bool = False
    dead_letter_topic: str | None = None
    max_delivery_attempts: int = 5

    @classmethod
    def from_env(cls) -> PubSubConfig:
        """Create config from environment variables."""
        return cls(
            project_id=os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT"),
            environment=os.getenv("KAGAMI_ENVIRONMENT", "dev"),
            topic_prefix=os.getenv("PUBSUB_TOPIC_PREFIX", "kagami"),
            subscription_prefix=os.getenv("PUBSUB_SUBSCRIPTION_PREFIX", "kagami-sub"),
            default_ack_deadline_seconds=int(os.getenv("PUBSUB_ACK_DEADLINE", "60")),
            enable_message_ordering=os.getenv("PUBSUB_ENABLE_ORDERING", "").lower() == "true",
            dead_letter_topic=os.getenv("PUBSUB_DEAD_LETTER_TOPIC"),
            max_delivery_attempts=int(os.getenv("PUBSUB_MAX_DELIVERY_ATTEMPTS", "5")),
        )


@dataclass
class PubSubMessage:
    """Wrapper for a received Pub/Sub message.

    Attributes:
        message_id: Unique message ID.
        data: Deserialized message data (dict).
        raw_data: Raw bytes.
        attributes: Message attributes.
        publish_time: When message was published.
        ordering_key: Ordering key if ordered delivery enabled.
        delivery_attempt: Current delivery attempt number.
    """

    message_id: str
    data: dict[str, Any]
    raw_data: bytes
    attributes: dict[str, str]
    publish_time: datetime
    ordering_key: str | None = None
    delivery_attempt: int = 1
    _ack_callback: Callable[[], None] | None = field(default=None, repr=False)
    _nack_callback: Callable[[], None] | None = field(default=None, repr=False)

    async def ack(self) -> None:
        """Acknowledge message (mark as processed)."""
        if self._ack_callback:
            self._ack_callback()

    async def nack(self) -> None:
        """Negative acknowledge (request redelivery)."""
        if self._nack_callback:
            self._nack_callback()

    @property
    def e8_index(self) -> int | None:
        """Get E8 routing index from attributes."""
        idx = self.attributes.get("e8_index")
        return int(idx) if idx else None

    @property
    def colony(self) -> str | None:
        """Get target colony from attributes."""
        return self.attributes.get("colony")

    @property
    def fano_line(self) -> str | None:
        """Get Fano line from attributes."""
        return self.attributes.get("fano_line")


@dataclass
class PublishResult:
    """Result from publishing a message.

    Attributes:
        message_id: Published message ID.
        topic: Topic published to.
        publish_time: Time of publish.
    """

    message_id: str
    topic: str
    publish_time: datetime = field(default_factory=lambda: datetime.now(UTC))


MessageHandler = Callable[[PubSubMessage], Awaitable[None]]


class CloudPubSubBackend:
    """Cloud Pub/Sub backend for event streaming.

    Provides durable, scalable message delivery with:
    - Automatic topic/subscription creation
    - E8 routing metadata
    - Dead letter queue support
    - Async message handling

    Thread-safe with connection pooling.

    Example:
        backend = CloudPubSubBackend()
        await backend.initialize()

        # Publish event
        result = await backend.publish(
            topic="colony-events",
            message={"colony": "spark", "event": "idea_generated"},
            e8_index=42,
        )

        # Subscribe with handler
        async def handle_event(msg: PubSubMessage):
            print(f"Event from {msg.colony}: {msg.data}")
            await msg.ack()

        await backend.subscribe("colony-events", handle_event)
    """

    def __init__(self, config: PubSubConfig | None = None):
        """Initialize Pub/Sub backend.

        Args:
            config: Backend configuration. If None, loads from environment.
        """
        self.config = config or PubSubConfig.from_env()
        self._initialized = False
        self._publisher = None
        self._subscriber = None
        self._subscriptions: dict[str, Any] = {}
        self._handlers: dict[str, list[MessageHandler]] = {}
        self._created_topics: set[str] = set()
        self._created_subscriptions: set[str] = set()

    def _full_topic_name(self, topic: str) -> str:
        """Get full topic resource name."""
        short_name = f"{self.config.topic_prefix}-{self.config.environment}-{topic}"
        return f"projects/{self.config.project_id}/topics/{short_name}"

    def _full_subscription_name(self, topic: str, suffix: str = "") -> str:
        """Get full subscription resource name."""
        short_name = f"{self.config.subscription_prefix}-{self.config.environment}-{topic}"
        if suffix:
            short_name = f"{short_name}-{suffix}"
        return f"projects/{self.config.project_id}/subscriptions/{short_name}"

    async def initialize(self) -> None:
        """Initialize Pub/Sub clients.

        Creates publisher and subscriber clients with connection pooling.

        Raises:
            ImportError: If google-cloud-pubsub not installed.
            RuntimeError: If project_id not configured.
        """
        if self._initialized:
            return

        pubsub_v1 = _lazy_import_pubsub()

        if not self.config.project_id:
            # Try metadata server
            try:
                import httpx

                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "http://metadata.google.internal/computeMetadata/v1/project/project-id",
                        headers={"Metadata-Flavor": "Google"},
                        timeout=2.0,
                    )
                    self.config.project_id = resp.text
            except Exception as e:
                raise RuntimeError(
                    "GCP project ID not configured. Set GCP_PROJECT_ID environment variable."
                ) from e

        # Create clients
        self._publisher = pubsub_v1.PublisherClient()
        self._subscriber = pubsub_v1.SubscriberClient()

        self._initialized = True
        logger.info(
            f"Cloud Pub/Sub initialized: project={self.config.project_id}, "
            f"env={self.config.environment}"
        )

    def _ensure_initialized(self) -> None:
        """Ensure backend is initialized."""
        if not self._initialized:
            raise RuntimeError("CloudPubSubBackend not initialized. Call initialize() first.")

    async def _ensure_topic_exists(self, topic: str) -> str:
        """Ensure topic exists, create if not.

        Args:
            topic: Short topic name.

        Returns:
            Full topic resource name.
        """
        full_name = self._full_topic_name(topic)

        if full_name in self._created_topics:
            return full_name

        pubsub_v1 = _lazy_import_pubsub()

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self._publisher.get_topic(topic=full_name),
            )
        except Exception:
            # Topic doesn't exist, create it
            try:
                await loop.run_in_executor(
                    None,
                    lambda: self._publisher.create_topic(request=pubsub_v1.Topic(name=full_name)),
                )
                logger.info(f"Created topic: {full_name}")
            except Exception as e:
                if "ALREADY_EXISTS" not in str(e):
                    raise

        self._created_topics.add(full_name)
        return full_name

    async def _ensure_subscription_exists(
        self,
        topic: str,
        subscription_suffix: str = "",
    ) -> str:
        """Ensure subscription exists, create if not.

        Args:
            topic: Short topic name.
            subscription_suffix: Optional suffix for subscription name.

        Returns:
            Full subscription resource name.
        """
        topic_name = self._full_topic_name(topic)
        sub_name = self._full_subscription_name(topic, subscription_suffix)

        if sub_name in self._created_subscriptions:
            return sub_name

        pubsub_v1 = _lazy_import_pubsub()

        # Ensure topic exists first
        await self._ensure_topic_exists(topic)

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self._subscriber.get_subscription(subscription=sub_name),
            )
        except Exception:
            # Subscription doesn't exist, create it
            try:
                request_kwargs: dict[str, Any] = {
                    "name": sub_name,
                    "topic": topic_name,
                    "ack_deadline_seconds": self.config.default_ack_deadline_seconds,
                    "enable_message_ordering": self.config.enable_message_ordering,
                }

                # Add dead letter policy if configured
                if self.config.dead_letter_topic:
                    dead_letter_name = self._full_topic_name(self.config.dead_letter_topic)
                    await self._ensure_topic_exists(self.config.dead_letter_topic)
                    request_kwargs["dead_letter_policy"] = pubsub_v1.DeadLetterPolicy(
                        dead_letter_topic=dead_letter_name,
                        max_delivery_attempts=self.config.max_delivery_attempts,
                    )

                await loop.run_in_executor(
                    None,
                    lambda: self._subscriber.create_subscription(
                        request=pubsub_v1.Subscription(**request_kwargs)
                    ),
                )
                logger.info(f"Created subscription: {sub_name}")
            except Exception as e:
                if "ALREADY_EXISTS" not in str(e):
                    raise

        self._created_subscriptions.add(sub_name)
        return sub_name

    async def publish(
        self,
        topic: str,
        message: dict[str, Any] | bytes,
        attributes: dict[str, str] | None = None,
        e8_index: int | None = None,
        colony: str | None = None,
        fano_line: str | None = None,
        ordering_key: str | None = None,
    ) -> PublishResult:
        """Publish message to topic.

        Args:
            topic: Short topic name (e.g., "colony-events").
            message: Message data (dict will be JSON serialized).
            attributes: Message attributes.
            e8_index: E8 lattice index for routing.
            colony: Target colony name.
            fano_line: Fano line for routing.
            ordering_key: Key for ordered delivery.

        Returns:
            PublishResult with message ID.

        Example:
            result = await backend.publish(
                topic="colony-events",
                message={"event": "state_change", "data": {...}},
                e8_index=42,
                colony="forge",
            )
        """
        self._ensure_initialized()

        # Ensure topic exists
        topic_name = await self._ensure_topic_exists(topic)

        # Serialize message
        if isinstance(message, dict):
            data = json.dumps(message).encode("utf-8")
        else:
            data = message

        # Build attributes
        attrs = attributes or {}
        if e8_index is not None:
            attrs["e8_index"] = str(e8_index)
        if colony:
            attrs["colony"] = colony
        if fano_line:
            attrs["fano_line"] = fano_line

        # Publish
        publish_kwargs: dict[str, Any] = {
            "topic": topic_name,
            "data": data,
        }

        if attrs:
            publish_kwargs["attributes"] = attrs

        if ordering_key and self.config.enable_message_ordering:
            publish_kwargs["ordering_key"] = ordering_key

        loop = asyncio.get_running_loop()
        future = await loop.run_in_executor(
            None,
            lambda: self._publisher.publish(**publish_kwargs),
        )

        # Wait for publish confirmation
        message_id = await loop.run_in_executor(None, future.result)

        logger.debug(f"Published to {topic}: {message_id}")

        return PublishResult(
            message_id=message_id,
            topic=topic,
        )

    async def publish_batch(
        self,
        topic: str,
        messages: list[tuple[dict[str, Any], dict[str, str] | None]],
    ) -> list[PublishResult]:
        """Publish multiple messages efficiently.

        Args:
            topic: Topic name.
            messages: List of (message, attributes) tuples.

        Returns:
            List of PublishResult.
        """
        results = await asyncio.gather(
            *[self.publish(topic, msg, attrs) for msg, attrs in messages],
            return_exceptions=True,
        )

        # Filter out exceptions, log them
        valid_results = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Batch publish error: {r}")
            else:
                valid_results.append(r)

        return valid_results

    async def subscribe(
        self,
        topic: str,
        handler: MessageHandler,
        subscription_suffix: str = "",
        flow_control_max_messages: int = 100,
    ) -> str:
        """Subscribe to topic with async handler.

        Args:
            topic: Topic name to subscribe to.
            handler: Async function to handle messages.
            subscription_suffix: Suffix for subscription name.
            flow_control_max_messages: Max outstanding messages.

        Returns:
            Subscription name.

        Example:
            async def handle(msg: PubSubMessage):
                print(f"Got: {msg.data}")
                await msg.ack()

            sub = await backend.subscribe("colony-events", handle)
        """
        self._ensure_initialized()

        sub_name = await self._ensure_subscription_exists(topic, subscription_suffix)

        # Register handler
        if sub_name not in self._handlers:
            self._handlers[sub_name] = []
        self._handlers[sub_name].append(handler)

        # Start streaming pull if not already running
        if sub_name not in self._subscriptions:
            await self._start_subscription(sub_name, flow_control_max_messages)

        return sub_name

    async def _start_subscription(
        self,
        subscription_name: str,
        max_messages: int,
    ) -> None:
        """Start streaming pull for subscription."""
        pubsub_v1 = _lazy_import_pubsub()

        def callback(message: Any) -> None:
            """Callback for received messages."""
            try:
                # Parse message
                data = message.data.decode("utf-8")
                try:
                    parsed_data = json.loads(data)
                except json.JSONDecodeError:
                    parsed_data = {"raw": data}

                pub_time = (
                    message.publish_time if hasattr(message, "publish_time") else datetime.now(UTC)
                )

                wrapped = PubSubMessage(
                    message_id=message.message_id,
                    data=parsed_data,
                    raw_data=message.data,
                    attributes=dict(message.attributes) if message.attributes else {},
                    publish_time=pub_time,
                    ordering_key=getattr(message, "ordering_key", None),
                    delivery_attempt=getattr(message, "delivery_attempt", 1),
                    _ack_callback=message.ack,
                    _nack_callback=message.nack,
                )

                # Call handlers
                handlers = self._handlers.get(subscription_name, [])
                for handler in handlers:
                    # Schedule async handler
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(handler(wrapped))
                    except RuntimeError:
                        # No running loop, run synchronously
                        asyncio.run(handler(wrapped))

            except Exception as e:
                logger.error(f"Message handling error: {e}")
                message.nack()

        # Configure flow control
        flow_control = pubsub_v1.types.FlowControl(max_messages=max_messages)

        # Start streaming pull
        streaming_pull_future = self._subscriber.subscribe(
            subscription_name,
            callback,
            flow_control=flow_control,
        )

        self._subscriptions[subscription_name] = streaming_pull_future
        logger.info(f"Started subscription: {subscription_name}")

    async def unsubscribe(self, subscription_name: str) -> None:
        """Stop subscription.

        Args:
            subscription_name: Subscription to stop.
        """
        if subscription_name in self._subscriptions:
            future = self._subscriptions[subscription_name]
            future.cancel()
            del self._subscriptions[subscription_name]

        if subscription_name in self._handlers:
            del self._handlers[subscription_name]

        logger.info(f"Unsubscribed: {subscription_name}")

    async def close(self) -> None:
        """Close all subscriptions and clients."""
        # Cancel all subscriptions
        for name, future in list(self._subscriptions.items()):
            try:
                future.cancel()
            except Exception as e:
                logger.warning(f"Error cancelling subscription {name}: {e}")

        self._subscriptions.clear()
        self._handlers.clear()

        # Close clients
        if self._publisher:
            self._publisher.transport.close()
        if self._subscriber:
            self._subscriber.close()

        self._initialized = False
        logger.info("Cloud Pub/Sub backend closed")

    # =========================================================================
    # E8 Bus Integration
    # =========================================================================

    async def publish_e8_event(
        self,
        topic: str,
        event_type: str,
        payload: dict[str, Any],
        e8_index: int,
        colony: str | None = None,
        fano_line: tuple[int, int, int] | None = None,
        control_token: int = 0x02,  # DATA token
    ) -> PublishResult:
        """Publish E8-routed event (integration with UnifiedE8Bus).

        Args:
            topic: Topic name.
            event_type: Event type string.
            payload: Event payload.
            e8_index: E8 lattice index (0-239).
            colony: Target colony.
            fano_line: Fano line tuple (e.g., (1, 2, 3)).
            control_token: E8 protocol control token.

        Returns:
            PublishResult.
        """
        message = {
            "event_type": event_type,
            "payload": payload,
            "e8_index": e8_index,
            "control_token": control_token,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if colony:
            message["colony"] = colony
        if fano_line:
            message["fano_line"] = list(fano_line)

        return await self.publish(
            topic=topic,
            message=message,
            e8_index=e8_index,
            colony=colony,
            fano_line=",".join(map(str, fano_line)) if fano_line else None,
        )


# Singleton instance
_pubsub_backend: CloudPubSubBackend | None = None


def get_pubsub_backend(config: PubSubConfig | None = None) -> CloudPubSubBackend:
    """Get or create singleton Pub/Sub backend.

    Args:
        config: Optional configuration (only used on first call).

    Returns:
        CloudPubSubBackend instance.
    """
    global _pubsub_backend
    if _pubsub_backend is None:
        _pubsub_backend = CloudPubSubBackend(config)
    return _pubsub_backend


async def initialize_pubsub(config: PubSubConfig | None = None) -> CloudPubSubBackend:
    """Initialize and return Pub/Sub backend.

    Args:
        config: Optional configuration.

    Returns:
        Initialized CloudPubSubBackend.
    """
    backend = get_pubsub_backend(config)
    await backend.initialize()
    return backend


__all__ = [
    "CloudPubSubBackend",
    "MessageHandler",
    "PubSubConfig",
    "PubSubMessage",
    "PublishResult",
    "get_pubsub_backend",
    "initialize_pubsub",
]
