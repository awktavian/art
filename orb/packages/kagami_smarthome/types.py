"""Smart Home Data Types.

These types define the core data structures for smart home integration.
They have no external dependencies and can be imported without vendor libs.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PresenceState(Enum):
    """Where you are relative to home."""

    AWAY = "away"  # Not home (WiFi disconnected, security armed)
    ARRIVING = "arriving"  # Approaching (doorbell, driveway motion)
    HOME = "home"  # Home, location unknown
    ACTIVE = "active"  # Home, recently detected in specific area
    SLEEPING = "sleeping"  # Home, nighttime, no motion


class SecurityState(Enum):
    """DSC security panel state."""

    DISARMED = "disarmed"
    ARMED_STAY = "armed_stay"  # Home, perimeter armed
    ARMED_AWAY = "armed_away"  # Away, full armed
    ARMED_NIGHT = "armed_night"  # Sleep mode
    ALARM = "alarm"  # Active alarm!
    TROUBLE = "trouble"  # System trouble


class ActivityContext(Enum):
    """Inferred activity context."""

    UNKNOWN = "unknown"
    WAKING = "waking"  # Morning routine
    WORKING = "working"  # In office/focused
    COOKING = "cooking"  # Kitchen activity
    RELAXING = "relaxing"  # Living areas, evening
    ENTERTAINING = "entertaining"  # Multiple presence signals
    SLEEPING = "sleeping"  # Night, minimal motion


@dataclass
class PresenceEvent:
    """A presence-related event from any sensor."""

    source: str  # "unifi_camera", "unifi_wifi", "dsc_zone", "control4_motion"
    event_type: str  # "motion", "person", "connect", "disconnect", "zone_open"
    location: str | None  # Room/zone name if known
    confidence: float  # 0-1
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DSCZoneState:
    """DSC zone state from Envisalink — comprehensive sensor data.

    Zone Types (from DSC programming):
    - door_window: Entry/exit sensors (magnetic contacts)
    - motion: PIR motion detectors
    - glass_break: Glass break sensors
    - smoke: Smoke detectors (2-wire or wireless)
    - co: Carbon monoxide detectors
    - heat: Heat detectors
    - water: Water/flood sensors
    - freeze: Freeze sensors

    Zone States:
    - closed: Normal/secure state
    - open: Zone faulted (door open, motion detected)
    - alarm: Zone in alarm condition
    - tamper: Tamper detected (cover removed)
    - fault: Zone supervision fault
    - bypassed: Bypassed by user
    """

    zone_num: int
    name: str = ""
    zone_type: str = "unknown"
    state: str = "closed"
    battery_low: bool = False
    last_activity: float = 0.0
    activity_count: int = 0

    # Room mapping (inferred or configured)
    room: str | None = None

    # For motion zones - tracks recent activity for presence
    last_motion_start: float = 0.0
    motion_duration: float = 0.0  # How long motion was detected

    @property
    def is_open(self) -> bool:
        """Check if zone is currently open/faulted."""
        return self.state in ("open", "alarm")

    @property
    def is_motion_zone(self) -> bool:
        """Check if this is a motion detector."""
        return self.zone_type == "motion"

    @property
    def is_entry_zone(self) -> bool:
        """Check if this is a door/window zone."""
        return self.zone_type == "door_window"

    @property
    def is_safety_zone(self) -> bool:
        """Check if this is a life safety zone (smoke/CO)."""
        return self.zone_type in ("smoke", "co", "heat")

    @property
    def time_since_activity(self) -> float:
        """Seconds since last activity."""
        if self.last_activity > 0:
            return time.time() - self.last_activity
        return float("inf")


@dataclass
class DSCTroubleState:
    """DSC system trouble conditions."""

    ac_failure: bool = False
    battery_low: bool = False
    bell_trouble: bool = False
    phone_line_trouble: bool = False
    fire_trouble: bool = False
    system_tamper: bool = False
    low_battery_zones: list[int] = field(default_factory=list)


@dataclass
class DSCTemperature:
    """Temperature readings from DSC EMS-100 module."""

    interior: float | None = None  # Fahrenheit
    exterior: float | None = None  # Fahrenheit
    timestamp: float = 0.0


class GeofenceState(Enum):
    """Device geofence state relative to home."""

    UNKNOWN = "unknown"
    HOME = "home"  # Within home geofence
    NEAR = "near"  # Within 500m of home
    AWAY = "away"  # Outside geofence
    ARRIVING = "arriving"  # Moving toward home
    LEAVING = "leaving"  # Moving away from home


@dataclass
class TrackedDevice:
    """A tracked device for presence/localization."""

    mac: str
    name: str = ""
    device_type: str = "unknown"  # phone, laptop, tablet, watch
    current_room: str | None = None
    previous_room: str | None = None
    geofence_state: GeofenceState = GeofenceState.UNKNOWN
    is_online: bool = False
    last_seen: float = 0.0
    battery_level: float | None = None
    is_owner: bool = False  # Is this Tim's device?


@dataclass
class HomeState:
    """Unified home state — single source of truth.

    Consolidates all presence, security, and sensor data into one structure.
    DSC zones are the primary sensor source for room-level presence.
    Device localization provides device-level tracking.

    State Hierarchy:
    1. DSC partition state → security state
    2. DSC zone events → room occupancy + presence
    3. Device localization → owner location + geofence
    4. Activity inference → what you're doing
    """

    # === Core State ===
    presence: PresenceState = PresenceState.AWAY
    security: SecurityState = SecurityState.DISARMED
    activity: ActivityContext = ActivityContext.UNKNOWN

    # === Location Tracking ===
    # Owner's current room (from device localization OR DSC motion)
    owner_room: str | None = None
    # Last known location (fallback)
    last_location: str | None = None
    last_motion_time: float = 0.0
    # Rooms with recent activity (motion or device presence)
    occupied_rooms: list[str] = field(default_factory=list)

    # === DSC Security System (Primary Sensor Source) ===
    # All zones with full state tracking
    dsc_zones: dict[int, DSCZoneState] = field(default_factory=dict)
    # Zone-to-room mapping: zone_num -> room_name
    zone_room_map: dict[int, str] = field(default_factory=dict)
    # System trouble conditions
    dsc_trouble: DSCTroubleState = field(default_factory=DSCTroubleState)
    # Temperature from EMS-100 module
    dsc_temperature: DSCTemperature = field(default_factory=DSCTemperature)
    # Partition state (entry/exit delays)
    entry_delay_active: bool = False
    exit_delay_active: bool = False

    # === Device Localization (WiFi AP + Apple Find My) ===
    # All tracked devices with locations
    tracked_devices: dict[str, TrackedDevice] = field(default_factory=dict)
    # WiFi devices currently connected (MAC addresses)
    wifi_devices_home: list[str] = field(default_factory=list)
    # Owner's geofence state
    owner_geofence: GeofenceState = GeofenceState.UNKNOWN

    # === Arrival Tracking ===
    just_arrived: bool = False  # True when owner just arrived home
    just_arrived_time: float = 0.0  # Timestamp of arrival

    # === Timestamp ===
    updated: float = field(default_factory=time.time)

    # === Computed Properties ===

    @property
    def open_zones(self) -> list[str]:
        """Get names of all currently open zones (computed from dsc_zones)."""
        return [z.name for z in self.dsc_zones.values() if z.is_open]

    @property
    def motion_zones(self) -> list[DSCZoneState]:
        """Get all motion detector zones."""
        return [z for z in self.dsc_zones.values() if z.is_motion_zone]

    @property
    def entry_zones(self) -> list[DSCZoneState]:
        """Get all door/window zones."""
        return [z for z in self.dsc_zones.values() if z.is_entry_zone]

    @property
    def safety_zones(self) -> list[DSCZoneState]:
        """Get all life safety zones (smoke/CO)."""
        return [z for z in self.dsc_zones.values() if z.is_safety_zone]

    @property
    def has_trouble(self) -> bool:
        """Check if any system trouble condition exists."""
        t = self.dsc_trouble
        return any(
            [
                t.ac_failure,
                t.battery_low,
                t.bell_trouble,
                t.phone_line_trouble,
                t.fire_trouble,
                t.system_tamper,
                len(t.low_battery_zones) > 0,
            ]
        )

    def get_recent_motion_rooms(self, seconds: float = 300) -> list[str]:
        """Get rooms with motion in the last N seconds."""
        rooms = set()
        for zone in self.dsc_zones.values():
            if zone.is_motion_zone and zone.time_since_activity < seconds:
                if zone.room:
                    rooms.add(zone.room)
        return list(rooms)

    def get_zone_for_room(self, room: str) -> list[DSCZoneState]:
        """Get all zones in a specific room."""
        room_lower = room.lower()
        return [z for z in self.dsc_zones.values() if z.room and z.room.lower() == room_lower]

    def is_room_occupied(self, room: str, motion_timeout: float = 300) -> bool:
        """Check if a room is occupied based on sensors + devices.

        Args:
            room: Room name
            motion_timeout: Seconds to consider motion recent (default 5 min)

        Returns:
            True if room has recent motion OR owner device present
        """
        # Check owner device location
        if self.owner_room and self.owner_room.lower() == room.lower():
            return True

        # Check for any tracked device in room
        for device in self.tracked_devices.values():
            if device.current_room and device.current_room.lower() == room.lower():
                if device.is_online:
                    return True

        # Check for recent motion from DSC
        for zone in self.dsc_zones.values():
            if zone.room and zone.room.lower() == room.lower():
                if zone.is_motion_zone and zone.time_since_activity < motion_timeout:
                    return True

        return False


@dataclass
class DeviceIdentifier:
    """Identifies a device for auto-discovery.

    Devices can be identified by:
    - MAC address (most reliable)
    - Hostname pattern (regex)
    - Static IP (fallback, not recommended)
    """

    mac: str | None = None  # "00:0f:ff:9f:26:f4"
    hostname_pattern: str | None = None  # "control4.*core5"
    static_ip: str | None = None  # Fallback only


@dataclass
class SmartHomeConfig:
    """Configuration for unified smart home.

    Architecture: UniFi is the source of truth for device discovery.
    IPs are resolved dynamically via UniFi Network API.

    For each integration, you can specify:
    - A MAC address (recommended, most stable)
    - A hostname pattern (good for dynamic DHCP)
    - A static IP (fallback, not recommended)

    If auto_discover=True, the system uses UniFi to find devices.
    """

    # ==========================================================================
    # UniFi (Required for auto-discovery)
    # ==========================================================================
    unifi_host: str | None = None  # UDM Pro IP or "unifi.ui.com" for cloud
    unifi_port: int = 443
    unifi_username: str | None = None  # UI.com email
    unifi_password: str | None = None  # UI.com password
    # SECURITY: SSL verification enabled by default to prevent MITM attacks.
    # For local controllers with self-signed certs, either:
    # 1. Install the controller's CA cert on your system (recommended)
    # 2. Set UNIFI_VERIFY_SSL=0 environment variable (development only)
    # 3. Set unifi_verify_ssl=False explicitly (document the risk)
    unifi_verify_ssl: bool = True

    # Auto-discovery settings
    auto_discover: bool = True  # Use UniFi to discover device IPs
    discovery_cache_ttl: int = 300  # Seconds to cache discovered IPs

    # ==========================================================================
    # Control4 (Director API)
    # ==========================================================================
    # Device identification (prefer MAC/hostname for UniFi discovery)
    control4_mac: str | None = None  # MAC of Director (e.g., "00:0f:ff:9f:26:f4")
    control4_hostname: str | None = None  # Hostname pattern (e.g., "core5")
    control4_host: str | None = None  # Static IP fallback (auto-resolved via UniFi preferred)

    # Authentication
    control4_bearer_token: str | None = None  # Director bearer token
    control4_username: str | None = None  # For cloud auth token refresh
    control4_password: str | None = None
    control4_controller_name: str | None = None

    # SSL/TLS settings
    # SECURITY: SSL verification enabled by default to prevent MITM attacks.
    # Control4 Directors often use self-signed certificates. Options:
    # 1. Export the Director's certificate and set control4_ca_cert path (recommended)
    # 2. Set CONTROL4_VERIFY_SSL=0 environment variable (development only)
    # 3. Set control4_verify_ssl=False explicitly (document the risk)
    # Disabling SSL verification allows attackers to intercept bearer tokens
    # and control your home automation system.
    control4_verify_ssl: bool = True
    control4_ca_cert: str | None = (
        None  # Path to custom CA certificate (recommended for self-signed)
    )

    # ==========================================================================
    # Denon AVR (Home Theater)
    # ==========================================================================
    # Device identification (prefer MAC/hostname for UniFi discovery)
    denon_mac: str | None = None  # MAC address
    denon_hostname: str | None = None  # Hostname pattern
    denon_host: str | None = None  # Static IP fallback (auto-resolved via UniFi preferred)
    denon_model: str = "AVR-A10H"

    # ==========================================================================
    # LG webOS TV
    # ==========================================================================
    # Device identification (prefer MAC/hostname for UniFi discovery)
    lg_tv_mac: str | None = None  # MAC address
    lg_tv_hostname: str | None = None  # Hostname pattern
    lg_tv_host: str | None = None  # Static IP fallback (auto-resolved via UniFi preferred)
    lg_tv_client_key: str | None = None  # Saved after pairing

    # ==========================================================================
    # Eight Sleep (Smart Mattress)
    # ==========================================================================
    # Uses cloud API, no local IP needed
    eight_sleep_email: str | None = None
    eight_sleep_password: str | None = None

    # ==========================================================================
    # Tesla (Vehicle)
    # ==========================================================================
    # Uses cloud API, no local IP needed
    tesla_access_token: str | None = None
    tesla_refresh_token: str | None = None
    tesla_client_id: str | None = None
    tesla_client_secret: str | None = None

    # ==========================================================================
    # Oelo (Outdoor Lighting)
    # ==========================================================================
    # Device identification (choose one)
    oelo_mac: str | None = None  # MAC address
    oelo_hostname: str | None = None  # Hostname pattern
    oelo_host: str | None = None  # Static IP fallback

    # ==========================================================================
    # Samsung TV (Tizen Smart TVs)
    # ==========================================================================
    # Device identification (choose one)
    samsung_tv_mac: str | None = None  # MAC address
    samsung_tv_hostname: str | None = None  # Hostname pattern
    samsung_tv_host: str | None = None  # Static IP fallback
    samsung_tv_token: str | None = None  # Auth token (obtained after first pairing)

    # ==========================================================================
    # Formlabs (Form 4 3D Printer)
    # ==========================================================================
    # Uses PreFormServer Local API (runs on same network)
    # Download SDK: https://github.com/Formlabs/formlabs-api-python
    formlabs_host: str | None = None  # PreFormServer host (default: localhost)
    formlabs_port: int = 44388  # PreFormServer port

    # ==========================================================================
    # Glowforge (Pro Laser Cutter)
    # ==========================================================================
    # LIMITED INTEGRATION - No official API available
    # Provides network monitoring only, no remote control
    glowforge_ip: str | None = None  # Static IP of Glowforge

    # ==========================================================================
    # LG ThinQ (Smart Appliances)
    # ==========================================================================
    # Cloud API - requires token from developer.lge.com
    lg_thinq_access_token: str | None = None
    lg_thinq_country: str = "US"
    lg_thinq_language: str = "en-US"

    # ==========================================================================
    # Samsung SmartThings (Cloud API)
    # ==========================================================================
    # Cloud API - requires PAT from my.smartthings.com/advanced/tokens
    smartthings_token: str | None = None

    # ==========================================================================
    # Sub-Zero / Wolf / Cove (Premium Appliances)
    # ==========================================================================
    # Integrates via Control4 driver (recommended) or cloud API
    # Control4 driver: Install via your Control4 dealer
    # Cloud API: Uses Sub-Zero Group Owner's App credentials
    subzero_wolf_email: str | None = None
    subzero_wolf_password: str | None = None

    # ==========================================================================
    # Electrolux (Washer/Dryer)
    # ==========================================================================
    # Cloud API - uses Electrolux OneApp credentials
    # Also works with AEG and Frigidaire branded appliances
    electrolux_email: str | None = None
    electrolux_password: str | None = None
    electrolux_country: str = "US"

    # ==========================================================================
    # Mitsubishi HVAC (Kumo Cloud)
    # ==========================================================================
    # Cloud API for Mitsubishi mini-split systems
    # Uses same credentials as Kumo Cloud app
    kumo_username: str | None = None
    kumo_password: str | None = None

    # ==========================================================================
    # DSC Security (via Control4 or Envisalink)
    # ==========================================================================
    dsc_integration: str = "control4"  # "control4", "envisalink", "keybus"
    dsc_host: str | None = None  # Envisalink IP address
    dsc_port: int = 4025  # Envisalink TPI port (default 4025)
    dsc_password: str = "user"  # Envisalink password (default "user")
    dsc_code: str | None = None  # Arm/disarm code

    # Zone configuration (zone_num -> name/type)
    # Load from secrets: dsc_zone_labels, dsc_zone_types
    dsc_zone_labels: dict[int, str] = field(
        default_factory=dict
    )  # {1: "Front Door", 2: "Back Door"}
    dsc_zone_types: dict[int, str] = field(default_factory=dict)  # {1: "door_window", 3: "motion"}

    # Enable temperature monitoring (requires EMS-100 module)
    dsc_enable_temperature: bool = False

    # ==========================================================================
    # Presence Detection
    # ==========================================================================
    # Your devices for WiFi presence (MAC addresses)
    # If empty and auto_discover=True, auto-detects Apple devices named "Tim*"
    known_devices: list[str] = field(default_factory=list)

    # User device identification for auto-discovery
    # Configure via secrets: secrets.set("user_device_patterns", "pattern1,pattern2")
    user_device_patterns: list[str] = field(default_factory=list)

    # ==========================================================================
    # Location (for geofencing)
    # ==========================================================================
    home_latitude: float | None = None
    home_longitude: float | None = None

    # ==========================================================================
    # Presence Timing
    # ==========================================================================
    away_timeout_minutes: int = 30
    sleep_start_hour: int = 23
    sleep_end_hour: int = 6


# =============================================================================
# Helper to create config with common defaults
# =============================================================================


def create_adaptive_config(
    unifi_username: str | None = None,
    unifi_password: str | None = None,
    unifi_host: str | None = None,
    control4_token: str | None = None,
    lg_tv_key: str | None = None,
    eight_sleep_email: str | None = None,
    eight_sleep_password: str | None = None,
    user_device_patterns: list[str] | None = None,
    load_from_keychain: bool = True,
) -> SmartHomeConfig:
    """Create a SmartHomeConfig with auto-discovery enabled.

    Automatically loads credentials from macOS Keychain if available.
    All personal configuration (device patterns, locations, etc.) is loaded
    from secure keychain storage - no hardcoded values in source code.

    Example:
        # Loads all credentials from Keychain automatically:
        config = create_adaptive_config()

        # Or override specific values:
        config = create_adaptive_config(
            unifi_host="192.168.1.1",
            control4_token="custom_token",
        )

        controller = SmartHomeController(config)
        await controller.initialize()  # Auto-discovers all devices
    """
    # Load from keychain if enabled
    patterns: list[str] = user_device_patterns or []
    lg_tv_host: str | None = None
    samsung_tv_host: str | None = None
    samsung_tv_token: str | None = None

    if load_from_keychain:
        # HARDENED: Required keychain access - no fallbacks
        from kagami_smarthome.secrets import secrets

        # Use keychain values as defaults, allow overrides
        unifi_host = unifi_host or secrets.get("unifi_host")
        unifi_username = (
            unifi_username or secrets.get("unifi_username") or secrets.get("unifi_local_username")
        )
        unifi_password = (
            unifi_password or secrets.get("unifi_password") or secrets.get("unifi_local_password")
        )
        control4_token = control4_token or secrets.get("control4_bearer_token")
        # LG TV
        lg_tv_host = secrets.get("lg_tv_host")
        lg_tv_key = lg_tv_key or secrets.get("lg_tv_client_key")
        # Samsung TV
        samsung_tv_host = secrets.get("samsung_tv_host")
        samsung_tv_token = secrets.get("samsung_tv_token")
        # Eight Sleep
        eight_sleep_email = eight_sleep_email or secrets.get("eight_sleep_email")
        eight_sleep_password = eight_sleep_password or secrets.get("eight_sleep_password")

        # Load user device patterns from secrets
        if not patterns:
            patterns_str = secrets.get("user_device_patterns")
            if patterns_str:
                patterns = [p.strip() for p in patterns_str.split(",") if p.strip()]

    return SmartHomeConfig(
        # UniFi (required for discovery)
        unifi_host=unifi_host,
        unifi_username=unifi_username,
        unifi_password=unifi_password,
        auto_discover=True,
        # Control4 (token only, IP discovered)
        control4_bearer_token=control4_token,
        # LG TV (static IP + key from keychain)
        lg_tv_host=lg_tv_host,
        lg_tv_client_key=lg_tv_key,
        # Samsung TV (static IP + token from keychain)
        samsung_tv_host=samsung_tv_host,
        samsung_tv_token=samsung_tv_token,
        # Eight Sleep (cloud auth)
        eight_sleep_email=eight_sleep_email,
        eight_sleep_password=eight_sleep_password,
        # User device patterns for presence detection
        user_device_patterns=patterns,
        # Everything else auto-discovered via UniFi
    )
