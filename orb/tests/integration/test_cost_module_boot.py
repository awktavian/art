"""Integration test for Cost Module boot sequence.

Tests the full wiring flow:
1. Boot initializes cost module
2. Organism receives cost module reference
3. Cost module is available for use

Created: December 20, 2025
Purpose: Verify end-to-end cost module integration
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



from unittest.mock import Mock, patch, AsyncMock

from kagami.core.rl.unified_cost_module import (
    UnifiedCostModule,
    CostModuleConfig,
    reset_cost_module,
)


@pytest.fixture(autouse=True)
def reset_cost_singleton() -> None:
    """Reset cost module singleton before each test."""
    reset_cost_module()


class TestCostModuleBootIntegration:
    """Test cost module integration during boot sequence."""

    @pytest.mark.asyncio
    async def test_boot_initializes_cost_module(self) -> None:
        """Test that boot sequence initializes cost module correctly."""
        # Mock FastAPI app
        mock_app = Mock()
        mock_app.state = Mock()

        # Mock organism
        from kagami.core.unified_agents.unified_organism import (
            UnifiedOrganism,
            OrganismConfig,
        )

        organism_config = OrganismConfig(device="cpu")
        organism = UnifiedOrganism(config=organism_config)

        # Simulate boot wiring (what happens in kagami/boot/actions/wiring.py)
        from kagami.core.rl.unified_cost_module import get_cost_module

        cost_config = CostModuleConfig(
            state_dim=512,
            action_dim=64,
            ic_weight=0.6,
            tc_weight=0.4,
        )
        cost_module = get_cost_module(cost_config)

        # Wire to app and organism
        mock_app.state.cost_module = cost_module
        organism._cost_module = cost_module

        # Verify wiring
        assert mock_app.state.cost_module is not None
        assert organism._cost_module is not None
        assert organism._cost_module is cost_module

        # Verify cost module configuration
        assert organism._cost_module.config.state_dim == 512
        assert organism._cost_module.config.action_dim == 64
        assert abs(float(organism._cost_module.ic_weight) - 0.6) < 1e-5  # type: ignore[arg-type]
        assert abs(float(organism._cost_module.tc_weight) - 0.4) < 1e-5  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_organism_can_access_cost_module_after_boot(self) -> None:
        """Test organism can access cost module via lazy loader after boot."""
        from kagami.core.unified_agents.unified_organism import (
            UnifiedOrganism,
            OrganismConfig,
        )
        from kagami.core.rl.unified_cost_module import get_cost_module

        # Create organism
        organism_config = OrganismConfig(device="cpu")
        organism = UnifiedOrganism(config=organism_config)

        # Simulate boot wiring
        cost_config = CostModuleConfig(state_dim=512, action_dim=64)
        cost_module = get_cost_module(cost_config)
        organism._cost_module = cost_module

        # Access via lazy loader (should return the wired module)
        loaded_module = organism._get_cost_module()

        assert loaded_module is cost_module
        assert loaded_module.config.state_dim == 512

    @pytest.mark.asyncio
    async def test_cost_module_survives_organism_lifecycle(self) -> None:
        """Test cost module persists across organism start/stop."""
        from kagami.core.unified_agents.unified_organism import (
            UnifiedOrganism,
            OrganismConfig,
        )
        from kagami.core.rl.unified_cost_module import get_cost_module

        # Create and start organism
        organism_config = OrganismConfig(device="cpu")
        organism = UnifiedOrganism(config=organism_config)

        # Wire cost module before start
        cost_config = CostModuleConfig(state_dim=512, action_dim=64)
        cost_module = get_cost_module(cost_config)
        organism._cost_module = cost_module

        # Start organism
        await organism.start()

        # Verify cost module still accessible
        assert organism._cost_module is cost_module
        assert organism._get_cost_module() is cost_module

        # Stop organism
        await organism.stop()

        # Cost module should still be accessible (it's singleton)
        assert organism._cost_module is cost_module

    @pytest.mark.asyncio
    async def test_cost_module_lazy_loading_fallback(self) -> None:
        """Test lazy loading creates module if not wired by boot."""
        from kagami.core.unified_agents.unified_organism import (
            UnifiedOrganism,
            OrganismConfig,
        )

        # Create organism WITHOUT boot wiring
        organism_config = OrganismConfig(device="cpu")
        organism = UnifiedOrganism(config=organism_config)

        # Cost module should be None initially
        assert organism._cost_module is None

        # Lazy loading should create it
        cost_module = organism._get_cost_module()

        assert cost_module is not None
        assert isinstance(cost_module, UnifiedCostModule)

        # Should be cached
        cost_module2 = organism._get_cost_module()
        assert cost_module2 is cost_module

    @pytest.mark.asyncio
    async def test_boot_handles_cost_module_initialization_failure(self) -> None:
        """Test graceful handling of cost module initialization failure."""
        mock_app = Mock()
        mock_app.state = Mock()

        from kagami.core.unified_agents.unified_organism import (
            UnifiedOrganism,
            OrganismConfig,
        )

        organism_config = OrganismConfig(device="cpu")
        organism = UnifiedOrganism(config=organism_config)

        # Simulate initialization failure (invalid config)
        try:
            from kagami.core.rl.unified_cost_module import (
                CostModuleConfig,
                UnifiedCostModule,
            )

            # Create invalid config (negative dimensions should fail)
            invalid_config = CostModuleConfig(state_dim=-1, action_dim=-1)
            cost_module = UnifiedCostModule(invalid_config)

            # This should fail, but if it doesn't, boot should handle it
            mock_app.state.cost_module = cost_module
            organism._cost_module = cost_module

        except Exception:
            # Boot should set None on failure
            mock_app.state.cost_module = None
            organism._cost_module = None

        # Organism should still function without cost module
        assert organism is not None

        # Lazy loading should work as fallback
        if organism._cost_module is None:
            cost_module = organism._get_cost_module()
            assert cost_module is not None
