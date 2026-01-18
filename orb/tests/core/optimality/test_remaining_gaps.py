"""Tests for Remaining Gaps Module.

Tests:
- FullStructuralEquationModel (counterfactual reasoning)
- TruePhiEstimator (IIT integration)
- EmpowermentEnhanced (multi-step empowerment)
- WorldModelOptimalityBridge (full integration)

Created: December 4, 2025
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import torch
import torch.nn as nn


class TestFullStructuralEquationModel:
    """Tests for full SEM counterfactual reasoning."""

    def test_init(self):
        """Test initialization."""
        from kagami.core.optimality.remaining_gaps import (
            FullStructuralEquationModel,
            StructuralEquation,
        )

        # Simple 3-variable SEM: X -> Y -> Z
        equations = [
            StructuralEquation("X", []),  # Exogenous
            StructuralEquation("Y", ["X"], {"X": 0.5}, intercept=1.0),
            StructuralEquation("Z", ["Y"], {"Y": 0.8}),
        ]

        sem = FullStructuralEquationModel(
            variables=["X", "Y", "Z"],
            equations=equations,
        )

        assert sem is not None
        assert len(sem.variables) == 3

    def test_forward_model(self):
        """Test forward model computation."""
        from kagami.core.optimality.remaining_gaps import (
            FullStructuralEquationModel,
            StructuralEquation,
        )

        equations = [
            StructuralEquation("X", []),
            StructuralEquation("Y", ["X"], {"X": 2.0}),
        ]

        sem = FullStructuralEquationModel(
            variables=["X", "Y"],
            equations=equations,
        )

        # Exogenous values
        exogenous = {
            "X": torch.tensor(1.0),
            "Y": torch.tensor(0.0),  # No noise
        }

        values = sem.forward_model(exogenous)

        # X = 1.0 (exogenous)
        # Y = 2.0 * X = 2.0
        assert values["X"].item() == 1.0
        assert abs(values["Y"].item() - 2.0) < 0.01

    def test_abduction(self):
        """Test abduction step."""
        from kagami.core.optimality.remaining_gaps import (
            FullStructuralEquationModel,
            StructuralEquation,
        )

        equations = [
            StructuralEquation("X", []),
            StructuralEquation("Y", ["X"], {"X": 2.0}),
        ]

        sem = FullStructuralEquationModel(
            variables=["X", "Y"],
            equations=equations,
        )

        # Observed data: X=1, Y=3 (should have noise of 1.0)
        observations = {
            "X": torch.tensor(1.0),
            "Y": torch.tensor(3.0),
        }

        exogenous = sem.abduction(observations)

        assert exogenous["X"].item() == 1.0
        # Y = 2*X + U_Y = 2*1 + 1 = 3, so U_Y = 1
        assert abs(exogenous["Y"].item() - 1.0) < 0.01

    def test_counterfactual(self):
        """Test full counterfactual computation."""
        from kagami.core.optimality.remaining_gaps import (
            FullStructuralEquationModel,
            StructuralEquation,
        )

        equations = [
            StructuralEquation("X", []),
            StructuralEquation("Y", ["X"], {"X": 2.0}),
        ]

        sem = FullStructuralEquationModel(
            variables=["X", "Y"],
            equations=equations,
        )

        # Factual: X=1, Y=3 (with noise)
        factual = {
            "X": torch.tensor(1.0),
            "Y": torch.tensor(3.0),
        }

        # Counterfactual: What if X had been 2?
        cf = sem.counterfactual(
            factual=factual,
            intervention={"X": torch.tensor(2.0)},
            query_vars=["Y"],
        )

        # Y = 2*2 + 1 (same noise) = 5
        assert abs(cf["Y"].item() - 5.0) < 0.01

    def test_causal_effect(self):
        """Test ATE estimation."""
        from kagami.core.optimality.remaining_gaps import (
            FullStructuralEquationModel,
            StructuralEquation,
        )

        equations = [
            StructuralEquation("X", []),
            StructuralEquation("Y", ["X"], {"X": 1.5}),
        ]

        sem = FullStructuralEquationModel(
            variables=["X", "Y"],
            equations=equations,
        )

        # Data
        data = {
            "X": torch.tensor([0.0, 0.5, 1.0]),
            "Y": torch.tensor([0.0, 0.75, 1.5]),  # Perfect fit
        }

        result = sem.estimate_causal_effect(
            treatment="X",
            outcome="Y",
            data=data,
            treatment_val=1.0,
            control_val=0.0,
        )

        # ATE should be 1.5 (coefficient of X)
        assert abs(result["ate"] - 1.5) < 0.1


class TestOctonionFanoCoherence:
    """Tests for Octonion Fano Coherence estimation (NOT IIT Phi)."""

    def test_init(self):
        """Test initialization."""
        from kagami.core.optimality.remaining_gaps import OctonionFanoCoherence

        coherence_est = OctonionFanoCoherence(use_true_octonion=True)
        assert coherence_est is not None
        assert coherence_est.fano_lines.shape == (7, 3)

    def test_forward_shape(self):
        """Test output shape."""
        from kagami.core.optimality.remaining_gaps import OctonionFanoCoherence

        coherence_est = OctonionFanoCoherence(use_true_octonion=True)

        # 7 colonies with 8D states
        colony_states = torch.randn(4, 7, 8)

        coherence = coherence_est(colony_states)

        assert coherence.shape == (4,)

    def test_coherence_bounded(self):
        """Test coherence is bounded."""
        from kagami.core.optimality.remaining_gaps import OctonionFanoCoherence

        coherence_est = OctonionFanoCoherence(use_true_octonion=True)

        colony_states = torch.randn(8, 7, 8)
        coherence = coherence_est(colony_states)

        # Should be bounded [0, 10] per implementation
        assert coherence.min() >= 0
        assert coherence.max() <= 10

    def test_proxy_mode(self):
        """Test proxy mode (without true octonion)."""
        from kagami.core.optimality.remaining_gaps import OctonionFanoCoherence

        coherence_est = OctonionFanoCoherence(use_true_octonion=False)

        colony_states = torch.randn(4, 7, 8)
        coherence = coherence_est(colony_states)

        assert coherence.shape == (4,)

    def test_gradient_flow(self):
        """Test gradients flow through."""
        from kagami.core.optimality.remaining_gaps import OctonionFanoCoherence

        coherence_est = OctonionFanoCoherence(use_true_octonion=True)

        colony_states = torch.randn(2, 7, 8, requires_grad=True)
        coherence = coherence_est(colony_states)

        loss = coherence.sum()
        loss.backward()

        assert colony_states.grad is not None


class TestEmpowermentEnhanced:
    """Tests for enhanced empowerment."""

    def test_init(self):
        """Test initialization."""
        from kagami.core.optimality.remaining_gaps import EmpowermentEnhanced

        emp = EmpowermentEnhanced(
            state_dim=64,
            action_dim=8,
            horizon=5,
        )

        assert emp is not None
        assert emp.horizon == 5

    def test_forward_shape(self):
        """Test output shape."""
        from kagami.core.optimality.remaining_gaps import EmpowermentEnhanced

        emp = EmpowermentEnhanced(
            state_dim=32,
            action_dim=4,
            horizon=3,
            num_action_samples=8,
        )

        state = torch.randn(4, 32)
        empowerment, info = emp(state)

        assert empowerment.shape == (4,)
        assert "pos_scores_mean" in info

    def test_empowerment_bounded(self):
        """Test empowerment is bounded."""
        from kagami.core.optimality.remaining_gaps import EmpowermentEnhanced

        emp = EmpowermentEnhanced(
            state_dim=32,
            action_dim=4,
            horizon=3,
            num_action_samples=8,
        )

        state = torch.randn(8, 32)
        empowerment, _ = emp(state)

        # Bounded by log(num_samples)
        import math

        assert empowerment.min() >= 0
        assert empowerment.max() <= math.log(8) + 1e-3

    def test_sample_action_sequences(self):
        """Test action sampling."""
        from kagami.core.optimality.remaining_gaps import EmpowermentEnhanced

        emp = EmpowermentEnhanced(
            state_dim=32,
            action_dim=4,
            horizon=5,
            num_action_samples=16,
        )

        actions = emp.sample_action_sequences(batch_size=8, device=torch.device("cpu"))

        assert actions.shape == (8, 16, 5, 4)

    def test_gradient_flow(self):
        """Test gradients flow through."""
        from kagami.core.optimality.remaining_gaps import EmpowermentEnhanced

        emp = EmpowermentEnhanced(
            state_dim=32,
            action_dim=4,
            horizon=3,
        )

        state = torch.randn(2, 32, requires_grad=True)
        empowerment, _ = emp(state)

        loss = empowerment.sum()
        loss.backward()

        assert state.grad is not None


class TestWorldModelOptimalityBridge:
    """Tests for world model integration."""

    def test_init(self):
        """Test initialization."""
        from kagami.core.optimality.remaining_gaps import WorldModelOptimalityBridge

        # Create dummy model
        model = nn.Linear(64, 64)

        bridge = WorldModelOptimalityBridge(model)
        assert bridge is not None
        assert bridge.world_model is model

    def test_wire_fano_coherence(self):
        """Test Fano coherence wiring."""
        from kagami.core.optimality.remaining_gaps import WorldModelOptimalityBridge

        model = nn.Linear(64, 64)
        bridge = WorldModelOptimalityBridge(model)

        result = bridge.wire_fano_coherence()
        assert result is True
        assert bridge.fano_coherence_estimator is not None

    def test_wire_empowerment(self):
        """Test empowerment wiring."""
        from kagami.core.optimality.remaining_gaps import WorldModelOptimalityBridge

        model = nn.Linear(64, 64)
        bridge = WorldModelOptimalityBridge(model)

        result = bridge.wire_empowerment()
        assert result is True
        assert bridge.empowerment is not None

    def test_compute_optimal_fano_coherence(self):
        """Test optimal Fano coherence computation."""
        from kagami.core.optimality.remaining_gaps import WorldModelOptimalityBridge

        model = nn.Linear(64, 64)
        bridge = WorldModelOptimalityBridge(model)
        bridge.wire_fano_coherence()

        colony_states = torch.randn(4, 7, 8)
        coherence = bridge.compute_optimal_fano_coherence(colony_states)

        assert coherence.shape == (4,)

    def test_get_status(self):
        """Test status retrieval."""
        from kagami.core.optimality.remaining_gaps import WorldModelOptimalityBridge

        model = nn.Linear(64, 64)
        bridge = WorldModelOptimalityBridge(model)

        status = bridge.get_status()
        assert "improvements_wired" in status
        assert "fano_coherence_estimator" in status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
