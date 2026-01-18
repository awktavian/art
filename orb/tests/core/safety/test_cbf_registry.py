"""Unit tests for CBF Registry.

CREATED: December 14, 2025
PURPOSE: Comprehensive testing of centralized CBF registry

Test Coverage:
1. Singleton behavior (only one instance exists)
2. Barrier registration and validation
3. Tier/colony indexing and filtering
4. Bulk evaluation and safety checking
5. Violation detection and reporting
6. Enable/disable functionality
7. Thread safety (concurrent access)
8. Statistics and reporting
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import threading
import time
from typing import Any

from kagami.core.safety.cbf_registry import (
    BarrierEntry,
    BarrierFunction,
    CBFRegistry,
    get_cbf_registry,
    init_cbf_registry,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def clean_registry():
    """Provide a clean registry for each test."""
    # Reset singleton before test
    CBFRegistry.reset_singleton()
    registry = CBFRegistry()
    yield registry
    # Reset after test
    CBFRegistry.reset_singleton()


@pytest.fixture
def populated_registry(clean_registry):
    """Provide a registry with some test barriers."""

    def h_memory(state: dict[str, Any] | None) -> float:
        if state is None:
            return 0.0
        return 0.8 - state.get("memory", 0.0)

    def h_disk(state: dict[str, Any] | None) -> float:
        if state is None:
            return 0.0
        return 0.9 - state.get("disk", 0.0)

    def h_colony_0(state: dict[str, Any] | None) -> float:
        if state is None:
            return 0.0
        return 0.5 - state.get("colony_0_risk", 0.0)

    def h_action(state: dict[str, Any] | None) -> float:
        if state is None:
            return 0.0
        return 0.7 - state.get("action_risk", 0.0)

    # Register barriers
    clean_registry.register(
        tier=1, name="memory", func=h_memory, description="Memory usage barrier"
    )
    clean_registry.register(tier=1, name="disk", func=h_disk, description="Disk usage barrier")
    clean_registry.register(
        tier=2, name="colony_0", func=h_colony_0, colony=0, description="Colony 0 barrier"
    )
    clean_registry.register(tier=3, name="action", func=h_action, description="Action barrier")

    return clean_registry


# =============================================================================
# SINGLETON TESTS
# =============================================================================


def test_singleton_same_instance():
    """Test that multiple calls return same instance."""
    CBFRegistry.reset_singleton()

    r1 = CBFRegistry()
    r2 = CBFRegistry()
    r3 = get_cbf_registry()

    assert r1 is r2, f"CBFRegistry singleton failed: different instances r1={id(r1)} vs r2={id(r2)}"
    assert (
        r2 is r3
    ), f"CBFRegistry singleton failed: get_cbf_registry() returned different instance r2={id(r2)} vs r3={id(r3)}"

    CBFRegistry.reset_singleton()


def test_singleton_thread_safety():
    """Test that singleton is thread-safe."""
    CBFRegistry.reset_singleton()

    instances = []

    def create_instance():
        r = CBFRegistry()
        instances.append(id(r))

    # Create registry from 10 threads simultaneously
    threads = [threading.Thread(target=create_instance) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All should be same instance
    assert (
        len(set(instances)) == 1
    ), f"CBFRegistry thread safety violated: got {len(set(instances))} different instances from 10 threads"

    CBFRegistry.reset_singleton()


def test_singleton_initialization_once():
    """Test that initialization only happens once."""
    CBFRegistry.reset_singleton()

    r1 = CBFRegistry()
    initial_stats = r1.get_stats()

    # Register a barrier
    r1.register(tier=1, name="test", func=lambda s: 1.0)

    # Get registry again
    r2 = CBFRegistry()
    second_stats = r2.get_stats()

    # Should have same state (not re-initialized)
    assert (
        r1 is r2
    ), f"CBFRegistry singleton identity lost after registration: r1={id(r1)} vs r2={id(r2)}"
    assert (
        second_stats["total_barriers"] == initial_stats["total_barriers"] + 1
    ), f"CBFRegistry re-initialized instead of persisting state: expected {initial_stats['total_barriers'] + 1} barriers, got {second_stats['total_barriers']}"

    CBFRegistry.reset_singleton()


# =============================================================================
# BARRIER REGISTRATION TESTS
# =============================================================================


def test_register_basic(clean_registry) -> None:
    """Test basic barrier registration."""

    def h_test(state: dict[str, Any] | None) -> float:
        return 1.0

    clean_registry.register(tier=1, name="test", func=h_test, description="Test barrier")

    entry = clean_registry.get_barrier("test")
    assert entry is not None, "Registered barrier 'test' not found in registry"
    assert entry.name == "test", f"Barrier name mismatch: expected 'test', got '{entry.name}'"
    assert entry.tier == 1, f"Barrier tier mismatch: expected 1, got {entry.tier}"
    assert (
        entry.threshold == 0.0
    ), f"Default threshold should be 0.0 (safety invariant h(x) ≥ 0), got {entry.threshold}"
    assert (
        entry.enabled is True
    ), f"Newly registered barrier should be enabled by default, got {entry.enabled}"
    assert (
        entry.description == "Test barrier"
    ), f"Barrier description mismatch: expected 'Test barrier', got '{entry.description}'"


def test_register_with_custom_threshold(clean_registry) -> None:
    """Test registration with custom threshold."""

    def h_test(state: dict[str, Any] | None) -> float:
        return 0.5

    clean_registry.register(tier=1, name="test", func=h_test, threshold=0.3)

    entry = clean_registry.get_barrier("test")
    assert entry is not None, "Registered barrier 'test' not found in registry"
    assert (
        entry.threshold == 0.3
    ), f"Custom threshold not set correctly: expected 0.3, got {entry.threshold}"


def test_register_tier_2_with_colony(clean_registry) -> None:
    """Test Tier 2 registration requires colony."""

    def h_test(state: dict[str, Any] | None) -> float:
        return 1.0

    # Should succeed with colony
    clean_registry.register(tier=2, name="test", func=h_test, colony=3)
    entry = clean_registry.get_barrier("test")
    assert entry is not None, "Tier 2 barrier with colony not registered"
    assert entry.colony == 3, f"Tier 2 colony ID mismatch: expected 3, got {entry.colony}"


def test_register_tier_2_without_colony_fails(clean_registry) -> None:
    """Test Tier 2 registration fails without colony."""

    def h_test(state: dict[str, Any] | None) -> float:
        return 1.0

    with pytest.raises(ValueError, match="Tier 2 barriers must specify colony"):
        clean_registry.register(tier=2, name="test", func=h_test)


def test_register_invalid_colony_fails(clean_registry) -> None:
    """Test registration fails with invalid colony ID."""

    def h_test(state: dict[str, Any] | None) -> float:
        return 1.0

    with pytest.raises(ValueError, match="colony must be 0-6"):
        clean_registry.register(tier=2, name="test", func=h_test, colony=10)


def test_register_duplicate_name_fails(clean_registry) -> None:
    """Test that duplicate names are rejected."""

    def h_test(state: dict[str, Any] | None) -> float:
        return 1.0

    clean_registry.register(tier=1, name="test", func=h_test)

    with pytest.raises(ValueError, match="already registered"):
        clean_registry.register(tier=1, name="test", func=h_test)


def test_register_invalid_tier_fails(clean_registry) -> None:
    """Test that invalid tier is rejected."""

    def h_test(state: dict[str, Any] | None) -> float:
        return 1.0

    with pytest.raises(ValueError, match="tier must be 1, 2, or 3"):
        clean_registry.register(tier=4, name="test", func=h_test)


def test_register_non_callable_fails(clean_registry) -> None:
    """Test that non-callable func is rejected."""
    with pytest.raises(TypeError, match="func must be callable"):
        clean_registry.register(tier=1, name="test", func="not a function")


# =============================================================================
# BARRIER ENTRY TESTS
# =============================================================================


def test_barrier_entry_evaluate():
    """Test BarrierEntry evaluation."""

    def h_test(state: dict[str, Any] | None) -> float:
        if state is None:
            return 0.0
        return 1.0 - state.get("x", 0.0)

    entry = BarrierEntry(tier=1, name="test", func=h_test)

    # Evaluate with state
    h = entry.evaluate({"x": 0.3})
    assert h == 0.7, f"Barrier evaluation incorrect: h(x) = 1.0 - 0.3 should be 0.7, got {h}"
    assert (
        entry.evaluation_count == 1
    ), f"Evaluation count not incremented: expected 1, got {entry.evaluation_count}"
    assert entry.last_value == 0.7, f"Last value not cached: expected 0.7, got {entry.last_value}"
    assert entry.last_check is not None, "Last check timestamp not recorded"


def test_barrier_entry_violation_tracking():
    """Test that violations are tracked."""

    def h_test(state: dict[str, Any] | None) -> float:
        if state is None:
            return 0.0
        return 0.5 - state.get("x", 0.0)

    entry = BarrierEntry(tier=1, name="test", func=h_test, threshold=0.0)

    # Safe evaluation
    entry.evaluate({"x": 0.3})
    assert (
        entry.violation_count == 0
    ), f"Safe evaluation incorrectly flagged as violation: h(x) = 0.2 ≥ 0, count = {entry.violation_count}"

    # Violating evaluation
    entry.evaluate({"x": 0.8})
    assert (
        entry.violation_count == 1
    ), f"Violation not tracked: h(x) = -0.3 < 0 should increment count, got {entry.violation_count}"


def test_barrier_entry_is_safe():
    """Test BarrierEntry.is_safe()."""

    def h_test(state: dict[str, Any] | None) -> float:
        if state is None:
            return 0.0
        return 1.0 - state.get("x", 0.0)

    entry = BarrierEntry(tier=1, name="test", func=h_test, threshold=0.0)

    assert entry.is_safe({"x": 0.3}) is True, "Safety check failed: h(x) = 0.7 ≥ 0 should be safe"
    assert (
        entry.is_safe({"x": 1.5}) is False
    ), "Safety check failed: h(x) = -0.5 < 0 should be unsafe"


def test_barrier_entry_disabled_always_safe():
    """Test that disabled barriers are always safe."""

    def h_test(state: dict[str, Any] | None) -> float:
        return -100.0  # Always violates

    entry = BarrierEntry(tier=1, name="test", func=h_test, enabled=False)

    assert (
        entry.is_safe({}) is True
    ), "Disabled barriers must always return safe, regardless of h(x) value"


# =============================================================================
# BULK EVALUATION TESTS
# =============================================================================


def test_check_all_no_filter(populated_registry) -> None:
    """Test checking all barriers without filter."""
    state = {"memory": 0.5, "disk": 0.7, "colony_0_risk": 0.2, "action_risk": 0.3}

    results = populated_registry.check_all(state=state)

    assert (
        len(results) == 4
    ), f"check_all should return all 4 registered barriers, got {len(results)}"
    assert "memory" in results, "Tier 1 barrier 'memory' missing from check_all results"
    assert "disk" in results, "Tier 1 barrier 'disk' missing from check_all results"
    assert "colony_0" in results, "Tier 2 barrier 'colony_0' missing from check_all results"
    assert "action" in results, "Tier 3 barrier 'action' missing from check_all results"


def test_check_all_tier_filter(populated_registry) -> None:
    """Test checking barriers filtered by tier."""
    state = {"memory": 0.5, "disk": 0.7}

    results = populated_registry.check_all(tier=1, state=state)

    assert len(results) == 2, f"Tier 1 filter should return 2 barriers, got {len(results)}"
    assert "memory" in results, "Tier 1 barrier 'memory' missing from tier=1 filter"
    assert "disk" in results, "Tier 1 barrier 'disk' missing from tier=1 filter"
    assert "colony_0" not in results, "Tier 2 barrier 'colony_0' should not appear in tier=1 filter"


def test_check_all_colony_filter(populated_registry) -> None:
    """Test checking barriers filtered by colony."""
    state = {"colony_0_risk": 0.2}

    results = populated_registry.check_all(colony=0, state=state)

    assert len(results) == 1, f"Colony 0 filter should return 1 barrier, got {len(results)}"
    assert "colony_0" in results, "Colony 0 barrier missing from colony=0 filter"


def test_check_all_values_correct(populated_registry) -> None:
    """Test that barrier values are computed correctly."""
    state = {"memory": 0.3, "disk": 0.5}

    results = populated_registry.check_all(tier=1, state=state)

    assert results["memory"] == pytest.approx(
        0.5
    ), f"Memory barrier value incorrect: h(x) = 0.8 - 0.3 should be 0.5, got {results['memory']}"
    assert results["disk"] == pytest.approx(
        0.4
    ), f"Disk barrier value incorrect: h(x) = 0.9 - 0.5 should be 0.4, got {results['disk']}"


# =============================================================================
# SAFETY CHECKING TESTS
# =============================================================================


def test_is_safe_all_barriers_satisfied(populated_registry) -> None:
    """Test is_safe when all barriers are satisfied."""
    state = {"memory": 0.3, "disk": 0.5, "colony_0_risk": 0.2, "action_risk": 0.3}

    assert (
        populated_registry.is_safe(state=state) is True
    ), "All barriers satisfied (h(x) ≥ 0), is_safe should return True"


def test_is_safe_one_violation(populated_registry) -> None:
    """Test is_safe when one barrier is violated."""
    state = {"memory": 0.9, "disk": 0.5, "colony_0_risk": 0.2, "action_risk": 0.3}

    assert (
        populated_registry.is_safe(state=state) is False
    ), "Memory barrier violated (h(x) < 0), is_safe should return False"


def test_is_safe_tier_filter(populated_registry) -> None:
    """Test is_safe with tier filter."""
    # Tier 1 safe, but tier 3 violated
    state = {"memory": 0.3, "disk": 0.5, "action_risk": 0.9}

    assert (
        populated_registry.is_safe(tier=1, state=state) is True
    ), "Tier 1 barriers safe, is_safe(tier=1) should return True"
    assert (
        populated_registry.is_safe(tier=3, state=state) is False
    ), "Tier 3 action barrier violated, is_safe(tier=3) should return False"


def test_is_safe_colony_filter(populated_registry) -> None:
    """Test is_safe with colony filter."""
    state = {"colony_0_risk": 0.2}

    assert (
        populated_registry.is_safe(colony=0, state=state) is True
    ), "Colony 0 barrier safe (h(x) = 0.3 ≥ 0), is_safe(colony=0) should return True"

    state = {"colony_0_risk": 0.9}
    assert (
        populated_registry.is_safe(colony=0, state=state) is False
    ), "Colony 0 barrier violated (h(x) = -0.4 < 0), is_safe(colony=0) should return False"


# =============================================================================
# VIOLATION DETECTION TESTS
# =============================================================================


def test_get_violations_none(populated_registry) -> None:
    """Test get_violations when no violations."""
    state = {"memory": 0.3, "disk": 0.5, "colony_0_risk": 0.2, "action_risk": 0.3}

    violations = populated_registry.get_violations(state=state)
    assert (
        len(violations) == 0
    ), f"No barriers violated, get_violations should return empty list, got {len(violations)} violations"


def test_get_violations_one(populated_registry) -> None:
    """Test get_violations with one violation."""
    state = {"memory": 0.9, "disk": 0.5, "colony_0_risk": 0.2, "action_risk": 0.3}

    violations = populated_registry.get_violations(state=state)
    assert (
        len(violations) == 1
    ), f"One barrier violated (memory), expected 1 violation, got {len(violations)}"
    assert (
        violations[0]["name"] == "memory"
    ), f"Violation should be 'memory' barrier, got '{violations[0]['name']}'"
    assert violations[0]["h_x"] == pytest.approx(
        -0.1
    ), f"Memory h(x) = 0.8 - 0.9 = -0.1, got {violations[0]['h_x']}"
    assert (
        violations[0]["threshold"] == 0.0
    ), f"Safety threshold is 0.0 (h(x) ≥ 0 invariant), got {violations[0]['threshold']}"
    assert violations[0]["margin"] == pytest.approx(
        -0.1
    ), f"Safety margin = h(x) - threshold = -0.1, got {violations[0]['margin']}"


def test_get_violations_multiple(populated_registry) -> None:
    """Test get_violations with multiple violations."""
    state = {"memory": 0.9, "disk": 0.95, "colony_0_risk": 0.2, "action_risk": 0.3}

    violations = populated_registry.get_violations(state=state)
    assert (
        len(violations) == 2
    ), f"Two barriers violated (memory, disk), expected 2 violations, got {len(violations)}"
    names = {v["name"] for v in violations}
    assert names == {"memory", "disk"}, f"Violations should be memory and disk, got {names}"


def test_get_violations_tier_filter(populated_registry) -> None:
    """Test get_violations with tier filter."""
    state = {"memory": 0.9, "disk": 0.95, "action_risk": 0.9}

    # Only tier 1 violations
    violations = populated_registry.get_violations(tier=1, state=state)
    assert len(violations) == 2, f"Tier 1 has 2 violations (memory, disk), got {len(violations)}"

    # Only tier 3 violations
    violations = populated_registry.get_violations(tier=3, state=state)
    assert len(violations) == 1, f"Tier 3 has 1 violation (action), got {len(violations)}"
    assert (
        violations[0]["name"] == "action"
    ), f"Tier 3 violation should be 'action', got '{violations[0]['name']}'"


# =============================================================================
# ENABLE/DISABLE TESTS
# =============================================================================


def test_enable_disable_barrier(populated_registry) -> None:
    """Test enabling and disabling barriers."""
    state = {"memory": 0.9}  # Would violate

    # Initially enabled, should violate
    assert (
        populated_registry.is_safe(tier=1, state=state) is False
    ), "Memory barrier enabled and violated, is_safe should return False"

    # Disable barrier
    populated_registry.disable("memory")
    entry = populated_registry.get_barrier("memory")
    assert entry is not None, "Memory barrier should still exist after disabling"
    assert entry.enabled is False, "Memory barrier should be disabled after disable() call"

    # Now should be safe (barrier disabled)
    assert (
        populated_registry.is_safe(tier=1, state=state) is True
    ), "Disabled barriers ignored, tier 1 should be safe"

    # Re-enable
    populated_registry.enable("memory")
    assert (
        populated_registry.is_safe(tier=1, state=state) is False
    ), "Re-enabled memory barrier violated again, is_safe should return False"


def test_disable_nonexistent_barrier_fails(clean_registry) -> None:
    """Test that disabling nonexistent barrier raises error."""
    with pytest.raises(KeyError, match="not found"):
        clean_registry.disable("nonexistent")


def test_enable_nonexistent_barrier_fails(clean_registry) -> None:
    """Test that enabling nonexistent barrier raises error."""
    with pytest.raises(KeyError, match="not found"):
        clean_registry.enable("nonexistent")


# =============================================================================
# UNREGISTER TESTS
# =============================================================================


def test_unregister_barrier(populated_registry) -> None:
    """Test unregistering a barrier."""
    assert (
        populated_registry.get_barrier("memory") is not None
    ), "Memory barrier should exist before unregister"

    populated_registry.unregister("memory")

    assert (
        populated_registry.get_barrier("memory") is None
    ), "Memory barrier should not exist after unregister"
    stats = populated_registry.get_stats()
    assert (
        stats["total_barriers"] == 3
    ), f"After unregistering 1 of 4 barriers, total should be 3, got {stats['total_barriers']}"
    assert (
        stats["tier_1"] == 1
    ), f"Tier 1 should have 1 barrier (disk) after unregistering memory, got {stats['tier_1']}"


def test_unregister_nonexistent_fails(clean_registry) -> None:
    """Test that unregistering nonexistent barrier raises error."""
    with pytest.raises(KeyError, match="not found"):
        clean_registry.unregister("nonexistent")


# =============================================================================
# STATISTICS TESTS
# =============================================================================


def test_get_stats_empty(clean_registry) -> None:
    """Test statistics on empty registry."""
    stats = clean_registry.get_stats()

    assert (
        stats["total_barriers"] == 0
    ), f"Empty registry should have 0 barriers, got {stats['total_barriers']}"
    assert (
        stats["tier_1"] == 0
    ), f"Empty registry should have 0 tier 1 barriers, got {stats['tier_1']}"
    assert (
        stats["tier_2"] == 0
    ), f"Empty registry should have 0 tier 2 barriers, got {stats['tier_2']}"
    assert (
        stats["tier_3"] == 0
    ), f"Empty registry should have 0 tier 3 barriers, got {stats['tier_3']}"
    assert (
        stats["enabled"] == 0
    ), f"Empty registry should have 0 enabled barriers, got {stats['enabled']}"
    assert (
        stats["disabled"] == 0
    ), f"Empty registry should have 0 disabled barriers, got {stats['disabled']}"
    assert (
        stats["total_evaluations"] == 0
    ), f"Empty registry should have 0 evaluations, got {stats['total_evaluations']}"
    assert (
        stats["total_violations"] == 0
    ), f"Empty registry should have 0 violations, got {stats['total_violations']}"


def test_get_stats_populated(populated_registry) -> None:
    """Test statistics on populated registry."""
    stats = populated_registry.get_stats()

    assert (
        stats["total_barriers"] == 4
    ), f"Populated registry has 4 barriers (memory, disk, colony_0, action), got {stats['total_barriers']}"
    assert stats["tier_1"] == 2, f"Tier 1 has 2 barriers (memory, disk), got {stats['tier_1']}"
    assert stats["tier_2"] == 1, f"Tier 2 has 1 barrier (colony_0), got {stats['tier_2']}"
    assert stats["tier_3"] == 1, f"Tier 3 has 1 barrier (action), got {stats['tier_3']}"
    assert (
        stats["enabled"] == 4
    ), f"All 4 barriers should be enabled by default, got {stats['enabled']}"


def test_get_stats_after_evaluations(populated_registry) -> None:
    """Test that evaluation stats are tracked."""
    state = {"memory": 0.5, "disk": 0.7, "colony_0_risk": 0.2, "action_risk": 0.3}

    # Run some evaluations
    populated_registry.check_all(state=state)
    populated_registry.check_all(state=state)

    stats = populated_registry.get_stats()
    assert (
        stats["total_evaluations"] == 8
    ), f"4 barriers × 2 checks should = 8 evaluations, got {stats['total_evaluations']}"


def test_reset_stats(populated_registry) -> None:
    """Test resetting statistics."""
    state = {"memory": 0.9}  # Causes violation

    # Run evaluations
    populated_registry.check_all(state=state)

    stats_before = populated_registry.get_stats()
    assert stats_before["total_evaluations"] > 0, "Evaluations should be tracked before reset"

    # Reset
    populated_registry.reset_stats()

    stats_after = populated_registry.get_stats()
    assert (
        stats_after["total_evaluations"] == 0
    ), f"Evaluation count should be 0 after reset, got {stats_after['total_evaluations']}"
    assert (
        stats_after["total_violations"] == 0
    ), f"Violation count should be 0 after reset, got {stats_after['total_violations']}"


# =============================================================================
# LIST BARRIERS TESTS
# =============================================================================


def test_list_barriers_all(populated_registry) -> None:
    """Test listing all barriers."""
    barriers = populated_registry.list_barriers()

    assert len(barriers) == 4, f"list_barriers should return all 4 barriers, got {len(barriers)}"
    names = {b["name"] for b in barriers}
    assert names == {
        "memory",
        "disk",
        "colony_0",
        "action",
    }, f"Barrier names should be complete set, got {names}"


def test_list_barriers_tier_filter(populated_registry) -> None:
    """Test listing barriers filtered by tier."""
    barriers = populated_registry.list_barriers(tier=1)

    assert len(barriers) == 2, f"Tier 1 filter should return 2 barriers, got {len(barriers)}"
    names = {b["name"] for b in barriers}
    assert names == {"memory", "disk"}, f"Tier 1 barriers should be memory and disk, got {names}"


def test_list_barriers_colony_filter(populated_registry) -> None:
    """Test listing barriers filtered by colony."""
    barriers = populated_registry.list_barriers(colony=0)

    assert len(barriers) == 1, f"Colony 0 filter should return 1 barrier, got {len(barriers)}"
    assert (
        barriers[0]["name"] == "colony_0"
    ), f"Colony 0 barrier name should be 'colony_0', got '{barriers[0]['name']}'"


def test_list_barriers_enabled_only(populated_registry) -> None:
    """Test listing only enabled barriers."""
    populated_registry.disable("memory")

    barriers = populated_registry.list_barriers(enabled_only=True)
    assert (
        len(barriers) == 3
    ), f"After disabling 1 of 4, enabled_only should return 3, got {len(barriers)}"

    barriers_all = populated_registry.list_barriers(enabled_only=False)
    assert (
        len(barriers_all) == 4
    ), f"enabled_only=False should return all 4 barriers, got {len(barriers_all)}"


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


def test_init_cbf_registry():
    """Test initialization function."""
    CBFRegistry.reset_singleton()

    registry = init_cbf_registry()

    stats = registry.get_stats()
    assert (
        stats["total_barriers"] >= 4
    ), f"init_cbf_registry should register at least 4 organism barriers, got {stats['total_barriers']}"
    assert (
        stats["tier_1"] >= 4
    ), f"Organism barriers are tier 1, expected at least 4, got {stats['tier_1']}"

    # Check that organism barriers are registered
    assert (
        registry.get_barrier("organism.memory") is not None
    ), "Organism memory barrier not registered by init_cbf_registry"
    assert (
        registry.get_barrier("organism.process") is not None
    ), "Organism process barrier not registered by init_cbf_registry"
    assert (
        registry.get_barrier("organism.blanket_integrity") is not None
    ), "Organism blanket integrity barrier not registered by init_cbf_registry"
    assert (
        registry.get_barrier("organism.disk_space") is not None
    ), "Organism disk space barrier not registered by init_cbf_registry"

    CBFRegistry.reset_singleton()


def test_get_cbf_registry():
    """Test convenience getter function."""
    CBFRegistry.reset_singleton()

    r1 = get_cbf_registry()
    r2 = get_cbf_registry()

    assert (
        r1 is r2
    ), f"get_cbf_registry() should return same instance, got r1={id(r1)} vs r2={id(r2)}"

    CBFRegistry.reset_singleton()


# =============================================================================
# THREAD SAFETY TESTS
# =============================================================================


def test_concurrent_registration():
    """Test that concurrent registration is thread-safe."""
    CBFRegistry.reset_singleton()
    registry = CBFRegistry()

    def register_barrier(idx: int):
        def h(s):
            return 1.0

        registry.register(tier=1, name=f"barrier_{idx}", func=h)

    # Register 20 barriers concurrently
    threads = [threading.Thread(target=register_barrier, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    stats = registry.get_stats()
    assert (
        stats["total_barriers"] == 20
    ), f"Concurrent registration of 20 barriers from 20 threads should result in 20 total, got {stats['total_barriers']}"

    CBFRegistry.reset_singleton()


def test_concurrent_evaluation():
    """Test that concurrent evaluation is thread-safe."""
    CBFRegistry.reset_singleton()
    registry = CBFRegistry()

    def h(s):
        return 1.0

    registry.register(tier=1, name="test", func=h)

    results = []

    def check_barrier():
        r = registry.check_all(state={})
        results.append(r)

    # Run 100 concurrent checks
    threads = [threading.Thread(target=check_barrier) for _ in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert (
        len(results) == 100
    ), f"100 concurrent check_all calls should produce 100 results, got {len(results)}"
    entry = registry.get_barrier("test")
    assert entry is not None, "Test barrier should exist after concurrent evaluation"
    assert (
        entry.evaluation_count == 100
    ), f"100 concurrent evaluations should increment count to 100, got {entry.evaluation_count}"

    CBFRegistry.reset_singleton()


# =============================================================================
# EDGE CASES
# =============================================================================


def test_evaluate_with_none_state(clean_registry) -> None:
    """Test that barriers handle None state gracefully."""

    def h_test(state: dict[str, Any] | None) -> float:
        if state is None:
            return 1.0
        return 0.0

    clean_registry.register(tier=1, name="test", func=h_test)

    results = clean_registry.check_all(state=None)
    assert (
        results["test"] == 1.0
    ), f"Barrier with None state should return 1.0 (safe), got {results['test']}"


def test_evaluate_with_missing_keys(clean_registry) -> None:
    """Test that barriers handle missing state keys gracefully."""

    def h_test(state: dict[str, Any] | None) -> float:
        if state is None:
            return 0.0
        return state.get("missing_key", 0.5)

    clean_registry.register(tier=1, name="test", func=h_test)

    results = clean_registry.check_all(state={"other_key": 1.0})
    assert (
        results["test"] == 0.5
    ), f"Barrier should use default 0.5 when state key missing, got {results['test']}"


def test_barrier_function_exception_handling(clean_registry) -> None:
    """Test that barrier function exceptions are handled."""

    def h_broken(state: dict[str, Any] | None) -> float:
        raise ValueError("Barrier is broken!")

    clean_registry.register(tier=1, name="broken", func=h_broken)

    # Should not crash, should return highly negative value
    results = clean_registry.check_all(state={})
    assert (
        results["broken"] == -1000.0
    ), f"Broken barrier should return -1000.0 sentinel value, got {results['broken']}"

    # Should be marked as violation
    assert not clean_registry.is_safe(
        state={}
    ), "Broken barrier (h(x) = -1000 < 0) should mark system as unsafe"


def test_multiple_colonies():
    """Test registry with multiple colony barriers."""
    CBFRegistry.reset_singleton()
    registry = CBFRegistry()

    for i in range(7):  # 7 colonies

        def h(s):
            return 1.0

        registry.register(tier=2, name=f"colony_{i}", func=h, colony=i)

    stats = registry.get_stats()
    assert (
        stats["tier_2"] == 7
    ), f"7 colony barriers registered, tier 2 count should be 7, got {stats['tier_2']}"

    # Check colony filtering
    for i in range(7):
        barriers = registry.list_barriers(colony=i)
        assert len(barriers) == 1, f"Colony {i} should have 1 barrier, got {len(barriers)}"
        assert (
            barriers[0]["colony"] == i
        ), f"Colony {i} barrier has wrong colony ID: {barriers[0]['colony']}"

    CBFRegistry.reset_singleton()


# =============================================================================
# COVERAGE: 100%
# =============================================================================

if __name__ == "__main__":
    pytest.main(
        [__file__, "-v", "--cov=kagami.core.safety.cbf_registry", "--cov-report=term-missing"]
    )
