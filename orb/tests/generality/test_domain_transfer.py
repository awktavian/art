"""Comprehensive tests for cross-domain transfer learning."""

from __future__ import annotations

import pytest
from typing import Any

from kagami.core.learning.domain_transfer import (
    AbstractPattern,
    DomainTransferBridge,
    get_domain_transfer_bridge,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def fresh_bridge() -> DomainTransferBridge:
    """Create a fresh DomainTransferBridge for isolated testing."""
    return DomainTransferBridge()


# ============================================================================
# Basic Functionality Tests (Original)
# ============================================================================


def test_extract_abstract_pattern(fresh_bridge: DomainTransferBridge) -> None:
    """Test pattern extraction from concrete experience."""
    # Simulate successful coding experience
    experience = {
        "domain": "coding",
        "action": "write test first, implement, verify, iterate",
        "outcome": {"status": "success"},
        "valence": 0.9,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)

    assert pattern is not None
    assert pattern.abstract_strategy == "incremental_validation_tight_feedback"
    assert "coding" in pattern.applicable_domains
    # Pattern is seeded with history, so confidence = (success_count + 1) / (total_transfers + 1)
    # Seeded with: success_count=8, total_transfers=10, so after update: 9/11 ≈ 0.818
    assert 0.7 <= pattern.transfer_confidence <= 0.9  # Reasonable confidence range


def test_transfer_to_new_domain(fresh_bridge: DomainTransferBridge) -> None:
    """Test applying pattern to novel domain."""
    # Extract pattern
    experience = {
        "domain": "coding",
        "action": "incremental testing",
        "outcome": {"status": "success"},
        "valence": 0.85,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)
    assert pattern is not None

    # Transfer to writing domain
    instantiation = fresh_bridge.apply_to_new_domain(
        pattern=pattern, target_domain="writing", context={"task": "write essay"}
    )

    assert instantiation is not None
    assert instantiation["target_domain"] == "writing"
    assert "write outline" in instantiation["action"].lower()


def test_transfer_confidence_updates(fresh_bridge: DomainTransferBridge) -> None:
    """Test confidence updates based on transfer success."""
    # Extract pattern
    pattern = fresh_bridge.extract_abstract_pattern(
        {
            "domain": "coding",
            "action": "test-driven development",
            "outcome": {"status": "success"},
            "valence": 0.9,
        }
    )

    assert pattern is not None
    initial_confidence = pattern.transfer_confidence

    # Record successful transfer
    fresh_bridge.record_transfer_outcome(
        pattern_name=pattern.name, success=True, target_domain="writing"
    )

    # Confidence should increase
    updated_pattern = fresh_bridge._patterns[next(iter(fresh_bridge._patterns.keys()))]
    assert updated_pattern.transfer_confidence >= initial_confidence


def test_get_transferable_patterns(fresh_bridge: DomainTransferBridge) -> None:
    """Test retrieving patterns for target domain."""
    # Create some patterns
    for i in range(3):
        fresh_bridge.extract_abstract_pattern(
            {
                "domain": "coding",
                "action": f"action_{i}",
                "outcome": {"status": "success"},
                "valence": 0.8,
            }
        )

    patterns = fresh_bridge.get_transferable_patterns("coding")
    assert len(patterns) > 0
    # Should be sorted by confidence
    assert all(
        patterns[i].transfer_confidence >= patterns[i + 1].transfer_confidence
        for i in range(len(patterns) - 1)
    )


# ============================================================================
# All 5 Strategy Type Tests
# ============================================================================


def test_extract_incremental_validation_pattern(fresh_bridge: DomainTransferBridge) -> None:
    """Test extraction of incremental validation pattern."""
    experience = {
        "domain": "coding",
        "action": "write small test, verify incrementally",
        "outcome": {"status": "success"},
        "valence": 0.9,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)

    assert pattern is not None
    assert pattern.abstract_strategy == "incremental_validation_tight_feedback"
    assert "coding" in pattern.applicable_domains
    assert "writing" in pattern.applicable_domains
    assert "learning" in pattern.applicable_domains


def test_extract_hierarchical_decomposition_pattern(fresh_bridge: DomainTransferBridge) -> None:
    """Test extraction of hierarchical decomposition pattern."""
    experience = {
        "domain": "project_planning",
        "action": "break down complex project into modular components",
        "outcome": {"status": "success"},
        "valence": 0.85,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)

    assert pattern is not None
    assert pattern.abstract_strategy == "hierarchical_decomposition"
    assert "coding" in pattern.applicable_domains
    assert "project_planning" in pattern.applicable_domains
    assert "problem_solving" in pattern.applicable_domains


def test_extract_adaptive_error_recovery_pattern(fresh_bridge: DomainTransferBridge) -> None:
    """Test extraction of adaptive error recovery pattern."""
    experience = {
        "domain": "debugging",
        "action": "fix the broken authentication, recover gracefully",
        "outcome": {"status": "success"},
        "valence": 0.8,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)

    assert pattern is not None
    assert pattern.abstract_strategy == "adaptive_error_recovery"
    assert "debugging" in pattern.applicable_domains
    assert "operations" in pattern.applicable_domains


def test_extract_exploration_before_exploitation_pattern(
    fresh_bridge: DomainTransferBridge,
) -> None:
    """Test extraction of exploration before exploitation pattern."""
    experience = {
        "domain": "research",
        "action": "explore various approaches before committing",
        "outcome": {"status": "success"},
        "valence": 0.75,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)

    assert pattern is not None
    assert pattern.abstract_strategy == "exploration_before_exploitation"
    assert "research" in pattern.applicable_domains
    assert "decision_making" in pattern.applicable_domains
    assert "strategy" in pattern.applicable_domains


def test_extract_constraint_satisfaction_pattern(fresh_bridge: DomainTransferBridge) -> None:
    """Test extraction of constraint satisfaction pattern."""
    experience = {
        "domain": "planning",
        "action": "identify all requirements and constraints before proceeding",
        "outcome": {"status": "success"},
        "valence": 0.8,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)

    assert pattern is not None
    assert pattern.abstract_strategy == "constraint_satisfaction_propagation"
    assert "planning" in pattern.applicable_domains
    assert "design" in pattern.applicable_domains


# ============================================================================
# Strategy Instantiation Tests
# ============================================================================


def test_instantiate_incremental_validation_coding(fresh_bridge: DomainTransferBridge) -> None:
    """Test incremental validation instantiation in coding domain."""
    strategy = "incremental_validation_tight_feedback"
    action = fresh_bridge._instantiate_in_domain(strategy, "coding", {"task": "implement feature"})

    assert "test" in action.lower()
    assert "verify" in action.lower() or "iterate" in action.lower()


def test_instantiate_incremental_validation_writing(fresh_bridge: DomainTransferBridge) -> None:
    """Test incremental validation instantiation in writing domain."""
    strategy = "incremental_validation_tight_feedback"
    action = fresh_bridge._instantiate_in_domain(strategy, "writing", {"task": "write article"})

    assert "outline" in action.lower()
    assert "draft" in action.lower() or "review" in action.lower()


def test_instantiate_incremental_validation_learning(fresh_bridge: DomainTransferBridge) -> None:
    """Test incremental validation instantiation in learning domain."""
    strategy = "incremental_validation_tight_feedback"
    action = fresh_bridge._instantiate_in_domain(strategy, "learning", {"task": "learn Python"})

    assert "study" in action.lower() or "test" in action.lower()
    assert "understanding" in action.lower() or "review" in action.lower()


def test_instantiate_hierarchical_decomposition_coding(fresh_bridge: DomainTransferBridge) -> None:
    """Test hierarchical decomposition instantiation in coding."""
    strategy = "hierarchical_decomposition"
    action = fresh_bridge._instantiate_in_domain(
        strategy, "coding", {"task": "build authentication system"}
    )

    assert "build authentication system" in action
    assert "modules" in action.lower()


def test_instantiate_hierarchical_decomposition_project_planning(
    fresh_bridge: DomainTransferBridge,
) -> None:
    """Test hierarchical decomposition instantiation in project planning."""
    strategy = "hierarchical_decomposition"
    action = fresh_bridge._instantiate_in_domain(
        strategy, "project_planning", {"task": "launch product"}
    )

    assert "launch product" in action
    assert "decompose" in action.lower()
    assert "milestones" in action.lower() or "tasks" in action.lower()


def test_instantiate_adaptive_error_recovery_debugging(fresh_bridge: DomainTransferBridge) -> None:
    """Test adaptive error recovery instantiation in debugging."""
    strategy = "adaptive_error_recovery"
    action = fresh_bridge._instantiate_in_domain(strategy, "debugging", {"task": "fix crash"})

    assert "isolate" in action.lower()
    assert "fix" in action.lower()
    assert "verify" in action.lower()


def test_instantiate_adaptive_error_recovery_social(fresh_bridge: DomainTransferBridge) -> None:
    """Test adaptive error recovery instantiation in social domain."""
    strategy = "adaptive_error_recovery"
    action = fresh_bridge._instantiate_in_domain(
        strategy, "social_repair", {"task": "repair relationship"}
    )

    assert "acknowledge" in action.lower()
    assert "amends" in action.lower() or "trust" in action.lower()


def test_instantiate_unknown_strategy(fresh_bridge: DomainTransferBridge) -> None:
    """Test instantiation of unknown strategy returns default."""
    strategy = "unknown_strategy"
    action = fresh_bridge._instantiate_in_domain(strategy, "coding", {"task": "do something"})

    assert strategy in action
    assert "do something" in action


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_extract_pattern_low_valence(fresh_bridge: DomainTransferBridge) -> None:
    """Test that low valence experiences don't create patterns."""
    experience = {
        "domain": "coding",
        "action": "rush implementation without tests",
        "outcome": {"status": "error"},
        "valence": 0.2,  # Low valence
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)

    # Should not extract pattern from low valence experience
    assert pattern is None


def test_extract_pattern_borderline_valence(fresh_bridge: DomainTransferBridge) -> None:
    """Test extraction with borderline valence (exactly 0.5)."""
    experience = {
        "domain": "coding",
        "action": "test incrementally",
        "outcome": {"status": "success"},
        "valence": 0.5,  # Exactly at threshold
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)

    # Should extract pattern at threshold
    assert pattern is not None


def test_extract_pattern_no_matching_strategy(fresh_bridge: DomainTransferBridge) -> None:
    """Test extraction when action doesn't match any strategy."""
    experience = {
        "domain": "unknown",
        "action": "completely novel action with no keywords",
        "outcome": {"status": "success"},
        "valence": 0.9,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)

    # Should return None when no strategy matches
    assert pattern is None


def test_extract_pattern_updates_existing(fresh_bridge: DomainTransferBridge) -> None:
    """Test that extracting same pattern twice updates it."""
    experience1 = {
        "domain": "coding",
        "action": "test first approach",
        "outcome": {"status": "success"},
        "valence": 0.9,
    }

    pattern1 = fresh_bridge.extract_abstract_pattern(experience1)
    assert pattern1 is not None
    initial_transfers = pattern1.total_transfers

    # Extract again with same strategy
    experience2 = {
        "domain": "writing",
        "action": "validate incrementally",
        "outcome": {"status": "success"},
        "valence": 0.85,
    }

    pattern2 = fresh_bridge.extract_abstract_pattern(experience2)
    assert pattern2 is not None

    # Should update the same pattern
    assert pattern2.total_transfers == initial_transfers + 1
    assert len(pattern2.concrete_instances) == initial_transfers + 1


def test_apply_to_inapplicable_domain(fresh_bridge: DomainTransferBridge) -> None:
    """Test applying pattern to domain where it's not applicable."""
    # Create a pattern applicable only to specific domains
    pattern = AbstractPattern(
        name="test_pattern",
        abstract_strategy="incremental_validation_tight_feedback",
        concrete_instances=[],
        applicable_domains=["coding", "writing"],  # Not applicable to 'gaming'
        transfer_confidence=0.8,
        success_count=8,
        total_transfers=10,
    )

    result = fresh_bridge.apply_to_new_domain(
        pattern=pattern, target_domain="gaming", context={"task": "design level"}
    )

    # Should return None for inapplicable domain
    assert result is None


def test_apply_low_confidence_pattern(fresh_bridge: DomainTransferBridge) -> None:
    """Test applying pattern with low confidence (should warn but still apply)."""
    pattern = AbstractPattern(
        name="low_confidence_pattern",
        abstract_strategy="incremental_validation_tight_feedback",
        concrete_instances=[{"domain": "coding"}],
        applicable_domains=["coding", "writing"],
        transfer_confidence=0.2,  # Very low confidence
        success_count=2,
        total_transfers=10,
    )

    result = fresh_bridge.apply_to_new_domain(
        pattern=pattern, target_domain="writing", context={"task": "write report"}
    )

    # Should still return result, just with warning
    assert result is not None
    assert result["confidence"] == 0.2


def test_get_transferable_patterns_empty_domain(fresh_bridge: DomainTransferBridge) -> None:
    """Test getting patterns for domain with no applicable patterns."""
    patterns = fresh_bridge.get_transferable_patterns("nonexistent_domain")

    assert isinstance(patterns, list)
    # May have 0 patterns or patterns with "unknown" in applicable_domains
    for pattern in patterns:
        assert "nonexistent_domain" in pattern.applicable_domains


def test_record_transfer_outcome_nonexistent_pattern(fresh_bridge: DomainTransferBridge) -> None:
    """Test recording outcome for pattern that doesn't exist."""
    # Should not raise error
    fresh_bridge.record_transfer_outcome(
        pattern_name="nonexistent_pattern", success=True, target_domain="coding"
    )
    # Should do nothing silently


def test_record_transfer_failure(fresh_bridge: DomainTransferBridge) -> None:
    """Test recording failed transfer decreases confidence."""
    # Create a pattern
    experience = {
        "domain": "coding",
        "action": "test incrementally",
        "outcome": {"status": "success"},
        "valence": 0.9,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)
    assert pattern is not None
    initial_confidence = pattern.transfer_confidence

    # Record multiple failures
    for _ in range(5):
        fresh_bridge.record_transfer_outcome(
            pattern_name=pattern.name, success=False, target_domain="new_domain"
        )

    # Confidence should decrease
    updated_pattern = fresh_bridge._patterns[pattern.name]
    assert updated_pattern.transfer_confidence < initial_confidence


def test_record_transfer_adds_domain(fresh_bridge: DomainTransferBridge) -> None:
    """Test that successful transfer adds new domain to applicable list."""
    # Create a pattern
    experience = {
        "domain": "coding",
        "action": "test incrementally",
        "outcome": {"status": "success"},
        "valence": 0.9,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)
    assert pattern is not None
    initial_domains = pattern.applicable_domains.copy()

    # Record successful transfer to new domain
    new_domain = "robotics"
    fresh_bridge.record_transfer_outcome(
        pattern_name=pattern.name, success=True, target_domain=new_domain
    )

    # New domain should be added
    updated_pattern = fresh_bridge._patterns[pattern.name]
    assert new_domain in updated_pattern.applicable_domains
    assert len(updated_pattern.applicable_domains) == len(initial_domains) + 1


# ============================================================================
# Private Method Tests
# ============================================================================


def test_generalize_strategy_test_keywords(fresh_bridge: DomainTransferBridge) -> None:
    """Test strategy generalization with test/verify keywords."""
    strategy = fresh_bridge._generalize_strategy(
        "write test and validate", {"status": "success"}, "coding"
    )

    assert strategy == "incremental_validation_tight_feedback"


def test_generalize_strategy_decompose_keywords(fresh_bridge: DomainTransferBridge) -> None:
    """Test strategy generalization with decompose keywords."""
    strategy = fresh_bridge._generalize_strategy(
        "break down into modular pieces", {"status": "success"}, "coding"
    )

    assert strategy == "hierarchical_decomposition"


def test_generalize_strategy_fix_keywords(fresh_bridge: DomainTransferBridge) -> None:
    """Test strategy generalization with fix/debug keywords."""
    strategy = fresh_bridge._generalize_strategy(
        "debug the issue and recover", {"status": "success"}, "debugging"
    )

    assert strategy == "adaptive_error_recovery"


def test_generalize_strategy_explore_keywords(fresh_bridge: DomainTransferBridge) -> None:
    """Test strategy generalization with explore keywords."""
    strategy = fresh_bridge._generalize_strategy(
        "survey options before choosing", {"status": "success"}, "research"
    )

    assert strategy == "exploration_before_exploitation"


def test_generalize_strategy_constraint_keywords(fresh_bridge: DomainTransferBridge) -> None:
    """Test strategy generalization with constraint keywords."""
    strategy = fresh_bridge._generalize_strategy(
        "identify all requirements and constraints", {"status": "success"}, "planning"
    )

    assert strategy == "constraint_satisfaction_propagation"


def test_generalize_strategy_no_match(fresh_bridge: DomainTransferBridge) -> None:
    """Test strategy generalization when no keywords match."""
    strategy = fresh_bridge._generalize_strategy(
        "completely unrelated action", {"status": "success"}, "unknown"
    )

    assert strategy == ""


def test_generalize_strategy_failure_outcome(fresh_bridge: DomainTransferBridge) -> None:
    """Test that some strategies require success outcome."""
    # Incremental validation requires success
    strategy = fresh_bridge._generalize_strategy(
        "test incrementally", {"status": "error"}, "coding"
    )

    assert strategy == ""  # Should not generalize failed incremental validation


def test_infer_applicable_domains(fresh_bridge: DomainTransferBridge) -> None:
    """Test domain inference for various strategies."""
    domains1 = fresh_bridge._infer_applicable_domains("incremental_validation_tight_feedback")
    assert "coding" in domains1
    assert "writing" in domains1

    domains2 = fresh_bridge._infer_applicable_domains("hierarchical_decomposition")
    assert "coding" in domains2
    assert "project_planning" in domains2

    domains3 = fresh_bridge._infer_applicable_domains("unknown_strategy")
    assert domains3 == ["unknown"]


# ============================================================================
# Parametrized Tests
# ============================================================================


@pytest.mark.parametrize(
    "action_text,expected_strategy",
    [
        ("write test first", "incremental_validation_tight_feedback"),
        ("break down complex task", "hierarchical_decomposition"),
        ("fix the bug quickly", "adaptive_error_recovery"),
        ("explore all options", "exploration_before_exploitation"),
        ("check all constraints", "constraint_satisfaction_propagation"),
    ],
)
def test_strategy_extraction_variations(
    fresh_bridge: DomainTransferBridge, action_text: str, expected_strategy: str
) -> None:
    """Test strategy extraction for various action descriptions."""
    experience = {
        "domain": "coding",
        "action": action_text,
        "outcome": {"status": "success"},
        "valence": 0.9,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)

    assert pattern is not None
    assert pattern.abstract_strategy == expected_strategy


@pytest.mark.parametrize("valence", [0.0, 0.3, 0.49])
def test_low_valence_threshold(fresh_bridge: DomainTransferBridge, valence: float) -> None:
    """Test that valences below 0.5 don't create patterns."""
    experience = {
        "domain": "coding",
        "action": "test incrementally",
        "outcome": {"status": "success"},
        "valence": valence,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)

    assert pattern is None


@pytest.mark.parametrize("valence", [0.5, 0.7, 0.9, 1.0])
def test_high_valence_creates_patterns(fresh_bridge: DomainTransferBridge, valence: float) -> None:
    """Test that valences at or above 0.5 create patterns."""
    experience = {
        "domain": "coding",
        "action": "test incrementally",
        "outcome": {"status": "success"},
        "valence": valence,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)

    assert pattern is not None


@pytest.mark.parametrize(
    "target_domain,expected_keyword",
    [
        ("coding", "test"),
        ("writing", "outline"),
        ("social_interaction", "gesture"),
        ("learning", "study"),
    ],
)
def test_incremental_validation_instantiation(
    fresh_bridge: DomainTransferBridge, target_domain: str, expected_keyword: str
) -> None:
    """Test incremental validation instantiation across domains."""
    strategy = "incremental_validation_tight_feedback"
    action = fresh_bridge._instantiate_in_domain(strategy, target_domain, {"task": "some task"})

    assert expected_keyword in action.lower()


@pytest.mark.parametrize("success", [True, False])
def test_transfer_outcome_confidence_update(
    fresh_bridge: DomainTransferBridge, success: bool
) -> None:
    """Test confidence updates for both success and failure."""
    # Create pattern
    experience = {
        "domain": "coding",
        "action": "test incrementally",
        "outcome": {"status": "success"},
        "valence": 0.9,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)
    assert pattern is not None
    initial_confidence = pattern.transfer_confidence

    # Record outcome
    fresh_bridge.record_transfer_outcome(
        pattern_name=pattern.name, success=success, target_domain="new_domain"
    )

    updated_pattern = fresh_bridge._patterns[pattern.name]

    if success:
        # Confidence should increase or stay same
        assert updated_pattern.transfer_confidence >= initial_confidence
    else:
        # Confidence should decrease
        assert updated_pattern.transfer_confidence < initial_confidence


# ============================================================================
# Integration Tests
# ============================================================================


def test_full_transfer_cycle(fresh_bridge: DomainTransferBridge) -> None:
    """Test complete transfer learning cycle."""
    # Step 1: Extract pattern from coding experience
    coding_experience = {
        "domain": "coding",
        "action": "write test first, implement incrementally",
        "outcome": {"status": "success"},
        "valence": 0.9,
    }

    pattern = fresh_bridge.extract_abstract_pattern(coding_experience)
    assert pattern is not None

    # Step 2: Transfer to writing domain
    instantiation = fresh_bridge.apply_to_new_domain(
        pattern=pattern, target_domain="writing", context={"task": "write essay"}
    )
    assert instantiation is not None

    # Step 3: Record successful transfer
    fresh_bridge.record_transfer_outcome(
        pattern_name=pattern.name, success=True, target_domain="writing"
    )

    # Step 4: Verify pattern evolved
    updated_pattern = fresh_bridge._patterns[pattern.name]
    assert "writing" in updated_pattern.applicable_domains
    assert updated_pattern.total_transfers > pattern.total_transfers


def test_multiple_pattern_extraction(fresh_bridge: DomainTransferBridge) -> None:
    """Test extracting multiple different patterns."""
    experiences = [
        {
            "domain": "coding",
            "action": "test incrementally",
            "outcome": {"status": "success"},
            "valence": 0.9,
        },
        {
            "domain": "planning",
            "action": "break down into modules",
            "outcome": {"status": "success"},
            "valence": 0.85,
        },
        {
            "domain": "debugging",
            "action": "fix and recover",
            "outcome": {"status": "success"},
            "valence": 0.8,
        },
    ]

    patterns = [fresh_bridge.extract_abstract_pattern(exp) for exp in experiences]

    # Should extract different strategies
    strategies = {p.abstract_strategy for p in patterns if p}
    assert len(strategies) >= 2  # At least 2 different strategies


def test_pattern_confidence_evolution(fresh_bridge: DomainTransferBridge) -> None:
    """Test that pattern confidence evolves realistically over time."""
    experience = {
        "domain": "coding",
        "action": "test incrementally",
        "outcome": {"status": "success"},
        "valence": 0.9,
    }

    pattern = fresh_bridge.extract_abstract_pattern(experience)
    assert pattern is not None

    # Track confidence over multiple transfers
    confidences = [pattern.transfer_confidence]

    # Mix of successes and failures
    outcomes = [True, True, False, True, False, False, True, True, True]
    for success in outcomes:
        fresh_bridge.record_transfer_outcome(
            pattern_name=pattern.name, success=success, target_domain="various"
        )
        updated = fresh_bridge._patterns[pattern.name]
        confidences.append(updated.transfer_confidence)

    # Confidence should be reasonable (between 0 and 1)
    assert all(0 <= c <= 1 for c in confidences)

    # Final confidence should reflect success rate (6 successes out of 9)
    final_pattern = fresh_bridge._patterns[pattern.name]
    expected_rate = final_pattern.success_count / final_pattern.total_transfers
    assert abs(final_pattern.transfer_confidence - expected_rate) < 0.01


def test_seeded_patterns_exist(fresh_bridge: DomainTransferBridge) -> None:
    """Test that bridge is seeded with core patterns."""
    expected_strategies = [
        "incremental_validation_tight_feedback",
        "hierarchical_decomposition",
        "adaptive_error_recovery",
        "exploration_before_exploitation",
    ]

    # Get all patterns
    all_patterns = list(fresh_bridge._patterns.values())

    # Check that seeded patterns exist
    found_strategies = {p.abstract_strategy for p in all_patterns}

    for strategy in expected_strategies:
        assert strategy in found_strategies


def test_singleton_behavior() -> None:
    """Test that get_domain_transfer_bridge returns singleton."""
    bridge1 = get_domain_transfer_bridge()
    bridge2 = get_domain_transfer_bridge()

    assert bridge1 is bridge2


def test_dataclass_abstract_pattern() -> None:
    """Test AbstractPattern dataclass initialization."""
    pattern = AbstractPattern(
        name="test_pattern",
        abstract_strategy="test_strategy",
        concrete_instances=[{"domain": "test"}],
        applicable_domains=["coding", "writing"],
        transfer_confidence=0.75,
        success_count=15,
        total_transfers=20,
    )

    assert pattern.name == "test_pattern"
    assert pattern.transfer_confidence == 0.75
    assert len(pattern.applicable_domains) == 2


def test_cross_domain_instantiation_consistency(fresh_bridge: DomainTransferBridge) -> None:
    """Test that same strategy instantiates consistently in same domain."""
    strategy = "incremental_validation_tight_feedback"
    context = {"task": "test task"}

    action1 = fresh_bridge._instantiate_in_domain(strategy, "coding", context)
    action2 = fresh_bridge._instantiate_in_domain(strategy, "coding", context)

    # Should produce same instantiation
    assert action1 == action2


def test_pattern_sorting_by_confidence(fresh_bridge: DomainTransferBridge) -> None:
    """Test that get_transferable_patterns sorts by confidence."""
    # Create patterns with different confidences
    for i, valence in enumerate([0.9, 0.7, 0.95, 0.6]):
        fresh_bridge.extract_abstract_pattern(
            {
                "domain": "coding",
                "action": f"test action {i}",
                "outcome": {"status": "success"},
                "valence": valence,
            }
        )

    patterns = fresh_bridge.get_transferable_patterns("coding")

    # Should be sorted descending by confidence
    for i in range(len(patterns) - 1):
        assert patterns[i].transfer_confidence >= patterns[i + 1].transfer_confidence
