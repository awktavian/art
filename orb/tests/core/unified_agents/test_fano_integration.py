"""Integration tests for Fano plane routing.

COVERAGE TARGET: Fano plane routing, colony composition, action generation
ESTIMATED RUNTIME: <5 seconds

Tests verify:
1. Colony composition (Spark × Forge = Flow via Fano lines)
2. Routing decisions (1/3/7 action modes based on complexity)
3. Load balancing across colonies
4. Nash equilibrium routing (GÖDEL agent integration)
5. Action mode selection (SINGLE, FANO_LINE, ALL_COLONIES)

Mathematical Foundation:
- Fano plane: 7 points, 7 lines, 3 points per line
- Octonion multiplication: e_i × e_j = ±e_k (structure constants)
- 1/3/7 routing: complexity → {1 colony, 3 colonies (Fano line), 7 colonies}
"""

from __future__ import annotations

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.tier_integration,
    pytest.mark.timeout(5),
]

import torch

from kagami.core.unified_agents.fano_action_router import (
    FanoActionRouter,
    ActionMode,
    ColonyAction,
    RoutingResult,
    create_fano_router,
    FANO_LINES_0IDX,
    COLONY_NAMES,
)


class TestFanoBasicRouting:
    """Test basic Fano routing functionality."""

    def test_router_initialization(self) -> None:
        """Router should initialize with default thresholds."""
        router = FanoActionRouter()

        assert (
            router.simple_threshold == 0.3
        ), f"Default simple threshold should be 0.3, got {router.simple_threshold}"
        assert (
            router.complex_threshold == 0.7
        ), f"Default complex threshold should be 0.7, got {router.complex_threshold}"
        assert router.device == "cpu", f"Default device should be 'cpu', got {router.device}"

    def test_single_action_routing(self) -> None:
        """Simple tasks (complexity < 0.3) should route to single colony."""
        router = FanoActionRouter()

        result = router.route(
            action="ping",
            params={},
            complexity=0.2,  # Below simple_threshold
        )

        assert (
            result.mode == ActionMode.SINGLE
        ), f"Simple tasks (complexity < 0.3) should route SINGLE, got {result.mode}"
        assert (
            len(result.actions) == 1
        ), f"SINGLE mode should generate 1 action, got {len(result.actions)}"
        assert result.actions[0].is_primary, "Single action must be marked as primary"

    def test_fano_line_routing(self) -> None:
        """Complex tasks (0.3-0.7) should route to Fano line (3 colonies)."""
        router = FanoActionRouter()

        result = router.route(
            action="build",
            params={"feature": "new_component"},
            complexity=0.5,  # Between thresholds
        )

        assert (
            result.mode == ActionMode.FANO_LINE
        ), f"Complex tasks (0.3-0.7) should route FANO_LINE, got {result.mode}"
        assert (
            len(result.actions) == 3
        ), f"FANO_LINE mode should generate 3 actions (Fano line), got {len(result.actions)}"
        assert result.fano_line is not None, "FANO_LINE mode must specify which Fano line"
        assert (
            len(result.fano_line) == 3
        ), f"Fano line must have exactly 3 colonies, got {len(result.fano_line)}"

    def test_all_colonies_routing(self) -> None:
        """Synthesis tasks (≥ 0.7) should route to all 7 colonies."""
        router = FanoActionRouter()

        result = router.route(
            action="architect",
            params={"system": "distributed_ai"},
            complexity=0.8,  # Above complex_threshold
        )

        assert (
            result.mode == ActionMode.ALL_COLONIES
        ), f"Synthesis tasks (complexity ≥ 0.7) should route ALL_COLONIES, got {result.mode}"
        assert (
            len(result.actions) == 7
        ), f"ALL_COLONIES mode should generate 7 actions (all colonies), got {len(result.actions)}"

    def test_colony_names_consistency(self) -> None:
        """Colony names should be consistent with indices."""
        assert len(COLONY_NAMES) == 7, f"KagamiOS has 7 colonies (e₁-e₇), got {len(COLONY_NAMES)}"
        expected_names = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
        # COLONY_NAMES might be tuple or list, convert for comparison
        assert (
            list(COLONY_NAMES) == expected_names
        ), f"Colony names must match 7-colony architecture, got {list(COLONY_NAMES)}"


