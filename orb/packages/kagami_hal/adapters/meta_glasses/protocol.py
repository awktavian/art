"""Meta Glasses Protocol — Communication with Companion App.

Handles the WebSocket protocol between Kagami and the companion app
which bridges to the Ray-Ban Meta smart glasses via BLE.

Protocol Messages:
    - connect: Establish connection to glasses
    - disconnect: Close connection
    - start_camera: Begin camera stream
    - stop_camera: End camera stream
    - capture_photo: Take a single photo
    - start_audio: Begin microphone stream
    - stop_audio: End microphone stream
    - play_audio: Send audio to open-ear speakers
    - get_status: Query glasses state

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class GlassesConnectionState(Enum):
    """Connection state of the glasses."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    PAIRING = "pairing"
    ERROR = "error"


class GlassesCommand(Enum):
    """Commands that can be sent to the glasses."""

    CONNECT = "connect"
    DISCONNECT = "disconnect"
    START_CAMERA = "start_camera"
    STOP_CAMERA = "stop_camera"
    CAPTURE_PHOTO = "capture_photo"
    START_AUDIO = "start_audio"
    STOP_AUDIO = "stop_audio"
    PLAY_AUDIO = "play_audio"
    GET_STATUS = "get_status"
    SET_LED = "set_led"


@dataclass
class GlassesEvent:
    """Event received from the glasses."""

    event_type: str
    timestamp: float
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, json_data: dict[str, Any]) -> GlassesEvent:
        """Create event from JSON data."""
        return cls(
            event_type=json_data.get("type", "unknown"),
            timestamp=json_data.get("timestamp", 0.0),
            data=json_data.get("data", {}),
        )


@dataclass
class GlassesStatus:
    """Current status of the glasses."""

    connection_state: GlassesConnectionState = GlassesConnectionState.DISCONNECTED
    battery_level: int = 0  # 0-100
    is_wearing: bool = False
    camera_active: bool = False
    audio_active: bool = False
    firmware_version: str = ""
    device_name: str = ""


EventCallback = Callable[[GlassesEvent], Awaitable[None]]


