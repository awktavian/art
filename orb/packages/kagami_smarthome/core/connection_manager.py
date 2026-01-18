"""Connection Manager - Handles IP discovery, device connections, and network health.

Responsibilities:
- Device discovery via UniFi
- IP resolution and caching
- Connection management with retry logic
- Network health monitoring
- Failover coordination
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages device discovery, IP resolution, and connection health."""

    def __init__(self, config, performance_monitor, failover_manager):
        self.config = config
        self.performance_monitor = performance_monitor
        self.failover_manager = failover_manager

        # IP resolution
        self._discovery = None
        self._resolved_ips: dict[str, str | None] = {}

        # Connection management
        self._connection_timeouts = {
            "control4_director": 5.0,
            "denon": 3.0,
            "lg_tv": 3.0,
            "samsung_tv": 3.0,
            "oelo": 2.0,
            "eight_sleep": 15.0,
            "tesla": 5.0,
            "august": 5.0,
            "mitsubishi": 5.0,
            "unifi": 3.0,
            "envisalink": 1.0,
        }
        self._max_concurrent_connections = 15
        self._connection_semaphore = asyncio.Semaphore(self._max_concurrent_connections)

        # Health monitoring
        self._health_monitor_task: asyncio.Task | None = None
        self._running = False

        # Failover configuration
        self._critical_integrations = {"control4_director", "unifi"}
        self._optional_integrations = {"envisalink", "oelo", "lg_tv", "samsung_tv"}
        self._degraded_integrations: set[str] = set()

    async def discover_devices(self) -> bool:
        """Discover devices and resolve IPs via UniFi."""
        if not self.config.auto_discover:
            logger.info("Auto-discovery disabled, using static IPs")
            return True

        try:
            from kagami_smarthome.discovery import DeviceDiscovery

            self._discovery = DeviceDiscovery(
                unifi_host=self.config.unifi_host,
                unifi_username=self.config.unifi_username,
                unifi_password=self.config.unifi_password,
            )

            success = await self._discovery.initialize()
            if success:
                self._discovery.registry.on_devices_changed = self._on_devices_changed
                self._update_resolved_ips()
                logger.info("Device discovery initialized successfully")
                return True

            logger.warning("Device discovery failed, falling back to static IPs")
            return False

        except Exception as e:
            logger.error(f"Failed to initialize device discovery: {e}")
            return False

    def _update_resolved_ips(self) -> None:
        """Update resolved IP cache from discovery."""
        if not self._discovery:
            return

        devices = self._discovery.registry.get_devices()
        logger.debug(f"Discovered {len(devices)} devices")

        for device in devices:
            if device.ip:
                self._resolved_ips[device.device_type] = device.ip

    def _on_devices_changed(self, registry) -> None:
        """Handle device IP changes and schedule reconnections."""
        old_ips = self._resolved_ips.copy()
        self._update_resolved_ips()

        for device_type, new_ip in self._resolved_ips.items():
            old_ip = old_ips.get(device_type)
            if old_ip != new_ip and old_ip is not None:
                logger.info(f"{device_type} IP changed: {old_ip} → {new_ip}")
                asyncio.create_task(self._reconnect_integration(device_type, new_ip))

    async def _reconnect_integration(self, device_type: str, new_ip: str) -> None:
        """Reconnect an integration after IP change."""
        integration_mapping = {
            "control4_director": "control4",
            "denon_avr": "denon",
            "lg_tv": "lg_tv",
            "samsung_tv": "samsung_tv",
            "oelo_outdoor": "oelo",
            "eight_sleep": "eight_sleep",
            "mitsubishi_hvac": "mitsubishi",
        }

        integration_attr = integration_mapping.get(device_type)
        if not integration_attr:
            logger.debug(f"No integration mapping for {device_type}")
            return

        # This would be called by the main controller
        logger.info(f"Scheduling reconnection for {device_type} with new IP {new_ip}")

    async def start_health_monitoring(self) -> None:
        """Start the health monitoring task."""
        if self._health_monitor_task:
            return

        self._running = True
        self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
        logger.info("Started connection health monitoring")

    async def stop_health_monitoring(self) -> None:
        """Stop the health monitoring task."""
        self._running = False
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass
            self._health_monitor_task = None
        logger.info("Stopped connection health monitoring")

    async def _health_monitor_loop(self) -> None:
        """Monitor network health and trigger reconnections as needed."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                if self._discovery:
                    await self._discovery.update_devices()

            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(5)

    def get_ip(self, device_type: str) -> str | None:
        """Get resolved IP for device type."""
        return self._resolved_ips.get(device_type)

    def get_resolved_ips(self) -> dict[str, str | None]:
        """Get all resolved IPs."""
        return self._resolved_ips.copy()

    def is_in_degraded_mode(self, device_type: str | None = None) -> bool:
        """Check if device/system is in degraded mode."""
        if device_type:
            return device_type in self._degraded_integrations
        return len(self._degraded_integrations) > 0

    def get_degraded_integrations(self) -> list[str]:
        """Get list of degraded integrations."""
        return list(self._degraded_integrations)

    async def enter_degradation_mode(self, device_type: str) -> None:
        """Enter degraded mode for a device type."""
        self._degraded_integrations.add(device_type)
        logger.warning(f"Entered degraded mode for {device_type}")

    async def exit_degradation_mode(self, device_type: str) -> None:
        """Exit degraded mode for a device type."""
        self._degraded_integrations.discard(device_type)
        logger.info(f"Exited degraded mode for {device_type}")

    @property
    def discovery(self):
        """Get the discovery instance."""
        return self._discovery
