#!/usr/bin/env python3
"""K OS Ambient Display — Visual Representation of Kagami's State.

Shows what the HAL display actually renders:
- Breath ring (active inference phases: PLAN → EXECUTE → VERIFY)
- 7 Colony nodes (octonion agents with activation levels)
- Safety aura (h(x) barrier visualization)

WHAT YOU'LL LEARN:
==================
1. Breath cycle visualization (4s inhale, 2s hold, 4s exhale, 2s rest)
2. Colony activation patterns
3. Safety h(x) edge glow
4. Interactive controls

CONTROLS:
=========
- Left-click colony → Boost activation
- Right-click → Advance breath phase
- Keys 1-7 → Boost colonies
- +/- → Adjust safety h(x)
- 's' → Save screenshot
- 'q' → Quit

Created: December 31, 2025
Colony: Crystal (e₇) — The Judge
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from enum import Enum

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

try:
    import cv2

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.error("OpenCV required: pip install opencv-python")


# =============================================================================
# Data Types (simplified from kagami/core/ambient/data_types.py)
# =============================================================================


class BreathPhase(Enum):
    INHALE = "inhale"  # PLAN phase
    HOLD = "hold"  # EXECUTE phase
    EXHALE = "exhale"  # VERIFY phase
    REST = "rest"


class Colony(Enum):
    SPARK = "spark"  # e₁ - Creativity
    FORGE = "forge"  # e₂ - Implementation
    FLOW = "flow"  # e₃ - Recovery
    NEXUS = "nexus"  # e₄ - Memory
    BEACON = "beacon"  # e₅ - Planning
    GROVE = "grove"  # e₆ - Research
    CRYSTAL = "crystal"  # e₇ - Verification


@dataclass
class BreathState:
    phase: BreathPhase
    value: float  # 0-1 within phase


@dataclass
class ColonyState:
    colony: Colony
    activation: float  # 0-1


@dataclass
class SafetyState:
    h_value: float  # 0-1, h(x) ≥ 0 is safe


# Colony colors (RGB) - from Fano plane mapping
COLONY_COLORS = {
    Colony.SPARK: (255, 0, 255),  # e₁ - Magenta
    Colony.FORGE: (255, 45, 85),  # e₂ - Red-Pink
    Colony.FLOW: (0, 255, 255),  # e₃ - Cyan
    Colony.NEXUS: (255, 215, 0),  # e₄ - Gold
    Colony.BEACON: (0, 255, 127),  # e₅ - Spring Green
    Colony.GROVE: (147, 112, 219),  # e₆ - Purple
    Colony.CRYSTAL: (30, 144, 255),  # e₇ - Dodger Blue
}

COLONY_ANGLES = {c: i * 2 * math.pi / 7 for i, c in enumerate(Colony)}


# =============================================================================
# Ambient Display Renderer
# =============================================================================


class AmbientDisplayDemo:
    """Demonstrates the actual K OS ambient display rendering."""

    def __init__(self, width: int = 800, height: int = 600):
        self.width = width
        self.height = height
        self.buffer = np.zeros((height, width, 3), dtype=np.uint8)

        # Simulated state
        self.breath = BreathState(BreathPhase.INHALE, 0.0)
        self.colonies = {c: ColonyState(c, 0.3) for c in Colony}
        self.safety = SafetyState(h_value=0.8)

        # Animation time
        self.time = 0.0

    def simulate_state(self, dt: float) -> None:
        """Simulate K OS state changes."""
        self.time += dt

        # Breath cycle: 4s inhale, 2s hold, 4s exhale, 2s rest = 12s total
        cycle_time = self.time % 12.0
        if cycle_time < 4.0:
            self.breath = BreathState(BreathPhase.INHALE, cycle_time / 4.0)
        elif cycle_time < 6.0:
            self.breath = BreathState(BreathPhase.HOLD, (cycle_time - 4.0) / 2.0)
        elif cycle_time < 10.0:
            self.breath = BreathState(BreathPhase.EXHALE, (cycle_time - 6.0) / 4.0)
        else:
            self.breath = BreathState(BreathPhase.REST, (cycle_time - 10.0) / 2.0)

        # Colony activations (wave pattern)
        for i, colony in enumerate(Colony):
            phase = (self.time * 0.5 + i * 0.7) % (2 * math.pi)
            self.colonies[colony].activation = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(phase))

        # Safety oscillation (mostly safe, occasional dips)
        safety_wave = 0.5 + 0.5 * math.sin(self.time * 0.3)
        self.safety.h_value = 0.4 + 0.5 * safety_wave

    def clear(self) -> None:
        """Clear to dark background."""
        self.buffer[:, :, 0] = 10  # B
        self.buffer[:, :, 1] = 10  # G
        self.buffer[:, :, 2] = 15  # R (BGR format for OpenCV)

    def draw_breath_ring(self) -> None:
        """Render the breath ring (PLAN → EXECUTE → VERIFY cycle)."""
        cx, cy = self.width // 2, self.height // 2
        base_radius = int(min(self.width, self.height) * 0.25)

        # Radius modulated by breath
        radius = int(base_radius * (0.8 + 0.2 * self.breath.value))

        # Color by phase
        phase_colors = {
            BreathPhase.INHALE: (255, 150, 100),  # Blue (PLAN) - BGR
            BreathPhase.HOLD: (100, 200, 255),  # Amber (EXECUTE)
            BreathPhase.EXHALE: (150, 255, 100),  # Green (VERIFY)
            BreathPhase.REST: (100, 80, 80),  # Gray
        }
        color = phase_colors.get(self.breath.phase, (100, 100, 100))

        # Draw main ring
        cv2.circle(self.buffer, (cx, cy), radius, color, 3)

        # Draw glow (outer rings with decreasing alpha)
        for i in range(1, 6):
            alpha = (6 - i) / 6.0 * 0.3
            glow_color = tuple(int(c * alpha) for c in color)
            cv2.circle(self.buffer, (cx, cy), radius + i * 3, glow_color, 1)

        # Inner pulse
        inner_radius = int(radius * 0.7 * self.breath.value)
        if inner_radius > 5:
            overlay = self.buffer.copy()
            cv2.circle(overlay, (cx, cy), inner_radius, color, -1)
            alpha = 0.15 * self.breath.value
            cv2.addWeighted(overlay, alpha, self.buffer, 1 - alpha, 0, self.buffer)

        # Phase label
        phase_name = self.breath.phase.value.upper()
        phase_labels = {"INHALE": "PLAN", "HOLD": "EXECUTE", "EXHALE": "VERIFY", "REST": "REST"}
        label = phase_labels.get(phase_name, phase_name)
        font = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), _ = cv2.getTextSize(label, font, 0.7, 2)
        tx = cx - tw // 2
        ty = cy + th // 2
        cv2.putText(self.buffer, label, (tx, ty), font, 0.7, (200, 200, 200), 2)

    def draw_colonies(self) -> None:
        """Render the 7 colony nodes orbiting the center."""
        cx, cy = self.width // 2, self.height // 2
        orbit_radius = int(min(self.width, self.height) * 0.35)

        # Draw orbit path
        cv2.circle(self.buffer, (cx, cy), orbit_radius, (40, 40, 40), 1)

        for colony, state in self.colonies.items():
            # Position on orbit (slowly rotating)
            angle = COLONY_ANGLES[colony] + self.time * 0.15
            x = int(cx + orbit_radius * math.cos(angle))
            y = int(cy + orbit_radius * math.sin(angle))

            # Size based on activation
            size = int(8 + 20 * state.activation)

            # Color (BGR for OpenCV)
            rgb = COLONY_COLORS[colony]
            bgr = (rgb[2], rgb[1], rgb[0])

            # Draw colony node
            cv2.circle(self.buffer, (x, y), size, bgr, -1)

            # Glow if highly active
            if state.activation > 0.5:
                glow_size = int(size * 1.5)
                glow_alpha = 0.2 * state.activation
                overlay = self.buffer.copy()
                cv2.circle(overlay, (x, y), glow_size, bgr, -1)
                cv2.addWeighted(overlay, glow_alpha, self.buffer, 1 - glow_alpha, 0, self.buffer)

            # Colony name (small)
            name = colony.value[:1].upper()  # First letter
            cv2.putText(
                self.buffer, name, (x - 5, y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1
            )

    def draw_safety_aura(self) -> None:
        """Render safety barrier as edge glow."""
        h = self.safety.h_value

        # Color based on safety level
        if h < 0.3:
            # DANGER - red pulsing
            pulse = 0.5 + 0.5 * math.sin(self.time * 5)
            color = (int(50 * pulse), int(50 * pulse), 255)  # BGR
            width = 30
        elif h < 0.5:
            # WARNING - yellow
            color = (50, 200, 255)  # BGR
            width = 20
        else:
            # SAFE - subtle green
            color = (100, 255, 50)  # BGR
            width = 10

        # Draw edge gradient
        for i in range(width):
            alpha = (width - i) / width * 0.3
            edge_color = tuple(int(c * alpha) for c in color)

            # Top
            cv2.line(self.buffer, (0, i), (self.width, i), edge_color, 1)
            # Bottom
            cv2.line(
                self.buffer,
                (0, self.height - 1 - i),
                (self.width, self.height - 1 - i),
                edge_color,
                1,
            )
            # Left
            cv2.line(self.buffer, (i, 0), (i, self.height), edge_color, 1)
            # Right
            cv2.line(
                self.buffer,
                (self.width - 1 - i, 0),
                (self.width - 1 - i, self.height),
                edge_color,
                1,
            )

        # Safety value text
        h_text = f"h(x) = {h:.2f}"
        color_text = (
            (100, 255, 100) if h >= 0.5 else (50, 200, 255) if h >= 0.3 else (100, 100, 255)
        )
        cv2.putText(self.buffer, h_text, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_text, 1)

    def draw_info(self) -> None:
        """Draw info overlay."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        y = self.height - 60

        # Title
        cv2.putText(self.buffer, "K OS Ambient Display", (20, y), font, 0.6, (180, 180, 200), 1)

        # Legend
        y += 25
        cv2.putText(
            self.buffer,
            "Ring=Breath | Nodes=Colonies | Edge=Safety h(x)",
            (20, y),
            font,
            0.4,
            (120, 120, 140),
            1,
        )

        # FPS indicator (top right)
        cv2.putText(
            self.buffer, f"t={self.time:.1f}s", (self.width - 80, 30), font, 0.5, (100, 100, 100), 1
        )

    def render_frame(self) -> np.ndarray:
        """Render one frame."""
        self.clear()
        self.draw_safety_aura()
        self.draw_breath_ring()
        self.draw_colonies()
        self.draw_info()
        return self.buffer

    # =========================================================================
    # Interaction Handling
    # =========================================================================

    def hit_test(self, nx: float, ny: float) -> str | None:
        """Test what element is at normalized coordinates."""
        px = int(nx * self.width)
        py = int(ny * self.height)
        cx, cy = self.width // 2, self.height // 2

        # Check colonies
        orbit_radius = int(min(self.width, self.height) * 0.35)
        for colony, state in self.colonies.items():
            angle = COLONY_ANGLES[colony] + self.time * 0.15
            x = int(cx + orbit_radius * math.cos(angle))
            y = int(cy + orbit_radius * math.sin(angle))
            size = int(8 + 20 * state.activation) + 10

            dist = math.sqrt((px - x) ** 2 + (py - y) ** 2)
            if dist <= size:
                return f"Colony: {colony.value}"

        # Check breath ring
        radius = int(min(self.width, self.height) * 0.25 * (0.8 + 0.2 * self.breath.value))
        dist = math.sqrt((px - cx) ** 2 + (py - cy) ** 2)
        if abs(dist - radius) < 20:
            return f"Breath: {self.breath.phase.value}"

        # Check edges (safety)
        if px < 40 or px > self.width - 40 or py < 40 or py > self.height - 40:
            return f"Safety: h(x)={self.safety.h_value:.2f}"

        return None

    def handle_click(self, nx: float, ny: float) -> None:
        """Handle click at normalized coordinates."""
        px = int(nx * self.width)
        py = int(ny * self.height)
        cx, cy = self.width // 2, self.height // 2

        # Check colonies
        orbit_radius = int(min(self.width, self.height) * 0.35)
        for colony, state in self.colonies.items():
            angle = COLONY_ANGLES[colony] + self.time * 0.15
            x = int(cx + orbit_radius * math.cos(angle))
            y = int(cy + orbit_radius * math.sin(angle))
            size = int(8 + 20 * state.activation) + 10

            dist = math.sqrt((px - x) ** 2 + (py - y) ** 2)
            if dist <= size:
                self.boost_colony(colony)
                return

    def boost_colony(self, colony: Colony) -> None:
        """Boost a colony's activation."""
        if colony in self.colonies:
            current = self.colonies[colony].activation
            self.colonies[colony].activation = min(1.0, current + 0.3)

    def advance_breath(self) -> None:
        """Advance to next breath phase."""
        phases = [BreathPhase.INHALE, BreathPhase.HOLD]
        current_idx = 0
        for i, p in enumerate(phases):
            if self.breath.phase == p:
                current_idx = i
                break
        next_phase = phases[(current_idx + 1) % len(phases)]
        self.breath = BreathState(next_phase, 0.0)


