"""Unified Cluster Management — Automatic optimal clustering across all infrastructure.

Brings together etcd, Redis, CockroachDB, and API with:
- Automatic service discovery
- Health monitoring and failover
- Load balancing
- Configuration synchronization
- Distributed state management

Architecture:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          UNIFIED CLUSTER MANAGER                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌───────────┐ │
│  │     etcd       │  │     Redis      │  │   CockroachDB  │  │    API    │ │
│  │  (Consensus)   │  │   (Caching)    │  │  (Persistence) │  │ (Gateway) │ │
│  ├────────────────┤  ├────────────────┤  ├────────────────┤  ├───────────┤ │
│  │ • Leader elect │  │ • Job queues   │  │ • Transactions │  │ • Routes  │ │
│  │ • Config sync  │  │ • Result cache │  │ • Migrations   │  │ • WebSock │ │
│  │ • Service disc │  │ • Pub/Sub      │  │ • Backups      │  │ • Health  │ │
│  │ • Dist locks   │  │ • Sessions     │  │ • Replication  │  │ • Metrics │ │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘  └─────┬─────┘ │
│          │                   │                   │                 │        │
│          └───────────────────┴───────────────────┴─────────────────┘        │
│                                     │                                        │
│                          ┌──────────┴──────────┐                            │
│                          │   Cluster Events    │                            │
│                          │  (Watch + Publish)  │                            │
│                          └─────────────────────┘                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

Usage:
    from kagami.core.cluster import get_cluster_manager

    cluster = await get_cluster_manager()

    # All services auto-connect and coordinate
    await cluster.wait_healthy()

    # Access any service
    redis = cluster.redis
    db = cluster.database
    etcd = cluster.etcd

    # Cluster operations
    await cluster.acquire_lock("my-resource")
    await cluster.publish_event("resource.updated", {"id": 123})

Created: January 1, 2026
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class ClusterRole(str, Enum):
    """Node role in cluster."""

    PRIMARY = "primary"  # Leader node
    SECONDARY = "secondary"  # Follower node
    STANDBY = "standby"  # Hot standby
    OBSERVER = "observer"  # Read-only observer


class ServiceHealth(str, Enum):
    """Service health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ClusterNode:
    """Information about a cluster node.

    Attributes:
        node_id: Unique node identifier
        hostname: Node hostname
        address: Network address
        port: Service port
        role: Node role in cluster
        capabilities: List of capabilities
        last_heartbeat: Last heartbeat timestamp
        health: Current health status
        metadata: Additional metadata
    """

    node_id: str
    hostname: str
    address: str
    port: int
    role: ClusterRole = ClusterRole.SECONDARY
    capabilities: list[str] = field(default_factory=list)
    last_heartbeat: float = field(default_factory=time.time)
    health: ServiceHealth = ServiceHealth.UNKNOWN
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "address": self.address,
            "port": self.port,
            "role": self.role.value,
            "capabilities": self.capabilities,
            "last_heartbeat": self.last_heartbeat,
            "health": self.health.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClusterNode:
        """Deserialize from dictionary."""
        return cls(
            node_id=data["node_id"],
            hostname=data["hostname"],
            address=data["address"],
            port=data["port"],
            role=ClusterRole(data.get("role", "secondary")),
            capabilities=data.get("capabilities", []),
            last_heartbeat=data.get("last_heartbeat", time.time()),
            health=ServiceHealth(data.get("health", "unknown")),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ClusterConfig:
    """Cluster configuration with auto-discovery.

    All settings can be overridden via environment variables.
    """

    # Cluster identity
    cluster_name: str = "kagami"
    node_id: str = ""

    # etcd (Consensus)
    etcd_endpoints: list[str] = field(default_factory=list)
    etcd_timeout: float = 5.0
    etcd_prefix: str = "/kagami"

    # Redis (Caching)
    redis_url: str = ""
    redis_cluster_mode: bool = False
    redis_sentinel_master: str = ""
    redis_sentinels: list[str] = field(default_factory=list)

    # CockroachDB (Persistence)
    database_url: str = ""
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # API
    api_port: int = 8000
    api_workers: int = 4

    # Health & Coordination
    heartbeat_interval: float = 10.0
    health_check_interval: float = 30.0
    leader_lease_ttl: int = 30
    stale_node_timeout: float = 60.0

    # Feature flags
    auto_failover: bool = True
    auto_rebalance: bool = True
    auto_scale: bool = False

    def __post_init__(self) -> None:
        """Load from environment."""
        # Node identity
        if not self.node_id:
            self.node_id = os.environ.get("KAGAMI_NODE_ID", f"{socket.gethostname()}-{os.getpid()}")

        self.cluster_name = os.environ.get("KAGAMI_CLUSTER_NAME", self.cluster_name)

        # etcd
        etcd_endpoints = os.environ.get("ETCD_ENDPOINTS", "")
        if etcd_endpoints:
            self.etcd_endpoints = [e.strip() for e in etcd_endpoints.split(",")]
        if not self.etcd_endpoints:
            self.etcd_endpoints = [os.environ.get("ETCD_ENDPOINT", "http://localhost:2379")]

        self.etcd_timeout = float(os.environ.get("ETCD_TIMEOUT", str(self.etcd_timeout)))
        self.etcd_prefix = os.environ.get("ETCD_PREFIX", self.etcd_prefix)

        # Redis
        self.redis_url = os.environ.get("REDIS_URL", self.redis_url or "redis://localhost:6379")
        self.redis_cluster_mode = os.environ.get("REDIS_CLUSTER_MODE", "").lower() == "true"

        # Sentinel
        sentinel_master = os.environ.get("REDIS_SENTINEL_MASTER", "")
        if sentinel_master:
            self.redis_sentinel_master = sentinel_master
            sentinels = os.environ.get("REDIS_SENTINELS", "")
            if sentinels:
                self.redis_sentinels = [s.strip() for s in sentinels.split(",")]

        # Database
        self.database_url = os.environ.get(
            "DATABASE_URL", os.environ.get("COCKROACH_URL", self.database_url or "")
        )
        self.database_pool_size = int(os.environ.get("DB_POOL_SIZE", str(self.database_pool_size)))

        # API
        self.api_port = int(os.environ.get("API_PORT", str(self.api_port)))
        self.api_workers = int(os.environ.get("API_WORKERS", str(self.api_workers)))

        # Features
        self.auto_failover = os.environ.get("CLUSTER_AUTO_FAILOVER", "true").lower() == "true"
        self.auto_rebalance = os.environ.get("CLUSTER_AUTO_REBALANCE", "true").lower() == "true"
        self.auto_scale = os.environ.get("CLUSTER_AUTO_SCALE", "false").lower() == "true"


# =============================================================================
# Service Wrappers
# =============================================================================


class EtcdService:
    """etcd service wrapper with cluster awareness."""

    def __init__(self, config: ClusterConfig):
        self.config = config
        self._client: Any = None
        self._healthy = False

    async def connect(self) -> None:
        """Connect to etcd cluster."""
        try:
            from kagami.core.consensus.etcd_client import get_etcd_client

            self._client = get_etcd_client()
            if self._client:
                self._healthy = True
                logger.info(f"✅ Connected to etcd: {self.config.etcd_endpoints}")
            else:
                logger.warning("etcd client unavailable (optional)")
        except Exception as e:
            logger.warning(f"etcd connection failed (optional): {e}")
            self._healthy = False

    async def disconnect(self) -> None:
        """Disconnect from etcd."""
        if self._client:
            try:
                from kagami.core.consensus.etcd_client import close_etcd_client

                close_etcd_client()
            except Exception as e:
                logger.debug(f"Error closing etcd: {e}")
        self._client = None
        self._healthy = False

    async def put(self, key: str, value: Any) -> bool:
        """Put value in etcd."""
        if not self._client:
            return False
        try:
            full_key = f"{self.config.etcd_prefix}/{key}"
            data = json.dumps(value) if not isinstance(value, str) else value
            self._client.put(full_key, data)
            return True
        except Exception as e:
            logger.error(f"etcd put failed: {e}")
            return False

    async def get(self, key: str) -> Any | None:
        """Get value from etcd."""
        if not self._client:
            return None
        try:
            full_key = f"{self.config.etcd_prefix}/{key}"
            value, _ = self._client.get(full_key)
            if value:
                try:
                    return json.loads(value.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return value.decode()
            return None
        except Exception as e:
            logger.error(f"etcd get failed: {e}")
            return None

    async def delete(self, key: str) -> bool:
        """Delete key from etcd."""
        if not self._client:
            return False
        try:
            full_key = f"{self.config.etcd_prefix}/{key}"
            self._client.delete(full_key)
            return True
        except Exception as e:
            logger.error(f"etcd delete failed: {e}")
            return False

    async def acquire_leader(self, role: str, ttl: int = 30) -> tuple[bool, int | None]:
        """Attempt to become leader."""
        if not self._client:
            return (True, None)  # Standalone mode
        try:
            from kagami.core.consensus.etcd_client import acquire_leader

            return await acquire_leader(role, self.config.node_id, ttl)
        except Exception as e:
            logger.error(f"Leader election failed: {e}")
            return (False, None)

    @property
    def healthy(self) -> bool:
        """Check if service is healthy."""
        return self._healthy

    @property
    def client(self) -> Any:
        """Get raw client."""
        return self._client


class RedisService:
    """Redis service wrapper with cluster/sentinel support."""

    def __init__(self, config: ClusterConfig):
        self.config = config
        self._client: Any = None
        self._healthy = False

    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            import redis.asyncio as aioredis

            # Sentinel mode
            if self.config.redis_sentinel_master and self.config.redis_sentinels:
                from redis.asyncio.sentinel import Sentinel

                sentinels = []
                for s in self.config.redis_sentinels:
                    host, port = s.split(":")
                    sentinels.append((host, int(port)))

                sentinel = Sentinel(sentinels)
                self._client = sentinel.master_for(
                    self.config.redis_sentinel_master,
                    decode_responses=True,
                )
                logger.info(f"✅ Connected to Redis Sentinel: {self.config.redis_sentinel_master}")

            # Cluster mode
            elif self.config.redis_cluster_mode:
                from redis.asyncio.cluster import RedisCluster

                self._client = RedisCluster.from_url(
                    self.config.redis_url,
                    decode_responses=True,
                )
                logger.info(f"✅ Connected to Redis Cluster: {self.config.redis_url}")

            # Standard mode
            else:
                self._client = aioredis.from_url(
                    self.config.redis_url,
                    decode_responses=True,
                )
                logger.info(f"✅ Connected to Redis: {self.config.redis_url}")

            # Test connection
            await self._client.ping()
            self._healthy = True

        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self._healthy = False

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            try:
                await self._client.close()
            except Exception as e:
                logger.debug(f"Error closing Redis: {e}")
        self._client = None
        self._healthy = False

    @property
    def healthy(self) -> bool:
        """Check if service is healthy."""
        return self._healthy

    @property
    def client(self) -> Any:
        """Get raw client."""
        return self._client


class DatabaseService:
    """Database service wrapper with connection pooling."""

    def __init__(self, config: ClusterConfig):
        self.config = config
        self._engine: Any = None
        self._session_factory: Any = None
        self._healthy = False

    async def connect(self) -> None:
        """Connect to database."""
        if not self.config.database_url:
            logger.warning("No database URL configured")
            return

        try:
            from kagami.core.database.optimized_pool import get_optimized_pool

            pool = await get_optimized_pool(self.config.database_url)
            self._engine = pool.engine
            self._healthy = True

            logger.info("✅ Connected to database with optimized pool")

        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            self._healthy = False

    async def disconnect(self) -> None:
        """Disconnect from database."""
        if self._engine:
            try:
                self._engine.dispose()
            except Exception as e:
                logger.debug(f"Error closing database: {e}")
        self._engine = None
        self._session_factory = None
        self._healthy = False

    @property
    def healthy(self) -> bool:
        """Check if service is healthy."""
        return self._healthy

    @property
    def engine(self) -> Any:
        """Get database engine."""
        return self._engine


# =============================================================================
# Unified Cluster Manager
# =============================================================================


class UnifiedClusterManager:
    """Unified cluster manager coordinating all services.

    Features:
    - Automatic service discovery and connection
    - Unified health monitoring
    - Leader election across all services
    - Distributed locking
    - Event pub/sub
    - Configuration synchronization
    - Automatic failover

    Usage:
        cluster = UnifiedClusterManager()
        await cluster.start()

        # Use services
        await cluster.redis.client.set("key", "value")
        await cluster.acquire_lock("resource")
        await cluster.publish("event", {"data": 123})

        await cluster.stop()
    """

    def __init__(self, config: ClusterConfig | None = None):
        self.config = config or ClusterConfig()

        # Services
        self.etcd = EtcdService(self.config)
        self.redis = RedisService(self.config)
        self.database = DatabaseService(self.config)

        # Cluster state
        self._node = ClusterNode(
            node_id=self.config.node_id,
            hostname=socket.gethostname(),
            address=self._get_local_ip(),
            port=self.config.api_port,
        )
        self._nodes: dict[str, ClusterNode] = {}
        self._is_leader = False
        self._leader_lease_id: int | None = None

        # Background tasks
        self._heartbeat_task: asyncio.Task | None = None
        self._discovery_task: asyncio.Task | None = None
        self._health_task: asyncio.Task | None = None

        # State
        self._started = False
        self._shutdown = False

        # Event callbacks
        self._event_handlers: dict[str, list[Callable]] = {}

    def _get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    async def start(self) -> None:
        """Start cluster manager and all services."""
        if self._started:
            return

        logger.info(f"🚀 Starting cluster manager: {self.config.cluster_name}")
        logger.info(f"   Node: {self.config.node_id}")

        # Connect all services in parallel
        await asyncio.gather(
            self.etcd.connect(),
            self.redis.connect(),
            self.database.connect(),
            return_exceptions=True,
        )

        # Attempt leader election
        await self._elect_leader()

        # Start background tasks
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._discovery_task = asyncio.create_task(self._discovery_loop())
        self._health_task = asyncio.create_task(self._health_loop())

        self._started = True

        # Log status
        status = []
        if self.etcd.healthy:
            status.append("etcd")
        if self.redis.healthy:
            status.append("redis")
        if self.database.healthy:
            status.append("database")

        role = "LEADER" if self._is_leader else "FOLLOWER"
        logger.info(f"✅ Cluster manager started ({role}): {', '.join(status)}")

    async def stop(self) -> None:
        """Stop cluster manager and all services."""
        if not self._started:
            return

        self._shutdown = True
        logger.info("🛑 Stopping cluster manager...")

        # Cancel background tasks
        for task in [self._heartbeat_task, self._discovery_task, self._health_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Unregister from cluster
        await self._unregister_node()

        # Disconnect all services
        await asyncio.gather(
            self.etcd.disconnect(),
            self.redis.disconnect(),
            self.database.disconnect(),
            return_exceptions=True,
        )

        self._started = False
        logger.info("✅ Cluster manager stopped")

    async def _elect_leader(self) -> None:
        """Attempt to become cluster leader."""
        success, lease_id = await self.etcd.acquire_leader(
            f"{self.config.cluster_name}:leader",
            self.config.leader_lease_ttl,
        )

        self._is_leader = success
        self._leader_lease_id = lease_id
        self._node.role = ClusterRole.PRIMARY if success else ClusterRole.SECONDARY

        if success:
            logger.info(f"🎖️ This node is cluster leader: {self.config.node_id}")
        else:
            logger.info(f"This node is cluster follower: {self.config.node_id}")

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat to register node."""
        while not self._shutdown:
            try:
                await self._register_node()
                await asyncio.sleep(self.config.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(5)

    async def _discovery_loop(self) -> None:
        """Discover other cluster nodes."""
        while not self._shutdown:
            try:
                await self._discover_nodes()
                await asyncio.sleep(self.config.heartbeat_interval * 2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Discovery error: {e}")
                await asyncio.sleep(10)

    async def _health_loop(self) -> None:
        """Monitor service health."""
        while not self._shutdown:
            try:
                await self._check_health()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(30)

    async def _register_node(self) -> None:
        """Register this node in cluster."""
        self._node.last_heartbeat = time.time()
        self._node.health = await self._get_node_health()

        # Register in etcd
        if self.etcd.healthy:
            key = f"nodes/{self.config.node_id}"
            await self.etcd.put(key, self._node.to_dict())

        # Register in Redis (fallback/faster access)
        if self.redis.healthy:
            key = f"kagami:cluster:node:{self.config.node_id}"
            await self.redis.client.setex(
                key,
                int(self.config.heartbeat_interval * 3),
                json.dumps(self._node.to_dict()),
            )

    async def _unregister_node(self) -> None:
        """Unregister this node from cluster."""
        # Remove from etcd
        if self.etcd.healthy:
            await self.etcd.delete(f"nodes/{self.config.node_id}")

        # Remove from Redis
        if self.redis.healthy:
            await self.redis.client.delete(f"kagami:cluster:node:{self.config.node_id}")

    async def _discover_nodes(self) -> None:
        """Discover other cluster nodes."""
        nodes: dict[str, ClusterNode] = {}

        # Discover from Redis (faster)
        if self.redis.healthy:
            pattern = "kagami:cluster:node:*"
            cursor = 0

            while True:
                cursor, keys = await self.redis.client.scan(cursor, match=pattern, count=100)

                for key in keys:
                    data = await self.redis.client.get(key)
                    if data:
                        try:
                            node = ClusterNode.from_dict(json.loads(data))

                            # Check if node is fresh
                            if time.time() - node.last_heartbeat < self.config.stale_node_timeout:
                                nodes[node.node_id] = node
                        except Exception as e:
                            logger.debug(f"Error parsing node: {e}")

                if cursor == 0:
                    break

        self._nodes = nodes

    async def _check_health(self) -> None:
        """Check health of all services."""
        # Update node health
        self._node.health = await self._get_node_health()

        # Emit health event
        await self._emit_event(
            "health.check",
            {
                "node_id": self.config.node_id,
                "health": self._node.health.value,
                "etcd": self.etcd.healthy,
                "redis": self.redis.healthy,
                "database": self.database.healthy,
            },
        )

    async def _get_node_health(self) -> ServiceHealth:
        """Calculate overall node health."""
        healthy_count = sum(
            [
                self.redis.healthy,  # Redis is critical
                self.database.healthy,  # Database is critical
            ]
        )

        if healthy_count == 2:
            return ServiceHealth.HEALTHY
        elif healthy_count == 1:
            return ServiceHealth.DEGRADED
        else:
            return ServiceHealth.UNHEALTHY

    # =========================================================================
    # Public API
    # =========================================================================

    @property
    def is_leader(self) -> bool:
        """Check if this node is cluster leader."""
        return self._is_leader

    @property
    def node_id(self) -> str:
        """Get this node's ID."""
        return self.config.node_id

    @property
    def nodes(self) -> dict[str, ClusterNode]:
        """Get all known cluster nodes."""
        return self._nodes.copy()

    @property
    def healthy(self) -> bool:
        """Check if cluster is healthy."""
        return self._node.health in (ServiceHealth.HEALTHY, ServiceHealth.DEGRADED)

    async def wait_healthy(self, timeout: float = 30.0) -> bool:
        """Wait for cluster to become healthy."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.healthy:
                return True
            await asyncio.sleep(1)

        return False

    async def acquire_lock(
        self,
        resource: str,
        ttl: int = 30,
        timeout: float = 10.0,
    ) -> bool:
        """Acquire distributed lock."""
        try:
            from kagami.core.consensus.distributed_lock import distributed_lock

            async with distributed_lock(resource, ttl=ttl, timeout=timeout):
                return True

        except Exception as e:
            logger.error(f"Failed to acquire lock '{resource}': {e}")
            return False

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish event to cluster."""
        event = {
            "type": event_type,
            "node_id": self.config.node_id,
            "timestamp": time.time(),
            "data": data,
        }

        # Publish via Redis pub/sub
        if self.redis.healthy:
            channel = f"kagami:cluster:events:{event_type}"
            await self.redis.client.publish(channel, json.dumps(event))

        # Also store in etcd for durability
        if self.etcd.healthy:
            key = f"events/{event_type}/{int(time.time() * 1000)}"
            await self.etcd.put(key, event)

    def on_event(self, event_type: str, handler: Callable) -> None:
        """Register event handler."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit event to local handlers."""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    async def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value from cluster."""
        # Try etcd first (authoritative)
        if self.etcd.healthy:
            value = await self.etcd.get(f"config/{key}")
            if value is not None:
                return value

        # Try Redis (cache)
        if self.redis.healthy:
            value = await self.redis.client.get(f"kagami:config:{key}")
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value

        return default

    async def set_config(self, key: str, value: Any) -> bool:
        """Set configuration value in cluster."""
        success = True

        # Store in etcd (authoritative)
        if self.etcd.healthy:
            success = await self.etcd.put(f"config/{key}", value) and success

        # Cache in Redis
        if self.redis.healthy:
            data = json.dumps(value) if not isinstance(value, str) else value
            await self.redis.client.set(f"kagami:config:{key}", data)

        return success

    async def get_stats(self) -> dict[str, Any]:
        """Get cluster statistics."""
        return {
            "cluster_name": self.config.cluster_name,
            "node_id": self.config.node_id,
            "is_leader": self._is_leader,
            "node_count": len(self._nodes),
            "health": self._node.health.value,
            "services": {
                "etcd": self.etcd.healthy,
                "redis": self.redis.healthy,
                "database": self.database.healthy,
            },
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "uptime_seconds": time.time() - self._node.last_heartbeat,
        }


# =============================================================================
# Factory
# =============================================================================


_cluster_manager: UnifiedClusterManager | None = None


async def get_cluster_manager(config: ClusterConfig | None = None) -> UnifiedClusterManager:
    """Get or create the global cluster manager."""
    global _cluster_manager

    if _cluster_manager is None:
        _cluster_manager = UnifiedClusterManager(config)
        await _cluster_manager.start()

    return _cluster_manager


async def shutdown_cluster() -> None:
    """Shutdown the global cluster manager."""
    global _cluster_manager

    if _cluster_manager:
        await _cluster_manager.stop()
        _cluster_manager = None


__all__ = [
    "ClusterConfig",
    "ClusterNode",
    "ClusterRole",
    "DatabaseService",
    "EtcdService",
    "RedisService",
    "ServiceHealth",
    "UnifiedClusterManager",
    "get_cluster_manager",
    "shutdown_cluster",
]
