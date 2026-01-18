"""Kagami Core Integrations — Event-Driven Sensory Architecture.

REFACTORED: December 29, 2025 — Unified Event-Driven Architecture
CLEANED: December 29, 2025 — Removed deprecated TimObserver
ENHANCED: December 29, 2025 — Added WakefulnessManager for adaptive polling

Components:
- UnifiedSensoryIntegration: THE SINGLE source for all sensory data (digital + physical)
- AlertHierarchy: Priority-based notification routing (wired to sensory)
- WakefulnessManager: Unified wakefulness state controlling all subsystems

Architecture:
    SituationPhase (SituationAwarenessEngine) → WakefulnessManager → adapts →
        - UnifiedSensory (poll intervals)
        - AutonomousGoalEngine (enable/pause)
        - AlertHierarchy (thresholds)
        - OrganismConsciousness (state sync)

Wakefulness Levels:
    DORMANT: Sleeping (10x slower polling, no autonomy)
    DROWSY: Waking/winding down (3x slower, limited autonomy)
    ALERT: Normal active (1x polling, full autonomy)
    FOCUSED: Deep work (2x slower, autonomy continues, fewer interrupts)
    HYPER: High urgency (2x faster, all alerts)

Usage:
    # Initialize with wakefulness
    from kagami.core.integrations import (
        initialize_unified_sensory,
        initialize_wakefulness,
        get_wakefulness_manager,
        WakefulnessLevel,
    )

    sensory = await initialize_unified_sensory()
    wakefulness = await initialize_wakefulness(sensory=sensory)

    # Wakefulness adapts automatically from SituationPhase
    # Or set manually:
    await wakefulness.set_level(WakefulnessLevel.FOCUSED)
"""

from kagami.core.integrations.alert_hierarchy import (
    Alert,
    AlertCategory,
    AlertConfig,
    AlertHierarchy,
    AlertPriority,
    get_alert_hierarchy,
    initialize_alert_hierarchy,
)
from kagami.core.integrations.character_identity import (
    CHARACTER_DIR,
    CharacterProfile,
    compute_face_embedding,
    get_character_profile,
    list_characters,
    load_character_profile,
    load_characters_to_identity_cache,
    sync_character_to_presence,
)
from kagami.core.integrations.contextual_alerts import (
    ESSENTIAL_ITEMS,
    AlertRule,
    ContextDetector,
    ContextualAlertEngine,
    KnownLocation,
    TripContext,
    TripPurpose,
    get_contextual_alert_engine,
    initialize_contextual_alerts,
)
from kagami.core.integrations.identity_detection import (
    find_person_by_name,
    get_detection_stats,
    get_people_home,
    get_person_location,
    initialize_identity_detection,
    is_person_home,
    shutdown_identity_detection,
)
from kagami.core.integrations.organism_physical_bridge import (
    COLONY_ROOM_AFFINITY,
    Colony,
    OrganismPhysicalBridge,
    PhysicalAction,
    RoomAffinity,
    connect_organism_physical_bridge,
    get_organism_physical_bridge,
    reset_organism_physical_bridge,
)
from kagami.core.integrations.presence_service import (
    PresenceCallback,
    PresenceService,
    PresenceSnapshot,
    PresenceState,
    TravelMode,
    get_presence_service,
    initialize_presence_service,
    reset_presence_service,
)
from kagami.core.integrations.semantic_matcher import (
    DEFAULT_MODEL as SEMANTIC_MODEL,
)
from kagami.core.integrations.semantic_matcher import (
    TRIP_PURPOSE_CATEGORIES,
    CategoryDefinition,
    SemanticMatcher,
    get_semantic_matcher,
    reset_semantic_matcher,
)

# NOTE: ClientRegistry has been deprecated in favor of MultiDeviceCoordinator
# from kagami.core.ambient import get_multi_device_coordinator
from kagami.core.integrations.sensorimotor_bridge import (
    SensorimotorBridge,
    WorldModelState,
    get_sensorimotor_bridge,
    initialize_sensorimotor_bridge,
    reset_sensorimotor_bridge,
)
from kagami.core.integrations.signed_identity import (
    IdentityEventSigner,
    SignedIdentityEvent,
    create_signed_identity_event,
    get_identity_event_signer,
)
from kagami.core.integrations.situation_awareness import (
    ActiveEvent,
    EnergyLevel,
    EnvironmentContext,
    HomeContext,
    Projection,
    Situation,
    SituationAwarenessEngine,
    SituationPhase,
    SituationProjection,
    SocialContext,
    TravelContext,
    UrgencyLevel,
    WorkContext,
    get_current_situation,
    get_situation_engine,
    reset_situation_engine,
)
from kagami.core.integrations.situation_orchestrator import (
    AutomationAction,
    PhaseAutomation,
    PhaseTransitionEvent,
    SituationActionOrchestrator,
    get_situation_orchestrator,
    reset_situation_orchestrator,
)
from kagami.core.integrations.system_health import (
    HealthCheckConfig,
    HealthStatus,
    IntegrationHealth,
    IntegrationTier,
    SystemHealthMonitor,
    get_system_health_monitor,
    register_default_health_checks,
    reset_system_health_monitor,
)
from kagami.core.integrations.unified_sensory import (
    CachedSense,
    SenseConfig,
    SenseEventCallback,
    SenseType,
    UnifiedSensoryIntegration,
    get_unified_sensory,
    initialize_unified_sensory,
    reset_unified_sensory,
)
from kagami.core.integrations.visual_perception import (
    CameraState,
    VisualPerceptionPipeline,
    VisualPerceptionState,
    get_visual_perception_pipeline,
    initialize_visual_perception,
    reset_visual_perception,
)
from kagami.core.integrations.wakefulness import (
    WAKEFULNESS_CONFIGS,
    WakefulnessCallback,
    WakefulnessConfig,
    WakefulnessLevel,
    WakefulnessManager,
    get_wakefulness_manager,
    initialize_wakefulness,
    reset_wakefulness_manager,
)
from kagami.core.integrations.world_state import (
    DayType,
    Season,
    TimeContext,
    TimeOfDay,
    TrafficState,
    WeatherForecast,
    WorldSenseType,
    WorldState,
    get_time_context,
    get_world_state,
    reset_world_state,
)