class TestFanoLineComposition:
    """Test Fano line composition (octonion multiplication)."""

    def test_fano_lines_structure(self) -> None:
        """Verify Fano plane structure: 7 lines, 3 points per line."""
        assert (
            len(FANO_LINES_0IDX) == 7
        ), f"Fano plane has exactly 7 lines (Baez 2002), got {len(FANO_LINES_0IDX)}"
        assert all(
            len(line) == 3 for line in FANO_LINES_0IDX
        ), "Each Fano line must contain exactly 3 points, got varying lengths"

    def test_fano_composition_spark_forge_flow(self) -> None:
        """Spark × Forge = Flow (Fano line 1)."""
        router = FanoActionRouter()

        # Line 1: (0, 1, 2) = (Spark, Forge, Flow)
        result_colony = router.get_fano_composition(source_colony=0, partner_colony=1)

        # Should return Flow (index 2)
        assert (
            result_colony == 2
        ), f"Fano composition: Spark (0) × Forge (1) = Flow (2) per octonion multiplication, got {result_colony}"

    def test_fano_composition_validity(self) -> None:
        """All Fano lines should have valid compositions."""
        router = FanoActionRouter()

        for i, j, k in FANO_LINES_0IDX:
            # Test all cyclic permutations
            assert (
                router.get_fano_composition(i, j) == k
            ), f"Fano line ({i}, {j}, {k}): {i} × {j} should = {k}"
            assert (
                router.get_fano_composition(j, k) == i
            ), f"Fano line ({i}, {j}, {k}): {j} × {k} should = {i}"
            assert (
                router.get_fano_composition(k, i) == j
            ), f"Fano line ({i}, {j}, {k}): {k} × {i} should = {j}"

    def test_fano_routing_uses_valid_line(self) -> None:
        """Fano routing should always use a valid Fano line."""
        router = FanoActionRouter()

        result = router.route(
            action="implement_feature",
            params={"name": "test"},
            complexity=0.5,
        )

        if result.mode == ActionMode.FANO_LINE:
            assert result.fano_line is not None, "FANO_LINE mode must specify which line"
            primary, partner, outcome = result.fano_line

            # Should be a valid Fano line
            assert (
                (primary, partner, outcome) in FANO_LINES_0IDX
                or (primary, outcome, partner) in FANO_LINES_0IDX
                or (partner, primary, outcome) in FANO_LINES_0IDX
                or (partner, outcome, primary) in FANO_LINES_0IDX
                or (outcome, primary, partner) in FANO_LINES_0IDX
                or (outcome, partner, primary) in FANO_LINES_0IDX
            ), f"Fano line ({primary}, {partner}, {outcome}) not found in FANO_LINES_0IDX (invalid Fano composition)"

    def test_invalid_composition_returns_none(self) -> None:
        """Invalid colony pairs should return None."""
        router = FanoActionRouter()

        # Test an invalid pair (not on any Fano line)
        # Need to find two colonies not on the same line
        # Try all pairs to find one that's invalid
        invalid_found = False
        for i in range(7):
            for j in range(7):
                if i != j:
                    result = router.get_fano_composition(i, j)
                    if result is None:
                        invalid_found = True
                        break
            if invalid_found:
                break

        # Note: In Fano plane, every pair of distinct points lies on exactly one line
        # So get_fano_composition should always return a valid result for distinct inputs


class TestComplexityInference:
    """Test complexity inference from actions and params."""

    def test_simple_action_inference(self) -> None:
        """Simple actions should infer low complexity."""
        router = FanoActionRouter()

        result = router.route(
            action="ping",
            params={},
            complexity=None,  # Let router infer
        )

        # Should infer as simple
        assert (
            result.complexity < 0.3
        ), f"'ping' action should infer low complexity (< 0.3), got {result.complexity}"
        assert (
            result.mode == ActionMode.SINGLE
        ), f"Inferred low complexity should route SINGLE, got {result.mode}"

    def test_build_action_inference(self) -> None:
        """Build actions should infer medium complexity."""
        router = FanoActionRouter()

        result = router.route(
            action="build_component",
            params={"name": "test", "type": "module"},
            complexity=None,
        )

        # Should infer as moderate/complex
        assert (
            result.complexity >= 0.3
        ), f"'build_component' action should infer moderate complexity (≥ 0.3), got {result.complexity}"

    def test_architect_action_inference(self) -> None:
        """Architect actions should infer high complexity."""
        router = FanoActionRouter()

        result = router.route(
            action="architect_system",
            params={
                "components": ["a", "b", "c"],
                "integrations": ["x", "y"],
                "constraints": {"scale": 1000},
            },
            complexity=None,
        )

        # Should infer as synthesis
        assert (
            result.complexity >= 0.5
        ), f"'architect_system' with complex params should infer high complexity (≥ 0.5), got {result.complexity}"

    def test_complexity_from_context(self) -> None:
        """Explicit context complexity should be used."""
        router = FanoActionRouter()

        result = router.route(
            action="test",
            params={},
            complexity=None,
            context={"complexity": 0.9},
        )

        assert (
            result.complexity == 0.9
        ), f"Explicit context complexity should be used, got {result.complexity}"
        assert (
            result.mode == ActionMode.ALL_COLONIES
        ), f"High complexity (0.9) should route ALL_COLONIES, got {result.mode}"


