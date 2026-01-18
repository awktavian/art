"""Tests for kagami.core.unified_agents.unified_organism module.

This tests the UnifiedOrganism class which manages the 7 colonies and was
involved in recent bug fixes around domain attribute access.

Created: December 13, 2025
Purpose: Fill critical test coverage gap in recently fixed code
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import torch
import asyncio

from kagami.core.unified_agents.unified_organism import (
    UnifiedOrganism,
    OrganismConfig,
    OrganismStats,
    OrganismStatus,
    HomeostasisState,
    create_organism,
    get_unified_organism,
    set_unified_organism,
)
from kagami.core.unified_agents.colony_constants import COLONY_NAMES, DomainType
from kagami.core.unified_agents.minimal_colony import MinimalColony


class TestOrganismConfig:
    """Test organism configuration."""

    def test_default_config(self) -> None:
        """Test default organism configuration."""
        config = OrganismConfig()

        # Should have sensible defaults
        assert config.min_workers_per_colony >= 1
        assert config.max_workers_per_colony >= config.min_workers_per_colony
        assert config.simple_threshold > 0
        assert config.complex_threshold > config.simple_threshold
        assert config.device in ["cpu", "cuda", "auto"]

    def test_custom_config(self) -> None:
        """Test custom organism configuration."""
        config = OrganismConfig(
            min_workers_per_colony=2,
            max_workers_per_colony=8,
            simple_threshold=0.2,
            complex_threshold=0.8,
            device="cpu",
        )

        assert config.min_workers_per_colony == 2
        assert config.max_workers_per_colony == 8
        assert config.simple_threshold == 0.2
        assert config.complex_threshold == 0.8
        assert config.device == "cpu"


class TestOrganismStats:
    """Test organism statistics tracking."""

    def test_stats_initialization(self) -> None:
        """Test stats initialize to zero."""
        stats = OrganismStats()

        assert stats.total_intents == 0
        assert stats.completed_intents == 0
        assert stats.failed_intents == 0
        assert stats.total_population == 0
        assert stats.active_colonies == 0
        assert stats.created_at > 0  # Should be set to current time

    def test_stats_update(self) -> None:
        """Test stats can be updated."""
        stats = OrganismStats()

        stats.total_intents = 10
        stats.completed_intents = 8
        stats.failed_intents = 2
        stats.total_population = 7

        assert stats.total_intents == 10
        assert stats.completed_intents == 8
        assert stats.failed_intents == 2
        assert stats.total_population == 7


class TestHomeostasisState:
    """Test homeostasis state tracking."""

    def test_homeostasis_initialization(self) -> None:
        """Test homeostasis initializes with reasonable defaults."""
        state = HomeostasisState()

        # Based on actual attributes from inspection
        assert hasattr(state, "overall_health")
        assert hasattr(state, "system_load")
        assert hasattr(state, "memory_pressure")
        assert hasattr(state, "queue_depth")
        assert hasattr(state, "colony_health")
        assert hasattr(state, "e8_coherence")

    def test_homeostasis_updates(self) -> None:
        """Test homeostasis can be updated."""
        state = HomeostasisState()

        # Test updating settable attributes (overall_health is computed property)
        state.system_load = 0.3
        state.memory_pressure = 0.1
        state.queue_depth = 5
        state.e8_coherence = 0.9
        state.colony_health = {"spark": 0.8, "forge": 0.9}

        assert state.system_load == 0.3
        assert state.memory_pressure == 0.1
        assert state.queue_depth == 5
        assert state.e8_coherence == 0.9
        assert state.colony_health == {"spark": 0.8, "forge": 0.9}
        # overall_health should be computed from colony_health
        assert state.overall_health == 0.85  # (0.8 + 0.9) / 2


class TestUnifiedOrganism:
    """Test UnifiedOrganism class functionality."""

    def test_organism_initialization(self) -> None:
        """Test organism initializes correctly."""
        config = OrganismConfig(min_workers_per_colony=1)
        organism = UnifiedOrganism(config)

        assert organism.config == config
        assert organism.status in [OrganismStatus.INITIALIZING, OrganismStatus.ACTIVE]
        assert isinstance(organism.stats, OrganismStats)
        assert isinstance(organism.homeostasis, HomeostasisState)

    def test_organism_colonies_property(self) -> None:
        """Test colonies property creates all 7 colonies."""
        organism = create_organism()
        colonies = organism.colonies

        # Should have all 7 colonies
        assert len(colonies) == 7
        assert set(colonies.keys()) == set(COLONY_NAMES)

        # All should be MinimalColony instances
        for colony in colonies.values():
            assert isinstance(colony, MinimalColony)

    def test_get_colony_method(self) -> None:
        """Test get_colony method (recently fixed)."""
        organism = create_organism()

        # Ensure colonies are initialized
        colonies_dict = organism.colonies
        assert len(colonies_dict) == 7

        # Should be able to get each colony
        for colony_name in COLONY_NAMES:
            colony = organism.get_colony(colony_name)
            assert colony is not None, f"Colony {colony_name} should not be None"
            assert isinstance(colony, MinimalColony)
            assert colony.colony_name == colony_name

            # Recently fixed: domain access
            assert hasattr(colony, "domain")
            assert colony.domain.value == colony_name  # FIX: Use .value for enum

    def test_get_colony_invalid_name(self) -> None:
        """Test get_colony with invalid name."""
        organism = create_organism()

        # Should return None for invalid names
        assert organism.get_colony("invalid") is None
        assert organism.get_colony("") is None
        assert organism.get_colony(None) is None

    def test_get_colony_by_index(self) -> None:
        """Test get_colony_by_index method."""
        organism = create_organism()

        # Should be able to get colonies by index
        for i in range(7):
            colony = organism.get_colony_by_index(i)
            assert colony is not None
            assert colony.colony_name == COLONY_NAMES[i]

        # Invalid indices should return None
        assert organism.get_colony_by_index(-1) is None
        assert organism.get_colony_by_index(7) is None

    def test_organism_router_and_reducer(self) -> None:
        """Test that organism has router and reducer."""
        organism = create_organism()

        # Should have internal router and reducer
        assert hasattr(organism, "_router")
        assert hasattr(organism, "_reducer")
        assert organism._router is not None
        assert organism._reducer is not None

    def test_organism_e8_roots(self) -> None:
        """Test organism has E8 roots for communication."""
        organism = create_organism()

        assert hasattr(organism, "_e8_roots")
        assert organism._e8_roots is not None
        assert organism._e8_roots.shape == (240, 8)


class TestOrganismSingleton:
    """Test organism singleton behavior."""

    def test_get_unified_organism_singleton(self) -> None:
        """Test that get_unified_organism returns singleton."""
        # Clear any existing organism
        set_unified_organism(None)

        # Multiple calls should return same instance
        org1 = get_unified_organism()
        org2 = get_unified_organism()

        assert org1 is org2
        assert isinstance(org1, UnifiedOrganism)

    def test_set_unified_organism(self) -> None:
        """Test setting global organism instance."""
        # Create custom organism
        custom_organism = create_organism()

        # Set it as global
        set_unified_organism(custom_organism)

        # Should be returned by get_unified_organism
        retrieved = get_unified_organism()
        assert retrieved is custom_organism

    def test_organism_reset(self) -> None:
        """Test resetting organism to None."""
        # Ensure organism exists
        get_unified_organism()

        # Reset to None
        set_unified_organism(None)

        # Next call should create new instance
        new_organism = get_unified_organism()
        assert new_organism is not None
        assert isinstance(new_organism, UnifiedOrganism)


class TestColonyIntegration:
    """Test colony integration within organism."""

    def test_all_colonies_have_correct_domains(self) -> None:
        """Test that all colonies have correct domain types."""
        organism = create_organism()

        # Ensure colonies are initialized
        colonies_dict = organism.colonies
        assert len(colonies_dict) == 7

        expected_domains = ["SPARK", "FORGE", "FLOW", "NEXUS", "BEACON", "GROVE", "CRYSTAL"]

        for i, colony_name in enumerate(COLONY_NAMES):
            colony = organism.get_colony(colony_name)
            assert colony is not None, f"Colony {colony_name} should not be None"
            assert colony.domain.name == expected_domains[i]

    def test_colony_stats_tracking(self) -> None:
        """Test that colony stats are tracked."""
        organism = create_organism()

        for colony_name in COLONY_NAMES:
            colony = organism.get_colony(colony_name)
            assert hasattr(colony, "stats")
            assert colony.stats is not None  # type: ignore[union-attr]

    def test_colony_worker_management(self) -> None:
        """Test basic worker management in colonies."""
        organism = create_organism()

        # Ensure colonies are initialized
        colonies_dict = organism.colonies
        assert len(colonies_dict) == 7

        spark = organism.get_colony("spark")
        assert spark is not None, "Spark colony should not be None"

        # Should have worker-related attributes
        assert hasattr(spark, "workers") or hasattr(
            spark, "_workers"
        ), "Colony should have worker attributes"

        # Should be able to access workers (even if empty initially)
        if hasattr(spark, "workers"):
            workers = spark.workers
            assert isinstance(workers, list)
        elif hasattr(spark, "_workers"):
            workers = spark._workers
            assert isinstance(workers, list)


class TestOrganismErrorHandling:
    """Test error handling and edge cases."""

    def test_organism_with_invalid_config(self) -> None:
        """Test organism handles invalid configuration gracefully."""
        # Test with edge case config
        config = OrganismConfig(min_workers_per_colony=0)  # Edge case

        # Should either work with defaults or raise clear error
        try:
            organism = UnifiedOrganism(config)
            # If it works, should have valid state
            assert organism.config is not None
        except (ValueError, AssertionError) as e:
            # If it fails, should be clear error
            assert "worker" in str(e).lower() or "config" in str(e).lower()

    def test_organism_cleanup(self) -> None:
        """Test organism cleanup doesn't break subsequent creation."""
        # Create and use organism
        org1 = create_organism()
        spark1 = org1.get_colony("spark")
        assert spark1 is not None

        # Reset and create new
        set_unified_organism(None)
        org2 = create_organism()
        spark2 = org2.get_colony("spark")

        assert spark2 is not None
        assert org2 is not org1  # Should be different instances


class TestOrganismAsyncBehavior:
    """Test organism async behavior if applicable."""

    def test_organism_with_async_context(self) -> None:
        """Test organism works in async context."""

        async def async_test():
            organism = create_organism()
            colony = organism.get_colony("spark")
            return colony is not None

        # Should work in async context
        result = asyncio.run(async_test())
        assert result is True

    @pytest.mark.asyncio
    async def test_organism_concurrent_access(self) -> None:
        """Test organism handles concurrent access."""
        organism = create_organism()

        # Concurrent colony access should work
        async def get_colony_async(name: Any) -> str:
            return organism.get_colony(name)

        tasks = [get_colony_async(name) for name in COLONY_NAMES]
        results = await asyncio.gather(*tasks)

        # All should succeed
        for result in results:
            assert result is not None
            assert isinstance(result, MinimalColony)


if __name__ == "__main__":
    pytest.main([__file__])
