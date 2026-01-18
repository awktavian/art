"""Situation Awareness — CONTEXT LAYER of the Predictive Hierarchy.

OPTIMAL ARCHITECTURE (4-Layer Predictive Hierarchy):
=====================================================
Based on research into OODA, Predictive Processing, and Active Inference.
NOT Endsley's sequential 3-stage model (criticized for being too linear).

┌────────────────────────────────────────────────────────────────────────┐
│                      PREDICTIVE HIERARCHY                              │
│                                                                        │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐        │
│  │  SENSE   │◄──►│ PATTERN  │◄──►│ CONTEXT  │◄──►│  ACTION  │        │
│  │  Layer   │    │  Layer   │    │  Layer   │    │  Layer   │        │
│  │          │    │          │    │  (THIS)  │    │          │        │
│  │ Raw data │    │ Temporal │    │ Meaning  │    │ Goals    │        │
│  │ polling  │    │ predict  │    │ & state  │    │ & drives │        │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘        │
│        │               │               │               │              │
│        └───────────────┴───────────────┴───────────────┘              │
│                     Shared State (OrganismRSSM)                        │
└────────────────────────────────────────────────────────────────────────┘

This module is the CONTEXT LAYER:
    - Receives: Raw senses + Pattern predictions
    - Produces: Situation understanding (phase, urgency, energy, social)
    - Sends to: Action layer + OrganismRSSM

The layers are COMPLEMENTARY and PARALLEL, not sequential:
    - SENSE: UnifiedSensoryIntegration (24 sense types)
    - PATTERN: PatternLearner (temporal predictions)
    - CONTEXT: SituationAwareness (THIS MODULE)
    - ACTION: SituationOrchestrator + AutonomousGoalEngine

Philosophy:
    Weather tells you temperature.
    Situation Awareness tells you "Tim is about to leave for a meeting
    in the rain without an umbrella."

Created: December 30, 2025
Updated: December 30, 2025 — Optimized to 4-layer predictive hierarchy
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# SITUATION TYPES
# =============================================================================


class SituationPhase(str, Enum):
    """Current life phase / mode."""

    SLEEPING = "sleeping"
    WAKING = "waking"
    MORNING_ROUTINE = "morning_routine"
    COMMUTING = "commuting"
    WORKING = "working"
    IN_MEETING = "in_meeting"
    FOCUSED = "focused"
    BREAK = "break"
    EXERCISING = "exercising"
    EATING = "eating"
    SOCIALIZING = "socializing"
    RELAXING = "relaxing"
    WINDING_DOWN = "winding_down"
    UNKNOWN = "unknown"


class UrgencyLevel(str, Enum):
    """How urgent is the current situation."""

    CALM = "calm"  # Nothing pressing
    NORMAL = "normal"  # Regular flow
    BUSY = "busy"  # Multiple things happening
    URGENT = "urgent"  # Time-sensitive
    CRITICAL = "critical"  # Immediate attention needed


class EnergyLevel(str, Enum):
    """Inferred energy level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SocialContext(str, Enum):
    """Social situation."""

    ALONE = "alone"
    WITH_PARTNER = "with_partner"
    WITH_FAMILY = "with_family"
    WITH_COLLEAGUES = "with_colleagues"
    WITH_FRIENDS = "with_friends"
    IN_PUBLIC = "in_public"
    HOSTING = "hosting"


# =============================================================================
# SITUATION COMPREHENSION (Level 2)
# =============================================================================


@dataclass
class ActiveEvent:
    """An event that's currently active or imminent."""

    title: str
    start_time: datetime
    end_time: datetime | None = None
    location: str | None = None
    attendees: list[str] = field(default_factory=list)
    is_meeting: bool = False
    is_travel: bool = False
    urgency: UrgencyLevel = UrgencyLevel.NORMAL

    @property
    def is_now(self) -> bool:
        """Is this event happening right now?"""
        now = datetime.now()
        if self.end_time:
            return self.start_time <= now <= self.end_time
        return self.start_time <= now <= self.start_time + timedelta(hours=1)

    @property
    def minutes_until(self) -> int:
        """Minutes until this event starts (negative if started)."""
        delta = self.start_time - datetime.now()
        return int(delta.total_seconds() / 60)


@dataclass
class TravelContext:
    """Understanding of current or imminent travel."""

    is_traveling: bool = False
    is_leaving_soon: bool = False  # Within 30 min
    destination: str | None = None
    purpose: str | None = None  # "work", "meeting", "errand", etc.
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    travel_time_minutes: int | None = None
    traffic_condition: str = "unknown"  # light, normal, heavy
    route_alerts: list[str] = field(default_factory=list)

    # What Tim needs
    needs_jacket: bool = False
    needs_umbrella: bool = False
    needs_charger: bool = False
    needs_laptop: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_traveling": self.is_traveling,
            "is_leaving_soon": self.is_leaving_soon,
            "destination": self.destination,
            "purpose": self.purpose,
            "departure_time": self.departure_time.isoformat() if self.departure_time else None,
            "travel_time_minutes": self.travel_time_minutes,
            "traffic_condition": self.traffic_condition,
            "route_alerts": self.route_alerts,
            "needs_jacket": self.needs_jacket,
            "needs_umbrella": self.needs_umbrella,
            "needs_charger": self.needs_charger,
            "needs_laptop": self.needs_laptop,
        }


