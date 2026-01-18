"""Pet Care Automation.

First-class pet integration for the Kagami household symbiosis system.

Pets are household members with:
- Presence tracking (where they are)
- Activity patterns (sleeping, playing, eating)
- Care schedules (feeding, walks, grooming)
- Smart home integration (announcements, climate, cameras)
- Behavioral signals → automation triggers

Colony: Symbiote (e₈) — Theory of Mind for all household members
Safety: h(x) ≥ 0 — Pet welfare is a safety constraint

"Bella is not a pet. Bella is a roommate with very strong opinions
about temperature control and treat frequency."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# PET ACTIVITY STATES
# =============================================================================


class PetActivityState(Enum):
    """Activity states for pets."""

    SLEEPING = "sleeping"
    RESTING = "resting"
    ALERT = "alert"
    PLAYING = "playing"
    EATING = "eating"
    DRINKING = "drinking"
    ANXIOUS = "anxious"
    NEEDS_BATHROOM = "needs_bathroom"
    WANTS_OUTSIDE = "wants_outside"
    WANTS_ATTENTION = "wants_attention"
    UNKNOWN = "unknown"


class PetCareEvent(Enum):
    """Types of pet care events."""

    FEEDING_TIME = "feeding_time"
    WALK_TIME = "walk_time"
    BATHROOM_BREAK = "bathroom_break"
    PLAY_TIME = "play_time"
    GROOMING = "grooming"
    VET_APPOINTMENT = "vet_appointment"
    MEDICATION = "medication"


# =============================================================================
# PET BEHAVIORAL SIGNALS
# =============================================================================


@dataclass
class BehavioralSignal:
    """A behavioral signal from a pet that may indicate a need."""

    signal_type: str  # e.g., "stands_by_door", "pacing", "vocal"
    confidence: float  # 0.0 - 1.0
    timestamp: float
    source: str  # e.g., "camera", "motion_sensor", "audio"
    indicates: list[str]  # Possible needs this indicates


# =============================================================================
# PET CARE SCHEDULE
# =============================================================================


@dataclass
class CareScheduleItem:
    """A scheduled care event."""

    event_type: PetCareEvent
    scheduled_time: time
    pet_id: str
    description: str
    reminder_minutes_before: int = 5
    completed: bool = False
    completed_at: datetime | None = None


@dataclass
class PetCareSchedule:
    """Complete care schedule for a pet."""

    pet_id: str
    pet_name: str
    items: list[CareScheduleItem] = field(default_factory=list)

    @classmethod
    def from_character_profile(cls, profile: Any) -> PetCareSchedule:
        """Create care schedule from pet's character profile metadata."""
        metadata = profile.metadata
        care = metadata.get("care_requirements", {})
        feeding = care.get("feeding", {})
        exercise = care.get("exercise", {})

        items = []

        # Add feeding times
        if "breakfast_time" in feeding:
            try:
                t = datetime.strptime(feeding["breakfast_time"], "%H:%M").time()
                items.append(
                    CareScheduleItem(
                        event_type=PetCareEvent.FEEDING_TIME,
                        scheduled_time=t,
                        pet_id=profile.identity_id,
                        description=f"{profile.name} breakfast",
                    )
                )
            except ValueError:
                pass

        if "dinner_time" in feeding:
            try:
                t = datetime.strptime(feeding["dinner_time"], "%H:%M").time()
                items.append(
                    CareScheduleItem(
                        event_type=PetCareEvent.FEEDING_TIME,
                        scheduled_time=t,
                        pet_id=profile.identity_id,
                        description=f"{profile.name} dinner",
                    )
                )
            except ValueError:
                pass

        # Add walk times
        for walk_time in exercise.get("preferred_walk_times", []):
            try:
                t = datetime.strptime(walk_time, "%H:%M").time()
                items.append(
                    CareScheduleItem(
                        event_type=PetCareEvent.WALK_TIME,
                        scheduled_time=t,
                        pet_id=profile.identity_id,
                        description=f"{profile.name} walk",
                    )
                )
            except ValueError:
                pass

        return cls(
            pet_id=profile.identity_id,
            pet_name=profile.name,
            items=sorted(items, key=lambda x: x.scheduled_time),
        )


# =============================================================================
# PET CARE AUTOMATION
# =============================================================================


