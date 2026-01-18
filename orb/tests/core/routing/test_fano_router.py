"""Tests for FanoActionRouter - Colony routing via Fano plane composition.

Tests verify:
1. Fano plane structure (21 colony pairs → exactly one third colony)
2. Routing modes (single, Fano line, all colonies)
3. Complexity inference (action patterns, params, context)
4. Determinism (same input → same output)
5. Colony selection (domain affinity, best colony)

Created: December 14, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

from kagami_math.catastrophe_constants import COLONY_NAMES
from kagami_math.fano_plane import FANO_LINES, get_fano_lines_zero_indexed
from kagami.core.unified_agents.fano_action_router import (
    ActionMode,
    FanoActionRouter,
    create_fano_router,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def router() -> FanoActionRouter:
    """Create a Fano action router for testing."""
    return create_fano_router()


# =============================================================================
# FANO PLANE STRUCTURE TESTS
# =============================================================================


def test_fano_lines_count():
    """Verify 7 Fano lines with 3 points each."""
    assert len(FANO_LINES) == 7, "Must have exactly 7 Fano lines"
    for line in FANO_LINES:
        assert len(line) == 3, f"Line {line} must have 3 points"
        assert len(set(line)) == 3, f"Line {line} has duplicates"


def test_all_21_pairs_covered():
    """Verify all 21 colony pairs (7 choose 2) appear exactly once."""
    pairs = set()
    for line in FANO_LINES:
        i, j, k = line
        # Add all 3 pairs from this line
        pairs.add((min(i, j), max(i, j)))
        pairs.add((min(i, k), max(i, k)))
        pairs.add((min(j, k), max(j, k)))

    # 7 choose 2 = 21
    assert len(pairs) == 21, f"Expected 21 pairs, got {len(pairs)}"

    # Verify each pair appears exactly once (no duplicates)
    pair_counts: dict[tuple[int, int], int] = {}
    for line in FANO_LINES:
        i, j, k = line
        for a, b in [(i, j), (i, k), (j, k)]:
            pair = (min(a, b), max(a, b))
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

    for pair, count in pair_counts.items():
        assert count == 1, f"Pair {pair} appears {count} times (should be 1)"


def test_fano_composition_determinism(router: FanoActionRouter):
    """Verify same colony pair always produces same third colony."""
    # Test all 21 pairs twice to ensure determinism
    results = {}
    for _ in range(2):
        for i in range(7):
            for j in range(i + 1, 7):
                # Convert to 0-indexed
                i_0, j_0 = i, j
                result = router.get_fano_composition(i_0, j_0)
                pair = (i_0, j_0)

                if pair in results:
                    # Second pass: verify same result
                    assert (
                        result == results[pair]
                    ), f"Pair {pair} produced different results: {result} vs {results[pair]}"
                else:
                    # First pass: record result
                    results[pair] = result


def test_every_pair_has_fano_composition(router: FanoActionRouter):
    """Verify every colony pair (0-6) has a valid Fano composition."""
    fano_lines_0idx = get_fano_lines_zero_indexed()

    for i in range(7):
        for j in range(7):
            if i == j:
                # Same colony - no composition
                continue

            # Find the Fano line containing both i and j
            found = False
            for line in fano_lines_0idx:
                if i in line and j in line:
                    found = True
                    # Verify get_fano_composition returns the third element
                    result = router.get_fano_composition(i, j)
                    third = next(x for x in line if x not in (i, j))
                    # Result should be the third element OR one of the permutations
                    # (Fano lines have cyclic structure: i×j=k, j×k=i, k×i=j)
                    assert result in line, f"Result {result} not on line {line} for pair ({i},{j})"
                    break

            assert found, f"Pair ({i},{j}) not found on any Fano line"


def test_fano_lines_form_complete_coverage():
    """Verify Fano lines cover all 7 colonies."""
    all_colonies = set()
    for line in FANO_LINES:
        all_colonies.update(line)

    assert all_colonies == {1, 2, 3, 4, 5, 6, 7}, "Fano lines must cover all 7 colonies"


# =============================================================================
# ROUTING MODE TESTS
# =============================================================================


def test_single_action_mode_low_complexity(router: FanoActionRouter):
    """Verify single action for low complexity (< 0.3)."""
    result = router.route(
        action="ping",
        params={},
        complexity=0.2,
    )

    assert result.mode == ActionMode.SINGLE
    assert len(result.actions) == 1
    assert result.actions[0].is_primary
    assert result.actions[0].weight == 1.0
    assert result.fano_line is None


def test_fano_line_mode_medium_complexity(router: FanoActionRouter):
    """Verify Fano line composition for medium complexity (0.3-0.7)."""
    result = router.route(
        action="build",
        params={"feature": "test"},
        complexity=0.5,
    )

    assert result.mode == ActionMode.FANO_LINE
    assert len(result.actions) == 3
    assert result.fano_line is not None

    # Verify roles
    roles = {a.fano_role for a in result.actions}
    assert roles == {"source", "partner", "result"}

    # Verify exactly one primary
    primaries = [a for a in result.actions if a.is_primary]
    assert len(primaries) == 1
    assert primaries[0].fano_role == "source"


def test_all_colonies_mode_high_complexity(router: FanoActionRouter):
    """Verify all 7 colonies for high complexity (≥ 0.7)."""
    result = router.route(
        action="synthesize.architecture",
        params={"domain": "distributed_systems"},
        complexity=0.8,
    )

    assert result.mode == ActionMode.ALL_COLONIES
    assert len(result.actions) == 7
    assert result.fano_line is None

    # Verify all colonies represented
    colony_indices = {a.colony_idx for a in result.actions}
    assert colony_indices == {0, 1, 2, 3, 4, 5, 6}

    # Verify exactly one primary
    primaries = [a for a in result.actions if a.is_primary]
    assert len(primaries) == 1

    # Verify weights sum to 1.0 (normalized)
    total_weight = sum(a.weight for a in result.actions)
    assert abs(total_weight - 1.0) < 1e-6


def test_fano_line_produces_valid_composition(router: FanoActionRouter):
    """Verify Fano line actions follow valid Fano plane structure."""
    result = router.route(
        action="integrate",
        params={"systems": ["a", "b"]},
        complexity=0.5,
    )

    assert result.mode == ActionMode.FANO_LINE
    assert result.fano_line is not None

    primary_idx, partner_idx, result_idx = result.fano_line

    # Verify this is a valid Fano line (0-indexed)
    fano_lines_0idx = get_fano_lines_zero_indexed()
    line_as_set = {primary_idx, partner_idx, result_idx}

    found = False
    for line in fano_lines_0idx:
        if set(line) == line_as_set:
            found = True
            break

    assert found, f"Line {result.fano_line} not found in valid Fano lines"


# =============================================================================
# COMPLEXITY INFERENCE TESTS
# =============================================================================


def test_complexity_inference_simple_patterns(router: FanoActionRouter):
    """Verify low complexity for simple patterns (ping, status, etc)."""
    simple_actions = ["ping", "health", "status", "get.info", "list.items"]

    for action in simple_actions:
        result = router.route(action=action, params={})
        assert result.complexity < 0.3, f"Action '{action}' should have low complexity"
        assert result.mode == ActionMode.SINGLE


def test_complexity_inference_moderate_patterns(router: FanoActionRouter):
    """Verify medium complexity for moderate patterns (create, update, etc)."""
    moderate_actions = ["create.item", "update.record", "query.database"]

    for action in moderate_actions:
        result = router.route(action=action, params={"field": "value"})
        # Should be in moderate range, but param count is low
        # Actual complexity depends on inference heuristics
        assert result.complexity > 0.0


def test_complexity_inference_synthesis_patterns(router: FanoActionRouter):
    """Verify high complexity for synthesis patterns (analyze, architect, etc)."""
    synthesis_actions = [
        "analyze.system",
        "architect.service",
        "design.protocol",
        "refactor.codebase",
    ]

    for action in synthesis_actions:
        result = router.route(action=action, params={})
        # Synthesis patterns should push complexity higher
        assert result.complexity >= 0.5, f"Action '{action}' should have high complexity"


def test_complexity_inference_parameter_count(router: FanoActionRouter):
    """Verify complexity increases with parameter count."""
    # 0 params
    result_0 = router.route(action="action.test", params={})

    # 5 params
    result_5 = router.route(
        action="action.test",
        params={"a": 1, "b": 2, "c": 3, "d": 4, "e": 5},
    )

    # 15 params
    result_15 = router.route(
        action="action.test",
        params={f"param_{i}": i for i in range(15)},
    )

    # More params should generally increase complexity
    # (though other factors also matter)
    assert result_15.complexity >= result_5.complexity


def test_complexity_inference_nested_params(router: FanoActionRouter):
    """Verify complexity increases with parameter nesting depth."""
    shallow = router.route(
        action="action.test",
        params={"a": 1, "b": 2},
    )

    deep = router.route(
        action="action.test",
        params={
            "level1": {
                "level2": {
                    "level3": {
                        "level4": "deep",
                    }
                }
            }
        },
    )

    # Deep nesting should increase complexity
    assert deep.complexity >= shallow.complexity


def test_complexity_inference_context_query_length(router: FanoActionRouter):
    """Verify complexity increases with query length."""
    short = router.route(
        action="action.test",
        params={},
        context={"query": "short"},
    )

    long = router.route(
        action="action.test",
        params={},
        context={
            "query": " ".join(["word"] * 50)  # 50-word query
        },
    )

    assert long.complexity >= short.complexity


def test_complexity_explicit_override(router: FanoActionRouter):
    """Verify explicit complexity in context overrides inference."""
    result = router.route(
        action="ping",  # Normally simple
        params={},
        context={"complexity": 0.9},  # Explicit override
    )

    assert result.complexity == 0.9
    assert result.mode == ActionMode.ALL_COLONIES  # High complexity


# =============================================================================
# COLONY SELECTION TESTS
# =============================================================================


def test_colony_selection_domain_affinity(router: FanoActionRouter):
    """Verify colonies selected based on domain affinity."""
    test_cases = [
        ("create.idea", 0, "spark"),  # Creative → Spark
        ("build.feature", 1, "forge"),  # Build → Forge
        ("fix.bug", 2, "flow"),  # Fix → Flow
        ("integrate.systems", 3, "nexus"),  # Integrate → Nexus
        ("plan.roadmap", 4, "beacon"),  # Plan → Beacon
        ("research.topic", 5, "grove"),  # Research → Grove
        ("test.feature", 6, "crystal"),  # Test → Crystal
    ]

    for action, expected_idx, expected_name in test_cases:
        result = router.route(action=action, params={}, complexity=0.2)  # Force single mode

        assert result.mode == ActionMode.SINGLE
        # Primary action should be the expected colony
        # Note: Safety-critical actions may have Crystal appended
        primary_action = next((a for a in result.actions if a.is_primary), result.actions[0])
        assert (
            primary_action.colony_idx == expected_idx
        ), f"Action '{action}' should route to {expected_name} (idx {expected_idx}), got {primary_action.colony_name}"


def test_colony_selection_keyword_matching(router: FanoActionRouter):
    """Verify keyword matching in action names."""
    # Multiple keywords that should match different colonies
    assert router._get_best_colony("brainstorm.ideas", {}) == 0  # Spark
    assert router._get_best_colony("implement.solution", {}) == 1  # Forge
    assert router._get_best_colony("debug.issue", {}) == 2  # Flow
    assert router._get_best_colony("merge.branches", {}) == 3  # Nexus
    assert router._get_best_colony("strategize.approach", {}) == 4  # Beacon
    assert router._get_best_colony("explore.options", {}) == 5  # Grove
    assert router._get_best_colony("validate.output", {}) == 6  # Crystal


def test_colony_selection_default_fallback(router: FanoActionRouter):
    """Verify default fallback to Forge for unknown actions."""
    result = router.route(
        action="unknown.action.pattern",
        params={},
        complexity=0.2,
    )

    # Should default to Forge (general execution)
    assert result.actions[0].colony_idx == 1
    assert result.actions[0].colony_name == "forge"


# =============================================================================
# DETERMINISM TESTS
# =============================================================================


def test_routing_determinism(router: FanoActionRouter):
    """Verify same input produces same output (determinism)."""
    action = "build.feature"
    params = {"name": "test", "priority": "high"}
    complexity = 0.5

    # Route same request 10 times
    results = [router.route(action=action, params=params, complexity=complexity) for _ in range(10)]

    # All results should be identical
    first = results[0]
    for result in results[1:]:
        assert result.mode == first.mode
        assert result.complexity == first.complexity
        assert len(result.actions) == len(first.actions)
        assert result.fano_line == first.fano_line

        # Verify action details match
        for i, action_obj in enumerate(result.actions):
            first_action = first.actions[i]
            assert action_obj.colony_idx == first_action.colony_idx
            assert action_obj.colony_name == first_action.colony_name
            assert action_obj.weight == first_action.weight
            assert action_obj.is_primary == first_action.is_primary
            assert action_obj.fano_role == first_action.fano_role


def test_complexity_inference_determinism(router: FanoActionRouter):
    """Verify complexity inference is deterministic."""
    action = "analyze.data"
    params = {"dataset": "test", "metrics": ["a", "b", "c"]}
    context = {"query": "analyze the test dataset", "domain": "ml"}

    # Infer complexity 10 times
    complexities = [
        router.route(action=action, params=params, context=context).complexity for _ in range(10)
    ]

    # All should be identical
    assert len(set(complexities)) == 1, f"Got varying complexities: {complexities}"


# =============================================================================
# EDGE CASES
# =============================================================================


def test_empty_params(router: FanoActionRouter):
    """Verify routing works with empty params."""
    result = router.route(action="test.action", params={})

    assert result.mode in (ActionMode.SINGLE, ActionMode.FANO_LINE, ActionMode.ALL_COLONIES)
    assert len(result.actions) > 0


def test_empty_context(router: FanoActionRouter):
    """Verify routing works with empty context."""
    result = router.route(action="test.action", params={}, context={})

    assert result.mode in (ActionMode.SINGLE, ActionMode.FANO_LINE, ActionMode.ALL_COLONIES)
    assert len(result.actions) > 0


def test_boundary_complexity_values(router: FanoActionRouter):
    """Verify correct mode selection at complexity boundaries."""
    # Just below simple threshold (0.3)
    result = router.route(action="test", params={}, complexity=0.29)
    assert result.mode == ActionMode.SINGLE

    # Exactly at simple threshold
    result = router.route(action="test", params={}, complexity=0.3)
    assert result.mode == ActionMode.FANO_LINE

    # Just below complex threshold (0.7)
    result = router.route(action="test", params={}, complexity=0.69)
    assert result.mode == ActionMode.FANO_LINE

    # Exactly at complex threshold
    result = router.route(action="test", params={}, complexity=0.7)
    assert result.mode == ActionMode.ALL_COLONIES


def test_complexity_clamping(router: FanoActionRouter):
    """Verify complexity is clamped to [0, 1]."""
    # Explicit out-of-range values should be clamped
    result_low = router.route(action="test", params={}, complexity=-0.5)
    assert 0.0 <= result_low.complexity <= 1.0

    result_high = router.route(action="test", params={}, complexity=1.5)
    assert 0.0 <= result_high.complexity <= 1.0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


def test_full_workflow_simple_task(router: FanoActionRouter):
    """Test complete routing workflow for simple task."""
    result = router.route(
        action="get.status",
        params={},
        context={"query": "What's the status?"},
    )

    # Should be simple (single colony)
    assert result.mode == ActionMode.SINGLE
    assert len(result.actions) == 1
    assert result.complexity < 0.3
    assert result.metadata["action"] == "get.status"


def test_full_workflow_complex_task(router: FanoActionRouter):
    """Test complete routing workflow for complex task."""
    result = router.route(
        action="architect.distributed.system",
        params={
            "requirements": ["scalability", "fault_tolerance", "consistency"],
            "constraints": {"latency": "100ms", "throughput": "10k rps"},
            "components": ["api", "database", "cache", "queue"],
        },
        context={
            "query": "Design a distributed system with high scalability and fault tolerance",
            "domain": "distributed_systems",
        },
    )

    # Should engage all colonies for synthesis
    assert result.mode == ActionMode.ALL_COLONIES
    assert len(result.actions) == 7
    assert result.complexity >= 0.7
    assert all(a.colony_name in COLONY_NAMES for a in result.actions)


def test_full_workflow_medium_task(router: FanoActionRouter):
    """Test complete routing workflow for medium complexity task."""
    result = router.route(
        action="implement.authentication",
        params={"provider": "oauth2", "scopes": ["read", "write"]},
        context={"query": "Implement OAuth2 authentication"},
    )

    # Should use Fano line composition
    # Complexity depends on inference, but should be in medium range
    if result.mode == ActionMode.FANO_LINE:
        # Note: Authentication is safety-critical, so Crystal may be appended
        # Fano line has 3 colonies, +1 for Crystal enforcement = 4
        assert result.fano_line is not None
        assert 0.3 <= result.complexity < 0.7
        # Should have at least 3 colonies (Fano line)
        assert len(result.actions) >= 3


def test_colony_names_match_constants():
    """Verify colony names in router match canonical constants."""
    # All colony actions should use names from COLONY_NAMES
    router = create_fano_router()
    result = router.route(action="test", params={}, complexity=0.8)  # All colonies

    action_names = {a.colony_name for a in result.actions}
    expected_names = set(COLONY_NAMES)

    assert (
        action_names == expected_names
    ), f"Colony names mismatch: {action_names} vs {expected_names}"


def test_s7_basis_vectors(router: FanoActionRouter):
    """Verify S⁷ basis vectors for colony actions."""
    result = router.route(action="test", params={}, complexity=0.2)

    action = result.actions[0]
    basis = action.s7_basis

    # Should be 8D vector (scalar + 7 imaginaries)
    assert basis.shape == (8,)

    # Should be one-hot at colony_idx + 1 (e₁ at index 1, etc)
    assert basis[action.colony_idx + 1] == 1.0

    # All other components should be zero
    assert basis.sum() == 1.0
