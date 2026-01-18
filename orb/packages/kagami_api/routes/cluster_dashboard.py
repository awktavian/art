"""Cluster Observability Dashboard — Real-time cluster health and metrics.

This module provides API endpoints for the cluster observability dashboard,
exposing real-time metrics on service health, consensus performance, and
distributed state.

Endpoints:
- GET /api/v1/cluster/dashboard — Full dashboard view
- GET /api/v1/cluster/health — Cluster health summary
- GET /api/v1/cluster/services — Service registry status
- GET /api/v1/cluster/consensus — Consensus metrics
- GET /api/v1/cluster/performance — Performance metrics
- GET /api/v1/cluster/homeostasis — Organism homeostasis state

Colony: Grove (D₄⁻) — Observation and documentation
h(x) ≥ 0. Always.

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cluster"])


# =============================================================================
# Dashboard Endpoint
# =============================================================================


@router.get("/dashboard")
async def get_cluster_dashboard(request: Request) -> dict[str, Any]:
    """Get complete cluster dashboard.

    Returns comprehensive view of cluster state including:
    - Overall health status
    - Service registry summary
    - Consensus performance metrics
    - Homeostasis state
    - Recent events

    Returns:
        Complete dashboard data.
    """
    dashboard = {
        "timestamp": time.time(),
        "cluster_id": getattr(request.app.state, "cluster_id", "kagami-primary"),
        "health": {},
        "services": {},
        "consensus": {},
        "performance": {},
        "homeostasis": {},
        "alerts": [],
    }

    # Gather data in parallel
    tasks = {
        "health": _get_cluster_health(),
        "services": _get_service_summary(),
        "consensus": _get_consensus_metrics(),
        "performance": _get_performance_metrics(),
        "homeostasis": _get_homeostasis_state(),
    }

    results = await asyncio.gather(
        *tasks.values(),
        return_exceptions=True,
    )

    for key, result in zip(tasks.keys(), results, strict=False):
        if isinstance(result, Exception):
            logger.warning(f"Dashboard section {key} failed: {result}")
            dashboard[key] = {"error": str(result)}
        else:
            dashboard[key] = result

    # Generate alerts from data
    dashboard["alerts"] = _generate_alerts(dashboard)

    return dashboard


# =============================================================================
# Health Endpoint
# =============================================================================


@router.get("/health")
async def get_cluster_health() -> dict[str, Any]:
    """Get cluster health summary.

    Returns:
        Health summary with status for each subsystem.
    """
    return await _get_cluster_health()


async def _get_cluster_health() -> dict[str, Any]:
    """Internal: Get cluster health."""
    health = {
        "overall": "healthy",
        "subsystems": {},
        "checks": [],
    }

    # Check etcd (optional in dev)
    try:
        from kagami.core.consensus.etcd_client import get_etcd_pool

        etcd = await get_etcd_pool()
        await etcd.status()
        health["subsystems"]["etcd"] = "healthy"
        health["checks"].append({"name": "etcd", "status": "pass", "latency_ms": 0})
    except Exception:
        health["subsystems"]["etcd"] = "unavailable"
        health["checks"].append(
            {"name": "etcd", "status": "skip", "error": "etcd not running (optional in dev)"}
        )
        # Don't degrade overall health for etcd in dev mode
        import os

        if os.getenv("ENVIRONMENT", "development") == "production":
            health["overall"] = "degraded"

    # Check Redis
    try:
        from kagami.core.caching.redis import RedisClientFactory

        redis = RedisClientFactory.get_client()
        await redis.ping()
        health["subsystems"]["redis"] = "healthy"
        health["checks"].append({"name": "redis", "status": "pass", "latency_ms": 0})
    except Exception as e:
        health["subsystems"]["redis"] = "unhealthy"
        health["checks"].append({"name": "redis", "status": "fail", "error": str(e)})
        health["overall"] = "degraded"

    # Check service registry (graceful fallback)
    try:
        from kagami.core.cluster.service_registry import get_service_registry

        registry = await get_service_registry()
        stats = registry.get_stats()
        health["subsystems"]["service_registry"] = "healthy"
        health["checks"].append(
            {
                "name": "service_registry",
                "status": "pass",
                "total_services": stats.get("total_healthy", 0),
            }
        )
    except Exception:
        # Service registry depends on etcd, so gracefully skip
        health["subsystems"]["service_registry"] = "unavailable"
        health["checks"].append(
            {"name": "service_registry", "status": "skip", "error": "requires etcd"}
        )

    return health


# =============================================================================
# Services Endpoint
# =============================================================================


@router.get("/services")
async def get_services() -> dict[str, Any]:
    """Get service registry summary.

    Returns:
        Service summary by type with health status.
    """
    return await _get_service_summary()


async def _get_service_summary() -> dict[str, Any]:
    """Internal: Get service summary from real service registry.

    Returns only actually registered services. No fallbacks, no demos.
    """
    from kagami.core.cluster.service_registry import (
        ServiceType,
        get_service_registry,
    )

    summary = {
        "total_services": 0,
        "healthy_services": 0,
        "by_type": {},
        "instances": [],
    }

    try:
        registry = await get_service_registry()

        # Debug: Log what's in the registry
        import sys

        print(
            f"[DEBUG] Registry id={id(registry)}, in_memory={registry._in_memory_mode}",
            file=sys.stderr,
            flush=True,
        )
        for st in ServiceType:
            cached = list(registry._services[st].keys())
            print(f"[DEBUG] {st.value}: {cached}", file=sys.stderr, flush=True)

        for service_type in ServiceType:
            services = await registry.discover(
                service_type,
                healthy_only=False,
                trusted_only=False,
            )
            print(
                f"[DEBUG] discover({service_type.value}): {len(services)} services",
                file=sys.stderr,
                flush=True,
            )

            healthy = [s for s in services if s.is_healthy]

            summary["by_type"][service_type.value] = {
                "total": len(services),
                "healthy": len(healthy),
                "instances": [
                    {
                        "node_id": s.node_id,
                        "address": s.address,
                        "port": s.port,
                        "health": s.health.value,
                        "byzantine_score": s.byzantine_score,
                        "service_type": service_type.value,
                        "metadata": s.metadata,
                    }
                    for s in services
                ],
            }

            summary["total_services"] += len(services)
            summary["healthy_services"] += len(healthy)
            summary["instances"].extend([s.to_dict() for s in services])

    except Exception as e:
        logger.warning(f"Service registry query failed: {e}")
        # Initialize empty by_type for all service types
        for service_type in ServiceType:
            summary["by_type"][service_type.value] = {
                "total": 0,
                "healthy": 0,
                "instances": [],
            }

    return summary


# =============================================================================
# Consensus Endpoint
# =============================================================================


@router.get("/consensus")
async def get_consensus_metrics() -> dict[str, Any]:
    """Get consensus system metrics.

    Returns:
        Consensus metrics including CRDT state, PBFT stats.
    """
    return await _get_consensus_metrics()


async def _get_consensus_metrics() -> dict[str, Any]:
    """Internal: Get consensus metrics."""
    metrics = {
        "crdt": {},
        "pbft": {},
        "colony_consensus": {},
    }

    # CRDT state
    try:
        from kagami.core.coordination.cross_hub_crdt import get_cross_hub_crdt_manager

        crdt = await get_cross_hub_crdt_manager()
        metrics["crdt"] = crdt.get_sync_status()
    except Exception as e:
        metrics["crdt"] = {"error": str(e)}

    # PBFT stats (if available)
    try:
        from kagami.core.consensus.critical_pbft import get_critical_pbft_coordinator_sync

        coordinator = get_critical_pbft_coordinator_sync()
        if coordinator:
            metrics["pbft"] = {
                "initialized": coordinator._initialized,
                # Add more PBFT metrics as needed
            }
        else:
            metrics["pbft"] = {"initialized": False}
    except Exception as e:
        metrics["pbft"] = {"error": str(e)}

    # Colony consensus
    try:
        from kagami.core.coordination.colony_consensus import get_colony_consensus_sync

        colony = get_colony_consensus_sync()
        if colony:
            metrics["colony_consensus"] = {
                "active_colonies": len(colony._colonies) if hasattr(colony, "_colonies") else 0,
            }
        else:
            metrics["colony_consensus"] = {"active": False}
    except Exception as e:
        metrics["colony_consensus"] = {"error": str(e)}

    return metrics


# =============================================================================
# Performance Endpoint
# =============================================================================


@router.get("/performance")
async def get_performance() -> dict[str, Any]:
    """Get performance metrics.

    Returns:
        Performance dashboard with latency stats, cache metrics.
    """
    return await _get_performance_metrics()


async def _get_performance_metrics() -> dict[str, Any]:
    """Internal: Get performance metrics."""
    try:
        from kagami.core.consensus.performance import get_performance_monitor

        monitor = get_performance_monitor()
        return monitor.get_dashboard()
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        return {"error": str(e)}


# =============================================================================
# Homeostasis Endpoint
# =============================================================================


@router.get("/homeostasis")
async def get_homeostasis() -> dict[str, Any]:
    """Get organism homeostasis state.

    Returns:
        Current homeostasis state including colony populations, vitals.
    """
    return await _get_homeostasis_state()


async def _get_homeostasis_state() -> dict[str, Any]:
    """Internal: Get homeostasis state."""
    try:
        from kagami.core.consensus.homeostasis_sync import get_homeostasis_sync

        sync = await get_homeostasis_sync()

        local_state = sync._local_state
        global_state = await sync.get_global_state()

        return {
            "local_instance": local_state.to_dict() if local_state else None,
            "global_state": global_state.to_dict() if global_state else None,
            "instance_count": global_state.instance_count if global_state else 0,
            "total_population": global_state.total_population if global_state else 0,
        }
    except Exception as e:
        logger.error(f"Failed to get homeostasis state: {e}")
        return {"error": str(e)}


# =============================================================================
# Alerts Generation
# =============================================================================


def _generate_alerts(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate alerts from dashboard data.

    Args:
        dashboard: Full dashboard data.

    Returns:
        List of alerts.
    """
    alerts: list[dict[str, Any]] = []

    # Check overall health
    health = dashboard.get("health", {})
    if health.get("overall") != "healthy":
        alerts.append(
            {
                "level": "warning",
                "message": f"Cluster health is {health.get('overall', 'unknown')}",
                "source": "health",
            }
        )

    # Check for unhealthy subsystems
    for subsystem, status in health.get("subsystems", {}).items():
        if status == "unhealthy":
            alerts.append(
                {
                    "level": "error",
                    "message": f"Subsystem {subsystem} is unhealthy",
                    "source": "subsystems",
                }
            )

    # Check service health
    services = dashboard.get("services", {})
    total = services.get("total_services", 0)
    healthy = services.get("healthy_services", 0)
    if total > 0 and healthy < total:
        unhealthy = total - healthy
        alerts.append(
            {
                "level": "warning",
                "message": f"{unhealthy} services are unhealthy",
                "source": "services",
            }
        )

    # Check performance SLO
    performance = dashboard.get("performance", {})
    slo_compliance = performance.get("slo_compliance", {})
    for op_type, compliant in slo_compliance.items():
        if not compliant:
            alerts.append(
                {
                    "level": "warning",
                    "message": f"SLO violation for {op_type}",
                    "source": "performance",
                }
            )

    # Check homeostasis
    homeostasis = dashboard.get("homeostasis", {})
    if homeostasis.get("instance_count", 0) == 0:
        alerts.append(
            {
                "level": "info",
                "message": "No homeostasis instances registered",
                "source": "homeostasis",
            }
        )

    return alerts


# =============================================================================
# Export
# =============================================================================

__all__ = ["router"]


# =============================================================================
# 鏡
# Dashboard reveals. Metrics guide. The organism observes itself.
# h(x) ≥ 0. Always.
# =============================================================================
