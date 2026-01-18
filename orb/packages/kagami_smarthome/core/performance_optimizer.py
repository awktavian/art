"""Performance Optimizer - Enhanced performance monitoring and optimization.

Responsibilities:
- Integration pool management
- Failover coordination
- Adaptive polling optimization
- Performance monitoring and alerting
- Health monitoring and diagnostics
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class PerformanceOptimizer:
    """Manages performance optimization and monitoring systems."""

    def __init__(self, integration_coordinator):
        self.integrations = integration_coordinator

        # Performance components
        self._performance_monitor = None
        self._integration_pool = None
        self._failover_manager = None
        self._adaptive_polling = None

        # State
        self._optimization_enabled = True
        self._running = False

    async def initialize(self) -> None:
        """Initialize all performance optimization components."""
        try:
            # Import performance modules
            from kagami_smarthome.failover_manager import FailoverManager
            from kagami_smarthome.integration_pool import IntegrationPool
            from kagami_smarthome.performance_monitor import PerformanceMonitor
            from kagami_smarthome.polling_stub import AdaptivePollingManager

            # Initialize components
            self._performance_monitor = PerformanceMonitor()
            self._integration_pool = IntegrationPool(self._performance_monitor)
            self._failover_manager = FailoverManager(self._performance_monitor)
            self._adaptive_polling = AdaptivePollingManager(self._performance_monitor)

            # Configure components
            await self._configure_integration_pool()
            await self._configure_failover_management()
            await self._configure_adaptive_polling()

            logger.info("Performance optimization initialized")

        except Exception as e:
            logger.error(f"Failed to initialize performance optimization: {e}")

    async def start(self) -> None:
        """Start optimization services."""
        if self._running:
            return

        try:
            self._running = True

            # Start integration pool monitoring
            if self._integration_pool:
                await self._integration_pool.start_monitoring()

            # Register performance alerts
            if self._performance_monitor:
                self._performance_monitor.on_alert = self._on_performance_alert

            logger.info("Performance optimization services started")

        except Exception as e:
            logger.error(f"Failed to start optimization services: {e}")

    async def stop(self) -> None:
        """Stop optimization services."""
        self._running = False

        try:
            # Stop integration pool
            if self._integration_pool:
                await self._integration_pool.stop_monitoring()

            logger.info("Performance optimization services stopped")

        except Exception as e:
            logger.error(f"Failed to stop optimization services: {e}")

    async def _configure_integration_pool(self) -> None:
        """Configure the integration pool with priority levels."""
        if not self._integration_pool:
            return

        # Register integrations by priority
        priorities = {
            # CRITICAL - Security & Safety
            "control4": {"priority": "critical", "timeout": 5.0, "retry_count": 3},
            "unifi": {"priority": "critical", "timeout": 3.0, "retry_count": 3},
            "envisalink": {"priority": "critical", "timeout": 1.0, "retry_count": 1},
            # HIGH - Core Infrastructure
            "denon": {"priority": "high", "timeout": 3.0, "retry_count": 2},
            "mitsubishi": {"priority": "high", "timeout": 5.0, "retry_count": 2},
            "august": {"priority": "high", "timeout": 5.0, "retry_count": 2},
            "eight_sleep": {"priority": "high", "timeout": 15.0, "retry_count": 2},
            # MEDIUM - Entertainment & Comfort
            "lg_tv": {"priority": "medium", "timeout": 3.0, "retry_count": 1},
            "samsung_tv": {"priority": "medium", "timeout": 3.0, "retry_count": 1},
            "tesla": {"priority": "medium", "timeout": 5.0, "retry_count": 1},
            # LOW - Optional Features
            "oelo": {"priority": "low", "timeout": 2.0, "retry_count": 1},
            "apple_findmy": {"priority": "low", "timeout": 10.0, "retry_count": 1},
            "apple_health": {"priority": "low", "timeout": 10.0, "retry_count": 1},
            "spotify": {"priority": "low", "timeout": 5.0, "retry_count": 1},
        }

        for integration_name, config in priorities.items():
            integration = getattr(self.integrations, f"_{integration_name}", None)
            if config and integration:
                await self._integration_pool.register_integration(
                    integration_name, integration, **config
                )

        # Register state change callback
        self._integration_pool.on_state_change = self._on_integration_state_change

    async def _configure_failover_management(self) -> None:
        """Configure failover management."""
        if not self._failover_manager:
            return

        # Start failover monitoring
        await self._failover_manager.start_monitoring()

        # Register failover alert callback
        self._failover_manager.on_failover = self._on_failover_event

    async def _configure_adaptive_polling(self) -> None:
        """Configure adaptive polling optimization."""
        if not self._adaptive_polling:
            return

        # Set initial presence state
        self._adaptive_polling.set_presence(True)  # Assume home initially

        # Start adaptive polling
        await self._adaptive_polling.start()

        # Register activity callbacks
        self._adaptive_polling.on_optimization = self._on_polling_optimization

    def _on_integration_state_change(self, integration: str, state: Any) -> None:
        """Handle integration state changes."""
        try:
            if state == "failed":
                # Integration failed, trigger failover
                asyncio.create_task(self._failover_manager.activate_failover(integration))

            elif state == "recovered":
                # Integration recovered, record activity
                if self._adaptive_polling:
                    self._adaptive_polling.record_activity(integration)

                if self._performance_monitor:
                    self._performance_monitor.record_success(integration)

        except Exception as e:
            logger.error(f"Error handling integration state change: {e}")

    def _on_failover_event(self, event: Any) -> None:
        """Handle failover events."""
        try:
            # Record failover in performance metrics
            if self._performance_monitor:
                self._performance_monitor.record_failover(
                    event.get("integration", "unknown"),
                    event.get("reason", "unknown"),
                    event.get("timestamp", 0),
                )

            logger.warning(f"Failover activated: {event}")

        except Exception as e:
            logger.error(f"Error handling failover event: {e}")

    def _on_performance_alert(self, alert: Any) -> None:
        """Handle performance alerts."""
        try:
            # Reduced to debug to avoid log spam
            logger.debug(f"Performance alert: {alert}")

            # Take automatic optimization actions based on alert
            if alert.get("severity") == "critical":
                # Critical performance issue - take immediate action
                alert_type = alert.get("type")

                if alert_type == "scene_activation_slow":
                    # Scene activation too slow - optimize orchestrator
                    asyncio.create_task(self._optimize_scene_performance())

                elif alert_type == "network_latency_high":
                    # Network latency issue - adjust polling
                    asyncio.create_task(self._optimize_network_performance())

        except Exception as e:
            logger.error(f"Error handling performance alert: {e}")

    def _on_polling_optimization(self, integration: str, new_interval: float) -> None:
        """Handle polling interval optimizations."""
        try:
            # Record optimization in performance metrics
            if self._performance_monitor:
                self._performance_monitor.record_optimization(
                    integration,
                    "polling_interval",
                    new_interval * 1000,  # Convert to ms for consistency
                )

            logger.debug(f"Optimized polling for {integration}: {new_interval}s")

        except Exception as e:
            logger.error(f"Error handling polling optimization: {e}")

    async def _optimize_scene_performance(self) -> None:
        """Optimize scene activation performance."""
        try:
            if self._integration_pool:
                # Increase priority for scene-critical integrations
                await self._integration_pool.boost_priority(["control4", "denon"])

        except Exception as e:
            logger.error(f"Failed to optimize scene performance: {e}")

    async def _optimize_network_performance(self) -> None:
        """Optimize network performance."""
        try:
            if self._adaptive_polling:
                # Reduce polling frequency for non-critical integrations
                await self._adaptive_polling.reduce_polling_frequency(["oelo", "spotify"])

        except Exception as e:
            logger.error(f"Failed to optimize network performance: {e}")

    async def force_optimization_cycle(self) -> dict[str, Any]:
        """Force a complete optimization cycle."""
        results = {"timestamp": asyncio.get_event_loop().time()}

        try:
            # Clear caches and reset adaptive systems
            if self._performance_monitor:
                await self._performance_monitor.reset_metrics()
                results["performance_reset"] = True

            # Force polling optimization
            if self._adaptive_polling:
                optimizations = await self._adaptive_polling.force_optimization()
                results["polling_optimizations"] = optimizations

            # Reset integration pool metrics
            if self._integration_pool:
                await self._integration_pool.reset_metrics()
                results["integration_pool_reset"] = True

            # Force failover health checks
            if self._failover_manager:
                health = await self._failover_manager.check_all_health()
                results["health_checks"] = health

            logger.info("Forced optimization cycle completed")

        except Exception as e:
            logger.error(f"Failed to force optimization cycle: {e}")
            results["error"] = str(e)

        return results

    def enable_optimization(self, enabled: bool = True) -> None:
        """Enable or disable optimization."""
        self._optimization_enabled = enabled

        # Update individual components
        if self._adaptive_polling:
            self._adaptive_polling.set_enabled(enabled)

        if self._integration_pool:
            self._integration_pool.set_optimization_enabled(enabled)

        logger.info(f"Optimization {'enabled' if enabled else 'disabled'}")

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary from all components."""
        summary = {
            "optimization_enabled": self._optimization_enabled,
            "running": self._running,
        }

        try:
            if self._performance_monitor:
                summary["metrics"] = self._performance_monitor.get_metrics()

            if self._integration_pool:
                summary["integration_pool"] = self._integration_pool.get_status()

            # Add orchestrator stats if available
            if hasattr(self, "_orchestrator") and self._orchestrator:
                summary["orchestrator"] = self._orchestrator.get_performance_stats()

        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            summary["error"] = str(e)

        return summary

    def get_integration_health(self) -> dict[str, Any]:
        """Get integration health status."""
        health = {}

        try:
            if self._failover_manager:
                health = self._failover_manager.get_health_status()

        except Exception as e:
            logger.error(f"Error getting integration health: {e}")
            health["error"] = str(e)

        return health

    # Property accessors
    @property
    def performance_monitor(self):
        """Get the performance monitor."""
        if not self._performance_monitor:
            raise RuntimeError("Performance monitor not initialized")
        return self._performance_monitor

    @property
    def failover_manager(self):
        """Get the failover manager."""
        if not self._failover_manager:
            raise RuntimeError("Failover manager not initialized")
        return self._failover_manager

    @property
    def adaptive_polling(self):
        """Get the adaptive polling manager."""
        if not self._adaptive_polling:
            raise RuntimeError("Adaptive polling not initialized")
        return self._adaptive_polling

    @property
    def integration_pool(self):
        """Get the integration pool."""
        if not self._integration_pool:
            raise RuntimeError("Integration pool not initialized")
        return self._integration_pool
