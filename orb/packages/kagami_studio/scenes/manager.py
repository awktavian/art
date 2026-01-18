"""Scene Manager — Manages scenes and transitions."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import numpy as np

from kagami_studio.scenes.scene import Scene

logger = logging.getLogger(__name__)


class SceneManager:
    """Manages all scenes and transitions."""

    def __init__(self, config: Any):
        self.config = config
        self._scenes: dict[str, Scene] = {}
        self._active_scene: str | None = None
        self._preview_scene: str | None = None
        self._transitioning = False
        self._transition_progress = 0.0
        self._source_manager: Any = None

    async def initialize(self) -> None:
        """Initialize the scene manager."""
        logger.info("SceneManager initialized")

    def set_source_manager(self, source_manager: Any) -> None:
        """Set the source manager reference."""
        self._source_manager = source_manager

    def create_scene(
        self,
        name: str,
        copy_from: str | None = None,
    ) -> Scene:
        """Create a new scene.

        Args:
            name: Scene name
            copy_from: Scene to copy from

        Returns:
            New Scene
        """
        if copy_from and copy_from in self._scenes:
            # Copy from existing scene
            base = self._scenes[copy_from]
            scene = Scene(
                name=name,
                width=base.width,
                height=base.height,
                background_color=base.background_color,
                items=base.items.copy(),
            )
        else:
            scene = Scene(
                name=name,
                width=self.config.resolution[0],
                height=self.config.resolution[1],
            )

        self._scenes[name] = scene

        # Set as active if first scene
        if self._active_scene is None:
            self._active_scene = name

        logger.info(f"Created scene: {name}")
        return scene

    def get_scene(self, name: str) -> Scene:
        """Get a scene by name."""
        if name not in self._scenes:
            raise KeyError(f"Scene not found: {name}")
        return self._scenes[name]

    def delete_scene(self, name: str) -> None:
        """Delete a scene."""
        if name in self._scenes:
            del self._scenes[name]
            if self._active_scene == name:
                self._active_scene = next(iter(self._scenes), None)

    def list_scenes(self) -> list[str]:
        """List all scene names."""
        return list(self._scenes.keys())

    async def switch_scene(
        self,
        name: str,
        transition: str = "cut",
        duration: float = 0.5,
    ) -> None:
        """Switch to a scene with transition.

        Args:
            name: Target scene name
            transition: Transition type (cut, fade, dissolve, wipe, zoom)
            duration: Transition duration in seconds
        """
        if name not in self._scenes:
            raise KeyError(f"Scene not found: {name}")

        if name == self._active_scene:
            return  # Already on this scene

        if transition == "cut":
            # Instant switch
            self._active_scene = name
        else:
            # Animated transition
            self._transitioning = True

            fps = self.config.fps
            frames = int(duration * fps)

            for i in range(frames):
                self._transition_progress = i / frames
                await asyncio.sleep(1 / fps)

            self._active_scene = name
            self._transitioning = False
            self._transition_progress = 0.0

        logger.info(f"Switched to scene: {name}")

    async def render_frame(self) -> np.ndarray:
        """Render the current frame.

        Handles transitions by blending between scenes.

        Returns:
            Rendered frame
        """
        if not self._active_scene or self._active_scene not in self._scenes:
            # Return black frame
            return np.zeros(
                (self.config.resolution[1], self.config.resolution[0], 3),
                dtype=np.uint8,
            )

        scene = self._scenes[self._active_scene]

        if self._source_manager:
            return await scene.render(self._source_manager)
        else:
            # Return scene background
            return np.full(
                (scene.height, scene.width, 3),
                scene.background_color,
                dtype=np.uint8,
            )

    def set_preview(self, name: str | None) -> None:
        """Set the preview scene (Studio Mode)."""
        if name is not None and name not in self._scenes:
            raise KeyError(f"Scene not found: {name}")
        self._preview_scene = name

    async def render_preview(self) -> np.ndarray | None:
        """Render the preview scene."""
        if not self._preview_scene:
            return None

        scene = self._scenes.get(self._preview_scene)
        if not scene:
            return None

        if self._source_manager:
            return await scene.render(self._source_manager)
        return None
