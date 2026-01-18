"""Theory of Mind Driven Presence Engine — Enhanced.

Combines sensor inputs to infer:
- WHERE you are (per-room tracking)
- WHO is present (identity detection from cameras)
- WHAT you're doing (activity context)
- WHAT you might need (anticipatory actions)
- WHAT you'll do next (intent prediction)

This is NOT colony mapping. This is learning YOUR patterns.

Enhanced Features (December 29, 2025):
- Per-room occupancy tracking
- Pattern learning (daily routines)
- Intent prediction (what's next?)
- Preference learning (manual adjustments)
- Room-specific recommendations

Split Architecture (January 2, 2026):
- presence_patterns.py: TimeSlot, RoomOccupancy, PatternRecord, PatternLearner
- presence_inference.py: IntentPredictor
- presence.py: PresenceEngine (this file)

Identity Detection (January 2, 2026):
- Real-time face recognition from UniFi cameras
- Per-identity presence tracking
- "Who's home?" queries
- Cryptographically signed identity events

Created: December 29, 2025
Refactored: January 2, 2026
"""

from __future__ import annotations

import datetime
import logging
import time
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

# Import split modules
from kagami_smarthome.presence_inference import IntentPredictor
from kagami_smarthome.presence_patterns import (
    PatternLearner,
    PatternRecord,
    RoomOccupancy,
    TimeSlot,
)
from kagami_smarthome.types import (
    ActivityContext,
    DSCZoneState,
    GeofenceState,
    HomeState,
    PresenceEvent,
    PresenceState,
    SecurityState,
    SmartHomeConfig,
    TrackedDevice,
)

if TYPE_CHECKING:
    from kagami_smarthome.localization import DeviceLocalizer, DeviceLocation
    from kagami_smarthome.room import RoomRegistry

logger = logging.getLogger(__name__)


# =============================================================================
# Enhanced Presence Engine
# =============================================================================


