"""Android Input Adapter using MotionEvent/KeyEvent via JNI.

Implements InputController for Android using Pyjnius (JNI).

Supports:
- Touch events via View.OnTouchListener
- Key events via View.OnKeyListener

Created: November 10, 2025
Updated: December 7, 2025 - Full JNI implementation (no stubs)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import InputEvent, InputType
from kagami_hal.input_controller import BaseInputController

logger = logging.getLogger(__name__)

ANDROID_AVAILABLE = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ

JNI_AVAILABLE = False
PythonActivity: Any = None
MotionEvent: Any = None
KeyEvent: Any = None
View: Any = None
PythonJavaClass: Any = None
java_method: Any = None

if ANDROID_AVAILABLE:
    try:
        from jnius import (
            PythonJavaClass as _PythonJavaClass,
        )
        from jnius import (
            autoclass,
        )
        from jnius import (
            java_method as _java_method,
        )

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        MotionEvent = autoclass("android.view.MotionEvent")
        KeyEvent = autoclass("android.view.KeyEvent")
        View = autoclass("android.view.View")
        PythonJavaClass = _PythonJavaClass
        java_method = _java_method
        JNI_AVAILABLE = True
    except ImportError:
        logger.warning("Pyjnius not available for Android input")


class AndroidInput(BaseInputController):
    """Android input implementation using JNI touch/key listeners."""

    def __init__(self):
        """Initialize Android input."""
        super().__init__()
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._running = False
        self._touch_listener: Any = None
        self._key_listener: Any = None
        self._dispatch_task: asyncio.Task | None = None

    async def initialize(self) -> bool:
        """Initialize input devices."""
        if not ANDROID_AVAILABLE:
            if is_test_mode():
                logger.info("Android input not available (wrong platform), gracefully degrading")
                return False
            raise RuntimeError("Android input only available on Android")

        if not JNI_AVAILABLE:
            if is_test_mode():
                logger.info("Pyjnius not available, gracefully degrading")
                return False
            raise RuntimeError("Pyjnius not available")

        try:
            activity = PythonActivity.mActivity

            # Get the root view
            root_view = activity.getWindow().getDecorView().getRootView()

            # Create touch listener
            parent = self

            class TouchListener(PythonJavaClass):
                __javainterfaces__ = ["android/view/View$OnTouchListener"]

                @java_method("(Landroid/view/View;Landroid/view/MotionEvent;)Z")
                def onTouch(self, view, event):
                    parent._handle_touch_event(event)
                    return False  # Don't consume, let it propagate

            class KeyListener(PythonJavaClass):
                __javainterfaces__ = ["android/view/View$OnKeyListener"]

                @java_method("(Landroid/view/View;ILandroid/view/KeyEvent;)Z")
                def onKey(self, view, keyCode, event):
                    parent._handle_key_event(keyCode, event)
                    return False

            self._touch_listener = TouchListener()
            self._key_listener = KeyListener()

            # Set listeners on root view
            root_view.setOnTouchListener(self._touch_listener)
            root_view.setOnKeyListener(self._key_listener)

            self._running = True

            # Start async dispatch task
            self._dispatch_task = asyncio.create_task(self._dispatch_loop())

            logger.info("✅ Android input initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Android input: {e}", exc_info=True)
            return False

    def _handle_touch_event(self, motion_event: Any) -> None:
        """Handle touch event from JNI callback."""
        try:
            action = motion_event.getAction() & MotionEvent.ACTION_MASK
            x = motion_event.getX()
            y = motion_event.getY()

            # Map action to value
            if action == MotionEvent.ACTION_DOWN:
                value = 1
            elif action == MotionEvent.ACTION_UP:
                value = 0
            elif action == MotionEvent.ACTION_MOVE:
                value = 2
            else:
                return  # Ignore other actions

            # Encode position in code (x * 10000 + y)
            code = int(x * 10000 + y)

            event = InputEvent(
                type=InputType.TOUCHSCREEN,
                code=code,
                value=value,
                timestamp_ms=int(time.time() * 1000),
            )

            try:
                self._event_queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop oldest events if queue full

        except Exception as e:
            logger.error(f"Error handling touch event: {e}")

    def _handle_key_event(self, key_code: int, key_event: Any) -> None:
        """Handle key event from JNI callback."""
        try:
            action = key_event.getAction()

            # Map action to value
            if action == KeyEvent.ACTION_DOWN:
                value = 1
            elif action == KeyEvent.ACTION_UP:
                value = 0
            else:
                return

            event = InputEvent(
                type=InputType.KEYBOARD,
                code=key_code,
                value=value,
                timestamp_ms=int(time.time() * 1000),
            )

            try:
                self._event_queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        except Exception as e:
            logger.error(f"Error handling key event: {e}")

    async def _dispatch_loop(self) -> None:
        """Dispatch queued events to subscribers."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=0.1)

                for callback in self._subscribers.get(event.type, []):
                    try:
                        await callback(event)
                    except Exception as e:
                        logger.error(f"Error in input callback: {e}")

            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Dispatch loop error: {e}")

    async def read_event(self) -> InputEvent | None:
        """Read next input event (non-blocking)."""
        try:
            return self._event_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def inject_event(self, type: InputType, code: int, value: int) -> bool:
        """Inject synthetic input event.

        Note: Requires INJECT_EVENTS permission (system apps only).
        """
        logger.warning("Event injection requires system permissions on Android")
        return False

    async def shutdown(self) -> None:
        """Shutdown input controller."""
        self._running = False

        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass

        logger.info("✅ Android input shutdown")
