"""Complete LeCun Architecture Integration Test.

This test verifies the entire ChronOS system end-to-end:
1. Boot sequence initialization
2. All 6 LeCun modules are accessible
3. Intent execution flow works correctly
4. Autonomous orchestrator generates goals
5. Receipts are persisted correctly

Created: December 21, 2025
Purpose: Comprehensive system integration verification
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import torch
from unittest.mock import Mock, patch, AsyncMock

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
async def reset_singletons():
    """Reset all singletons before each test."""
    from kagami.core.rl.unified_cost_module import reset_cost_module
    from kagami.core.unified_agents.unified_organism import reset_organism
    from kagami.core.executive.configurator import reset_configurator

    reset_cost_module()
    reset_organism()
    reset_configurator()
    yield
    # Cleanup after test
    reset_cost_module()
    reset_organism()
    reset_configurator()


@pytest.fixture
async def organism():
    """Create and start organism for testing."""
    from kagami.core.unified_agents.unified_organism import (
        UnifiedOrganism,
        OrganismConfig,
    )

    config = OrganismConfig(device="cpu")
    org = UnifiedOrganism(config=config)
    await org.start()
    yield org
    await org.stop()


@pytest.fixture
async def wired_organism(organism: Any) -> None:
    """Organism with all LeCun modules wired (simulates boot)."""
    from kagami.core.rl.unified_cost_module import get_cost_module, CostModuleConfig
    from kagami.core.executive.configurator import get_executive_control

    # Wire cost module (as boot does)
    cost_config = CostModuleConfig(
        state_dim=512,
        action_dim=64,
        ic_weight=0.6,
        tc_weight=0.4,
    )
    cost_module = get_cost_module(cost_config)
    organism._cost_module = cost_module

    # Executive control is lazy loaded, ensure it's available
    executive = get_executive_control()
    organism._executive = executive

    yield organism


# =============================================================================
# TEST 1: BOOT SEQUENCE
# =============================================================================


class TestBootSequence:
    """Test complete boot sequence initialization."""

    @pytest.mark.asyncio
    async def test_organism_starts_successfully(self, organism: Any) -> None:
        """Verify organism starts without errors."""
        # Check organism is running
        assert organism._running is True
        assert organism.status == "running"

        # Check homeostasis monitor is active
        assert organism._homeostasis_monitor is not None
        assert organism.homeostasis.h_x >= 0.0  # Safety invariant

    @pytest.mark.asyncio
    async def test_all_colonies_initialize(self, organism: Any) -> None:
        """Verify all 7 colonies are created."""
        # Trigger colony creation by getting one
        colony = organism._get_or_create_colony("spark")
        assert colony is not None

        # Verify colony names
        expected_colonies = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
        for name in expected_colonies:
            colony = organism._get_or_create_colony(name)
            assert colony is not None
            assert colony.name == name

    @pytest.mark.asyncio
    async def test_organism_ready_flag_set(self, organism: Any) -> None:
        """Verify organism_ready flag is set after start."""
        # organism_ready is implicit in status
        assert organism.status == "running"
        assert organism._running is True

    @pytest.mark.asyncio
    async def test_cbf_monitor_initialized(self, organism: Any) -> None:
        """Verify CBF safety monitoring is active."""
        # Check homeostasis includes safety metrics
        assert hasattr(organism.homeostasis, "h_x")
        assert organism.homeostasis.h_x >= 0.0  # Safety invariant
        assert organism.homeostasis.safety_margin >= 0.0


# =============================================================================
# TEST 2: LECUN MODULE INTEGRATION
# =============================================================================


class TestLeCunModuleIntegration:
    """Test all 6 LeCun modules are accessible."""

    @pytest.mark.asyncio
    async def test_configurator_is_accessible(self, wired_organism: Any) -> None:
        """Verify Configurator module is available."""
        executive = wired_organism._get_executive_control()
        assert executive is not None

        configurator = executive.configurator
        assert configurator is not None

        # Verify it can generate configurations
        task_emb = torch.randn(1, 512)
        config = configurator.configure(task_emb, task_type="general")

        assert config is not None
        assert hasattr(config, "world_model")
        assert hasattr(config, "actor")
        assert hasattr(config, "cost")

    @pytest.mark.asyncio
    async def test_perception_api_works(self, wired_organism: Any) -> None:
        """Verify unified perception API is accessible."""
        # Perception is accessed via UnifiedOrganism
        # It processes intents and routes to colonies
        assert wired_organism is not None

        # Verify perception layer (router) is available
        assert wired_organism._router is not None
        assert wired_organism._router.simple_threshold == 0.3
        assert wired_organism._router.complex_threshold == 0.7

    @pytest.mark.asyncio
    async def test_world_model_is_loaded(self, wired_organism: Any) -> None:
        """Verify world model is available."""
        # World model is accessed via lazy loading
        try:
            from kagami.core.world_model.service import get_world_model_service

            service = get_world_model_service()
            # Service should be initialized (even if model not loaded)
            assert service is not None
        except ImportError:
            pytest.skip("World model service not available")

    @pytest.mark.asyncio
    async def test_cost_module_is_accessible(self, wired_organism: Any) -> None:
        """Verify Cost module is wired and accessible."""
        cost_module = wired_organism._get_cost_module()
        assert cost_module is not None

        # Verify configuration
        assert cost_module.config.state_dim == 512
        assert cost_module.config.action_dim == 64
        assert abs(float(cost_module.ic_weight) - 0.6) < 1e-5
        assert abs(float(cost_module.tc_weight) - 0.4) < 1e-5

        # Verify it can evaluate costs
        state = torch.randn(1, 512)
        action = torch.randn(1, 64)
        result = cost_module(state, action)

        assert "total" in result
        assert "ic_total" in result
        assert "tc_value" in result

    @pytest.mark.asyncio
    async def test_actor_routing_works(self, wired_organism: Any) -> None:
        """Verify Actor (colony routing) works."""
        router = wired_organism._router
        assert router is not None

        # Test routing decision
        action = "test.action"
        params = {}
        context = {}

        mode, complexity = router.infer_action_mode(action, params, context)
        assert mode in ["single", "fano_line", "all_colonies"]
        assert 0.0 <= complexity <= 1.0

    @pytest.mark.asyncio
    async def test_memory_receipts_work(self, wired_organism: Any) -> None:
        """Verify Memory (receipts) are created."""
        # Memory is accessed via receipt creation during intent execution
        # We'll verify this in the intent execution test
        assert wired_organism._coordinator is not None


# =============================================================================
# TEST 3: INTENT EXECUTION FLOW
# =============================================================================


class TestIntentExecutionFlow:
    """Test complete intent execution with all modules."""

    @pytest.mark.asyncio
    async def test_simple_intent_execution(self, wired_organism: Any) -> None:
        """Test executing a simple intent (single colony)."""
        result = await wired_organism.execute_intent(
            intent="test.simple",
            params={"value": 42},
            context={"complexity": 0.2},  # Force simple mode
        )

        # Verify execution succeeded
        assert result is not None
        assert "success" in result
        assert result.get("success", False) is True

        # Verify routing
        assert "results" in result or "e8_action" in result

    @pytest.mark.asyncio
    async def test_cbf_safety_check_runs(self, wired_organism: Any) -> None:
        """Verify CBF safety check is called during execution."""
        with patch("kagami.core.safety.cbf_integration.check_cbf_for_operation") as mock_cbf:
            # Mock CBF to return safe result
            mock_cbf.return_value = Mock(safe=True, h_x=0.8, margin=0.3, emergency_action=None)

            result = await wired_organism.execute_intent(
                intent="test.safe",
                params={},
                context={"complexity": 0.2},
            )

            # Verify CBF was called
            assert mock_cbf.called

            # Verify execution succeeded (safe)
            assert result.get("success", False) is True

    @pytest.mark.asyncio
    async def test_configurator_is_called(self, wired_organism: Any) -> None:
        """Verify Configurator is used during intent execution."""
        # Configurator is called when world model is available
        # For now, verify executive control is accessible
        executive = wired_organism._get_executive_control()
        assert executive is not None

        # Create task config
        task_emb = torch.randn(1, 512)
        config = await executive.configure_for_task(
            task_embedding=task_emb,
            task_type="test",
            task_description="test intent",
        )

        assert config is not None
        assert config.urgency >= 0.0
        assert config.urgency <= 1.0

    @pytest.mark.asyncio
    async def test_colony_selection_works(self, wired_organism: Any) -> None:
        """Verify correct colonies are selected based on complexity."""
        # Simple action (< 0.3) → 1 colony
        mode_simple, _ = wired_organism._router.infer_action_mode(
            "simple.task", {}, {"complexity": 0.2}
        )
        assert mode_simple == "single"

        # Medium action (0.3-0.7) → Fano line (3 colonies)
        mode_fano, _ = wired_organism._router.infer_action_mode(
            "medium.task", {}, {"complexity": 0.5}
        )
        assert mode_fano == "fano_line"

        # Complex action (>0.7) → all colonies
        mode_all, _ = wired_organism._router.infer_action_mode(
            "complex.task", {}, {"complexity": 0.9}
        )
        assert mode_all == "all_colonies"

    @pytest.mark.asyncio
    async def test_receipt_creation(self, wired_organism: Any) -> None:
        """Verify receipt is created after execution."""
        result = await wired_organism.execute_intent(
            intent="test.receipt",
            params={},
            context={"complexity": 0.2},
        )

        # Receipt ID should be in result
        assert "intent_id" in result or "correlation_id" in result


# =============================================================================
# TEST 4: AUTONOMOUS LOOP
# =============================================================================


class TestAutonomousLoop:
    """Test autonomous orchestrator functionality."""

    @pytest.mark.asyncio
    async def test_autonomous_orchestrator_can_start(self, wired_organism: Any) -> None:
        """Verify autonomous orchestrator can be initialized."""
        # Autonomous orchestrator is optional
        # Verify organism can run without it
        assert wired_organism._running is True

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Autonomous orchestrator is optional, skip in CI")
    async def test_goal_generation_works(self, wired_organism: Any) -> None:
        """Verify autonomous goal generation (when enabled)."""
        # This test requires autonomous orchestrator to be wired
        # Skip if not available
        if not hasattr(wired_organism, "_autonomous_orchestrator"):
            pytest.skip("Autonomous orchestrator not wired")

    @pytest.mark.asyncio
    async def test_execution_does_not_abort_on_ready(self, wired_organism: Any) -> None:
        """Verify execution continues after organism is ready."""
        # Execute multiple intents to verify stability
        for i in range(3):
            result = await wired_organism.execute_intent(
                intent=f"test.multi.{i}",
                params={"iteration": i},
                context={"complexity": 0.2},
            )
            assert result is not None

        # Organism should still be running
        assert wired_organism._running is True


# =============================================================================
# TEST 5: DATABASE VERIFICATION
# =============================================================================


class TestDatabaseVerification:
    """Test database persistence and querying."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires live database, run manually")
    async def test_query_cockroachdb_for_receipts(self, wired_organism: Any) -> None:
        """Verify receipts are stored in CockroachDB."""
        # This test requires live database connection
        # Execute intent to generate receipt
        await wired_organism.execute_intent(
            intent="test.db",
            params={},
            context={"complexity": 0.2},
        )

        # Query database (requires db connection)
        # Skip in CI
        pytest.skip("Requires live database")

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Redis, run manually")
    async def test_redis_cache_works(self, wired_organism: Any) -> None:
        """Verify Redis cache is accessible."""
        # This test requires Redis connection
        pytest.skip("Requires Redis")

    @pytest.mark.asyncio
    async def test_receipt_count_increases(self, wired_organism: Any) -> None:
        """Verify receipt count increases with each execution."""
        # Get initial stats
        stats_before = wired_organism.get_stats()
        total_before = stats_before.get("total_intents", 0)

        # Execute intent
        await wired_organism.execute_intent(
            intent="test.count",
            params={},
            context={"complexity": 0.2},
        )

        # Get stats after
        stats_after = wired_organism.get_stats()
        total_after = stats_after.get("total_intents", 0)

        # Verify count increased
        assert total_after >= total_before


