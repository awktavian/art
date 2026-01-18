"""OBS Bridge — Connect Kagami Studio to OBS.

Bridges the Kagami Studio production system to OBS Studio,
enabling real-time output from AI-generated content to OBS.

Features:
- Automatic scene/source creation from Studio
- Real-time avatar/video streaming to OBS
- Synchronized transitions and overlays
- Two-way event handling

Usage:
    from kagami_studio import Studio
    from kagami_studio.obs import OBSBridge

    async with Studio() as studio:
        # Create bridge to OBS
        bridge = OBSBridge(studio)
        await bridge.connect()

        # Now studio output goes to OBS
        await studio.generate_and_speak("Welcome!")

        # Bridge handles:
        # - Creating OBS sources for Studio sources
        # - Routing frames to virtual camera
        # - Triggering transitions on scene changes
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_studio.engine import StudioEngine

from kagami_studio.obs.client import OBSConfig, OBSController

logger = logging.getLogger(__name__)


class BridgeMode(str, Enum):
    """Bridge operation mode."""

    # One-way: Studio → OBS
    PUSH = "push"

    # Two-way: Studio ↔ OBS
    SYNC = "sync"

    # OBS controls Studio
    PULL = "pull"


@dataclass
class BridgeConfig:
    """Bridge configuration."""

    mode: BridgeMode = BridgeMode.PUSH

    # Auto-create OBS scenes from Studio
    auto_create_scenes: bool = True

    # Auto-create OBS sources from Studio
    auto_create_sources: bool = True

    # Use virtual camera for output
    use_virtual_camera: bool = True

    # Scene prefix in OBS
    scene_prefix: str = "Kagami_"

    # Source prefix in OBS
    source_prefix: str = "kagami_"

    # Browser source settings for HTML overlays
    browser_port: int = 8765
    browser_width: int = 1920
    browser_height: int = 1080


class OBSBridge:
    """Bridge between Kagami Studio and OBS Studio.

    Handles synchronization between Studio's production system
    and OBS Studio's scene composition.

    Example:
        async with Studio() as studio:
            bridge = OBSBridge(studio)
            await bridge.connect()

            # Create scene in Studio - auto-creates in OBS
            studio.create_scene("Main")

            # Add avatar source - auto-creates in OBS
            await studio.add_avatar_source("kagami")

            # Speech routes through to OBS output
            await studio.generate_and_speak("Hello!")
    """

    def __init__(
        self,
        studio: StudioEngine,
        obs_config: OBSConfig | None = None,
        bridge_config: BridgeConfig | None = None,
    ):
        """Initialize bridge.

        Args:
            studio: Kagami Studio engine instance
            obs_config: OBS connection config
            bridge_config: Bridge behavior config
        """
        self.studio = studio
        self.obs = OBSController(obs_config)
        self.config = bridge_config or BridgeConfig()

        self._connected = False
        self._source_mapping: dict[str, str] = {}  # Studio ID → OBS name
        self._scene_mapping: dict[str, str] = {}  # Studio name → OBS name
        self._sync_task: asyncio.Task | None = None

    async def connect(self) -> bool:
        """Connect bridge to OBS.

        Returns:
            True if connected successfully
        """
        connected = await self.obs.connect()
        if not connected:
            return False

        self._connected = True

        # Set up event handlers
        self._setup_event_handlers()

        # Initial sync
        if self.config.mode in (BridgeMode.PUSH, BridgeMode.SYNC):
            await self._sync_studio_to_obs()

        if self.config.mode in (BridgeMode.PULL, BridgeMode.SYNC):
            await self._sync_obs_to_studio()

        # Start virtual camera if configured
        if self.config.use_virtual_camera:
            try:
                await self.obs.start_virtual_camera()
            except Exception as e:
                logger.warning(f"Could not start virtual camera: {e}")

        logger.info(f"OBS Bridge connected in {self.config.mode.value} mode")
        return True

    async def disconnect(self) -> None:
        """Disconnect bridge."""
        if self._sync_task:
            self._sync_task.cancel()
            self._sync_task = None

        if self.config.use_virtual_camera:
            try:
                await self.obs.stop_virtual_camera()
            except Exception:
                pass

        await self.obs.disconnect()
        self._connected = False
        logger.info("OBS Bridge disconnected")

    def _setup_event_handlers(self) -> None:
        """Set up event handlers for two-way sync."""
        if self.config.mode in (BridgeMode.PULL, BridgeMode.SYNC):
            self.obs.on_event("scene_changed", self._on_obs_scene_changed)
            self.obs.on_event("source_created", self._on_obs_source_created)

    def _on_obs_scene_changed(self, data: Any) -> None:
        """Handle OBS scene change - sync to Studio."""
        if self.config.mode not in (BridgeMode.PULL, BridgeMode.SYNC):
            return

        scene_name = data.get("sceneName", "")

        # Check if this is a Kagami scene
        if scene_name.startswith(self.config.scene_prefix):
            studio_name = scene_name[len(self.config.scene_prefix) :]
            # Update Studio's active scene (if it exists)
            # This requires Studio API support
            logger.debug(f"OBS switched to scene: {studio_name}")

    def _on_obs_source_created(self, data: Any) -> None:
        """Handle OBS source creation."""
        source_name = data.get("inputName", "")
        logger.debug(f"OBS source created: {source_name}")

    async def _sync_studio_to_obs(self) -> None:
        """Sync Studio state to OBS."""
        if not self.config.auto_create_scenes:
            return

        # Get Studio scenes
        scenes = self.studio.list_scenes()

        for scene_name in scenes:
            obs_name = f"{self.config.scene_prefix}{scene_name}"

            # Check if scene exists in OBS
            obs_scenes = await self.obs.get_scenes()
            exists = any(s.get("sceneName") == obs_name for s in obs_scenes)

            if not exists:
                await self.obs.create_scene(obs_name)
                logger.info(f"Created OBS scene: {obs_name}")

            self._scene_mapping[scene_name] = obs_name

    async def _sync_obs_to_studio(self) -> None:
        """Sync OBS state to Studio."""
        # Get OBS scenes with Kagami prefix
        obs_scenes = await self.obs.get_scenes()

        for scene_info in obs_scenes:
            scene_name = scene_info.get("sceneName", "")
            if scene_name.startswith(self.config.scene_prefix):
                studio_name = scene_name[len(self.config.scene_prefix) :]
                self._scene_mapping[studio_name] = scene_name

    # =========================================================================
    # SCENE MANAGEMENT
    # =========================================================================

    async def create_scene(self, name: str) -> str:
        """Create scene in both Studio and OBS.

        Args:
            name: Scene name

        Returns:
            OBS scene name
        """
        # Create in Studio
        self.studio.create_scene(name)

        # Create in OBS
        obs_name = f"{self.config.scene_prefix}{name}"
        await self.obs.create_scene(obs_name)

        self._scene_mapping[name] = obs_name
        return obs_name

    async def switch_scene(
        self,
        name: str,
        transition: str | None = None,
        duration: int | None = None,
    ) -> None:
        """Switch scene in both Studio and OBS.

        Args:
            name: Scene name
            transition: Transition type
            duration: Transition duration in ms
        """
        # Switch in Studio
        await self.studio.switch_scene(name, transition or "cut", (duration or 0) / 1000)

        # Switch in OBS
        obs_name = self._scene_mapping.get(name, f"{self.config.scene_prefix}{name}")
        await self.obs.switch_scene(obs_name, transition, duration)

    async def delete_scene(self, name: str) -> None:
        """Delete scene from both Studio and OBS."""
        # Delete from OBS
        obs_name = self._scene_mapping.get(name)
        if obs_name:
            await self.obs.delete_scene(obs_name)
            del self._scene_mapping[name]

    # =========================================================================
    # SOURCE MANAGEMENT
    # =========================================================================

    async def add_browser_source(
        self,
        name: str,
        url: str,
        scene: str | None = None,
        position: tuple[float, float] = (0, 0),
        scale: tuple[float, float] = (1.0, 1.0),
    ) -> str:
        """Add browser source to OBS.

        Browser sources are perfect for:
        - Overlays generated by Kagami
        - Dynamic HTML content
        - Real-time data displays

        Args:
            name: Source name
            url: URL to display
            scene: Target scene (current if None)
            position: (x, y) position
            scale: (x, y) scale

        Returns:
            OBS source name
        """
        from kagami_studio.obs.sources import create_browser_source

        obs_name = f"{self.config.source_prefix}{name}"
        obs_scene = self._get_obs_scene(scene)

        settings = create_browser_source(
            url=url,
            width=self.config.browser_width,
            height=self.config.browser_height,
        )

        await self.obs.add_source(obs_name, "browser_source", settings, obs_scene)

        if position != (0, 0) or scale != (1.0, 1.0):
            await self.obs.set_source_transform(
                obs_name,
                scene_name=obs_scene,
                position=position,
                scale=scale,
            )

        self._source_mapping[name] = obs_name
        return obs_name

    async def add_avatar_source(
        self,
        avatar_id: str,
        scene: str | None = None,
        position: tuple[float, float] = (0, 0),
        scale: tuple[float, float] = (1.0, 1.0),
    ) -> str:
        """Add Kagami avatar as browser source.

        Creates a browser source pointing to the avatar stream.

        Args:
            avatar_id: Avatar identifier
            scene: Target scene
            position: Position
            scale: Scale

        Returns:
            OBS source name
        """
        # Avatar is served as HTML via local server
        avatar_url = f"http://localhost:{self.config.browser_port}/avatar/{avatar_id}"

        return await self.add_browser_source(
            name=f"avatar_{avatar_id}",
            url=avatar_url,
            scene=scene,
            position=position,
            scale=scale,
        )

    async def add_video_source(
        self,
        name: str,
        path: str,
        scene: str | None = None,
        loop: bool = True,
    ) -> str:
        """Add video file source to OBS.

        Args:
            name: Source name
            path: Path to video file
            scene: Target scene
            loop: Whether to loop

        Returns:
            OBS source name
        """
        from kagami_studio.obs.sources import create_video_source

        obs_name = f"{self.config.source_prefix}{name}"
        obs_scene = self._get_obs_scene(scene)

        settings = create_video_source(path, loop=loop)
        await self.obs.add_source(obs_name, "ffmpeg_source", settings, obs_scene)

        self._source_mapping[name] = obs_name
        return obs_name

    async def add_overlay_source(
        self,
        name: str,
        overlay_html: str,
        scene: str | None = None,
    ) -> str:
        """Add HTML overlay source.

        For custom HTML content like lower thirds, alerts, etc.

        Args:
            name: Source name
            overlay_html: HTML content or file path
            scene: Target scene

        Returns:
            OBS source name
        """
        # If it's a file path, use file:// URL
        if overlay_html.endswith(".html"):
            url = f"file://{overlay_html}"
        else:
            # Save HTML to temp file and serve
            import tempfile
            from pathlib import Path

            temp_dir = Path(tempfile.gettempdir()) / "kagami_overlays"
            temp_dir.mkdir(exist_ok=True)

            html_file = temp_dir / f"{name}.html"
            html_file.write_text(overlay_html)
            url = f"file://{html_file}"

        return await self.add_browser_source(name, url, scene)

    async def remove_source(self, name: str, scene: str | None = None) -> None:
        """Remove source from OBS.

        Args:
            name: Source name
            scene: Scene (current if None)
        """
        obs_name = self._source_mapping.get(name)
        if obs_name:
            await self.obs.remove_source(obs_name, self._get_obs_scene(scene))
            del self._source_mapping[name]

    async def set_source_visible(
        self,
        name: str,
        visible: bool,
        scene: str | None = None,
    ) -> None:
        """Set source visibility.

        Args:
            name: Source name
            visible: Whether visible
            scene: Scene (current if None)
        """
        obs_name = self._source_mapping.get(name)
        if obs_name:
            await self.obs.set_source_visible(obs_name, visible, self._get_obs_scene(scene))

    def _get_obs_scene(self, scene: str | None) -> str | None:
        """Get OBS scene name from Studio scene name."""
        if scene is None:
            return None
        return self._scene_mapping.get(scene, f"{self.config.scene_prefix}{scene}")

    # =========================================================================
    # STREAMING & RECORDING
    # =========================================================================

    async def start_streaming(self) -> None:
        """Start OBS streaming."""
        await self.obs.start_streaming()

    async def stop_streaming(self) -> None:
        """Stop OBS streaming."""
        await self.obs.stop_streaming()

    async def start_recording(self) -> None:
        """Start OBS recording."""
        await self.obs.start_recording()

    async def stop_recording(self) -> str:
        """Stop OBS recording.

        Returns:
            Path to recorded file
        """
        return await self.obs.stop_recording()

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    async def setup_kagami_scene(
        self,
        name: str = "Kagami Live",
        background: str | None = None,
        avatar: str = "kagami",
    ) -> str:
        """Set up a complete Kagami scene.

        Creates scene with:
        - Background (image/video)
        - Kagami avatar
        - Overlay layer

        Args:
            name: Scene name
            background: Background image/video path
            avatar: Avatar ID

        Returns:
            OBS scene name
        """
        obs_scene = await self.create_scene(name)

        # Add background if provided
        if background:
            await self.add_video_source(
                "background",
                background,
                scene=name,
                loop=True,
            )

        # Add avatar
        await self.add_avatar_source(
            avatar,
            scene=name,
            position=(100, 100),
            scale=(0.8, 0.8),
        )

        # Add overlay layer (for dynamic content)
        await self.add_browser_source(
            "overlay",
            f"http://localhost:{self.config.browser_port}/overlay",
            scene=name,
        )

        return obs_scene

    async def setup_documentary_scene(
        self,
        name: str = "Documentary",
        video_source: str | None = None,
        text_overlay: bool = True,
    ) -> str:
        """Set up DCC-style documentary scene.

        Creates scene optimized for documentary content:
        - Video panel (left)
        - Text overlay (right)
        - Word-by-word reveal

        Args:
            name: Scene name
            video_source: Video file path
            text_overlay: Enable text overlay

        Returns:
            OBS scene name
        """
        obs_scene = await self.create_scene(name)

        # Video on left
        if video_source:
            await self.add_video_source(
                "documentary_video",
                video_source,
                scene=name,
            )
            await self.obs.set_source_transform(
                f"{self.config.source_prefix}documentary_video",
                scene_name=obs_scene,
                scale=(0.6, 1.0),  # 60% of width
                position=(0, 0),
            )

        # Text overlay on right
        if text_overlay:
            await self.add_browser_source(
                "documentary_text",
                f"http://localhost:{self.config.browser_port}/documentary/text",
                scene=name,
                position=(1152, 0),  # Right side
                scale=(0.4, 1.0),
            )

        return obs_scene

    async def __aenter__(self) -> OBSBridge:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        await self.disconnect()
