"""Agent Knowledge Graph — Property graph-based memory for agents.

Implements a hierarchical knowledge graph with:
- Entities: Nodes with properties and types
- Relations: Edges between entities with properties
- Temporal awareness: All data timestamped
- Scoped storage: page → agent → topic → domain

Research-based design:
- Property Graphs over RDF for intuitiveness and query performance
- Hierarchical indexing (inspired by CogniGraph)
- Time-semantic-relational entities (inspired by MemoriesDB)
- Cross-session persistence via Redis + IndexedDB sync

Colony: Nexus (e4) — Integration
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Storage Scopes
# =============================================================================


class StorageScope(str, Enum):
    """Hierarchical storage scopes for knowledge graph data.

    Scopes from narrowest to broadest:
    - PAGE: Single page view (ephemeral)
    - SESSION: Browser session (sessionStorage)
    - AGENT: Specific agent (persisted)
    - TOPIC: Topic/domain cluster (shared across agents)
    - DOMAIN: Entire domain (global knowledge)
    """

    PAGE = "page"
    SESSION = "session"
    AGENT = "agent"
    TOPIC = "topic"
    DOMAIN = "domain"


# =============================================================================
# Entity Types
# =============================================================================


class EntityType(str, Enum):
    """Core entity types for the knowledge graph."""

    # Core entities
    CONCEPT = "concept"  # Abstract ideas, topics
    ENTITY = "entity"  # Named things (people, places, objects)
    EVENT = "event"  # Temporal occurrences
    ACTION = "action"  # User or system actions
    STATE = "state"  # System/UI states

    # Agent-specific
    INTENT = "intent"  # User intents
    RESPONSE = "response"  # Agent responses
    SECRET = "secret"  # Discovered secrets
    PREFERENCE = "preference"  # User preferences

    # Temporal
    MEMORY = "memory"  # Episodic memories
    FACT = "fact"  # Learned facts
    PATTERN = "pattern"  # Behavioral patterns


class RelationType(str, Enum):
    """Core relation types for the knowledge graph."""

    # Structural
    IS_A = "is_a"  # Type hierarchy
    PART_OF = "part_of"  # Composition
    RELATED_TO = "related_to"  # Generic relation

    # Temporal
    PRECEDED_BY = "preceded_by"  # Temporal ordering
    FOLLOWED_BY = "followed_by"  # Temporal ordering
    CAUSED = "caused"  # Causal relation
    TRIGGERED = "triggered"  # Event triggers

    # Agent-specific
    ASKED_ABOUT = "asked_about"  # User queries
    RESPONDED_WITH = "responded_with"  # Agent responses
    DISCOVERED = "discovered"  # Secret discovery
    PREFERS = "prefers"  # User preferences
    INTERACTED_WITH = "interacted_with"  # Interactions

    # Learning
    LEARNED_FROM = "learned_from"  # Learning source
    REINFORCED_BY = "reinforced_by"  # Reinforcement


# =============================================================================
# Knowledge Graph Entities
# =============================================================================


@dataclass
class Entity:
    """A node in the knowledge graph.

    Attributes:
        id: Unique entity identifier.
        type: Entity type.
        name: Human-readable name.
        properties: Key-value properties.
        scope: Storage scope.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        confidence: Confidence score (0-1).
        source: Source of the entity (agent_id, user, system).
    """

    id: str
    type: EntityType
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    scope: StorageScope = StorageScope.AGENT
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    confidence: float = 1.0
    source: str = "system"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "properties": self.properties,
            "scope": self.scope.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "confidence": self.confidence,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Entity:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            type=EntityType(data["type"]),
            name=data["name"],
            properties=data.get("properties", {}),
            scope=StorageScope(data.get("scope", "agent")),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            confidence=data.get("confidence", 1.0),
            source=data.get("source", "system"),
        )

    def update(self, properties: dict[str, Any]) -> None:
        """Update entity properties."""
        self.properties.update(properties)
        self.updated_at = time.time()


@dataclass
class Relation:
    """An edge in the knowledge graph.

    Attributes:
        id: Unique relation identifier.
        type: Relation type.
        source_id: Source entity ID.
        target_id: Target entity ID.
        properties: Edge properties.
        weight: Relation strength (0-1).
        created_at: Creation timestamp.
        context: Context in which relation was created.
    """

    id: str
    type: RelationType
    source_id: str
    target_id: str
    properties: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    created_at: float = field(default_factory=time.time)
    context: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "properties": self.properties,
            "weight": self.weight,
            "created_at": self.created_at,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Relation:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            type=RelationType(data["type"]),
            source_id=data["source_id"],
            target_id=data["target_id"],
            properties=data.get("properties", {}),
            weight=data.get("weight", 1.0),
            created_at=data.get("created_at", time.time()),
            context=data.get("context", ""),
        )


# =============================================================================
# Knowledge Graph
# =============================================================================


@dataclass
class KnowledgeGraph:
    """Property graph-based knowledge graph for agent memory.

    Provides:
    - Entity CRUD operations
    - Relation management
    - Graph traversal
    - Scoped queries
    - Temporal queries
    - Pattern extraction

    Example:
        ```python
        kg = KnowledgeGraph(agent_id="obs-studio")

        # Add entities
        user = kg.add_entity(EntityType.ENTITY, "Tim", {"role": "user"})
        scene = kg.add_entity(EntityType.CONCEPT, "Cooking Scene", {"type": "obs_scene"})

        # Add relation
        kg.add_relation(RelationType.PREFERS, user.id, scene.id)

        # Query
        preferences = kg.get_related(user.id, RelationType.PREFERS)
        ```
    """

    agent_id: str
    entities: dict[str, Entity] = field(default_factory=dict)
    relations: dict[str, Relation] = field(default_factory=dict)
    _entity_index: dict[str, set[str]] = field(default_factory=dict)  # type -> entity_ids
    _relation_index: dict[str, set[str]] = field(default_factory=dict)  # source_id -> relation_ids

    def add_entity(
        self,
        entity_type: EntityType,
        name: str,
        properties: dict[str, Any] | None = None,
        scope: StorageScope = StorageScope.AGENT,
        entity_id: str | None = None,
    ) -> Entity:
        """Add an entity to the graph.

        Args:
            entity_type: Type of entity.
            name: Entity name.
            properties: Entity properties.
            scope: Storage scope.
            entity_id: Optional specific ID.

        Returns:
            Created entity.
        """
        # Generate ID if not provided
        if not entity_id:
            entity_id = self._generate_entity_id(entity_type, name)

        # Check if exists and update
        if entity_id in self.entities:
            existing = self.entities[entity_id]
            if properties:
                existing.update(properties)
            return existing

        # Create new entity
        entity = Entity(
            id=entity_id,
            type=entity_type,
            name=name,
            properties=properties or {},
            scope=scope,
            source=self.agent_id,
        )

        self.entities[entity_id] = entity

        # Update index
        if entity_type.value not in self._entity_index:
            self._entity_index[entity_type.value] = set()
        self._entity_index[entity_type.value].add(entity_id)

        return entity

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID."""
        return self.entities.get(entity_id)

    def get_entities_by_type(self, entity_type: EntityType) -> list[Entity]:
        """Get all entities of a type."""
        entity_ids = self._entity_index.get(entity_type.value, set())
        return [self.entities[eid] for eid in entity_ids if eid in self.entities]

    def remove_entity(self, entity_id: str) -> bool:
        """Remove entity and its relations."""
        if entity_id not in self.entities:
            return False

        entity = self.entities.pop(entity_id)

        # Remove from type index
        if entity.type.value in self._entity_index:
            self._entity_index[entity.type.value].discard(entity_id)

        # Remove relations involving this entity
        relations_to_remove = [
            rid
            for rid, rel in self.relations.items()
            if rel.source_id == entity_id or rel.target_id == entity_id
        ]
        for rid in relations_to_remove:
            self.remove_relation(rid)

        return True

    def add_relation(
        self,
        relation_type: RelationType,
        source_id: str,
        target_id: str,
        properties: dict[str, Any] | None = None,
        weight: float = 1.0,
        context: str = "",
    ) -> Relation | None:
        """Add a relation between entities.

        Args:
            relation_type: Type of relation.
            source_id: Source entity ID.
            target_id: Target entity ID.
            properties: Relation properties.
            weight: Relation strength.
            context: Context of relation.

        Returns:
            Created relation or None if entities don't exist.
        """
        # Verify entities exist
        if source_id not in self.entities or target_id not in self.entities:
            logger.warning("Cannot create relation: entities not found")
            return None

        # Generate relation ID
        relation_id = f"{source_id}:{relation_type.value}:{target_id}"

        # Check if exists and update weight
        if relation_id in self.relations:
            existing = self.relations[relation_id]
            existing.weight = min(1.0, existing.weight + weight * 0.1)  # Reinforce
            return existing

        # Create new relation
        relation = Relation(
            id=relation_id,
            type=relation_type,
            source_id=source_id,
            target_id=target_id,
            properties=properties or {},
            weight=weight,
            context=context,
        )

        self.relations[relation_id] = relation

        # Update index
        if source_id not in self._relation_index:
            self._relation_index[source_id] = set()
        self._relation_index[source_id].add(relation_id)

        return relation

    def get_relation(self, relation_id: str) -> Relation | None:
        """Get relation by ID."""
        return self.relations.get(relation_id)

    def remove_relation(self, relation_id: str) -> bool:
        """Remove a relation."""
        if relation_id not in self.relations:
            return False

        relation = self.relations.pop(relation_id)

        # Remove from index
        if relation.source_id in self._relation_index:
            self._relation_index[relation.source_id].discard(relation_id)

        return True

    def get_related(
        self,
        entity_id: str,
        relation_type: RelationType | None = None,
        direction: str = "outgoing",
    ) -> list[tuple[Entity, Relation]]:
        """Get entities related to a given entity.

        Args:
            entity_id: Source entity ID.
            relation_type: Optional filter by relation type.
            direction: "outgoing", "incoming", or "both".

        Returns:
            List of (related_entity, relation) tuples.
        """
        results = []

        if direction in ("outgoing", "both"):
            relation_ids = self._relation_index.get(entity_id, set())
            for rid in relation_ids:
                rel = self.relations.get(rid)
                if rel and (relation_type is None or rel.type == relation_type):
                    target = self.entities.get(rel.target_id)
                    if target:
                        results.append((target, rel))

        if direction in ("incoming", "both"):
            for rel in self.relations.values():
                if rel.target_id == entity_id:
                    if relation_type is None or rel.type == relation_type:
                        source = self.entities.get(rel.source_id)
                        if source:
                            results.append((source, rel))

        return results

    def query(
        self,
        entity_type: EntityType | None = None,
        scope: StorageScope | None = None,
        min_confidence: float = 0.0,
        since: float | None = None,
        properties: dict[str, Any] | None = None,
    ) -> list[Entity]:
        """Query entities with filters.

        Args:
            entity_type: Filter by type.
            scope: Filter by scope.
            min_confidence: Minimum confidence threshold.
            since: Only entities created after this timestamp.
            properties: Property filters (exact match).

        Returns:
            Matching entities.
        """
        results = []

        for entity in self.entities.values():
            # Type filter
            if entity_type and entity.type != entity_type:
                continue

            # Scope filter
            if scope and entity.scope != scope:
                continue

            # Confidence filter
            if entity.confidence < min_confidence:
                continue

            # Temporal filter
            if since and entity.created_at < since:
                continue

            # Property filter
            if properties:
                match = all(entity.properties.get(k) == v for k, v in properties.items())
                if not match:
                    continue

            results.append(entity)

        return results

    def traverse(
        self,
        start_id: str,
        relation_types: list[RelationType] | None = None,
        max_depth: int = 3,
    ) -> list[list[Entity]]:
        """Traverse the graph from a starting entity.

        Args:
            start_id: Starting entity ID.
            relation_types: Allowed relation types (None = all).
            max_depth: Maximum traversal depth.

        Returns:
            List of paths (each path is a list of entities).
        """
        paths = []
        visited = set()

        def dfs(entity_id: str, path: list[Entity], depth: int) -> None:
            if depth > max_depth or entity_id in visited:
                return

            entity = self.entities.get(entity_id)
            if not entity:
                return

            visited.add(entity_id)
            current_path = [*path, entity]

            if len(current_path) > 1:
                paths.append(current_path)

            for related, rel in self.get_related(entity_id):
                if relation_types is None or rel.type in relation_types:
                    dfs(related.id, current_path, depth + 1)

            visited.discard(entity_id)

        dfs(start_id, [], 0)
        return paths

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> list[Entity] | None:
        """Find shortest path between two entities.

        Args:
            source_id: Source entity ID.
            target_id: Target entity ID.
            max_depth: Maximum search depth.

        Returns:
            Path as list of entities, or None if no path found.
        """
        if source_id == target_id:
            entity = self.entities.get(source_id)
            return [entity] if entity else None

        visited = {source_id}
        queue = [(source_id, [self.entities.get(source_id)])]

        while queue:
            current_id, path = queue.pop(0)

            if len(path) > max_depth:
                continue

            for related, _ in self.get_related(current_id, direction="both"):
                if related.id == target_id:
                    return [*path, related]

                if related.id not in visited:
                    visited.add(related.id)
                    queue.append((related.id, [*path, related]))

        return None

    def extract_patterns(self, min_occurrences: int = 2) -> list[dict[str, Any]]:
        """Extract recurring patterns from the graph.

        Identifies common entity-relation-entity patterns.

        Args:
            min_occurrences: Minimum occurrences to be a pattern.

        Returns:
            List of patterns with counts.
        """
        pattern_counts: dict[str, int] = {}

        for relation in self.relations.values():
            source = self.entities.get(relation.source_id)
            target = self.entities.get(relation.target_id)
            if not source or not target:
                continue

            pattern_key = f"{source.type.value}:{relation.type.value}:{target.type.value}"
            pattern_counts[pattern_key] = pattern_counts.get(pattern_key, 0) + 1

        patterns = []
        for pattern_key, count in pattern_counts.items():
            if count >= min_occurrences:
                parts = pattern_key.split(":")
                patterns.append(
                    {
                        "source_type": parts[0],
                        "relation_type": parts[1],
                        "target_type": parts[2],
                        "count": count,
                    }
                )

        return sorted(patterns, key=lambda p: p["count"], reverse=True)

    def to_dict(self) -> dict[str, Any]:
        """Serialize graph to dictionary."""
        return {
            "agent_id": self.agent_id,
            "entities": {eid: e.to_dict() for eid, e in self.entities.items()},
            "relations": {rid: r.to_dict() for rid, r in self.relations.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeGraph:
        """Deserialize graph from dictionary."""
        kg = cls(agent_id=data["agent_id"])

        for entity_data in data.get("entities", {}).values():
            entity = Entity.from_dict(entity_data)
            kg.entities[entity.id] = entity
            if entity.type.value not in kg._entity_index:
                kg._entity_index[entity.type.value] = set()
            kg._entity_index[entity.type.value].add(entity.id)

        for relation_data in data.get("relations", {}).values():
            relation = Relation.from_dict(relation_data)
            kg.relations[relation.id] = relation
            if relation.source_id not in kg._relation_index:
                kg._relation_index[relation.source_id] = set()
            kg._relation_index[relation.source_id].add(relation.id)

        return kg

    def _generate_entity_id(self, entity_type: EntityType, name: str) -> str:
        """Generate deterministic entity ID."""
        key = f"{self.agent_id}:{entity_type.value}:{name.lower()}"
        return hashlib.md5(key.encode()).hexdigest()[:12]


# =============================================================================
# Redis Persistence
# =============================================================================


def kg_redis_key(agent_id: str) -> str:
    """Get Redis key for knowledge graph."""
    return f"agent:{agent_id}:knowledge_graph"


async def save_knowledge_graph(kg: KnowledgeGraph) -> None:
    """Save knowledge graph to Redis."""
    try:
        from kagami.core.agents.learning import get_redis

        redis = await get_redis()
        await redis.set(
            kg_redis_key(kg.agent_id),
            json.dumps(kg.to_dict()),
        )
    except Exception as e:
        logger.error(f"Failed to save knowledge graph: {e}")


async def load_knowledge_graph(agent_id: str) -> KnowledgeGraph:
    """Load knowledge graph from Redis."""
    try:
        from kagami.core.agents.learning import get_redis

        redis = await get_redis()
        data = await redis.get(kg_redis_key(agent_id))

        if data:
            return KnowledgeGraph.from_dict(json.loads(data))
    except Exception as e:
        logger.warning(f"Failed to load knowledge graph: {e}")

    return KnowledgeGraph(agent_id=agent_id)


# =============================================================================
# Schema Extension
# =============================================================================


@dataclass
class KnowledgeGraphConfig:
    """Configuration for agent's knowledge graph.

    Attributes:
        enabled: Whether KG is enabled.
        scope: Default storage scope.
        auto_extract: Auto-extract entities from interactions.
        sync_interval: Sync to Redis interval (seconds).
        max_entities: Maximum entities per agent.
        decay_enabled: Enable confidence decay over time.
        decay_rate: Confidence decay rate per day.
    """

    enabled: bool = True
    scope: StorageScope = StorageScope.AGENT
    auto_extract: bool = True
    sync_interval: int = 60
    max_entities: int = 1000
    decay_enabled: bool = True
    decay_rate: float = 0.01

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "enabled": self.enabled,
            "scope": self.scope.value,
            "auto_extract": self.auto_extract,
            "sync_interval": self.sync_interval,
            "max_entities": self.max_entities,
            "decay_enabled": self.decay_enabled,
            "decay_rate": self.decay_rate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeGraphConfig:
        """Deserialize from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            scope=StorageScope(data.get("scope", "agent")),
            auto_extract=data.get("auto_extract", True),
            sync_interval=data.get("sync_interval", 60),
            max_entities=data.get("max_entities", 1000),
            decay_enabled=data.get("decay_enabled", True),
            decay_rate=data.get("decay_rate", 0.01),
        )


# =============================================================================
# Entity Extraction
# =============================================================================


def extract_entities_from_text(
    text: str,
    agent_id: str,
    context: dict[str, Any] | None = None,
) -> list[Entity]:
    """Extract entities from text using simple NLP patterns.

    Args:
        text: Input text.
        agent_id: Agent ID for entity source.
        context: Additional context.

    Returns:
        List of extracted entities.
    """
    import re

    entities = []
    text_lower = text.lower()

    # Extract concepts (capitalized words)
    concepts = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
    for concept in concepts:
        entities.append(
            Entity(
                id=hashlib.md5(f"{agent_id}:concept:{concept.lower()}".encode()).hexdigest()[:12],
                type=EntityType.CONCEPT,
                name=concept,
                source=agent_id,
            )
        )

    # Extract actions (verb patterns)
    action_patterns = [
        r"(?:start|stop|switch|toggle|turn|set|get|show|hide|play|pause)\s+\w+",
    ]
    for pattern in action_patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            entities.append(
                Entity(
                    id=hashlib.md5(f"{agent_id}:action:{match}".encode()).hexdigest()[:12],
                    type=EntityType.ACTION,
                    name=match,
                    source=agent_id,
                )
            )

    return entities


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    # Core classes
    "Entity",
    "EntityType",
    "KnowledgeGraph",
    "KnowledgeGraphConfig",
    "Relation",
    "RelationType",
    # Enums
    "StorageScope",
    # Extraction
    "extract_entities_from_text",
    "load_knowledge_graph",
    # Persistence
    "save_knowledge_graph",
]