class PresenceEngine:
    """Theory of Mind driven presence inference — Enhanced with Deep Localization.

    Tracks:
    - Presence state (away, home, active, sleeping)
    - Activity context (waking, working, cooking, relaxing, sleeping)
    - Per-room occupancy with device-level tracking
    - Daily patterns (learned over time)
    - Device locations via UniFi WiFi AP association
    - Geofence state via Apple Find My

    Generates:
    - Anticipatory recommendations based on patterns
    - Room-specific suggestions
    - Intent predictions
    - Device-aware presence inference
    """

    def __init__(self, config: SmartHomeConfig):
        self.config = config
        self._state = HomeState()
        self._event_history: deque[PresenceEvent] = deque(maxlen=1000)

        # Per-room tracking
        self._room_occupancy: dict[str, RoomOccupancy] = {}

        # Pattern learning
        self.pattern_learner = PatternLearner(learning_rate=0.1)
        self.intent_predictor = IntentPredictor(self.pattern_learner)

        # Enhanced pattern tracking
        self._location_times: dict[str, list[float]] = {}
        self._activity_durations: dict[str, float] = {}

        # Room vacancy timeout (seconds)
        self._room_vacancy_timeout = 600  # 10 minutes

        # Device localization integration
        self._localizer: DeviceLocalizer | None = None

        # Identity tracking (face recognition from cameras)
        # identity_id -> {"last_seen": float, "last_location": str, "confidence": float, "name": str}
        self._identified_people: dict[str, dict[str, Any]] = {}
        # identity_id -> list of {timestamp, location, confidence}
        self._identity_history: dict[str, deque] = {}
        # How long before someone is considered "away"
        self._identity_away_timeout = 1800  # 30 minutes without detection

        # Arrival callback (called when owner arrives home via WiFi)
        self._on_arrival_callback: Callable[[], Any] | None = None

    def set_rooms(self, rooms: RoomRegistry) -> None:
        """Initialize room tracking from room registry."""
        for room in rooms.get_all():
            self._room_occupancy[room.name] = RoomOccupancy(room_name=room.name)

    def on_arrival(self, callback: Callable[[], Any]) -> None:
        """Register callback for owner arrival events.

        Args:
            callback: Async function called when owner arrives home
        """
        self._on_arrival_callback = callback

    def set_localizer(self, localizer: DeviceLocalizer) -> None:
        """Attach device localizer for deep presence tracking.

        Args:
            localizer: DeviceLocalizer instance
        """
        self._localizer = localizer

        # Register for room change callbacks
        localizer.on_room_change(self._on_device_room_change)

        logger.info("PresenceEngine: Device localizer attached")

    def _on_device_room_change(
        self,
        location: DeviceLocation,
        previous_room: str | None,
    ) -> None:
        """Handle device room change from localizer.

        This provides higher-fidelity presence tracking than motion sensors alone.
        """
        if not location.is_owner_device:
            return  # Only track owner's devices for presence

        now = time.time()

        # Update state
        self._state.last_location = location.current_room
        self._state.last_motion_time = now
        self._state.owner_room = location.current_room
        self._state.updated = now

        # Update room occupancy
        if location.current_room:
            if location.current_room not in self._room_occupancy:
                self._room_occupancy[location.current_room] = RoomOccupancy(
                    room_name=location.current_room
                )
            self._room_occupancy[location.current_room].enter(now)

        if previous_room and previous_room in self._room_occupancy:
            self._room_occupancy[previous_room].exit(now)

        # Create presence event
        event = PresenceEvent(
            source="device_localization",
            event_type="device_room_change",
            location=location.current_room,
            confidence=0.95,  # High confidence from WiFi AP
            timestamp=now,
            metadata={
                "device_mac": location.mac,
                "device_name": location.device_name,
                "previous_room": previous_room,
                "ap_mac": location.connected_ap_mac,
            },
        )
        self.process_event(event)

        # Learn from room transition
        self.pattern_learner.observe_room(location.current_room or "", now)

    def sync_from_localizer(self) -> None:
        """Synchronize state from device localizer.

        Call this periodically to ensure presence state matches device locations.
        """
        if not self._localizer:
            return

        now = time.time()

        # Update owner location
        owner_room = self._localizer.get_owner_room()
        if owner_room:
            self._state.owner_room = owner_room
            self._state.last_location = owner_room

        # Update geofence state
        self._state.owner_geofence = GeofenceState(self._localizer.get_owner_geofence_state().value)

        # Update occupied rooms
        self._state.occupied_rooms = self._localizer.get_all_occupied_rooms()

        # Update presence based on localization
        if self._localizer.is_owner_home():
            if self._localizer.get_owner_location():
                self._state.presence = PresenceState.ACTIVE
            else:
                self._state.presence = PresenceState.HOME
        elif self._localizer.is_owner_away():
            self._state.presence = PresenceState.AWAY

        # Update tracked devices in state
        for mac, loc in self._localizer.get_all_device_locations().items():
            self._state.tracked_devices[mac] = TrackedDevice(
                mac=mac,
                name=loc.device_name,
                device_type=loc.device_type,
                current_room=loc.current_room,
                previous_room=loc.previous_room,
                geofence_state=GeofenceState(loc.geofence_state.value),
                is_online=loc.is_online,
                last_seen=loc.last_seen,
                battery_level=loc.battery_level,
                is_owner=loc.is_owner_device,
            )

        self._state.updated = now

    def process_event(self, event: PresenceEvent) -> HomeState:
        """Process presence event and update state.

        Args:
            event: Presence event from sensor

        Returns:
            Updated home state
        """
        self._event_history.append(event)
        now = time.time()
        self._state.updated = now

        # Clear just_arrived after 60 seconds (gives routines time to trigger)
        if self._state.just_arrived and self._state.just_arrived_time > 0:
            if now - self._state.just_arrived_time > 60:
                self._state.just_arrived = False

        # Handle by event type
        if event.event_type in ("motion", "person", "smart_person"):
            self._handle_motion(event, now)
        elif event.event_type == "identity_detected":
            self._handle_identity_detected(event, now)
        elif event.event_type == "ring":
            self._handle_doorbell(event, now)
        elif event.event_type == "connect":
            self._handle_wifi_connect(event)
        elif event.event_type == "disconnect":
            self._handle_wifi_disconnect(event, now)
        elif event.event_type == "zone_open":
            self._handle_zone_open(event)
        elif event.event_type == "zone_closed":
            self._handle_zone_closed(event)

        # Infer activity context
        self._state.activity = self._infer_activity()

        # Learn patterns
        if event.location:
            self.pattern_learner.observe_room(event.location, now)
        self.pattern_learner.observe_activity(self._state.activity, now)

        # Check for rooms that should be marked vacant
        self._check_room_vacancy(now)

        return self._state

    def _handle_motion(self, event: PresenceEvent, now: float) -> None:
        """Handle motion/person detection."""
        self._state.presence = PresenceState.ACTIVE
        self._state.last_motion_time = now

        if event.location:
            # Update last location
            old_location = self._state.last_location
            self._state.last_location = event.location

            # Track location pattern (HARDENED)
            if event.location not in self._location_times:
                self._location_times[event.location] = []
            self._location_times[event.location].append(now)

            # Per-room tracking
            if event.location not in self._room_occupancy:
                self._room_occupancy[event.location] = RoomOccupancy(room_name=event.location)

            room_occ = self._room_occupancy[event.location]
            room_occ.enter(now)

            # If changed rooms, mark old room as exited
            if old_location and old_location != event.location:
                if old_location in self._room_occupancy:
                    self._room_occupancy[old_location].exit(now)

        # Person detection is higher confidence
        if event.event_type in ("person", "smart_person"):
            logger.debug(f"Person detected at {event.location}")

    def _handle_identity_detected(self, event: PresenceEvent, now: float) -> None:
        """Handle identity detection from camera face recognition."""
        identity_id = event.metadata.get("identity_id")
        if not identity_id:
            return

        # Delegate to process_identity_detected
        self.process_identity_detected(
            identity_id=identity_id,
            camera_id=event.metadata.get("camera_id", ""),
            camera_name=event.metadata.get("camera_name", event.location or ""),
            confidence=event.confidence,
            name=event.metadata.get("name"),
            face_quality=event.metadata.get("face_quality", 0.0),
            timestamp=now,
        )

    def _handle_doorbell(self, event: PresenceEvent, now: float) -> None:
        """Handle doorbell ring."""
        if self._state.presence == PresenceState.AWAY:
            self._state.presence = PresenceState.ARRIVING
            logger.info("Doorbell: Someone arriving")

    def _handle_wifi_connect(self, event: PresenceEvent) -> None:
        """Handle WiFi device connect."""
        mac = event.metadata.get("mac", "").lower()
        known_macs = {m.lower() for m in self.config.known_devices}

        if mac in known_macs:
            # Track if this is an arrival (was away, now home)
            was_away = self._state.presence == PresenceState.AWAY

            self._state.presence = PresenceState.HOME
            if mac not in self._state.wifi_devices_home:
                self._state.wifi_devices_home.append(mac)

            # Trigger welcome home on arrival (was away, now home)
            if was_away:
                self._state.just_arrived = True
                self._state.just_arrived_time = event.timestamp
                logger.info(f"🏠 WiFi: Owner arrived home ({mac[:8]}...)")
                # Trigger welcome home callback if registered
                if self._on_arrival_callback:
                    import asyncio

                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self._on_arrival_callback())
                    except RuntimeError:
                        # No running loop - run synchronously in new loop
                        asyncio.run(self._on_arrival_callback())
            else:
                logger.info(f"WiFi: Known device connected ({mac[:8]}...)")

    def _handle_wifi_disconnect(self, event: PresenceEvent, now: float) -> None:
        """Handle WiFi device disconnect."""
        mac = event.metadata.get("mac", "").lower()

        if mac in self._state.wifi_devices_home:
            self._state.wifi_devices_home.remove(mac)

        # If no known devices connected and no recent motion → might be away
        if not self._state.wifi_devices_home:
            time_since_motion = now - self._state.last_motion_time
            if time_since_motion > self.config.away_timeout_minutes * 60:
                self._state.presence = PresenceState.AWAY
                logger.info("No WiFi devices, no motion → Away")

    def _handle_zone_open(self, event: PresenceEvent) -> None:
        """Handle DSC zone open — update dsc_zones dict (open_zones is computed)."""
        zone_num = event.metadata.get("zone_num")
        if zone_num:
            self._update_dsc_zone(zone_num, "open", event)
        elif event.location:
            # No zone_num provided - use location name to find/create zone
            zone_num = self._get_or_create_zone_for_location(event.location)
            self._update_dsc_zone(zone_num, "open", event)

    def _handle_zone_closed(self, event: PresenceEvent) -> None:
        """Handle DSC zone closed — update dsc_zones dict (open_zones is computed)."""
        zone_num = event.metadata.get("zone_num")
        if zone_num:
            self._update_dsc_zone(zone_num, "closed", event)
        elif event.location:
            # No zone_num provided - find zone by location name
            zone_num = self._find_zone_by_name(event.location)
            if zone_num:
                self._update_dsc_zone(zone_num, "closed", event)

    def _get_or_create_zone_for_location(self, location: str) -> int:
        """Get existing zone number for location or create a synthetic one."""
        # First try to find existing zone with this name
        existing = self._find_zone_by_name(location)
        if existing:
            return existing

        # Create synthetic zone number (use hash to get consistent number)
        synthetic_num = abs(hash(location)) % 1000 + 1000  # 1000-1999 range
        return synthetic_num

    def _find_zone_by_name(self, name: str) -> int | None:
        """Find zone number by name."""
        name_lower = name.lower()
        for zone_num, zone in self._state.dsc_zones.items():
            if zone.name.lower() == name_lower:
                return zone_num
        return None

    def _update_dsc_zone(self, zone_num: int, state: str, event: PresenceEvent) -> None:
        """Update DSC zone state with room mapping."""
        zone_type = event.metadata.get("zone_type", "unknown")
        zone_name = event.location or f"Zone {zone_num}"

        # Infer room from zone name
        room = self._infer_room_from_zone(zone_name)

        if zone_num not in self._state.dsc_zones:
            self._state.dsc_zones[zone_num] = DSCZoneState(
                zone_num=zone_num,
                name=zone_name,
                zone_type=zone_type,
                room=room,
            )
            # Update zone-to-room mapping
            if room:
                self._state.zone_room_map[zone_num] = room

        zone = self._state.dsc_zones[zone_num]
        zone.state = state
        zone.last_activity = event.timestamp

        if state == "open":
            zone.activity_count += 1
            # Track motion duration for motion zones
            if zone.is_motion_zone:
                zone.last_motion_start = event.timestamp

    # =========================================================================
    # Enhanced DSC Integration (Envisalink)
    # =========================================================================

    def process_dsc_zone_event(
        self,
        zone_num: int,
        zone_name: str,
        zone_type: str,
        event_type: str,  # "open", "closed", "alarm", "tamper", "fault"
        timestamp: float | None = None,
    ) -> HomeState:
        """Process a DSC zone event from Envisalink.

        DSC zones are the PRIMARY sensor source for presence detection:
        - Motion zones → room occupancy + presence state
        - Door/window zones → entry/exit detection + security
        - Smoke/CO zones → life safety alerts

        Args:
            zone_num: Zone number (1-64)
            zone_name: Zone name (e.g., "Front Door", "Living Room Motion")
            zone_type: Zone type (door_window, motion, smoke, co, glass_break)
            event_type: Event type (open, closed, alarm, tamper, fault)
            timestamp: Event timestamp (defaults to now)

        Returns:
            Updated home state
        """
        ts = timestamp or time.time()

        # Infer room from zone name
        room_name = self._infer_room_from_zone(zone_name)

        # Create or update zone state
        if zone_num not in self._state.dsc_zones:
            self._state.dsc_zones[zone_num] = DSCZoneState(
                zone_num=zone_num,
                name=zone_name,
                zone_type=zone_type,
                room=room_name,
            )
            # Update zone-to-room mapping
            if room_name:
                self._state.zone_room_map[zone_num] = room_name

        zone = self._state.dsc_zones[zone_num]
        zone.state = event_type if event_type != "closed" else "closed"
        zone.last_activity = ts

        if event_type == "open":
            zone.activity_count += 1

            # Track motion timing for motion zones
            if zone_type == "motion":
                zone.last_motion_start = ts

                # Update occupied rooms
                if room_name and room_name not in self._state.occupied_rooms:
                    self._state.occupied_rooms.append(room_name)

        elif event_type == "closed" and zone_type == "motion":
            # Calculate motion duration
            if zone.last_motion_start > 0:
                zone.motion_duration = ts - zone.last_motion_start

        # Process as presence event for room tracking
        if zone_type == "motion" and event_type == "open":
            # Motion detection → strong presence signal
            presence_event = PresenceEvent(
                source="dsc_motion",
                event_type="motion",
                location=room_name,
                confidence=0.95,  # DSC motion is high confidence
                timestamp=ts,
                metadata={"zone_num": zone_num, "zone_type": zone_type},
            )
            self.process_event(presence_event)

        elif zone_type == "door_window" and event_type == "open":
            # Door/window opened → entry point activity
            presence_event = PresenceEvent(
                source="dsc_door",
                event_type="zone_open",
                location=room_name,
                confidence=0.9,
                timestamp=ts,
                metadata={"zone_num": zone_num, "zone_type": zone_type},
            )
            self.process_event(presence_event)

        elif zone_type in ("smoke", "co") and event_type == "alarm":
            # Life safety alarm — critical event
            logger.critical(f"LIFE SAFETY ALARM: {zone_name} ({zone_type})")

        # Update occupied rooms based on recent motion
        self._update_occupied_rooms_from_dsc()

        self._state.updated = ts
        return self._state

    def _update_occupied_rooms_from_dsc(self) -> None:
        """Update occupied_rooms list based on recent DSC motion."""
        recent_rooms = self._state.get_recent_motion_rooms(seconds=self._room_vacancy_timeout)

        # Merge with device-based occupancy
        device_rooms = set()
        if self._localizer:
            device_rooms = set(self._localizer.get_all_occupied_rooms())

        # Combine both sources
        self._state.occupied_rooms = list(set(recent_rooms) | device_rooms)

    def process_dsc_partition_event(
        self,
        partition_num: int,
        state: str,  # "ready", "armed_away", "armed_stay", "disarmed", "alarm", "entry_delay", "exit_delay"
        timestamp: float | None = None,
    ) -> HomeState:
        """Process a DSC partition event from Envisalink.

        Partition events provide strong presence signals:
        - armed_away → definitely leaving/left
        - disarmed → arriving home
        - entry_delay → arriving (door opened while armed)
        - exit_delay → leaving (arming in progress)

        Args:
            partition_num: Partition number (1-8)
            state: Partition state
            timestamp: Event timestamp

        Returns:
            Updated home state
        """
        ts = timestamp or time.time()

        # Update security state
        state_map = {
            "armed_away": SecurityState.ARMED_AWAY,
            "armed_stay": SecurityState.ARMED_STAY,
            "armed_night": SecurityState.ARMED_NIGHT,
            "disarmed": SecurityState.DISARMED,
            "alarm": SecurityState.ALARM,
            "trouble": SecurityState.TROUBLE,
        }

        if state in state_map:
            self._state.security = state_map[state]

        # Entry/exit delay tracking
        self._state.entry_delay_active = state == "entry_delay"
        self._state.exit_delay_active = state == "exit_delay"

        # Presence inference from partition state
        if state == "armed_away":
            # Armed away = leaving or left
            if self._state.presence not in (PresenceState.AWAY,):
                logger.info("DSC Armed Away → Presence: AWAY")
            self._state.presence = PresenceState.AWAY

        elif state == "disarmed":
            # Just disarmed = arriving or home
            if self._state.presence == PresenceState.AWAY:
                logger.info("DSC Disarmed (was away) → Presence: ARRIVING")
                self._state.presence = PresenceState.ARRIVING
            else:
                self._state.presence = PresenceState.HOME

        elif state == "entry_delay":
            # Entry delay = definitely arriving
            logger.info("DSC Entry Delay → Presence: ARRIVING")
            self._state.presence = PresenceState.ARRIVING

        elif state == "exit_delay":
            # Exit delay = leaving
            logger.info("DSC Exit Delay → User is leaving")
            # Don't change to AWAY yet - wait for armed_away

        elif state == "alarm":
            # Alarm! Could be intrusion or false alarm
            logger.warning("DSC ALARM triggered!")

        self._state.updated = ts
        return self._state

    def process_dsc_trouble_event(
        self,
        trouble_type: str,  # "ac_failure", "battery_low", "bell_trouble", etc.
        active: bool,
        zone_num: int | None = None,  # For zone-specific troubles
    ) -> HomeState:
        """Process a DSC trouble event from Envisalink.

        Args:
            trouble_type: Type of trouble condition
            active: True if trouble is active, False if restored
            zone_num: Zone number for zone-specific troubles (low battery)

        Returns:
            Updated home state
        """
        trouble = self._state.dsc_trouble

        if trouble_type == "ac_failure":
            trouble.ac_failure = active
        elif trouble_type == "battery_low":
            trouble.battery_low = active
        elif trouble_type == "bell_trouble":
            trouble.bell_trouble = active
        elif trouble_type == "phone_line":
            trouble.phone_line_trouble = active
        elif trouble_type == "fire_trouble":
            trouble.fire_trouble = active
        elif trouble_type == "system_tamper":
            trouble.system_tamper = active
        elif trouble_type == "zone_low_battery" and zone_num:
            if active:
                if zone_num not in trouble.low_battery_zones:
                    trouble.low_battery_zones.append(zone_num)
                if zone_num in self._state.dsc_zones:
                    self._state.dsc_zones[zone_num].battery_low = True
            else:
                if zone_num in trouble.low_battery_zones:
                    trouble.low_battery_zones.remove(zone_num)
                if zone_num in self._state.dsc_zones:
                    self._state.dsc_zones[zone_num].battery_low = False

        self._state.updated = time.time()
        return self._state

    def process_dsc_temperature(
        self,
        interior: float | None = None,
        exterior: float | None = None,
    ) -> HomeState:
        """Process temperature reading from DSC EMS-100 module.

        Args:
            interior: Interior temperature (°F)
            exterior: Exterior temperature (°F)

        Returns:
            Updated home state
        """
        if interior is not None:
            self._state.dsc_temperature.interior = interior
        if exterior is not None:
            self._state.dsc_temperature.exterior = exterior
        self._state.dsc_temperature.timestamp = time.time()
        self._state.updated = time.time()
        return self._state

    def _infer_room_from_zone(self, zone_name: str) -> str | None:
        """Infer room name from DSC zone name.

        Common patterns:
        - "Front Door" → "Entry"
        - "Living Room Motion" → "Living Room"
        - "Master Bedroom Window" → "Master Bedroom"
        """
        zone_lower = zone_name.lower()

        # Remove common suffixes to get room name
        suffixes = [" motion", " door", " window", " glass break", " smoke", " co"]
        room = zone_name
        for suffix in suffixes:
            if zone_lower.endswith(suffix):
                room = zone_name[: -len(suffix)]
                break

        # Map common entry points
        if "front door" in zone_lower or "back door" in zone_lower or "garage door" in zone_lower:
            return "Entry"

        return room if room != zone_name else None

    def get_dsc_zone_activity_summary(self) -> dict[str, list[DSCZoneState]]:
        """Get DSC zone activity summary grouped by type.

        Returns:
            Dict with keys: "motion", "door_window", "smoke", "co", "other"
            Each containing list of zones of that type sorted by last activity
        """
        summary: dict[str, list[DSCZoneState]] = {
            "motion": [],
            "door_window": [],
            "smoke": [],
            "co": [],
            "other": [],
        }

        for zone in self._state.dsc_zones.values():
            zone_type = zone.zone_type
            if zone_type in summary:
                summary[zone_type].append(zone)
            else:
                summary["other"].append(zone)

        # Sort each by last activity (most recent first)
        for zones in summary.values():
            zones.sort(key=lambda z: z.last_activity, reverse=True)

        return summary

    def get_recent_dsc_motion(self, seconds: float = 300) -> list[DSCZoneState]:
        """Get DSC motion zones with recent activity.

        Args:
            seconds: Time window (default 5 minutes)

        Returns:
            List of motion zones with activity in time window
        """
        now = time.time()
        return [
            z
            for z in self._state.dsc_zones.values()
            if z.zone_type == "motion" and z.last_activity > 0 and (now - z.last_activity) < seconds
        ]

    def _check_room_vacancy(self, now: float) -> None:
        """Check for rooms that should be marked vacant."""
        for room_name, occupancy in self._room_occupancy.items():
            if occupancy.occupied:
                if occupancy.time_since_motion() > self._room_vacancy_timeout:
                    occupancy.exit(now)
                    logger.debug(f"Room {room_name} marked vacant (timeout)")

    def _infer_activity(self) -> ActivityContext:
        """Infer current activity from state and time."""
        now = datetime.datetime.now()
        hour = now.hour
        time_since_motion = time.time() - self._state.last_motion_time

        # Night + no motion = sleeping
        is_night = hour >= self.config.sleep_start_hour or hour < self.config.sleep_end_hour
        if is_night and time_since_motion > 1800:  # 30 min
            return ActivityContext.SLEEPING

        # Morning routine (6-9 AM)
        if 6 <= hour < 9:
            return ActivityContext.WAKING

        # Location-based inference
        location = (self._state.last_location or "").lower()

        if any(x in location for x in ["office", "desk"]):
            return ActivityContext.WORKING

        if "kitchen" in location:
            # Kitchen during meal times
            if 7 <= hour <= 9 or 11 <= hour <= 13 or 17 <= hour <= 20:
                return ActivityContext.COOKING

        if any(x in location for x in ["living", "family", "game"]):
            if hour >= 18:
                return ActivityContext.RELAXING

        if "bed" in location and hour >= 21:
            return ActivityContext.SLEEPING

        return ActivityContext.UNKNOWN

    # =========================================================================
    # Room Tracking
    # =========================================================================

    def get_occupied_rooms(self) -> list[str]:
        """Get list of currently occupied rooms."""
        return [name for name, occ in self._room_occupancy.items() if occ.occupied]

    def get_room_occupancy(self, room_name: str) -> RoomOccupancy | None:
        """Get occupancy info for a room."""
        return self._room_occupancy.get(room_name)

    def is_room_occupied(self, room_name: str) -> bool:
        """Check if a room is occupied."""
        occ = self._room_occupancy.get(room_name)
        return occ.occupied if occ else False

    def get_most_active_room(self) -> str | None:
        """Get room with most recent activity."""
        best_room = None
        best_time = 0.0

        for name, occ in self._room_occupancy.items():
            if occ.last_motion > best_time:
                best_time = occ.last_motion
                best_room = name

        return best_room

    # =========================================================================
    # Intent Prediction
    # =========================================================================

    def predict_intent(self, device_states: dict[str, Any] | None = None) -> dict[str, Any]:
        """Predict user intent.

        Args:
            device_states: Optional dict of current device states
                e.g., {"eight_sleep_awake": True, "denon_on": False}

        Returns:
            Intent prediction with activity, room, confidence, reasoning
        """
        return self.intent_predictor.predict_intent(
            current_room=self._state.last_location,
            current_activity=self._state.activity,
            device_states=device_states,
        )

    def predict_next_room(self) -> tuple[str, float] | None:
        """Predict next room based on patterns."""
        if not self._state.last_location:
            return None
        return self.pattern_learner.predict_next_room(self._state.last_location)

    # =========================================================================
    # Preference Learning
    # =========================================================================

    def learn_preference_adjustment(
        self,
        room_name: str,
        setting: str,
        value: float,
    ) -> None:
        """Learn from manual adjustment.

        Call this when Tim manually adjusts a setting (lights, temp, etc.)
        to learn preferences.
        """
        activity = self._state.activity
        self.pattern_learner.learn_preference(room_name, activity, setting, value)
        logger.debug(f"Learned preference: {room_name}/{activity.value}/{setting}={value}")

    def get_preferred_setting(
        self,
        room_name: str,
        setting: str,
        default: float,
    ) -> float:
        """Get learned preference for current activity."""
        return self.pattern_learner.get_preferred_setting(
            room_name,
            self._state.activity,
            setting,
            default,
        )

    # =========================================================================
    # State and Recommendations
    # =========================================================================

    def get_state(self) -> HomeState:
        """Get current home state."""
        return self._state

    def is_owner_home(self) -> bool:
        """Check if owner is home.

        Returns:
            True if owner is home (not away)
        """
        return self._state.presence != PresenceState.AWAY

    def is_owner_away(self) -> bool:
        """Check if owner is away.

        Returns:
            True if owner is away
        """
        return self._state.presence == PresenceState.AWAY

    def get_owner_location(self) -> str | None:
        """Get owner's current location (room name).

        Returns:
            Room name if known, None otherwise
        """
        return self._state.last_location

    def get_geofence_state(self) -> GeofenceState:
        """Get owner's geofence state.

        Returns:
            GeofenceState enum value
        """
        return self._state.owner_geofence

    def is_in_room(self, room: str) -> bool:
        """Check if owner is in a specific room.

        Args:
            room: Room name to check

        Returns:
            True if owner is in the room
        """
        return self._state.last_location == room

    def get_recommendations(self) -> list[dict[str, Any]]:
        """Get Theory of Mind recommendations.

        Returns actions based on:
        - Current presence state
        - Current activity context
        - Time of day
        - Recent patterns
        - Per-room occupancy
        """
        recommendations: list[dict[str, Any]] = []
        state = self._state

        # === ARRIVING HOME ===
        if state.presence == PresenceState.ARRIVING:
            recommendations.append(
                {
                    "action": "disarm_security",
                    "reason": "Arriving home",
                    "confidence": 0.9,
                    "params": {},
                }
            )
            recommendations.append(
                {
                    "action": "set_scene",
                    "reason": "Welcome home scene",
                    "confidence": 0.85,
                    "params": {"scene": "welcome_home"},
                }
            )

        # === WAKING UP ===
        if state.activity == ActivityContext.WAKING:
            recommendations.append(
                {
                    "action": "set_scene",
                    "reason": "Morning routine",
                    "confidence": 0.85,
                    "params": {"scene": "morning", "rooms": self.get_occupied_rooms()},
                }
            )

        # === COOKING ===
        if state.activity == ActivityContext.COOKING:
            recommendations.append(
                {
                    "action": "set_scene",
                    "reason": "Cooking activity",
                    "confidence": 0.8,
                    "params": {"scene": "cooking", "rooms": ["Kitchen"]},
                }
            )

        # === RELAXING (Evening) ===
        if state.activity == ActivityContext.RELAXING:
            recommendations.append(
                {
                    "action": "set_scene",
                    "reason": "Evening relaxation",
                    "confidence": 0.75,
                    "params": {"scene": "relaxing", "rooms": self.get_occupied_rooms()},
                }
            )

        # === GOING TO BED ===
        if state.activity == ActivityContext.SLEEPING:
            recommendations.append(
                {
                    "action": "set_scene",
                    "reason": "Bedtime",
                    "confidence": 0.9,
                    "params": {"scene": "goodnight"},
                }
            )
            recommendations.append(
                {
                    "action": "arm_security",
                    "reason": "Night security",
                    "confidence": 0.85,
                    "params": {"mode": "night"},
                }
            )

        # === LEAVING (Away + Disarmed) ===
        if state.presence == PresenceState.AWAY and state.security == SecurityState.DISARMED:
            recommendations.append(
                {
                    "action": "set_scene",
                    "reason": "Nobody home",
                    "confidence": 0.95,
                    "params": {"scene": "away"},
                }
            )
            recommendations.append(
                {
                    "action": "arm_security",
                    "reason": "Left home, security should be armed",
                    "confidence": 0.95,
                    "params": {"mode": "away"},
                }
            )
            recommendations.append(
                {
                    "action": "lock_all",
                    "reason": "Lock all doors when away",
                    "confidence": 0.95,
                    "params": {},
                }
            )

        # === ROOM-SPECIFIC: Vacant rooms ===
        for room_name, occ in self._room_occupancy.items():
            if not occ.occupied and occ.motion_count > 0:
                # Room was occupied but now vacant
                time_vacant = time.time() - (occ.entry_time or time.time())
                if time_vacant > 300:  # 5 minutes
                    recommendations.append(
                        {
                            "action": "room_vacant",
                            "reason": f"{room_name} unoccupied for {int(time_vacant / 60)} min",
                            "confidence": 0.7,
                            "params": {"room": room_name},
                        }
                    )

        # === INTENT-BASED ===
        intent = self.predict_intent()
        if intent["confidence"] > 0.7 and intent["predicted_next_room"]:
            recommendations.append(
                {
                    "action": "prepare_room",
                    "reason": f"Likely moving to {intent['predicted_next_room']}",
                    "confidence": intent["confidence"],
                    "params": {"room": intent["predicted_next_room"]},
                }
            )

        return recommendations

    def get_room_recommendations(self, room_name: str) -> list[dict[str, Any]]:
        """Get recommendations specific to a room."""
        recommendations = []

        occupancy = self._room_occupancy.get(room_name)
        if not occupancy:
            return recommendations

        activity = self._state.activity

        # Suggest learned preferences
        light_pref = self.get_preferred_setting(room_name, "light", -1)
        if light_pref >= 0:
            recommendations.append(
                {
                    "action": "set_lights",
                    "reason": f"Learned preference for {activity.value}",
                    "confidence": 0.7,
                    "params": {"room": room_name, "level": int(light_pref)},
                }
            )

        temp_pref = self.get_preferred_setting(room_name, "temp", -1)
        if temp_pref >= 0:
            recommendations.append(
                {
                    "action": "set_temp",
                    "reason": f"Learned preference for {activity.value}",
                    "confidence": 0.7,
                    "params": {"room": room_name, "temp": temp_pref},
                }
            )

        return recommendations

    def get_recent_events(self, count: int = 20) -> list[PresenceEvent]:
        """Get recent events."""
        return list(self._event_history)[-count:]

    def get_location_patterns(self) -> dict[str, int]:
        """Get location visit counts (for debugging)."""
        return {loc: len(times) for loc, times in self._location_times.items()}

    # =========================================================================
    # PATTERN PERSISTENCE
    # =========================================================================

    def save_patterns(self, path: str | None = None) -> bool:
        """Save learned patterns to disk.

        Args:
            path: Optional path (default: ~/.kagami/patterns.json via persistence module)

        Returns:
            True if saved successfully
        """
        if path is None:
            from kagami_smarthome.persistence import PATTERNS_FILE, ensure_kagami_home

            ensure_kagami_home()
            path = str(PATTERNS_FILE)

        return self.pattern_learner.save_to_file(path)

    def load_patterns(self, path: str | None = None) -> bool:
        """Load learned patterns from disk.

        Args:
            path: Optional path (default: ~/.kagami/patterns.json via persistence module)

        Returns:
            True if loaded successfully
        """
        if path is None:
            from kagami_smarthome.persistence import PATTERNS_FILE

            path = str(PATTERNS_FILE)

        loaded = PatternLearner.load_from_file(path)
        if loaded:
            self.pattern_learner = loaded
            self.intent_predictor = IntentPredictor(self.pattern_learner)
            return True
        return False

    def get_pattern_stats(self) -> dict[str, Any]:
        """Get statistics about learned patterns."""
        return self.pattern_learner.get_pattern_stats()

    # =========================================================================
    # IDENTITY DETECTION (Face Recognition from Cameras)
    # =========================================================================

    def process_identity_detected(
        self,
        identity_id: str,
        camera_id: str,
        camera_name: str,
        confidence: float,
        name: str | None = None,
        face_quality: float = 0.0,
        timestamp: float | None = None,
    ) -> HomeState:
        """Process an identity detection event from camera face recognition.

        This is called when the realtime face matcher identifies someone.
        Updates "who is home" tracking and emits signed identity events.

        Args:
            identity_id: Unique identifier for the detected person
            camera_id: Camera that detected the identity
            camera_name: Human-readable camera name (used as location)
            confidence: Match confidence (0-1)
            name: Optional display name for the identity
            face_quality: Quality score of the face detection
            timestamp: Event timestamp (defaults to now)

        Returns:
            Updated home state
        """
        ts = timestamp or time.time()

        # Infer room from camera name
        room_name = self._infer_room_from_camera(camera_name)

        # Update identity tracking
        if identity_id not in self._identified_people:
            self._identified_people[identity_id] = {
                "first_seen": ts,
                "name": name,
            }
            self._identity_history[identity_id] = deque(maxlen=100)

        self._identified_people[identity_id].update(
            {
                "last_seen": ts,
                "last_location": room_name or camera_name,
                "confidence": confidence,
                "face_quality": face_quality,
            }
        )
        if name:
            self._identified_people[identity_id]["name"] = name

        # Add to history
        self._identity_history[identity_id].append(
            {
                "timestamp": ts,
                "location": room_name or camera_name,
                "confidence": confidence,
                "camera_id": camera_id,
            }
        )

        # Update room occupancy
        if room_name:
            if room_name not in self._room_occupancy:
                self._room_occupancy[room_name] = RoomOccupancy(room_name=room_name)
            self._room_occupancy[room_name].enter(ts)
            self._state.last_location = room_name

        # Update presence state
        self._state.presence = PresenceState.ACTIVE
        self._state.last_motion_time = ts
        self._state.updated = ts

        # Create presence event
        event = PresenceEvent(
            source="face_recognition",
            event_type="identity_detected",
            location=room_name or camera_name,
            confidence=confidence,
            timestamp=ts,
            metadata={
                "identity_id": identity_id,
                "name": name,
                "camera_id": camera_id,
                "camera_name": camera_name,
                "face_quality": face_quality,
            },
        )
        self._event_history.append(event)

        # Learn from identity detection
        if room_name:
            self.pattern_learner.observe_room(room_name, ts)

        logger.info(
            f"👤 Identity detected: {name or identity_id} at {room_name or camera_name} "
            f"(confidence: {confidence:.2f})"
        )

        return self._state

    def get_people_home(self) -> list[dict[str, Any]]:
        """Get list of identified people currently at home.

        Returns:
            List of dicts with identity_id, name, last_seen, last_location, confidence
        """
        now = time.time()
        people_home = []

        for identity_id, data in self._identified_people.items():
            time_since_seen = now - data.get("last_seen", 0)
            if time_since_seen < self._identity_away_timeout:
                people_home.append(
                    {
                        "identity_id": identity_id,
                        "name": data.get("name"),
                        "last_seen": data.get("last_seen"),
                        "last_location": data.get("last_location"),
                        "confidence": data.get("confidence", 0),
                        "minutes_since_seen": int(time_since_seen / 60),
                    }
                )

        return people_home

    def is_person_home(self, identity_id: str) -> bool:
        """Check if a specific person is home.

        Args:
            identity_id: Identity to check

        Returns:
            True if person was recently detected
        """
        if identity_id not in self._identified_people:
            return False

        now = time.time()
        last_seen = self._identified_people[identity_id].get("last_seen", 0)
        return (now - last_seen) < self._identity_away_timeout

    def get_person_location(self, identity_id: str) -> str | None:
        """Get last known location of a person.

        Args:
            identity_id: Identity to look up

        Returns:
            Last known location or None
        """
        if identity_id not in self._identified_people:
            return None
        return self._identified_people[identity_id].get("last_location")

    def get_person_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a person by name.

        Args:
            name: Name to search for (case-insensitive)

        Returns:
            Person data dict or None
        """
        name_lower = name.lower()
        for identity_id, data in self._identified_people.items():
            if data.get("name", "").lower() == name_lower:
                return {
                    "identity_id": identity_id,
                    **data,
                }
        return None

    def get_identity_history(
        self,
        identity_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get detection history for an identity.

        Args:
            identity_id: Identity to look up
            limit: Maximum number of records to return

        Returns:
            List of detection records (most recent first)
        """
        if identity_id not in self._identity_history:
            return []
        return list(self._identity_history[identity_id])[-limit:][::-1]

    def _infer_room_from_camera(self, camera_name: str) -> str | None:
        """Infer room name from camera name.

        Common patterns:
        - "Living Room Camera" → "Living Room"
        - "Front Door" → "Entry"
        - "Garage Camera" → "Garage"
        """
        camera_lower = camera_name.lower()

        # Remove common camera suffixes
        suffixes = [" camera", " cam", " doorbell", " nvr"]
        room = camera_name
        for suffix in suffixes:
            if camera_lower.endswith(suffix):
                room = camera_name[: -len(suffix)]
                break

        # Map specific camera names to rooms
        camera_to_room = {
            "front door": "Entry",
            "back door": "Patio",
            "garage": "Garage",
            "driveway": "Entry",
        }

        room_lower = room.lower()
        for pattern, mapped_room in camera_to_room.items():
            if pattern in room_lower:
                return mapped_room

        return room if room != camera_name else None

    def set_identity_away_timeout(self, minutes: int) -> None:
        """Set how long before someone is considered away.

        Args:
            minutes: Minutes without detection before considered away
        """
        self._identity_away_timeout = minutes * 60


# Re-export for backwards compatibility
__all__ = [
    "PresenceEngine",
    # Re-exported from split modules
    "TimeSlot",
    "RoomOccupancy",
    "PatternRecord",
    "PatternLearner",
    "IntentPredictor",
]