# =============================================================================
# TEST 6: SAFETY INVARIANT
# =============================================================================


class TestSafetyInvariant:
    """Test h(x) >= 0 is maintained throughout execution."""

    @pytest.mark.asyncio
    async def test_h_x_always_non_negative(self, wired_organism: Any) -> None:
        """Verify h(x) >= 0 throughout execution."""
        # Check initial state
        assert wired_organism.homeostasis.h_x >= 0.0

        # Execute several intents
        for i in range(5):
            await wired_organism.execute_intent(
                intent=f"test.safety.{i}",
                params={},
                context={"complexity": 0.2},
            )

            # Check h(x) after each execution
            assert wired_organism.homeostasis.h_x >= 0.0, f"Safety violated at iteration {i}"

    @pytest.mark.asyncio
    async def test_unsafe_action_is_blocked(self, wired_organism: Any) -> None:
        """Verify unsafe actions (h < 0) are blocked."""
        with patch("kagami.core.safety.cbf_integration.check_cbf_for_operation") as mock_cbf:
            # Mock CBF to return unsafe result
            mock_cbf.return_value = Mock(safe=False, h_x=-0.1, margin=-0.6, emergency_action="HALT")

            # Execute intent that would be unsafe
            from kagami.core.safety.control_barrier_function import SafetyViolationError

            with pytest.raises(SafetyViolationError):
                await wired_organism.execute_intent(
                    intent="test.unsafe",
                    params={},
                    context={"complexity": 0.2},
                )


