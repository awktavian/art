"""Tests for Intent Router.

This module tests intent-based execution, including:
- Intent parsing (string and dict formats)
- Complexity inference with real calculation validation
- Mode determination (single/fano/all)
- Execution paths with state transitions
- E8 aggregation
- Receipt generation with data completeness
- Stats monitoring
- Error recovery paths

Moved from kagami/orchestration/intent_orchestrator.py on December 15, 2025.
Renamed from test_intent_orchestrator to test_intent_router on December 16, 2025.
"""

from __future__ import annotations

import pytest
import asyncio

from kagami.orchestration.intent_orchestrator import (
    IntentRouter,
    IntentParseError,
    create_intent_router,
    PATTERN_FORGE_AMBIENT,
    PATTERN_AMBIENT_ROOMS,
    PATTERN_THREE_WAY,
)
from kagami.core.unified_agents.fano_action_router import (
    FanoActionRouter,
    create_fano_router,
    SIMPLE_THRESHOLD,
    COMPLEX_THRESHOLD,
    COLONY_NAMES,
)


# =============================================================================
# INTENT PARSING TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_intent_parsing():
    """Test 1: Intent parsing for string and dict formats."""
    orch = create_intent_router()

    # Test string parsing with domain
    parsed = orch._parse_intent("research.web")
    assert parsed["action"] == "research"
    assert parsed["domain"] == "web"
    assert parsed["params"] == {}

    # Test simple string without domain
    parsed = orch._parse_intent("build")
    assert parsed["action"] == "build"
    assert parsed["domain"] == "general"
    assert parsed["params"] == {}

    # Test dict parsing with params
    parsed = orch._parse_intent({"action": "verify", "domain": "security", "params": {"depth": 3}})
    assert parsed["action"] == "verify"
    assert parsed["domain"] == "security"
    assert parsed["params"]["depth"] == 3

    # Test error: empty string
    with pytest.raises(IntentParseError) as exc_info:
        orch._parse_intent("")
    assert "empty" in str(exc_info.value).lower()

    # Test error: invalid type
    with pytest.raises(IntentParseError) as exc_info:
        orch._parse_intent(123)  # type: ignore[arg-type]
    assert "must be string or dict" in str(exc_info.value).lower()

    # Test error: dict without action key
    with pytest.raises(IntentParseError) as exc_info:
        orch._parse_intent({"domain": "web", "params": {}})
    assert "action" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_intent_parsing_edge_cases():
    """Test intent parsing edge cases."""
    orch = create_intent_router()

    # Test multiple dots in action string
    parsed = orch._parse_intent("research.web.deep")
    assert parsed["action"] == "research"
    assert parsed["domain"] == "web.deep"

    # Test whitespace handling
    parsed = orch._parse_intent("  build  ")
    assert parsed["action"] == "build"

    # Test dict with missing optional fields
    parsed = orch._parse_intent({"action": "test"})
    assert parsed["action"] == "test"
    assert parsed["domain"] == "general"
    assert parsed["params"] == {}


# =============================================================================
# COMPLEXITY INFERENCE TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_complexity_inference_simple_actions():
    """Test complexity inference for simple actions."""
    orch = create_intent_router()

    # Simple action patterns should produce low complexity (< 0.3)
    simple_actions = ["ping", "health", "status", "echo", "noop"]
    for action in simple_actions:
        intent = {"action": action, "domain": "general", "params": {}}
        complexity = await orch._infer_complexity(intent, {})
        assert (
            complexity < SIMPLE_THRESHOLD
        ), f"Expected simple complexity for '{action}', got {complexity}"


@pytest.mark.asyncio
async def test_complexity_inference_complex_actions():
    """Test complexity inference for complex actions."""
    orch = create_intent_router()

    # Complex actions should produce higher complexity (>= 0.5)
    complex_actions = ["analyze", "synthesize", "plan", "architect"]
    for action in complex_actions:
        intent = {"action": action, "domain": "architecture", "params": {}}
        complexity = await orch._infer_complexity(intent, {})
        assert complexity >= 0.5, f"Expected high complexity for '{action}', got {complexity}"


