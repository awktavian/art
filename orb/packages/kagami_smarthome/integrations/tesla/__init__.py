"""Tesla Integration Subpackage — Consolidated.

All Tesla functionality in three modules:
- tesla.py: Main integration, streaming, commands, events, voice, safety, alerts
- types.py: All type definitions (enums, dataclasses)
- geo.py: Geolocation utilities (haversine, geofencing)

Usage:
    from kagami_smarthome.integrations.tesla import (
        TeslaIntegration,
        TeslaStreamingClient,
        TeslaCommandExecutor,
        TeslaEventBus,
        TeslaSafetyBarrier,
        TeslaVoiceAdapter,
        TeslaCompanionProtocol,
        TeslaAlertDictionary,
        TeslaAlertRouter,
        VehicleState,
        ChargingState,
        DrivingState,
        TeslaState,
    )

    from kagami_smarthome.integrations.tesla.geo import (
        is_at_home,
        distance_to_home,
    )

Created: January 11, 2026 (consolidated from 7 modules)
"""

# Types - Enums and Dataclasses
# Geo - Location utilities
from kagami_smarthome.integrations.tesla.geo import (
    HOME_LAT,
    HOME_LON,
    HOME_RADIUS_METERS,
    HOME_RADIUS_MILES,
    bearing,
    distance_to_home,
    distance_to_home_meters,
    haversine,
    haversine_meters,
    is_at_home,
    is_heading_home,
)

# Main Tesla classes (consolidated module)
from kagami_smarthome.integrations.tesla.tesla import (
    API_BASE,
    DRIVING_PROTECTION,
    AlertCallback,
    AlertCategory,
    AlertPriority,
    AudioTarget,
    CommandCategory,
    CommandMeta,
    CompanionState,
    CompanionStatus,
    EventCallback,
    PredefinedSound,
    SafetyLevel,
    SpeakResult,
    # Alert System
    TeslaAlert,
    TeslaAlertDictionary,
    TeslaAlertRouter,
    # Command Executor
    TeslaCommandExecutor,
    # Companion Protocol
    TeslaCompanionProtocol,
    # Event Bus
    TeslaEventBus,
    TeslaEventCallback,
    # Core Integration
    TeslaIntegration,
    # Safety Barrier
    TeslaSafetyBarrier,
    TeslaStreamingClient,
    # Voice Adapter
    TeslaVoiceAdapter,
    VoiceResult,
    cbf_protected,
    connect_tesla_event_bus,
    create_tesla_voice_adapter,
    get_companion_protocol,
    get_tesla_event_bus,
)
from kagami_smarthome.integrations.tesla.types import (
    ChargingState,
    ConfirmationRequest,
    ConfirmationType,
    DrivingState,
    EventPayload,
    SafetyState,
    TelemetrySnapshot,
    TelemetryValue,
    TeslaEventType,
    TeslaPresenceState,
    TeslaState,
    VehicleState,
)

__all__ = [
    # API
    "API_BASE",
    # Core Integration
    "TeslaIntegration",
    "TeslaStreamingClient",
    "TeslaEventCallback",
    # Command Executor
    "TeslaCommandExecutor",
    "CommandCategory",
    "CommandMeta",
    "SafetyLevel",
    "cbf_protected",
    # Safety Barrier
    "TeslaSafetyBarrier",
    "DRIVING_PROTECTION",
    # Event Bus
    "TeslaEventBus",
    "EventCallback",
    "get_tesla_event_bus",
    "connect_tesla_event_bus",
    # Companion Protocol
    "TeslaCompanionProtocol",
    "CompanionState",
    "CompanionStatus",
    "SpeakResult",
    "get_companion_protocol",
    # Voice Adapter
    "TeslaVoiceAdapter",
    "AudioTarget",
    "PredefinedSound",
    "VoiceResult",
    "create_tesla_voice_adapter",
    # Alert System
    "TeslaAlert",
    "TeslaAlertDictionary",
    "TeslaAlertRouter",
    "AlertPriority",
    "AlertCategory",
    "AlertCallback",
    # Types - Enums
    "ChargingState",
    "ConfirmationType",
    "DrivingState",
    "TeslaEventType",
    "TeslaPresenceState",
    "VehicleState",
    # Types - Dataclasses
    "ConfirmationRequest",
    "EventPayload",
    "SafetyState",
    "TelemetrySnapshot",
    "TelemetryValue",
    "TeslaState",
    # Geo - Constants
    "HOME_LAT",
    "HOME_LON",
    "HOME_RADIUS_METERS",
    "HOME_RADIUS_MILES",
    # Geo - Functions
    "bearing",
    "distance_to_home",
    "distance_to_home_meters",
    "haversine",
    "haversine_meters",
    "is_at_home",
    "is_heading_home",
]
