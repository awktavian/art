"""Tesla Companion App WebSocket Namespace.

Handles real-time communication with the Tesla companion iOS/Android app
for Bluetooth audio relay to cabin speakers.

Protocol:
- App connects with auth token
- Server sends audio commands
- App acknowledges playback completion
- Heartbeat for connection health

Namespace: /companion

Created: January 1, 2026
"""

from __future__ import annotations

import logging
import time
from typing import Any

from kagami_api.socketio.namespaces.base import BaseNamespace
from kagami_api.socketio.telemetry import traced_operation

logger = logging.getLogger(__name__)


class CompanionNamespace(BaseNamespace):
    """Socket.IO namespace for Tesla companion app connections.

    Handles:
    - Device registration and health monitoring
    - Audio playback commands
    - Bluetooth status updates
    - Connection resilience

    Events (Server → App):
    - speak: Play audio through Bluetooth
    - stop: Stop current playback
    - config: Configuration update
    - ping: Health check

    Events (App → Server):
    - status: Device status update
    - speak_complete: Playback finished
    - error: Error report
    - pong: Health check response
    """

    def __init__(self):
        super().__init__(namespace="/companion")
        self._protocol = None  # Lazy load
        self._device_info: dict[str, dict[str, Any]] = {}

    def _get_protocol(self):
        """Get companion protocol (lazy load)."""
        if self._protocol is None:
            from kagami_smarthome.integrations.tesla import (
                get_companion_protocol,
            )

            self._protocol = get_companion_protocol()
        return self._protocol

    async def on_connect(
        self, sid: str, environ: dict[str, Any], auth: dict[str, Any] | None = None
    ):
        """Handle companion app connection."""
        with traced_operation("companion.connect", attributes={"sid": sid}):
            # Standard auth
            result = await super().on_connect(sid, environ, auth)
            if not result:
                return False

            # Extract device info
            device_info = (auth or {}).get("device", {})
            device_id = device_info.get("id") or f"device_{sid[:8]}"

            self._device_info[sid] = {
                "device_id": device_id,
                "platform": device_info.get("platform", "unknown"),
                "model": device_info.get("model"),
                "app_version": device_info.get("app_version"),
                "connected_at": time.time(),
            }

            # Register with protocol
            protocol = self._get_protocol()

            async def send_to_device(message: str) -> None:
                """Send message to this specific device."""
                await self.emit("message", {"data": message}, room=sid)

            await protocol.register_connection(
                send_func=send_to_device,
                device_id=device_id,
                device_info=device_info,
            )

            logger.info(
                f"✓ Companion connected: {device_id} ({device_info.get('platform', 'unknown')})"
            )

            return True

    async def on_disconnect(self, sid: str) -> None:
        """Handle companion app disconnection."""
        with traced_operation("companion.disconnect", attributes={"sid": sid}):
            # Get device ID before cleanup
            info = self._device_info.pop(sid, {})
            device_id = info.get("device_id", sid)

            # Unregister from protocol
            try:
                protocol = self._get_protocol()
                await protocol.unregister_connection(device_id)
            except Exception as e:
                logger.error(f"Error unregistering companion {device_id}: {e}")

            await super().on_disconnect(sid)

            logger.info(f"✗ Companion disconnected: {device_id}")

    async def on_status(self, sid: str, data: dict[str, Any]) -> None:
        """Handle status update from companion app.

        Expected data:
        {
            "connected": true,
            "bluetooth": true,
            "bluetooth_device": "Tesla Model S",
            "playing": false,
            "volume": 1.0,
            "battery_level": 0.85
        }
        """
        if not await self._require_auth(sid):
            return

        info = self._device_info.get(sid, {})
        device_id = info.get("device_id", sid)

        protocol = self._get_protocol()
        await protocol.handle_message(data | {"type": "status"}, device_id)

    async def on_speak_complete(self, sid: str, data: dict[str, Any]) -> None:
        """Handle speak completion from companion app.

        Expected data:
        {
            "request_id": "device_1_123456",
            "success": true,
            "duration_ms": 1500,
            "error": null
        }
        """
        if not await self._require_auth(sid):
            return

        info = self._device_info.get(sid, {})
        device_id = info.get("device_id", sid)

        protocol = self._get_protocol()
        await protocol.handle_message(data | {"type": "speak_complete"}, device_id)

    async def on_error(self, sid: str, data: dict[str, Any]) -> None:
        """Handle error report from companion app.

        Expected data:
        {
            "error": "Bluetooth disconnected",
            "request_id": "device_1_123456"  # optional
        }
        """
        if not await self._require_auth(sid):
            return

        info = self._device_info.get(sid, {})
        device_id = info.get("device_id", sid)

        protocol = self._get_protocol()
        await protocol.handle_message(data | {"type": "error"}, device_id)

    async def on_pong(self, sid: str, data: dict[str, Any]) -> None:
        """Handle pong response from companion app."""
        if not await self._require_auth(sid):
            return

        info = self._device_info.get(sid, {})
        device_id = info.get("device_id", sid)

        protocol = self._get_protocol()
        await protocol.handle_message(data | {"type": "pong"}, device_id)

    async def on_message(self, sid: str, data: dict[str, Any]) -> None:
        """Handle generic message (for raw protocol messages)."""
        if not await self._require_auth(sid):
            return

        info = self._device_info.get(sid, {})
        device_id = info.get("device_id", sid)

        protocol = self._get_protocol()
        await protocol.handle_message(data, device_id)

    # =========================================================================
    # SERVER → APP COMMANDS (called by protocol)
    # =========================================================================

    async def send_speak(
        self,
        device_id: str,
        request_id: str,
        text: str,
        audio_url: str,
        priority: int = 1,
        interrupt: bool = False,
    ) -> bool:
        """Send speak command to a specific device.

        Args:
            device_id: Target device
            request_id: Request tracking ID
            text: Text being spoken
            audio_url: URL to audio file
            priority: 1=normal, 2=high, 3=urgent
            interrupt: Stop current audio first

        Returns:
            True if message sent
        """
        # Find SID for this device
        target_sid = None
        for sid, info in self._device_info.items():
            if info.get("device_id") == device_id:
                target_sid = sid
                break

        if not target_sid:
            logger.warning(f"Device {device_id} not found")
            return False

        await self.emit(
            "speak",
            {
                "request_id": request_id,
                "text": text,
                "audio_url": audio_url,
                "priority": priority,
                "interrupt": interrupt,
            },
            room=target_sid,
        )
        return True

    async def send_stop(self, device_id: str, reason: str = "user") -> bool:
        """Send stop command to a specific device."""
        target_sid = None
        for sid, info in self._device_info.items():
            if info.get("device_id") == device_id:
                target_sid = sid
                break

        if not target_sid:
            return False

        await self.emit("stop", {"reason": reason}, room=target_sid)
        return True


# Singleton instance
_namespace_instance: CompanionNamespace | None = None


def get_companion_namespace() -> CompanionNamespace:
    """Get the singleton companion namespace instance."""
    global _namespace_instance
    if _namespace_instance is None:
        _namespace_instance = CompanionNamespace()
    return _namespace_instance


__all__ = ["CompanionNamespace", "get_companion_namespace"]