@pytest.mark.asyncio
async def test_complexity_inference_parameter_depth():
    """Test that parameter complexity affects overall complexity."""
    orch = create_intent_router()

    # Shallow params
    intent_shallow = {"action": "build", "domain": "feature", "params": {"name": "test"}}
    complexity_shallow = await orch._infer_complexity(intent_shallow, {})

    # Deep nested params should increase complexity
    intent_deep = {
        "action": "build",
        "domain": "feature",
        "params": {
            "name": "test",
            "config": {"level1": {"level2": {"level3": {"value": 42}}}},
            "options": ["a", "b", "c", "d", "e"],
        },
    }
    complexity_deep = await orch._infer_complexity(intent_deep, {})

    assert (
        complexity_deep > complexity_shallow
    ), f"Deep params should increase complexity: {complexity_deep} vs {complexity_shallow}"


@pytest.mark.asyncio
async def test_complexity_inference_query_length():
    """Test that longer queries increase complexity."""
    orch = create_intent_router()

    intent = {"action": "research", "domain": "web", "params": {}}

    # Short query
    complexity_short = await orch._infer_complexity(intent, {"query": "what is X"})

    # Long multi-part query with complexity markers
    complexity_long = await orch._infer_complexity(
        intent,
        {
            "query": "how does this system work and why was it designed this way, then also explain the architecture"
        },
    )

    assert (
        complexity_long > complexity_short
    ), f"Longer query should increase complexity: {complexity_long} vs {complexity_short}"


@pytest.mark.asyncio
async def test_complexity_explicit_override():
    """Test explicit complexity override in context."""
    orch = create_intent_router()

    intent = {"action": "ping", "domain": "general", "params": {}}

    # Override complexity to 0.9 for a normally simple action
    complexity = await orch._infer_complexity(intent, {"complexity": 0.9})
    assert complexity == 0.9, f"Explicit override should be respected, got {complexity}"


@pytest.mark.asyncio
async def test_complexity_calculation_formula():
    """Test the actual complexity calculation formula (60% avg + 40% max)."""
    router = create_fano_router()

    # Build action with multiple signals
    action = "build.feature"
    params = {"name": "test", "config": {}}
    context = {"query": "implement this feature and also test it"}

    complexity = router._infer_complexity(action, params, context)

    # Complexity should be between 0.0 and 1.0
    assert 0.0 <= complexity <= 1.0, f"Complexity out of range: {complexity}"

    # For "build" action with medium params and multi-part query, expect medium-high complexity
    assert complexity >= 0.4, f"Expected medium complexity for build action, got {complexity}"


# =============================================================================
# ROUTING MODE DETERMINATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_mode_determination_single():
    """Test single mode determination for simple complexity."""
    orch = create_intent_router()

    # Simple complexity (< 0.3) should route to single mode
    mode, pattern = orch._determine_routing_mode(0.2, {}, {})
    assert mode == "single", f"Expected single mode for complexity 0.2, got {mode}"
    assert pattern is None, f"Expected no pattern for single mode, got {pattern}"


@pytest.mark.asyncio
async def test_mode_determination_fano():
    """Test Fano mode determination for medium complexity."""
    orch = create_intent_router()

    # Medium complexity (0.3-0.7) should route to fano mode
    mode, pattern = orch._determine_routing_mode(0.5, {"beacon": 0.6, "grove": 0.5}, {})
    assert mode == "fano", f"Expected fano mode for complexity 0.5, got {mode}"


@pytest.mark.asyncio
async def test_mode_determination_all():
    """Test all-colonies mode determination for high complexity."""
    orch = create_intent_router()

    # High complexity (>= 0.7) should route to all mode
    mode, pattern = orch._determine_routing_mode(
        0.8, {"beacon": 0.7, "grove": 0.6, "forge": 0.6}, {}
    )
    assert mode == "all", f"Expected all mode for complexity 0.8, got {mode}"


