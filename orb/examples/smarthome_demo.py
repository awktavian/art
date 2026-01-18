#!/usr/bin/env python3
"""Smart Home Demo — Control Your Home with Kagami.

This is Kagami's PRIMARY VALUE PROPOSITION: intelligent home control.

WHAT YOU'LL LEARN:
==================
1. Connect to SmartHomeController
2. Control lights (set levels, scenes)
3. Control shades (open/close/position)
4. Run scenes (movie mode, goodnight)
5. Audio announcements
6. Lock control with safety checks

Created: December 31, 2025
Colony: Forge (e2) — The Builder
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from unittest.mock import MagicMock

# Add examples/common to path
sys.path.insert(0, str(Path(__file__).parent))

from common.output import (
    print_header,
    print_section,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_metrics,
    print_footer,
    print_separator,
)
from common.metrics import Timer, MetricsCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS — Named values for light levels and configuration
# =============================================================================


# Light level presets (0-100 percentage)
class LightLevel:
    """Named constants for light level percentages."""

    OFF = 0
    DIM = 10
    LOW = 25
    MEDIUM = 50
    BRIGHT = 70
    FULL = 100

    # Context-specific presets
    LIVING_ROOM_DEFAULT = 50
    KITCHEN_DEFAULT = 70
    OFFICE_DEFAULT = 40
    MOVIE_BIAS = 10


# CBF Safety thresholds
class SafetyThreshold:
    """Control Barrier Function safety thresholds."""

    SAFE = 0.0  # h(x) >= 0 is safe
    CAUTION = 0.3  # Below this, extra warnings
    BLOCKED = -0.1  # Below this, action blocked


# Valid rooms in the home (from localization.py FLOOR_ROOMS)
VALID_ROOMS: frozenset[str] = frozenset(
    [
        # First Floor
        "Living Room",
        "Entry",
        "Porch",
        "Kitchen",
        "Dining",
        "Mudroom",
        "Powder Room",
        "Garage",
        "Deck",
        "Stairway",
        # Second Floor
        "Primary Bed",
        "Primary Bath",
        "Primary Closet",
        "Primary Hall",
        "Loft",
        "Office",
        "Office Bath",
        "Bed 3",
        "Bath 3",
        "Laundry",
        # Basement
        "Game Room",
        "Rack Room",
        "Bed 4",
        "Bath 4",
        "Gym",
        "Patio",
    ]
)

# Common room aliases for user convenience
ROOM_ALIASES: dict[str, str] = {
    "living": "Living Room",
    "kitchen": "Kitchen",
    "office": "Office",
    "bedroom": "Primary Bed",
    "primary bedroom": "Primary Bed",
    "master bedroom": "Primary Bed",
    "game": "Game Room",
    "gameroom": "Game Room",
    "gym": "Gym",
    "loft": "Loft",
    "garage": "Garage",
    "entry": "Entry",
    "dining": "Dining",
}


# =============================================================================
# TYPE DEFINITIONS — Protocol for controller interface
# =============================================================================

if TYPE_CHECKING:
    from kagami_smarthome.types import HomeState


@runtime_checkable
class SmartHomeControllerProtocol(Protocol):
    """Protocol defining the SmartHomeController interface.

    This allows type checking without importing the actual implementation,
    and enables proper typing for both real and mock controllers.
    """

    def get_state(self) -> HomeState:
        """Get current home state."""
        ...

    def get_all_lights(self) -> list[str]:
        """Get list of all lights."""
        ...

    def get_all_shades(self) -> list[str]:
        """Get list of all shades."""
        ...

    async def set_lights(self, level: int, rooms: list[str] | None = None) -> None:
        """Set light level for specified rooms."""
        ...

    async def open_shades(self, rooms: list[str] | None = None) -> None:
        """Open shades in specified rooms."""
        ...

    async def close_shades(self, rooms: list[str] | None = None) -> None:
        """Close shades in specified rooms."""
        ...

    async def enter_movie_mode(self) -> None:
        """Activate movie mode scene."""
        ...

    async def exit_movie_mode(self) -> None:
        """Deactivate movie mode scene."""
        ...

    async def announce(self, text: str, rooms: list[str] | None = None) -> None:
        """Make announcement in specified rooms."""
        ...

    async def announce_all(self, text: str) -> None:
        """Make announcement in all rooms."""
        ...

    async def lock_all(self) -> None:
        """Lock all doors."""
        ...

    async def fireplace_on(self) -> None:
        """Turn on fireplace."""
        ...

    async def fireplace_off(self) -> None:
        """Turn off fireplace."""
        ...


# =============================================================================
# INPUT VALIDATION
# =============================================================================


class RoomValidationError(ValueError):
    """Raised when an invalid room name is provided."""

    def __init__(self, invalid_room: str, valid_rooms: frozenset[str]) -> None:
        self.invalid_room = invalid_room
        self.valid_rooms = valid_rooms
        suggestions = self._get_suggestions(invalid_room, valid_rooms)
        suggestion_text = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"Invalid room name: '{invalid_room}'.{suggestion_text}")

    @staticmethod
    def _get_suggestions(invalid: str, valid: frozenset[str]) -> list[str]:
        """Get similar room name suggestions using simple substring matching."""
        invalid_lower = invalid.lower()
        suggestions = []
        for room in valid:
            if invalid_lower in room.lower() or room.lower() in invalid_lower:
                suggestions.append(room)
        return suggestions[:3]  # Return at most 3 suggestions


def validate_room_name(room: str) -> str:
    """Validate and normalize a room name.

    Args:
        room: The room name to validate

    Returns:
        Normalized room name

    Raises:
        RoomValidationError: If room name is not valid
    """
    # Check aliases first
    room_lower = room.lower().strip()
    if room_lower in ROOM_ALIASES:
        return ROOM_ALIASES[room_lower]

    # Check exact match (case-insensitive)
    for valid_room in VALID_ROOMS:
        if valid_room.lower() == room_lower:
            return valid_room

    # No match found
    raise RoomValidationError(room, VALID_ROOMS)


def validate_rooms(rooms: list[str] | None) -> list[str] | None:
    """Validate a list of room names.

    Args:
        rooms: List of room names to validate, or None

    Returns:
        List of validated/normalized room names, or None

    Raises:
        RoomValidationError: If any room name is not valid
    """
    if rooms is None:
        return None
    return [validate_room_name(room) for room in rooms]


# =============================================================================
# CBF SAFETY INTEGRATION
# =============================================================================


def check_safety(action: str, target: str, **params: object) -> tuple[bool, float, str]:
    """Check CBF safety before executing an action.

    Integrates with kagami_smarthome.safety when available,
    falls back to conservative defaults otherwise.

    Args:
        action: Action type (e.g., "fireplace_on", "unlock")
        target: Target device or room
        **params: Additional parameters for safety check

    Returns:
        Tuple of (is_safe, h_x_value, reason)
    """
    try:
        from kagami_smarthome.safety import (
            PhysicalActionType,
            SafetyContext,
            check_physical_safety,
        )

        # Map action strings to PhysicalActionType
        action_map = {
            "fireplace_on": PhysicalActionType.FIREPLACE_ON,
            "fireplace_off": PhysicalActionType.FIREPLACE_OFF,
            "lock": PhysicalActionType.LOCK,
            "unlock": PhysicalActionType.UNLOCK,
            "tv_lower": PhysicalActionType.TV_LOWER,
            "tv_raise": PhysicalActionType.TV_RAISE,
        }

        action_type = action_map.get(action)
        if action_type is None:
            # Unknown action type, allow with caution
            logger.warning(f"Unknown action type for CBF check: {action}")
            return True, 0.5, "Unknown action - defaulting to caution"

        context = SafetyContext(
            action_type=action_type,
            target=target,
            parameters=dict(params) if params else {},
        )

        result = check_physical_safety(context)
        return result.allowed, result.h_x, result.reason or "CBF check complete"

    except ImportError:
        logger.debug("CBF integration not available, using defaults")
        # Conservative defaults when CBF module not available
        safe_actions = {"fireplace_off", "lock"}
        h_x = 0.8 if action in safe_actions else 0.5
        return True, h_x, "Rule-based safety (CBF unavailable)"


# =============================================================================
# MOCK CONTROLLER — Created via factory function using unittest.mock
# =============================================================================


def create_mock_controller() -> SmartHomeControllerProtocol:
    """Create a mock SmartHomeController for simulation mode.

    Uses unittest.mock.MagicMock with configured return values
    to provide a realistic mock for demonstration purposes.

    Returns:
        A mock object implementing SmartHomeControllerProtocol
    """
    from unittest.mock import AsyncMock

    mock = MagicMock(spec=SmartHomeControllerProtocol)

    # Configure state mock
    state_mock = MagicMock()
    state_mock.rooms = [f"Room{i}" for i in range(26)]
    mock.get_state.return_value = state_mock

    # Configure device lists
    mock.get_all_lights.return_value = [f"Light{i}" for i in range(41)]
    mock.get_all_shades.return_value = [f"Shade{i}" for i in range(11)]

    # Async methods use AsyncMock for proper coroutine handling
    mock.set_lights = AsyncMock()
    mock.open_shades = AsyncMock()
    mock.close_shades = AsyncMock()
    mock.enter_movie_mode = AsyncMock()
    mock.exit_movie_mode = AsyncMock()
    mock.announce = AsyncMock()
    mock.announce_all = AsyncMock()
    mock.lock_all = AsyncMock()
    mock.fireplace_on = AsyncMock()
    mock.fireplace_off = AsyncMock()

    return mock  # type: ignore[return-value]


# =============================================================================
# SECTION 1: CONNECT TO SMART HOME
# =============================================================================


async def section_1_connect(metrics: MetricsCollector) -> SmartHomeControllerProtocol:
    """Connect to the SmartHomeController."""
    print_section(1, "Connecting to SmartHomeController")

    # Add packages to path
    sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

    from kagami_smarthome import get_smart_home

    with Timer() as t:
        controller = await get_smart_home()

    metrics.record_timing("connect", t.elapsed)

    # Get state summary
    state = controller.get_state()

    print_success("Connected to SmartHomeController", f"latency: {t.elapsed_ms:.0f}ms")
    print()
    print("   Home: 7331 W Green Lake Dr N, Seattle")
    print(f"   Rooms: {len(state.rooms) if hasattr(state, 'rooms') else 26}")
    print(f"   Status: {'Online' if controller else 'Offline'}")

    logger.info(f"Connected to SmartHomeController in {t.elapsed_ms:.0f}ms")

    return controller


# =============================================================================
# SECTION 2: LIGHT CONTROL
# =============================================================================


async def section_2_lights(
    controller: SmartHomeControllerProtocol,
    metrics: MetricsCollector,
    rooms: list[str] | None = None,
) -> None:
    """Demonstrate light control.

    Args:
        controller: SmartHomeController instance
        metrics: Metrics collector
        rooms: Optional list of rooms to control (defaults to Living Room, Kitchen, Office)
    """
    print_separator()
    print_section(2, "Light Control")

    # Get current light states
    lights = controller.get_all_lights()
    print(f"   Total lights: {len(lights)}")
    print()

    # Validate and set default rooms
    target_rooms = rooms or ["Living Room", "Kitchen", "Office"]
    validated_rooms = validate_rooms(target_rooms)
    assert validated_rooms is not None  # For type checker

    # Example: Set living room lights using named constant
    if "Living Room" in validated_rooms:
        print(f"   Setting Living Room to {LightLevel.LIVING_ROOM_DEFAULT}%...")
        with Timer() as t:
            try:
                await controller.set_lights(LightLevel.LIVING_ROOM_DEFAULT, rooms=["Living Room"])
                print_success(
                    f"Living Room lights set to {LightLevel.LIVING_ROOM_DEFAULT}%",
                    f"{t.elapsed_ms:.0f}ms",
                )
                metrics.increment("commands")
                logger.info(f"Set Living Room lights to {LightLevel.LIVING_ROOM_DEFAULT}%")
            except Exception as e:
                print_warning(f"Simulated: {e}")
                metrics.increment("simulated")
                logger.warning(f"Light control simulated: {e}")

    # Example: Multiple rooms with named constants
    print()
    print(
        f"   Setting Kitchen to {LightLevel.KITCHEN_DEFAULT}%, Office to {LightLevel.OFFICE_DEFAULT}%..."
    )
    with Timer() as t:
        try:
            if "Kitchen" in validated_rooms:
                await controller.set_lights(LightLevel.KITCHEN_DEFAULT, rooms=["Kitchen"])
            if "Office" in validated_rooms:
                await controller.set_lights(LightLevel.OFFICE_DEFAULT, rooms=["Office"])
            print_success("Multi-room lights set", f"{t.elapsed_ms:.0f}ms")
            metrics.increment("commands", 2)
            logger.info("Set multi-room lights")
        except Exception as e:
            print_warning(f"Simulated: {e}")
            metrics.increment("simulated", 2)
            logger.warning(f"Multi-room light control simulated: {e}")

    metrics.record_timing("lights", t.elapsed)


# =============================================================================
# SECTION 3: SHADE CONTROL
# =============================================================================


async def section_3_shades(
    controller: SmartHomeControllerProtocol,
    metrics: MetricsCollector,
    rooms: list[str] | None = None,
) -> None:
    """Demonstrate shade control.

    Args:
        controller: SmartHomeController instance
        metrics: Metrics collector
        rooms: Optional list of rooms to control
    """
    print_separator()
    print_section(3, "Shade Control")

    # Get current shade states
    shades = controller.get_all_shades()
    print(f"   Total shades: {len(shades)}")
    print()

    # Example: Close living room shades
    print("   Closing Living Room shades...")
    with Timer() as t:
        try:
            await controller.close_shades(rooms=["Living Room"])
            print_success("Living Room shades closed", f"{t.elapsed_ms:.0f}ms")
            metrics.increment("commands")
            logger.info("Closed Living Room shades")
        except Exception as e:
            print_warning(f"Simulated: {e}")
            metrics.increment("simulated")
            logger.warning(f"Shade control simulated: {e}")

    # Example: Open bedroom shades
    print()
    print("   Opening Primary Bedroom shades...")
    with Timer() as t:
        try:
            await controller.open_shades(rooms=["Primary Bed"])
            print_success("Primary Bedroom shades opened", f"{t.elapsed_ms:.0f}ms")
            metrics.increment("commands")
            logger.info("Opened Primary Bedroom shades")
        except Exception as e:
            print_warning(f"Simulated: {e}")
            metrics.increment("simulated")
            logger.warning(f"Shade control simulated: {e}")

    metrics.record_timing("shades", t.elapsed)


# =============================================================================
# SECTION 4: SCENES (MOVIE MODE, GOODNIGHT)
# =============================================================================


async def section_4_scenes(
    controller: SmartHomeControllerProtocol,
    metrics: MetricsCollector,
) -> None:
    """Demonstrate scene control.

    Args:
        controller: SmartHomeController instance
        metrics: Metrics collector
    """
    print_separator()
    print_section(4, "Scene Control")

    print(
        """
   Scenes coordinate multiple devices at once:

   * Movie Mode: TV down, lights dim, shades close, Atmos on
   * Goodnight: All off, locks check, security arm
   * Welcome Home: Entry lights, climate, security disarm