class PetCareAutomation:
    """Automation engine for pet care.

    Integrates with:
    - HouseholdSymbiosis for presence tracking
    - SmartHome for announcements, climate, cameras
    - Scheduling for care reminders
    - Behavioral signal processing
    """

    def __init__(self) -> None:
        self._schedules: dict[str, PetCareSchedule] = {}
        self._behavioral_signals: dict[str, list[BehavioralSignal]] = {}
        self._last_check: float = 0

    def load_pet_schedules(self) -> int:
        """Load care schedules for all pets from character profiles.

        Returns:
            Number of pets loaded
        """
        try:
            from kagami.core.integrations.character_identity import (
                list_characters,
                load_character_profile,
            )

            count = 0
            for char_name in list_characters():
                profile = load_character_profile(char_name)
                if not profile or profile.role != "pet":
                    continue

                schedule = PetCareSchedule.from_character_profile(profile)
                self._schedules[profile.identity_id] = schedule
                self._behavioral_signals[profile.identity_id] = []
                count += 1

                logger.info(
                    f"🐾 Loaded care schedule for {profile.name}: "
                    f"{len(schedule.items)} scheduled events"
                )

            return count

        except Exception as e:
            logger.error(f"Error loading pet schedules: {e}")
            return 0

    def get_upcoming_events(
        self,
        pet_id: str | None = None,
        within_minutes: int = 60,
    ) -> list[CareScheduleItem]:
        """Get upcoming care events.

        Args:
            pet_id: Specific pet, or None for all pets
            within_minutes: Window to look ahead

        Returns:
            List of upcoming care events
        """
        now = datetime.now().time()
        upcoming = []

        schedules = (
            [self._schedules[pet_id]]
            if pet_id and pet_id in self._schedules
            else self._schedules.values()
        )

        for schedule in schedules:
            for item in schedule.items:
                if item.completed:
                    continue

                # Calculate minutes until event
                now_minutes = now.hour * 60 + now.minute
                event_minutes = item.scheduled_time.hour * 60 + item.scheduled_time.minute
                delta = event_minutes - now_minutes

                # Handle day wrap
                if delta < -60:  # Event was earlier today, might be tomorrow
                    continue
                if delta < 0:  # Just passed
                    continue
                if delta <= within_minutes:
                    upcoming.append(item)

        return sorted(upcoming, key=lambda x: x.scheduled_time)

    def record_behavioral_signal(
        self,
        pet_id: str,
        signal: BehavioralSignal,
    ) -> list[str]:
        """Record a behavioral signal and return indicated needs.

        Args:
            pet_id: Pet identity ID
            signal: The behavioral signal observed

        Returns:
            List of indicated needs
        """
        if pet_id not in self._behavioral_signals:
            self._behavioral_signals[pet_id] = []

        # Keep last 50 signals
        self._behavioral_signals[pet_id].append(signal)
        self._behavioral_signals[pet_id] = self._behavioral_signals[pet_id][-50:]

        logger.debug(
            f"🐾 Signal from {pet_id}: {signal.signal_type} "
            f"(confidence: {signal.confidence:.2f}) → {signal.indicates}"
        )

        return signal.indicates

    def infer_pet_needs(self, pet_id: str) -> dict[str, Any]:
        """Infer current pet needs from behavioral signals.

        Args:
            pet_id: Pet identity ID

        Returns:
            Dict with inferred needs and confidence
        """
        signals = self._behavioral_signals.get(pet_id, [])
        if not signals:
            return {"needs": [], "confidence": 0.0}

        # Aggregate signals from last 10 minutes
        import time as time_module

        cutoff = time_module.time() - 600  # 10 minutes
        recent = [s for s in signals if s.timestamp > cutoff]

        if not recent:
            return {"needs": [], "confidence": 0.0}

        # Count indicated needs
        need_scores: dict[str, float] = {}
        for signal in recent:
            for need in signal.indicates:
                if need not in need_scores:
                    need_scores[need] = 0.0
                need_scores[need] += signal.confidence

        # Normalize and threshold
        if not need_scores:
            return {"needs": [], "confidence": 0.0}

        max_score = max(need_scores.values())
        needs = [
            {"need": need, "score": score / max_score}
            for need, score in need_scores.items()
            if score / max_score > 0.5
        ]

        return {
            "needs": sorted(needs, key=lambda x: x["score"], reverse=True),
            "confidence": min(max_score / len(recent), 1.0),
            "signal_count": len(recent),
        }

    async def announce_care_event(
        self,
        event: CareScheduleItem,
        announcement_type: str = "reminder",
    ) -> bool:
        """Announce a care event through the smart home.

        Args:
            event: The care event
            announcement_type: "reminder" or "time"

        Returns:
            True if announced successfully
        """
        try:
            from kagami_smarthome import get_smart_home

            controller = await get_smart_home()

            if announcement_type == "reminder":
                message = f"{event.pet_name}'s {event.description} in {event.reminder_minutes_before} minutes"
            else:
                message = f"Time for {event.pet_name}'s {event.description}!"

            # Announce to common areas
            await controller.announce(message, rooms=["Living Room", "Office"])

            logger.info(f"🐾 Announced: {message}")
            return True

        except Exception as e:
            logger.error(f"Error announcing care event: {e}")
            return False

    async def check_pet_comfort(self, pet_id: str) -> dict[str, Any]:
        """Check environmental comfort for a pet.

        Args:
            pet_id: Pet identity ID

        Returns:
            Comfort assessment
        """
        try:
            from kagami_smarthome import get_smart_home

            from kagami.core.integrations.character_identity import (
                get_character_profile,
            )

            profile = get_character_profile(pet_id.replace("_", " ").split()[0].lower())
            if not profile:
                return {"error": "pet_not_found"}

            # Get pet's comfort preferences
            schedule = profile.metadata.get("presence_schedule", {})
            outdoor_prefs = schedule.get("outdoor_preferences", {})
            max_temp = outdoor_prefs.get("max_comfortable_temp_f", 75)

            # Get current house temperature
            await get_smart_home()
            # This would need actual climate sensor integration
            # For now, return the assessment structure

            return {
                "pet_id": pet_id,
                "pet_name": profile.name,
                "max_comfortable_temp_f": max_temp,
                "prefers_cold": outdoor_prefs.get("loves_cold", False),
                "recommendation": None,  # Would contain climate adjustment if needed
            }

        except Exception as e:
            logger.error(f"Error checking pet comfort: {e}")
            return {"error": str(e)}


