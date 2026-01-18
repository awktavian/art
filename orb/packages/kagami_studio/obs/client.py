"""OBS WebSocket Client — Core connection and control.

Provides async interface to OBS Studio via WebSocket 5.x protocol.

Usage:
    from kagami_studio.obs import OBSController, connect_obs

    # Context manager (auto-connect/disconnect)
    async with connect_obs() as obs:
        scenes = await obs.get_scenes()
        await obs.switch_scene("Main")

    # Manual connection
    obs = OBSController()
    await obs.connect()
    await obs.switch_scene("Kagami Live")
    await obs.disconnect()
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class OBSConnectionState(str, Enum):
    """OBS connection state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class OBSConfig:
    """OBS connection configuration."""

    host: str = "localhost"
    port: int = 4455
    password: str | None = None
    auto_reconnect: bool = True
    reconnect_delay: float = 5.0
    timeout: float = 10.0

    @classmethod
    def from_keychain(cls) -> OBSConfig:
        """Load config with password from keychain."""
        try:
            from kagami.core.security import get_secret

            password = get_secret("obs_websocket_password")
            return cls(password=password)
        except Exception:
            return cls()


class OBSController:
    """OBS Studio WebSocket controller.

    Provides full control over OBS Studio:
    - Scene management (create, delete, switch, transition)
    - Source management (add, remove, configure)
    - Filter management (add, remove, enable/disable)
    - Streaming and recording control
    - Virtual camera control
    - Audio mixing
    - Screenshots

    Example:
        obs = OBSController()
        await obs.connect()

        # Scene control
        scenes = await obs.get_scenes()
        await obs.switch_scene("Main", transition="Fade", duration=500)

        # Source control
        await obs.add_source("Camera", "v4l2_input", {"device": "/dev/video0"})
        await obs.set_source_visible("Camera", visible=True)

        # Streaming
        await obs.start_streaming()
        await obs.start_recording()

        await obs.disconnect()
    """

    def __init__(self, config: OBSConfig | None = None):
        """Initialize controller.

        Args:
            config: Connection config (uses defaults if None)
        """
        self.config = config or OBSConfig()
        self._client: Any = None
        self._event_client: Any = None
        self._state = OBSConnectionState.DISCONNECTED
        self._reconnect_task: asyncio.Task | None = None
        self._event_handlers: dict[str, list] = {}
        self._lock = asyncio.Lock()

    @property
    def state(self) -> OBSConnectionState:
        """Current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._state == OBSConnectionState.CONNECTED

    async def connect(self) -> bool:
        """Connect to OBS Studio.

        Returns:
            True if connected successfully
        """
        if self.is_connected:
            return True

        self._state = OBSConnectionState.CONNECTING

        try:
            import obsws_python as obs

            # Request client (for commands)
            self._client = obs.ReqClient(
                host=self.config.host,
                port=self.config.port,
                password=self.config.password,
                timeout=self.config.timeout,
            )

            # Event client (for real-time events)
            self._event_client = obs.EventClient(
                host=self.config.host,
                port=self.config.port,
                password=self.config.password,
            )

            # Register event handlers
            self._setup_event_handlers()

            self._state = OBSConnectionState.CONNECTED
            logger.info(f"Connected to OBS at {self.config.host}:{self.config.port}")
            return True

        except ImportError:
            logger.error("obsws-python not installed. Run: pip install obsws-python")
            self._state = OBSConnectionState.ERROR
            return False

        except Exception as e:
            logger.error(f"Failed to connect to OBS: {e}")
            self._state = OBSConnectionState.ERROR

            if self.config.auto_reconnect:
                self._start_reconnect()

            return False

    async def disconnect(self) -> None:
        """Disconnect from OBS Studio."""
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None

        if self._event_client:
            try:
                self._event_client.unsubscribe()
            except Exception:
                pass
            self._event_client = None

        self._client = None
        self._state = OBSConnectionState.DISCONNECTED
        logger.info("Disconnected from OBS")

    def _setup_event_handlers(self) -> None:
        """Set up OBS event handlers."""
        if not self._event_client:
            return

        # Scene events
        self._event_client.callback.register(self._on_scene_changed)
        self._event_client.callback.register(self._on_scene_list_changed)

        # Source events
        self._event_client.callback.register(self._on_source_created)
        self._event_client.callback.register(self._on_source_removed)

        # Streaming events
        self._event_client.callback.register(self._on_stream_state_changed)
        self._event_client.callback.register(self._on_record_state_changed)

    def _on_scene_changed(self, data: Any) -> None:
        """Handle scene change event."""
        self._emit_event("scene_changed", data)

    def _on_scene_list_changed(self, data: Any) -> None:
        """Handle scene list change event."""
        self._emit_event("scene_list_changed", data)

    def _on_source_created(self, data: Any) -> None:
        """Handle source created event."""
        self._emit_event("source_created", data)

    def _on_source_removed(self, data: Any) -> None:
        """Handle source removed event."""
        self._emit_event("source_removed", data)

    def _on_stream_state_changed(self, data: Any) -> None:
        """Handle stream state change event."""
        self._emit_event("stream_state_changed", data)

    def _on_record_state_changed(self, data: Any) -> None:
        """Handle record state change event."""
        self._emit_event("record_state_changed", data)

    def _emit_event(self, event: str, data: Any) -> None:
        """Emit event to registered handlers."""
        for handler in self._event_handlers.get(event, []):
            try:
                handler(data)
            except Exception as e:
                logger.warning(f"Event handler error: {e}")

    def on_event(self, event: str, handler: callable) -> None:
        """Register event handler.

        Args:
            event: Event name (scene_changed, stream_state_changed, etc.)
            handler: Callback function
        """
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def _start_reconnect(self) -> None:
        """Start reconnection task."""
        if self._reconnect_task is not None:
            return

        async def reconnect_loop():
            while self._state != OBSConnectionState.CONNECTED:
                self._state = OBSConnectionState.RECONNECTING
                logger.info(f"Reconnecting to OBS in {self.config.reconnect_delay}s...")
                await asyncio.sleep(self.config.reconnect_delay)

                try:
                    await self.connect()
                except Exception:
                    pass

        self._reconnect_task = asyncio.create_task(reconnect_loop())

    def _ensure_connected(self) -> None:
        """Ensure we're connected, raise if not."""
        if not self.is_connected or not self._client:
            raise RuntimeError("Not connected to OBS. Call connect() first.")

    # =========================================================================
    # SCENE MANAGEMENT
    # =========================================================================

    async def get_scenes(self) -> list[dict]:
        """Get list of all scenes.

        Returns:
            List of scene info dicts with 'sceneName' and 'sceneIndex'
        """
        self._ensure_connected()
        result = self._client.get_scene_list()
        return [
            {"sceneName": s.get("sceneName"), "sceneIndex": s.get("sceneIndex")}
            for s in result.scenes
        ]

    async def get_current_scene(self) -> str:
        """Get current program scene name."""
        self._ensure_connected()
        return self._client.get_current_program_scene().current_program_scene_name

    async def switch_scene(
        self,
        scene_name: str,
        transition: str | None = None,
        duration: int | None = None,
    ) -> None:
        """Switch to a scene.

        Args:
            scene_name: Target scene name
            transition: Transition type (Fade, Cut, etc.) or None for default
            duration: Transition duration in ms
        """
        self._ensure_connected()

        if transition:
            self._client.set_current_scene_transition(transition)

        if duration:
            self._client.set_current_scene_transition_duration(duration)

        self._client.set_current_program_scene(scene_name)
        logger.info(f"Switched to scene: {scene_name}")

    async def create_scene(self, scene_name: str) -> None:
        """Create a new scene.

        Args:
            scene_name: Name for the new scene
        """
        self._ensure_connected()
        self._client.create_scene(scene_name)
        logger.info(f"Created scene: {scene_name}")

    async def delete_scene(self, scene_name: str) -> None:
        """Delete a scene.

        Args:
            scene_name: Scene to delete
        """
        self._ensure_connected()
        self._client.remove_scene(scene_name)
        logger.info(f"Deleted scene: {scene_name}")

    # =========================================================================
    # SOURCE MANAGEMENT
    # =========================================================================

    async def get_sources(self, scene_name: str | None = None) -> list[dict]:
        """Get sources in a scene.

        Args:
            scene_name: Scene name (current scene if None)

        Returns:
            List of source info dicts
        """
        self._ensure_connected()

        if scene_name is None:
            scene_name = await self.get_current_scene()

        result = self._client.get_scene_item_list(scene_name)
        return [
            {
                "sceneItemId": item.get("sceneItemId"),
                "sourceName": item.get("sourceName"),
                "sourceType": item.get("sourceType"),
                "sceneItemEnabled": item.get("sceneItemEnabled"),
            }
            for item in result.scene_items
        ]

    async def add_source(
        self,
        source_name: str,
        source_kind: str,
        settings: dict | None = None,
        scene_name: str | None = None,
    ) -> int:
        """Add a source to a scene.

        Args:
            source_name: Name for the source
            source_kind: Source type (browser_source, vlc_source, etc.)
            settings: Source-specific settings
            scene_name: Target scene (current if None)

        Returns:
            Scene item ID
        """
        self._ensure_connected()

        if scene_name is None:
            scene_name = await self.get_current_scene()

        # Create input
        result = self._client.create_input(
            scene_name=scene_name,
            input_name=source_name,
            input_kind=source_kind,
            input_settings=settings or {},
            scene_item_enabled=True,
        )

        logger.info(f"Added source '{source_name}' ({source_kind}) to '{scene_name}'")
        return result.scene_item_id

    async def remove_source(self, source_name: str, scene_name: str | None = None) -> None:
        """Remove a source from a scene.

        Args:
            source_name: Source to remove
            scene_name: Scene to remove from (current if None)
        """
        self._ensure_connected()

        if scene_name is None:
            scene_name = await self.get_current_scene()

        # Get scene item ID
        sources = await self.get_sources(scene_name)
        item_id = None
        for source in sources:
            if source["sourceName"] == source_name:
                item_id = source["sceneItemId"]
                break

        if item_id:
            self._client.remove_scene_item(scene_name, item_id)
            logger.info(f"Removed source '{source_name}' from '{scene_name}'")

    async def set_source_visible(
        self,
        source_name: str,
        visible: bool,
        scene_name: str | None = None,
    ) -> None:
        """Set source visibility.

        Args:
            source_name: Source name
            visible: Whether visible
            scene_name: Scene (current if None)
        """
        self._ensure_connected()

        if scene_name is None:
            scene_name = await self.get_current_scene()

        sources = await self.get_sources(scene_name)
        for source in sources:
            if source["sourceName"] == source_name:
                self._client.set_scene_item_enabled(scene_name, source["sceneItemId"], visible)
                return

    async def set_source_transform(
        self,
        source_name: str,
        scene_name: str | None = None,
        position: tuple[float, float] | None = None,
        scale: tuple[float, float] | None = None,
        rotation: float | None = None,
        crop: dict | None = None,
    ) -> None:
        """Set source transform properties.

        Args:
            source_name: Source name
            scene_name: Scene (current if None)
            position: (x, y) position
            scale: (x, y) scale factors
            rotation: Rotation in degrees
            crop: Crop dict with 'top', 'bottom', 'left', 'right'
        """
        self._ensure_connected()

        if scene_name is None:
            scene_name = await self.get_current_scene()

        sources = await self.get_sources(scene_name)
        item_id = None
        for source in sources:
            if source["sourceName"] == source_name:
                item_id = source["sceneItemId"]
                break

        if not item_id:
            return

        transform = {}
        if position:
            transform["positionX"] = position[0]
            transform["positionY"] = position[1]
        if scale:
            transform["scaleX"] = scale[0]
            transform["scaleY"] = scale[1]
        if rotation is not None:
            transform["rotation"] = rotation
        if crop:
            transform.update(
                {
                    "cropTop": crop.get("top", 0),
                    "cropBottom": crop.get("bottom", 0),
                    "cropLeft": crop.get("left", 0),
                    "cropRight": crop.get("right", 0),
                }
            )

        if transform:
            self._client.set_scene_item_transform(scene_name, item_id, transform)

    # =========================================================================
    # FILTER MANAGEMENT
    # =========================================================================

    async def add_filter(
        self,
        source_name: str,
        filter_name: str,
        filter_kind: str,
        settings: dict | None = None,
    ) -> None:
        """Add a filter to a source.

        Args:
            source_name: Source to add filter to
            filter_name: Name for the filter
            filter_kind: Filter type (chroma_key_filter_v2, etc.)
            settings: Filter settings
        """
        self._ensure_connected()
        self._client.create_source_filter(
            source_name=source_name,
            filter_name=filter_name,
            filter_kind=filter_kind,
            filter_settings=settings or {},
        )
        logger.info(f"Added filter '{filter_name}' to '{source_name}'")

    async def remove_filter(self, source_name: str, filter_name: str) -> None:
        """Remove a filter from a source."""
        self._ensure_connected()
        self._client.remove_source_filter(source_name, filter_name)

    async def set_filter_enabled(self, source_name: str, filter_name: str, enabled: bool) -> None:
        """Enable/disable a filter."""
        self._ensure_connected()
        self._client.set_source_filter_enabled(source_name, filter_name, enabled)

    async def set_filter_settings(self, source_name: str, filter_name: str, settings: dict) -> None:
        """Update filter settings."""
        self._ensure_connected()
        self._client.set_source_filter_settings(source_name, filter_name, settings)

    # =========================================================================
    # STREAMING & RECORDING
    # =========================================================================

    async def start_streaming(self) -> None:
        """Start streaming."""
        self._ensure_connected()
        self._client.start_stream()
        logger.info("Streaming started")

    async def stop_streaming(self) -> None:
        """Stop streaming."""
        self._ensure_connected()
        self._client.stop_stream()
        logger.info("Streaming stopped")

    async def toggle_streaming(self) -> bool:
        """Toggle streaming state.

        Returns:
            New streaming state (True = streaming)
        """
        self._ensure_connected()
        result = self._client.toggle_stream()
        return result.output_active

    async def get_stream_status(self) -> dict:
        """Get streaming status."""
        self._ensure_connected()
        result = self._client.get_stream_status()
        return {
            "active": result.output_active,
            "reconnecting": result.output_reconnecting,
            "timecode": result.output_timecode,
            "duration": result.output_duration,
            "bytes": result.output_bytes,
        }

    async def start_recording(self) -> None:
        """Start recording."""
        self._ensure_connected()
        self._client.start_record()
        logger.info("Recording started")

    async def stop_recording(self) -> str:
        """Stop recording.

        Returns:
            Path to recorded file
        """
        self._ensure_connected()
        result = self._client.stop_record()
        logger.info(f"Recording stopped: {result.output_path}")
        return result.output_path

    async def toggle_recording(self) -> None:
        """Toggle recording state."""
        self._ensure_connected()
        self._client.toggle_record()

    async def pause_recording(self) -> None:
        """Pause recording."""
        self._ensure_connected()
        self._client.pause_record()

    async def resume_recording(self) -> None:
        """Resume recording."""
        self._ensure_connected()
        self._client.resume_record()

    async def get_record_status(self) -> dict:
        """Get recording status."""
        self._ensure_connected()
        result = self._client.get_record_status()
        return {
            "active": result.output_active,
            "paused": result.output_paused,
            "timecode": result.output_timecode,
            "duration": result.output_duration,
            "bytes": result.output_bytes,
        }

    # =========================================================================
    # VIRTUAL CAMERA
    # =========================================================================

    async def start_virtual_camera(self) -> None:
        """Start virtual camera output."""
        self._ensure_connected()
        self._client.start_virtual_cam()
        logger.info("Virtual camera started")

    async def stop_virtual_camera(self) -> None:
        """Stop virtual camera."""
        self._ensure_connected()
        self._client.stop_virtual_cam()
        logger.info("Virtual camera stopped")

    async def toggle_virtual_camera(self) -> bool:
        """Toggle virtual camera.

        Returns:
            New state (True = active)
        """
        self._ensure_connected()
        result = self._client.toggle_virtual_cam()
        return result.output_active

    # =========================================================================
    # AUDIO
    # =========================================================================

    async def set_input_mute(self, input_name: str, muted: bool) -> None:
        """Mute/unmute an input."""
        self._ensure_connected()
        self._client.set_input_mute(input_name, muted)

    async def toggle_input_mute(self, input_name: str) -> bool:
        """Toggle input mute state.

        Returns:
            New mute state
        """
        self._ensure_connected()
        result = self._client.toggle_input_mute(input_name)
        return result.input_muted

    async def set_input_volume(
        self, input_name: str, volume_db: float | None = None, volume_mul: float | None = None
    ) -> None:
        """Set input volume.

        Args:
            input_name: Input name
            volume_db: Volume in dB (use one or the other)
            volume_mul: Volume multiplier (0.0-1.0)
        """
        self._ensure_connected()
        self._client.set_input_volume(
            input_name,
            input_volume_db=volume_db,
            input_volume_mul=volume_mul,
        )

    # =========================================================================
    # SCREENSHOTS
    # =========================================================================

    async def screenshot(
        self,
        source_name: str | None = None,
        format: str = "png",
        width: int | None = None,
        height: int | None = None,
    ) -> str:
        """Take a screenshot.

        Args:
            source_name: Source to screenshot (current output if None)
            format: Image format (png, jpg, bmp)
            width: Output width
            height: Output height

        Returns:
            Base64-encoded image data
        """
        self._ensure_connected()

        if source_name:
            result = self._client.get_source_screenshot(
                source_name,
                format,
                width=width or 1920,
                height=height or 1080,
            )
        else:
            # Screenshot current output
            scene = await self.get_current_scene()
            result = self._client.get_source_screenshot(
                scene,
                format,
                width=width or 1920,
                height=height or 1080,
            )

        return result.image_data

    # =========================================================================
    # TRANSITIONS
    # =========================================================================

    async def get_transitions(self) -> list[str]:
        """Get available transitions."""
        self._ensure_connected()
        result = self._client.get_scene_transition_list()
        return [t.get("transitionName") for t in result.transitions]

    async def get_current_transition(self) -> dict:
        """Get current transition info."""
        self._ensure_connected()
        result = self._client.get_current_scene_transition()
        return {
            "name": result.transition_name,
            "kind": result.transition_kind,
            "duration": result.transition_duration,
        }

    async def set_transition(self, name: str, duration: int | None = None) -> None:
        """Set current transition.

        Args:
            name: Transition name
            duration: Duration in ms
        """
        self._ensure_connected()
        self._client.set_current_scene_transition(name)
        if duration:
            self._client.set_current_scene_transition_duration(duration)

    async def trigger_transition(self) -> None:
        """Trigger the current transition."""
        self._ensure_connected()
        self._client.trigger_studio_mode_transition()


@asynccontextmanager
async def connect_obs(
    config: OBSConfig | None = None,
) -> AsyncIterator[OBSController]:
    """Context manager for OBS connection.

    Usage:
        async with connect_obs() as obs:
            await obs.switch_scene("Main")

    Args:
        config: Connection config

    Yields:
        Connected OBSController
    """
    controller = OBSController(config)
    connected = await controller.connect()

    if not connected:
        raise RuntimeError("Failed to connect to OBS")

    try:
        yield controller
    finally:
        await controller.disconnect()
