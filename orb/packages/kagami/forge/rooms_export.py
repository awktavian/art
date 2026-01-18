"""ForgeRoomsExporter - Export Forge-generated assets to Rooms as physics entities.

This module provides one-way integration from Forge to Rooms, allowing generated
characters and assets to appear in multiplayer spatial environments.

Design:
- One-way export (Forge → Rooms), no reverse dependency
- Uses Rooms CRDT for conflict-free collaborative updates
- Idempotent operations (safe retries)
- Batch operations for efficiency

Usage:
    exporter = ForgeRoomsExporter()

    # Export single character
    success = await exporter.export_character_to_room(
        room_id="test_room",
        character_data={"id": "char_123", "gltf_url": "https://...", ...},
        position=[0, 0, 0],
    )

    # Export batch with auto-layout
    results = await exporter.export_batch_to_room(
        room_id="test_room",
        characters_list=[char1, char2, char3],
        spacing=2.0,
    )
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HybridLogicalClock:
    """Hybrid Logical Clock (HLC) for distributed event ordering.

    Combines physical time with logical counter to provide:
    - Total ordering of events across nodes
    - Causality tracking
    - Bounded drift from physical time

    Based on: "Logical Physical Clocks and Consistent Snapshots in Globally
    Distributed Databases" (Kulkarni et al., 2014)
    """

    physical_time: int = 0  # Milliseconds since epoch
    logical_counter: int = 0
    node_id: str = ""

    @classmethod
    def now(cls, node_id: str) -> HybridLogicalClock:
        """Create HLC with current physical time."""
        return cls(
            physical_time=int(time.time() * 1000),
            logical_counter=0,
            node_id=node_id,
        )

    def update(self, remote_hlc: HybridLogicalClock | None = None) -> HybridLogicalClock:
        """Update clock, potentially incorporating remote clock.

        Args:
            remote_hlc: Remote clock to merge (None for local-only update)

        Returns:
            New HLC with updated timestamp
        """
        current_physical = int(time.time() * 1000)

        if remote_hlc is None:
            # Local event only
            if current_physical > self.physical_time:
                return HybridLogicalClock(
                    physical_time=current_physical,
                    logical_counter=0,
                    node_id=self.node_id,
                )
            else:
                return HybridLogicalClock(
                    physical_time=self.physical_time,
                    logical_counter=self.logical_counter + 1,
                    node_id=self.node_id,
                )
        else:
            # Merge with remote clock
            max_physical = max(current_physical, self.physical_time, remote_hlc.physical_time)

            if max_physical == current_physical and max_physical > self.physical_time:
                new_logical = 0
            elif max_physical == self.physical_time and max_physical > remote_hlc.physical_time:
                new_logical = self.logical_counter + 1
            elif max_physical == remote_hlc.physical_time and max_physical > self.physical_time:
                new_logical = remote_hlc.logical_counter + 1
            else:
                # All equal - increment max logical
                new_logical = max(self.logical_counter, remote_hlc.logical_counter) + 1

            return HybridLogicalClock(
                physical_time=max_physical,
                logical_counter=new_logical,
                node_id=self.node_id,
            )

    def compare(self, other: HybridLogicalClock) -> int:
        """Compare two HLCs.

        Returns:
            -1 if self < other
             0 if self == other
             1 if self > other
        """
        if self.physical_time < other.physical_time:
            return -1
        elif self.physical_time > other.physical_time:
            return 1
        elif self.logical_counter < other.logical_counter:
            return -1
        elif self.logical_counter > other.logical_counter:
            return 1
        elif self.node_id < other.node_id:
            return -1
        elif self.node_id > other.node_id:
            return 1
        else:
            return 0

    def __lt__(self, other: HybridLogicalClock) -> bool:
        return self.compare(other) < 0

    def __le__(self, other: HybridLogicalClock) -> bool:
        return self.compare(other) <= 0

    def __gt__(self, other: HybridLogicalClock) -> bool:
        return self.compare(other) > 0

    def __ge__(self, other: HybridLogicalClock) -> bool:
        return self.compare(other) >= 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HybridLogicalClock):
            return False
        return self.compare(other) == 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict[str, Any]."""
        return {
            "physical_time": self.physical_time,
            "logical_counter": self.logical_counter,
            "node_id": self.node_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HybridLogicalClock:
        """Deserialize from dict[str, Any]."""
        return cls(
            physical_time=data["physical_time"],
            logical_counter=data["logical_counter"],
            node_id=data["node_id"],
        )


@dataclass
class RoomEntityState:
    """State for a single room entity with CRDT metadata."""

    entity_id: str
    position: list[float]
    orientation: list[float]
    mesh_url: str
    metadata: dict[str, Any]
    timestamp: HybridLogicalClock
    client_id: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict[str, Any]."""
        return {
            "id": self.entity_id,
            "type": "forge_character",
            "position": self.position,
            "orientation": self.orientation,
            "mesh_url": self.mesh_url,
            "metadata": self.metadata,
            "crdt_meta": {
                "timestamp": self.timestamp.to_dict(),
                "client_id": self.client_id,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomEntityState:
        """Deserialize from dict[str, Any]."""
        crdt_meta = data.get("crdt_meta", {})
        timestamp_data = crdt_meta.get("timestamp", {})

        return cls(
            entity_id=data["id"],
            position=data["position"],
            orientation=data["orientation"],
            mesh_url=data["mesh_url"],
            metadata=data.get("metadata", {}),
            timestamp=HybridLogicalClock.from_dict(timestamp_data)
            if timestamp_data
            else HybridLogicalClock.now("unknown"),
            client_id=crdt_meta.get("client_id", "unknown"),
        )


@dataclass
class RoomCRDT:
    """Conflict-free Replicated Data Type for room entity exports.

    Implements Last-Writer-Wins Register (LWW-Register) semantics with:
    - Hybrid Logical Clock for total ordering
    - Position/orientation conflict resolution
    - Concurrent batch export support
    - Rollback capability on partial failures

    Design:
    - Each entity has an HLC timestamp
    - Conflicts resolved by comparing HLCs (latest wins)
    - Merge operation is commutative, associative, idempotent
    - Tombstones track deletions with timestamps
    """

    client_id: str
    entities: dict[str, RoomEntityState] = field(default_factory=dict[str, Any])
    tombstones: dict[str, HybridLogicalClock] = field(default_factory=dict[str, Any])
    clock: HybridLogicalClock = field(default_factory=lambda: HybridLogicalClock.now("default"))
    snapshots: list[dict[str, RoomEntityState]] = field(default_factory=list[Any])
    max_snapshots: int = 10

    def __post_init__(self) -> None:
        """Initialize clock with client_id."""
        if not self.clock.node_id or self.clock.node_id == "default":
            self.clock = HybridLogicalClock.now(self.client_id)

    def _create_snapshot(self) -> None:
        """Create snapshot for rollback capability."""
        snapshot = {
            entity_id: RoomEntityState(
                entity_id=state.entity_id,
                position=state.position.copy(),
                orientation=state.orientation.copy(),
                mesh_url=state.mesh_url,
                metadata=state.metadata.copy(),
                timestamp=HybridLogicalClock(
                    physical_time=state.timestamp.physical_time,
                    logical_counter=state.timestamp.logical_counter,
                    node_id=state.timestamp.node_id,
                ),
                client_id=state.client_id,
            )
            for entity_id, state in self.entities.items()
        }

        self.snapshots.append(snapshot)

        # Keep only max_snapshots most recent
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots = self.snapshots[-self.max_snapshots :]

    def add_entity(
        self,
        entity_id: str,
        position: list[float],
        orientation: list[float],
        mesh_url: str,
        metadata: dict[str, Any] | None = None,
    ) -> RoomEntityState:
        """Add or update an entity with LWW semantics.

        Args:
            entity_id: Unique entity identifier
            position: [x, y, z] position
            orientation: [x, y, z, w] quaternion
            mesh_url: 3D model URL
            metadata: Optional metadata dict[str, Any]

        Returns:
            The entity state (new or updated)
        """
        # Create snapshot before mutation
        self._create_snapshot()

        # Update clock
        self.clock = self.clock.update()

        # Create new state
        new_state = RoomEntityState(
            entity_id=entity_id,
            position=position.copy() if isinstance(position, list) else list(position),
            orientation=orientation.copy() if isinstance(orientation, list) else list(orientation),
            mesh_url=mesh_url,
            metadata=metadata.copy() if metadata else {},
            timestamp=HybridLogicalClock(
                physical_time=self.clock.physical_time,
                logical_counter=self.clock.logical_counter,
                node_id=self.clock.node_id,
            ),
            client_id=self.client_id,
        )

        # Check if entity exists
        if entity_id in self.entities:
            existing = self.entities[entity_id]
            # LWW: Only update if new timestamp is greater
            if new_state.timestamp > existing.timestamp:
                self.entities[entity_id] = new_state
            else:
                # Keep existing (it's newer)
                return existing
        else:
            # Check tombstone
            if entity_id in self.tombstones:
                tombstone_ts = self.tombstones[entity_id]
                # Only add if our timestamp is newer than deletion
                if new_state.timestamp > tombstone_ts:
                    self.entities[entity_id] = new_state
                    del self.tombstones[entity_id]
                else:
                    # Entity was deleted more recently, don't resurrect
                    logger.warning(
                        f"Entity {entity_id} was deleted at {tombstone_ts.physical_time}, "
                        f"refusing to resurrect with older timestamp {new_state.timestamp.physical_time}"
                    )
                    return new_state  # Return the state but don't add it
            else:
                # New entity
                self.entities[entity_id] = new_state

        return new_state

    def remove_entity(self, entity_id: str) -> bool:
        """Remove an entity (create tombstone).

        Args:
            entity_id: Entity to remove

        Returns:
            True if entity was removed, False if already gone
        """
        # Create snapshot before mutation
        self._create_snapshot()

        # Update clock
        self.clock = self.clock.update()

        # Create tombstone with current timestamp
        tombstone_ts = HybridLogicalClock(
            physical_time=self.clock.physical_time,
            logical_counter=self.clock.logical_counter,
            node_id=self.clock.node_id,
        )

        if entity_id in self.entities:
            existing = self.entities[entity_id]
            # Only delete if tombstone is newer
            if tombstone_ts > existing.timestamp:
                del self.entities[entity_id]
                self.tombstones[entity_id] = tombstone_ts
                return True
            else:
                # Entity is newer than deletion request
                logger.warning(
                    f"Entity {entity_id} has timestamp {existing.timestamp.physical_time} "
                    f"newer than deletion request {tombstone_ts.physical_time}"
                )
                return False
        else:
            # Not present, but record tombstone anyway (prevents resurrection)
            if entity_id not in self.tombstones or tombstone_ts > self.tombstones[entity_id]:
                self.tombstones[entity_id] = tombstone_ts
            return False

    def merge(self, other: RoomCRDT) -> None:
        """Merge another CRDT state into this one.

        Implements LWW merge:
        - For each entity, keep the one with the latest timestamp
        - Merge tombstones (keep latest deletion timestamp)
        - Update clock by merging with remote clock

        This operation is:
        - Commutative: merge(A, B) = merge(B, A)
        - Associative: merge(merge(A, B), C) = merge(A, merge(B, C))
        - Idempotent: merge(A, A) = A

        Args:
            other: Another RoomCRDT to merge
        """
        # Create snapshot before mutation
        self._create_snapshot()

        # Merge clocks
        self.clock = self.clock.update(other.clock)

        # Merge entities (LWW)
        for entity_id, other_state in other.entities.items():
            if entity_id in self.entities:
                our_state = self.entities[entity_id]
                # Keep whichever is newer
                if other_state.timestamp > our_state.timestamp:
                    self.entities[entity_id] = RoomEntityState(
                        entity_id=other_state.entity_id,
                        position=other_state.position.copy(),
                        orientation=other_state.orientation.copy(),
                        mesh_url=other_state.mesh_url,
                        metadata=other_state.metadata.copy(),
                        timestamp=HybridLogicalClock(
                            physical_time=other_state.timestamp.physical_time,
                            logical_counter=other_state.timestamp.logical_counter,
                            node_id=other_state.timestamp.node_id,
                        ),
                        client_id=other_state.client_id,
                    )
            else:
                # Check our tombstones
                if entity_id in self.tombstones:
                    our_tombstone = self.tombstones[entity_id]
                    # Only add if entity is newer than our deletion
                    if other_state.timestamp > our_tombstone:
                        self.entities[entity_id] = RoomEntityState(
                            entity_id=other_state.entity_id,
                            position=other_state.position.copy(),
                            orientation=other_state.orientation.copy(),
                            mesh_url=other_state.mesh_url,
                            metadata=other_state.metadata.copy(),
                            timestamp=HybridLogicalClock(
                                physical_time=other_state.timestamp.physical_time,
                                logical_counter=other_state.timestamp.logical_counter,
                                node_id=other_state.timestamp.node_id,
                            ),
                            client_id=other_state.client_id,
                        )
                        # Remove tombstone
                        del self.tombstones[entity_id]
                else:
                    # New entity not in our state
                    self.entities[entity_id] = RoomEntityState(
                        entity_id=other_state.entity_id,
                        position=other_state.position.copy(),
                        orientation=other_state.orientation.copy(),
                        mesh_url=other_state.mesh_url,
                        metadata=other_state.metadata.copy(),
                        timestamp=HybridLogicalClock(
                            physical_time=other_state.timestamp.physical_time,
                            logical_counter=other_state.timestamp.logical_counter,
                            node_id=other_state.timestamp.node_id,
                        ),
                        client_id=other_state.client_id,
                    )

        # Merge tombstones (keep latest)
        for entity_id, other_tombstone in other.tombstones.items():
            if entity_id in self.tombstones:
                our_tombstone = self.tombstones[entity_id]
                # Keep newer tombstone
                if other_tombstone > our_tombstone:
                    self.tombstones[entity_id] = HybridLogicalClock(
                        physical_time=other_tombstone.physical_time,
                        logical_counter=other_tombstone.logical_counter,
                        node_id=other_tombstone.node_id,
                    )
                    # Remove entity if tombstone is newer
                    if entity_id in self.entities:
                        entity_state = self.entities[entity_id]
                        if other_tombstone > entity_state.timestamp:
                            del self.entities[entity_id]
            else:
                # New tombstone
                self.tombstones[entity_id] = HybridLogicalClock(
                    physical_time=other_tombstone.physical_time,
                    logical_counter=other_tombstone.logical_counter,
                    node_id=other_tombstone.node_id,
                )
                # Remove entity if tombstone is newer
                if entity_id in self.entities:
                    entity_state = self.entities[entity_id]
                    if other_tombstone > entity_state.timestamp:
                        del self.entities[entity_id]

    def rollback_to_snapshot(self, snapshot_index: int = -1) -> bool:
        """Rollback to a previous snapshot.

        Args:
            snapshot_index: Index of snapshot to restore (-1 for most recent)

        Returns:
            True if rollback succeeded, False if no snapshot available
        """
        if not self.snapshots:
            logger.warning("No snapshots available for rollback")
            return False

        if abs(snapshot_index) > len(self.snapshots):
            logger.warning(
                f"Snapshot index {snapshot_index} out of range "
                f"(have {len(self.snapshots)} snapshots)"
            )
            return False

        # Restore snapshot
        snapshot = self.snapshots[snapshot_index]
        self.entities = {
            entity_id: RoomEntityState(
                entity_id=state.entity_id,
                position=state.position.copy(),
                orientation=state.orientation.copy(),
                mesh_url=state.mesh_url,
                metadata=state.metadata.copy(),
                timestamp=HybridLogicalClock(
                    physical_time=state.timestamp.physical_time,
                    logical_counter=state.timestamp.logical_counter,
                    node_id=state.timestamp.node_id,
                ),
                client_id=state.client_id,
            )
            for entity_id, state in snapshot.items()
        }

        # Remove the snapshots after the one we restored to
        if snapshot_index == -1:
            self.snapshots = self.snapshots[:-1]
        else:
            self.snapshots = self.snapshots[:snapshot_index]

        logger.info(f"Rolled back to snapshot {snapshot_index}")
        return True

    def get_entities(self) -> dict[str, dict[str, Any]]:
        """Get all entities as dicts (for export to Rooms).

        Returns:
            Dict mapping entity_id -> entity dict[str, Any]
        """
        return {entity_id: state.to_dict() for entity_id, state in self.entities.items()}

    def to_dict(self) -> dict[str, Any]:
        """Serialize full CRDT state to dict[str, Any]."""
        return {
            "client_id": self.client_id,
            "entities": {entity_id: state.to_dict() for entity_id, state in self.entities.items()},
            "tombstones": {entity_id: ts.to_dict() for entity_id, ts in self.tombstones.items()},
            "clock": self.clock.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomCRDT:
        """Deserialize CRDT state from dict[str, Any]."""
        crdt = cls(client_id=data["client_id"])

        # Restore entities
        crdt.entities = {
            entity_id: RoomEntityState.from_dict(entity_data)
            for entity_id, entity_data in data.get("entities", {}).items()
        }

        # Restore tombstones
        crdt.tombstones = {
            entity_id: HybridLogicalClock.from_dict(ts_data)
            for entity_id, ts_data in data.get("tombstones", {}).items()
        }

        # Restore clock
        if "clock" in data:
            crdt.clock = HybridLogicalClock.from_dict(data["clock"])

        return crdt


class ForgeRoomsExporter:
    """Export Forge-generated assets to Rooms as physics entities.

    This class provides methods to export characters and other Forge assets
    into Rooms multiplayer environments where they can be viewed and
    interacted with by multiple users.

    All operations use CRDT semantics for conflict-free updates.
    """

    def __init__(self, client_id: str = "forge_service") -> None:
        """Initialize the exporter.

        Args:
            client_id: CRDT client identifier for this service (default: "forge_service")
        """
        self.client_id = client_id

    async def export_character_to_room(
        self,
        room_id: str,
        character_data: dict[str, Any],
        position: list[float],
        orientation: list[float] | None = None,
    ) -> bool:
        """Export a single character to a room as a physics entity.

        The character will appear in the room at the specified position and can be
        viewed by all room members. This operation is idempotent - calling it multiple
        times with the same character_id will update the entity rather than creating
        duplicates.

        Args:
            room_id: Target room identifier
            character_data: Character dict[str, Any] from ForgeService.generate_character()
                Required keys:
                - id: unique character identifier
                - gltf_url or glb_url: 3D model URL
                Optional keys:
                - concept: character concept
                - request_id: original request identifier
                - quality: quality level (preview/draft/final)
            position: [x, y, z] position in 3D space
            orientation: [x, y, z, w] quaternion (default: [0, 0, 0, 1])

        Returns:
            True if export succeeded, False if export failed

        Raises:
            ValueError: If character_data is missing required fields
            RuntimeError: If CRDT operation fails

        Examples:
            >>> exporter = ForgeRoomsExporter()
            >>> character = {
            ...     "id": "warrior_01",
            ...     "gltf_url": "https://cdn.example.com/warrior.glb",
            ...     "concept": "medieval warrior",
            ...     "quality": "draft",
            ... }
            >>> await exporter.export_character_to_room(
            ...     room_id="dungeon_01",
            ...     character_data=character,
            ...     position=[5.0, 0.0, -3.0],
            ... )
            True
        """
        try:
            from kagami.core.rooms.crdt import OperationType, create_operation
            from kagami.core.rooms.state_service import apply_crdt_operations, get_snapshot
        except ImportError as e:
            logger.error(f"Failed to import Rooms CRDT: {e}")
            raise RuntimeError(f"Rooms system not available: {e}") from e

        # Validate character_data
        character_id = character_data.get("id")
        if not character_id:
            raise ValueError("character_data must contain 'id' field")

        character_id = str(character_id).strip()
        if not character_id:
            raise ValueError("character_data 'id' must be non-empty")

        # Extract mesh URL (prefer gltf_url, fallback to glb_url)
        mesh_url = character_data.get("gltf_url") or character_data.get("glb_url")
        if not mesh_url:
            logger.error(f"Character {character_id} missing mesh URL (gltf_url or glb_url)")
            return False

        # Validate position
        if not isinstance(position, (list, tuple)) or len(position) != 3:
            raise ValueError("position must be [x, y, z] list[Any] with 3 elements")

        try:
            position = [float(p) for p in position]
        except (TypeError, ValueError) as e:
            raise ValueError(f"position elements must be numeric: {e}") from e

        # Validate/default orientation
        if orientation is None:
            orientation = [0.0, 0.0, 0.0, 1.0]  # Identity quaternion

        if not isinstance(orientation, (list, tuple)) or len(orientation) != 4:
            raise ValueError("orientation must be [x, y, z, w] quaternion with 4 elements")

        try:
            orientation = [float(o) for o in orientation]
        except (TypeError, ValueError) as e:
            raise ValueError(f"orientation elements must be numeric: {e}") from e

        # Verify room exists
        try:
            snapshot = await get_snapshot(room_id)
            if snapshot.room_id != room_id:
                logger.warning(f"Room {room_id} not found (empty snapshot)")
                return False
        except Exception as e:
            logger.warning(f"Failed to get snapshot for room {room_id}: {e}")
            return False

        # Build physics entity
        entity = {
            "id": character_id,
            "type": "forge_character",
            "position": position,
            "orientation": orientation,
            "mesh_url": mesh_url,
            "metadata": {
                "concept": character_data.get("concept"),
                "request_id": character_data.get("request_id"),
                "quality": character_data.get("quality"),
                "exported_at": time.time(),
            },
        }

        # Create CRDT ADD operation
        # Using ADD with element_id makes this idempotent - multiple calls
        # with same character_id will update the entity, not duplicate it
        try:
            op = create_operation(
                op_type=OperationType.ADD,
                path="physics_entities",
                value=entity,
                element_id=character_id,
                client_id=self.client_id,
                version=int(time.time() * 1000),  # Use timestamp as version
            )
        except Exception as e:
            logger.error(f"Failed to create CRDT operation: {e}")
            raise RuntimeError(f"CRDT operation creation failed: {e}") from e

        # Apply operation to room
        try:
            _, deltas = await apply_crdt_operations(
                room_id,
                [op.to_dict()],
                default_client_id=self.client_id,
            )

            if deltas:
                logger.info(
                    f"Exported character {character_id} to room {room_id} at position {position}"
                )
                return True
            else:
                logger.warning(
                    f"CRDT operation for character {character_id} did not change "
                    f"room {room_id} state (may be duplicate)"
                )
                return True  # Still considered success (idempotent)

        except Exception as e:
            logger.error(f"Failed to apply CRDT operation to room {room_id}: {e}")
            raise RuntimeError(f"Failed to export character to room: {e}") from e

    async def export_batch_to_room(
        self,
        room_id: str,
        characters_list: list[dict[str, Any]],
        spacing: float = 2.0,
    ) -> dict[str, bool]:
        """Export multiple characters to a room with automatic grid layout.

        Characters are arranged in a grid pattern with specified spacing.
        This is more efficient than calling export_character_to_room() multiple
        times because CRDT operations are batched.

        Args:
            room_id: Target room identifier
            characters_list: List of character dicts from ForgeService
            spacing: Distance between characters in grid (meters)

        Returns:
            Dict mapping character_id -> success status

        Raises:
            ValueError: If characters_list is empty or invalid
            RuntimeError: If CRDT batch operation fails

        Examples:
            >>> exporter = ForgeRoomsExporter()
            >>> characters = [
            ...     {"id": "char_1", "gltf_url": "...", "concept": "warrior"},
            ...     {"id": "char_2", "gltf_url": "...", "concept": "mage"},
            ...     {"id": "char_3", "gltf_url": "...", "concept": "rogue"},
            ... ]
            >>> results = await exporter.export_batch_to_room(
            ...     room_id="gallery",
            ...     characters_list=characters,
            ...     spacing=3.0,
            ... )
            >>> results
            {"char_1": True, "char_2": True, "char_3": True}
        """
        if not characters_list:
            raise ValueError("characters_list must not be empty")

        if spacing <= 0:
            raise ValueError("spacing must be positive")

        try:
            from kagami.core.rooms.crdt import OperationType, create_operation
            from kagami.core.rooms.state_service import apply_crdt_operations, get_snapshot
        except ImportError as e:
            logger.error(f"Failed to import Rooms CRDT: {e}")
            raise RuntimeError(f"Rooms system not available: {e}") from e

        # Verify room exists
        try:
            snapshot = await get_snapshot(room_id)
            if snapshot.room_id != room_id:
                logger.warning(f"Room {room_id} not found (empty snapshot)")
                return {
                    str(char.get("id", "")): False for char in characters_list if char.get("id")
                }
        except Exception as e:
            logger.warning(f"Failed to get snapshot for room {room_id}: {e}")
            return {str(char.get("id", "")): False for char in characters_list if char.get("id")}

        # Calculate grid layout
        # Grid size: ceil(sqrt(n)) x ceil(sqrt(n))
        n = len(characters_list)
        grid_size = math.ceil(math.sqrt(n))

        # Build CRDT operations for all characters
        operations = []
        results: dict[str, bool] = {}

        for idx, character_data in enumerate(characters_list):
            # Extract character_id
            character_id = character_data.get("id")
            if not character_id:
                logger.warning(f"Character at index {idx} missing 'id' field, skipping")
                continue

            character_id = str(character_id).strip()
            if not character_id:
                logger.warning(f"Character at index {idx} has empty 'id', skipping")
                continue

            # Extract mesh URL
            mesh_url = character_data.get("gltf_url") or character_data.get("glb_url")
            if not mesh_url:
                logger.error(f"Character {character_id} missing mesh URL, skipping")
                results[character_id] = False
                continue

            # Calculate grid position
            row = idx // grid_size
            col = idx % grid_size

            # Center the grid around origin
            offset_x = -(grid_size - 1) * spacing / 2
            offset_z = -(grid_size - 1) * spacing / 2

            position = [
                offset_x + col * spacing,
                0.0,  # Ground level
                offset_z + row * spacing,
            ]

            # Build entity
            entity = {
                "id": character_id,
                "type": "forge_character",
                "position": position,
                "orientation": [0.0, 0.0, 0.0, 1.0],
                "mesh_url": mesh_url,
                "metadata": {
                    "concept": character_data.get("concept"),
                    "request_id": character_data.get("request_id"),
                    "quality": character_data.get("quality"),
                    "batch_index": idx,
                    "exported_at": time.time(),
                },
            }

            # Create CRDT operation
            try:
                op = create_operation(
                    op_type=OperationType.ADD,
                    path="physics_entities",
                    value=entity,
                    element_id=character_id,
                    client_id=self.client_id,
                    version=int(time.time() * 1000) + idx,  # Unique version per character
                )
                operations.append(op.to_dict())
                results[character_id] = True  # Optimistic
            except Exception as e:
                logger.error(f"Failed to create CRDT operation for {character_id}: {e}")
                results[character_id] = False

        if not operations:
            logger.warning("No valid characters to export")
            return results

        # Batch apply all operations
        try:
            _, _deltas = await apply_crdt_operations(
                room_id,
                operations,
                default_client_id=self.client_id,
            )

            logger.info(
                f"Exported batch of {len(operations)} characters to room {room_id} "
                f"(grid: {grid_size}x{grid_size}, spacing: {spacing}m)"
            )

            # All operations succeeded (or were idempotent)
            return results

        except Exception as e:
            logger.error(f"Failed to apply batch CRDT operations to room {room_id}: {e}")
            # Mark all as failed
            for character_id in results:
                results[character_id] = False
            raise RuntimeError(f"Failed to export batch to room: {e}") from e

    async def update_character_in_room(
        self,
        room_id: str,
        character_id: str,
        updates: dict[str, Any],
    ) -> bool:
        """Update an existing character entity in a room.

        This allows updating position, orientation, or metadata of an already
        exported character without re-creating it.

        Args:
            room_id: Target room identifier
            character_id: Character identifier to update
            updates: Dict of fields to update (position, orientation, metadata, etc.)

        Returns:
            True if update succeeded, False otherwise

        Raises:
            ValueError: If character_id is empty or updates is invalid
            RuntimeError: If CRDT operation fails

        Examples:
            >>> exporter = ForgeRoomsExporter()
            >>> await exporter.update_character_in_room(
            ...     room_id="dungeon_01",
            ...     character_id="warrior_01",
            ...     updates={"position": [10.0, 0.0, -5.0]},
            ... )
            True
        """
        if not character_id or not str(character_id).strip():
            raise ValueError("character_id must be non-empty")

        if not updates:
            raise ValueError("updates must contain at least one field")

        try:
            from kagami.core.rooms.crdt import OperationType, create_operation
            from kagami.core.rooms.state_service import apply_crdt_operations, get_snapshot
        except ImportError as e:
            logger.error(f"Failed to import Rooms CRDT: {e}")
            raise RuntimeError(f"Rooms system not available: {e}") from e

        character_id = str(character_id).strip()

        # Verify room and character exist
        try:
            snapshot = await get_snapshot(room_id)
            physics_entities = snapshot.state.get("physics_entities", {})

            if not isinstance(physics_entities, dict):
                logger.warning(f"Room {room_id} has no physics_entities dict[str, Any]")
                return False

            if character_id not in physics_entities:
                logger.warning(
                    f"Character {character_id} not found in room {room_id} "
                    f"(cannot update non-existent entity)"
                )
                return False

        except Exception as e:
            logger.warning(f"Failed to verify character in room {room_id}: {e}")
            return False

        # Get current entity and merge updates
        current_entity = physics_entities.get(character_id, {})
        if not isinstance(current_entity, dict):
            logger.error(f"Character {character_id} entity is not a dict[str, Any]")
            return False

        # Merge updates into current entity
        updated_entity = dict(current_entity)
        for key, value in updates.items():
            if key == "metadata":
                # Merge metadata dicts
                current_meta = updated_entity.get("metadata", {})
                if isinstance(current_meta, dict) and isinstance(value, dict):
                    merged_meta = dict(current_meta)
                    merged_meta.update(value)
                    updated_entity["metadata"] = merged_meta
                else:
                    updated_entity["metadata"] = value
            else:
                updated_entity[key] = value

        # Ensure updated_at timestamp
        if "metadata" not in updated_entity:
            updated_entity["metadata"] = {}
        if isinstance(updated_entity["metadata"], dict):
            updated_entity["metadata"]["updated_at"] = time.time()

        # Create CRDT ADD operation (ADD is idempotent update for existing elements)
        try:
            op = create_operation(
                op_type=OperationType.ADD,
                path="physics_entities",
                value=updated_entity,
                element_id=character_id,
                client_id=self.client_id,
                version=int(time.time() * 1000),
            )
        except Exception as e:
            logger.error(f"Failed to create CRDT update operation: {e}")
            raise RuntimeError(f"CRDT operation creation failed: {e}") from e

        # Apply operation
        try:
            _, deltas = await apply_crdt_operations(
                room_id,
                [op.to_dict()],
                default_client_id=self.client_id,
            )

            if deltas:
                logger.info(
                    f"Updated character {character_id} in room {room_id}: {list(updates.keys())}"
                )

            return True

        except Exception as e:
            logger.error(f"Failed to apply CRDT update to room {room_id}: {e}")
            raise RuntimeError(f"Failed to update character in room: {e}") from e

    async def remove_character_from_room(
        self,
        room_id: str,
        character_id: str,
    ) -> bool:
        """Remove a character entity from a room.

        This removes the character from the room's physics entities, making it
        no longer visible to room members.

        Args:
            room_id: Target room identifier
            character_id: Character identifier to remove

        Returns:
            True if removal succeeded, False otherwise

        Raises:
            ValueError: If character_id is empty
            RuntimeError: If CRDT operation fails

        Examples:
            >>> exporter = ForgeRoomsExporter()
            >>> await exporter.remove_character_from_room(
            ...     room_id="dungeon_01",
            ...     character_id="warrior_01",
            ... )
            True
        """
        if not character_id or not str(character_id).strip():
            raise ValueError("character_id must be non-empty")

        try:
            from kagami.core.rooms.crdt import OperationType, create_operation
            from kagami.core.rooms.state_service import apply_crdt_operations
        except ImportError as e:
            logger.error(f"Failed to import Rooms CRDT: {e}")
            raise RuntimeError(f"Rooms system not available: {e}") from e

        character_id = str(character_id).strip()

        # Create CRDT REMOVE operation
        try:
            op = create_operation(
                op_type=OperationType.REMOVE,
                path="physics_entities",
                value=None,
                element_id=character_id,
                client_id=self.client_id,
                version=int(time.time() * 1000),
            )
        except Exception as e:
            logger.error(f"Failed to create CRDT remove operation: {e}")
            raise RuntimeError(f"CRDT operation creation failed: {e}") from e

        # Apply operation
        try:
            _, deltas = await apply_crdt_operations(
                room_id,
                [op.to_dict()],
                default_client_id=self.client_id,
            )

            if deltas:
                logger.info(f"Removed character {character_id} from room {room_id}")
            else:
                logger.info(
                    f"Character {character_id} was not in room {room_id} (remove is idempotent)"
                )

            return True

        except Exception as e:
            logger.error(f"Failed to apply CRDT remove to room {room_id}: {e}")
            raise RuntimeError(f"Failed to remove character from room: {e}") from e


__all__ = [
    "ForgeRoomsExporter",
    "HybridLogicalClock",
    "RoomCRDT",
    "RoomEntityState",
]
