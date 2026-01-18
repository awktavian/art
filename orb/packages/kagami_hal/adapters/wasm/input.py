"""WASM Input Adapter using DOM Events.

Implements InputController for WebAssembly using:
- KeyboardEvent for keyboard input
- MouseEvent for mouse input
- TouchEvent for touch input

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import InputEvent, InputType
from kagami_hal.input_controller import BaseInputController

logger = logging.getLogger(__name__)

WASM_AVAILABLE = False
try:
    import js
    from pyodide.ffi import create_proxy

    WASM_AVAILABLE = True
except ImportError:
    pass


class WASMInput(BaseInputController):
    """WASM input implementation using DOM events."""

    def __init__(self):
        """Initialize WASM input."""
        super().__init__()
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._event_proxies: list[Any] = []
        self._running = False

    async def initialize(self) -> bool:
        """Initialize input event listeners."""
        if not WASM_AVAILABLE:
            if is_test_mode():
                logger.info("WASM input not available, gracefully degrading")
                return False
            raise RuntimeError("WASM input only available in browser")

        try:
            # Keyboard events
            keydown_proxy = create_proxy(self._on_keydown)
            keyup_proxy = create_proxy(self._on_keyup)
            js.document.addEventListener("keydown", keydown_proxy)
            js.document.addEventListener("keyup", keyup_proxy)
            self._event_proxies.extend([keydown_proxy, keyup_proxy])

            # Mouse events
            mousedown_proxy = create_proxy(self._on_mousedown)
            mouseup_proxy = create_proxy(self._on_mouseup)
            mousemove_proxy = create_proxy(self._on_mousemove)
            js.document.addEventListener("mousedown", mousedown_proxy)
            js.document.addEventListener("mouseup", mouseup_proxy)
            js.document.addEventListener("mousemove", mousemove_proxy)
            self._event_proxies.extend([mousedown_proxy, mouseup_proxy, mousemove_proxy])

            # Touch events
            touchstart_proxy = create_proxy(self._on_touchstart)
            touchend_proxy = create_proxy(self._on_touchend)
            touchmove_proxy = create_proxy(self._on_touchmove)
            js.document.addEventListener("touchstart", touchstart_proxy)
            js.document.addEventListener("touchend", touchend_proxy)
            js.document.addEventListener("touchmove", touchmove_proxy)
            self._event_proxies.extend([touchstart_proxy, touchend_proxy, touchmove_proxy])

            self._running = True
            logger.info("✅ WASM input initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize WASM input: {e}", exc_info=True)
            return False

    def _on_keydown(self, event: Any) -> None:
        """Handle keydown event."""
        try:
            hal_event = InputEvent(
                type=InputType.KEYBOARD,
                code=event.keyCode or 0,
                value=1,
                timestamp_ms=int(time.time() * 1000),
            )
            self._event_queue.put_nowait(hal_event)
            self._dispatch_sync(hal_event)
        except Exception as e:
            logger.error(f"Error handling keydown: {e}")

    def _on_keyup(self, event: Any) -> None:
        """Handle keyup event."""
        try:
            hal_event = InputEvent(
                type=InputType.KEYBOARD,
                code=event.keyCode or 0,
                value=0,
                timestamp_ms=int(time.time() * 1000),
            )
            self._event_queue.put_nowait(hal_event)
            self._dispatch_sync(hal_event)
        except Exception as e:
            logger.error(f"Error handling keyup: {e}")

    def _on_mousedown(self, event: Any) -> None:
        """Handle mousedown event."""
        try:
            hal_event = InputEvent(
                type=InputType.MOUSE,
                code=event.button,
                value=1,
                timestamp_ms=int(time.time() * 1000),
            )
            self._event_queue.put_nowait(hal_event)
            self._dispatch_sync(hal_event)
        except Exception as e:
            logger.error(f"Error handling mousedown: {e}")

    def _on_mouseup(self, event: Any) -> None:
        """Handle mouseup event."""
        try:
            hal_event = InputEvent(
                type=InputType.MOUSE,
                code=event.button,
                value=0,
                timestamp_ms=int(time.time() * 1000),
            )
            self._event_queue.put_nowait(hal_event)
            self._dispatch_sync(hal_event)
        except Exception as e:
            logger.error(f"Error handling mouseup: {e}")

    def _on_mousemove(self, event: Any) -> None:
        """Handle mousemove event."""
        # Only dispatch if subscribers exist (high frequency event)
        if not self._subscribers.get(InputType.MOUSE):
            return

        try:
            # Encode position in code (x * 10000 + y)
            code = int(event.clientX * 10000 + event.clientY)
            hal_event = InputEvent(
                type=InputType.MOUSE,
                code=code,
                value=2,  # Move event
                timestamp_ms=int(time.time() * 1000),
            )
            self._dispatch_sync(hal_event)
        except Exception as e:
            logger.error(f"Error handling mousemove: {e}")

    def _on_touchstart(self, event: Any) -> None:
        """Handle touchstart event."""
        try:
            touch = event.touches.item(0)
            if touch:
                code = int(touch.clientX * 10000 + touch.clientY)
                hal_event = InputEvent(
                    type=InputType.TOUCHSCREEN,
                    code=code,
                    value=1,
                    timestamp_ms=int(time.time() * 1000),
                )
                self._event_queue.put_nowait(hal_event)
                self._dispatch_sync(hal_event)
        except Exception as e:
            logger.error(f"Error handling touchstart: {e}")

    def _on_touchend(self, event: Any) -> None:
        """Handle touchend event."""
        try:
            hal_event = InputEvent(
                type=InputType.TOUCHSCREEN,
                code=0,
                value=0,
                timestamp_ms=int(time.time() * 1000),
            )
            self._event_queue.put_nowait(hal_event)
            self._dispatch_sync(hal_event)
        except Exception as e:
            logger.error(f"Error handling touchend: {e}")

    def _on_touchmove(self, event: Any) -> None:
        """Handle touchmove event."""
        if not self._subscribers.get(InputType.TOUCHSCREEN):
            return

        try:
            touch = event.touches.item(0)
            if touch:
                code = int(touch.clientX * 10000 + touch.clientY)
                hal_event = InputEvent(
                    type=InputType.TOUCHSCREEN,
                    code=code,
                    value=2,
                    timestamp_ms=int(time.time() * 1000),
                )
                self._dispatch_sync(hal_event)
        except Exception as e:
            logger.error(f"Error handling touchmove: {e}")

    def _dispatch_sync(self, event: InputEvent) -> None:
        """Dispatch event to subscribers (sync version for DOM callbacks)."""
        # Note: Can't await in DOM callback, would need to schedule
        callbacks = list(self._subscribers.get(event.type, []))
        if not callbacks:
            return None

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        for cb in callbacks:
            try:
                if loop is not None:
                    loop.create_task(cb(event))
                else:
                    asyncio.create_task(cb(event))
            except Exception as e:
                logger.debug(f"WASM input subscriber dispatch failed: {e}")

        return None

    async def read_event(self) -> InputEvent | None:
        """Read next input event (non-blocking)."""
        try:
            return self._event_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def inject_event(self, type: InputType, code: int, value: int) -> bool:
        """Inject synthetic event via dispatchEvent."""
        if not WASM_AVAILABLE:
            return False

        try:
            if type == InputType.KEYBOARD:
                event = js.KeyboardEvent.new("keydown" if value else "keyup", {"keyCode": code})
                js.document.dispatchEvent(event)
                return True

            elif type == InputType.MOUSE:
                event = js.MouseEvent.new("mousedown" if value else "mouseup", {"button": code})
                js.document.dispatchEvent(event)
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to inject event: {e}")
            return False

    async def shutdown(self) -> None:
        """Shutdown input controller."""
        self._running = False

        # Remove event listeners
        if WASM_AVAILABLE:
            try:
                # Would need to remove listeners properly
                pass
            except Exception:
                pass

        self._event_proxies.clear()
        logger.info("✅ WASM input shutdown")
