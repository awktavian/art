"""Unit tests for BeaconAgent - The Planner.

Tests:
- Agent initialization
- System prompt content
- Tool availability
- Hyperbolic catastrophe dynamics (D₄⁺)
- Multi-path planning behavior
- Escalation logic
- Risk analysis
- Contingency planning
- S⁷ embedding correctness
- Planning quality

Created: December 14, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import asyncio
import torch

from kagami.core.unified_agents.agents.base_colony_agent import AgentResult
from kagami.core.unified_agents.agents.beacon_agent import BeaconAgent, create_beacon_agent


class TestBeaconAgent:
    """Test suite for BeaconAgent."""

    def test_initialization(self) -> None:
        """Test Beacon agent initialization."""
        beacon = create_beacon_agent()

        # BeaconAgent uses BaseColonyAgent with colony_idx (0-indexed)
        # e₅ = colony_idx 4 (indices 0-6 for e₁-e₇)
        assert beacon.colony_idx == 4  # e₅
        assert beacon.colony_name == "beacon"
        assert beacon.active_plans == []
        assert beacon.risk_register == []

    def test_system_prompt(self) -> None:
        """Test system prompt contains key Beacon characteristics."""
        beacon = create_beacon_agent()
        prompt = beacon.get_system_prompt()

        # Check for key identity markers
        assert "Beacon" in prompt
        assert "Architect" in prompt or "architect" in prompt.lower()
        assert "Hyperbolic" in prompt or "hyperbolic" in prompt.lower()
        assert "e₅" in prompt or "e5" in prompt

        # Check for catastrophe dynamics
        assert "D₄" in prompt or "D4" in prompt or "saddle" in prompt.lower()
        assert "path" in prompt.lower() or "future" in prompt.lower()

    def test_available_tools(self) -> None:
        """Test Beacon has planning/research tools."""
        beacon = create_beacon_agent()
        tools = beacon.get_available_tools()

        # Check essential tools for planning
        assert "Read" in tools
        assert "Glob" in tools or "Grep" in tools

        # Should have multiple tools
        assert len(tools) >= 4

    def test_hyperbolic_catastrophe_behavior(self) -> None:
        """Test Hyperbolic (D₄⁺) catastrophe dynamics - dual basin behavior."""
        beacon = create_beacon_agent()

        # Create a task description and context
        task_description = "Design multi-path architecture"
        context = {"complexity": "high"}

        # Process with catastrophe dynamics
        result = beacon.process_with_catastrophe(task_description, context)
        metadata = result.metadata or {}

        # Verify catastrophe type
        assert metadata.get("catastrophe_type") == "hyperbolic"

        # Verify branching factor computed
        assert "branching_factor" in metadata
        assert 0.0 <= metadata["branching_factor"] <= 1.0

        # Verify planning mode determined
        assert "planning_mode" in metadata
        assert metadata["planning_mode"] in ["single_path", "multi_path"]

        # Verify result is successful
        assert result.success is True
        assert result.output is not None

        # Verify S⁷ embedding exists and is normalized
        if result.s7_embedding is not None:
            import numpy as np

            s7_norm = np.linalg.norm(result.s7_embedding.numpy())
            assert abs(s7_norm - 1.0) < 1e-5

    def test_strategic_planning_single_path(self) -> None:
        """Test strategic planning with low branching (single path mode)."""
        beacon = create_beacon_agent()

        # Create task with low branching
        task_description = "Simple linear architecture"
        context = {}

        # Initialize hyperbolic position for low gradient difference
        beacon.hyperbolic_position = torch.tensor([0.1, 0.1])

        result = beacon.process_with_catastrophe(task_description, context)
        metadata = result.metadata or {}

        # Low gradient difference → single path mode
        # (branching_factor = |grad_x1 - grad_x2| / (|grad_x1| + |grad_x2| + eps))
        # With similar x1, x2 values, gradients should be similar
        assert metadata["planning_mode"] == "single_path"

    def test_strategic_planning_multi_path(self) -> None:
        """Test strategic planning with high branching (multi-path mode)."""
        beacon = create_beacon_agent()

        # Create task with high branching
        task_description = "Complex multi-component architecture"
        context = {}

        # Initialize hyperbolic position for high gradient difference
        beacon.hyperbolic_position = torch.tensor([1.0, 0.0])

        result = beacon.process_with_catastrophe(task_description, context)
        metadata = result.metadata or {}

        # High gradient difference → multi-path mode
        # branching_factor > 0.3 triggers multi_path
        assert metadata["planning_mode"] == "multi_path"

    @pytest.mark.asyncio
    async def test_plan_method(self) -> None:
        """Test the plan() method produces structured plan."""
        beacon = create_beacon_agent()

        plan = await beacon.plan(
            goal="Implement authentication system",
            current_state="No authentication present",
            constraints=["Must use OAuth2", "Must support MFA"],
        )

        # Verify plan structure
        assert "goal" in plan
        assert "current_state" in plan
        assert "constraints" in plan
        assert "approach" in plan
        assert "risks" in plan
        assert "milestones" in plan
        assert "success_criteria" in plan
        assert "contingencies" in plan
        assert "estimated_duration" in plan
        assert "recommended_colonies" in plan

        # Verify plan content
        assert plan["goal"] == "Implement authentication system"
        assert len(plan["approach"]) > 0
        assert len(plan["risks"]) > 0
        assert len(plan["milestones"]) > 0
        assert len(plan["success_criteria"]) > 0

        # Verify plan stored
        assert len(beacon.active_plans) == 1

    @pytest.mark.asyncio
    async def test_risk_identification(self) -> None:
        """Test risk analysis and mitigation generation."""
        beacon = create_beacon_agent()

        plan = await beacon.plan(
            goal="Build distributed system",
            current_state="Single server",
            constraints=["High availability required"],
        )

        # Should identify multiple risks
        assert len(plan["risks"]) >= 2

        # Each risk should have structure
        for risk in plan["risks"]:
            assert "risk" in risk
            assert "probability" in risk
            assert "impact" in risk
            assert "mitigation" in risk

        # Risks should be added to register
        assert len(beacon.risk_register) > 0

    @pytest.mark.asyncio
    async def test_contingency_planning(self) -> None:
        """Test contingency generation for failure modes."""
        beacon = create_beacon_agent()

        plan = await beacon.plan(
            goal="Launch new feature",
            current_state="Feature in development",
        )

        contingencies = plan["contingencies"]

        # Should have contingencies for common failure modes
        assert "if_primary_approach_fails" in contingencies
        assert "if_timeline_slips" in contingencies

        # Contingencies should be strings (descriptions)
        for _, value in contingencies.items():
            assert isinstance(value, str)
            assert len(value) > 0

    @pytest.mark.asyncio
    async def test_milestone_definition(self) -> None:
        """Test milestone generation for tracking progress."""
        beacon = create_beacon_agent()

        plan = await beacon.plan(
            goal="Refactor legacy code",
            current_state="Monolithic codebase",
        )

        milestones = plan["milestones"]

        # Should have multiple milestones
        assert len(milestones) >= 3

        # Each milestone should have structure
        for milestone in milestones:
            assert "milestone" in milestone
            assert "phase" in milestone

    @pytest.mark.asyncio
    async def test_success_criteria_definition(self) -> None:
        """Test success criteria generation."""
        beacon = create_beacon_agent()

        plan = await beacon.plan(
            goal="Optimize performance",
            current_state="System is slow",
        )

        criteria = plan["success_criteria"]

        # Should have multiple criteria
        assert len(criteria) >= 3

        # Should all be strings
        assert all(isinstance(c, str) for c in criteria)

    @pytest.mark.asyncio
    async def test_colony_recommendation(self) -> None:
        """Test recommendation of which colonies to involve."""
        beacon = create_beacon_agent()

        # Goal with building keyword
        plan_build = await beacon.plan(
            goal="Build new API endpoint",
            current_state="No endpoint",
        )
        assert "forge" in plan_build["recommended_colonies"]

        # Goal with research keyword
        plan_research = await beacon.plan(
            goal="Research best practices for caching",
            current_state="No caching strategy",
        )
        assert "grove" in plan_research["recommended_colonies"]

        # Goal with verification keyword
        plan_verify = await beacon.plan(
            goal="Verify security of authentication",
            current_state="Auth implemented",
        )
        assert "crystal" in plan_verify["recommended_colonies"]

    def test_escalation_high_complexity(self) -> None:
        """Test escalation when complexity > 0.7."""
        beacon = create_beacon_agent()

        # Long description + many constraints triggers high complexity
        task_description = "x" * 300  # Long task (300/200 = 1.5 → capped at 1.0)
        context = {
            "constraints": [
                f"constraint_{i}" for i in range(15)
            ]  # Many constraints (15/10 = 1.5 → capped at 1.0)
        }

        # Process task to get result
        result = beacon.process_with_catastrophe(task_description, context)

        # Verify complexity is high (should be (1.0 + 1.5 capped at 1.0)/2 = 1.0)
        metadata = result.metadata or {}
        complexity = metadata.get("complexity", 0.0)
        assert complexity > 0.7, f"Expected complexity > 0.7, got {complexity}"

        # Check if escalation recommended
        should_escalate = beacon.should_escalate(result, context)
        assert should_escalate is True

    def test_escalation_research_needed(self) -> None:
        """Test escalation when research keywords detected."""
        beacon = create_beacon_agent()

        task_description = "Research unknown distributed consensus algorithms"
        context = {}

        # Process task to get result
        result = beacon.process_with_catastrophe(task_description, context)

        # Check if escalation recommended (should be True due to "research" keyword)
        should_escalate = beacon.should_escalate(result, context)
        assert should_escalate is True  # "research" keyword triggers escalation

    def test_escalation_creative_needed(self) -> None:
        """Test escalation when creative keywords detected."""
        beacon = create_beacon_agent()

        task_description = "Brainstorm innovative approaches to caching"
        context = {}

        # Process task to get result
        result = beacon.process_with_catastrophe(task_description, context)

        # Check if escalation recommended (should be True due to creative keywords)
        should_escalate = beacon.should_escalate(result, context)
        assert should_escalate is True  # "brainstorm" and "innovative" keywords

    def test_escalation_risk_analysis_needed(self) -> None:
        """Test escalation when risk/security keywords detected."""
        beacon = create_beacon_agent()

        task_description = "Verify security vulnerabilities in authentication"
        context = {}

        # Process task to get result
        result = beacon.process_with_catastrophe(task_description, context)

        # Check if escalation recommended (should be True due to security keywords)
        should_escalate = beacon.should_escalate(result, context)
        assert should_escalate is True  # "verify" and "security" keywords

    def test_no_escalation_simple_task(self) -> None:
        """Test no escalation for simple planning tasks."""
        beacon = create_beacon_agent()

        task_description = "Design simple REST endpoint"
        context = {}

        # Process task to get result
        result = beacon.process_with_catastrophe(task_description, context)

        # Check if escalation recommended (should be False for simple task)
        should_escalate = beacon.should_escalate(result, context)
        assert should_escalate is False

    def test_s7_embedding(self) -> None:
        """Test S⁷ embedding correctness."""
        beacon = create_beacon_agent()

        # BEACON is e₅, which is colony_idx=4 (0-indexed)
        # BaseColonyAgent provides s7_unit attribute (line 67 in base_colony_agent.py)
        import numpy as np

        s7_unit = beacon.s7_unit.numpy()

        # Should be a 7D vector
        assert s7_unit.shape == (7,)

        # Should be unit vector
        norm = np.linalg.norm(s7_unit)
        assert abs(norm - 1.0) < 1e-6

        # Should have exactly one non-zero component (at index 4 for e₅)
        nonzero_indices = np.where(s7_unit != 0)[0]
        assert len(nonzero_indices) == 1
        assert nonzero_indices[0] == 4  # e₅ = index 4

        # That component should be 1.0
        assert abs(s7_unit[4] - 1.0) < 1e-6

    @pytest.mark.asyncio
    async def test_duration_estimation(self) -> None:
        """Test duration estimation scales with complexity."""
        beacon = create_beacon_agent()

        # Low complexity
        plan_simple = await beacon.plan(
            goal="x",
            current_state="y",
        )
        duration_simple = plan_simple["estimated_duration"]["estimated_hours"]

        # High complexity
        plan_complex = await beacon.plan(
            goal="x" * 200,
            current_state="y",
            constraints=["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "c10"],
        )
        duration_complex = plan_complex["estimated_duration"]["estimated_hours"]

        # High complexity should have longer duration
        assert duration_complex > duration_simple

        # Should have best/worst case estimates
        assert "best_case_hours" in plan_complex["estimated_duration"]
        assert "worst_case_hours" in plan_complex["estimated_duration"]
        assert "confidence" in plan_complex["estimated_duration"]

    @pytest.mark.asyncio
    async def test_planning_approach_structure(self) -> None:
        """Test generated approach has proper step structure."""
        beacon = create_beacon_agent()

        plan = await beacon.plan(
            goal="Implement feature",
            current_state="No feature",
        )

        approach = plan["approach"]

        # Each step should have structure
        for step in approach:
            assert "step" in step
            assert "action" in step
            assert "rationale" in step
            assert "dependencies" in step

        # Steps should be numbered sequentially
        step_numbers = [s["step"] for s in approach]
        assert step_numbers == list(range(1, len(approach) + 1))

    @pytest.mark.asyncio
    async def test_multiple_plans(self) -> None:
        """Test creating multiple plans and tracking."""
        beacon = create_beacon_agent()

        # Create multiple plans
        plan1 = await beacon.plan(goal="Goal 1", current_state="State 1")
        plan2 = await beacon.plan(goal="Goal 2", current_state="State 2")
        plan3 = await beacon.plan(goal="Goal 3", current_state="State 3")

        # Should track all plans
        assert len(beacon.active_plans) == 3

        # Each plan should be distinct
        assert plan1["goal"] != plan2["goal"]
        assert plan2["goal"] != plan3["goal"]

    @pytest.mark.asyncio
    async def test_foresight_characteristic(self) -> None:
        """Test Beacon exhibits foresight in planning."""
        beacon = create_beacon_agent()

        plan = await beacon.plan(
            goal="Launch product",
            current_state="Development phase",
        )

        # Foresight shown through:
        # 1. Multiple milestones (looking ahead)
        assert len(plan["milestones"]) >= 4

        # 2. Risk identification (anticipating problems)
        assert len(plan["risks"]) >= 2

        # 3. Contingency planning (preparing for failures)
        assert len(plan["contingencies"]) >= 3

        # 4. Time estimation with uncertainty
        assert "best_case_hours" in plan["estimated_duration"]
        assert "worst_case_hours" in plan["estimated_duration"]

    def test_planning_personality_voice(self) -> None:
        """Test Beacon's divergent, future-seeing personality."""
        beacon = create_beacon_agent()
        prompt = beacon.get_system_prompt()

        # Future-seeing characteristics
        assert any(word in prompt.lower() for word in ["future", "path", "see", "diverge"])

        # Architectural characteristics
        assert any(word in prompt.lower() for word in ["architect", "map", "saddle", "structure"])

        # D4+ geometry
        assert "D₄" in prompt or "outward" in prompt.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