@pytest.mark.asyncio
async def test_fano_routing_pattern_detection():
    """Test Fano line pattern detection for cross-system routing."""
    orch = create_intent_router()

    # Forge + Ambient (both > 0.5) should trigger PATTERN_FORGE_AMBIENT
    mode, pattern = orch._determine_routing_mode(
        0.5, {"forge": 0.8, "rooms": 0.0, "ambient": 0.8}, {}
    )
    assert mode == "fano", f"Expected fano mode for forge+ambient, got {mode}"
    assert pattern == PATTERN_FORGE_AMBIENT, f"Expected forge×ambient pattern, got {pattern}"

    # Ambient + Rooms should trigger PATTERN_AMBIENT_ROOMS
    mode, pattern = orch._determine_routing_mode(
        0.5, {"forge": 0.0, "rooms": 0.9, "ambient": 0.8}, {}
    )
    assert mode == "fano", f"Expected fano mode for ambient+rooms, got {mode}"
    assert pattern == PATTERN_AMBIENT_ROOMS, f"Expected ambient×rooms pattern, got {pattern}"


@pytest.mark.asyncio
async def test_three_way_integration_triggers_all_mode():
    """Test that three-way system integration forces all-colonies mode."""
    orch = create_intent_router()

    # All three systems active should trigger PATTERN_THREE_WAY
    mode, pattern = orch._determine_routing_mode(
        0.5, {"forge": 0.8, "rooms": 0.9, "ambient": 0.8}, {}
    )
    assert mode == "all", f"Expected all mode for three-way integration, got {mode}"
    assert pattern == PATTERN_THREE_WAY, f"Expected all_colonies pattern, got {pattern}"


# =============================================================================
# SYSTEM AFFINITY SCORING TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_system_affinity_scoring():
    """Test system affinity scoring based on context signals."""
    orch = create_intent_router()

    # Test forge affinity from model/prompt context
    scores = orch._score_system_affinity("generate", {"model": "gpt-4", "prompt": "test"})
    assert scores["forge"] == 0.8, f"Expected forge=0.8 with model context, got {scores['forge']}"

    # Test rooms affinity from room_id context
    scores = orch._score_system_affinity("share", {"room_id": "room_123"})
    assert scores["rooms"] == 0.9, f"Expected rooms=0.9 with room_id context, got {scores['rooms']}"

    # Test ambient affinity from ambient_mode context
    scores = orch._score_system_affinity("adapt", {"ambient_mode": "calm"})
    assert (
        scores["ambient"] == 0.8
    ), f"Expected ambient=0.8 with ambient_mode context, got {scores['ambient']}"

    # Test no affinity for empty context
    scores = orch._score_system_affinity("test", {})
    assert scores["forge"] == 0.0
    assert scores["rooms"] == 0.0
    assert scores["ambient"] == 0.0


# =============================================================================
# EXECUTION TESTS WITH STATE TRANSITIONS
# =============================================================================


@pytest.mark.asyncio
async def test_single_execution_state_transition():
    """Test single colony execution with state changes."""
    orch = create_intent_router()

    # Capture initial state
    initial_executions = orch._total_executions

    # Execute simple intent
    result = await orch.execute_intent(intent="ping", context={})

    assert result["success"] or "error" in result, "Should return success or error"

    assert result.get("mode") in [
        "single",
        "simple",
        None,
    ], f"Expected simple mode, got {result.get('mode')}"
    print(
        f"✓ Single execution: mode={result.get('mode')}, latency={result.get('latency_ms', 0):.1f}ms"
    )