class MetaGlassesProtocol:
    """Protocol handler for Meta Glasses communication.

    This class manages the WebSocket connection to the companion app
    which bridges to the glasses via BLE.

    Usage:
        protocol = MetaGlassesProtocol()
        await protocol.initialize("http://kagami.local:8001")
        await protocol.connect_glasses()

        # Subscribe to events
        protocol.on_event(handle_glasses_event)

        # Send commands
        await protocol.send_command(GlassesCommand.START_CAMERA)
    """

    def __init__(self) -> None:
        self._api_base_url: str | None = None
        self._status = GlassesStatus()
        self._event_callbacks: list[EventCallback] = []
        self._websocket: Any | None = None
        self._running = False
        self._receive_task: asyncio.Task | None = None

        # Command response futures (for request-response pattern)
        self._pending_responses: dict[str, asyncio.Future] = {}

    @property
    def status(self) -> GlassesStatus:
        """Get current glasses status."""
        return self._status

    @property
    def is_connected(self) -> bool:
        """Check if glasses are connected."""
        return self._status.connection_state == GlassesConnectionState.CONNECTED

    async def initialize(self, api_base_url: str = "http://kagami.local:8001") -> bool:
        """Initialize protocol handler.

        Args:
            api_base_url: Base URL of the Kagami API

        Returns:
            True if initialization successful
        """
        self._api_base_url = api_base_url

        # In test mode, just initialize without connecting
        try:
            from kagami.core.boot_mode import is_test_mode

            if is_test_mode():
                logger.info("MetaGlassesProtocol in test mode")
                return True
        except ImportError:
            pass

        logger.info("MetaGlassesProtocol initialized")
        return True

    async def connect_glasses(self) -> bool:
        """Connect to the glasses via companion app.

        Returns:
            True if connection successful
        """
        if not self._api_base_url:
            logger.warning("Protocol not initialized")
            return False

        self._status.connection_state = GlassesConnectionState.CONNECTING

        try:
            import aiohttp

            # Connect WebSocket to companion app endpoint
            ws_url = self._api_base_url.replace("http://", "ws://").replace("https://", "wss://")
            session = aiohttp.ClientSession()
            self._websocket = await session.ws_connect(
                f"{ws_url}/ws/meta-glasses",
                timeout=aiohttp.ClientTimeout(total=10),
            )

            # Start receive loop
            self._running = True
            self._receive_task = asyncio.create_task(self._receive_loop())

            # Send connect command
            await self.send_command(GlassesCommand.CONNECT)

            # Wait for connection confirmation
            await asyncio.sleep(1)  # Give time for response

            if self._status.connection_state == GlassesConnectionState.CONNECTED:
                logger.info("Glasses connected successfully")
                return True
            else:
                logger.warning("Glasses connection not confirmed")
                return False

        except Exception as e:
            logger.error(f"Failed to connect glasses: {e}")
            self._status.connection_state = GlassesConnectionState.ERROR
            return False

    async def disconnect_glasses(self) -> None:
        """Disconnect from the glasses."""
        self._running = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._websocket:
            await self._websocket.close()
            self._websocket = None

        self._status.connection_state = GlassesConnectionState.DISCONNECTED
        logger.info("Glasses disconnected")

    async def send_command(
        self,
        command: GlassesCommand,
        params: dict[str, Any] | None = None,
        wait_response: bool = False,
        timeout: float = 5.0,
    ) -> dict[str, Any] | None:
        """Send a command to the glasses.

        Args:
            command: Command to send
            params: Optional command parameters
            wait_response: Whether to wait for response
            timeout: Response timeout in seconds

        Returns:
            Response data if wait_response=True, else None
        """
        if not self._websocket:
            logger.warning("WebSocket not connected")
            return None

        import uuid

        message_id = str(uuid.uuid4())
        message = {
            "id": message_id,
            "command": command.value,
            "params": params or {},
        }

        try:
            await self._websocket.send_json(message)

            if wait_response:
                # Create future for response
                future: asyncio.Future = asyncio.Future()
                self._pending_responses[message_id] = future

                try:
                    return await asyncio.wait_for(future, timeout=timeout)
                except TimeoutError:
                    logger.warning(f"Command {command.value} timed out")
                    return None
                finally:
                    self._pending_responses.pop(message_id, None)

            return None

        except Exception as e:
            logger.error(f"Failed to send command {command.value}: {e}")
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
                    # Binary data (camera frames, audio)
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
            self._status.connection_state = GlassesConnectionState.DISCONNECTED

    async def _handle_message(self, data: dict[str, Any]) -> None:
        """Handle received JSON message."""
        msg_type = data.get("type", "")

        # Handle command responses
        if msg_type == "response":
            msg_id = data.get("id")
            if msg_id and msg_id in self._pending_responses:
                self._pending_responses[msg_id].set_result(data.get("data", {}))
            return

        # Handle status updates
        if msg_type == "status":
            self._update_status(data.get("data", {}))
            return

        # Handle events
        event = GlassesEvent.from_json(data)
        await self._dispatch_event(event)

    async def _handle_binary(self, data: bytes) -> None:
        """Handle received binary data (camera frames, audio)."""
        # First byte indicates data type
        if len(data) < 1:
            return

        data_type = data[0]

        if data_type == 0x01:  # Camera frame
            event = GlassesEvent(
                event_type="camera_frame",
                timestamp=0.0,
                data={"frame_data": data[1:]},
            )
            await self._dispatch_event(event)

        elif data_type == 0x02:  # Audio buffer
            event = GlassesEvent(
                event_type="audio_buffer",
                timestamp=0.0,
                data={"audio_data": data[1:]},
            )
            await self._dispatch_event(event)

    def _update_status(self, data: dict[str, Any]) -> None:
        """Update glasses status from data."""
        if "connection_state" in data:
            try:
                self._status.connection_state = GlassesConnectionState(data["connection_state"])
            except ValueError:
                pass

        if "battery_level" in data:
            self._status.battery_level = data["battery_level"]

        if "is_wearing" in data:
            self._status.is_wearing = data["is_wearing"]

        if "camera_active" in data:
            self._status.camera_active = data["camera_active"]

        if "audio_active" in data:
            self._status.audio_active = data["audio_active"]

        if "firmware_version" in data:
            self._status.firmware_version = data["firmware_version"]

        if "device_name" in data:
            self._status.device_name = data["device_name"]

    async def _dispatch_event(self, event: GlassesEvent) -> None:
        """Dispatch event to callbacks."""
        for callback in self._event_callbacks:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")

    def on_event(self, callback: EventCallback) -> None:
        """Register event callback.

        Args:
            callback: Async function to call with events
        """
        self._event_callbacks.append(callback)

    def off_event(self, callback: EventCallback) -> None:
        """Unregister event callback.

        Args:
            callback: Previously registered callback
        """
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)

    async def get_status(self) -> GlassesStatus:
        """Get current glasses status from device.

        Returns:
            GlassesStatus with current state
        """
        if self.is_connected:
            result = await self.send_command(GlassesCommand.GET_STATUS, wait_response=True)
            if result:
                self._update_status(result)

        return self._status

    async def shutdown(self) -> None:
        """Shutdown protocol handler."""
        await self.disconnect_glasses()
        self._event_callbacks.clear()
        logger.info("MetaGlassesProtocol shutdown")


"""
Mirror
h(x) >= 0. Always.

The protocol is the nervous system.
Commands flow out, events flow in.
"""