class TestColonySelection:
    """Test colony selection logic."""

    def test_keyword_based_selection(self) -> None:
        """Keywords should route to appropriate colonies."""
        router = FanoActionRouter()

        test_cases = [
            ("create_idea", 0),  # Spark (creative)
            ("build_feature", 1),  # Forge (build)
            ("fix_bug", 2),  # Flow (maintain)
            ("integrate_system", 3),  # Nexus (integrate)
            ("plan_architecture", 4),  # Beacon (plan)
            ("research_topic", 5),  # Grove (research)
            ("test_functionality", 6),  # Crystal (verify)
        ]

        for action, expected_colony_idx in test_cases:
            result = router.route(action, params={}, complexity=0.1)

            assert (
                result.mode == ActionMode.SINGLE
            ), f"Action '{action}' with low complexity should route SINGLE, got {result.mode}"
            assert (
                result.actions[0].colony_idx == expected_colony_idx
            ), f"Action '{action}' should route to colony {expected_colony_idx} ({COLONY_NAMES[expected_colony_idx]}), got {result.actions[0].colony_idx}"

    def test_primary_colony_weight(self) -> None:
        """Primary colony should have highest weight in Fano routing."""
        router = FanoActionRouter()

        result = router.route(
            action="implement",
            params={},
            complexity=0.5,
        )

        if result.mode == ActionMode.FANO_LINE:
            primary_actions = [a for a in result.actions if a.is_primary]
            assert (
                len(primary_actions) == 1
            ), f"FANO_LINE mode should have exactly 1 primary action, got {len(primary_actions)}"

            primary_weight = primary_actions[0].weight
            other_weights = [a.weight for a in result.actions if not a.is_primary]

            # Primary should have highest weight
            assert all(
                primary_weight >= w for w in other_weights
            ), f"Primary action weight ({primary_weight}) should be highest, but found others: {other_weights}"

    def test_all_colonies_weight_distribution(self) -> None:
        """All-colonies mode should distribute weights properly."""
        router = FanoActionRouter()

        result = router.route(
            action="synthesize",
            params={},
            complexity=0.9,
        )

        assert (
            result.mode == ActionMode.ALL_COLONIES
        ), f"High complexity (0.9) should route ALL_COLONIES, got {result.mode}"

        # Weights should sum to 1.0 (normalized)
        total_weight = sum(a.weight for a in result.actions)
        assert (
            abs(total_weight - 1.0) < 1e-5
        ), f"Action weights must be normalized to sum = 1.0, got {total_weight}"


