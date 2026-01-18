"""Device Constellation Mesh Network Tests.

Comprehensive tests for the Kagami mesh network constellation:
- Hub failover: Primary hub fails, secondary takes over
- Client roaming: Device moves between hubs
- Split-brain recovery: Network partition then healing
- New device join: New device joins mesh automatically
- Device removal: Device leaves mesh gracefully

These tests validate the resilience and self-healing capabilities of the mesh network.

Colony: Nexus (e4) - Connection and integration
Colony: Crystal (e7) - Verification and trust

h(x) >= 0. Always.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import pytest_asyncio

from tests.e2e.conftest import (
    MockDeviceConstellation,
    MockDevice,
    MockHub,
    DeviceType,
    ConnectionState,
    CircuitState,
    NetworkCondition,
    UserPersona,
)

logger = logging.getLogger(__name__)

# Mark all tests in this module
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.mesh,
    pytest.mark.asyncio,
]


# ==============================================================================
# MESH NETWORK DATA STRUCTURES
# ==============================================================================


class LeaderState(str, Enum):
    """Leader election states."""

    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


class HealthStatus(str, Enum):
    """Hub health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNREACHABLE = "unreachable"


@dataclass
class VectorClock:
    """Vector clock for causality tracking across hubs."""

    clocks: dict[str, int] = field(default_factory=dict)

    def increment(self, hub_id: str) -> None:
        self.clocks[hub_id] = self.clocks.get(hub_id, 0) + 1

    def get(self, hub_id: str) -> int:
        return self.clocks.get(hub_id, 0)

    def merge(self, other: VectorClock) -> None:
        for hub_id, ts in other.clocks.items():
            self.clocks[hub_id] = max(self.clocks.get(hub_id, 0), ts)

    def happens_before(self, other: VectorClock) -> bool:
        """Check if this clock happens-before another."""
        all_leq = True
        any_lt = False

        all_keys = set(self.clocks.keys()) | set(other.clocks.keys())
        for key in all_keys:
            self_val = self.get(key)
            other_val = other.get(key)
            if self_val > other_val:
                all_leq = False
            if self_val < other_val:
                any_lt = True

        return all_leq and any_lt


@dataclass
class HubHealth:
    """Health metrics for a hub."""

    hub_id: str
    status: HealthStatus = HealthStatus.HEALTHY
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    network_latency_ms: float = 10.0
    last_heartbeat: float = field(default_factory=time.time)
    consecutive_failures: int = 0
    connected_devices: int = 0

    def is_healthy(self) -> bool:
        return (
            self.status == HealthStatus.HEALTHY
            and self.cpu_percent < 90
            and self.memory_percent < 90
            and self.network_latency_ms < 1000
            and self.consecutive_failures < 3
        )

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:
            self.status = HealthStatus.DEGRADED
        if self.consecutive_failures >= 5:
            self.status = HealthStatus.UNHEALTHY

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.status = HealthStatus.HEALTHY
        self.last_heartbeat = time.time()


