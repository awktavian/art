"""Organism Vitals - Core system health metrics.

Human-friendly vitals reporting:
- Metabolism (activity rate)
- Coherence (stability/success)
- Load (backlog pressure)
- Fano collaboration health
- E8 message bus statistics
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from kagami_api.security import require_auth

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(tags=["vitals"])

    def _interpret_metabolism(value: float) -> dict[str, Any]:
        """Interpret metabolism for humans."""
        if value >= 70:
            return {"status": "high", "label": "High Activity", "color": "#F59E0B", "icon": "🔥"}
        elif value >= 40:
            return {"status": "optimal", "label": "Optimal", "color": "#10B981", "icon": "✨"}
        elif value >= 15:
            return {"status": "low", "label": "Low Activity", "color": "#3B82F6", "icon": "💤"}
        return {"status": "idle", "label": "Idle", "color": "#6B7280", "icon": "⏸️"}

    def _interpret_coherence(value: float) -> dict[str, Any]:
        """Interpret coherence for humans."""
        pct = value * 100
        if value >= 0.95:
            return {
                "status": "excellent",
                "label": f"Excellent ({pct:.0f}%)",
                "color": "#10B981",
                "icon": "🎯",
            }
        elif value >= 0.85:
            return {
                "status": "good",
                "label": f"Good ({pct:.0f}%)",
                "color": "#22D3EE",
                "icon": "✓",
            }
        elif value >= 0.70:
            return {
                "status": "fair",
                "label": f"Fair ({pct:.0f}%)",
                "color": "#F59E0B",
                "icon": "⚠️",
            }
        return {
            "status": "degraded",
            "label": f"Degraded ({pct:.0f}%)",
            "color": "#EF4444",
            "icon": "🔴",
        }

    def _interpret_load(value: float) -> dict[str, Any]:
        """Interpret load for humans."""
        if value >= 80:
            return {"status": "critical", "label": "Critical", "color": "#EF4444", "icon": "🚨"}
        elif value >= 60:
            return {"status": "high", "label": "High", "color": "#F59E0B", "icon": "📈"}
        elif value >= 30:
            return {"status": "normal", "label": "Normal", "color": "#10B981", "icon": "📊"}
        return {"status": "light", "label": "Light", "color": "#3B82F6", "icon": "💨"}

    def _get_e8_bus_stats(organism: Any) -> dict[str, Any]:
        """Get E8 message bus statistics."""
        from kagami.core.events import get_unified_bus

        bus = get_unified_bus()
        stats = bus.get_stats()
        return {
            "status": "active" if stats.get("running") else "stopped",
            "queued": stats.get("queued", 0),
            "recent_events": stats.get("recent_events", 0),
            "subscribers": stats.get("subscribers", {}),
            "use_redis": stats.get("use_redis", False),
        }

    def _compute_core_vitals(organism: Any) -> tuple[float, float, float]:
        """Compute metabolism/coherence/load from UnifiedOrganism state."""
        # Metabolism: intents/sec over uptime
        uptime = max(1e-6, float(getattr(getattr(organism, "stats", None), "uptime", 0.0)))
        total_intents = int(getattr(getattr(organism, "stats", None), "total_intents", 0))
        metabolism = total_intents / uptime

        # Coherence: average colony success_rate
        colonies = getattr(organism, "colonies", {}) or {}
        colony_vals = list(colonies.values()) if isinstance(colonies, dict) else list(colonies)
        if not colony_vals:
            raise RuntimeError("UnifiedOrganism has no colonies")
        success_rates = [
            float(getattr(getattr(c, "stats", None), "success_rate", 0.0)) for c in colony_vals
        ]
        coherence = sum(success_rates) / max(1, len(success_rates))

        # Load: percent of workers currently busy/unavailable
        total_workers = sum(int(c.get_worker_count()) for c in colony_vals)
        available = sum(int(c.get_available_count()) for c in colony_vals)
        if total_workers <= 0:
            raise RuntimeError("UnifiedOrganism has zero workers")
        load = 100.0 * (1.0 - (available / total_workers))

        return metabolism, coherence, load

    @router.get("/")
    async def get_vitals(request: Request, _user=Depends(require_auth)) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        """Get comprehensive organism vitals.

        Returns metabolism, coherence, load with human-friendly interpretation.
        """
        try:
            from kagami.core.unified_agents import get_unified_organism

            organism = get_unified_organism()
            # Ensure colonies initialized for accurate vitals
            _ = organism.colonies
            metabolism, coherence, load = _compute_core_vitals(organism)
        except Exception as e:
            logger.error("Failed to compute vitals: %s", e)
            raise HTTPException(status_code=500, detail=str(e)) from None

        return {
            "timestamp": time.time(),
            "core": {
                "metabolism": {
                    "value": round(metabolism, 2),
                    "interpretation": _interpret_metabolism(metabolism),
                },
                "coherence": {
                    "value": round(coherence, 4),
                    "interpretation": _interpret_coherence(coherence),
                },
                "load": {"value": round(load, 2), "interpretation": _interpret_load(load)},
            },
            "e8_bus": _get_e8_bus_stats(organism),
        }

    @router.get("/summary")
    async def get_vitals_summary(request: Request, _user=Depends(require_auth)) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        """Compact vitals for status bars."""
        from kagami.core.unified_agents import get_unified_organism

        organism = get_unified_organism()
        _ = organism.colonies
        metabolism, coherence, load = _compute_core_vitals(organism)

        if coherence < 0.7 or load > 80:
            return {"status": "attention", "icon": "⚠️", "label": "Needs Attention"}
        if coherence < 0.85 or load > 60:
            return {"status": "nominal", "icon": "📊", "label": "Nominal"}
        return {
            "status": "optimal",
            "icon": "✨",
            "label": "Optimal",
            "metabolism": round(metabolism, 2),
        }

    @router.get("/fano")
    async def get_fano_vitals(request: Request, _user=Depends(require_auth)) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        """Detailed Fano collaboration vitals."""
        try:
            from kagami.core.unified_agents import get_fano_vitals

            fano = get_fano_vitals()
            return fano.get_vitals_snapshot()  # type: ignore[no-any-return, attr-defined]
        except Exception as e:
            logger.error(f"Failed to get Fano vitals: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    # =========================================================================
    # COLONY-LEVEL METRICS (Dec 27, 2025)
    # =========================================================================

    @router.get("/colonies")
    async def get_all_colonies(request: Request, _user=Depends(require_auth)) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        """Get vitals for all 7 colonies.

        Returns detailed metrics for each colony including:
        - Worker counts and availability
        - Success rate and latency
        - Catastrophe dynamics state
        - Circuit breaker status
        """
        from kagami.core.unified_agents import get_unified_organism

        organism = get_unified_organism()
        colonies = organism.colonies

        colony_data = {}
        for idx, colony in enumerate(colonies.values()):
            name = colony.name if hasattr(colony, "name") else f"colony_{idx}"
            stats = getattr(colony, "stats", None)

            colony_data[name] = {
                "index": idx,
                "name": name,
                "catastrophe_type": getattr(colony, "catastrophe_type", "unknown"),
                "workers": {
                    "total": colony.get_worker_count(),
                    "available": colony.get_available_count(),
                    "busy": colony.get_worker_count() - colony.get_available_count(),
                },
                "performance": {
                    "success_rate": getattr(stats, "success_rate", 0.0) if stats else 0.0,
                    "avg_latency": getattr(stats, "avg_latency", 0.0) if stats else 0.0,
                    "total_tasks": getattr(stats, "total_tasks", 0) if stats else 0,
                },
                "queue_depth": getattr(colony, "queue_depth", 0),
            }

        return {
            "timestamp": time.time(),
            "colony_count": len(colony_data),
            "colonies": colony_data,
        }

    @router.get("/colonies/{colony_id}")
    async def get_colony_detail(  # type: ignore[no-untyped-def]
        request: Request,
        colony_id: int,
        _user=Depends(require_auth),
    ) -> dict[str, Any]:
        """Get detailed vitals for a specific colony.

        Args:
            colony_id: Colony index (0-6) or name

        Returns:
            Detailed colony metrics including worker-level data
        """
        from kagami.core.unified_agents import get_unified_organism

        if not 0 <= colony_id <= 6:
            raise HTTPException(status_code=400, detail="colony_id must be 0-6")

        organism = get_unified_organism()
        colony = organism.get_colony_by_index(colony_id)

        if colony is None:
            raise HTTPException(status_code=404, detail=f"Colony {colony_id} not found")

        stats = getattr(colony, "stats", None)
        name = colony.name if hasattr(colony, "name") else f"colony_{colony_id}"

        # Get worker details
        workers = []
        if hasattr(colony, "workers"):
            for worker in colony.workers:
                worker_stats = worker.get_stats() if hasattr(worker, "get_stats") else {}
                workers.append(
                    {
                        "worker_id": getattr(worker, "worker_id", "unknown"),
                        "status": getattr(worker.state, "status", "unknown").value  # type: ignore[union-attr]
                        if hasattr(worker, "state")
                        else "unknown",
                        "fitness": getattr(worker.state, "fitness", 0.0)
                        if hasattr(worker, "state")
                        else 0.0,
                        "completed": getattr(worker.state, "completed_tasks", 0)
                        if hasattr(worker, "state")
                        else 0,
                        "failed": getattr(worker.state, "failed_tasks", 0)
                        if hasattr(worker, "state")
                        else 0,
                        **worker_stats,
                    }
                )

        # Circuit breaker status if available
        circuit_breaker = None
        if hasattr(colony, "circuit_breaker"):
            cb = colony.circuit_breaker
            circuit_breaker = cb.get_stats() if hasattr(cb, "get_stats") else None

        return {
            "timestamp": time.time(),
            "colony": {
                "index": colony_id,
                "name": name,
                "catastrophe_type": getattr(colony, "catastrophe_type", "unknown"),
                "basis_vector": f"e_{colony_id + 1}",
            },
            "workers": {
                "total": colony.get_worker_count(),
                "available": colony.get_available_count(),
                "details": workers,
            },
            "performance": {
                "success_rate": getattr(stats, "success_rate", 0.0) if stats else 0.0,
                "avg_latency": getattr(stats, "avg_latency", 0.0) if stats else 0.0,
                "total_tasks": getattr(stats, "total_tasks", 0) if stats else 0,
                "total_intents": getattr(stats, "total_intents", 0) if stats else 0,
            },
            "queue_depth": getattr(colony, "queue_depth", 0),
            "circuit_breaker": circuit_breaker,
        }

    @router.get("/scaling")
    async def get_scaling_status(request: Request, _user=Depends(require_auth)) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        """Get auto-scaling status and metrics.

        Returns current scaling state, recent decisions, and configuration.
        """
        from kagami.core.unified_agents import get_unified_organism

        organism = get_unified_organism()

        # Get auto-scaler if available
        scaler_stats = None
        if hasattr(organism, "auto_scaler"):
            scaler = organism.auto_scaler
            scaler_stats = scaler.get_stats() if hasattr(scaler, "get_stats") else None

        # Per-colony worker counts
        colony_workers = {}
        for idx in range(7):
            colony = organism.get_colony_by_index(idx)
            if colony:
                name = colony.name if hasattr(colony, "name") else f"colony_{idx}"
                colony_workers[name] = {
                    "total": colony.get_worker_count(),
                    "available": colony.get_available_count(),
                }

        return {
            "timestamp": time.time(),
            "auto_scaler": scaler_stats,
            "colony_workers": colony_workers,
            "total_workers": sum(c["total"] for c in colony_workers.values()),
            "total_available": sum(c["available"] for c in colony_workers.values()),
        }

    return router
