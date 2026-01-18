"""Device Reconciler — Multi-device presence reconciliation.

Tracks multiple devices (phone, laptop, car) to understand:
- TRUE presence (not just where one device is)
- Travel mode (driving, carpooling, walking, transit)
- "Bring laptop" and other essential reminders
- Robust location that works even when carpooling

Real-world scenarios handled:
- Tim drives to work → phone + laptop + car all at work
- Tim carpools → phone + laptop away, car at home
- Tim forgets laptop → phone away, laptop at home → ALERT
- Tim is home → all devices at home or within geofence

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.integrations.apple_findmy import AppleFindMyIntegration
    from kagami_smarthome.integrations.maps import MapsService

logger = logging.getLogger(__name__)


# Home location — imported from central config for portability
from kagami.core.config.location_config import get_home_location

_location = get_home_location()
HOME_LAT = _location.latitude
HOME_LON = _location.longitude
HOME_RADIUS_MILES = _location.geofence_radius_m / 1609.34  # Convert meters to miles


class TravelMode(str, Enum):
    """How Tim is traveling."""

    HOME = "home"  # At home
    DRIVING = "driving"  # In own car (Tesla)
    CARPOOLING = "carpooling"  # With someone else (phone away, car home)
    WALKING = "walking"  # Short distance, no vehicle
    TRANSIT = "transit"  # Public transit (phone away, car home, long distance)
    UNKNOWN = "unknown"


class TrackedDeviceType(str, Enum):
    """Types of tracked personal devices.

    NOTE: Renamed from DeviceType (Dec 30, 2025) to avoid collision
    with discovery.DeviceType (smart home device types).
    """

    PHONE = "phone"  # Primary device (iPhone)
    LAPTOP = "laptop"  # MacBook
    CAR = "car"  # Tesla
    WATCH = "watch"  # Apple Watch
    TABLET = "tablet"  # iPad
    AIRPODS = "airpods"  # AirPods (usually with phone)


@dataclass
class TrackedDeviceState:
    """State of a tracked device."""

    device_type: TrackedDeviceType
    device_name: str

    # Location
    latitude: float | None = None
    longitude: float | None = None
    location_accuracy: float | None = None  # meters
    location_timestamp: float = 0.0

    # Distance from home
    distance_from_home_miles: float | None = None
    is_home: bool = True
    is_near_home: bool = True  # Within 2 miles

    # Battery
    battery_level: float = 1.0  # 0-1
    battery_status: str = "unknown"

    # Online status
    is_online: bool = False
    last_seen: float = 0.0

    # Movement
    is_moving: bool = False
    speed_mph: float | None = None
    heading: float | None = None

    def update_location(self, lat: float, lon: float, accuracy: float | None = None) -> None:
        """Update device location."""
        self.latitude = lat
        self.longitude = lon
        self.location_accuracy = accuracy
        self.location_timestamp = time.time()

        # Calculate distance from home
        self.distance_from_home_miles = self._haversine_miles(lat, lon, HOME_LAT, HOME_LON)
        self.is_home = self.distance_from_home_miles < HOME_RADIUS_MILES
        self.is_near_home = self.distance_from_home_miles < 2.0

    @staticmethod
    def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine distance in miles."""
        R = 3959
        lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        return R * c


@dataclass
class ReconciledPresence:
    """Reconciled presence from all devices."""

    # Overall state
    is_home: bool = True
    travel_mode: TravelMode = TravelMode.HOME

    # Primary location (from most reliable device)
    primary_lat: float | None = None
    primary_lon: float | None = None
    location_source: str = "unknown"

    # Distance from home (using primary device)
    distance_from_home_miles: float | None = None
    eta_minutes: int | None = None
    eta_text: str | None = None

    # Individual device states
    phone_state: TrackedDeviceState | None = None
    laptop_state: TrackedDeviceState | None = None
    car_state: TrackedDeviceState | None = None

    # Alerts
    missing_essentials: list[str] = field(default_factory=list)  # ["laptop", "airpods"]

    # Confidence
    confidence: float = 0.5
    reasoning: str = ""

    # Timestamps
    timestamp: float = field(default_factory=time.time)


# Callback type for alerts
AlertCallback = Callable[[str, str, dict[str, Any]], Awaitable[None]]