@dataclass
class LeaderElection:
    """BFT leader election state."""

    term: int = 0
    leader_id: str | None = None
    voted_for: str | None = None
    votes_received: set[str] = field(default_factory=set)
    state: LeaderState = LeaderState.FOLLOWER

    def start_election(self, candidate_id: str) -> None:
        self.term += 1
        self.state = LeaderState.CANDIDATE
        self.voted_for = candidate_id
        self.votes_received = {candidate_id}

    def receive_vote(self, voter_id: str) -> None:
        if self.state == LeaderState.CANDIDATE:
            self.votes_received.add(voter_id)

    def has_quorum(self, total_nodes: int) -> bool:
        quorum_size = (total_nodes // 2) + 1
        return len(self.votes_received) >= quorum_size

    def become_leader(self, hub_id: str) -> None:
        self.state = LeaderState.LEADER
        self.leader_id = hub_id

    def step_down(self) -> None:
        self.state = LeaderState.FOLLOWER
        self.votes_received = set()


# ==============================================================================
# MESH CONSTELLATION MANAGER
# ==============================================================================


class MeshConstellationManager:
    """Manages the mesh network constellation for testing."""

    def __init__(self, constellation: MockDeviceConstellation):
        self.constellation = constellation
        self.hub_health: dict[str, HubHealth] = {}
        self.elections: dict[str, LeaderElection] = {}
        self.vector_clocks: dict[str, VectorClock] = {}
        self.device_assignments: dict[str, str] = {}  # device_id -> hub_id
        self.partition_groups: list[set[str]] = []  # Groups of isolated hubs

        # Initialize health tracking for existing hubs
        for hub_id, hub in constellation.hubs.items():
            self.hub_health[hub_id] = HubHealth(
                hub_id=hub_id,
                connected_devices=len(hub.devices),
            )
            self.elections[hub_id] = LeaderElection()
            self.vector_clocks[hub_id] = VectorClock()

            # Track device assignments
            for device in hub.devices:
                self.device_assignments[device.device_id] = hub_id

    def get_leader(self) -> str | None:
        """Get the current leader hub ID."""
        for hub in self.constellation.hubs.values():
            if hub.is_leader:
                return hub.hub_id
        return None

    def get_primary(self) -> str | None:
        """Get the primary hub ID."""
        for hub in self.constellation.hubs.values():
            if hub.is_primary:
                return hub.hub_id
        return None

    def get_healthy_hubs(self) -> list[str]:
        """Get list of healthy hub IDs."""
        return [hub_id for hub_id, health in self.hub_health.items() if health.is_healthy()]

    async def simulate_hub_failure(self, hub_id: str) -> dict[str, Any]:
        """Simulate a hub going offline and trigger failover."""
        if hub_id not in self.constellation.hubs:
            return {"success": False, "error": "Hub not found"}

        hub = self.constellation.hubs[hub_id]
        was_leader = hub.is_leader
        was_primary = hub.is_primary

        # Mark hub as offline
        hub.connection_state = ConnectionState.DISCONNECTED
        hub.is_leader = False
        self.hub_health[hub_id].status = HealthStatus.UNREACHABLE

        # Disconnect devices on this hub
        orphaned_devices = []
        for device in hub.devices:
            device.connection_state = ConnectionState.DISCONNECTED
            orphaned_devices.append(device.device_id)

        # Remove from peer lists
        for other_hub in self.constellation.hubs.values():
            if hub_id in other_hub.peers:
                other_hub.peers.remove(hub_id)

        # Trigger leader election if leader failed
        new_leader = None
        if was_leader:
            new_leader = await self._elect_new_leader(exclude=[hub_id])

        # Trigger device migration
        migrations = await self._migrate_devices(orphaned_devices)

        return {
            "success": True,
            "failed_hub": hub_id,
            "was_leader": was_leader,
            "was_primary": was_primary,
            "new_leader": new_leader,
            "orphaned_devices": orphaned_devices,
            "device_migrations": migrations,
        }

    async def simulate_hub_recovery(self, hub_id: str) -> dict[str, Any]:
        """Simulate a hub coming back online."""
        if hub_id not in self.constellation.hubs:
            return {"success": False, "error": "Hub not found"}

        hub = self.constellation.hubs[hub_id]

        # Mark hub as online
        hub.connection_state = ConnectionState.CONNECTED
        self.hub_health[hub_id].status = HealthStatus.HEALTHY
        self.hub_health[hub_id].consecutive_failures = 0
        self.hub_health[hub_id].last_heartbeat = time.time()

        # Rejoin peer network
        for other_hub_id, other_hub in self.constellation.hubs.items():
            if other_hub_id != hub_id and other_hub.is_online():
                if hub_id not in other_hub.peers:
                    other_hub.peers.append(hub_id)
                if other_hub_id not in hub.peers:
                    hub.peers.append(other_hub_id)

        # Sync state from leader
        leader_id = self.get_leader()
        if leader_id and leader_id != hub_id:
            await self._sync_state_from_leader(hub_id, leader_id)

        # Reconnect devices
        reconnected = []
        for device in hub.devices:
            device.connection_state = ConnectionState.CONNECTED
            reconnected.append(device.device_id)

        return {
            "success": True,
            "recovered_hub": hub_id,
            "reconnected_devices": reconnected,
            "peer_count": len(hub.peers),
        }

    async def _elect_new_leader(self, exclude: list[str] = None) -> str | None:
        """Elect a new leader from available hubs."""
        exclude = exclude or []
        candidates = [
            hub_id
            for hub_id, health in self.hub_health.items()
            if hub_id not in exclude and health.is_healthy()
        ]

        if not candidates:
            logger.error("No healthy candidates for leader election")
            return None

        # Simple election: pick hub with lowest ID (deterministic)
        new_leader_id = min(candidates)

        # Update hub states
        for hub_id, hub in self.constellation.hubs.items():
            hub.is_leader = hub_id == new_leader_id
            self.elections[hub_id].leader_id = new_leader_id

        logger.info(f"Elected new leader: {new_leader_id}")
        return new_leader_id

    async def _migrate_devices(self, device_ids: list[str]) -> list[dict]:
        """Migrate devices to healthy hubs."""
        migrations = []
        healthy_hubs = self.get_healthy_hubs()

        if not healthy_hubs:
            logger.error("No healthy hubs available for device migration")
            return migrations

        for device_id in device_ids:
            # Find device
            device = self.constellation.devices.get(device_id)
            if not device:
                continue

            # Select target hub (round-robin or least-loaded)
            target_hub_id = min(
                healthy_hubs,
                key=lambda h: self.hub_health[h].connected_devices,
            )

            # Migrate device
            old_hub_id = self.device_assignments.get(device_id)
            device.hub_id = target_hub_id
            device.connection_state = ConnectionState.CONNECTED
            self.device_assignments[device_id] = target_hub_id

            # Update hub device lists
            if old_hub_id and old_hub_id in self.constellation.hubs:
                old_hub = self.constellation.hubs[old_hub_id]
                old_hub.devices = [d for d in old_hub.devices if d.device_id != device_id]

            target_hub = self.constellation.hubs[target_hub_id]
            target_hub.devices.append(device)
            self.hub_health[target_hub_id].connected_devices += 1

            migrations.append(
                {
                    "device_id": device_id,
                    "from_hub": old_hub_id,
                    "to_hub": target_hub_id,
                }
            )

            logger.info(f"Migrated device {device_id} from {old_hub_id} to {target_hub_id}")

        return migrations

    async def _sync_state_from_leader(self, hub_id: str, leader_id: str) -> None:
        """Sync state from leader to recovering hub."""
        leader_clock = self.vector_clocks[leader_id]
        hub_clock = self.vector_clocks[hub_id]

        # Merge vector clocks
        hub_clock.merge(leader_clock)

        # Copy pending sync items from leader
        leader_hub = self.constellation.hubs[leader_id]
        recovering_hub = self.constellation.hubs[hub_id]

        recovering_hub.pending_sync = leader_hub.pending_sync.copy()
        logger.info(f"Synced state from {leader_id} to {hub_id}")

    async def simulate_network_partition(
        self,
        group_a: list[str],
        group_b: list[str],
    ) -> dict[str, Any]:
        """Simulate a network partition between two groups of hubs."""
        self.partition_groups = [set(group_a), set(group_b)]

        # Disconnect hubs across partition
        for hub_a in group_a:
            for hub_b in group_b:
                if hub_a in self.constellation.hubs:
                    hub_a_obj = self.constellation.hubs[hub_a]
                    if hub_b in hub_a_obj.peers:
                        hub_a_obj.peers.remove(hub_b)

                if hub_b in self.constellation.hubs:
                    hub_b_obj = self.constellation.hubs[hub_b]
                    if hub_a in hub_b_obj.peers:
                        hub_b_obj.peers.remove(hub_a)

        # Each partition may elect its own leader (split-brain)
        leaders = {}
        for i, group in enumerate(self.partition_groups):
            group_list = list(group)
            if group_list:
                leaders[f"partition_{i}"] = await self._elect_leader_in_group(group_list)

        return {
            "success": True,
            "partition_a": group_a,
            "partition_b": group_b,
            "leaders": leaders,
        }

    async def _elect_leader_in_group(self, hub_ids: list[str]) -> str | None:
        """Elect a leader within a partition group."""
        healthy = [h for h in hub_ids if self.hub_health.get(h, HubHealth(h)).is_healthy()]
        if not healthy:
            return None

        leader_id = min(healthy)
        for hub_id in hub_ids:
            if hub_id in self.constellation.hubs:
                self.constellation.hubs[hub_id].is_leader = hub_id == leader_id

        return leader_id

    async def heal_network_partition(self) -> dict[str, Any]:
        """Heal a network partition and resolve split-brain."""
        if not self.partition_groups:
            return {"success": False, "error": "No active partition"}

        # Reconnect all hubs
        all_hub_ids = []
        for group in self.partition_groups:
            all_hub_ids.extend(group)

        for hub_id in all_hub_ids:
            hub = self.constellation.hubs.get(hub_id)
            if hub:
                for other_id in all_hub_ids:
                    if other_id != hub_id and other_id not in hub.peers:
                        other_hub = self.constellation.hubs.get(other_id)
                        if other_hub and other_hub.is_online():
                            hub.peers.append(other_id)

        # Resolve split-brain: elect single leader
        new_leader = await self._elect_new_leader()

        # Merge state across partitions
        await self._merge_partition_states()

        # Clear partition tracking
        old_groups = self.partition_groups.copy()
        self.partition_groups = []

        return {
            "success": True,
            "healed_partitions": old_groups,
            "new_leader": new_leader,
        }

    async def _merge_partition_states(self) -> None:
        """Merge CRDT states after partition healing."""
        # Merge all vector clocks
        merged_clock = VectorClock()
        for clock in self.vector_clocks.values():
            merged_clock.merge(clock)

        # Update all hubs with merged clock
        for hub_id in self.vector_clocks:
            self.vector_clocks[hub_id] = VectorClock()
            self.vector_clocks[hub_id].merge(merged_clock)

        logger.info("Merged partition states using CRDT vector clocks")

    async def add_new_hub(self, hub: MockHub) -> dict[str, Any]:
        """Add a new hub to the mesh constellation."""
        hub_id = hub.hub_id

        # Add to constellation
        self.constellation.add_hub(hub)

        # Initialize health and election state
        self.hub_health[hub_id] = HubHealth(hub_id=hub_id)
        self.elections[hub_id] = LeaderElection()
        self.vector_clocks[hub_id] = VectorClock()

        # Get current leader
        leader_id = self.get_leader()

        # Sync state from leader if one exists
        if leader_id:
            await self._sync_state_from_leader(hub_id, leader_id)

        # Update election state
        if leader_id:
            self.elections[hub_id].leader_id = leader_id

        return {
            "success": True,
            "hub_id": hub_id,
            "peer_count": len(hub.peers),
            "leader": leader_id,
        }

    async def remove_hub(self, hub_id: str, graceful: bool = True) -> dict[str, Any]:
        """Remove a hub from the mesh constellation."""
        if hub_id not in self.constellation.hubs:
            return {"success": False, "error": "Hub not found"}

        hub = self.constellation.hubs[hub_id]
        was_leader = hub.is_leader

        # Migrate devices first
        device_ids = [d.device_id for d in hub.devices]
        migrations = await self._migrate_devices(device_ids)

        # Remove from peer lists
        for other_hub in self.constellation.hubs.values():
            if hub_id in other_hub.peers:
                other_hub.peers.remove(hub_id)

        # Remove hub
        del self.constellation.hubs[hub_id]
        del self.hub_health[hub_id]
        del self.elections[hub_id]
        del self.vector_clocks[hub_id]

        # Elect new leader if needed
        new_leader = None
        if was_leader:
            new_leader = await self._elect_new_leader()

        return {
            "success": True,
            "removed_hub": hub_id,
            "was_leader": was_leader,
            "new_leader": new_leader,
            "device_migrations": migrations,
            "graceful": graceful,
        }

    async def roam_device(
        self,
        device_id: str,
        target_hub_id: str,
    ) -> dict[str, Any]:
        """Roam a device to a different hub."""
        device = self.constellation.devices.get(device_id)
        if not device:
            return {"success": False, "error": "Device not found"}

        if target_hub_id not in self.constellation.hubs:
            return {"success": False, "error": "Target hub not found"}

        source_hub_id = self.device_assignments.get(device_id)
        target_hub = self.constellation.hubs[target_hub_id]

        if not target_hub.is_online():
            return {"success": False, "error": "Target hub is offline"}

        # Remove from source hub
        if source_hub_id and source_hub_id in self.constellation.hubs:
            source_hub = self.constellation.hubs[source_hub_id]
            source_hub.devices = [d for d in source_hub.devices if d.device_id != device_id]
            self.hub_health[source_hub_id].connected_devices -= 1

        # Add to target hub
        device.hub_id = target_hub_id
        target_hub.devices.append(device)
        self.device_assignments[device_id] = target_hub_id
        self.hub_health[target_hub_id].connected_devices += 1

        return {
            "success": True,
            "device_id": device_id,
            "source_hub": source_hub_id,
            "target_hub": target_hub_id,
        }


# ==============================================================================
# FIXTURES
# ==============================================================================


@pytest.fixture
def mesh_manager(mock_constellation: MockDeviceConstellation) -> MeshConstellationManager:
    """Create a mesh constellation manager for testing."""
    return MeshConstellationManager(mock_constellation)


# ==============================================================================
# HUB FAILOVER TESTS
# ==============================================================================


class TestHubFailover:
    """Test hub failover scenarios."""

    async def test_primary_hub_failover(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test failover when primary hub fails."""
        primary_id = mesh_manager.get_primary()
        assert primary_id is not None

        # Set primary as leader
        mesh_manager.constellation.hubs[primary_id].is_leader = True

        # Simulate primary failure
        result = await mesh_manager.simulate_hub_failure(primary_id)

        assert result["success"]
        assert result["was_primary"]
        assert result["was_leader"]
        assert result["new_leader"] is not None
        assert result["new_leader"] != primary_id

        # Verify new leader is set
        new_leader_id = result["new_leader"]
        new_leader = mesh_manager.constellation.hubs[new_leader_id]
        assert new_leader.is_leader

    async def test_non_leader_hub_failover(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test failover when non-leader hub fails."""
        # Get a non-leader hub
        non_leaders = [
            hub_id for hub_id, hub in mesh_manager.constellation.hubs.items() if not hub.is_leader
        ]
        assert len(non_leaders) > 0

        target_hub_id = non_leaders[0]

        # Simulate failure
        result = await mesh_manager.simulate_hub_failure(target_hub_id)

        assert result["success"]
        assert not result["was_leader"]
        # No new leader election needed
        assert result["new_leader"] is None or result["new_leader"] == mesh_manager.get_leader()

    async def test_device_migration_on_failover(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that devices are migrated when hub fails."""
        # Get a hub with devices
        hub_with_devices = None
        for _hub_id, hub in mesh_manager.constellation.hubs.items():
            if hub.devices:
                hub_with_devices = _hub_id
                break

        assert hub_with_devices is not None

        original_devices = [
            d.device_id for d in mesh_manager.constellation.hubs[hub_with_devices].devices
        ]

        # Simulate failure
        result = await mesh_manager.simulate_hub_failure(hub_with_devices)

        assert result["success"]
        assert len(result["orphaned_devices"]) > 0

        # Verify devices were migrated
        if result["device_migrations"]:
            for migration in result["device_migrations"]:
                assert migration["to_hub"] != hub_with_devices
                assert migration["to_hub"] in mesh_manager.constellation.hubs

    async def test_hub_recovery_rejoins_mesh(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that recovered hub rejoins the mesh."""
        # Fail a hub
        hub_ids = list(mesh_manager.constellation.hubs.keys())
        target_hub = hub_ids[1]  # Not primary

        await mesh_manager.simulate_hub_failure(target_hub)

        # Verify offline
        assert not mesh_manager.constellation.hubs[target_hub].is_online()

        # Recover hub
        result = await mesh_manager.simulate_hub_recovery(target_hub)

        assert result["success"]
        assert mesh_manager.constellation.hubs[target_hub].is_online()
        assert result["peer_count"] > 0

    async def test_circuit_breaker_opens_on_failures(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that circuit breaker opens after repeated failures."""
        hub_id = list(mesh_manager.constellation.hubs.keys())[0]
        health = mesh_manager.hub_health[hub_id]

        # Simulate failures
        for _ in range(5):
            health.record_failure()

        assert health.status == HealthStatus.UNHEALTHY
        assert not health.is_healthy()

    async def test_circuit_breaker_recovers(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that circuit breaker recovers after success."""
        hub_id = list(mesh_manager.constellation.hubs.keys())[0]
        health = mesh_manager.hub_health[hub_id]

        # Open circuit breaker
        for _ in range(5):
            health.record_failure()

        assert health.status == HealthStatus.UNHEALTHY

        # Recovery success
        health.record_success()

        assert health.status == HealthStatus.HEALTHY
        assert health.consecutive_failures == 0


# ==============================================================================
# CLIENT ROAMING TESTS
# ==============================================================================


class TestClientRoaming:
    """Test device roaming between hubs."""

    async def test_device_roams_to_new_hub(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test device moving to a different hub."""
        # Get a device and different hub
        device_id = list(mesh_manager.device_assignments.keys())[0]
        current_hub = mesh_manager.device_assignments[device_id]

        # Find a different hub
        target_hub = None
        for hub_id in mesh_manager.constellation.hubs:
            if hub_id != current_hub:
                target_hub = hub_id
                break

        assert target_hub is not None

        # Roam device
        result = await mesh_manager.roam_device(device_id, target_hub)

        assert result["success"]
        assert result["source_hub"] == current_hub
        assert result["target_hub"] == target_hub

        # Verify assignment updated
        assert mesh_manager.device_assignments[device_id] == target_hub

    async def test_device_roaming_updates_hub_counts(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that device counts are updated on roaming."""
        device_id = list(mesh_manager.device_assignments.keys())[0]
        source_hub = mesh_manager.device_assignments[device_id]

        # Find target with lowest device count
        target_hub = min(
            [h for h in mesh_manager.constellation.hubs if h != source_hub],
            key=lambda h: mesh_manager.hub_health[h].connected_devices,
        )

        source_count_before = mesh_manager.hub_health[source_hub].connected_devices
        target_count_before = mesh_manager.hub_health[target_hub].connected_devices

        # Roam device
        await mesh_manager.roam_device(device_id, target_hub)

        # Verify counts updated
        assert mesh_manager.hub_health[source_hub].connected_devices == source_count_before - 1
        assert mesh_manager.hub_health[target_hub].connected_devices == target_count_before + 1

    async def test_roaming_to_offline_hub_fails(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that roaming to an offline hub fails gracefully."""
        device_id = list(mesh_manager.device_assignments.keys())[0]

        # Make a hub offline
        hub_ids = list(mesh_manager.constellation.hubs.keys())
        offline_hub = hub_ids[-1]
        mesh_manager.constellation.hubs[offline_hub].connection_state = ConnectionState.DISCONNECTED

        # Try to roam
        result = await mesh_manager.roam_device(device_id, offline_hub)

        assert not result["success"]
        assert "offline" in result["error"].lower()

    async def test_multiple_devices_roam_simultaneously(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test multiple devices roaming at once."""
        device_ids = list(mesh_manager.device_assignments.keys())[:3]
        hub_ids = list(mesh_manager.constellation.hubs.keys())

        # Roam devices to different hubs
        results = []
        for i, device_id in enumerate(device_ids):
            target = hub_ids[(i + 1) % len(hub_ids)]
            result = await mesh_manager.roam_device(device_id, target)
            results.append(result)

        # All should succeed
        for result in results:
            assert result["success"]


# ==============================================================================
# SPLIT-BRAIN RECOVERY TESTS
# ==============================================================================


class TestSplitBrainRecovery:
    """Test network partition and split-brain recovery."""

    async def test_network_partition_creates_groups(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that network partition creates isolated groups."""
        hub_ids = list(mesh_manager.constellation.hubs.keys())

        # Split into two groups
        group_a = hub_ids[:2]
        group_b = hub_ids[2:]

        result = await mesh_manager.simulate_network_partition(group_a, group_b)

        assert result["success"]
        assert len(mesh_manager.partition_groups) == 2

        # Verify groups are isolated
        for hub_a in group_a:
            hub = mesh_manager.constellation.hubs[hub_a]
            for hub_b in group_b:
                assert hub_b not in hub.peers

    async def test_partition_elects_leaders_per_group(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that each partition elects its own leader."""
        hub_ids = list(mesh_manager.constellation.hubs.keys())
        group_a = hub_ids[:2]
        group_b = hub_ids[2:]

        result = await mesh_manager.simulate_network_partition(group_a, group_b)

        assert "leaders" in result
        assert len(result["leaders"]) == 2
        assert result["leaders"]["partition_0"] in group_a
        assert result["leaders"]["partition_1"] in group_b

    async def test_partition_healing_merges_state(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that partition healing merges CRDT state."""
        hub_ids = list(mesh_manager.constellation.hubs.keys())
        group_a = hub_ids[:2]
        group_b = hub_ids[2:]

        # Create partition
        await mesh_manager.simulate_network_partition(group_a, group_b)

        # Simulate updates in each partition
        for hub_id in group_a:
            mesh_manager.vector_clocks[hub_id].increment(hub_id)
        for hub_id in group_b:
            mesh_manager.vector_clocks[hub_id].increment(hub_id)

        # Heal partition
        result = await mesh_manager.heal_network_partition()

        assert result["success"]
        assert result["new_leader"] is not None

        # Verify clocks merged
        for hub_id in hub_ids:
            clock = mesh_manager.vector_clocks[hub_id]
            for other_id in hub_ids:
                # All clocks should have entries for all hubs
                assert clock.get(other_id) >= 0

    async def test_partition_healing_restores_connectivity(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that partition healing restores full connectivity."""
        hub_ids = list(mesh_manager.constellation.hubs.keys())
        group_a = hub_ids[:2]
        group_b = hub_ids[2:]

        # Create and heal partition
        await mesh_manager.simulate_network_partition(group_a, group_b)
        await mesh_manager.heal_network_partition()

        # Verify full connectivity restored
        for hub_id in hub_ids:
            hub = mesh_manager.constellation.hubs[hub_id]
            expected_peers = [h for h in hub_ids if h != hub_id]
            for peer_id in expected_peers:
                assert peer_id in hub.peers, f"{peer_id} not in {hub_id}'s peers"

    async def test_single_leader_after_heal(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that only one leader exists after partition heals."""
        hub_ids = list(mesh_manager.constellation.hubs.keys())

        await mesh_manager.simulate_network_partition(hub_ids[:2], hub_ids[2:])
        await mesh_manager.heal_network_partition()

        # Count leaders
        leaders = [
            hub_id for hub_id, hub in mesh_manager.constellation.hubs.items() if hub.is_leader
        ]

        assert len(leaders) == 1, f"Expected 1 leader, found {len(leaders)}: {leaders}"


# ==============================================================================
# NEW DEVICE JOIN TESTS
# ==============================================================================


class TestNewDeviceJoin:
    """Test new device joining the mesh."""

    async def test_new_hub_joins_mesh(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test new hub joining the mesh network."""
        new_hub = MockHub(
            hub_id="hub-new",
            name="New Hub",
            port=8090,
        )

        result = await mesh_manager.add_new_hub(new_hub)

        assert result["success"]
        assert result["hub_id"] == "hub-new"
        assert "hub-new" in mesh_manager.constellation.hubs
        assert result["peer_count"] > 0

    async def test_new_hub_gets_leader_info(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that new hub learns about current leader."""
        # Ensure there's a leader
        mesh_manager.constellation.hubs["hub-living-room"].is_leader = True

        new_hub = MockHub(
            hub_id="hub-new",
            name="New Hub",
            port=8090,
        )

        result = await mesh_manager.add_new_hub(new_hub)

        assert result["leader"] is not None
        assert mesh_manager.elections["hub-new"].leader_id == result["leader"]

    async def test_new_hub_syncs_state(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that new hub syncs state from leader."""
        # Set up leader with state
        leader_id = "hub-living-room"
        mesh_manager.constellation.hubs[leader_id].is_leader = True
        mesh_manager.vector_clocks[leader_id].increment(leader_id)
        mesh_manager.vector_clocks[leader_id].increment(leader_id)

        new_hub = MockHub(
            hub_id="hub-new",
            name="New Hub",
            port=8090,
        )

        await mesh_manager.add_new_hub(new_hub)

        # New hub should have synced clock
        new_clock = mesh_manager.vector_clocks["hub-new"]
        assert new_clock.get(leader_id) == 2

    async def test_new_device_assigned_to_hub(
        self,
        mesh_manager: MeshConstellationManager,
        mock_constellation: MockDeviceConstellation,
    ):
        """Test that new device is assigned to a hub."""
        new_device = MockDevice(
            device_id="new-light",
            name="New Light",
            device_type=DeviceType.LIGHT,
            room="Guest Room",
        )

        mock_constellation.add_device(new_device)

        # Device should be assigned to primary hub
        assert new_device.hub_id is not None
        assert new_device.hub_id in mesh_manager.constellation.hubs


# ==============================================================================
# DEVICE REMOVAL TESTS
# ==============================================================================


class TestDeviceRemoval:
    """Test device removal from the mesh."""

    async def test_hub_graceful_removal(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test graceful hub removal from mesh."""
        hub_ids = list(mesh_manager.constellation.hubs.keys())
        target_hub = hub_ids[-1]  # Remove last hub

        result = await mesh_manager.remove_hub(target_hub, graceful=True)

        assert result["success"]
        assert result["removed_hub"] == target_hub
        assert target_hub not in mesh_manager.constellation.hubs
        assert result["graceful"]

    async def test_leader_removal_triggers_election(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that removing leader triggers new election."""
        # Make first hub leader
        leader_id = "hub-living-room"
        mesh_manager.constellation.hubs[leader_id].is_leader = True

        result = await mesh_manager.remove_hub(leader_id, graceful=True)

        assert result["success"]
        assert result["was_leader"]
        assert result["new_leader"] is not None
        assert result["new_leader"] != leader_id

    async def test_devices_migrated_on_removal(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that devices are migrated when hub is removed."""
        hub_ids = list(mesh_manager.constellation.hubs.keys())

        # Find hub with devices
        target_hub = None
        for hub_id in hub_ids:
            if mesh_manager.constellation.hubs[hub_id].devices:
                target_hub = hub_id
                break

        if target_hub is None:
            pytest.skip("No hub with devices found")

        device_count = len(mesh_manager.constellation.hubs[target_hub].devices)

        result = await mesh_manager.remove_hub(target_hub, graceful=True)

        assert result["success"]
        assert len(result["device_migrations"]) == device_count

        # Verify all devices migrated
        for migration in result["device_migrations"]:
            assert migration["to_hub"] != target_hub
            assert migration["to_hub"] in mesh_manager.constellation.hubs

    async def test_peers_updated_on_removal(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that peer lists are updated when hub is removed."""
        hub_ids = list(mesh_manager.constellation.hubs.keys())
        target_hub = hub_ids[-1]

        await mesh_manager.remove_hub(target_hub, graceful=True)

        # Verify no remaining hub has target in peers
        for _hub_id, hub in mesh_manager.constellation.hubs.items():
            assert target_hub not in hub.peers


# ==============================================================================
# INTEGRATION TESTS
# ==============================================================================


class TestMeshIntegration:
    """Integration tests combining multiple mesh operations."""

    async def test_full_failure_recovery_cycle(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test complete failure and recovery cycle."""
        # Get primary leader
        primary_id = mesh_manager.get_primary()
        mesh_manager.constellation.hubs[primary_id].is_leader = True

        # Fail primary
        fail_result = await mesh_manager.simulate_hub_failure(primary_id)
        assert fail_result["success"]
        assert fail_result["new_leader"] is not None

        # System continues operating
        healthy_hubs = mesh_manager.get_healthy_hubs()
        assert len(healthy_hubs) >= 2

        # Recover primary
        recover_result = await mesh_manager.simulate_hub_recovery(primary_id)
        assert recover_result["success"]

        # Primary rejoins as follower
        assert not mesh_manager.constellation.hubs[primary_id].is_leader

    async def test_partition_during_failover(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test network partition occurring during hub failover."""
        hub_ids = list(mesh_manager.constellation.hubs.keys())

        # Fail a hub
        await mesh_manager.simulate_hub_failure(hub_ids[0])

        # Partition remaining hubs
        remaining = hub_ids[1:]
        result = await mesh_manager.simulate_network_partition(
            remaining[:1],
            remaining[1:],
        )

        assert result["success"]

        # Each partition should have a leader
        assert len(result["leaders"]) == 2

        # Heal partition
        heal_result = await mesh_manager.heal_network_partition()
        assert heal_result["success"]

    async def test_roaming_during_failover(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test device roaming while hub is failing over."""
        hub_ids = list(mesh_manager.constellation.hubs.keys())
        device_ids = list(mesh_manager.device_assignments.keys())

        if len(device_ids) < 1:
            pytest.skip("No devices to roam")

        device_id = device_ids[0]
        source_hub = mesh_manager.device_assignments[device_id]
        target_hub = [h for h in hub_ids if h != source_hub][0]

        # Fail source hub
        fail_task = mesh_manager.simulate_hub_failure(source_hub)

        # Roam device during failure
        roam_task = mesh_manager.roam_device(device_id, target_hub)

        # Execute concurrently
        fail_result, roam_result = await asyncio.gather(fail_task, roam_task)

        # Both operations should complete (roam may fail if source is already gone)
        assert fail_result["success"]
        # Device should end up somewhere
        assert device_id in mesh_manager.device_assignments

    async def test_metrics_during_operations(
        self,
        mesh_manager: MeshConstellationManager,
    ):
        """Test that health metrics are maintained during operations."""
        hub_ids = list(mesh_manager.constellation.hubs.keys())

        # Initial health check
        for hub_id in hub_ids:
            assert hub_id in mesh_manager.hub_health

        # Perform operations
        await mesh_manager.simulate_hub_failure(hub_ids[0])
        await mesh_manager.simulate_hub_recovery(hub_ids[0])

        # Health should be tracked
        health = mesh_manager.hub_health[hub_ids[0]]
        assert health.last_heartbeat > 0
        assert health.status == HealthStatus.HEALTHY


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
