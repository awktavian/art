"""Tests for Improvement Proposal implementations (December 2, 2025).

Tests the learning improvement components:
- AdaptiveIBScheduler: Dynamic IB beta scheduling
- CBFAwareLossScaler: Safety-margin-based loss scaling
- fsd_loss: Function-space discrepancy loss

All implementations are in kagami.core.world_model.losses (composed.py, latent_regularization.py)
and re-exported through kagami.core.learning for convenience.

Created: December 2, 2025
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import torch
import torch.nn as nn


class TestAdaptiveIBScheduler:
    """Tests for Adaptive Information Bottleneck scheduler."""

    def test_linear_schedule(self) -> None:
        """Test linear warmup schedule."""
        from kagami.core.world_model.losses import (
            AdaptiveIBScheduler,
            LossConfig,
        )

        config = LossConfig(
            ib_beta=0.005,
            ib_beta_min=0.001,
            ib_beta_max=0.1,
            ib_warmup_steps=100,
            ib_beta_schedule="linear",
        )
        scheduler = AdaptiveIBScheduler(config)

        # At step 0, should be at beta_min
        beta0 = scheduler.get_beta()
        assert abs(beta0 - config.ib_beta_min) < 1e-6

        # Advance half way
        for _ in range(50):
            scheduler.get_beta()

        beta_mid = scheduler.get_beta()
        expected_mid = config.ib_beta_min + 0.5 * (config.ib_beta_max - config.ib_beta_min)
        assert abs(beta_mid - expected_mid) < 0.02

    def test_cyclical_schedule(self) -> None:
        """Test cyclical annealing schedule."""
        from kagami.core.world_model.losses import (
            AdaptiveIBScheduler,
            LossConfig,
        )

        config = LossConfig(
            ib_beta_min=0.001,
            ib_beta_max=0.1,
            ib_warmup_steps=100,
            ib_beta_schedule="cyclical",
        )
        scheduler = AdaptiveIBScheduler(config)

        # Track beta through full cycle
        betas = []
        for _ in range(200):
            betas.append(scheduler.get_beta())

        # Should go up then down
        max_idx = betas.index(max(betas))
        assert 90 <= max_idx <= 110  # Peak near warmup_steps

    def test_constant_schedule(self) -> None:
        """Test constant beta schedule."""
        from kagami.core.world_model.losses import (
            AdaptiveIBScheduler,
            LossConfig,
        )

        config = LossConfig(
            ib_beta=0.05,
            ib_beta_schedule="constant",
        )
        scheduler = AdaptiveIBScheduler(config)

        # Should always return the constant beta
        for _ in range(100):
            assert abs(scheduler.get_beta() - 0.05) < 1e-6

    def test_state_dict(self) -> None:
        """Test state serialization."""
        from kagami.core.world_model.losses import (
            AdaptiveIBScheduler,
            LossConfig,
        )

        config = LossConfig(ib_beta_schedule="adaptive")
        scheduler1 = AdaptiveIBScheduler(config)

        for _ in range(50):
            scheduler1.get_beta(rate=1.0, distortion=2.0)

        state = scheduler1.state_dict()

        scheduler2 = AdaptiveIBScheduler(config)
        scheduler2.load_state_dict(state)

        assert scheduler1.step == scheduler2.step
        assert scheduler1._current_beta == scheduler2._current_beta


class TestCBFAwareLossScaler:
    """Tests for CBF-aware loss scaling."""

    def test_safe_region_no_scaling(self) -> None:
        """Test no scaling when in safe region."""
        from kagami.core.world_model.losses import (
            CBFAwareLossScaler,
            LossConfig,
        )

        config = LossConfig(cbf_aware_scaling=True, cbf_safety_sensitivity=1.0)
        scaler = CBFAwareLossScaler(config)

        weights = {"prediction": 1.0, "safety_loss": 0.1, "empowerment": 0.1}

        # High safety margin - should not scale
        scaled = scaler.scale_weights(weights, safety_margin=0.8)

        assert abs(scaled["prediction"] - 1.0) < 1e-6
        assert abs(scaled["safety_loss"] - 0.1) < 1e-6

    def test_danger_zone_scaling(self) -> None:
        """Test scaling when in danger zone."""
        from kagami.core.world_model.losses import (
            CBFAwareLossScaler,
            LossConfig,
        )

        config = LossConfig(cbf_aware_scaling=True, cbf_safety_sensitivity=1.0)
        scaler = CBFAwareLossScaler(config)

        weights = {"prediction": 1.0, "safety_loss": 0.1, "cbf_weight": 0.05}

        # Low safety margin - should scale
        scaled = scaler.scale_weights(weights, safety_margin=0.1)

        # Non-safety losses should be reduced
        assert scaled["prediction"] < 1.0

        # Safety losses should be boosted
        assert scaled["safety_loss"] > 0.1
        assert scaled["cbf_weight"] > 0.05

    def test_disabled_returns_original(self) -> None:
        """Test disabled scaler returns original weights."""
        from kagami.core.world_model.losses import (
            CBFAwareLossScaler,
            LossConfig,
        )

        config = LossConfig(cbf_aware_scaling=False)
        scaler = CBFAwareLossScaler(config)

        weights = {"prediction": 1.0, "safety_loss": 0.1}
        scaled = scaler.scale_weights(weights, safety_margin=0.1)

        assert scaled == weights


class TestFSDLoss:
    """Tests for Function-Space Discrepancy loss."""

    def test_fsd_loss_no_change(self) -> None:
        """Test FSD loss is zero when no change."""
        from kagami.core.world_model.losses import fsd_loss

        # Simple model
        model = nn.Linear(10, 5)
        batch = {"input": torch.randn(16, 10)}

        # Define a simple forward that handles dict input
        class SimpleModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.linear = nn.Linear(10, 5)

            def forward(self, x: Any) -> None:
                if isinstance(x, dict):
                    x = x["input"]
                return self.linear(x)

        model = SimpleModel()  # type: ignore[assignment]

        # Cache predictions
        old_pred = fsd_loss(model, batch, old_predictions=None)

        # Compute FSD - should be zero (no update happened)
        loss = fsd_loss(model, batch, old_predictions=old_pred)
        assert loss.item() < 1e-6

    def test_fsd_loss_after_update(self) -> None:
        """Test FSD loss is non-zero after model update."""
        from kagami.core.world_model.losses import fsd_loss

        class SimpleModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.linear = nn.Linear(10, 5)

            def forward(self, x: Any) -> None:
                if isinstance(x, dict):
                    x = x["input"]
                return self.linear(x)

        model = SimpleModel()
        batch = {"input": torch.randn(16, 10)}

        # Cache predictions
        old_pred = fsd_loss(model, batch, old_predictions=None)

        # Perturb model weights
        with torch.no_grad():
            model.linear.weight.add_(torch.randn_like(model.linear.weight) * 0.1)

        # Compute FSD - should be non-zero
        loss = fsd_loss(model, batch, old_predictions=old_pred)
        assert loss.item() > 0


class TestIntegration:
    """Integration tests for improvement proposal components."""

    def test_all_imports_from_learning(self) -> None:
        """Test all components can be imported from learning module."""
        from kagami.core.learning import (
            AdaptiveIBScheduler,
            CBFAwareLossScaler,
            fsd_loss,
            LossConfig,
        )

        # Verify types
        config = LossConfig()
        assert hasattr(config, "ib_beta_schedule")
        assert hasattr(config, "cbf_aware_scaling")
        assert hasattr(config, "fsd_weight")

    def test_all_imports_from_losses(self) -> None:
        """Test all components can be imported from losses module."""
        from kagami.core.world_model.losses import (
            AdaptiveIBScheduler,
            CBFAwareLossScaler,
            fsd_loss,
            LossConfig,
            UnifiedLossModule,
        )

        # Create unified loss module
        config = LossConfig()
        loss_module = UnifiedLossModule(config)

        assert loss_module.config.ib_beta_schedule in ["constant", "linear", "cyclical", "adaptive"]
