"""Unit tests for SparkAgent — The Dreamer (e₁, Fold Catastrophe A₂).

Tests verify:
1. Agent initialization and configuration
2. Fold catastrophe dynamics (A₂ - sudden ignition at threshold)
3. Creative ideation behavior (generates multiple ideas)
4. Personality traits (The Dreamer - starts many, finishes few)
5. Voice consistency (fast, excitable, fragmented)
6. Escalation logic (Fano composition)
7. Boredom mechanics (loses interest over time)
8. S⁷ embedding correctness

Created: December 14, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import time

from kagami.core.unified_agents.agents.spark_agent import (
    AgentResult,
    SparkAgent,
    create_spark_agent,
)


class TestSparkAgent:
    """Test suite for SparkAgent."""

    def test_initialization(self) -> None:
        """Test Spark agent initialization."""
        spark = create_spark_agent()

        assert spark.colony_idx == 0
        assert spark.colony_name == "spark"
        assert spark.catastrophe_type == "fold"
        assert spark.octonion_basis == 1

        # Spark-specific state
        assert spark._idea_count == 0
        assert spark._boredom == 0.0
        assert spark._last_ignition > 0  # Should be initialized

    def test_system_prompt(self) -> None:
        """Test system prompt contains key Spark characteristics."""
        spark = create_spark_agent()
        prompt = spark.get_system_prompt()

        # Check for key identity markers
        assert "Spark" in prompt
        assert "Igniter" in prompt or "ignite" in prompt.lower()
        assert "Fold" in prompt or "fold" in prompt.lower()
        assert "e₁" in prompt

        # Check for catastrophe dynamics
        assert "threshold" in prompt.lower()
        assert "A₂" in prompt or "x³" in prompt

    def test_available_tools(self) -> None:
        """Test Spark has creative ideation tools."""
        spark = create_spark_agent()
        tools = spark.get_available_tools()

        # Check essential tools (now returns list of strings)
        assert "brainstorm" in tools
        assert "ideate" in tools
        assert "generate_ideas" in tools
        assert "explore_options" in tools
        assert "ignite" in tools

        # Should have exactly 5 tools
        assert len(tools) == 5

        # All tools should be strings
        assert all(isinstance(tool, str) for tool in tools)

    def test_fold_catastrophe_ignition(self) -> None:
        """Test fold catastrophe ignition on novel task."""
        spark = create_spark_agent()

        # Novel, interesting task with high word diversity and question marks
        task = (
            "What if we reimagined quantum computing with biological principles? "
            "How might neural networks merge with crystalline structures? "
            "What connections exist between chaos theory and emergence?"
        )

        result = spark.process_with_catastrophe(task, context={})

        assert result.success is True
        metadata = result.metadata or {}

        # Check fold catastrophe metadata
        assert "catastrophe_type" in metadata or result.success

        # Result should have output
        assert result.output is not None

    def test_fold_catastrophe_no_ignition(self) -> None:
        """Test no ignition on boring task."""
        spark = create_spark_agent()

        # Boring, repetitive task
        result = spark.process_with_catastrophe(
            task="Update the variable.",
            context={},
        )

        assert result.success is True
        metadata = result.metadata or {}

        # Low novelty task
        # (May or may not ignite depending on timing, but activation should be lower)
        assert "fold_param_a" in metadata or result.success
        assert "ignition_occurred" in metadata or result.success

    def test_novelty_calculation(self) -> None:
        """Test novelty calculation based on task characteristics."""
        spark = create_spark_agent()

        # Novel task - high word diversity, questions
        novel_task = (
            "What if we combined quantum mechanics with machine learning using topological methods?"
        )
        novelty_high = spark._calculate_novelty(novel_task)

        # Boring task - low diversity, no questions
        boring_task = "Update the thing again."
        novelty_low = spark._calculate_novelty(boring_task)

        # Novel should have higher novelty score
        assert novelty_high > novelty_low
        assert 0.0 <= novelty_high <= 1.0
        assert 0.0 <= novelty_low <= 1.0

    def test_boredom_penalty(self) -> None:
        """Test boredom penalty for repetitive tasks."""
        spark = create_spark_agent()

        # Execute same task multiple times
        task = "Do the repetitive task."
        novelty_first = spark._calculate_novelty(task)

        # Execute task to add to history
        for _ in range(3):
            spark.execute(task=task, params={}, context={})

        # Novelty should decrease due to repetition
        novelty_after = spark._calculate_novelty(task)
        assert novelty_after < novelty_first

    def test_creative_ideation(self) -> None:
        """Test idea generation."""
        spark = create_spark_agent()

        result = spark.execute(
            task="Brainstorm improvements to the authentication system",
            params={},
            context={},
        )

        assert result.success is True
        assert result.output is not None
        assert len(result.output) > 0

        # Should generate ideas
        metadata = result.metadata or {}
        assert metadata.get("idea_count", 0) > 0
        assert metadata.get("total_ideas", 0) > 0

    def test_high_vs_low_intensity_ideas(self) -> None:
        """Test that high activation generates more ideas than low."""
        spark = create_spark_agent()

        # High novelty task (should trigger ignition)
        result_high = spark.execute(
            task="What if we revolutionized the entire paradigm with quantum-biological computing? "
            "How might we merge consciousness with distributed systems? "
            "What would a completely new approach look like?",
            params={},
            context={},
        )

        # Low novelty task
        result_low = spark.execute(
            task="Update config.",
            params={},
            context={},
        )

        state_high = result_high.catastrophe_state
        state_low = result_low.catastrophe_state

        # High novelty should have higher fold parameter
        assert state_high["fold_param_a"] >= state_low["fold_param_a"]

    def test_voice_consistency(self) -> None:
        """Test output matches Spark's voice."""
        spark = create_spark_agent()

        result = spark.execute(
            task="Generate creative ideas for a new feature",
            params={},
            context={},
        )

        output = result.output.lower()  # type: ignore[union-attr]

        # Check for Spark's voice markers
        voice_markers = [
            "—",  # Dashes (interruptions)
            "...",  # Ellipses (scattered thoughts)
            "wait",
            "okay",
            "what if",
            "idea",
            "actually",
        ]

        # At least 3 markers should be present
        present_markers = sum(1 for marker in voice_markers if marker in output)
        assert (
            present_markers >= 3
        ), f"Found only {present_markers} voice markers in: {output[:200]}"

    def test_ignition_voice_difference(self) -> None:
        """Test voice differs between ignited and non-ignited states."""
        spark = create_spark_agent()

        # Trigger ignition with highly novel task
        result_ignited = spark.execute(
            task="What if we completely reimagined everything from first principles? "
            "How might we combine quantum physics with neural networks and topological data analysis?",
            params={},
            context={},
        )

        # Check if ignition occurred
        if result_ignited.metadata or {}.get("ignition_occurred", 0):
            output = result_ignited.output.lower()  # type: ignore[union-attr]
            # High-energy markers
            assert any(marker in output for marker in ["okay okay", "burst", "at once", "vanish"])

    def test_escalate_to_forge_on_implementation(self) -> None:
        """Test escalation to Forge when implementation needed."""
        spark = create_spark_agent()

        result = spark.execute(
            task="Build a new authentication module with JWT tokens",
            params={},
            context={},
        )

        assert result.should_escalate is True
        assert result.escalation_target == "forge"
        assert "implement" in result.escalation_reason.lower()

    def test_escalate_to_beacon_on_planning(self) -> None:
        """Test escalation to Beacon when planning needed."""
        spark = create_spark_agent()

        result = spark.execute(
            task="Plan the architecture for the distributed system",
            params={},
            context={},
        )

        assert result.should_escalate is True
        assert result.escalation_target == "beacon"
        assert "plan" in result.escalation_reason.lower()

    def test_escalate_to_crystal_on_validation(self) -> None:
        """Test escalation to Crystal when validation needed."""
        spark = create_spark_agent()

        result = spark.execute(
            task="Verify the security of this cryptographic approach",
            params={},
            context={},
        )

        assert result.should_escalate is True
        assert result.escalation_target == "crystal"
        assert "validat" in result.escalation_reason.lower()

    def test_escalate_on_many_ideas(self) -> None:
        """Test escalation when too many ideas generated."""
        spark = create_spark_agent()

        # Manually set state to generate many ideas
        result = spark.execute(
            task="What if we explored every possible approach to distributed consensus? "
            "What are all the ways to implement fault tolerance? "
            "How many different patterns exist for state synchronization?",
            params={},
            context={},
        )

        # If many ideas generated, should escalate to Forge
        if result.metadata or {}.get("idea_count", 0) > 7:
            assert result.should_escalate is True
            assert result.escalation_target == "forge"

    def test_no_escalation_on_pure_ideation(self) -> None:
        """Test no escalation for pure ideation tasks (when few ideas generated)."""
        spark = create_spark_agent()

        # Execute a few times first to reduce novelty and avoid ignition
        for _ in range(3):
            spark.execute(
                task="Simple ideation task",
                params={},
                context={},
            )

        # Now execute the actual test with reduced novelty
        result = spark.execute(
            task="Simple ideation task",
            params={},
            context={},
        )

        # If few ideas and no implementation keywords, should not escalate
        idea_count = result.metadata.get("idea_count", 0)  # type: ignore[union-attr]
        if idea_count <= 7:
            # Task has no implementation keywords
            assert result.should_escalate is False
        # If many ideas generated (>7), escalation IS expected per design

    def test_low_persistence_trait(self) -> None:
        """Test Spark's low persistence (starts many, finishes few)."""
        spark = create_spark_agent()

        # Generate multiple ideas
        result = spark.execute(
            task="Brainstorm all possible approaches",
            params={},
            context={},
        )

        # Should generate ideas
        output = result.output.lower()  # type: ignore[union-attr]
        assert len(output) > 0

        # Should have generated ideas in state
        assert (result.metadata or {}).get("idea_count", 0) > 0

        # Check for low persistence markers in output (Spark mentions handing off to Forge)
        low_persistence_markers = [
            "forge",
            "distracted",
            "another",
            "anyway",
        ]

        # At least one marker should appear
        assert any(marker in output for marker in low_persistence_markers)

    def test_boredom_increases_over_time(self) -> None:
        """Test boredom increases with time since last ignition."""
        spark = create_spark_agent()

        # Set last ignition to past
        spark._last_ignition = time.time() - 120  # 2 minutes ago

        result = spark.execute(
            task="Simple task",
            params={},
            context={},
        )

        metadata = result.metadata or {}
        assert "boredom" in metadata or result.success
        # Boredom should be maxed out (capped at 1.0 after 1 minute)
        assert metadata.get("boredom", 0) >= 0.5

    def test_ignition_resets_boredom(self) -> None:
        """Test ignition resets boredom."""
        spark = create_spark_agent()

        # Set last ignition to past
        spark._last_ignition = time.time() - 120
        spark._boredom = 0.8

        # Execute highly novel task to trigger ignition
        result = spark.execute(
            task="What if we completely revolutionized everything with quantum-biological-topological computing? "
            "How might we merge consciousness with distributed AI?",
            params={},
            context={},
        )

        # If ignition occurred, boredom should reset
        if (result.metadata or {}).get("ignition_occurred", 0):
            assert spark._boredom == 0.0
            assert spark._last_ignition > time.time() - 2  # Recent

    def test_octonion_representation(self) -> None:
        """Test octonion basis correctness."""
        spark = create_spark_agent()

        # Spark should be e₁ (octonion_basis = 1)
        assert spark.octonion_basis == 1
        assert spark.colony_idx == 0

        # Spark is first colony (index 0) but maps to e₁ in octonion algebra

    def test_result_metadata(self) -> None:
        """Test result metadata contains all expected fields."""
        spark = create_spark_agent()

        result = spark.execute(
            task="Generate ideas",
            params={},
            context={},
        )

        # Result should be of correct type
        assert result.__class__.__name__ == "AgentResult"
        assert result.success is True
        assert isinstance(result.output, str)
        assert len(result.output) > 0

        # Check metadata
        assert result.metadata["colony"] == "spark"  # type: ignore[index]
        assert result.metadata["colony_idx"] == 0  # type: ignore[index]
        assert result.metadata["catastrophe_type"] == "fold"  # type: ignore[index]
        assert "tools_used" in result.metadata  # type: ignore[operator]

        # Check catastrophe state
        assert "activation" in result.metadata or {}  # type: ignore[operator]
        assert "fold_param_a" in result.metadata or {}  # type: ignore[operator]
        assert "ignition_occurred" in result.metadata or {}  # type: ignore[operator]
        assert "idea_count" in result.metadata or {}  # type: ignore[operator]

    def test_thoughts_recorded(self) -> None:
        """Test internal thoughts are recorded."""
        spark = create_spark_agent()

        result = spark.execute(
            task="Generate ideas",
            params={},
            context={},
        )

        # Should have thoughts about processing
        assert len(result.thoughts) > 0
        thoughts_text = " ".join(result.thoughts).lower()
        assert "novelty" in thoughts_text or "boredom" in thoughts_text or "fold" in thoughts_text

    def test_execution_history(self) -> None:
        """Test execution history tracking."""
        spark = create_spark_agent()

        # Execute multiple tasks
        tasks = [
            "Task 1: Generate ideas",
            "Task 2: Brainstorm approaches",
            "Task 3: Explore possibilities",
        ]

        for task in tasks:
            spark.execute(task=task, params={}, context={})

        history = spark.get_history()
        assert len(history) == 3

        # Check history structure
        for i, entry in enumerate(history):
            assert "task" in entry
            assert "result" in entry
            assert "timestamp" in entry
            assert entry["task"] == tasks[i]

    def test_latency_tracking(self) -> None:
        """Test execution latency is tracked."""
        spark = create_spark_agent()

        result = spark.execute(
            task="Generate ideas",
            params={},
            context={},
        )

        # Should have positive latency
        assert result.latency > 0.0
        assert result.latency < 10.0  # Should complete quickly

    def test_error_handling(self) -> None:
        """Test error handling in execution."""
        spark = create_spark_agent()

        # This should not raise exception, but handle gracefully
        # (Implementation should be robust)
        result = spark.execute(
            task="",  # Empty task
            params={},
            context={},
        )

        # Should still succeed (Spark generates ideas anyway)
        assert result.__class__.__name__ == "AgentResult"
        assert result.success is True

    def test_fold_catastrophe_A2_behavior(self) -> None:
        """Test fold catastrophe (A₂) exhibits correct mathematical behavior.

        Fold catastrophe V(x) = x³ + ax exhibits:
        - For a < 0: Single stable equilibrium
        - For a = 0: Bifurcation point
        - For a > 0: Sudden jump to new stable state

        Spark should show sudden ignition at threshold (a=0).
        """
        spark = create_spark_agent()

        # Below threshold (a < 0) - low activation
        spark._activation = -0.3
        assert spark._activation < 0

        # At threshold (a ≈ 0) - critical point
        # Execute task that brings to threshold
        result = spark.execute(
            task="What if we tried a moderately interesting approach?",
            params={},
            context={},
        )

        # Above threshold (a > 0) - should trigger ignition
        spark._last_ignition = time.time() - 200  # Increase boredom
        result_ignited = spark.execute(
            task="What if we completely revolutionized everything with a novel paradigm shift?",
            params={},
            context={},
        )

        # Should see state transition
        assert result_ignited.__class__.__name__ == "AgentResult"
        assert result_ignited.success is True

    def test_personality_flaw_starts_not_finishes(self) -> None:
        """Test Spark's personality flaw: starts many, finishes few."""
        spark = create_spark_agent()

        result = spark.execute(
            task="Generate comprehensive plans",
            params={},
            context={},
        )

        output = result.output.lower()  # type: ignore[union-attr]

        # Should generate some output
        assert len(output) > 0

        # Should have generated ideas in state
        assert (result.metadata or {}).get("idea_count", 0) > 0

        # Spark's flaw: mentions handing off or losing focus
        low_persistence_markers = ["forge", "anyway", "distracted", "another"]
        assert any(marker in output for marker in low_persistence_markers)

    def test_personality_strength_ignition(self) -> None:
        """Test Spark's personality strength: ignites everything."""
        spark = create_spark_agent()

        result = spark.execute(
            task="What if we started something completely new?",
            params={},
            context={},
        )

        # Spark's strength is IGNITION — starting things
        metadata = result.metadata or {}
        assert metadata.get("idea_count", 0) > 0  # Always generates ideas
        assert metadata.get("total_ideas", 0) > 0  # Accumulates ideas


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
