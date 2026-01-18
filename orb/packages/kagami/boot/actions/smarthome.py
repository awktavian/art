"""Smart Home Boot Action - Organism Integration.

🔥 FORGE COLONY MAXIMUM VELOCITY DEPLOYMENT

This module integrates the smart home system directly into the organism boot sequence,
creating a persistent daemon that continuously synchronizes organism state with
physical home expression.

ARCHITECTURE:
- SmartHomeOrganismBridge: Direct organism state → home expression
- Persistent polling: Real-time device state monitoring
- Auto-recovery: Network resilience and reconnection
- Breath expression: Organism breath rhythm → lighting/audio
- Presence feedback: Home sensors → organism awareness

INTEGRATION POINTS:
1. Boot Phase: ORGANISM (after colonies, before API)
2. Organism State: UnifiedOrganismState direct wire
3. Bridge: CrossDomainBridge initialization
4. Persistence: Background task runner for continuous sync

Created: December 29, 2025
Author: Forge Colony / Kagami OS
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from kagami_smarthome import get_smart_home

from kagami.core.boot_mode import require_full_mode

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

    from kagami.core.ambient.cross_domain_bridge import CrossDomainBridge
    from kagami.core.unified_agents.unified_organism_state import UnifiedOrganismState

logger = logging.getLogger(__name__)


class SmartHomeOrganismBridge:
    """Bridge connecting organism consciousness to physical home expression.

    This creates a direct neural pathway from the organism's unified state tensor
    to the smart home's physical actuators, enabling real-time home expression
    of the organism's internal state.

    ORGANISM → HOME MAPPINGS:
    - breath_phase → lighting brightness oscillation
    - active_colony → room lighting color/intensity
    - safety_state → security system alerts
    - social_state → presence-aware automation
    - attention_state → focus lighting in active rooms
    """

    def __init__(
        self,
        smart_home_controller: SmartHomeController,
        organism_state: UnifiedOrganismState | None = None,
        cross_domain_bridge: CrossDomainBridge | None = None,
    ):
        self.smart_home = smart_home_controller
        self.organism_state = organism_state
        self.cross_domain_bridge = cross_domain_bridge

        # State tracking
        self._running = False
        self._last_organism_state = None
        self._last_sync_time = 0.0
        self._sync_interval = 2.0  # 2-second organism expression updates

        # Background tasks
        self._sync_task: asyncio.Task | None = None
        self._monitoring_task: asyncio.Task | None = None

        # Performance
        self._sync_count = 0
        self._error_count = 0

    async def start(self) -> None:
        """Start the organism-home bridge."""
        if self._running:
            logger.warning("SmartHomeOrganismBridge already running")
            return

        logger.info("🏠 Starting SmartHome-Organism bridge...")

        # Initialize smart home controller
        if not self.smart_home._initialized:
            await self.smart_home.initialize()

        # Initialize cross-domain bridge if available
        if self.cross_domain_bridge:
            # CrossDomainBridge is already connected via wiring.py
            pass

        self._running = True

        # Start background tasks
        self._sync_task = asyncio.create_task(self._organism_sync_loop())
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

        logger.info("✅ SmartHome-Organism bridge active")

    async def stop(self) -> None:
        """Stop the bridge and cleanup."""
        if not self._running:
            return

        logger.info("🏠 Stopping SmartHome-Organism bridge...")
        self._running = False

        # Cancel background tasks
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        # Shutdown smart home
        if getattr(self.smart_home, "_running", False):
            await self.smart_home.stop()

        logger.info("✅ SmartHome-Organism bridge stopped")

    async def _organism_sync_loop(self) -> None:
        """Continuously sync organism state to home expression."""
        logger.debug("🧬 Starting organism→home sync loop")

        while self._running:
            try:
                await self._sync_organism_to_home()
                await asyncio.sleep(self._sync_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._error_count += 1
                logger.error(f"Organism sync error: {e}")
                await asyncio.sleep(5.0)  # Error backoff

    async def _monitoring_loop(self) -> None:
        """Monitor smart home health and performance."""
        while self._running:
            try:
                await self._health_check()
                await asyncio.sleep(30.0)  # Health check every 30s
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(30.0)

    async def _sync_organism_to_home(self) -> None:
        """Sync current organism state to home expression.

        Reads from UnifiedOrganismState to express:
        - Breath rhythm through ambient lighting
        - Colony activity through room scenes
        - Safety state through security readiness
        """
        if not self.organism_state:
            return

        try:
            current_time = time.time()

            # Express organism breath rhythm through ambient lighting
            await self._express_breath_rhythm()

            # Express colony activity through room scenes
            await self._express_colony_activity()

            # Express safety state through security readiness
            await self._express_safety_state()

            self._sync_count += 1
            self._last_sync_time = current_time

            if self._sync_count % 30 == 0:  # Log every minute
                logger.debug(
                    f"🧬 Organism sync: {self._sync_count} cycles, {self._error_count} errors"
                )

        except Exception as e:
            self._error_count += 1
            logger.error(f"Organism expression error: {e}")

    async def _express_breath_rhythm(self) -> None:
        """Express organism breath rhythm through subtle lighting.

        DISABLED (Jan 7, 2026): Constant light updates cause flickering!
        Even subtle 5% changes (90-100%) when called frequently create
        visible flicker. The debouncer helps but it's better to not call
        this at all.

        If you want breath-synced lighting, use dedicated smart bulbs
        that support smooth transitions internally (e.g., Philips Hue
        with transition times).
        """
        # DISABLED: Causes flickering even with 5% amplitude
        # The Lutron dimmers don't handle rapid changes smoothly
        pass

    async def _express_colony_activity(self) -> None:
        """Express active colony through room ambiance."""
        # Map active colonies to room characteristics:
        # Spark → warm energizing light
        # Forge → focused task lighting
        # Flow → dynamic flowing scenes
        # Nexus → interconnected zones
        # Beacon → bright guidance lighting
        # Grove → natural ambient tones
        # Crystal → precise clear lighting

        try:
            # Detect active colony from organism state tensor
            self._detect_active_colony()

            # DISABLED (Dec 30, 2025): Auto-scene triggers are too aggressive
            # Scenes should be manual or presence-based only
            # if active_colony == "forge":
            #     await self.smart_home.set_room_scene("Office", "working")
            # elif active_colony == "flow":
            #     await self._optimize_transition_lighting()
            # elif active_colony == "grove":
            #     await self.smart_home.set_room_scene("Living Room", "relaxing")
            pass

        except Exception as e:
            logger.debug(f"Colony expression error: {e}")

    async def _express_safety_state(self) -> None:
        """Express organism safety state through security readiness."""
        try:
            # Monitor h(x) ≥ 0 constraint and adjust security accordingly
            safety_level = self._get_safety_level()  # 0.0 to 1.0

            if safety_level < 0.3:
                # Low safety: enhance security monitoring
                await self._enhance_security_monitoring()
            elif safety_level > 0.8:
                # High safety: optimize for comfort
                await self._optimize_comfort_settings()

        except Exception as e:
            logger.debug(f"Safety expression error: {e}")

    def _detect_active_colony(self) -> str:
        """Detect currently active colony from organism state.

        Reads from UnifiedOrganismState.colony_states tensor to find
        the most active colony based on activation magnitude.

        Colony indices: 0=Spark, 1=Forge, 2=Flow, 3=Nexus, 4=Beacon, 5=Grove, 6=Crystal
        """
        if self.organism_state is None:
            # Fallback to time-based heuristic if no organism state
            hour = time.localtime().tm_hour
            if 9 <= hour <= 17:
                return "forge"
            elif 18 <= hour <= 21:
                return "flow"
            else:
                return "grove"

        try:
            import torch

            # Get colony activations from organism state [B, 7, 64]
            colony_states = self.organism_state.colony_states

            # Compute activation magnitude for each colony
            # colony_states shape: [batch, 7, 64]
            colony_magnitudes = torch.norm(colony_states, dim=-1).squeeze()  # [7]

            # Find most active colony
            active_idx = torch.argmax(colony_magnitudes).item()

            colony_names = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
            return colony_names[int(active_idx)]

        except Exception as e:
            logger.debug(f"Colony detection from organism state failed: {e}")
            # Fallback to time-based
            hour = time.localtime().tm_hour
            if 9 <= hour <= 17:
                return "forge"
            elif 18 <= hour <= 21:
                return "flow"
            else:
                return "grove"

    def _get_safety_level(self) -> float:
        """Get current safety level from organism state.

        Computes h(x) from UnifiedOrganismState.safety_state tensor.
        safety_state = [threat, uncertainty, complexity, risk]
        h(x) = 1.0 - sum(components), clamped to [0, 1]
        """
        if self.organism_state is None:
            return 0.7  # Safe default when no organism state

        try:
            import torch

            # Get safety state from organism [B, 4]
            # Components: [threat, uncertainty, complexity, risk]
            safety_state = self.organism_state.safety_state

            # Compute h(x) = 1.0 - sum(threat + uncertainty + complexity + risk)
            with torch.no_grad():
                components_sum = safety_state.sum(dim=-1).mean().item()
                h_x = max(0.0, min(1.0, 1.0 - components_sum))

            return h_x

        except Exception as e:
            logger.debug(f"Safety level from organism state failed: {e}")
            return 0.7  # Safe fallback

    async def _optimize_transition_lighting(self) -> None:
        """Optimize lighting for smooth room transitions."""
        # DISABLED (Dec 30, 2025): Auto-light changes are too aggressive
        # connected_rooms = ["Kitchen", "Living Room", "Dining Room"]
        # for room in connected_rooms:
        #     await self.smart_home.set_lights(level=60, rooms=[room], fade_time=5.0)
        pass

    async def _enhance_security_monitoring(self) -> None:
        """Enhance security monitoring during low safety periods."""
        # Increase motion sensor sensitivity, ensure doors locked
        await self.smart_home.lock_all()

    async def _optimize_comfort_settings(self) -> None:
        """Optimize settings for comfort during high safety periods."""
        # DISABLED (Dec 30, 2025): Auto-scene triggers are too aggressive
        # Scenes should be manual or presence-based only
        # await self.smart_home.set_room_scene("Living Room", "relaxing")
        pass

    async def _health_check(self) -> None:
        """Check bridge health and smart home connectivity."""
        try:
            # Check smart home integration health
            if not getattr(self.smart_home, "_running", self.smart_home._initialized):
                logger.warning("Smart home controller not running, attempting restart")
                await self.smart_home.initialize()

            # Check integration status
            degraded = self.smart_home._integration_manager.get_degraded_integrations()
            if degraded:
                logger.warning(f"Degraded smart home integrations: {degraded}")

            # Performance metrics
            sync_rate = self._sync_count / max(1, (time.time() - self._last_sync_time + 60))
            error_rate = self._error_count / max(1, self._sync_count)

            logger.debug(f"🏠 Bridge health: {sync_rate:.1f} Hz, {error_rate:.2%} errors")

        except Exception as e:
            logger.error(f"Health check error: {e}")


# Global bridge instance
_bridge_instance: SmartHomeOrganismBridge | None = None


async def startup_smart_home_organism_bridge() -> SmartHomeOrganismBridge:
    """Boot action: Start the smart home organism bridge.

    This initializes the persistent smart home daemon and wires it into
    the organism state system for continuous home expression.

    Returns:
        SmartHomeOrganismBridge instance
    """
    global _bridge_instance

    require_full_mode("SmartHome Organism Bridge")

    if _bridge_instance and _bridge_instance._running:
        logger.info("SmartHome organism bridge already running")
        return _bridge_instance

    logger.info("🔥 FORGE: Initializing SmartHome-Organism bridge...")
    start_time = time.time()

    try:
        # Get smart home controller (singleton)
        smart_home = await get_smart_home()

        # Get organism state (if available)
        organism_state = None
        try:
            # Attempt to get unified organism state for context
            from kagami.core.unified_agents.unified_organism_state import get_unified_consciousness

            organism_state = get_unified_consciousness()
            logger.debug("Successfully retrieved organism state for smart home context")
        except ImportError:
            logger.debug("UnifiedOrganismState not available - continuing without organism context")
        except Exception as e:
            logger.warning(f"Failed to get organism state: {e}")
            # Continue without organism state - smart home should work standalone

        # Get cross-domain bridge (if available)
        cross_domain_bridge = None
        try:
            from kagami.core.ambient.cross_domain_bridge import get_cross_domain_bridge

            cross_domain_bridge = get_cross_domain_bridge()
        except Exception as e:
            logger.debug(f"CrossDomainBridge not available: {e}")

        # Create and start bridge
        bridge = SmartHomeOrganismBridge(
            smart_home_controller=smart_home,
            organism_state=organism_state,
            cross_domain_bridge=cross_domain_bridge,
        )

        await bridge.start()

        _bridge_instance = bridge

        init_time = time.time() - start_time
        logger.info(f"✅ FORGE: SmartHome-Organism bridge ready ({init_time:.2f}s)")
        room_count = len(smart_home.rooms.get_all()) if smart_home._rooms else 0
        logger.info(f"🏠 Managing: {room_count} rooms")

        return bridge

    except Exception as e:
        logger.error(f"❌ FORGE: SmartHome bridge initialization failed: {e}")
        raise


async def shutdown_smart_home_organism_bridge() -> None:
    """Shutdown the smart home organism bridge."""
    global _bridge_instance

    if _bridge_instance:
        await _bridge_instance.stop()
        _bridge_instance = None
        logger.info("SmartHome organism bridge shutdown complete")


# Add missing import for math operations