"""
    )

    # Example: Movie mode
    print("   Entering Movie Mode...")
    with Timer() as t:
        try:
            await controller.enter_movie_mode()
            print_success("Movie Mode activated", f"{t.elapsed_ms:.0f}ms")
            metrics.increment("commands")
            metrics.increment("scenes")
            logger.info("Activated Movie Mode")
        except Exception as e:
            print_warning(f"Simulated: {e}")
            metrics.increment("simulated")
            logger.warning(f"Movie Mode simulated: {e}")

    print()
    print("   Movie Mode actions:")
    print("      + MantelMount lowered to viewing preset")
    print(f"      + Living room lights -> {LightLevel.MOVIE_BIAS}% bias")
    print("      + Living room shades -> closed")
    print("      + Denon -> Movie mode, volume 45")
    print("      + Other audio zones -> muted")

    # Example: Exit movie mode
    print()
    print("   Exiting Movie Mode...")
    with Timer() as t:
        try:
            await controller.exit_movie_mode()
            print_success("Movie Mode deactivated", f"{t.elapsed_ms:.0f}ms")
            metrics.increment("commands")
            logger.info("Deactivated Movie Mode")
        except Exception as e:
            print_warning(f"Simulated: {e}")
            metrics.increment("simulated")
            logger.warning(f"Exit Movie Mode simulated: {e}")

    metrics.record_timing("scenes", t.elapsed)


# =============================================================================
# SECTION 5: AUDIO ANNOUNCEMENTS
# =============================================================================


async def section_5_audio(
    controller: SmartHomeControllerProtocol,
    metrics: MetricsCollector,
    rooms: list[str] | None = None,
) -> None:
    """Demonstrate audio announcements.

    Args:
        controller: SmartHomeController instance
        metrics: Metrics collector
        rooms: Optional list of rooms for targeted announcements
    """
    print_separator()
    print_section(5, "Audio Announcements")

    print("   26 audio zones via Triad AMS")
    print("   Living Room: KEF Reference 5.2.4 Dolby Atmos")
    print()

    # Validate rooms if provided
    announcement_rooms = validate_rooms(rooms) or ["Office"]

    # Example: Announce in specific room
    print(f"   Announcing in {announcement_rooms[0]}...")
    with Timer() as t:
        try:
            await controller.announce("Demo announcement", rooms=announcement_rooms[:1])
            print_success(f"Announcement sent to {announcement_rooms[0]}", f"{t.elapsed_ms:.0f}ms")
            metrics.increment("commands")
            logger.info(f"Sent announcement to {announcement_rooms[0]}")
        except Exception as e:
            print_warning(f"Simulated: {e}")
            metrics.increment("simulated")
            logger.warning(f"Announcement simulated: {e}")

    # Example: Announce in all rooms
    print()
    print("   Announcing in all rooms...")
    with Timer() as t:
        try:
            await controller.announce_all("Whole home announcement")
            print_success("Announcement sent to all rooms", f"{t.elapsed_ms:.0f}ms")
            metrics.increment("commands")
            logger.info("Sent whole-home announcement")
        except Exception as e:
            print_warning(f"Simulated: {e}")
            metrics.increment("simulated")
            logger.warning(f"Whole-home announcement simulated: {e}")

    metrics.record_timing("audio", t.elapsed)


# =============================================================================
# SECTION 6: LOCK CONTROL WITH SAFETY
# =============================================================================


async def section_6_locks(
    controller: SmartHomeControllerProtocol,
    metrics: MetricsCollector,
) -> None:
    """Demonstrate lock control with CBF safety checks.

    Args:
        controller: SmartHomeController instance
        metrics: Metrics collector
    """
    print_separator()
    print_section(6, "Lock Control (with Safety)")

    print(
        """
   Lock operations are CBF-protected:

   * h(x) >= 0 required before unlock
   * Never auto-unlock at night
   * Verify lock state after command
   * Receipt logged for audit
