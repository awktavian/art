"""Ambient Controller - Central Orchestrator for Ambient OS.

REFACTORED: January 2026 - Decomposed into focused modules

The AmbientController is now a thin orchestrator that delegates to:
- BreathManager: Breath rhythm synchronization
- PresenceManager: Presence detection and adaptation
- ConstellationSync: Multi-device state synchronization
- SymbioteBridge: Theory of Mind integration
- SmartHomeFacade: Smart home operations

Design Principle: ZERO UI
- No explicit interaction required
- Context-aware and anticipatory
- Technology that creates calm (Weiser)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from kagami.core.ambient.breath_engine import BreathEngine, get_breath_engine
from kagami.core.ambient.breath_manager import BreathManager, BreathManagerConfig
from kagami.core.ambient.consent import ConsentManager, get_consent_manager
from kagami.core.ambient.constellation_sync import ConstellationSync, ConstellationSyncConfig
from kagami.core.ambient.data_types import (
    AmbientState,
    BreathPhase,
    BreathState,
    Colony,
    ColonyState,
    PresenceLevel,
    PresenceState,
    SafetyState,
    SoundscapeConfig,
)
from kagami.core.ambient.explainability import (
    DecisionType,
    ExplainabilityEngine,
    TriggerType,
    get_explainability_engine,
)
from kagami.core.ambient.presence_manager import PresenceManager, PresenceManagerConfig
from kagami.core.ambient.privacy import DataCategory, PrivacyManager, get_privacy_manager
from kagami.core.ambient.smarthome_facade import SmartHomeFacade
from kagami.core.ambient.soundscape import Soundscape, get_soundscape
from kagami.core.ambient.symbiote_bridge import SymbioteBridge
from kagami.core.ambient.unified_colony_renderer import ColonyRenderConfig, UnifiedColonyRenderer
from kagami.core.ambient.voice_interface import VoiceInterface

logger = logging.getLogger(__name__)


@dataclass
class AmbientConfig:
    """Ambient controller configuration."""

    # Feature toggles
    enable_lights: bool = True
    enable_sound: bool = True
    enable_haptic: bool = True
    enable_voice: bool = True
    enable_vision: bool = True
    enable_display: bool = True
    enable_world_model: bool = True
    enable_smart_home: bool = True
    enable_constellation: bool = True
    enable_privacy: bool = True
    enable_consent: bool = True
    enable_explainability: bool = True

    # Smart Home credentials (optional)
    unifi_host: str | None = None
    unifi_username: str | None = None
    unifi_password: str | None = None
    control4_host: str | None = None
    control4_bearer_token: str | None = None
    denon_host: str | None = None
    known_devices: list[str] | None = None

    # Constellation
    constellation_sync_interval_s: float = 2.0

    # Privacy & Consent
    require_consent_for_audio: bool = True
    require_consent_for_video: bool = True
    require_consent_for_location: bool = True

    # Accessibility
    accessibility_mode: bool = False
    accessibility_announce_changes: bool = True
    accessibility_slow_transitions: bool = True
    accessibility_transition_ms: int = 2000

    # Breath settings
    breath_bpm: float = 6.0

    # Light settings
    light_breath_sync: bool = False
    light_colony_reactive: bool = True
    light_base_brightness: float = 0.3
    light_breath_sync_interval: float = 10.0

    # Sound settings
    sound_master_volume: float = 0.2
    sound_breath_sync: bool = True

    # Voice settings
    voice_wake_word: str = "kagami"
    voice_wake_word_enabled: bool = True
    voice_continuous_listen: bool = False

    # Presence detection
    presence_idle_timeout_s: float = 300.0
    presence_sleep_hours: tuple[int, int] = (23, 7)

    # Safety
    safety_visual_enabled: bool = True
    safety_audio_enabled: bool = True


class AmbientController:
    """Central controller for ambient computing.

    Orchestrates all ambient subsystems to create a unified
    presence that expresses Kagami's state without demanding attention.
    """

    def __init__(self, config: AmbientConfig | None = None):
        """Initialize ambient controller."""
        self.config = config or AmbientConfig()

        # Managers (extracted modules)
        self._breath_manager = BreathManager(
            BreathManagerConfig(
                breath_bpm=self.config.breath_bpm,
                light_breath_sync=self.config.light_breath_sync,
                light_base_brightness=self.config.light_base_brightness,
                light_breath_sync_interval=self.config.light_breath_sync_interval,
                sound_breath_sync=self.config.sound_breath_sync,
            )
        )
        self._presence_manager = PresenceManager(
            PresenceManagerConfig(
                idle_timeout_s=self.config.presence_idle_timeout_s,
                sleep_hours=self.config.presence_sleep_hours,
                sound_master_volume=self.config.sound_master_volume,
            )
        )
        self._constellation_sync = ConstellationSync(
            ConstellationSyncConfig(
                sync_interval_s=self.config.constellation_sync_interval_s,
                enabled=self.config.enable_constellation,
            )
        )
        self._symbiote_bridge = SymbioteBridge()
        self._smarthome_facade = SmartHomeFacade()

        # Core subsystems
        self._breath: BreathEngine | None = None
        self._colony_renderer: UnifiedColonyRenderer | None = None
        self._soundscape: Soundscape | None = None
        self._haptic: Any = None
        self._voice: VoiceInterface | None = None

        # Privacy and explainability
        self._privacy: PrivacyManager | None = None
        self._consent: ConsentManager | None = None
        self._explainability: ExplainabilityEngine | None = None

        # State
        self._state = AmbientState(
            breath=BreathState(
                phase=BreathPhase.REST,
                phase_progress=0.0,
                cycle_count=0,
                bpm=self.config.breath_bpm,
                intensity=0.5,
            ),
            colonies={},
            safety=SafetyState(
                h_value=1.0,
                x_threat=0.0,
                x_uncertainty=0.0,
                x_complexity=0.0,
                x_risk=0.0,
                gradient=(0.0, 0.0, 0.0, 0.0),
            ),
            presence=PresenceState(
                level=PresenceLevel.PERIPHERAL,
                confidence=0.5,
                attention_target=None,
                activity_type=None,
                location=None,
            ),
            lights=[],
            soundscape=SoundscapeConfig(elements=[]),
        )

        # Control
        self._initialized = False
        self._running = False
        self._main_loop_task: asyncio.Task | None = None

        # Statistics
        self._stats: dict[str, Any] = {}

    async def initialize(self) -> bool:
        """Initialize all ambient subsystems."""
        if self._initialized:
            return True

        logger.info("Initializing Ambient Controller...")

        # Initialize breath engine
        self._breath = await get_breath_engine()
        self._breath_manager.connect_breath_engine(self._breath)
        self._breath_manager.set_state_callback(self._update_breath_state)

        # Initialize colony renderer
        render_config = ColonyRenderConfig(
            width=800, height=480, enable_ambient_mode=True, emit_to_hal=True, emit_to_agui=True
        )
        self._colony_renderer = UnifiedColonyRenderer(render_config)
        await self._colony_renderer.initialize()
        self._breath_manager.connect_colony_renderer(self._colony_renderer)
        self._presence_manager.connect_colony_renderer(self._colony_renderer)

        # Initialize soundscape
        if self.config.enable_sound:
            try:
                self._soundscape = await get_soundscape()
                self._soundscape.set_volume(self.config.sound_master_volume)
                self._breath_manager.connect_soundscape(self._soundscape)
                self._presence_manager.connect_soundscape(self._soundscape)
            except Exception as e:
                logger.warning(f"Soundscape unavailable: {e}")

        # Initialize haptic
        if self.config.enable_haptic:
            try:
                from kagami_hal.adapters.common.haptic import get_haptic_controller_async

                self._haptic = await get_haptic_controller_async()
                self._breath_manager.connect_haptic(self._haptic)
            except Exception as e:
                logger.warning(f"Haptic unavailable: {e}")

        # Initialize voice interface
        if self.config.enable_voice:
            try:
                from kagami.core.ambient.voice_interface import VoiceConfig, VoiceInterface

                voice_config = VoiceConfig(
                    wake_word=self.config.voice_wake_word,
                    wake_word_enabled=self.config.voice_wake_word_enabled,
                    continuous_mode=self.config.voice_continuous_listen,
                    enable_vision=self.config.enable_vision,
                )
                self._voice = VoiceInterface(voice_config)
                await self._voice.initialize()
                self._voice.on_utterance(self._on_voice_input)
                self._voice.on_wake_word(self._on_wake_word)
                self._breath_manager.connect_voice(self._voice)
                self._smarthome_facade.set_voice(self._voice)
            except Exception as e:
                logger.warning(f"Voice interface unavailable: {e}")

        # Initialize privacy and consent
        if self.config.enable_privacy:
            try:
                self._privacy = await get_privacy_manager()
            except Exception as e:
                logger.warning(f"Privacy manager unavailable: {e}")

        if self.config.enable_consent:
            try:
                self._consent = get_consent_manager()
                self._consent.on_consent_change(self._on_consent_change)
                self._consent.on_pause_change(self._on_pause_change)
                self._constellation_sync.set_consent(self._consent)
            except Exception as e:
                logger.warning(f"Consent manager unavailable: {e}")

        if self.config.enable_explainability:
            try:
                self._explainability = get_explainability_engine()
                self._presence_manager.connect_explainability(self._explainability)
            except Exception as e:
                logger.warning(f"Explainability engine unavailable: {e}")

        # Initialize constellation coordinator
        if self.config.enable_constellation:
            try:
                from kagami.core.ambient.multi_device_coordinator import (
                    get_multi_device_coordinator,
                )

                coordinator = await get_multi_device_coordinator()
                self._constellation_sync.set_coordinator(coordinator)
                self._constellation_sync.set_state_source(self._state)
                self._breath_manager.set_constellation_sync(self._constellation_sync.sync)
                self._presence_manager.set_constellation_sync(self._constellation_sync.sync)
            except Exception as e:
                logger.warning(f"Constellation coordinator unavailable: {e}")

        # Initialize Symbiote
        try:
            from kagami.core.symbiote import get_symbiote_module

            symbiote = get_symbiote_module()
            self._symbiote_bridge.set_symbiote(symbiote)
        except Exception as e:
            logger.debug(f"Symbiote connection deferred: {e}")

        # Initialize UnifiedSensory integration
        try:
            from kagami.core.integrations import get_unified_sensory

            unified_sensory = get_unified_sensory()
            unified_sensory.on_sense_change(self._presence_manager.on_sense_event)
        except Exception as e:
            logger.debug(f"UnifiedSensory subscription deferred: {e}")

        # Initialize Smart Home
        if self.config.enable_smart_home:
            try:
                from kagami_smarthome import get_smart_home

                smart_home = await get_smart_home()
                self._smarthome_facade.set_smart_home(smart_home)
                self._breath_manager.connect_smart_home(smart_home)
                self._presence_manager.connect_smart_home(smart_home)

                if smart_home and getattr(smart_home, "_initialized", False):
                    devices = smart_home.get_devices()
                    logger.info(
                        f"Smart Home available: "
                        f"{len(devices.get('lights', {}))} lights, "
                        f"{len(devices.get('audio_zones', {}))} audio zones"
                    )

                    # Connect CrossDomainBridge
                    try:
                        from kagami.core.ambient.cross_domain_bridge import (
                            BridgeConfig,
                            get_cross_domain_bridge,
                        )

                        bridge_config = BridgeConfig(
                            colony_scene_mapping=True,
                            presence_scene_triggers=True,
                        )
                        bridge = get_cross_domain_bridge()
                        bridge.config = bridge_config
                        self._smarthome_facade.set_bridge(bridge)
                    except Exception as e:
                        logger.debug(f"CrossDomainBridge not available: {e}")
            except ImportError:
                logger.debug("kagami_smarthome not installed")
            except Exception as e:
                logger.warning(f"Smart Home unavailable: {e}")

        self._initialized = True
        logger.info("Ambient Controller ready")
        return True

    async def start(self) -> None:
        """Start ambient operation."""
        if self._running:
            return

        if not self._initialized:
            await self.initialize()

        self._running = True

        if self._breath:
            await self._breath.start()
        if self._colony_renderer:
            await self._colony_renderer.start()
        if self._soundscape:
            await self._soundscape.start()
        if self._voice:
            await self._voice.start()

        from kagami.core.async_utils import safe_create_task

        self._main_loop_task = safe_create_task(
            self._main_loop(),
            name="ambient_controller",
            error_callback=lambda e: logger.error(f"Ambient controller error: {e}"),
        )
        logger.info("Ambient Controller started")

    async def stop(self) -> None:
        """Stop ambient operation."""
        self._running = False

        if self._main_loop_task:
            self._main_loop_task.cancel()
        if self._breath:
            await self._breath.stop()
        if self._colony_renderer:
            await self._colony_renderer.stop()
        if self._soundscape:
            await self._soundscape.stop()
        if self._voice:
            await self._voice.stop()

        logger.info("Ambient Controller stopped")

    async def shutdown(self) -> None:
        """Shutdown all subsystems."""
        await self.stop()

        bridge = self._smarthome_facade.get_bridge()
        if bridge:
            await bridge.stop()

        smart_home = self._smarthome_facade.get_smart_home()
        if smart_home:
            await smart_home.stop()

        self._initialized = False
        logger.info("Ambient Controller shutdown")

    # =========================================================================
    # State Updates
    # =========================================================================

    def _update_breath_state(self, breath: BreathState) -> None:
        """Update breath state from manager."""
        self._state.breath = breath

    def update_colony_states(self, states: dict[Colony, ColonyState]) -> None:
        """Update colony states from world model."""
        self._state.colonies = states
        if self._colony_renderer:
            self._colony_renderer.update_colonies(states)

    def update_safety(self, safety: SafetyState) -> None:
        """Update safety barrier state."""
        prev_safe = self._state.safety.is_safe
        self._state.safety = safety

        if self._colony_renderer:
            self._colony_renderer.update_safety(safety.h_value)

        if prev_safe and not safety.is_safe:
            asyncio.create_task(self._express_safety_alert())
            asyncio.create_task(self._constellation_sync.sync(force=True))

    def update_presence(self, presence: PresenceState) -> None:
        """Update user presence state."""
        self._presence_manager.update_presence(presence)
        self._state.presence = presence

    def sync_to_receipt(self, phase: str, correlation_id: str | None = None) -> None:
        """Sync breath to receipt phase."""
        self._breath_manager.sync_to_receipt(phase)

    # =========================================================================
    # Symbiote Integration
    # =========================================================================

    def set_symbiote(self, symbiote: Any) -> None:
        """Connect Symbiote module for Theory of Mind."""
        self._symbiote_bridge.set_symbiote(symbiote)

    async def observe_user_presence(
        self, user_id: str, presence: PresenceState, context: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Observe user presence via Symbiote."""
        return await self._symbiote_bridge.observe_user_presence(user_id, presence, context)

    async def get_user_intent_inference(self, user_id: str) -> dict[str, Any]:
        """Get Symbiote's inference about user intent."""
        return await self._symbiote_bridge.get_intent_inference(user_id)

    async def should_proactively_assist(
        self, user_id: str, presence: PresenceState | None = None
    ) -> tuple[bool, str | None]:
        """Check if system should proactively assist."""
        return await self._symbiote_bridge.should_proactively_assist(user_id, presence)

    # =========================================================================
    # Voice Interface
    # =========================================================================

    async def speak(self, text: str, colony: Colony | None = None, interrupt: bool = False) -> bool:
        """Speak text through voice interface."""
        if not self._voice:
            return False
        return await self._voice.speak(text, colony=colony, interrupt=interrupt)

    async def listen(self, timeout: float = 10.0) -> str | None:
        """Listen for voice input."""
        if not self._voice:
            return None
        result = await self._voice.listen(timeout=timeout)
        return result.text if result else None

    async def capture_vision(self) -> dict[str, Any] | None:
        """Capture current visual scene."""
        if not self._voice:
            return None
        return await self._voice.capture_vision()

    async def _on_voice_input(self, utterance: Any) -> None:
        """Handle voice input from user."""
        text = utterance.text if hasattr(utterance, "text") else str(utterance)
        logger.info(f"Voice input: {text}")
        self._state.presence = PresenceState(
            level=PresenceLevel.ENGAGED,
            confidence=0.9,
            attention_target="voice_input",
            activity_type="speaking",
            location=None,
        )

    async def _on_wake_word(self) -> None:
        """Handle wake word detection."""
        logger.info("Wake word detected!")
        if self._haptic:
            await self._haptic.notification()
        smart_home = self._smarthome_facade.get_smart_home()
        if smart_home and getattr(smart_home, "_initialized", False):
            await smart_home.set_lights(80)
            await asyncio.sleep(0.3)
            await smart_home.set_lights(int(self.config.light_base_brightness * 100))

    # =========================================================================
    # Smart Home
    # =========================================================================

    async def capture_home_state(self) -> dict[str, Any]:
        """Capture complete home state snapshot."""
        return await self._smarthome_facade.capture_home_state(self._state)

    async def capture_state_delta(self) -> dict[str, Any]:
        """Capture only changes since last snapshot."""
        return await self._smarthome_facade.capture_state_delta()

    async def apply_colony_scene(self, colony: Colony, room_name: str) -> bool:
        """Apply a scene to a room based on colony state."""
        return await self._smarthome_facade.apply_colony_scene(colony, room_name)

    async def trigger_presence_scene(
        self, presence: PresenceLevel | None = None, location: str | None = None
    ) -> None:
        """Trigger appropriate scenes based on presence level."""
        level = presence or self._state.presence.level
        await self._smarthome_facade.trigger_presence_scene(level, location)

    def get_smarthome_bridge(self) -> Any:
        """Get the CrossDomainBridge instance."""
        return self._smarthome_facade.get_bridge()

    def get_cross_domain_bridge(self) -> Any:
        """Get the CrossDomainBridge instance (alias)."""
        return self._smarthome_facade.get_bridge()

    def get_smart_home(self) -> Any:
        """Get the SmartHomeController instance."""
        return self._smarthome_facade.get_smart_home()

    async def announce(
        self,
        text: str,
        rooms: list[str] | None = None,
        volume: int | None = None,
        colony: Colony | str = "kagami",
    ) -> bool:
        """Announce a message to specific rooms."""
        return await self._smarthome_facade.announce(text, rooms, volume, colony)

    async def announce_all(
        self,
        text: str,
        volume: int | None = None,
        colony: Colony | str = "beacon",
        exclude_rooms: list[str] | None = None,
    ) -> bool:
        """Announce a message to all rooms."""
        return await self._smarthome_facade.announce_all(text, volume, colony, exclude_rooms)

    async def speak_to_room(self, room: str, text: str, colony: Colony | str = "kagami") -> bool:
        """Speak to a specific room with colony voice."""
        return await self._smarthome_facade.speak_to_room(room, text, colony)

    def get_audio_rooms(self) -> list[str]:
        """Get list of rooms with audio capability."""
        return self._smarthome_facade.get_audio_rooms()

    # =========================================================================
    # Privacy & Consent
    # =========================================================================

    def _on_consent_change(self, category: DataCategory, level: Any) -> None:
        """Handle consent change."""
        logger.info(f"Consent changed: {category.value} -> {level.value}")
        if self._explainability:
            self._explainability.log_decision(
                decision_type=DecisionType.OTHER,
                trigger_type=TriggerType.USER_COMMAND,
                trigger_details=f"User changed consent for {category.value}",
                reasoning=f"Consent set to {level.value}",
                effect=f"{category.value} sensing {'enabled' if level.value.startswith('granted') else 'disabled'}",
                reversible=True,
            )

    def _on_pause_change(self, paused: bool) -> None:
        """Handle pause state change."""
        logger.info(f"Ambient sensing {'paused' if paused else 'resumed'}")
        if self._explainability:
            self._explainability.log_decision(
                decision_type=DecisionType.PAUSE if paused else DecisionType.RESUME,
                trigger_type=TriggerType.USER_COMMAND,
                trigger_details="User toggled ambient pause",
                reasoning="User requested " + ("pause" if paused else "resume"),
                effect="All ambient sensing " + ("paused" if paused else "resumed"),
                reversible=True,
            )

    async def pause_ambient(self, duration_minutes: float = 30, reason: str = "") -> None:
        """Pause all ambient sensing."""
        if self._consent:
            await self._consent.pause_ambient(duration_minutes, reason)

    async def resume_ambient(self) -> None:
        """Resume ambient sensing."""
        if self._consent:
            await self._consent.resume_ambient()

    def is_paused(self) -> bool:
        """Check if ambient is paused."""
        return self._consent.is_paused if self._consent else False

    def has_consent(self, category: DataCategory) -> bool:
        """Check if consent granted for a data category."""
        if not self._consent:
            return True
        return self._consent.has_consent(category)

    def get_active_sensors(self) -> list[dict[str, Any]]:
        """Get list of sensors with active consent."""
        return self._consent.get_active_sensors() if self._consent else []

    def get_sensor_indicator(self) -> dict[str, Any]:
        """Get visual indicator for active sensors."""
        if self._consent:
            return self._consent.get_sensor_indicator()
        return {"status": "unknown", "color": "gray", "active_count": 0}

    def get_privacy_preferences(self) -> dict[str, Any]:
        """Get privacy preferences for settings UI."""
        return self._consent.get_preferences() if self._consent else {}

    # =========================================================================
    # Explainability
    # =========================================================================

    def explain(self, question: str) -> str:
        """Answer a question about ambient behavior."""
        if self._explainability:
            return self._explainability.explain_question(question)
        return "Explainability not enabled."

    def explain_last(self, count: int = 3, verbose: bool = False) -> list[str]:
        """Explain the last N ambient decisions."""
        return self._explainability.explain_last(count, verbose) if self._explainability else []

    def get_decision_dashboard(self) -> dict[str, Any]:
        """Get explainability dashboard data."""
        return self._explainability.get_dashboard() if self._explainability else {}

    # =========================================================================
    # Accessibility
    # =========================================================================

    def set_accessibility_mode(self, enabled: bool) -> None:
        """Enable or disable accessibility mode."""
        self.config.accessibility_mode = enabled
        logger.info(f"Accessibility mode: {'enabled' if enabled else 'disabled'}")
        if self._explainability:
            self._explainability.log_decision(
                decision_type=DecisionType.OTHER,
                trigger_type=TriggerType.USER_COMMAND,
                trigger_details="Accessibility mode toggled",
                reasoning=f"User {'enabled' if enabled else 'disabled'} accessibility mode",
                effect="Transitions will be " + ("slower" if enabled else "normal"),
                reversible=True,
            )

    # =========================================================================
    # Main Loop
    # =========================================================================

    async def _main_loop(self) -> None:
        """Main ambient update loop."""
        logger.info("Ambient main loop started")

        while self._running:
            try:
                self._state.timestamp = time.time()

                if self._colony_renderer:
                    frame = await self._colony_renderer.render_frame()
                    await self._colony_renderer.stream_to_hal(frame)

                if not self._state.safety.is_safe:
                    await self._express_safety_alert()

                await self._constellation_sync.sync()
                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ambient loop error: {e}", exc_info=True)
                await asyncio.sleep(1.0)

        logger.info("Ambient main loop stopped")

    async def _express_safety_alert(self) -> None:
        """Express safety alert through ambient modalities."""
        safety = self._state.safety
        if not safety.is_safe:
            logger.warning(f"Safety barrier breached: h(x) = {safety.h_value:.3f}")
            smart_home = self._smarthome_facade.get_smart_home()
            if smart_home and getattr(smart_home, "_initialized", False):
                await smart_home.set_lights(100)
                await smart_home.set_audio(0)
            if self._haptic:
                await self._haptic.alert()

    # =========================================================================
    # Public API
    # =========================================================================

    def get_state(self) -> AmbientState:
        """Get current ambient state."""
        return self._state

    def get_stats(self) -> dict[str, Any]:
        """Get ambient statistics."""
        stats = {
            **self._breath_manager.get_stats(),
            **self._presence_manager.get_stats(),
            **self._constellation_sync.get_stats(),
            "initialized": self._initialized,
            "running": self._running,
            "breath_bpm": self._state.breath.bpm,
            "breath_cycle": self._state.breath.cycle_count,
            "presence_level": self._state.presence.level.value,
            "safety_h": self._state.safety.h_value,
            "active_colonies": len(self._state.colonies),
        }

        if self._voice:
            voice_stats = self._voice.get_stats()
            stats["voice_state"] = voice_stats.get("state", "unavailable")
            stats["voice_speaking"] = self._voice.is_speaking
            stats["voice_listening"] = self._voice.is_listening

        bridge = self._smarthome_facade.get_bridge()
        if bridge:
            stats["smarthome_bridge"] = bridge.get_stats()
            stats["smart_home_connected"] = True
        else:
            stats["smart_home_connected"] = self._smarthome_facade.is_connected

        return stats

    @property
    def is_running(self) -> bool:
        """Check if controller is running."""
        return self._running


# =============================================================================
# Global Instance
# =============================================================================

_AMBIENT_CONTROLLER: AmbientController | None = None


def set_ambient_controller(controller: AmbientController | None) -> None:
    """Set the global ambient controller instance."""
    global _AMBIENT_CONTROLLER
    _AMBIENT_CONTROLLER = controller


async def get_ambient_controller() -> AmbientController:
    """Get global ambient controller instance."""
    global _AMBIENT_CONTROLLER
    if _AMBIENT_CONTROLLER is None:
        _AMBIENT_CONTROLLER = AmbientController()
        await _AMBIENT_CONTROLLER.initialize()
    return _AMBIENT_CONTROLLER


async def start_ambient() -> AmbientController:
    """Start the ambient system."""
    controller = await get_ambient_controller()
    await controller.start()
    return controller


async def stop_ambient() -> None:
    """Stop the ambient system."""
    if _AMBIENT_CONTROLLER:
        await _AMBIENT_CONTROLLER.shutdown()
        set_ambient_controller(None)
