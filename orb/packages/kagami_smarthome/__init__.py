"""Kagami Smart Home Integration — Room-Centric Architecture.

Unified smart home control with Theory of Mind presence inference.
Device IPs are discovered dynamically via UniFi - no hardcoded addresses.

Supported Systems:
- Control4: Lighting (Lutron), shades, multi-room audio (Triad AMS), security (DSC), locks (August), fireplace
- UniFi: Cameras (Protect), WiFi presence (Network), Device Discovery
- Denon AVR: Home theater receiver (telnet)
- Eight Sleep: Smart mattress, sleep detection (OAuth2)
- LG TV: webOS TV direct control (WebSocket)
- Samsung TV: Tizen TV control (REST/WebSocket)
- Mitsubishi HVAC: Mini-split zones (Kumo Cloud)
- Tesla: Vehicle geofencing/presence (OAuth2)
- Oelo: Outdoor lighting (HTTP)

Room-Centric Architecture:
=========================
- Each room is a first-class citizen with lights, shades, audio, HVAC
- Scene-based orchestration (Morning, Working, Movie, Sleep, Away)
- Home theater mode coordination
- Pattern learning for preferences
- Per-room occupancy tracking

Usage:
======
```python
from kagami_smarthome import SmartHomeController, SmartHomeConfig

controller = SmartHomeController()  # Uses default config
await controller.initialize()

# Room-centric control
await controller.set_room_scene("Living Room", "relaxing")
await controller.set_room_temp("Office", 72)

# Home theater
await controller.enter_movie_mode()

# House-wide
await controller.goodnight()
```

Created: December 29, 2025
Updated: December 29, 2025 — Room-centric architecture
"""

__version__ = "2.2.0"

# Data types
# Controller
# =============================================================================
# SINGLETON SMART HOME CONTROLLER
# =============================================================================
import logging
import os
import threading

# =============================================================================
# LOGGING CONFIGURATION — Reduce spam, keep essential info
# =============================================================================
# Set SMARTHOME_DEBUG=1 for verbose logging
_debug_mode = os.environ.get("SMARTHOME_DEBUG", "").lower() in ("1", "true", "yes")
_log_level = logging.DEBUG if _debug_mode else logging.WARNING

# Quiet down chatty loggers during boot
for _logger_name in [
    "kagami_smarthome.integration_pool",
    "kagami_smarthome.polling_stub",  # Minimal stub (replaces adaptive_polling)
    "kagami_smarthome.performance_monitor",
    "kagami_smarthome.failover_manager",
    "kagami_smarthome.localization",
    "kagami_smarthome.discovery",
    "kagami_smarthome.presence",
    "kagami_smarthome.orchestrator",
    "kagami_smarthome.audio_bridge",
    "kagami_smarthome.integrations.mitsubishi",
    "kagami_smarthome.integrations.unifi",
    "kagami_smarthome.integrations.control4",
    "kagami_smarthome.integrations.apple_findmy",
    "kagami_smarthome.integrations.august",
    "kagami_smarthome.integrations.tesla",
    "kagami_smarthome.integrations.denon",
    "kagami_smarthome.integrations.lg_tv",
    "kagami_smarthome.integrations.samsung_tv",
    "kagami_smarthome.integrations.oelo",
    "kagami_smarthome.integrations.eight_sleep",
    "kagami_smarthome.controller",
]:
    logging.getLogger(_logger_name).setLevel(_log_level)

# Audio Bridge (Streaming Parler-TTS → Control4/Denon)
# Advanced Automation (Dec 30, 2025 - Architecture Improvements)
from kagami_smarthome.advanced_automation import (
    AdvancedAutomationManager,
    CircadianPhase,
    CircadianSettings,
    GuestMode,
    GuestModeConfig,
    OccupancySimulator,
    PredictiveHVAC,
    SleepOptimizer,
    StateReconciler,
    VacationModeConfig,
    get_advanced_automation,
    get_circadian_color_temp,
    get_circadian_max_brightness,
    get_current_circadian_phase,
    start_advanced_automation,
)
from kagami_smarthome.audio_bridge import (
    PlaybackMetrics,
    RoomAudioBridge,
    RoomResult,
    StreamConfig,
    get_audio_bridge,
)

# Security Infrastructure (January 2, 2026)
from kagami_smarthome.audit import (
    ActionCategory,
    ActionStatus,
    AuditRecord,
    AuditTrail,
    get_audit_trail,
)
from kagami_smarthome.controller import SmartHomeController

