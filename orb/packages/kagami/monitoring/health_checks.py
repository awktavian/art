"""Comprehensive Health Check System.

Multi-layered health monitoring for production readiness:
- Service health checks (deep & shallow)
- Dependency health monitoring
- Resource constraint validation
- Integration connectivity tests
- Performance health scoring
- Automated remediation triggers

Implements health check standards for Kubernetes readiness/liveness.

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import aiohttp
import psutil

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status levels."""

    HEALTHY = "healthy"  # All checks passing
    DEGRADED = "degraded"  # Some non-critical issues
    UNHEALTHY = "unhealthy"  # Critical issues present
    UNKNOWN = "unknown"  # Unable to determine health


class HealthCheckType(str, Enum):
    """Types of health checks."""

    READINESS = "readiness"  # Service ready to receive traffic
    LIVENESS = "liveness"  # Service is alive and responsive
    DEPENDENCY = "dependency"  # External dependency health
    RESOURCE = "resource"  # System resource availability
    FUNCTIONAL = "functional"  # Feature-specific functionality


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    check_type: HealthCheckType
    duration_ms: float
    message: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class HealthCheckDefinition:
    """Definition of a health check."""

    name: str
    check_type: HealthCheckType
    check_function: Callable[[], Any]
    interval_seconds: int = 30
    timeout_seconds: int = 10
    critical: bool = True  # If False, failure won't mark service as unhealthy
    enabled: bool = True
    description: str = ""
    tags: dict[str, str] = field(default_factory=dict)


