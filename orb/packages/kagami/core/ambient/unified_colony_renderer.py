"""
Unified Colony Renderer — Single Source of Truth for Colony Visualization.

Consolidates functionality from:
- AmbientDisplay colony rendering (simple orbit visualization)
- ColonyHALBridge catastrophe dynamics
- ColonyRenderer core rendering logic

Provides unified colony visualization for:
- Ambient OS displays
- AR systems
- Web clients via HAL streaming

Design Principles:
- Single colony rendering pipeline
- Catastrophe-driven dynamics
- HAL display integration
- Event-driven updates

Created: December 14, 2025
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from kagami.core.ambient.data_types import (
    BreathPhase,
    Colony,
    ColonyState,
    PresenceState,
)
from kagami.core.events import get_unified_bus

logger = logging.getLogger(__name__)


@dataclass
class ColonyRenderConfig:
    """Configuration for colony rendering."""

    width: int = 800
    height: int = 480
    fps: int = 30

    # Colony visualization
    show_colonies: bool = True
    show_breath_ring: bool = True
    show_safety_aura: bool = True
    show_catastrophe_viz: bool = True

    # Positioning
    colony_orbit_radius: float = 0.35
    breath_ring_radius: float = 0.25
    background_color: tuple[int, int, int] = (10, 10, 15)

    # Ambient integration
    enable_ambient_mode: bool = True  # Simple orbit when True, full catastrophe when False
    ambient_orbit_radius: float = 0.2

    # HAL integration
    emit_to_hal: bool = True
    emit_to_agui: bool = True


@dataclass
class RenderFrame:
    """A complete render frame with all colony states."""

    timestamp: float
    colonies: dict[Colony, ColonyState]
    breath_phase: BreathPhase = BreathPhase.REST
    breath_progress: float = 0.0
    safety_h: float = 1.0
    presence: PresenceState | None = None
    frame_number: int = 0

    # Rendered buffer
    buffer: np.ndarray[Any, Any] | None = None
    buffer_format: str = "rgba32"


class UnifiedColonyRenderer:
    """
    Single unified renderer for colony visualizations.

    Consolidates:
    - AmbientDisplay simple orbit rendering
    - ColonyHALBridge catastrophe dynamics
    - ColonyRenderer core logic

    Usage:
        renderer = UnifiedColonyRenderer()
        await renderer.initialize()

        # Render frame
        frame = await renderer.render_frame()
        # frame.buffer contains RGBA data
        # frame.colonies contains state

        await renderer.stream_to_hal(frame)
    """

    def __init__(self, config: ColonyRenderConfig | None = None):
        self.config = config or ColonyRenderConfig()

        # Frame buffer (RGBA)
        self._buffer: np.ndarray[Any, Any] = np.zeros(
            (self.config.height, self.config.width, 4), dtype=np.uint8
        )

        # State
        self._time = 0.0
        self._frame_count = 0
        self._last_fps_time = time.time()
        self._fps = 0.0

        # Current states
        self._colonies: dict[Colony, ColonyState] = {}
        self._breath_phase = BreathPhase.REST
        self._breath_progress = 0.0
        self._safety_h = 1.0
        self._presence: PresenceState | None = None

        # Event bus for HAL streaming
        self._bus = get_unified_bus()

        # Control
        self._running = False
        self._render_task: asyncio.Task | None = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the renderer."""
        logger.info("🎨 Initializing Unified Colony Renderer")

        # Emit init event
        if self.config.emit_to_agui:
            await self._bus.publish(
                "colony.renderer.init",
                {
                    "type": "colony.renderer.init",
                    "width": self.config.width,
                    "height": self.config.height,
                    "mode": "ambient" if self.config.enable_ambient_mode else "catastrophe",
                    "has_hal": self.config.emit_to_hal,
                },
            )

        self._initialized = True
        logger.info(
            f"✅ Unified Colony Renderer initialized ({self.config.width}x{self.config.height})"
        )
        return True

    async def start(self) -> None:
        """Start the renderer."""
        if self._running:
            return
        self._running = True
        logger.info("▶️ Unified Colony Renderer started")

    async def stop(self) -> None:
        """Stop the renderer."""
        self._running = False
        if self._render_task:
            self._render_task.cancel()
            try:
                await self._render_task
            except asyncio.CancelledError:
                pass
        logger.info("⏹️ Unified Colony Renderer stopped")

    def update_colonies(self, colonies: dict[Colony, ColonyState]) -> None:
        """Update colony states."""
        self._colonies = colonies

    def update_breath(self, phase: BreathPhase, progress: float) -> None:
        """Update breath state."""
        self._breath_phase = phase
        self._breath_progress = progress

    def update_safety(self, safety_h: float) -> None:
        """Update safety barrier value."""
        self._safety_h = safety_h

    def update_presence(self, presence: PresenceState) -> None:
        """Update presence state."""
        self._presence = presence

    async def render_frame(self) -> RenderFrame:
        """Render a complete frame.

        Uses asyncio.to_thread to offload CPU-intensive rendering and prevent
        event loop blocking.
        """
        # Offload CPU-intensive rendering to thread pool
        frame = await asyncio.to_thread(self._render_frame_sync)
        return frame

    def _render_frame_sync(self) -> RenderFrame:
        """Synchronous frame rendering (called from thread pool)."""
        # Clear buffer
        self._clear_buffer()

        # Render layers based on mode
        if self.config.enable_ambient_mode:
            self._render_ambient_colonies()
        else:
            self._render_catastrophe_colonies()

        if self.config.show_breath_ring:
            self._render_breath_ring()

        if self.config.show_safety_aura:
            self._render_safety_aura()

        # Update stats
        self._frame_count += 1
        self._time += 1.0 / self.config.fps
        self._update_fps()

        # Create frame
        frame = RenderFrame(
            timestamp=time.time(),
            colonies=self._colonies.copy(),
            breath_phase=self._breath_phase,
            breath_progress=self._breath_progress,
            safety_h=self._safety_h,
            presence=self._presence,
            frame_number=self._frame_count,
            buffer=self._buffer.copy(),
            buffer_format="rgba32",
        )

        return frame

    async def stream_to_hal(self, frame: RenderFrame) -> None:
        """Stream frame to HAL display and AGUI."""
        if not self.config.emit_to_hal:
            return

        # Write to HAL display
        try:
            from kagami_hal import get_hal_manager

            hal = await get_hal_manager()
            if hal.display:
                # Convert to bytes
                buffer_bytes = frame.buffer.tobytes()  # type: ignore[union-attr]
                await hal.display.write_frame(buffer_bytes)
        except Exception as e:
            logger.debug(f"HAL write failed: {e}")

        # Emit to AGUI
        if self.config.emit_to_agui:
            try:
                # Encode for transport
                import base64

                encoded = base64.b64encode(frame.buffer.tobytes()).decode("utf-8")  # type: ignore[union-attr]

                await self._bus.publish(
                    "colony.renderer.frame",
                    {
                        "type": "colony.renderer.frame",
                        "buffer": encoded,
                        "format": frame.buffer_format,
                        "width": self.config.width,
                        "height": self.config.height,
                        "frame_number": frame.frame_number,
                        "breath_phase": frame.breath_phase.value,
                        "breath_progress": frame.breath_progress,
                        "safety_h": frame.safety_h,
                        "fps": self._fps,
                        "colonies": {
                            colony.value: {
                                "activation": state.activation,
                                "potential": getattr(state, "potential", 0.0),
                                "speaking": getattr(state, "is_speaking", False),
                            }
                            for colony, state in frame.colonies.items()
                        },
                    },
                )
            except Exception as e:
                logger.debug(f"AGUI emit failed: {e}")

    def _clear_buffer(self) -> None:
        """Clear frame buffer."""
        bg = self.config.background_color
        self._buffer[:, :, 0] = bg[0]
        self._buffer[:, :, 1] = bg[1]
        self._buffer[:, :, 2] = bg[2]
        self._buffer[:, :, 3] = 255

    def _render_ambient_colonies(self) -> None:
        """Render colonies in ambient mode (simple orbit)."""
        # Simplified version from AmbientDisplay
        cx, cy = self.config.width // 2, self.config.height // 2
        orbit_radius = int(self.config.width * self.config.ambient_orbit_radius)

        # Get accent color (dominant colony)
        accent_rgb = self._get_dominant_colony_color()

        for i, (_colony, state) in enumerate(self._colonies.items()):
            # Position on orbit
            angle = i * 2 * math.pi / len(self._colonies) + self._time * 0.1
            x = int(cx + orbit_radius * math.cos(angle))
            y = int(cy + orbit_radius * math.sin(angle))

            # Size based on activation
            size = int(8 + 16 * state.activation)

            # Color based on activation
            if state.activation > 0.3:
                color = accent_rgb
            else:
                color = (100, 100, 120)  # Neutral

            # Draw
            self._draw_filled_circle(x, y, size, color)

    def _render_catastrophe_colonies(self) -> None:
        """Render colonies with catastrophe dynamics."""
        cx, cy = self.config.width // 2, self.config.height // 2
        orbit_radius = int(self.config.width * self.config.colony_orbit_radius)

        for i, (colony, state) in enumerate(self._colonies.items()):
            # Position on orbit with catastrophe influence
            base_angle = i * 2 * math.pi / len(self._colonies)
            catastrophe_offset = self._get_catastrophe_offset(colony, state)
            angle = base_angle + catastrophe_offset + self._time * 0.15

            x = int(cx + orbit_radius * math.cos(angle))
            y = int(cy + orbit_radius * math.sin(angle))

            # Size with catastrophe modulation
            base_size = 8
            catastrophe_size = self._get_catastrophe_size(colony, state)
            size = int(base_size + catastrophe_size * state.activation)

            # Color from colony definition
            color = self._get_colony_color(colony)

            # Draw with glow if active
            self._draw_filled_circle(x, y, size, color)
            if state.activation > 0.5:
                glow_size = int(size * 1.5)
                glow_color = tuple(int(c * 0.3) for c in color)
                self._draw_filled_circle(x, y, glow_size, glow_color)  # type: ignore[arg-type]

    def _render_breath_ring(self) -> None:
        """Render breath ring."""
        cx, cy = self.config.width // 2, self.config.height // 2
        base_radius = int(self.config.width * self.config.breath_ring_radius)

        # Color based on phase
        phase_colors = {
            BreathPhase.INHALE: (100, 150, 255),  # Blue (PLAN)
            BreathPhase.HOLD: (255, 200, 100),  # Amber (EXECUTE)
            BreathPhase.EXHALE: (100, 255, 150),  # Green (VERIFY)
            BreathPhase.REST: (80, 80, 100),  # Gray
        }
        color = phase_colors.get(self._breath_phase, (80, 80, 100))

        # Radius modulated by progress
        radius = int(base_radius * (0.8 + 0.2 * self._breath_progress))

        # Draw ring
        self._draw_circle(cx, cy, radius, color, thickness=3)

    def _render_safety_aura(self) -> None:
        """Render safety aura."""
        h = max(0.0, min(1.0, self._safety_h))
        width, height = self.config.width, self.config.height

        # Color based on safety
        if h < 0.3:
            color = (255, 60, 60)  # Red
        elif h < 0.5:
            color = (255, 200, 60)  # Amber
        else:
            color = (60, 255, 120)  # Green

        edge_width = 10 if h > 0.5 else (20 if h > 0.3 else 30)

        # Draw edge gradient
        for i in range(edge_width):
            alpha = (edge_width - i) / edge_width * 0.3
            edge_color = tuple(int(c * alpha) for c in color)

            # Edges
            self._buffer[i, :, :3] = np.maximum(self._buffer[i, :, :3], edge_color)
            self._buffer[height - 1 - i, :, :3] = np.maximum(
                self._buffer[height - 1 - i, :, :3], edge_color
            )
            self._buffer[:, i, :3] = np.maximum(self._buffer[:, i, :3], edge_color)
            self._buffer[:, width - 1 - i, :3] = np.maximum(
                self._buffer[:, width - 1 - i, :3], edge_color
            )

    def _get_dominant_colony_color(self) -> tuple[int, int, int]:
        """Get color for dominant colony."""
        # Simple dominant colony detection
        dominant = None
        max_activation = 0.0

        for colony, state in self._colonies.items():
            if state.activation > max_activation:
                max_activation = state.activation
                dominant = colony

        if dominant:
            return self._get_colony_color(dominant)
        return (212, 175, 55)  # Gold default

    def _get_colony_color(self, colony: Colony) -> tuple[int, int, int]:
        """Get color for colony."""
        # Colony color mapping
        colors = {
            Colony.SPARK: (255, 100, 100),  # Red-orange
            Colony.FORGE: (255, 150, 50),  # Orange
            Colony.FLOW: (100, 150, 255),  # Blue
            Colony.NEXUS: (150, 100, 255),  # Purple
            Colony.BEACON: (200, 200, 200),  # White
            Colony.GROVE: (50, 150, 50),  # Green
            Colony.CRYSTAL: (100, 200, 255),  # Ice blue
        }
        return colors.get(colony, (150, 150, 150))

    def _get_catastrophe_offset(self, colony: Colony, state: ColonyState) -> float:
        """Get catastrophe-based angle offset."""
        # Simplified catastrophe influence on position
        potential = getattr(state, "potential", 0.0)
        return math.sin(potential * self._time) * 0.2

    def _get_catastrophe_size(self, colony: Colony, state: ColonyState) -> float:
        """Get catastrophe-based size modulation."""
        potential = getattr(state, "potential", 0.0)
        return 20 + 10 * abs(math.sin(potential * 2))

    def _draw_circle(
        self, cx: int, cy: int, radius: int, color: tuple[int, int, int], thickness: int = 1
    ) -> None:
        """Draw a circle."""
        for t in range(360 * 2):
            angle = t * math.pi / 360
            for dr in range(thickness):
                x = int(cx + (radius + dr) * math.cos(angle))
                y = int(cy + (radius + dr) * math.sin(angle))
                if 0 <= x < self.config.width and 0 <= y < self.config.height:
                    self._buffer[y, x, :3] = color

    def _draw_filled_circle(
        self, cx: int, cy: int, radius: int, color: tuple[int, int, int]
    ) -> None:
        """Draw a filled circle."""
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    x, y = cx + dx, cy + dy
                    if 0 <= x < self.config.width and 0 <= y < self.config.height:
                        self._buffer[y, x, :3] = color

    def _update_fps(self) -> None:
        """Update FPS calculation."""
        now = time.time()
        if now - self._last_fps_time >= 1.0:
            self._fps = self._frame_count / (now - self._last_fps_time)
            self._frame_count = 0
            self._last_fps_time = now

    def get_stats(self) -> dict[str, Any]:
        """Get renderer statistics."""
        return {
            "fps": self._fps,
            "frame_count": self._frame_count,
            "width": self.config.width,
            "height": self.config.height,
            "colony_count": len(self._colonies),
            "breath_phase": self._breath_phase.value,
            "safety_h": self._safety_h,
        }