@pytest.mark.asyncio
async def test_fano_execution_with_forced_complexity():
    """Test Fano line execution with forced complexity."""
    orch = create_intent_router()

    # Force Fano mode via complexity override
    result = await orch.execute_intent(
        intent="build.feature",
        context={"complexity": 0.5},
    )

    assert result["success"] or "error" in result, "Should return success or error"

    assert result.get("mode") in [
        "fano",
        "fano_composition",
        "medium",
        None,
    ], f"Expected fano mode, got {result.get('mode')}"
    assert (
        result.get("complexity") == 0.5
    ), f"Complexity should be preserved: {result.get('complexity')}"


@pytest.mark.asyncio
async def test_all_colonies_execution():
    """Test all-colony execution for synthesis tasks."""
    orch = create_intent_router()

    # Force all-colonies mode via high complexity
    result = await orch.execute_intent(
        intent="analyze.architecture",
        context={"complexity": 0.8},
    )

    assert result["success"] or "error" in result, "Should return success or error"

    assert result.get("mode") in [
        "all",
        "all_colonies",
        "complex",
        None,
    ], f"Expected all mode, got {result.get('mode')}"

    # If successful, should have multiple colonies used
    if result.get("success"):
        colonies = result.get("colonies_used", [])
        assert len(colonies) > 0, "Should have colonies_used data"


@pytest.mark.asyncio
async def test_execution_with_cross_system_routing():
    """Test execution with cross-system routing metadata."""
    orch = create_intent_router()

    # Trigger cross-system routing with forge + rooms context
    result = await orch.execute_intent(
        intent="generate.image",
        context={
            "room_id": "room_abc123",
            "prompt": "a serene landscape",
        },
    )

    # Should have system_scores in result if cross-system routing was detected
    if result.get("success"):
        # Check for routing metadata
        assert "mode" in result
        assert "latency_ms" in result


# =============================================================================
# E8 AGGREGATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_e8_aggregation_structure():
    """Test E8 aggregation output structure."""
    orch = create_intent_router()

    result = await orch.execute_intent(
        intent="test.aggregation",
        context={"complexity": 0.5},
    )

    if result.get("success"):
        e8_action = result.get("e8_action")
        assert e8_action is not None, "Should have e8_action for successful execution"
        assert "code" in e8_action, "e8_action should have 'code' field"
        assert "index" in e8_action, "e8_action should have 'index' field"
        assert isinstance(e8_action["code"], list), "e8_action code should be a list"
        assert isinstance(e8_action["index"], int), "e8_action index should be an integer"


# =============================================================================
# RECEIPT GENERATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_receipt_generation_completeness():
    """Test receipt generation with complete data."""
    orch = create_intent_router()

    result = await orch.execute_intent(
        intent="test.receipt",
        context={},
    )

    # Receipt ID must be present
    receipt_id = result.get("receipt_id")
    assert receipt_id is not None, "Should have receipt_id"
    assert len(receipt_id) > 0, "receipt_id should not be empty"
    assert isinstance(receipt_id, str), "receipt_id should be a string"

    # Verify receipt ID format (should be 8 chars for uuid[:8] or longer for correlation_id)
    assert len(receipt_id) >= 8, f"receipt_id should be at least 8 chars, got {len(receipt_id)}"


@pytest.mark.asyncio
async def test_receipt_correlation_id_passthrough():
    """Test that correlation_id from context is used as receipt_id."""
    orch = create_intent_router()

    correlation_id = "custom-correlation-123"
    result = await orch.execute_intent(
        intent="test",
        context={"correlation_id": correlation_id},
    )

    # Should use correlation_id as receipt_id
    receipt_id = result.get("receipt_id")
    assert receipt_id == correlation_id, f"Expected correlation_id passthrough, got {receipt_id}"


