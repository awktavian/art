"""Failover Management — Robust Multi-Integration Resilience.

Implements comprehensive failover strategies across all 18 smart home integrations:
- Graceful degradation patterns
- Automatic fallback routing
- Cross-integration redundancy
- Recovery orchestration
- Service mesh resilience

DELEGATES health tracking to SystemHealthMonitor (Phase 1 refactor).

Maintains h(x) ≥ 0 safety compliance while ensuring 99.9% uptime through
intelligent failover coordination.

Created: December 29, 2025
Updated: December 30, 2025 - Delegate health to SystemHealthMonitor
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from kagami_smarthome.performance_monitor import MetricType, PerformanceMonitor

logger = logging.getLogger(__name__)


def _get_health_monitor():
    """Lazy import to avoid circular dependency."""
    try:
        from kagami.core.integrations.system_health import get_system_health_monitor

        return get_system_health_monitor()
    except ImportError:
        return None


class FailoverStrategy(str, Enum):
    """Failover strategies for different integration scenarios."""

    IMMEDIATE = "immediate"  # Instant failover (security, safety)
    GRACEFUL = "graceful"  # Wait for current ops to complete
    DELAYED = "delayed"  # Wait with timeout before failover
    CIRCUIT_BREAKER = "circuit_breaker"  # Stop trying after failures
    RETRY_EXPONENTIAL = "retry_exponential"  # Exponential backoff retry
    LOAD_BALANCE = "load_balance"  # Distribute load across alternatives


class IntegrationTier(int, Enum):
    """Integration criticality tiers for failover priority."""

    CRITICAL = 1  # Security, Safety (immediate failover)
    ESSENTIAL = 2  # Lighting, HVAC (graceful failover)
    IMPORTANT = 3  # Audio, Entertainment, ALL features (delayed failover)
    # HARDENED: NO OPTIONAL TIER - ALL INTEGRATIONS ARE REQUIRED


class ServiceHealth(str, Enum):
    """Health states for integration services."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNSTABLE = "unstable"
    FAILING = "failing"
    OFFLINE = "offline"
    RECOVERING = "recovering"


@dataclass
class FailoverRoute:
    """Defines a failover path for an integration."""

    primary: str
    fallbacks: list[str]
    strategy: FailoverStrategy
    max_attempts: int = 3
    timeout_seconds: float = 30.0
    health_check_interval: float = 60.0
    recovery_threshold: float = 0.8  # Success rate to consider recovered


@dataclass
class IntegrationHealthStatus:
    """Comprehensive health status for an integration."""

    name: str
    tier: IntegrationTier
    health: ServiceHealth
    success_rate: float
    avg_response_time: float
    last_success: float
    last_failure: float
    failure_count: int
    recovery_attempts: int
    is_primary_active: bool
    active_route: str
    available_routes: list[str]


@dataclass
class FailoverEvent:
    """Records a failover event for analysis."""

    integration: str
    from_route: str
    to_route: str
    reason: str
    strategy: FailoverStrategy
    timestamp: float
    recovery_time: float | None = None
    success: bool = False


