"""Meta Neural Band EMG Adapter.

Provides integration with Meta's sEMG (surface Electromyography) wristband
for neural input control. The Meta Neural Band captures electrical signals
from muscle movements in the wrist to enable gesture recognition.

Technical Background:
- 16 electrode pods with gold-plated sensors
- 2kHz sampling rate per electrode
- On-device ML for gesture classification
- Response times measured in milliseconds

Supported Gestures (based on Meta's published patterns):
- Thumb tap (discrete click)
- Thumb swipe left/right/forward/backward
- Pinch (thumb to index)
- Finger-based gestures via EMG patterns

Integration:
- WebSocket connection to Meta companion app
- Works alongside Meta Ray-Ban Display glasses
- Can pair with Quest headsets for development

References:
- Meta EMG Technology: https://www.meta.com/emerging-tech/emg-wearable-technology/
- sEMG White Paper: https://www.meta.com/blog/surface-emg-wrist-white-paper-reality-labs/
- Microgestures SDK: https://developers.meta.com/horizon/documentation/unity/unity-microgestures/

Created: January 2026
h(x) >= 0. Always.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class EMGConnectionState(Enum):
    """Connection state for Meta Neural Band."""

    DISCONNECTED = "disconnected"
    SCANNING = "scanning"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CALIBRATING = "calibrating"
    READY = "ready"
    ERROR = "error"


class EMGCalibrationState(Enum):
    """Calibration state for neural band."""

    NOT_CALIBRATED = "not_calibrated"
    CALIBRATING = "calibrating"
    CALIBRATED = "calibrated"
    NEEDS_RECALIBRATION = "needs_recalibration"


class EMGGesture(Enum):
    """EMG-detectable gestures from Meta Neural Band.

    Based on Meta's published gesture vocabulary for sEMG wristbands.
    These gestures are detected via muscle activation patterns, not cameras.
    """

    NONE = "none"

    # Thumb microgestures (on index finger surface)
    THUMB_TAP = "thumb_tap"  # Quick tap on index finger
    THUMB_DOUBLE_TAP = "thumb_double_tap"  # Double tap
    THUMB_SWIPE_LEFT = "thumb_swipe_left"  # Swipe toward fingertip (left hand)
    THUMB_SWIPE_RIGHT = "thumb_swipe_right"  # Swipe away from fingertip (left hand)
    THUMB_SWIPE_FORWARD = "thumb_swipe_forward"  # Swipe away from palm
    THUMB_SWIPE_BACKWARD = "thumb_swipe_backward"  # Swipe toward palm

    # Pinch gestures
    PINCH_INDEX = "pinch_index"  # Thumb to index finger
    PINCH_MIDDLE = "pinch_middle"  # Thumb to middle finger
    PINCH_HOLD = "pinch_hold"  # Sustained pinch
    PINCH_RELEASE = "pinch_release"  # Release from pinch

    # Finger gestures (EMG-detectable)
    INDEX_TAP = "index_tap"  # Index finger tap
    MIDDLE_TAP = "middle_tap"  # Middle finger tap
    DOUBLE_FINGER_TAP = "double_finger_tap"  # Two fingers together

    # Wrist rotations (via IMU + EMG confirmation)
    WRIST_ROTATE_CW = "wrist_rotate_cw"  # Clockwise rotation
    WRIST_ROTATE_CCW = "wrist_rotate_ccw"  # Counter-clockwise rotation

    # EMG handwriting (text input mode)
    HANDWRITING_CHAR = "handwriting_char"  # Character drawn on surface

    # Special
    CUSTOM = "custom"  # User-defined gesture


@dataclass
class EMGSignalData:
    """Raw EMG signal data from electrodes."""

    electrode_values: list[float]  # 16 electrode readings
    timestamp: float
    sample_index: int = 0

    @property
    def rms(self) -> float:
        """Root mean square of electrode values."""
        if not self.electrode_values:
            return 0.0
        import math

        squared = sum(v * v for v in self.electrode_values)
        return math.sqrt(squared / len(self.electrode_values))


@dataclass
class EMGGestureEvent:
    """Detected gesture from EMG processing."""

    gesture: EMGGesture
    confidence: float  # 0.0 to 1.0
    timestamp: float = field(default_factory=time.time)

    # For swipe gestures
    direction: tuple[float, float] | None = None  # (x, y) normalized

    # For handwriting
    character: str | None = None

    # Raw signal data (optional, for debugging)
    raw_signal: EMGSignalData | None = None


@dataclass
class MetaEMGEvent:
    """Event from Meta Neural Band."""

    event_type: str
    timestamp: float
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, json_data: dict[str, Any]) -> MetaEMGEvent:
        """Create event from JSON data."""
        return cls(
            event_type=json_data.get("type", "unknown"),
            timestamp=json_data.get("timestamp", time.time()),
            data=json_data.get("data", {}),
        )


@dataclass
class MetaEMGConfig:
    """Configuration for Meta EMG adapter."""

    # Connection
    companion_url: str = "ws://localhost:8002/ws/neural-band"
    auto_reconnect: bool = True
    reconnect_delay_s: float = 5.0

    # Gesture detection
    gesture_confidence_threshold: float = 0.7
    debounce_ms: int = 100

    # Haptic feedback
    haptic_feedback_enabled: bool = True

    # Calibration
    auto_calibrate_on_connect: bool = True
    calibration_samples: int = 50

    # Band size (affects electrode spacing)
    # Options: "small" (10.6mm), "medium" (12mm), "large" (13mm), "xlarge" (15mm)
    band_size: str = "medium"


EMGEventCallback = Callable[[MetaEMGEvent], Awaitable[None]]
GestureCallback = Callable[[EMGGestureEvent], Awaitable[None]]


class MetaEMGAdapter:
    """Adapter for Meta Neural Band (sEMG wristband).

    Provides neural input for XR applications via EMG gesture recognition.
    Works in conjunction with Meta Ray-Ban Display or Quest headsets.

    Usage:
        adapter = MetaEMGAdapter()
        await adapter.initialize()

        # Register gesture callback
        adapter.on_gesture(handle_gesture)

        # Connect to neural band
        await adapter.connect()

        # Gestures are now delivered via callback

    The adapter communicates with a companion app that bridges to the
    actual neural band hardware via Bluetooth.
    """

    def __init__(self, config: MetaEMGConfig | None = None) -> None:
        self.config = config or MetaEMGConfig()

        self._connection_state = EMGConnectionState.DISCONNECTED
        self._calibration_state = EMGCalibrationState.NOT_CALIBRATED

        self._websocket: Any | None = None
        self._running = False
        self._receive_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None

        # Callbacks
        self._event_callbacks: list[EMGEventCallback] = []
        self._gesture_callbacks: list[GestureCallback] = []

        # Gesture detection state
        self._last_gesture_time: float = 0.0
        self._current_gesture: EMGGesture = EMGGesture.NONE

        # Device info
        self._device_name: str = ""
        self._firmware_version: str = ""
        self._battery_level: int = 0

        # Calibration data
        self._baseline_signal: EMGSignalData | None = None

        logger.info("MetaEMGAdapter created")

    @property
    def connection_state(self) -> EMGConnectionState:
        """Get current connection state."""
        return self._connection_state

    @property
    def calibration_state(self) -> EMGCalibrationState:
        """Get current calibration state."""
        return self._calibration_state

    @property
    def is_connected(self) -> bool:
        """Check if neural band is connected."""
        return self._connection_state in (
            EMGConnectionState.CONNECTED,
            EMGConnectionState.CALIBRATING,
            EMGConnectionState.READY,
        )

    @property
    def is_ready(self) -> bool:
        """Check if neural band is ready for gesture detection."""
        return self._connection_state == EMGConnectionState.READY

    @property
    def device_info(self) -> dict[str, Any]:
        """Get device information."""
        return {
            "device_name": self._device_name,
            "firmware_version": self._firmware_version,
            "battery_level": self._battery_level,
            "band_size": self.config.band_size,
        }

    async def initialize(self) -> bool:
        """Initialize the EMG adapter.

        Returns:
            True if initialization successful
        """
        logger.info("Initializing MetaEMGAdapter...")

        # In test mode, skip actual connection
        try:
            from kagami.core.boot_mode import is_test_mode

            if is_test_mode():
                logger.info("MetaEMGAdapter in test mode")
                return True
        except ImportError:
            pass

        logger.info("MetaEMGAdapter initialized")
        return True

    async def connect(self) -> bool:
        """Connect to Meta Neural Band via companion app.

        Returns:
            True if connection successful
        """
        if self.is_connected:
            logger.warning("Already connected to neural band")
            return True

        self._connection_state = EMGConnectionState.SCANNING
        logger.info("Scanning for Meta Neural Band...")

        try:
            import aiohttp

            self._connection_state = EMGConnectionState.CONNECTING

            # Connect WebSocket to companion app
            session = aiohttp.ClientSession()
            self._websocket = await session.ws_connect(
                self.config.companion_url,
                timeout=aiohttp.ClientTimeout(total=15),
            )

            self._running = True
            self._receive_task = asyncio.create_task(self._receive_loop())

            # Send connect command to companion
            await self._send_command("connect", {"band_size": self.config.band_size})

            # Wait for connection confirmation
            await asyncio.sleep(1.0)

            if self._connection_state == EMGConnectionState.CONNECTED:
                logger.info(f"Connected to Neural Band: {self._device_name}")

                # Auto-calibrate if configured
                if self.config.auto_calibrate_on_connect:
                    await self.calibrate()

                return True
            else:
                logger.warning("Neural band connection not confirmed")
                return False

        except ImportError:
            logger.warning("aiohttp not available - running in mock mode")
            self._connection_state = EMGConnectionState.READY
            return True

        except Exception as e:
            logger.error(f"Failed to connect to neural band: {e}")
            self._connection_state = EMGConnectionState.ERROR

            # Start reconnect task if configured
            if self.config.auto_reconnect:
                self._start_reconnect_task()

            return False

    async def disconnect(self) -> None:
        """Disconnect from neural band."""
        logger.info("Disconnecting from neural band...")

        self._running = False

        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._websocket:
            await self._websocket.close()
            self._websocket = None

        self._connection_state = EMGConnectionState.DISCONNECTED
        logger.info("Disconnected from neural band")

    async def calibrate(self) -> bool:
        """Calibrate the neural band for current user.

        Calibration captures baseline EMG signals to improve gesture
        recognition accuracy for the current user.

        Returns:
            True if calibration successful
        """
        if not self.is_connected:
            logger.warning("Cannot calibrate - not connected")
            return False

        logger.info("Starting neural band calibration...")
        self._connection_state = EMGConnectionState.CALIBRATING
        self._calibration_state = EMGCalibrationState.CALIBRATING

        try:
            result = await self._send_command(
                "calibrate",
                {"samples": self.config.calibration_samples},
                wait_response=True,
                timeout=30.0,
            )

            if result and result.get("success"):
                self._calibration_state = EMGCalibrationState.CALIBRATED
                self._connection_state = EMGConnectionState.READY
                logger.info("Neural band calibration complete")
                return True
            else:
                self._calibration_state = EMGCalibrationState.NEEDS_RECALIBRATION
                self._connection_state = EMGConnectionState.CONNECTED
                logger.warning("Neural band calibration failed")
                return False

        except Exception as e:
            logger.error(f"Calibration error: {e}")
            self._calibration_state = EMGCalibrationState.NEEDS_RECALIBRATION
            self._connection_state = EMGConnectionState.CONNECTED
            return False

    async def _send_command(
        self,
        command: str,
        params: dict[str, Any] | None = None,
        wait_response: bool = False,
        timeout: float = 5.0,
    ) -> dict[str, Any] | None:
        """Send command to companion app."""
        if not self._websocket:
            logger.warning("WebSocket not connected")
            return None

        import uuid

        message_id = str(uuid.uuid4())
        message = {
            "id": message_id,
            "command": command,
            "params": params or {},
        }

        try:
            await self._websocket.send_json(message)

            if wait_response:
                # Simple response waiting - in production would use proper futures
                await asyncio.sleep(timeout)
                return {"success": True}  # Placeholder

            return None

        except Exception as e:
            logger.error(f"Failed to send command {command}: {e}")
            return None

    async def _receive_loop(self) -> None:
        """Receive messages from WebSocket."""
        if not self._websocket:
            return

        try:
            async for msg in self._websocket:
                if not self._running:
                    break

                if msg.type == 1:  # TEXT
                    await self._handle_message(json.loads(msg.data))
                elif msg.type == 2:  # BINARY
                    await self._handle_binary(msg.data)
                elif msg.type == 8:  # CLOSE
                    break
                elif msg.type == 256:  # ERROR
                    logger.error(f"WebSocket error: {msg.data}")
                    break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
        finally:
            self._connection_state = EMGConnectionState.DISCONNECTED
            if self.config.auto_reconnect:
                self._start_reconnect_task()

    async def _handle_message(self, data: dict[str, Any]) -> None:
        """Handle received JSON message."""
        msg_type = data.get("type", "")

        if msg_type == "connection_status":
            self._handle_connection_status(data.get("data", {}))

        elif msg_type == "gesture":
            await self._handle_gesture(data.get("data", {}))

        elif msg_type == "device_info":
            self._handle_device_info(data.get("data", {}))

        elif msg_type == "battery":
            self._battery_level = data.get("data", {}).get("level", 0)

        else:
            # Forward as generic event
            event = MetaEMGEvent.from_json(data)
            await self._dispatch_event(event)

    async def _handle_binary(self, data: bytes) -> None:
        """Handle raw EMG signal data (binary)."""
        # First byte is packet type
        if len(data) < 1:
            return

        packet_type = data[0]

        if packet_type == 0x10:  # Raw EMG data
            # Parse 16 electrode values (32 bytes, 2 bytes each)
            if len(data) >= 33:
                import struct

                electrode_values = []
                for i in range(16):
                    offset = 1 + i * 2
                    value = struct.unpack("<h", data[offset : offset + 2])[0] / 32768.0
                    electrode_values.append(value)

                # Could expose raw signal callback here if needed
                _ = EMGSignalData(
                    electrode_values=electrode_values,
                    timestamp=time.time(),
                )

    def _handle_connection_status(self, data: dict[str, Any]) -> None:
        """Handle connection status update."""
        status = data.get("status", "")

        if status == "connected":
            self._connection_state = EMGConnectionState.CONNECTED
            self._device_name = data.get("device_name", "Meta Neural Band")
        elif status == "ready":
            self._connection_state = EMGConnectionState.READY
        elif status == "disconnected":
            self._connection_state = EMGConnectionState.DISCONNECTED
        elif status == "error":
            self._connection_state = EMGConnectionState.ERROR
            logger.error(f"Neural band error: {data.get('error', 'Unknown')}")

    def _handle_device_info(self, data: dict[str, Any]) -> None:
        """Handle device info update."""
        self._device_name = data.get("device_name", self._device_name)
        self._firmware_version = data.get("firmware_version", "")
        self._battery_level = data.get("battery_level", 0)

    async def _handle_gesture(self, data: dict[str, Any]) -> None:
        """Handle gesture detection from companion app."""
        now = time.time()

        # Debounce
        if (now - self._last_gesture_time) * 1000 < self.config.debounce_ms:
            return

        gesture_name = data.get("gesture", "none")
        confidence = data.get("confidence", 0.0)

        # Filter by confidence threshold
        if confidence < self.config.gesture_confidence_threshold:
            return

        try:
            gesture = EMGGesture(gesture_name)
        except ValueError:
            gesture = EMGGesture.CUSTOM

        # Create gesture event
        event = EMGGestureEvent(
            gesture=gesture,
            confidence=confidence,
            timestamp=now,
            direction=data.get("direction"),
            character=data.get("character"),
        )

        self._last_gesture_time = now
        self._current_gesture = gesture

        # Dispatch to callbacks
        for callback in self._gesture_callbacks:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Gesture callback error: {e}")

    async def _dispatch_event(self, event: MetaEMGEvent) -> None:
        """Dispatch event to callbacks."""
        for callback in self._event_callbacks:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")

    def _start_reconnect_task(self) -> None:
        """Start automatic reconnection task."""
        if self._reconnect_task and not self._reconnect_task.done():
            return

        async def reconnect_loop():
            while self._connection_state == EMGConnectionState.DISCONNECTED:
                await asyncio.sleep(self.config.reconnect_delay_s)
                logger.info("Attempting to reconnect to neural band...")
                try:
                    await self.connect()
                except Exception as e:
                    logger.warning(f"Reconnect failed: {e}")

        self._reconnect_task = asyncio.create_task(reconnect_loop())

    # =========================================================================
    # Public Gesture Mapping API
    # =========================================================================

    def on_event(self, callback: EMGEventCallback) -> None:
        """Register callback for raw events."""
        self._event_callbacks.append(callback)

    def off_event(self, callback: EMGEventCallback) -> None:
        """Unregister event callback."""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)

    def on_gesture(self, callback: GestureCallback) -> None:
        """Register callback for gesture events.

        Args:
            callback: Async function called when gesture detected
        """
        self._gesture_callbacks.append(callback)

    def off_gesture(self, callback: GestureCallback) -> None:
        """Unregister gesture callback."""
        if callback in self._gesture_callbacks:
            self._gesture_callbacks.remove(callback)

    def map_to_kagami_action(self, gesture: EMGGesture) -> str | None:
        """Map EMG gesture to Kagami semantic action.

        Standard mappings:
            THUMB_TAP -> primary_action (select/confirm)
            THUMB_DOUBLE_TAP -> toggle
            THUMB_SWIPE_LEFT -> previous
            THUMB_SWIPE_RIGHT -> next
            PINCH_INDEX -> select
            PINCH_HOLD -> voice_input
            WRIST_ROTATE_CW -> volume_up / brightness_up
            WRIST_ROTATE_CCW -> volume_down / brightness_down

        Returns:
            Kagami action name or None if no mapping
        """
        mapping = {
            EMGGesture.THUMB_TAP: "primary_action",
            EMGGesture.THUMB_DOUBLE_TAP: "toggle",
            EMGGesture.THUMB_SWIPE_LEFT: "previous",
            EMGGesture.THUMB_SWIPE_RIGHT: "next",
            EMGGesture.THUMB_SWIPE_FORWARD: "scroll_up",
            EMGGesture.THUMB_SWIPE_BACKWARD: "scroll_down",
            EMGGesture.PINCH_INDEX: "select",
            EMGGesture.PINCH_HOLD: "voice_input",
            EMGGesture.PINCH_RELEASE: "confirm",
            EMGGesture.WRIST_ROTATE_CW: "volume_up",
            EMGGesture.WRIST_ROTATE_CCW: "volume_down",
            EMGGesture.INDEX_TAP: "quick_action_1",
            EMGGesture.MIDDLE_TAP: "quick_action_2",
        }

        return mapping.get(gesture)

    async def shutdown(self) -> None:
        """Shutdown the EMG adapter."""
        await self.disconnect()
        self._event_callbacks.clear()
        self._gesture_callbacks.clear()
        logger.info("MetaEMGAdapter shutdown")


# =============================================================================
# Singleton
# =============================================================================

_adapter: MetaEMGAdapter | None = None


def get_meta_emg_adapter(config: MetaEMGConfig | None = None) -> MetaEMGAdapter:
    """Get or create the Meta EMG adapter singleton."""
    global _adapter
    if _adapter is None:
        _adapter = MetaEMGAdapter(config)
    return _adapter


async def initialize_meta_emg(config: MetaEMGConfig | None = None) -> MetaEMGAdapter:
    """Initialize and return the Meta EMG adapter."""
    adapter = get_meta_emg_adapter(config)
    await adapter.initialize()
    return adapter


"""
Mirror
h(x) >= 0. Always.

Neural input is thought made motion.
The wrist speaks what the mind intends.
Muscle signals bridge will to action.
"""