# =============================================================================
# SINGLETON
# =============================================================================


_PET_CARE: PetCareAutomation | None = None


def get_pet_care() -> PetCareAutomation:
    """Get global PetCareAutomation instance."""
    global _PET_CARE
    if _PET_CARE is None:
        _PET_CARE = PetCareAutomation()
        _PET_CARE.load_pet_schedules()
    return _PET_CARE


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def check_on_bella() -> dict[str, Any]:
    """Convenience function to check on Bella.

    Returns:
        Status dict with Bella's current state and needs
    """
    from kagami.core.symbiote.household_symbiosis import get_household_symbiosis

    symbiosis = get_household_symbiosis()
    pet_care = get_pet_care()

    bella = symbiosis.get_member("bella_malamute")
    if not bella:
        return {"error": "Bella not found in household"}

    needs = symbiosis.predict_pet_needs("bella_malamute")
    inferred = pet_care.infer_pet_needs("bella_malamute")
    upcoming = pet_care.get_upcoming_events("bella_malamute", within_minutes=30)

    return {
        "name": bella.display_name,
        "breed": bella.breed,
        "presence": bella.presence.value if bella.presence else "unknown",
        "activity": bella.activity_state,
        "room": bella.current_room,
        "scheduled_needs": needs.get("needs", []),
        "inferred_needs": inferred.get("needs", []),
        "upcoming_events": [
            {
                "type": e.event_type.value,
                "time": e.scheduled_time.strftime("%H:%M"),
                "description": e.description,
            }
            for e in upcoming
        ],
    }


async def bella_dinner_time() -> bool:
    """Announce Bella's dinner time.

    Returns:
        True if announced successfully
    """
    try:
        from kagami_smarthome import get_smart_home

        controller = await get_smart_home()
        await controller.announce("Bella, dinner!", rooms=["Living Room"])
        logger.info("🐕 Announced Bella's dinner time")
        return True
    except Exception as e:
        logger.error(f"Error announcing Bella's dinner: {e}")
        return False


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "BehavioralSignal",
    "CareScheduleItem",
    "PetActivityState",
    "PetCareAutomation",
    "PetCareEvent",
    "PetCareSchedule",
    "bella_dinner_time",
    "check_on_bella",
    "get_pet_care",
]