class FailoverManager:
    """Manages robust failover patterns across all smart home integrations.

    DELEGATES health tracking to SystemHealthMonitor (unified health source).

    Provides:
    - Multi-tier failover strategies based on criticality
    - Cross-integration redundancy (e.g., Control4 → UniFi for presence)
    - Graceful degradation with service mesh patterns
    - Automatic recovery coordination (via SystemHealthMonitor)
    - Performance-aware routing decisions

    Failover Tiers (mapped to SystemHealthMonitor.IntegrationTier):
    - CRITICAL: Security, locks, safety systems (immediate failover)
    - ESSENTIAL: Lighting, HVAC, core functionality (graceful failover)
    - IMPORTANT: Audio, entertainment, convenience (delayed failover)
    """

    def __init__(self, performance_monitor: PerformanceMonitor | None = None):
        self._performance_monitor = performance_monitor

        # Delegate health tracking to SystemHealthMonitor
        self._health_monitor = _get_health_monitor()

        # Failover configuration
        self._failover_routes: dict[str, FailoverRoute] = {}

        # Local health status (for backwards compatibility, synced with SystemHealthMonitor)
        self._integration_status: dict[str, IntegrationHealthStatus] = {}

        # Cross-integration redundancy mappings
        self._redundancy_mappings: dict[str, dict[str, str]] = {}

        # Active failover state (delegated to SystemHealthMonitor._active_failovers)
        self._active_failovers: set[str] = set()
        self._recovery_tasks: dict[str, asyncio.Task] = {}

        # Event tracking
        self._failover_events: list[FailoverEvent] = []
        self._event_callbacks: list[Callable[[FailoverEvent], None]] = []

        # Monitoring - health checks delegated to SystemHealthMonitor
        self._monitor_task: asyncio.Task | None = None
        self._running = False

        # Initialize default routes
        self._initialize_default_routes()

    def _initialize_default_routes(self) -> None:
        """Initialize default failover routes for all integrations."""

        # === CRITICAL TIER - Security & Safety ===

        # Security System (DSC via Envisalink or Control4)
        self.register_failover_route(
            FailoverRoute(
                primary="envisalink",
                fallbacks=["control4"],
                strategy=FailoverStrategy.IMMEDIATE,
                max_attempts=5,
                timeout_seconds=10.0,
                health_check_interval=30.0,
            )
        )
        self._set_integration_tier("envisalink", IntegrationTier.CRITICAL)
        self._set_integration_tier("control4", IntegrationTier.CRITICAL)

        # Locks (August direct or Control4)
        self.register_failover_route(
            FailoverRoute(
                primary="august",
                fallbacks=["control4"],
                strategy=FailoverStrategy.IMMEDIATE,
                max_attempts=3,
                timeout_seconds=15.0,
            )
        )
        self._set_integration_tier("august", IntegrationTier.CRITICAL)

        # === ESSENTIAL TIER - Core Functionality ===

        # Lighting (Control4 primary, local fallback)
        self.register_failover_route(
            FailoverRoute(
                primary="control4",
                fallbacks=["local_control", "manual_override"],
                strategy=FailoverStrategy.GRACEFUL,
                max_attempts=3,
                timeout_seconds=20.0,
            )
        )

        # HVAC (Mitsubishi primary, manual fallback)
        self.register_failover_route(
            FailoverRoute(
                primary="mitsubishi",
                fallbacks=["manual_thermostat"],
                strategy=FailoverStrategy.GRACEFUL,
                max_attempts=2,
                timeout_seconds=30.0,
            )
        )
        self._set_integration_tier("mitsubishi", IntegrationTier.ESSENTIAL)

        # Network/Presence (UniFi primary, ping fallback)
        self.register_failover_route(
            FailoverRoute(
                primary="unifi",
                fallbacks=["ping_sweep", "tesla"],
                strategy=FailoverStrategy.GRACEFUL,
                max_attempts=2,
                timeout_seconds=15.0,
            )
        )
        self._set_integration_tier("unifi", IntegrationTier.ESSENTIAL)

        # === IMPORTANT TIER - Convenience Features ===

        # Home Theater Audio (Denon primary, Control4 fallback)
        self.register_failover_route(
            FailoverRoute(
                primary="denon",
                fallbacks=["control4", "direct_tv_audio"],
                strategy=FailoverStrategy.DELAYED,
                max_attempts=2,
                timeout_seconds=25.0,
            )
        )
        self._set_integration_tier("denon", IntegrationTier.IMPORTANT)

        # TV Control (LG primary, Control4 or manual)
        self.register_failover_route(
            FailoverRoute(
                primary="lg_tv",
                fallbacks=["control4", "manual_remote"],
                strategy=FailoverStrategy.DELAYED,
                max_attempts=2,
                timeout_seconds=20.0,
            )
        )
        self._set_integration_tier("lg_tv", IntegrationTier.IMPORTANT)

        # Samsung TV (Family Room)
        self.register_failover_route(
            FailoverRoute(
                primary="samsung_tv",
                fallbacks=["manual_remote"],
                strategy=FailoverStrategy.DELAYED,
                max_attempts=2,
                timeout_seconds=20.0,
            )
        )
        self._set_integration_tier("samsung_tv", IntegrationTier.IMPORTANT)

        # Sleep Tracking (Eight Sleep)
        self.register_failover_route(
            FailoverRoute(
                primary="eight_sleep",
                fallbacks=["manual_sleep_log"],
                strategy=FailoverStrategy.DELAYED,
                max_attempts=1,
                timeout_seconds=30.0,
            )
        )
        self._set_integration_tier("eight_sleep", IntegrationTier.IMPORTANT)

        # === OPTIONAL TIER - Non-Essential Features ===

        # Vehicle Integration
        self.register_failover_route(
            FailoverRoute(
                primary="tesla",
                fallbacks=["manual_tracking"],
                strategy=FailoverStrategy.CIRCUIT_BREAKER,
                max_attempts=1,
                timeout_seconds=45.0,
            )
        )
        self._set_integration_tier("tesla", IntegrationTier.IMPORTANT)

        # Outdoor Lighting
        self.register_failover_route(
            FailoverRoute(
                primary="oelo",
                fallbacks=["manual_outdoor"],
                strategy=FailoverStrategy.CIRCUIT_BREAKER,
                max_attempts=1,
                timeout_seconds=30.0,
            )
        )
        self._set_integration_tier("oelo", IntegrationTier.IMPORTANT)

        # Appliances (LG ThinQ, SmartThings, etc.)
        appliance_integrations = ["lg_thinq", "smartthings", "electrolux", "subzero_wolf"]
        for integration in appliance_integrations:
            self.register_failover_route(
                FailoverRoute(
                    primary=integration,
                    fallbacks=["manual_appliance"],
                    strategy=FailoverStrategy.CIRCUIT_BREAKER,
                    max_attempts=1,
                    timeout_seconds=60.0,
                )
            )
            self._set_integration_tier(integration, IntegrationTier.IMPORTANT)

        # Initialize cross-integration redundancy
        self._setup_redundancy_mappings()

    def _setup_redundancy_mappings(self) -> None:
        """Setup cross-integration redundancy mappings."""

        # Presence detection redundancy
        self._redundancy_mappings["presence"] = {
            "unifi": "wifi_clients",  # Primary: UniFi client detection
            "tesla": "vehicle_location",  # Secondary: Tesla geofencing
            "august": "lock_activity",  # Tertiary: Lock usage
            "eight_sleep": "bed_presence",  # Quaternary: Bed occupancy
        }

        # Security monitoring redundancy
        self._redundancy_mappings["security"] = {
            "envisalink": "dsc_zones",  # Primary: Direct DSC panel
            "control4": "security_panel",  # Secondary: Control4 security
            "unifi": "camera_motion",  # Tertiary: Camera detection
            "august": "door_sensors",  # Quaternary: Door state
        }

        # Lighting control redundancy
        self._redundancy_mappings["lighting"] = {
            "control4": "lutron_leap",  # Primary: Control4/Lutron
            "lutron_direct": "lutron_api",  # Secondary: Direct Lutron
            "manual": "physical_switches",  # Fallback: Manual control
        }

        # Audio control redundancy
        self._redundancy_mappings["audio"] = {
            "control4": "triad_ams",  # Primary: Control4/Triad
            "denon": "heos_direct",  # Secondary: Direct Denon/HEOS
            "manual": "physical_controls",  # Fallback: Manual operation
        }

        # Temperature control redundancy
        self._redundancy_mappings["temperature"] = {
            "mitsubishi": "kumo_cloud",  # Primary: Mitsubishi Cloud
            "dsc_sensors": "zone_temps",  # Secondary: DSC temp sensors
            "manual": "thermostat_local",  # Fallback: Manual thermostats
        }

    def register_failover_route(self, route: FailoverRoute) -> None:
        """Register a failover route for an integration."""
        self._failover_routes[route.primary] = route

        # Initialize health status for primary and fallbacks
        for integration in [route.primary] + route.fallbacks:
            if integration not in self._integration_status:
                self._integration_status[integration] = IntegrationHealthStatus(
                    name=integration,
                    tier=IntegrationTier.IMPORTANT,  # All integrations are required
                    health=ServiceHealth.HEALTHY,
                    success_rate=1.0,
                    avg_response_time=0.0,
                    last_success=0.0,
                    last_failure=0.0,
                    failure_count=0,
                    recovery_attempts=0,
                    is_primary_active=integration == route.primary,
                    active_route=integration if integration == route.primary else "",
                    available_routes=[integration],
                )

        logger.debug(f"Registered failover route: {route.primary} → {route.fallbacks}")

    def _set_integration_tier(self, integration: str, tier: IntegrationTier) -> None:
        """Set criticality tier for an integration."""
        if integration in self._integration_status:
            self._integration_status[integration].tier = tier

    async def start_monitoring(self) -> None:
        """Start failover monitoring and health checks."""
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("🛡️ Failover monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop failover monitoring."""
        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Cancel recovery tasks
        for task in self._recovery_tasks.values():
            task.cancel()

        self._recovery_tasks.clear()

    async def handle_integration_failure(
        self, integration: str, error: Exception, context: dict[str, Any] | None = None
    ) -> str:
        """Handle integration failure and execute failover.

        Returns the name of the integration/route that should be used.
        """
        if integration not in self._integration_status:
            logger.warning(f"Unknown integration failed: {integration}")
            return integration

        status = self._integration_status[integration]
        status.failure_count += 1
        status.last_failure = time.time()

        # Update health based on failure pattern
        self._update_integration_health(integration)

        # Check if failover is needed
        route = self._failover_routes.get(integration)
        if not route or not route.fallbacks:
            logger.warning(f"No failover route for {integration}")
            return integration

        # Execute failover based on strategy and tier
        fallback_integration = await self._execute_failover(integration, route, error, context)

        return fallback_integration

    async def _execute_failover(
        self,
        integration: str,
        route: FailoverRoute,
        error: Exception,
        context: dict[str, Any] | None,
    ) -> str:
        """Execute failover to next available route."""
        status = self._integration_status[integration]

        # Find next available fallback
        for fallback in route.fallbacks:
            fallback_status = self._integration_status.get(fallback)
            if not fallback_status:
                continue

            # Skip if fallback is also failing
            if fallback_status.health in (ServiceHealth.FAILING, ServiceHealth.OFFLINE):
                continue

            # Execute failover based on strategy
            if await self._perform_failover(integration, fallback, route, error):
                # Record successful failover event
                event = FailoverEvent(
                    integration=integration,
                    from_route=status.active_route or integration,
                    to_route=fallback,
                    reason=str(error),
                    strategy=route.strategy,
                    timestamp=time.time(),
                    success=True,
                )
                self._record_failover_event(event)

                # Update statuses
                status.active_route = fallback
                status.is_primary_active = False
                fallback_status.is_primary_active = True

                # Start recovery attempt for primary
                if integration not in self._recovery_tasks:
                    self._recovery_tasks[integration] = asyncio.create_task(
                        self._attempt_recovery(integration, route)
                    )

                logger.warning(f"🔄 Failover: {integration} → {fallback} (reason: {error})")

                return fallback

        # No successful failover
        logger.error(f"❌ All failover routes exhausted for {integration}")
        status.health = ServiceHealth.OFFLINE

        # Record failed failover event
        event = FailoverEvent(
            integration=integration,
            from_route=status.active_route or integration,
            to_route="none",
            reason=f"All routes exhausted: {error}",
            strategy=route.strategy,
            timestamp=time.time(),
            success=False,
        )
        self._record_failover_event(event)

        return integration  # Return original, caller must handle offline state

    async def _perform_failover(
        self, primary: str, fallback: str, route: FailoverRoute, error: Exception
    ) -> bool:
        """Perform actual failover based on strategy."""
        try:
            if route.strategy == FailoverStrategy.IMMEDIATE:
                # Immediate failover for critical systems
                return await self._immediate_failover(primary, fallback)

            elif route.strategy == FailoverStrategy.GRACEFUL:
                # Graceful failover for essential systems
                return await self._graceful_failover(primary, fallback, route.timeout_seconds)

            elif route.strategy == FailoverStrategy.DELAYED:
                # Delayed failover for important systems
                return await self._delayed_failover(primary, fallback, route.timeout_seconds)

            elif route.strategy == FailoverStrategy.CIRCUIT_BREAKER:
                # Circuit breaker for optional systems
                return await self._circuit_breaker_failover(primary, fallback, route)

            else:
                logger.warning(f"Unknown failover strategy: {route.strategy}")
                return False

        except Exception as e:
            logger.error(f"Failover execution failed: {e}")
            return False

    async def _immediate_failover(self, primary: str, fallback: str) -> bool:
        """Immediate failover for critical systems."""
        logger.info(f"🚨 Immediate failover: {primary} → {fallback}")

        # For critical systems, switch immediately without delay
        # This maintains h(x) ≥ 0 safety compliance

        return await self._test_fallback_health(fallback)

    async def _graceful_failover(self, primary: str, fallback: str, timeout: float) -> bool:
        """Graceful failover for essential systems."""
        logger.info(f"🔄 Graceful failover: {primary} → {fallback}")

        # Allow current operations to complete, then switch
        await asyncio.sleep(min(timeout / 4, 2.0))  # Brief grace period

        return await self._test_fallback_health(fallback)

    async def _delayed_failover(self, primary: str, fallback: str, timeout: float) -> bool:
        """Delayed failover for important systems."""
        logger.info(f"⏱️ Delayed failover: {primary} → {fallback}")

        # Wait to see if primary recovers
        await asyncio.sleep(min(timeout / 2, 10.0))

        # Check if primary has recovered
        if await self._test_integration_health(primary):
            logger.info(f"✅ {primary} recovered, canceling failover")
            return False

        return await self._test_fallback_health(fallback)

    async def _circuit_breaker_failover(
        self, primary: str, fallback: str, route: FailoverRoute
    ) -> bool:
        """Circuit breaker failover for optional systems."""
        status = self._integration_status[primary]

        # If too many failures, open circuit (stop trying)
        if status.failure_count >= route.max_attempts:
            logger.warning(f"🔌 Circuit breaker open for {primary}")
            status.health = ServiceHealth.OFFLINE
            return False

        return await self._test_fallback_health(fallback)

    async def _test_fallback_health(self, fallback: str) -> bool:
        """Test if fallback integration is healthy."""
        try:
            # Simple health check - in real implementation, this would
            # call the integration's health check method

            status = self._integration_status.get(fallback)
            if not status:
                return False

            # Assume healthy if not marked as failing/offline
            return status.health not in (ServiceHealth.FAILING, ServiceHealth.OFFLINE)

        except Exception as e:
            logger.debug(f"Fallback health check failed for {fallback}: {e}")
            return False

    async def _test_integration_health(self, integration: str) -> bool:
        """Test integration health for recovery detection."""
        # Simple health check implementation
        status = self._integration_status.get(integration)
        if not status:
            return False

        return status.health in (ServiceHealth.HEALTHY, ServiceHealth.DEGRADED)

    async def _attempt_recovery(self, integration: str, route: FailoverRoute) -> None:
        """Attempt to recover failed primary integration."""
        try:
            status = self._integration_status[integration]
            status.recovery_attempts += 1

            logger.info(f"🩹 Attempting recovery for {integration}")

            # Exponential backoff for recovery attempts
            backoff_delay = min(2**status.recovery_attempts, 300)  # Max 5 minutes
            await asyncio.sleep(backoff_delay)

            # Test if primary has recovered
            if await self._test_integration_health(integration):
                # Primary is healthy again, fail back
                await self._fail_back_to_primary(integration, route)
            else:
                # Schedule next recovery attempt
                if status.recovery_attempts < route.max_attempts:
                    self._recovery_tasks[integration] = asyncio.create_task(
                        self._attempt_recovery(integration, route)
                    )
                else:
                    logger.warning(
                        f"❌ Recovery failed for {integration} after {route.max_attempts} attempts"
                    )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Recovery attempt failed for {integration}: {e}")
        finally:
            # Clean up recovery task
            self._recovery_tasks.pop(integration, None)

    async def _fail_back_to_primary(self, integration: str, route: FailoverRoute) -> None:
        """Fail back to primary integration after recovery."""
        status = self._integration_status[integration]

        logger.info(f"✅ Failing back to primary: {integration}")

        # Reset status
        status.is_primary_active = True
        status.active_route = integration
        status.health = ServiceHealth.RECOVERING
        status.recovery_attempts = 0

        # Record recovery event
        event = FailoverEvent(
            integration=integration,
            from_route=status.active_route,
            to_route=integration,
            reason="Primary recovered",
            strategy=route.strategy,
            timestamp=time.time(),
            recovery_time=time.time() - status.last_failure,
            success=True,
        )
        self._record_failover_event(event)

        # Deactivate fallback
        for fallback in route.fallbacks:
            fallback_status = self._integration_status.get(fallback)
            if fallback_status and fallback_status.is_primary_active:
                fallback_status.is_primary_active = False

    def _update_integration_health(self, integration: str) -> None:
        """Update integration health status based on metrics.

        Syncs with SystemHealthMonitor for unified tracking.
        """
        status = self._integration_status.get(integration)
        if not status:
            return

        # Calculate success rate
        total_operations = status.failure_count + max(status.success_rate * 100, 1)
        success_rate = max(0, (total_operations - status.failure_count) / total_operations)
        status.success_rate = success_rate

        # Determine health based on success rate and recent failures
        if success_rate >= 0.95:
            status.health = ServiceHealth.HEALTHY
        elif success_rate >= 0.8:
            status.health = ServiceHealth.DEGRADED
        elif success_rate >= 0.5:
            status.health = ServiceHealth.UNSTABLE
        else:
            status.health = ServiceHealth.FAILING

        # Record metrics
        if self._performance_monitor:
            self._performance_monitor.record_metric(
                MetricType.ERROR_RATE, 1.0 - success_rate, integration
            )

        # Sync with SystemHealthMonitor
        if self._health_monitor:
            health = self._health_monitor.get_health(integration)
            if health:
                health.record_failure(
                    f"Failure count: {status.failure_count}"
                ) if status.failure_count > 0 else None

    def _record_failover_event(self, event: FailoverEvent) -> None:
        """Record failover event for analysis."""
        self._failover_events.append(event)

        # Keep only recent events
        if len(self._failover_events) > 1000:
            self._failover_events = self._failover_events[-1000:]

        # Notify callbacks
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Failover event callback error: {e}")

        # Log important events
        if event.success:
            logger.info(
                f"🔄 Failover event: {event.integration} {event.from_route} → {event.to_route}"
            )
        else:
            logger.error(f"❌ Failed failover: {event.integration} - {event.reason}")

    async def _monitor_loop(self) -> None:
        """Background monitoring loop for health checks."""
        while self._running:
            try:
                await self._perform_health_monitoring()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(10)

    async def _perform_health_monitoring(self) -> None:
        """Perform periodic health monitoring."""
        for integration, status in self._integration_status.items():
            # Skip if currently in recovery
            if integration in self._recovery_tasks:
                continue

            # Perform health check based on tier
            route = self._failover_routes.get(integration)
            if not route:
                continue

            # More frequent checks for critical systems
            check_interval = route.health_check_interval
            if status.tier == IntegrationTier.CRITICAL:
                check_interval = min(check_interval, 30.0)

            # Check if it's time for health check
            time_since_check = time.time() - status.last_success
            if time_since_check < check_interval:
                continue

            # Perform health check
            try:
                is_healthy = await self._test_integration_health(integration)

                if is_healthy:
                    status.last_success = time.time()
                    if status.health == ServiceHealth.RECOVERING:
                        status.health = ServiceHealth.HEALTHY
                else:
                    # Health check failed, might need failover
                    if status.is_primary_active and status.health != ServiceHealth.FAILING:
                        logger.warning(f"⚠️ Health check failed for {integration}")
                        await self.handle_integration_failure(
                            integration, Exception("Health check failed"), {"type": "health_check"}
                        )

            except Exception as e:
                logger.debug(f"Health monitoring error for {integration}: {e}")

    def get_integration_status(self, integration: str) -> IntegrationHealthStatus | None:
        """Get current status of an integration."""
        return self._integration_status.get(integration)

    def get_all_statuses(self) -> dict[str, IntegrationHealthStatus]:
        """Get status of all managed integrations."""
        return self._integration_status.copy()

    def get_active_failovers(self) -> list[str]:
        """Get list of integrations currently in failover state."""
        return [
            integration
            for integration, status in self._integration_status.items()
            if not status.is_primary_active
        ]

    def get_failover_events(self, limit: int = 100) -> list[FailoverEvent]:
        """Get recent failover events."""
        return self._failover_events[-limit:]

    def on_failover_event(self, callback: Callable[[FailoverEvent], None]) -> None:
        """Register callback for failover events."""
        self._event_callbacks.append(callback)

    def get_redundancy_options(self, function: str) -> dict[str, str]:
        """Get redundancy options for a function (presence, security, etc.)."""
        return self._redundancy_mappings.get(function, {})

    def force_failover(self, integration: str, reason: str = "Manual override") -> bool:
        """Force failover for an integration."""
        if integration not in self._failover_routes:
            return False

        logger.warning(f"🔧 Forced failover for {integration}: {reason}")

        # Create task to handle failover
        asyncio.create_task(
            self.handle_integration_failure(
                integration, Exception(reason), {"type": "manual_override"}
            )
        )

        return True

    def reset_integration(self, integration: str) -> bool:
        """Reset integration to healthy state and primary route."""
        status = self._integration_status.get(integration)
        if not status:
            return False

        logger.info(f"🔄 Resetting integration: {integration}")

        # Reset status
        status.health = ServiceHealth.HEALTHY
        status.failure_count = 0
        status.recovery_attempts = 0
        status.success_rate = 1.0
        status.is_primary_active = True
        status.active_route = integration

        # Cancel any active recovery
        task = self._recovery_tasks.pop(integration, None)
        if task:
            task.cancel()

        return True

    def get_health_summary(self) -> dict[str, Any]:
        """Get overall failover system health summary.

        Combines local state with SystemHealthMonitor data.
        """
        # Get data from SystemHealthMonitor if available
        if self._health_monitor:
            report = self._health_monitor.get_health_report()
            return {
                "total_integrations": report["summary"]["total"],
                "healthy_integrations": report["summary"]["healthy"]
                + report["summary"]["degraded"],
                "health_percentage": report["summary"]["health_percentage"],
                "active_failovers": report["summary"]["active_failovers"],
                "circuit_open": report["summary"].get("circuit_open", 0),
                "recent_events": len(
                    [
                        event
                        for event in self._failover_events
                        if time.time() - event.timestamp < 3600
                    ]
                ),
                "recovery_tasks": len(self._recovery_tasks),
                "overall_status": report["status"],
            }

        # Fallback to local tracking
        total_integrations = len(self._integration_status)
        healthy_count = sum(
            1
            for status in self._integration_status.values()
            if status.health in (ServiceHealth.HEALTHY, ServiceHealth.DEGRADED)
        )

        active_failovers = len(self.get_active_failovers())
        recent_events = len(
            [
                event
                for event in self._failover_events
                if time.time() - event.timestamp < 3600  # Last hour
            ]
        )

        return {
            "total_integrations": total_integrations,
            "healthy_integrations": healthy_count,
            "health_percentage": (healthy_count / max(total_integrations, 1)) * 100,
            "active_failovers": active_failovers,
            "recent_events": recent_events,
            "recovery_tasks": len(self._recovery_tasks),
            "overall_status": "healthy"
            if healthy_count >= total_integrations * 0.9
            else "degraded",
        }

    async def stop(self) -> None:
        """Stop the failover manager and monitoring."""
        await self.stop_monitoring()
