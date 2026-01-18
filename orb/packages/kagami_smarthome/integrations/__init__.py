"""Smart Home Vendor Integrations.

All integrations use direct REST/HTTP/WebSocket/Telnet APIs.
No external vendor library dependencies (except optional thinqconnect for LG ThinQ).

Integrations:
- Apple Find My: Device location, play sound, lost mode (iCloud API)
- Control4: Lighting, shades, audio, security, locks, fireplace, MantelMount
- Envisalink: DSC security panel (TPI protocol) - zones, sensors, temperature
- UniFi: Cameras, network, presence detection
- Denon: Home theater receiver (telnet)
- EightSleep: Smart mattress, sleep detection (OAuth2)
- August: Smart locks (direct yalexs API)
- LG TV: webOS TV control (WebSocket)
- Samsung TV: Tizen Smart TV control (REST/WebSocket)
- Tesla: Vehicle presence/geofencing (OAuth2)
- Oelo: Outdoor lighting (HTTP)
- LG ThinQ: Smart appliances - fridge, oven, washer, dryer (Cloud API)
- SmartThings: Samsung/third-party devices (Cloud API)
- Spotify: Music streaming via librespot-python (Premium required)
- Formlabs: Form 4 resin 3D printer (Local API)
- Glowforge: Pro laser cutter (limited - no official API, network monitoring only)
"""

from kagami_smarthome.integrations.apple_findmy import (
    AppleDeviceInfo,
    AppleFindMyIntegration,
    find_my_iphone,
)
from kagami_smarthome.integrations.apple_health import (
    ActivityData,
    AppleHealthIntegration,
    BodyData,
    HealthEventCallback,
    HealthMetricType,
    HealthState,
    HeartData,
    RespiratoryData,
    SleepData,
    SleepStage,
    WorkoutData,
    WorkoutType,
    get_apple_health,
    start_apple_health,
)
from kagami_smarthome.integrations.august import (
    AugustIntegration,
    DoorState,
    LockInfo,
    LockState,
)
from kagami_smarthome.integrations.control4 import Control4Integration
from kagami_smarthome.integrations.denon import DenonIntegration
from kagami_smarthome.integrations.eight_sleep import (
    BedSide,
    EightSleepIntegration,
    SleepState,
)

# SleepStage already exported from apple_health, eight_sleep exports it differently
from kagami_smarthome.integrations.electrolux import (
    ElectroluxAppliance,
    ElectroluxDryerCycle,
    ElectroluxDryerStatus,
    ElectroluxDryLevel,
    ElectroluxIntegration,
    ElectroluxSpinSpeed,
    ElectroluxWasherCycle,
    ElectroluxWasherStatus,
    ElectroluxWaterTemp,
)
from kagami_smarthome.integrations.envisalink import (
    EnvisalinkIntegration,
    PartitionInfo,
    PartitionState,
    TemperatureReading,
    TroubleStatus,
    TroubleType,
    ZoneInfo,
    ZoneState,
    ZoneType,
)
from kagami_smarthome.integrations.formlabs import (
    FormlabsIntegration,
    FormlabsState,
    PrinterState,
    PrintJob,
    PrintJobStatus,
    ResinType,
    TankStatus,
    get_formlabs,
    start_formlabs,
)
from kagami_smarthome.integrations.glowforge import (
    MATERIAL_PRESETS,
    GlowforgeIntegration,
    GlowforgeMachine,
    GlowforgeState,
    GlowforgeStatus,
    LaserPower,
    MaterialSettings,
    get_glowforge,
    start_glowforge,
)
from kagami_smarthome.integrations.kagami_host import (
    KagamiHostInfo,
    KagamiHostIntegration,
    KagamiHostStatus,
)
from kagami_smarthome.integrations.lg_thinq import (
    DryerCycle,
    DryerStatus,
    LGThinQIntegration,
    OvenMode,
    OvenStatus,
    RefrigeratorStatus,
    ThinQDevice,
    ThinQDeviceType,
    WasherCycle,
    WasherStatus,
)
from kagami_smarthome.integrations.lg_tv import LGTVIntegration
from kagami_smarthome.integrations.maps import (
    HOME_ADDRESS,
    HOME_LAT,
    HOME_LON,
    LocationInfo,
    MapsService,
    get_distance_to_home,
    get_maps_service,
)
from kagami_smarthome.integrations.meta_glasses import (
    MetaGlassesIntegration,
    VisualContext,
    get_meta_glasses,
)
from kagami_smarthome.integrations.mitsubishi import (
    FanSpeed,
    HVACMode,
    HVACZone,
    HVACZoneStatus,
    MitsubishiIntegration,
    VaneDirection,
)
from kagami_smarthome.integrations.oelo import (
    OeloHoliday,
    OeloIntegration,
    OeloPattern,
    OeloState,
    OeloZone,
)
from kagami_smarthome.integrations.samsung_tv import (
    SamsungTVInfo,
    SamsungTVIntegration,
    SamsungTVKey,
)
from kagami_smarthome.integrations.smartthings import (
    SmartThingsCapability,
    SmartThingsDevice,
    SmartThingsDeviceType,
    SmartThingsIntegration,
    SmartThingsLocation,
)
from kagami_smarthome.integrations.spotify import (
    KAGAMI_PLAYLISTS,
    AudioOutput,
    PlaybackState,
    SpotifyConfig,
    SpotifyIntegration,
    SpotifyState,
    SpotifyTrack,
    parse_spotify_uri,
)
from kagami_smarthome.integrations.subzero_wolf import (
    CoveDishwasherStatus,
    CoveWashCycle,
    SubZeroMode,
    SubZeroStatus,
    SubZeroWolfIntegration,
    WolfOvenMode,
    WolfRangeStatus,
)
from kagami_smarthome.integrations.tesla import (
    ChargingState,
    # Alerts
    TeslaAlertDictionary,
    TeslaAlertRouter,
    # Command Executor
    TeslaCommandExecutor,
    # Companion/Voice
    TeslaCompanionProtocol,
    # Event Bus
    TeslaEventBus,
    TeslaEventType,
    # Core
    TeslaIntegration,
    TeslaPresenceState,
    TeslaSafetyBarrier,
    TeslaState,
    TeslaStreamingClient,
    TeslaVoiceAdapter,
    VehicleState,
    connect_tesla_event_bus,
    create_tesla_voice_adapter,
    get_companion_protocol,
    get_tesla_event_bus,
)
from kagami_smarthome.integrations.unifi import UniFiIntegration
from kagami_smarthome.integrations.weather import (
    WeatherCondition,
    WeatherData,
    WeatherService,
    get_current_weather,
    get_weather_service,
)

