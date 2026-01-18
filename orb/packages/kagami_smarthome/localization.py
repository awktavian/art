"""Device Localization — Room-Level Device Tracking.

Combines multiple data sources for precise room-level localization:
- UniFi WiFi: AP association + RSSI triangulation
- Apple Find My: GPS location (geofencing) + device proximity
- Control4 motion: Presence validation

Architecture:
- Each WiFi access point is mapped to a room/zone
- Device AP association determines primary room
- RSSI from multiple APs can triangulate position
- Apple Find My provides geofence (home/away) and device finder
- Motion sensors validate/refine predictions

Room Mapping Philosophy:
- AP placement defines coverage zones
- Overlapping coverage enables triangulation
- Mobile devices track user movement
- Static devices anchor room identity

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from kagami_smarthome.types import GeofenceState

if TYPE_CHECKING:
    from kagami_smarthome.integrations.apple_findmy import AppleFindMyIntegration
    from kagami_smarthome.integrations.unifi import UniFiIntegration

logger = logging.getLogger(__name__)


class LocationConfidence(Enum):
    """Confidence level of device location."""

    UNKNOWN = "unknown"  # No data
    LOW = "low"  # Single weak signal
    MEDIUM = "medium"  # AP association only
    HIGH = "high"  # AP + motion correlation
    VERIFIED = "verified"  # Multiple sources agree


@dataclass
class AccessPointMapping:
    """Maps a WiFi access point to physical location."""

    mac: str  # AP MAC address
    name: str  # AP name (e.g., "U7 Pro Office")
    room: str  # Primary room coverage
    floor: str = "Main"  # Floor level
    adjacent_rooms: list[str] = field(default_factory=list)  # Nearby rooms
    position: tuple[float, float, float] | None = None  # x, y, z coordinates in meters
    coverage_radius: float = 10.0  # Approximate coverage in meters


@dataclass
class DeviceLocation:
    """Location data for a tracked device."""

    mac: str  # Device MAC address
    device_name: str  # Friendly name
    device_type: str  # phone, laptop, tablet, etc.

    # Room-level location (from UniFi AP)
    current_room: str | None = None
    previous_room: str | None = None
    room_confidence: LocationConfidence = LocationConfidence.UNKNOWN

    # AP-based data
    connected_ap_mac: str | None = None
    connected_ap_name: str | None = None
    rssi: int | None = None  # Signal strength (dBm)

    # Geofence (from Apple Find My or GPS)
    geofence_state: GeofenceState = GeofenceState.UNKNOWN
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    gps_accuracy: float | None = None  # Meters

    # Timing
    last_seen: float = 0.0
    room_entry_time: float = 0.0
    time_in_room: float = 0.0  # Seconds in current room

    # Metadata
    is_online: bool = False
    is_owner_device: bool = False  # Is this Tim's device?
    battery_level: float | None = None

    def time_since_seen(self) -> float:
        """Seconds since device was last seen."""
        return time.time() - self.last_seen if self.last_seen else float("inf")

    def is_stale(self, threshold: float = 300.0) -> bool:
        """Check if location data is stale (default 5 minutes)."""
        return self.time_since_seen() > threshold


@dataclass
class RoomOccupants:
    """Devices currently in a room."""

    room: str
    devices: list[DeviceLocation] = field(default_factory=list)
    owner_present: bool = False  # Is Tim's device in this room?
    last_motion: float = 0.0  # Last motion sensor trigger

    @property
    def device_count(self) -> int:
        return len(self.devices)

    @property
    def is_occupied(self) -> bool:
        """Room is occupied if owner device present or recent motion."""
        if self.owner_present:
            return True
        # Recent motion (within 5 minutes) also counts
        return (time.time() - self.last_motion) < 300 if self.last_motion else False


class DeviceLocalizer:
    """Room-level device localization using UniFi and Apple Find My.

    Tracks all WiFi devices and provides:
    - Real-time room-level location
    - Geofence state (home/away)
    - Movement history
    - Owner presence inference

    Usage:
        localizer = DeviceLocalizer(unifi_integration, apple_findmy)
        localizer.configure_access_points(ap_mappings)
        localizer.set_owner_devices(owner_macs)

        await localizer.start()

        # Get current locations
        locations = localizer.get_all_device_locations()
        room_occupants = localizer.get_room_occupants("Living Room")
        owner_location = localizer.get_owner_location()
    """

    # Home location — imported from central config for portability
    # To change, set KAGAMI_HOME_LAT/LON env vars or config/location.yaml
    @property
    def HOME_LATITUDE(self) -> float:
        from kagami.core.config.location_config import get_home_location

        return get_home_location().latitude

    @property
    def HOME_LONGITUDE(self) -> float:
        from kagami.core.config.location_config import get_home_location

        return get_home_location().longitude

    @property
    def HOME_GEOFENCE_RADIUS(self) -> float:
        from kagami.core.config.location_config import get_home_location

        return get_home_location().geofence_radius_m

    NEAR_GEOFENCE_RADIUS = 500.0  # meters

    def __init__(
        self,
        unifi: UniFiIntegration | None = None,
        apple_findmy: AppleFindMyIntegration | None = None,
    ):
        self._unifi = unifi
        self._apple_findmy = apple_findmy

        # AP to room mapping
        self._ap_mappings: dict[str, AccessPointMapping] = {}

        # Device tracking
        self._device_locations: dict[str, DeviceLocation] = {}  # MAC -> Location
        self._owner_device_macs: set[str] = set()

        # Room occupancy
        self._room_occupants: dict[str, RoomOccupants] = {}

        # Callbacks for location changes
        self._location_callbacks: list[Any] = []
        self._room_change_callbacks: list[Any] = []

        # State
        self._running = False
        self._poll_task: asyncio.Task | None = None
        self._findmy_task: asyncio.Task | None = None

        # Polling intervals
        self._wifi_poll_interval = 5.0  # Poll UniFi every 5 seconds
        self._findmy_poll_interval = 60.0  # Poll Find My every minute

        # Initialize default AP mappings for 7331 W Green Lake Dr N
        self._setup_default_ap_mappings()

    def _setup_default_ap_mappings(self) -> None:
        """Setup default AP mappings for the house.

        7331 W Green Lake Dr N has UniFi APs placed in key locations.
        This mapping associates each AP with its primary room.
        """
        # Default mappings - these get updated with actual MAC addresses
        # when UniFi connects and discovers APs
        default_mappings = [
            # Second Floor
            AccessPointMapping(
                mac="",  # Discovered dynamically
                name="U7 Pro Primary",
                room="Primary Bedroom",
                floor="Upper",
                adjacent_rooms=["Primary Bath", "Primary Closet", "Loft"],
                coverage_radius=12.0,
            ),
            AccessPointMapping(
                mac="",
                name="U7 Pro Office",
                room="Office",
                floor="Upper",
                adjacent_rooms=["Office Bath", "Bed 3", "Laundry"],
                coverage_radius=10.0,
            ),
            # First Floor
            AccessPointMapping(
                mac="",
                name="U7 Pro Living",
                room="Living Room",
                floor="Main",
                adjacent_rooms=["Kitchen", "Dining Room", "Entry"],
                coverage_radius=15.0,
            ),
            AccessPointMapping(
                mac="",
                name="U7 Pro Kitchen",
                room="Kitchen",
                floor="Main",
                adjacent_rooms=["Living Room", "Dining Room", "Mudroom", "Garage"],
                coverage_radius=12.0,
            ),
            # Basement
            AccessPointMapping(
                mac="",
                name="U7 Pro Game",
                room="Game Room",
                floor="Lower",
                adjacent_rooms=["Bed 4", "Bath 4", "Gym"],
                coverage_radius=12.0,
            ),
        ]

        # Store by name initially (MAC discovered later)
        for mapping in default_mappings:
            # Use name as key until MAC is discovered
            self._ap_mappings[mapping.name.lower()] = mapping

    def configure_access_point(
        self,
        mac: str,
        name: str,
        room: str,
        floor: str = "Main",
        adjacent_rooms: list[str] | None = None,
    ) -> None:
        """Configure an access point to room mapping.

        Args:
            mac: AP MAC address
            name: AP friendly name
            room: Primary room the AP covers
            floor: Floor level
            adjacent_rooms: Nearby rooms within coverage
        """
        mac_lower = mac.lower()
        mapping = AccessPointMapping(
            mac=mac_lower,
            name=name,
            room=room,
            floor=floor,
            adjacent_rooms=adjacent_rooms or [],
        )
        self._ap_mappings[mac_lower] = mapping

        # Also store by name for discovery matching
        name_key = name.lower()
        self._ap_mappings[name_key] = mapping

        logger.debug(f"Localization: Mapped AP {mac} ({name}) → {room}")

    def set_owner_devices(self, macs: list[str]) -> None:
        """Set MAC addresses of owner's devices for presence tracking.

        Args:
            macs: List of MAC addresses belonging to the owner
        """
        self._owner_device_macs = {m.lower() for m in macs}
        logger.info(f"Localization: Tracking {len(self._owner_device_macs)} owner devices")

    async def start(self) -> bool:
        """Start device localization tracking.

        Returns:
            True if started successfully
        """
        if self._running:
            return True

        # Discover APs and update mappings
        await self._discover_access_points()

        # Start polling
        self._running = True
        self._poll_task = asyncio.create_task(self._wifi_poll_loop())

        if self._apple_findmy and self._apple_findmy.is_connected:
            self._findmy_task = asyncio.create_task(self._findmy_poll_loop())

        logger.info("📍 Device localization started")
        return True

    async def stop(self) -> None:
        """Stop device localization."""
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        if self._findmy_task:
            self._findmy_task.cancel()
            try:
                await self._findmy_task
            except asyncio.CancelledError:
                pass
            self._findmy_task = None

        logger.info("Device localization stopped")

    async def _discover_access_points(self) -> None:
        """Discover UniFi access points and update mappings."""
        if not self._unifi or not self._unifi.is_connected:
            return

        # Get AP list from UniFi
        try:
            # Access points are available through the protect/network API
            # For now, we'll rely on client data to discover APs
            clients = self._unifi.get_clients()

            discovered_aps = set()
            for client_data in clients.values():
                ap_mac = client_data.get("ap_mac", "").lower()
                if ap_mac:
                    discovered_aps.add(ap_mac)

            logger.info(f"Localization: Discovered {len(discovered_aps)} access points")

            # Try to match discovered APs to our mappings by name or position
            # This requires the admin to configure AP names to match room names

        except Exception as e:
            logger.warning(f"Localization: AP discovery failed: {e}")

    async def _wifi_poll_loop(self) -> None:
        """Poll UniFi for device locations."""
        while self._running:
            try:
                await self._update_wifi_locations()
                await asyncio.sleep(self._wifi_poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Localization: WiFi poll error: {e}")
                await asyncio.sleep(10)

    async def _findmy_poll_loop(self) -> None:
        """Poll Apple Find My for device locations."""
        while self._running:
            try:
                await self._update_findmy_locations()
                await asyncio.sleep(self._findmy_poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Localization: Find My poll error: {e}")
                await asyncio.sleep(60)

    async def _update_wifi_locations(self) -> None:
        """Update device locations from UniFi WiFi data."""
        if not self._unifi or not self._unifi.is_connected:
            return

        now = time.time()
        clients = self._unifi.get_clients()

        for mac, client_data in clients.items():
            mac_lower = mac.lower()

            # Get or create device location
            if mac_lower not in self._device_locations:
                self._device_locations[mac_lower] = DeviceLocation(
                    mac=mac_lower,
                    device_name=client_data.get("hostname", "Unknown"),
                    device_type=self._infer_device_type(client_data),
                    is_owner_device=mac_lower in self._owner_device_macs,
                )

            location = self._device_locations[mac_lower]
            previous_room = location.current_room

            # Update basic info
            location.device_name = client_data.get("hostname") or location.device_name
            location.is_online = True
            location.last_seen = now

            # Get AP association
            ap_mac = client_data.get("ap_mac", "").lower()
            if ap_mac:
                location.connected_ap_mac = ap_mac

                # Map AP to room
                ap_mapping = self._ap_mappings.get(ap_mac)
                if ap_mapping:
                    location.current_room = ap_mapping.room
                    location.connected_ap_name = ap_mapping.name
                    location.room_confidence = LocationConfidence.MEDIUM
                else:
                    # Unknown AP - try to infer from name
                    location.room_confidence = LocationConfidence.LOW

            # Detect room change
            if location.current_room and location.current_room != previous_room:
                location.previous_room = previous_room
                location.room_entry_time = now
                location.time_in_room = 0

                # Notify room change
                await self._on_room_change(location, previous_room)
            elif location.room_entry_time:
                location.time_in_room = now - location.room_entry_time

        # Mark stale devices
        for location in self._device_locations.values():
            if location.time_since_seen() > 300:  # 5 minutes
                location.is_online = False

        # Update room occupants
        self._update_room_occupants()

    async def _update_findmy_locations(self) -> None:
        """Update device locations from Apple Find My."""
        if not self._apple_findmy or not self._apple_findmy.is_connected:
            return

        try:
            devices = await self._apple_findmy.get_devices()

            for device in devices:
                # Find matching WiFi device by name pattern
                device_name_lower = device.name.lower()

                matched_mac = None
                for mac, location in self._device_locations.items():
                    if location.device_name.lower() in device_name_lower:
                        matched_mac = mac
                        break
                    if device_name_lower in location.device_name.lower():
                        matched_mac = mac
                        break

                if matched_mac and device.location:
                    location = self._device_locations[matched_mac]

                    # Update GPS location
                    location.gps_latitude = device.location.get("latitude")
                    location.gps_longitude = device.location.get("longitude")
                    location.gps_accuracy = device.location.get("accuracy")
                    location.battery_level = device.battery_level

                    # Calculate geofence state
                    location.geofence_state = self._calculate_geofence_state(
                        location.gps_latitude,
                        location.gps_longitude,
                    )

                    # High confidence if GPS confirms WiFi location
                    if location.current_room and location.geofence_state == GeofenceState.HOME:
                        location.room_confidence = LocationConfidence.HIGH

        except Exception as e:
            logger.warning(f"Localization: Find My update failed: {e}")

    def _calculate_geofence_state(
        self,
        lat: float | None,
        lon: float | None,
    ) -> GeofenceState:
        """Calculate geofence state from GPS coordinates."""
        if lat is None or lon is None:
            return GeofenceState.UNKNOWN

        # Haversine distance (simplified for short distances)
        import math

        R = 6371000  # Earth radius in meters
        lat1 = math.radians(self.HOME_LATITUDE)
        lat2 = math.radians(lat)
        dlat = math.radians(lat - self.HOME_LATITUDE)
        dlon = math.radians(lon - self.HOME_LONGITUDE)

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        if distance <= self.HOME_GEOFENCE_RADIUS:
            return GeofenceState.HOME
        elif distance <= self.NEAR_GEOFENCE_RADIUS:
            return GeofenceState.NEAR
        else:
            return GeofenceState.AWAY

    def _infer_device_type(self, client_data: dict[str, Any]) -> str:
        """Infer device type from UniFi client data."""
        hostname = (client_data.get("hostname") or "").lower()
        oui = (client_data.get("oui") or "").lower()

        if "iphone" in hostname:
            return "phone"
        elif "ipad" in hostname:
            return "tablet"
        elif "macbook" in hostname or "mac-studio" in hostname:
            return "laptop"
        elif "imac" in hostname:
            return "desktop"
        elif "apple" in oui or "apple" in hostname:
            return "apple_device"
        elif "watch" in hostname:
            return "watch"
        else:
            return "unknown"

    def _update_room_occupants(self) -> None:
        """Update room occupancy based on device locations."""
        # Clear existing
        self._room_occupants.clear()

        # Group devices by room
        for location in self._device_locations.values():
            if not location.current_room or not location.is_online:
                continue

            room = location.current_room
            if room not in self._room_occupants:
                self._room_occupants[room] = RoomOccupants(room=room)

            occupants = self._room_occupants[room]
            occupants.devices.append(location)

            if location.is_owner_device:
                occupants.owner_present = True

    async def _on_room_change(
        self,
        location: DeviceLocation,
        previous_room: str | None,
    ) -> None:
        """Handle device room change event."""
        logger.info(
            f"📍 {location.device_name} moved: "
            f"{previous_room or 'Unknown'} → {location.current_room}"
        )

        # Notify callbacks
        for callback in self._room_change_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(location, previous_room)
                else:
                    callback(location, previous_room)
            except Exception as e:
                logger.error(f"Localization: Room change callback error: {e}")

    # =========================================================================
    # Public API
    # =========================================================================

    def get_device_location(self, mac: str) -> DeviceLocation | None:
        """Get location for a specific device.

        Args:
            mac: Device MAC address

        Returns:
            DeviceLocation or None if not tracked
        """
        return self._device_locations.get(mac.lower())

    def get_all_device_locations(self) -> dict[str, DeviceLocation]:
        """Get all tracked device locations."""
        return self._device_locations.copy()

    def get_owner_location(self) -> DeviceLocation | None:
        """Get location of primary owner device (first online).

        Returns:
            DeviceLocation of owner's primary device
        """
        for mac in self._owner_device_macs:
            location = self._device_locations.get(mac)
            if location and location.is_online:
                return location
        return None

    def get_owner_room(self) -> str | None:
        """Get the room where the owner is currently located.

        Returns:
            Room name or None if owner not detected
        """
        location = self.get_owner_location()
        return location.current_room if location else None

    def get_owner_geofence_state(self) -> GeofenceState:
        """Get owner's geofence state (home/away/near).

        Returns:
            GeofenceState of owner's primary device
        """
        location = self.get_owner_location()
        if location:
            return location.geofence_state
        return GeofenceState.UNKNOWN

    def get_room_occupants(self, room: str) -> RoomOccupants | None:
        """Get devices currently in a room.

        Args:
            room: Room name

        Returns:
            RoomOccupants or None if no devices
        """
        return self._room_occupants.get(room)

    def is_room_occupied(self, room: str) -> bool:
        """Check if a room has any devices (owner or other).

        Args:
            room: Room name

        Returns:
            True if any device is in the room
        """
        occupants = self._room_occupants.get(room)
        return occupants.device_count > 0 if occupants else False

    def is_owner_in_room(self, room: str) -> bool:
        """Check if owner is in a specific room.

        Args:
            room: Room name

        Returns:
            True if owner's device is in the room
        """
        occupants = self._room_occupants.get(room)
        return occupants.owner_present if occupants else False

    def get_all_occupied_rooms(self) -> list[str]:
        """Get list of all rooms with devices."""
        return [
            room for room, occupants in self._room_occupants.items() if occupants.device_count > 0
        ]

    def get_owner_occupied_rooms(self) -> list[str]:
        """Get rooms where owner is present."""
        return [room for room, occupants in self._room_occupants.items() if occupants.owner_present]

    def is_owner_home(self) -> bool:
        """Check if owner is home based on WiFi and/or geofence.

        Returns:
            True if any owner device is online and at home
        """
        for mac in self._owner_device_macs:
            location = self._device_locations.get(mac)
            if location and location.is_online:
                # WiFi connected = home
                return True
            if location and location.geofence_state == GeofenceState.HOME:
                # GPS says home
                return True
        return False

    def is_owner_away(self) -> bool:
        """Check if owner is definitely away.

        Returns:
            True if no owner devices online and geofence says away
        """
        any_online = False
        all_away = True

        for mac in self._owner_device_macs:
            location = self._device_locations.get(mac)
            if location:
                if location.is_online:
                    any_online = True
                if location.geofence_state not in (GeofenceState.AWAY, GeofenceState.UNKNOWN):
                    all_away = False

        # Away if no devices online AND all geofences say away
        return not any_online and all_away

    def get_owner_movement_history(self, hours: float = 24.0) -> list[tuple[str, float]]:
        """Get owner's room movement history.

        Args:
            hours: How far back to look

        Returns:
            List of (room, timestamp) tuples
        """
        # This would require storing history - for now return empty
        # Future: implement with a deque of room changes
        return []

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_room_change(self, callback: Any) -> None:
        """Register callback for room change events.

        Callback receives: (location: DeviceLocation, previous_room: str | None)
        """
        self._room_change_callbacks.append(callback)

    def on_location_update(self, callback: Any) -> None:
        """Register callback for any location update."""
        self._location_callbacks.append(callback)

    # =========================================================================
    # Motion Sensor Integration
    # =========================================================================

    def report_motion(self, room: str, timestamp: float | None = None) -> None:
        """Report motion detected in a room (from DSC/Control4 sensors).

        This helps validate/refine device-based localization.

        Args:
            room: Room where motion was detected
            timestamp: When motion occurred (default now)
        """
        ts = timestamp or time.time()

        if room not in self._room_occupants:
            self._room_occupants[room] = RoomOccupants(room=room)

        self._room_occupants[room].last_motion = ts

        # If owner device is in an adjacent room, consider them in motion room
        owner_location = self.get_owner_location()
        if owner_location and owner_location.current_room:
            owner_ap = self._ap_mappings.get(
                owner_location.connected_ap_mac or "",
            )
            if owner_ap and room in owner_ap.adjacent_rooms:
                # Motion in adjacent room - likely owner transitioning
                owner_location.room_confidence = LocationConfidence.HIGH

    # =========================================================================
    # Diagnostics
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get localization system status."""
        return {
            "running": self._running,
            "ap_mappings": len(self._ap_mappings),
            "tracked_devices": len(self._device_locations),
            "online_devices": sum(1 for d in self._device_locations.values() if d.is_online),
            "owner_devices": len(self._owner_device_macs),
            "owner_home": self.is_owner_home(),
            "owner_room": self.get_owner_room(),
            "occupied_rooms": self.get_all_occupied_rooms(),
            "unifi_connected": self._unifi.is_connected if self._unifi else False,
            "findmy_connected": self._apple_findmy.is_connected if self._apple_findmy else False,
        }
