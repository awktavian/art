"""Test BaseColonyAgent consolidation.

Verifies that all colony agents use consistent base classes after consolidation:
- Canonical base: kagami/core/unified_agents/base_colony_agent.py
- Simplified base: kagami/core/unified_agents/agents/base_colony_agent.py (backward compat)
- No embedded base classes in agent files

Created: December 14, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import torch

from kagami.core.unified_agents.agents import (
    BaseColonyAgent,
    AgentResult,
    ForgeAgent,
    FlowAgent,
    NexusAgent,
    GroveAgent,
    SparkAgent,
    BeaconAgent,
    CrystalAgent,
)
from kagami.core.unified_agents.agents.base_colony_agent import (
    BaseColonyAgent as SimplifiedBase,  # The actual base agents inherit from
)


class TestBaseColonyAgentConsolidation:
    """Test suite for base colony agent consolidation."""

    def test_base_colony_agent_exists(self) -> None:
        """BaseColonyAgent should exist and be importable."""
        assert BaseColonyAgent is not None
        assert hasattr(BaseColonyAgent, "__init__")
        assert hasattr(BaseColonyAgent, "get_system_prompt")
        assert hasattr(BaseColonyAgent, "get_available_tools")

    def test_simplified_base_exists(self) -> None:
        """Simplified BaseColonyAgent should exist for backward compatibility."""
        assert SimplifiedBase is not None
        assert hasattr(SimplifiedBase, "__init__")
        assert hasattr(SimplifiedBase, "get_system_prompt")

    def test_exported_base_is_simplified(self) -> None:
        """Exported base from agents.__init__ should be the simplified base."""
        assert BaseColonyAgent is SimplifiedBase

    def test_agent_result_type_exists(self) -> None:
        """AgentResult dataclass should be available."""
        result = AgentResult(
            success=True,
            output="test output",
            s7_embedding=torch.zeros(7),
            should_escalate=False,
            escalation_target=None,
            metadata={"test": "data"},
        )
        assert result.success is True
        assert result.output == "test output"

    def test_forge_inherits_simplified_base(self) -> None:
        """ForgeAgent should inherit from SimplifiedBase."""
        forge = ForgeAgent()
        assert isinstance(forge, SimplifiedBase)
        assert forge.colony_name == "forge"
        assert forge.colony_idx == 1
        assert hasattr(forge, "get_system_prompt")
        assert hasattr(forge, "get_available_tools")
        assert hasattr(forge, "get_embedding")

    def test_flow_inherits_simplified_base(self) -> None:
        """FlowAgent should inherit from SimplifiedBase."""
        flow = FlowAgent()
        assert isinstance(flow, SimplifiedBase)
        assert flow.colony_name == "flow"
        assert flow.colony_idx == 2

    def test_nexus_inherits_simplified_base(self) -> None:
        """NexusAgent should inherit from SimplifiedBase."""
        nexus = NexusAgent()
        assert isinstance(nexus, SimplifiedBase)
        assert nexus.colony_name == "nexus"
        assert nexus.colony_idx == 3

    def test_grove_inherits_simplified_base(self) -> None:
        """GroveAgent should inherit from SimplifiedBase."""
        grove = GroveAgent()
        assert isinstance(grove, SimplifiedBase)
        assert grove.colony_name == "grove"
        assert grove.colony_idx == 5

    def test_spark_standalone_implementation(self) -> None:
        """SparkAgent has standalone implementation (can be refactored later)."""
        spark = SparkAgent()
        assert spark.colony_name == "spark"
        assert spark.colony_idx == 0
        # Should have similar interface even if not inheriting
        assert hasattr(spark, "get_system_prompt")
        assert hasattr(spark, "get_available_tools")

    def test_beacon_standalone_implementation(self) -> None:
        """BeaconAgent has standalone implementation (can be refactored later)."""
        beacon = BeaconAgent()
        assert beacon.colony_name == "beacon"
        # Should have similar interface even if not inheriting
        assert hasattr(beacon, "get_system_prompt")
        assert hasattr(beacon, "get_available_tools")

    def test_crystal_standalone_implementation(self) -> None:
        """CrystalAgent has standalone implementation (different architecture)."""
        crystal = CrystalAgent()
        # Crystal has different architecture (doesn't inherit from base)
        # Should still have basic interface
        assert hasattr(crystal, "verify")

    def test_s7_embeddings_consistent(self) -> None:
        """All agents should have consistent S⁷ embeddings."""
        agents = [
            ForgeAgent(),
            FlowAgent(),
            NexusAgent(),
            GroveAgent(),
        ]

        for agent in agents:
            embedding = agent.get_embedding()
            assert embedding.shape == (7,)
            # Should be unit vector (norm = 1.0)
            assert torch.allclose(embedding.norm(), torch.tensor(1.0))
            # Should be one-hot (exactly one element = 1.0)
            assert (embedding == 1.0).sum() == 1

    def test_colony_indices_unique(self) -> None:
        """Each agent should have unique colony index."""
        agents_with_idx = [
            (ForgeAgent(), 1),
            (FlowAgent(), 2),
            (NexusAgent(), 3),
            (GroveAgent(), 5),
        ]

        for agent, expected_idx in agents_with_idx:
            assert agent.colony_idx == expected_idx

    def test_no_import_errors(self) -> None:
        """All imports should work without circular dependencies."""
        # Verify all imported classes are actually loaded and accessible
        imported_classes = [
            BaseColonyAgent,
            AgentResult,
            ForgeAgent,
            FlowAgent,
            NexusAgent,
            GroveAgent,
            SparkAgent,
            BeaconAgent,
            CrystalAgent,
            SimplifiedBase,
        ]
        # All classes should be non-None and callable
        for cls in imported_classes:
            assert cls is not None, f"Import failed: {cls}"
            assert callable(cls), f"Class should be callable: {cls}"
        # Verify module references are consistent (no duplicates from different imports)
        assert BaseColonyAgent is SimplifiedBase, "Base class imports should be identical"

    def test_forge_process_with_catastrophe(self) -> None:
        """Forge should be able to process tasks with catastrophe dynamics."""
        forge = ForgeAgent()
        result = forge.process_with_catastrophe(
            task="implement feature X",
            context={"quality_demand": 0.8, "time_pressure": 0.2},
        )
        assert isinstance(result, AgentResult)
        assert result.success in (True, False)
        assert result.output is not None

    def test_flow_process_with_catastrophe(self) -> None:
        """Flow should be able to process tasks with catastrophe dynamics."""
        flow = FlowAgent()
        result = flow.process_with_catastrophe(
            task="debug error Y",
            context={"error_count": 3},
        )
        assert isinstance(result, AgentResult)
        assert result.success in (True, False)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
