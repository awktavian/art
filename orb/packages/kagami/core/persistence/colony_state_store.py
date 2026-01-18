"""Colony state persistence for Kagami.

CREATED: December 28, 2025
PURPOSE: Save and load state for all 7 colonies with E8 embeddings.

Persists:
- Colony hidden state (deterministic RNN)
- Colony stochastic state (latent variables)
- E8 embeddings (octonion codes)
- Attention weights and messages
- Hofstadter loop state
- Metadata (timestep, active status, etc.)

Format: PyTorch state_dict with safetensors
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import torch

from kagami.core.persistence.backends.protocol import StorageBackend
from kagami.core.persistence.serializers import (
    CompositeSerializer,
    CompressionType,
    JSONSerializer,
    TensorSerializer,
)


@dataclass
class ColonyStateSnapshot:
    """Snapshot of all 7 colony states."""

    # Per-colony tensors (7 entries each)
    hidden_states: dict[int, torch.Tensor]  # colony_id -> hidden
    stochastic_states: dict[int, torch.Tensor]  # colony_id -> stochastic
    e8_embeddings: dict[int, torch.Tensor]  # colony_id -> [8] octonion

    # Optional per-colony tensors
    attention_weights: dict[int, torch.Tensor] = field(default_factory=dict[str, Any])
    messages: dict[int, torch.Tensor] = field(default_factory=dict[str, Any])
    loop_states: dict[int, torch.Tensor] = field(default_factory=dict[str, Any])
    fixed_points: dict[int, torch.Tensor] = field(default_factory=dict[str, Any])

    # Metadata
    timestep: int = 0
    active_colonies: list[int] = field(default_factory=lambda: list(range(7)))
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_state_dict(self) -> dict[str, torch.Tensor]:
        """Convert to flat state_dict for serialization."""
        state_dict = {}

        for colony_id in range(7):
            prefix = f"colony_{colony_id}"

            if colony_id in self.hidden_states:
                state_dict[f"{prefix}_hidden"] = self.hidden_states[colony_id]
            if colony_id in self.stochastic_states:
                state_dict[f"{prefix}_stochastic"] = self.stochastic_states[colony_id]
            if colony_id in self.e8_embeddings:
                state_dict[f"{prefix}_e8"] = self.e8_embeddings[colony_id]

            # Optional tensors
            if colony_id in self.attention_weights:
                state_dict[f"{prefix}_attention"] = self.attention_weights[colony_id]
            if colony_id in self.messages:
                state_dict[f"{prefix}_messages"] = self.messages[colony_id]
            if colony_id in self.loop_states:
                state_dict[f"{prefix}_loop"] = self.loop_states[colony_id]
            if colony_id in self.fixed_points:
                state_dict[f"{prefix}_fixed_point"] = self.fixed_points[colony_id]

        return state_dict

    @classmethod
    def from_state_dict(
        cls,
        state_dict: dict[str, torch.Tensor],
        metadata: dict[str, Any],
    ) -> ColonyStateSnapshot:
        """Construct from flat state_dict."""
        hidden_states = {}
        stochastic_states = {}
        e8_embeddings = {}
        attention_weights = {}
        messages = {}
        loop_states = {}
        fixed_points = {}

        for colony_id in range(7):
            prefix = f"colony_{colony_id}"

            if f"{prefix}_hidden" in state_dict:
                hidden_states[colony_id] = state_dict[f"{prefix}_hidden"]
            if f"{prefix}_stochastic" in state_dict:
                stochastic_states[colony_id] = state_dict[f"{prefix}_stochastic"]
            if f"{prefix}_e8" in state_dict:
                e8_embeddings[colony_id] = state_dict[f"{prefix}_e8"]

            # Optional
            if f"{prefix}_attention" in state_dict:
                attention_weights[colony_id] = state_dict[f"{prefix}_attention"]
            if f"{prefix}_messages" in state_dict:
                messages[colony_id] = state_dict[f"{prefix}_messages"]
            if f"{prefix}_loop" in state_dict:
                loop_states[colony_id] = state_dict[f"{prefix}_loop"]
            if f"{prefix}_fixed_point" in state_dict:
                fixed_points[colony_id] = state_dict[f"{prefix}_fixed_point"]

        return cls(
            hidden_states=hidden_states,
            stochastic_states=stochastic_states,
            e8_embeddings=e8_embeddings,
            attention_weights=attention_weights,
            messages=messages,
            loop_states=loop_states,
            fixed_points=fixed_points,
            timestep=metadata.get("timestep", 0),
            active_colonies=metadata.get("active_colonies", list(range(7))),
            metadata=metadata.get("extra", {}),
        )


class ColonyStateStore:
    """Store for colony state snapshots."""

    def __init__(
        self,
        backend: StorageBackend,
        compression: CompressionType = CompressionType.ZSTD,
    ):
        """Initialize colony state store.

        Args:
            backend: Storage backend
            compression: Compression algorithm
        """
        self.backend = backend
        self.tensor_serializer = CompositeSerializer(
            base=TensorSerializer(use_safetensors=True),
            compression=compression,
        )
        self.json_serializer = JSONSerializer(indent=2)

    async def save_snapshot(
        self,
        snapshot_id: str,
        snapshot: ColonyStateSnapshot,
    ) -> str:
        """Save colony state snapshot.

        Args:
            snapshot_id: Identifier for snapshot
            snapshot: Colony state snapshot

        Returns:
            Version ID from backend
        """
        # Convert to state_dict
        state_dict = snapshot.to_state_dict()

        # Serialize tensors
        serialized = self.tensor_serializer.serialize(
            state_dict,
            metadata={
                "timestep": snapshot.timestep,
                "active_colonies": snapshot.active_colonies,
                "extra": snapshot.metadata,
                "timestamp": time.time(),
            },
        )

        # Save to backend
        key = f"colonies/{snapshot_id}"
        version = await self.backend.save(
            key=key,
            data=serialized.data,
            metadata=serialized.to_dict(),
        )

        return version

    async def load_snapshot(
        self,
        snapshot_id: str,
        version: str | None = None,
    ) -> ColonyStateSnapshot:
        """Load colony state snapshot.

        Args:
            snapshot_id: Identifier for snapshot
            version: Optional version ID

        Returns:
            Colony state snapshot
        """
        # Load from backend
        key = f"colonies/{snapshot_id}"
        data, metadata = await self.backend.load(key, version)

        # Deserialize
        from kagami.core.persistence.serializers import SerializedState

        serialized = SerializedState.from_dict(data, metadata)
        state_dict = self.tensor_serializer.deserialize(serialized)

        # Reconstruct snapshot
        return ColonyStateSnapshot.from_state_dict(
            state_dict,
            serialized.metadata,
        )

    async def list_snapshots(self, limit: int | None = None) -> list[str]:
        """List all colony snapshots.

        Args:
            limit: Maximum number of snapshots

        Returns:
            List of snapshot IDs
        """
        keys = await self.backend.list_keys(prefix="colonies/", limit=limit)
        # Remove prefix
        return [k.replace("colonies/", "") for k in keys]

    async def delete_snapshot(
        self,
        snapshot_id: str,
        version: str | None = None,
    ) -> bool:
        """Delete colony snapshot.

        Args:
            snapshot_id: Identifier for snapshot
            version: Optional version ID

        Returns:
            True if deleted
        """
        key = f"colonies/{snapshot_id}"
        return await self.backend.delete(key, version)

    async def get_snapshot_metadata(
        self,
        snapshot_id: str,
        version: str | None = None,
    ) -> dict[str, Any]:
        """Get snapshot metadata without loading full state.

        Args:
            snapshot_id: Identifier for snapshot
            version: Optional version ID

        Returns:
            Metadata dictionary
        """
        key = f"colonies/{snapshot_id}"
        return await self.backend.get_metadata(key, version)