def mouse_callback(event, x, y, flags, param):
    """Handle mouse events on the display."""
    display = param

    # Normalize coordinates
    nx = x / display.width
    ny = y / display.height

    if event == cv2.EVENT_LBUTTONDOWN:
        hit = display.hit_test(nx, ny)
        if hit:
            print(f"  🖱️ Click: {hit}")
            display.handle_click(nx, ny)
    elif event == cv2.EVENT_RBUTTONDOWN:
        # Right click advances breath phase
        display.advance_breath()
        print("  🖱️ Right-click: Advanced breath phase")


async def main():
    """Run the ambient display demo."""
    print()
    print("═" * 64)
    print("  🌀 K OS AMBIENT DISPLAY")
    print("═" * 64)
    print()
    print("  This shows what the HAL display actually renders:")
    print("  • Breath Ring — Active inference cycle (PLAN→EXECUTE→VERIFY)")
    print("  • Colony Nodes — 7 octonion agents with activation levels")
    print("  • Safety Aura — h(x) barrier visualization (CBF)")
    print()
    print("  CONTROLS:")
    print("  • Left-click colony → Boost activation & select")
    print("  • Right-click anywhere → Advance breath phase")
    print("  • Keys 1-7 → Boost colonies (S/F/L/N/B/G/C)")
    print("  • +/- → Adjust safety h(x)")
    print("  • 'q' → Quit, 's' → Save screenshot")
    print()
    print("═" * 64)

    if not CV2_AVAILABLE:
        print("\n  ❌ OpenCV not available")
        return

    display = AmbientDisplayDemo(800, 600)
    window_name = "K OS Ambient Display"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_name, mouse_callback, display)

    dt = 1.0 / 30  # 30 FPS

    while True:
        # Simulate state
        display.simulate_state(dt)

        # Render
        frame = display.render_frame()

        # Show
        cv2.imshow(window_name, frame)

        # Handle keyboard input
        key = cv2.waitKey(int(dt * 1000)) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("s"):
            filename = f"ambient_display_{int(time.time())}.png"
            cv2.imwrite(filename, frame)
            print(f"  Saved: {filename}")
        elif ord("1") <= key <= ord("7"):
            # Boost colony by number
            idx = key - ord("1")
            colonies = list(Colony)
            if idx < len(colonies):
                colony = colonies[idx]
                display.boost_colony(colony)
                print(f"  ⬆️ Boosted {colony.value}")
        elif key == ord("+") or key == ord("="):
            display.safety.h_value = min(1.0, display.safety.h_value + 0.1)
            print(f"  🛡️ Safety h(x) = {display.safety.h_value:.2f}")
        elif key == ord("-"):
            display.safety.h_value = max(0.0, display.safety.h_value - 0.1)
            print(f"  ⚠️ Safety h(x) = {display.safety.h_value:.2f}")

    cv2.destroyAllWindows()
    print()
    print("═" * 64)
    print("  ✓ Demo complete!")
    print()
    print("  Next steps:")
    print("    → Run hello_kagami.py for first contact")
    print("    → Run seven_colony_code_review.py for flagship demo")
    print("    → See docs/05_HOW_I_THINK.md for colony details")
    print("═" * 64)
    print()
    print("  鏡 The mirror reflects.")


if __name__ == "__main__":
    asyncio.run(main())
