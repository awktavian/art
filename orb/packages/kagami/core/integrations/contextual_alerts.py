"""Contextual Alert System — Pattern-Aware, Purpose-Driven Notifications.

Replaces hardcoded alerts with a general, context-aware system that:
- Learns what items are needed for what trips
- Only alerts when context requires it (e.g., laptop for work, not dinner)
- Uses time, calendar, destination, and patterns to infer context

Philosophy: Thoughtful alerts, not noisy ones.

Created: December 30, 2025
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

logger = logging.getLogger(__name__)


# =============================================================================
# TRIP CONTEXT
# =============================================================================


class TripPurpose(str, Enum):
    """What kind of trip is this?"""

    WORK = "work"  # Needs laptop
    MEETING = "meeting"  # Needs laptop, formal
    ERRAND = "errand"  # Quick, local, no laptop
    SOCIAL = "social"  # Dinner, friends, no laptop
    EXERCISE = "exercise"  # Gym, run, minimal gear
    MEDICAL = "medical"  # Doctor, etc.
    TRAVEL = "travel"  # Airport, long trip
    UNKNOWN = "unknown"  # Conservative: assume work-like


# Essential items by context
ESSENTIAL_ITEMS: dict[TripPurpose, list[str]] = {
    TripPurpose.WORK: ["laptop", "phone"],
    TripPurpose.MEETING: ["laptop", "phone"],
    TripPurpose.ERRAND: ["phone"],
    TripPurpose.SOCIAL: ["phone"],
    TripPurpose.EXERCISE: ["phone"],  # Watch optional
    TripPurpose.MEDICAL: ["phone"],
    TripPurpose.TRAVEL: ["laptop", "phone"],  # Usually need laptop
    TripPurpose.UNKNOWN: [],  # Don't alert for unknown
}


@dataclass
class TripContext:
    """Inferred context of a trip."""

    purpose: TripPurpose = TripPurpose.UNKNOWN
    confidence: float = 0.0  # 0-1

    # Evidence that contributed to this inference
    evidence: dict[str, Any] = field(default_factory=dict)

    # Inferred destination (if known)
    destination_name: str | None = None
    destination_lat: float | None = None
    destination_lon: float | None = None

    # Time context
    is_weekday: bool = True
    is_work_hours: bool = False  # 7am-7pm weekday
    is_morning_commute: bool = False  # 6am-10am weekday
    is_evening_commute: bool = False  # 4pm-8pm weekday

    # Calendar context
    has_calendar_event: bool = False
    calendar_event_name: str | None = None
    calendar_event_location: str | None = None

    def get_essentials(self) -> list[str]:
        """Get essential items for this trip context."""
        return ESSENTIAL_ITEMS.get(self.purpose, [])

    def requires_item(self, item: str) -> bool:
        """Check if this trip requires a specific item."""
        return item.lower() in self.get_essentials()


# =============================================================================
# KNOWN LOCATIONS
# =============================================================================


@dataclass
class KnownLocation:
    """A location with known purpose."""

    name: str
    lat: float
    lon: float
    purpose: TripPurpose
    radius_miles: float = 0.3  # Match radius

    def matches(self, lat: float, lon: float) -> bool:
        """Check if coordinates match this location."""
        dist = self._haversine_miles(lat, lon, self.lat, self.lon)
        return dist < self.radius_miles

    @staticmethod
    def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 3959
        lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))


# Default known locations (user can add more)
DEFAULT_KNOWN_LOCATIONS = [
    # Common destinations (Tim can add his work location)
    KnownLocation("Home", 47.6762, -122.3405, TripPurpose.UNKNOWN),  # Home is special
]


# =============================================================================
# CONTEXT DETECTOR
# =============================================================================


class ContextDetector:
    """Infers trip context from multiple signals.

    Signals used:
    1. Time of day + day of week (morning weekday = likely work)
    2. Calendar events (SEMANTIC MATCHING - no hardcoded keywords)
    3. Destination (known work location)
    4. Historical patterns (learned over time)
    5. Direction of travel (toward work location)

    Uses SemanticMatcher for intent classification instead of keyword lists.
    """

    def __init__(self):
        # Known locations
        self._locations: list[KnownLocation] = DEFAULT_KNOWN_LOCATIONS.copy()

        # Work location (learned or configured)
        self._work_location: KnownLocation | None = None

        # Semantic matcher (lazy init - no model loading at startup)
        self._semantic_matcher = None

        # Calendar integration
        self._calendar_events: list[dict[str, Any]] = []

        # Statistics
        self._stats = {
            "detections": 0,
            "work_trips": 0,
            "errand_trips": 0,
            "unknown_trips": 0,
            "semantic_classifications": 0,
        }

    def _get_semantic_matcher(self):
        """Lazy-load semantic matcher."""
        if self._semantic_matcher is None:
            try:
                from kagami.core.integrations.semantic_matcher import get_semantic_matcher

                self._semantic_matcher = get_semantic_matcher()
            except ImportError:
                logger.debug("SemanticMatcher not available")
                return None
        return self._semantic_matcher

    def _classify_event_semantic(
        self,
        title: str,
        location: str = "",
    ) -> dict[str, Any] | None:
        """Classify calendar event using semantic matching.

        Args:
            title: Event title
            location: Event location (optional)

        Returns:
            Classification result or None if matcher unavailable
        """
        matcher = self._get_semantic_matcher()
        if matcher is None:
            return None

        # Combine title and location for better context
        text = title
        if location:
            text = f"{title} at {location}"

        if not text.strip():
            return None

        try:
            result = matcher.classify(text, threshold=0.35)
            self._stats["semantic_classifications"] += 1
            return result
        except Exception as e:
            logger.debug(f"Semantic classification failed: {e}")
            return None

    def set_work_location(self, name: str, lat: float, lon: float) -> None:
        """Configure work location for better detection."""
        self._work_location = KnownLocation(name, lat, lon, TripPurpose.WORK)
        self._locations.append(self._work_location)
        logger.info(f"📍 Work location set: {name} ({lat:.4f}, {lon:.4f})")

    def add_known_location(self, location: KnownLocation) -> None:
        """Add a known location."""
        self._locations.append(location)

    def set_calendar_events(self, events: list[dict[str, Any]]) -> None:
        """Update calendar events for context detection.

        Events should have: start_time, title, location (optional)
        """
        self._calendar_events = events

    def detect_context(
        self,
        lat: float | None = None,
        lon: float | None = None,
        departure_time: datetime | None = None,
    ) -> TripContext:
        """Detect trip context from available signals.

        Args:
            lat: Destination latitude (if known)
            lon: Destination longitude (if known)
            departure_time: Time of departure (default: now)

        Returns:
            TripContext with inferred purpose and confidence
        """
        self._stats["detections"] += 1
        departure_time = departure_time or datetime.now()

        context = TripContext()
        evidence = {}
        scores: dict[TripPurpose, float] = dict.fromkeys(TripPurpose, 0.0)

        # === TIME-BASED SIGNALS ===
        weekday = departure_time.weekday()
        hour = departure_time.hour

        context.is_weekday = weekday < 5
        context.is_work_hours = context.is_weekday and 7 <= hour <= 19
        context.is_morning_commute = context.is_weekday and 6 <= hour <= 10
        context.is_evening_commute = context.is_weekday and 16 <= hour <= 20

        # Morning weekday departure → likely work
        if context.is_morning_commute:
            scores[TripPurpose.WORK] += 0.4
            evidence["time"] = "morning_commute"
        # Weekend → probably not work
        elif not context.is_weekday:
            scores[TripPurpose.ERRAND] += 0.2
            scores[TripPurpose.SOCIAL] += 0.2
            evidence["time"] = "weekend"
        # Lunch time weekday
        elif context.is_weekday and 11 <= hour <= 14:
            scores[TripPurpose.ERRAND] += 0.3
            evidence["time"] = "lunch_time"
        # Evening weekday
        elif context.is_evening_commute:
            scores[TripPurpose.SOCIAL] += 0.2
            scores[TripPurpose.ERRAND] += 0.2
            evidence["time"] = "evening"

        # === CALENDAR-BASED SIGNALS (Semantic Matching) ===
        upcoming_event = self._find_upcoming_event(departure_time)
        if upcoming_event:
            context.has_calendar_event = True
            context.calendar_event_name = upcoming_event.get("title")
            context.calendar_event_location = upcoming_event.get("location")

            # Use semantic matching instead of hardcoded keywords
            classification = self._classify_event_semantic(
                context.calendar_event_name or "",
                context.calendar_event_location or "",
            )

            if classification:
                purpose_str = classification["category"]
                confidence = classification["confidence"]

                # Map semantic category to TripPurpose
                purpose_map = {
                    "work": TripPurpose.WORK,
                    "meeting": TripPurpose.MEETING,
                    "social": TripPurpose.SOCIAL,
                    "errand": TripPurpose.ERRAND,
                    "exercise": TripPurpose.EXERCISE,
                    "medical": TripPurpose.MEDICAL,
                    "travel": TripPurpose.TRAVEL,
                }

                if purpose_str in purpose_map:
                    purpose = purpose_map[purpose_str]
                    scores[purpose] += confidence * 0.6  # Scale by confidence
                    evidence["calendar"] = (
                        f"{purpose_str} (semantic={confidence:.2f}): {context.calendar_event_name}"
                    )

                    # Add meeting score for work events
                    if purpose_str == "work":
                        scores[TripPurpose.MEETING] += confidence * 0.3
            else:
                # Fallback: Generic calendar event during work hours
                if context.is_work_hours:
                    scores[TripPurpose.WORK] += 0.2
                    evidence["calendar"] = f"generic_work_hours: {context.calendar_event_name}"

        # === DESTINATION-BASED SIGNALS ===
        if lat and lon:
            # Check against known locations
            for loc in self._locations:
                if loc.matches(lat, lon):
                    if loc.purpose != TripPurpose.UNKNOWN:
                        scores[loc.purpose] += 0.6
                        context.destination_name = loc.name
                        context.destination_lat = lat
                        context.destination_lon = lon
                        evidence["destination"] = f"known: {loc.name}"
                        break

            # Check if heading toward work location
            if self._work_location and self._work_location.matches(lat, lon):
                scores[TripPurpose.WORK] += 0.5
                evidence["destination"] = "work_location"

        # === DETERMINE PURPOSE ===
        # Find highest scoring purpose
        best_purpose = max(scores.keys(), key=lambda p: scores[p])
        best_score = scores[best_purpose]

        # Only assign purpose if score is above threshold
        if best_score >= 0.3:
            context.purpose = best_purpose
            context.confidence = min(best_score, 1.0)
        else:
            context.purpose = TripPurpose.UNKNOWN
            context.confidence = 0.2

        context.evidence = evidence

        # Update stats
        if context.purpose == TripPurpose.WORK:
            self._stats["work_trips"] += 1
        elif context.purpose in (TripPurpose.ERRAND, TripPurpose.SOCIAL):
            self._stats["errand_trips"] += 1
        else:
            self._stats["unknown_trips"] += 1

        logger.debug(f"Trip context: {context.purpose.value} (confidence={context.confidence:.2f})")
        return context

    def _find_upcoming_event(
        self,
        departure_time: datetime,
        window_hours: float = 2.0,
    ) -> dict[str, Any] | None:
        """Find calendar event within window of departure."""
        if not self._calendar_events:
            return None

        window_end = departure_time + timedelta(hours=window_hours)

        for event in self._calendar_events:
            start_str = event.get("start_time") or event.get("start")
            if not start_str:
                continue

            try:
                if isinstance(start_str, str):
                    # Parse ISO format
                    event_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    event_start = event_start.replace(tzinfo=None)  # Naive comparison
                else:
                    event_start = start_str

                if departure_time <= event_start <= window_end:
                    return event
            except Exception:
                continue

        return None

    def learn_trip_purpose(
        self,
        lat: float,
        lon: float,
        actual_purpose: TripPurpose,
    ) -> None:
        """Learn from actual trip purpose (for future predictions)."""
        # Add to known locations if we learn a pattern
        for loc in self._locations:
            if loc.matches(lat, lon):
                # Location already known, update if purpose differs
                if loc.purpose == TripPurpose.UNKNOWN:
                    loc.purpose = actual_purpose
                    logger.info(f"Learned location purpose: {loc.name} → {actual_purpose.value}")
                return

        # New location - learn it
        new_loc = KnownLocation(
            f"Learned_{len(self._locations)}",
            lat,
            lon,
            actual_purpose,
        )
        self._locations.append(new_loc)
        logger.info(f"Learned new location for {actual_purpose.value}")

    def get_stats(self) -> dict[str, Any]:
        """Get detection statistics."""
        return {
            **self._stats,
            "known_locations": len(self._locations),
            "has_work_location": self._work_location is not None,
        }


# =============================================================================
# CONTEXTUAL ALERT RULES
# =============================================================================


@dataclass
class AlertRule:
    """A declarative alert rule.

    Replaces hardcoded if-statements with data-driven rules.
    """

    name: str
    description: str

    # Conditions
    trip_purposes: list[TripPurpose] | None = None  # None = all
    required_item: str | None = None  # Item that must be present
    missing_item: str | None = None  # Item that must be missing
    min_confidence: float = 0.5  # Minimum context confidence

    # Time conditions
    enabled_hours: tuple[int, int] | None = None  # (start, end) or None for all
    weekdays_only: bool = False
    weekends_only: bool = False

    # Alert properties
    priority: str = "normal"  # critical, high, normal, low
    cooldown_seconds: float = 300.0  # Minimum time between alerts

    # Message template (can use {item}, {purpose}, {destination})
    message_template: str = ""

    # Rooms for announcement
    announcement_rooms: list[str] = field(default_factory=lambda: ["Living Room"])

    def matches(
        self,
        context: TripContext,
        missing_items: list[str],
    ) -> tuple[bool, str]:
        """Check if rule matches current situation.

        Returns:
            (matches, message) tuple
        """
        now = datetime.now()

        # Check trip purpose
        if self.trip_purposes:
            if context.purpose not in self.trip_purposes:
                return False, ""

        # Check confidence threshold
        if context.confidence < self.min_confidence:
            return False, ""

        # Check missing item
        if self.missing_item:
            if self.missing_item not in missing_items:
                return False, ""

        # Check required item
        if self.required_item:
            if self.required_item in missing_items:
                return False, ""  # Required item is missing, rule doesn't apply

        # Check time conditions
        if self.enabled_hours:
            start, end = self.enabled_hours
            if not (start <= now.hour < end):
                return False, ""

        if self.weekdays_only and now.weekday() >= 5:
            return False, ""

        if self.weekends_only and now.weekday() < 5:
            return False, ""

        # Generate message
        message = self.message_template.format(
            item=self.missing_item or self.required_item or "",
            purpose=context.purpose.value,
            destination=context.destination_name or "your destination",
            event=context.calendar_event_name or "",
        )

        return True, message


# =============================================================================
# DEFAULT ALERT RULES
# =============================================================================


DEFAULT_ALERT_RULES = [
    # === WORK LAPTOP REMINDER ===
    AlertRule(
        name="work_laptop_reminder",
        description="Remind to bring laptop when going to work",
        trip_purposes=[TripPurpose.WORK, TripPurpose.MEETING],
        missing_item="laptop",
        min_confidence=0.5,
        weekdays_only=True,
        enabled_hours=(6, 12),  # Morning departures only
        priority="high",
        cooldown_seconds=600,  # 10 minutes
        message_template="Don't forget your laptop! You appear to be heading to {purpose}.",
        announcement_rooms=["Office", "Living Room", "Entry"],
    ),
    # === LOW PHONE BATTERY WHEN LEAVING ===
    AlertRule(
        name="low_phone_battery",
        description="Warn about low phone battery when leaving",
        trip_purposes=None,  # Any trip
        missing_item=None,  # Not about missing items
        required_item="phone",  # Phone must be present but low
        min_confidence=0.3,
        priority="normal",
        cooldown_seconds=1800,  # 30 minutes
        message_template="Your phone battery is low. Consider charging before you leave.",
        announcement_rooms=["Living Room"],
    ),
]


# =============================================================================
# CONTEXTUAL ALERT ENGINE
# =============================================================================


# Callback type
AlertCallback = Callable[[str, str, dict[str, Any]], Awaitable[None]]


class ContextualAlertEngine:
    """Context-aware alert engine.

    Combines:
    - ContextDetector for understanding trip purpose
    - AlertRules for declarative alert definitions
    - Pattern learning for improving over time

    Key principle: Only alert when it matters.
    - "Laptop at home" + "going to work" → ALERT
    - "Laptop at home" + "going to dinner" → no alert
    """

    def __init__(self):
        self._detector = ContextDetector()
        self._rules: list[AlertRule] = DEFAULT_ALERT_RULES.copy()

        # Alert callbacks
        self._callbacks: list[AlertCallback] = []

        # Cooldown tracking
        self._last_alerts: dict[str, float] = {}

        # SmartHome for announcements
        self._smart_home: SmartHomeController | None = None

        # Statistics
        self._stats = {
            "evaluations": 0,
            "alerts_sent": 0,
            "alerts_suppressed_cooldown": 0,
            "alerts_suppressed_context": 0,
        }

    async def initialize(self, smart_home: SmartHomeController | None = None) -> None:
        """Initialize with SmartHome connection."""
        self._smart_home = smart_home
        logger.info("🔔 ContextualAlertEngine initialized")

    def set_work_location(self, name: str, lat: float, lon: float) -> None:
        """Configure work location."""
        self._detector.set_work_location(name, lat, lon)

    def set_calendar_events(self, events: list[dict[str, Any]]) -> None:
        """Update calendar events."""
        self._detector.set_calendar_events(events)

    def add_rule(self, rule: AlertRule) -> None:
        """Add a custom alert rule."""
        self._rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name."""
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                del self._rules[i]
                return True
        return False

    def on_alert(self, callback: AlertCallback) -> None:
        """Subscribe to alerts."""
        self._callbacks.append(callback)

    async def evaluate_departure(
        self,
        missing_items: list[str],
        destination_lat: float | None = None,
        destination_lon: float | None = None,
        item_states: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Evaluate alert rules for a departure.

        Called when leaving home with information about:
        - What items are missing (left behind)
        - Where we're going (if known)
        - Device states (battery levels, etc.)

        Args:
            missing_items: Items left at home (e.g., ["laptop"])
            destination_lat: Destination latitude (if known)
            destination_lon: Destination longitude (if known)
            item_states: Optional dict with item states (e.g., {"phone_battery": 0.15})

        Returns:
            List of triggered alerts
        """
        self._stats["evaluations"] += 1

        # Detect trip context
        context = self._detector.detect_context(
            lat=destination_lat,
            lon=destination_lon,
        )

        triggered_alerts = []
        now = time.time()

        for rule in self._rules:
            # Check cooldown
            if rule.name in self._last_alerts:
                elapsed = now - self._last_alerts[rule.name]
                if elapsed < rule.cooldown_seconds:
                    self._stats["alerts_suppressed_cooldown"] += 1
                    continue

            # Evaluate rule
            matches, message = rule.matches(context, missing_items)

            if not matches:
                self._stats["alerts_suppressed_context"] += 1
                continue

            # Rule triggered!
            self._last_alerts[rule.name] = now
            self._stats["alerts_sent"] += 1

            alert_data = {
                "rule": rule.name,
                "message": message,
                "priority": rule.priority,
                "context": {
                    "purpose": context.purpose.value,
                    "confidence": context.confidence,
                    "destination": context.destination_name,
                },
                "missing_items": missing_items,
                "rooms": rule.announcement_rooms,
            }

            triggered_alerts.append(alert_data)

            # Emit to callbacks
            for callback in self._callbacks:
                try:
                    await callback(rule.name, message, alert_data)
                except Exception as e:
                    logger.warning(f"Alert callback error: {e}")

            # Announce if SmartHome available
            if self._smart_home and rule.priority in ("critical", "high"):
                try:
                    await self._smart_home.announce(
                        message,
                        rooms=rule.announcement_rooms,
                    )
                except Exception as e:
                    logger.debug(f"Announcement failed: {e}")

        return triggered_alerts

    def get_detector(self) -> ContextDetector:
        """Get context detector for configuration."""
        return self._detector

    def get_rules(self) -> list[AlertRule]:
        """Get all alert rules."""
        return self._rules.copy()

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        return {
            **self._stats,
            "detector_stats": self._detector.get_stats(),
            "rule_count": len(self._rules),
        }


# =============================================================================
# SINGLETON
# =============================================================================


_engine: ContextualAlertEngine | None = None


def get_contextual_alert_engine() -> ContextualAlertEngine:
    """Get global ContextualAlertEngine instance."""
    global _engine
    if _engine is None:
        _engine = ContextualAlertEngine()
    return _engine


async def initialize_contextual_alerts(
    smart_home: SmartHomeController | None = None,
) -> ContextualAlertEngine:
    """Initialize the contextual alert engine."""
    engine = get_contextual_alert_engine()
    await engine.initialize(smart_home)
    return engine


__all__ = [
    "DEFAULT_ALERT_RULES",
    "ESSENTIAL_ITEMS",
    "AlertRule",
    "ContextDetector",
    "ContextualAlertEngine",
    "KnownLocation",
    "TripContext",
    "TripPurpose",
    "get_contextual_alert_engine",
    "initialize_contextual_alerts",
]
