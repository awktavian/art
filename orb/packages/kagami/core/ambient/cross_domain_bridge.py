"""CrossDomainBridge — Unified Digital-Physical Bridge.

CREATED: December 30, 2025 (Phase 4 Refactor)
UPDATED: January 5, 2026 (Architecture Clarification)

THE SINGLE bridge between digital/physical senses and physical home actions.

## Trigger Responsibility

**CrossDomainBridge handles REACTIVE triggers** (sense → action):
- Weather changes → Announcements, shade adjustments
- Emails/calendar → Announcements, room preparation
- Sleep/vehicle → Scene triggers
- GitHub events → Celebration scenes

**NOT handled here:**
- Autonomous/time-based actions → OrganismPhysicalBridge
- Service → Service triggers → AutoTriggers
- Astronomical calculations → CelestialTriggers
- Agent collaboration → ImportanceTriggers

## Features

1. Subscribes to UnifiedSensoryIntegration (event-driven, no polling)
2. Trigger registry with conditions, actions, cooldowns
3. Colony/breath state → room scenes
4. Unified state snapshot format
5. Device registration in Constellation

## Philosophy

Sense changes trigger physical actions.
Colony states drive ambient scenes.
Subscribe, don't poll.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from kagami.core.integrations.situation_awareness import SituationPhase

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

    from kagami.core.ambient.controller import AmbientController
    from kagami.core.integrations.unified_sensory import (
        UnifiedSensoryIntegration,
    )

logger = logging.getLogger(__name__)


# =============================================================================
# DATA TYPES
# =============================================================================


class SmartDeviceType(str, Enum):
    """Smart home device types for registration."""

    LIGHT = "light"
    SHADE = "shade"
    AUDIO_ZONE = "audio_zone"
    HVAC_ZONE = "hvac_zone"
    LOCK = "lock"
    TV = "tv"
    CAMERA = "camera"
    THERMOSTAT = "thermostat"
    SENSOR = "sensor"
    ROOM = "room"


@dataclass
class CrossDomainTrigger:
    """A trigger that bridges digital events to physical actions."""

    name: str
    source: str  # Sense type that triggers this
    condition: Callable[[dict], bool]
    action: Callable[[dict], Awaitable[None]]
    cooldown: float = 60.0
    enabled: bool = True
    last_triggered: float = 0
    trigger_count: int = 0

    def can_trigger(self, data: dict) -> bool:
        """Check if trigger can fire."""
        if not self.enabled:
            return False
        if (time.time() - self.last_triggered) < self.cooldown:
            return False
        try:
            return self.condition(data)
        except Exception:
            return False


@dataclass
class UnifiedHomeSnapshot:
    """THE canonical home state snapshot.

    Consolidates HomeSnapshot and RoomStateSnapshot from smarthome_bridge.
    """

    timestamp: float = field(default_factory=time.time)

    # Presence
    presence_state: str = "unknown"  # home, away, arriving, leaving
    current_room: str | None = None
    travel_mode: str = "home"
    is_home: bool = True

    # Security
    security_armed: bool = False
    all_doors_locked: bool = True
    any_door_open: bool = False

    # Climate
    avg_temperature: float = 72.0
    hvac_mode: str = "auto"

    # Lighting
    lights_on_count: int = 0
    avg_light_level: float = 0.0

    # Audio
    audio_playing: bool = False
    active_audio_zones: list[str] = field(default_factory=list)

    # Ambient (from Kagami)
    active_colony: str | None = None
    breath_phase: str | None = None
    safety_h: float = 1.0

    # Situation (from SituationAwarenessEngine)
    situation_phase: str = "relaxing"
    urgency: str = "low"

    # Integration status
    integrations_online: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "presence_state": self.presence_state,
            "current_room": self.current_room,
            "is_home": self.is_home,
            "security_armed": self.security_armed,
            "all_doors_locked": self.all_doors_locked,
            "avg_temperature": self.avg_temperature,
            "lights_on_count": self.lights_on_count,
            "audio_playing": self.audio_playing,
            "active_colony": self.active_colony,
            "situation_phase": self.situation_phase,
            "urgency": self.urgency,
        }


@dataclass
class BridgeConfig:
    """Configuration for the cross-domain bridge."""

    # Trigger settings
    announce_urgent_emails: bool = True
    prepare_for_meetings: bool = True
    celebration_sounds: bool = True

    # Scene settings
    colony_scene_mapping: bool = True
    presence_scene_triggers: bool = True

    # Cooldowns (seconds)
    email_announce_cooldown: float = 60.0
    meeting_prep_cooldown: float = 300.0
    welcome_home_cooldown: float = 600.0
    goodnight_cooldown: float = 14400.0  # 4 hours


# =============================================================================
# CROSS-DOMAIN BRIDGE
# =============================================================================


class CrossDomainBridge:
    """Unified bridge between digital and physical domains.

    CONSOLIDATES:
    - AmbientSmartHomeBridge (device sync, scenes)
    - ComposioSmartHomeBridge (triggers, events)

    ARCHITECTURE:
    - SUBSCRIBES to UnifiedSensoryIntegration (no polling!)
    - Fires triggers on sense events
    - Maps colony states to room scenes
    - Provides unified state snapshot

    Usage:
        bridge = get_cross_domain_bridge()
        await bridge.connect(sensory, smart_home)

        # Get unified state
        snapshot = await bridge.get_home_snapshot()

        # Fire manual trigger
        await bridge.fire_trigger("welcome_home", {})
    """

    def __init__(self, config: BridgeConfig | None = None):
        self.config = config or BridgeConfig()

        # Connected services
        self._sensory: UnifiedSensoryIntegration | None = None
        self._smart_home: SmartHomeController | None = None
        self._ambient: AmbientController | None = None

        # Situation awareness
        self._situation_phase = SituationPhase.RELAXING
        self._situation_engine: Any = None

        # UNIFIED TRIGGER SYSTEM (January 5, 2026)
        from kagami.core.triggers import get_trigger_registry

        self._trigger_registry = get_trigger_registry()

        # Legacy compatibility (for migration period)
        self._triggers: list[CrossDomainTrigger] = []
        self._trigger_map: dict[str, CrossDomainTrigger] = {}

        # State
        self._running = False
        self._last_snapshot: UnifiedHomeSnapshot | None = None
        self._snapshot_cache_ttl = 30.0
        self._last_snapshot_time = 0.0

        # Email dedup
        self._announced_emails: set[str] = set()

        # Statistics
        self._stats = {
            "events_received": 0,
            "triggers_fired": 0,
            "announcements": 0,
            "scenes_applied": 0,
        }

    # =========================================================================
    # CONNECTION
    # =========================================================================

    async def connect(
        self,
        sensory: UnifiedSensoryIntegration,
        smart_home: SmartHomeController,
        ambient: AmbientController | None = None,
    ) -> bool:
        """Connect to all services.

        Args:
            sensory: UnifiedSensoryIntegration to subscribe to
            smart_home: SmartHomeController for physical actions
            ambient: Optional AmbientController for colony states

        Returns:
            True if connected
        """
        self._sensory = sensory
        self._smart_home = smart_home
        self._ambient = ambient

        # SUBSCRIBE to sensory events (THE KEY - no polling!)
        sensory.on_sense_change(self._on_sense_event)

        # Connect trigger registry to services
        self._trigger_registry.connect(smart_home, sensory)

        # Setup default triggers (UNIFIED SYSTEM - January 5, 2026)
        self._setup_unified_triggers()

        # Wire situation awareness
        await self._wire_situation_awareness()

        # Wire travel intelligence
        await self._wire_travel_intelligence()

        # Wire wakefulness (January 5, 2026 - automatic morning briefings)
        await self._wire_wakefulness()

        self._running = True

        logger.info("🔗 CrossDomainBridge connected (unified trigger system)")
        return True

    async def disconnect(self) -> None:
        """Disconnect from all services."""
        self._running = False
        self._sensory = None
        self._smart_home = None
        self._ambient = None
        logger.info("🔗 CrossDomainBridge disconnected")

    async def _wire_situation_awareness(self) -> None:
        """Wire to SituationAwarenessEngine."""
        try:
            from kagami.core.integrations.situation_awareness import get_situation_engine

            self._situation_engine = get_situation_engine()
            logger.debug("SituationAwarenessEngine wired")
        except Exception as e:
            logger.debug(f"SituationAwarenessEngine not available: {e}")

    async def _wire_travel_intelligence(self) -> None:
        """Wire travel intelligence alerts."""
        if not self._smart_home:
            return

        try:
            from kagami_smarthome.travel_intelligence import (
                RouteAlert,
                start_travel_monitoring,
            )

            travel = await start_travel_monitoring(self._smart_home)

            async def handle_travel_alert(alert: RouteAlert, data: dict) -> None:
                if not self._smart_home:
                    return

                message = None

                if alert == RouteAlert.TRAFFIC_HEAVY:
                    delay = data.get("delay_minutes", 0)
                    message = f"Traffic alert: Commute is {delay} minutes longer."
                elif alert == RouteAlert.TRAFFIC_CLEARED:
                    message = "Traffic cleared. Normal commute time restored."
                elif alert == RouteAlert.ARRIVAL_SOON:
                    eta = data.get("eta_minutes", 0)
                    message = f"Arriving home in approximately {eta} minutes."

                if message:
                    await self._announce(message, ["Living Room"])

            travel.on_alert(handle_travel_alert)
            logger.debug("TravelIntelligence wired")

        except Exception as e:
            logger.debug(f"TravelIntelligence not available: {e}")

    async def _wire_wakefulness(self) -> None:
        """Wire to WakefulnessManager for morning briefings.

        ADDED: January 5, 2026
        CRITICAL FIX: Automatic weather briefing on wake-up
        """
        try:
            from kagami.core.integrations.wakefulness import (
                WakefulnessLevel,
                get_wakefulness_manager,
            )

            wakefulness = get_wakefulness_manager()

            async def on_wakefulness_change(
                old_level: WakefulnessLevel, new_level: WakefulnessLevel
            ) -> None:
                """Handle wakefulness transitions."""
                # Morning briefing: When transitioning to ALERT or ENGAGED
                if old_level in [
                    WakefulnessLevel.DORMANT,
                    WakefulnessLevel.DROWSY,
                ] and new_level in [WakefulnessLevel.ALERT, WakefulnessLevel.FOCUSED]:
                    # Get current weather and announce if it's morning
                    import datetime

                    now = datetime.datetime.now()
                    if 6 <= now.hour < 12:  # Morning window
                        logger.info(
                            f"Wakefulness: {old_level.value} → {new_level.value}, triggering morning briefing"
                        )
                        # Fire the morning weather briefing trigger
                        if self._sensory:
                            from kagami.core.integrations.unified_sensory import SenseType

                            # Poll all senses and extract weather data
                            all_data = await self._sensory.poll_all(use_cache=True)
                            weather_data = all_data.get(SenseType.WEATHER, {})
                            if weather_data:
                                await self.fire_trigger("morning_weather_briefing", weather_data)

            wakefulness.on_change(on_wakefulness_change)
            logger.info("🔗 CrossDomainBridge wired to WakefulnessManager")

        except Exception as e:
            logger.warning(f"Could not wire wakefulness (optional): {e}")

    # =========================================================================
    # TRIGGERS
    # =========================================================================

    def _setup_unified_triggers(self) -> None:
        """Setup triggers using unified trigger system.

        MIGRATED: January 5, 2026 (Phase 2 Consolidation)
        Uses core/triggers/ unified system instead of local CrossDomainTrigger.
        """
        from kagami.core.triggers.migration import register_all_weather_triggers

        # Register weather triggers
        if self._smart_home:
            register_all_weather_triggers(self._trigger_registry, self._announce, self._smart_home)
            logger.info("✅ Weather triggers registered (unified system)")

        # Legacy triggers coexist during migration to unified trigger system
        self._setup_default_triggers()

    def _setup_default_triggers(self) -> None:
        """Setup default cross-domain triggers.

        Note: Weather triggers have been migrated to unified system.
        Email/calendar triggers remain here until migration completes.
        """

        # Email urgency → announcement
        def is_urgent_email(data: dict) -> bool:
            if not self.config.announce_urgent_emails:
                return False
            urgency = data.get("urgency", 0)
            unread = data.get("unread_important", 0)
            return urgency > 0.7 or unread > 0

        async def announce_email(data: dict) -> None:
            important = data.get("important_from", [])
            if important:
                sender = (
                    important[0]
                    if isinstance(important[0], str)
                    else important[0].get("from", "someone")
                )
                email_id = f"{sender}:{data.get('unread_important', 0)}"

                if email_id not in self._announced_emails:
                    self._announced_emails.add(email_id)
                    await self._announce(
                        f"You have an important email from {sender}", ["Living Room"]
                    )

        self._register_trigger(
            CrossDomainTrigger(
                name="urgent_email",
                source="gmail",
                condition=is_urgent_email,
                action=announce_email,
                cooldown=self.config.email_announce_cooldown,
            )
        )

        # Meeting soon → room prep
        def meeting_soon(data: dict) -> bool:
            if not self.config.prepare_for_meetings:
                return False
            minutes_to_next = data.get("minutes_to_next", float("inf"))
            return minutes_to_next and minutes_to_next <= 15

        async def prepare_for_meeting(_data: dict) -> None:
            if self._smart_home:
                # Prepare office for meeting
                await self._smart_home.set_lights(80, rooms=["Office"])
                await self._announce("Meeting starting in 15 minutes", ["Office"])

        self._register_trigger(
            CrossDomainTrigger(
                name="meeting_prep",
                source="calendar",
                condition=meeting_soon,
                action=prepare_for_meeting,
                cooldown=self.config.meeting_prep_cooldown,
            )
        )

        # Sleep detected → goodnight
        def is_sleeping(data: dict) -> bool:
            sleep_state = data.get("state", "")
            return sleep_state == "asleep"

        async def trigger_goodnight(data: dict) -> None:
            if self._smart_home:
                await self._smart_home.goodnight()

        self._register_trigger(
            CrossDomainTrigger(
                name="goodnight",
                source="sleep",
                condition=is_sleeping,
                action=trigger_goodnight,
                cooldown=self.config.goodnight_cooldown,
            )
        )

        # Vehicle arriving → welcome home
        def vehicle_arriving(data: dict) -> bool:
            is_home = data.get("is_home", True)
            return not is_home  # Will trigger when transitioning to home

        async def trigger_welcome_home(data: dict) -> None:
            if self._smart_home:
                await self._smart_home.welcome_home()

        self._register_trigger(
            CrossDomainTrigger(
                name="welcome_home",
                source="vehicle",
                condition=lambda d: d.get("eta_minutes", 999) < 5 and not d.get("is_home", True),
                action=trigger_welcome_home,
                cooldown=self.config.welcome_home_cooldown,
            )
        )

        # Weather/sun shade adjustment — NOW USING CELESTIAL MECHANICS
        # REPLACED: Hardcoded "Living Room, Dining" with calculated sun geometry
        # The celestial module calculates actual sun position and window orientations

        def celestial_shade_needed(data: dict) -> bool:
            """Check if sun position warrants shade adjustment.

            Uses celestial mechanics to calculate actual sun exposure
            instead of relying on weather API data.
            """
            try:
                from kagami.core.celestial import (
                    is_sun_up,
                    rooms_need_shade_now,
                )

                # Only during daytime
                if not is_sun_up():
                    return False

                # Check if any rooms have direct sun exposure
                rooms = rooms_need_shade_now()
                return len(rooms) > 0

            except ImportError:
                # Fallback to legacy behavior if celestial not available
                is_daytime = data.get("is_daytime", True)
                return is_daytime

        async def adjust_shades_celestial(data: dict) -> None:
            """Close shades based on calculated sun position and window geometry."""
            if not self._smart_home:
                return

            try:
                from kagami.core.celestial import (
                    explain_sun,
                    rooms_need_shade_now,
                )

                # Get rooms that actually have direct sun based on orbital mechanics
                sun_exposed_rooms = rooms_need_shade_now()

                if sun_exposed_rooms:
                    await self._smart_home.close_shades(rooms=sun_exposed_rooms)
                    explanation = explain_sun()
                    logger.info(f"☀️ Celestial shade control: {explanation}")

            except ImportError:
                # Fallback: use legacy hardcoded rooms
                await self._smart_home.close_shades(rooms=["Living Room", "Dining"])

        self._register_trigger(
            CrossDomainTrigger(
                name="celestial_shade",
                source="weather",  # Still triggered by weather sense, but uses celestial calc
                condition=celestial_shade_needed,
                action=adjust_shades_celestial,
                cooldown=3600.0,  # 1 hour cooldown
            )
        )

        # GitHub PR merged → celebration (December 30, 2025)
        def pr_merged(data: dict) -> bool:
            """Check if a PR was merged."""
            events = data.get("events", [])
            for event in events:
                if event.get("action") == "closed" and event.get("merged", False):
                    return True
            # Also check direct merged flag
            return data.get("pr_merged", False)

        async def celebrate_pr_merge(data: dict) -> None:
            """Celebration for merged PR."""
            if not self._smart_home:
                return

            pr_title = data.get("pr_title", "Pull request")

            await self._announce(
                f"Congratulations! {pr_title} has been merged.", ["Office", "Living Room"]
            )

            # Brief light celebration (pulse lights)
            try:
                # Flash lights briefly
                await self._smart_home.set_lights(100, rooms=["Office"])
                import asyncio

                await asyncio.sleep(0.5)
                await self._smart_home.set_lights(60, rooms=["Office"])
            except Exception:
                pass  # Light celebration is optional

        self._register_trigger(
            CrossDomainTrigger(
                name="pr_celebration",
                source="github",
                condition=pr_merged,
                action=celebrate_pr_merge,
                cooldown=30.0,  # 30 second cooldown between celebrations
            )
        )

        # DELETED: rain_protection, cold_weather_alert
        # → Migrated to unified trigger system (core/triggers/migration.py)
        # January 12, 2026 - removed duplicate registrations

        # Sunset approaching → prepare evening lighting
        # REPLACED: Weather API sunset timestamp with CALCULATED sunset from orbital mechanics
        def sunset_approaching_celestial(data: dict) -> bool:
            """Check if sunset is within 30 minutes using celestial calculations.

            Uses proper astronomical algorithms instead of weather API data.
            """
            try:
                from kagami.core.celestial import minutes_until_sunset

                mins = minutes_until_sunset()
                if mins is None:
                    return False

                # Trigger 15-30 minutes before calculated sunset
                return 15 <= mins <= 30

            except ImportError:
                # Fallback to legacy weather API behavior
                import time

                sunset = data.get("sunset", 0)
                if not sunset:
                    return False

                now = int(time.time())
                minutes_until = (sunset - now) / 60
                return 15 <= minutes_until <= 30

        async def prepare_evening_lights_celestial(data: dict) -> None:
            """Prepare home for evening using celestially-calculated sunset."""
            if not self._smart_home:
                return

            try:
                presence = self._smart_home.get_presence_state()
                if presence and not presence.get("owner_home", True):
                    return  # Don't light empty house
            except Exception:
                pass

            # Gently raise lights in main living areas
            await self._smart_home.set_lights(40, rooms=["Living Room", "Kitchen"])

            try:
                from kagami.core.celestial import minutes_until_sunset

                mins = minutes_until_sunset()
                if mins:
                    logger.info(f"🌅 Sunset in {mins:.0f} minutes (calculated) — adjusting lights")
            except ImportError:
                pass

        self._register_trigger(
            CrossDomainTrigger(
                name="sunset_preparation",
                source="weather",  # Still triggered by weather sense polling
                condition=sunset_approaching_celestial,
                action=prepare_evening_lights_celestial,
                cooldown=86400.0,  # Once per day
            )
        )

        # DELETED: snow_alert, morning_weather_briefing, weather_change_alert
        # → Migrated to unified trigger system (core/triggers/migration.py)
        # January 5, 2026

    def _register_trigger(self, trigger: CrossDomainTrigger) -> None:
        """Register a cross-domain trigger."""
        self._triggers.append(trigger)
        self._trigger_map[trigger.name] = trigger
        logger.debug(f"Registered trigger: {trigger.name}")

    async def fire_trigger(self, name: str, data: dict) -> bool:
        """Manually fire a trigger by name."""
        trigger = self._trigger_map.get(name)
        if not trigger:
            return False

        try:
            trigger.last_triggered = time.time()
            trigger.trigger_count += 1
            await trigger.action(data)
            self._stats["triggers_fired"] += 1
            return True
        except Exception as e:
            logger.error(f"Trigger {name} failed: {e}")
            return False

    # =========================================================================
    # EVENT HANDLING
    # =========================================================================

    async def _on_sense_event(self, sense_type: Any, data: dict, delta: dict | None = None) -> None:
        """Handle sensory events from UnifiedSensoryIntegration.

        This is the main event handler - evaluates triggers through unified registry.

        Args:
            sense_type: SenseType enum or string
            data: Current sense data
            delta: Changes from previous state (optional)
        """
        self._stats["events_received"] += 1

        # Convert SenseType enum to string for trigger matching
        sense_str = sense_type.value if hasattr(sense_type, "value") else str(sense_type)

        # UNIFIED TRIGGER SYSTEM (January 5, 2026)
        # Evaluate triggers through unified registry
        try:
            results = await self._trigger_registry.evaluate(sense_str, data)
            for result in results:
                if result.success:
                    self._stats["triggers_fired"] += 1
        except Exception as e:
            logger.error(f"Unified trigger evaluation failed: {e}")

    # =========================================================================
    # ANNOUNCEMENTS
    # =========================================================================

    async def _announce(self, message: str, rooms: list[str] | None = None) -> bool:
        """Make an announcement through the smart home audio system."""
        if not self._smart_home:
            return False

        try:
            await self._smart_home.announce(message, rooms or ["Living Room"])
            self._stats["announcements"] += 1
            return True
        except Exception as e:
            logger.error(f"Announcement failed: {e}")
            return False

    # =========================================================================
    # STATE SNAPSHOT
    # =========================================================================

    async def get_home_snapshot(self, force_refresh: bool = False) -> UnifiedHomeSnapshot:
        """Get unified home state snapshot.

        THE canonical format for home state.
        """
        now = time.time()

        # Use cache if valid
        if not force_refresh and self._last_snapshot:
            if now - self._last_snapshot_time < self._snapshot_cache_ttl:
                return self._last_snapshot

        snapshot = UnifiedHomeSnapshot()

        if self._smart_home:
            try:
                home_state = self._smart_home.get_state()
                if home_state:
                    snapshot.presence_state = (
                        home_state.presence.value if home_state.presence else "unknown"
                    )
                    snapshot.is_home = snapshot.presence_state in ["home", "active"]
                    # HomeState uses owner_room/last_location, not location
                    snapshot.current_room = home_state.owner_room or home_state.last_location
                    # SecurityState enum: DISARMED, ARMED_STAY, ARMED_AWAY, ARMED_NIGHT, etc.
                    snapshot.security_armed = (
                        home_state.security is not None
                        and "armed" in home_state.security.value.lower()
                    )

                # Get integration status
                snapshot.integrations_online = await self._get_integration_status()

            except Exception as e:
                logger.error(f"Error getting home state: {e}")

        # Add situation phase
        if self._situation_engine:
            try:
                current = self._situation_engine.get_current_situation()
                if current:
                    snapshot.situation_phase = current.phase.value
                    snapshot.urgency = (
                        current.urgency.value if hasattr(current, "urgency") else "low"
                    )
            except Exception:
                pass

        # Add ambient state from internal state
        if self._ambient:
            try:
                # Access internal state for breath phase
                if hasattr(self._ambient, "_state") and self._ambient._state:
                    snapshot.breath_phase = self._ambient._state.breath.phase.value
                    # Get dominant colony from colonies dict
                    if self._ambient._state.colonies:
                        dominant = max(
                            self._ambient._state.colonies.items(),
                            key=lambda x: x[1].activation,
                            default=(None, None),
                        )
                        if dominant[0] and dominant[1] and dominant[1].activation > 0.1:
                            snapshot.active_colony = dominant[0].value
            except Exception:
                pass

        self._last_snapshot = snapshot
        self._last_snapshot_time = now

        return snapshot

    async def _get_integration_status(self) -> dict[str, bool]:
        """Get online status of all integrations."""
        status: dict[str, bool] = {}

        if self._smart_home:
            try:
                # Use sync get_integration_health from controller
                health = self._smart_home.get_integration_health()
                # Health returns {"degraded": [...], "status": {...}}
                integration_status = health.get("status", {})
                for name, data in integration_status.items():
                    if isinstance(data, dict):
                        status[name] = data.get("connected", False)
                    else:
                        status[name] = bool(data)
            except Exception:
                pass

        return status

    # =========================================================================
    # SCENES
    # =========================================================================

    async def apply_scene(self, scene_name: str, rooms: list[str] | None = None) -> bool:
        """Apply a scene to specified rooms."""
        if not self._smart_home:
            return False

        try:
            if scene_name == "movie":
                await self._smart_home.movie_mode()
            elif scene_name == "goodnight":
                await self._smart_home.goodnight()
            elif scene_name == "welcome_home":
                await self._smart_home.welcome_home()
            else:
                # Try orchestrator - apply scene to all rooms in parallel
                orchestrator = self._smart_home._orchestrator
                if orchestrator and rooms:
                    # Convert room names to Room objects
                    room_objs = []
                    for room_name in rooms:
                        room_obj = orchestrator.rooms.get_by_name(room_name)
                        if room_obj:
                            room_objs.append(room_obj)
                    if room_objs:
                        await asyncio.gather(
                            *[orchestrator.set_room_scene(room, scene_name) for room in room_objs],
                            return_exceptions=True,
                        )

            self._stats["scenes_applied"] += 1
            return True

        except Exception as e:
            logger.error(f"Scene {scene_name} failed: {e}")
            return False

    # =========================================================================
    # STATUS
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get bridge statistics."""
        return {
            **self._stats,
            "triggers_registered": len(self._triggers),
            "running": self._running,
            "sensory_connected": self._sensory is not None,
            "smarthome_connected": self._smart_home is not None,
        }

    def get_situation_phase(self) -> SituationPhase:
        """Get current situation phase."""
        if self._situation_engine:
            try:
                current = self._situation_engine.get_current_situation()
                if current:
                    return current.phase
            except Exception:
                pass
        return self._situation_phase


# =============================================================================
# SINGLETON
# =============================================================================

_bridge: CrossDomainBridge | None = None


def get_cross_domain_bridge() -> CrossDomainBridge:
    """Get global CrossDomainBridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = CrossDomainBridge()
    return _bridge


def reset_cross_domain_bridge() -> None:
    """Reset the singleton (for testing)."""
    global _bridge
    _bridge = None


async def connect_cross_domain_bridge(
    sensory: UnifiedSensoryIntegration,
    smart_home: SmartHomeController,
    ambient: AmbientController | None = None,
) -> CrossDomainBridge:
    """Connect and return the cross-domain bridge.

    Args:
        sensory: UnifiedSensoryIntegration
        smart_home: SmartHomeController
        ambient: Optional AmbientController

    Returns:
        Connected CrossDomainBridge
    """
    bridge = get_cross_domain_bridge()
    await bridge.connect(sensory, smart_home, ambient)
    return bridge


__all__ = [
    "BridgeConfig",
    "CrossDomainBridge",
    "CrossDomainTrigger",
    "SmartDeviceType",
    "UnifiedHomeSnapshot",
    "connect_cross_domain_bridge",
    "get_cross_domain_bridge",
    "reset_cross_domain_bridge",
]
