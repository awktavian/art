"""Callback Registry for K os Kernel.

Manages async callbacks for sensor subscriptions, input events, and notifications.

Created: November 15, 2025
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)


class CallbackRegistry:
    """Global registry for async callbacks.

    Supports:
    - Sensor subscriptions
    - Input event handlers
    - Custom callbacks
    """

    def __init__(self) -> None:
        self._callbacks: dict[str, Callable[[Any], Awaitable[None]]] = {}
        self._subscriptions: dict[str, tuple[str, Any]] = {}  # callback_id -> (type, handle)
        self._lock = asyncio.Lock()

    def register_callback(
        self,
        callback_id: str,
        callback: Callable[[Any], Awaitable[None]],
    ) -> None:
        """Register a callback function.

        Args:
            callback_id: Unique callback ID
            callback: Async callback function
        """
        self._callbacks[callback_id] = callback
        logger.debug(f"Registered callback: {callback_id}")

    def register_subscription(
        self,
        callback_id: str,
        subscription_type: str,
        handle: Any,
    ) -> None:
        """Register subscription metadata.

        Args:
            callback_id: Callback ID
            subscription_type: Type of subscription (sensor, input, etc.)
            handle: Subscription handle for cleanup
        """
        self._subscriptions[callback_id] = (subscription_type, handle)

    async def invoke_callback(self, callback_id: str, data: Any) -> bool:
        """Invoke a registered callback.

        Args:
            callback_id: Callback ID
            data: Data to pass to callback

        Returns:
            True if invoked, False if not found
        """
        callback = self._callbacks.get(callback_id)

        if not callback:
            logger.warning(f"Callback not found: {callback_id}")
            return False

        try:
            await callback(data)
            return True
        except Exception as e:
            logger.error(f"Callback {callback_id} failed: {e}")
            return False

    async def unregister_callback(self, callback_id: str) -> bool:
        """Unregister a callback.

        Args:
            callback_id: Callback ID

        Returns:
            True if unregistered, False if not found
        """
        async with self._lock:
            if callback_id in self._callbacks:
                del self._callbacks[callback_id]

            if callback_id in self._subscriptions:
                del self._subscriptions[callback_id]

            logger.debug(f"Unregistered callback: {callback_id}")
            return True

    def list_callbacks(self) -> list[dict[str, Any]]:
        """List all registered callbacks.

        Returns:
            List of callback info
        """
        callbacks = []

        for callback_id in self._callbacks:
            subscription_info = self._subscriptions.get(callback_id)

            callbacks.append(
                {
                    "callback_id": callback_id,
                    "has_subscription": subscription_info is not None,
                    "subscription_type": subscription_info[0] if subscription_info else None,
                }
            )

        return callbacks

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Stats dict[str, Any]
        """
        return {
            "total_callbacks": len(self._callbacks),
            "total_subscriptions": len(self._subscriptions),
        }


# Global singleton
_callback_registry: CallbackRegistry | None = None


def get_callback_registry() -> CallbackRegistry:
    """Get global callback registry.

    Returns:
        CallbackRegistry singleton
    """
    global _callback_registry

    if _callback_registry is None:
        _callback_registry = CallbackRegistry()

    return _callback_registry


__all__ = [
    "CallbackRegistry",
    "get_callback_registry",
]
