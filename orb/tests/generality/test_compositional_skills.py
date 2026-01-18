"""Comprehensive tests for compositional skill learning."""

from __future__ import annotations

import pytest
from typing import Any

from kagami.core.learning.compositional_learning import (
    CompositeSkill,
    PrimitiveSkill,
    SkillComposer,
    get_skill_composer,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def fresh_composer() -> SkillComposer:
    """Create a fresh SkillComposer for isolated testing."""
    return SkillComposer()


# ============================================================================
# Basic Functionality Tests (Original)
# ============================================================================


def test_learn_primitive(
    fresh_composer: SkillComposer,
    sample_action_success: dict[str, Any],
    sample_outcome_success: dict[str, Any],
) -> None:
    """Test learning primitive skill from experience."""
    primitive = fresh_composer.learn_primitive(
        action=sample_action_success,
        outcome=sample_outcome_success,
    )

    assert primitive is not None
    assert primitive.usage_count >= 1
    assert 0.0 <= primitive.success_rate <= 1.0


def test_decompose_into_primitives(fresh_composer: SkillComposer) -> None:
    """Test decomposing complex task."""
    primitives = fresh_composer.decompose_into_primitives(
        {"type": "refactor", "action": "refactor authentication"}
    )

    assert primitives is not None
    assert len(primitives) > 0
    assert "observe" in primitives  # Should include universal primitives


def test_compose_novel_solution(fresh_composer: SkillComposer) -> None:
    """Test composing primitives into novel solution."""
    # Compose from known primitives
    solution = fresh_composer.compose_novel_solution(
        primitives=["observe", "decompose", "test", "iterate"],
        goal={"goal": "debug_issue", "type": "debug"},
    )

    assert solution is not None
    assert "composite" in solution
    assert "expected_success" in solution
    assert 0.0 <= solution["expected_success"] <= 1.0


def test_get_best_primitives(fresh_composer: SkillComposer) -> None:
    """Test retrieving high-success primitives."""
    # Learn some primitives
    for i in range(3):
        fresh_composer.learn_primitive(
            action={"action": f"action_{i}", "type": "test"},
            outcome={"status": "success" if i % 2 == 0 else "error"},
        )

    best = fresh_composer.get_best_primitives(min_success_rate=0.5)
    assert isinstance(best, list)


def test_recommend_composition(fresh_composer: SkillComposer) -> None:
    """Test composition recommendation for goal."""
    recommendation = fresh_composer.recommend_composition(
        {"type": "implement", "goal": "implement feature"}
    )

    assert recommendation is not None
    assert len(recommendation) > 0


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_learn_primitive_empty_action(fresh_composer: SkillComposer) -> None:
    """Test learning from empty action."""
    primitive = fresh_composer.learn_primitive(action={}, outcome={"status": "success"})

    assert primitive is not None
    assert primitive.usage_count == 1


def test_learn_primitive_invalid_outcome(fresh_composer: SkillComposer) -> None:
    """Test learning with missing outcome status."""
    primitive = fresh_composer.learn_primitive(
        action={"action": "test_action", "type": "test"}, outcome={}
    )

    assert primitive is not None
    # Success rate should be 0.0 when no success status
    assert primitive.success_rate == 0.0


def test_learn_primitive_non_atomic_action(fresh_composer: SkillComposer) -> None:
    """Test that composite actions are not learned as primitives."""
    result = fresh_composer.learn_primitive(
        action={"action": "write test and implement feature", "type": "composite"},
        outcome={"status": "success"},
    )

    # Should return None for non-atomic actions
    assert result is None


def test_learn_primitive_with_steps_keyword(fresh_composer: SkillComposer) -> None:
    """Test that actions with 'steps' keyword are not atomic."""
    result = fresh_composer.learn_primitive(
        action={"action": "complex task", "steps": ["step1", "step2"]},
        outcome={"status": "success"},
    )

    assert result is None


def test_learn_primitive_updates_existing(fresh_composer: SkillComposer) -> None:
    """Test that learning same primitive twice updates it."""
    action = {"action": "test_action", "type": "test"}

    # Learn first time with success
    prim1 = fresh_composer.learn_primitive(action, {"status": "success"})
    assert prim1 is not None
    initial_count = prim1.usage_count

    # Learn second time with failure
    prim2 = fresh_composer.learn_primitive(action, {"status": "error"})
    assert prim2 is not None
    assert prim2.usage_count == initial_count + 1
    assert prim2.success_rate < 1.0  # Should decrease


def test_decompose_empty_task(fresh_composer: SkillComposer) -> None:
    """Test decomposing empty task returns default sequence."""
    primitives = fresh_composer.decompose_into_primitives({})

    assert primitives is not None
    assert len(primitives) > 0
    # Should return default sequence
    assert "observe" in primitives


def test_decompose_debug_task(fresh_composer: SkillComposer) -> None:
    """Test decomposing debug task."""
    primitives = fresh_composer.decompose_into_primitives(
        {"type": "debug", "action": "debug login issue"}
    )

    assert primitives is not None
    assert "observe" in primitives
    assert "test" in primitives


def test_decompose_implement_task(fresh_composer: SkillComposer) -> None:
    """Test decomposing implementation task."""
    primitives = fresh_composer.decompose_into_primitives(
        {"type": "implement", "action": "implement new API"}
    )

    assert primitives is not None
    assert "decompose" in primitives
    assert "test" in primitives


def test_decompose_learn_task(fresh_composer: SkillComposer) -> None:
    """Test decomposing learning task."""
    primitives = fresh_composer.decompose_into_primitives(
        {"type": "learn", "action": "learn new framework"}
    )

    assert primitives is not None
    assert "observe" in primitives
    assert "practice" in primitives
    assert "iterate" in primitives


def test_compose_with_missing_primitives(fresh_composer: SkillComposer) -> None:
    """Test composing with non-existent primitives."""
    solution = fresh_composer.compose_novel_solution(
        primitives=["nonexistent_skill_1", "nonexistent_skill_2"],
        goal={"goal": "impossible_task", "type": "test"},
    )

    # Should return None when primitives don't exist
    assert solution is None


def test_compose_with_partial_missing_primitives(fresh_composer: SkillComposer) -> None:
    """Test composing with some missing primitives."""
    solution = fresh_composer.compose_novel_solution(
        primitives=["observe", "nonexistent_skill"],
        goal={"goal": "partial_task", "type": "test"},
    )

    assert solution is None


def test_compose_empty_primitives(fresh_composer: SkillComposer) -> None:
    """Test composing with empty primitive list."""
    solution = fresh_composer.compose_novel_solution(
        primitives=[], goal={"goal": "empty_task", "type": "test"}
    )

    # Empty list should be valid (all primitives exist in empty set)
    assert solution is not None
    assert solution["expected_success"] == 1.0  # Product of empty set


def test_get_best_primitives_by_domain(fresh_composer: SkillComposer) -> None:
    """Test filtering primitives by domain."""
    best = fresh_composer.get_best_primitives(domain="universal", min_success_rate=0.7)

    assert isinstance(best, list)
    assert len(best) > 0
    # All returned should be universal or match domain
    assert all(p.domain in ["universal"] for p in best)


def test_get_best_primitives_high_threshold(fresh_composer: SkillComposer) -> None:
    """Test filtering with very high success rate threshold."""
    best = fresh_composer.get_best_primitives(min_success_rate=0.99)

    # Should return only primitives with >0.99 success rate
    assert all(p.success_rate >= 0.99 for p in best)


def test_get_best_primitives_no_matches(fresh_composer: SkillComposer) -> None:
    """Test when no primitives meet threshold."""
    best = fresh_composer.get_best_primitives(domain="nonexistent_domain", min_success_rate=0.99)

    assert isinstance(best, list)
    assert len(best) == 0


def test_recommend_composition_with_proven_composite(fresh_composer: SkillComposer) -> None:
    """Test recommendation reuses proven composites."""
    # Create a proven composite
    goal_type = "test_goal"
    primitives = ["observe", "test", "iterate"]

    # First compose to create the composite
    fresh_composer.compose_novel_solution(
        primitives=primitives, goal={"goal": goal_type, "type": goal_type}
    )

    # Manually set high success rate for the composite
    composite_name = "_".join(primitives[:3])
    if composite_name in fresh_composer._composites:
        fresh_composer._composites[composite_name].success_rate = 0.85

    # Should reuse the proven composite
    recommendation = fresh_composer.recommend_composition({"type": goal_type, "goal": "same goal"})

    assert recommendation is not None
    assert recommendation == primitives


def test_recommend_composition_unknown_goal(fresh_composer: SkillComposer) -> None:
    """Test recommendation for unknown goal type falls back to decomposition."""
    recommendation = fresh_composer.recommend_composition(
        {"type": "unknown_goal_type", "goal": "mysterious task"}
    )

    assert recommendation is not None
    assert len(recommendation) > 0
    # Should get default decomposition
    assert "observe" in recommendation


# ============================================================================
# Private Method Tests
# ============================================================================


def test_compute_signature_consistency(fresh_composer: SkillComposer) -> None:
    """Test that same actions produce same signatures."""
    action1 = {"action": "test_action", "type": "test"}
    action2 = {"action": "test_action", "type": "test"}

    sig1 = fresh_composer._compute_signature(action1)
    sig2 = fresh_composer._compute_signature(action2)

    assert sig1 == sig2
    assert len(sig1) == 16  # MD5 hex digest truncated to 16 chars


def test_compute_signature_different_actions(fresh_composer: SkillComposer) -> None:
    """Test that different actions produce different signatures."""
    action1 = {"action": "action1", "type": "test"}
    action2 = {"action": "action2", "type": "test"}

    sig1 = fresh_composer._compute_signature(action1)
    sig2 = fresh_composer._compute_signature(action2)

    assert sig1 != sig2


def test_is_atomic_simple_action(fresh_composer: SkillComposer) -> None:
    """Test atomic detection for simple actions."""
    action = {"action": "write test", "type": "test"}

    assert fresh_composer._is_atomic(action) is True


def test_is_atomic_compound_with_and(fresh_composer: SkillComposer) -> None:
    """Test non-atomic detection for 'and' compound."""
    action = {"action": "write test and implement", "type": "composite"}

    assert fresh_composer._is_atomic(action) is False


def test_is_atomic_compound_with_then(fresh_composer: SkillComposer) -> None:
    """Test non-atomic detection for 'then' compound."""
    action = {"action": "test first then deploy", "type": "composite"}

    assert fresh_composer._is_atomic(action) is False


def test_is_atomic_with_steps(fresh_composer: SkillComposer) -> None:
    """Test non-atomic detection for actions with steps."""
    action = {"action": "complex task", "steps": ["a", "b", "c"]}

    assert fresh_composer._is_atomic(action) is False


def test_infer_preconditions_with_context(fresh_composer: SkillComposer) -> None:
    """Test precondition inference from context."""
    action = {
        "action": "test",
        "context": {"has_tests": True, "has_code": True},
    }

    preconditions = fresh_composer._infer_preconditions(action)

    assert "tests_exist" in preconditions
    assert "code_exists" in preconditions


def test_infer_preconditions_empty_context(fresh_composer: SkillComposer) -> None:
    """Test precondition inference with no context."""
    action = {"action": "test"}

    preconditions = fresh_composer._infer_preconditions(action)

    assert isinstance(preconditions, list)
    assert len(preconditions) == 0


def test_infer_postconditions_success(fresh_composer: SkillComposer) -> None:
    """Test postcondition inference from successful outcome."""
    outcome = {"status": "success", "tests_pass": True}

    postconditions = fresh_composer._infer_postconditions(outcome)

    assert "action_succeeded" in postconditions
    assert "tests_passing" in postconditions


def test_infer_postconditions_failure(fresh_composer: SkillComposer) -> None:
    """Test postcondition inference from failed outcome."""
    outcome = {"status": "error"}

    postconditions = fresh_composer._infer_postconditions(outcome)

    # Should not include success postconditions
    assert "action_succeeded" not in postconditions


def test_validate_composition_all_exist(fresh_composer: SkillComposer) -> None:
    """Test composition validation with all primitives existing."""
    primitives = ["observe", "test", "iterate"]

    is_valid = fresh_composer._validate_composition(primitives)

    assert is_valid is True


def test_validate_composition_some_missing(fresh_composer: SkillComposer) -> None:
    """Test composition validation with missing primitives."""
    primitives = ["observe", "nonexistent_primitive"]

    is_valid = fresh_composer._validate_composition(primitives)

    assert is_valid is False


def test_validate_composition_empty(fresh_composer: SkillComposer) -> None:
    """Test composition validation with empty list."""
    primitives: list[str] = []

    is_valid = fresh_composer._validate_composition(primitives)

    assert is_valid is True  # Empty composition is valid


# ============================================================================
# Parametrized Tests
# ============================================================================


@pytest.mark.parametrize(
    "task_type,expected_primitive",
    [
        ("refactor", "observe"),
        ("debug", "test"),
        ("implement", "decompose"),
        ("learn", "practice"),
    ],
)
def test_decompose_task_types(
    fresh_composer: SkillComposer, task_type: str, expected_primitive: str
) -> None:
    """Test decomposition for various task types."""
    primitives = fresh_composer.decompose_into_primitives(
        {"type": task_type, "action": f"{task_type} something"}
    )

    assert primitives is not None
    assert expected_primitive in primitives


@pytest.mark.parametrize(
    "action_text,expected_atomic",
    [
        ("simple_action", True),
        ("action and another", False),
        ("do this then that", False),
        ("single_verb", True),
    ],
)
def test_is_atomic_variations(
    fresh_composer: SkillComposer, action_text: str, expected_atomic: bool
) -> None:
    """Test atomicity detection for various action formats."""
    action = {"action": action_text, "type": "test"}

    assert fresh_composer._is_atomic(action) == expected_atomic


@pytest.mark.parametrize("success_count,total_count", [(10, 10), (7, 10), (0, 10), (5, 5)])
def test_success_rate_calculation(
    fresh_composer: SkillComposer, success_count: int, total_count: int
) -> None:
    """Test success rate calculation with various counts."""
    action = {"action": "test_skill", "type": "test"}

    # Learn primitive multiple times
    for i in range(total_count):
        outcome = {"status": "success" if i < success_count else "error"}
        fresh_composer.learn_primitive(action, outcome)

    # Get the learned primitive
    sig = fresh_composer._compute_signature(action)
    primitive = fresh_composer._primitives.get(sig)

    assert primitive is not None
    assert primitive.usage_count == total_count
    # Success rate should be approximately success_count / total_count
    # Using Bayesian update, so it's not exact
    expected_rate = success_count / total_count
    assert abs(primitive.success_rate - expected_rate) < 0.3


@pytest.mark.parametrize(
    "primitives,expected_in_range",
    [
        (["observe", "test"], (0.85, 0.95)),  # Both high success
        (["observe", "test", "iterate", "compose"], (0.5, 0.8)),  # Multiple primitives
    ],
)
def test_compose_success_rate_calculation(
    fresh_composer: SkillComposer, primitives: list[str], expected_in_range: tuple[float, float]
) -> None:
    """Test expected success rate calculation for compositions."""
    solution = fresh_composer.compose_novel_solution(
        primitives=primitives, goal={"goal": "test_goal", "type": "test"}
    )

    assert solution is not None
    min_rate, max_rate = expected_in_range
    assert min_rate <= solution["expected_success"] <= max_rate


@pytest.mark.parametrize("domain", ["universal", "testing", "coding", None])
def test_get_best_primitives_domain_filter(
    fresh_composer: SkillComposer, domain: str | None
) -> None:
    """Test domain filtering for best primitives."""
    best = fresh_composer.get_best_primitives(domain=domain, min_success_rate=0.0)

    assert isinstance(best, list)
    if domain:
        # Check all returned primitives match domain or are universal
        for prim in best:
            assert prim.domain in [domain, "universal"]


# ============================================================================
# Integration Tests
# ============================================================================


def test_full_learning_cycle(fresh_composer: SkillComposer) -> None:
    """Test complete learning cycle: learn, decompose, compose, recommend."""
    # Step 1: Learn primitives from experiences
    experiences = [
        ({"action": "write_test", "type": "test"}, {"status": "success"}),
        ({"action": "implement_feature", "type": "implement"}, {"status": "success"}),
        ({"action": "verify_behavior", "type": "test"}, {"status": "success"}),
    ]

    for action, outcome in experiences:
        fresh_composer.learn_primitive(action, outcome)

    # Step 2: Decompose a complex task
    primitives = fresh_composer.decompose_into_primitives(
        {"type": "implement", "action": "implement authentication"}
    )
    assert primitives is not None

    # Step 3: Compose novel solution using learned primitives
    solution = fresh_composer.compose_novel_solution(
        primitives=["observe", "test", "iterate"], goal={"goal": "quality_gate", "type": "test"}
    )
    assert solution is not None

    # Step 4: Get recommendation
    recommendation = fresh_composer.recommend_composition(
        {"type": "implement", "goal": "new feature"}
    )
    assert recommendation is not None


def test_primitive_evolution_with_feedback(fresh_composer: SkillComposer) -> None:
    """Test that primitives evolve based on feedback."""
    action = {"action": "evolving_skill", "type": "test"}

    # Learn with initial success
    prim1 = fresh_composer.learn_primitive(action, {"status": "success"})
    assert prim1 is not None
    initial_rate = prim1.success_rate

    # Add failures to see success rate decrease
    for _ in range(5):
        fresh_composer.learn_primitive(action, {"status": "error"})

    sig = fresh_composer._compute_signature(action)
    evolved_prim = fresh_composer._primitives[sig]

    # Success rate should have decreased
    assert evolved_prim.success_rate < initial_rate
    assert evolved_prim.usage_count == 6


def test_bootstrap_primitives_exist(fresh_composer: SkillComposer) -> None:
    """Test that bootstrap primitives are initialized."""
    expected_primitives = ["observe", "decompose", "test", "iterate", "compose"]

    for prim_name in expected_primitives:
        assert prim_name in fresh_composer._primitives
        prim = fresh_composer._primitives[prim_name]
        assert prim.domain == "universal"
        assert prim.success_rate > 0


def test_singleton_behavior() -> None:
    """Test that get_skill_composer returns singleton."""
    composer1 = get_skill_composer()
    composer2 = get_skill_composer()

    assert composer1 is composer2


def test_dataclass_primitive_skill() -> None:
    """Test PrimitiveSkill dataclass initialization."""
    skill = PrimitiveSkill(
        name="test",
        description="Test skill",
        preconditions=["a"],
        postconditions=["b"],
        success_rate=0.8,
        usage_count=5,
        domain="test_domain",
    )

    assert skill.name == "test"
    assert skill.examples == []  # Default empty list


def test_dataclass_composite_skill() -> None:
    """Test CompositeSkill dataclass initialization."""
    skill = CompositeSkill(
        name="test_composite",
        primitives=["a", "b"],
        goal="test_goal",
        success_rate=0.7,
        uses=3,
        discovered_at="2025-01-01",
    )

    assert skill.name == "test_composite"
    assert len(skill.primitives) == 2
