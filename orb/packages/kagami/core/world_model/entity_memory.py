"""EntityMemory - Key-Value Storage with Partial Updates.

LeCun (2022) Section 4.4:
"The short-term memory stores relevant information about the past, present,
and future state of the world... The state of the world changes relatively
slowly, hence the short-term memory may be sparse and only need to contain
updates to the world state."

Key insight: Instead of storing complete world states, store ENTITIES as
key-value pairs that can be partially updated. This is:
- Memory efficient (only update what changed)
- Compositional (can query individual entities)
- Supports incremental updates

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                      ENTITY MEMORY                              │
    │  ┌─────────────────────────────────────────────────────────────┐│
    │  │  Entity Registry: key → (embedding, attributes, timestamp)  ││
    │  │                                                              ││
    │  │  Update: partial_state → diff → apply to relevant entities  ││
    │  │                                                              ││
    │  │  Query: attention over entity embeddings → aggregate         ││
    │  │                                                              ││
    │  │  Decay: forgetting via recency-weighted pruning              ││
    │  └─────────────────────────────────────────────────────────────┘│
    └─────────────────────────────────────────────────────────────────┘

Created: December 6, 2025
Reference: LeCun (2022) Section 4.4 "Short-Term Memory"
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


@dataclass
class EntityMemoryConfig:
    """Configuration for EntityMemory."""

    # Dimensions
    entity_dim: int = 128  # Entity embedding dimension
    key_dim: int = 64  # Key dimension for attention
    max_entities: int = 1024  # Maximum entities to track

    # Architecture
    n_heads: int = 4  # Attention heads for query
    dropout: float = 0.1

    # Memory management
    decay_rate: float = 0.01  # Per-step forgetting rate
    prune_threshold: float = 0.1  # Remove entities below this relevance
    update_lr: float = 0.1  # Learning rate for partial updates


@dataclass
class Entity:
    """A single entity in memory.

    Entities are the atomic units of world state representation.
    Each entity has:
    - key: Identifier (string or hash)
    - embedding: Learned representation
    - attributes: Dictionary of properties
    - timestamp: When last updated
    - relevance: How important (decays over time)
    """

    key: str
    embedding: torch.Tensor  # [entity_dim]
    attributes: dict[str, Any] = field(default_factory=dict[str, Any])
    timestamp: float = field(default_factory=time.time)
    relevance: float = 1.0

    def to_tensor_dict(self) -> dict[str, torch.Tensor]:
        """Convert to tensor dict[str, Any] for batching."""
        return {
            "embedding": self.embedding,
            "relevance": torch.tensor([self.relevance]),
            "timestamp": torch.tensor([self.timestamp]),
        }


class EntityEncoder(nn.Module):
    """Encode raw observations into entity representations."""

    def __init__(self, config: EntityMemoryConfig, input_dim: int = 512):
        super().__init__()
        self.config = config

        self.encoder = nn.Sequential(
            nn.Linear(input_dim, config.entity_dim * 2),
            nn.LayerNorm(config.entity_dim * 2),
            nn.GELU(),
            nn.Linear(config.entity_dim * 2, config.entity_dim),
        )

        # Key projection for attention
        self.key_proj = nn.Linear(config.entity_dim, config.key_dim)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Encode observation into entity embedding and key.

        Args:
            x: [B, input_dim] raw observation

        Returns:
            embedding: [B, entity_dim] entity embedding
            key: [B, key_dim] attention key
        """
        embedding = self.encoder(x)
        key = self.key_proj(embedding)
        return embedding, key


class EntityUpdater(nn.Module):
    """Apply partial updates to entity embeddings.

    LeCun: "The short-term memory may be sparse and only need to
    contain updates to the world state."
    """

    def __init__(self, config: EntityMemoryConfig):
        super().__init__()
        self.config = config

        # Gate determines how much of update to apply
        self.gate = nn.Sequential(
            nn.Linear(config.entity_dim * 2, config.entity_dim),
            nn.Sigmoid(),
        )

        # Transform update before applying
        self.update_transform = nn.Sequential(
            nn.Linear(config.entity_dim, config.entity_dim),
            nn.LayerNorm(config.entity_dim),
            nn.GELU(),
            nn.Linear(config.entity_dim, config.entity_dim),
        )

    def forward(
        self,
        current: torch.Tensor,
        update: torch.Tensor,
    ) -> torch.Tensor:
        """Apply partial update to entity embedding.

        Args:
            current: [B, entity_dim] current entity state
            update: [B, entity_dim] proposed update

        Returns:
            [B, entity_dim] updated entity state
        """
        # Compute gate (how much to update)
        gate_input = torch.cat([current, update], dim=-1)
        gate = self.gate(gate_input)

        # Transform update
        transformed = self.update_transform(update)

        # Gated update
        return current + gate * transformed


