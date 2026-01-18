"""Comprehensive Health Check Endpoints — Kubernetes-ready health probes.

This module provides health check endpoints following Kubernetes best practices:
- /health/live — Liveness probe (is the process alive?)
- /health/ready — Readiness probe (can it serve traffic?)
- /health/startup — Startup probe (has it finished starting?)
- /health/deep — Deep health check (all dependencies)

Architecture:
```
    Probe Type          What It Checks              Failure Response
    ──────────          ──────────────              ────────────────
    Liveness        →   Process running         →   Restart container
    Readiness       →   Can serve requests      →   Remove from LB
    Startup         →   Initialization done     →   Wait for startup
    Deep            →   All dependencies        →   Detailed diagnostics
```

Colony: Crystal (D₅) — Verification and validation
h(x) ≥ 0. Always.

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fastapi import APIRouter, Response, status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


# =============================================================================
# Health Status Types
# =============================================================================


class HealthStatus(str, Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class DependencyType(str, Enum):
    """Types of dependencies to check."""

    DATABASE = "database"
    CACHE = "cache"
    MESSAGE_QUEUE = "message_queue"
    EXTERNAL_API = "external_api"
    FILE_SYSTEM = "file_system"
    CONSENSUS = "consensus"
    SERVICE_REGISTRY = "service_registry"


@dataclass
class DependencyHealth:
    """Health status of a single dependency."""

    name: str
    type: DependencyType
    status: HealthStatus
    latency_ms: float | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
        }
        if self.latency_ms is not None:
            result["latency_ms"] = self.latency_ms
        if self.message:
            result["message"] = self.message
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class HealthReport:
    """Complete health report."""

    status: HealthStatus
    timestamp: float = field(default_factory=time.time)
    version: str = "1.0.0"
    uptime_seconds: float = 0.0
    dependencies: list[DependencyHealth] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "timestamp": self.timestamp,
            "version": self.version,
            "uptime_seconds": self.uptime_seconds,
            "dependencies": [d.to_dict() for d in self.dependencies],
        }


# =============================================================================
# Health Check Manager
# =============================================================================


class HealthCheckManager:
    """Manages health checks for the application.

    Features:
    - Configurable dependency checks
    - Caching to prevent check storms
    - Timeout handling
    - Detailed diagnostics
    """

    def __init__(self) -> None:
        """Initialize the health check manager."""
        self._start_time = time.time()
        self._is_ready = False
        self._is_started = False

        # Cache settings
        self._cache_ttl_seconds = 5.0
        self._last_deep_check: HealthReport | None = None
        self._last_deep_check_time = 0.0

        # Check timeout
        self._check_timeout_seconds = 5.0

    @property
    def uptime_seconds(self) -> float:
        """Get application uptime in seconds."""
        return time.time() - self._start_time

    def mark_started(self) -> None:
        """Mark the application as started."""
        self._is_started = True
        logger.info("Health: Application marked as started")

    def mark_ready(self) -> None:
        """Mark the application as ready to serve traffic."""
        self._is_ready = True
        logger.info("Health: Application marked as ready")

    def mark_not_ready(self) -> None:
        """Mark the application as not ready."""
        self._is_ready = False
        logger.info("Health: Application marked as not ready")

    async def check_liveness(self) -> HealthReport:
        """Check if the application is alive.

        This is a minimal check — if we can respond, we're alive.

        Returns:
            Health report.
        """
        return HealthReport(
            status=HealthStatus.HEALTHY,
            uptime_seconds=self.uptime_seconds,
        )

    async def check_readiness(self) -> HealthReport:
        """Check if the application is ready to serve traffic.

        Returns:
            Health report.
        """
        status = HealthStatus.HEALTHY if self._is_ready else HealthStatus.UNHEALTHY

        return HealthReport(
            status=status,
            uptime_seconds=self.uptime_seconds,
        )

    async def check_startup(self) -> HealthReport:
        """Check if the application has finished starting.

        Returns:
            Health report.
        """
        status = HealthStatus.HEALTHY if self._is_started else HealthStatus.UNHEALTHY

        return HealthReport(
            status=status,
            uptime_seconds=self.uptime_seconds,
        )

    async def check_deep(self, use_cache: bool = True) -> HealthReport:
        """Perform a deep health check of all dependencies.

        Args:
            use_cache: Whether to use cached results.

        Returns:
            Detailed health report.
        """
        # Check cache
        if use_cache and self._last_deep_check:
            elapsed = time.time() - self._last_deep_check_time
            if elapsed < self._cache_ttl_seconds:
                return self._last_deep_check

        # Perform checks
        dependencies = await self._check_all_dependencies()

        # Determine overall status
        statuses = [d.status for d in dependencies]
        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall_status = HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.UNKNOWN

        report = HealthReport(
            status=overall_status,
            uptime_seconds=self.uptime_seconds,
            dependencies=dependencies,
        )

        # Update cache
        self._last_deep_check = report
        self._last_deep_check_time = time.time()

        return report

    async def _check_all_dependencies(self) -> list[DependencyHealth]:
        """Check all dependencies."""
        checks = [
            self._check_redis(),
            self._check_etcd(),
            self._check_consensus(),
            self._check_service_registry(),
            self._check_filesystem(),
        ]

        results = await asyncio.gather(*checks, return_exceptions=True)

        dependencies = []
        for result in results:
            if isinstance(result, Exception):
                dependencies.append(
                    DependencyHealth(
                        name="unknown",
                        type=DependencyType.EXTERNAL_API,
                        status=HealthStatus.UNHEALTHY,
                        message=str(result),
                    )
                )
            else:
                dependencies.append(result)

        return dependencies

    async def _check_redis(self) -> DependencyHealth:
        """Check Redis connectivity."""
        try:
            start = time.time()

            # Try to import and ping Redis
            try:
                from kagami.core.cache import get_cache

                cache = await get_cache()
                await asyncio.wait_for(
                    cache.ping(),
                    timeout=self._check_timeout_seconds,
                )
                latency = (time.time() - start) * 1000

                return DependencyHealth(
                    name="redis",
                    type=DependencyType.CACHE,
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency,
                )
            except ImportError:
                return DependencyHealth(
                    name="redis",
                    type=DependencyType.CACHE,
                    status=HealthStatus.UNKNOWN,
                    message="Redis module not available",
                )
            except TimeoutError:
                return DependencyHealth(
                    name="redis",
                    type=DependencyType.CACHE,
                    status=HealthStatus.UNHEALTHY,
                    message="Connection timeout",
                )
        except Exception as e:
            return DependencyHealth(
                name="redis",
                type=DependencyType.CACHE,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )

    async def _check_etcd(self) -> DependencyHealth:
        """Check etcd connectivity."""
        try:
            start = time.time()

            try:
                from kagami.core.consensus.etcd_client import get_etcd_client

                client = await get_etcd_client()

                # Try a simple get operation
                await asyncio.wait_for(
                    client.get("/health/ping"),
                    timeout=self._check_timeout_seconds,
                )
                latency = (time.time() - start) * 1000

                return DependencyHealth(
                    name="etcd",
                    type=DependencyType.CONSENSUS,
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency,
                )
            except ImportError:
                return DependencyHealth(
                    name="etcd",
                    type=DependencyType.CONSENSUS,
                    status=HealthStatus.UNKNOWN,
                    message="etcd module not available",
                )
            except TimeoutError:
                return DependencyHealth(
                    name="etcd",
                    type=DependencyType.CONSENSUS,
                    status=HealthStatus.UNHEALTHY,
                    message="Connection timeout",
                )
        except Exception as e:
            return DependencyHealth(
                name="etcd",
                type=DependencyType.CONSENSUS,
                status=HealthStatus.DEGRADED,
                message=str(e),
            )

    async def _check_consensus(self) -> DependencyHealth:
        """Check PBFT consensus status."""
        try:
            try:
                from kagami.core.consensus import get_pbft_node

                node = await get_pbft_node()

                if node and node.is_leader:
                    return DependencyHealth(
                        name="pbft_consensus",
                        type=DependencyType.CONSENSUS,
                        status=HealthStatus.HEALTHY,
                        details={"is_leader": True},
                    )
                elif node:
                    return DependencyHealth(
                        name="pbft_consensus",
                        type=DependencyType.CONSENSUS,
                        status=HealthStatus.HEALTHY,
                        details={"is_leader": False},
                    )
                else:
                    return DependencyHealth(
                        name="pbft_consensus",
                        type=DependencyType.CONSENSUS,
                        status=HealthStatus.DEGRADED,
                        message="PBFT node not initialized",
                    )
            except ImportError:
                return DependencyHealth(
                    name="pbft_consensus",
                    type=DependencyType.CONSENSUS,
                    status=HealthStatus.UNKNOWN,
                    message="PBFT module not available",
                )
        except Exception as e:
            return DependencyHealth(
                name="pbft_consensus",
                type=DependencyType.CONSENSUS,
                status=HealthStatus.DEGRADED,
                message=str(e),
            )

    async def _check_service_registry(self) -> DependencyHealth:
        """Check service registry status."""
        try:
            try:
                from kagami.core.cluster import get_service_registry

                registry = await get_service_registry()

                services = await registry.get_services()
                healthy_count = sum(1 for s in services if s.health.value == "healthy")

                return DependencyHealth(
                    name="service_registry",
                    type=DependencyType.SERVICE_REGISTRY,
                    status=HealthStatus.HEALTHY,
                    details={
                        "total_services": len(services),
                        "healthy_services": healthy_count,
                    },
                )
            except ImportError:
                return DependencyHealth(
                    name="service_registry",
                    type=DependencyType.SERVICE_REGISTRY,
                    status=HealthStatus.UNKNOWN,
                    message="Service registry module not available",
                )
        except Exception as e:
            return DependencyHealth(
                name="service_registry",
                type=DependencyType.SERVICE_REGISTRY,
                status=HealthStatus.DEGRADED,
                message=str(e),
            )

    async def _check_filesystem(self) -> DependencyHealth:
        """Check filesystem access."""
        try:
            start = time.time()

            # Check if we can write to temp directory
            test_file = f"/tmp/kagami_health_check_{os.getpid()}"
            try:
                with open(test_file, "w") as f:
                    f.write("health_check")
                os.remove(test_file)

                latency = (time.time() - start) * 1000

                return DependencyHealth(
                    name="filesystem",
                    type=DependencyType.FILE_SYSTEM,
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency,
                )
            except OSError as e:
                return DependencyHealth(
                    name="filesystem",
                    type=DependencyType.FILE_SYSTEM,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                )
        except Exception as e:
            return DependencyHealth(
                name="filesystem",
                type=DependencyType.FILE_SYSTEM,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )


# =============================================================================
# Singleton
# =============================================================================


_health_manager: HealthCheckManager | None = None


def get_health_manager() -> HealthCheckManager:
    """Get or create the health check manager singleton."""
    global _health_manager

    if _health_manager is None:
        _health_manager = HealthCheckManager()

    return _health_manager


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/live")
async def liveness_probe(response: Response) -> dict[str, Any]:
    """Liveness probe — is the process alive?

    Returns 200 if the process is alive and can respond.
    Kubernetes uses this to determine if a container should be restarted.
    """
    manager = get_health_manager()
    report = await manager.check_liveness()

    return {"status": report.status.value}


@router.get("/ready")
async def readiness_probe(response: Response) -> dict[str, Any]:
    """Readiness probe — can the application serve traffic?

    Returns 200 if the application is ready to receive requests.
    Returns 503 if not ready (e.g., still starting up or draining).
    """
    manager = get_health_manager()
    report = await manager.check_readiness()

    if report.status != HealthStatus.HEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": report.status.value}


@router.get("/startup")
async def startup_probe(response: Response) -> dict[str, Any]:
    """Startup probe — has the application finished starting?

    Returns 200 once startup is complete.
    Returns 503 while still starting up.
    """
    manager = get_health_manager()
    report = await manager.check_startup()

    if report.status != HealthStatus.HEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": report.status.value}


@router.get("/deep")
async def deep_health_check(
    response: Response,
    force: bool = False,
) -> dict[str, Any]:
    """Deep health check — comprehensive dependency check.

    Checks all dependencies and returns detailed status.

    Args:
        force: If True, bypass cache and perform fresh checks.
    """
    manager = get_health_manager()
    report = await manager.check_deep(use_cache=not force)

    if report.status == HealthStatus.UNHEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif report.status == HealthStatus.DEGRADED:
        response.status_code = status.HTTP_207_MULTI_STATUS

    return report.to_dict()


@router.get("")
async def health_summary() -> dict[str, Any]:
    """Quick health summary."""
    manager = get_health_manager()

    return {
        "status": "healthy" if manager._is_ready else "not_ready",
        "uptime_seconds": manager.uptime_seconds,
        "started": manager._is_started,
        "ready": manager._is_ready,
    }


# =============================================================================
# 鏡
# Health is measurable. Observable. Verifiable. h(x) ≥ 0. Always.
# =============================================================================
