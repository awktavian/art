"""Pattern learning and prediction for sensory data.

This module provides behavioral pattern learning capabilities for
all sense types, enabling predictive anticipation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from .base import SenseType

logger = logging.getLogger(__name__)


class PatternManager:
    """Manages pattern learning and prediction across all senses."""

    def __init__(self):
        self._pattern_learners: dict[str, Any] = {}
        self._initialized = False

    def initialize(self) -> None:
        """Initialize pattern learners for all sense types."""
        if self._initialized:
            return

        try:
            from kagami.core.learning import TimeGranularity, get_pattern_learner

            # Presence & Activity
            self._pattern_learners["presence_home"] = get_pattern_learner(
                "presence_home", TimeGranularity.HOUR
            )
            self._pattern_learners["presence_location"] = get_pattern_learner(
                "presence_location", TimeGranularity.QUARTER_HOUR
            )
            self._pattern_learners["activity"] = get_pattern_learner(
                "activity", TimeGranularity.HOUR
            )

            # Sleep
            self._pattern_learners["sleep"] = get_pattern_learner("sleep", TimeGranularity.HOUR)
            self._pattern_learners["sleep_quality"] = get_pattern_learner(
                "sleep_quality", TimeGranularity.HOUR
            )

            # Digital
            self._pattern_learners["gmail_activity"] = get_pattern_learner(
                "gmail_activity", TimeGranularity.HOUR
            )
            self._pattern_learners["gmail_urgency"] = get_pattern_learner(
                "gmail_urgency", TimeGranularity.HOUR
            )
            self._pattern_learners["calendar_meetings"] = get_pattern_learner(
                "calendar_meetings", TimeGranularity.HOUR
            )
            self._pattern_learners["linear_activity"] = get_pattern_learner(
                "linear_activity", TimeGranularity.HOUR
            )
            self._pattern_learners["github_activity"] = get_pattern_learner(
                "github_activity", TimeGranularity.HOUR
            )

            # Physical
            self._pattern_learners["lights_brightness"] = get_pattern_learner(
                "lights_brightness", TimeGranularity.HOUR
            )
            self._pattern_learners["lights_occupied"] = get_pattern_learner(
                "lights_occupied", TimeGranularity.HOUR
            )
            self._pattern_learners["climate_temp"] = get_pattern_learner(
                "climate_temp", TimeGranularity.HOUR
            )
            self._pattern_learners["climate_mode"] = get_pattern_learner(
                "climate_mode", TimeGranularity.DAY_PART
            )
            self._pattern_learners["security_locked"] = get_pattern_learner(
                "security_locked", TimeGranularity.HOUR
            )

            # Vehicle
            self._pattern_learners["vehicle_departure"] = get_pattern_learner(
                "vehicle_departure", TimeGranularity.QUARTER_HOUR
            )
            self._pattern_learners["vehicle_location"] = get_pattern_learner(
                "vehicle_location", TimeGranularity.HOUR
            )

            # Environmental
            self._pattern_learners["weather_temp"] = get_pattern_learner(
                "weather_temp", TimeGranularity.HOUR
            )

            # Situation
            self._pattern_learners["situation_phase"] = get_pattern_learner(
                "situation_phase", TimeGranularity.HOUR
            )
            self._pattern_learners["situation_urgency"] = get_pattern_learner(
                "situation_urgency", TimeGranularity.HOUR
            )

            # Biometric
            self._pattern_learners["health_heart_rate"] = get_pattern_learner(
                "health_heart_rate", TimeGranularity.HOUR
            )
            self._pattern_learners["health_hrv"] = get_pattern_learner(
                "health_hrv", TimeGranularity.HOUR
            )
            self._pattern_learners["health_activity"] = get_pattern_learner(
                "health_activity", TimeGranularity.HOUR
            )
            self._pattern_learners["health_exercise"] = get_pattern_learner(
                "health_exercise", TimeGranularity.DAY_PART
            )
            self._pattern_learners["health_sleep_score"] = get_pattern_learner(
                "health_sleep_score", TimeGranularity.DAY_PART
            )

            self._initialized = True
            logger.debug("Pattern learners initialized for behavioral learning")

        except ImportError:
            logger.debug("Pattern learning not available")

    def record_sense_patterns(self, sense_type: SenseType, data: dict[str, Any]) -> None:
        """Record patterns from sense data."""
        if not self._initialized:
            return

        try:
            if sense_type == SenseType.PRESENCE:
                self._record_presence_patterns(data)
            elif sense_type == SenseType.SLEEP:
                self._record_sleep_patterns(data)
            elif sense_type == SenseType.GMAIL:
                self._record_gmail_patterns(data)
            elif sense_type == SenseType.CALENDAR:
                self._record_calendar_patterns(data)
            elif sense_type == SenseType.LINEAR:
                self._record_linear_patterns(data)
            elif sense_type == SenseType.GITHUB:
                self._record_github_patterns(data)
            elif sense_type == SenseType.LIGHTS:
                self._record_lights_patterns(data)
            elif sense_type == SenseType.CLIMATE:
                self._record_climate_patterns(data)
            elif sense_type == SenseType.SECURITY:
                self._record_security_patterns(data)
            elif sense_type == SenseType.VEHICLE:
                self._record_vehicle_patterns(data)
            elif sense_type == SenseType.WEATHER:
                self._record_weather_patterns(data)
            elif sense_type == SenseType.SITUATION:
                self._record_situation_patterns(data)
        except Exception as e:
            logger.debug(f"Pattern recording failed for {sense_type.value}: {e}")

    def _record_presence_patterns(self, data: dict[str, Any]) -> None:
        """Record presence-related patterns."""
        presence = data.get("presence", "unknown")
        is_home = presence in ("home", "active", "sleeping")
        if "presence_home" in self._pattern_learners:
            self._pattern_learners["presence_home"].record_event(is_home)
        if "presence_location" in self._pattern_learners:
            location = data.get("location", "unknown")
            location_map = {"home": 1.0, "work": 2.0, "away": 3.0}
            self._pattern_learners["presence_location"].record_value(
                location_map.get(location, 0.0)
            )
        if "activity" in self._pattern_learners:
            activity = data.get("activity", "unknown")
            is_active = activity == "active"
            self._pattern_learners["activity"].record_event(is_active)

    def _record_sleep_patterns(self, data: dict[str, Any]) -> None:
        """Record sleep-related patterns."""
        state = data.get("state", "unknown")
        if "sleep" in self._pattern_learners:
            is_sleeping = state in ("sleeping", "asleep", "deep_sleep")
            self._pattern_learners["sleep"].record_event(is_sleeping)
        if "sleep_quality" in self._pattern_learners:
            score = data.get("sleep_score", 0)
            if score > 0:
                self._pattern_learners["sleep_quality"].record_value(score)

    def _record_gmail_patterns(self, data: dict[str, Any]) -> None:
        """Record Gmail-related patterns."""
        if "gmail_activity" in self._pattern_learners:
            unread = data.get("unread_count", 0)
            has_unread = unread > 0
            self._pattern_learners["gmail_activity"].record_event(has_unread)
        if "gmail_urgency" in self._pattern_learners:
            urgent = data.get("urgent_count", 0)
            has_urgent = urgent > 0
            self._pattern_learners["gmail_urgency"].record_event(has_urgent)

    def _record_calendar_patterns(self, data: dict[str, Any]) -> None:
        """Record calendar-related patterns."""
        if "calendar_meetings" in self._pattern_learners:
            events = data.get("events", [])
            has_meeting = len(events) > 0
            self._pattern_learners["calendar_meetings"].record_event(has_meeting)

    def _record_linear_patterns(self, data: dict[str, Any]) -> None:
        """Record Linear-related patterns."""
        if "linear_activity" in self._pattern_learners:
            issues = data.get("active_issues", 0)
            is_active = issues > 0
            self._pattern_learners["linear_activity"].record_event(is_active)

    def _record_github_patterns(self, data: dict[str, Any]) -> None:
        """Record GitHub-related patterns."""
        if "github_activity" in self._pattern_learners:
            notifications = data.get("notification_count", 0)
            is_active = notifications > 0
            self._pattern_learners["github_activity"].record_event(is_active)

    def _record_lights_patterns(self, data: dict[str, Any]) -> None:
        """Record lights-related patterns."""
        if "lights_brightness" in self._pattern_learners:
            avg_brightness = data.get("average_brightness", 0)
            self._pattern_learners["lights_brightness"].record_value(avg_brightness)
        if "lights_occupied" in self._pattern_learners:
            on_count = data.get("on_count", 0)
            has_lights_on = on_count > 0
            self._pattern_learners["lights_occupied"].record_event(has_lights_on)

    def _record_climate_patterns(self, data: dict[str, Any]) -> None:
        """Record climate-related patterns."""
        if "climate_temp" in self._pattern_learners:
            temp = data.get("temperature", 0)
            if temp > 0:
                self._pattern_learners["climate_temp"].record_value(temp)
        if "climate_mode" in self._pattern_learners:
            mode = data.get("mode", "off")
            mode_map = {"off": 0, "cool": 1, "heat": 2, "auto": 3}
            self._pattern_learners["climate_mode"].record_value(mode_map.get(mode, 0))

    def _record_security_patterns(self, data: dict[str, Any]) -> None:
        """Record security-related patterns."""
        if "security_locked" in self._pattern_learners:
            locked = data.get("all_locked", False)
            self._pattern_learners["security_locked"].record_event(locked)

    def _record_vehicle_patterns(self, data: dict[str, Any]) -> None:
        """Record vehicle-related patterns."""
        if "vehicle_departure" in self._pattern_learners:
            state = data.get("state", "unknown")
            is_driving = state == "driving"
            self._pattern_learners["vehicle_departure"].record_event(is_driving)
        if "vehicle_location" in self._pattern_learners:
            at_home = data.get("at_home", False)
            self._pattern_learners["vehicle_location"].record_event(at_home)

    def _record_weather_patterns(self, data: dict[str, Any]) -> None:
        """Record weather-related patterns."""
        if "weather_temp" in self._pattern_learners:
            temp = data.get("temperature", 0)
            if temp != 0:
                self._pattern_learners["weather_temp"].record_value(temp)

    def _record_situation_patterns(self, data: dict[str, Any]) -> None:
        """Record situation-related patterns."""
        if "situation_phase" in self._pattern_learners:
            phase = data.get("phase", "unknown")
            phase_map = {
                "sleeping": 0,
                "waking": 1,
                "morning_routine": 2,
                "working": 3,
                "focused": 4,
                "break": 5,
                "relaxing": 6,
                "winding_down": 7,
                "unknown": -1,
            }
            self._pattern_learners["situation_phase"].record_value(phase_map.get(phase, -1))
        if "situation_urgency" in self._pattern_learners:
            urgency = data.get("urgency", "normal")
            is_urgent = urgency in ("urgent", "critical")
            self._pattern_learners["situation_urgency"].record_event(is_urgent)

    def get_prediction(
        self, pattern_name: str, at: datetime | None = None
    ) -> dict[str, Any] | None:
        """Get pattern prediction for a specific behavior."""
        if pattern_name not in self._pattern_learners:
            return None
        learner = self._pattern_learners[pattern_name]
        return learner.predict(at)

    def get_all_predictions(self, at: datetime | None = None) -> dict[str, dict[str, Any]]:
        """Get predictions for all learned patterns."""
        predictions = {}
        for name, learner in self._pattern_learners.items():
            try:
                predictions[name] = learner.predict(at)
            except Exception as e:
                logger.debug(f"Pattern prediction failed for {name}: {e}")
        return predictions

    def get_summaries(self) -> dict[str, dict[str, Any]]:
        """Get summaries of all learned patterns."""
        summaries = {}
        for name, learner in self._pattern_learners.items():
            try:
                summaries[name] = learner.get_summary()
            except Exception as e:
                logger.debug(f"Pattern summary failed for {name}: {e}")
        return summaries

    def predict_upcoming(self, horizon_minutes: int = 60) -> list[dict[str, Any]]:
        """Predict upcoming patterns within time horizon."""
        predictions = []
        now = datetime.now()

        for minutes_ahead in range(0, horizon_minutes, 15):
            future_time = now + timedelta(minutes=minutes_ahead)

            for name, learner in self._pattern_learners.items():
                try:
                    pred = learner.predict(future_time)
                    confidence = pred.get("confidence", 0)

                    if confidence > 0.6:
                        predictions.append(
                            {
                                "pattern": name,
                                "time": future_time.isoformat(),
                                "minutes_ahead": minutes_ahead,
                                "probability": pred.get("probability", 0),
                                "expected_value": pred.get("expected_value"),
                                "confidence": confidence,
                            }
                        )
                except Exception:
                    continue

        predictions.sort(key=lambda p: p.get("confidence", 0), reverse=True)
        return predictions

    def get_proactive_suggestions(self) -> list[dict[str, Any]]:
        """Get proactive suggestions based on pattern predictions."""
        suggestions = []
        predictions = self.predict_upcoming(horizon_minutes=120)

        for pred in predictions:
            pattern = pred.get("pattern", "")
            prob = pred.get("probability", 0)
            confidence = pred.get("confidence", 0)
            minutes = pred.get("minutes_ahead", 0)

            if pattern == "sleep" and prob > 0.7 and minutes < 60:
                suggestions.append(
                    {
                        "suggestion": "Prepare for sleep",
                        "reason": f"Sleep pattern predicted in {minutes} minutes",
                        "confidence": confidence,
                        "action": "scene.goodnight",
                    }
                )
            elif pattern == "vehicle_departure" and prob > 0.6 and minutes < 30:
                suggestions.append(
                    {
                        "suggestion": "Precondition vehicle",
                        "reason": f"Departure predicted in {minutes} minutes",
                        "confidence": confidence,
                        "action": "tesla.precondition",
                    }
                )
            elif pattern == "calendar_meetings" and prob > 0.7 and minutes < 15:
                suggestions.append(
                    {
                        "suggestion": "Prepare for meeting",
                        "reason": f"Meeting likely in {minutes} minutes",
                        "confidence": confidence,
                        "action": "lights.focus",
                    }
                )
            elif pattern == "situation_phase" and minutes == 0:
                expected = pred.get("expected_value", 0)
                if expected == 3:  # working
                    suggestions.append(
                        {
                            "suggestion": "Switch to focus mode",
                            "reason": "Work phase predicted",
                            "confidence": confidence,
                            "action": "lights.focus",
                        }
                    )
                elif expected == 6:  # relaxing
                    suggestions.append(
                        {
                            "suggestion": "Relax lighting",
                            "reason": "Relaxation phase predicted",
                            "confidence": confidence,
                            "action": "lights.relax",
                        }
                    )

        seen: set[str] = set()
        unique = []
        for s in sorted(suggestions, key=lambda x: x.get("confidence", 0), reverse=True):
            key = s.get("action")
            if key and key not in seen:
                seen.add(key)
                unique.append(s)

        return unique[:5]

    def save_all(self) -> None:
        """Save all learned patterns to disk."""
        for learner in self._pattern_learners.values():
            try:
                learner.save()
            except Exception as e:
                logger.debug(f"Pattern save failed: {e}")


__all__ = ["PatternManager"]