class EntityQueryAttention(nn.Module):
    """Query entity memory using attention."""

    def __init__(self, config: EntityMemoryConfig):
        super().__init__()
        self.config = config

        # Multi-head attention
        self.attention = nn.MultiheadAttention(
            embed_dim=config.entity_dim,
            num_heads=config.n_heads,
            dropout=config.dropout,
            batch_first=True,
        )

        # Query projection
        self.query_proj = nn.Linear(config.key_dim, config.entity_dim)

    def forward(
        self,
        query: torch.Tensor,
        entities: torch.Tensor,
        relevances: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Query entity memory.

        Args:
            query: [B, key_dim] query vector
            entities: [B, N, entity_dim] entity embeddings
            relevances: [B, N] entity relevance scores (optional)

        Returns:
            result: [B, entity_dim] aggregated entity information
            weights: [B, N] attention weights
        """
        # Project query
        q = self.query_proj(query).unsqueeze(1)  # [B, 1, entity_dim]

        # Apply relevance as attention bias if provided
        attn_mask = None
        if relevances is not None:
            # Low relevance → large negative bias
            attn_mask = -1e9 * (relevances < self.config.prune_threshold).float()

        # Attention
        result, weights = self.attention(
            q,
            entities,
            entities,
            attn_mask=attn_mask,
        )

        return result.squeeze(1), weights.squeeze(1)


class EntityMemory(nn.Module):
    """Key-value entity memory with partial updates.

    Usage:
        memory = EntityMemory()

        # Add entities from observation
        memory.update_from_observation(obs, entity_keys)

        # Partial update (only what changed)
        memory.partial_update(entity_key, delta_embedding)

        # Query relevant entities
        result = memory.query(query_embedding)

        # Decay and prune
        memory.step()
    """

    def __init__(self, config: EntityMemoryConfig | None = None, input_dim: int = 512):
        super().__init__()
        self.config = config or EntityMemoryConfig()

        # Components
        self.encoder = EntityEncoder(self.config, input_dim)
        self.updater = EntityUpdater(self.config)
        self.query_attention = EntityQueryAttention(self.config)

        # Entity storage (as Buffers for persistence)
        # Note: register_buffer returns None, so we register then access via attribute
        self.register_buffer(
            "entity_embeddings",
            torch.zeros(self.config.max_entities, self.config.entity_dim),
        )
        self.register_buffer(
            "entity_keys",
            torch.zeros(self.config.max_entities, self.config.key_dim),
        )
        self.register_buffer(
            "entity_relevances",
            torch.zeros(self.config.max_entities),
        )
        self.register_buffer(
            "entity_timestamps",
            torch.zeros(self.config.max_entities),
        )

        # Type hints for buffers (mypy doesn't understand register_buffer)
        self.entity_embeddings: torch.Tensor
        self.entity_keys: torch.Tensor
        self.entity_relevances: torch.Tensor
        self.entity_timestamps: torch.Tensor

        # Bookkeeping
        self.entity_key_map: dict[str, int] = {}  # key → index
        self.n_entities = 0

        logger.info(
            f"EntityMemory: max_entities={self.config.max_entities}, "
            f"entity_dim={self.config.entity_dim}"
        )

    def _get_or_create_slot(self, key: str) -> int:
        """Get existing slot or create new one for entity key."""
        if key in self.entity_key_map:
            return self.entity_key_map[key]

        # Find slot (reuse low-relevance if full)
        if self.n_entities < self.config.max_entities:
            slot = self.n_entities
            self.n_entities += 1
        else:
            # Prune lowest relevance entity
            slot = int(self.entity_relevances.argmin())
            old_key = None
            for k, v in self.entity_key_map.items():
                if v == slot:
                    old_key = k
                    break
            if old_key:
                del self.entity_key_map[old_key]

        self.entity_key_map[key] = slot
        return slot

    def add_entity(
        self,
        key: str,
        embedding: torch.Tensor,
        key_embedding: torch.Tensor | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Add or update an entity.

        Args:
            key: Entity identifier
            embedding: [entity_dim] entity embedding
            key_embedding: [key_dim] attention key (optional)
            attributes: Entity attributes dict[str, Any] (optional)
        """
        slot = self._get_or_create_slot(key)

        self.entity_embeddings[slot] = embedding.detach()
        if key_embedding is not None:
            self.entity_keys[slot] = key_embedding.detach()
        self.entity_relevances[slot] = 1.0
        self.entity_timestamps[slot] = time.time()

    def update_entity(
        self,
        key: str,
        delta: torch.Tensor,
    ) -> bool:
        """Apply partial update to existing entity.

        Args:
            key: Entity identifier
            delta: [entity_dim] update to apply

        Returns:
            True if entity existed and was updated
        """
        if key not in self.entity_key_map:
            return False

        slot = self.entity_key_map[key]
        current = self.entity_embeddings[slot].unsqueeze(0)
        delta = delta.unsqueeze(0)

        updated = self.updater(current, delta)
        self.entity_embeddings[slot] = updated.squeeze(0)
        self.entity_relevances[slot] = 1.0  # Reset relevance
        self.entity_timestamps[slot] = time.time()

        return True

    def update_from_observation(
        self,
        observation: torch.Tensor,
        entity_keys: list[str],
    ) -> None:
        """Update entities from raw observation.

        Args:
            observation: [B, input_dim] raw observations
            entity_keys: List of entity keys (one per batch element)
        """
        embeddings, keys = self.encoder(observation)

        for i, key in enumerate(entity_keys):
            self.add_entity(key, embeddings[i], keys[i])

    def query(
        self,
        query: torch.Tensor,
        top_k: int | None = None,
    ) -> tuple[torch.Tensor, dict[str, float]]:
        """Query entity memory.

        Args:
            query: [B, key_dim] query vector
            top_k: Return only top-k entities (optional)

        Returns:
            result: [B, entity_dim] aggregated entity information
            attention_weights: Dict mapping entity keys to weights
        """
        if self.n_entities == 0:
            return torch.zeros(
                query.shape[0],
                self.config.entity_dim,
                device=query.device,
            ), {}

        # Get active entities
        active_embeddings = self.entity_embeddings[: self.n_entities].unsqueeze(0)
        active_relevances = self.entity_relevances[: self.n_entities].unsqueeze(0)

        # Expand for batch
        batch_size = query.shape[0]
        active_embeddings = active_embeddings.expand(batch_size, -1, -1)
        active_relevances = active_relevances.expand(batch_size, -1)

        # Query
        result, weights = self.query_attention(query, active_embeddings, active_relevances)

        # Build weight dict[str, Any]
        weight_dict = {}
        avg_weights = weights.mean(dim=0).detach()
        for key, slot in self.entity_key_map.items():
            if slot < self.n_entities:
                weight_dict[key] = float(avg_weights[slot])

        return result, weight_dict

    def step(self) -> int:
        """Decay relevances and prune low-relevance entities.

        Returns:
            Number of entities pruned
        """
        # Decay relevances
        self.entity_relevances[: self.n_entities] *= 1 - self.config.decay_rate

        # Count entities below threshold
        below_threshold = (
            (self.entity_relevances[: self.n_entities] < self.config.prune_threshold).sum().item()
        )

        # Note: We don't actually remove entities, just mark them as low relevance
        # They will be overwritten when new entities are added

        return int(below_threshold)

    def get_entity(self, key: str) -> torch.Tensor | None:
        """Get entity embedding by key."""
        if key not in self.entity_key_map:
            return None
        slot = self.entity_key_map[key]
        return self.entity_embeddings[slot]

    def get_all_entities(self) -> tuple[torch.Tensor, list[str]]:
        """Get all active entity embeddings and keys.

        Returns:
            embeddings: [N, entity_dim] all entity embeddings
            keys: List of entity keys
        """
        embeddings = self.entity_embeddings[: self.n_entities]
        keys = []
        for key, slot in sorted(self.entity_key_map.items(), key=lambda x: x[1]):
            if slot < self.n_entities:
                keys.append(key)
        return embeddings, keys

    def clear(self) -> None:
        """Clear all entities."""
        self.entity_embeddings.zero_()
        self.entity_keys.zero_()
        self.entity_relevances.zero_()
        self.entity_timestamps.zero_()
        self.entity_key_map.clear()
        self.n_entities = 0

    def forward(
        self,
        query: torch.Tensor,
        observation: torch.Tensor | None = None,
        entity_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        """Forward pass: optionally update, then query.

        Args:
            query: [B, key_dim] query vector
            observation: [B, input_dim] optional observation to add
            entity_keys: List of entity keys for observation

        Returns:
            Dict with result, attention_weights, n_entities
        """
        # Update if observation provided
        if observation is not None and entity_keys is not None:
            self.update_from_observation(observation, entity_keys)

        # Query
        result, weights = self.query(query)

        return {
            "result": result,
            "attention_weights": weights,
            "n_entities": self.n_entities,
        }


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_entity_memory: EntityMemory | None = None


def get_entity_memory(config: EntityMemoryConfig | None = None) -> EntityMemory:
    """Get or create global EntityMemory."""
    global _entity_memory
    if _entity_memory is None:
        _entity_memory = EntityMemory(config)
        logger.info("Created global EntityMemory")
    return _entity_memory


def reset_entity_memory() -> None:
    """Reset global EntityMemory (for testing)."""
    global _entity_memory
    _entity_memory = None
