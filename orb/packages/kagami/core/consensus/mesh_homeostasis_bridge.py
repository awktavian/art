"""Mesh-Homeostasis Bridge — Connect colony homeostasis to distributed hub mesh.

This module bridges the Python-side homeostasis system with the Rust hub mesh
network, enabling distributed homeostasis across physical locations.

Architecture:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MESH-HOMEOSTASIS BRIDGE                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Python API (etcd-based)              Rust Hubs (mesh-based)           │
│   ───────────────────────              ─────────────────────            │
│   EtcdHomeostasisSync                  MeshCoordinator                  │
│   ├── InstanceState                    ├── CRDTState                    │
│   ├── GlobalHomeostasisState           ├── VectorClock                  │
│   ├── ConsensusQuality                 ├── LeaderElection               │
│   └── HomeostasisAdjustments           └── StateSyncProtocol            │
│                                                                          │
│   ┌─────────────────────┐   REST API   ┌─────────────────────┐          │
│   │ MeshHomeostasisBridge│◄───────────►│     Hub Mesh        │          │
│   │   (this module)     │  /api/hub/   │   (mesh_network.rs) │          │
│   └─────────────────────┘  homeostasis └─────────────────────┘          │
│                                                                          │
│   Bridge Functions:                                                     │
│   1. push_to_mesh(): Send homeostasis state to hub mesh                │
│   2. pull_from_mesh(): Get merged state from all hubs                  │
│   3. sync_bidirectional(): Full bidirectional sync                     │
│   4. watch_mesh_changes(): Subscribe to mesh state changes             │
│                                                                          │
│   Data Flow:                                                            │
│   • API pushes InstanceState → Bridge converts → Hub receives CRDTState │
│   • Hub pushes CRDTState → Bridge converts → API merges to GlobalState │
│   • Changes propagate automatically through vector clocks               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

Colony: Nexus (e₄) — Bridge across distributed systems
h(x) ≥ 0. Always.

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import aiohttp

from kagami.core.cluster.service_registry import (
    ServiceRegistry,
    ServiceType,
    get_service_registry,
)
from kagami.core.consensus.homeostasis_sync import (
    EtcdHomeostasisSync,
    GlobalHomeostasisState,
    HomeostasisAdjustments,
    InstanceState,
)
from kagami.core.coordination.cross_hub_crdt import (
    CrossHubCRDTManager,
    CrossHubCRDTState,
    LWWRegister,
    get_cross_hub_crdt_manager,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class MeshBridgeConfig:
    """Configuration for the mesh-homeostasis bridge.

    Attributes:
        sync_interval: Interval between bidirectional syncs (seconds).
        push_timeout: HTTP timeout for pushing state to hubs (seconds).
        pull_timeout: HTTP timeout for pulling state from hubs (seconds).
        retry_attempts: Number of retry attempts on failure.
        retry_delay: Delay between retries (seconds).
        hub_api_port: Port for hub API endpoints.
    """

    sync_interval: float = 10.0
    push_timeout: float = 5.0
    pull_timeout: float = 5.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    hub_api_port: int = 8080


# =============================================================================
# Conversion Functions
# =============================================================================


def instance_state_to_crdt(instance: InstanceState, node_id: str) -> CrossHubCRDTState:
    """Convert InstanceState to CrossHubCRDTState.

    Maps Python homeostasis state to CRDT format compatible with Rust hubs.

    Args:
        instance: Python InstanceState.
        node_id: Node identifier for CRDT operations.

    Returns:
        CrossHubCRDTState compatible with hub mesh.
    """
    crdt = CrossHubCRDTState(source_hub=node_id)

    # Set presence from vitals and population
    presence_data = {
        "instance_id": instance.instance_id,
        "population": instance.population,
        "vitals": instance.vitals,
        "pheromones": instance.pheromones,
        "catastrophe_risk": instance.catastrophe_risk,
        "e8_code": instance.e8_code,
        "s7_phase": instance.s7_phase,
    }
    crdt.presence = LWWRegister(
        value=presence_data,
        timestamp=instance.timestamp or time.time(),
        writer=node_id,
    )

    # Update vector clock
    crdt.clock.increment(node_id)
    crdt.timestamp = time.time()

    return crdt


def crdt_to_instance_state(crdt: CrossHubCRDTState) -> InstanceState:
    """Convert CrossHubCRDTState to InstanceState.

    Maps hub CRDT state back to Python homeostasis format.

    Args:
        crdt: CrossHubCRDTState from hub.

    Returns:
        InstanceState for Python homeostasis.
    """
    presence = crdt.presence.value if crdt.presence else {}

    return InstanceState(
        instance_id=presence.get("instance_id", crdt.source_hub),
        population=presence.get("population", {}),
        vitals=presence.get("vitals", {}),
        pheromones=presence.get("pheromones", {}),
        catastrophe_risk=presence.get("catastrophe_risk", {}),
        e8_code=presence.get("e8_code", []),
        s7_phase=presence.get("s7_phase", []),
        timestamp=crdt.timestamp,
    )


# =============================================================================
# Mesh-Homeostasis Bridge
# =============================================================================


class MeshHomeostasisBridge:
    """Bridge between Python homeostasis and Rust hub mesh.

    Responsibilities:
    - Bidirectional state synchronization
    - Format conversion between systems
    - Hub discovery and health monitoring
    - Conflict resolution via CRDT semantics

    Example:
        >>> bridge = MeshHomeostasisBridge(homeostasis_sync, config)
        >>> await bridge.initialize()
        >>> await bridge.start_sync_loop()
    """

    def __init__(
        self,
        homeostasis_sync: EtcdHomeostasisSync,
        config: MeshBridgeConfig | None = None,
    ) -> None:
        """Initialize the bridge.

        Args:
            homeostasis_sync: Python-side homeostasis synchronization.
            config: Bridge configuration.
        """
        self.homeostasis = homeostasis_sync
        self.config = config or MeshBridgeConfig()

        self._crdt_manager: CrossHubCRDTManager | None = None
        self._service_registry: ServiceRegistry | None = None
        self._http_session: aiohttp.ClientSession | None = None

        self._sync_task: asyncio.Task | None = None
        self._running = False
        self._initialized = False

        # Metrics
        self._sync_count = 0
        self._push_count = 0
        self._pull_count = 0
        self._error_count = 0
        self._last_sync_time: float | None = None

        logger.debug(f"MeshHomeostasisBridge created (instance: {homeostasis_sync.instance_id})")

    async def initialize(self) -> None:
        """Initialize the bridge and connect to mesh.

        This must be called before starting the sync loop.
        """
        if self._initialized:
            return

        logger.info("Initializing MeshHomeostasisBridge...")

        # Get CRDT manager
        self._crdt_manager = await get_cross_hub_crdt_manager(self.homeostasis.instance_id)

        # Get service registry for hub discovery
        try:
            self._service_registry = get_service_registry()
            await self._service_registry.initialize()
        except Exception as e:
            logger.warning(f"Service registry unavailable: {e}")
            self._service_registry = None

        # Create HTTP session for hub communication
        self._http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.push_timeout)
        )

        self._initialized = True
        logger.info("✅ MeshHomeostasisBridge initialized")

    async def shutdown(self) -> None:
        """Shutdown the bridge and cleanup resources."""
        logger.info("Shutting down MeshHomeostasisBridge...")

        self._running = False

        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        if self._http_session:
            await self._http_session.close()
            self._http_session = None

        self._initialized = False
        logger.info("🛑 MeshHomeostasisBridge shutdown")

    async def start_sync_loop(self) -> None:
        """Start the background synchronization loop.

        Runs bidirectional sync at configured interval.
        """
        if not self._initialized:
            await self.initialize()

        self._running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info(f"Started mesh homeostasis sync loop (interval: {self.config.sync_interval}s)")

    async def _sync_loop(self) -> None:
        """Background loop for bidirectional synchronization."""
        while self._running:
            try:
                await self.sync_bidirectional()
                self._sync_count += 1
                self._last_sync_time = time.time()
            except Exception as e:
                logger.error(f"Mesh sync error: {e}")
                self._error_count += 1

            await asyncio.sleep(self.config.sync_interval)

    async def sync_bidirectional(self) -> None:
        """Perform full bidirectional sync with hub mesh.

        1. Push local homeostasis state to CRDT manager
        2. Push CRDT state to known hubs
        3. Pull state from hubs
        4. Merge received state
        """
        if not self._initialized:
            logger.warning("Bridge not initialized, skipping sync")
            return

        # Step 1: Update CRDT from local homeostasis
        local_state = self.homeostasis._local_state
        if local_state:
            crdt_state = instance_state_to_crdt(local_state, self.homeostasis.instance_id)
            await self._crdt_manager.merge_hub_state(crdt_state)

        # Step 2: Push to known hubs
        await self.push_to_mesh()

        # Step 3: Pull from hubs
        await self.pull_from_mesh()

        logger.debug(
            f"Bidirectional sync complete (syncs: {self._sync_count}, errors: {self._error_count})"
        )

    async def push_to_mesh(self) -> int:
        """Push current CRDT state to all known hubs.

        Returns:
            Number of successful pushes.
        """
        if not self._crdt_manager:
            return 0

        state = self._crdt_manager.get_state()
        state_dict = state.to_dict()

        # Get hub addresses
        hubs = await self._get_hub_addresses()
        if not hubs:
            logger.debug("No hubs found for push")
            return 0

        success_count = 0
        for hub_address in hubs:
            try:
                url = f"http://{hub_address}/api/mesh/crdt-state"
                async with self._http_session.post(url, json=state_dict) as resp:
                    if resp.status == 200 or resp.status == 202:
                        success_count += 1
                        self._push_count += 1
                        logger.debug(f"Pushed state to hub {hub_address}")
                    else:
                        logger.warning(f"Hub {hub_address} rejected state: {resp.status}")
            except Exception as e:
                logger.debug(f"Failed to push to hub {hub_address}: {e}")

        return success_count

    async def pull_from_mesh(self) -> int:
        """Pull CRDT state from all known hubs.

        Returns:
            Number of successful pulls.
        """
        if not self._crdt_manager:
            return 0

        hubs = await self._get_hub_addresses()
        if not hubs:
            logger.debug("No hubs found for pull")
            return 0

        success_count = 0
        for hub_address in hubs:
            try:
                url = f"http://{hub_address}/api/mesh/crdt-state"
                async with self._http_session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        hub_state = CrossHubCRDTState.from_dict(data)
                        await self._crdt_manager.merge_hub_state(hub_state)
                        success_count += 1
                        self._pull_count += 1
                        logger.debug(f"Pulled state from hub {hub_address}")
            except Exception as e:
                logger.debug(f"Failed to pull from hub {hub_address}: {e}")

        return success_count

    async def _get_hub_addresses(self) -> list[str]:
        """Get addresses of known hubs.

        Returns:
            List of hub addresses (host:port format).
        """
        addresses = []

        # Try service registry first
        if self._service_registry:
            try:
                hubs = await self._service_registry.get_services(
                    service_type=ServiceType.HUB, status="healthy"
                )
                for hub in hubs:
                    addresses.append(f"{hub.address}:{self.config.hub_api_port}")
            except Exception as e:
                logger.debug(f"Service registry lookup failed: {e}")

        # Fallback: configure via KAGAMI_HUB_ADDRESSES env var if service registry unavailable
        return addresses

    def get_merged_global_state(self) -> GlobalHomeostasisState | None:
        """Get merged global homeostasis state from CRDT.

        Converts CRDT state to GlobalHomeostasisState format.

        Returns:
            Merged global state, or None if unavailable.
        """
        if not self._crdt_manager:
            return None

        state = self._crdt_manager.get_state()

        # Convert presence data to instance states
        instances: list[InstanceState] = []
        if state.presence and state.presence.value:
            instance = crdt_to_instance_state(state)
            instances.append(instance)

        if not instances:
            return None

        # Aggregate instance states
        global_population: dict[str, int] = {}
        pheromones: dict[str, float] = {}
        catastrophe_risk: dict[str, float] = {}
        total_population = 0

        for inst in instances:
            for colony, pop in inst.population.items():
                global_population[colony] = global_population.get(colony, 0) + pop
                total_population += pop

            for colony, pheromone in inst.pheromones.items():
                pheromones[colony] = max(pheromones.get(colony, 0.0), pheromone)

            for colony, risk in inst.catastrophe_risk.items():
                catastrophe_risk[colony] = max(catastrophe_risk.get(colony, 0.0), risk)

        return GlobalHomeostasisState(
            global_population=global_population,
            pheromones=pheromones,
            catastrophe_risk=catastrophe_risk,
            instance_count=len(instances),
            total_population=total_population,
            last_sync=time.time(),
        )

    def compute_mesh_adjustments(
        self, global_state: GlobalHomeostasisState | None = None
    ) -> HomeostasisAdjustments:
        """Compute homeostasis adjustments based on mesh state.

        Uses CRDT-merged state to compute adjustments.

        Args:
            global_state: Optional global state to use.

        Returns:
            HomeostasisAdjustments for local homeostasis.
        """
        if global_state is None:
            global_state = self.get_merged_global_state()

        adjustments = HomeostasisAdjustments()

        if global_state is None:
            return adjustments

        # Adjust based on population
        if global_state.total_population < 50:
            adjustments.apoptosis_modifier = 0.5  # Less apoptosis
            adjustments.mitosis_modifier = 1.5  # More mitosis
        elif global_state.total_population > 200:
            adjustments.apoptosis_modifier = 1.5  # More apoptosis
            adjustments.mitosis_modifier = 0.5  # Less mitosis

        # Check for high catastrophe risk
        max_risk = max(global_state.catastrophe_risk.values(), default=0.0)
        if max_risk > 0.7:
            adjustments.tighten_cbf = True
            adjustments.emergency_signals.append(
                {
                    "type": "high_risk",
                    "risk": max_risk,
                }
            )

        return adjustments

    def get_status(self) -> dict[str, Any]:
        """Get bridge status.

        Returns:
            Status dictionary.
        """
        return {
            "initialized": self._initialized,
            "running": self._running,
            "sync_count": self._sync_count,
            "push_count": self._push_count,
            "pull_count": self._pull_count,
            "error_count": self._error_count,
            "last_sync_time": self._last_sync_time,
            "config": {
                "sync_interval": self.config.sync_interval,
                "hub_api_port": self.config.hub_api_port,
            },
        }


# =============================================================================
# Singleton Factory
# =============================================================================

_bridge: MeshHomeostasisBridge | None = None
_bridge_lock = asyncio.Lock()


async def get_mesh_homeostasis_bridge(
    homeostasis_sync: EtcdHomeostasisSync | None = None,
    config: MeshBridgeConfig | None = None,
) -> MeshHomeostasisBridge:
    """Get or create the global MeshHomeostasisBridge.

    Args:
        homeostasis_sync: EtcdHomeostasisSync instance (required for first call).
        config: Bridge configuration.

    Returns:
        MeshHomeostasisBridge singleton instance.
    """
    global _bridge

    async with _bridge_lock:
        if _bridge is None:
            if homeostasis_sync is None:
                raise ValueError("MeshHomeostasisBridge must be initialized with homeostasis_sync")
            _bridge = MeshHomeostasisBridge(homeostasis_sync, config)
            await _bridge.initialize()

    return _bridge


async def shutdown_mesh_homeostasis_bridge() -> None:
    """Shutdown the global MeshHomeostasisBridge."""
    global _bridge

    if _bridge:
        await _bridge.shutdown()
        _bridge = None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "MeshBridgeConfig",
    "MeshHomeostasisBridge",
    "crdt_to_instance_state",
    "get_mesh_homeostasis_bridge",
    "instance_state_to_crdt",
    "shutdown_mesh_homeostasis_bridge",
]


# =============================================================================
# 鏡
# Homeostasis flows. Mesh syncs. The organism breathes as one.
# h(x) ≥ 0. Always.
# =============================================================================