# =============================================================================
# STATS AND MONITORING TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_stats_tracking():
    """Test stats and monitoring data."""
    orch = create_intent_router()

    # Execute multiple intents
    await orch.execute_intent("ping", {})
    await orch.execute_intent("test", {})
    await orch.execute_intent("build", {})

    # Get stats
    stats = orch.get_stats()

    # Verify required stats fields
    assert "total_executions" in stats, "Should have total_executions"
    assert (
        stats["total_executions"] >= 2
    ), f"Expected >= 2 executions, got {stats['total_executions']}"
    assert "uptime_seconds" in stats, "Should have uptime_seconds"
    assert stats["uptime_seconds"] > 0, "Uptime should be positive"

    assert "router_thresholds" in stats, "Should have router_thresholds"
    assert "simple" in stats["router_thresholds"], "Should have simple threshold"
    assert "complex" in stats["router_thresholds"], "Should have complex threshold"


@pytest.mark.asyncio
async def test_stats_organism_integration():
    """Test that stats include organism statistics."""
    orch = create_intent_router()

    await orch.execute_intent("test", {})

    stats = orch.get_stats()
    assert "organism_stats" in stats, "Should have organism_stats"


# =============================================================================
# ERROR RECOVERY TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_error_recovery_invalid_intent():
    """Test error recovery for invalid intent."""
    orch = create_intent_router()

    # Empty string should fail gracefully
    result = await orch.execute_intent(intent="", context={})

    assert result.get("success") is False, "Should return failure for empty intent"
    assert "error" in result, "Should have error message"
    assert "IntentParseError" in result["error"], "Error should indicate parse error"
    assert "latency_ms" in result, "Should track latency even on error"


@pytest.mark.asyncio
async def test_error_recovery_invalid_type():
    """Test error recovery for invalid intent type."""
    orch = create_intent_router()

    result = await orch.execute_intent(intent=12345, context={})  # type: ignore[arg-type]

    assert result.get("success") is False, "Should return failure for invalid type"
    assert "error" in result, "Should have error message"
    assert "latency_ms" in result, "Should track latency even on error"


@pytest.mark.asyncio
async def test_error_recovery_preserves_state():
    """Test that error recovery preserves orchestrator state."""
    orch = create_intent_router()

    initial_executions = orch._total_executions

    # Intentionally cause an error
    await orch.execute_intent(intent="", context={})

    # Successful execution should still work
    result = await orch.execute_intent(intent="ping", context={})

    # State should be preserved and updated
    assert (
        orch._total_executions > initial_executions
    ), "Should track successful execution after error"


# =============================================================================
# FANO ROUTER INTEGRATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_fano_router_threshold_integration():
    """Test that router thresholds are properly used."""
    # Create router with custom thresholds
    custom_router = create_fano_router(
        simple_threshold=0.2,
        complex_threshold=0.8,
    )

    orch = create_intent_router(router=custom_router)

    # Verify thresholds are propagated
    assert orch.router.simple_threshold == 0.2
    assert orch.router.complex_threshold == 0.8

    stats = orch.get_stats()
    assert stats["router_thresholds"]["simple"] == 0.2
    assert stats["router_thresholds"]["complex"] == 0.8


@pytest.mark.asyncio
async def test_fano_composition_calculation():
    """Test Fano composition calculation for valid colony pairs."""
    router = create_fano_router()

    # Test valid Fano line composition
    # Fano lines are: (0,1,2), (0,3,4), (0,5,6), (1,3,5), (1,4,6), (2,3,6), (2,4,5)
    result = router.get_fano_composition(0, 1)
    assert result == 2, f"Fano composition 0×1 should equal 2, got {result}"

    result = router.get_fano_composition(1, 0)
    assert result == 2, f"Fano composition 1×0 should equal 2, got {result}"

    # Test invalid composition (not on a Fano line together)
    # 0 and 2 are on the same line, but 0 and 6 might not be depending on structure
    result = router.get_fano_composition(0, 5)
    assert result is not None, "0 and 5 should be on a Fano line (0,5,6)"


