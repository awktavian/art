"""Tests for Cost Module integration into UnifiedOrganism.

This tests:
1. Cost module initialization during boot
2. Lazy loading in organism
3. Cost module availability for action selection

Created: December 20, 2025
Purpose: Verify cost module is wired correctly (TDD)
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import torch

from kagami.core.rl.unified_cost_module import (
    UnifiedCostModule,
    CostModuleConfig,
    get_cost_module,
    reset_cost_module,
)
from kagami.core.unified_agents.unified_organism import (
    UnifiedOrganism,
    OrganismConfig,
)


@pytest.fixture(autouse=True)
def reset_singleton() -> None:
    """Reset cost module singleton before each test."""
    reset_cost_module()


class TestCostModuleInitialization:
    """Test cost module initialization."""

    def test_cost_module_creation(self) -> None:
        """Test cost module can be created with config."""
        config = CostModuleConfig(
            state_dim=512,
            action_dim=64,
            ic_weight=0.6,
            tc_weight=0.4,
        )
        cost_module = UnifiedCostModule(config)

        assert cost_module is not None
        assert cost_module.config.state_dim == 512
        assert cost_module.config.action_dim == 64
        assert abs(float(cost_module.ic_weight) - 0.6) < 1e-5  # type: ignore[arg-type]
        assert abs(float(cost_module.tc_weight) - 0.4) < 1e-5  # type: ignore[arg-type]

    def test_cost_module_singleton(self) -> None:
        """Test cost module singleton pattern."""
        config = CostModuleConfig(state_dim=256)
        module1 = get_cost_module(config)
        module2 = get_cost_module()

        # Should return same instance
        assert module1 is module2
        assert module1.config.state_dim == 256


class TestOrganismCostModuleIntegration:
    """Test cost module integration with UnifiedOrganism."""

    @pytest.mark.asyncio
    async def test_organism_has_cost_module_property(self) -> None:
        """Test organism has _cost_module attribute after initialization."""
        config = OrganismConfig(device="cpu")
        organism = UnifiedOrganism(config=config)

        # Should have _cost_module attribute (initially None)
        assert hasattr(organism, "_cost_module")
        # Initially None until wired by boot or lazy-loaded
        assert organism._cost_module is None

    @pytest.mark.asyncio
    async def test_organism_lazy_load_cost_module(self) -> None:
        """Test organism can lazy load cost module."""
        config = OrganismConfig(device="cpu")
        organism = UnifiedOrganism(config=config)

        # Should have lazy load method
        assert hasattr(organism, "_get_cost_module")

        # Lazy load should create module
        cost_module = organism._get_cost_module()
        assert cost_module is not None
        assert isinstance(cost_module, UnifiedCostModule)

        # Should cache the module
        cost_module2 = organism._get_cost_module()
        assert cost_module is cost_module2

    @pytest.mark.asyncio
    async def test_organism_cost_module_can_be_set(self) -> None:
        """Test organism can have cost module set externally (by boot)."""
        config = OrganismConfig(device="cpu")
        organism = UnifiedOrganism(config=config)

        # Create cost module with custom config
        cost_config = CostModuleConfig(
            state_dim=512,
            action_dim=64,
            ic_weight=0.7,  # Safety-critical bias
            tc_weight=0.3,
        )
        cost_module = UnifiedCostModule(cost_config)

        # Set on organism (simulates boot wiring)
        organism._cost_module = cost_module

        # Should be available via lazy loader
        loaded_module = organism._get_cost_module()
        assert loaded_module is cost_module
        assert abs(float(loaded_module.ic_weight) - 0.7) < 1e-5


class TestCostModuleUsage:
    """Test cost module usage patterns."""

    def test_cost_module_forward(self) -> None:
        """Test cost module forward pass."""
        config = CostModuleConfig(state_dim=512, action_dim=64)
        cost_module = UnifiedCostModule(config)

        # Create dummy state and action
        batch_size = 4
        state = torch.randn(batch_size, 512)
        action = torch.randn(batch_size, 64)

        # Forward pass should work
        result = cost_module(state, action)

        assert "total" in result
        assert "ic_total" in result
        assert "tc_value" in result
        assert result["total"].shape == (batch_size, 1)

    def test_cost_module_with_cbf(self) -> None:
        """Test cost module with CBF values."""
        config = CostModuleConfig(state_dim=512, action_dim=64)
        cost_module = UnifiedCostModule(config)

        batch_size = 4
        state = torch.randn(batch_size, 512)
        action = torch.randn(batch_size, 64)
        cbf_value = torch.tensor([[0.5], [0.1], [-0.1], [1.0]])  # One unsafe

        result = cost_module(state, action, cbf_value)

        # Should have safety cost
        assert "ic_safety" in result
        # Unsafe state (h < 0) should have infinite cost
        assert torch.isinf(result["ic_safety"][2, 0])

    def test_cost_module_configure(self) -> None:
        """Test cost module reconfiguration."""
        config = CostModuleConfig(ic_weight=0.6, tc_weight=0.4)
        cost_module = UnifiedCostModule(config)

        # Initial weights
        assert abs(float(cost_module.ic_weight) - 0.6) < 1e-5  # type: ignore[arg-type]
        assert abs(float(cost_module.tc_weight) - 0.4) < 1e-5  # type: ignore[arg-type]

        # Reconfigure (simulates Configurator)
        cost_module.configure(ic_weight=0.8, tc_weight=0.2)

        assert abs(float(cost_module.ic_weight) - 0.8) < 1e-5  # type: ignore[arg-type]
        assert abs(float(cost_module.tc_weight) - 0.2) < 1e-5  # type: ignore[arg-type]


class TestCostModuleGradients:
    """Test gradient flow through cost module."""

    def test_cost_gradient_wrt_action(self) -> None:
        """Test cost gradient w.r.t. action (for gradient-based optimization)."""
        config = CostModuleConfig(state_dim=512, action_dim=64)
        cost_module = UnifiedCostModule(config)

        state = torch.randn(2, 512)
        action = torch.randn(2, 64)

        # Get gradient
        grad = cost_module.get_cost_gradient(state, action)

        assert grad.shape == (2, 64)
        assert not grad.requires_grad  # Should be detached

    def test_trainable_critic_has_gradients(self) -> None:
        """Test trainable critic parameters have gradients enabled."""
        config = CostModuleConfig(state_dim=512, action_dim=64)
        cost_module = UnifiedCostModule(config)

        # TC parameters should be trainable
        tc_params = list(cost_module.trainable_critic.value_network.parameters())
        assert len(tc_params) > 0
        assert all(p.requires_grad for p in tc_params)

    def test_intrinsic_cost_frozen(self) -> None:
        """Test intrinsic cost parameters are frozen."""
        config = CostModuleConfig(state_dim=512, action_dim=64)
        cost_module = UnifiedCostModule(config)

        # IC parameters should be frozen
        ic_params = list(cost_module.intrinsic_cost.parameters())
        assert len(ic_params) > 0
        assert all(not p.requires_grad for p in ic_params)
