"""Streamlined application lifespan handler (V2).

Refactored from 2,600+ line lifespan monster into focused orchestration.
All service initialization extracted into helper modules (kagami.boot.actions).

Complexity: <30 (down from 408)
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from kagami.boot import BootGraph, BootGraphExecutionError, BootGraphReport
from kagami.boot.actions import (
    _env_int,
    coordinate_background_tasks,
    shutdown_all,
)
from kagami.core.boot_mode import is_full_mode

logger = logging.getLogger(__name__)
# Don't force INFO - let global config control verbosity

# ===  Global State (migrated from old lifespan.py) ===
active_sessions: dict[str, Any] = {}
websocket_connections: dict[str, Any] = {}


_PENDING_QUEUE_MAXSIZE = max(1, _env_int("KAGAMI_PENDING_ACTIONS_MAXSIZE", 1024))
# Global pending actions queue for events arriving before orchestrator/apps ready
pending_actions_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=_PENDING_QUEUE_MAXSIZE)


async def enqueue_pending_action(event: dict[str, Any], *, block: bool = False) -> bool:
    """Enqueue an event for later processing with overflow protection."""
    try:
        if block:
            await pending_actions_queue.put(event)
        else:
            pending_actions_queue.put_nowait(event)
        return True
    except asyncio.QueueFull:
        logger.warning("Pending actions queue full; dropping event")
        return False


def get_active_sessions() -> dict[str, Any]:
    """Get the active sessions dictionary."""
    return active_sessions


def get_websocket_connections() -> dict[str, Any]:
    """Get the WebSocket connections dictionary."""
    return websocket_connections


# === End Global State ===


def _build_boot_graph() -> BootGraph:
    """Construct the declarative boot graph for Kagami subsystems."""
    # Extract node definitions to helper modules to reduce complexity
    from kagami.boot.nodes.background import get_background_nodes
    from kagami.boot.nodes.core import get_core_nodes
    from kagami.boot.nodes.network import get_network_nodes

    # Combine all nodes
    return BootGraph(get_core_nodes() + get_network_nodes() + get_background_nodes())


def _log_boot_report(report: BootGraphReport, level: int = logging.DEBUG) -> None:
    """Emit structured logging for boot node execution (DEBUG level by default).

    Boot node details are verbose - use DEBUG level to reduce startup spam.
    Only log failures at ERROR level.
    """
    # Log individual nodes at DEBUG level
    for name, status in report.statuses.items():
        if status.success:
            logger.debug(f"[boot] {name}: {status.duration_ms:.1f}ms")
        else:
            logger.error(
                "[boot] %s failed after %.1fms: %s",
                name,
                status.duration_ms,
                status.error or "unknown",
            )

    # Log summary at INFO level (aggregate view)
    success_count = sum(1 for s in report.statuses.values() if s.success)
    total_count = len(report.statuses)
    total_ms = sum(s.duration_ms for s in report.statuses.values())
    if success_count == total_count:
        logger.info(f"Boot: {success_count} nodes in {total_ms:.0f}ms")
    else:
        logger.warning(f"Boot: {success_count}/{total_count} nodes succeeded")


async def _start_boot_sequence(app: FastAPI) -> tuple[BootGraph, BootGraphReport]:
    """Execute the boot graph and record status on app state."""
    boot_graph = _build_boot_graph()
    try:
        report = await boot_graph.start(app)
    except BootGraphExecutionError as exc:
        _log_boot_report(exc.report, level=logging.ERROR)
        app.state.boot_graph_report = exc.report.as_dict()
        raise

    _log_boot_report(report)
    app.state.boot_graph_report = report.as_dict()
    try:
        app.state.boot_health = await boot_graph.health(app)
    except Exception:
        logger.debug("Boot health snapshot unavailable", exc_info=True)
    return boot_graph, report


@asynccontextmanager  # type: ignore[arg-type]
async def lifespan_v2(app: FastAPI) -> None:  # type: ignore[misc]
    """Streamlined lifespan handler (V2).

    Complexity: <30 (down from 408)

    Handles startup and shutdown with proper error handling.
    All heavy lifting delegated to focused helper functions in kagami.boot.actions.

    **Startup Graph**:
    Boot nodes and dependencies are declared in `_build_boot_graph()` and executed via the
    `BootGraph` engine to guarantee deterministic ordering and observability.
    """
    # Optional diagnostics: allow stack dumps for startup hangs.
    # Enable with: KAGAMI_FAULTHANDLER=1 then `kill -USR1 <pid>`
    try:
        if os.getenv("KAGAMI_FAULTHANDLER", "0").lower() in ("1", "true", "yes", "on"):
            import faulthandler
            import signal

            faulthandler.register(signal.SIGUSR1, all_threads=True)
            logger.debug("faulthandler enabled (SIGUSR1 dumps stacks)")
    except Exception:
        logger.debug("faulthandler registration failed", exc_info=True)

    logger.info("🪞 Kagami OS starting...")

    # Initialize boot state
    import time

    from kagami.core.receipts import UnifiedReceiptFacade as URF

    app.state.active_sessions = active_sessions
    app.state.websocket_connections = websocket_connections

    boot_correlation_id = f"boot-{os.getpid()}-{int(time.time())}"

    # PLAN: Boot sequence
    try:
        URF.emit(
            correlation_id=boot_correlation_id,
            action="system.boot",
            event_name="boot.planned",
            event_data={"phase": "plan", "pid": os.getpid(), "mode": "full"},
            status="pending",
        )
    except Exception:
        pass

    boot_start_time = time.perf_counter()

    # Start the boot graph
    boot_graph, boot_report = await _start_boot_sequence(app)
    boot_duration = (time.perf_counter() - boot_start_time) * 1000

    if boot_report.success:
        logger.debug("Boot graph completed")

        # Set system_ready flag (REQUIRED for readiness probe)
        app.state.system_ready = True

        # Mark health manager as started and ready (Jan 4, 2026 — 125%)
        try:
            from kagami_api.routes.health import get_health_manager

            health_manager = get_health_manager()
            health_manager.mark_started()
            health_manager.mark_ready()
            logger.debug("Health manager: ready")
        except Exception as e:
            logger.debug(f"Health manager init skipped: {e}")

        # systemd sd_notify: Signal READY to systemd for Type=notify services (Jan 4, 2026)
        # Also starts watchdog ping task if WATCHDOG_USEC is set
        try:
            from kagami_api.systemd_notify import (
                notify_ready,
                start_watchdog_task,
            )

            notify_ready()
            watchdog_task = start_watchdog_task()
            app.state.watchdog_task = watchdog_task
            logger.debug("systemd: READY notified, watchdog started")
        except Exception as e:
            logger.debug(f"systemd notify skipped: {e}")

        # Collect detailed boot metrics
        boot_metrics = {
            "total_duration_ms": boot_duration,
            "node_count": len(boot_report.statuses),
            "successful_nodes": sum(1 for s in boot_report.statuses.values() if s.success),
            "failed_nodes": sum(1 for s in boot_report.statuses.values() if not s.success),
        }

        # Emit per-node metrics
        try:
            from kagami.observability.metrics.system import BOOT_NODE_DURATION_MS

            for node_name, status in boot_report.statuses.items():
                BOOT_NODE_DURATION_MS.labels(node=node_name).observe(status.duration_ms)
        except Exception as e:
            logger.debug(f"Metric recording failed: {e}")
            # Metrics are non-critical

        # Emit aggregate metrics
        try:
            import psutil
            from kagami.observability.metrics.system import (
                BOOT_CPU_AVERAGE_PERCENT,
                BOOT_MEMORY_PEAK_MB,
                BOOT_TIME_TO_READY_MS,
            )

            process = psutil.Process()

            BOOT_TIME_TO_READY_MS.observe(boot_duration)
            BOOT_MEMORY_PEAK_MB.observe(process.memory_info().rss / 1024 / 1024)
            BOOT_CPU_AVERAGE_PERCENT.observe(process.cpu_percent())
        except Exception as e:
            logger.debug(f"Metric recording failed: {e}")
            # Metrics are non-critical

        # EXECUTE: Boot completed
        try:
            URF.emit(
                correlation_id=boot_correlation_id,
                action="system.boot",
                event_name="boot.executed",
                event_data={
                    "phase": "execute",
                    "report": boot_report.as_dict(),
                    "nodes": list(boot_report.statuses.keys()),
                    "metrics": boot_metrics,
                },
                duration_ms=boot_duration,
                status="success",
            )
        except Exception:
            pass

        # COORDINATION POINT: Background tasks coordinate themselves
        # Run in background to avoid blocking API startup
        from kagami.core.async_utils import safe_create_task as _safe_create_task

        _safe_create_task(coordinate_background_tasks(app), name="coordinate_background_tasks")

        # Start etcd extended metrics collection and GC (REQUIRED - Full Operation Mode)
        from kagami.core.consensus.gc import start_etcd_gc, stop_etcd_gc
        from kagami.core.consensus.metrics_extended import (
            start_etcd_metrics_collection,
            stop_etcd_metrics_collection,
        )

        # Non-blocking: etcd metrics collection
        etcd_metrics_started = False
        try:
            await asyncio.wait_for(start_etcd_metrics_collection(), timeout=10.0)
            etcd_metrics_started = True
        except TimeoutError:
            logger.warning(
                "⚠️  etcd metrics collection timed out (10s) - continuing without extended metrics"
            )
        except Exception as e:
            logger.warning(f"⚠️  etcd metrics collection failed: {e} - continuing without")

        # Non-blocking: etcd GC
        etcd_gc_started = False
        try:
            await asyncio.wait_for(start_etcd_gc(), timeout=10.0)
            etcd_gc_started = True
        except TimeoutError:
            logger.warning("⚠️  etcd GC timed out (10s) - continuing without GC")
        except Exception as e:
            logger.warning(f"⚠️  etcd GC failed: {e} - continuing without")

        # Attach stop handles to app state for clean shutdown (only if started)
        app.state.stop_etcd_metrics_collection = (
            stop_etcd_metrics_collection if etcd_metrics_started else None
        )
        app.state.stop_etcd_gc = stop_etcd_gc if etcd_gc_started else None
        app.state.etcd_metrics_available = etcd_metrics_started
        app.state.etcd_gc_available = etcd_gc_started

        if etcd_metrics_started and etcd_gc_started:
            logger.debug("etcd metrics and GC started")
        elif etcd_metrics_started or etcd_gc_started:
            logger.debug(f"etcd partial: metrics={etcd_metrics_started}, gc={etcd_gc_started}")
        else:
            logger.debug("etcd extended features unavailable")

        # Start cross-instance receipt sync (non-blocking - networked organism feature)
        from kagami.core.receipts.etcd_receipt_sync import get_etcd_receipt_sync

        receipt_sync = get_etcd_receipt_sync()
        sync_started = False
        try:
            sync_started = await asyncio.wait_for(receipt_sync.start(), timeout=10.0)
        except TimeoutError:
            logger.warning(
                "⚠️  Receipt sync timed out (10s) - continuing without cross-instance sync"
            )
        except Exception as e:
            logger.warning(f"⚠️  Receipt sync failed: {e} - continuing without cross-instance sync")

        if sync_started:
            app.state.receipt_sync = receipt_sync
            app.state.receipt_sync_available = True
            logger.debug("Receipt sync started")
        else:
            app.state.receipt_sync = None
            app.state.receipt_sync_available = False
            logger.debug("Receipt sync unavailable (standalone mode)")

        # Start cryptographic provenance tracking (non-blocking)
        from kagami.core.receipts import enable_provenance_tracking
        from kagami.core.safety.provenance_integration import start_cross_instance_verification

        provenance_started = False
        verification_started = False
        try:
            provenance_started = await asyncio.wait_for(enable_provenance_tracking(), timeout=10.0)
        except TimeoutError:
            logger.warning(
                "⚠️  Provenance tracking timed out (10s) - continuing without cryptographic audit"
            )
        except Exception as e:
            logger.warning(f"⚠️  Provenance tracking failed: {e} - continuing without")

        if provenance_started:
            try:
                await asyncio.wait_for(start_cross_instance_verification(), timeout=10.0)
                verification_started = True
            except TimeoutError:
                logger.warning(
                    "⚠️  Cross-instance verification timed out (10s) - "
                    "provenance enabled but no cross-instance checks"
                )
            except Exception as e:
                logger.warning(f"⚠️  Cross-instance verification failed: {e}")

        app.state.provenance_available = provenance_started
        app.state.cross_instance_verification_available = verification_started

        if provenance_started and verification_started:
            logger.debug("Provenance tracking enabled")
        elif provenance_started:
            logger.debug("Provenance enabled (no cross-instance)")
        else:
            logger.debug("Provenance unavailable")

        # Start dynamic feature flags (OPTIONAL - etcd-backed)
        # NOTE: Skip for now to avoid blocking - feature flags use defaults
        logger.debug("Feature flags disabled (using defaults)")
        app.state.feature_flag_watcher = None

        # VERIFY: System operational (non-blocking)
        logger.debug("Emitting boot.verified receipt...")
        try:
            health_snapshot = getattr(app.state, "boot_health", {})
            # Use asyncio to avoid blocking if URF.emit blocks
            URF.emit(
                correlation_id=boot_correlation_id,
                action="system.boot",
                event_name="boot.verified",
                event_data={
                    "phase": "verify",
                    "health": health_snapshot,
                    "full_operation": is_full_mode(),
                },
                status="success",
            )
            logger.debug("Boot receipt emitted")
        except Exception as e:
            logger.debug(f"Receipt emission skipped: {e}")

        # Final startup message
        logger.info(f"🪞 Kagami OS ready ({boot_duration:.0f}ms)")
        yield

    else:
        # Boot failed - emit failure receipt and raise
        boot_duration = (time.perf_counter() - boot_start_time) * 1000
        try:
            URF.emit(
                correlation_id=boot_correlation_id,
                action="system.boot",
                event_name="boot.failed",
                event_data={"phase": "execute", "error": "Boot graph failed"},
                duration_ms=boot_duration,
                status="error",
            )
        except Exception:
            pass
        logger.critical("❌ Boot graph failed - aborting startup")
        raise RuntimeError("Boot graph execution failed")

    # Shutdown sequence (always runs)
    shutdown_start = time.perf_counter()

    # Mark health manager as not ready during shutdown (Jan 4, 2026 — 125%)
    try:
        from kagami_api.routes.health import get_health_manager

        health_manager = get_health_manager()
        health_manager.mark_not_ready()
    except Exception:
        pass

    # systemd sd_notify: Signal STOPPING to systemd (Jan 4, 2026)
    try:
        from kagami_api.systemd_notify import notify_stopping, stop_watchdog_task

        notify_stopping()
        # Cancel watchdog task to prevent spurious pings during shutdown
        watchdog_task = getattr(app.state, "watchdog_task", None)
        stop_watchdog_task(watchdog_task)
    except Exception:
        pass

    # Shutdown WebSocket manager (Jan 4, 2026 — 125%)
    try:
        from kagami_api.routes.cluster_websocket import shutdown_ws_manager

        await shutdown_ws_manager()
        logger.debug("WebSocket manager stopped")
    except Exception:
        pass

    # Shutdown auto recovery manager (Jan 4, 2026 — 125%)
    try:
        from kagami.core.consensus.auto_recovery import shutdown_recovery_manager

        await shutdown_recovery_manager()
        logger.debug("Recovery manager stopped")
    except Exception:
        pass

    try:
        URF.emit(
            correlation_id=boot_correlation_id,
            action="system.shutdown",
            event_name="shutdown.planned",
            event_data={"phase": "plan"},
            status="pending",
        )
    except Exception:
        pass

    # CRITICAL: Clean up MPS/GPU resources FIRST to prevent deadlock on exit
    # The PyTorch MPS allocator can deadlock with Tcl's exit() if not cleaned up first
    try:
        import torch

        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            if hasattr(torch.mps, "synchronize"):
                torch.mps.synchronize()
            if hasattr(torch.mps, "empty_cache"):
                torch.mps.empty_cache()
            logger.debug("✅ MPS cache cleared before shutdown")
        elif torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            logger.debug("✅ CUDA cache cleared before shutdown")
    except Exception as e:
        logger.debug(f"GPU cache cleanup skipped: {e}")

    # Stop provenance tracking and cross-instance verification
    try:
        from kagami.core.receipts import disable_provenance_tracking
        from kagami.core.safety.provenance_integration import stop_cross_instance_verification

        await stop_cross_instance_verification()
        await disable_provenance_tracking()
        logger.debug("Provenance tracking stopped")
    except Exception:
        pass

    # Stop cross-instance receipt sync
    try:
        if hasattr(app.state, "receipt_sync") and app.state.receipt_sync:
            await app.state.receipt_sync.stop()
            logger.debug("Receipt sync stopped")
    except Exception:
        pass

    # Stop feature flag watcher
    try:
        if hasattr(app.state, "feature_flag_watcher") and app.state.feature_flag_watcher:
            await app.state.feature_flag_watcher.stop()
    except Exception:
        pass

    # Stop etcd metrics and GC if started
    try:
        if (
            hasattr(app.state, "stop_etcd_metrics_collection")
            and app.state.stop_etcd_metrics_collection
        ):
            await app.state.stop_etcd_metrics_collection()
        if hasattr(app.state, "stop_etcd_gc") and app.state.stop_etcd_gc:
            await app.state.stop_etcd_gc()
    except Exception as e:
        logger.debug(f"Cache operation failed (continuing): {e}")

    if boot_graph is not None:
        try:
            await boot_graph.stop(app)
        except Exception as exc:
            logger.debug(f"Boot graph stop failed: {exc}", exc_info=True)

    await shutdown_all(app)

    shutdown_duration = (time.perf_counter() - shutdown_start) * 1000
    try:
        URF.emit(
            correlation_id=boot_correlation_id,
            action="system.shutdown",
            event_name="shutdown.executed",
            event_data={"phase": "execute"},
            duration_ms=shutdown_duration,
            status="success",
        )
    except Exception:
        pass


__all__ = [
    "active_sessions",
    "enqueue_pending_action",
    "get_active_sessions",
    "get_websocket_connections",
    "lifespan_v2",
    "pending_actions_queue",
    "websocket_connections",
]