# Device Reconciler (multi-device tracking)
from kagami_smarthome.device_reconciler import (
    DeviceReconciler,
    ReconciledPresence,
    TrackedDeviceState,
    TrackedDeviceType,  # Renamed from DeviceType to avoid collision with discovery.DeviceType
    TravelMode,
    get_device_reconciler,
)

# Device Discovery
from kagami_smarthome.discovery import (
    DeviceDiscovery,
    DeviceRegistry,
    DeviceType,
    DiscoveredDevice,
)

# Integrations
from kagami_smarthome.integrations import (
    HOME_ADDRESS,
    HOME_LAT,
    HOME_LON,
    # Apple Health (Biometrics)
    ActivityData,
    AppleHealthIntegration,
    # August (Smart Locks)
    AugustIntegration,
    BedSide,
    BodyData,
    ChargingState,
    # Core
    Control4Integration,
    CoveDishwasherStatus,
    CoveWashCycle,
    DenonIntegration,
    DoorState,
    DryerCycle,
    DryerStatus,
    # Eight Sleep
    EightSleepIntegration,
    ElectroluxAppliance,
    ElectroluxDryerStatus,
    # Electrolux
    ElectroluxIntegration,
    ElectroluxWasherStatus,
    # Envisalink (DSC Security)
    EnvisalinkIntegration,
    FanSpeed,
    HealthEventCallback,
    HealthMetricType,
    HealthState,
    HeartData,
    HVACMode,
    HVACZone,
    HVACZoneStatus,
    KagamiHostInfo,
    # Kagami Host (Self-Monitoring)
    KagamiHostIntegration,
    KagamiHostStatus,
    # LG ThinQ (Appliances)
    LGThinQIntegration,
    # LG TV
    LGTVIntegration,
    # Maps / Location
    LocationInfo,
    LockInfo,
    LockState,
    MapsService,
    # Mitsubishi HVAC
    MitsubishiIntegration,
    OeloHoliday,
    # Oelo
    OeloIntegration,
    OeloPattern,
    OeloState,
    OeloZone,
    OvenMode,
    OvenStatus,
    PartitionInfo,
    PartitionState,
    RefrigeratorStatus,
    RespiratoryData,
    SamsungTVInfo,
    # Samsung TV
    SamsungTVIntegration,
    SamsungTVKey,
    SleepData,
    SleepStage,
    SleepState,
    SmartThingsCapability,
    SmartThingsDevice,
    SmartThingsDeviceType,
    # SmartThings
    SmartThingsIntegration,
    SmartThingsLocation,
    SubZeroMode,
    SubZeroStatus,
    # Sub-Zero/Wolf/Cove
    SubZeroWolfIntegration,
    TemperatureReading,
    # Tesla
    TeslaIntegration,
    TeslaState,
    ThinQDevice,
    ThinQDeviceType,
    TroubleStatus,
    TroubleType,
    UniFiIntegration,
    VaneDirection,
    VehicleState,
    WasherCycle,
    WasherStatus,
    # Weather
    WeatherCondition,
    WeatherData,
    WeatherService,
    WolfOvenMode,
    WolfRangeStatus,
    WorkoutData,
    WorkoutType,
    ZoneInfo,
    ZoneState,
    ZoneType,
    get_apple_health,
    get_current_weather,
    get_distance_to_home,
    get_maps_service,
    get_weather_service,
    start_apple_health,
)

# Intent-Based Automation (January 2, 2026 — Household-Agnostic)
from kagami_smarthome.intent_automation import (
    AutomationIntent,
    AutomationRule,
    Capability,
    Condition,
    HouseholdCapabilities,
    IntentAutomationEngine,
    IntentExecution,
    IntentExecutor,
    discover_capabilities,
    get_intent_automation,
    setup_intent_automation,
)
from kagami_smarthome.light_debouncer import (
    LightCommandDebouncer,
    get_light_debouncer,
)

# Device Localization (Deep Presence Tracking)
from kagami_smarthome.localization import (
    AccessPointMapping,
    DeviceLocalizer,
    DeviceLocation,
    LocationConfidence,
    RoomOccupants,
)
from kagami_smarthome.orchestrator import (
    OrchestratorConfig,
    RoomOrchestrator,
)

# Unified Persistence (Dec 30, 2025 - Memory Optimization)
from kagami_smarthome.persistence import (
    DEVICE_REGISTRY_FILE,
    KAGAMI_HOME,
    PATTERNS_FILE,
    SESSION_FILE,
    SPOTIFY_CREDENTIALS_FILE,
    STATE_SNAPSHOT_FILE,
    PersistenceManager,
    SessionState,
    StateSnapshot,
    atomic_write_json,
    ensure_kagami_home,
    get_persistence_manager,
    safe_read_json,
    start_persistence,
)