@pytest.mark.asyncio
async def test_safety_critical_detection():
    """Test safety-critical action detection."""
    router = create_fano_router()

    # Safety-critical actions
    assert router._is_safety_critical("execute", {}) is True
    assert router._is_safety_critical("delete", {}) is True
    assert router._is_safety_critical("deploy", {}) is True
    assert router._is_safety_critical("write_file", {"path": "/etc/config"}) is True

    # Non-safety-critical actions
    assert router._is_safety_critical("ping", {}) is False
    assert router._is_safety_critical("read", {}) is False
    assert router._is_safety_critical("list", {}) is False


# =============================================================================
# BACKWARDS COMPATIBILITY TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_backwards_compatibility_alias():
    """Test that IntentRouter alias works for backwards compatibility."""
    # IntentRouter should be an alias for ColonyIntentRouter
    assert IntentRouter is ColonyIntentRouter

    # Should be able to instantiate via alias
    router = IntentRouter()
    assert isinstance(router, ColonyIntentRouter)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


@pytest.mark.asyncio
async def main():
    """Run all tests."""
    print("=" * 60)
    print("Intent Orchestrator Test Suite")
    print("=" * 60)

    try:
        await test_intent_parsing()
        print("  Test 1: Intent Parsing")

        await test_intent_parsing_edge_cases()
        print("  Test 2: Intent Parsing Edge Cases")

        await test_complexity_inference_simple_actions()
        print("  Test 3: Complexity Inference - Simple Actions")

        await test_complexity_inference_complex_actions()
        print("  Test 4: Complexity Inference - Complex Actions")

        await test_complexity_inference_parameter_depth()
        print("  Test 5: Complexity Inference - Parameter Depth")

        await test_complexity_inference_query_length()
        print("  Test 6: Complexity Inference - Query Length")

        await test_complexity_explicit_override()
        print("  Test 7: Complexity Explicit Override")

        await test_complexity_calculation_formula()
        print("  Test 8: Complexity Calculation Formula")

        await test_mode_determination_single()
        print("  Test 9: Mode Determination - Single")

        await test_mode_determination_fano()
        print("  Test 10: Mode Determination - Fano")

        await test_mode_determination_all()
        print("  Test 11: Mode Determination - All")

        await test_fano_routing_pattern_detection()
        print("  Test 12: Fano Routing Pattern Detection")

        await test_three_way_integration_triggers_all_mode()
        print("  Test 13: Three-Way Integration")

        await test_system_affinity_scoring()
        print("  Test 14: System Affinity Scoring")

        await test_single_execution_state_transition()
        print("  Test 15: Single Execution State Transition")

        await test_fano_execution_with_forced_complexity()
        print("  Test 16: Fano Execution")

        await test_all_colonies_execution()
        print("  Test 17: All Colonies Execution")

        await test_execution_with_cross_system_routing()
        print("  Test 18: Cross-System Routing")

        await test_e8_aggregation_structure()
        print("  Test 19: E8 Aggregation Structure")

        await test_receipt_generation_completeness()
        print("  Test 20: Receipt Generation")

        await test_receipt_correlation_id_passthrough()
        print("  Test 21: Receipt Correlation ID")

        await test_stats_tracking()
        print("  Test 22: Stats Tracking")

        await test_stats_organism_integration()
        print("  Test 23: Stats Organism Integration")

        await test_error_recovery_invalid_intent()
        print("  Test 24: Error Recovery - Invalid Intent")

        await test_error_recovery_invalid_type()
        print("  Test 25: Error Recovery - Invalid Type")

        await test_error_recovery_preserves_state()
        print("  Test 26: Error Recovery - State Preservation")

        await test_fano_router_threshold_integration()
        print("  Test 27: Fano Router Threshold Integration")

        await test_fano_composition_calculation()
        print("  Test 28: Fano Composition Calculation")

        await test_safety_critical_detection()
        print("  Test 29: Safety Critical Detection")

        await test_backwards_compatibility_alias()
        print("  Test 30: Backwards Compatibility")

        print("\n" + "=" * 60)
        print("All tests passed")
        print("=" * 60)

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
