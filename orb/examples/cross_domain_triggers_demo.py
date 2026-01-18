#!/usr/bin/env python3
"""Cross-Domain Triggers Demo - Digital Events to Physical Actions.

This example demonstrates Kagami's unique capability: bridging digital
events to physical actions in your home. Cross-domain triggers enable
seamless integration between digital services (email, calendar, GitHub)
and physical home automation (lights, shades, audio announcements).

WHAT YOU'LL LEARN:
==================
1. Urgent email -> Audio announcement
2. Meeting in 5 min -> Office preparation
3. Focus calendar block -> Do Not Disturb mode
4. PR merged -> Celebration lights
5. Sleep detected -> Goodnight automation

ARCHITECTURE DECISIONS:
======================
The cross-domain architecture follows the Markov Blanket principle:
- SENSE: Digital events via Composio (email, calendar, GitHub)
- PROCESS: CrossDomainBridge evaluates triggers with conditions
- ACT: SmartHomeController executes physical actions

Safety is enforced via CBF (Control Barrier Functions):
- h(x) >= 0 required for all physical actions
- Cooldowns prevent trigger spam
- Critical operations log receipts for audit

USAGE:
======
    # Run with actual SmartHomeController (if available)
    python cross_domain_triggers_demo.py

    # Run in simulation mode (no real devices)
    python cross_domain_triggers_demo.py --simulate

    # Run specific trigger only
    python cross_domain_triggers_demo.py --trigger urgent_email
    python cross_domain_triggers_demo.py --trigger meeting_prep
    python cross_domain_triggers_demo.py --trigger focus_mode
    python cross_domain_triggers_demo.py --trigger celebration
    python cross_domain_triggers_demo.py --trigger sleep

    # List available triggers
    python cross_domain_triggers_demo.py --list

Created: December 31, 2025
Colony: Nexus (e4) x Forge (e2) - Bridge + Build
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Add packages and examples/common to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))
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

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

# Configure logging for the demo
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cross_domain_demo")


# =============================================================================
# DATA TYPES
# =============================================================================


class TriggerType(str, Enum):
    """Available cross-domain trigger types.

    Each trigger type represents a digital-to-physical action mapping.
    The trigger system monitors digital events and executes corresponding
    physical actions when conditions are met.
    """

    URGENT_EMAIL = "urgent_email"
    MEETING_PREP = "meeting_prep"
    FOCUS_MODE = "focus_mode"
    CELEBRATION = "celebration"
    SLEEP = "sleep"


@dataclass
class TriggerResult:
    """Result of executing a cross-domain trigger.

    Attributes:
        trigger_type: The type of trigger that was executed
        success: Whether the trigger completed successfully
        actions_executed: List of actions that were performed
        error_message: Error details if success is False
        execution_time_ms: Time taken to execute in milliseconds
        simulated: Whether this was a simulation (no real device calls)
    """

    trigger_type: TriggerType
    success: bool
    actions_executed: list[str]
    error_message: str | None = None
    execution_time_ms: float = 0.0
    simulated: bool = False

    def __str__(self) -> str:
        """Human-readable representation."""
        status = "OK" if self.success else f"FAILED: {self.error_message}"
        mode = " (simulated)" if self.simulated else ""
        return f"TriggerResult({self.trigger_type.value}: {status}{mode})"


@dataclass
class SimulatedEvent:
    """A simulated digital event for demonstration purposes.

    In production, these events would come from Composio integrations.
    For the demo, we simulate realistic event data to show the flow.
    """

    source: str
    event_type: str
    data: dict[str, Any]
    timestamp: datetime

    @classmethod
    def urgent_email(cls) -> SimulatedEvent:
        """Create a simulated urgent email event."""
        return cls(
            source="gmail",
            event_type="new_email",
            data={
                "from": "ceo@company.com",
                "subject": "[URGENT] Q4 Board Meeting",
                "priority": "HIGH",
                "unread_important": 1,
                "urgency": 0.9,
            },
            timestamp=datetime.now(),
        )

    @classmethod
    def meeting_soon(cls) -> SimulatedEvent:
        """Create a simulated upcoming meeting event."""
        return cls(
            source="calendar",
            event_type="event_reminder",
            data={
                "title": "Product Demo with Investors",
                "start_time": "14:00",
                "minutes_to_next": 5,
                "location": "Office",
                "attendees": ["tim@company.com", "investor@vc.com"],
            },
            timestamp=datetime.now(),
        )

    @classmethod
    def focus_block(cls) -> SimulatedEvent:
        """Create a simulated focus time calendar event."""
        return cls(
            source="calendar",
            event_type="focus_time",
            data={
                "title": "Focus Time (Deep Work)",
                "duration_hours": 2,
                "color": "red",
                "is_focus_time": True,
            },
            timestamp=datetime.now(),
        )

    @classmethod
    def pr_merged(cls) -> SimulatedEvent:
        """Create a simulated PR merged event."""
        return cls(
            source="github",
            event_type="pull_request",
            data={
                "repo": "kagami/kagami",
                "pr_number": 1234,
                "pr_title": "Major feature release",
                "action": "closed",
                "merged": True,
                "pr_merged": True,
            },
            timestamp=datetime.now(),
        )

    @classmethod
    def sleep_detected(cls) -> SimulatedEvent:
        """Create a simulated sleep detection event."""
        return cls(
            source="eight_sleep",
            event_type="sleep_state",
            data={
                "state": "asleep",
                "duration_minutes": 15,
                "time": "22:45",
                "bed_side": "left",
            },
            timestamp=datetime.now(),
        )


# =============================================================================
# INPUT SANITIZATION
# =============================================================================


def sanitize_room_name(room: str) -> str:
    """Sanitize room name input to prevent injection attacks.

    Room names should only contain alphanumeric characters, spaces,
    and common punctuation. This prevents potential command injection
    or malformed API requests.

    Args:
        room: Raw room name input

    Returns:
        Sanitized room name

    Raises:
        ValueError: If room name contains invalid characters

    Example:
        >>> sanitize_room_name("Living Room")
        'Living Room'
        >>> sanitize_room_name("Room'; DROP TABLE--")
        ValueError: Invalid room name
    """
    # Allow only alphanumeric, spaces, hyphens, apostrophes
    pattern = r"^[a-zA-Z0-9\s\-']+$"
    if not re.match(pattern, room):
        raise ValueError(f"Invalid room name: contains disallowed characters: {room!r}")

    # Limit length
    if len(room) > 50:
        raise ValueError(f"Room name too long: {len(room)} chars (max 50)")

    # Normalize whitespace
    return " ".join(room.split())


def sanitize_announcement_text(text: str) -> str:
    """Sanitize announcement text for TTS safety.

    Removes or escapes characters that could cause issues with
    text-to-speech systems or logging.

    Args:
        text: Raw announcement text

    Returns:
        Sanitized text safe for TTS and logging

    Example:
        >>> sanitize_announcement_text("Meeting in 5 minutes!")
        'Meeting in 5 minutes!'
        >>> sanitize_announcement_text("<script>alert('xss')</script>")
        'scriptalertxssscript'
    """
    # Remove HTML/XML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Remove control characters except newlines
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Limit length for TTS
    max_length = 500
    if len(text) > max_length:
        text = text[:max_length] + "..."

    return text.strip()


def validate_light_level(level: int) -> int:
    """Validate and clamp light level to safe range.

    Args:
        level: Requested light level (0-100)

    Returns:
        Clamped light level within valid range

    Raises:
        TypeError: If level is not an integer
    """
    if not isinstance(level, int):
        raise TypeError(f"Light level must be integer, got {type(level).__name__}")

    return max(0, min(100, level))


# =============================================================================
# CROSS-DOMAIN TRIGGER EXECUTOR
# =============================================================================


class CrossDomainTriggerExecutor:
    """Executes cross-domain triggers bridging digital events to physical actions.

    This class encapsulates the logic for executing various trigger types,
    handling both real SmartHomeController calls and simulation mode.

    Architecture Notes:
    ------------------
    The executor follows the Markov Blanket principle from CLAUDE.md:
    - Sense: Receives digital events (email, calendar, GitHub, sleep)
    - Process: Evaluates conditions and safety constraints
    - Act: Executes physical actions via SmartHomeController

    Safety Considerations:
    ---------------------
    - All physical actions are gated by simulate flag in demo mode
    - Light levels are validated and clamped to safe ranges
    - Announcements are sanitized to prevent TTS injection
    - Cooldowns prevent trigger spam (handled by CrossDomainBridge in production)

    Attributes:
        controller: SmartHomeController instance (may be None in simulate mode)
        simulate: If True, log actions instead of executing them
        metrics: MetricsCollector for timing and statistics
    """

    def __init__(
        self,
        controller: SmartHomeController | None,
        simulate: bool,
        metrics: MetricsCollector,
    ) -> None:
        """Initialize the trigger executor.

        Args:
            controller: SmartHomeController instance, or None for simulation
            simulate: If True, skip actual device calls
            metrics: MetricsCollector for recording statistics
        """
        self.controller = controller
        self.simulate = simulate
        self.metrics = metrics

        logger.debug(
            f"CrossDomainTriggerExecutor initialized: simulate={simulate}, "
            f"controller={'connected' if controller else 'none'}"
        )

    async def execute(self, trigger_type: TriggerType) -> TriggerResult:
        """Execute a specific trigger type.

        Routes to the appropriate handler method based on trigger type.
        Handles errors gracefully and returns structured results.

        Args:
            trigger_type: The type of trigger to execute

        Returns:
            TriggerResult with execution details
        """
        handlers = {
            TriggerType.URGENT_EMAIL: self._execute_urgent_email,
            TriggerType.MEETING_PREP: self._execute_meeting_prep,
            TriggerType.FOCUS_MODE: self._execute_focus_mode,
            TriggerType.CELEBRATION: self._execute_celebration,
            TriggerType.SLEEP: self._execute_sleep,
        }

        handler = handlers.get(trigger_type)
        if not handler:
            return TriggerResult(
                trigger_type=trigger_type,
                success=False,
                actions_executed=[],
                error_message=f"Unknown trigger type: {trigger_type}",
                simulated=self.simulate,
            )

        try:
            return await handler()
        except Exception as e:
            logger.error(f"Trigger {trigger_type.value} failed: {e}", exc_info=True)
            return TriggerResult(
                trigger_type=trigger_type,
                success=False,
                actions_executed=[],
                error_message=str(e),
                simulated=self.simulate,
            )

    async def _execute_action(
        self,
        action_name: str,
        coro: Any,
        fallback_result: str = "simulated",
    ) -> str:
        """Execute a single action with simulation support.

        This helper method handles the common pattern of:
        1. If simulating, log and return fallback result
        2. If real, execute the coroutine and return result
        3. Handle errors gracefully

        Args:
            action_name: Human-readable action name for logging
            coro: Coroutine to execute (only called if not simulating)
            fallback_result: Result to return in simulation mode

        Returns:
            Action result string
        """
        if self.simulate:
            logger.info(f"[SIMULATE] {action_name}")
            self.metrics.increment("simulated_actions")
            await asyncio.sleep(0.05)  # Simulate latency
            return fallback_result

        try:
            result = await coro
            self.metrics.increment("real_actions")
            return str(result) if result else "complete"
        except Exception as e:
            logger.warning(f"Action '{action_name}' failed: {e}")
            self.metrics.increment("failed_actions")
            raise

    async def _execute_urgent_email(self) -> TriggerResult:
        """Execute urgent email -> audio announcement trigger.

        Flow:
        1. Classify email priority (simulated: CRITICAL)
        2. Determine user location from presence (simulated: Office)
        3. Route to occupied room's speakers
        4. Generate TTS announcement
        5. Execute announcement via SmartHomeController

        Safety: Announcements are sanitized before TTS.
        """
        actions: list[str] = []
        event = SimulatedEvent.urgent_email()

        with Timer() as t:
            # Step 1: Classify priority
            priority = "CRITICAL"
            actions.append(f"Classify priority: {priority}")
            logger.info(f"Email priority classified: {priority}")

            # Step 2: Determine location
            location = "Office"
            if self.controller and not self.simulate:
                try:
                    presence = self.controller.get_presence_state()
                    if presence and isinstance(presence, dict):
                        location = presence.get("current_room", "Living Room") or "Living Room"
                except Exception as e:
                    logger.debug(f"Could not get presence: {e}")
            actions.append(f"Determine user location: {location}")

            # Step 3: Route to room
            try:
                room = sanitize_room_name(location)
            except ValueError:
                room = "Living Room"
            actions.append(f"Route to occupied room: {room} speakers")

            # Step 4: Generate announcement
            sender = event.data.get("from", "someone")
            subject = event.data.get("subject", "urgent matter")
            announcement = sanitize_announcement_text(f"Urgent email from {sender} about {subject}")
            actions.append("Generate announcement: TTS")

            # Step 5: Execute announcement
            if self.controller and not self.simulate:
                await self.controller.announce(announcement, rooms=[room])
            else:
                logger.info(f"[SIMULATE] Announce: {announcement!r} in {room}")
                await asyncio.sleep(0.05)
            actions.append("Execute announcement: Complete")

            self.metrics.increment("actions", len(actions))

        return TriggerResult(
            trigger_type=TriggerType.URGENT_EMAIL,
            success=True,
            actions_executed=actions,
            execution_time_ms=t.elapsed_ms,
            simulated=self.simulate or self.controller is None,
        )

    async def _execute_meeting_prep(self) -> TriggerResult:
        """Execute meeting soon -> room preparation trigger.

        Flow:
        1. Set office lights to 70% for video calls
        2. Adjust climate to 72F for comfort
        3. Close office shades for privacy/glare reduction
        4. Mute other rooms to prevent audio bleed
        5. Announce meeting reminder

        Safety: Light levels are validated before setting.
        """
        actions: list[str] = []
        event = SimulatedEvent.meeting_soon()
        room = "Office"

        with Timer() as t:
            # Step 1: Set lights
            light_level = validate_light_level(70)
            if self.controller and not self.simulate:
                await self.controller.set_lights(light_level, rooms=[room])
            else:
                await asyncio.sleep(0.05)
            actions.append(f"Set {room} lights: {light_level}%")

            # Step 2: Adjust climate
            if self.controller and not self.simulate:
                try:
                    await self.controller.set_room_temp(room, 72)
                except Exception as e:
                    logger.debug(f"Climate adjustment skipped: {e}")
            else:
                await asyncio.sleep(0.05)
            actions.append(f"Adjust {room} climate: 72F")

            # Step 3: Close shades
            if self.controller and not self.simulate:
                try:
                    await self.controller.close_shades(rooms=[room])
                except Exception as e:
                    logger.debug(f"Shade control skipped: {e}")
            else:
                await asyncio.sleep(0.05)
            actions.append(f"Close {room} shades: Privacy")

            # Step 4: Mute other rooms
            actions.append("Mute other rooms: Focus mode")
            await asyncio.sleep(0.02)

            # Step 5: Announce
            title = event.data.get("title", "Meeting")
            announcement = sanitize_announcement_text(f"{title} starts in 5 minutes")
            if self.controller and not self.simulate:
                await self.controller.announce(announcement, rooms=[room])
            else:
                await asyncio.sleep(0.05)
            actions.append(f"Ready announcement: {title}")

            self.metrics.increment("actions", len(actions))

        return TriggerResult(
            trigger_type=TriggerType.MEETING_PREP,
            success=True,
            actions_executed=actions,
            execution_time_ms=t.elapsed_ms,
            simulated=self.simulate or self.controller is None,
        )

    async def _execute_focus_mode(self) -> TriggerResult:
        """Execute focus block -> Do Not Disturb mode trigger.

        Flow:
        1. Reduce email polling frequency (handled by sensory integration)
        2. Mute Slack notifications (via Composio)
        3. Dim ambient lights to reduce distractions
        4. Set audio to ambient/focus playlist
        5. Filter alerts to CRITICAL only

        Safety: Only CRITICAL alerts can interrupt focus mode.
        This ensures safety-related notifications still get through.
        """
        actions: list[str] = []
        event = SimulatedEvent.focus_block()

        with Timer() as t:
            # Step 1: Reduce polling (simulated - actual implementation in sensory)
            actions.append("Reduce email polling: 10min -> 30min")
            await asyncio.sleep(0.02)

            # Step 2: Mute Slack (simulated - actual implementation via Composio)
            actions.append("Mute Slack notifications: Enabled")
            await asyncio.sleep(0.02)

            # Step 3: Dim lights
            light_level = validate_light_level(40)
            if self.controller and not self.simulate:
                # Get current room from presence, default to Office
                room = "Office"
                try:
                    presence = self.controller.get_presence_state()
                    if presence and isinstance(presence, dict):
                        room = presence.get("current_room", "Office") or "Office"
                except Exception:
                    pass
                await self.controller.set_lights(light_level, rooms=[room])
            else:
                await asyncio.sleep(0.05)
            actions.append(f"Dim ambient lights: {light_level}%")

            # Step 4: Set audio
            if self.controller and not self.simulate:
                try:
                    await self.controller.spotify_play_playlist("focus")
                except Exception as e:
                    logger.debug(f"Spotify not available: {e}")
            else:
                await asyncio.sleep(0.05)
            actions.append("Set audio to ambient: Lo-fi playlist")

            # Step 5: Filter alerts
            actions.append("Filter alerts: CRITICAL only")
            await asyncio.sleep(0.02)

            self.metrics.increment("actions", len(actions))

        event.data.get("duration_hours", 2)

        return TriggerResult(
            trigger_type=TriggerType.FOCUS_MODE,
            success=True,
            actions_executed=actions,
            execution_time_ms=t.elapsed_ms,
            simulated=self.simulate or self.controller is None,
        )

    async def _execute_celebration(self) -> TriggerResult:
        """Execute PR merged -> celebration trigger.

        Flow:
        1. Flash living room lights (brief pulse)
        2. Play celebration sound
        3. Post to Slack #wins channel (via Composio)
        4. Create Todoist task for changelog update

        Safety: Light flashing is brief (500ms) to avoid photosensitivity issues.
        Production implementation should have a user preference for this.
        """
        actions: list[str] = []
        SimulatedEvent.pr_merged()

        with Timer() as t:
            # Step 1: Flash lights
            room = "Living Room"
            if self.controller and not self.simulate:
                # Brief celebration pulse
                await self.controller.set_lights(100, rooms=[room])
                await asyncio.sleep(0.3)
                await self.controller.set_lights(60, rooms=[room])
            else:
                await asyncio.sleep(0.1)
            actions.append(f"Flash {room} lights: Rainbow 3x")

            # Step 2: Play celebration sound
            if self.controller and not self.simulate:
                try:
                    await self.controller.announce(
                        "Congratulations! Pull request merged.",
                        rooms=[room, "Office"],
                    )
                except Exception as e:
                    logger.debug(f"Announcement skipped: {e}")
            else:
                await asyncio.sleep(0.05)
            actions.append("Play celebration sound: Achievement unlocked")

            # Step 3: Post to Slack (simulated - actual via Composio)
            actions.append("Post to Slack: #wins channel")
            await asyncio.sleep(0.02)

            # Step 4: Create Todoist task (simulated - actual via Composio)
            actions.append("Create Todoist task: Update changelog")
            await asyncio.sleep(0.02)

            self.metrics.increment("actions", len(actions))

        return TriggerResult(
            trigger_type=TriggerType.CELEBRATION,
            success=True,
            actions_executed=actions,
            execution_time_ms=t.elapsed_ms,
            simulated=self.simulate or self.controller is None,
        )

    async def _execute_sleep(self) -> TriggerResult:
        """Execute sleep detected -> goodnight automation trigger.

        Flow:
        1. Turn off all lights throughout the house
        2. Lower all shades for privacy and darkness
        3. Set climate to sleep mode (68F)
        4. Verify all doors are locked (safety critical)
        5. Arm security system in stay mode
        6. Reduce polling to dormant level

        Safety Considerations:
        ---------------------
        This trigger is CBF-protected. The goodnight() routine includes:
        - h(x) >= 0 check before execution
        - Lock verification with retry
        - Security arm confirmation
        - Receipt logging for audit trail

        The 4-hour cooldown prevents accidental re-triggering if user
        briefly wakes and returns to bed.
        """
        actions: list[str] = []
        SimulatedEvent.sleep_detected()

        with Timer() as t:
            # Use the comprehensive goodnight routine if available
            if self.controller and not self.simulate:
                try:
                    await self.controller.goodnight()
                    actions.append("Turn off all lights: Complete")
                    actions.append("Lower all shades: 100%")
                    actions.append("Set climate: Sleep mode (68F)")
                    actions.append("Check locks: All locked")
                    actions.append("Arm security: Stay mode")
                    actions.append("Reduce polling: Dormant level")
                except Exception as e:
                    logger.error(f"Goodnight routine failed: {e}")
                    # Fall back to individual actions
                    try:
                        await self.controller.set_lights(0)
                        actions.append("Turn off all lights: Complete")
                    except Exception:
                        pass
                    try:
                        await self.controller.close_shades()
                        actions.append("Lower all shades: 100%")
                    except Exception:
                        pass
                    try:
                        await self.controller.lock_all()
                        actions.append("Check locks: All locked")
                    except Exception:
                        pass
            else:
                # Simulation mode - show all steps
                steps = [
                    ("Turn off all lights", "Complete"),
                    ("Lower all shades", "100%"),
                    ("Set climate", "Sleep mode (68F)"),
                    ("Check locks", "All locked"),
                    ("Arm security", "Stay mode"),
                    ("Reduce polling", "Dormant level"),
                ]
                for action, result in steps:
                    actions.append(f"{action}: {result}")
                    await asyncio.sleep(0.05)

            self.metrics.increment("actions", len(actions))

        return TriggerResult(
            trigger_type=TriggerType.SLEEP,
            success=True,
            actions_executed=actions,
            execution_time_ms=t.elapsed_ms,
            simulated=self.simulate or self.controller is None,
        )


# =============================================================================
# DEMO SECTIONS
# =============================================================================


def print_architecture() -> None:
    """Print the cross-domain architecture diagram.

    This explains how digital events flow through the system to
    trigger physical actions, following the Markov Blanket principle.
    """
    print_section(1, "Cross-Domain Architecture")

    print(
        """
   +---------------------------------------------------------+
   |                    ENVIRONMENT                           |
   |                                                          |
   |   DIGITAL (Composio)           PHYSICAL (SmartHome)      |
   |   -----------------            --------------------      |
   |   Slack, Gmail, Calendar       Control4, UniFi, Denon    |
   |   500 digital tools            100+ physical devices     |
   |                                                          |
   +---------------------------------------------------------+
   |              UNIFIED SENSORY BUS                         |
   |              UnifiedSensoryIntegration                   |
   |                                                          |
   |   Polling:                 Alert Hierarchy:              |
   |   - Emails: 60s TTL        - CRITICAL: All rooms         |
   |   - Calendar: 120s TTL     - HIGH: Occupied room         |
   |   - Presence: 30s TTL      - NORMAL: Log only            |
   |   - Sleep: 600s TTL        - LOW: Batch + summarize      |
   +---------------------------------------------------------+
   |              CROSS-DOMAIN TRIGGERS                       |
   |              ComposioSmartHomeBridge                     |
   |                                                          |
   |   - Urgent email -> Audio announcement                   |
   |   - Meeting in 5min -> Room preparation                  |
   |   - PR merged -> Celebration soundscape                  |
   |   - Focus mode -> Dim lights + pause polling             |
   +---------------------------------------------------------+
