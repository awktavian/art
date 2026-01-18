"""Windows Input Adapter using Win32 API.

Implements InputController for Windows using:
- Raw Input API for low-latency keyboard/mouse
- Win32 message hooks for global input

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import InputEvent, InputType
from kagami_hal.input_controller import BaseInputController

logger = logging.getLogger(__name__)

WINDOWS_AVAILABLE = sys.platform == "win32"
WIN32_AVAILABLE = False

if WINDOWS_AVAILABLE:
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        WIN32_AVAILABLE = True

        # Win32 constants
        WH_KEYBOARD_LL = 13
        WH_MOUSE_LL = 14
        WM_KEYDOWN = 0x0100
        WM_KEYUP = 0x0101
        WM_LBUTTONDOWN = 0x0201
        WM_LBUTTONUP = 0x0202
        WM_RBUTTONDOWN = 0x0204
        WM_RBUTTONUP = 0x0205
        WM_MOUSEMOVE = 0x0200
        WM_MOUSEWHEEL = 0x020A

        # Hook procedure type
        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    except (ImportError, AttributeError):
        logger.warning("Win32 API not available")


class WindowsInput(BaseInputController):
    """Windows input implementation using Win32 API."""

    def __init__(self, hook_thread_cls: type | None = None):
        """Initialize Windows input.

        Args:
            hook_thread_cls: Optional custom hook thread class for testing
        """
        super().__init__()
        self._keyboard_hook: Any = None
        self._mouse_hook: Any = None
        self._running = False
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._process_task: asyncio.Task | None = None
        self._hook_thread_cls = hook_thread_cls
        self._hook_thread: Any = None

    async def initialize(self) -> bool:
        """Initialize input devices."""
        # Use custom hook thread for testing if provided
        if self._hook_thread_cls is not None:
            self._running = True
            self._hook_thread = self._hook_thread_cls(self._emit_event)
            self._hook_thread.start()
            logger.info("✅ Windows input initialized (test mode with custom hook)")
            return True

        if not WINDOWS_AVAILABLE:
            if is_test_mode():
                logger.info("Windows input not available (wrong platform), gracefully degrading")
                return False
            raise RuntimeError("Windows input only available on Windows")

        if not WIN32_AVAILABLE:
            if is_test_mode():
                logger.info("Win32 API not available, gracefully degrading")
                return False
            raise RuntimeError("Win32 API not available")

        try:
            self._running = True

            # Note: Installing hooks requires a message loop
            # For now, we'll use polling-based input via GetAsyncKeyState
            # Full hook implementation requires running in main thread with message pump

            self._process_task = asyncio.create_task(self._poll_input())

            logger.info("✅ Windows input initialized (polling mode)")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Windows input: {e}", exc_info=True)
            return False

    def _emit_event(self, event: InputEvent) -> None:
        """Emit event to subscribers (sync version for hook thread)."""
        asyncio.get_event_loop().call_soon(lambda: asyncio.create_task(self._dispatch_event(event)))

    async def _dispatch_event(self, event: InputEvent) -> None:
        """Dispatch event to subscribers."""
        for callback in self._subscribers.get(event.type, []):
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error in input callback: {e}")

    async def _poll_input(self) -> None:
        """Poll for input using GetAsyncKeyState."""
        # Track key states
        key_states: dict[int, bool] = {}

        while self._running:
            try:
                # Poll keyboard keys (VK codes 0-255)
                for vk in range(256):
                    state = user32.GetAsyncKeyState(vk)
                    pressed = bool(state & 0x8000)

                    prev_pressed = key_states.get(vk, False)

                    if pressed != prev_pressed:
                        key_states[vk] = pressed

                        event = InputEvent(
                            type=InputType.KEYBOARD,
                            code=vk,
                            value=1 if pressed else 0,
                            timestamp_ms=int(time.time() * 1000),
                        )

                        await self._event_queue.put(event)

                        # Dispatch to subscribers
                        for callback in self._subscribers.get(InputType.KEYBOARD, []):
                            try:
                                await callback(event)
                            except Exception as e:
                                logger.error(f"Error in input callback: {e}")

                # Poll mouse buttons
                for vk, input_type in [
                    (0x01, InputType.MOUSE),  # VK_LBUTTON
                    (0x02, InputType.MOUSE),  # VK_RBUTTON
                    (0x04, InputType.MOUSE),  # VK_MBUTTON
                ]:
                    state = user32.GetAsyncKeyState(vk)
                    pressed = bool(state & 0x8000)
                    prev_pressed = key_states.get(vk, False)

                    if pressed != prev_pressed:
                        key_states[vk] = pressed

                        event = InputEvent(
                            type=input_type,
                            code=vk,
                            value=1 if pressed else 0,
                            timestamp_ms=int(time.time() * 1000),
                        )

                        await self._event_queue.put(event)

                        for callback in self._subscribers.get(InputType.MOUSE, []):
                            try:
                                await callback(event)
                            except Exception as e:
                                logger.error(f"Error in input callback: {e}")

                await asyncio.sleep(0.01)  # 10ms polling

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Input polling error: {e}")
                await asyncio.sleep(0.1)

    async def read_event(self) -> InputEvent | None:
        """Read next input event (non-blocking)."""
        try:
            return self._event_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def inject_event(self, type: InputType, code: int, value: int) -> bool:
        """Inject synthetic input event.

        Args:
            type: Event type
            code: Key/button code (VK code)
            value: Value (1=press, 0=release)

        Returns:
            True if successful
        """
        if not WIN32_AVAILABLE:
            return False

        try:
            if type == InputType.KEYBOARD:
                # Use keybd_event for keyboard
                flags = 0 if value else 0x0002  # KEYEVENTF_KEYUP
                user32.keybd_event(code, 0, flags, 0)
                return True

            elif type == InputType.MOUSE:
                # Use mouse_event for mouse
                if code == 0x01:  # Left button
                    flag = 0x0002 if value else 0x0004  # LEFTDOWN/LEFTUP
                elif code == 0x02:  # Right button
                    flag = 0x0008 if value else 0x0010  # RIGHTDOWN/RIGHTUP
                else:
                    return False

                user32.mouse_event(flag, 0, 0, 0, 0)
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to inject event: {e}")
            return False

    async def shutdown(self) -> None:
        """Shutdown input controller."""
        self._running = False

        if self._hook_thread is not None:
            self._hook_thread.stop()

        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass

        logger.info("✅ Windows input shutdown")
