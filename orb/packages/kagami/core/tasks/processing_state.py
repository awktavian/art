"""
Celery tasks for organism processing state monitoring.

These tasks run periodically to compute cognitive metrics and maintain
organism health. They wrap existing monitoring infrastructure.
"""

import asyncio
import logging
from typing import Any

from kagami.core.tasks.app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="kagami.core.tasks.processing_state.train_instincts_task")
def train_instincts_task() -> dict[str, Any]:
    """
    Train instinct systems based on recent experiences.

    Runs periodically (every 60s via Celery Beat) to adapt instinct weights.
    """
    try:
        from kagami.core.learning.instinct_learning_loop import get_learning_loop

        loop = get_learning_loop()
        if loop is None:
            return {"status": "skipped", "reason": "learning_loop_unavailable"}

        # Run async train_step
        result = asyncio.run(loop.train_step())
        return result
    except Exception as e:
        logger.error(f"Instinct training failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="kagami.core.tasks.processing_state.update_lzc_task")
def update_lzc_task() -> dict[str, Any]:
    """
    Update Lempel-Ziv Complexity metrics for organism state.

    LZC measures the algorithmic complexity of brain state time series,
    correlating with consciousness research metrics.
    """
    try:
        from kagami.core.integrations.monitors.lzc_monitor import update as lzc_update

        lzc = lzc_update(window=200)

        # Emit metric
        try:
            from kagami_observability.metrics import ORGANISM_LZC

            ORGANISM_LZC.set(lzc)
        except Exception:
            pass

        return {"status": "success", "lzc": lzc}
    except Exception as e:
        logger.debug(f"LZC update skipped: {e}")
        return {"status": "skipped", "reason": str(e)}


@celery_app.task(name="kagami.core.tasks.processing_state.update_fractal_task")
def update_fractal_task() -> dict[str, Any]:
    """
    Update fractal dimension metrics for organism activity patterns.

    Measures self-similarity in activation patterns across time scales.
    Placeholder - fractal dimension computation not yet implemented.
    """
    # Fractal dimension computation requires time series data
    # This is a placeholder until implementation is available
    return {"status": "skipped", "reason": "not_implemented"}


@celery_app.task(name="kagami.core.tasks.processing_state.update_synergy_task")
def update_synergy_task() -> dict[str, Any]:
    """
    Update synergy metrics (Phi-R) for colony interactions.

    Measures emergent information from multi-colony coordination.
    """
    try:
        from kagami.core.integrations.monitors.gaussian_pid_synergy import (
            compute_daily_synergy_from_receipts,
        )

        result = asyncio.run(compute_daily_synergy_from_receipts())
        return {"status": "success", "synergy": result}
    except Exception as e:
        logger.debug(f"Synergy update skipped: {e}")
        return {"status": "skipped", "reason": str(e)}


@celery_app.task(name="kagami.core.tasks.processing_state.update_causal_task")
def update_causal_task() -> dict[str, Any]:
    """
    Update causal density metrics for colony interactions.

    Measures directed information flow between colonies.
    Placeholder - requires causal graph from organism state.
    """
    # Causal density requires building a causal graph from receipts
    # This is a placeholder until full implementation
    return {"status": "skipped", "reason": "not_implemented"}


@celery_app.task(name="kagami.core.tasks.processing_state.generate_goals_task")
def generate_goals_task() -> dict[str, Any]:
    """
    Generate autonomous goals based on intrinsic drives.

    This enables the organism to pursue self-generated goals.
    """
    try:
        from kagami.core.unified_agents import get_unified_organism

        # get_unified_organism() always returns instance (creates if needed)
        get_unified_organism()

        # Generate goals via motivation system
        try:
            from kagami.core.motivation.intrinsic_motivation import (
                IntrinsicMotivationSystem,
            )

            motivation = IntrinsicMotivationSystem()
            drives = motivation.get_drive_weights()

            return {
                "status": "success",
                "drives": drives,
            }
        except Exception as e:
            return {"status": "partial", "error": str(e)}
    except Exception as e:
        logger.debug(f"Goal generation skipped: {e}")
        return {"status": "skipped", "reason": str(e)}


@celery_app.task(name="kagami.core.tasks.processing_state.compute_composite_integration")
def compute_composite_integration() -> dict[str, Any]:
    """
    Compute composite integration metric (Phi) for the organism.

    Measures overall information integration across all colonies.
    Placeholder - Phi computation requires full organism state.
    """
    # Phi (Integrated Information) requires computing across all colonies
    # This is a placeholder until full IIT implementation
    return {"status": "skipped", "reason": "not_implemented"}


@celery_app.task(name="kagami.core.tasks.processing_state.gaussian_pid_synergy_task")
def gaussian_pid_synergy_task() -> dict[str, Any]:
    """
    Run full Gaussian PID synergy analysis (daily batch).

    Computationally expensive O(N²) analysis of colony interactions.
    Runs daily at 03:15 UTC.
    """
    try:
        from kagami.core.integrations.monitors.gaussian_pid_synergy import (
            compute_daily_synergy_from_receipts,
        )

        result = asyncio.run(compute_daily_synergy_from_receipts())
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"Gaussian PID synergy analysis failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="kagami.core.tasks.processing_state.batch_train_task")
def batch_train_task() -> dict[str, Any]:
    """
    Execute batch training from experience replay.

    Runs periodically (every 5 minutes) to train world model from
    accumulated experiences.
    """
    try:
        from kagami.core.learning.coordinator import get_learning_coordinator

        # get_learning_coordinator() always returns instance (creates if needed)
        coordinator = get_learning_coordinator()
        result = asyncio.run(coordinator.batch_train_step())
        return result
    except Exception as e:
        logger.error(f"Batch training failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="kagami.core.tasks.processing_state.evolution_status_task")
def evolution_status_task() -> dict[str, Any]:
    """
    Check evolution engine status and metrics.

    The evolution engine runs its own continuous loop with 5-min cycles
    and 1-hour verification windows. This task monitors its health.
    """
    try:
        from kagami.core.evolution.continuous_evolution_engine import (
            get_evolution_engine,
        )

        async def _get_status() -> dict[str, Any]:
            # get_evolution_engine() always returns instance (creates if needed)
            engine = await get_evolution_engine()
            stats = await engine.get_stats()
            return {
                "status": "success",
                "running": stats.get("running", False),
                "cycle_count": stats.get("cycle_count", 0),
                "improvements_applied": stats.get("improvements_applied", 0),
                "success_rate": stats.get("success_rate", 0.0),
            }

        return asyncio.run(_get_status())
    except Exception as e:
        logger.debug(f"Evolution status check skipped: {e}")
        return {"status": "skipped", "reason": str(e)}


@celery_app.task(name="kagami.core.tasks.processing_state.context_tracker_task")
def context_tracker_task() -> dict[str, Any]:
    """
    Update context tracker with recent activity patterns.

    Runs periodically (every 60s) to maintain user context.
    """
    try:
        from kagami.core.ambient.context_tracker import get_context_tracker

        # get_context_tracker() always returns instance (creates if needed)
        tracker = get_context_tracker()
        result = asyncio.run(tracker.update_context())
        return (
            {"status": "success", **result} if isinstance(result, dict) else {"status": "success"}
        )
    except Exception as e:
        logger.debug(f"Context update skipped: {e}")
        return {"status": "skipped", "reason": str(e)}