@dataclass
class WorkContext:
    """Understanding of work situation."""

    is_work_time: bool = False
    is_in_meeting: bool = False
    is_focused: bool = False  # Deep work mode
    next_meeting_minutes: int | None = None
    unread_urgent_emails: int = 0
    pending_tasks: int = 0
    active_project: str | None = None
    blocked_on: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_work_time": self.is_work_time,
            "is_in_meeting": self.is_in_meeting,
            "is_focused": self.is_focused,
            "next_meeting_minutes": self.next_meeting_minutes,
            "unread_urgent_emails": self.unread_urgent_emails,
            "pending_tasks": self.pending_tasks,
            "active_project": self.active_project,
            "blocked_on": self.blocked_on,
        }


@dataclass
class HomeContext:
    """Understanding of home situation."""

    is_home: bool = True
    is_alone: bool = True
    current_room: str | None = None
    lights_on: list[str] = field(default_factory=list)
    temperature_f: float | None = None
    is_comfortable: bool = True
    security_status: str = "armed_stay"  # armed_away, armed_stay, disarmed
    recent_motion: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_home": self.is_home,
            "is_alone": self.is_alone,
            "current_room": self.current_room,
            "lights_on_count": len(self.lights_on),
            "temperature_f": self.temperature_f,
            "is_comfortable": self.is_comfortable,
            "security_status": self.security_status,
            "recent_motion_rooms": self.recent_motion,
        }


@dataclass
class EnvironmentContext:
    """Understanding of environmental conditions."""

    weather_condition: str = "unknown"
    temperature_f: float | None = None
    is_raining: bool = False
    will_rain_soon: bool = False  # Next 2 hours
    is_dark_outside: bool = False
    sunrise_minutes_ago: int | None = None
    sunset_minutes_until: int | None = None
    air_quality: str = "good"  # good, moderate, poor

    def to_dict(self) -> dict[str, Any]:
        return {
            "weather_condition": self.weather_condition,
            "temperature_f": self.temperature_f,
            "is_raining": self.is_raining,
            "will_rain_soon": self.will_rain_soon,
            "is_dark_outside": self.is_dark_outside,
            "air_quality": self.air_quality,
        }


# =============================================================================
# SITUATION PROJECTION (Level 3)
# =============================================================================


@dataclass
class Projection:
    """A prediction about what will happen."""

    description: str
    confidence: float  # 0-1
    timeframe_minutes: int  # When this might happen
    recommended_action: str | None = None
    urgency: UrgencyLevel = UrgencyLevel.NORMAL


@dataclass
class SituationProjection:
    """Projections about what will happen next."""

    projections: list[Projection] = field(default_factory=list)

    # Key predictions
    likely_next_phase: SituationPhase = SituationPhase.UNKNOWN
    next_phase_confidence: float = 0.0
    next_phase_minutes: int = 0

    # Recommendations
    should_leave_soon: bool = False
    should_prepare_for: str | None = None
    interrupt_risk: float = 0.0  # 0-1, likelihood of interruption

    def to_dict(self) -> dict[str, Any]:
        return {
            "projections": [
                {
                    "description": p.description,
                    "confidence": p.confidence,
                    "timeframe_minutes": p.timeframe_minutes,
                    "recommended_action": p.recommended_action,
                    "urgency": p.urgency.value,
                }
                for p in self.projections
            ],
            "likely_next_phase": self.likely_next_phase.value,
            "next_phase_confidence": self.next_phase_confidence,
            "next_phase_minutes": self.next_phase_minutes,
            "should_leave_soon": self.should_leave_soon,
            "should_prepare_for": self.should_prepare_for,
            "interrupt_risk": self.interrupt_risk,
        }


# =============================================================================
# COMPLETE SITUATION (All Levels)
# =============================================================================