__all__ = [
    # Character Identity Bridge (Jan 2, 2026 - Characters → Identity System)
    "CHARACTER_DIR",
    "COLONY_ROOM_AFFINITY",
    "ESSENTIAL_ITEMS",
    "SEMANTIC_MODEL",
    "TRIP_PURPOSE_CATEGORIES",
    "WAKEFULNESS_CONFIGS",
    "ActiveEvent",
    # Alert Hierarchy (auto-wired to sensory)
    "Alert",
    "AlertCategory",
    "AlertConfig",
    "AlertHierarchy",
    "AlertPriority",
    "AlertRule",
    "AutomationAction",
    "CachedSense",
    # Visual Perception Pipeline (Dec 30, 2025 - Camera → VisionSystem → World Model)
    "CameraState",
    "CategoryDefinition",
    "CharacterProfile",
    # Organism Physical Bridge (Dec 30, 2025 - Autonomous physical actions)
    "Colony",
    "ContextDetector",
    "ContextualAlertEngine",
    "DayType",
    "EnergyLevel",
    "EnvironmentContext",
    "HealthCheckConfig",
    # System Health (Dec 30, 2025) - UNIFIED health monitoring
    "HealthStatus",
    "HomeContext",
    "IdentityEventSigner",
    "IntegrationHealth",
    "IntegrationTier",
    "KnownLocation",
    "OrganismPhysicalBridge",
    "PhaseAutomation",
    "PhaseTransitionEvent",
    "PhysicalAction",
    "PresenceCallback",
    "PresenceService",
    "PresenceSnapshot",
    # Presence Service (Dec 30, 2025 - Phase 3 consolidation)
    "PresenceState",
    "Projection",
    "RoomAffinity",
    "Season",
    # Semantic Matcher (Dec 30, 2025)
    "SemanticMatcher",
    "SenseConfig",
    "SenseEventCallback",
    "SenseType",
    # NOTE: Client devices use MultiDeviceCoordinator from kagami.core.ambient
    # Sensorimotor Bridge (Dec 30, 2025 - Closed loop perception → world model)
    "SensorimotorBridge",
    # Signed Identity Events (Jan 2, 2026 - Ed25519 signed mesh events)
    "SignedIdentityEvent",
    # Situation Awareness (Dec 30, 2025)
    "Situation",
    # Situation Orchestrator (Dec 30, 2025)
    "SituationActionOrchestrator",
    "SituationAwarenessEngine",
    "SituationPhase",
    "SituationProjection",
    "SocialContext",
    "SystemHealthMonitor",
    "TimeContext",
    "TimeOfDay",
    "TrafficState",
    "TravelContext",
    "TravelMode",
    "TripContext",
    # Contextual Alerts (Dec 30, 2025)
    "TripPurpose",
    # Unified Sensory - THE SINGLE SOURCE
    "UnifiedSensoryIntegration",
    "UrgencyLevel",
    "VisualPerceptionPipeline",
    "VisualPerceptionState",
    "WakefulnessCallback",
    "WakefulnessConfig",
    # Wakefulness Manager (Dec 29, 2025)
    "WakefulnessLevel",
    "WakefulnessManager",
    "WeatherForecast",
    "WorkContext",
    "WorldModelState",
    "WorldSenseType",
    # World State (Dec 30, 2025)
    "WorldState",
    "compute_face_embedding",
    "connect_organism_physical_bridge",
    "create_signed_identity_event",
    "find_person_by_name",
    "get_alert_hierarchy",
    "get_character_profile",
    "get_contextual_alert_engine",
    "get_current_situation",
    "get_detection_stats",
    "get_identity_event_signer",
    "get_organism_physical_bridge",
    "get_people_home",
    "get_person_location",
    "get_presence_service",
    "get_semantic_matcher",
    "get_sensorimotor_bridge",
    "get_situation_engine",
    "get_situation_orchestrator",
    "get_system_health_monitor",
    "get_time_context",
    "get_unified_sensory",
    "get_visual_perception_pipeline",
    "get_wakefulness_manager",
    "get_world_state",
    "initialize_alert_hierarchy",
    "initialize_contextual_alerts",
    # Identity Detection (Jan 2, 2026 - Real-time face recognition from cameras)
    "initialize_identity_detection",
    "initialize_presence_service",
    "initialize_sensorimotor_bridge",
    "initialize_unified_sensory",
    "initialize_visual_perception",
    "initialize_wakefulness",
    "is_person_home",
    "list_characters",
    "load_character_profile",
    "load_characters_to_identity_cache",
    "register_default_health_checks",
    "reset_organism_physical_bridge",
    "reset_presence_service",
    "reset_semantic_matcher",
    "reset_sensorimotor_bridge",
    "reset_situation_engine",
    "reset_situation_orchestrator",
    "reset_system_health_monitor",
    "reset_unified_sensory",
    "reset_visual_perception",
    "reset_wakefulness_manager",
    "reset_world_state",
    "shutdown_identity_detection",
    "sync_character_to_presence",
]
