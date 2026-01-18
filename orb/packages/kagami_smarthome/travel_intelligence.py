"""Travel Intelligence — Route Monitoring and Proactive Advice.

Uses the general PatternLearner for all pattern learning.
Focuses on:
- Real-time route monitoring
- Departure time recommendations
- Traffic alerts
- Arrival preparation

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

from kagami_smarthome.device_reconciler import (
    DeviceReconciler,
    ReconciledPresence,
    TravelMode,
    get_device_reconciler,
)
from kagami_smarthome.integrations.maps import (
    HOME_LAT,
    HOME_LON,
    LocationInfo,
    MapsService,
    get_maps_service,
)

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

logger = logging.getLogger(__name__)


class TravelState(str, Enum):
    """Current travel state."""

    HOME = "home"
    DEPARTING = "departing"
    DRIVING_AWAY = "driving_away"
    DRIVING_HOME = "driving_home"
    ARRIVING = "arriving"
    PARKED_AWAY = "parked_away"


class RouteAlert(str, Enum):
    """Types of route alerts."""

    TRAFFIC_HEAVY = "traffic_heavy"
    TRAFFIC_CLEARED = "traffic_cleared"
    ACCIDENT = "accident"
    FASTER_ROUTE = "faster_route"
    ARRIVAL_SOON = "arrival_soon"
    DEPARTURE_REMINDER = "departure_reminder"


@dataclass
class ActiveRoute:
    """Currently active route being monitored."""

    destination_lat: float
    destination_lon: float
    destination_name: str | None = None

    start_time: float = field(default_factory=time.time)
    start_lat: float = HOME_LAT
    start_lon: float = HOME_LON

    current_lat: float = HOME_LAT
    current_lon: float = HOME_LON

    initial_eta_minutes: int = 0
    current_eta_minutes: int = 0
    best_eta_minutes: int = 0
    worst_eta_minutes: int = 0

    total_distance_miles: float = 0.0
    remaining_distance_miles: float = 0.0

    alerts_sent: set[str] = field(default_factory=set)


TravelEventCallback = Callable[[RouteAlert, dict[str, Any]], Awaitable[None]]


class TravelIntelligence:
    """Travel monitoring with general pattern learning.

    Uses kagami.core.learning.PatternLearner for all patterns:
    - travel_departures: When do I typically leave?
    - travel_durations: How long do commutes take?

    Features:
    1. Route Monitoring: Real-time tracking while driving
    2. Departure Advice: Calendar-aware leave time recommendations
    3. Traffic Alerts: Significant delays or faster routes
    4. Arrival Prediction: Accurate ETA with traffic
    """

    DRIVING_POLL_INTERVAL = 60
    PARKED_POLL_INTERVAL = 300
    TRAFFIC_DELAY_THRESHOLD_MINUTES = 10
    ARRIVAL_ALERT_MINUTES = 10

    def __init__(self):
        self._smart_home: SmartHomeController | None = None
        self._maps: MapsService = get_maps_service()

        # Device reconciler for multi-device tracking (phone, laptop, car)
        self._reconciler: DeviceReconciler = get_device_reconciler()

        self._state = TravelState.HOME
        self._active_route: ActiveRoute | None = None

        # Use general pattern learners
        self._departure_learner = self._get_departure_learner()
        self._duration_learner = self._get_duration_learner()

        self._alert_callbacks: list[TravelEventCallback] = []

        self._running = False
        self._monitor_task: asyncio.Task | None = None
        self._last_position: tuple[float, float] | None = None
        self._last_position_time: float = 0

        self._stats = {
            "trips_tracked": 0,
            "alerts_sent": 0,
            "carpool_trips": 0,
            "driving_trips": 0,
            "total_miles": 0.0,
        }

    def _get_departure_learner(self):
        """Get the departure pattern learner."""
        try:
            from kagami.core.learning import get_travel_departure_learner

            return get_travel_departure_learner()
        except ImportError:
            logger.warning("PatternLearner not available, using stub")
            return _StubLearner()

    def _get_duration_learner(self):
        """Get the duration pattern learner."""
        try:
            from kagami.core.learning import get_travel_duration_learner

            return get_travel_duration_learner()
        except ImportError:
            return _StubLearner()

    async def start_monitoring(self, smart_home: SmartHomeController) -> None:
        """Start travel monitoring."""
        self._smart_home = smart_home
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("🚗 TravelIntelligence monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop travel monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None

        # Save patterns
        self._departure_learner.save()
        self._duration_learner.save()

        logger.info("🚗 TravelIntelligence monitoring stopped")

    def on_alert(self, callback: TravelEventCallback) -> None:
        """Subscribe to travel alerts."""
        self._alert_callbacks.append(callback)

    async def _emit_alert(self, alert: RouteAlert, data: dict[str, Any]) -> None:
        """Emit alert to all subscribers."""
        for callback in self._alert_callbacks:
            try:
                await callback(alert, data)
            except Exception as e:
                logger.warning(f"Travel alert callback error: {e}")
        self._stats["alerts_sent"] += 1

    # =========================================================================
    # MONITORING
    # =========================================================================

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_travel_state()

                if self._state in (
                    TravelState.DRIVING_AWAY,
                    TravelState.DRIVING_HOME,
                    TravelState.ARRIVING,
                ):
                    await asyncio.sleep(self.DRIVING_POLL_INTERVAL)
                else:
                    await asyncio.sleep(self.PARKED_POLL_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Travel monitor error: {e}")
                await asyncio.sleep(60)

    async def _check_travel_state(self) -> None:
        """Check and update travel state using multi-device reconciliation.

        Uses DeviceReconciler to track phone, laptop, AND car:
        - Handles carpooling (phone away, car home)
        - Uses most accurate device for location
        - Alerts if laptop left behind
        """
        if not self._smart_home:
            return

        # Use reconciler for multi-device presence
        presence = await self._reconciler.reconcile()

        # Get primary location (from phone if carpooling, else from best source)
        lat = presence.primary_lat
        lon = presence.primary_lon

        if not lat or not lon:
            return

        location = await self._maps.get_distance_to_home(lat, lon)

        # Determine driving state from reconciled travel mode
        is_driving = presence.travel_mode in (TravelMode.DRIVING, TravelMode.CARPOOLING)

        old_state = self._state
        new_state = self._determine_state_from_reconciled(presence, location)

        if new_state != old_state:
            await self._handle_state_transition_reconciled(old_state, new_state, location, presence)

        self._state = new_state

        if self._active_route and is_driving:
            await self._update_active_route(lat, lon, location)

        self._last_position = (lat, lon)
        self._last_position_time = time.time()

    def _determine_state_from_reconciled(
        self,
        presence: ReconciledPresence,
        location: LocationInfo,
    ) -> TravelState:
        """Determine travel state from reconciled multi-device presence."""
        if presence.is_home:
            return TravelState.HOME

        is_driving = presence.travel_mode in (TravelMode.DRIVING, TravelMode.CARPOOLING)

        if not is_driving:
            return TravelState.PARKED_AWAY

        if location.is_arriving:
            return TravelState.ARRIVING

        if self._last_position:
            last_lat, last_lon = self._last_position
            last_dist = self._haversine_miles(last_lat, last_lon, HOME_LAT, HOME_LON)
            curr_dist = location.distance_miles

            if curr_dist < last_dist - 0.1:
                return TravelState.DRIVING_HOME
            elif curr_dist > last_dist + 0.1:
                return TravelState.DRIVING_AWAY

        if location.distance_miles < 5:
            return TravelState.DRIVING_HOME
        return TravelState.DRIVING_AWAY

    async def _handle_state_transition_reconciled(
        self,
        old_state: TravelState,
        new_state: TravelState,
        location: LocationInfo,
        presence: ReconciledPresence,
    ) -> None:
        """Handle state transitions with reconciled presence."""
        logger.info(
            f"🚗 Travel state: {old_state.value} → {new_state.value} (mode: {presence.travel_mode.value})"
        )

        # Leaving home - record departure
        if old_state == TravelState.HOME and new_state in (
            TravelState.DEPARTING,
            TravelState.DRIVING_AWAY,
        ):
            self._stats["trips_tracked"] += 1

            if presence.travel_mode == TravelMode.CARPOOLING:
                self._stats["carpool_trips"] += 1
            else:
                self._stats["driving_trips"] += 1

            # Record departure in pattern learner
            self._departure_learner.record_event(True)

            self._active_route = ActiveRoute(
                destination_lat=0,
                destination_lon=0,
                start_lat=HOME_LAT,
                start_lon=HOME_LON,
                current_lat=location.latitude,
                current_lon=location.longitude,
            )

        # Arriving home
        if new_state == TravelState.ARRIVING and old_state != TravelState.ARRIVING:
            await self._emit_alert(
                RouteAlert.ARRIVAL_SOON,
                {
                    "eta_minutes": location.duration_minutes,
                    "eta_text": location.duration_text,
                    "distance_miles": location.distance_miles,
                    "travel_mode": presence.travel_mode.value,
                },
            )

        # Arrived home - record duration
        if new_state == TravelState.HOME and old_state != TravelState.HOME:
            if self._active_route:
                duration = (time.time() - self._active_route.start_time) / 60

                # Record duration in pattern learner
                self._duration_learner.record_value(duration)

                self._stats["total_miles"] += self._active_route.remaining_distance_miles
                self._active_route = None

    def _determine_state(self, location: LocationInfo, is_driving: bool) -> TravelState:
        """Determine travel state from location and driving status."""
        if location.is_home:
            return TravelState.HOME

        if not is_driving:
            return TravelState.PARKED_AWAY

        if location.is_arriving:
            return TravelState.ARRIVING

        if self._last_position:
            last_lat, last_lon = self._last_position
            last_dist = self._haversine_miles(last_lat, last_lon, HOME_LAT, HOME_LON)
            curr_dist = location.distance_miles

            if curr_dist < last_dist - 0.1:
                return TravelState.DRIVING_HOME
            elif curr_dist > last_dist + 0.1:
                return TravelState.DRIVING_AWAY

        if location.distance_miles < 5:
            return TravelState.DRIVING_HOME
        return TravelState.DRIVING_AWAY

    async def _handle_state_transition(
        self,
        old_state: TravelState,
        new_state: TravelState,
        location: LocationInfo,
        tesla: dict[str, Any],
    ) -> None:
        """Handle state transitions."""
        logger.info(f"🚗 Travel state: {old_state.value} → {new_state.value}")

        # Leaving home - record departure
        if old_state == TravelState.HOME and new_state in (
            TravelState.DEPARTING,
            TravelState.DRIVING_AWAY,
        ):
            self._stats["trips_tracked"] += 1

            # Record departure in pattern learner
            self._departure_learner.record_event(True)

            self._active_route = ActiveRoute(
                destination_lat=0,
                destination_lon=0,
                start_lat=HOME_LAT,
                start_lon=HOME_LON,
                current_lat=location.latitude,
                current_lon=location.longitude,
            )

        # Arriving home
        if new_state == TravelState.ARRIVING and old_state != TravelState.ARRIVING:
            await self._emit_alert(
                RouteAlert.ARRIVAL_SOON,
                {
                    "eta_minutes": location.duration_minutes,
                    "eta_text": location.duration_text,
                    "distance_miles": location.distance_miles,
                },
            )

        # Arrived home - record duration
        if new_state == TravelState.HOME and old_state != TravelState.HOME:
            if self._active_route:
                duration = (time.time() - self._active_route.start_time) / 60

                # Record duration in pattern learner
                self._duration_learner.record_value(duration)

                self._stats["total_miles"] += self._active_route.remaining_distance_miles
                self._active_route = None

    async def _update_active_route(
        self,
        lat: float,
        lon: float,
        location: LocationInfo,
    ) -> None:
        """Update active route with new position."""
        if not self._active_route:
            return

        route = self._active_route
        route.current_lat = lat
        route.current_lon = lon

        old_eta = route.current_eta_minutes
        route.current_eta_minutes = (
            location.duration_in_traffic_minutes or location.duration_minutes
        )

        if route.current_eta_minutes < route.best_eta_minutes or route.best_eta_minutes == 0:
            route.best_eta_minutes = route.current_eta_minutes
        if route.current_eta_minutes > route.worst_eta_minutes:
            route.worst_eta_minutes = route.current_eta_minutes

        route.remaining_distance_miles = location.distance_miles

        # Traffic delay alert
        if (
            old_eta > 0
            and route.current_eta_minutes > old_eta + self.TRAFFIC_DELAY_THRESHOLD_MINUTES
        ):
            if "traffic_delay" not in route.alerts_sent:
                await self._emit_alert(
                    RouteAlert.TRAFFIC_HEAVY,
                    {
                        "old_eta_minutes": old_eta,
                        "new_eta_minutes": route.current_eta_minutes,
                        "delay_minutes": route.current_eta_minutes - old_eta,
                    },
                )
                route.alerts_sent.add("traffic_delay")

        # Traffic cleared alert
        elif old_eta > 0 and route.current_eta_minutes < old_eta - 5:
            if "traffic_delay" in route.alerts_sent:
                await self._emit_alert(
                    RouteAlert.TRAFFIC_CLEARED,
                    {
                        "new_eta_minutes": route.current_eta_minutes,
                        "time_saved_minutes": old_eta - route.current_eta_minutes,
                    },
                )

    # =========================================================================
    # DEPARTURE ADVICE
    # =========================================================================

    async def get_departure_advice(
        self,
        event_time: datetime,
        destination_lat: float,
        destination_lon: float,
        destination_name: str | None = None,
    ) -> dict[str, Any]:
        """Get departure time advice for an event."""
        now = datetime.now()

        distance = self._haversine_miles(HOME_LAT, HOME_LON, destination_lat, destination_lon)

        # Get learned duration for this time
        learned_duration = self._duration_learner.get_expected_value(event_time)
        confidence = self._duration_learner.get_confidence(event_time)

        # Use learned duration or estimate
        if confidence > 0.5 and learned_duration > 0:
            traffic_multiplier = 1.0  # Already learned with traffic
            base_minutes = learned_duration * (distance / 10)  # Scale by distance
        else:
            traffic_multiplier = 1.3  # Default buffer
            base_minutes = (distance / 25) * 60

        adjusted_minutes = int(base_minutes * traffic_multiplier)
        buffer_minutes = 10
        total_minutes = adjusted_minutes + buffer_minutes

        recommended_departure = event_time - timedelta(minutes=total_minutes)
        minutes_until_departure = (recommended_departure - now).total_seconds() / 60

        urgency = "normal"
        if minutes_until_departure <= 0:
            urgency = "leave_now"
        elif minutes_until_departure <= 5:
            urgency = "leave_soon"
        elif minutes_until_departure <= 15:
            urgency = "prepare"

        return {
            "event_time": event_time.isoformat(),
            "destination": destination_name or f"{destination_lat:.4f}, {destination_lon:.4f}",
            "distance_miles": round(distance, 1),
            "estimated_travel_minutes": adjusted_minutes,
            "buffer_minutes": buffer_minutes,
            "total_minutes": total_minutes,
            "recommended_departure": recommended_departure.isoformat(),
            "minutes_until_departure": max(0, int(minutes_until_departure)),
            "urgency": urgency,
            "traffic_multiplier": traffic_multiplier,
            "confidence": "high" if confidence > 0.7 else "medium" if confidence > 0.3 else "low",
        }

    # =========================================================================
    # UTILITIES
    # =========================================================================

    @staticmethod
    def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate haversine distance in miles."""
        R = 3959

        lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def get_state(self) -> TravelState:
        """Get current travel state."""
        return self._state

    def get_active_route(self) -> ActiveRoute | None:
        """Get active route if driving."""
        return self._active_route

    def get_stats(self) -> dict[str, Any]:
        """Get travel statistics."""
        return {
            **self._stats,
            "state": self._state.value,
            "departure_patterns": self._departure_learner.get_summary()
            if hasattr(self._departure_learner, "get_summary")
            else {},
            "duration_patterns": self._duration_learner.get_summary()
            if hasattr(self._duration_learner, "get_summary")
            else {},
        }

    def get_learned_patterns(self) -> dict[str, Any]:
        """Get summary of learned patterns."""
        departure_summary = (
            self._departure_learner.get_summary()
            if hasattr(self._departure_learner, "get_summary")
            else {}
        )
        duration_summary = (
            self._duration_learner.get_summary()
            if hasattr(self._duration_learner, "get_summary")
            else {}
        )

        return {
            "departures": departure_summary,
            "durations": duration_summary,
        }


class _StubLearner:
    """Stub learner when kagami.core.learning is not available."""

    def record_event(self, occurred: bool = True) -> None:
        pass

    def record_value(self, value: float) -> None:
        pass

    def get_expected_value(self, at=None) -> float:
        return 0.0

    def get_confidence(self, at=None) -> float:
        return 0.0

    def get_summary(self) -> dict:
        return {}

    def save(self) -> None:
        pass


# Singleton
_travel_intelligence: TravelIntelligence | None = None


def get_travel_intelligence() -> TravelIntelligence:
    """Get global TravelIntelligence instance."""
    global _travel_intelligence
    if _travel_intelligence is None:
        _travel_intelligence = TravelIntelligence()
    return _travel_intelligence


async def start_travel_monitoring(smart_home: SmartHomeController) -> TravelIntelligence:
    """Start travel monitoring with SmartHome."""
    travel = get_travel_intelligence()
    await travel.start_monitoring(smart_home)
    return travel


__all__ = [
    "ActiveRoute",
    "RouteAlert",
    "TravelEventCallback",
    "TravelIntelligence",
    "TravelState",
    "get_travel_intelligence",
    "start_travel_monitoring",
]
