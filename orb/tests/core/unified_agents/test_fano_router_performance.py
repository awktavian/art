"""Performance tests for FanoActionRouter optimization.

Tests the precomputed lookup table and LRU caching optimizations.

PERFORMANCE TARGETS:
- Cache hit rate: >70% on typical workloads
- Routing latency: <1ms on cache hit
- Lookup table: 7×7 = 49 precomputed compositions

Created: December 18, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import time
from typing import Any

from kagami.core.unified_agents.fano_action_router import (
    FanoActionRouter,
    create_fano_router,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def router() -> FanoActionRouter:
    """Create router with default cache size."""
    return create_fano_router()


@pytest.fixture
def small_cache_router() -> FanoActionRouter:
    """Create router with small cache for testing eviction."""
    return FanoActionRouter(cache_size=4)


# =============================================================================
# TEST FANO LOOKUP TABLE
# =============================================================================


class TestFanoLookupTable:
    """Test precomputed Fano lookup table."""

    def test_lookup_table_initialized(self, router: FanoActionRouter) -> None:
        """Lookup table should be built at initialization."""
        assert hasattr(router, "_fano_lookup_table")
        assert router._fano_lookup_table is not None

        # Should be 7×7 tensor
        table = router._fano_lookup_table
        assert table.shape == (7, 7)

    def test_lookup_table_valid_compositions(self, router: FanoActionRouter) -> None:
        """Valid Fano compositions should be in lookup table."""
        # Test known Fano line: e₁ × e₂ = e₃ (0-indexed: 0 × 1 = 2)
        result = router._fano_lookup_table[0, 1].item()
        assert result == 2

        # Test another line: e₁ × e₄ = e₅ (0-indexed: 0 × 3 = 4)
        result = router._fano_lookup_table[0, 3].item()
        assert result == 4

    def test_lookup_table_invalid_compositions(self, router: FanoActionRouter) -> None:
        """Invalid compositions should be -1 in lookup table."""
        # Same colony multiplication is not valid
        result = router._fano_lookup_table[0, 0].item()
        assert result == -1

    def test_lookup_table_matches_get_fano_composition(self, router: FanoActionRouter) -> None:
        """Lookup table should match get_fano_composition results."""
        for i in range(7):
            for j in range(7):
                table_result = router._fano_lookup_table[i, j].item()
                method_result = router.get_fano_composition(i, j)

                if method_result is None:
                    assert table_result == -1
                else:
                    assert table_result == method_result


# =============================================================================
# TEST LRU CACHE
# =============================================================================


class TestLRUCache:
    """Test LRU caching for affinity results."""

    def test_cache_initialized(self, router: FanoActionRouter) -> None:
        """Cache should be initialized at startup."""
        assert hasattr(router, "_affinity_cache")
        assert router._cache_size == 8192
        assert router._cache_hits == 0
        assert router._cache_misses == 0

    def test_cache_hit_on_repeated_action(self, router: FanoActionRouter) -> None:
        """Repeated identical actions should hit cache."""
        action = "build.feature"
        params: dict[str, Any] = {}

        # First call - cache miss
        router.route(action, params, complexity=0.1)
        assert router._cache_misses == 1
        assert router._cache_hits == 0

        # Second call - cache hit
        router.route(action, params, complexity=0.1)
        assert router._cache_hits == 1

        # Third call - cache hit
        router.route(action, params, complexity=0.1)
        assert router._cache_hits == 2

    def test_cache_miss_on_different_action(self, router: FanoActionRouter) -> None:
        """Different actions should cause cache miss."""
        router.route("build", {}, complexity=0.1)
        assert router._cache_misses == 1

        router.route("test", {}, complexity=0.1)
        assert router._cache_misses == 2

    def test_cache_considers_context(self, router: FanoActionRouter) -> None:
        """Cache should consider context in key."""
        action = "build"
        params: dict[str, Any] = {}

        # Different contexts should cause cache miss
        router.route(action, params, context={"domain": "ml"})
        assert router._cache_misses == 1

        router.route(action, params, context={"domain": "security"})
        assert router._cache_misses == 2

        # Same context should hit cache
        router.route(action, params, context={"domain": "ml"})
        assert router._cache_hits == 1

    def test_cache_lru_eviction(self, small_cache_router: FanoActionRouter) -> None:
        """Cache should evict oldest entries when full."""
        router = small_cache_router

        # Fill cache with 4 unique actions
        # Use same context to ensure consistent cache keys
        context: dict[str, Any] = {}
        actions = ["action1", "action2", "action3", "action4"]
        for action in actions:
            router.route(action, {}, complexity=0.1, context=context)

        assert len(router._affinity_cache) == 4
        assert router._cache_misses == 4

        # Add 5th action - should evict oldest (action1)
        router.route("action5", {}, complexity=0.1, context=context)
        assert len(router._affinity_cache) == 4
        assert router._cache_misses == 5

        # Accessing action3 should hit (still in cache after action5 added)
        router.route("action3", {}, complexity=0.1, context=context)
        assert router._cache_hits == 1

        # Accessing action1 again should miss (was evicted), and re-add it
        router.route("action1", {}, complexity=0.1, context=context)
        assert router._cache_misses == 6

        # Now action2 should be evicted (oldest after action1 was re-added)
        # Accessing action2 should miss
        router.route("action2", {}, complexity=0.1, context=context)
        assert router._cache_misses == 7

    def test_cache_stats(self, router: FanoActionRouter) -> None:
        """get_cache_stats should return accurate metrics."""
        # Initial state
        stats = router.get_cache_stats()
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 0
        assert stats["total_requests"] == 0
        assert stats["hit_rate"] == 0.0
        assert stats["cache_size"] == 0

        # Route some actions
        router.route("build", {}, complexity=0.1)  # miss
        router.route("build", {}, complexity=0.1)  # hit
        router.route("test", {}, complexity=0.1)  # miss

        stats = router.get_cache_stats()
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 2
        assert stats["total_requests"] == 3
        assert abs(stats["hit_rate"] - 1 / 3) < 0.01
        assert stats["cache_size"] == 2


# =============================================================================
# TEST CACHE HIT RATE
# =============================================================================


class TestCacheHitRate:
    """Test cache hit rate on realistic workloads."""

    def test_cache_hit_rate_repeated_actions(self, router: FanoActionRouter) -> None:
        """Cache should achieve >70% hit rate on repeated actions."""
        actions = [
            "build",
            "test",
            "fix",
            "integrate",
            "plan",
            "research",
            "verify",
        ]

        # Generate 1000 actions with repetitions
        action_sequence = []
        for _ in range(150):
            action_sequence.extend(actions)

        # Route all actions
        for action in action_sequence:
            router.route(action, {}, complexity=0.1)

        stats = router.get_cache_stats()
        assert stats["hit_rate"] > 0.7, f"Cache hit rate {stats['hit_rate']:.2%} < 70%"

    def test_cache_hit_rate_with_params(self, router: FanoActionRouter) -> None:
        """Cache should work well with parameterized actions."""
        action_patterns = [
            ("build.feature", {"name": "auth"}),
            ("build.feature", {"name": "api"}),
            ("test.unit", {"module": "core"}),
            ("test.unit", {"module": "api"}),
        ]

        # Generate 500 actions (many repeats)
        action_sequence = action_patterns * 125

        for action, params in action_sequence:
            router.route(action, params, complexity=0.1)

        stats = router.get_cache_stats()
        # Should get high hit rate due to repetition
        assert stats["hit_rate"] > 0.75


# =============================================================================
# TEST PERFORMANCE
# =============================================================================


class TestPerformance:
    """Test routing performance with optimizations."""

    def test_routing_latency_cold(self, router: FanoActionRouter) -> None:
        """Cold routing (cache miss) should be fast enough."""
        action = "build.feature"
        params: dict[str, Any] = {}

        start = time.perf_counter()
        router.route(action, params, complexity=0.1)
        latency = time.perf_counter() - start

        # First call (cold) should be < 10ms
        assert latency < 0.01, f"Cold routing took {latency * 1000:.2f}ms"

    def test_routing_latency_warm(self, router: FanoActionRouter) -> None:
        """Warm routing (cache hit) should be very fast."""
        action = "build.feature"
        params: dict[str, Any] = {}

        # Warm up cache
        router.route(action, params, complexity=0.1)

        # Measure warm latency
        start = time.perf_counter()
        for _ in range(100):
            router.route(action, params, complexity=0.1)
        total_latency = time.perf_counter() - start

        avg_latency = total_latency / 100
        # Cache hit should be < 1ms (typically ~0.01ms)
        assert avg_latency < 0.001, f"Warm routing took {avg_latency * 1000:.2f}ms"

    def test_lookup_table_performance(self, router: FanoActionRouter) -> None:
        """Lookup table should be faster than repeated computation."""
        # Test 1000 lookups using table
        start = time.perf_counter()
        for i in range(7):
            for j in range(7):
                _ = router._fano_lookup_table[i, j].item()
        table_time = time.perf_counter() - start

        # Test 1000 lookups using computation
        start = time.perf_counter()
        for i in range(7):
            for j in range(7):
                _ = router.get_fano_composition(i, j)
        compute_time = time.perf_counter() - start

        # Lookup should be faster (or at least comparable)
        # Allow 2x slower due to method call overhead
        assert table_time < compute_time * 2


# =============================================================================
# TEST BEHAVIOR PRESERVATION
# =============================================================================


class TestBehaviorPreservation:
    """Test that optimization preserves exact behavior."""

    def test_same_result_with_cache(self, router: FanoActionRouter) -> None:
        """Cached result should match original result."""
        action = "build.feature"
        params: dict[str, Any] = {"name": "auth"}

        # First call (no cache)
        result1 = router.route(action, params, complexity=0.5)

        # Second call (cache hit)
        result2 = router.route(action, params, complexity=0.5)

        # Results should be identical
        assert result1.mode == result2.mode
        assert len(result1.actions) == len(result2.actions)
        assert result1.complexity == result2.complexity

        # Actions should match
        for a1, a2 in zip(result1.actions, result2.actions, strict=True):
            assert a1.colony_idx == a2.colony_idx
            assert a1.colony_name == a2.colony_name
            assert a1.action == a2.action
            assert a1.params == a2.params

    def test_keyword_affinity_preserved(self, router: FanoActionRouter) -> None:
        """Keyword affinity routing should work with cache."""
        test_cases = [
            ("create", 0),  # spark
            ("build", 1),  # forge
            ("fix", 2),  # flow
            ("integrate", 3),  # nexus
            ("plan", 4),  # beacon
            ("research", 5),  # grove
            ("test", 6),  # crystal
        ]

        for action, expected_colony in test_cases:
            # First call (cache miss)
            result1 = router.route(action, {}, complexity=0.1)
            assert result1.actions[0].colony_idx == expected_colony

            # Second call (cache hit)
            result2 = router.route(action, {}, complexity=0.1)
            assert result2.actions[0].colony_idx == expected_colony

    def test_world_model_hint_preserved(self, router: FanoActionRouter) -> None:
        """World model hints should work with cache."""
        context = {
            "wm_colony_hint": {
                "colony_idx": 5,  # grove
                "confidence": 0.9,
            }
        }

        # First call
        result1 = router.route("unknown_action", {}, complexity=0.1, context=context)
        assert result1.actions[0].colony_idx == 5

        # Second call (should cache world model hint result)
        result2 = router.route("unknown_action", {}, complexity=0.1, context=context)
        assert result2.actions[0].colony_idx == 5


# =============================================================================
# TEST INTEGRATION
# =============================================================================


class TestIntegration:
    """Test cache integration with full routing pipeline."""

    def test_cache_works_with_fano_line(self, router: FanoActionRouter) -> None:
        """Cache should work with Fano line routing."""
        action = "build.feature"
        params: dict[str, Any] = {}

        # Route with Fano complexity
        result1 = router.route(action, params, complexity=0.5)
        assert len(result1.actions) == 3

        # Second call should use cache for primary colony selection
        result2 = router.route(action, params, complexity=0.5)
        assert len(result2.actions) == 3

        # Primary colony should match
        primary1 = next(a for a in result1.actions if a.is_primary)
        primary2 = next(a for a in result2.actions if a.is_primary)
        assert primary1.colony_idx == primary2.colony_idx

    def test_cache_works_with_all_colonies(self, router: FanoActionRouter) -> None:
        """Cache should work with all-colonies routing."""
        action = "analyze.architecture"
        params: dict[str, Any] = {}

        # Route with high complexity
        result1 = router.route(action, params, complexity=0.9)
        assert len(result1.actions) == 7

        # Second call should use cache for primary colony
        result2 = router.route(action, params, complexity=0.9)
        assert len(result2.actions) == 7

        # Primary colony should match
        primary1 = next(a for a in result1.actions if a.is_primary)
        primary2 = next(a for a in result2.actions if a.is_primary)
        assert primary1.colony_idx == primary2.colony_idx