# Presence engine
from kagami_smarthome.presence import PresenceEngine
from kagami_smarthome.rate_limiter import (
    RateLimitConfig,
    RateLimiter,
    get_rate_limiter,
)

# Room-centric components
from kagami_smarthome.room import (
    ActivityContext as RoomActivityContext,
)
from kagami_smarthome.room import (
    AudioZone,
    Light,
    Room,
    RoomPreferences,
    RoomRegistry,
    RoomState,
    RoomType,
    Shade,
)

# Safety (CBF integration - December 30, 2025)
from kagami_smarthome.safety import (
    FIREPLACE_MAX_ON_DURATION,
    PhysicalActionType,
    SafetyContext,
    SafetyResult,
    check_fireplace_safety,
    check_lock_safety,
    check_physical_safety,
    check_tv_mount_safety,
)
from kagami_smarthome.scenes import (
    SCENES,
    Scene,
    Season,
    TimeOfDay,
    get_all_scenes,
    get_scene,
)

# Secrets management (macOS Keychain)
from kagami_smarthome.secrets import (
    KeychainSecrets,
    get_config_from_keychain,
    secrets,
)

# Domain Services (Phase 5 Refactor)
from kagami_smarthome.services import (
    AVService,
    ClimateService,
    DeviceService,
    SecurityService,
)

# Travel Intelligence
from kagami_smarthome.travel_intelligence import (
    RouteAlert,
    TravelIntelligence,
    TravelState,
    get_travel_intelligence,
    start_travel_monitoring,
)
from kagami_smarthome.types import (
    ActivityContext,
    DeviceIdentifier,
    DSCTemperature,
    DSCTroubleState,
    DSCZoneState,
    GeofenceState,
    HomeState,
    PresenceEvent,
    PresenceState,
    SecurityState,
    SmartHomeConfig,
    TrackedDevice,
    create_adaptive_config,
)
from kagami_smarthome.validation import (
    VALID_ROOMS,
    VALID_SCENES,
    AnnounceCommand,
    LightCommand,
    LockCommand,
    SceneCommand,
    ShadeCommand,
    SpotifyCommand,
    TemperatureCommand,
    TVMountCommand,
    VolumeCommand,
    validate_command,
    validate_room,
    validate_rooms,
)

# Visitor Detection (Dec 30, 2025 - Guest Mode Enhancement)
from kagami_smarthome.visitor_detection import (
    DeviceCategory,
    KnownDeviceRegistry,  # Renamed from DeviceRegistry to avoid collision with discovery
    RegisteredDevice,
    VisitorAlert,
    VisitorDetector,
    VisitorSession,
    get_visitor_detector,
    start_visitor_detection,
)

_smart_home_instance: SmartHomeController | None = None
_smart_home_lock = threading.Lock()
_smart_home_initializing = False

_logger = logging.getLogger(__name__)


async def get_smart_home(
    config: SmartHomeConfig | None = None,
    auto_initialize: bool = True,
) -> SmartHomeController:
    """Get singleton SmartHomeController instance (async).

    This is the canonical way to access smart home functionality.
    The controller is initialized once and reused - no boot delay on subsequent calls.

    Args:
        config: Optional config (only used on first call)
        auto_initialize: Whether to auto-initialize if not already done

    Returns:
        SmartHomeController singleton instance

    Usage:
        # First call initializes (takes ~6s with parallel boot)
        controller = await get_smart_home()

        # Subsequent calls return immediately
        controller = await get_smart_home()

        # Use the controller
        await controller.close_shades(rooms=["Living Room"])
    """
    global _smart_home_instance, _smart_home_initializing

    with _smart_home_lock:
        if _smart_home_instance is None and not _smart_home_initializing:
            _smart_home_initializing = True

    if _smart_home_instance is None:
        try:
            _logger.info("🏠 Creating SmartHomeController singleton...")
            # Use create_adaptive_config to load credentials from Keychain
            cfg = config or create_adaptive_config()
            instance = SmartHomeController(cfg)

            if auto_initialize:
                await instance.initialize()

            with _smart_home_lock:
                _smart_home_instance = instance
                _smart_home_initializing = False

            _logger.info("✅ SmartHomeController singleton ready")
        except Exception:
            with _smart_home_lock:
                _smart_home_initializing = False
            raise

    return _smart_home_instance