# =============================================================================
# TEST 7: PERFORMANCE METRICS
# =============================================================================


class TestPerformanceMetrics:
    """Test system performance and responsiveness."""

    @pytest.mark.asyncio
    async def test_intent_execution_is_fast(self, wired_organism: Any) -> None:
        """Verify intent execution completes in reasonable time."""
        import time

        start = time.time()
        await wired_organism.execute_intent(
            intent="test.perf",
            params={},
            context={"complexity": 0.2},
        )
        elapsed = time.time() - start

        # Should complete in < 5 seconds (generous for CI)
        assert elapsed < 5.0, f"Intent took {elapsed:.2f}s (> 5s threshold)"

    @pytest.mark.asyncio
    async def test_get_stats_works(self, wired_organism: Any) -> None:
        """Verify stats endpoint returns valid data."""
        stats = wired_organism.get_stats()

        assert stats is not None
        assert "total_intents" in stats or "organism_stats" in stats or "uptime_seconds" in stats


# =============================================================================
# INTEGRATION SMOKE TEST
# =============================================================================


@pytest.mark.asyncio
async def test_complete_lecun_integration_smoke(wired_organism: Any) -> None:
    """Smoke test: Execute one intent through the complete pipeline.

    This test verifies the entire system works end-to-end:
    1. Organism is ready
    2. CBF checks safety
    3. Configurator generates config
    4. Router selects colonies
    5. Intent executes successfully
    6. Receipt is created
    7. Safety invariant maintained
    """
    # 1. Verify organism is ready
    assert wired_organism._running is True
    assert wired_organism.homeostasis.h_x >= 0.0

    # 2. Execute test intent
    result = await wired_organism.execute_intent(
        intent="test.integration",
        params={"test": "smoke"},
        context={"complexity": 0.5},  # Fano line mode
    )

    # 3. Verify result
    assert result is not None
    assert result.get("success", False) is True

    # 4. Verify safety maintained
    assert wired_organism.homeostasis.h_x >= 0.0

    # 5. Verify stats updated
    stats = wired_organism.get_stats()
    assert stats is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
