"""Core Types for Unified Agents.

Essential dataclasses and enums extracted from legacy_bridge.
These are the stable types that should continue to be used.

Created: December 7, 2025 (extracted from legacy_bridge.py)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from kagami_math.catastrophe_constants import (
    CATASTROPHE_NAMES,
    COLONY_CATASTROPHE_MAP,
)

# =============================================================================
# TASK
# =============================================================================


@dataclass
class Task:
    """A task to be executed by an agent."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_type: str = "default"
    description: str = ""
    params: dict[str, Any] = field(default_factory=dict[str, Any])
    context: dict[str, Any] = field(default_factory=dict[str, Any])
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    deadline: float | None = None

    @property
    def action(self) -> str:
        """Alias for task_type (backwards compatibility)."""
        return self.task_type

    @property
    def is_expired(self) -> bool:
        if self.deadline is None:
            return False
        return time.time() > self.deadline


# =============================================================================
# GOAL
# =============================================================================


@dataclass
class Goal:
    """A goal to be pursued by the organism."""

    goal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    priority: int = 0
    domain: str = "general"
    params: dict[str, Any] = field(default_factory=dict[str, Any])
    created_at: float = field(default_factory=time.time)
    completed: bool = False

    def mark_complete(self) -> None:
        self.completed = True


# =============================================================================
# EXECUTION MODE
# =============================================================================


class ExecutionMode(str, Enum):
    """Execution modes."""

    NORMAL = "normal"
    FAST = "fast"
    CAREFUL = "careful"
    CREATIVE = "creative"


# =============================================================================
# CATASTROPHE POTENTIAL
# =============================================================================


class CatastrophePotential(str, Enum):
    """Catastrophe types for each domain."""

    FOLD = CATASTROPHE_NAMES[0]
    CUSP = CATASTROPHE_NAMES[1]
    SWALLOWTAIL = CATASTROPHE_NAMES[2]
    BUTTERFLY = CATASTROPHE_NAMES[3]
    HYPERBOLIC = CATASTROPHE_NAMES[4]
    ELLIPTIC = CATASTROPHE_NAMES[5]
    PARABOLIC = CATASTROPHE_NAMES[6]


# =============================================================================
# AGENT DNA
# =============================================================================


@dataclass
class AgentDNA:
    """Agent DNA encoding capabilities and personality."""

    from kagami.core.unified_agents.colony_constants import DomainType

    domain: DomainType | None = None
    capabilities: set[str] = field(default_factory=set[Any])
    # Personality vector starts at 0.0 - evolves through actual behavior, not fake 0.5
    personality_vector: list[float] = field(default_factory=lambda: [0.0] * 8)
    execution_mode: ExecutionMode = ExecutionMode.NORMAL

    def __post_init__(self) -> None:
        from kagami.core.unified_agents.colony_constants import DomainType

        if self.domain is None:
            self.domain = DomainType.FORGE

    @property
    def catastrophe(self) -> CatastrophePotential:
        cat_name = COLONY_CATASTROPHE_MAP.get(self.domain.value, CATASTROPHE_NAMES[0])  # type: ignore[union-attr]
        return CatastrophePotential(cat_name)


# Alias
DNA = AgentDNA


# =============================================================================
# OCTONION MAPPINGS
# =============================================================================

from kagami.core.unified_agents.colony_constants import DomainType

DOMAIN_TO_OCTONION = {
    DomainType.SPARK: 1,
    DomainType.FORGE: 2,
    DomainType.FLOW: 3,
    DomainType.NEXUS: 4,
    DomainType.BEACON: 5,
    DomainType.GROVE: 6,
    DomainType.CRYSTAL: 7,
}


# =============================================================================
# REGISTRY DEFINITIONS
# =============================================================================

CANONICAL_AGENTS_REGISTRY = {
    "spark": {
        "description": "Creative/divergent thinking",
        "capabilities": ["create", "generate", "brainstorm"],
    },
    "forge": {
        "description": "Building/implementation",
        "capabilities": ["build", "implement", "code"],
    },
    "flow": {"description": "Recovery/maintenance", "capabilities": ["fix", "repair", "maintain"]},
    "nexus": {
        "description": "Integration/connection",
        "capabilities": ["integrate", "connect", "merge"],
    },
    "beacon": {
        "description": "Planning/strategy",
        "capabilities": ["plan", "strategize", "organize"],
    },
    "grove": {
        "description": "Research/exploration",
        "capabilities": ["research", "document", "explore"],
    },
    "crystal": {
        "description": "Testing/verification",
        "capabilities": ["test", "verify", "validate"],
    },
}

AGENT_PERSONALITIES = {
    "spark": "creative and divergent",
    "forge": "focused and productive",
    "flow": "adaptive and resilient",
    "nexus": "integrative and connecting",
    "beacon": "strategic and guiding",
    "grove": "exploratory and nurturing",
    "crystal": "rigorous and precise",
}

ACTION_TO_APP_MAP = {
    "create": "spark",
    "generate": "spark",
    "build": "forge",
    "implement": "forge",
    "code": "forge",
    "fix": "flow",
    "repair": "flow",
    "integrate": "nexus",
    "connect": "nexus",
    "plan": "beacon",
    "research": "grove",
    "test": "crystal",
    "verify": "crystal",
    # Smart Home actions (December 29, 2025) - routed to Nexus (integration)
    "lights": "nexus",
    "shades": "nexus",
    "blinds": "nexus",
    "temperature": "nexus",
    "hvac": "nexus",
    "lock": "nexus",
    "unlock": "nexus",
    "scene": "nexus",
    "goodnight": "nexus",
    "movie_mode": "nexus",
    "announce": "nexus",
    "home": "nexus",
}


# =============================================================================
# APP REGISTRY (Legacy Compatibility)
# =============================================================================

APP_MATURITY: dict[str, str] = {
    "spark": "stable",
    "forge": "stable",
    "flow": "stable",
    "nexus": "stable",
    "beacon": "stable",
    "grove": "stable",
    "crystal": "stable",
}

APP_METADATA: dict[str, dict[str, Any]] = {
    name: {
        "name": name.title(),
        "description": info["description"],
        "capabilities": info["capabilities"],
        "maturity": APP_MATURITY.get(name, "experimental"),
        "personality": AGENT_PERSONALITIES.get(name, ""),
    }
    for name, info in CANONICAL_AGENTS_REGISTRY.items()
}

APP_REGISTRY_V2: dict[str, dict[str, Any]] = APP_METADATA


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ACTION_TO_APP_MAP",
    "AGENT_PERSONALITIES",
    "APP_MATURITY",
    "APP_METADATA",
    "APP_REGISTRY_V2",
    "CANONICAL_AGENTS_REGISTRY",
    "DNA",
    "DOMAIN_TO_OCTONION",
    "AgentDNA",
    "CatastrophePotential",
    "ExecutionMode",
    "Goal",
    "Task",
]
