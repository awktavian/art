"""Core User Journey End-to-End Tests.

Comprehensive tests for complete user journeys through the Kagami smart home:
- Morning Routine: Wake up, lights on, coffee machine
- Movie Night: Dim lights, lower shades, TV on
- Leaving Home: All off, lock doors, arm alarm
- Coming Home: Unlock, lights on, climate adjust
- Goodnight: All off, lock up, set alarm

Each journey tests the full integration chain with CBF safety validation.

Colony: Nexus (e4) - Connection and integration
Colony: Crystal (e7) - Verification and trust

h(x) >= 0. Always.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import pytest_asyncio

from tests.e2e.conftest import (
    MockDeviceConstellation,
    MockDevice,
    MockHub,
    DeviceType,
    ConnectionState,
    NetworkCondition,
    UserPersona,
    UserRole,
)

logger = logging.getLogger(__name__)

# Mark all tests in this module
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.user_journey,
    pytest.mark.asyncio,
]


# ==============================================================================
# USER JOURNEY FRAMEWORK
# ==============================================================================


@dataclass
class JourneyStep:
    """A single step in a user journey."""

    name: str
    action: Callable
    description: str
    expected_result: Any = True
    timeout_seconds: float = 5.0
    is_critical: bool = False  # If True, journey fails if step fails


@dataclass
class JourneyResult:
    """Result of a complete user journey."""

    journey_name: str
    success: bool
    steps_completed: int
    steps_total: int
    duration_seconds: float
    step_results: list[dict] = field(default_factory=list)
    safety_violations: int = 0
    min_safety_h: float = 1.0
    errors: list[str] = field(default_factory=list)


class UserJourneyRunner:
    """Framework for running and validating user journeys."""

    def __init__(
        self,
        controller: Any,
        constellation: MockDeviceConstellation,
        safety_filter: Any,
    ):
        self.controller = controller
        self.constellation = constellation
        self.safety_filter = safety_filter
        self.metrics: dict[str, Any] = {
            "total_journeys": 0,
            "successful_journeys": 0,
            "failed_journeys": 0,
            "total_steps": 0,
            "failed_steps": 0,
            "safety_violations": 0,
        }

    async def run_journey(
        self,
        journey_name: str,
        steps: list[JourneyStep],
        user: UserPersona | None = None,
    ) -> JourneyResult:
        """Run a complete user journey with safety validation."""
        logger.info(f"Starting journey: {journey_name}")
        start_time = time.time()

        result = JourneyResult(
            journey_name=journey_name,
            success=True,
            steps_completed=0,
            steps_total=len(steps),
            duration_seconds=0.0,
        )

        self.metrics["total_journeys"] += 1

        try:
            for i, step in enumerate(steps):
                step_result = await self._execute_step(step, i, journey_name, user)
                result.step_results.append(step_result)

                if step_result["success"]:
                    result.steps_completed += 1
                    self.metrics["total_steps"] += 1
                else:
                    self.metrics["failed_steps"] += 1
                    if step.is_critical:
                        result.success = False
                        result.errors.append(f"Critical step failed: {step.name}")
                        break

                # Track safety metrics
                if step_result.get("h_value", 1.0) < result.min_safety_h:
                    result.min_safety_h = step_result["h_value"]

                if step_result.get("safety_violation", False):
                    result.safety_violations += 1
                    self.metrics["safety_violations"] += 1

                # Brief pause between steps (Fibonacci timing)
                await asyncio.sleep(0.089)  # 89ms micro-interaction timing

        except Exception as e:
            result.success = False
            result.errors.append(f"Journey error: {str(e)}")
            logger.error(f"Journey {journey_name} failed: {e}")

        result.duration_seconds = time.time() - start_time

        if result.success:
            self.metrics["successful_journeys"] += 1
            logger.info(
                f"Journey {journey_name} completed successfully in {result.duration_seconds:.2f}s"
            )
        else:
            self.metrics["failed_journeys"] += 1
            logger.error(f"Journey {journey_name} failed: {result.errors}")

        return result

    async def _execute_step(
        self,
        step: JourneyStep,
        step_index: int,
        journey_name: str,
        user: UserPersona | None,
    ) -> dict[str, Any]:
        """Execute a single journey step with safety checks."""
        step_result = {
            "name": step.name,
            "description": step.description,
            "success": False,
            "h_value": 1.0,
            "safety_violation": False,
            "duration_ms": 0,
            "error": None,
        }

        start_time = time.time()

        try:
            # Pre-action safety check
            h_pre = self.safety_filter.evaluate_safety(
                {
                    "journey": journey_name,
                    "step": step_index,
                    "action": step.name,
                    "phase": "pre_action",
                    "user": user.to_dict() if user else None,
                }
            )

            # Execute the action
            if asyncio.iscoroutinefunction(step.action):
                result = await asyncio.wait_for(
                    step.action(),
                    timeout=step.timeout_seconds,
                )
            else:
                result = step.action()

            # Post-action safety check
            h_post = self.safety_filter.evaluate_safety(
                {
                    "journey": journey_name,
                    "step": step_index,
                    "action": step.name,
                    "result": result,
                    "phase": "post_action",
                    "user": user.to_dict() if user else None,
                }
            )

            step_result["h_value"] = min(h_pre, h_post)
            step_result["safety_violation"] = h_post < 0

            # Check expected result
            if step.expected_result is not None:
                step_result["success"] = result == step.expected_result or bool(result)
            else:
                step_result["success"] = True

            step_result["result"] = result

        except TimeoutError:
            step_result["error"] = f"Step timed out after {step.timeout_seconds}s"
            logger.warning(f"Step {step.name} timed out")
        except Exception as e:
            step_result["error"] = str(e)
            logger.error(f"Step {step.name} failed: {e}")

        step_result["duration_ms"] = (time.time() - start_time) * 1000
        return step_result


# ==============================================================================
# FIXTURES
# ==============================================================================


@pytest.fixture
def journey_runner(
    mock_smart_home_controller,
    mock_constellation: MockDeviceConstellation,
    mock_safety_filter,
) -> UserJourneyRunner:
    """Create a user journey runner with mocked dependencies."""
    return UserJourneyRunner(
        controller=mock_smart_home_controller,
        constellation=mock_constellation,
        safety_filter=mock_safety_filter,
    )


# ==============================================================================
# MORNING ROUTINE TESTS
# ==============================================================================


class TestMorningRoutine:
    """Test complete morning routine user journey."""

    async def test_morning_routine_weekday(
        self,
        journey_runner: UserJourneyRunner,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test weekday morning routine: wake up, lights, coffee, temperature."""
        controller = mock_smart_home_controller

        steps = [
            JourneyStep(
                name="bedroom_lights_gentle",
                action=lambda: controller.set_room_scene("Primary Bedroom", "morning"),
                description="Turn on gentle bedroom lighting for wake up",
                is_critical=True,
            ),
            JourneyStep(
                name="bedroom_shades_partial",
                action=lambda: controller.set_shades(25, ["Primary Bedroom"]),
                description="Open bedroom shades partially for natural light",
            ),
            JourneyStep(
                name="bedroom_temperature",
                action=lambda: controller.set_room_temp("Primary Bedroom", 72.0),
                description="Set comfortable bedroom temperature",
            ),
            JourneyStep(
                name="bathroom_prep",
                action=lambda: controller.set_room_scene("Primary Bathroom", "bright"),
                description="Prepare bathroom with bright lighting",
            ),
            JourneyStep(
                name="bathroom_heat",
                action=lambda: controller.set_room_temp("Primary Bathroom", 74.0),
                description="Pre-heat bathroom for comfort",
            ),
            JourneyStep(
                name="kitchen_lights",
                action=lambda: controller.set_room_scene("Kitchen", "morning"),
                description="Turn on kitchen lights",
            ),
            JourneyStep(
                name="kitchen_shades",
                action=lambda: controller.open_shades(["Kitchen"]),
                description="Open kitchen shades for natural light",
            ),
            JourneyStep(
                name="start_coffee",
                action=lambda: controller.start_coffee(),
                description="Start coffee machine",
            ),
            JourneyStep(
                name="office_prep",
                action=lambda: controller.set_room_scene("Office", "working"),
                description="Prepare office for work day",
            ),
            JourneyStep(
                name="disarm_security",
                action=lambda: controller.disarm_security(),
                description="Disarm overnight security",
            ),
            JourneyStep(
                name="morning_announcement",
                action=lambda: controller.announce(
                    "Good morning! Coffee is brewing.",
                    rooms=["Kitchen"],
                ),
                description="Morning greeting announcement",
            ),
        ]

        result = await journey_runner.run_journey(
            "morning_routine_weekday",
            steps,
            user=tim_persona,
        )

        assert result.success, f"Morning routine failed: {result.errors}"
        assert result.steps_completed >= 9, "Most steps should complete"
        assert result.min_safety_h >= 0, "Safety h(x) must be >= 0"
        assert result.safety_violations == 0, "No safety violations allowed"
        assert result.duration_seconds < 30, "Should complete in reasonable time"

    async def test_morning_routine_weekend(
        self,
        journey_runner: UserJourneyRunner,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test relaxed weekend morning routine."""
        controller = mock_smart_home_controller

        # Weekend is more relaxed
        steps = [
            JourneyStep(
                name="bedroom_lights_soft",
                action=lambda: controller.set_room_scene("Primary Bedroom", "relaxing"),
                description="Soft bedroom lighting for relaxed wake up",
            ),
            JourneyStep(
                name="bedroom_shades_partial",
                action=lambda: controller.set_shades(50, ["Primary Bedroom"]),
                description="Open shades partially for privacy",
            ),
            JourneyStep(
                name="living_room_prep",
                action=lambda: controller.set_room_scene("Living Room", "relaxing"),
                description="Prepare living room for relaxation",
            ),
            JourneyStep(
                name="kitchen_morning",
                action=lambda: controller.set_room_scene("Kitchen", "morning"),
                description="Kitchen lights for breakfast",
            ),
            JourneyStep(
                name="start_coffee",
                action=lambda: controller.start_coffee(),
                description="Start weekend coffee",
            ),
            JourneyStep(
                name="play_music",
                action=lambda: controller.spotify_play_playlist("weekend-morning"),
                description="Play relaxing weekend music",
            ),
        ]

        result = await journey_runner.run_journey(
            "morning_routine_weekend",
            steps,
            user=tim_persona,
        )

        assert result.success
        assert result.safety_violations == 0

    async def test_morning_routine_with_guest(
        self,
        journey_runner: UserJourneyRunner,
        mock_smart_home_controller,
        guest_persona: UserPersona,
    ):
        """Test morning routine with guest user - limited capabilities."""
        controller = mock_smart_home_controller

        # Guest has limited access
        steps = [
            JourneyStep(
                name="guest_room_lights",
                action=lambda: controller.set_room_scene("Guest Room", "morning"),
                description="Turn on guest room lights",
            ),
            JourneyStep(
                name="guest_bathroom",
                action=lambda: controller.set_room_scene("Guest Bathroom", "bright"),
                description="Prepare guest bathroom",
            ),
            # Guest cannot control security
            JourneyStep(
                name="check_security",
                action=lambda: controller.get_security_state(),
                description="Check security state (read-only for guest)",
            ),
        ]

        result = await journey_runner.run_journey(
            "morning_routine_guest",
            steps,
            user=guest_persona,
        )

        assert result.success
        assert result.safety_violations == 0


# ==============================================================================
# MOVIE NIGHT TESTS
# ==============================================================================


class TestMovieNight:
    """Test complete movie night user journey."""

    async def test_movie_night_setup(
        self,
        journey_runner: UserJourneyRunner,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test movie night setup: dim lights, lower shades, TV on."""
        controller = mock_smart_home_controller

        steps = [
            JourneyStep(
                name="dim_lights",
                action=lambda: controller.set_room_scene("Living Room", "movie"),
                description="Dim living room lights for movie watching",
                is_critical=True,
            ),
            JourneyStep(
                name="close_shades",
                action=lambda: controller.close_shades(["Living Room"]),
                description="Close shades to block outside light",
            ),
            JourneyStep(
                name="lower_tv",
                action=lambda: controller.lower_tv(1),  # Preset 1 = viewing position
                description="Lower TV from MantelMount to viewing position",
            ),
            JourneyStep(
                name="tv_on",
                action=lambda: controller.tv_on(),
                description="Turn on the TV",
            ),
            JourneyStep(
                name="set_climate",
                action=lambda: controller.set_room_temp("Living Room", 72.0),
                description="Set comfortable temperature for movie watching",
            ),
            JourneyStep(
                name="fireplace_ambiance",
                action=lambda: controller.fireplace_on(),
                description="Turn on fireplace for ambiance",
            ),
            JourneyStep(
                name="mute_other_zones",
                action=lambda: controller.mute_room("Kitchen", True),
                description="Mute audio in other rooms",
            ),
            JourneyStep(
                name="enter_movie_mode",
                action=lambda: controller.enter_movie_mode(),
                description="Activate full movie mode orchestration",
            ),
            JourneyStep(
                name="movie_ready_announcement",
                action=lambda: controller.announce(
                    "Movie mode ready. Enjoy the show!",
                    rooms=["Living Room"],
                ),
                description="Announce movie mode is ready",
            ),
        ]

        result = await journey_runner.run_journey(
            "movie_night_setup",
            steps,
            user=tim_persona,
        )

        assert result.success, f"Movie night setup failed: {result.errors}"
        assert result.steps_completed >= 7, "Most steps should complete"
        assert result.min_safety_h >= 0, "Safety must be maintained"

    async def test_movie_night_exit(
        self,
        journey_runner: UserJourneyRunner,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test exiting movie mode gracefully."""
        controller = mock_smart_home_controller

        steps = [
            JourneyStep(
                name="exit_movie_mode",
                action=lambda: controller.exit_movie_mode(),
                description="Exit movie mode orchestration",
            ),
            JourneyStep(
                name="raise_tv",
                action=lambda: controller.raise_tv(),
                description="Raise TV back to hidden position",
            ),
            JourneyStep(
                name="fireplace_off",
                action=lambda: controller.fireplace_off(),
                description="Turn off fireplace",
            ),
            JourneyStep(
                name="restore_lights",
                action=lambda: controller.set_room_scene("Living Room", "relaxing"),
                description="Restore normal lighting",
            ),
            JourneyStep(
                name="partial_shades",
                action=lambda: controller.set_shades(50, ["Living Room"]),
                description="Open shades partially",
            ),
            JourneyStep(
                name="unmute_zones",
                action=lambda: controller.mute_room("Kitchen", False),
                description="Unmute other audio zones",
            ),
        ]

        result = await journey_runner.run_journey(
            "movie_night_exit",
            steps,
            user=tim_persona,
        )

        assert result.success
        assert result.safety_violations == 0


# ==============================================================================
# LEAVING HOME TESTS
# ==============================================================================


class TestLeavingHome:
    """Test complete leaving home user journey."""

    async def test_leaving_home(
        self,
        journey_runner: UserJourneyRunner,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test leaving home: all off, lock doors, arm alarm."""
        controller = mock_smart_home_controller

        steps = [
            JourneyStep(
                name="turn_off_all_lights",
                action=lambda: controller.set_lights(0),
                description="Turn off all lights in the house",
                is_critical=True,
            ),
            JourneyStep(
                name="close_all_shades",
                action=lambda: controller.close_shades(),
                description="Close all window shades",
            ),
            JourneyStep(
                name="turn_off_tv",
                action=lambda: controller.tv_off(),
                description="Ensure TV is off",
            ),
            JourneyStep(
                name="fireplace_off",
                action=lambda: controller.fireplace_off(),
                description="Ensure fireplace is off",
            ),
            JourneyStep(
                name="set_away_hvac",
                action=lambda: controller.set_away_hvac(65.0),
                description="Set HVAC to energy-saving away mode",
            ),
            JourneyStep(
                name="pause_music",
                action=lambda: controller.spotify_pause(),
                description="Pause any playing music",
            ),
            JourneyStep(
                name="lock_all_doors",
                action=lambda: controller.lock_all(),
                description="Lock all entry doors",
                is_critical=True,
            ),
            JourneyStep(
                name="verify_locks",
                action=lambda: controller.get_lock_states(),
                description="Verify all doors are locked",
            ),
            JourneyStep(
                name="arm_security_away",
                action=lambda: controller.arm_security("away"),
                description="Arm security system in away mode",
                is_critical=True,
            ),
            JourneyStep(
                name="activate_away_mode",
                action=lambda: controller.set_away_mode(),
                description="Activate full away mode orchestration",
            ),
            JourneyStep(
                name="departure_announcement",
                action=lambda: controller.announce(
                    "Home secured. Have a great day!",
                    rooms=["Entry"],
                ),
                description="Departure confirmation announcement",
            ),
        ]

        result = await journey_runner.run_journey(
            "leaving_home",
            steps,
            user=tim_persona,
        )

        assert result.success, f"Leaving home failed: {result.errors}"
        assert result.steps_completed >= 9, "Most steps should complete"
        assert result.min_safety_h >= 0, "Safety must be maintained"
        assert result.safety_violations == 0, "No safety violations allowed"

        # Verify critical security steps completed
        critical_steps = ["turn_off_all_lights", "lock_all_doors", "arm_security_away"]
        completed_steps = [r["name"] for r in result.step_results if r["success"]]
        for step_name in critical_steps:
            assert step_name in completed_steps, f"Critical step {step_name} must complete"


# ==============================================================================
# COMING HOME TESTS
# ==============================================================================


class TestComingHome:
    """Test complete coming home user journey."""

    async def test_coming_home(
        self,
        journey_runner: UserJourneyRunner,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test coming home: unlock, lights on, climate adjust."""
        controller = mock_smart_home_controller

        steps = [
            JourneyStep(
                name="disarm_security",
                action=lambda: controller.disarm_security(),
                description="Disarm security system",
                is_critical=True,
            ),
            JourneyStep(
                name="unlock_front_door",
                action=lambda: controller.unlock_door("front_door"),
                description="Unlock front door",
            ),
            JourneyStep(
                name="entry_lights",
                action=lambda: controller.set_room_scene("Entry", "bright"),
                description="Turn on entry lights",
            ),
            JourneyStep(
                name="living_room_lights",
                action=lambda: controller.set_room_scene("Living Room", "relaxing"),
                description="Turn on living room lights",
            ),
            JourneyStep(
                name="kitchen_lights",
                action=lambda: controller.set_room_scene("Kitchen", "cooking"),
                description="Turn on kitchen lights",
            ),
            JourneyStep(
                name="open_main_shades",
                action=lambda: controller.open_shades(["Living Room", "Kitchen"]),
                description="Open main room shades",
            ),
            JourneyStep(
                name="set_comfort_temp",
                action=lambda: controller.set_room_temp("Living Room", 72.0),
                description="Set comfortable temperature",
            ),
            JourneyStep(
                name="outdoor_welcome",
                action=lambda: controller.outdoor_welcome(),
                description="Activate outdoor welcome lighting",
            ),
            JourneyStep(
                name="welcome_home_scene",
                action=lambda: controller.welcome_home(),
                description="Execute welcome home orchestration",
            ),
            JourneyStep(
                name="welcome_announcement",
                action=lambda: controller.announce(
                    "Welcome home! Everything is ready for you.",
                    rooms=["Entry", "Living Room"],
                ),
                description="Welcome home announcement",
            ),
        ]

        result = await journey_runner.run_journey(
            "coming_home",
            steps,
            user=tim_persona,
        )

        assert result.success, f"Coming home failed: {result.errors}"
        assert result.steps_completed >= 8, "Most steps should complete"
        assert result.min_safety_h >= 0, "Safety must be maintained"

    async def test_coming_home_evening(
        self,
        journey_runner: UserJourneyRunner,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test coming home in the evening with different lighting."""
        controller = mock_smart_home_controller

        steps = [
            JourneyStep(
                name="disarm_security",
                action=lambda: controller.disarm_security(),
                description="Disarm security",
            ),
            JourneyStep(
                name="evening_entry",
                action=lambda: controller.set_room_scene("Entry", "evening"),
                description="Evening entry lighting",
            ),
            JourneyStep(
                name="evening_living",
                action=lambda: controller.set_room_scene("Living Room", "evening"),
                description="Warm evening lighting for living room",
            ),
            JourneyStep(
                name="outdoor_evening",
                action=lambda: controller.outdoor_lights_on(),
                description="Turn on outdoor lights",
            ),
            JourneyStep(
                name="climate_comfort",
                action=lambda: controller.set_room_temp("Living Room", 71.0),
                description="Evening comfort temperature",
            ),
        ]

        result = await journey_runner.run_journey(
            "coming_home_evening",
            steps,
            user=tim_persona,
        )

        assert result.success


# ==============================================================================
# GOODNIGHT TESTS
# ==============================================================================


class TestGoodnight:
    """Test complete goodnight user journey."""

    async def test_goodnight_routine(
        self,
        journey_runner: UserJourneyRunner,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test goodnight routine: all off, lock up, set alarm."""
        controller = mock_smart_home_controller

        steps = [
            JourneyStep(
                name="lock_all_doors",
                action=lambda: controller.lock_all(),
                description="Lock all entry doors",
                is_critical=True,
            ),
            JourneyStep(
                name="verify_locks",
                action=lambda: controller.get_lock_states(),
                description="Verify all doors are locked",
            ),
            JourneyStep(
                name="close_all_shades",
                action=lambda: controller.close_shades(),
                description="Close all window shades",
            ),
            JourneyStep(
                name="turn_off_main_lights",
                action=lambda: controller.set_lights(
                    0,
                    rooms=["Living Room", "Kitchen", "Dining Room", "Office"],
                ),
                description="Turn off main area lights",
            ),
            JourneyStep(
                name="bedroom_sleep_scene",
                action=lambda: controller.set_room_scene("Primary Bedroom", "sleep"),
                description="Set bedroom to sleep lighting",
            ),
            JourneyStep(
                name="set_sleep_temperature",
                action=lambda: controller.set_room_temp("Primary Bedroom", 68.0),
                description="Set cool sleeping temperature",
            ),
            JourneyStep(
                name="set_bed_temperature",
                action=lambda: controller.set_bed_temperature(-3, "both"),
                description="Set Eight Sleep bed to cool",
            ),
            JourneyStep(
                name="outdoor_lights_off",
                action=lambda: controller.outdoor_lights_off(),
                description="Turn off outdoor lights",
            ),
            JourneyStep(
                name="arm_security_stay",
                action=lambda: controller.arm_security("stay"),
                description="Arm security in stay mode",
                is_critical=True,
            ),
            JourneyStep(
                name="bedroom_lights_off",
                action=lambda: controller.set_lights(0, rooms=["Primary Bedroom"]),
                description="Turn off bedroom lights completely",
            ),
            JourneyStep(
                name="goodnight_scene",
                action=lambda: controller.goodnight(),
                description="Execute goodnight orchestration",
            ),
            JourneyStep(
                name="goodnight_announcement",
                action=lambda: controller.announce(
                    "Good night. Sleep well.",
                    rooms=["Primary Bedroom"],
                ),
                description="Goodnight announcement",
            ),
        ]

        result = await journey_runner.run_journey(
            "goodnight_routine",
            steps,
            user=tim_persona,
        )

        assert result.success, f"Goodnight routine failed: {result.errors}"
        assert result.steps_completed >= 10, "Most steps should complete"
        assert result.min_safety_h >= 0, "Safety must be maintained"
        assert result.safety_violations == 0, "No safety violations allowed"

        # Verify critical security steps
        critical_steps = ["lock_all_doors", "arm_security_stay"]
        completed_steps = [r["name"] for r in result.step_results if r["success"]]
        for step_name in critical_steps:
            assert step_name in completed_steps, f"Critical step {step_name} must complete"

    async def test_goodnight_with_guest(
        self,
        journey_runner: UserJourneyRunner,
        mock_smart_home_controller,
        tim_persona: UserPersona,
        kristi_persona: UserPersona,
    ):
        """Test goodnight with guest staying over - considers multiple people."""
        controller = mock_smart_home_controller

        # Guest is present
        kristi_persona.presence_home = True
        kristi_persona.current_room = "Guest Room"

        steps = [
            JourneyStep(
                name="lock_all_doors",
                action=lambda: controller.lock_all(),
                description="Lock all doors",
            ),
            JourneyStep(
                name="main_lights_off",
                action=lambda: controller.set_lights(
                    0,
                    rooms=["Living Room", "Kitchen", "Dining Room"],
                ),
                description="Turn off common area lights",
            ),
            # Don't turn off guest room lights - let guest control
            JourneyStep(
                name="bedroom_sleep",
                action=lambda: controller.set_room_scene("Primary Bedroom", "sleep"),
                description="Set master bedroom for sleep",
            ),
            JourneyStep(
                name="guest_notification",
                action=lambda: controller.announce(
                    "Good night. Guest controls in your room.",
                    rooms=["Guest Room"],
                ),
                description="Notify guest of goodnight mode",
            ),
            JourneyStep(
                name="arm_security_stay",
                action=lambda: controller.arm_security("stay"),
                description="Arm in stay mode for residents",
            ),
        ]

        result = await journey_runner.run_journey(
            "goodnight_with_guest",
            steps,
            user=tim_persona,
        )

        assert result.success


# ==============================================================================
# EDGE CASE AND FAILURE TESTS
# ==============================================================================


class TestJourneyEdgeCases:
    """Test edge cases and failure scenarios in user journeys."""

    async def test_morning_routine_with_failures(
        self,
        journey_runner: UserJourneyRunner,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test morning routine when some devices fail."""
        controller = mock_smart_home_controller

        # Simulate coffee machine failure
        controller.start_coffee = AsyncMock(side_effect=Exception("Coffee machine offline"))

        steps = [
            JourneyStep(
                name="bedroom_lights",
                action=lambda: controller.set_room_scene("Primary Bedroom", "morning"),
                description="Turn on bedroom lights",
                is_critical=True,
            ),
            JourneyStep(
                name="start_coffee",
                action=lambda: controller.start_coffee(),
                description="Start coffee - expected to fail",
                is_critical=False,  # Not critical - journey should continue
            ),
            JourneyStep(
                name="kitchen_lights",
                action=lambda: controller.set_room_scene("Kitchen", "morning"),
                description="Kitchen lights should still work",
            ),
        ]

        result = await journey_runner.run_journey(
            "morning_routine_with_failures",
            steps,
            user=tim_persona,
        )

        # Journey should complete despite coffee machine failure
        assert result.success, "Non-critical failures should not stop journey"
        assert result.steps_completed >= 2, "Non-critical step failure should allow continuation"

    async def test_leaving_home_security_failure_is_critical(
        self,
        journey_runner: UserJourneyRunner,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test that security failures in leaving home are handled appropriately."""
        controller = mock_smart_home_controller

        # Create a failing async mock for lock_all
        async def failing_lock():
            raise Exception("Lock communication error")

        steps = [
            JourneyStep(
                name="lights_off",
                action=lambda: controller.set_lights(0),
                description="Turn off lights",
            ),
            JourneyStep(
                name="lock_all",
                action=failing_lock,  # Directly use the failing function
                description="Lock doors - will fail",
                is_critical=True,  # Critical step!
            ),
            JourneyStep(
                name="arm_security",
                action=lambda: controller.arm_security("away"),
                description="Should not reach this step",
            ),
        ]

        result = await journey_runner.run_journey(
            "leaving_home_security_failure",
            steps,
            user=tim_persona,
        )

        # Journey should fail because critical step failed
        assert not result.success, "Critical step failure should fail journey"
        assert "Critical step failed" in result.errors[0]

    async def test_journey_timeout_handling(
        self,
        journey_runner: UserJourneyRunner,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test that step timeouts are handled gracefully."""
        controller = mock_smart_home_controller

        # Simulate a very slow operation (takes any args)
        async def slow_operation(*args, **kwargs):
            await asyncio.sleep(10)  # 10 seconds
            return True

        steps = [
            JourneyStep(
                name="slow_lights",
                action=slow_operation,  # Directly use the slow function
                description="Slow light operation - should timeout",
                timeout_seconds=1.0,  # 1 second timeout
                is_critical=False,
            ),
            JourneyStep(
                name="next_step",
                action=lambda: controller.close_shades(),
                description="This should still run",
            ),
        ]

        result = await journey_runner.run_journey(
            "journey_with_timeout",
            steps,
            user=tim_persona,
        )

        # First step should have timed out
        first_step = result.step_results[0]
        assert not first_step["success"]
        assert "timed out" in first_step["error"]

        # Journey should continue
        assert result.steps_completed >= 1


# ==============================================================================
# PERFORMANCE TESTS
# ==============================================================================


class TestJourneyPerformance:
    """Test user journey performance characteristics."""

    async def test_journey_completes_in_reasonable_time(
        self,
        journey_runner: UserJourneyRunner,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test that journeys complete within expected timeframes."""
        controller = mock_smart_home_controller

        # Quick journey with many steps
        steps = [
            JourneyStep(
                name=f"step_{i}",
                action=lambda: controller.set_lights(i),
                description=f"Step {i}",
            )
            for i in range(10)
        ]

        result = await journey_runner.run_journey(
            "performance_test",
            steps,
            user=tim_persona,
        )

        assert result.success
        assert result.duration_seconds < 10, "10 steps should complete in < 10 seconds"

        # Check individual step timing
        for step_result in result.step_results:
            assert step_result["duration_ms"] < 1000, "Each step should be < 1 second"

    async def test_concurrent_journeys(
        self,
        mock_smart_home_controller,
        mock_constellation: MockDeviceConstellation,
        mock_safety_filter,
        tim_persona: UserPersona,
    ):
        """Test running multiple journeys concurrently."""
        controller = mock_smart_home_controller

        # Create multiple runners
        runners = [
            UserJourneyRunner(controller, mock_constellation, mock_safety_filter) for _ in range(3)
        ]

        # Define quick journeys
        def create_steps(prefix: str):
            return [
                JourneyStep(
                    name=f"{prefix}_step_{i}",
                    action=lambda: controller.set_lights(i),
                    description=f"{prefix} step {i}",
                )
                for i in range(5)
            ]

        # Run concurrently
        tasks = [
            runner.run_journey(f"concurrent_{i}", create_steps(f"journey_{i}"), tim_persona)
            for i, runner in enumerate(runners)
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        for result in results:
            assert result.success, f"Concurrent journey failed: {result.errors}"


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