@dataclass
class Situation:
    """Complete situation awareness — what's happening and what it means.

    This is THE answer to "what's going on?"
    """

    # Level 1: Perception (aggregated from sensors)
    timestamp: datetime = field(default_factory=datetime.now)

    # Level 2: Comprehension (what does it mean?)
    phase: SituationPhase = SituationPhase.UNKNOWN
    urgency: UrgencyLevel = UrgencyLevel.NORMAL
    energy: EnergyLevel = EnergyLevel.MEDIUM
    social: SocialContext = SocialContext.ALONE

    # Contexts
    travel: TravelContext = field(default_factory=TravelContext)
    work: WorkContext = field(default_factory=WorkContext)
    home: HomeContext = field(default_factory=HomeContext)
    environment: EnvironmentContext = field(default_factory=EnvironmentContext)

    # Active events
    current_event: ActiveEvent | None = None
    upcoming_events: list[ActiveEvent] = field(default_factory=list)

    # Level 3: Projection (what will happen?)
    projection: SituationProjection = field(default_factory=SituationProjection)

    # Level 4: Anticipation (Dec 30, 2025) — proactive desire inference
    anticipations: list[dict[str, Any]] = field(default_factory=list)

    # Narrative (human-readable summary)
    summary: str = ""
    narrative: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "phase": self.phase.value,
            "urgency": self.urgency.value,
            "energy": self.energy.value,
            "social": self.social.value,
            "travel": self.travel.to_dict(),
            "work": self.work.to_dict(),
            "home": self.home.to_dict(),
            "environment": self.environment.to_dict(),
            "current_event": {
                "title": self.current_event.title,
                "minutes_until": self.current_event.minutes_until,
            }
            if self.current_event
            else None,
            "upcoming_event_count": len(self.upcoming_events),
            "projection": self.projection.to_dict(),
            "anticipations": self.anticipations,  # Dec 30, 2025: Proactive desires
            "summary": self.summary,
            "narrative": self.narrative,
        }

    def encode_to_perception(self) -> list[float]:
        """Encode situation to perception vector (256 dims).

        This is the COMPREHENSION layer for the World Model.
        Layout:
        - 0-31: Phase & state
        - 32-63: Travel context
        - 64-95: Work context
        - 96-127: Home context
        - 128-159: Environment context
        - 160-191: Events & calendar
        - 192-223: Projections
        - 224-255: Reserved
        """
        vector = [0.0] * 256

        # Phase encoding (0-31)
        phase_map = {
            SituationPhase.SLEEPING: 0.0,
            SituationPhase.WAKING: 0.1,
            SituationPhase.MORNING_ROUTINE: 0.2,
            SituationPhase.COMMUTING: 0.3,
            SituationPhase.WORKING: 0.4,
            SituationPhase.IN_MEETING: 0.5,
            SituationPhase.FOCUSED: 0.6,
            SituationPhase.BREAK: 0.7,
            SituationPhase.EXERCISING: 0.8,
            SituationPhase.RELAXING: 0.85,
            SituationPhase.WINDING_DOWN: 0.9,
            SituationPhase.UNKNOWN: 0.5,
        }
        vector[0] = phase_map.get(self.phase, 0.5)

        urgency_map = {
            UrgencyLevel.CALM: 0.0,
            UrgencyLevel.NORMAL: 0.25,
            UrgencyLevel.BUSY: 0.5,
            UrgencyLevel.URGENT: 0.75,
            UrgencyLevel.CRITICAL: 1.0,
        }
        vector[1] = urgency_map.get(self.urgency, 0.25)

        energy_map = {EnergyLevel.LOW: 0.0, EnergyLevel.MEDIUM: 0.5, EnergyLevel.HIGH: 1.0}
        vector[2] = energy_map.get(self.energy, 0.5)

        social_map = {
            SocialContext.ALONE: 0.0,
            SocialContext.WITH_PARTNER: 0.3,
            SocialContext.WITH_FAMILY: 0.4,
            SocialContext.WITH_COLLEAGUES: 0.5,
            SocialContext.WITH_FRIENDS: 0.6,
            SocialContext.IN_PUBLIC: 0.7,
            SocialContext.HOSTING: 0.9,
        }
        vector[3] = social_map.get(self.social, 0.0)

        # Travel context (32-63)
        travel_offset = 32
        vector[travel_offset] = float(self.travel.is_traveling)
        vector[travel_offset + 1] = float(self.travel.is_leaving_soon)
        if self.travel.travel_time_minutes:
            vector[travel_offset + 2] = min(self.travel.travel_time_minutes / 60.0, 1.0)
        traffic_map = {"light": 0.9, "normal": 0.6, "heavy": 0.2, "unknown": 0.5}
        vector[travel_offset + 3] = traffic_map.get(self.travel.traffic_condition, 0.5)
        vector[travel_offset + 4] = float(self.travel.needs_umbrella)
        vector[travel_offset + 5] = float(self.travel.needs_jacket)

        # Work context (64-95)
        work_offset = 64
        vector[work_offset] = float(self.work.is_work_time)
        vector[work_offset + 1] = float(self.work.is_in_meeting)
        vector[work_offset + 2] = float(self.work.is_focused)
        if self.work.next_meeting_minutes is not None:
            vector[work_offset + 3] = min(self.work.next_meeting_minutes / 120.0, 1.0)
        vector[work_offset + 4] = min(self.work.unread_urgent_emails / 10.0, 1.0)
        vector[work_offset + 5] = min(self.work.pending_tasks / 20.0, 1.0)

        # Home context (96-127)
        home_offset = 96
        vector[home_offset] = float(self.home.is_home)
        vector[home_offset + 1] = float(self.home.is_alone)
        vector[home_offset + 2] = float(self.home.is_comfortable)
        security_map = {"armed_away": 0.0, "armed_stay": 0.5, "disarmed": 1.0}
        vector[home_offset + 3] = security_map.get(self.home.security_status, 0.5)
        vector[home_offset + 4] = min(len(self.home.lights_on) / 20.0, 1.0)
        vector[home_offset + 5] = min(len(self.home.recent_motion) / 5.0, 1.0)

        # Environment context (128-159)
        env_offset = 128
        if self.environment.temperature_f:
            vector[env_offset] = (self.environment.temperature_f - 32) / 68.0
        vector[env_offset + 1] = float(self.environment.is_raining)
        vector[env_offset + 2] = float(self.environment.will_rain_soon)
        vector[env_offset + 3] = float(self.environment.is_dark_outside)
        air_map = {"good": 0.9, "moderate": 0.5, "poor": 0.1}
        vector[env_offset + 4] = air_map.get(self.environment.air_quality, 0.5)

        # Projections (192-223)
        proj_offset = 192
        vector[proj_offset] = phase_map.get(self.projection.likely_next_phase, 0.5)
        vector[proj_offset + 1] = self.projection.next_phase_confidence
        vector[proj_offset + 2] = min(self.projection.next_phase_minutes / 60.0, 1.0)
        vector[proj_offset + 3] = float(self.projection.should_leave_soon)
        vector[proj_offset + 4] = self.projection.interrupt_risk

        return vector


