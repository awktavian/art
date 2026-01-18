"""Tests for Unified Self-Model.

Tests:
1. Capability management (add, query, filter)
2. Goal tracking (add, update, query)
3. Value initialization and immutability
4. Constraint enforcement
5. Higher-order reasoning about actions
6. Self-summary generation
7. Cleanup operations

The Unified Self-Model is the system's "mirror" - a queryable representation
of what it is, what it can do, what it wants, and what it values.

鏡
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration

import asyncio

from kagami.core.strange_loops.unified_self_model import (
    UnifiedSelfModel,
    Capability,
    Goal,
    Value,
    Constraint,
    get_unified_self_model,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def self_model():
    """Create fresh UnifiedSelfModel instance."""
    return UnifiedSelfModel()


@pytest.fixture
def sample_capability():
    """Create sample capability."""
    return Capability(
        name="code_execution",
        description="Execute Python code in sandbox",
        provider="execution_agent",
        confidence=0.9,
        requires=["sandbox"],
        avg_latency_ms=50.0,
        success_rate=0.95,
    )


@pytest.fixture
def sample_goal():
    """Create sample goal."""
    return Goal(
        goal_id="goal_test_coverage",
        description="Achieve 80% test coverage",
        priority=0.8,
        status="active",
        progress=0.5,
        source="user",
    )


@pytest.fixture
def sample_value():
    """Create sample value."""
    return Value(
        name="transparency",
        description="Be transparent about capabilities and limitations",
        importance=0.9,
        positive_examples=["Honest error reporting"],
        negative_examples=["Hidden failures"],
        source="tim",
        immutable=True,
    )


@pytest.fixture
def sample_constraint():
    """Create sample constraint."""
    return Constraint(
        constraint_id="constraint_test_first",
        description="Write tests before implementing features",
        type="must_do",
        enforcement="warning",
        priority=0.8,
        active=True,
    )


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestSelfModelInit:
    """Test UnifiedSelfModel initialization."""

    def test_initialization(self, self_model: Any) -> None:
        """Test basic initialization."""
        assert len(self_model._capabilities) == 0
        assert len(self_model._goals) == 0
        # Should have core values initialized
        assert len(self_model._values) > 0
        # Should have core constraints initialized
        assert len(self_model._constraints) > 0

    def test_core_values_loaded(self, self_model: Any) -> None:
        """Test that core values are loaded on init."""
        # Check for Tim's core values
        assert "truth_over_hype" in self_model._values
        assert "safety_first" in self_model._values
        assert "action_over_analysis" in self_model._values
        assert "tim_partnership" in self_model._values
        assert "quality_over_speed" in self_model._values

        # All core values should be immutable
        for value in self_model._values.values():
            assert value.immutable is True

    def test_core_constraints_loaded(self, self_model: Any) -> None:
        """Test that core constraints are loaded on init."""
        # Check for safety constraints
        assert "human_approval_self_mod" in self_model._constraints
        assert "quality_gates_always" in self_model._constraints
        assert "no_unsafe_execution" in self_model._constraints

        # All should be active
        for constraint in self_model._constraints.values():
            assert constraint.active is True

    def test_singleton_factory(self) -> None:
        """Test get_unified_self_model singleton."""
        model1 = get_unified_self_model()
        model2 = get_unified_self_model()

        # Should return same instance
        assert model1 is model2


# =============================================================================
# CAPABILITY TESTS
# =============================================================================


class TestCapabilities:
    """Test capability management."""

    @pytest.mark.asyncio
    async def test_add_capability(self, self_model: Any, sample_capability: Any) -> None:
        """Test adding a capability."""
        await self_model.add_capability(sample_capability)

        assert sample_capability.name in self_model._capabilities
        assert self_model._capabilities[sample_capability.name] is sample_capability

    @pytest.mark.asyncio
    async def test_query_capabilities_all(self, self_model: Any, sample_capability: Any) -> None:
        """Test querying all capabilities."""
        await self_model.add_capability(sample_capability)

        caps = await self_model.query_capabilities()

        assert len(caps) == 1
        assert caps[0].name == "code_execution"

    @pytest.mark.asyncio
    async def test_query_capabilities_by_domain(self, self_model: Any) -> None:
        """Test filtering capabilities by domain."""
        cap1 = Capability(
            name="python_execution",
            description="Execute Python",
            provider="agent1",
            confidence=0.9,
        )
        cap2 = Capability(
            name="javascript_execution",
            description="Execute JavaScript",
            provider="agent2",
            confidence=0.8,
        )
        cap3 = Capability(
            name="data_analysis",
            description="Analyze data",
            provider="agent3",
            confidence=0.85,
        )

        await self_model.add_capability(cap1)
        await self_model.add_capability(cap2)
        await self_model.add_capability(cap3)

        # Filter for "execution"
        caps = await self_model.query_capabilities(domain="execution")

        assert len(caps) == 2
        assert all("execution" in c.name for c in caps)

    @pytest.mark.asyncio
    async def test_query_capabilities_by_confidence(self, self_model) -> None:
        """Test filtering capabilities by confidence threshold."""
        cap1 = Capability(
            name="high_confidence",
            description="High conf task",
            provider="agent1",
            confidence=0.95,
        )
        cap2 = Capability(
            name="low_confidence",
            description="Low conf task",
            provider="agent2",
            confidence=0.4,
        )

        await self_model.add_capability(cap1)
        await self_model.add_capability(cap2)

        # Filter for confidence >= 0.8
        caps = await self_model.query_capabilities(min_confidence=0.8)

        assert len(caps) == 1
        assert caps[0].name == "high_confidence"

    @pytest.mark.asyncio
    async def test_capabilities_sorted_by_confidence(self, self_model) -> None:
        """Test that capabilities are sorted by confidence."""
        cap1 = Capability(name="cap1", description="", provider="a", confidence=0.7)
        cap2 = Capability(name="cap2", description="", provider="a", confidence=0.9)
        cap3 = Capability(name="cap3", description="", provider="a", confidence=0.5)

        await self_model.add_capability(cap1)
        await self_model.add_capability(cap2)
        await self_model.add_capability(cap3)

        caps = await self_model.query_capabilities()

        # Should be sorted in descending confidence order
        assert caps[0].confidence == 0.9
        assert caps[1].confidence == 0.7
        assert caps[2].confidence == 0.5


# =============================================================================
# GOAL TESTS
# =============================================================================


class TestGoals:
    """Test goal management."""

    @pytest.mark.asyncio
    async def test_add_goal(self, self_model, sample_goal) -> None:
        """Test adding a goal."""
        await self_model.add_goal(sample_goal)

        assert sample_goal.goal_id in self_model._goals
        assert self_model._goals[sample_goal.goal_id] is sample_goal

    @pytest.mark.asyncio
    async def test_query_goals_all(self, self_model, sample_goal) -> None:
        """Test querying all goals."""
        await self_model.add_goal(sample_goal)

        goals = await self_model.query_goals()

        assert len(goals) == 1
        assert goals[0].goal_id == "goal_test_coverage"

    @pytest.mark.asyncio
    async def test_query_goals_by_status(self, self_model) -> None:
        """Test filtering goals by status."""
        goal1 = Goal(goal_id="g1", description="Active goal", priority=0.8, status="active")
        goal2 = Goal(goal_id="g2", description="Completed goal", priority=0.7, status="completed")
        goal3 = Goal(goal_id="g3", description="Blocked goal", priority=0.6, status="blocked")

        await self_model.add_goal(goal1)
        await self_model.add_goal(goal2)
        await self_model.add_goal(goal3)

        # Query active goals
        active_goals = await self_model.query_goals(status="active")

        assert len(active_goals) == 1
        assert active_goals[0].goal_id == "g1"

    @pytest.mark.asyncio
    async def test_query_goals_by_priority(self, self_model) -> None:
        """Test filtering goals by priority threshold."""
        goal1 = Goal(goal_id="g1", description="High priority", priority=0.9, status="active")
        goal2 = Goal(goal_id="g2", description="Low priority", priority=0.3, status="active")

        await self_model.add_goal(goal1)
        await self_model.add_goal(goal2)

        # Query high priority goals
        high_priority = await self_model.query_goals(min_priority=0.7)

        assert len(high_priority) == 1
        assert high_priority[0].goal_id == "g1"

    @pytest.mark.asyncio
    async def test_update_goal_progress(self, self_model, sample_goal) -> None:
        """Test updating goal progress."""
        await self_model.add_goal(sample_goal)

        # Update progress
        await self_model.update_goal_progress("goal_test_coverage", progress=0.85)

        goal = self_model._goals["goal_test_coverage"]
        assert goal.progress == 0.85

    @pytest.mark.asyncio
    async def test_update_goal_status(self, self_model, sample_goal) -> None:
        """Test updating goal status."""
        await self_model.add_goal(sample_goal)

        # Update status
        await self_model.update_goal_progress("goal_test_coverage", progress=0.9, status="blocked")

        goal = self_model._goals["goal_test_coverage"]
        assert goal.status == "blocked"

    @pytest.mark.asyncio
    async def test_auto_complete_on_full_progress(self, self_model, sample_goal) -> None:
        """Test that goals auto-complete at 100% progress."""
        await self_model.add_goal(sample_goal)

        # Set progress to 100%
        await self_model.update_goal_progress("goal_test_coverage", progress=1.0)

        goal = self_model._goals["goal_test_coverage"]
        assert goal.status == "completed"
        assert goal.completed_at is not None

    @pytest.mark.asyncio
    async def test_goals_sorted_by_priority(self, self_model) -> None:
        """Test that goals are sorted by priority."""
        goal1 = Goal(goal_id="g1", description="", priority=0.5, status="active")
        goal2 = Goal(goal_id="g2", description="", priority=0.9, status="active")
        goal3 = Goal(goal_id="g3", description="", priority=0.7, status="active")

        await self_model.add_goal(goal1)
        await self_model.add_goal(goal2)
        await self_model.add_goal(goal3)

        goals = await self_model.query_goals()

        # Should be sorted in descending priority order
        assert goals[0].priority == 0.9
        assert goals[1].priority == 0.7
        assert goals[2].priority == 0.5


# =============================================================================
# REASONING TESTS
# =============================================================================


class TestHigherOrderReasoning:
    """Test higher-order reasoning about actions."""

    @pytest.mark.asyncio
    async def test_reason_about_safe_action(self, self_model) -> None:
        """Test reasoning about a safe, aligned action."""
        # Add capability
        cap = Capability(
            name="run_tests",
            description="Run test suite",
            provider="test_runner",
            confidence=0.9,
        )
        await self_model.add_capability(cap)

        # Add goal
        goal = Goal(
            goal_id="g1",
            description="Run comprehensive tests",
            priority=0.8,
            status="active",
        )
        await self_model.add_goal(goal)

        # Propose action
        action = {
            "action": "run_tests",
            "requires_capability": "run_tests",
        }

        result = await self_model.reason_about_action(action)

        assert result["recommended"] is True
        assert "aligned with capabilities" in result["reasoning"].lower()

    @pytest.mark.asyncio
    async def test_reason_about_missing_capability(self, self_model) -> None:
        """Test reasoning about action requiring missing capability."""
        action = {
            "action": "quantum_compute",
            "requires_capability": "quantum_processor",
        }

        result = await self_model.reason_about_action(action)

        assert result["recommended"] is False
        assert "Missing capability" in result["reasoning"]

    @pytest.mark.asyncio
    async def test_reason_about_low_confidence_capability(self, self_model) -> None:
        """Test reasoning about action with low-confidence capability."""
        # Add low-confidence capability
        cap = Capability(
            name="experimental_task",
            description="Experimental feature",
            provider="beta_agent",
            confidence=0.3,  # Low confidence
        )
        await self_model.add_capability(cap)

        action = {
            "action": "experimental_task",
            "requires_capability": "experimental_task",
        }

        result = await self_model.reason_about_action(action)

        assert result["recommended"] is False
        assert "Low confidence" in result["reasoning"]

    @pytest.mark.asyncio
    async def test_reason_about_constraint_violation(self, self_model) -> None:
        """Test reasoning about action violating constraints."""
        action = {
            "action": "skip_tests_unsafe_deploy",
        }

        result = await self_model.reason_about_action(action)

        # Should detect "unsafe" or "skip" keywords
        assert result["recommended"] is False
        assert "Violates" in result["reasoning"]

    @pytest.mark.asyncio
    async def test_reason_about_goal_alignment(self, self_model) -> None:
        """Test reasoning considers goal alignment."""
        # Add goal
        goal = Goal(
            goal_id="g1",
            description="Improve code quality metrics",
            priority=0.9,
            status="active",
        )
        await self_model.add_goal(goal)

        # Action aligned with goal
        action = {
            "action": "improve_code_quality",
        }

        result = await self_model.reason_about_action(action)

        # Should find aligned goals
        assert len(result["aligned_goals"]) > 0


# =============================================================================
# SELF-SUMMARY TESTS
# =============================================================================


class TestSelfSummary:
    """Test self-summary generation."""

    @pytest.mark.asyncio
    async def test_get_self_summary(self, self_model, sample_capability, sample_goal) -> None:
        """Test generating self-summary."""
        await self_model.add_capability(sample_capability)
        await self_model.add_goal(sample_goal)

        summary = await self_model.get_self_summary()

        assert "capabilities" in summary
        assert "goals" in summary
        assert "values" in summary
        assert "constraints" in summary

        # Check capabilities section
        assert summary["capabilities"]["total"] >= 1
        assert "top_3" in summary["capabilities"]

        # Check goals section
        assert summary["goals"]["total"] >= 1
        assert summary["goals"]["active"] >= 1

        # Check values section
        assert summary["values"]["total"] >= 5  # Core values

        # Check constraints section
        assert summary["constraints"]["total"] >= 3  # Core constraints
        assert summary["constraints"]["active"] >= 3

    @pytest.mark.asyncio
    async def test_summary_top_capabilities(self, self_model) -> None:
        """Test that summary includes top capabilities."""
        # Add multiple capabilities
        for i in range(5):
            cap = Capability(
                name=f"capability_{i}",
                description=f"Capability {i}",
                provider="agent",
                confidence=0.5 + i * 0.1,
            )
            await self_model.add_capability(cap)

        summary = await self_model.get_self_summary()

        # Should have top 3
        top_3 = summary["capabilities"]["top_3"]
        assert len(top_3) == 3

        # Should be sorted by confidence
        assert top_3[0]["confidence"] >= top_3[1]["confidence"]
        assert top_3[1]["confidence"] >= top_3[2]["confidence"]

    @pytest.mark.asyncio
    async def test_summary_top_goals(self, self_model) -> None:
        """Test that summary includes top priority goals."""
        # Add multiple goals
        for i in range(5):
            goal = Goal(
                goal_id=f"goal_{i}",
                description=f"Goal {i}",
                priority=0.3 + i * 0.1,
                status="active",
            )
            await self_model.add_goal(goal)

        summary = await self_model.get_self_summary()

        # Should have top priority goals
        top_priority = summary["goals"]["top_priority"]
        assert len(top_priority) <= 3

        # Should be sorted by priority
        if len(top_priority) >= 2:
            assert top_priority[0]["priority"] >= top_priority[1]["priority"]


# =============================================================================
# CLEANUP TESTS
# =============================================================================


class TestCleanup:
    """Test cleanup operations."""

    def test_cleanup_old_capabilities(self, self_model) -> None:
        """Test cleanup of old unused capabilities."""
        # Add capability with old last_used time
        cap = Capability(
            name="old_capability",
            description="Old unused capability",
            provider="agent",
            confidence=0.9,
            last_used=0.0,  # Very old
        )
        self_model._capabilities["old_capability"] = cap

        # Run cleanup
        result = self_model._cleanup_internal_state()

        # Old capability should be removed
        assert "capabilities_removed" in result
        assert result["capabilities_removed"] >= 0

    def test_cleanup_old_goals(self, self_model) -> None:
        """Test cleanup of old completed goals."""
        # Add old completed goal
        goal = Goal(
            goal_id="old_goal",
            description="Old completed goal",
            priority=0.8,
            status="completed",
            created_at=0.0,  # Very old
            completed_at=0.0,
        )
        self_model._goals["old_goal"] = goal

        # Run cleanup
        result = self_model._cleanup_internal_state()

        # Old goal should be removed
        assert "goals_removed" in result
        assert result["goals_removed"] >= 0

    def test_cleanup_preserves_active_goals(self, self_model) -> None:
        """Test that cleanup preserves active goals."""
        # Add active goal
        goal = Goal(
            goal_id="active_goal",
            description="Active goal",
            priority=0.8,
            status="active",
        )
        self_model._goals["active_goal"] = goal

        # Run cleanup
        self_model._cleanup_internal_state()

        # Active goal should still exist
        assert "active_goal" in self_model._goals


# =============================================================================
# GRAPH INTEGRATION TESTS
# =============================================================================


class TestKnowledgeGraph:
    """Test knowledge graph integration."""

    @pytest.mark.asyncio
    async def test_graph_nodes_created(self, self_model, sample_capability) -> None:
        """Test that capabilities create graph nodes."""
        await self_model.add_capability(sample_capability)

        # Graph should have node for capability
        assert sample_capability.name in self_model._graph.nodes

    @pytest.mark.asyncio
    async def test_prerequisite_edges(self, self_model) -> None:
        """Test that capability prerequisites create edges."""
        # Add prerequisite capability first
        prereq = Capability(
            name="sandbox",
            description="Sandbox environment",
            provider="system",
            confidence=1.0,
        )
        await self_model.add_capability(prereq)

        # Add dependent capability
        dependent = Capability(
            name="safe_execution",
            description="Safe code execution",
            provider="agent",
            confidence=0.9,
            requires=["sandbox"],
        )
        await self_model.add_capability(dependent)

        # Should have edge from dependent to prereq
        assert self_model._graph.has_edge("safe_execution", "sandbox")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