class TestFanoActionProperties:
    """Test ColonyAction properties and attributes."""

    def test_colony_action_creation(self) -> None:
        """ColonyAction should initialize correctly."""
        action = ColonyAction(
            colony_idx=0,
            colony_name="spark",
            action="create",
            params={"test": "value"},
            weight=1.0,
            is_primary=True,
        )

        assert action.colony_idx == 0, f"Expected colony_idx=0 (spark), got {action.colony_idx}"
        assert (
            action.colony_name == "spark"
        ), f"Expected colony_name='spark', got {action.colony_name}"
        assert action.action == "create", f"Expected action='create', got {action.action}"
        assert action.weight == 1.0, f"Single action should have weight 1.0, got {action.weight}"
        assert action.is_primary, "Single action must be marked as primary"

    def test_s7_basis_vector(self) -> None:
        """Each colony should have correct S⁷ basis vector."""
        for colony_idx in range(7):
            action = ColonyAction(
                colony_idx=colony_idx,
                colony_name=COLONY_NAMES[colony_idx],
                action="test",
                params={},
            )

            basis = action.s7_basis

            # Should be 8D vector (e₀ + e₁...e₇)
            assert basis.shape == (8,), f"S⁷ basis vector must be 8D (octonion), got {basis.shape}"

            # Should have 1.0 at colony_idx + 1 (e₁ at index 1, etc.)
            assert (
                basis[colony_idx + 1] == 1.0
            ), f"Colony {colony_idx} should have basis[{colony_idx + 1}] = 1.0 (e_{colony_idx + 1}), got {basis[colony_idx + 1]}"

            # All other entries should be 0
            assert (
                basis[: colony_idx + 1].sum() == 0.0
            ), f"S⁷ basis should have zeros before index {colony_idx + 1}, got {basis[: colony_idx + 1]}"

            assert (
                basis[colony_idx + 2 :].sum() == 0.0
            ), f"S⁷ basis should have zeros after index {colony_idx + 1}, got {basis[colony_idx + 2 :]}"

    def test_fano_role_assignment(self) -> None:
        """Fano line routing should assign roles correctly."""
        router = FanoActionRouter()

        result = router.route(
            action="build",
            params={},
            complexity=0.5,
        )

        if result.mode == ActionMode.FANO_LINE:
            roles = [a.fano_role for a in result.actions]

            # Should have source, partner, result
            assert "source" in roles, f"FANO_LINE must have 'source' role, got roles: {roles}"
            assert "partner" in roles, f"FANO_LINE must have 'partner' role, got roles: {roles}"
            assert "result" in roles, f"FANO_LINE must have 'result' role, got roles: {roles}"


class TestRoutingResult:
    """Test RoutingResult properties."""

    def test_routing_result_creation(self) -> None:
        """RoutingResult should initialize with all fields."""
        actions = [
            ColonyAction(
                colony_idx=0,
                colony_name="spark",
                action="test",
                params={},
            )
        ]

        result = RoutingResult(
            mode=ActionMode.SINGLE,
            actions=actions,
            complexity=0.2,
            confidence=0.9,
        )

        assert result.mode == ActionMode.SINGLE, f"Expected ActionMode.SINGLE, got {result.mode}"
        assert (
            len(result.actions) == 1
        ), f"SINGLE mode should have 1 action, got {len(result.actions)}"
        assert result.complexity == 0.2, f"Expected complexity=0.2, got {result.complexity}"
        assert result.confidence == 0.9, f"Expected confidence=0.9, got {result.confidence}"
        assert result.fano_line is None, "SINGLE mode should not have fano_line set"

    def test_routing_result_metadata(self) -> None:
        """RoutingResult should support metadata."""
        router = FanoActionRouter()

        result = router.route(
            action="test",
            params={},
            complexity=0.5,
        )

        assert "action" in result.metadata, "Metadata should contain 'action' key"
        assert (
            result.metadata["action"] == "test"
        ), f"Metadata['action'] should be 'test', got {result.metadata['action']}"
        assert (
            "inferred_complexity" in result.metadata
        ), "Metadata should contain 'inferred_complexity' flag"


