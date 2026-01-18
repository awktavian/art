"""Tests for Colony Memory Bridge.

Validates:
1. ColonyMemoryBridge - agent memory integration
2. UnifiedMemoryAccess - E8 memory addressing
3. Singleton management

Created: December 14, 2025
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import torch

from kagami.core.unified_agents.memory.colony_memory_bridge import (
    ColonyMemoryConfig,
    UnifiedMemoryAccess,
    ColonyMemoryBridge,
    get_colony_memory_bridge,
    reset_colony_memory_bridge,
)
from kagami.core.unified_agents.core_types import Task, AgentDNA
from kagami.core.unified_agents.colony_constants import DomainType

# =============================================================================
# TEST CONFIGURATION
# =============================================================================


class TestColonyMemoryConfig:
    """Test memory bridge configuration."""

    def test_default_config(self) -> None:
        """Config should have sensible defaults."""
        config = ColonyMemoryConfig()

        assert config.use_organism_rssm is True
        assert config.colony_state_dim == 14
        assert config.use_hopfield_memory is True
        assert config.use_mdl_selection is True
        assert config.learning_rate > 0


# =============================================================================
# TEST UNIFIED MEMORY ACCESS
# =============================================================================


class TestUnifiedMemoryAccess:
    """Test unified memory access layer."""

    def test_initialization(self) -> None:
        """Should initialize without errors."""
        memory = UnifiedMemoryAccess()
        assert memory is not None

    def test_retrieve_basic(self) -> None:
        """Should retrieve from memory."""
        memory = UnifiedMemoryAccess()
        query = torch.randn(14)

        result = memory.retrieve(query, domain="forge")

        assert "hopfield_content" in result
        assert "program_embedding" in result
        assert "colony_state" in result
        assert "attention_weights" in result

    def test_retrieve_handles_shapes(self) -> None:
        """Should handle different query shapes."""
        memory = UnifiedMemoryAccess()

        # 1D query
        query_1d = torch.randn(14)
        result_1d = memory.retrieve(query_1d)
        assert result_1d is not None

        # 2D query
        query_2d = torch.randn(1, 14)
        result_2d = memory.retrieve(query_2d)
        assert result_2d is not None

    def test_retrieve_pads_query(self) -> None:
        """Should pad/truncate query to 14D."""
        memory = UnifiedMemoryAccess()

        # Short query
        query_short = torch.randn(8)
        result = memory.retrieve(query_short)
        assert result is not None

        # Long query
        query_long = torch.randn(20)
        result = memory.retrieve(query_long)
        assert result is not None

    def test_write_basic(self) -> None:
        """Should write to memory."""
        memory = UnifiedMemoryAccess()

        key = torch.randn(14)
        value = torch.randn(128)

        stats = memory.write(key, value, domain="forge", success=True)

        assert "hopfield_updated" in stats
        assert "solomonoff_updated" in stats
        assert "colony_updated" in stats

    def test_write_handles_shapes(self) -> None:
        """Should handle different key/value shapes."""
        memory = UnifiedMemoryAccess()

        # 1D inputs
        key_1d = torch.randn(14)
        value_1d = torch.randn(128)
        stats = memory.write(key_1d, value_1d)
        assert stats is not None

    def test_set_library(self) -> None:
        """Should allow setting program library."""
        memory = UnifiedMemoryAccess()

        # Mock library
        library = object()
        memory.set_library(library)

        assert memory._solomonoff is library


# =============================================================================
# TEST COLONY MEMORY BRIDGE
# =============================================================================


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, domain="forge"):
        self.dna = AgentDNA(domain=DomainType(domain))
        self.semantic_pointer = None


class TestColonyMemoryBridge:
    """Test colony memory bridge."""

    def test_initialization(self) -> None:
        """Should initialize without errors."""
        bridge = ColonyMemoryBridge()
        assert bridge is not None

    def test_get_agent_context(self) -> None:
        """Should get context for agent."""
        bridge = ColonyMemoryBridge()
        agent = MockAgent()
        task = Task(task_type="build.feature")

        context = bridge.get_agent_context(agent, task)

        assert "memory" in context
        assert "domain" in context
        assert "query_embedding" in context

    def test_record_outcome(self) -> None:
        """Should record task outcome."""
        bridge = ColonyMemoryBridge()
        agent = MockAgent()
        task = Task()
        result = {"status": "success"}

        stats = bridge.record_outcome(agent, task, success=True, result=result)

        assert isinstance(stats, dict)

    def test_get_action_candidates(self) -> None:
        """Should generate action candidates."""
        bridge = ColonyMemoryBridge()
        agent = MockAgent()
        task = Task(task_type="test.function")

        candidates = bridge.get_action_candidates(agent, task, num_candidates=3)

        assert len(candidates) >= 1
        for candidate in candidates:
            assert "action_type" in candidate
            assert "params" in candidate

    def test_stats(self) -> None:
        """Should return statistics."""
        bridge = ColonyMemoryBridge()
        agent = MockAgent()
        task = Task()

        # Perform operations
        bridge.get_agent_context(agent, task)
        bridge.record_outcome(agent, task, success=True, result={})

        stats = bridge.get_stats()

        assert "total_queries" in stats
        assert "total_writes" in stats
        assert "last_access" in stats
        assert stats["total_queries"] >= 1
        assert stats["total_writes"] >= 1

    def test_build_query_from_semantic_pointer(self) -> None:
        """Should use semantic pointer if available."""
        bridge = ColonyMemoryBridge()
        agent = MockAgent()
        agent.semantic_pointer = torch.randn(14)
        task = Task()

        query = bridge._build_query(agent, task)

        assert query is not None
        assert query.shape[-1] >= 14

    def test_build_query_fallback(self) -> None:
        """Should fallback to task hash if no pointer."""
        bridge = ColonyMemoryBridge()
        agent = MockAgent()
        task = Task(task_type="unique.action")

        query = bridge._build_query(agent, task)

        assert query is not None
        assert query.shape[-1] == 14

    def test_build_outcome_embedding(self) -> None:
        """Should encode outcome to embedding."""
        bridge = ColonyMemoryBridge()

        result = {
            "valence": 0.8,
            "brain_confidence": 0.9,
            "duration": 5.0,
        }

        embedding = bridge._build_outcome_embedding(result, success=True)

        assert embedding.shape[-1] == bridge.config.memory_value_dim
        # Success should be encoded
        assert embedding[0, 0] == 1.0

    def test_failure_encoding(self) -> None:
        """Should encode failures differently."""
        bridge = ColonyMemoryBridge()

        embedding = bridge._build_outcome_embedding({}, success=False)

        # Failure should be encoded as -1
        assert embedding[0, 0] == -1.0


# =============================================================================
# TEST SINGLETON
# =============================================================================


class TestSingleton:
    """Test singleton management."""

    def test_get_singleton(self) -> None:
        """Should return singleton instance."""
        reset_colony_memory_bridge()

        bridge1 = get_colony_memory_bridge()
        bridge2 = get_colony_memory_bridge()

        assert bridge1 is bridge2

    def test_reset_singleton(self) -> None:
        """Should reset singleton."""
        bridge1 = get_colony_memory_bridge()
        reset_colony_memory_bridge()
        bridge2 = get_colony_memory_bridge()

        assert bridge1 is not bridge2
