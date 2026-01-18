"""Unified Sensor Fusion Bus — Multi-Signal Location and Context.

Fuses multiple sensory inputs to provide:
- High-confidence location tracking
- Visual context awareness
- Intent prediction enhancement
- Cross-device coordination

Signal Sources:
- WiFi AP association (UniFi) → Floor/room detection
- WiFi RSSI (signal strength) → Room inference
- GPS (Apple FindMy) → At home vs away
- Control4 activity → Room confirmation
- Meta Glasses camera → Visual context
- Meta Glasses audio → Speech context
- Motion sensors (DSC) → Presence confirmation
- Health sensors (Watch) → Biometric context

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.integrations.meta_glasses import MetaGlassesIntegration
    from kagami_smarthome.localization import PersonTracker

logger = logging.getLogger(__name__)


class SignalSource(Enum):
    """Available signal sources for sensor fusion."""

    # Location signals
    WIFI_AP = "wifi_ap"  # UniFi AP association
    WIFI_RSSI = "wifi_rssi"  # WiFi signal strength
    GPS_FINDMY = "gps_findmy"  # Apple FindMy GPS
    CONTROL4_ACTIVITY = "control4_activity"  # Control4 device activity
    DSC_MOTION = "dsc_motion"  # DSC motion sensors

    # Visual signals (Meta Glasses)
    META_CAMERA = "meta_camera"  # First-person camera
    META_AUDIO = "meta_audio"  # Microphone/speech

    # Biometric signals
    WATCH_HEALTH = "watch_health"  # Apple Watch health data
    EIGHT_SLEEP = "eight_sleep"  # Sleep tracking

    # Future signals
    UWB_BEACON = "uwb_beacon"  # Ultra-wideband beacons


@dataclass
class SignalReading:
    """A reading from a signal source."""

    source: SignalSource
    timestamp: float
    confidence: float  # 0.0 - 1.0
    data: dict[str, Any] = field(default_factory=dict)

    # Location inference (if applicable)
    floor: str | None = None
    room: str | None = None

    # Context (if applicable)
    activity: str | None = None
    scene_type: str | None = None

    @property
    def age_seconds(self) -> float:
        """Get age of reading in seconds."""
        return time.time() - self.timestamp

    @property
    def is_stale(self) -> bool:
        """Check if reading is too old to be useful."""
        max_ages = {
            SignalSource.WIFI_AP: 30,
            SignalSource.WIFI_RSSI: 30,
            SignalSource.GPS_FINDMY: 600,
            SignalSource.CONTROL4_ACTIVITY: 60,
            SignalSource.DSC_MOTION: 300,
            SignalSource.META_CAMERA: 10,
            SignalSource.META_AUDIO: 5,
            SignalSource.WATCH_HEALTH: 60,
            SignalSource.EIGHT_SLEEP: 600,
            SignalSource.UWB_BEACON: 5,
        }
        return self.age_seconds > max_ages.get(self.source, 60)


@dataclass
class FusedLocation:
    """Location result from sensor fusion."""

    floor: str | None = None
    room: str | None = None
    confidence: float = 0.0

    # Contributing signals
    sources: list[SignalSource] = field(default_factory=list)
    source_count: int = 0

    # GPS fallback
    is_home: bool | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None

    @property
    def has_location(self) -> bool:
        """Check if we have a valid location."""
        return self.floor is not None or self.room is not None


@dataclass
class FusedContext:
    """Context result from sensor fusion."""

    # Visual context (from glasses)
    is_indoor: bool | None = None
    lighting: str | None = None
    scene_type: str | None = None
    detected_objects: list[str] = field(default_factory=list)
    detected_text: list[str] = field(default_factory=list)
    faces_detected: int = 0
    known_people: list[str] = field(default_factory=list)

    # Activity context
    activity: str | None = None
    activity_confidence: float = 0.0

    # Biometric context
    heart_rate: int | None = None
    is_sleeping: bool | None = None
    stress_level: str | None = None

    # Confidence
    visual_confidence: float = 0.0
    overall_confidence: float = 0.0


@dataclass
class FusedState:
    """Combined fused state from all sensors."""

    location: FusedLocation = field(default_factory=FusedLocation)
    context: FusedContext = field(default_factory=FusedContext)
    timestamp: float = field(default_factory=time.time)

    # Raw readings for debugging
    readings: list[SignalReading] = field(default_factory=list)


class SensorFusionBus:
    """Unified sensor fusion bus.

    Collects readings from multiple signal sources and fuses them
    to produce high-confidence location and context estimates.

    Usage:
        fusion = SensorFusionBus()

        # Register signal sources
        fusion.register_person_tracker(tracker)
        fusion.register_meta_glasses(glasses)

        # Start polling
        await fusion.start()

        # Get fused state
        state = await fusion.get_fused_state()
        print(f"Location: {state.location.room} ({state.location.confidence:.0%})")
        print(f"Activity: {state.context.activity}")
    """

    def __init__(self) -> None:
        # Signal sources
        self._person_tracker: PersonTracker | None = None
        self._meta_glasses: MetaGlassesIntegration | None = None

        # Recent readings by source
        self._readings: dict[SignalSource, SignalReading] = {}

        # Polling
        self._running = False
        self._poll_task: asyncio.Task | None = None
        self._poll_interval = 3.0

        # Signal weights for fusion
        self._location_weights = {
            SignalSource.WIFI_AP: 0.35,
            SignalSource.WIFI_RSSI: 0.20,
            SignalSource.GPS_FINDMY: 0.10,  # Only for home/away
            SignalSource.CONTROL4_ACTIVITY: 0.15,
            SignalSource.DSC_MOTION: 0.10,
            SignalSource.META_CAMERA: 0.05,  # Scene hints
            SignalSource.UWB_BEACON: 0.40,  # High precision when available
        }

        self._context_weights = {
            SignalSource.META_CAMERA: 0.50,
            SignalSource.META_AUDIO: 0.20,
            SignalSource.CONTROL4_ACTIVITY: 0.15,
            SignalSource.WATCH_HEALTH: 0.10,
            SignalSource.EIGHT_SLEEP: 0.05,
        }

    # =========================================================================
    # Signal Source Registration
    # =========================================================================

    def register_person_tracker(self, tracker: PersonTracker) -> None:
        """Register person tracker for WiFi/GPS signals.

        Args:
            tracker: PersonTracker instance
        """
        self._person_tracker = tracker
        logger.info("SensorFusion: PersonTracker registered")

    def register_meta_glasses(self, glasses: MetaGlassesIntegration) -> None:
        """Register Meta glasses for visual/audio signals.

        Args:
            glasses: MetaGlassesIntegration instance
        """
        self._meta_glasses = glasses
        logger.info("SensorFusion: MetaGlasses registered")

    # =========================================================================
    # Manual Signal Injection
    # =========================================================================

    def inject_reading(self, reading: SignalReading) -> None:
        """Inject a signal reading manually.

        Used by integrations to push readings to the fusion bus.

        Args:
            reading: SignalReading to inject
        """
        self._readings[reading.source] = reading
        logger.debug(f"SensorFusion: Injected {reading.source.value} reading")

    def inject_control4_activity(
        self,
        room: str,
        activity_type: str,
        confidence: float = 0.8,
    ) -> None:
        """Inject Control4 activity signal.

        Args:
            room: Room where activity occurred
            activity_type: Type of activity (light, audio, etc.)
            confidence: Confidence level
        """
        reading = SignalReading(
            source=SignalSource.CONTROL4_ACTIVITY,
            timestamp=time.time(),
            confidence=confidence,
            room=room,
            activity=activity_type,
            data={"room": room, "type": activity_type},
        )
        self.inject_reading(reading)

    def inject_dsc_motion(
        self,
        room: str,
        zone_type: str = "motion",
        confidence: float = 0.9,
    ) -> None:
        """Inject DSC motion signal.

        Args:
            room: Room where motion detected
            zone_type: Type of zone
            confidence: Confidence level
        """
        reading = SignalReading(
            source=SignalSource.DSC_MOTION,
            timestamp=time.time(),
            confidence=confidence,
            room=room,
            data={"room": room, "zone_type": zone_type},
        )
        self.inject_reading(reading)

    def inject_visual_context(
        self,
        scene_type: str | None = None,
        is_indoor: bool | None = None,
        lighting: str | None = None,
        objects: list[str] | None = None,
        text: list[str] | None = None,
        faces: int = 0,
        activity: str | None = None,
        confidence: float = 0.7,
    ) -> None:
        """Inject visual context from Meta glasses.

        Args:
            scene_type: Type of scene detected
            is_indoor: Whether indoor
            lighting: Lighting condition
            objects: Detected objects
            text: Detected text
            faces: Number of faces
            activity: Inferred activity
            confidence: Confidence level
        """
        reading = SignalReading(
            source=SignalSource.META_CAMERA,
            timestamp=time.time(),
            confidence=confidence,
            scene_type=scene_type,
            activity=activity,
            data={
                "is_indoor": is_indoor,
                "lighting": lighting,
                "objects": objects or [],
                "text": text or [],
                "faces": faces,
            },
        )
        self.inject_reading(reading)

    def inject_health_data(
        self,
        heart_rate: int | None = None,
        is_sleeping: bool | None = None,
        stress_level: str | None = None,
        confidence: float = 0.8,
    ) -> None:
        """Inject health data from watch.

        Args:
            heart_rate: Current heart rate
            is_sleeping: Whether user is sleeping
            stress_level: Stress level (low, medium, high)
            confidence: Confidence level
        """
        reading = SignalReading(
            source=SignalSource.WATCH_HEALTH,
            timestamp=time.time(),
            confidence=confidence,
            data={
                "heart_rate": heart_rate,
                "is_sleeping": is_sleeping,
                "stress_level": stress_level,
            },
        )
        self.inject_reading(reading)

    # =========================================================================
    # Polling
    # =========================================================================

    async def start(self) -> None:
        """Start sensor fusion polling."""
        if self._running:
            return

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("SensorFusion: Started")

    async def stop(self) -> None:
        """Stop sensor fusion polling."""
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        logger.info("SensorFusion: Stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self._poll_sources()
            except Exception as e:
                logger.error(f"SensorFusion poll error: {e}")

            await asyncio.sleep(self._poll_interval)

    async def _poll_sources(self) -> None:
        """Poll all registered signal sources."""
        now = time.time()

        # Poll person tracker (WiFi, GPS)
        if self._person_tracker:
            await self._poll_person_tracker(now)

        # Poll Meta glasses (visual context)
        if self._meta_glasses:
            await self._poll_meta_glasses(now)

    async def _poll_person_tracker(self, now: float) -> None:
        """Poll person tracker for location signals."""
        if not self._person_tracker:
            return

        # Get owner location
        owner_room = self._person_tracker.get_owner_room()
        owner_geofence = self._person_tracker.get_owner_geofence_state()

        if owner_room:
            # Get floor from room
            from kagami_smarthome.localization import FLOOR_ROOMS

            floor = None
            for floor_name, rooms in FLOOR_ROOMS.items():
                if owner_room in rooms:
                    floor = floor_name
                    break

            reading = SignalReading(
                source=SignalSource.WIFI_AP,
                timestamp=now,
                confidence=0.85,
                floor=floor,
                room=owner_room,
                data={"room": owner_room, "floor": floor},
            )
            self.inject_reading(reading)

        # GPS/geofence
        from kagami_smarthome.types import GeofenceState

        is_home = owner_geofence == GeofenceState.HOME

        reading = SignalReading(
            source=SignalSource.GPS_FINDMY,
            timestamp=now,
            confidence=0.9 if owner_geofence != GeofenceState.UNKNOWN else 0.3,
            data={
                "is_home": is_home,
                "geofence_state": owner_geofence.value,
            },
        )
        self.inject_reading(reading)

    async def _poll_meta_glasses(self, now: float) -> None:
        """Poll Meta glasses for visual context."""
        if not self._meta_glasses or not self._meta_glasses.is_connected:
            return

        try:
            context = await self._meta_glasses.get_visual_context()
            if context:
                self.inject_visual_context(
                    scene_type=context.scene_type,
                    is_indoor=context.is_indoor,
                    lighting=context.lighting,
                    objects=context.detected_objects,
                    text=context.detected_text,
                    faces=context.faces_detected,
                    activity=context.activity_hint,
                    confidence=context.confidence,
                )
        except Exception as e:
            logger.debug(f"Failed to poll Meta glasses: {e}")

    # =========================================================================
    # Fusion
    # =========================================================================

    async def get_fused_state(self) -> FusedState:
        """Get current fused state from all sensors.

        Returns:
            FusedState with location and context
        """
        now = time.time()

        # Filter out stale readings
        fresh_readings = [r for r in self._readings.values() if not r.is_stale]

        # Fuse location
        location = self._fuse_location(fresh_readings)

        # Fuse context
        context = self._fuse_context(fresh_readings)

        return FusedState(
            location=location,
            context=context,
            timestamp=now,
            readings=fresh_readings,
        )

    def _fuse_location(self, readings: list[SignalReading]) -> FusedLocation:
        """Fuse location from multiple readings.

        Uses weighted voting with confidence scores.
        """
        location = FusedLocation()

        # Collect room/floor votes
        floor_votes: dict[str, float] = defaultdict(float)
        room_votes: dict[str, float] = defaultdict(float)
        sources: list[SignalSource] = []

        for reading in readings:
            weight = self._location_weights.get(reading.source, 0.1)
            score = weight * reading.confidence

            if reading.floor:
                floor_votes[reading.floor] += score

            if reading.room:
                room_votes[reading.room] += score

            # Track GPS for home/away
            if reading.source == SignalSource.GPS_FINDMY:
                location.is_home = reading.data.get("is_home")
                location.gps_latitude = reading.data.get("latitude")
                location.gps_longitude = reading.data.get("longitude")

            sources.append(reading.source)

        # Select best floor
        if floor_votes:
            location.floor = max(floor_votes.keys(), key=lambda f: floor_votes[f])

        # Select best room
        if room_votes:
            location.room = max(room_votes.keys(), key=lambda r: room_votes[r])
            # Calculate confidence from vote strength
            total_room_votes = sum(room_votes.values())
            if total_room_votes > 0:
                location.confidence = min(1.0, room_votes[location.room] / (total_room_votes * 0.5))

        location.sources = list(set(sources))
        location.source_count = len(location.sources)

        return location

    def _fuse_context(self, readings: list[SignalReading]) -> FusedContext:
        """Fuse context from multiple readings."""
        context = FusedContext()

        # Find visual reading
        camera_reading = self._readings.get(SignalSource.META_CAMERA)
        if camera_reading and not camera_reading.is_stale:
            data = camera_reading.data
            context.is_indoor = data.get("is_indoor")
            context.lighting = data.get("lighting")
            context.scene_type = camera_reading.scene_type
            context.detected_objects = data.get("objects", [])
            context.detected_text = data.get("text", [])
            context.faces_detected = data.get("faces", 0)
            context.visual_confidence = camera_reading.confidence

        # Find health reading
        health_reading = self._readings.get(SignalSource.WATCH_HEALTH)
        if health_reading and not health_reading.is_stale:
            data = health_reading.data
            context.heart_rate = data.get("heart_rate")
            context.is_sleeping = data.get("is_sleeping")
            context.stress_level = data.get("stress_level")

        # Fuse activity from multiple sources
        activity_votes: dict[str, float] = defaultdict(float)

        for reading in readings:
            if reading.activity:
                weight = self._context_weights.get(reading.source, 0.1)
                activity_votes[reading.activity] += weight * reading.confidence

        if activity_votes:
            context.activity = max(activity_votes.keys(), key=lambda a: activity_votes[a])
            context.activity_confidence = min(1.0, activity_votes[context.activity])

        # Overall confidence
        confidence_sources = [
            context.visual_confidence,
            context.activity_confidence,
        ]
        if confidence_sources:
            context.overall_confidence = sum(confidence_sources) / len(confidence_sources)

        return context

    # =========================================================================
    # Queries
    # =========================================================================

    def get_reading(self, source: SignalSource) -> SignalReading | None:
        """Get latest reading from a specific source.

        Args:
            source: Signal source to query

        Returns:
            SignalReading or None if not available
        """
        reading = self._readings.get(source)
        if reading and not reading.is_stale:
            return reading
        return None

    def get_all_readings(self) -> list[SignalReading]:
        """Get all current readings."""
        return [r for r in self._readings.values() if not r.is_stale]

    @property
    def has_visual_context(self) -> bool:
        """Check if visual context is available."""
        reading = self._readings.get(SignalSource.META_CAMERA)
        return reading is not None and not reading.is_stale

    @property
    def has_location(self) -> bool:
        """Check if location data is available."""
        for source in [SignalSource.WIFI_AP, SignalSource.GPS_FINDMY]:
            reading = self._readings.get(source)
            if reading and not reading.is_stale:
                return True
        return False


# =============================================================================
# Factory
# =============================================================================

_fusion_bus: SensorFusionBus | None = None


def get_sensor_fusion() -> SensorFusionBus:
    """Get or create sensor fusion bus singleton."""
    global _fusion_bus
    if _fusion_bus is None:
        _fusion_bus = SensorFusionBus()
    return _fusion_bus


__all__ = [
    "FusedContext",
    "FusedLocation",
    "FusedState",
    "SensorFusionBus",
    "SignalReading",
    "SignalSource",
    "get_sensor_fusion",
]


"""
Mirror
h(x) >= 0. Always.

Fusion is synthesis.
Many signals, one understanding.
The whole greater than the parts.
"""