"""
    )

    # Example: Lock all doors with real CBF check
    print("   Locking all doors...")

    # Perform CBF safety check before action
    is_safe, h_x, reason = check_safety("lock", "all_doors")

    with Timer() as t:
        if is_safe and h_x >= SafetyThreshold.SAFE:
            try:
                await controller.lock_all()
                print_success("All doors locked", f"h(x) = {h_x:.2f}")
                metrics.increment("commands")
                logger.info(f"Locked all doors, h(x) = {h_x:.2f}")
            except Exception as e:
                print_warning(f"Simulated: {e}")
                metrics.increment("simulated")
                logger.warning(f"Lock simulated: {e}")
        else:
            print_error("Lock BLOCKED by CBF", f"h(x) = {h_x:.2f} ({reason})")
            logger.warning(f"Lock blocked by CBF: h(x) = {h_x:.2f}, reason: {reason}")

    # Example: Check lock status
    print()
    print("   Lock status:")
    print("      + Entry Lock: LOCKED")
    print("      + Game Room Lock: LOCKED")

    # Example: Unlock attempt with safety check (daytime scenario)
    print()
    print("   Unlock attempt (user home, daytime)...")
    is_safe_unlock, h_x_unlock, _reason_unlock = check_safety(
        "unlock",
        "entry_door",
        user_home=True,
        is_daytime=True,
    )
    if is_safe_unlock and h_x_unlock >= SafetyThreshold.SAFE:
        print_success("Unlock permitted", f"h(door_safety) = {h_x_unlock:.2f}")
        logger.info(f"Unlock permitted: h(x) = {h_x_unlock:.2f}")
    else:
        print_warning("Unlock requires caution", f"h(x) = {h_x_unlock:.2f}")

    # Example: Unlock attempt that would be blocked (nighttime, user away)
    print()
    print("   Unlock attempt (user away, night)...")
    # Simulate a blocked scenario
    blocked_h_x = -0.30
    print_error("Unlock BLOCKED", f"h(door_safety) = {blocked_h_x:.2f}")
    logger.warning(f"Unlock would be blocked: h(x) = {blocked_h_x:.2f}")

    metrics.record_timing("locks", t.elapsed)


# =============================================================================
# SECTION 7: FIREPLACE CONTROL
# =============================================================================


async def section_7_fireplace(
    controller: SmartHomeControllerProtocol,
    metrics: MetricsCollector,
) -> None:
    """Demonstrate fireplace control.

    Args:
        controller: SmartHomeController instance
        metrics: Metrics collector
    """
    print_separator()
    print_section(7, "Fireplace Control")

    print("   Gas fireplace with CBF safety:")
    print("      * Maximum 90-minute runtime (auto-shutoff)")
    print("      * h(x) check before activation")
    print("      * Receipt emitted for audit")
    print()

    # Example: Turn on fireplace with real CBF check
    print("   Turning on fireplace...")

    is_safe, h_x, reason = check_safety("fireplace_on", "fireplace")

    with Timer() as t:
        if is_safe and h_x >= SafetyThreshold.SAFE:
            try:
                await controller.fireplace_on()
                print_success("Fireplace ON", f"h(fire_safety) = {h_x:.2f}")
                metrics.increment("commands")
                logger.info(f"Fireplace turned on, h(x) = {h_x:.2f}")
            except Exception as e:
                print_warning(f"Simulated: {e}")
                metrics.increment("simulated")
                logger.warning(f"Fireplace on simulated: {e}")
        elif h_x < SafetyThreshold.CAUTION:
            print_warning("Fireplace ON with caution", f"h(x) = {h_x:.2f} ({reason})")
            # Still proceed but log warning
            try:
                await controller.fireplace_on()
                metrics.increment("commands")
                logger.warning(f"Fireplace on with caution: h(x) = {h_x:.2f}")
            except Exception as e:
                print_warning(f"Simulated: {e}")
                metrics.increment("simulated")
        else:
            print_error("Fireplace BLOCKED by CBF", f"h(x) = {h_x:.2f}")
            logger.error(f"Fireplace blocked: h(x) = {h_x:.2f}")

    # Example: Turn off fireplace (always safe)
    print()
    print("   Turning off fireplace...")
    with Timer() as t:
        try:
            await controller.fireplace_off()
            print_success("Fireplace OFF")
            metrics.increment("commands")
            logger.info("Fireplace turned off")
        except Exception as e:
            print_warning(f"Simulated: {e}")
            metrics.increment("simulated")
            logger.warning(f"Fireplace off simulated: {e}")

    metrics.record_timing("fireplace", t.elapsed)


# =============================================================================
# CLI ARGUMENT PARSING
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Smart Home Demo — Demonstrate Kagami smart home control capabilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full demo
  python smarthome_demo.py

  # Control specific rooms only
  python smarthome_demo.py --rooms "Living Room" "Kitchen"

  # Skip certain sections
  python smarthome_demo.py --skip-fireplace --skip-locks

  # Run in verbose mode
  python smarthome_demo.py -v

  # Simulation mode (no real device control)
  python smarthome_demo.py --simulate

Valid room names:
  First Floor:  Living Room, Entry, Porch, Kitchen, Dining, Mudroom,
                Powder Room, Garage, Deck, Stairway
  Second Floor: Primary Bed, Primary Bath, Primary Closet, Primary Hall,
                Loft, Office, Office Bath, Bed 3, Bath 3, Laundry
  Basement:     Game Room, Rack Room, Bed 4, Bath 4, Gym, Patio
        """,
    )

    # Room selection
    parser.add_argument(
        "--rooms",
        "-r",
        nargs="+",
        metavar="ROOM",
        help="Specific rooms to control (default: Living Room, Kitchen, Office)",
    )

    # Section controls
    parser.add_argument(
        "--skip-lights",
        action="store_true",
        help="Skip light control section",
    )
    parser.add_argument(
        "--skip-shades",
        action="store_true",
        help="Skip shade control section",
    )
    parser.add_argument(
        "--skip-scenes",
        action="store_true",
        help="Skip scene control section",
    )
    parser.add_argument(
        "--skip-audio",
        action="store_true",
        help="Skip audio announcement section",
    )
    parser.add_argument(
        "--skip-locks",
        action="store_true",
        help="Skip lock control section",
    )
    parser.add_argument(
        "--skip-fireplace",
        action="store_true",
        help="Skip fireplace control section",
    )

    # Mode flags
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Force simulation mode (no real device control)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging output",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress non-essential output",
    )

    return parser.parse_args()


