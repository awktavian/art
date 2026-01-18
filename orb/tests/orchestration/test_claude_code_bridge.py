"""Test suite for Claude Code Task Bridge.

Tests the bridge between kagami Python orchestration and Claude Code Task tool,
including single agent spawning, parallel execution, and Fano line routing.

Created: December 15, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.orchestration.claude_code_bridge import (
    BridgeConfig,
    BridgeMode,
    ClaudeCodeTaskBridge,
    COLONY_TO_SUBAGENT,
    FANO_COMPOSITION,
    SUBAGENT_TO_COLONY,
    TaskResult,
    create_claude_code_bridge,
    get_claude_code_bridge,
    should_use_claude_code,
)

# =============================================================================
# BASIC FUNCTIONALITY
# =============================================================================


def test_colony_mappings() -> None:
    """Test colony index to subagent name mappings."""
    assert COLONY_TO_SUBAGENT[0] == "spark"
    assert COLONY_TO_SUBAGENT[1] == "forge"
    assert COLONY_TO_SUBAGENT[2] == "flow"
    assert COLONY_TO_SUBAGENT[3] == "nexus"
    assert COLONY_TO_SUBAGENT[4] == "beacon"
    assert COLONY_TO_SUBAGENT[5] == "grove"
    assert COLONY_TO_SUBAGENT[6] == "crystal"

    # Reverse mapping
    assert SUBAGENT_TO_COLONY["spark"] == 0
    assert SUBAGENT_TO_COLONY["forge"] == 1
    assert SUBAGENT_TO_COLONY["crystal"] == 6


def test_fano_composition() -> None:
    """Test Fano composition lookup table."""
    # Test known compositions from CLAUDE.md
    assert FANO_COMPOSITION[("spark", "forge")] == "flow"
    assert FANO_COMPOSITION[("spark", "nexus")] == "beacon"
    assert FANO_COMPOSITION[("spark", "grove")] == "crystal"
    assert FANO_COMPOSITION[("forge", "nexus")] == "grove"
    assert FANO_COMPOSITION[("beacon", "forge")] == "crystal"
    assert FANO_COMPOSITION[("nexus", "flow")] == "crystal"
    assert FANO_COMPOSITION[("beacon", "flow")] == "grove"


def test_bridge_config_defaults() -> None:
    """Test default bridge configuration."""
    config = BridgeConfig()

    assert config.mode == BridgeMode.DISABLED
    assert config.timeout_seconds == 120.0
    assert config.model == "sonnet"
    assert config.enable_parallel is True
    assert config.max_concurrent == 7


def test_create_bridge() -> None:
    """Test bridge creation."""
    bridge = create_claude_code_bridge()

    assert isinstance(bridge, ClaudeCodeTaskBridge)
    assert bridge.config.mode == BridgeMode.DISABLED


def test_get_bridge_singleton() -> None:
    """Test global bridge singleton."""
    bridge1 = get_claude_code_bridge()
    bridge2 = get_claude_code_bridge()

    assert bridge1 is bridge2  # Same instance


# =============================================================================
# TASK RESULT
# =============================================================================


def test_task_result_success() -> None:
    """Test successful task result."""
    result = TaskResult(
        success=True,
        colony_name="forge",
        colony_idx=1,
        output="Task completed successfully",
        latency_ms=123.4,
        correlation_id="abc123",
    )

    assert result.success
    assert not result.is_error
    assert result.colony_name == "forge"
    assert result.colony_idx == 1
    assert result.output == "Task completed successfully"
    assert result.latency_ms == 123.4


def test_task_result_error() -> None:
    """Test error task result."""
    result = TaskResult(
        success=False,
        colony_name="forge",
        colony_idx=1,
        error="Something went wrong",
        latency_ms=50.0,
    )

    assert not result.success
    assert result.is_error
    assert result.error == "Something went wrong"


# =============================================================================
# SPAWN COLONY AGENT
# =============================================================================


@pytest.mark.asyncio
async def test_spawn_agent_disabled() -> None:
    """Test spawning agent when bridge is disabled."""
    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.DISABLED))

    with pytest.raises(ValueError, match="bridge is disabled"):
        await bridge.spawn_colony_agent(colony_name="forge", task="Test task", params={})


@pytest.mark.asyncio
async def test_spawn_agent_invalid_colony() -> None:
    """Test spawning agent with invalid colony name."""
    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID))

    with pytest.raises(ValueError, match="Invalid colony name"):
        await bridge.spawn_colony_agent(colony_name="invalid", task="Test task", params={})


@pytest.mark.asyncio
async def test_spawn_agent_success() -> None:
    """Test spawning single colony agent."""
    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID))

    result = await bridge.spawn_colony_agent(
        colony_name="forge",
        task="Implement test module",
        params={"file": "test.py"},
    )

    assert isinstance(result, TaskResult)
    assert result.colony_name == "forge"
    assert result.colony_idx == 1
    assert result.success
    assert result.latency_ms > 0
    assert result.correlation_id  # Should be auto-generated


@pytest.mark.asyncio
async def test_spawn_agent_with_correlation_id() -> None:
    """Test spawning agent with explicit correlation ID."""
    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID))

    correlation_id = "test-123"
    result = await bridge.spawn_colony_agent(
        colony_name="spark",
        task="Brainstorm ideas",
        params={},
        correlation_id=correlation_id,
    )

    assert result.correlation_id == correlation_id


# =============================================================================
# PARALLEL AGENT SPAWNING
# =============================================================================


@pytest.mark.asyncio
async def test_spawn_parallel_agents() -> None:
    """Test parallel agent spawning (MAXIMUM PARALLELISM)."""
    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID, enable_parallel=True))

    tasks = [
        ("forge", "Task A", {"file": "a.py"}),
        ("forge", "Task B", {"file": "b.py"}),
        ("forge", "Task C", {"file": "c.py"}),
    ]

    results = await bridge.spawn_parallel_agents(tasks)

    assert len(results) == 3
    assert all(isinstance(r, TaskResult) for r in results)
    assert all(r.colony_name == "forge" for r in results)
    assert all(r.success for r in results)


@pytest.mark.asyncio
async def test_spawn_parallel_disabled() -> None:
    """Test parallel execution disabled (falls back to sequential)."""
    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID, enable_parallel=False))

    tasks = [
        ("spark", "Task 1", {}),
        ("forge", "Task 2", {}),
    ]

    results = await bridge.spawn_parallel_agents(tasks)

    assert len(results) == 2
    # Should still complete, just sequentially


@pytest.mark.asyncio
async def test_spawn_parallel_different_colonies() -> None:
    """Test parallel spawning with different colonies."""
    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID, enable_parallel=True))

    tasks = [
        ("spark", "Brainstorm", {}),
        ("beacon", "Plan architecture", {}),
        ("grove", "Research patterns", {}),
    ]

    results = await bridge.spawn_parallel_agents(tasks)

    assert len(results) == 3
    assert results[0].colony_name == "spark"
    assert results[1].colony_name == "beacon"
    assert results[2].colony_name == "grove"


@pytest.mark.asyncio
async def test_spawn_parallel_shared_correlation_id() -> None:
    """Test parallel spawning with shared correlation ID."""
    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID))

    correlation_id = "parallel-test-123"
    tasks = [
        ("forge", "Task A", {}),
        ("forge", "Task B", {}),
    ]

    results = await bridge.spawn_parallel_agents(tasks, correlation_id=correlation_id)

    assert all(r.correlation_id == correlation_id for r in results)


# =============================================================================
# FANO COMPOSITION ROUTING
# =============================================================================


def test_get_fano_composition_valid() -> None:
    """Test valid Fano composition lookup."""
    bridge = create_claude_code_bridge()

    # Test known composition
    result = bridge.get_fano_composition("spark", "forge")
    assert result == "flow"

    # Test reverse order (should work due to symmetry)
    result = bridge.get_fano_composition("forge", "spark")
    assert result == "flow"


def test_get_fano_composition_invalid() -> None:
    """Test invalid Fano composition (not on same line)."""
    bridge = create_claude_code_bridge()

    # spark and spark are not a valid pair
    result = bridge.get_fano_composition("spark", "spark")
    assert result is None


def test_get_fano_composition_completeness() -> None:
    """Verify all Fano compositions are defined."""
    from kagami_math.fano_plane import FANO_LINES

    bridge = create_claude_code_bridge()

    # Check all Fano lines have valid compositions
    for i, j, k in FANO_LINES:
        source = COLONY_TO_SUBAGENT[i - 1]  # Fano uses 1-indexed
        partner = COLONY_TO_SUBAGENT[j - 1]
        expected_result = COLONY_TO_SUBAGENT[k - 1]

        result = bridge.get_fano_composition(source, partner)

        assert (
            result == expected_result
        ), f"Composition mismatch: {source} × {partner} = {result}, expected {expected_result}"


@pytest.mark.asyncio
async def test_execute_fano_line() -> None:
    """Test full Fano line execution (3 colonies)."""
    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID))

    results = await bridge.execute_fano_line(
        source="beacon",
        partner="forge",
        task="Design and build test module",
        params={"output": "test.py"},
    )

    assert len(results) == 3
    assert results[0].colony_name == "beacon"  # Phase 1a
    assert results[1].colony_name == "forge"  # Phase 1b
    assert results[2].colony_name == "crystal"  # Phase 2 synthesis (beacon × forge = crystal)

    # All should share correlation ID
    correlation_ids = [r.correlation_id for r in results]
    assert len(set(correlation_ids)) == 1  # All same


@pytest.mark.asyncio
async def test_execute_fano_line_invalid() -> None:
    """Test Fano line execution with invalid pair."""
    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID))

    with pytest.raises(ValueError, match="Invalid Fano line"):
        await bridge.execute_fano_line(
            source="spark",
            partner="spark",  # Invalid: same colony
            task="Test task",
            params={},
        )


# =============================================================================
# PROMPT CONSTRUCTION
# =============================================================================


def test_build_agent_prompt() -> None:
    """Test prompt construction for Claude agents."""
    bridge = create_claude_code_bridge()

    prompt = bridge._build_agent_prompt(
        colony_name="forge",
        task="Implement authentication module",
        params={"file_path": "kagami/auth.py", "style": "jwt"},
    )

    # Check prompt contains key elements
    assert "implementation specialist" in prompt.lower()
    assert "Implement authentication module" in prompt
    assert "file_path: kagami/auth.py" in prompt
    assert "style: jwt" in prompt
    assert "h(x) ≥ 0" in prompt  # Safety constraint


def test_build_agent_prompt_all_colonies() -> None:
    """Test prompt construction for all colony types."""
    bridge = create_claude_code_bridge()

    for colony_name in COLONY_TO_SUBAGENT.values():
        prompt = bridge._build_agent_prompt(
            colony_name=colony_name, task=f"Test task for {colony_name}", params={}
        )

        assert colony_name in prompt or colony_name.capitalize() in prompt
        assert "h(x) ≥ 0" in prompt  # All prompts include safety


# =============================================================================
# TASK SELECTION HEURISTICS
# =============================================================================


def test_should_use_claude_code_file_tasks() -> None:
    """File manipulation tasks should prefer Claude Code."""
    # File editing
    assert should_use_claude_code("implement", {"file_path": "test.py"})
    assert should_use_claude_code("build", {"edit_file": "test.py"})


def test_should_use_claude_code_web_tasks() -> None:
    """Web research tasks should prefer Claude Code."""
    assert should_use_claude_code("research", {"use_web": True})
    assert should_use_claude_code("investigate", {"use_web": True})


def test_should_use_claude_code_compute_tasks() -> None:
    """Compute tasks should prefer Python."""
    assert not should_use_claude_code("train", {"model": "world_model"})
    assert not should_use_claude_code("optimize", {"epochs": 100})
    assert not should_use_claude_code("compute", {"tensor": "..."})


def test_should_use_claude_code_explicit() -> None:
    """Explicit flag should override heuristics."""
    # Force Claude Code regardless of task type
    assert should_use_claude_code("compute", {"force_claude_code": True})


# =============================================================================
# STATS & MONITORING
# =============================================================================


@pytest.mark.asyncio
async def test_bridge_stats() -> None:
    """Test bridge statistics tracking."""
    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID))

    # Execute some tasks
    await bridge.spawn_colony_agent("forge", "Task 1", {})
    await bridge.spawn_colony_agent("spark", "Task 2", {})

    stats = bridge.get_stats()

    assert stats["mode"] == BridgeMode.HYBRID.value
    assert stats["model"] == "sonnet"
    assert stats["total_executions"] == 2
    assert "config" in stats


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_plan_execute_verify_pattern() -> None:
    """Test standard PLAN-EXECUTE-VERIFY pattern via Fano lines."""
    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID))

    # PLAN: Beacon designs architecture
    plan_result = await bridge.spawn_colony_agent(
        colony_name="beacon",
        task="Design authentication system architecture",
        params={"output_format": "diagram"},
    )

    assert plan_result.success

    # EXECUTE: Forge implements based on plan
    exec_result = await bridge.spawn_colony_agent(
        colony_name="forge",
        task="Implement authentication based on architecture",
        params={
            "plan": plan_result.output,
            "file_path": "kagami/auth.py",
        },
    )

    assert exec_result.success

    # VERIFY: Crystal validates implementation
    verify_result = await bridge.spawn_colony_agent(
        colony_name="crystal",
        task="Verify authentication implementation",
        params={
            "file_path": "kagami/auth.py",
            "spec": plan_result.output,
        },
    )

    assert verify_result.success


@pytest.mark.asyncio
async def test_maximum_parallelism_pattern() -> None:
    """Test MAXIMUM PARALLELISM pattern from CLAUDE.md."""
    bridge = create_claude_code_bridge(
        BridgeConfig(mode=BridgeMode.HYBRID, enable_parallel=True, max_concurrent=7)
    )

    # Launch all 7 colonies in parallel (one task each)
    tasks = [
        ("spark", "Brainstorm authentication strategies", {}),
        ("beacon", "Design auth architecture", {}),
        ("grove", "Research auth best practices", {}),
        ("forge", "Implement auth module", {}),
        ("nexus", "Integrate with existing system", {}),
        ("flow", "Debug auth flow", {}),
        ("crystal", "Verify auth security", {}),
    ]

    results = await bridge.spawn_parallel_agents(tasks)

    assert len(results) == 7
    assert all(r.success for r in results)

    # Each colony should be represented
    colony_names = [r.colony_name for r in results]
    assert set(colony_names) == set(COLONY_TO_SUBAGENT.values())


# =============================================================================
# ERROR HANDLING
# =============================================================================


@pytest.mark.asyncio
async def test_error_handling_invalid_params() -> None:
    """Test error handling for invalid parameters."""
    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.HYBRID))

    # Invalid colony name
    with pytest.raises(ValueError):
        await bridge.spawn_colony_agent(colony_name="invalid_colony", task="Test", params={})


@pytest.mark.asyncio
async def test_error_handling_disabled_mode() -> None:
    """Test error handling when bridge is disabled."""
    bridge = create_claude_code_bridge(BridgeConfig(mode=BridgeMode.DISABLED))

    with pytest.raises(ValueError, match="disabled"):
        await bridge.spawn_colony_agent(colony_name="forge", task="Test", params={})


# =============================================================================
# CONFIGURATION
# =============================================================================


def test_bridge_mode_enum() -> None:
    """Test BridgeMode enum values."""
    assert BridgeMode.DISABLED.value == "disabled"
    assert BridgeMode.HYBRID.value == "hybrid"
    assert BridgeMode.CLAUDE_ONLY.value == "claude_only"


def test_config_custom() -> None:
    """Test custom bridge configuration."""
    config = BridgeConfig(
        mode=BridgeMode.CLAUDE_ONLY,
        timeout_seconds=300.0,
        model="opus",
        enable_parallel=False,
        max_concurrent=3,
    )

    assert config.mode == BridgeMode.CLAUDE_ONLY
    assert config.timeout_seconds == 300.0
    assert config.model == "opus"
    assert config.enable_parallel is False
    assert config.max_concurrent == 3


# =============================================================================
# EXPORTS
# =============================================================================


def test_exports() -> None:
    """Verify all expected symbols are exported."""
    from kagami.orchestration.claude_code_bridge import __all__

    expected = [
        "ClaudeCodeTaskBridge",
        "BridgeConfig",
        "BridgeMode",
        "TaskResult",
        "create_claude_code_bridge",
        "get_claude_code_bridge",
        "set_claude_code_bridge",
        "should_use_claude_code",
        "COLONY_TO_SUBAGENT",
        "SUBAGENT_TO_COLONY",
        "FANO_COMPOSITION",
    ]

    for symbol in expected:
        assert symbol in __all__, f"Missing export: {symbol}"
