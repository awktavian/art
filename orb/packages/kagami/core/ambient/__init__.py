"""Ambient Computing Layer for K os.

Provides always-on, context-aware, multi-device ambient presence.

Core Design Principles:
- Zero UI: No explicit interaction required
- Calm Technology: Information moves between center and periphery
- Anticipatory: Acts before asked
- Multi-modal: Light, sound, haptic expression
- Breath-synchronized: PLAN→EXECUTE→VERIFY rhythm
- Privacy by Design: User controls their data
- Transparency: User can ask "why did that happen?"

Key Components:
- AmbientController: Central orchestrator
- BreathEngine: Breath rhythm generation
- ColonyExpressor: Colony → modality mapping
- SmartHomeController: Control4/Lutron light control (via kagami-smarthome)
- Soundscape: Ambient audio generation
- ContextTracker: Context awareness
- NotificationManager: Peripheral notifications
- MultiDeviceCoordinator: Cross-device sync
- PrivacyManager: Data classification, retention, audit
- ConsentManager: Granular consent management
- ExplainabilityEngine: Decision transparency

Created: November 10, 2025
Updated: December 5, 2025 - Full ambient OS implementation
Updated: December 7, 2025 - Privacy, consent, explainability
"""

# Core controller
# Breath engine
from kagami.core.ambient.breath_engine import (
    BreathConfig,
    BreathEngine,
    get_breath_engine,
)

# Breath manager (January 2026 - extracted from controller)
from kagami.core.ambient.breath_manager import (
    BreathManager,
    BreathManagerConfig,
)

# Colony expression
from kagami.core.ambient.colony_expressor import (
    COLONY_COLORS,
    COLONY_FREQUENCIES,
    ColonyExpressor,
    ExpressionConfig,
    get_colony_expressor,
)

# Consent management (December 7, 2025)
from kagami.core.ambient.consent import (
    ConsentConfig,
    ConsentContext,
    ConsentLevel,
    ConsentManager,
    ConsentRecord,
    get_consent_manager,
)

# Constellation sync (January 2026 - extracted from controller)
from kagami.core.ambient.constellation_sync import (
    ConstellationSync,
    ConstellationSyncConfig,
)

# Context tracking
from kagami.core.ambient.context_tracker import (
    Activity,
    ContextTracker,
    Environment,
    UserContext,
    get_context_tracker,
)
from kagami.core.ambient.controller import (
    AmbientConfig,
    AmbientController,
    get_ambient_controller,
    start_ambient,
    stop_ambient,
)

# Data types
from kagami.core.ambient.data_types import (
    AmbientState,
    BreathPhase,
    BreathState,
    Colony,
    ColonyExpression,
    ColonyState,
    LightState,
    LightZone,
    Modality,
    PresenceLevel,
    PresenceState,
    SafetyState,
    SoundElement,
    SoundLayer,
    SoundscapeConfig,
)

# Explainability (December 7, 2025)
from kagami.core.ambient.explainability import (
    AmbientDecision,
    DecisionType,
    ExplainabilityConfig,
    ExplainabilityEngine,
    TriggerType,
    get_explainability_engine,
)

# Multi-device coordination
from kagami.core.ambient.multi_device_coordinator import (
    Device,
    DeviceSensoryData,
    DeviceStatus,
    DeviceType,
    MultiDeviceCoordinator,
    get_multi_device_coordinator,
)

# Notification management
from kagami.core.ambient.notification_manager import (
    Notification,
    NotificationManager,
    NotificationPriority,
    get_notification_manager,
)

# Presence manager (January 2026 - extracted from controller)
from kagami.core.ambient.presence_manager import (
    PresenceManager,
    PresenceManagerConfig,
)

# Privacy framework (December 7, 2025)
from kagami.core.ambient.privacy import (
    AuditEntry,
    DataCategory,
    DataSensitivity,
    PrivacyConfig,
    PrivacyManager,
    SensorPolicy,
    get_privacy_manager,
)

# SmartHome facade (January 2026 - extracted from controller)
from kagami.core.ambient.smarthome_facade import SmartHomeFacade

# Note: SmartLightBridge deleted Dec 29, 2025
# Lights now controlled via SmartHomeController (kagami-smarthome)
# Soundscape
from kagami.core.ambient.soundscape import (
    SoundGenerator,
    Soundscape,
    get_soundscape,
)

# Symbiote bridge (January 2026 - extracted from controller)
from kagami.core.ambient.symbiote_bridge import SymbioteBridge

# Colony renderer (HAL-based visual output)
from kagami.core.ambient.unified_colony_renderer import (
    ColonyRenderConfig,
    UnifiedColonyRenderer,
)

# Voice interface
from kagami.core.ambient.voice_interface import (
    SpeechRequest,
    UtteranceResult,
    VoiceConfig,
    VoiceInterface,
    VoiceState,
    get_voice_interface,
)

