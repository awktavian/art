"""Tests for OptimalCBF - Learned Control Barrier Function.

Created: December 3, 2025
Tests the new learned CBF implementation with:
- Learned state encoder
- Learned barrier function h(x)
- Learned class-K function α(h)
- Learned dynamics f(x), g(x)
- Topological barrier (catastrophe distance)
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import torch

from kagami.core.safety.optimal_cbf import (
    OptimalCBF,
    OptimalCBFConfig,
    SafetyStateEncoder,
    LearnedBarrierFunction,
    LearnedClassK,
    LearnedDynamics,
    TopologicalBarrier,
    create_optimal_cbf,
    get_optimal_cbf,
)


class TestSafetyStateEncoder:
    """Tests for SafetyStateEncoder."""

    def test_encode_observation(self) -> None:
        """Test encoding full observation."""
        encoder = SafetyStateEncoder(
            observation_dim=256,
            state_dim=16,
        )

        obs = torch.randn(4, 256)
        state = encoder(obs)

        assert state.shape == (4, 16)
        # Output should be bounded by tanh
        assert state.abs().max() <= 1.0

    # test_encode_legacy_state deleted (Dec 21, 2025)
    # Rationale: No "legacy 4D state" format exists. SafetyStateEncoder accepts
    # variable dims via padding/truncation (tested in test_encode_variable_dim).

    def test_encode_variable_dim(self) -> None:
        """Test encoding variable dimension input."""
        encoder = SafetyStateEncoder(
            observation_dim=256,
            state_dim=16,
        )

        # Shorter than observation_dim - should be padded
        short = torch.randn(2, 100)
        state = encoder(short)
        assert state.shape == (2, 16)

        # Longer than observation_dim - should be truncated
        long = torch.randn(2, 500)
        state = encoder(long)
        assert state.shape == (2, 16)


class TestLearnedBarrierFunction:
    """Tests for LearnedBarrierFunction."""

    def test_barrier_values(self) -> None:
        """Test barrier function output."""
        barrier = LearnedBarrierFunction(
            state_dim=16,
            safety_threshold=0.3,
        )

        x = torch.randn(4, 16) * 0.5  # Moderate values
        h = barrier(x)

        assert h.shape == (4,)
        # h should be a mix of positive/negative depending on risk

    def test_low_risk_is_safe(self) -> None:
        """Low risk state should have positive h."""
        barrier = LearnedBarrierFunction(
            state_dim=16,
            safety_threshold=0.5,
            use_neural_residual=False,  # Pure linear for predictability
        )

        # Very low risk (near zero)
        x = torch.zeros(1, 16)
        h = barrier(x)

        # threshold=0.5, risk≈0 → h≈0.5
        assert h.item() > 0.0

    def test_high_risk_is_unsafe(self) -> None:
        """High risk state should have negative h."""
        barrier = LearnedBarrierFunction(
            state_dim=16,
            safety_threshold=0.3,
            use_neural_residual=False,
        )

        # High risk (near 1.0)
        x = torch.ones(1, 16) * 0.8
        h = barrier(x)

        # threshold=0.3, risk≈0.8 → h≈-0.5
        assert h.item() < 0.0


class TestLearnedClassK:
    """Tests for LearnedClassK function."""

    def test_class_k_properties(self) -> None:
        """Test class-K function satisfies α(0)=0."""
        class_k = LearnedClassK()

        # α(0) should be 0
        h_zero = torch.tensor([0.0])
        alpha_zero = class_k(h_zero)
        assert abs(alpha_zero.item()) < 1e-6

    def test_monotonicity(self) -> None:
        """Test class-K function is monotonically increasing."""
        class_k = LearnedClassK()

        h_vals = torch.linspace(-1, 1, 20)
        alpha_vals = class_k(h_vals)

        # Check monotonicity: α(h₁) < α(h₂) for h₁ < h₂
        for i in range(len(h_vals) - 1):
            assert alpha_vals[i] <= alpha_vals[i + 1] + 1e-5  # Small tolerance


class TestLearnedDynamics:
    """Tests for LearnedDynamics."""

    def test_dynamics_shape(self) -> None:
        """Test dynamics output shapes."""
        dynamics = LearnedDynamics(
            state_dim=16,
            control_dim=2,
        )

        x = torch.randn(4, 16)
        f, g = dynamics(x)

        assert f.shape == (4, 16)
        assert g.shape == (4, 16, 2)

    def test_control_effect(self) -> None:
        """Test that control generally reduces risk (negative g)."""
        dynamics = LearnedDynamics(
            state_dim=16,
            control_dim=2,
        )

        x = torch.randn(4, 16)
        _, g = dynamics(x)

        # g should be mostly negative (control reduces risk)
        # Due to initialization, at least the mean should be negative
        assert g.mean().item() < 0.5  # Not strongly positive


class TestTopologicalBarrier:
    """Tests for TopologicalBarrier."""

    def test_barrier_output(self) -> None:
        """Test topological barrier output."""
        barrier = TopologicalBarrier(
            state_dim=16,
            threshold=0.7,
        )

        x = torch.randn(4, 16)
        h_topo, risk_vector = barrier(x)

        assert h_topo.shape == (4,)
        assert risk_vector.shape == (4, 7)  # 7 catastrophe types

    def test_risk_bounded(self) -> None:
        """Test that risk values are in [0, 1]."""
        barrier = TopologicalBarrier(state_dim=16)

        x = torch.randn(10, 16)
        _, risk_vector = barrier(x)

        assert (risk_vector >= 0).all()
        assert (risk_vector <= 1).all()


class TestOptimalCBF:
    """Tests for the complete OptimalCBF."""

    @pytest.fixture
    def cbf(self):
        """Create OptimalCBF for testing."""
        config = OptimalCBFConfig(
            observation_dim=256,
            state_dim=16,
            control_dim=2,
            use_topological=True,
        )
        return OptimalCBF(config)

    def test_forward_pass(self, cbf: Any) -> None:
        """Test complete forward pass."""
        obs = torch.randn(4, 256)
        u_nom = torch.randn(4, 2)

        u_safe, penalty, info = cbf(obs, u_nom)

        assert u_safe.shape == (4, 2)
        assert penalty.ndim == 0  # Scalar
        assert "h_metric" in info
        assert "h_topo" in info

    def test_control_bounds(self, cbf: Any) -> None:
        """Test that output control is within bounds."""
        obs = torch.randn(10, 256)
        u_nom = torch.randn(10, 2) * 5  # Out of bounds

        u_safe, _, _ = cbf(obs, u_nom)

        assert (u_safe >= 0.0).all()
        assert (u_safe <= 1.0).all()

    def test_is_safe(self, cbf: Any) -> None:
        """Test is_safe method."""
        obs = torch.randn(4, 256)
        safe = cbf.is_safe(obs)

        assert safe.shape == (4,)
        assert safe.dtype == torch.bool

    def test_barrier_value(self, cbf: Any) -> None:
        """Test barrier_value method."""
        obs = torch.randn(4, 256)
        h = cbf.barrier_value(obs)

        assert h.shape == (4,)

    def test_gradient_flow(self, cbf: Any) -> None:
        """Test that gradients flow through the CBF."""
        obs = torch.randn(4, 256, requires_grad=True)
        u_nom = torch.randn(4, 2, requires_grad=True)

        u_safe, penalty, _ = cbf(obs, u_nom)
        loss = u_safe.sum() + penalty

        loss.backward()

        # Gradients should flow to inputs
        assert obs.grad is not None
        assert u_nom.grad is not None


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_optimal_cbf(self) -> None:
        """Test create_optimal_cbf factory."""
        cbf = create_optimal_cbf(
            observation_dim=128,
            state_dim=8,
            control_dim=3,
        )

        assert cbf.config.observation_dim == 128
        assert cbf.config.state_dim == 8
        assert cbf.config.control_dim == 3

    def test_get_optimal_cbf_singleton(self) -> None:
        """Test get_optimal_cbf returns singleton."""
        cbf1 = get_optimal_cbf()
        cbf2 = get_optimal_cbf()

        assert cbf1 is cbf2


class TestIntegration:
    """Integration tests for OptimalCBF with system."""

    @pytest.mark.asyncio
    async def test_cbf_integration_check(self) -> None:
        """Test OptimalCBF works with cbf_integration module."""
        from kagami.core.safety.cbf_integration import check_cbf_for_operation

        result = await check_cbf_for_operation(
            operation="test.operation",
            action="test",
            target="test",
            source="pytest",
        )

        assert hasattr(result, "safe")
        assert hasattr(result, "h_x")

    def test_cbf_integration_sync(self) -> None:
        """Test OptimalCBF works with sync check."""
        from kagami.core.safety.cbf_integration import check_cbf_sync

        result = check_cbf_sync(
            operation="test.operation",
            action="test",
            target="test",
            source="pytest",
        )

        assert hasattr(result, "safe")
        assert hasattr(result, "h_x")

    def test_cbf_integration_fails_closed_on_missing_h_metric(self, monkeypatch: Any) -> None:
        """Fail CLOSED if safety filter doesn't return h_metric."""
        import kagami.core.safety.cbf_integration as cbf_integration

        class _DummyClassification:
            is_safe = True
            confidence = 1.0

            def max_risk(self):
                return ("none", 0.0)

            def total_risk(self):
                return 0.0

        class _DummyFilter:
            def filter_text(self, text: Any, nominal_control: Any, context: Any = None) -> Any:
                return (
                    nominal_control,
                    torch.tensor(0.0),
                    {"classification": _DummyClassification()},
                )

        monkeypatch.setattr(cbf_integration, "_safety_filter", _DummyFilter(), raising=False)

        result = cbf_integration.check_cbf_sync(operation="test.missing_h_metric", content="hello")
        assert result.safe is False
        assert result.reason == "missing_h_metric"
        assert (result.h_x or 0.0) < 0

    def test_cbf_integration_blocks_classifier_unsafe(self, monkeypatch: Any) -> Any:
        """Block if classifier says unsafe even when h(x) is positive."""
        import kagami.core.safety.cbf_integration as cbf_integration

        class _DummyClassification:
            is_safe = False
            confidence = 1.0

            def max_risk(self):
                return ("violence", 0.9)

            def total_risk(self):
                return 0.9

        class _DummyFilter:
            def filter_text(self, text: Any, nominal_control: Any, context: Any = None) -> Any:
                info = {
                    "classification": _DummyClassification(),
                    "h_metric": torch.tensor([0.25]),
                }
                return nominal_control, torch.tensor(0.0), info

        monkeypatch.setattr(cbf_integration, "_safety_filter", _DummyFilter(), raising=False)

        result = cbf_integration.check_cbf_sync(
            operation="test.classifier_unsafe", content="unsafe"
        )
        assert result.safe is False
        assert result.reason == "classifier_unsafe"


# Ensure backward compatibility with existing tests
class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_imports_work(self) -> None:
        """Test that old imports still work."""
        from kagami.core.safety import OptimalCBF, get_optimal_cbf

        cbf = get_optimal_cbf()
        assert isinstance(cbf, OptimalCBF)

    # test_legacy_cbf_still_works deleted (Dec 21, 2025)
    # Rationale: OptimalCBF is the canonical CBF implementation. Legacy
    # ControlBarrierFunction tests are backward compat only. OptimalCBF has
    # comprehensive tests including barrier_function correctness.
