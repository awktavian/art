"""Wiring actions for boot process.

Actions that connect subsystems together:
- Orchestrator + production systems
- World model + ambient controller
- Brain + stigmergy
- Learning systems coordination
- Background tasks + autonomous orchestration
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any

# OPTIMIZED (Dec 28, 2025): Defer torch import to avoid 966ms module-level cost
# torch is imported lazily inside functions that need it
from kagami.boot.actions.init import _should_enable_loader

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


async def startup_orchestrator(app: FastAPI) -> None:
    """Initialize intent orchestrator and unified organism.

    OPTIMIZED (Dec 28, 2025): Split into fast + deferred phases.
    - Fast phase (~500ms): Orchestrator + ProductionSystems + basic wiring
    - Deferred phase (background): Organism, Symbiote, Cost, Ambient, World Model
    """
    from kagami.boot.model_loader import get_model_loader_state
    from kagami.core.orchestrator import IntentOrchestrator
    from kagami.core.production_systems_coordinator import ProductionSystemsCoordinator

    try:
        # ===== FAST PHASE: Essential wiring only =====
        loader_state = get_model_loader_state()
        await loader_state.initialize()
        app.state.model_loader_state = loader_state

        orchestrator = IntentOrchestrator()
        await orchestrator.initialize()

        production_systems = ProductionSystemsCoordinator()
        await production_systems.initialize()
        production_systems.wire_to_orchestrator(orchestrator)
        app.state.production_systems = production_systems
        app.state.orchestrator = orchestrator
        app.state.kagami_intelligence = orchestrator

        # Tools integration (optional, non-blocking)
        try:
            from kagami.core.tools_integration import get_kagami_tools_integration

            tools_integration = get_kagami_tools_integration()
            await tools_integration.initialize()
            app.state.kagami_tools_integration = tools_integration
        except (ImportError, RuntimeError, AttributeError):
            app.state.kagami_tools_integration = None

        # Mark orchestrator ready BEFORE heavy initialization
        app.state.fractal_organism = True  # Health check flag
        logger.debug("Orchestrator fast phase complete")

        # ===== DEFERRED PHASE: Heavy initialization in background =====
        async def _deferred_orchestrator_init() -> None:
            """Heavy orchestrator initialization (organism, models, etc.)."""
            try:
                await _init_organism(app, orchestrator, production_systems, loader_state)
            except Exception as e:
                logger.error(f"Deferred orchestrator init failed: {e}")

        from kagami.core.async_utils import safe_create_task

        safe_create_task(_deferred_orchestrator_init(), name="deferred_orchestrator")

        logger.info("✅ Orchestrator ready (heavy components loading in background)")

    except Exception as e:
        import traceback

        logger.error(f"❌ Orchestrator init failed: {type(e).__name__}: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        raise


async def _init_organism(
    app: Any,
    orchestrator: Any,
    production_systems: Any,
    loader_state: Any,
) -> None:
    """Initialize UnifiedOrganism and heavy components (runs in background).

    OPTIMIZED (Dec 28, 2025): Run all sub-tasks in parallel.
    - Model loading starts immediately (don't wait for organism)
    - Symbiote, Cost, Cognitive, Ambient all run in parallel
    - Homeostasis sync is non-blocking
    """
    import time

    start = time.time()
    from kagami.core.unified_agents import UnifiedOrganism, set_unified_organism
    from kagami.core.unified_agents.unified_organism import OrganismConfig

    # Start model loading FIRST (most expensive, don't wait for anything)
    model_task = asyncio.create_task(
        _parallel_load_all_systems(app, orchestrator, production_systems, loader_state)
    )

    # Create organism (fast - just object creation)
    organism_config = OrganismConfig(homeostasis_interval=60.0)
    organism = UnifiedOrganism(config=organism_config)

    # Start organism in parallel with other init
    organism_task = asyncio.create_task(organism.start())

    # Run ALL subsystem inits in parallel (no dependencies between them)
    await asyncio.gather(
        organism_task,  # Organism.start()
        _init_symbiote(app, organism),  # Theory of Mind
        _init_cost_module(app, organism),  # Cost module
        _init_cognitive_systems(app, organism),  # Background tasks
        _init_unified_sensory(app, organism),  # Unified sensory bus (Dec 29, 2025)
        _init_ambient(app, organism),  # Ambient controller
        _init_homeostasis_sync(app, organism),  # Distributed sync
        _init_distributed_consensus(app),  # Byzantine consensus (Jan 4, 2026)
        # auto_triggers deleted - all notifications through curator now (Jan 5, 2026)
        _init_slack_bridge(app, organism),  # Bidirectional Slack (realtime + bridge) (Jan 5, 2026)
        return_exceptions=True,  # Don't fail if one fails
    )

    # Set organism as global after start completes
    set_unified_organism(organism)
    app.state.unified_organism = organism
    app.state.organism_ready = True

    # Wait for model loading to complete
    await model_task

    elapsed = time.time() - start
    logger.info(f"✅ Full organism init complete ({elapsed:.1f}s)")


async def _init_homeostasis_sync(app: Any, organism: Any) -> None:
    """Wire homeostasis sync (optional, non-blocking)."""
    try:
        from kagami.core.consensus.homeostasis_sync import get_homeostasis_sync

        homeostasis_sync = await get_homeostasis_sync(organism=organism, instance_id=None)
        app.state.homeostasis_sync = homeostasis_sync
        if hasattr(organism, "_homeostasis_monitor") and organism._homeostasis_monitor:
            organism._homeostasis_monitor.set_distributed_sync(homeostasis_sync)
    except Exception:
        app.state.homeostasis_sync = None


async def _init_distributed_consensus(app: Any) -> None:
    """Initialize Byzantine fault-tolerant distributed consensus (Jan 4, 2026).

    This wires:
    - CriticalPBFTCoordinator for safety/security operations
    - ServiceRegistry for node discovery and health
    - CrossHubCRDTManager for eventually consistent state
    - MeshHomeostasisBridge for hub synchronization

    PBFT is used for CRITICAL operations only (security, safety).
    CRDTs are used for eventually consistent state (presence, preferences).
    """
    import os

    # PBFT Coordinator (critical operations)
    try:
        from kagami.core.consensus import (
            PBFTConfig,
            get_critical_pbft_coordinator,
            get_pbft_node,
        )

        # Get PBFT configuration from environment
        cluster_size = int(os.getenv("PBFT_CLUSTER_SIZE", "4"))
        byzantine_tolerance = int(os.getenv("PBFT_BYZANTINE_TOLERANCE", "1"))

        pbft_config = PBFTConfig(
            n=cluster_size,
            f=byzantine_tolerance,
        )

        # Initialize PBFT node
        pbft_node = await get_pbft_node(config=pbft_config)
        app.state.pbft_node = pbft_node

        # Initialize Critical PBFT Coordinator
        pbft_coordinator = get_critical_pbft_coordinator()
        await pbft_coordinator.initialize()
        app.state.pbft_coordinator = pbft_coordinator

        logger.info(f"✅ PBFT Consensus initialized (n={cluster_size}, f={byzantine_tolerance})")
    except Exception as e:
        logger.debug(f"PBFT Consensus deferred: {e}")
        app.state.pbft_node = None
        app.state.pbft_coordinator = None

    # Service Registry (node discovery)
    try:
        from kagami.core.cluster import ServiceType, get_service_registry

        registry = await get_service_registry()
        # Registry is already started by get_service_registry()

        # Register this API node
        node_id = os.getenv("KAGAMI_NODE_ID", f"api-{os.getpid()}")
        service_type_str = os.getenv("KAGAMI_SERVICE_TYPE", "api")
        service_type = (
            ServiceType(service_type_str)
            if service_type_str in ServiceType.__members__
            else ServiceType.API
        )

        import socket

        await registry.register(
            service_type=service_type,
            node_id=node_id,
            hostname=socket.gethostname(),
            address=os.getenv("API_ADDRESS", "0.0.0.0"),
            port=int(os.getenv("API_PORT", "8001")),
            capabilities=["api", "consensus"],
        )

        app.state.service_registry = registry
        logger.info(f"✅ ServiceRegistry initialized (node={node_id})")
    except Exception as e:
        logger.debug(f"ServiceRegistry deferred: {e}")
        app.state.service_registry = None

    # Cross-Hub CRDT Manager (eventually consistent state)
    try:
        from kagami.core.coordination import get_cross_hub_crdt_manager

        node_id = os.getenv("KAGAMI_NODE_ID", f"api-{os.getpid()}")
        crdt_manager = await get_cross_hub_crdt_manager(node_id=node_id)
        app.state.crdt_manager = crdt_manager
        logger.info("✅ CrossHubCRDT initialized")
    except Exception as e:
        logger.debug(f"CrossHubCRDT deferred: {e}")
        app.state.crdt_manager = None

    # Mesh Homeostasis Bridge (hub synchronization)
    try:
        from kagami.core.consensus import get_mesh_homeostasis_bridge

        mesh_bridge = get_mesh_homeostasis_bridge()
        await mesh_bridge.initialize()
        app.state.mesh_homeostasis_bridge = mesh_bridge
        logger.info("✅ MeshHomeostasisBridge initialized")
    except Exception as e:
        logger.debug(f"MeshHomeostasisBridge deferred: {e}")
        app.state.mesh_homeostasis_bridge = None


async def _init_auto_triggers(app: Any) -> None:
    """Initialize Nash-optimal cross-service auto-triggers (Jan 5, 2026).

    This starts the circulatory system's heartbeat:
    - Polls GitHub, Gmail, Linear, Figma, Calendar, Todoist for events
    - Routes events through Nash-equilibrium optimized triggers
    - Executes cross-service actions (CI fail → Linear + Slack)

    THE ORGANISM'S HEARTBEAT - without this, triggers are DORMANT.
    """
    try:
        from kagami.core.events.unified_e8_bus import get_unified_bus
        from kagami.core.orchestration.auto_triggers import (  # type: ignore[import-not-found]
            get_auto_trigger_orchestrator,
        )

        # Get orchestrator and start polling
        orchestrator = await get_auto_trigger_orchestrator()
        await orchestrator.start_polling()

        # Wire to E8 bus for event distribution
        bus = get_unified_bus()

        # Subscribe to trigger events for monitoring
        async def _trigger_event_handler(event):
            """Log trigger events for observability."""
            logger.debug(f"🎯 Trigger event: {event.topic} → {event.payload.get('target_service')}")

        bus.subscribe("trigger.*", _trigger_event_handler)

        app.state.auto_triggers = orchestrator
        app.state.auto_triggers_ready = True

        status = orchestrator.get_status()
        logger.info(
            f"✅ AutoTriggers started: {status['enabled_triggers']} triggers, "
            f"polling {len([i for i, v in orchestrator._poll_intervals.items() if v > 0])} services"
        )
    except Exception as e:
        logger.debug(f"AutoTriggers deferred: {e}")
        app.state.auto_triggers = None
        app.state.auto_triggers_ready = False


async def _init_slack_bridge(app: Any, organism: Any) -> None:
    """Initialize Slack integration with full Markov blanket handler.

    Architecture:
        Slack WebSocket → SlackRealtime → Markov Handler → Organism
                                                ↓
                                    Plan → Execute → Verify → Respond

    Single integration point with full preamble + tools.
    """
    try:
        from kagami.core.integrations.slack_realtime import start_slack_integration

        # Get E8 bus from app state
        e8_bus = getattr(app.state, "e8_bus", None)
        realtime = await start_slack_integration(organism, e8_bus)
        app.state.slack_realtime = realtime
        app.state.slack_ready = True

        logger.info("✅ Slack Markov blanket active (full preamble + tools)")
    except Exception as e:
        logger.debug(f"Slack integration deferred: {e}")
        app.state.slack_realtime = None
        app.state.slack_ready = False


async def _init_symbiote(app: Any, organism: Any) -> None:
    """Initialize Symbiote module (Theory of Mind)."""
    try:
        from kagami.core.symbiote import SymbioteConfig, SymbioteModule, set_symbiote_module

        symbiote_config = SymbioteConfig(
            max_agent_models=32,
            social_surprise_weight=0.3,
            social_cbf_weight=0.2,
        )
        symbiote = SymbioteModule(config=symbiote_config)
        set_symbiote_module(symbiote)
        app.state.symbiote_module = symbiote
        organism.set_symbiote_module(symbiote)

        # Wire to Active Inference
        try:
            from kagami.core.active_inference.engine import get_active_inference_engine

            ai_engine = get_active_inference_engine()
            ai_engine.set_symbiote_module(symbiote)
        except Exception:
            pass

        # Initialize Social CBF
        try:
            from kagami.core.safety.cbf_init import initialize_social_cbf

            social_cbf = initialize_social_cbf(symbiote)
            if social_cbf:
                app.state.social_cbf = social_cbf
        except Exception:
            pass

    except Exception as e:
        logger.debug(f"Symbiote init skipped: {e}")
        app.state.symbiote_module = None


async def _init_cost_module(app: Any, organism: Any) -> None:
    """Initialize Cost module (LeCun architecture)."""
    import torch  # Lazy import

    try:
        from kagami.core.rl.unified_cost_module import CostModuleConfig, get_cost_module

        cost_config = CostModuleConfig(state_dim=512, action_dim=64, ic_weight=0.6, tc_weight=0.4)
        cost_module = get_cost_module(cost_config)
        app.state.cost_module = cost_module
        organism._cost_module = cost_module

        # Pre-warm synchronously (fast, ~10ms)
        try:
            device = cost_module.intrinsic_cost.safety_detector[0].weight.device
            device_str = str(device) if device is not None else "cpu"
            dummy_state = torch.randn(1, 512, device=device_str)
            dummy_action = torch.randn(1, 64, device=device_str)
            with torch.no_grad():
                for _ in range(2):  # 2 passes instead of 3
                    _ = cost_module(dummy_state, dummy_action)
        except Exception:
            pass

    except Exception as e:
        logger.debug(f"Cost module init skipped: {e}")
        app.state.cost_module = None


async def _init_cognitive_systems(app: Any, organism: Any) -> None:
    """Initialize cognitive coordination systems (background tasks)."""
    try:
        from kagami.core.config.feature_flags import get_feature_flags

        _research = get_feature_flags().research
    except Exception:
        _research = None

    # Continuous Mind (always-on autonomous reasoning)
    try:
        from kagami.core.continuous.continuous_mind import ContinuousMind

        continuous_mind = ContinuousMind()
        organism._continuous_mind = continuous_mind
        asyncio.create_task(continuous_mind.run_forever())
    except Exception:
        pass

    # Continuous Evolution (opt-in)
    if _research and getattr(_research, "enable_continuous_evolution", False):
        try:
            from kagami.core.evolution.continuous_evolution_engine import ContinuousEvolutionEngine

            evolution = ContinuousEvolutionEngine()
            await evolution.initialize()
            organism._evolution_engine = evolution
            asyncio.create_task(evolution.start())
        except Exception:
            pass

    # Self-Healing (opt-in)
    if _research and getattr(_research, "enable_self_healing", False):
        try:
            from kagami.core.resilience.selfhealing_system import SelfHealingSystem

            healing = SelfHealingSystem()
            organism._self_healing = healing
            asyncio.create_task(healing.start())
        except Exception:
            pass

    # Periodic Reflection (opt-in)
    if _research and getattr(_research, "enable_periodic_reflection", False):
        try:
            from kagami.core.debugging.manager import start_periodic_reflection_loop

            asyncio.create_task(start_periodic_reflection_loop(interval_seconds=600))
        except Exception:
            pass


async def _init_unified_sensory(app: Any, organism: Any) -> None:
    """Initialize UnifiedSensory (THE SINGLE source for all sensory data).

    CRITICAL (Dec 29, 2025): All sensory data flows through UnifiedSensory.
    Other components SUBSCRIBE to events, they do NOT poll directly.

    Wires:
    - AlertHierarchy for auto-alerts
    - OrganismConsciousness for perception updates
    - ComposioSmartHomeBridge for cross-domain triggers
    - WakefulnessManager for adaptive polling (NEW Dec 29, 2025)
    - SituationAwarenessEngine for comprehensive situation understanding (NEW Dec 30, 2025)
    - SystemHealthMonitor for health tracking and self-healing (NEW Dec 30, 2025)
    - SensorimotorBridge for closed-loop world model (NEW Dec 30, 2025)
    - PatternLearner for temporal pattern learning (NEW Dec 30, 2025)
    - OrganismPhysicalBridge for autonomous physical actions (NEW Dec 30, 2025)
    """
    try:
        from kagami.core.integrations import (
            get_alert_hierarchy,
            get_situation_engine,
            get_system_health_monitor,
            initialize_alert_hierarchy,
            initialize_unified_sensory,
            initialize_wakefulness,
            register_default_health_checks,
        )

        # Initialize unified sensory (wires AlertHierarchy + Consciousness)
        sensory = await initialize_unified_sensory(
            with_alerts=True,
            with_consciousness=True,
        )

        # Initialize AlertHierarchy with SmartHome for audio
        alert_hierarchy = None
        smart_home = None  # May be set below, used by multiple downstream components
        try:
            alert_hierarchy = get_alert_hierarchy()
            from kagami_smarthome import get_smart_home

            smart_home = await get_smart_home()
            await initialize_alert_hierarchy(smart_home)
            app.state.alert_hierarchy = alert_hierarchy
            logger.info("✅ AlertHierarchy wired to SmartHome audio")
        except Exception as e:
            logger.debug(f"AlertHierarchy SmartHome wiring deferred: {e}")

        # Wire CrossDomainBridge (unified digital-physical bridge)
        try:
            from kagami.core.ambient.cross_domain_bridge import (
                get_cross_domain_bridge,
            )

            bridge = get_cross_domain_bridge()
            if sensory and smart_home:
                await bridge.connect(sensory, smart_home)
            app.state.cross_domain_bridge = bridge
            logger.info("✅ CrossDomainBridge connected (unified, event-driven)")
        except Exception as e:
            logger.debug(f"CrossDomainBridge deferred: {e}")

        # CELESTIAL TRIGGER ENGINE (Jan 3, 2026)
        # THE astronomical automation engine - calculates sun position and fires
        # triggers at sunrise, sunset, civil dusk. This is separate from weather-
        # based triggers and runs continuously based on orbital mechanics.
        if smart_home is not None:
            try:
                from kagami.core.celestial import connect_celestial_engine

                celestial_engine = await connect_celestial_engine(smart_home)
                app.state.celestial_engine = celestial_engine

                # Start periodic celestial check loop (every 60 seconds)
                async def _celestial_check_loop() -> None:
                    """Periodically check celestial triggers (sun position, etc.)."""
                    import asyncio

                    while True:
                        try:
                            fired = await celestial_engine.check_triggers()
                            if fired:
                                logger.debug(f"🌞 Celestial triggers fired: {fired}")
                        except Exception as e:
                            logger.debug(f"Celestial check error: {e}")
                        await asyncio.sleep(60)  # Check every minute

                from kagami.core.async_utils import safe_create_task

                safe_create_task(_celestial_check_loop(), name="celestial_trigger_loop")
                logger.info("✅ CelestialTriggerEngine connected (astronomical automation)")
            except Exception as e:
                logger.debug(f"CelestialTriggerEngine deferred: {e}")
                app.state.celestial_engine = None
        else:
            app.state.celestial_engine = None

        # WAKEFULNESS MANAGER (Dec 29, 2025)
        # Unified wakefulness state controlling polling, autonomy, and alerts
        try:
            # Get autonomy engine if available
            autonomy = getattr(app.state, "autonomous_goal_engine", None)

            # Get consciousness if available
            consciousness = None
            if organism and hasattr(organism, "get_consciousness"):
                consciousness = organism.get_consciousness()

            # Initialize and wire WakefulnessManager
            wakefulness = await initialize_wakefulness(
                sensory=sensory,
                autonomy=autonomy,
                alert_hierarchy=alert_hierarchy,
                consciousness=consciousness,
            )
            app.state.wakefulness_manager = wakefulness
            logger.info("✅ WakefulnessManager wired (adaptive polling enabled)")
        except Exception as e:
            logger.debug(f"WakefulnessManager init deferred: {e}")

        # EMAIL MONITOR SERVICE (Jan 4, 2026)
        # Proactive email monitoring for priority contacts and service requests.
        # Tracks conversations Tim initiates (appliance repairs, contractors, etc.)
        # and alerts when responses arrive.
        try:
            from kagami.core.services.email_monitor import (  # type: ignore[import-not-found]
                setup_email_monitor,
            )

            email_monitor = await setup_email_monitor(
                smart_home=smart_home,
                auto_start=True,
            )
            app.state.email_monitor = email_monitor

            # Log active service requests
            pending = email_monitor.get_pending_responses()
            if pending:
                logger.info(
                    f"✅ EmailMonitor started ({len(email_monitor._rules)} rules, "
                    f"{len(pending)} pending service requests)"
                )
            else:
                logger.info(f"✅ EmailMonitor started ({len(email_monitor._rules)} watch rules)")
        except Exception as e:
            logger.debug(f"EmailMonitor init deferred: {e}")
            app.state.email_monitor = None

        # Start the SINGLE polling loop (now wakefulness-aware)
        await sensory.start_polling()

        app.state.unified_sensory = sensory
        app.state.unified_sensory_ready = True
        logger.info("✅ UnifiedSensory started (wakefulness-aware polling)")

        # TELEMETRY COLLECTION (Dec 30, 2025 - 100/100 audit)
        # Track integration boot metrics for observability
        try:
            integration_telemetry = {
                "unified_sensory": sensory is not None,
                "alert_hierarchy": alert_hierarchy is not None,
                "cross_domain_bridge": app.state.cross_domain_bridge is not None
                if hasattr(app.state, "cross_domain_bridge")
                else False,
                "wakefulness_manager": app.state.wakefulness_manager is not None
                if hasattr(app.state, "wakefulness_manager")
                else False,
                "email_monitor": app.state.email_monitor is not None
                if hasattr(app.state, "email_monitor")
                else False,
                "smart_home_connected": smart_home is not None,
            }
            # Extended telemetry for 100/100 audit
            integration_telemetry.update(
                {
                    "situation_engine": app.state.situation_engine is not None
                    if hasattr(app.state, "situation_engine")
                    else False,
                    "system_health_monitor": app.state.system_health_monitor is not None
                    if hasattr(app.state, "system_health_monitor")
                    else False,
                    "sensorimotor_bridge": app.state.sensorimotor_bridge is not None
                    if hasattr(app.state, "sensorimotor_bridge")
                    else False,
                    "pattern_learners": app.state.pattern_learners is not None
                    if hasattr(app.state, "pattern_learners")
                    else False,
                    "organism_physical_bridge": app.state.organism_physical_bridge is not None
                    if hasattr(app.state, "organism_physical_bridge")
                    else False,
                }
            )
            app.state.integration_telemetry = integration_telemetry
            success_count = sum(1 for v in integration_telemetry.values() if v)
            total_count = len(integration_telemetry)

            # Calculate health score (0-100)
            health_score = round((success_count / total_count) * 100)
            app.state.integration_health_score = health_score

            logger.info(
                f"📊 Integration telemetry: {success_count}/{total_count} integrations wired "
                f"(health score: {health_score}/100)"
            )
        except Exception as e:
            logger.debug(f"Telemetry collection failed: {e}")

        # SITUATION AWARENESS ENGINE (Dec 30, 2025)
        # THE source of truth for "what's happening"
        # ComposioSmartHomeBridge and AutonomousGoalEngine consume this
        try:
            situation_engine = get_situation_engine()
            app.state.situation_engine = situation_engine
            logger.info("✅ SituationAwarenessEngine initialized")
        except Exception as e:
            logger.debug(f"SituationAwarenessEngine init deferred: {e}")
            app.state.situation_engine = None

        # SYSTEM HEALTH MONITOR (Dec 30, 2025)
        # Unified health tracking and self-healing
        try:
            health_monitor = get_system_health_monitor()
            await register_default_health_checks(health_monitor)
            await health_monitor.start()
            app.state.system_health_monitor = health_monitor
            app.state.system_health_ready = True
            logger.info("✅ SystemHealthMonitor started (self-healing enabled)")
        except Exception as e:
            logger.debug(f"SystemHealthMonitor init deferred: {e}")
            app.state.system_health_monitor = None
            app.state.system_health_ready = False

        # SENSORIMOTOR BRIDGE (Dec 30, 2025)
        # THE closed loop: Sense → Encode → WorldModel → Decode → Act
        try:
            from kagami.core.integrations.sensorimotor_bridge import (
                initialize_sensorimotor_bridge,
            )

            sensorimotor = await initialize_sensorimotor_bridge(
                sensory=sensory,
                device="cpu",
                enable_motor_decode=False,  # Autonomous motor decode is opt-in
            )
            app.state.sensorimotor_bridge = sensorimotor
            app.state.sensorimotor_ready = True
            logger.info("✅ SensorimotorBridge connected (closed-loop perception)")
        except Exception as e:
            logger.debug(f"SensorimotorBridge init deferred: {e}")
            app.state.sensorimotor_bridge = None
            app.state.sensorimotor_ready = False

        # PATTERN LEARNER WIRING (Dec 30, 2025)
        # Subscribe pattern learners to sense events for temporal learning
        try:
            from kagami.core.learning.pattern_learner import (
                TimeGranularity,
                get_pattern_learner,
            )

            # Create pattern learners for key domains
            presence_learner = get_pattern_learner("presence", TimeGranularity.HOUR)
            sleep_learner = get_pattern_learner("sleep", TimeGranularity.HOUR)
            activity_learner = get_pattern_learner("activity", TimeGranularity.QUARTER_HOUR)

            # Subscribe to sense events
            async def _pattern_sense_callback(sense_type: Any, data: dict, delta: dict) -> None:
                """Record patterns from sense events."""
                try:
                    sense_name = (
                        sense_type.value if hasattr(sense_type, "value") else str(sense_type)
                    )

                    if sense_name == "presence":
                        is_home = data.get("owner_home", True)
                        presence_learner.record_event(is_home)
                    elif sense_name == "sleep":
                        is_sleeping = data.get("state") == "asleep"
                        sleep_learner.record_event(is_sleeping)
                    elif sense_name == "situation":
                        phase = data.get("phase", "unknown")
                        activity_learner.record_event(phase == "focused")
                except Exception:
                    pass  # Pattern learning is best-effort

            sensory.on_sense_change(_pattern_sense_callback)
            app.state.pattern_learners = {
                "presence": presence_learner,
                "sleep": sleep_learner,
                "activity": activity_learner,
            }
            logger.info("✅ PatternLearners wired to UnifiedSensory")
        except Exception as e:
            logger.debug(f"PatternLearner wiring deferred: {e}")
            app.state.pattern_learners = None

        # ORGANISM PHYSICAL BRIDGE (Dec 30, 2025)
        # Enables autonomous physical actions based on colony/situation state
        try:
            from kagami.core.integrations.organism_physical_bridge import (
                connect_organism_physical_bridge,
            )

            if smart_home:
                physical_bridge = await connect_organism_physical_bridge(smart_home)
                app.state.organism_physical_bridge = physical_bridge
                logger.info("✅ OrganismPhysicalBridge connected (autonomous actions enabled)")
            else:
                app.state.organism_physical_bridge = None
        except Exception as e:
            logger.debug(f"OrganismPhysicalBridge init deferred: {e}")
            app.state.organism_physical_bridge = None

    except Exception as e:
        logger.warning(f"UnifiedSensory init failed: {e}")
        app.state.unified_sensory = None
        app.state.unified_sensory_ready = False


async def _init_ambient(app: Any, organism: Any) -> None:
    """Initialize Ambient controller (subscribes to UnifiedSensory events)."""
    ambient_enabled = _should_enable_loader(
        "KAGAMI_ENABLE_AMBIENT", default_full=True, default_test=False
    )
    if not ambient_enabled:
        app.state.ambient_controller = None
        return

    try:
        from kagami.core.ambient import AmbientConfig
        from kagami.core.ambient.controller import AmbientController, set_ambient_controller

        ambient_config = AmbientConfig(
            enable_lights=os.getenv("KAGAMI_AMBIENT_LIGHTS", "0") == "1",
            enable_sound=os.getenv("KAGAMI_AMBIENT_SOUND", "0") == "1",
            enable_haptic=False,
            enable_voice=os.getenv("KAGAMI_AMBIENT_VOICE", "0") == "1",
            enable_display=True,
            enable_world_model=True,
            enable_smart_home=True,
        )
        ambient = AmbientController(ambient_config)
        await ambient.initialize()

        if hasattr(app.state, "world_model") and app.state.world_model:
            if ambient._display:
                ambient._display.connect_world_model(app.state.world_model)

        set_ambient_controller(ambient)

        from kagami.core.async_utils import safe_create_task

        safe_create_task(ambient.start(), name="ambient_controller")
        app.state.ambient_controller = ambient

        organism.set_ambient_controller(ambient)

    except Exception as e:
        logger.debug(f"Ambient init skipped: {e}")
        app.state.ambient_controller = None


async def _parallel_load_all_systems(
    app: Any,
    orchestrator: Any,
    production_systems: Any,
    loader_state: Any,
) -> None:
    """Load all heavy systems in parallel with retry logic.

    OPTIMIZED (Dec 28, 2025): Reduced retry delays, parallel execution.
    """
    import time

    start_time = time.time()

    loader_states = {"world_model": False, "encoder": False, "receipt_processor": False}

    async def _load_with_retry(loader_name: str, loader_fn: Any, max_retries: int = 2) -> None:
        """Load with fast retry (0.2s, 0.5s delays)."""
        for attempt in range(max_retries):
            try:
                await loader_fn()
                loader_states[loader_name] = True
                return
            except Exception as e:
                wait_time = (attempt + 1) * 0.2  # 0.2s, 0.4s (faster retries)
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                else:
                    logger.debug(f"{loader_name} load failed: {e}")

    async def _load_world_model() -> None:
        import torch  # Lazy import

        if not _should_enable_loader(
            "KAGAMI_ENABLE_WORLD_MODEL", default_full=True, default_test=False
        ):
            return

        await loader_state.mark_loading("world_model")
        try:
            from kagami.core.world_model.service import get_world_model_service

            service = get_world_model_service()
            loop = asyncio.get_running_loop()
            model = await loop.run_in_executor(None, lambda: service.model)

            production_systems.world_model = model
            orchestrator._world_model = model
            orchestrator._world_model_service = service
            app.state.world_model_service = service
            app.state.world_model = model

            # Pre-warm (non-blocking)
            try:
                if model is not None:
                    device_str = str(model.device) if model.device is not None else "cpu"
                    with torch.no_grad():
                        dummy_obs = torch.randn(1, model.observation_dim, device=device_str)
                        dummy_action = torch.randn(1, model.action_dim, device=device_str)
                        for _ in range(3):
                            _ = model(dummy_obs, dummy_action)
            except Exception:
                pass

            # Wire ambient display
            try:
                ambient = getattr(app.state, "ambient_controller", None)
                if ambient and getattr(ambient, "_display", None):
                    ambient._display.connect_world_model(model)
            except Exception:
                pass

            await loader_state.mark_ready("world_model")
        except Exception as e:
            await loader_state.mark_failed("world_model", str(e))
            raise

    async def _load_encoder() -> None:
        await loader_state.mark_loading("encoder")
        try:
            from kagami.core.world_model.multimodal_encoder import get_multimodal_encoder

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, get_multimodal_encoder)
            await loader_state.mark_ready("encoder")
        except Exception as e:
            await loader_state.mark_failed("encoder", str(e))
            raise

    async def _load_receipt_processor() -> None:
        await loader_state.mark_loading("receipt_processor")
        try:
            from kagami.core.events.receipt_stream_processor import ReceiptStreamProcessor

            processor = ReceiptStreamProcessor(
                queue_size=1000, batch_size=32, batch_timeout_ms=1000
            )
            processor._learning = production_systems.learning_instinct
            processor._prediction = production_systems.prediction_instinct
            processor._experience = production_systems.prioritized_replay

            async def learning_handler(receipt: dict[str, Any]) -> None:
                try:
                    if processor._learning:
                        context = {"action": receipt.get("action", "unknown")}
                        outcome = {"status": receipt.get("status", "unknown")}
                        valence = await processor._learning.evaluate_outcome(outcome)
                        await processor._learning.remember(
                            context=context, outcome=outcome, valence=valence, event=receipt
                        )
                except Exception:
                    pass

            processor.add_handler(learning_handler)
            await processor.start()
            app.state.receipt_processor = processor
            await loader_state.mark_ready("receipt_processor")
        except Exception as e:
            await loader_state.mark_failed("receipt_processor", str(e))
            raise

    # Execute all loaders in parallel with 20s timeout
    try:
        await asyncio.wait_for(
            asyncio.gather(
                _load_with_retry("world_model", _load_world_model),
                _load_with_retry("encoder", _load_encoder),
                _load_with_retry("receipt_processor", _load_receipt_processor),
                return_exceptions=True,
            ),
            timeout=20.0,
        )
    except TimeoutError:
        app.state.loader_timeout = True

    duration = time.time() - start_time
    app.state.loader_states = loader_states
    app.state.loaders_ready = all(loader_states.values())
    logger.debug(
        f"Model loading: {sum(loader_states.values())}/{len(loader_states)} in {duration:.1f}s"
    )


async def startup_safety(app: FastAPI) -> None:
    """Initialize safety systems (CBF registry, monitors).

    OPTIMIZED (Dec 28, 2025): Pre-warming deferred to background.
    - CBF registry + monitor init: ~1s (required)
    - Model pre-warming: deferred to background (was 8-10s)
    """
    try:
        from kagami.core.safety.cbf_registry import init_cbf_registry
        from kagami.core.safety.cbf_runtime_monitor import get_cbf_monitor

        # Initialize CBF registry with Tier-1 barriers
        registry = init_cbf_registry()
        stats = registry.get_stats()
        tier_summary = (
            f"T1:{stats.get('tier_1', 0)}, T2:{stats.get('tier_2', 0)}, T3:{stats.get('tier_3', 0)}"
        )
        logger.debug(f"CBF Registry: {stats['total_barriers']} barriers ({tier_summary})")

        # Initialize CBF monitor for violation detection
        monitor = get_cbf_monitor()
        app.state.cbf_monitor = monitor
        app.state.cbf_monitor_ready = True
        logger.debug("CBF Monitor initialized")

        # DEFERRED: Pre-warming moved to background to speed up boot
        async def _background_prewarm() -> None:
            """Pre-warm safety models in background (non-blocking)."""
            import torch  # Lazy import

            await asyncio.sleep(1.0)  # Let API start first

            # Pre-warm CBF model
            try:
                from kagami.core.safety.optimal_cbf import get_optimal_cbf

                cbf = get_optimal_cbf()
                cbf_device = cbf.state_encoder.encoder[0].weight.device
                cbf_device_str = str(cbf_device) if cbf_device is not None else "cpu"
                dummy_state = torch.randn(1, 4, device=cbf_device_str)
                with torch.no_grad():
                    for _ in range(3):
                        _ = cbf.barrier_value(dummy_state)
                logger.debug(f"CBF model pre-warmed on {cbf_device}")
            except Exception as warmup_err:
                logger.debug(f"CBF pre-warming skipped: {warmup_err}")

            # Pre-warm WildGuard safety classifier
            try:
                import time

                from kagami.core.safety.cbf_integration import get_safety_filter

                warmup_start = time.time()
                safety_filter = get_safety_filter()
                for _i in range(3):
                    _, _, _ = safety_filter.filter_text(
                        text="Pre-warming safety classifier",
                        nominal_control=torch.tensor([[0.5, 0.5]], dtype=torch.float32),
                        context="warmup",
                    )
                warmup_elapsed = time.time() - warmup_start
                logger.debug(f"Safety classifier pre-warmed in {warmup_elapsed:.2f}s")
            except Exception as warmup_err:
                logger.debug(f"Safety classifier pre-warming skipped: {warmup_err}")

        # Start pre-warming in background
        from kagami.core.async_utils import safe_create_task

        safe_create_task(_background_prewarm(), name="safety_prewarm")

    except Exception as e:
        logger.error(f"⚠️ Safety system initialization failed: {e}")
        app.state.cbf_monitor = None
        app.state.cbf_monitor_ready = False


async def startup_brain(app: FastAPI) -> None:
    """Initialize Matryoshka Brain for geometric reasoning."""

    # ALWAYS ENABLED
    try:
        from kagami.core.brain_api import BrainAPI

        brain_api = BrainAPI(max_batch_size=8, batch_timeout_ms=10.0)
        # FIX: Don't await start() - it creates background tasks
        # Starting synchronously blocks lifespan completion
        from kagami.core.async_utils import safe_create_task

        safe_create_task(brain_api.start(), name="brain_api_start")
        logger.debug("Brain API start task created")

        app.state.brain_api = brain_api

        # Wire brain to orchestrator for geometric reasoning
        if hasattr(app.state, "orchestrator") and app.state.orchestrator:
            app.state.orchestrator.set_brain(brain_api)
            logger.debug("Brain wired to orchestrator")
        else:
            logger.debug("Brain ready (orchestrator wiring deferred)")

        # 🔌 WIRE: Connect Stigmergy to World Model (Semantic Loop)
        # This enables the StigmergyLearner to query the World Model if needed
        # and ensures World Model updates feed into Stigmergy via receipts
        try:
            from kagami.core.unified_agents.memory.stigmergy import get_stigmergy_learner

            get_stigmergy_learner()
            # Ensure learner is initialized
            # (We don't have an explicit wire method yet, but getting the singleton
            # ensures it's alive when the brain comes up)
            logger.debug("Stigmergy Learner linked")
        except (ImportError, RuntimeError, AttributeError) as sl_err:
            logger.warning(f"Stigmergy wiring warning: {sl_err}")

    except (ImportError, RuntimeError, AttributeError) as e:
        logger.warning(f"⚠️  Brain initialization failed: {e}")
        # Non-fatal - system can operate without brain


async def startup_llm_service(app: FastAPI) -> None:
    """Initialize LLM service with background model loading.

    Models load in background to prevent startup blocking.
    API serves immediately while models load.
    """
    try:
        from kagami.core.services.llm import get_llm_service

        llm_service = get_llm_service()
        await llm_service.initialize()
        app.state.llm_service = llm_service
        app.state.llm_service_ready = llm_service.are_models_ready

        logger.debug("LLM service initialized")

        # Start a background task to track LLM readiness
        async def _track_llm_readiness() -> None:
            """Monitor LLM readiness and update app state."""
            try:
                ready = await llm_service.wait_for_models(timeout_seconds=120.0)
                app.state.llm_service_ready = ready
                if ready:
                    logger.debug("LLM models fully loaded")
                else:
                    logger.warning("LLM models incomplete after 120s timeout")
            except Exception as e:
                logger.error(f"LLM readiness monitoring failed: {e}")
                app.state.llm_service_ready = False

        from kagami.core.async_utils import safe_create_task

        safe_create_task(_track_llm_readiness(), name="llm_readiness_monitor")

    except (ImportError, RuntimeError, AttributeError) as e:
        logger.warning(f"⚠️  LLM service initialization failed: {e}")
        app.state.llm_service = None
        app.state.llm_service_ready = False


async def startup_background_tasks(app: FastAPI) -> None:
    """Start background task manager and autonomous goal generation."""
    try:
        from kagami.core.tasks.background_task_manager import BackgroundTaskManager

        btm = BackgroundTaskManager()
        # FIX: Don't await start() - creates background tasks that block
        from kagami.core.async_utils import safe_create_task

        safe_create_task(btm.start(), name="background_task_manager_start")
        logger.debug("Background task manager start task created")

        app.state.background_task_manager = btm
        logger.debug("Background tasks started")

    except (ImportError, RuntimeError, AttributeError) as e:
        logger.warning(f"⚠️  Background tasks failed: {e}")

    # Start Redis job storage cleanup tasks
    try:
        from kagami_api.services.redis_job_storage import get_job_storage

        # Start cleanup for image jobs
        image_storage = get_job_storage("image")
        await image_storage.start_cleanup_task()
        logger.debug("Image job cleanup task started")

        # Start cleanup for animation jobs
        animation_storage = get_job_storage("animation")
        await animation_storage.start_cleanup_task()
        logger.debug("Animation job cleanup task started")

        # Store references for shutdown
        app.state.job_storage_image = image_storage
        app.state.job_storage_animation = animation_storage

    except (ImportError, RuntimeError, AttributeError) as e:
        logger.warning(f"⚠️  Job storage cleanup tasks failed: {e}")

    # Start autonomous goal generation (continuous self-directed behavior)
    try:
        from kagami.core.autonomous_goal_engine import AutonomousGoalEngine

        autonomous = AutonomousGoalEngine()

        # Initialize with main orchestrator
        if hasattr(app.state, "orchestrator"):
            await autonomous.initialize(app.state.orchestrator)

            # Perform self-diagnostic (DEBUG level - too verbose for INFO)
            try:
                status = await autonomous.introspect()
                logger.debug(
                    f"Volition: {'Running' if status['enabled'] else 'Standby'}, "
                    f"Motivation: {status.get('motivation_system', 'unknown')}"
                )
            except (RuntimeError, AttributeError, KeyError) as diag_err:
                logger.debug(f"Self-diagnostic skipped: {diag_err}")

            # FIX: Don't await start - it runs forever, blocks lifespan
            from kagami.core.async_utils import safe_create_task

            safe_create_task(autonomous.start_autonomous_pursuit(), name="autonomous_pursuit")
            logger.debug("Autonomous pursuit started")

            app.state.autonomous_orchestrator = autonomous
            logger.debug("Autonomous goal generation enabled")
        else:
            logger.warning("⚠️  Autonomous goals require orchestrator")

    except (ImportError, RuntimeError, AttributeError) as e:
        logger.warning(f"⚠️  Autonomous goal generation failed: {e}")

    # DYNAMIC OPTIMIZATION LOADING (Strange Loop Closure)
    try:
        from kagami.core.training.optimization.dynamic_loader import load_dynamic_optimizations

        count = load_dynamic_optimizations(app)
        if count:
            logger.debug(f"Dynamic optimizations: {count} active")
        else:
            logger.debug("Dynamic optimizations: none")
    except (ImportError, RuntimeError, AttributeError) as e:
        logger.warning(f"⚠️  Dynamic optimization loading failed: {e}")

    # Start Redis/DB pool monitors (best-effort)
    try:
        from kagami.core.database.async_connection import get_async_engine
        from kagami.core.database.pool_monitor import DBPoolMonitor
        from kagami.core.redis_pool_monitor import (  # type: ignore[import-not-found]
            get_redis_pool_monitor,
        )

        try:
            engine = get_async_engine()
            if engine is not None:
                app.state.db_pool_monitor = DBPoolMonitor(engine)
        except (ImportError, RuntimeError, AttributeError):
            pass  # OK to continue without DB pool monitor

        try:
            app.state.redis_pool_monitor = get_redis_pool_monitor()
        except (ImportError, RuntimeError, AttributeError):
            pass  # OK to continue without Redis pool monitor
    except (ImportError, AttributeError):
        pass  # OK to continue without pool monitoring infrastructure


async def startup_learning_systems(app: FastAPI) -> None:
    """Start learning systems (instinct loop + coordinator) with Full Operation guarantees."""
    # Full Operation is now implicit

    app.state.learning_loop_ready = False
    app.state.learning_coordinator_ready = False
    app.state.learning_systems_ready = False

    production_systems = getattr(app.state, "production_systems", None)
    if not production_systems:
        msg = "Production systems unavailable; cannot initialize learning systems"
        logger.warning(f"⚠️  {msg}")
        return

    try:
        from kagami.core.learning.instinct_learning_loop import create_learning_loop

        learning_loop = create_learning_loop(production_systems)
        app.state.learning_loop = learning_loop
        app.state.learning_loop_ready = True
        logger.debug("Instinct learning loop initialized")
    except (ImportError, RuntimeError, AttributeError) as exc:
        logger.warning(f"⚠️  Instinct learning loop unavailable: {exc}")

    try:
        from kagami.core.learning.coordinator import get_learning_coordinator

        learning_coordinator = get_learning_coordinator()
        # NOTE: Batch training is scheduled via Celery Beat, not an internal loop
        # See: kagami.core.tasks.processing_state.batch_train_task
        app.state.learning_coordinator = learning_coordinator
        app.state.learning_coordinator_ready = True
        logger.debug("Learning Coordinator initialized (Celery Beat schedules batch_train_task)")
    except (ImportError, RuntimeError, AttributeError) as exc:
        logger.warning(f"⚠️  Unified Learning Coordinator unavailable: {exc}")

    app.state.learning_systems_ready = (
        app.state.learning_loop_ready and app.state.learning_coordinator_ready
    )
    if app.state.learning_systems_ready:
        logger.debug("Learning systems ready")
    else:
        logger.warning("Learning systems degraded")


async def coordinate_background_tasks(app: FastAPI) -> None:
    """Coordinate background task startup to ensure dependencies are met."""
    try:
        # Give background tasks a brief window to initialize
        # They run async but need core systems to be ready
        await asyncio.sleep(0.5)

        # Verify critical background tasks are running
        checks = {
            "receipt_processor": hasattr(app.state, "receipt_processor")
            and app.state.receipt_processor,
            "unified_organism": hasattr(app.state, "unified_organism")
            and app.state.unified_organism,
            "orchestrator": hasattr(app.state, "orchestrator") and app.state.orchestrator,
            "learning_systems": getattr(app.state, "learning_systems_ready", False),
        }

        ready_count = sum(1 for v in checks.values() if v)
        total_count = len(checks)

        if ready_count < total_count:
            not_ready = [k for k, v in checks.items() if not v]
            logger.warning(f"Background systems degraded: {not_ready}")
        else:
            logger.debug(f"Background task coordination complete ({ready_count}/{total_count})")

    except (AttributeError, RuntimeError) as e:
        logger.warning(f"⚠️  Background task coordination check failed: {e}")


async def startup_voice_warmup(app: FastAPI) -> None:
    """Pre-warm voice TTS model for low-latency announcements.

    Uses the unified media pipeline (ElevenLabs Flash v2.5).
    Runs in background after ambient_os to avoid boot blocking.
    """
    try:
        # Use unified media pipeline for voice (Jan 2026)
        from kagami.core.media import speak

        logger.info("🎤 Pre-warming voice module...")

        # Pre-warm with a short phrase (fills caches, establishes connection)
        result = await speak("System ready.")

        if result.success:
            logger.info(f"✅ Voice ready (unified media pipeline, {result.latency_ms:.0f}ms)")
            app.state.voice_ready = True
        else:
            logger.warning("⚠️  Voice warmup returned unsuccessful")
            app.state.voice_ready = False

    except ImportError:
        # Fallback: try legacy TTS module
        try:
            from kagami.core.services.voice.tts import speak as tts_speak

            await tts_speak("System ready.", play=False)
            logger.info("✅ Voice ready (TTS service)")
            app.state.voice_ready = True
        except Exception as fallback_err:
            logger.debug(f"Voice fallback failed: {fallback_err}")
            app.state.voice_ready = False
    except Exception as e:
        logger.warning(f"⚠️  Voice module unavailable: {e}")
        app.state.voice_module = None
        app.state.voice_ready = False


__all__ = [
    "coordinate_background_tasks",
    "startup_background_tasks",
    "startup_brain",
    "startup_learning_systems",
    "startup_llm_service",
    "startup_orchestrator",
    "startup_voice_warmup",
]