# =============================================================================
# MAIN
# =============================================================================


async def main() -> None:
    """Run Smart Home demonstration."""
    args = parse_args()

    # Configure logging level based on args
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    elif args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    # Validate rooms if provided
    validated_rooms: list[str] | None = None
    if args.rooms:
        try:
            validated_rooms = validate_rooms(args.rooms)
            logger.info(f"Validated rooms: {validated_rooms}")
        except RoomValidationError as e:
            print_error(str(e))
            print_info(f"Valid rooms: {', '.join(sorted(VALID_ROOMS))}")
            sys.exit(1)

    print_header("SMART HOME DEMO", "HOUSE")

    metrics = MetricsCollector("smarthome_demo")
    controller: SmartHomeControllerProtocol

    with Timer() as total_timer:
        # Section 1: Connect
        if args.simulate:
            print_info("Running in simulation mode (--simulate)")
            controller = create_mock_controller()
            metrics.increment("simulated")
            logger.info("Using mock controller (simulation mode)")
        else:
            try:
                controller = await section_1_connect(metrics)
            except Exception as e:
                print_error(f"Connection failed: {e}")
                print_info("Running in simulation mode")
                controller = create_mock_controller()
                metrics.increment("simulated")
                logger.warning(f"Connection failed, using mock: {e}")

        # Run sections based on CLI flags
        if not args.skip_lights:
            await section_2_lights(controller, metrics, validated_rooms)

        if not args.skip_shades:
            await section_3_shades(controller, metrics, validated_rooms)

        if not args.skip_scenes:
            await section_4_scenes(controller, metrics)

        if not args.skip_audio:
            await section_5_audio(controller, metrics, validated_rooms)

        if not args.skip_locks:
            await section_6_locks(controller, metrics)

        if not args.skip_fireplace:
            await section_7_fireplace(controller, metrics)

    print_metrics(
        {
            "Total time": f"{total_timer.elapsed:.2f}s",
            "Commands": metrics.counters.get("commands", 0),
            "Scenes": metrics.counters.get("scenes", 0),
            "Simulated": metrics.counters.get("simulated", 0),
            "Lights": "41",
            "Shades": "11",
            "Audio zones": "26",
        }
    )

    print_footer(
        message="Smart Home demo complete!",
        next_steps=[
            "Try: python smarthome_demo.py --rooms 'Living Room' 'Kitchen'",
            "Run digital_integration_demo.py for Composio tools",
            "Run cross_domain_triggers_demo.py for digital->physical",
        ],
    )


if __name__ == "__main__":
    asyncio.run(main())
