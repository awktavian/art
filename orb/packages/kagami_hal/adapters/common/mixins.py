"""Common HAL adapter utilities and mixins."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)


def get_timestamp_ms() -> int:
    """Get current timestamp in milliseconds."""
    return int(time.time() * 1000)


class SubscriptionMixin:
    """Mixin for handling subscriptions."""

    def __init__(self) -> None:
        self._callbacks: dict[Any, list[Callable[[Any], Awaitable[None]]]] = {}

    async def subscribe(
        self, key: Any, callback: Callable[[Any], Awaitable[None]], **kwargs: Any
    ) -> None:
        if key not in self._callbacks:
            self._callbacks[key] = []
        self._callbacks[key].append(callback)

    async def unsubscribe(self, key: Any) -> None:
        if key in self._callbacks:
            del self._callbacks[key]

    async def _notify_subscribers(self, key: Any, data: Any) -> None:
        if key in self._callbacks:
            for callback in self._callbacks[key]:
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"Subscriber callback failed: {e}")


class VolumeMixin:
    """Mixin for volume control."""

    def __init__(self) -> None:
        self._volume: float = 1.0

    async def set_volume(self, level: float) -> None:
        self._volume = max(0.0, min(1.0, level))

    async def get_volume(self) -> float:
        return self._volume


class PowerModeMixin:
    """Mixin for power mode control."""

    def __init__(self, default_mode: Any):
        self._power_mode = default_mode

    async def set_power_mode(self, mode: Any) -> None:
        self._power_mode = mode

    async def get_power_mode(self) -> Any:
        return self._power_mode
