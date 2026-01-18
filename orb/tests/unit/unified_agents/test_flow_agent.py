"""Unit tests for FlowAgent - The Healer.

Tests:
- Agent initialization
- System prompt content
- Tool availability
- Swallowtail multi-path recovery
- Escalation logic
- Safety margin handling
- S⁷ embedding correctness

Created: December 14, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import torch

from kagami.core.unified_agents.agents.base_colony_agent import AgentResult
from kagami.core.unified_agents.agents.flow_agent import FlowAgent, create_flow_agent


class TestFlowAgent:
    """Test suite for FlowAgent."""

    def test_initialization(self) -> None:
        """Test Flow agent initialization."""
        flow = create_flow_agent()

        assert flow.colony_idx == 2
        assert flow.colony_name == "flow"
        assert flow.max_recovery_paths == 3
        assert flow.recovery_attempts == 0

    def test_system_prompt(self) -> None:
        """Test system prompt contains key Flow characteristics."""
        flow = create_flow_agent()
        prompt = flow.get_system_prompt()

        # Check for key identity markers
        assert "Flow" in prompt
        assert "Healer" in prompt or "healer" in prompt.lower()
        assert "Swallowtail" in prompt
        assert "e₃" in prompt

        # Check for catastrophe dynamics
        assert "Path" in prompt or "path" in prompt.lower()
        assert "A₄" in prompt or "x⁵" in prompt
        assert "Water" in prompt or "water" in prompt.lower()

    def test_available_tools(self) -> None:
        """Test Flow has debugging/recovery tools."""
        flow = create_flow_agent()
        tools = flow.get_available_tools()

        # Check essential tools
        assert "debug" in tools
        assert "fix" in tools
        assert "recover" in tools
        assert "adapt" in tools

        # Should have multiple tools
        assert len(tools) >= 5

    def test_direct_fix_recovery(self) -> None:
        """Test direct fix (first recovery path)."""
        flow = create_flow_agent()

        result = flow.process_with_catastrophe(
            task="debug authentication error",
            context={"error": "401 Unauthorized"},
        )

        assert result.success is True
        assert result.metadata["recovery_path"] == "direct_fix"  # type: ignore[index]
        assert result.metadata["catastrophe_type"] == "swallowtail"  # type: ignore[index]
        assert result.should_escalate is False
        assert "Water" in result.output["message"] or "water" in result.output["message"]  # type: ignore[index]

    def test_workaround_recovery(self) -> None:
        """Test workaround (second recovery path)."""
        flow = create_flow_agent()

        result = flow.process_with_catastrophe(
            task="debug authentication error",
            context={
                "error": "401 Unauthorized",
                "attempted_paths": ["direct_fix"],
            },
        )

        assert result.success is True
        assert result.metadata["recovery_path"] == "workaround"  # type: ignore[index]
        assert result.should_escalate is False

    def test_redesign_recovery(self) -> None:
        """Test redesign (third recovery path)."""
        flow = create_flow_agent()

        result = flow.process_with_catastrophe(
            task="debug authentication error",
            context={
                "error": "401 Unauthorized",
                "attempted_paths": ["direct_fix", "workaround"],
            },
        )

        assert result.success is True
        assert result.metadata["recovery_path"] == "redesign"  # type: ignore[index]
        assert result.output["scope"] == "architectural"  # type: ignore[index]

    def test_exhausted_paths_escalation(self) -> None:
        """Test escalation when all recovery paths exhausted."""
        flow = create_flow_agent()

        result = flow.process_with_catastrophe(
            task="debug authentication error",
            context={
                "error": "401 Unauthorized",
                "attempted_paths": ["direct_fix", "workaround", "redesign"],
            },
        )

        assert result.success is False
        assert result.should_escalate is True
        assert result.escalation_target == "beacon"
        assert "exhausted" in result.output.lower()  # type: ignore[union-attr]

    def test_safety_margin_handling(self) -> None:
        """Test conservative recovery with low safety margin."""
        flow = create_flow_agent()

        result = flow.process_with_catastrophe(
            task="debug authentication error",
            context={
                "error": "401 Unauthorized",
                "safety_margin": 0.05,  # Low h(x)
            },
        )

        assert result.success is True
        assert result.output["strategy"] == "conservative"  # type: ignore[index]

    def test_security_critical_escalation(self) -> None:
        """Test escalation for security-critical fixes."""
        flow = create_flow_agent()

        result = flow.process_with_catastrophe(
            task="fix security vulnerability",
            context={"security_critical": True},
        )

        # Should complete but mark for escalation
        assert result.success is True

        # Check escalation
        escalate = flow.should_escalate(result, {"security_critical": True})
        assert escalate is True
        assert result.escalation_target == "crystal"

    def test_architectural_escalation(self) -> None:
        """Test escalation when architectural redesign needed."""
        flow = create_flow_agent()

        result = flow.process_with_catastrophe(
            task="debug authentication error",
            context={
                "attempted_paths": ["direct_fix", "workaround"],
            },
        )

        # Redesign path should trigger escalation
        escalate = flow.should_escalate(result, {})
        assert escalate is True
        assert result.escalation_target == "beacon"

    def test_recovery_attempts_escalation(self) -> None:
        """Test escalation after too many recovery attempts."""
        flow = create_flow_agent()

        # Simulate 6 recovery attempts
        for i in range(6):
            result = flow.process_with_catastrophe(
                task=f"debug error {i}",
                context={},
            )

        # Should escalate after 5 attempts
        escalate = flow.should_escalate(result, {})
        assert escalate is True
        assert flow.recovery_attempts > 5

    def test_reset_recovery_attempts(self) -> None:
        """Test recovery attempts reset."""
        flow = create_flow_agent()

        # Make some attempts
        for i in range(3):
            flow.process_with_catastrophe(
                task=f"debug error {i}",
                context={},
            )

        assert flow.recovery_attempts == 3

        # Reset
        flow.reset_recovery_attempts()
        assert flow.recovery_attempts == 0

    def test_recovery_stats(self) -> None:
        """Test recovery statistics."""
        flow = create_flow_agent()

        stats = flow.get_recovery_stats()

        assert stats["colony"] == "flow"
        assert stats["recovery_attempts"] == 0
        assert stats["max_recovery_paths"] == 3
        assert stats["catastrophe_type"] == "swallowtail"

    def test_s7_embedding(self) -> None:
        """Test S⁷ embedding correctness."""
        flow = create_flow_agent()

        embedding = flow.get_embedding()

        # Check shape
        assert embedding.shape == (7,)

        # Check normalization
        norm = embedding.norm()
        assert torch.isclose(norm, torch.tensor(1.0), atol=1e-6)

        # Check unit vector at index 2 (Flow is e₃)
        assert embedding[2].item() == 1.0
        assert (embedding[[0, 1, 3, 4, 5, 6]] == 0).all()

    def test_result_s7_embedding(self) -> None:
        """Test S⁷ embedding in processing result."""
        flow = create_flow_agent()

        result = flow.process_with_catastrophe(
            task="debug error",
            context={},
        )

        assert result.s7_embedding is not None
        assert result.s7_embedding.shape == (7,)
        assert result.s7_embedding[2].item() == 1.0  # Flow's index

    def test_multiple_paths_sequence(self) -> None:
        """Test full sequence of recovery paths."""
        flow = create_flow_agent()

        # Path 1: Direct fix
        result1 = flow.process_with_catastrophe(
            task="debug error",
            context={"attempted_paths": []},
        )
        assert result1.metadata["recovery_path"] == "direct_fix"  # type: ignore[index]

        # Path 2: Workaround
        result2 = flow.process_with_catastrophe(
            task="debug error",
            context={"attempted_paths": ["direct_fix"]},
        )
        assert result2.metadata["recovery_path"] == "workaround"  # type: ignore[index]

        # Path 3: Redesign
        result3 = flow.process_with_catastrophe(
            task="debug error",
            context={"attempted_paths": ["direct_fix", "workaround"]},
        )
        assert result3.metadata["recovery_path"] == "redesign"  # type: ignore[index]

        # Path 4: Escalate
        result4 = flow.process_with_catastrophe(
            task="debug error",
            context={"attempted_paths": ["direct_fix", "workaround", "redesign"]},
        )
        assert result4.should_escalate is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
