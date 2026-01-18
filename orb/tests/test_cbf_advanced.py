"""Tests for Advanced CBF Components.

CREATED: December 27, 2025
PURPOSE: Verify spectral-normalized barriers, fault-tolerant CBF, and CBF-QP
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import torch

from kagami.core.safety.cbf_advanced import (
    CBFQP,
    ActuatorFaultConfig,
    FaultTolerantNCBF,
    SpectralNormalizedBarrier,
    create_cbf_qp,
    create_fault_tolerant_cbf,
    create_spectral_cbf,
)


class TestSpectralNormalizedBarrier:
    """Test spectral-normalized barrier function."""

    def test_initialization(self) -> None:
        """Test barrier initialization."""
        barrier = SpectralNormalizedBarrier(state_dim=16, hidden_dim=64, lipschitz_target=1.0)
        assert barrier.state_dim == 16
        assert barrier.use_neural_residual is True

    def test_forward_pass(self) -> None:
        """Test barrier forward pass."""
        barrier = SpectralNormalizedBarrier(state_dim=16, hidden_dim=64)
        state = torch.randn(4, 16)  # Batch of 4 states
        h = barrier(state)

        assert h.shape == (4,)
        assert h.dtype == torch.float32

    def test_lipschitz_estimation(self) -> None:
        """Test Lipschitz constant estimation."""
        barrier = SpectralNormalizedBarrier(state_dim=16, hidden_dim=64, lipschitz_target=1.0)
        lipschitz = barrier.estimate_lipschitz_constant()

        assert isinstance(lipschitz, float)
        assert lipschitz > 0
        # Should be reasonably bounded due to spectral norm
        assert lipschitz < 100.0

    def test_spectral_norm_enforcement(self) -> None:
        """Test that spectral normalization is applied to layers."""
        barrier = SpectralNormalizedBarrier(state_dim=16, hidden_dim=64)

        # Check that residual_net has spectral norm applied
        if barrier.use_neural_residual:
            has_spectral_norm = False
            for module in barrier.residual_net.modules():
                if hasattr(module, "weight_u"):  # spectral_norm adds _u buffer
                    has_spectral_norm = True
                    break

            assert has_spectral_norm, "Spectral normalization not applied to layers"

    def test_factory_function(self) -> None:
        """Test factory function for creating spectral CBF."""
        barrier = create_spectral_cbf(state_dim=8, hidden_dim=32, lipschitz_target=2.0)

        assert barrier.state_dim == 8
        assert barrier.lipschitz_target == 2.0


class TestFaultTolerantNCBF:
    """Test fault-tolerant neural CBF."""

    def test_initialization(self) -> None:
        """Test NCBF initialization."""
        config = ActuatorFaultConfig(state_dim=16, action_dim=4)
        ncbf = FaultTolerantNCBF(config)

        assert ncbf.config.action_dim == 4
        assert ncbf.fault_mask.shape == (4,)
        assert (ncbf.fault_mask == 1).all()  # All healthy initially

    def test_set_fault_mask(self) -> None:
        """Test setting actuator fault mask."""
        config = ActuatorFaultConfig(action_dim=4)
        ncbf = FaultTolerantNCBF(config)

        # Mark actuator 2 as faulty
        fault_mask = torch.tensor([1.0, 1.0, 0.0, 1.0])
        ncbf.set_fault_mask(fault_mask)

        assert (ncbf.fault_mask == fault_mask).all()
        assert ncbf.fault_mask[2] == 0.0

    def test_reset_faults(self) -> None:
        """Test resetting faults."""
        config = ActuatorFaultConfig(action_dim=4)
        ncbf = FaultTolerantNCBF(config)

        # Set fault
        fault_mask = torch.tensor([1.0, 0.0, 1.0, 1.0])
        ncbf.set_fault_mask(fault_mask)

        # Reset
        ncbf.reset_faults()
        assert (ncbf.fault_mask == 1).all()

    def test_fault_compensation(self) -> None:
        """Test fault compensation mechanism."""
        config = ActuatorFaultConfig(action_dim=4)
        ncbf = FaultTolerantNCBF(config)

        # Set fault mask: actuator 1 is faulty
        fault_mask = torch.tensor([1.0, 0.0, 1.0, 1.0])

        # Nominal action
        action = torch.tensor([[0.5, 0.5, 0.5, 0.5]])

        # Compensate
        compensated, info = ncbf.compensate_for_faults(action, fault_mask)

        # Faulty actuator should be zeroed
        assert compensated[0, 1] == 0.0

        # Healthy actuators should be scaled up
        assert compensated[0, 0] > action[0, 0]

        # Check metadata
        assert info["num_faulty"] == 1
        assert info["num_healthy"] == 3
        assert info["compensation_scale"] > 1.0

    def test_safe_action_with_faults(self) -> None:
        """Test safe action computation with faults."""
        config = ActuatorFaultConfig(state_dim=16, action_dim=4)
        ncbf = FaultTolerantNCBF(config)

        state = torch.randn(2, 16)
        action = torch.randn(2, 4)
        fault_mask = torch.tensor([1.0, 0.0, 1.0, 1.0])  # Actuator 1 faulty

        safe_action, info = ncbf.safe_action_with_faults(state, action, fault_mask)

        assert safe_action.shape == action.shape
        assert safe_action[:, 1].abs().max() == 0.0  # Faulty actuator is zero
        assert "h_value" in info
        assert "compensation_scale" in info

    def test_forward_pass(self) -> None:
        """Test forward pass."""
        config = ActuatorFaultConfig(state_dim=16, action_dim=4)
        ncbf = FaultTolerantNCBF(config)

        state = torch.randn(2, 16)
        action = torch.randn(2, 4)

        safe_action, info = ncbf(state, action)

        assert safe_action.shape == action.shape
        assert "h_value" in info

    def test_factory_function(self) -> None:
        """Test factory function."""
        ncbf = create_fault_tolerant_cbf(state_dim=8, action_dim=3, use_spectral_norm=True)

        assert ncbf.config.state_dim == 8
        assert ncbf.config.action_dim == 3
        assert ncbf.config.use_spectral_norm is True


class TestCBFQP:
    """Test CBF-QP implementation."""

    def test_initialization(self) -> None:
        """Test CBF-QP initialization."""
        # Create a simple barrier
        barrier = SpectralNormalizedBarrier(state_dim=16)

        cbf_qp = CBFQP(action_dim=2, cbf=barrier, alpha=1.0)

        assert cbf_qp.action_dim == 2
        assert cbf_qp.alpha.item() == 1.0

    def test_safe_action(self) -> None:
        """Test safe action computation via QP."""
        # Create barrier
        barrier = SpectralNormalizedBarrier(state_dim=16)

        # Create CBF-QP
        cbf_qp = CBFQP(action_dim=2, cbf=barrier, alpha=1.0)

        # Test data
        state = torch.randn(3, 16)
        desired_action = torch.randn(3, 2)

        # Compute safe action
        safe_action, info = cbf_qp.safe_action(state, desired_action)

        assert safe_action.shape == desired_action.shape
        assert "h_value" in info
        assert "constraint_satisfied" in info
        assert "action_modified" in info

    def test_forward_pass(self) -> None:
        """Test forward pass."""
        barrier = SpectralNormalizedBarrier(state_dim=16)
        cbf_qp = CBFQP(action_dim=2, cbf=barrier)

        state = torch.randn(3, 16)
        action = torch.randn(3, 2)

        safe_action, _info = cbf_qp(state, action)

        assert safe_action.shape == action.shape

    def test_factory_function(self) -> None:
        """Test factory function."""
        barrier = SpectralNormalizedBarrier(state_dim=16)
        cbf_qp = create_cbf_qp(action_dim=3, cbf=barrier, alpha=2.0)

        assert cbf_qp.action_dim == 3
        assert cbf_qp.alpha.item() == 2.0


class TestIntegration:
    """Integration tests combining components."""

    def test_spectral_cbf_with_qp(self) -> None:
        """Test spectral barrier with QP solver."""
        # Create spectral barrier
        barrier = create_spectral_cbf(state_dim=8, lipschitz_target=1.0)

        # Create QP controller
        cbf_qp = create_cbf_qp(action_dim=2, cbf=barrier, alpha=1.5)

        # Test
        state = torch.randn(4, 8)
        action = torch.randn(4, 2)

        safe_action, info = cbf_qp(state, action)

        assert safe_action.shape == action.shape
        assert info["constraint_satisfied"] or info["action_modified"]

    def test_fault_tolerant_with_spectral_norm(self) -> None:
        """Test fault-tolerant CBF with spectral normalization."""
        ncbf = create_fault_tolerant_cbf(state_dim=16, action_dim=4, use_spectral_norm=True)

        # Set faults
        fault_mask = torch.tensor([1.0, 0.0, 1.0, 0.0])
        ncbf.set_fault_mask(fault_mask)

        # Test
        state = torch.randn(2, 16)
        action = torch.randn(2, 4)

        safe_action, info = ncbf(state, action)

        # Verify faulty actuators are zeroed
        assert safe_action[:, 1].abs().max() == 0.0
        assert safe_action[:, 3].abs().max() == 0.0

        # Verify compensation occurred
        assert info["compensation_scale"] > 1.0

    def test_end_to_end_pipeline(self) -> None:
        """Test complete pipeline: spectral barrier + fault tolerance + QP."""
        # 1. Create spectral barrier with Lipschitz constraint
        barrier = create_spectral_cbf(state_dim=16, lipschitz_target=1.0)

        # 2. Create fault-tolerant CBF
        ncbf = create_fault_tolerant_cbf(state_dim=16, action_dim=3, use_spectral_norm=True)

        # 3. Create CBF-QP
        cbf_qp = create_cbf_qp(action_dim=3, cbf=barrier, alpha=1.0)

        # 4. Set some faults
        fault_mask = torch.tensor([1.0, 0.0, 1.0])
        ncbf.set_fault_mask(fault_mask)

        # 5. Run through pipeline
        state = torch.randn(2, 16)
        nominal_action = torch.randn(2, 3)

        # First: fault compensation
        fault_compensated, fault_info = ncbf(state, nominal_action)

        # Then: QP filtering
        safe_action, qp_info = cbf_qp(state, fault_compensated)

        # Verify
        assert safe_action.shape == nominal_action.shape
        assert safe_action[:, 1].abs().max() == 0.0  # Faulty actuator
        assert fault_info["num_faulty"] == 1
        assert "h_value" in qp_info


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
