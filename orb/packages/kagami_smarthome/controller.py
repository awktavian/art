"""Unified Smart Home Controller — Slim Facade (Under 500 LOC).

This is the refactored controller that delegates to specialized services
and managers. The original controller.py (4000+ LOC) has been decomposed into:
- IntegrationManager: Discovery, reconnection, health, failover
- StateManager: Home state, presence, organism state
- Domain Services: DeviceService, AVService, ClimateService, etc.

This file serves as the unified facade for backward compatibility.

Architecture:
- Room-Centric: Each room is a first-class citizen
- Service-Oriented: Domain logic in specialized services
- Manager-Delegated: Infrastructure in managers

Created: January 2, 2026
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from kagami_smarthome.advanced_automation import AdvancedAutomationManager

# Security infrastructure
from kagami_smarthome.core.integration_manager import IntegrationManager
from kagami_smarthome.core.state_manager import StateManager
from kagami_smarthome.failover_manager import FailoverManager
from kagami_smarthome.integration_pool import IntegrationPool
from kagami_smarthome.performance_monitor import PerformanceMonitor
from kagami_smarthome.polling_stub import AdaptivePollingManager
from kagami_smarthome.presence import PresenceEngine
from kagami_smarthome.services import (
    AutomationService,
    AVService,
    ClimateService,
    DeviceService,
    FindMyService,
    HealthService,
    OeloService,
    PresenceService,
    RoomService,
    SceneService,
    SecurityService,
    TeslaService,
    VisitorService,
    WorkshopService,
)
from kagami_smarthome.types import HomeState, SmartHomeConfig

if TYPE_CHECKING:
    from kagami_smarthome.discovery import DeviceDiscovery
    from kagami_smarthome.orchestrator import RoomOrchestrator
    from kagami_smarthome.room import RoomRegistry

logger = logging.getLogger(__name__)


class SmartHomeController:
    """Unified smart home controller — slim facade pattern.

    Delegates all operations to specialized services and managers.
    This reduces the controller from 4000+ LOC to <500 LOC.

    Usage:
        controller = SmartHomeController(config)
        await controller.initialize()
        await controller.set_lights(50, rooms=["Living Room"])
    """

    def __init__(self, config: SmartHomeConfig | None = None) -> None:
        """Initialize controller with config."""
        self.config = config or SmartHomeConfig()

        # Performance infrastructure
        self._performance_monitor = PerformanceMonitor()
        self._integration_pool = IntegrationPool(self._performance_monitor)
        self._failover_manager = FailoverManager(self._performance_monitor)
        self._adaptive_polling = AdaptivePollingManager(self._performance_monitor)

        # Managers (infrastructure)
        self._integration_manager = IntegrationManager(
            self.config,
            self._performance_monitor,
            self._integration_pool,
            self._failover_manager,
            self._adaptive_polling,
        )

        # Presence engine
        self._presence = PresenceEngine(config)

        # State manager
        self._state_manager = StateManager(self._presence)

        # Domain services (initialized empty, wired after integrations connect)
        # Track automation-initiated changes for CBF (shared with device service)
        self._automation_initiated_changes: set[int] = set()
        self._device_service = DeviceService(automation_tracker=self._automation_initiated_changes)
        self._av_service = AVService()
        self._climate_service = ClimateService()
        self._security_service = SecurityService()
        self._tesla_service = TeslaService()
        self._oelo_service = OeloService()
        self._workshop_service = WorkshopService()
        self._health_service = HealthService()
        self._findmy_service = FindMyService()
        self._presence_service = PresenceService()
        self._scene_service = SceneService()
        self._room_service = RoomService()
        self._automation_service = AutomationService()
        self._visitor_service = VisitorService()

        # Room-centric components (set after initialization)
        self._rooms: RoomRegistry | None = None
        self._orchestrator: RoomOrchestrator | None = None
        self._initialized = False

        # Advanced automation (celestial shades, predictive HVAC, sleep optimization)
        self._advanced_automation: AdvancedAutomationManager | None = None

        # Event-driven boot: callbacks and background tasks
        self._on_ready_callbacks: list[tuple[str | None, Any]] = []
        self._background_tasks: list[asyncio.Task] = []

    # =========================================================================
    # Initialization — EVENT-DRIVEN, NON-BLOCKING
    # =========================================================================

    def on_integration_ready(self, callback: Any, integration_name: str | None = None) -> None:
        """Register callback for when an integration becomes ready.

        Args:
            callback: Async function(name, integration) called when ready
            integration_name: Specific integration to watch, or None for any
        """
        self._on_ready_callbacks.append((integration_name, callback))

        # If already connected, fire immediately
        if integration_name:
            integration = self._integration_manager.get_integration(integration_name)
            if integration:
                asyncio.create_task(self._fire_callback(callback, integration_name, integration))

    async def _fire_callback(self, callback: Any, name: str, integration: Any) -> None:
        """Fire a single callback safely."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(name, integration)
            else:
                callback(name, integration)
        except Exception as e:
            logger.error(f"Integration ready callback failed: {e}")

    async def _notify_integration_ready(self, name: str, integration: Any) -> None:
        """Notify all registered callbacks that an integration is ready."""
        for filter_name, callback in self._on_ready_callbacks:
            if filter_name is None or filter_name == name:
                await self._fire_callback(callback, name, integration)

    async def initialize(self) -> bool:
        """Initialize controller — INSTANT, NON-BLOCKING.

        Returns immediately. Integrations connect in background.
        Use on_integration_ready() to get notified when integrations connect.

        Returns:
            True (always succeeds, integrations connect async)
        """
        if self._initialized:
            return True

        start = time.monotonic()

        # Validate location configuration at startup
        self._validate_location_config()

        # Mark initialized IMMEDIATELY — controller is usable
        self._initialized = True

        # Fire off ALL background tasks (no awaiting, no blocking)
        self._background_tasks = [
            asyncio.create_task(self._connect_all_integrations()),
            asyncio.create_task(self._integration_manager.discover_devices()),
        ]

        elapsed = (time.monotonic() - start) * 1000
        logger.info(f"✅ SmartHomeController ready in {elapsed:.0f}ms (integrations connecting...)")
        return True

    async def wait_for_integration(self, name: str, timeout: float = 10.0) -> bool:
        """Wait for a specific integration to connect.

        Use this when you need to ensure an integration is ready before proceeding.
        Most operations should use on_integration_ready() instead.

        Args:
            name: Integration name (e.g., "control4", "denon")
            timeout: Max seconds to wait

        Returns:
            True if integration connected, False if timeout
        """
        # Already connected?
        if self._integration_manager.get_integration(name):
            return True

        # Wait with polling
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if self._integration_manager.get_integration(name):
                return True
            await asyncio.sleep(0.1)

        return False

    async def wait_for_core(self, timeout: float = 5.0) -> bool:
        """Wait for core integrations (Control4) to connect.

        Convenience method for operations that need Control4.

        Returns:
            True if Control4 connected, False if timeout
        """
        return await self.wait_for_integration("control4", timeout)

    def _validate_location_config(self) -> None:
        """Validate location configuration at startup.

        Logs the configured location and warns if using defaults.
        This ensures all subsystems have consistent coordinates.
        """
        try:
            from kagami.core.config.location_config import (
                get_home_location,
                validate_location_consistency,
            )

            location = get_home_location()
            validation = validate_location_consistency()

            # Log the configured location
            if validation["is_default"]:
                logger.info(
                    f"📍 Location: {location.name} ({location.latitude:.4f}, {location.longitude:.4f}) "
                    f"[DEFAULT — set KAGAMI_HOME_LAT/LON for portable deployment]"
                )
            else:
                logger.info(
                    f"📍 Location: {location.name} ({location.latitude:.4f}, {location.longitude:.4f}) "
                    f"[from {validation['source']}]"
                )

            # Log any validation issues
            if validation["issues"]:
                for issue in validation["issues"]:
                    logger.warning(f"📍 Location issue: {issue}")

        except Exception as e:
            logger.warning(f"📍 Could not validate location config: {e}")

    async def _connect_all_integrations(self) -> None:
        """Connect all integrations in background, fire callbacks on success."""
        from kagami_smarthome.integrations.control4 import Control4Integration
        from kagami_smarthome.integrations.denon import DenonIntegration
        from kagami_smarthome.integrations.eight_sleep import EightSleepIntegration
        from kagami_smarthome.integrations.lg_tv import LGTVIntegration
        from kagami_smarthome.integrations.samsung_tv import SamsungTVIntegration
        from kagami_smarthome.integrations.tesla import TeslaIntegration
        from kagami_smarthome.integrations.unifi import UniFiIntegration

        # Integration definitions: (class, timeout, critical)
        # Critical integrations get retries, optional ones don't
        integrations = {
            "control4": (Control4Integration, 5.0, True),
            "unifi": (UniFiIntegration, 5.0, True),
            "denon": (DenonIntegration, 3.0, True),
            "tesla": (TeslaIntegration, 3.0, False),
            "lg_tv": (LGTVIntegration, 2.0, False),
            "samsung_tv": (SamsungTVIntegration, 2.0, False),
            "eight_sleep": (EightSleepIntegration, 2.0, False),
        }

        async def connect_one(name: str, cls: type, timeout: float, critical: bool) -> None:
            """Connect single integration with timeout, no blocking."""
            try:
                integration = cls(self.config)
                success = await asyncio.wait_for(integration.connect(), timeout=timeout)

                if success:
                    self._integration_manager.register_integration(name, integration)
                    logger.info(f"✅ {name}")
                    await self._notify_integration_ready(name, integration)

                    # Wire services when key integrations connect
                    if name == "control4":
                        self._wire_services()
                        await self._build_room_registry()
                    elif name == "unifi":
                        asyncio.create_task(self._start_presence_detection())

            except TimeoutError:
                if critical:
                    logger.warning(f"⚠️  {name} timeout")
            except Exception as e:
                if critical:
                    logger.warning(f"⚠️  {name}: {e}")

        # Fire ALL connections simultaneously — no waiting
        await asyncio.gather(
            *[
                connect_one(name, cls, timeout, critical)
                for name, (cls, timeout, critical) in integrations.items()
            ],
            return_exceptions=True,
        )

        # Start health monitoring after initial connections
        asyncio.create_task(self._integration_manager.start_health_monitoring())

        # Start automatic reconnection loop for critical integrations (Jan 4, 2026)
        asyncio.create_task(self._auto_reconnect_loop(integrations))

    async def _auto_reconnect_loop(self, integrations: dict[str, tuple[type, float, bool]]) -> None:
        """Auto-reconnect failed critical integrations.

        Runs every 60 seconds, checks for disconnected critical integrations,
        and attempts to reconnect them with exponential backoff.

        This ensures Kagami recovers from temporary network issues,
        Control4 token expiry, etc. without manual intervention.

        Created: January 4, 2026 — Resiliency improvement
        """
        # Track consecutive failures per integration for backoff
        failure_counts: dict[str, int] = {}
        base_interval = 60  # Check every 60 seconds

        while True:
            await asyncio.sleep(base_interval)

            try:
                for name, (cls, timeout, critical) in integrations.items():
                    if not critical:
                        continue  # Only auto-reconnect critical integrations

                    integration = self._integration_manager.get_integration(name)

                    # Check if integration needs reconnection
                    needs_reconnect = False
                    if (
                        integration is None
                        or hasattr(integration, "is_connected")
                        and not integration.is_connected
                        or hasattr(integration, "_initialized")
                        and not integration._initialized
                    ):
                        needs_reconnect = True

                    if needs_reconnect:
                        # Exponential backoff: skip if we've failed recently
                        failures = failure_counts.get(name, 0)
                        if failures > 0:
                            # Wait 2^failures intervals before retry (max 32 intervals = ~32 min)
                            skip_intervals = min(2**failures, 32)
                            failure_counts[name] = failures  # Keep count, will decrement on success
                            if failures % skip_intervals != 0:
                                continue  # Skip this cycle

                        logger.info(f"🔄 Auto-reconnecting {name}...")

                        try:
                            new_integration = cls(self.config)
                            success = await asyncio.wait_for(
                                new_integration.connect(), timeout=timeout * 2
                            )

                            if success:
                                self._integration_manager.register_integration(
                                    name, new_integration
                                )
                                logger.info(f"✅ {name} reconnected")
                                failure_counts[name] = 0  # Reset on success

                                # Re-wire services if Control4 reconnected
                                if name == "control4":
                                    self._wire_services()
                                    await self._build_room_registry()

                                await self._notify_integration_ready(name, new_integration)
                            else:
                                failure_counts[name] = failures + 1
                                logger.warning(
                                    f"⚠️  {name} reconnect failed (attempt {failures + 1})"
                                )

                        except TimeoutError:
                            failure_counts[name] = failures + 1
                            logger.warning(f"⚠️  {name} reconnect timeout")
                        except Exception as e:
                            failure_counts[name] = failures + 1
                            logger.warning(f"⚠️  {name} reconnect error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-reconnect loop error: {e}")

    def _wire_services(self) -> None:
        """Wire services to integrations."""
        control4 = self._integration_manager.get_integration("control4")
        denon = self._integration_manager.get_integration("denon")
        lg_tv = self._integration_manager.get_integration("lg_tv")
        samsung_tv = self._integration_manager.get_integration("samsung_tv")
        tesla = self._integration_manager.get_integration("tesla")

        # Wire device service
        self._device_service.set_control4(control4)

        # Wire AV service
        self._av_service.set_integrations(
            control4=control4, denon=denon, lg_tv=lg_tv, samsung_tv=samsung_tv
        )

        # Wire Tesla service
        if tesla:
            self._tesla_service.set_integration(tesla)
            logger.info("✅ Tesla service wired")

        # Wire Resident Override CBF to Control4 events
        # This protects manual device changes from automation override
        self._wire_resident_override_cbf(control4)

        # Wire Home Theater Voice Service to Denon
        # Enables voice input when "Mac" input is selected on Control4 remote
        self._wire_home_theater_voice(denon)

        # Start advanced automation (celestial shades, predictive HVAC, etc.)
        self._start_advanced_automation()

        logger.info("✅ Services wired to integrations")

    def _start_advanced_automation(self) -> None:
        """Start advanced automation features after services are wired."""
        if self._advanced_automation is None:
            self._advanced_automation = AdvancedAutomationManager(self)
            asyncio.create_task(self._advanced_automation.start())
            logger.info("☀️ Advanced automation started (celestial shades, HVAC, sleep)")

    def _wire_resident_override_cbf(self, control4: Any) -> None:
        """Wire Control4 events to ResidentOverrideCBF.

        When a device change is detected that wasn't initiated by Kagami,
        record it as a manual change. This creates a cooldown during which
        automation won't override the resident's intent.

        h(x) >= 0 always.
        """
        if not control4:
            return

        from kagami_smarthome.resident_override_cbf import get_resident_override_cbf

        cbf = get_resident_override_cbf()

        async def on_control4_event(
            item_id: int,
            var_name: str,
            old_value: Any,
            new_value: Any,
        ) -> None:
            """Handle Control4 device change events.

            Called for ALL device changes (manual, automation, scheduled).
            Only record to CBF if NOT initiated by Kagami automation.
            """
            # Skip if this was an automation-initiated change
            if item_id in self._automation_initiated_changes:
                self._automation_initiated_changes.discard(item_id)
                return

            # Determine device type from Control4 item metadata
            device_type = self._get_device_type_for_item(item_id, control4)
            if device_type is None:
                return  # Unknown device type, skip

            # Only track Level changes (lights/shades)
            if var_name != "Level":
                return

            # Record as manual change
            cbf.record_manual_change(
                device_id=item_id,
                device_type=device_type,
                old_value=old_value,
                new_value=new_value,
                source="resident",
            )

        # Wire to Control4 WebSocket events if available
        if hasattr(control4, "_ws") and control4._ws:
            control4._ws.on_event(on_control4_event)
            logger.info("✅ ResidentOverrideCBF wired to Control4 events")
        else:
            logger.debug("Control4 WebSocket not available, CBF wiring deferred")

    def _get_device_type_for_item(self, item_id: int, control4: Any) -> Any:
        """Determine DeviceType for a Control4 item ID."""
        from kagami_smarthome.resident_override_cbf import DeviceType

        # Check if it's a light
        if hasattr(control4, "_lights") and item_id in control4._lights:
            return DeviceType.LIGHT

        # Check if it's a shade
        if hasattr(control4, "_shades") and item_id in control4._shades:
            return DeviceType.SHADE

        # Check if it's the fireplace
        if hasattr(control4, "_fireplace_id") and item_id == control4._fireplace_id:
            return DeviceType.FIREPLACE

        return None

    def _wire_home_theater_voice(self, denon: Any) -> None:
        """Wire Home Theater Voice Service to Denon integration.

        Enables voice input through the Mac Studio microphone when the "Mac"
        input is selected on the Control4 remote (via Denon AVR).

        Security Model:
        - Physical presence authentication: selecting the input on the Control4
          remote proves the user is physically present in the home
        - Local network only: the voice endpoints only accept local requests
        - Equivalent to caller ID auth in phone answering machine

        Args:
            denon: Denon integration instance.
        """
        if not denon:
            logger.debug("Denon not available, home theater voice disabled")
            return

        async def start_voice_service() -> None:
            """Start voice service in background."""
            try:
                from kagami.core.services.voice.home_theater_voice import (
                    get_home_theater_voice,
                )

                voice_service = await get_home_theater_voice()
                voice_service.set_denon(denon)

                # Start monitoring Denon input selection
                success = await voice_service.start()
                if success:
                    logger.info("🎙️ Home Theater Voice Service wired to Denon")
                else:
                    logger.warning("Home Theater Voice Service failed to start")

            except ImportError as e:
                logger.debug(f"Home Theater Voice dependencies not available: {e}")
            except Exception as e:
                logger.warning(f"Home Theater Voice Service error: {e}")

        # Start in background to not block boot
        asyncio.create_task(start_voice_service())

    async def _build_room_registry(self) -> None:
        """Build room registry from Control4 data."""
        from kagami_smarthome.room import RoomRegistry

        control4 = self._integration_manager.get_integration("control4")
        if control4:
            # Extract discovered items from Control4 integration
            rooms = getattr(control4, "_rooms", {})
            lights = getattr(control4, "_lights", {})
            shades = getattr(control4, "_shades", {})
            audio_zones = getattr(control4, "_audio_zones", {})

            self._rooms = RoomRegistry.from_control4(rooms, lights, shades, audio_zones)
            self._state_manager.set_rooms(self._rooms)
            logger.info(f"✅ Room registry built: {len(self._rooms._rooms)} rooms")

    async def _start_presence_detection(self) -> None:
        """Start UniFi event stream for WiFi presence detection.

        Connects UniFi WiFi events to PresenceEngine for arrival detection.
        When a known device connects after being away, triggers welcome home.
        """
        unifi = self._integration_manager.get_integration("unifi")
        if not unifi:
            logger.warning("UniFi not available, presence detection disabled")
            return

        # Wire arrival callback to welcome home
        self._presence.on_arrival(self._on_owner_arrival)

        # Wire UniFi events to presence engine
        unifi.on_event(self._presence.process_event)

        # Start event stream (WebSocket preferred for low latency)
        await unifi.start_event_stream(prefer_websocket=True)
        logger.info("✅ WiFi presence detection started")

    async def _on_owner_arrival(self) -> None:
        """Handle owner arrival — trigger welcome home sequence."""
        logger.info("🏠 Owner arrived home — triggering welcome sequence")
        await self.welcome_home()

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> None:
        """Start controller (alias for initialize)."""
        await self.initialize()

    async def stop(self) -> None:
        """Stop controller and clean up."""
        # Stop advanced automation first
        if self._advanced_automation:
            await self._advanced_automation.stop()

        await self._integration_manager.stop_health_monitoring()
        await self._integration_manager.stop_optimization_services()

        # Disconnect integrations
        for name in ["control4", "unifi", "denon", "lg_tv", "samsung_tv"]:
            integration = self._integration_manager.get_integration(name)
            if integration and hasattr(integration, "disconnect"):
                await integration.disconnect()

        logger.info("SmartHomeController stopped")

    async def __aenter__(self) -> SmartHomeController:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.stop()

    # =========================================================================
    # Device Control (Delegates to DeviceService)
    # =========================================================================

    async def set_lights(
        self,
        level: int,
        rooms: list[str] | None = None,
        respect_cbf: bool = True,
        source: str = "controller",
    ) -> bool:
        """Set lighting level.

        Args:
            level: Light level 0-100
            rooms: Rooms to affect (None = all)
            respect_cbf: If True, respect manual override cooldowns (h(x) >= 0)
            source: Source identifier for logging/CBF tracking
        """
        return await self._device_service.set_lights(
            level, rooms, respect_cbf=respect_cbf, source=source
        )

    async def set_shades(self, level: int, rooms: list[str] | None = None) -> bool:
        """Set shade position."""
        return await self._device_service.set_shades(level, rooms)

    async def open_shades(self, rooms: list[str] | None = None) -> bool:
        """Open shades."""
        return await self._device_service.open_shades(rooms)

    async def close_shades(self, rooms: list[str] | None = None) -> bool:
        """Close shades."""
        return await self._device_service.close_shades(rooms)

    async def optimize_shades_celestial(self) -> list:
        """Optimize all shades based on sun position and window geometry.

        This is THE main adaptive shade function. Call it:
        - Every 30 min during daylight
        - At sunrise/sunset
        - When presence changes

        Returns:
            List of ShadeOptimization results
        """
        return await self._device_service.optimize_shades_celestial()

    async def get_shade_status(self) -> dict:
        """Get shade status with celestial context."""
        return await self._device_service.get_shade_optimization_status()

    async def fireplace_on(self) -> bool:
        """Turn fireplace on."""
        return await self._device_service.fireplace_on()

    async def fireplace_off(self) -> bool:
        """Turn fireplace off."""
        return await self._device_service.fireplace_off()

    async def raise_tv(self) -> bool:
        """Raise TV mount."""
        return await self._device_service.raise_tv()

    async def lower_tv(self, preset: int = 1) -> bool:
        """Lower TV mount to preset."""
        return await self._device_service.lower_tv(preset)

    # =========================================================================
    # AV Control (Delegates to AVService)
    # =========================================================================

    async def set_audio(
        self, volume: int, room: str | None = None, source: str | None = None
    ) -> bool:
        """Set audio volume."""
        return await self._av_service.set_audio(volume, room, source)

    async def mute_room(self, room: str, mute: bool = True) -> bool:
        """Mute room audio."""
        return await self._av_service.mute_room(room, mute)

    async def tv_on(self) -> bool:
        """Turn TV on."""
        return await self._av_service.tv_on()

    async def tv_off(self) -> bool:
        """Turn TV off."""
        return await self._av_service.tv_off()

    async def enter_movie_mode(self) -> None:
        """Enter movie mode."""
        await self._av_service.enter_movie_mode()

    async def exit_movie_mode(self) -> None:
        """Exit movie mode."""
        await self._av_service.exit_movie_mode()

    def is_movie_mode(self) -> bool:
        """Check if in movie mode."""
        return self._av_service.is_movie_mode()

    # =========================================================================
    # Security (Delegates to SecurityService)
    # =========================================================================

    async def lock_all(self) -> bool:
        """Lock all doors."""
        return await self._security_service.lock_all()

    async def unlock_door(self, door: str) -> bool:
        """Unlock specific door."""
        return await self._security_service.unlock_door(door)

    # =========================================================================
    # Scenes (Delegates to SceneService)
    # =========================================================================

    async def goodnight(self) -> bool:
        """Execute goodnight routine."""
        return await self._scene_service.goodnight()

    async def welcome_home(self) -> bool:
        """Execute welcome home routine."""
        return await self._scene_service.welcome_home()

    async def movie_mode(self) -> bool:
        """Enter movie mode scene."""
        return await self._scene_service.movie_mode()

    # =========================================================================
    # Announcements (Delegates to RoomService)
    # =========================================================================

    async def announce(self, text: str, rooms: list[str] | None = None) -> bool:
        """Announce to specific rooms."""
        return await self._room_service.announce(text, rooms)

    async def announce_all(self, text: str) -> bool:
        """Announce to all rooms."""
        return await self._room_service.announce_all(text)

    # NOTE: play_audio() removed - voice output now uses UnifiedVoiceEffector
    # from kagami.core.effectors.voice import speak, VoiceTarget
    # await speak("Hello", target=VoiceTarget.HOME_ROOM, rooms=["Living Room"])

    # =========================================================================
    # State (Delegates to StateManager)
    # =========================================================================

    def get_state(self) -> HomeState:
        """Get current home state."""
        return self._state_manager.get_state()

    def get_home_state(self) -> HomeState:
        """Get home state (alias)."""
        return self._state_manager.get_home_state()

    def get_room_states(self) -> dict[str, dict[str, Any]]:
        """Get all room states."""
        return self._state_manager.get_room_states()

    def get_organism_state(self) -> dict[str, Any]:
        """Get organism state."""
        return self._state_manager.get_organism_state()

    def update_organism_state(self, key: str, value: Any) -> None:
        """Update organism state."""
        self._state_manager.update_organism_state(key, value)

    # =========================================================================
    # Presence (Delegates to StateManager)
    # =========================================================================

    def get_owner_location(self) -> str | None:
        """Get owner location."""
        return self._state_manager.get_owner_location()

    def is_owner_home(self) -> bool:
        """Check if owner is home."""
        return self._state_manager.is_owner_home()

    def get_occupied_rooms(self) -> list[str]:
        """Get occupied rooms."""
        return self._state_manager.get_occupied_rooms()

    def get_presence_state(self) -> dict[str, Any]:
        """Get presence state."""
        return self._state_manager.get_presence_state()

    def is_anyone_in_bed(self) -> bool:
        """Check if anyone is in bed.

        Returns:
            True if anyone is in bed (via Eight Sleep)
        """
        return self._climate_service.is_anyone_in_bed()

    # =========================================================================
    # Properties for Backward Compatibility
    # =========================================================================

    @property
    def presence(self) -> PresenceEngine:
        """Get presence engine."""
        return self._presence

    @property
    def rooms(self) -> RoomRegistry:
        """Get room registry."""
        if not self._rooms:
            raise RuntimeError("Controller not initialized")
        return self._rooms

    @property
    def discovery(self) -> DeviceDiscovery | None:
        """Get device discovery."""
        return self._integration_manager.discovery

    @property
    def device_service(self) -> DeviceService:
        """Get device service."""
        return self._device_service

    @property
    def av_service(self) -> AVService:
        """Get AV service."""
        return self._av_service

    @property
    def climate_service(self) -> ClimateService:
        """Get climate service."""
        return self._climate_service

    @property
    def security_service(self) -> SecurityService:
        """Get security service."""
        return self._security_service

    @property
    def tesla_service(self) -> TeslaService:
        """Get Tesla service."""
        return self._tesla_service

    # =========================================================================
    # Integration Access (for advanced use)
    # =========================================================================

    def get_integration_status(self) -> dict[str, bool]:
        """Get integration connection status.

        Returns status for all integrations:
        - control4: Primary home automation (includes August locks)
        - unifi: Network/cameras/presence
        - denon: AV receiver
        - tesla: Vehicle
        - lg_tv: Living room TV
        - samsung_tv: Secondary TV (if present)
        - eight_sleep: Bed presence/temperature
        """
        status: dict[str, bool] = {}
        integrations = [
            "control4",
            "unifi",
            "denon",
            "tesla",
            "lg_tv",
            "samsung_tv",
            "eight_sleep",
        ]
        for name in integrations:
            integration = self._integration_manager.get_integration(name)
            if integration is None:
                status[name] = False
            else:
                # Check various connection indicators
                is_connected = (
                    getattr(integration, "is_connected", False)
                    or getattr(integration, "_initialized", False)
                    or hasattr(integration, "_session")
                )
                status[name] = is_connected
        return status

    def get_integration_health(self) -> dict[str, Any]:
        """Get integration health summary."""
        return {
            "degraded": self._integration_manager.get_degraded_integrations(),
            "status": self.get_integration_status(),
        }

    def get_resolved_ips(self) -> dict[str, str | None]:
        """Get resolved device IPs."""
        return self._integration_manager.resolved_ips


# Factory function
_controller_instance: SmartHomeController | None = None


async def get_smart_home(config: SmartHomeConfig | None = None) -> SmartHomeController:
    """Get or create the smart home controller singleton.

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        SmartHomeController instance
    """
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = SmartHomeController(config)
        await _controller_instance.initialize()
    return _controller_instance


__all__ = ["SmartHomeController", "get_smart_home"]
