"""World model checkpoint persistence.

CREATED: December 28, 2025
PURPOSE: Save/load RSSM parameters, trajectory cache, training state.
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
    TensorSerializer,
)


@dataclass
class WorldModelCheckpoint:
    """World model checkpoint."""

    # Model parameters
    model_state_dict: dict[str, torch.Tensor]

    # Optimizer state (optional)
    optimizer_state_dict: dict[str, Any] | None = None

    # Trajectory cache (E8 quantized)
    trajectory_cache: dict[str, torch.Tensor] = field(default_factory=dict[str, Any])

    # Training metadata
    epoch: int = 0
    step: int = 0
    loss: float = 0.0
    metrics: dict[str, float] = field(default_factory=dict[str, Any])

    # Version info
    model_version: str = "1.0.0"
    config: dict[str, Any] = field(default_factory=dict[str, Any])
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_state_dict(self) -> dict[str, torch.Tensor]:
        """Flatten to state_dict."""
        state = {"model": self.model_state_dict}

        if self.optimizer_state_dict:
            # Convert optimizer state to tensors
            pass  # Handle separately

        # Add trajectory cache
        for key, tensor in self.trajectory_cache.items():
            state[f"cache_{key}"] = tensor

        return state


class WorldModelStore:
    """Store for world model checkpoints."""

    def __init__(
        self,
        backend: StorageBackend,
        compression: CompressionType = CompressionType.ZSTD,
    ):
        self.backend = backend
        self.serializer = CompositeSerializer(
            base=TensorSerializer(use_safetensors=True),
            compression=compression,
        )

    async def save_checkpoint(
        self,
        checkpoint_id: str,
        checkpoint: WorldModelCheckpoint,
    ) -> str:
        """Save world model checkpoint."""
        state_dict = checkpoint.to_state_dict()

        serialized = self.serializer.serialize(
            state_dict,
            metadata={
                "epoch": checkpoint.epoch,
                "step": checkpoint.step,
                "loss": checkpoint.loss,
                "metrics": checkpoint.metrics,
                "model_version": checkpoint.model_version,
                "config": checkpoint.config,
                "extra": checkpoint.metadata,
                "timestamp": time.time(),
            },
        )

        key = f"world_model/{checkpoint_id}"
        return await self.backend.save(key, serialized.data, serialized.to_dict())

    async def load_checkpoint(
        self,
        checkpoint_id: str,
        version: str | None = None,
    ) -> WorldModelCheckpoint:
        """Load world model checkpoint."""
        key = f"world_model/{checkpoint_id}"
        data, metadata = await self.backend.load(key, version)

        from kagami.core.persistence.serializers import SerializedState

        serialized = SerializedState.from_dict(data, metadata)
        state_dict = self.serializer.deserialize(serialized)

        # Extract model state
        model_state = {
            k.replace("model.", ""): v for k, v in state_dict.items() if k.startswith("model.")
        }

        # Extract trajectory cache
        cache = {
            k.replace("cache_", ""): v for k, v in state_dict.items() if k.startswith("cache_")
        }

        return WorldModelCheckpoint(
            model_state_dict=model_state,
            trajectory_cache=cache,
            epoch=serialized.metadata.get("epoch", 0),
            step=serialized.metadata.get("step", 0),
            loss=serialized.metadata.get("loss", 0.0),
            metrics=serialized.metadata.get("metrics", {}),
            model_version=serialized.metadata.get("model_version", "1.0.0"),
            config=serialized.metadata.get("config", {}),
            metadata=serialized.metadata.get("extra", {}),
        )

    async def list_checkpoints(self, limit: int | None = None) -> list[str]:
        """List all checkpoints."""
        keys = await self.backend.list_keys(prefix="world_model/", limit=limit)
        return [k.replace("world_model/", "") for k in keys]

    async def delete_checkpoint(self, checkpoint_id: str, version: str | None = None) -> bool:
        """Delete checkpoint."""
        return await self.backend.delete(f"world_model/{checkpoint_id}", version)
