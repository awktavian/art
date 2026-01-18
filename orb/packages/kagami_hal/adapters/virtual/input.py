"""Virtual Input Adapter for testing/headless environments.

Implements InputController with event queue.

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
"""

from __future__ import annotations

import asyncio
import logging

from kagami_hal.data_types import InputEvent, InputType
from kagami_hal.input_controller import BaseInputController

from .config import get_virtual_config

logger = logging.getLogger(__name__)


class VirtualInput(BaseInputController):
    """Virtual input implementation for testing."""

    def __init__(self) -> None:
        """Initialize virtual input."""
        super().__init__()
        self._config = get_virtual_config()
        self._platform_name = "Virtual"
        self._event_queue: asyncio.Queue = asyncio.Queue()

    async def initialize(self) -> bool:
        """Initialize input."""
        logger.info("✅ Virtual input initialized")
        return True

    async def read_event(self) -> InputEvent | None:
        """Read next input event (non-blocking)."""
        try:
            return self._event_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def read_events(self) -> list[InputEvent]:
        """Read all available input events."""
        events = []
        while True:
            event = await self.read_event()
            if event is None:
                break
            events.append(event)
        return events

    async def inject_event(self, type: InputType, code: int, value: int) -> bool:
        """Inject synthetic input event."""
        try:
            event = InputEvent(
                type=type,
                code=code,
                value=value,
                timestamp_ms=int(self._config.get_time() * 1000),
            )
            await self._event_queue.put(event)

            # Dispatch to subscribers
            for callback in self._subscribers.get(type, []):
                try:
                    await callback(event)
                except Exception as e:
                    logger.error(f"Error in input callback: {e}")

            return True
        except Exception as e:
            logger.error(f"Failed to inject event: {e}")
            return False

    def queue_event(self, event: InputEvent) -> None:
        """Queue an event for testing (sync version)."""
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            pass
