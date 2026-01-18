"""Infrastructure startup actions.

Extracted from actions.py to reduce god module.
Handles provenance chain initialization.

Created: Nov 30, 2025
Updated: Dec 2025 - Moved core infra to kagami.boot.actions.init
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Re-export core infrastructure actions for backwards compatibility


async def startup_provenance(app: FastAPI) -> None:
    """Initialize cryptographic provenance chain.

    OPTIMIZED (Dec 28, 2025): Reduced logging verbosity.
    """
    try:
        from kagami.core.safety.provenance_chain import get_provenance_chain

        chain = get_provenance_chain()
        success = await chain.initialize()

        if success:
            app.state.provenance_ready = True
            app.state.provenance_instance_id = chain.instance_id
            logger.debug(f"Provenance ready ({chain.instance_id})")
        else:
            app.state.provenance_ready = False
            logger.debug("Provenance init failed")

    except Exception as e:
        app.state.provenance_ready = False
        logger.debug(f"Provenance unavailable: {e}")


async def shutdown_provenance(app: FastAPI) -> None:
    """Shutdown provenance tracking.

    Args:
        app: FastAPI application instance
    """
    try:
        from kagami.core.receipts import disable_provenance_tracking
        from kagami.core.safety.provenance_integration import stop_cross_instance_verification

        await stop_cross_instance_verification()
        await disable_provenance_tracking()
        logger.info("✅ Provenance shutdown complete")
    except Exception as e:
        logger.warning(f"⚠️  Provenance shutdown warning: {e}")
