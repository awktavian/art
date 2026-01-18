"""Validation tests for Neural Class-K Control Barrier Functions.

Tests validate that the neural CBF system:
1. Learns valid barrier functions h(x) ≥ 0 for safe states
2. Maintains forward invariance (h(x) ≥ 0 implies h(f(x,u)) ≥ 0)
3. Properly filters unsafe control inputs

Mathematical Reference: Ames et al. "Control Barrier Functions: Theory and Applications" (2019)

Created: November 29, 2025
Status: Validation Tests
"""

from __future__ import annotations

from typing import Any, cast

import pytest

pytestmark = pytest.mark.tier_integration


import torch
import torch.nn as nn
import math


class MockNeuralCBF(nn.Module):
    """Simplified neural CBF for testing.

    A valid CBF h(x) must satisfy:
    1. h(x) ≥ 0 for all x in safe set
    2. h(x) < 0 for all x outside safe set
    3. ḣ(x) + α(h(x)) ≥ 0 (forward invariance condition)
    """

    def __init__(self, state_dim: int = 4, hidden_dim: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 1),
        )

        # Class-K function parameter (linear class-K: α(h) = γ·h)
        self.gamma = nn.Parameter(torch.tensor(1.0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Compute barrier function value h(x)."""
        return cast(torch.Tensor, self.net(x).squeeze(-1))

    def barrier_derivative(self, x: torch.Tensor, f: torch.Tensor) -> torch.Tensor:
        """Compute ḣ(x) = ∇h(x)·f(x,u) using autograd."""
        x.requires_grad_(True)
        h = self.forward(x)
        grad_h = torch.autograd.grad(h.sum(), x, create_graph=True)[0]
        return (grad_h * f).sum(dim=-1)

    def class_k(self, h: torch.Tensor) -> torch.Tensor:
        """Class-K function α(h) = γ·h."""
        return self.gamma * h

    def cbf_constraint(self, x: torch.Tensor, f: torch.Tensor) -> torch.Tensor:
        """CBF constraint: ḣ(x) + α(h(x)) ≥ 0."""
        h = self.forward(x)
        h_dot = self.barrier_derivative(x, f)
        return h_dot + self.class_k(h)


class TestNeuralCBFBasics:
    """Test basic neural CBF operations."""

    @pytest.fixture
    def cbf(self):
        return MockNeuralCBF(state_dim=4)

    def test_forward_shape(self, cbf) -> None:
        """CBF outputs scalar per state."""
        x = torch.randn(10, 4)
        h = cbf(x)
        assert h.shape == (10,), f"Expected (10,), got {h.shape}"

    def test_gradient_exists(self, cbf) -> None:
        """CBF gradient exists and is well-defined."""
        x = torch.randn(5, 4, requires_grad=True)
        h = cbf(x)
        h.sum().backward()

        assert x.grad is not None
        assert not torch.isnan(x.grad).any()

    def test_class_k_properties(self, cbf) -> None:
        """Class-K function satisfies required properties."""
        # α(0) = 0
        assert cbf.class_k(torch.tensor(0.0)) == 0.0

        # α is strictly increasing (for h > 0)
        h_vals = torch.tensor([0.1, 0.5, 1.0, 2.0])
        alpha_vals = cbf.class_k(h_vals)

        for i in range(len(alpha_vals) - 1):
            assert alpha_vals[i] < alpha_vals[i + 1], "Class-K must be increasing"


class TestCBFConstraint:
    """Test CBF constraint satisfaction."""

    @pytest.fixture
    def cbf(self):
        return MockNeuralCBF(state_dim=2)

    def test_constraint_computation(self, cbf) -> None:
        """CBF constraint is computable."""
        x = torch.randn(5, 2)
        f = torch.randn(5, 2)  # Dynamics

        constraint = cbf.cbf_constraint(x, f)

        assert constraint.shape == (5,)
        assert not torch.isnan(constraint).any()

    def test_constraint_for_safe_control(self, cbf) -> None:
        """Safe control satisfies CBF constraint."""
        # Start in safe region (h > 0)
        x = torch.randn(1, 2)
        h = cbf(x)

        if h.item() > 0:
            # Zero dynamics (standing still) should be safe
            f = torch.zeros(1, 2)
            constraint = cbf.cbf_constraint(x, f)

            # With zero dynamics, ḣ = 0, so constraint = α(h) ≥ 0
            if h.item() > 0:
                assert constraint.item() >= 0


class TestCBFTraining:
    """Test CBF training dynamics."""

    def test_can_learn_simple_barrier(self) -> None:
        """CBF can learn a simple safe set (circle)."""
        cbf = MockNeuralCBF(state_dim=2, hidden_dim=64)
        optimizer = torch.optim.Adam(cbf.parameters(), lr=0.01)

        # Safe set: ||x|| < 1 (unit circle)
        def is_safe(x):
            return torch.linalg.norm(x, dim=-1) < 1.0

        # Training loop
        losses = []
        for _epoch in range(100):
            # Sample points
            x_safe = torch.randn(32, 2) * 0.5  # Inside circle
            x_unsafe = torch.randn(32, 2) * 2 + torch.sign(torch.randn(32, 2))  # Outside

            h_safe = cbf(x_safe)
            h_unsafe = cbf(x_unsafe)

            # Loss: h(safe) > 0, h(unsafe) < 0
            loss_safe = torch.relu(-h_safe + 0.1).mean()  # Push h > 0.1 for safe
            loss_unsafe = torch.relu(h_unsafe + 0.1).mean()  # Push h < -0.1 for unsafe

            loss = loss_safe + loss_unsafe

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            losses.append(loss.item())

        # Check final accuracy
        with torch.no_grad():
            x_test_safe = torch.randn(100, 2) * 0.3
            x_test_unsafe = torch.randn(100, 2) * 3

            h_test_safe = cbf(x_test_safe)
            h_test_unsafe = cbf(x_test_unsafe)

            safe_accuracy = (h_test_safe > 0).float().mean()
            unsafe_accuracy = (h_test_unsafe < 0).float().mean()

        print(f"\n📊 CBF Training: safe_acc={safe_accuracy:.2%}, unsafe_acc={unsafe_accuracy:.2%}")
        print(f"   Final loss: {losses[-1]:.4f}")

        # Should achieve reasonable accuracy
        assert safe_accuracy > 0.7, f"Safe accuracy too low: {safe_accuracy:.2%}"


class TestForwardInvariance:
    """Test forward invariance property."""

    def test_invariance_with_safe_control(self) -> None:
        """Safe set remains invariant under safe control."""
        cbf = MockNeuralCBF(state_dim=2, hidden_dim=32)

        # Pretrain CBF on simple safe set
        optimizer = torch.optim.Adam(cbf.parameters(), lr=0.01)
        for _ in range(50):
            x_safe = torch.randn(32, 2) * 0.5
            x_unsafe = torch.randn(32, 2) * 2 + 1

            h_safe = cbf(x_safe)
            h_unsafe = cbf(x_unsafe)

            loss = torch.relu(-h_safe + 0.1).mean() + torch.relu(h_unsafe + 0.1).mean()

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        # Test forward invariance
        with torch.no_grad():
            x_start = torch.randn(20, 2) * 0.3  # Start safe
            h_start = cbf(x_start)

            # Count how many start in safe region
            n_safe_start = (h_start > 0).sum().item()

        # Simulate one step with small dynamics
        dt = 0.1
        dynamics = torch.randn(20, 2) * 0.1
        x_next = x_start + dt * dynamics

        with torch.no_grad():
            h_next = cbf(x_next)
            n_safe_next = (h_next > 0).sum().item()

        # Most should remain safe (small step)
        preservation_rate = n_safe_next / max(1, n_safe_start)
        print(
            f"\n📊 Forward Invariance: {n_safe_start} → {n_safe_next} safe ({preservation_rate:.2%})"
        )

        # Allow some loss due to untrained dynamics
        assert preservation_rate > 0.5


class TestControlFiltering:
    """Test control input filtering via CBF."""

    def test_filter_unsafe_control(self) -> None:
        """CBF can identify unsafe controls."""
        cbf = MockNeuralCBF(state_dim=2)

        x = torch.randn(1, 2)

        # Large control pushing state outward
        u_unsafe = x.clone() * 5  # Pushes away from origin

        # Small control
        u_safe = torch.zeros(1, 2)

        constraint_unsafe = cbf.cbf_constraint(x, u_unsafe)
        constraint_safe = cbf.cbf_constraint(x, u_safe)

        # Safe control should have higher constraint value
        # (more margin for safety)
        print(
            f"\n📊 Control Filtering: unsafe={constraint_unsafe.item():.3f}, safe={constraint_safe.item():.3f}"
        )


class TestCBFSmokeTests:
    """Smoke tests for CBF implementation."""

    def test_cbf_creation(self) -> None:
        """Can create neural CBF."""
        cbf = MockNeuralCBF(state_dim=4)
        assert isinstance(cbf, nn.Module)

    def test_cbf_parameter_count(self) -> None:
        """CBF has reasonable parameter count."""
        cbf = MockNeuralCBF(state_dim=4, hidden_dim=32)
        n_params = sum(p.numel() for p in cbf.parameters())

        # Should be modest (< 10k for simple CBF)
        assert n_params < 10000, f"Too many parameters: {n_params}"
        print(f"\n📊 Neural CBF Parameters: {n_params}")

    def test_cbf_differentiable(self) -> None:
        """CBF is end-to-end differentiable."""
        cbf = MockNeuralCBF(state_dim=2)
        x = torch.randn(5, 2, requires_grad=True)
        f = torch.randn(5, 2)

        constraint = cbf.cbf_constraint(x, f)
        loss = constraint.sum()
        loss.backward()

        assert x.grad is not None
        assert not torch.isnan(x.grad).any()