# Wake word detection
from kagami.core.ambient.wake_word import (
    WakeWordDetector,
    WakeWordEvent,
)

# Unified Smart Home Integration (December 29, 2025)
# Theory of Mind driven: UniFi + Control4 + Denon + DSC
# Now provided by kagami-smarthome satellite package
try:
    from kagami_smarthome import (
        ActivityContext,
        Control4Integration,
        DenonIntegration,
        HomeState,
        PresenceEngine,
        PresenceEvent,
        SecurityState,
        SmartHomeConfig,
        SmartHomeController,
        UniFiIntegration,
        get_smart_home,
        get_smart_home_sync,
    )
    from kagami_smarthome import (
        PresenceState as SmartHomePresenceState,  # Avoid collision with data_types.PresenceState
    )

    _SMARTHOME_AVAILABLE = True
except ImportError:
    # kagami-smarthome not installed - define stubs for type checking
    ActivityContext = None  # type: ignore
    Control4Integration = None  # type: ignore
    DenonIntegration = None  # type: ignore
    HomeState = None  # type: ignore
    PresenceEngine = None  # type: ignore
    PresenceEvent = None  # type: ignore
    SmartHomePresenceState = None  # type: ignore
    SecurityState = None  # type: ignore
    SmartHomeConfig = None  # type: ignore
    SmartHomeController = None  # type: ignore
    UniFiIntegration = None  # type: ignore
    get_smart_home = None  # type: ignore
    get_smart_home_sync = None  # type: ignore
    _SMARTHOME_AVAILABLE = False

# CrossDomainBridge (December 30, 2025) - Unified digital-physical bridge
# Consolidates AmbientSmartHomeBridge and ComposioSmartHomeBridge
from kagami.core.ambient.cross_domain_bridge import (
    BridgeConfig,
    CrossDomainBridge,
    CrossDomainTrigger,
    SmartDeviceType,
    UnifiedHomeSnapshot,
    connect_cross_domain_bridge,
    get_cross_domain_bridge,
    reset_cross_domain_bridge,
)

__all__ = [
    "COLONY_COLORS",
    "COLONY_FREQUENCIES",
    "Activity",
    "ActivityContext",
    "AmbientConfig",
    "AmbientController",
    "AmbientDecision",
    "AmbientState",
    "AuditEntry",
    "BreathConfig",
    "BreathEngine",
    "BreathManager",
    "BreathManagerConfig",
    "BreathPhase",
    "BreathState",
    "BridgeConfig",
    "Colony",
    "ColonyExpression",
    "ColonyExpressor",
    "ColonyRenderConfig",
    "ColonyState",
    "ConsentConfig",
    "ConsentContext",
    "ConsentLevel",
    "ConsentManager",
    "ConsentRecord",
    "ConstellationSync",
    "ConstellationSyncConfig",
    "ContextTracker",
    "Control4Integration",
    "CrossDomainBridge",
    "CrossDomainTrigger",
    "DataCategory",
    "DataSensitivity",
    "DecisionType",
    "DenonIntegration",
    "Device",
    "DeviceSensoryData",
    "DeviceStatus",
    "DeviceType",
    "Environment",
    "ExplainabilityConfig",
    "ExplainabilityEngine",
    "ExpressionConfig",
    "HomeState",
    "LightState",
    "LightZone",
    "Modality",
    "MultiDeviceCoordinator",
    "Notification",
    "NotificationManager",
    "NotificationPriority",
    "PresenceEngine",
    "PresenceEvent",
    "PresenceLevel",
    "PresenceManager",
    "PresenceManagerConfig",
    "PresenceState",
    "PrivacyConfig",
    "PrivacyManager",
    "SafetyState",
    "SecurityState",
    "SensorPolicy",
    "SmartDeviceType",
    "SmartHomeConfig",
    "SmartHomeController",
    "SmartHomeFacade",
    "SmartHomePresenceState",
    "SoundElement",
    "SoundGenerator",
    "SoundLayer",
    "Soundscape",
    "SoundscapeConfig",
    "SpeechRequest",
    "SymbioteBridge",
    "TriggerType",
    "UniFiIntegration",
    "UnifiedColonyRenderer",
    "UnifiedDeviceState",
    "UnifiedHomeSnapshot",
    "UserContext",
    "UtteranceResult",
    "VoiceConfig",
    "VoiceInterface",
    "VoiceState",
    "WakeWordDetector",
    "WakeWordEvent",
    "connect_cross_domain_bridge",
    "get_ambient_controller",
    "get_breath_engine",
    "get_colony_expressor",
    "get_consent_manager",
    "get_context_tracker",
    "get_cross_domain_bridge",
    "get_explainability_engine",
    "get_multi_device_coordinator",
    "get_notification_manager",
    "get_privacy_manager",
    "get_smart_home",
    "get_smart_home_sync",
    "get_soundscape",
    "get_voice_interface",
    "reset_cross_domain_bridge",
    "start_ambient",
    "stop_ambient",
]
