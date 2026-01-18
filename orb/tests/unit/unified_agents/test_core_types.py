"""Tests for Core Types.

Validates:
1. Task dataclass
2. Goal dataclass
3. ExecutionMode enum
4. AgentDNA dataclass
5. Registry definitions

Created: December 14, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import time

from kagami.core.unified_agents.core_types import (
    # Task and Goal
    Task,
    Goal,
    # Execution
    ExecutionMode,
    CatastrophePotential,
    AgentDNA,
    DNA,
    DOMAIN_TO_OCTONION,
    # Definitions
    CANONICAL_AGENTS_REGISTRY,
    AGENT_PERSONALITIES,
    ACTION_TO_APP_MAP,
    APP_MATURITY,
    APP_METADATA,
    APP_REGISTRY_V2,
)
from kagami.core.unified_agents.colony_constants import DomainType

# =============================================================================
# TEST TASK
# =============================================================================


class TestTask:
    """Test Task dataclass."""

    def test_default_initialization(self) -> None:
        """Task should initialize with defaults."""
        task = Task()

        assert task.task_id is not None
        assert len(task.task_id) == 8
        assert task.task_type == "default"
        assert task.description == ""
        assert task.params == {}
        assert task.priority == 0

    def test_custom_initialization(self) -> None:
        """Task should accept custom values."""
        task = Task(
            task_type="build.feature",
            description="Build new feature",
            params={"language": "python"},
            priority=5,
        )

        assert task.task_type == "build.feature"
        assert task.description == "Build new feature"
        assert task.params["language"] == "python"
        assert task.priority == 5

    def test_action_alias(self) -> None:
        """action should alias task_type."""
        task = Task(task_type="test.function")
        assert task.action == "test.function"

    def test_deadline_expiry(self) -> None:
        """Should detect expired deadlines."""
        past = time.time() - 100
        future = time.time() + 100

        expired_task = Task(deadline=past)
        active_task = Task(deadline=future)
        no_deadline_task = Task()

        assert expired_task.is_expired
        assert not active_task.is_expired
        assert not no_deadline_task.is_expired


# =============================================================================
# TEST GOAL
# =============================================================================


class TestGoal:
    """Test Goal dataclass."""

    def test_default_initialization(self) -> None:
        """Goal should initialize with defaults."""
        goal = Goal()

        assert goal.goal_id is not None
        assert len(goal.goal_id) == 8
        assert goal.description == ""
        assert goal.priority == 0
        assert goal.domain == "general"
        assert goal.completed is False

    def test_custom_initialization(self) -> None:
        """Goal should accept custom values."""
        goal = Goal(
            description="Complete project",
            priority=10,
            domain="forge",
            params={"complexity": "high"},
        )

        assert goal.description == "Complete project"
        assert goal.priority == 10
        assert goal.domain == "forge"
        assert goal.params["complexity"] == "high"

    def test_mark_complete(self) -> None:
        """Should mark goal as complete."""
        goal = Goal()
        assert not goal.completed

        goal.mark_complete()
        assert goal.completed


# =============================================================================
# TEST EXECUTION MODE
# =============================================================================


class TestExecutionMode:
    """Test ExecutionMode enum."""

    def test_all_modes(self) -> None:
        """Should have all execution modes."""
        modes = list(ExecutionMode)

        assert ExecutionMode.NORMAL in modes
        assert ExecutionMode.FAST in modes
        assert ExecutionMode.CAREFUL in modes
        assert ExecutionMode.CREATIVE in modes

    def test_mode_values(self) -> None:
        """Mode values should be strings."""
        assert ExecutionMode.NORMAL.value == "normal"
        assert ExecutionMode.FAST.value == "fast"


# =============================================================================
# TEST CATASTROPHE POTENTIAL
# =============================================================================


class TestCatastrophePotential:
    """Test CatastrophePotential enum."""

    def test_all_catastrophes(self) -> None:
        """Should have all 7 catastrophes."""
        catastrophes = list(CatastrophePotential)
        assert len(catastrophes) == 7

    def test_catastrophe_names(self) -> None:
        """Catastrophe values should match names."""
        assert CatastrophePotential.FOLD.value == "fold"
        assert CatastrophePotential.CUSP.value == "cusp"
        assert CatastrophePotential.PARABOLIC.value == "parabolic"


# =============================================================================
# TEST AGENT DNA
# =============================================================================


class TestAgentDNA:
    """Test AgentDNA dataclass."""

    def test_default_initialization(self) -> None:
        """DNA should initialize with defaults."""
        dna = AgentDNA()

        assert dna.domain == DomainType.FORGE
        assert dna.capabilities == set()
        assert len(dna.personality_vector) == 8
        assert dna.execution_mode == ExecutionMode.NORMAL

    def test_custom_initialization(self) -> None:
        """DNA should accept custom values."""
        dna = AgentDNA(
            domain=DomainType.SPARK,
            capabilities={"create", "brainstorm"},
            personality_vector=[0.8] * 8,
            execution_mode=ExecutionMode.CREATIVE,
        )

        assert dna.domain == DomainType.SPARK
        assert "create" in dna.capabilities
        assert dna.personality_vector[0] == 0.8
        assert dna.execution_mode == ExecutionMode.CREATIVE

    def test_catastrophe_property(self) -> None:
        """Should derive catastrophe from domain."""
        dna = AgentDNA(domain=DomainType.SPARK)
        assert dna.catastrophe == CatastrophePotential.FOLD

        dna = AgentDNA(domain=DomainType.CRYSTAL)
        assert dna.catastrophe == CatastrophePotential.PARABOLIC

    def test_dna_alias(self) -> None:
        """DNA should be alias for AgentDNA."""
        assert DNA is AgentDNA


# =============================================================================
# TEST OCTONION MAPPINGS
# =============================================================================


class TestOctonionMappings:
    """Test domain to octonion mappings."""

    def test_all_domains_mapped(self) -> None:
        """All 7 domains should map to octonions."""
        assert len(DOMAIN_TO_OCTONION) == 7

    def test_octonion_indices(self) -> None:
        """Octonion indices should be 1-7."""
        assert DOMAIN_TO_OCTONION[DomainType.SPARK] == 1
        assert DOMAIN_TO_OCTONION[DomainType.FORGE] == 2
        assert DOMAIN_TO_OCTONION[DomainType.CRYSTAL] == 7

    def test_unique_indices(self) -> None:
        """Each domain should have unique index."""
        indices = set(DOMAIN_TO_OCTONION.values())
        assert len(indices) == 7


# =============================================================================
# TEST REGISTRY DEFINITIONS
# =============================================================================


class TestRegistryDefinitions:
    """Test agent registry definitions."""

    def test_canonical_registry(self) -> None:
        """Canonical registry should have all colonies."""
        assert len(CANONICAL_AGENTS_REGISTRY) == 7

        for colony in ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]:
            assert colony in CANONICAL_AGENTS_REGISTRY
            assert "description" in CANONICAL_AGENTS_REGISTRY[colony]
            assert "capabilities" in CANONICAL_AGENTS_REGISTRY[colony]

    def test_agent_personalities(self) -> None:
        """All agents should have personalities."""
        assert len(AGENT_PERSONALITIES) == 7

        assert AGENT_PERSONALITIES["spark"] == "creative and divergent"
        assert AGENT_PERSONALITIES["forge"] == "focused and productive"
        assert AGENT_PERSONALITIES["crystal"] == "rigorous and precise"

    def test_action_to_app_map(self) -> None:
        """Actions should map to apps."""
        assert ACTION_TO_APP_MAP["create"] == "spark"
        assert ACTION_TO_APP_MAP["build"] == "forge"
        assert ACTION_TO_APP_MAP["test"] == "crystal"

    def test_app_maturity(self) -> None:
        """All apps should have maturity levels."""
        assert len(APP_MATURITY) == 7

        for colony in CANONICAL_AGENTS_REGISTRY.keys():
            assert colony in APP_MATURITY

    def test_app_metadata(self) -> None:
        """App metadata should be complete."""
        assert len(APP_METADATA) == 7

        for colony in CANONICAL_AGENTS_REGISTRY.keys():
            metadata = APP_METADATA[colony]
            assert "name" in metadata
            assert "description" in metadata
            assert "capabilities" in metadata
            assert "maturity" in metadata
            assert "personality" in metadata

    def test_app_registry_v2_alias(self) -> None:
        """APP_REGISTRY_V2 should alias APP_METADATA."""
        assert APP_REGISTRY_V2 is APP_METADATA
