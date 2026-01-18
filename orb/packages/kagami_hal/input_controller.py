"""Input Controller HAL for K os.

Unified interface for input devices across platforms.

Supported:
- Linux: evdev (keyboard, mouse, touchscreen)
- macOS: IOKit
- Embedded: GPIO buttons, capacitive touch

Created: November 10, 2025
Updated: November 30, 2025 - Added BaseInputController to reduce duplication
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

# Import types from centralized data_types to avoid duplication
from kagami_hal.data_types import InputEvent, InputType, KeyCode

# Re-export for backwards compatibility
__all__ = ["BaseInputController", "InputController", "InputEvent", "InputType", "KeyCode"]

logger = logging.getLogger(__name__)


class InputController(ABC):
    """Abstract input controller interface."""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize input devices.

        Returns:
            True if successful
        """

    @abstractmethod
    async def subscribe(
        self, input_type: InputType, callback: Callable[[InputEvent], Awaitable[None]]
    ) -> None:
        """Subscribe to input events.

        Args:
            input_type: Type of input to subscribe to
            callback: Async callback for events
        """

    @abstractmethod
    async def unsubscribe(self, input_type: InputType) -> None:
        """Unsubscribe from input events.

        Args:
            input_type: Type of input to unsubscribe from
        """

    @abstractmethod
    async def read_event(self) -> InputEvent | None:
        """Read next input event (non-blocking).

        Returns:
            InputEvent or None if no events
        """

    async def inject_event(self, type: InputType, code: int, value: int) -> bool:
        """Inject synthetic input event (optional).

        Args:
            type: Event type
            code: Key/button code
            value: Value (0/1)

        Returns:
            True if supported and successful
        """
        return False

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown input controller."""


class BaseInputController(InputController):
    """Base input controller with common subscriber management.

    Provides default implementations for common operations that are
    duplicated across platform-specific adapters (WASM, Android, Embedded, etc.).

    Subclasses only need to implement:
    - initialize() - platform-specific initialization
    - shutdown() - platform-specific cleanup (can call super().shutdown())

    Consolidation: November 30, 2025
    Previously, subscribe/unsubscribe/read_event were duplicated across:
    - WASMInput, AndroidInput, EmbeddedInput, etc.
    """

    def __init__(self) -> None:
        """Initialize subscriber dictionary for all input types."""
        self._subscribers: dict[InputType, list[Callable]] = {t: [] for t in InputType}
        self._platform_name: str = self.__class__.__name__

    async def subscribe(
        self, input_type: InputType, callback: Callable[[InputEvent], Awaitable[None]]
    ) -> None:
        """Subscribe to input events."""
        self._subscribers[input_type].append(callback)

    async def unsubscribe(self, input_type: InputType) -> None:
        """Unsubscribe from input events."""
        callbacks = self._subscribers.get(input_type)
        if callbacks is not None:
            callbacks.clear()

    async def read_event(self) -> InputEvent | None:
        """Read next input event (default: no events)."""
        return None

    async def shutdown(self) -> None:
        """Shutdown input controller."""
        logger.info(f"{self._platform_name} input shut down")

    async def _dispatch_event(self, event: InputEvent) -> None:
        """Dispatch event to all subscribers (helper for subclasses)."""
        for callback in self._subscribers.get(event.type, []):
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error in input callback: {e}")
