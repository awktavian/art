"""Deferred Boot — Non-Blocking Orchestrator Startup.

CREATED: December 30, 2025

Simple: API starts instantly, models load in background.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


async def startup_orchestrator_deferred(app: FastAPI) -> None:
    """Start orchestrator instantly, load models in background.

    FAST (~500ms):
    - IntentOrchestrator
    - ProductionSystemsCoordinator
    - DeferredModelLoader

    BACKGROUND (non-blocking):
    - World model
    - Encoder
    - Organism
    - Everything else
    """
    from kagami.boot.deferred_loader import get_deferred_loader
    from kagami.core.async_utils import safe_create_task
    from kagami.core.orchestrator import IntentOrchestrator
    from kagami.core.production_systems_coordinator import ProductionSystemsCoordinator

    try:
        # === FAST PHASE ===

        # Deferred loader (instant)
        loader = get_deferred_loader()
        app.state.deferred_loader = loader

        # Orchestrator (fast)
        orchestrator = IntentOrchestrator()
        await orchestrator.initialize()
        app.state.orchestrator = orchestrator
        app.state.kagami_intelligence = orchestrator

        # Production systems (fast)
        production_systems = ProductionSystemsCoordinator()
        await production_systems.initialize()
        production_systems.wire_to_orchestrator(orchestrator)
        app.state.production_systems = production_systems

        # Tools (optional)
        try:
            from kagami.core.tools_integration import get_kagami_tools_integration

            tools = get_kagami_tools_integration()
            await tools.initialize()
            app.state.kagami_tools_integration = tools
        except Exception:
            app.state.kagami_tools_integration = None

        # Mark ready
        app.state.fractal_organism = True
        app.state.orchestrator_ready = True

        logger.info("✅ Orchestrator ready (models loading in background)")

        # === BACKGROUND PHASE ===
        safe_create_task(
            _load_models_background(app, orchestrator, production_systems),
            name="deferred_model_loading",
        )

    except Exception as e:
        import traceback

        logger.error(f"❌ Orchestrator failed: {e}\n{traceback.format_exc()}")
        raise


async def _load_models_background(
    app: FastAPI,
    orchestrator: Any,
    production_systems: Any,
) -> None:
    """Load all models in background."""
    import time

    start = time.time()

    loader = app.state.deferred_loader

    # Load world model
    async def load_world_model():
        from kagami.core.world_model.service import get_world_model_service

        service = get_world_model_service()
        model = await service.get_model_async()
        app.state.world_model = model
        app.state.world_model_service = service
        production_systems.world_model = model
        orchestrator._world_model = model
        return model

    # Load encoder
    async def load_encoder():
        from kagami.core.world_model.multimodal_encoder import get_multimodal_encoder

        loop = asyncio.get_running_loop()
        encoder = await loop.run_in_executor(None, get_multimodal_encoder)
        app.state.multimodal_encoder = encoder
        return encoder

    # Load organism
    async def load_organism():
        from kagami.core.unified_agents import UnifiedOrganism, set_unified_organism
        from kagami.core.unified_agents.unified_organism import OrganismConfig

        config = OrganismConfig(homeostasis_interval=60.0)
        organism = UnifiedOrganism(config=config)
        await organism.start()
        set_unified_organism(organism)
        app.state.unified_organism = organism
        app.state.organism_ready = True
        return organism

    # Register and load all models in parallel
    await loader.register_model("world_model")
    await loader.register_model("encoder")
    await loader.register_model("organism")

    results = await asyncio.gather(
        loader.load_model("world_model", load_world_model),
        loader.load_model("encoder", load_encoder),
        loader.load_model("organism", load_organism),
        return_exceptions=True,
    )

    # Log results
    elapsed = time.time() - start
    success = sum(1 for r in results if r is True)
    logger.info(f"✅ Background loading complete: {success}/{len(results)} models ({elapsed:.1f}s)")


__all__ = ["startup_orchestrator_deferred"]
