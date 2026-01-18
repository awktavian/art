"""Redis-backed message bus for networked organism coordination.

UNIFIED E₈ BYTE PROTOCOL (Dec 1, 2025):
======================================
Programs can be transmitted as E₈ byte sequences for efficient
inter-instance communication. Each byte is an E₈ index (0-239).

Message types:
- "e8_program": Transmit program as E₈ bytes [level0, level1, ...]
- "e8_memory": Memory retrieval query as E₈ index
- "e8_sync": Sync E₈ slot values between instances

See: kagami/core/world_model/memory/unified_e8_codebook.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from kagami.core.caching.redis import RedisClientFactory
from kagami.core.resilience.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    get_circuit_breaker,
)
from kagami.utils.retry import retry_async

logger = logging.getLogger(__name__)

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


class MeshMessageBus:
    """Simple pub/sub message bus on top of Redis channels."""

    def __init__(
        self,
        instance_id: str,
        channel_prefix: str = "networked_organism",
        dedup_size: int = 4096,
    ) -> None:
        self.instance_id = instance_id
        self.channel_prefix = channel_prefix
        self._dedup_size = dedup_size
        self._recent: deque[str] = deque(maxlen=dedup_size)
        self._recent_index: set[str] = set()
        self._redis = None
        self._subscriber_task: asyncio.Task | None = None
        self._running = False

        # Circuit breaker for Redis operations
        # Prevents cascading failures when Redis times out or becomes unavailable
        self._breaker = get_circuit_breaker(
            "redis_message_bus",
            CircuitBreakerConfig(
                failure_threshold=3,  # Open after 3 consecutive failures
                success_threshold=2,  # Close after 2 consecutive successes
                timeout_seconds=30.0,  # Try recovery after 30s
                half_open_max_calls=2,  # Limit concurrent recovery attempts
            ),
        )

    async def _get_redis(self) -> Any:
        if self._redis is None:
            self._redis = RedisClientFactory.get_client(
                purpose="default",
                async_mode=True,
                decode_responses=True,
            )
        return self._redis

    def _channel(self, instance: str) -> str:
        return f"{self.channel_prefix}:{instance}"

    def _dedup(self, message_id: str) -> bool:
        if not message_id:
            return False
        if message_id in self._recent_index:
            return True
        self._recent.append(message_id)
        self._recent_index.add(message_id)
        if len(self._recent_index) > self._dedup_size:
            oldest = self._recent.popleft()
            self._recent_index.discard(oldest)
        return False

    async def _publish_internal(
        self,
        target_instance: str,
        message_type: str,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> str:
        """Internal publish implementation (wrapped by circuit breaker + retry)."""
        redis = await self._get_redis()
        message_id = correlation_id or uuid.uuid4().hex
        event = {
            "id": message_id,
            "type": message_type,
            "source": self.instance_id,
            "target": target_instance,
            "payload": payload or {},
            "ts": time.time(),
        }

        channel = self._channel(target_instance)
        data = json.dumps(event, separators=(",", ":"))
        await redis.publish(channel, data)

        try:
            from kagami_observability.metrics import _counter

            published = _counter(
                "kagami_mesh_messages_published_total",
                "Mesh messages published",
                ["from_instance", "to_instance", "message_type"],
            )
            published.labels(
                from_instance=self.instance_id,
                to_instance=target_instance,
                message_type=message_type,
            ).inc()
        except Exception:
            pass

        return message_id

    @retry_async(attempts=3, delay=0.5, backoff=2.0)
    async def publish(
        self,
        target_instance: str,
        message_type: str,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> str:
        """Publish message to a peer instance.

        Protected by circuit breaker and automatic retry (3 attempts with exponential backoff).
        Fails gracefully if Redis is unavailable.

        Args:
            target_instance: Target instance ID
            message_type: Message type identifier
            payload: Optional message payload
            correlation_id: Optional correlation ID for tracking

        Returns:
            Message ID if published successfully

        Raises:
            CircuitBreakerOpen: If Redis circuit breaker is open
            Exception: If publish fails after retries
        """
        try:
            return await self._breaker.call(  # type: ignore[no-any-return]
                self._publish_internal, target_instance, message_type, payload, correlation_id
            )
        except CircuitBreakerOpen:
            logger.warning(
                f"Redis circuit breaker is OPEN - publish to {target_instance} blocked (type={message_type})"
            )
            raise
        except Exception as e:
            logger.error(
                f"Failed to publish message to {target_instance} (type={message_type}): {e}"
            )
            raise

    async def publish_e8_program(
        self,
        target_instance: str,
        e8_bytes: bytes | list[int],
        correlation_id: str | None = None,
    ) -> str:
        """Publish E₈-encoded program to peer instance.

        Uses the unified E₈ byte protocol for efficient program transmission.

        Args:
            target_instance: Target instance ID
            e8_bytes: E₈ indices as bytes [level0, level1, ...]
            correlation_id: Optional correlation ID

        Returns:
            message_id
        """
        if isinstance(e8_bytes, bytes):
            e8_list = list(e8_bytes)
        else:
            e8_list = e8_bytes

        return await self.publish(  # type: ignore[no-any-return]
            target_instance=target_instance,
            message_type="e8_program",
            payload={
                "e8_bytes": e8_list,
                "num_levels": len(e8_list),
            },
            correlation_id=correlation_id,
        )

    async def publish_e8_memory_query(
        self,
        target_instance: str,
        slot_index: int,
        correlation_id: str | None = None,
    ) -> str:
        """Query remote memory by E₈ slot index.

        Args:
            target_instance: Target instance ID
            slot_index: E₈ slot (0-239)
            correlation_id: Optional correlation ID

        Returns:
            message_id
        """
        return await self.publish(  # type: ignore[no-any-return]
            target_instance=target_instance,
            message_type="e8_memory_query",
            payload={"slot_index": slot_index % 240},
            correlation_id=correlation_id,
        )

    @staticmethod
    def decode_e8_payload(payload: dict[str, Any]) -> list[int]:
        """Decode E₈ bytes from message payload.

        Args:
            payload: Message payload dict[str, Any]

        Returns:
            List of E₈ indices
        """
        return payload.get("e8_bytes", [])  # type: ignore[no-any-return]

    async def start(self, handler: MessageHandler) -> None:
        """Start background subscriber loop."""
        if self._running:
            return
        self._running = True
        self._subscriber_task = asyncio.create_task(
            self._subscribe_loop(handler), name="mesh_message_bus"
        )

    async def stop(self) -> None:
        self._running = False
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
            self._subscriber_task = None

    async def _subscribe_loop(self, handler: MessageHandler) -> None:
        redis = await self._get_redis()
        channel = self._channel(self.instance_id)
        pubsub = redis.pubsub(ignore_subscribe_messages=True)
        await pubsub.subscribe(channel)
        logger.info("📨 MeshMessageBus subscribed to %s", channel)

        try:
            async for message in pubsub.listen():
                if not self._running:
                    break
                if message is None or message.get("type") != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                except Exception as exc:
                    logger.debug(f"Invalid mesh message: {exc}")
                    continue

                message_id = data.get("id")
                if self._dedup(message_id):
                    continue
                if data.get("source") == self.instance_id:
                    continue

                try:
                    await handler(data)
                except Exception as exc:
                    logger.error(f"Mesh message handler error: {exc}", exc_info=True)

                try:
                    from kagami_observability.metrics import _counter

                    received = _counter(
                        "kagami_mesh_messages_received_total",
                        "Mesh messages received",
                        ["from_instance", "to_instance", "message_type"],
                    )
                    received.labels(
                        from_instance=data.get("source", "unknown"),
                        to_instance=self.instance_id,
                        message_type=data.get("type", "unknown"),
                    ).inc()
                except Exception:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"MeshMessageBus subscribe loop error: {exc}", exc_info=True)
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            except Exception:
                pass


_bus: MeshMessageBus | None = None


def get_message_bus(instance_id: str | None = None) -> MeshMessageBus:
    global _bus
    if _bus is None:
        instance = instance_id or os.getenv("KAGAMI_INSTANCE_ID") or _generate_instance_id()
        _bus = MeshMessageBus(instance)
    return _bus


def _generate_instance_id() -> str:
    host = os.getenv("HOSTNAME") or socket.gethostname() or "kagami"
    pid = os.getpid()
    return f"{host}-{pid}-{uuid.uuid4().hex[:8]}"