def get_smart_home_sync(
    config: SmartHomeConfig | None = None,
) -> SmartHomeController:
    """Get singleton SmartHomeController (sync version - not initialized).

    Returns the singleton instance without async initialization.
    Call initialize() separately if needed.

    Args:
        config: Optional config (only used on first call)

    Returns:
        SmartHomeController singleton (may not be initialized)
    """
    global _smart_home_instance

    with _smart_home_lock:
        if _smart_home_instance is None:
            cfg = config or SmartHomeConfig(auto_discover=True)
            _smart_home_instance = SmartHomeController(cfg)

    return _smart_home_instance


def is_smart_home_initialized() -> bool:
    """Check if smart home singleton is initialized and connected."""
    return _smart_home_instance is not None and _smart_home_instance._initialized


async def shutdown_smart_home() -> None:
    """Shutdown the smart home singleton."""
    global _smart_home_instance

    with _smart_home_lock:
        if _smart_home_instance is not None:
            await _smart_home_instance.stop()
            _smart_home_instance = None
            _logger.info("🏠 SmartHomeController singleton shutdown")


__all__ = [
    # Apple Health (Biometrics)
    "AppleHealthIntegration",
    "HealthState",
    "HealthMetricType",
    "HeartData",
    "SleepData",
    "ActivityData",
    "RespiratoryData",
    "BodyData",
    "WorkoutData",
    "WorkoutType",
    "HealthEventCallback",
    "get_apple_health",
    "start_apple_health",
    # Types
    "ActivityContext",
    "DeviceIdentifier",
    "DSCTemperature",
    "DSCTroubleState",
    "DSCZoneState",
    "GeofenceState",
    "HomeState",
    "PresenceEvent",
    "PresenceState",
    "SecurityState",
    "SmartHomeConfig",
    "TrackedDevice",
    "create_adaptive_config",
    # Discovery
    "DeviceDiscovery",
    "DeviceRegistry",
    "DeviceType",
    "DiscoveredDevice",
    # Controller
    "SmartHomeController",
    # Presence
    "PresenceEngine",
    # Device Localization
    "DeviceLocalizer",
    "DeviceLocation",
    "AccessPointMapping",
    "LocationConfidence",
    "RoomOccupants",
    # Room-centric
    "Room",
    "RoomRegistry",
    "RoomState",
    "RoomType",
    "RoomPreferences",
    "RoomActivityContext",
    "Light",
    "Shade",
    "AudioZone",
    "Scene",
    "SCENES",
    "get_scene",
    "get_all_scenes",
    "TimeOfDay",
    "Season",
    "RoomOrchestrator",
    "OrchestratorConfig",
    # Light Debouncer (prevents flickering)
    "LightCommandDebouncer",
    "get_light_debouncer",
    # Core Integrations
    "Control4Integration",
    "DenonIntegration",
    "EnvisalinkIntegration",
    "UniFiIntegration",
    # August (Smart Locks)
    "AugustIntegration",
    "LockState",
    "DoorState",
    "LockInfo",
    # Envisalink (DSC Security)
    "ZoneInfo",
    "ZoneState",
    "ZoneType",
    "PartitionInfo",
    "PartitionState",
    "TroubleStatus",
    "TroubleType",
    "TemperatureReading",
    # Eight Sleep
    "EightSleepIntegration",
    "BedSide",
    "SleepStage",
    "SleepState",
    # LG TV
    "LGTVIntegration",
    # Samsung TV
    "SamsungTVIntegration",
    "SamsungTVKey",
    "SamsungTVInfo",
    # Mitsubishi HVAC
    "MitsubishiIntegration",
    "HVACZone",
    "HVACZoneStatus",
    "HVACMode",
    "FanSpeed",
    "VaneDirection",
    # Tesla
    "TeslaIntegration",
    "TeslaState",
    "VehicleState",
    "ChargingState",
    # Oelo
    "OeloIntegration",
    "OeloPattern",
    "OeloHoliday",
    "OeloState",
    "OeloZone",
    # LG ThinQ (Appliances)
    "LGThinQIntegration",
    "ThinQDevice",
    "ThinQDeviceType",
    "RefrigeratorStatus",
    "OvenStatus",
    "OvenMode",
    "WasherStatus",
    "WasherCycle",
    "DryerStatus",
    "DryerCycle",
    # SmartThings
    "SmartThingsIntegration",
    "SmartThingsDevice",
    "SmartThingsDeviceType",
    "SmartThingsCapability",
    "SmartThingsLocation",
    # Sub-Zero/Wolf/Cove
    "SubZeroWolfIntegration",
    "WolfRangeStatus",
    "WolfOvenMode",
    "SubZeroStatus",
    "SubZeroMode",
    "CoveDishwasherStatus",
    "CoveWashCycle",
    # Electrolux
    "ElectroluxIntegration",
    "ElectroluxAppliance",
    "ElectroluxWasherStatus",
    "ElectroluxDryerStatus",
    # Kagami Host
    "KagamiHostIntegration",
    "KagamiHostInfo",
    "KagamiHostStatus",
    # Audio Bridge (Multi-Room Streaming Parler-TTS)
    "RoomAudioBridge",
    "StreamConfig",
    "RoomResult",
    "PlaybackMetrics",
    "get_audio_bridge",
    # Secrets (macOS Keychain)
    "secrets",
    "KeychainSecrets",
    "get_config_from_keychain",
    # Weather
    "WeatherService",
    "WeatherData",
    "WeatherCondition",
    "WeatherForecast",
    "HourlyForecast",
    "get_weather_service",
    "get_current_weather",
    "get_weather_forecast",
    "get_shade_recommendation",
    # Maps / Location
    "LocationInfo",
    "MapsService",
    "get_maps_service",
    "get_distance_to_home",
    "HOME_LAT",
    "HOME_LON",
    "HOME_ADDRESS",
    # Travel Intelligence
    "TravelState",
    "RouteAlert",
    "TravelIntelligence",
    "get_travel_intelligence",
    "start_travel_monitoring",
    # Device Reconciler
    "TravelMode",
    "TrackedDeviceType",  # Renamed from DeviceType to avoid collision
    "TrackedDeviceState",
    "ReconciledPresence",
    "DeviceReconciler",
    "get_device_reconciler",
    # Domain Services (Phase 5 Refactor)
    "DeviceService",
    "AVService",
    "ClimateService",
    "SecurityService",
    # Safety (CBF integration - December 30, 2025)
    "PhysicalActionType",
    "SafetyContext",
    "SafetyResult",
    "check_physical_safety",
    "check_fireplace_safety",
    "check_tv_mount_safety",
    "check_lock_safety",
    "FIREPLACE_MAX_ON_DURATION",
    # Singleton access
    "get_smart_home",
    "get_smart_home_sync",
    "is_smart_home_initialized",
    "shutdown_smart_home",
    # Advanced Automation (Dec 30, 2025)
    "AdvancedAutomationManager",
    "CircadianPhase",
    "CircadianSettings",
    "GuestMode",
    "GuestModeConfig",
    "OccupancySimulator",
    "PredictiveHVAC",
    "SleepOptimizer",
    "StateReconciler",
    "VacationModeConfig",
    "get_advanced_automation",
    "get_circadian_color_temp",
    "get_circadian_max_brightness",
    "get_current_circadian_phase",
    "start_advanced_automation",
    # Visitor Detection (Dec 30, 2025)
    "DeviceCategory",
    "KnownDeviceRegistry",  # Renamed from DeviceRegistry to avoid collision
    "RegisteredDevice",
    "VisitorAlert",
    "VisitorDetector",
    "VisitorSession",
    "get_visitor_detector",
    "start_visitor_detection",
    # Unified Persistence (Dec 30, 2025)
    "KAGAMI_HOME",
    "PATTERNS_FILE",
    "DEVICE_REGISTRY_FILE",
    "SPOTIFY_CREDENTIALS_FILE",
    "STATE_SNAPSHOT_FILE",
    "SESSION_FILE",
    "PersistenceManager",
    "StateSnapshot",
    "SessionState",
    "atomic_write_json",
    "safe_read_json",
    "ensure_kagami_home",
    "get_persistence_manager",
    "start_persistence",
    # Security Infrastructure (January 2, 2026)
    "ActionCategory",
    "ActionStatus",
    "AuditRecord",
    "AuditTrail",
    "get_audit_trail",
    "RateLimitConfig",
    "RateLimiter",
    "get_rate_limiter",
    "VALID_ROOMS",
    "VALID_SCENES",
    "AnnounceCommand",
    "LightCommand",
    "LockCommand",
    "SceneCommand",
    "ShadeCommand",
    "SpotifyCommand",
    "TVMountCommand",
    "TemperatureCommand",
    "VolumeCommand",
    "validate_command",
    "validate_room",
    "validate_rooms",
    # Intent-Based Automation (January 2, 2026 — Household-Agnostic)
    "AutomationIntent",
    "AutomationRule",
    "Capability",
    "Condition",
    "HouseholdCapabilities",
    "IntentAutomationEngine",
    "IntentExecution",
    "IntentExecutor",
    "discover_capabilities",
    "get_intent_automation",
    "setup_intent_automation",
]