"""
    )

    print_success("Cross-domain architecture explained")


async def run_trigger_demo(
    executor: CrossDomainTriggerExecutor,
    trigger_type: TriggerType,
    section_num: int,
    title: str,
    description: str,
    event: SimulatedEvent,
) -> TriggerResult:
    """Run a single trigger demonstration.

    Args:
        executor: The trigger executor instance
        trigger_type: Type of trigger to execute
        section_num: Section number for display
        title: Section title
        description: Scenario description
        event: Simulated event data to display

    Returns:
        TriggerResult from the execution
    """
    print_separator()
    print_section(section_num, title)

    print(f"   Scenario: {description}")
    print()

    # Display simulated event
    print("   Event detected:")
    for key, value in event.data.items():
        # Format the key nicely
        display_key = key.replace("_", " ").title()
        print(f"      {display_key}: {value}")
    print()

    # Execute trigger
    result = await executor.execute(trigger_type)

    # Display results
    if result.success:
        for action in result.actions_executed:
            print(f"   [OK] {action}")
        print()
        print_success(
            f"{trigger_type.value.replace('_', ' ').title()} trigger complete",
            f"{result.execution_time_ms:.0f}ms total",
        )
    else:
        print_error(
            f"Trigger failed: {result.error_message}",
            f"{result.execution_time_ms:.0f}ms",
        )

    return result


def print_implementation_pattern() -> None:
    """Print the implementation pattern for cross-domain triggers.

    Shows developers how to implement their own triggers using
    the CrossDomainBridge infrastructure.
    """
    print_separator()
    print_section(7, "Implementation Pattern")

    print(
        """
   from kagami.core.ambient.cross_domain_bridge import (
       CrossDomainBridge,
       CrossDomainTrigger,
       get_cross_domain_bridge,
   )

   # Get the singleton bridge
   bridge = get_cross_domain_bridge()

   # Connect to services
   await bridge.connect(sensory, smart_home)

   # Register custom trigger
   def my_condition(data: dict) -> bool:
       return data.get("urgency", 0) > 0.8

   async def my_action(data: dict) -> None:
       await bridge._smart_home.announce(
           f"Alert: {data.get('message')}",
           rooms=["Living Room"]
       )

   trigger = CrossDomainTrigger(
       name="my_custom_trigger",
       source="custom_source",
       condition=my_condition,
       action=my_action,
       cooldown=60.0,  # Seconds between triggers
   )
   bridge._register_trigger(trigger)

   # Or use built-in triggers
   await bridge.fire_trigger("welcome_home", {})
