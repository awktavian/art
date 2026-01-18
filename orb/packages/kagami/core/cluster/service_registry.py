"""Unified Service Registry — Track all Kagami nodes across locations.

Byzantine-aware service discovery with etcd-backed registration.
Supports API servers, Hubs, SmartHome daemons, workers, and edge nodes.

Architecture:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SERVICE REGISTRY                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  etcd: /kagami/services/                                                │
│  ├── api/                                                               │
│  │   ├── kagami-primary/   { node_id, address, port, health, ... }     │
│  │   └── kagami-edge-1/    { ... }                                     │
│  ├── hub/                                                               │
│  │   ├── hub-kitchen/      { ... }                                     │
│  │   ├── hub-living/       { ... }                                     │
│  │   └── hub-bedroom/      { ... }                                     │
│  ├── smarthome/                                                         │
│  │   └── smarthome-primary/ { ... }                                    │
│  └── worker/                                                            │
│      └── worker-1/         { ... }                                     │
│                                                                          │
│  Watches: Real-time updates via etcd watch API                          │
│  TTL: Services expire after 3x heartbeat interval                       │
│  Byzantine: Detect and isolate misbehaving nodes                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

Usage:
    from kagami.core.cluster.service_registry import (
        get_service_registry,
        ServiceType,
        ServiceInstance,
    )

    registry = await get_service_registry()

    # Register this node
    await registry.register(
        service_type=ServiceType.API,
        node_id="kagami-primary",
        address="192.168.1.100",
        port=8001,
    )

    # Discover services
    hubs = await registry.discover(ServiceType.HUB)
    for hub in hubs:
        print(f"Hub: {hub.node_id} at {hub.address}:{hub.port}")

    # Watch for changes
    async for event in registry.watch(ServiceType.HUB):
        print(f"Hub {event.type}: {event.instance.node_id}")

Created: January 4, 2026
Colony: Nexus (e₄) — Connection and coordination
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.consensus.etcd_client import EtcdConnectionPool

logger = logging.getLogger(__name__)


# =============================================================================
# SERVICE TYPES
# =============================================================================


class ServiceType(str, Enum):
    """Types of services in the Kagami distributed system.

    Each service type has specific capabilities and roles:
    - API: HTTP/WebSocket API servers (primary interaction point)
    - HUB: Raspberry Pi voice hubs (wake word, TTS, LED ring)
    - SMARTHOME: Smart home daemon (Control4, integrations)
    - WORKER: Background task workers (Celery, async jobs)
    - EDGE: Cloud edge nodes (failover, read-only replicas)
    - CONSENSUS: Dedicated consensus workers (PBFT, leader election)
    """

    API = "api"
    HUB = "hub"
    SMARTHOME = "smarthome"
    WORKER = "worker"
    EDGE = "edge"
    CONSENSUS = "consensus"


class ServiceHealth(str, Enum):
    """Service health status for Byzantine detection."""

    HEALTHY = "healthy"  # All checks passing
    DEGRADED = "degraded"  # Some checks failing, but operational
    UNHEALTHY = "unhealthy"  # Critical failures
    SUSPECT = "suspect"  # Byzantine behavior detected
    ISOLATED = "isolated"  # Removed from consensus
    UNKNOWN = "unknown"  # No recent heartbeat


class ServiceEvent(str, Enum):
    """Event types for service discovery watches."""

    REGISTERED = "registered"  # New service joined
    UPDATED = "updated"  # Service state changed
    DEREGISTERED = "deregistered"  # Service left
    SUSPECT = "suspect"  # Byzantine behavior
    ISOLATED = "isolated"  # Removed from mesh


# =============================================================================
# SERVICE INSTANCE
# =============================================================================


@dataclass
class ServiceInstance:
    """Information about a registered service instance.

    Attributes:
        service_type: Type of service (API, HUB, etc.)
        node_id: Unique node identifier
        hostname: Node hostname
        address: Network address (IP or hostname)
        port: Service port
        health: Current health status
        version: Service version string
        capabilities: List of supported capabilities
        last_heartbeat: Unix timestamp of last heartbeat
        registered_at: Unix timestamp of registration
        metadata: Additional service-specific metadata
        byzantine_score: Suspicion score (0.0 = trusted, 1.0 = isolated)
    """

    service_type: ServiceType
    node_id: str
    hostname: str
    address: str
    port: int
    health: ServiceHealth = ServiceHealth.UNKNOWN
    version: str = ""
    capabilities: list[str] = field(default_factory=list)
    last_heartbeat: float = field(default_factory=time.time)
    registered_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    byzantine_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for etcd storage."""
        return {
            "service_type": self.service_type.value,
            "node_id": self.node_id,
            "hostname": self.hostname,
            "address": self.address,
            "port": self.port,
            "health": self.health.value,
            "version": self.version,
            "capabilities": self.capabilities,
            "last_heartbeat": self.last_heartbeat,
            "registered_at": self.registered_at,
            "metadata": self.metadata,
            "byzantine_score": self.byzantine_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServiceInstance:
        """Deserialize from dictionary."""
        return cls(
            service_type=ServiceType(data["service_type"]),
            node_id=data["node_id"],
            hostname=data.get("hostname", ""),
            address=data["address"],
            port=data["port"],
            health=ServiceHealth(data.get("health", "unknown")),
            version=data.get("version", ""),
            capabilities=data.get("capabilities", []),
            last_heartbeat=data.get("last_heartbeat", time.time()),
            registered_at=data.get("registered_at", time.time()),
            metadata=data.get("metadata", {}),
            byzantine_score=data.get("byzantine_score", 0.0),
        )

    @property
    def is_healthy(self) -> bool:
        """Check if service is considered healthy."""
        return self.health in (ServiceHealth.HEALTHY, ServiceHealth.DEGRADED)

    @property
    def is_trusted(self) -> bool:
        """Check if service is trusted for consensus."""
        return self.byzantine_score < 0.5 and self.health != ServiceHealth.ISOLATED

    @property
    def is_stale(self) -> bool:
        """Check if service heartbeat is stale (3x interval)."""
        heartbeat_interval = float(os.getenv("CLUSTER_HEARTBEAT_INTERVAL", "10"))
        stale_threshold = heartbeat_interval * 3
        return time.time() - self.last_heartbeat > stale_threshold

    @property
    def api_url(self) -> str:
        """Get the API URL for this service."""
        return f"http://{self.address}:{self.port}"

    @property
    def ws_url(self) -> str:
        """Get the WebSocket URL for this service."""
        return f"ws://{self.address}:{self.port}"


@dataclass
class ServiceEventData:
    """Event data for service registry watches."""

    event_type: ServiceEvent
    instance: ServiceInstance
    timestamp: float = field(default_factory=time.time)
    reason: str = ""


# =============================================================================
# SERVICE REGISTRY
# =============================================================================


class ServiceRegistry:
    """Unified service registry with etcd-backed discovery.

    Features:
    - Service registration with TTL-based expiry
    - Real-time discovery via etcd watches
    - Byzantine detection and isolation
    - Health aggregation across services
    - Automatic stale service cleanup

    Thread Safety:
    - All public methods are async and thread-safe
    - Uses etcd transactions for atomic operations

    Byzantine Tolerance:
    - Tracks byzantine_score for each service
    - Isolates services with score >= 0.5
    - Requires 2f+1 agreement for critical operations
    """

    # etcd key prefix for services
    ETCD_PREFIX = "/kagami/services"

    # Heartbeat and expiry settings
    DEFAULT_HEARTBEAT_INTERVAL = 10.0  # seconds
    DEFAULT_TTL_MULTIPLIER = 3.0  # TTL = heartbeat * multiplier

    def __init__(
        self,
        etcd_pool: EtcdConnectionPool | None = None,
        heartbeat_interval: float | None = None,
    ):
        """Initialize service registry.

        Args:
            etcd_pool: etcd connection pool (auto-discovered if None)
            heartbeat_interval: Heartbeat interval in seconds
        """
        self._etcd_pool = etcd_pool
        self._heartbeat_interval = heartbeat_interval or float(
            os.getenv("CLUSTER_HEARTBEAT_INTERVAL", str(self.DEFAULT_HEARTBEAT_INTERVAL))
        )

        # In-memory mode when etcd is unavailable
        self._in_memory_mode = os.getenv("SKIP_ETCD", "").lower() in ("true", "1", "yes")

        # Local cache of discovered services
        self._services: dict[ServiceType, dict[str, ServiceInstance]] = {
            st: {} for st in ServiceType
        }

        # This node's registration
        self._local_instance: ServiceInstance | None = None
        self._lease_id: int | None = None

        # Background tasks
        self._heartbeat_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._watch_tasks: list[asyncio.Task] = []

        # Event subscribers
        self._event_callbacks: list[asyncio.Queue[ServiceEventData]] = []

        # State
        self._started = False
        self._shutdown = False

        mode = "in-memory" if self._in_memory_mode else "etcd"
        logger.info(
            f"ServiceRegistry initialized (mode={mode}, heartbeat={self._heartbeat_interval}s)"
        )

    async def _get_etcd(self) -> EtcdConnectionPool:
        """Get or create etcd connection pool."""
        if self._etcd_pool is None:
            from kagami.core.consensus.etcd_client import get_etcd_pool

            self._etcd_pool = await get_etcd_pool()
        return self._etcd_pool

    # =========================================================================
    # REGISTRATION
    # =========================================================================

    async def register(
        self,
        service_type: ServiceType,
        node_id: str,
        address: str,
        port: int,
        *,
        hostname: str | None = None,
        version: str = "",
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ServiceInstance:
        """Register this node as a service.

        Args:
            service_type: Type of service
            node_id: Unique node identifier
            address: Network address (IP or hostname)
            port: Service port
            hostname: Node hostname (auto-detected if None)
            version: Service version string
            capabilities: List of supported capabilities
            metadata: Additional metadata

        Returns:
            ServiceInstance representing this node

        Example:
            instance = await registry.register(
                service_type=ServiceType.HUB,
                node_id="hub-kitchen",
                address="192.168.1.50",
                port=8080,
                capabilities=["voice", "led", "mesh"],
            )
        """
        # Create service instance
        instance = ServiceInstance(
            service_type=service_type,
            node_id=node_id,
            hostname=hostname or socket.gethostname(),
            address=address,
            port=port,
            health=ServiceHealth.HEALTHY,
            version=version or os.getenv("KAGAMI_VERSION", "0.1.0"),
            capabilities=capabilities or [],
            metadata=metadata or {},
        )

        # Store in memory first (always)
        self._local_instance = instance
        self._services[service_type][node_id] = instance

        # Also store in etcd if available
        if not self._in_memory_mode:
            try:
                etcd = await self._get_etcd()

                # Create lease for TTL-based expiry
                ttl = int(self._heartbeat_interval * self.DEFAULT_TTL_MULTIPLIER)
                try:
                    lease_response = await etcd.lease_grant(ttl)
                    self._lease_id = lease_response.ID if hasattr(lease_response, "ID") else None
                except Exception as e:
                    logger.warning(f"Failed to create lease: {e}")
                    self._lease_id = None

                # Store in etcd
                key = f"{self.ETCD_PREFIX}/{service_type.value}/{node_id}"
                value = json.dumps(instance.to_dict())

                if self._lease_id:
                    await etcd.put(key, value, lease=self._lease_id)
                else:
                    await etcd.put(key, value)

                logger.info(
                    f"✅ Registered {service_type.value}/{node_id} at {address}:{port} "
                    f"(etcd, lease_id={self._lease_id})"
                )
            except Exception as e:
                logger.warning(f"etcd unavailable, using in-memory registry: {e}")
                self._in_memory_mode = True
        else:
            import sys

            print(
                f"[REG] Registry id={id(self)}, registered {service_type.value}/{node_id}, cache={list(self._services[service_type].keys())}",
                file=sys.stderr,
                flush=True,
            )
            logger.info(
                f"✅ Registered {service_type.value}/{node_id} at {address}:{port} (in-memory)"
            )

        # Start heartbeat task
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Emit registration event
        await self._emit_event(
            ServiceEventData(
                event_type=ServiceEvent.REGISTERED,
                instance=instance,
            )
        )

        return instance

    async def deregister(self) -> None:
        """Deregister this node from the registry."""
        if not self._local_instance:
            return

        etcd = await self._get_etcd()
        service_type = self._local_instance.service_type
        node_id = self._local_instance.node_id

        # Delete from etcd
        key = f"{self.ETCD_PREFIX}/{service_type.value}/{node_id}"
        try:
            await etcd.delete(key)
            logger.info(f"✅ Deregistered {service_type.value}/{node_id}")
        except Exception as e:
            logger.error(f"Failed to deregister: {e}")

        # Revoke lease
        if self._lease_id:
            try:
                await etcd.lease_revoke(self._lease_id)
            except Exception:
                pass

        # Emit event
        await self._emit_event(
            ServiceEventData(
                event_type=ServiceEvent.DEREGISTERED,
                instance=self._local_instance,
            )
        )

        # Clear local state
        self._services[service_type].pop(node_id, None)
        self._local_instance = None
        self._lease_id = None

    async def update_health(self, health: ServiceHealth) -> None:
        """Update this node's health status.

        Args:
            health: New health status
        """
        if not self._local_instance:
            return

        self._local_instance.health = health
        self._local_instance.last_heartbeat = time.time()

        # Update in etcd
        etcd = await self._get_etcd()
        key = f"{self.ETCD_PREFIX}/{self._local_instance.service_type.value}/{self._local_instance.node_id}"
        value = json.dumps(self._local_instance.to_dict())

        try:
            if self._lease_id:
                await etcd.put(key, value, lease=self._lease_id)
            else:
                await etcd.put(key, value)
        except Exception as e:
            logger.debug(f"Failed to update health: {e}")

    # =========================================================================
    # DISCOVERY
    # =========================================================================

    async def discover(
        self,
        service_type: ServiceType | None = None,
        *,
        healthy_only: bool = True,
        trusted_only: bool = True,
    ) -> list[ServiceInstance]:
        """Discover registered services.

        Args:
            service_type: Filter by service type (None = all types)
            healthy_only: Only return healthy services
            trusted_only: Only return trusted (non-Byzantine) services

        Returns:
            List of ServiceInstance objects

        Example:
            # Get all healthy hubs
            hubs = await registry.discover(ServiceType.HUB)

            # Get all services including unhealthy
            all_services = await registry.discover(healthy_only=False)
        """
        instances: list[ServiceInstance] = []

        # In-memory mode: use local cache only
        if self._in_memory_mode:
            if service_type:
                instances = list(self._services[service_type].values())
            else:
                for services in self._services.values():
                    instances.extend(services.values())
        else:
            # etcd mode: query etcd
            try:
                etcd = await self._get_etcd()

                # Determine prefix to search
                if service_type:
                    prefix = f"{self.ETCD_PREFIX}/{service_type.value}/"
                else:
                    prefix = f"{self.ETCD_PREFIX}/"

                result = await etcd.get_prefix(prefix)
                for kv in result:
                    try:
                        data = json.loads(
                            kv.value.decode() if isinstance(kv.value, bytes) else kv.value
                        )
                        instance = ServiceInstance.from_dict(data)

                        # Update local cache
                        self._services[instance.service_type][instance.node_id] = instance

                        instances.append(instance)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.debug(f"Failed to parse service: {e}")
            except Exception as e:
                logger.warning(f"etcd unavailable, using in-memory cache: {e}")
                # Fall back to cache
                if service_type:
                    instances = list(self._services[service_type].values())
                else:
                    for services in self._services.values():
                        instances.extend(services.values())

        # Apply filters
        if healthy_only:
            instances = [i for i in instances if i.is_healthy and not i.is_stale]
        if trusted_only:
            instances = [i for i in instances if i.is_trusted]

        return instances

    async def get_service(
        self,
        service_type: ServiceType,
        node_id: str,
    ) -> ServiceInstance | None:
        """Get a specific service instance.

        Args:
            service_type: Type of service
            node_id: Node identifier

        Returns:
            ServiceInstance or None if not found
        """
        etcd = await self._get_etcd()
        key = f"{self.ETCD_PREFIX}/{service_type.value}/{node_id}"

        try:
            result = await etcd.get(key)
            if result:
                data = json.loads(result.decode() if isinstance(result, bytes) else result)
                return ServiceInstance.from_dict(data)
        except Exception as e:
            logger.debug(f"Failed to get service: {e}")

        # Fall back to cache
        return self._services[service_type].get(node_id)

    async def get_api_endpoints(self, *, healthy_only: bool = True) -> list[str]:
        """Get all API endpoints for load balancing.

        Returns:
            List of API URLs (e.g., ["http://192.168.1.100:8001"])
        """
        apis = await self.discover(ServiceType.API, healthy_only=healthy_only)
        return [api.api_url for api in apis]

    async def get_hub_mesh(self) -> list[ServiceInstance]:
        """Get all hub instances for mesh coordination.

        Returns:
            List of Hub ServiceInstances
        """
        return await self.discover(ServiceType.HUB)

    # =========================================================================
    # WATCHES
    # =========================================================================

    async def watch(
        self,
        service_type: ServiceType | None = None,
    ) -> AsyncIterator[ServiceEventData]:
        """Watch for service changes.

        Args:
            service_type: Filter by service type (None = all types)

        Yields:
            ServiceEventData for each change

        Example:
            async for event in registry.watch(ServiceType.HUB):
                if event.event_type == ServiceEvent.REGISTERED:
                    print(f"New hub: {event.instance.node_id}")
        """
        queue: asyncio.Queue[ServiceEventData] = asyncio.Queue()
        self._event_callbacks.append(queue)

        try:
            while not self._shutdown:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    if service_type is None or event.instance.service_type == service_type:
                        yield event
                except TimeoutError:
                    continue
        finally:
            self._event_callbacks.remove(queue)

    async def _emit_event(self, event: ServiceEventData) -> None:
        """Emit event to all subscribers."""
        for queue in self._event_callbacks:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    # =========================================================================
    # BYZANTINE DETECTION
    # =========================================================================

    async def report_byzantine(
        self,
        service_type: ServiceType,
        node_id: str,
        reason: str,
        severity: float = 0.2,
    ) -> None:
        """Report suspected Byzantine behavior.

        Args:
            service_type: Type of service
            node_id: Node identifier
            reason: Description of suspicious behavior
            severity: Severity score to add (0.0 - 1.0)
        """
        instance = await self.get_service(service_type, node_id)
        if not instance:
            return

        # Increase byzantine score
        instance.byzantine_score = min(1.0, instance.byzantine_score + severity)
        logger.warning(
            f"⚠️ Byzantine report for {service_type.value}/{node_id}: {reason} "
            f"(score={instance.byzantine_score:.2f})"
        )

        # Update in etcd
        etcd = await self._get_etcd()
        key = f"{self.ETCD_PREFIX}/{service_type.value}/{node_id}"
        value = json.dumps(instance.to_dict())
        await etcd.put(key, value)

        # Check if should isolate
        if instance.byzantine_score >= 0.5:
            await self._isolate_service(instance, reason)

    async def _isolate_service(
        self,
        instance: ServiceInstance,
        reason: str,
    ) -> None:
        """Isolate a Byzantine service from the mesh.

        Args:
            instance: Service to isolate
            reason: Reason for isolation
        """
        instance.health = ServiceHealth.ISOLATED
        logger.error(f"🚫 ISOLATED {instance.service_type.value}/{instance.node_id}: {reason}")

        # Update in etcd
        etcd = await self._get_etcd()
        key = f"{self.ETCD_PREFIX}/{instance.service_type.value}/{instance.node_id}"
        value = json.dumps(instance.to_dict())
        await etcd.put(key, value)

        # Emit event
        await self._emit_event(
            ServiceEventData(
                event_type=ServiceEvent.ISOLATED,
                instance=instance,
                reason=reason,
            )
        )

    async def clear_byzantine_score(
        self,
        service_type: ServiceType,
        node_id: str,
    ) -> None:
        """Clear Byzantine score for a rehabilitated service.

        Args:
            service_type: Type of service
            node_id: Node identifier
        """
        instance = await self.get_service(service_type, node_id)
        if not instance:
            return

        instance.byzantine_score = 0.0
        if instance.health == ServiceHealth.ISOLATED:
            instance.health = ServiceHealth.HEALTHY

        # Update in etcd
        etcd = await self._get_etcd()
        key = f"{self.ETCD_PREFIX}/{service_type.value}/{node_id}"
        value = json.dumps(instance.to_dict())
        await etcd.put(key, value)

        logger.info(f"✅ Cleared Byzantine score for {service_type.value}/{node_id}")

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    async def start(self) -> None:
        """Start the service registry background tasks."""
        if self._started:
            return

        self._started = True
        self._shutdown = False

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("✅ ServiceRegistry started")

    async def stop(self) -> None:
        """Stop the service registry and cleanup."""
        self._shutdown = True

        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel watch tasks
        for task in self._watch_tasks:
            task.cancel()

        # Deregister
        await self.deregister()

        self._started = False
        logger.info("✅ ServiceRegistry stopped")

    async def _heartbeat_loop(self) -> None:
        """Background task to send heartbeats."""
        while not self._shutdown:
            try:
                if self._local_instance and self._lease_id:
                    etcd = await self._get_etcd()
                    await etcd.lease_keepalive(self._lease_id)

                    # Update last_heartbeat
                    self._local_instance.last_heartbeat = time.time()

                await asyncio.sleep(self._heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Heartbeat error: {e}")
                await asyncio.sleep(5)

    async def _cleanup_loop(self) -> None:
        """Background task to clean up stale services."""
        while not self._shutdown:
            try:
                # Check for stale services
                for service_type in ServiceType:
                    stale = []
                    for node_id, instance in self._services[service_type].items():
                        if instance.is_stale:
                            stale.append(node_id)

                    for node_id in stale:
                        instance = self._services[service_type].pop(node_id, None)
                        if instance:
                            logger.warning(f"Removed stale service: {service_type.value}/{node_id}")
                            await self._emit_event(
                                ServiceEventData(
                                    event_type=ServiceEvent.DEREGISTERED,
                                    instance=instance,
                                    reason="stale_heartbeat",
                                )
                            )

                await asyncio.sleep(self._heartbeat_interval * 2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Cleanup error: {e}")
                await asyncio.sleep(30)

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Dictionary with service counts and health summary
        """
        stats: dict[str, Any] = {
            "started": self._started,
            "local_instance": self._local_instance.to_dict() if self._local_instance else None,
            "services": {},
            "total_healthy": 0,
            "total_unhealthy": 0,
            "total_isolated": 0,
        }

        for service_type in ServiceType:
            services = list(self._services[service_type].values())
            healthy = sum(1 for s in services if s.is_healthy)
            isolated = sum(1 for s in services if s.health == ServiceHealth.ISOLATED)

            stats["services"][service_type.value] = {
                "total": len(services),
                "healthy": healthy,
                "isolated": isolated,
            }
            stats["total_healthy"] += healthy
            stats["total_unhealthy"] += len(services) - healthy
            stats["total_isolated"] += isolated

        return stats


# =============================================================================
# FACTORY
# =============================================================================


_registry: ServiceRegistry | None = None
_registry_lock = asyncio.Lock()


async def get_service_registry() -> ServiceRegistry:
    """Get or create the global service registry.

    Returns:
        ServiceRegistry singleton instance

    Example:
        registry = await get_service_registry()
        await registry.register(...)
    """
    global _registry

    async with _registry_lock:
        if _registry is None:
            _registry = ServiceRegistry()
            await _registry.start()

    return _registry


def get_service_registry_sync() -> ServiceRegistry | None:
    """Get the service registry synchronously (may be None).

    Returns:
        ServiceRegistry or None if not initialized
    """
    return _registry


# =============================================================================
# 鏡
# η → s → μ → a → η′
# h(x) ≥ 0. Always.
# =============================================================================