__all__ = [
    # Apple Find My
    "AppleFindMyIntegration",
    "AppleDeviceInfo",
    "find_my_iphone",
    # Apple Health (Biometrics)
    "AppleHealthIntegration",
    "HealthState",
    "HealthMetricType",
    "HeartData",
    "SleepData",
    "SleepStage",
    "ActivityData",
    "RespiratoryData",
    "BodyData",
    "WorkoutData",
    "WorkoutType",
    "HealthEventCallback",
    "get_apple_health",
    "start_apple_health",
    # Control4
    "Control4Integration",
    # Envisalink (DSC Security)
    "EnvisalinkIntegration",
    "ZoneInfo",
    "ZoneState",
    "ZoneType",
    "PartitionInfo",
    "PartitionState",
    "TroubleStatus",
    "TroubleType",
    "TemperatureReading",
    # August (Direct API)
    "AugustIntegration",
    "LockState",
    "DoorState",
    "LockInfo",
    # Denon
    "DenonIntegration",
    # UniFi
    "UniFiIntegration",
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
    # Tesla (Core)
    "TeslaIntegration",
    "TeslaState",
    "TeslaStreamingClient",
    "VehicleState",
    "ChargingState",
    # Tesla Event Bus
    "TeslaEventBus",
    "TeslaEventType",
    "TeslaPresenceState",
    "get_tesla_event_bus",
    "connect_tesla_event_bus",
    # Tesla Command/Safety
    "TeslaCommandExecutor",
    "TeslaSafetyBarrier",
    # Tesla Companion/Voice
    "TeslaCompanionProtocol",
    "TeslaVoiceAdapter",
    "get_companion_protocol",
    "create_tesla_voice_adapter",
    # Tesla Alerts
    "TeslaAlertDictionary",
    "TeslaAlertRouter",
    # Meta Glasses
    "MetaGlassesIntegration",
    "VisualContext",
    "get_meta_glasses",
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
    # Sub-Zero / Wolf / Cove
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
    "ElectroluxWasherCycle",
    "ElectroluxSpinSpeed",
    "ElectroluxWaterTemp",
    "ElectroluxDryerStatus",
    "ElectroluxDryerCycle",
    "ElectroluxDryLevel",
    # Formlabs (Form 4 3D Printer)
    "FormlabsIntegration",
    "FormlabsState",
    "PrinterState",
    "PrintJob",
    "PrintJobStatus",
    "ResinType",
    "TankStatus",
    "get_formlabs",
    "start_formlabs",
    # Glowforge (Laser Cutter - Limited)
    "GlowforgeIntegration",
    "GlowforgeState",
    "GlowforgeMachine",
    "GlowforgeStatus",
    "LaserPower",
    "MaterialSettings",
    "MATERIAL_PRESETS",
    "get_glowforge",
    "start_glowforge",
    # Kagami Host (Self-Monitoring)
    "KagamiHostIntegration",
    "KagamiHostInfo",
    "KagamiHostStatus",
    # Mitsubishi HVAC
    "MitsubishiIntegration",
    "HVACZone",
    "HVACZoneStatus",
    "HVACMode",
    "FanSpeed",
    "VaneDirection",
    # Spotify Streaming
    "SpotifyIntegration",
    "SpotifyState",
    "SpotifyTrack",
    "SpotifyConfig",
    "PlaybackState",
    "AudioOutput",
    "KAGAMI_PLAYLISTS",
    "parse_spotify_uri",
    # Weather
    "WeatherService",
    "WeatherData",
    "WeatherCondition",
    "get_weather_service",
    "get_current_weather",
    # Maps / Location
    "LocationInfo",
    "MapsService",
    "get_maps_service",
    "get_distance_to_home",
    "HOME_LAT",
    "HOME_LON",
    "HOME_ADDRESS",
]