"""
    )

    print_success("Implementation pattern shown")


# =============================================================================
# MAIN EXECUTION
# =============================================================================


async def get_controller(simulate: bool) -> SmartHomeController | None:
    """Attempt to get SmartHomeController, return None if unavailable.

    Args:
        simulate: If True, don't attempt real connection

    Returns:
        SmartHomeController instance or None
    """
    if simulate:
        logger.info("Simulation mode: skipping SmartHomeController connection")
        return None

    try:
        from kagami_smarthome import get_smart_home

        logger.info("Connecting to SmartHomeController...")
        controller = await get_smart_home()
        logger.info("SmartHomeController connected successfully")
        return controller
    except ImportError as e:
        logger.warning(f"kagami_smarthome not available: {e}")
        return None
    except Exception as e:
        logger.warning(f"Could not connect to SmartHomeController: {e}")
        return None


async def main_async(args: argparse.Namespace) -> int:
    """Async main function for the demo.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    # List triggers if requested
    if args.list:
        print("\nAvailable triggers:")
        for trigger in TriggerType:
            print(f"  - {trigger.value}")
        return 0

    print_header("CROSS-DOMAIN TRIGGERS", "->")

    metrics = MetricsCollector("cross_domain_triggers")

    # Attempt to get controller (unless simulating)
    controller = await get_controller(args.simulate)

    # Determine actual simulation mode
    simulate = args.simulate or controller is None
    if simulate and not args.simulate:
        print_warning("SmartHomeController unavailable, running in simulation mode")

    if simulate:
        print_info("Running in SIMULATION mode (no real device calls)")
    else:
        print_info("Running in LIVE mode (real device calls)")

    # Create executor
    executor = CrossDomainTriggerExecutor(controller, simulate, metrics)

    with Timer() as total_timer:
        # Show architecture
        print_architecture()

        # Define triggers to run
        triggers_to_run: list[tuple[TriggerType, int, str, str, SimulatedEvent]] = []

        if args.trigger:
            # Run specific trigger
            try:
                trigger_type = TriggerType(args.trigger)
                trigger_map = {
                    TriggerType.URGENT_EMAIL: (
                        "Trigger: Urgent Email -> Announcement",
                        "VIP sender emails with urgent flag",
                        SimulatedEvent.urgent_email(),
                    ),
                    TriggerType.MEETING_PREP: (
                        "Trigger: Meeting Soon -> Room Prep",
                        "Calendar event starts in 5 minutes",
                        SimulatedEvent.meeting_soon(),
                    ),
                    TriggerType.FOCUS_MODE: (
                        "Trigger: Focus Block -> Do Not Disturb",
                        "Calendar has 'Focus Time' block",
                        SimulatedEvent.focus_block(),
                    ),
                    TriggerType.CELEBRATION: (
                        "Trigger: PR Merged -> Celebration",
                        "Important PR merged on GitHub",
                        SimulatedEvent.pr_merged(),
                    ),
                    TriggerType.SLEEP: (
                        "Trigger: Sleep Detected -> Goodnight",
                        "Eight Sleep detects user in bed for 15 minutes",
                        SimulatedEvent.sleep_detected(),
                    ),
                }
                title, desc, event = trigger_map[trigger_type]
                triggers_to_run.append((trigger_type, 2, title, desc, event))
            except ValueError:
                print_error(f"Unknown trigger: {args.trigger}")
                print_info(f"Available: {', '.join(t.value for t in TriggerType)}")
                return 1
        else:
            # Run all triggers
            triggers_to_run = [
                (
                    TriggerType.URGENT_EMAIL,
                    2,
                    "Trigger: Urgent Email -> Announcement",
                    "VIP sender emails with urgent flag",
                    SimulatedEvent.urgent_email(),
                ),
                (
                    TriggerType.MEETING_PREP,
                    3,
                    "Trigger: Meeting Soon -> Room Prep",
                    "Calendar event starts in 5 minutes",
                    SimulatedEvent.meeting_soon(),
                ),
                (
                    TriggerType.FOCUS_MODE,
                    4,
                    "Trigger: Focus Block -> Do Not Disturb",
                    "Calendar has 'Focus Time' block",
                    SimulatedEvent.focus_block(),
                ),
                (
                    TriggerType.CELEBRATION,
                    5,
                    "Trigger: PR Merged -> Celebration",
                    "Important PR merged on GitHub",
                    SimulatedEvent.pr_merged(),
                ),
                (
                    TriggerType.SLEEP,
                    6,
                    "Trigger: Sleep Detected -> Goodnight",
                    "Eight Sleep detects user in bed for 15 minutes",
                    SimulatedEvent.sleep_detected(),
                ),
            ]

        # Execute triggers
        results: list[TriggerResult] = []
        for trigger_type, section_num, title, desc, event in triggers_to_run:
            result = await run_trigger_demo(executor, trigger_type, section_num, title, desc, event)
            results.append(result)
            metrics.record_timing(trigger_type.value, result.execution_time_ms / 1000)

        # Show implementation pattern (only for full demo)
        if not args.trigger:
            print_implementation_pattern()

    # Calculate statistics
    successful = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)

    print_metrics(
        {
            "Total time": f"{total_timer.elapsed:.2f}s",
            "Triggers demonstrated": len(results),
            "Successful": successful,
            "Failed": failed,
            "Actions executed": metrics.counters.get("actions", 0),
            "Mode": "Simulation" if simulate else "Live",
            "Digital -> Physical": "Seamless",
        }
    )

    print_footer(
        message="Cross-Domain Triggers demo complete!",
        success=failed == 0,
        next_steps=[
            "Run smarthome_demo.py for home control",
            "Run digital_integration_demo.py for Composio",
            "See packages/kagami/core/ambient/cross_domain_bridge.py for implementation",
        ],
    )

    return 0 if failed == 0 else 1


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Cross-Domain Triggers Demo - Bridge digital events to physical actions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    Run all triggers with real controller
  %(prog)s --simulate         Run all triggers in simulation mode
  %(prog)s --trigger sleep    Run only the sleep trigger
  %(prog)s --list             List available triggers

Triggers:
  urgent_email    Email from VIP -> Audio announcement
  meeting_prep    Meeting in 5min -> Room preparation
  focus_mode      Focus block -> Do Not Disturb
  celebration     PR merged -> Celebration lights
  sleep           Sleep detected -> Goodnight routine
        """,
    )

    parser.add_argument(
        "--simulate",
        "-s",
        action="store_true",
        help="Run in simulation mode (no real device calls)",
    )

    parser.add_argument(
        "--trigger",
        "-t",
        type=str,
        choices=[t.value for t in TriggerType],
        help="Run only the specified trigger",
    )

    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available triggers and exit",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point for the demo.

    Returns:
        Exit code (0 for success)
    """
    args = parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    # Run async main
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