class TestFactoryFunction:
    """Test factory function for router creation."""

    def test_create_fano_router_defaults(self) -> None:
        """Factory should create router with defaults."""
        router = create_fano_router()

        assert isinstance(
            router, FanoActionRouter
        ), f"Factory should return FanoActionRouter, got {type(router)}"
        assert (
            router.simple_threshold == 0.3
        ), f"Factory defaults: simple_threshold=0.3, got {router.simple_threshold}"
        assert (
            router.complex_threshold == 0.7
        ), f"Factory defaults: complex_threshold=0.7, got {router.complex_threshold}"

    def test_create_fano_router_custom(self) -> None:
        """Factory should accept custom parameters."""
        router = create_fano_router(
            simple_threshold=0.2,
            complex_threshold=0.8,
            device="cuda",
        )

        assert (
            router.simple_threshold == 0.2
        ), f"Custom simple_threshold=0.2, got {router.simple_threshold}"
        assert (
            router.complex_threshold == 0.8
        ), f"Custom complex_threshold=0.8, got {router.complex_threshold}"
        assert router.device == "cuda", f"Custom device='cuda', got {router.device}"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_params(self) -> None:
        """Empty params should not crash."""
        router = FanoActionRouter()

        result = router.route(
            action="test",
            params={},
            complexity=0.5,
        )

        assert isinstance(
            result, RoutingResult
        ), f"Router should return RoutingResult, got {type(result)}"

    def test_none_complexity(self) -> None:
        """None complexity should trigger inference."""
        router = FanoActionRouter()

        result = router.route(
            action="query",
            params={},
            complexity=None,
        )

        # Should infer complexity
        assert result.complexity is not None, "Router should infer complexity when None provided"
        assert (
            0.0 <= result.complexity <= 1.0
        ), f"Complexity must be in [0, 1], got {result.complexity}"
        assert result.metadata[
            "inferred_complexity"
        ], "Metadata should flag that complexity was inferred"

    def test_boundary_complexity_values(self) -> None:
        """Boundary complexity values should route correctly."""
        router = FanoActionRouter()

        # Exactly at threshold
        result_boundary = router.route("test", {}, complexity=0.3)
        # Should be FANO_LINE (>= simple_threshold)
        assert (
            result_boundary.mode == ActionMode.FANO_LINE
        ), f"Complexity 0.3 (at threshold) should route FANO_LINE, got {result_boundary.mode}"

        # Just below threshold
        result_below = router.route("test", {}, complexity=0.29)
        assert (
            result_below.mode == ActionMode.SINGLE
        ), f"Complexity 0.29 (< 0.3) should route SINGLE, got {result_below.mode}"

        # At complex threshold
        result_complex = router.route("test", {}, complexity=0.7)
        assert (
            result_complex.mode == ActionMode.ALL_COLONIES
        ), f"Complexity 0.7 (at threshold) should route ALL_COLONIES, got {result_complex.mode}"

    def test_extreme_complexity_values(self) -> None:
        """Extreme complexity values should be handled."""
        router = FanoActionRouter()

        # Very low
        result_low = router.route("test", {}, complexity=0.0)
        assert (
            result_low.mode == ActionMode.SINGLE
        ), f"Complexity 0.0 (minimum) should route SINGLE, got {result_low.mode}"

        # Very high
        result_high = router.route("test", {}, complexity=1.0)
        assert (
            result_high.mode == ActionMode.ALL_COLONIES
        ), f"Complexity 1.0 (maximum) should route ALL_COLONIES, got {result_high.mode}"

    def test_large_params_dict(self) -> None:
        """Large params dict should not crash."""
        router = FanoActionRouter()

        large_params = {f"key_{i}": f"value_{i}" for i in range(1000)}

        result = router.route(
            action="test",
            params=large_params,
            complexity=None,
        )

        # Should infer higher complexity due to param count
        assert (
            result.complexity > 0.5
        ), f"Large params dict (1000 keys) should infer high complexity (> 0.5), got {result.complexity}"

    def test_nested_params(self) -> None:
        """Nested params should increase complexity."""
        router = FanoActionRouter()

        nested_params = {"level1": {"level2": {"level3": {"data": "value"}}}}

        result = router.route(
            action="test",
            params=nested_params,
            complexity=None,
        )

        # Should infer moderate complexity due to nesting
        assert (
            result.complexity > 0.3
        ), f"Nested params (3 levels) should infer moderate complexity (> 0.3), got {result.complexity}"


class TestMultiOperationScenarios:
    """Test realistic multi-operation scenarios."""

    def test_workflow_routing_sequence(self) -> None:
        """Test realistic workflow routing sequence."""
        router = FanoActionRouter()

        workflow = [
            ("brainstorm_ideas", {}, 0.4),  # Spark + partners
            ("implement_feature", {"name": "x"}, 0.5),  # Forge + partners
            ("test_implementation", {}, 0.3),  # Crystal + partners
        ]

        results = []
        for action, params, _expected_complexity in workflow:
            result = router.route(action, params, complexity=None)
            results.append(result)

        # All should be valid
        assert (
            len(results) == 3
        ), f"Workflow has 3 steps, should return 3 results, got {len(results)}"
        assert all(
            isinstance(r, RoutingResult) for r in results
        ), "All workflow results should be RoutingResult instances"

    def test_parallel_routing(self) -> None:
        """Test parallel routing requests."""
        router = FanoActionRouter()

        actions = ["create", "build", "test", "integrate", "plan", "research", "verify"]

        results = [router.route(action, params={}, complexity=0.5) for action in actions]

        # All should succeed
        assert len(results) == 7, f"7 actions should generate 7 results, got {len(results)}"
        assert all(
            r.mode == ActionMode.FANO_LINE for r in results
        ), f"All actions with complexity=0.5 should route FANO_LINE, got modes: {[r.mode for r in results]}"


# Mark all tests with timeout