# =============================================================================
# SITUATION AWARENESS ENGINE
# =============================================================================


class SituationAwarenessEngine:
    """Engine that builds situation awareness from raw signals.

    This is WHERE reasoning happens.
    """

    def __init__(self) -> None:
        self._last_situation: Situation | None = None
        self._last_update: float = 0
        self._history: list[Situation] = []  # Last N situations for trend analysis
        self._max_history = 20

    async def assess(
        self,
        sensory_state: dict[str, Any] | None = None,
        world_state: dict[str, Any] | None = None,
    ) -> Situation:
        """Assess current situation from all available signals.

        This is THE main reasoning function.
        """
        now = datetime.now()

        # Get sensory data if not provided
        if sensory_state is None:
            sensory_state = await self._get_sensory_state()

        if world_state is None:
            world_state = await self._get_world_state()

        # Level 1: Perception (already done by sensors)
        # Level 2: Comprehension (build contexts)
        travel = self._assess_travel(sensory_state, world_state)
        work = self._assess_work(sensory_state, world_state)
        home = self._assess_home(sensory_state)
        environment = self._assess_environment(sensory_state, world_state)
        events = self._assess_events(sensory_state)

        # Infer phase from contexts
        phase = self._infer_phase(travel, work, home, environment, events, world_state)

        # Infer urgency
        urgency = self._infer_urgency(travel, work, events)

        # Infer energy (from time, sleep, activity)
        energy = self._infer_energy(sensory_state, world_state)

        # Infer social context
        social = self._infer_social(home, events)

        # Level 3: Projection
        projection = self._project_future(phase, travel, work, events, world_state)

        # Build narrative
        summary, narrative = self._build_narrative(
            phase, urgency, travel, work, home, environment, events, projection
        )

        # Level 4: Anticipation (Dec 30, 2025)
        # Get proactive suggestions from Theory of Mind
        anticipations = await self._get_anticipations(sensory_state)

        situation = Situation(
            timestamp=now,
            phase=phase,
            urgency=urgency,
            energy=energy,
            social=social,
            travel=travel,
            work=work,
            home=home,
            environment=environment,
            current_event=events[0] if events and events[0].is_now else None,
            upcoming_events=events[:5] if events else [],
            projection=projection,
            anticipations=anticipations,
            summary=summary,
            narrative=narrative,
        )

        # Store in history
        self._last_situation = situation
        self._last_update = time.time()
        self._history.append(situation)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        logger.debug(f"Situation assessed: {phase.value}, urgency={urgency.value}")

        return situation

    async def _get_sensory_state(self) -> dict[str, Any]:
        """Get current sensory state."""
        try:
            from kagami.core.integrations import get_unified_sensory

            sensory = get_unified_sensory()
            if sensory:
                return await sensory.poll_all()
        except Exception as e:
            logger.debug(f"Could not get sensory state: {e}")
        return {}

    async def _get_world_state(self) -> dict[str, Any]:
        """Get current world state."""
        try:
            from kagami.core.integrations.world_state import get_world_state

            world = await get_world_state()
            return world.to_dict()
        except Exception as e:
            logger.debug(f"Could not get world state: {e}")
        return {}

    async def _get_anticipations(self, sensory_state: dict[str, Any]) -> list[dict[str, Any]]:
        """Get anticipations from Theory of Mind (Symbiote).

        ANTICIPATORY INTELLIGENCE (Dec 30, 2025):
        Level 4 of situation awareness — proactive desire inference.

        Args:
            sensory_state: Current sensory state

        Returns:
            List of anticipations with actions and confidence
        """
        try:
            from kagami.core.symbiote import get_symbiote_module

            symbiote = get_symbiote_module()

            # Get proactive actions (uses desire inference + pattern learning)
            anticipations = await symbiote.get_proactive_actions(
                sensory_state=sensory_state,
                min_confidence=0.5,  # Include medium-confidence anticipations
            )

            logger.debug(f"🔮 Anticipations: {len(anticipations)} proactive actions available")
            return anticipations

        except Exception as e:
            logger.debug(f"Could not get anticipations: {e}")
            return []

    def _assess_travel(self, sensory: dict[str, Any], world: dict[str, Any]) -> TravelContext:
        """Assess travel context from signals.

        Enhanced with SemanticMatcher (December 30, 2025):
        Uses semantic classification to infer travel purpose from calendar event titles.
        """
        travel = TravelContext()

        # Check calendar for travel events
        calendar = sensory.get("calendar", {})
        events = calendar.get("events", [])

        for event in events:
            location = event.get("location", "")
            title = event.get("title", event.get("summary", ""))

            if location and location.lower() not in ["home", "virtual", "zoom", "teams"]:
                # This event requires travel
                start = event.get("start")
                if start:
                    try:
                        if isinstance(start, str):
                            event_time = datetime.fromisoformat(start.replace("Z", "+00:00"))
                        else:
                            event_time = start
                        minutes_until = (event_time - datetime.now()).total_seconds() / 60

                        if 0 < minutes_until < 60:  # Within the next hour
                            travel.is_leaving_soon = True
                            travel.destination = location
                            travel.departure_time = datetime.now() + timedelta(
                                minutes=max(0, minutes_until - 30)
                            )

                            # Infer travel purpose using SemanticMatcher (Dec 30, 2025)
                            travel.purpose = self._infer_travel_purpose(title, location)
                    except (ValueError, TypeError):
                        pass

        # Check vehicle status
        vehicle = sensory.get("vehicle", {})
        if vehicle.get("driving"):
            travel.is_traveling = True

        # Check presence - if not home, traveling
        presence = sensory.get("presence", {})
        if not presence.get("home", True):
            travel.is_traveling = True

        # Weather-based needs
        weather = sensory.get("weather", {})
        temp = weather.get("temp_f", 65)
        condition = weather.get("condition", "").lower()

        travel.needs_jacket = temp < 55
        travel.needs_umbrella = "rain" in condition or "drizzle" in condition

        # Will rain soon (from world state forecast)
        forecast = world.get("weather_forecast", {})
        if forecast:
            travel.needs_umbrella = travel.needs_umbrella or forecast.get("umbrella_needed", False)

        # Traffic from world state
        traffic = world.get("traffic", {})
        if traffic:
            travel.traffic_condition = traffic.get("overall_condition", "unknown")

        # Infer laptop need based on purpose (Dec 30, 2025)
        if travel.purpose in ("work", "meeting"):
            travel.needs_laptop = True

        return travel

    def _infer_travel_purpose(self, event_title: str, location: str = "") -> str:
        """Infer travel purpose using SemanticMatcher.

        Uses semantic similarity to classify event titles into purpose categories.

        Args:
            event_title: Calendar event title
            location: Event location (optional, for context)

        Returns:
            Purpose category: "work", "meeting", "social", "errand", "exercise", "medical", "travel"
        """
        try:
            from kagami.core.integrations.semantic_matcher import get_semantic_matcher

            matcher = get_semantic_matcher()

            # Combine title and location for richer context
            text = f"{event_title} at {location}" if location else event_title

            result = matcher.classify(text)

            if result and result.get("confidence", 0) > 0.4:
                return result.get("category", "unknown")

        except ImportError:
            logger.debug("SemanticMatcher not available for travel purpose inference")
        except Exception as e:
            logger.debug(f"Travel purpose inference failed: {e}")

        # Fallback: keyword matching
        title_lower = event_title.lower()

        keyword_mapping = {
            "work": ["standup", "sync", "sprint", "review", "planning", "1:1", "team"],
            "meeting": ["meeting", "call", "interview", "presentation"],
            "social": ["dinner", "lunch", "coffee", "drinks", "party", "hangout"],
            "exercise": ["gym", "workout", "run", "yoga", "class", "training"],
            "medical": ["doctor", "dentist", "appointment", "checkup", "therapy"],
            "errand": ["pickup", "drop off", "shopping", "grocery", "haircut"],
        }

        for purpose, keywords in keyword_mapping.items():
            if any(kw in title_lower for kw in keywords):
                return purpose

        return "unknown"

    def _assess_work(self, sensory: dict[str, Any], world: dict[str, Any]) -> WorkContext:
        """Assess work context from signals."""
        work = WorkContext()

        # Time context
        time_ctx = world.get("time", {})
        work.is_work_time = time_ctx.get("is_work_hours", False)

        # Calendar for meetings
        calendar = sensory.get("calendar", {})
        events = calendar.get("events", [])

        for event in events:
            attendees = event.get("attendees", [])
            if len(attendees) > 1:  # Meeting has other people
                start = event.get("start")
                end = event.get("end")
                if start:
                    try:
                        if isinstance(start, str):
                            event_time = datetime.fromisoformat(start.replace("Z", "+00:00"))
                        else:
                            event_time = start

                        now = datetime.now()
                        minutes_until = (event_time - now).total_seconds() / 60

                        # Check if in meeting now
                        if end:
                            if isinstance(end, str):
                                end_time = datetime.fromisoformat(end.replace("Z", "+00:00"))
                            else:
                                end_time = end
                            if event_time <= now <= end_time:
                                work.is_in_meeting = True

                        # Track next meeting
                        if minutes_until > 0:
                            if (
                                work.next_meeting_minutes is None
                                or minutes_until < work.next_meeting_minutes
                            ):
                                work.next_meeting_minutes = int(minutes_until)
                    except (ValueError, TypeError):
                        pass

        # Email urgency
        gmail = sensory.get("gmail", {})
        urgent = gmail.get("urgent_count", 0)
        work.unread_urgent_emails = urgent

        # Linear tasks
        linear = sensory.get("linear", {})
        work.pending_tasks = linear.get("my_issues_count", 0)

        return work

    def _assess_home(self, sensory: dict[str, Any]) -> HomeContext:
        """Assess home context from signals."""
        home = HomeContext()

        # Presence
        presence = sensory.get("presence", {})
        home.is_home = presence.get("home", True)
        home.is_alone = presence.get("alone", True)

        # Lights
        lights = sensory.get("lights", {})
        home.lights_on = lights.get("on_lights", [])

        # Climate
        climate = sensory.get("climate", {})
        home.temperature_f = climate.get("temperature_f")
        home.is_comfortable = climate.get("is_comfortable", True)

        # Security
        security = sensory.get("security", {})
        home.security_status = security.get("status", "armed_stay")

        # Motion
        motion = sensory.get("motion", {})
        home.recent_motion = motion.get("recent_rooms", [])

        return home

    def _assess_environment(
        self, sensory: dict[str, Any], world: dict[str, Any]
    ) -> EnvironmentContext:
        """Assess environment context.

        Now uses celestial calculations for sunrise/sunset times
        instead of leaving them as None.
        """
        env = EnvironmentContext()

        weather = sensory.get("weather", {})
        env.weather_condition = weather.get("condition", "unknown")
        env.temperature_f = weather.get("temp_f")
        env.is_raining = "rain" in env.weather_condition.lower()

        # Use celestial module for accurate sunrise/sunset data
        try:
            from kagami.core.celestial import (
                HOME_LATITUDE,
                HOME_LONGITUDE,
                is_sun_up,
                sun_times,
            )

            times = sun_times(HOME_LATITUDE, HOME_LONGITUDE)
            env.is_dark_outside = not is_sun_up()

            # Calculate minutes since sunrise / until sunset
            mins_since_sunrise = times.minutes_since_sunrise()
            mins_until_sunset = times.minutes_until_sunset()

            if mins_since_sunrise is not None:
                env.sunrise_minutes_ago = int(mins_since_sunrise)
            if mins_until_sunset is not None:
                env.sunset_minutes_until = int(mins_until_sunset)

        except ImportError:
            # Fallback to weather API data
            env.is_dark_outside = not weather.get("is_daytime", True)

        # Forecast from world state
        forecast = world.get("weather_forecast", {})
        if forecast:
            env.will_rain_soon = forecast.get("umbrella_needed", False)

        return env

    def _assess_events(self, sensory: dict[str, Any]) -> list[ActiveEvent]:
        """Extract and sort active/upcoming events."""
        events: list[ActiveEvent] = []

        calendar = sensory.get("calendar", {})
        for event in calendar.get("events", []):
            try:
                start = event.get("start")
                if isinstance(start, str):
                    start_time = datetime.fromisoformat(start.replace("Z", "+00:00"))
                else:
                    start_time = start or datetime.now()

                end = event.get("end")
                if end:
                    if isinstance(end, str):
                        end_time = datetime.fromisoformat(end.replace("Z", "+00:00"))
                    else:
                        end_time = end
                else:
                    end_time = None

                events.append(
                    ActiveEvent(
                        title=event.get("summary", "Event"),
                        start_time=start_time,
                        end_time=end_time,
                        location=event.get("location"),
                        attendees=event.get("attendees", []),
                        is_meeting=len(event.get("attendees", [])) > 1,
                    )
                )
            except (ValueError, TypeError):
                continue

        # Sort by start time
        events.sort(key=lambda e: e.start_time)

        return events

    def _infer_phase(
        self,
        travel: TravelContext,
        work: WorkContext,
        home: HomeContext,
        environment: EnvironmentContext,
        events: list[ActiveEvent],
        world: dict[str, Any],
    ) -> SituationPhase:
        """Infer current life phase from all contexts."""
        time_ctx = world.get("time", {})
        hour = time_ctx.get("hour", 12)
        time_of_day = time_ctx.get("time_of_day", "afternoon")

        # Sleep detection
        if time_of_day == "night" and hour < 6:
            return SituationPhase.SLEEPING

        # Travel
        if travel.is_traveling:
            return SituationPhase.COMMUTING

        # Work phases
        if work.is_in_meeting:
            return SituationPhase.IN_MEETING

        if work.is_work_time:
            if work.is_focused:
                return SituationPhase.FOCUSED
            return SituationPhase.WORKING

        # Time-based phases
        if time_of_day == "morning" and 6 <= hour < 9:
            if hour < 7:
                return SituationPhase.WAKING
            return SituationPhase.MORNING_ROUTINE

        if time_of_day == "evening" and hour >= 21:
            return SituationPhase.WINDING_DOWN

        if time_of_day == "evening":
            return SituationPhase.RELAXING

        return SituationPhase.UNKNOWN

    def _infer_urgency(
        self,
        travel: TravelContext,
        work: WorkContext,
        events: list[ActiveEvent],
    ) -> UrgencyLevel:
        """Infer urgency level."""
        # Critical: very close event
        if events:
            minutes = events[0].minutes_until
            if 0 < minutes < 5:
                return UrgencyLevel.CRITICAL

        # Urgent: leaving soon or meeting soon
        if travel.is_leaving_soon:
            return UrgencyLevel.URGENT

        if work.next_meeting_minutes and work.next_meeting_minutes < 15:
            return UrgencyLevel.URGENT

        # Busy: multiple urgent emails or tasks
        if work.unread_urgent_emails > 3 or work.pending_tasks > 10:
            return UrgencyLevel.BUSY

        # Normal
        if work.is_work_time:
            return UrgencyLevel.NORMAL

        return UrgencyLevel.CALM

    def _infer_energy(self, sensory: dict[str, Any], world: dict[str, Any]) -> EnergyLevel:
        """Infer energy level from sleep, time, activity."""
        time_ctx = world.get("time", {})
        hour = time_ctx.get("hour", 12)

        # Get sleep data from sensory inputs to inform energy level
        sleep = sensory.get("sleep", {})
        sleep_quality = sleep.get("quality", 0.7)  # 0-1 scale (0=poor, 1=excellent)
        sleep_hours = sleep.get("hours", 7.5)  # Hours of sleep last night
        sleep_efficiency = sleep.get("efficiency", 0.85)  # Time asleep / time in bed

        # Calculate base energy from sleep quality
        sleep_energy_factor = (
            sleep_quality * 0.4 + min(sleep_hours / 8.0, 1.0) * 0.4 + sleep_efficiency * 0.2
        )

        # Calculate circadian energy pattern based on time of day
        if 6 <= hour < 9:
            base_energy = 0.7  # Morning moderate
        elif 9 <= hour < 12:
            base_energy = 0.9  # Morning peak
        elif 12 <= hour < 14:
            base_energy = 0.6  # Post-lunch dip
        elif 14 <= hour < 17:
            base_energy = 0.8  # Afternoon recovery
        elif 17 <= hour < 21:
            base_energy = 0.7  # Evening moderate
        elif hour >= 21 or hour < 6:
            base_energy = 0.3  # Night/early morning low
        else:
            base_energy = 0.7  # Default moderate

        # Combine circadian pattern with sleep-based energy factor
        final_energy = (base_energy * 0.6) + (sleep_energy_factor * 0.4)

        # Convert to EnergyLevel enum
        if final_energy >= 0.8:
            return EnergyLevel.HIGH
        elif final_energy >= 0.6:
            return EnergyLevel.MEDIUM
        else:
            return EnergyLevel.LOW

    def _infer_social(self, home: HomeContext, events: list[ActiveEvent]) -> SocialContext:
        """Infer social context."""
        if not home.is_home:
            return SocialContext.IN_PUBLIC

        if not home.is_alone:
            # Could be more specific with presence data
            return SocialContext.WITH_PARTNER

        # Check if in meeting (virtual social)
        for event in events:
            if event.is_now and event.is_meeting:
                return SocialContext.WITH_COLLEAGUES

        return SocialContext.ALONE

    def _project_future(
        self,
        phase: SituationPhase,
        travel: TravelContext,
        work: WorkContext,
        events: list[ActiveEvent],
        world: dict[str, Any],
    ) -> SituationProjection:
        """Project what will happen next."""
        projection = SituationProjection()
        projections: list[Projection] = []

        time_ctx = world.get("time", {})
        hour = time_ctx.get("hour", 12)

        # Event-based projections
        if events:
            for event in events[:3]:  # Next 3 events
                if event.minutes_until > 0:
                    projections.append(
                        Projection(
                            description=f"Event: {event.title}",
                            confidence=0.9,
                            timeframe_minutes=event.minutes_until,
                            recommended_action="Prepare" if event.minutes_until < 30 else None,
                            urgency=UrgencyLevel.URGENT
                            if event.minutes_until < 15
                            else UrgencyLevel.NORMAL,
                        )
                    )

        # Travel projection
        if travel.is_leaving_soon:
            projection.should_leave_soon = True
            projections.append(
                Projection(
                    description=f"Need to leave for {travel.destination}",
                    confidence=0.8,
                    timeframe_minutes=30,
                    recommended_action="Get ready to leave",
                    urgency=UrgencyLevel.URGENT,
                )
            )

        # Meeting projection
        if work.next_meeting_minutes and work.next_meeting_minutes < 30:
            projections.append(
                Projection(
                    description="Meeting coming up",
                    confidence=0.95,
                    timeframe_minutes=work.next_meeting_minutes,
                    recommended_action="Wrap up current task",
                    urgency=UrgencyLevel.BUSY,
                )
            )

        # Phase transition projections
        if phase == SituationPhase.MORNING_ROUTINE:
            projection.likely_next_phase = SituationPhase.WORKING
            projection.next_phase_confidence = 0.8
            projection.next_phase_minutes = 30

        elif phase == SituationPhase.WORKING:
            if work.next_meeting_minutes and work.next_meeting_minutes < 60:
                projection.likely_next_phase = SituationPhase.IN_MEETING
                projection.next_phase_minutes = work.next_meeting_minutes
            else:
                projection.likely_next_phase = SituationPhase.BREAK
                projection.next_phase_minutes = 90

        elif phase == SituationPhase.RELAXING:
            if hour >= 22:
                projection.likely_next_phase = SituationPhase.WINDING_DOWN
                projection.next_phase_confidence = 0.7
                projection.next_phase_minutes = 30

        # Interrupt risk
        if work.unread_urgent_emails > 0:
            projection.interrupt_risk = min(work.unread_urgent_emails * 0.2, 0.8)

        projection.projections = projections
        return projection

    def _build_narrative(
        self,
        phase: SituationPhase,
        urgency: UrgencyLevel,
        travel: TravelContext,
        work: WorkContext,
        home: HomeContext,
        environment: EnvironmentContext,
        events: list[ActiveEvent],
        projection: SituationProjection,
    ) -> tuple[str, str]:
        """Build human-readable summary and narrative."""
        # Summary (one line)
        summary_parts = [phase.value.replace("_", " ").title()]

        if urgency in [UrgencyLevel.URGENT, UrgencyLevel.CRITICAL]:
            summary_parts.append(f"({urgency.value})")

        if travel.is_leaving_soon:
            summary_parts.append(f"• Leaving soon for {travel.destination or 'event'}")

        if work.is_in_meeting:
            summary_parts.append("• In meeting")
        elif work.next_meeting_minutes and work.next_meeting_minutes < 30:
            summary_parts.append(f"• Meeting in {work.next_meeting_minutes}m")

        summary = " ".join(summary_parts)

        # Narrative (paragraph)
        narrative_parts = []

        # Phase description
        phase_desc = {
            SituationPhase.SLEEPING: "Tim is sleeping.",
            SituationPhase.WAKING: "Tim is waking up.",
            SituationPhase.MORNING_ROUTINE: "Tim is in his morning routine.",
            SituationPhase.COMMUTING: "Tim is traveling.",
            SituationPhase.WORKING: "Tim is working.",
            SituationPhase.IN_MEETING: "Tim is in a meeting.",
            SituationPhase.FOCUSED: "Tim is in deep focus mode.",
            SituationPhase.RELAXING: "Tim is relaxing.",
            SituationPhase.WINDING_DOWN: "Tim is winding down for bed.",
        }
        narrative_parts.append(phase_desc.get(phase, ""))

        # Location
        if home.is_home:
            if home.current_room:
                narrative_parts.append(f"He's in the {home.current_room}.")
            else:
                narrative_parts.append("He's at home.")
        else:
            if travel.destination:
                narrative_parts.append(f"He's heading to {travel.destination}.")

        # What's next
        if projection.projections:
            next_proj = projection.projections[0]
            narrative_parts.append(f"Coming up: {next_proj.description}.")

        # Weather/environment
        if environment.is_raining:
            narrative_parts.append("It's raining outside.")
        elif environment.will_rain_soon:
            narrative_parts.append("Rain is expected soon.")

        # Needs
        needs = []
        if travel.needs_umbrella:
            needs.append("umbrella")
        if travel.needs_jacket:
            needs.append("jacket")
        if needs:
            narrative_parts.append(f"He'll need a {' and '.join(needs)}.")

        narrative = " ".join(narrative_parts)

        return summary, narrative


# =============================================================================
# SINGLETON & FACTORY
# =============================================================================

_engine: SituationAwarenessEngine | None = None


def get_situation_engine() -> SituationAwarenessEngine:
    """Get singleton situation awareness engine."""
    global _engine
    if _engine is None:
        _engine = SituationAwarenessEngine()
    return _engine


def reset_situation_engine() -> None:
    """Reset engine (for testing)."""
    global _engine
    _engine = None


async def get_current_situation() -> Situation:
    """Get current situation assessment."""
    engine = get_situation_engine()
    return await engine.assess()


__all__ = [
    # Core types
    "ActiveEvent",
    "EnergyLevel",
    "EnvironmentContext",
    "HomeContext",
    "Projection",
    "Situation",
    "SituationAwarenessEngine",
    "SituationPhase",
    "SituationProjection",
    "SocialContext",
    "TravelContext",
    "UrgencyLevel",
    "WorkContext",
    # Factory functions
    "get_current_situation",
    "get_situation_engine",
    "reset_situation_engine",
]
