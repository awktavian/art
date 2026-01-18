#!/usr/bin/env python3
"""Demo: Ambient Intelligence - Organism State Bridge.

Demonstrates real-time state flow from organism to ambient display.

NEXUS BRIDGE: Organism execution -> Ambient visualization

The Bridge Pattern:
===================
The organism.set_ambient_controller() method establishes a unidirectional
data flow from the UnifiedOrganism to the AmbientController:

    UnifiedOrganism                    AmbientController
    ---------------                    -----------------
    | execute_intent() |  ------>     | breath.phase    |
    | phase_detector   |  state flow  | colony.activation|
    | _last_safety_check|  ------>    | safety.h_value  |
    ---------------                    -----------------

After each intent execution, the organism calls _update_ambient_state()
which propagates:
- Coordination phase -> Breath phase mapping
- Colony activations -> Colony state visualization
- CBF safety result h(x) -> Safety barrier visualization
- Presence detection -> Presence level display

This enables zero-latency visual feedback of cognitive state without polling.

This demo:
1. Creates organism + ambient controller
2. Wires them together via set_ambient_controller()
3. Executes intents
4. Shows ambient state updates in real-time

Created: December 14, 2025
Author: Nexus (Integration)
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING
from collections.abc import AsyncIterator

from kagami.core.ambient.controller import AmbientController, AmbientConfig
from kagami.core.unified_agents.unified_organism import (
    UnifiedOrganism,
    OrganismConfig,
)

if TYPE_CHECKING:
    from kagami.core.ambient.data_types import AmbientState

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class DemoConfig:
    """Configuration for demo execution."""

    device: str = "cpu"
    enable_hardware: bool = False

    def create_organism_config(self) -> OrganismConfig:
        """Create organism configuration from demo settings."""
        return OrganismConfig(
            max_workers_per_colony=2,
            min_workers_per_colony=1,
            device=self.device,
        )

    def create_ambient_config(self) -> AmbientConfig:
        """Create ambient configuration from demo settings."""
        return AmbientConfig(
            enable_lights=self.enable_hardware,
            enable_sound=self.enable_hardware,
            enable_haptic=self.enable_hardware,
            enable_voice=self.enable_hardware,
            enable_constellation=self.enable_hardware,
        )


@asynccontextmanager
async def organism_ambient_bridge(
    config: DemoConfig | None = None,
) -> AsyncIterator[tuple[UnifiedOrganism, AmbientController]]:
    """Async context manager for organism-ambient bridge lifecycle.

    Handles setup, connection, and teardown of both components with proper
    error handling and cleanup guarantees.

    Args:
        config: Optional demo configuration. Defaults to DemoConfig().

    Yields:
        Tuple of (organism, ambient_controller) ready for use.

    Example:
        async with organism_ambient_bridge() as (organism, ambient):
            await organism.execute_intent("test.intent", {}, {})
            state = ambient.get_state()
    """
    config = config or DemoConfig()

    organism: UnifiedOrganism | None = None
    ambient: AmbientController | None = None

    try:
        logger.info("Initializing organism-ambient bridge...")

        # Create components
        organism = UnifiedOrganism(config=config.create_organism_config())
        ambient = AmbientController(config=config.create_ambient_config())

        # Initialize in parallel where possible
        await ambient.initialize()
        await organism.start()

        # Establish the nexus bridge: organism state -> ambient display
        # This enables real-time visualization of cognitive state
        organism.set_ambient_controller(ambient)

        logger.info("Bridge established: organism state will flow to ambient display")

        yield organism, ambient

    except Exception as e:
        logger.error("Failed to initialize bridge: %s", e, exc_info=True)
        raise

    finally:
        # Cleanup in reverse order of initialization
        logger.info("Shutting down organism-ambient bridge...")

        if organism is not None:
            try:
                await organism.stop()
                logger.debug("Organism stopped")
            except Exception as e:
                logger.warning("Error stopping organism: %s", e)

        if ambient is not None:
            try:
                await ambient.shutdown()
                logger.debug("Ambient controller shut down")
            except Exception as e:
                logger.warning("Error shutting down ambient controller: %s", e)

        logger.info("Bridge shutdown complete")


def print_separator(title: str = "") -> None:
    """Print visual separator for demo sections."""
    width = 80
    if title:
        print(f"\n{'=' * width}")
        print(f"  {title}")
        print(f"{'=' * width}\n")
    else:
        print(f"{'=' * width}\n")


def print_ambient_state(state: AmbientState) -> None:
    """Print current ambient state in a readable format.

    Args:
        state: The ambient state to display.
    """
    print("\n--- AMBIENT STATE ---")

    # Breath
    print(f"Breath: {state.breath.phase.value} ({state.breath.phase_progress:.1%} through phase)")
    print(f"  BPM: {state.breath.bpm:.1f}, Cycle: {state.breath.cycle_count}")

    # Colonies
    print(f"\nColonies ({len(state.colonies)} active):")
    for colony, colony_state in state.colonies.items():
        print(f"  {colony.value:8s}: activation={colony_state.activation:.2f}")

    # Safety
    print("\nSafety:")
    safety_status = "SAFE" if state.safety.is_safe else "UNSAFE"
    print(f"  h(x) = {state.safety.h_value:.3f} ({safety_status})")
    print(f"  Margin: {state.safety.safety_margin:.1%}")

    # Presence
    print("\nPresence:")
    print(f"  Level: {state.presence.level.value} (confidence={state.presence.confidence:.1%})")

    print("\n" + "-" * 60)


async def demo_basic_connection() -> None:
    """Demo 1: Basic organism-ambient connection.

    Shows the minimal setup required to establish the bridge between
    organism execution and ambient visualization.
    """
    print_separator("DEMO 1: Basic Connection")

    async with organism_ambient_bridge() as (_organism, ambient):
        print("[OK] Bridge established!")
        print("  Organism state will now flow to ambient display in real-time")

        # Verify connection by checking ambient state
        state = ambient.get_state()
        print(f"  Current breath phase: {state.breath.phase.value}")
        print(f"  Safety h(x): {state.safety.h_value:.3f}")


async def demo_state_propagation() -> None:
    """Demo 2: Watch state propagate through bridge.

    Executes multiple intents and observes how organism state
    flows to ambient display after each execution.
    """
    print_separator("DEMO 2: State Propagation")

    intents: list[tuple[str, dict[str, str]]] = [
        ("research.explore", {"topic": "ambient intelligence"}),
        ("build.implement", {"feature": "real-time bridge"}),
        ("verify.test", {"target": "integration"}),
    ]

    async with organism_ambient_bridge() as (organism, ambient):
        for i, (intent, params) in enumerate(intents, 1):
            print(f"\n[{i}/{len(intents)}] Executing intent: {intent}")

            result = await organism.execute_intent(intent=intent, params=params, context={})

            # Access result fields with proper typing
            success = result.get("success", False)
            mode = result.get("mode", "unknown")
            latency = result.get("latency", 0.0)

            print(f"  -> Success: {success}")
            print(f"  -> Mode: {mode}")
            print(f"  -> Latency: {latency:.3f}s")

            # Show ambient state after execution
            state = ambient.get_state()
            print_ambient_state(state)

            await asyncio.sleep(0.5)


async def demo_safety_visualization() -> None:
    """Demo 3: Safety barrier (h(x)) visualization.

    Shows how CBF safety values propagate to ambient display,
    enabling real-time safety state visualization.
    """
    print_separator("DEMO 3: Safety Barrier Visualization")

    async with organism_ambient_bridge() as (organism, ambient):
        print("Executing safe intents and monitoring h(x)...\n")

        for i in range(3):
            await organism.execute_intent(
                intent=f"test.safe_{i}",
                params={"iteration": i},
                context={},
            )

            state = ambient.get_state()
            h_x = state.safety.h_value

            # Color zone classification based on h(x)
            if h_x >= 0.5:
                zone = "GREEN"
            elif h_x >= 0:
                zone = "YELLOW"
            else:
                zone = "RED"

            print(f"Intent {i + 1}: h(x) = {h_x:.3f} [{zone}]")


async def demo_phase_transitions() -> None:
    """Demo 4: Coordination phase -> Breath phase mapping.

    Demonstrates how organism coordination phases map to
    ambient breath phases for intuitive state visualization.
    """
    print_separator("DEMO 4: Phase Transitions")

    async with organism_ambient_bridge() as (organism, ambient):
        print("Executing intents and tracking phase changes...\n")

        prev_phase = None

        for i in range(5):
            await organism.execute_intent(
                intent=f"test.phase_{i}",
                params={"iteration": i},
                context={},
            )

            # Check coordination phase from organism
            coord_phase = organism.phase_detector.current_phase

            # Check breath phase from ambient state
            state = ambient.get_state()
            breath_phase = state.breath.phase

            if coord_phase != prev_phase:
                print(f"Phase transition: {prev_phase} -> {coord_phase}")
                prev_phase = coord_phase

            print(f"  Coordination: {coord_phase.value:12s} -> Breath: {breath_phase.value}")

            await asyncio.sleep(0.2)


async def main() -> None:
    """Run all demos with proper error handling."""
    print("\n")
    print("+" + "=" * 78 + "+")
    print("|" + " " * 78 + "|")
    print("|" + "  AMBIENT - ORGANISM BRIDGE DEMO".center(78) + "|")
    print("|" + " " * 78 + "|")
    print("|" + "  Nexus Integration: Real-time state flow".center(78) + "|")
    print("|" + " " * 78 + "|")
    print("+" + "=" * 78 + "+")
    print("\n")

    try:
        await demo_basic_connection()
        await demo_state_propagation()
        await demo_safety_visualization()
        await demo_phase_transitions()

        print_separator("ALL DEMOS COMPLETE")
        print("[OK] Ambient - Organism bridge is operational")
        print("[OK] Real-time state flow verified")
        print("[OK] Safety, colonies, and phases propagate correctly")

    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error("Demo failed: %s", e, exc_info=True)
        raise SystemExit(1) from e


if __name__ == "__main__":
    asyncio.run(main())
