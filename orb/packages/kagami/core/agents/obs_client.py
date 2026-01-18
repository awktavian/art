"""OBS WebSocket Client — Control OBS Studio from agents.

This module provides:
- WebSocket connection to OBS Studio
- Scene switching
- Recording control
- Source manipulation
- Real-time events

Protocol: OBS WebSocket Protocol v5
Reference: https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md

Colony: Forge (e2) — Building
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from kagami.core.agents.schema import OBSConfig

logger = logging.getLogger(__name__)


# =============================================================================
# OBS WebSocket Protocol
# =============================================================================


class OBSOpCode:
    """OBS WebSocket operation codes."""

    HELLO = 0
    IDENTIFY = 1
    IDENTIFIED = 2
    REIDENTIFY = 3
    EVENT = 5
    REQUEST = 6
    REQUEST_RESPONSE = 7
    REQUEST_BATCH = 8
    REQUEST_BATCH_RESPONSE = 9


# =============================================================================
# OBS Client
# =============================================================================


@dataclass
class OBSClient:
    """WebSocket client for OBS Studio.

    Connects to OBS via obs-websocket and provides methods for:
    - Scene management
    - Recording/streaming control
    - Source manipulation
    - Event subscriptions

    Example:
        ```python
        obs = OBSClient(config)
        await obs.connect()
        await obs.set_current_scene("Cooking")
        await obs.start_recording()
        await obs.disconnect()
        ```
    """

    config: OBSConfig
    _ws: aiohttp.ClientWebSocketResponse | None = None
    _session: aiohttp.ClientSession | None = None
    _connected: bool = False
    _authenticated: bool = False
    _message_id: int = 0
    _pending_requests: dict[str, asyncio.Future] = field(default_factory=dict)
    _event_handlers: dict[str, list[Callable]] = field(default_factory=dict)
    _receive_task: asyncio.Task | None = None

    async def connect(self) -> bool:
        """Connect to OBS WebSocket server.

        Returns:
            True if connection successful.
        """
        if self._connected:
            return True

        try:
            self._session = aiohttp.ClientSession()
            self._ws = await self._session.ws_connect(
                self.config.websocket,
                heartbeat=30.0,
            )

            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())

            # Wait for Hello message and authenticate
            hello = await asyncio.wait_for(self._wait_for_hello(), timeout=5.0)
            await self._authenticate(hello)

            self._connected = True
            logger.info(f"Connected to OBS at {self.config.websocket}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to OBS: {e}")
            await self.disconnect()
            return False

    async def disconnect(self) -> None:
        """Disconnect from OBS."""
        self._connected = False
        self._authenticated = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._session:
            await self._session.close()
            self._session = None

        logger.info("Disconnected from OBS")

    async def _wait_for_hello(self) -> dict[str, Any]:
        """Wait for Hello message from OBS."""
        while self._ws:
            msg = await self._ws.receive()
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get("op") == OBSOpCode.HELLO:
                    return data.get("d", {})
        raise ConnectionError("No Hello message received")

    async def _authenticate(self, hello: dict[str, Any]) -> None:
        """Authenticate with OBS."""
        auth_required = hello.get("authentication")

        identify_payload = {
            "rpcVersion": 1,
            "eventSubscriptions": 0xFFFFFFFF,  # Subscribe to all events
        }

        if auth_required and self.config.password:
            # Generate authentication string
            challenge = auth_required.get("challenge", "")
            salt = auth_required.get("salt", "")

            # SHA256(password + salt) -> base64 -> SHA256(base64 + challenge) -> base64
            secret_hash = hashlib.sha256((self.config.password + salt).encode()).digest()
            secret = base64.b64encode(secret_hash).decode()

            auth_hash = hashlib.sha256((secret + challenge).encode()).digest()
            auth = base64.b64encode(auth_hash).decode()

            identify_payload["authentication"] = auth

        # Send Identify
        await self._send_message(OBSOpCode.IDENTIFY, identify_payload)

        # Wait for Identified response
        while self._ws:
            msg = await self._ws.receive()
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get("op") == OBSOpCode.IDENTIFIED:
                    self._authenticated = True
                    return
                elif data.get("op") == OBSOpCode.REQUEST_RESPONSE:
                    # Some OBS versions send this instead
                    if not data.get("d", {}).get("requestStatus", {}).get("result", False):
                        raise ConnectionError("Authentication failed")
                    return

        raise ConnectionError("Authentication failed")

    async def _send_message(self, op: int, data: dict[str, Any]) -> None:
        """Send message to OBS."""
        if not self._ws:
            raise ConnectionError("Not connected to OBS")

        message = {"op": op, "d": data}
        await self._ws.send_str(json.dumps(message))

    async def _receive_loop(self) -> None:
        """Background loop to receive messages."""
        while self._ws:
            try:
                msg = await self._ws.receive()

                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._handle_message(data)

                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                    break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"OBS receive error: {e}")

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """Handle incoming OBS message."""
        op = message.get("op")
        data = message.get("d", {})

        if op == OBSOpCode.REQUEST_RESPONSE:
            # Handle request response
            request_id = data.get("requestId")
            if request_id in self._pending_requests:
                future = self._pending_requests.pop(request_id)
                if data.get("requestStatus", {}).get("result", False):
                    future.set_result(data.get("responseData", {}))
                else:
                    error = data.get("requestStatus", {}).get("comment", "Unknown error")
                    future.set_exception(RuntimeError(error))

        elif op == OBSOpCode.EVENT:
            # Handle event
            event_type = data.get("eventType")
            event_data = data.get("eventData", {})
            await self._dispatch_event(event_type, event_data)

    async def _dispatch_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Dispatch event to registered handlers."""
        handlers = self._event_handlers.get(event_type, [])
        handlers += self._event_handlers.get("*", [])  # Wildcard handlers

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_type, event_data)
                else:
                    handler(event_type, event_data)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    # =========================================================================
    # Request Methods
    # =========================================================================

    async def request(
        self, request_type: str, request_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send request to OBS and wait for response.

        Args:
            request_type: OBS request type (e.g., "SetCurrentProgramScene").
            request_data: Optional request data.

        Returns:
            Response data from OBS.
        """
        if not self._connected:
            raise ConnectionError("Not connected to OBS")

        request_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.Future()
        self._pending_requests[request_id] = future

        payload = {
            "requestType": request_type,
            "requestId": request_id,
        }
        if request_data:
            payload["requestData"] = request_data

        await self._send_message(OBSOpCode.REQUEST, payload)

        try:
            return await asyncio.wait_for(future, timeout=10.0)
        except TimeoutError as e:
            self._pending_requests.pop(request_id, None)
            raise TimeoutError(f"OBS request timed out: {request_type}") from e

    async def execute_command(
        self, command: str, args: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute OBS command by name.

        Common commands:
        - StartRecording, StopRecording
        - StartStreaming, StopStreaming
        - SetCurrentProgramScene
        - GetSceneList
        - GetCurrentProgramScene

        Args:
            command: OBS command name.
            args: Optional arguments.

        Returns:
            Command result.
        """
        return await self.request(command, args)

    # =========================================================================
    # Scene Methods
    # =========================================================================

    async def get_scene_list(self) -> list[dict[str, Any]]:
        """Get list of all scenes.

        Returns:
            List of scene objects with names.
        """
        result = await self.request("GetSceneList")
        return result.get("scenes", [])

    async def get_current_scene(self) -> str:
        """Get current program scene name.

        Returns:
            Scene name.
        """
        result = await self.request("GetCurrentProgramScene")
        return result.get("currentProgramSceneName", "")

    async def set_current_scene(self, scene_name: str) -> None:
        """Switch to a scene.

        Args:
            scene_name: Name of scene to switch to.
        """
        await self.request("SetCurrentProgramScene", {"sceneName": scene_name})
        logger.info(f"OBS: Switched to scene '{scene_name}'")

    # =========================================================================
    # Recording Methods
    # =========================================================================

    async def start_recording(self) -> None:
        """Start recording."""
        await self.request("StartRecord")
        logger.info("OBS: Recording started")

    async def stop_recording(self) -> None:
        """Stop recording."""
        await self.request("StopRecord")
        logger.info("OBS: Recording stopped")

    async def toggle_recording(self) -> bool:
        """Toggle recording state.

        Returns:
            True if now recording.
        """
        result = await self.request("ToggleRecord")
        return result.get("outputActive", False)

    async def get_recording_status(self) -> dict[str, Any]:
        """Get recording status.

        Returns:
            Recording status object.
        """
        return await self.request("GetRecordStatus")

    # =========================================================================
    # Streaming Methods
    # =========================================================================

    async def start_streaming(self) -> None:
        """Start streaming."""
        await self.request("StartStream")
        logger.info("OBS: Streaming started")

    async def stop_streaming(self) -> None:
        """Stop streaming."""
        await self.request("StopStream")
        logger.info("OBS: Streaming stopped")

    async def toggle_streaming(self) -> bool:
        """Toggle streaming state.

        Returns:
            True if now streaming.
        """
        result = await self.request("ToggleStream")
        return result.get("outputActive", False)

    async def get_streaming_status(self) -> dict[str, Any]:
        """Get streaming status.

        Returns:
            Streaming status object.
        """
        return await self.request("GetStreamStatus")

    # =========================================================================
    # Source Methods
    # =========================================================================

    async def get_source_list(self, scene_name: str | None = None) -> list[dict[str, Any]]:
        """Get list of sources in a scene.

        Args:
            scene_name: Scene name (uses current if not specified).

        Returns:
            List of source objects.
        """
        if not scene_name:
            scene_name = await self.get_current_scene()

        result = await self.request("GetSceneItemList", {"sceneName": scene_name})
        return result.get("sceneItems", [])

    async def set_source_visibility(
        self, source_name: str, visible: bool, scene_name: str | None = None
    ) -> None:
        """Set source visibility.

        Args:
            source_name: Source name.
            visible: Whether source should be visible.
            scene_name: Scene name (uses current if not specified).
        """
        if not scene_name:
            scene_name = await self.get_current_scene()

        # Get scene item ID
        items = await self.get_source_list(scene_name)
        item_id = None
        for item in items:
            if item.get("sourceName") == source_name:
                item_id = item.get("sceneItemId")
                break

        if item_id is None:
            raise ValueError(f"Source not found: {source_name}")

        await self.request(
            "SetSceneItemEnabled",
            {
                "sceneName": scene_name,
                "sceneItemId": item_id,
                "sceneItemEnabled": visible,
            },
        )

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def on_event(self, event_type: str, handler: Callable) -> None:
        """Register event handler.

        Args:
            event_type: Event type to handle (or "*" for all).
            handler: Callback function(event_type, event_data).
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def off_event(self, event_type: str, handler: Callable) -> None:
        """Unregister event handler.

        Args:
            event_type: Event type.
            handler: Handler to remove.
        """
        if event_type in self._event_handlers:
            self._event_handlers[event_type] = [
                h for h in self._event_handlers[event_type] if h != handler
            ]


# =============================================================================
# Singleton Factory
# =============================================================================


_clients: dict[str, OBSClient] = {}


async def get_obs_client(config: OBSConfig) -> OBSClient:
    """Get or create OBS client for a config.

    Caches clients by WebSocket URL.

    Args:
        config: OBS configuration.

    Returns:
        Connected OBSClient.
    """
    key = config.websocket

    if key not in _clients:
        client = OBSClient(config=config)
        if await client.connect():
            _clients[key] = client
        else:
            raise ConnectionError(f"Failed to connect to OBS at {config.websocket}")

    return _clients[key]


async def close_all_obs_clients() -> None:
    """Close all OBS clients."""
    for client in _clients.values():
        await client.disconnect()
    _clients.clear()


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "OBSClient",
    "OBSOpCode",
    "close_all_obs_clients",
    "get_obs_client",
]