class DeviceReconciler:
    """Reconciles multiple device locations for accurate presence.

    Features:
    1. **Multi-device tracking**: Phone, laptop, car tracked independently
    2. **Travel mode detection**: Driving vs carpooling vs walking
    3. **Contextual alerts**: Uses ContextualAlertEngine for smart reminders
    4. **Robust presence**: Works even when carpooling (car at home)

    Note: Essential device alerts are now handled by ContextualAlertEngine,
    which considers trip context (work vs errands) before alerting.

    Usage:
        reconciler = DeviceReconciler()
        await reconciler.connect(findmy, controller)

        # Get reconciled presence
        presence = await reconciler.get_presence()
    """

    # Poll interval
    POLL_INTERVAL = 120  # 2 minutes

    # Device name patterns for identification
    DEVICE_PATTERNS = {
        TrackedDeviceType.PHONE: ["iphone", "tim's iphone", "tim's phone"],
        TrackedDeviceType.LAPTOP: ["macbook", "tim's macbook", "mac"],
        TrackedDeviceType.WATCH: ["watch", "apple watch"],
        TrackedDeviceType.TABLET: ["ipad"],
        TrackedDeviceType.AIRPODS: ["airpods"],
    }

    def __init__(self):
        self._findmy: AppleFindMyIntegration | None = None
        self._maps: MapsService | None = None
        self._smart_home: Any = None

        # Device states
        self._devices: dict[TrackedDeviceType, TrackedDeviceState] = {}

        # Last reconciled presence
        self._presence = ReconciledPresence()

        # Alert callbacks
        self._alert_callbacks: list[AlertCallback] = []

        # Polling
        self._running = False
        self._poll_task: asyncio.Task | None = None

        # Alert cooldowns (avoid spam)
        self._last_alerts: dict[str, float] = {}
        self._alert_cooldown = 300  # 5 minutes

        # Statistics
        self._stats = {
            "reconciliations": 0,
            "alerts_sent": 0,
            "carpool_detections": 0,
        }

    async def connect(
        self,
        findmy: AppleFindMyIntegration,
        smart_home: Any,
        maps: MapsService | None = None,
    ) -> bool:
        """Connect to device sources.

        Args:
            findmy: Apple Find My for phone/laptop/watch
            smart_home: SmartHomeController for Tesla
            maps: Optional MapsService for ETA

        Returns:
            True if connected
        """
        self._findmy = findmy
        self._smart_home = smart_home
        self._maps = maps

        # Initialize device states
        await self._discover_devices()

        logger.info(f"🔗 DeviceReconciler connected ({len(self._devices)} devices)")
        return True

    async def start_monitoring(self) -> None:
        """Start continuous monitoring."""
        if self._running:
            return

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("🔄 DeviceReconciler monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None

    def on_alert(self, callback: AlertCallback) -> None:
        """Subscribe to alerts.

        Callback signature: async callback(alert_type, message, data)
        """
        self._alert_callbacks.append(callback)

    async def _emit_alert(self, alert_type: str, message: str, data: dict[str, Any]) -> None:
        """Emit an alert to subscribers (with cooldown)."""
        now = time.time()

        # Check cooldown
        if alert_type in self._last_alerts:
            if now - self._last_alerts[alert_type] < self._alert_cooldown:
                return  # Skip, still in cooldown

        self._last_alerts[alert_type] = now
        self._stats["alerts_sent"] += 1

        for callback in self._alert_callbacks:
            try:
                await callback(alert_type, message, data)
            except Exception as e:
                logger.warning(f"Alert callback error: {e}")

    # =========================================================================
    # DEVICE DISCOVERY
    # =========================================================================

    async def _discover_devices(self) -> None:
        """Discover and classify devices from Find My."""
        if not self._findmy or not self._findmy.is_connected:
            return

        try:
            devices = await self._findmy.get_devices()

            for device in devices:
                device_type = self._classify_device(device.name, device.device_type)

                if device_type:
                    state = TrackedDeviceState(
                        device_type=device_type,
                        device_name=device.name,
                        battery_level=device.battery_level,
                        battery_status=device.battery_status,
                        is_online=device.is_online,
                        last_seen=time.time(),
                    )

                    if device.location:
                        state.update_location(
                            device.location["latitude"],
                            device.location["longitude"],
                            device.location.get("accuracy"),
                        )

                    self._devices[device_type] = state
                    logger.debug(f"Discovered device: {device.name} → {device_type.value}")

        except Exception as e:
            logger.error(f"Device discovery failed: {e}")

    def _classify_device(self, name: str, device_type: str) -> TrackedDeviceType | None:
        """Classify device by name/type."""
        name_lower = name.lower()
        type_lower = device_type.lower()

        for dt, patterns in self.DEVICE_PATTERNS.items():
            for pattern in patterns:
                if pattern in name_lower or pattern in type_lower:
                    return dt

        return None

    # =========================================================================
    # POLLING
    # =========================================================================

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self.reconcile()
                await asyncio.sleep(self.POLL_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"DeviceReconciler poll error: {e}")
                await asyncio.sleep(60)

    async def reconcile(self) -> ReconciledPresence:
        """Reconcile all device locations and determine presence.

        Returns:
            ReconciledPresence with full state
        """
        self._stats["reconciliations"] += 1

        # Update device locations
        await self._update_device_locations()

        # Get Tesla location
        await self._update_tesla_location()

        # Reconcile
        presence = self._reconcile_presence()

        # Check for alerts
        await self._check_alerts(presence)

        self._presence = presence
        return presence

    async def _update_device_locations(self) -> None:
        """Update all Find My device locations."""
        if not self._findmy or not self._findmy.is_connected:
            return

        try:
            devices = await self._findmy.get_devices()

            for device in devices:
                device_type = self._classify_device(device.name, device.device_type)

                if device_type and device_type in self._devices:
                    state = self._devices[device_type]
                    state.battery_level = device.battery_level
                    state.battery_status = device.battery_status
                    state.is_online = device.is_online
                    state.last_seen = time.time()

                    if device.location:
                        state.update_location(
                            device.location["latitude"],
                            device.location["longitude"],
                            device.location.get("accuracy"),
                        )

        except Exception as e:
            logger.error(f"Device location update failed: {e}")

    async def _update_tesla_location(self) -> None:
        """Update Tesla location from SmartHome."""
        if not self._smart_home:
            return

        try:
            devices = self._smart_home.get_devices()
            tesla = devices.get("tesla", {})

            if not tesla:
                return

            lat = tesla.get("latitude")
            lon = tesla.get("longitude")

            if lat and lon:
                if TrackedDeviceType.CAR not in self._devices:
                    self._devices[TrackedDeviceType.CAR] = TrackedDeviceState(
                        device_type=TrackedDeviceType.CAR,
                        device_name="Tesla Model Y",
                    )

                car = self._devices[TrackedDeviceType.CAR]
                car.update_location(lat, lon)
                car.battery_level = tesla.get("battery_level", 0) / 100.0
                car.is_online = True
                car.last_seen = time.time()
                car.is_moving = tesla.get("shift_state") in ["D", "R"]

        except Exception as e:
            logger.debug(f"Tesla update failed: {e}")

    # =========================================================================
    # RECONCILIATION LOGIC
    # =========================================================================

    def _reconcile_presence(self) -> ReconciledPresence:
        """Reconcile device locations into unified presence."""
        phone = self._devices.get(TrackedDeviceType.PHONE)
        laptop = self._devices.get(TrackedDeviceType.LAPTOP)
        car = self._devices.get(TrackedDeviceType.CAR)

        presence = ReconciledPresence(
            phone_state=phone,
            laptop_state=laptop,
            car_state=car,
            timestamp=time.time(),
        )

        # Determine if home
        # Tim is home if phone is home (primary indicator)

        # Phone is the primary presence indicator
        if phone:
            presence.is_home = phone.is_home
            presence.primary_lat = phone.latitude
            presence.primary_lon = phone.longitude
            presence.location_source = "phone"
            presence.distance_from_home_miles = phone.distance_from_home_miles
        elif laptop:
            presence.is_home = laptop.is_home
            presence.primary_lat = laptop.latitude
            presence.primary_lon = laptop.longitude
            presence.location_source = "laptop"
            presence.distance_from_home_miles = laptop.distance_from_home_miles
        elif car:
            presence.is_home = car.is_home
            presence.primary_lat = car.latitude
            presence.primary_lon = car.longitude
            presence.location_source = "car"
            presence.distance_from_home_miles = car.distance_from_home_miles

        # Determine travel mode
        if presence.is_home:
            presence.travel_mode = TravelMode.HOME
            presence.confidence = 0.95
            presence.reasoning = "Phone at home"

        else:
            # Away - determine how
            if car:
                if car.is_moving or (not car.is_home and phone and not phone.is_home):
                    # Car is moving or both car and phone are away
                    presence.travel_mode = TravelMode.DRIVING
                    presence.confidence = 0.9
                    presence.reasoning = "Phone and car both away, likely driving"

                elif car.is_home and phone and not phone.is_home:
                    # Car home, phone away = CARPOOLING
                    presence.travel_mode = TravelMode.CARPOOLING
                    presence.confidence = 0.85
                    presence.reasoning = "Phone away but car at home — carpooling"
                    self._stats["carpool_detections"] += 1

            else:
                # No car data, assume walking/transit based on distance
                if phone and phone.distance_from_home_miles:
                    if phone.distance_from_home_miles < 1.0:
                        presence.travel_mode = TravelMode.WALKING
                        presence.reasoning = "Close to home, no car data"
                    else:
                        presence.travel_mode = TravelMode.TRANSIT
                        presence.reasoning = "Far from home, no car data"
                    presence.confidence = 0.6

        # Track missing devices (for contextual alert engine to evaluate)
        # Note: We don't alert here - ContextualAlertEngine decides based on trip context
        if not presence.is_home:
            for device_type, state in self._devices.items():
                if state and state.is_home:
                    presence.missing_essentials.append(device_type.value)

        return presence

    # =========================================================================
    # ALERTS (Context-Aware)
    # =========================================================================

    async def _check_alerts(self, presence: ReconciledPresence) -> None:
        """Check for conditions requiring alerts.

        Note: Missing item alerts (laptop, etc.) are delegated to
        ContextualAlertEngine which considers trip purpose.
        Only context-independent alerts (carpool, battery) are handled here.
        """
        # Delegate contextual alerts (e.g., "bring laptop for work")
        # to the ContextualAlertEngine via the bridge
        if presence.missing_essentials and not presence.is_home:
            await self._evaluate_contextual_alerts(presence)

        # Alert: Carpooling detected (informational, not a warning)
        # This is context-independent - always useful to know travel mode
        if presence.travel_mode == TravelMode.CARPOOLING:
            old_mode = self._presence.travel_mode if self._presence else TravelMode.HOME
            if old_mode != TravelMode.CARPOOLING:
                await self._emit_alert(
                    "carpool_detected",
                    "Detected carpooling mode — tracking via phone.",
                    {
                        "car_location": "home",
                        "phone_distance": presence.distance_from_home_miles,
                    },
                )

        # Alert: Low battery when away (context-independent safety alert)
        for device_type, state in self._devices.items():
            if state.battery_level < 0.2 and not presence.is_home:
                await self._emit_alert(
                    f"low_battery_{device_type.value}",
                    f"{state.device_name} battery is low ({int(state.battery_level * 100)}%).",
                    {
                        "device": device_type.value,
                        "battery_percent": int(state.battery_level * 100),
                    },
                )

    async def _evaluate_contextual_alerts(self, presence: ReconciledPresence) -> None:
        """Evaluate alerts through the ContextualAlertEngine.

        This considers trip context (work vs errands) before alerting
        about missing items.
        """
        try:
            from kagami.core.integrations.contextual_alerts import (
                get_contextual_alert_engine,
            )

            engine = get_contextual_alert_engine()

            # Prepare item states (battery levels, etc.)
            item_states = {}
            for device_type, state in self._devices.items():
                item_states[f"{device_type.value}_battery"] = state.battery_level

            # Evaluate departure alerts
            await engine.evaluate_departure(
                missing_items=presence.missing_essentials,
                destination_lat=presence.primary_lat,
                destination_lon=presence.primary_lon,
                item_states=item_states,
            )

        except ImportError:
            # ContextualAlertEngine not available, skip contextual alerts
            logger.debug("ContextualAlertEngine not available")
        except Exception as e:
            logger.debug(f"Contextual alert evaluation failed: {e}")

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def get_presence(self) -> ReconciledPresence:
        """Get current reconciled presence."""
        return self._presence

    def get_device_state(self, device_type: TrackedDeviceType) -> TrackedDeviceState | None:
        """Get state of a specific device."""
        return self._devices.get(device_type)

    def get_all_device_states(self) -> dict[TrackedDeviceType, TrackedDeviceState]:
        """Get all device states."""
        return self._devices.copy()

    def is_carpooling(self) -> bool:
        """Check if currently carpooling."""
        return self._presence.travel_mode == TravelMode.CARPOOLING

    def get_primary_location(self) -> tuple[float, float] | None:
        """Get primary (most accurate) location.

        Returns:
            (latitude, longitude) or None
        """
        if self._presence.primary_lat and self._presence.primary_lon:
            return (self._presence.primary_lat, self._presence.primary_lon)
        return None

    def get_stats(self) -> dict[str, Any]:
        """Get reconciler statistics."""
        return {
            **self._stats,
            "devices_tracked": len(self._devices),
            "travel_mode": self._presence.travel_mode.value,
            "is_home": self._presence.is_home,
            "missing_essentials": self._presence.missing_essentials,
        }


# Singleton
_reconciler: DeviceReconciler | None = None


def get_device_reconciler() -> DeviceReconciler:
    """Get global DeviceReconciler instance."""
    global _reconciler
    if _reconciler is None:
        _reconciler = DeviceReconciler()
    return _reconciler


__all__ = [
    "AlertCallback",
    "DeviceReconciler",
    "ReconciledPresence",
    "TrackedDeviceState",
    "TrackedDeviceType",  # Renamed from DeviceType (Dec 30, 2025)
    "TravelMode",
    "get_device_reconciler",
]