class HealthCheckManager:
    """Comprehensive health check management system.

    Provides multi-layered health monitoring:
    - Service readiness/liveness checks
    - Dependency health monitoring
    - Resource constraint validation
    - Performance health scoring
    - Automated remediation triggers
    """

    def __init__(self):
        # Health check definitions
        self._checks: dict[str, HealthCheckDefinition] = {}

        # Health check results
        self._results: dict[str, HealthCheckResult] = {}
        self._result_history: dict[str, list[HealthCheckResult]] = defaultdict(list)

        # Monitoring state
        self._running = False
        self._check_tasks: dict[str, asyncio.Task] = {}

        # Remediation callbacks
        self._remediation_callbacks: dict[str, list[Callable[[HealthCheckResult], None]]] = (
            defaultdict(list)
        )

        # Health score calculation
        self._health_weights: dict[str, float] = {}

        # System info
        self._process = psutil.Process()
        self._start_time = time.time()

        # Setup default health checks
        self._setup_default_checks()

    def _setup_default_checks(self) -> None:
        """Set up default health checks."""
        # System resource checks
        self.register_check(
            HealthCheckDefinition(
                name="memory_usage",
                check_type=HealthCheckType.RESOURCE,
                check_function=self._check_memory_usage,
                interval_seconds=30,
                critical=True,
                description="Memory usage within acceptable limits",
            )
        )

        self.register_check(
            HealthCheckDefinition(
                name="cpu_usage",
                check_type=HealthCheckType.RESOURCE,
                check_function=self._check_cpu_usage,
                interval_seconds=30,
                critical=False,
                description="CPU usage within acceptable limits",
            )
        )

        self.register_check(
            HealthCheckDefinition(
                name="disk_space",
                check_type=HealthCheckType.RESOURCE,
                check_function=self._check_disk_space,
                interval_seconds=60,
                critical=True,
                description="Adequate disk space available",
            )
        )

        # Network connectivity
        self.register_check(
            HealthCheckDefinition(
                name="network_connectivity",
                check_type=HealthCheckType.DEPENDENCY,
                check_function=self._check_network_connectivity,
                interval_seconds=60,
                critical=True,
                description="Basic network connectivity",
            )
        )

        # Application liveness
        self.register_check(
            HealthCheckDefinition(
                name="application_liveness",
                check_type=HealthCheckType.LIVENESS,
                check_function=self._check_application_liveness,
                interval_seconds=15,
                critical=True,
                description="Application is responsive",
            )
        )

        # Database connectivity (if applicable)
        self.register_check(
            HealthCheckDefinition(
                name="database_connectivity",
                check_type=HealthCheckType.DEPENDENCY,
                check_function=self._check_database_connectivity,
                interval_seconds=45,
                critical=True,
                description="Database connection healthy",
            )
        )

        # Redis connectivity
        self.register_check(
            HealthCheckDefinition(
                name="redis_connectivity",
                check_type=HealthCheckType.DEPENDENCY,
                check_function=self._check_redis_connectivity,
                interval_seconds=45,
                critical=False,
                description="Redis connection healthy",
            )
        )

    async def start(self) -> None:
        """Start health check monitoring."""
        if self._running:
            return

        self._running = True

        # Start health check tasks
        for name, check_def in self._checks.items():
            if check_def.enabled:
                self._check_tasks[name] = asyncio.create_task(self._run_check_loop(name, check_def))

        logger.info("🏥 Health check manager started")

    async def stop(self) -> None:
        """Stop health check monitoring."""
        self._running = False

        # Cancel all check tasks
        for task in self._check_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        if self._check_tasks:
            await asyncio.gather(*self._check_tasks.values(), return_exceptions=True)

        self._check_tasks.clear()
        logger.info("🏥 Health check manager stopped")

    def register_check(self, check_def: HealthCheckDefinition) -> None:
        """Register a new health check."""
        self._checks[check_def.name] = check_def

        # Set default weight for health score calculation
        if check_def.name not in self._health_weights:
            weight = 2.0 if check_def.critical else 1.0
            self._health_weights[check_def.name] = weight

        logger.info(f"🏥 Health check registered: {check_def.name}")

    def set_health_weight(self, check_name: str, weight: float) -> None:
        """Set weight for health check in overall score calculation."""
        self._health_weights[check_name] = weight

    def on_unhealthy(self, check_name: str, callback: Callable[[HealthCheckResult], None]) -> None:
        """Register callback for when a specific check becomes unhealthy."""
        self._remediation_callbacks[check_name].append(callback)

    async def _run_check_loop(self, name: str, check_def: HealthCheckDefinition) -> None:
        """Run health check in a loop."""
        while self._running:
            try:
                result = await self._execute_check(check_def)
                self._results[name] = result
                self._result_history[name].append(result)

                # Keep only recent results (last 100)
                if len(self._result_history[name]) > 100:
                    self._result_history[name] = self._result_history[name][-100:]

                # Trigger remediation callbacks if unhealthy
                if result.status == HealthStatus.UNHEALTHY:
                    for callback in self._remediation_callbacks[name]:
                        try:
                            callback(result)
                        except Exception as e:
                            logger.error(f"Remediation callback error for {name}: {e}")

                await asyncio.sleep(check_def.interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error for {name}: {e}")
                await asyncio.sleep(check_def.interval_seconds)

    async def _execute_check(self, check_def: HealthCheckDefinition) -> HealthCheckResult:
        """Execute a single health check."""
        start_time = time.time()

        try:
            # Execute check with timeout
            result = await asyncio.wait_for(
                self._run_check_function(check_def.check_function),
                timeout=check_def.timeout_seconds,
            )

            duration_ms = (time.time() - start_time) * 1000

            if isinstance(result, HealthCheckResult):
                result.duration_ms = duration_ms
                return result
            else:
                # Simple boolean result
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                return HealthCheckResult(
                    name=check_def.name,
                    status=status,
                    check_type=check_def.check_type,
                    duration_ms=duration_ms,
                    message="Check passed" if result else "Check failed",
                    timestamp=time.time(),
                )

        except TimeoutError:
            duration_ms = check_def.timeout_seconds * 1000
            return HealthCheckResult(
                name=check_def.name,
                status=HealthStatus.UNHEALTHY,
                check_type=check_def.check_type,
                duration_ms=duration_ms,
                message=f"Health check timed out after {check_def.timeout_seconds}s",
                timestamp=time.time(),
                error="timeout",
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=check_def.name,
                status=HealthStatus.UNHEALTHY,
                check_type=check_def.check_type,
                duration_ms=duration_ms,
                message=f"Health check failed: {e!s}",
                timestamp=time.time(),
                error=str(e),
            )

    async def _run_check_function(self, check_function: Callable) -> Any:
        """Run check function (async or sync)."""
        if asyncio.iscoroutinefunction(check_function):
            return await check_function()
        else:
            return check_function()

    # Default health check implementations

    def _check_memory_usage(self) -> HealthCheckResult:
        """Check memory usage health."""
        try:
            memory_percent = self._process.memory_percent()
            memory_info = self._process.memory_info()
            rss_mb = memory_info.rss / (1024 * 1024)

            # Thresholds
            warning_percent = 80.0
            critical_percent = 95.0
            critical_rss_mb = 1024  # 1GB

            if memory_percent > critical_percent or rss_mb > critical_rss_mb:
                status = HealthStatus.UNHEALTHY
                message = f"Critical memory usage: {memory_percent:.1f}% ({rss_mb:.1f}MB)"
            elif memory_percent > warning_percent:
                status = HealthStatus.DEGRADED
                message = f"High memory usage: {memory_percent:.1f}% ({rss_mb:.1f}MB)"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {memory_percent:.1f}% ({rss_mb:.1f}MB)"

            return HealthCheckResult(
                name="memory_usage",
                status=status,
                check_type=HealthCheckType.RESOURCE,
                duration_ms=0,
                message=message,
                timestamp=time.time(),
                metadata={
                    "memory_percent": memory_percent,
                    "rss_mb": rss_mb,
                    "vms_mb": memory_info.vms / (1024 * 1024),
                },
            )

        except Exception as e:
            return HealthCheckResult(
                name="memory_usage",
                status=HealthStatus.UNKNOWN,
                check_type=HealthCheckType.RESOURCE,
                duration_ms=0,
                message=f"Failed to check memory usage: {e}",
                timestamp=time.time(),
                error=str(e),
            )

    def _check_cpu_usage(self) -> HealthCheckResult:
        """Check CPU usage health."""
        try:
            # Get CPU usage over 1 second window
            cpu_percent = self._process.cpu_percent(interval=1.0)

            # Thresholds
            warning_percent = 70.0
            critical_percent = 90.0

            if cpu_percent > critical_percent:
                status = HealthStatus.UNHEALTHY
                message = f"Critical CPU usage: {cpu_percent:.1f}%"
            elif cpu_percent > warning_percent:
                status = HealthStatus.DEGRADED
                message = f"High CPU usage: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU usage normal: {cpu_percent:.1f}%"

            return HealthCheckResult(
                name="cpu_usage",
                status=status,
                check_type=HealthCheckType.RESOURCE,
                duration_ms=0,
                message=message,
                timestamp=time.time(),
                metadata={"cpu_percent": cpu_percent},
            )

        except Exception as e:
            return HealthCheckResult(
                name="cpu_usage",
                status=HealthStatus.UNKNOWN,
                check_type=HealthCheckType.RESOURCE,
                duration_ms=0,
                message=f"Failed to check CPU usage: {e}",
                timestamp=time.time(),
                error=str(e),
            )

    def _check_disk_space(self) -> HealthCheckResult:
        """Check disk space health."""
        try:
            # Check current working directory disk space
            disk_usage = psutil.disk_usage("/")
            free_percent = (disk_usage.free / disk_usage.total) * 100

            # Thresholds
            warning_percent = 20.0  # Warn if less than 20% free
            critical_percent = 10.0  # Critical if less than 10% free

            if free_percent < critical_percent:
                status = HealthStatus.UNHEALTHY
                message = f"Critical disk space: {free_percent:.1f}% free"
            elif free_percent < warning_percent:
                status = HealthStatus.DEGRADED
                message = f"Low disk space: {free_percent:.1f}% free"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space adequate: {free_percent:.1f}% free"

            return HealthCheckResult(
                name="disk_space",
                status=status,
                check_type=HealthCheckType.RESOURCE,
                duration_ms=0,
                message=message,
                timestamp=time.time(),
                metadata={
                    "free_percent": free_percent,
                    "free_gb": disk_usage.free / (1024**3),
                    "total_gb": disk_usage.total / (1024**3),
                },
            )

        except Exception as e:
            return HealthCheckResult(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                check_type=HealthCheckType.RESOURCE,
                duration_ms=0,
                message=f"Failed to check disk space: {e}",
                timestamp=time.time(),
                error=str(e),
            )

    async def _check_network_connectivity(self) -> HealthCheckResult:
        """Check basic network connectivity."""
        try:
            # Test DNS resolution and connectivity to a reliable service
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(
                    "https://1.1.1.1/", timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        status = HealthStatus.HEALTHY
                        message = "Network connectivity confirmed"
                    else:
                        status = HealthStatus.DEGRADED
                        message = f"Network connectivity issues: HTTP {response.status}"

        except TimeoutError:
            status = HealthStatus.UNHEALTHY
            message = "Network connectivity timeout"
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            message = f"Network connectivity failed: {e!s}"

        return HealthCheckResult(
            name="network_connectivity",
            status=status,
            check_type=HealthCheckType.DEPENDENCY,
            duration_ms=0,
            message=message,
            timestamp=time.time(),
        )

    def _check_application_liveness(self) -> HealthCheckResult:
        """Check application liveness."""
        try:
            # Basic liveness - check if we can allocate memory and threads are responsive
            uptime = time.time() - self._start_time

            # Check thread count
            thread_count = self._process.num_threads()

            if thread_count > 100:  # Excessive thread count
                status = HealthStatus.DEGRADED
                message = f"High thread count: {thread_count}"
            else:
                status = HealthStatus.HEALTHY
                message = f"Application responsive (uptime: {uptime:.0f}s, threads: {thread_count})"

            return HealthCheckResult(
                name="application_liveness",
                status=status,
                check_type=HealthCheckType.LIVENESS,
                duration_ms=0,
                message=message,
                timestamp=time.time(),
                metadata={"uptime_seconds": uptime, "thread_count": thread_count},
            )

        except Exception as e:
            return HealthCheckResult(
                name="application_liveness",
                status=HealthStatus.UNHEALTHY,
                check_type=HealthCheckType.LIVENESS,
                duration_ms=0,
                message=f"Liveness check failed: {e}",
                timestamp=time.time(),
                error=str(e),
            )

    async def _check_database_connectivity(self) -> HealthCheckResult:
        """Check database connectivity using real connection test."""
        start = time.time()
        try:
            from kagami.core.database.connection import check_connection

            # Run sync check in executor to avoid blocking
            loop = asyncio.get_event_loop()
            is_connected = await loop.run_in_executor(None, check_connection)

            duration_ms = (time.time() - start) * 1000

            if is_connected:
                return HealthCheckResult(
                    name="database_connectivity",
                    status=HealthStatus.HEALTHY,
                    check_type=HealthCheckType.DEPENDENCY,
                    duration_ms=duration_ms,
                    message="Database connection successful",
                    timestamp=time.time(),
                )
            else:
                return HealthCheckResult(
                    name="database_connectivity",
                    status=HealthStatus.UNHEALTHY,
                    check_type=HealthCheckType.DEPENDENCY,
                    duration_ms=duration_ms,
                    message="Database connection failed",
                    timestamp=time.time(),
                )
        except ImportError:
            return HealthCheckResult(
                name="database_connectivity",
                status=HealthStatus.UNKNOWN,
                check_type=HealthCheckType.DEPENDENCY,
                duration_ms=(time.time() - start) * 1000,
                message="Database module not available",
                timestamp=time.time(),
            )
        except Exception as e:
            return HealthCheckResult(
                name="database_connectivity",
                status=HealthStatus.UNHEALTHY,
                check_type=HealthCheckType.DEPENDENCY,
                duration_ms=(time.time() - start) * 1000,
                message=f"Database check error: {e}",
                timestamp=time.time(),
                error=str(e),
            )

    async def _check_redis_connectivity(self) -> HealthCheckResult:
        """Check Redis connectivity using real ping test."""
        start = time.time()
        try:
            from kagami.core.caching.redis.factory import RedisClientFactory

            # Get async Redis client and ping
            redis_client = RedisClientFactory.get_client("default", async_mode=True)
            pong = await redis_client.ping()

            duration_ms = (time.time() - start) * 1000

            if pong:
                return HealthCheckResult(
                    name="redis_connectivity",
                    status=HealthStatus.HEALTHY,
                    check_type=HealthCheckType.DEPENDENCY,
                    duration_ms=duration_ms,
                    message="Redis connection successful (PONG received)",
                    timestamp=time.time(),
                )
            else:
                return HealthCheckResult(
                    name="redis_connectivity",
                    status=HealthStatus.UNHEALTHY,
                    check_type=HealthCheckType.DEPENDENCY,
                    duration_ms=duration_ms,
                    message="Redis ping failed",
                    timestamp=time.time(),
                )
        except ImportError:
            return HealthCheckResult(
                name="redis_connectivity",
                status=HealthStatus.UNKNOWN,
                check_type=HealthCheckType.DEPENDENCY,
                duration_ms=(time.time() - start) * 1000,
                message="Redis module not available",
                timestamp=time.time(),
            )
        except Exception as e:
            return HealthCheckResult(
                name="redis_connectivity",
                status=HealthStatus.UNHEALTHY,
                check_type=HealthCheckType.DEPENDENCY,
                duration_ms=(time.time() - start) * 1000,
                message=f"Redis check error: {e}",
                timestamp=time.time(),
                error=str(e),
            )

    # Health status query methods

    def get_overall_health(self) -> HealthStatus:
        """Get overall system health status."""
        if not self._results:
            return HealthStatus.UNKNOWN

        critical_checks = [
            result for name, result in self._results.items() if self._checks[name].critical
        ]

        # If any critical check is unhealthy, system is unhealthy
        if any(check.status == HealthStatus.UNHEALTHY for check in critical_checks):
            return HealthStatus.UNHEALTHY

        # If any check is degraded, system is degraded
        if any(check.status == HealthStatus.DEGRADED for check in self._results.values()):
            return HealthStatus.DEGRADED

        # If all checks are healthy
        if all(check.status == HealthStatus.HEALTHY for check in self._results.values()):
            return HealthStatus.HEALTHY

        return HealthStatus.UNKNOWN

    def get_health_score(self) -> float:
        """Calculate overall health score (0-100)."""
        if not self._results:
            return 0.0

        total_weight = 0.0
        weighted_score = 0.0

        for name, result in self._results.items():
            weight = self._health_weights.get(name, 1.0)
            total_weight += weight

            # Score based on status
            if result.status == HealthStatus.HEALTHY:
                score = 100.0
            elif result.status == HealthStatus.DEGRADED:
                score = 60.0
            elif result.status == HealthStatus.UNHEALTHY:
                score = 0.0
            else:  # UNKNOWN
                score = 30.0

            weighted_score += score * weight

        return weighted_score / max(total_weight, 1.0)

    def get_health_summary(self) -> dict[str, Any]:
        """Get comprehensive health summary."""
        overall_health = self.get_overall_health()
        health_score = self.get_health_score()

        # Count checks by status
        status_counts = defaultdict(int)
        for result in self._results.values():
            status_counts[result.status.value] += 1

        # Get failing checks
        failing_checks = [
            {
                "name": result.name,
                "status": result.status.value,
                "message": result.message,
                "timestamp": result.timestamp,
            }
            for result in self._results.values()
            if result.status in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED)
        ]

        return {
            "overall_status": overall_health.value,
            "health_score": health_score,
            "total_checks": len(self._results),
            "status_counts": dict(status_counts),
            "failing_checks": failing_checks,
            "last_updated": max(
                (result.timestamp for result in self._results.values()), default=time.time()
            ),
            "uptime_seconds": time.time() - self._start_time,
        }

    def get_check_details(self, check_name: str) -> dict[str, Any] | None:
        """Get detailed information about a specific check."""
        if check_name not in self._results:
            return None

        result = self._results[check_name]
        check_def = self._checks.get(check_name)
        history = self._result_history.get(check_name, [])

        # Calculate success rate from recent history
        recent_history = history[-20:] if history else []
        success_rate = (
            sum(1 for r in recent_history if r.status == HealthStatus.HEALTHY)
            / max(len(recent_history), 1)
            * 100
        )

        return {
            "name": check_name,
            "current_status": result.status.value,
            "current_message": result.message,
            "last_check": result.timestamp,
            "duration_ms": result.duration_ms,
            "success_rate_percent": success_rate,
            "check_type": check_def.check_type.value if check_def else "unknown",
            "critical": check_def.critical if check_def else False,
            "enabled": check_def.enabled if check_def else False,
            "interval_seconds": check_def.interval_seconds if check_def else 0,
            "metadata": result.metadata,
            "error": result.error,
            "history_count": len(history),
        }

    def is_ready(self) -> bool:
        """Check if service is ready to receive traffic (readiness probe)."""
        readiness_checks = [
            result
            for name, result in self._results.items()
            if self._checks[name].check_type == HealthCheckType.READINESS
        ]

        # All readiness checks must be healthy
        return all(check.status == HealthStatus.HEALTHY for check in readiness_checks)

    def is_alive(self) -> bool:
        """Check if service is alive (liveness probe)."""
        liveness_checks = [
            result
            for name, result in self._results.items()
            if self._checks[name].check_type == HealthCheckType.LIVENESS
        ]

        # All liveness checks must not be unhealthy
        return all(check.status != HealthStatus.UNHEALTHY for check in liveness_checks)

    def enable_check(self, check_name: str) -> None:
        """Enable a specific health check."""
        if check_name in self._checks:
            self._checks[check_name].enabled = True
            logger.info(f"🏥 Health check enabled: {check_name}")

    def disable_check(self, check_name: str) -> None:
        """Disable a specific health check."""
        if check_name in self._checks:
            self._checks[check_name].enabled = False

            # Cancel running task if exists
            if check_name in self._check_tasks:
                self._check_tasks[check_name].cancel()
                del self._check_tasks[check_name]

            logger.info(f"🏥 Health check disabled: {check_name}")


# Global health check manager instance
_global_health_manager: HealthCheckManager | None = None


def get_health_manager() -> HealthCheckManager:
    """Get the global health check manager instance."""
    global _global_health_manager
    if _global_health_manager is None:
        _global_health_manager = HealthCheckManager()

    return _global_health_manager
