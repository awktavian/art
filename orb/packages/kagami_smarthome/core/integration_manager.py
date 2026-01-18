"""Integration Manager — Discovery, Reconnection, Health, Failover.

Extracted from SmartHomeController to handle all integration lifecycle
management. This reduces the controller from 4000+ LOC to <500 LOC.

Responsibilities:
- Device discovery via UniFi
- Integration initialization
- Health monitoring
- Reconnection logic
- Failover management
- Degradation mode

Created: January 2, 2026
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.discovery import DeviceDiscovery, DeviceRegistry
    from kagami_smarthome.failover_manager import FailoverManager
    from kagami_smarthome.integration_pool import IntegrationPool
    from kagami_smarthome.performance_monitor import PerformanceMonitor
    from kagami_smarthome.polling_stub import AdaptivePollingManager
    from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)


class IntegrationManager:
    """Manages integration lifecycle: discovery, health, reconnection, failover.

    Extracts ~1500 LOC of infrastructure code from SmartHomeController.

    Usage:
        manager = IntegrationManager(config, performance_monitor)
        await manager.discover_devices()
        await manager.initialize_integrations()
        await manager.start_health_monitoring()
    """

    def __init__(
        self,
        config: SmartHomeConfig,
        performance_monitor: PerformanceMonitor,
        integration_pool: IntegrationPool,
        failover_manager: FailoverManager,
        adaptive_polling: AdaptivePollingManager,
    ) -> None:
        """Initialize integration manager.

        Args:
            config: Smart home configuration
            performance_monitor: Performance monitoring instance
            integration_pool: Connection pooling for integrations
            failover_manager: Failover management
            adaptive_polling: Adaptive polling manager
        """
        self.config = config
        self._performance_monitor = performance_monitor
        self._integration_pool = integration_pool
        self._failover_manager = failover_manager
        self._adaptive_polling = adaptive_polling

        # Device discovery
        self._discovery: DeviceDiscovery | None = None
        self._resolved_ips: dict[str, str | None] = {}

        # Integration instances (set by controller)
        self._integrations: dict[str, Any] = {}

        # Health monitoring
        self._health_task: asyncio.Task[None] | None = None
        self._degraded_integrations: set[str] = set()

        # Callbacks
        self._on_state_change: Callable[[str, Any], None] | None = None
        self._on_failover: Callable[[Any], None] | None = None
        self._on_performance_alert: Callable[[Any], None] | None = None

    def register_integration(self, name: str, integration: Any) -> None:
        """Register an integration instance.

        Args:
            name: Integration name (e.g., 'control4', 'denon')
            integration: Integration instance
        """
        self._integrations[name] = integration

    def get_integration(self, name: str) -> Any | None:
        """Get an integration by name.

        Args:
            name: Integration name

        Returns:
            Integration instance or None
        """
        return self._integrations.get(name)

    @property
    def resolved_ips(self) -> dict[str, str | None]:
        """Get resolved device IPs."""
        return self._resolved_ips.copy()

    @property
    def discovery(self) -> DeviceDiscovery | None:
        """Get device discovery instance."""
        return self._discovery

    # =========================================================================
    # Device Discovery
    # =========================================================================

    async def discover_devices(self) -> bool:
        """Discover devices via UniFi and resolve IPs.

        Returns:
            True if discovery succeeded
        """
        if not self.config.auto_discover:
            logger.info("Auto-discovery disabled, using static IPs")
            self._use_static_ips()
            return True

        try:
            from kagami_smarthome.discovery import DeviceDiscovery

            self._discovery = DeviceDiscovery(
                unifi_host=self.config.unifi_host,
                unifi_username=self.config.unifi_username,
                unifi_password=self.config.unifi_password,
            )

            await self._discovery.connect()
            await self._discovery.refresh()

            self._update_resolved_ips()
            self._discovery.on_devices_changed = self._on_devices_changed

            logger.info(f"✅ Device discovery complete: {len(self._resolved_ips)} devices")
            return True

        except Exception as e:
            logger.warning(f"Device discovery failed: {e}, using static IPs")
            self._use_static_ips()
            return False

    def _use_static_ips(self) -> None:
        """Use static IPs from config as fallback."""
        self._resolved_ips = {
            "denon": self.config.denon_host,
            "lg_tv": self.config.lg_tv_host,
            "samsung_tv": self.config.samsung_tv_host,
            "control4": self.config.control4_host,
            "envisalink": self.config.dsc_host,  # DSC/Envisalink host
        }

    def _update_resolved_ips(self) -> None:
        """Update resolved IPs from discovery registry."""
        if not self._discovery:
            return

        registry = self._discovery.registry

        # Map device types to discovery patterns
        device_patterns = {
            "denon": {"mac_prefix": "00:05:cd", "hostname_contains": "denon"},
            "lg_tv": {"mac_prefix": "38:8c:50", "hostname_contains": "lg"},
            "samsung_tv": {"hostname_contains": "samsung"},
        }

        for device_type, patterns in device_patterns.items():
            ip = registry.find_by_pattern(**patterns)
            if ip:
                self._resolved_ips[device_type] = ip

        # Control4 uses static IP (controller)
        self._resolved_ips["control4"] = self.config.control4_host

    def _on_devices_changed(self, registry: DeviceRegistry) -> None:
        """Handle device registry changes.

        Args:
            registry: Updated device registry
        """
        old_ips = self._resolved_ips.copy()
        self._update_resolved_ips()

        # Check for IP changes requiring reconnection
        for device_type, new_ip in self._resolved_ips.items():
            old_ip = old_ips.get(device_type)
            if old_ip and new_ip and old_ip != new_ip:
                logger.info(f"IP changed for {device_type}: {old_ip} -> {new_ip}")
                asyncio.create_task(self._reconnect_integration(device_type, new_ip))

    def get_ip(self, device_type: str) -> str | None:
        """Get resolved IP for a device type.

        Args:
            device_type: Device type name

        Returns:
            IP address or None
        """
        return self._resolved_ips.get(device_type)

    # =========================================================================
    # Health Monitoring
    # =========================================================================

    async def start_health_monitoring(self) -> None:
        """Start background health monitoring."""
        if self._health_task is None:
            self._health_task = asyncio.create_task(self._health_monitor_loop())
            logger.info("✅ Health monitoring started")

    async def stop_health_monitoring(self) -> None:
        """Stop background health monitoring."""
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None
            logger.info("Health monitoring stopped")

    async def _health_monitor_loop(self) -> None:
        """Background health monitoring loop."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every 60 seconds
                await self._perform_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(30)

    async def _perform_health_check(self) -> None:
        """Perform health check on all integrations."""
        health_results = await self.check_integration_health()

        for device_type, health in health_results.items():
            if not health.get("reachable", True):
                await self._handle_unreachable_device(device_type, health)

    async def check_integration_health(self) -> dict[str, dict[str, Any]]:
        """Check health of all integrations.

        Returns:
            Dict of integration name -> health info
        """
        results: dict[str, dict[str, Any]] = {}

        for name, integration in self._integrations.items():
            try:
                if hasattr(integration, "ping") or hasattr(integration, "is_connected"):
                    is_connected = (
                        await integration.ping()
                        if hasattr(integration, "ping")
                        else integration.is_connected
                    )
                    results[name] = {
                        "reachable": is_connected,
                        "degraded": name in self._degraded_integrations,
                    }
                else:
                    results[name] = {"reachable": True, "degraded": False}
            except Exception as e:
                logger.warning(f"Health check failed for {name}: {e}")
                results[name] = {"reachable": False, "error": str(e)}

        return results

    async def _handle_unreachable_device(self, device_type: str, health: dict[str, Any]) -> None:
        """Handle unreachable device.

        Args:
            device_type: Device type name
            health: Health check results
        """
        if device_type in self._degraded_integrations:
            return  # Already degraded

        logger.warning(f"Device unreachable: {device_type}")

        # Try reconnection first
        new_ip = self.get_ip(device_type)
        if new_ip:
            success = await self._reconnect_integration(device_type, new_ip)
            if success:
                return

        # Enter degradation mode
        await self._enter_degradation_mode(device_type)

    # =========================================================================
    # Reconnection
    # =========================================================================

    async def _reconnect_integration(self, device_type: str, new_ip: str) -> bool:
        """Reconnect an integration with new IP.

        Args:
            device_type: Device type name
            new_ip: New IP address

        Returns:
            True if reconnection succeeded
        """
        integration = self._integrations.get(device_type)
        if not integration:
            return False

        try:
            # Graceful disconnect
            await self._graceful_disconnect(integration, device_type)

            # Update config
            self._update_integration_config(integration, device_type, new_ip)

            # Attempt reconnection
            success = await self._attempt_reconnection(integration, device_type)

            if success:
                # Remove from degraded if was degraded
                self._degraded_integrations.discard(device_type)
                logger.info(f"✅ Reconnected {device_type} at {new_ip}")

            return success

        except Exception as e:
            logger.error(f"Reconnection failed for {device_type}: {e}")
            return False

    async def _graceful_disconnect(self, integration: Any, device_type: str) -> None:
        """Gracefully disconnect integration.

        Args:
            integration: Integration instance
            device_type: Device type name
        """
        if hasattr(integration, "disconnect"):
            try:
                await asyncio.wait_for(integration.disconnect(), timeout=5.0)
            except TimeoutError:
                logger.warning(f"Disconnect timeout for {device_type}")
            except Exception as e:
                logger.warning(f"Disconnect error for {device_type}: {e}")

    def _update_integration_config(self, integration: Any, device_type: str, new_ip: str) -> None:
        """Update integration config with new IP.

        Args:
            integration: Integration instance
            device_type: Device type name
            new_ip: New IP address
        """
        if hasattr(integration, "host"):
            integration.host = new_ip
        elif hasattr(integration, "_host"):
            integration._host = new_ip

    async def _attempt_reconnection(self, integration: Any, device_type: str) -> bool:
        """Attempt to reconnect integration.

        Args:
            integration: Integration instance
            device_type: Device type name

        Returns:
            True if reconnection succeeded
        """
        if hasattr(integration, "connect"):
            try:
                await asyncio.wait_for(integration.connect(), timeout=30.0)
                return True
            except TimeoutError:
                logger.warning(f"Reconnection timeout for {device_type}")
                return False
            except Exception as e:
                logger.warning(f"Reconnection failed for {device_type}: {e}")
                return False
        return True

    async def force_reconnect_integration(self, integration_name: str) -> bool:
        """Force reconnect a specific integration.

        Args:
            integration_name: Integration name

        Returns:
            True if reconnection succeeded
        """
        ip = self.get_ip(integration_name)
        if ip:
            return await self._reconnect_integration(integration_name, ip)
        return False

    # =========================================================================
    # Degradation and Failover
    # =========================================================================

    async def _enter_degradation_mode(self, device_type: str) -> None:
        """Enter degradation mode for a device type.

        Args:
            device_type: Device type name
        """
        self._degraded_integrations.add(device_type)
        logger.warning(f"⚠️ Entered degradation mode for {device_type}")

        # Notify callbacks
        if self._on_state_change:
            self._on_state_change(device_type, {"degraded": True})

    async def _exit_degradation_mode(self, device_type: str) -> None:
        """Exit degradation mode for a device type.

        Args:
            device_type: Device type name
        """
        self._degraded_integrations.discard(device_type)
        logger.info(f"✅ Exited degradation mode for {device_type}")

        # Notify callbacks
        if self._on_state_change:
            self._on_state_change(device_type, {"degraded": False})

    def is_in_degraded_mode(self, device_type: str | None = None) -> bool:
        """Check if in degraded mode.

        Args:
            device_type: Optional specific device type to check

        Returns:
            True if in degraded mode
        """
        if device_type:
            return device_type in self._degraded_integrations
        return len(self._degraded_integrations) > 0

    def get_degraded_integrations(self) -> list[str]:
        """Get list of degraded integrations.

        Returns:
            List of degraded integration names
        """
        return list(self._degraded_integrations)

    # =========================================================================
    # Callbacks
    # =========================================================================

    def set_callbacks(
        self,
        on_state_change: Callable[[str, Any], None] | None = None,
        on_failover: Callable[[Any], None] | None = None,
        on_performance_alert: Callable[[Any], None] | None = None,
    ) -> None:
        """Set event callbacks.

        Args:
            on_state_change: Called when integration state changes
            on_failover: Called on failover events
            on_performance_alert: Called on performance alerts
        """
        if on_state_change:
            self._on_state_change = on_state_change
        if on_failover:
            self._on_failover = on_failover
        if on_performance_alert:
            self._on_performance_alert = on_performance_alert

    # =========================================================================
    # Integration Pool / Optimization
    # =========================================================================

    async def configure_integration_pool(self) -> None:
        """Configure integration connection pooling."""
        for name, integration in self._integrations.items():
            if hasattr(integration, "get_connection"):
                await self._integration_pool.register(
                    name=name,
                    factory=integration.get_connection,
                    max_connections=self.config.pool_size_per_integration,
                )

    async def configure_adaptive_polling(self) -> None:
        """Configure adaptive polling for integrations."""
        polling_configs = {
            "unifi": {"base_interval": 30, "min_interval": 10, "max_interval": 120},
            "control4": {"base_interval": 5, "min_interval": 1, "max_interval": 30},
            "eight_sleep": {"base_interval": 300, "min_interval": 60, "max_interval": 900},
            "tesla": {"base_interval": 60, "min_interval": 30, "max_interval": 300},
        }

        for name, config in polling_configs.items():
            if name in self._integrations:
                await self._adaptive_polling.register(name, **config)

    async def start_optimization_services(self) -> None:
        """Start optimization services (pool, failover, polling)."""
        await self._integration_pool.start()
        await self._failover_manager.start()
        await self._adaptive_polling.start()

    async def stop_optimization_services(self) -> None:
        """Stop optimization services."""
        await self._integration_pool.stop()
        await self._failover_manager.stop()
        await self._adaptive_polling.stop()

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary.

        Returns:
            Performance metrics summary
        """
        return {
            "integrations": len(self._integrations),
            "degraded": list(self._degraded_integrations),
            "pool_stats": self._integration_pool.get_stats(),
            "failover_stats": self._failover_manager.get_stats(),
            "polling_stats": self._adaptive_polling.get_stats(),
        }


__all__ = ["IntegrationManager"]
