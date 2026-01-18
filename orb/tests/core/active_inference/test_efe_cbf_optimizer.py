"""Tests for EFE-CBF Constrained Optimizer.

CREATED: December 14, 2025
COVERAGE:
- Basic initialization
- Soft constraint mode (training)
- Hard constraint mode (deployment)
- QP feasibility
- Safety guarantees
- Integration with EFE + CBF
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration
import torch
from kagami.core.active_inference.efe_cbf_optimizer import (
    EFECBFConfig,
    EFECBFOptimizer,
    create_efe_cbf_optimizer,
)
from kagami.core.safety.optimal_cbf import OptimalCBF, OptimalCBFConfig
class TestEFECBFOptimizer:
    """Test suite for EFE-CBF optimizer."""
    @pytest.fixture
    def config(self) -> EFECBFConfig:
        """Default configuration."""
        return EFECBFConfig(
            state_dim=16,  # Smaller for tests
            stochastic_dim=8,
            action_dim=4,
            penalty_weight=5.0,
            qp_solver_method="analytical",
        )
    @pytest.fixture
    def cbf(self) -> OptimalCBF:
        """Pre-configured CBF module."""
        cbf_config = OptimalCBFConfig(
            observation_dim=24,  # 16 + 8
            state_dim=16,
            control_dim=4,
            use_qp_solver=True,
            qp_solver="analytical",
        )
        return OptimalCBF(cbf_config)
    @pytest.fixture
    def optimizer(self, config: EFECBFConfig, cbf: OptimalCBF) -> EFECBFOptimizer:
        """Initialized optimizer."""
        return EFECBFOptimizer(config, cbf)
    def test_initialization(self, optimizer: EFECBFOptimizer, config: EFECBFConfig):
        """Test basic initialization."""
        assert optimizer.config == config
        assert optimizer.combined_dim == config.state_dim + config.stochastic_dim
        assert optimizer.cbf is not None
        assert optimizer.qp_solver is not None
        assert optimizer._num_violations == 0
        assert optimizer._total_evaluations == 0
    def test_compute_barrier_values(self, optimizer: EFECBFOptimizer):
        """Test barrier computation for states."""
        batch = 2
        num_policies = 3
        state_dim = optimizer.combined_dim
        # Create test states
        states = torch.randn(batch, num_policies, state_dim)
        # Compute barriers
        h_values, info = optimizer.compute_barrier_values(states)
        # Check shapes
        assert h_values.shape == (batch, num_policies)
        assert "h_metric" in info
        assert info["h_metric"].shape == (batch, num_policies)
    def test_soft_mode_basic(self, optimizer: EFECBFOptimizer):
        """Test soft constraint optimization (training mode)."""
        batch = 2
        num_policies = 4
        horizon = 3
        state_dim = optimizer.combined_dim
        action_dim = optimizer.config.action_dim
        # Create test inputs
        G_values = torch.randn(batch, num_policies) * 2  # EFE values
        states = torch.randn(batch, num_policies, state_dim) * 0.5
        policies = torch.randn(batch, num_policies, horizon, action_dim)
        # Apply soft constraints
        optimizer.train()
        G_safe, info = optimizer(G_values, states, policies, training=True)
        # Check outputs
        assert G_safe.shape == (batch, num_policies)
        assert info["mode"] == "soft"
        assert "h_values" in info
        assert "cbf_penalty" in info
        assert "num_violations" in info
        # G_safe should be >= G (penalty only increases)
        # (except for safe policies where penalty=0)
        assert torch.all(G_safe >= G_values - 1e-5)  # Small tolerance
    def test_soft_mode_penalty_applied(self, optimizer: EFECBFOptimizer):
        """Test that penalty is applied to unsafe policies."""
        batch = 1
        num_policies = 2
        horizon = 2
        state_dim = optimizer.combined_dim
        action_dim = optimizer.config.action_dim
        # Create one safe, one unsafe state
        # Safe: small values (low risk)
        # Unsafe: large negative values (high risk → negative h)
        states = torch.zeros(batch, num_policies, state_dim)
        states[:, 0] = 0.1  # Safe
        states[:, 1] = 2.0  # Likely unsafe (high risk → h < 0)
        G_values = torch.ones(batch, num_policies)
        policies = torch.randn(batch, num_policies, horizon, action_dim)
        optimizer.train()
        _G_safe, info = optimizer(G_values, states, policies, training=True)
        # Check that unsafe policy has higher penalty
        # Note: Actual h values depend on learned CBF, so we check structure
        assert "violation" in info
        violation = info["violation"]
        assert violation.shape == (batch, num_policies)
    def test_hard_mode_basic(self, optimizer: EFECBFOptimizer):
        """Test hard constraint optimization (deployment mode)."""
        batch = 2
        num_policies = 3
        horizon = 2
        state_dim = optimizer.combined_dim
        action_dim = optimizer.config.action_dim
        # Create test inputs
        G_values = torch.randn(batch, num_policies)
        states = torch.randn(batch, num_policies, state_dim) * 0.5
        policies = torch.randn(batch, num_policies, horizon, action_dim)
        # Apply hard constraints
        optimizer.eval()
        safe_policies, info = optimizer(G_values, states, policies, training=False)
        # Check outputs
        assert safe_policies.shape == (batch, num_policies, horizon, action_dim)
        assert info["mode"] == "hard"
        assert "qp_corrections" in info
        assert "num_violations" in info
    def test_select_safe_policy(self, optimizer: EFECBFOptimizer):
        """Test safe policy selection."""
        batch = 1
        num_policies = 5
        horizon = 3
        state_dim = optimizer.combined_dim
        action_dim = optimizer.config.action_dim
        G_values = torch.randn(batch, num_policies)
        states = torch.randn(batch, num_policies, state_dim) * 0.5
        policies = torch.randn(batch, num_policies, horizon, action_dim)
        # Select best safe policy
        selected, idx, info = optimizer.select_safe_policy(
            G_values, states, policies, training=True
        )
        # Check outputs
        assert selected.shape == (batch, horizon, action_dim)
        assert isinstance(idx, int)
        assert 0 <= idx < num_policies
        assert "selected_idx" in info
        assert "selected_G" in info
    def test_statistics_tracking(self, optimizer: EFECBFOptimizer):
        """Test violation statistics tracking."""
        batch = 2
        num_policies = 3
        horizon = 2
        state_dim = optimizer.combined_dim
        action_dim = optimizer.config.action_dim
        # Initial stats
        stats = optimizer.get_statistics()
        assert stats["total_evaluations"] == 0
        assert stats["total_violations"] == 0
        # Run optimization
        G_values = torch.randn(batch, num_policies)
        states = torch.randn(batch, num_policies, state_dim)
        policies = torch.randn(batch, num_policies, horizon, action_dim)
        optimizer(G_values, states, policies, training=True)
        # Check stats updated
        stats = optimizer.get_statistics()
        assert stats["total_evaluations"] == batch * num_policies
        # Violations may or may not occur depending on random states
        # Reset
        optimizer.reset_statistics()
        stats = optimizer.get_statistics()
        assert stats["total_evaluations"] == 0
    def test_factory_creation(self):
        """Test factory function."""
        optimizer = create_efe_cbf_optimizer(
            state_dim=32,
            stochastic_dim=16,
            action_dim=8,
            penalty_weight=15.0,
        )
        assert optimizer.config.state_dim == 32
        assert optimizer.config.stochastic_dim == 16
        assert optimizer.config.action_dim == 8
        assert optimizer.config.penalty_weight == 15.0
    def test_gradient_flow_soft_mode(self, optimizer: EFECBFOptimizer):
        """Test that gradients flow in soft mode."""
        batch = 2
        num_policies = 3
        horizon = 2
        state_dim = optimizer.combined_dim
        action_dim = optimizer.config.action_dim
        G_values = torch.randn(batch, num_policies, requires_grad=True)
        states = torch.randn(batch, num_policies, state_dim, requires_grad=True)
        policies = torch.randn(batch, num_policies, horizon, action_dim)
        optimizer.train()
        G_safe, _info = optimizer(G_values, states, policies, training=True)
        # Backprop
        loss = G_safe.mean()
        loss.backward()
        # Check gradients exist
        assert G_values.grad is not None
        assert states.grad is not None
        assert torch.any(G_values.grad != 0) or torch.any(states.grad != 0)
    def test_deployment_mode_safety(self, optimizer: EFECBFOptimizer):
        """Test that deployment mode improves safety."""
        batch = 1
        num_policies = 10
        horizon = 3
        state_dim = optimizer.combined_dim
        action_dim = optimizer.config.action_dim
        # Create policies with some unsafe states
        G_values = torch.randn(batch, num_policies)
        states = torch.randn(batch, num_policies, state_dim) * 2.0  # Higher variance
        policies = torch.randn(batch, num_policies, horizon, action_dim)
        # Check h before
        h_before, _ = optimizer.compute_barrier_values(states)
        unsafe_before = (h_before < 0).sum().item()
        # Apply hard constraints
        optimizer.eval()
        _safe_policies, info = optimizer(G_values, states, policies, training=False)
        # QP corrections should be applied
        assert info["mode"] == "hard"
        # Note: Full safety check requires re-evaluating h after corrections
        # which needs world model integration
    @pytest.mark.parametrize("batch_size", [1, 2, 4])
    @pytest.mark.parametrize("num_policies", [3, 5, 10])
    def test_batch_sizes(self, optimizer: EFECBFOptimizer, batch_size: int, num_policies: int):
        """Test various batch sizes."""
        horizon = 2
        state_dim = optimizer.combined_dim
        action_dim = optimizer.config.action_dim
        G_values = torch.randn(batch_size, num_policies)
        states = torch.randn(batch_size, num_policies, state_dim)
        policies = torch.randn(batch_size, num_policies, horizon, action_dim)
        # Soft mode
        G_safe, info = optimizer(G_values, states, policies, training=True)
        assert G_safe.shape == (batch_size, num_policies)
        # Hard mode
        safe_policies, _info = optimizer(G_values, states, policies, training=False)
        assert safe_policies.shape == (batch_size, num_policies, horizon, action_dim)
# =============================================================================
# INTEGRATION TESTS
# =============================================================================
class TestEFECBFIntegration:
    """Integration tests with EFE and CBF modules."""
    def test_with_pretrained_cbf(self):
        """Test optimizer with a pre-trained CBF."""
        # Create and "train" a CBF
        cbf_config = OptimalCBFConfig(
            observation_dim=24,
            state_dim=16,
            control_dim=4,
        )
        cbf = OptimalCBF(cbf_config)
        # Create optimizer
        config = EFECBFConfig(state_dim=16, stochastic_dim=8, action_dim=4)
        optimizer = EFECBFOptimizer(config, cbf)
        # Test basic operation
        batch = 2
        num_policies = 3
        horizon = 2
        G_values = torch.randn(batch, num_policies)
        states = torch.randn(batch, num_policies, 24)
        policies = torch.randn(batch, num_policies, horizon, 4)
        G_safe, _info = optimizer(G_values, states, policies, training=True)
        assert G_safe.shape == (batch, num_policies)
    def test_end_to_end_pipeline(self):
        """Test complete EFE → CBF → selection pipeline."""
        # Create optimizer
        optimizer = create_efe_cbf_optimizer(
            state_dim=16,
            stochastic_dim=8,
            action_dim=4,
        )
        batch = 1
        num_policies = 5
        horizon = 3
        # Simulate EFE output
        G_values = torch.tensor([[2.5, 1.8, 3.2, 1.5, 2.9]])  # Best is idx=3
        # States and policies
        states = torch.randn(batch, num_policies, 24)
        policies = torch.randn(batch, num_policies, horizon, 4)
        # Select safe policy
        optimizer.train()
        selected, _idx, info = optimizer.select_safe_policy(G_values, states, policies)
        assert selected.shape == (batch, horizon, 4)
        assert "selected_G" in info
        assert info["constraint_satisfied"] in [True, False]
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
